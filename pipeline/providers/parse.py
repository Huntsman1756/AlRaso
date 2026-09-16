"""DocumentParser: fetched bytes → ParsedInstrument (structure only).

Boundary (Task 5): mechanical extraction of structure and citations from
bytes already obtained. No network access, no reachability, no version
resolution, no effective dates, no legal interpretation, no publication.

XML safety: DOCTYPE/ENTITY declarations are rejected outright; parsing is
stdlib ElementTree which never resolves external resources.

``pdf_text`` route: the external ``pdftotext`` binary is optional. When it
is absent the result is a clean ``available=False`` — no opaque exception
and no OCR fallback in M10.1.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from pipeline.models import (
    DocumentEvidence,
    FetchOutcome,
    ParsedInstrument,
)
from pipeline.profiles import SourceProfile

PARSER_VERSION_BOCYL_XML = "bocyl_xml/0.1"
PARSER_VERSION_PDF_TEXT = "pdf_text/0.1"
PARSER_VERSION_BOA_HTML = "boa_html/0.1"
PARSER_VERSION_BOC_DAILY_XML = "boc_daily_xml/0.1"
PARSER_VERSION_AKN = "akn/0.1"
PARSER_VERSION_BOC_CANARIAS_HTML = "boc_canarias_html/0.1"

# BOCyL emits this canonical sentence when the XML is not the complete
# official rendering of the disposition (annex/image content lives in the
# PDF fichero — G0: PRUG 430 pp is PDF-only).
_BOCYL_INCOMPLETE_MARKER = "Este documento contiene imágenes"

_HEADING_RE = re.compile(
    r"^(Artículo\b|Artículos\b|DISPOSICIÓN\b|Disposición\b|ANEXO\b|Anexo\b)"
)

# Mechanical citation extraction only — declared-type + number/year
# patterns. Norm types span the languages Spanish official gazettes publish
# in (Spanish + Catalan at M10.1); extraction stays mechanical — a matched
# string is a citation mention, never a legal claim.
_CITATION_RE = re.compile(
    r"\b(?:Ley Orgánica|Ley|Real Decreto-ley|Real Decreto|"
    r"Decreto Legislativo|Decreto|Reglamento|Orden|Directiva|Resolución|"
    r"Llei orgànica|Llei|Reial decret|Decret|Ordre)"
    r"\s+(?:\([^)]*\)\s*)?n?[°º]?\s*(\d[\d./]*/\d{4}|\d{4})"
)


class ParseError(ValueError):
    """The bytes cannot be parsed into the declared format — explicit
    failure, never a partially invented ParsedInstrument."""


@dataclass(frozen=True)
class PdfText:
    """Result of the optional ``pdftotext`` route.

    ``available`` is False only when the tool could not run (missing binary
    or non-zero exit). A run that produces no usable text is explicit via
    ``reason="empty_text_layer"`` — never silently OCR'd.
    """

    available: bool
    text: str
    reason: str | None = None


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pdf_text_available() -> bool:
    """Whether the external ``pdftotext`` binary is on PATH."""
    return shutil.which("pdftotext") is not None


def _default_runner(cmd: list[str], stdin_bytes: bytes) -> tuple[int, bytes]:
    proc = subprocess.run(
        cmd,
        input=stdin_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode, proc.stdout


def extract_pdf_text(
    body: bytes,
    *,
    runner: Callable[[list[str], bytes], tuple[int, bytes]] | None = None,
) -> PdfText:
    """Extract a PDF text layer via ``pdftotext`` (stdin → stdout).

    ``runner`` is injectable for deterministic offline tests.
    """
    if runner is None:
        if not pdf_text_available():
            return PdfText(
                available=False, text="", reason="pdftotext_missing"
            )
        runner = _default_runner
    try:
        rc, out = runner(["pdftotext", "-", "-"], body)
    except FileNotFoundError:
        return PdfText(available=False, text="", reason="pdftotext_missing")
    except OSError:
        return PdfText(available=False, text="", reason="pdftotext_failed")
    if rc != 0:
        return PdfText(available=False, text="", reason="pdftotext_failed")
    text = out.decode("utf-8", "replace").strip()
    if not text:
        return PdfText(available=True, text="", reason="empty_text_layer")
    return PdfText(available=True, text=text)


def _mechanical_citations(text: str) -> tuple[str, ...]:
    seen: list[str] = []
    for match in _CITATION_RE.finditer(text):
        cite = " ".join(match.group(0).split())
        if cite not in seen:
            seen.append(cite)
    return tuple(seen)


def _require(parent: ET.Element, tag: str, where: str) -> str:
    el = parent.find(tag)
    if el is None or el.text is None or not el.text.strip():
        raise ParseError(f"{where}: missing required <{tag}>")
    return el.text.strip()


def _paragraphs(texto: ET.Element) -> list[str]:
    return [
        "".join(p.itertext()).strip()
        for p in texto.iter("p")
        if "".join(p.itertext()).strip()
    ]


def _bocyl_xml(
    evidence: DocumentEvidence, body: bytes, now: str
) -> ParsedInstrument:
    """Parse a BOCyL per-disposition XML (``<disposicion>``).

    annexes_present is structural: an ``<anexos>``/``<anexo>`` element, or
    the publisher's completeness marker paragraph — never a length
    heuristic.
    """
    head = body[:1024].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise ParseError(
            "DOCTYPE/ENTITY declarations rejected — external resources are "
            "never resolved"
        )
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ParseError(f"bocyl_xml: malformed XML: {exc}") from exc
    if root.tag != "disposicion":
        raise ParseError(
            f"bocyl_xml: expected <disposicion> root, got <{root.tag}>"
        )

    _require(root, "numeroOficial", "disposicion")
    _require(root, "fechaPublicacion", "disposicion")
    contenido = root.find("contenido")
    if contenido is None:
        raise ParseError("disposicion: missing required <contenido>")
    _require(contenido, "titulo", "contenido")
    texto = contenido.find("texto")
    if texto is None:
        raise ParseError("contenido: missing required <texto>")

    paragraphs = _paragraphs(texto)
    headings = [p for p in paragraphs if _HEADING_RE.match(p)]
    articles = tuple(
        {"ref": p[:120], "order": i} for i, p in enumerate(headings)
    )
    full_text = "\n".join(paragraphs)

    annexes_present = (
        root.find(".//anexos") is not None
        or root.find(".//anexo") is not None
        or _BOCYL_INCOMPLETE_MARKER in full_text
    )

    return ParsedInstrument(
        doc_id=evidence.doc_ref.doc_id,
        format="bocyl_xml",
        annexes_present=annexes_present,
        extracted_at=now,
        parser_version=PARSER_VERSION_BOCYL_XML,
        articles=articles,
        citations=_mechanical_citations(full_text),
    )


def _pdf_text(
    evidence: DocumentEvidence,
    body: bytes,
    now: str,
    runner: Callable[[list[str], bytes], tuple[int, bytes]] | None,
) -> ParsedInstrument:
    """PDF route: extract the text layer and derive mechanical citations.

    The extracted text is transient (redistribution stays DIGEST_ONLY); the
    instrument records structure, not the full body.
    """
    result = extract_pdf_text(body, runner=runner)
    if not result.available:
        raise ParseError(f"pdf_text unavailable: {result.reason}")
    return ParsedInstrument(
        doc_id=evidence.doc_ref.doc_id,
        format="pdf_text",
        annexes_present=False,
        extracted_at=now,
        parser_version=PARSER_VERSION_PDF_TEXT,
        articles=(),
        citations=_mechanical_citations(result.text),
    )


_BOA_SCRIPT_RE = re.compile(r"<script.*?</script>", re.DOTALL | re.IGNORECASE)
_BOA_TAG_RE = re.compile(r"<[^>]+>")
_BOA_ANNEX_RE = re.compile(r"^(ANEXO|Anexo)\b")


def _boa_html(
    evidence: DocumentEvidence, body: bytes, now: str
) -> ParsedInstrument:
    """Parse a BOA BRSCGI VERDOC page (ISO-8859-1 HTML).

    Structure: title in ``<p class="boaseccion">``, the decree body as
    ``<P>``-separated paragraphs after the ``Emisor:`` block. Articles are
    structural headings (Artículo/Disposición); ``annexes_present`` only
    from an ANEXO heading — no length heuristics.
    """
    text = body.decode("iso-8859-1", "replace")
    if 'class="boaseccion"' not in text:
        raise ParseError("boa_html: no boaseccion title block")
    emisor = text.find("Emisor:")
    if emisor < 0:
        raise ParseError("boa_html: no 'Emisor:' block — not a doc page")
    tail = _BOA_SCRIPT_RE.sub(" ", text[emisor:])
    paragraphs = [
        re.sub(r"\s+", " ", _BOA_TAG_RE.sub(" ", html.unescape(c))).strip()
        for c in re.split(r"<[Pp]>", tail)
    ]
    paragraphs = [p for p in paragraphs if p]
    headings = [p for p in paragraphs if _HEADING_RE.match(p)]
    articles = tuple(
        {"ref": p[:120], "order": i} for i, p in enumerate(headings)
    )
    full_text = "\n".join(paragraphs)
    return ParsedInstrument(
        doc_id=evidence.doc_ref.doc_id,
        format="boa_html",
        annexes_present=any(_BOA_ANNEX_RE.match(p) for p in paragraphs),
        extracted_at=now,
        parser_version=PARSER_VERSION_BOA_HTML,
        articles=articles,
        citations=_mechanical_citations(full_text),
    )


def _xml_root(body: bytes, fmt: str) -> ET.Element:
    head = body[:1024].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise ParseError(
            "DOCTYPE/ENTITY declarations rejected — external resources are "
            "never resolved"
        )
    try:
        return ET.fromstring(body)
    except ET.ParseError as exc:
        raise ParseError(f"{fmt}: malformed XML: {exc}") from exc


def _boc_daily_xml(
    evidence: DocumentEvidence, body: bytes, now: str
) -> ParsedInstrument:
    """Parse a BOC Cantabria daily XML and select one ``<disposicion>``.

    The daily bundle wraps every announcement of the bulletin; the target
    disposition is matched against the identity ids the source itself
    emits — ``numeroExp`` (CVE-YYYY-NNNN), the ``numExpediente`` attribute
    (YYYY-NNNN) or its ``BOC-``/``CVE-`` print forms — never by position.
    ``annexes_present`` is the disposition's own ``anexos`` attribute.
    """
    root = _xml_root(body, "boc_daily_xml")
    if root.tag != "root":
        raise ParseError(
            f"boc_daily_xml: expected <root>, got <{root.tag}>"
        )

    doc_id = evidence.doc_ref.doc_id
    match = None
    for disp in root.iter("disposicion"):
        expediente = (disp.get("numExpediente") or "").strip()
        numero_exp = (disp.findtext("numeroExp") or "").strip()
        candidates = {
            c for c in {
                numero_exp,
                expediente,
                f"CVE-{expediente}" if expediente else "",
                f"BOC-{expediente}" if expediente else "",
            } if c
        }
        if doc_id in candidates:
            match = disp
            break
    if match is None:
        raise ParseError(
            f"boc_daily_xml: no <disposicion> for doc_id {doc_id!r}"
        )

    texto = match.find("texto")
    paragraphs = _paragraphs(texto) if texto is not None else []
    headings = [p for p in paragraphs if _HEADING_RE.match(p)]
    articles = tuple(
        {"ref": p[:120], "order": i} for i, p in enumerate(headings)
    )
    return ParsedInstrument(
        doc_id=doc_id,
        format="boc_daily_xml",
        annexes_present=(match.get("anexos") == "1"),
        extracted_at=now,
        parser_version=PARSER_VERSION_BOC_DAILY_XML,
        articles=articles,
        citations=_mechanical_citations("\n".join(paragraphs)),
    )


_AKN_NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"
_AKN_HEADING_RE = re.compile(
    r"^(Article\b|Artícle\b|Disposició\b|Disposicions\b|Annex\b|ANNEX\b)"
)
_AKN_P_RE = re.compile(r"<[Pp](?:\s[^>]*)?>")
_TAG_RE = re.compile(r"<[^>]+>")


def _akn(evidence: DocumentEvidence, body: bytes, now: str) -> ParsedInstrument:
    """Parse an Akoma Ntoso document (ELI ``/xml`` rendering).

    The gencat rendering carries the normative text HTML-escaped inside the
    ``<content period>`` attribute — one ``<P>`` block per paragraph.
    Structural headings (Article/Disposició/Annex) and citations are
    extracted mechanically; ``FRBRthis`` values must contain the selected
    doc id so the parsed instrument is bound to the chosen ELI.
    """
    root = _xml_root(body, "akn")
    if root.tag != f"{_AKN_NS}akomaNtoso":
        raise ParseError(
            f"akn: expected akomaNtoso root, got <{root.tag}>"
        )

    doc_id = evidence.doc_ref.doc_id
    frbr_values = [
        el.get("value") or "" for el in root.iter(f"{_AKN_NS}FRBRthis")
    ]
    if not any(f"/eli/{doc_id}" in value for value in frbr_values):
        raise ParseError(
            f"akn: no FRBRthis value contains doc id {doc_id!r}"
        )

    paragraphs: list[str] = []
    for content in root.iter(f"{_AKN_NS}content"):
        period = content.get("period")
        if not period:
            continue
        raw = html.unescape(period)
        for chunk in _AKN_P_RE.split(raw):
            cleaned = re.sub(
                r"\s+", " ", html.unescape(_TAG_RE.sub(" ", chunk))
            ).strip()
            if cleaned:
                paragraphs.append(cleaned)
    if not paragraphs:
        raise ParseError("akn: no <content period> paragraphs found")

    headings = [p for p in paragraphs if _AKN_HEADING_RE.match(p)]
    articles = tuple(
        {"ref": p[:120], "order": i} for i, p in enumerate(headings)
    )
    return ParsedInstrument(
        doc_id=doc_id,
        format="akn",
        annexes_present=any(
            re.match(r"^(Annex|ANNEX)\b", p) for p in paragraphs
        ),
        extracted_at=now,
        parser_version=PARSER_VERSION_AKN,
        articles=articles,
        citations=_mechanical_citations("\n".join(paragraphs)),
    )


# BOC Canarias page-structure patterns — defined independently per layer so
# PARSE never imports from DISCOVERY (the layers must stay separable).
_BOC_CN_TITLE_RE = re.compile(r"<h3>\s*\d+\s*-\s*(.*?)</h3>", re.DOTALL)
_BOC_CN_DATE_RE = re.compile(
    r"BOC\s*-\s*\d{4}/\d+\.\s*[^-<]*?(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})"
)
_BOC_CN_PDF_RE = re.compile(
    r"sede\.gobiernodecanarias\.org/boc/(boc-a-\d{4}-\d+-\d+)\.pdf",
    re.IGNORECASE,
)
_BOC_CN_BODY_RE = re.compile(
    r'<p class="justificado">(.*?)</p>', re.DOTALL
)


def _boc_canarias_html(
    evidence: DocumentEvidence, body: bytes, now: str
) -> ParsedInstrument:
    """Parse a BOC Canarias document page (UTF-8 HTML).

    The archive page is a document summary (issuer, title, justification)
    with a signed-PDF link carrying the ``BOC-A-*`` id. Structure is the
    ``<p class="justificado">`` body; ``annexes_present`` records that the
    page publishes a separate signed-PDF rendering — the PDF itself is
    evidence via the ``pdf_text`` route, not redistributed.
    """
    text = body.decode("utf-8", "replace")
    if _BOC_CN_TITLE_RE.search(text) is None:
        raise ParseError("boc_canarias_html: no <h3> announcement title")
    if _BOC_CN_DATE_RE.search(text) is None:
        raise ParseError("boc_canarias_html: no BOC bulletin line")
    pdf_m = _BOC_CN_PDF_RE.search(text)

    paragraphs = [
        re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", c))).strip()
        for c in _BOC_CN_BODY_RE.findall(text)
    ]
    paragraphs = [p for p in paragraphs if p]
    headings = [p for p in paragraphs if _HEADING_RE.match(p)]
    articles = tuple(
        {"ref": p[:120], "order": i} for i, p in enumerate(headings)
    )
    return ParsedInstrument(
        doc_id=evidence.doc_ref.doc_id,
        format="boc_canarias_html",
        annexes_present=pdf_m is not None,
        extracted_at=now,
        parser_version=PARSER_VERSION_BOC_CANARIAS_HTML,
        articles=articles,
        citations=_mechanical_citations("\n".join(paragraphs)),
    )


_PARSERS: dict[str, Callable[..., ParsedInstrument]] = {
    "bocyl_xml": _bocyl_xml,
    "boa_html": _boa_html,
    "boc_daily_xml": _boc_daily_xml,
    "akn": _akn,
    "boc_canarias_html": _boc_canarias_html,
}


def parse(
    profile: SourceProfile,
    evidence: DocumentEvidence,
    body: bytes,
    *,
    clock: Callable[[], str] = _utc_now_iso,
    pdf_runner: Callable[[list[str], bytes], tuple[int, bytes]] | None = None,
) -> ParsedInstrument:
    """Parse fetched ``body`` bytes per ``profile.parse["format"]``.

    Only SUCCESS evidence whose digest matches ``body`` is parsed — the
    parser never works on failed fetches or alien bytes.
    """
    if evidence.fetch_outcome is not FetchOutcome.SUCCESS:
        raise ParseError(
            f"refusing to parse fetch_outcome={evidence.fetch_outcome} — "
            "only SUCCESS evidence carries a document body"
        )
    if hashlib.sha256(body).hexdigest() != evidence.bytes_sha256:
        raise ParseError(
            "body bytes do not match evidence sha256 digest"
        )

    fmt = profile.parse["format"]
    now = clock()
    if fmt == "pdf_text":
        return _pdf_text(evidence, body, now, pdf_runner)
    handler = _PARSERS.get(fmt)
    if handler is None:
        raise ParseError(f"unsupported parse format {fmt!r}")
    return handler(evidence, body, now)
