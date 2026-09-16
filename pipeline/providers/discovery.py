"""DiscoveryProvider: discovery responses → ``DocumentRef[]``.

Boundary (Task 3): this module only interprets discovery responses. It does
not fetch document bytes, does not evaluate content markers, does not parse
instrument contents and does not derive effective dates. Reachability
expectation stays in the profile; execution truth is recorded later by the
fetcher on ``DocumentEvidence``.

No dynamic plugin framework: a small dispatch table maps
``profile.discovery["provider"]`` to its interpreter. New sources add a
function here only when their response shape actually differs.
"""

from __future__ import annotations

import bisect
import datetime as dt
import html
import re
from typing import Any, Callable, Mapping
from urllib.parse import urljoin

from pipeline.models import DocumentRef
from pipeline.profiles import SourceProfile


class DiscoveryError(ValueError):
    """The discovery payload or profile is unusable — fail explicit, never
    emit a partially invented DocumentRef."""


# Stable native gazette id, preregistered in G0 access-matrix
# (stable_document_id = BOCYL-D-DDMMYYYY-N).
_BOCYL_DOC_ID_RE = re.compile(r"BOCYL-D-\d{8}-\d+")


def _require_str(rec: Mapping[str, Any], key: str, where: str) -> str:
    value = rec.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"{where}: missing or empty field {key!r}")
    return value.strip()


def _iso_date(raw: str, where: str, key: str) -> str:
    try:
        return dt.date.fromisoformat(raw.strip()[:10]).isoformat()
    except ValueError as exc:
        raise DiscoveryError(
            f"{where}: invalid {key} {raw!r}"
        ) from exc


def _bocyl_opendatasoft(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """Opendatasoft ``records`` response → DocumentRef[].

    Verified record fields (G0 ``bocyl-dataset-meta.json``):
    ``enlace_fichero_xml|pdf|html``, ``no_oficial``, ``fecha_publicacion``,
    ``titulo``, ``organismo``, ``rango``, ``no_edicion``.
    """
    results = payload.get("results")
    if not isinstance(results, list):
        raise DiscoveryError("opendatasoft payload requires a 'results' array")

    rows = []
    for i, rec in enumerate(results):
        where = f"results[{i}]"
        if not isinstance(rec, dict):
            raise DiscoveryError(f"{where}: record must be an object")
        xml_url = _require_str(rec, "enlace_fichero_xml", where)
        title = _require_str(rec, "titulo", where)
        issuer = _require_str(rec, "organismo", where)
        published_on = _iso_date(
            _require_str(rec, "fecha_publicacion", where),
            where,
            "fecha_publicacion",
        )
        match = _BOCYL_DOC_ID_RE.search(xml_url)
        if match is None:
            raise DiscoveryError(
                f"{where}: cannot derive doc_id from enlace_fichero_xml "
                f"{xml_url!r}"
            )
        rows.append((published_on, match.group(0), title, issuer, xml_url))

    rows.sort(key=lambda r: (r[0], r[1]))

    if window is not None:
        start, end = window
        rows = [
            r
            for r in rows
            if (start is None or r[0] >= start)
            and (end is None or r[0] <= end)
        ]

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=doc_id,
            published_on=published_on,
            title=title,
            issuer=issuer,
            discovery_url=url,
            rank=i,
        )
        for i, (published_on, doc_id, title, issuer, url) in enumerate(rows)
    ]


_BOA_DOCN_RE = re.compile(r"DOCN=(\d+)")
_BOA_TITLE_RE = re.compile(
    r'<p class="boaseccion">(.*?)</p>', re.DOTALL
)
_BOA_PUB_RE = re.compile(r"Publicado el (\d{2})/(\d{2})/(\d{4})")


def _boa_cgi(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """BRSCGI VERDOC response → DocumentRef.

    BOA's discovery key is the preregistered DOCN; the lookup response is
    the document page itself (G0 fixture ``boa-decreto-16-2022-doc.html``).
    Payload shape: ``{"url": <requested URL>, "body": <raw bytes>}`` —
    BOA serves ISO-8859-1.
    """
    url = payload.get("url")
    body = payload.get("body")
    if not isinstance(url, str) or not isinstance(body, bytes):
        raise DiscoveryError(
            "boa_cgi payload requires {'url': str, 'body': bytes}"
        )
    match = _BOA_DOCN_RE.search(url)
    if match is None:
        raise DiscoveryError(f"boa_cgi: no DOCN in request URL {url!r}")
    docn = match.group(1)

    text = body.decode("iso-8859-1", "replace")
    title_m = _BOA_TITLE_RE.search(text)
    if title_m is None:
        raise DiscoveryError("boa_cgi: no <p class=boaseccion> title")
    title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1)))
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        raise DiscoveryError("boa_cgi: empty document title")

    pub_m = _BOA_PUB_RE.search(text)
    if pub_m is None:
        raise DiscoveryError("boa_cgi: no 'Publicado el' date")
    day, month, year = pub_m.groups()
    published_on = f"{year}-{month}-{day}"
    if window is not None:
        start, end = window
        if (start and published_on < start) or (
            end and published_on > end
        ):
            return []

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=docn,
            published_on=published_on,
            title=title,
            issuer="Gobierno de Aragón",
            discovery_url=url,
            rank=0,
        )
    ]


# BOC Cantabria TOC (POST boletines.do response): bulletin date in
# ``BOC DD/MM/YYYY Núm. N``, daily full-text XML behind
# ``verXmlAction.do?idBlob=N``, and one ``verAnuncioAction.do?idAnuBlob=N``
# link per announcement whose text carries the ``BOC-YYYY-NNNN`` print id.
_BOC_TOC_DATE_RE = re.compile(
    r"BOC\s+(\d{2})/(\d{2})/(\d{4})\s*N&uacute;m\.\s*(\d+)"
)
_BOC_TOC_IDBLOB_RE = re.compile(r"verXmlAction\.do\?idBlob=(\d+)")
_BOC_TOC_ISSUER_RE = re.compile(
    r'<span class="spanH4">(.*?)</span>', re.DOTALL
)
_BOC_TOC_ANNOUNCEMENT_RE = re.compile(
    r'<p>((?:(?!</p>).)*?)</p>\s*<div class="enlacesDoc">\s*'
    r'<div class="tipoPDFanuncio">\s*'
    r'<a href="(verAnuncioAction\.do\?idAnuBlob=\d+)"[^>]*>'
    r"PDF \(BOC-(\d{4}-\d+)",
    re.DOTALL,
)


def _envelope(payload: Mapping[str, Any], provider: str) -> tuple[str, bytes]:
    """Document-response envelope ``{"url", "body"}`` used by providers
    whose discovery response is a page, not a JSON API payload."""
    url = payload.get("url")
    body = payload.get("body")
    if not isinstance(url, str) or not isinstance(body, bytes):
        raise DiscoveryError(
            f"{provider} payload requires {{'url': str, 'body': bytes}}"
        )
    return url, body


def _strip_tags(fragment: str) -> str:
    return re.sub(
        r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))
    ).strip()


def _boc_toc_post(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """BOC Cantabria TOC (``POST boletines.do`` response) → DocumentRef[].

    One ref per announcement: doc_id is the ``BOC-YYYY-NNNN`` print id the
    TOC itself publishes, ``published_on`` is the bulletin date printed in
    the TOC header, and ``discovery_url`` points at the announcement page.
    The daily ``idBlob`` (``verXmlAction``) is required to exist — it is the
    fetchable full-text XML the fetch recipe re-discovers.
    """
    url, body = _envelope(payload, "boc_toc_post")
    text = body.decode("utf-8", "replace")

    date_m = _BOC_TOC_DATE_RE.search(text)
    if date_m is None:
        raise DiscoveryError(
            "boc_toc_post: no 'BOC DD/MM/YYYY Núm. N' bulletin header"
        )
    day, month, year, _num = date_m.groups()
    published_on = f"{year}-{month}-{day}"

    if _BOC_TOC_IDBLOB_RE.search(text) is None:
        raise DiscoveryError(
            "boc_toc_post: no verXmlAction idBlob link — the daily "
            "full-text XML id is mandatory"
        )

    issuers = [
        (m.start(), _strip_tags(m.group(1)))
        for m in _BOC_TOC_ISSUER_RE.finditer(text)
    ]
    issuer_pos = [pos for pos, _ in issuers]

    rows = []
    for m in _BOC_TOC_ANNOUNCEMENT_RE.finditer(text):
        title = _strip_tags(m.group(1))
        if not title:
            raise DiscoveryError("boc_toc_post: empty announcement title")
        idx = bisect.bisect_right(issuer_pos, m.start()) - 1
        issuer = issuers[idx][1] if idx >= 0 else ""
        doc_id = f"BOC-{m.group(3)}"
        rows.append(
            (
                published_on,
                doc_id,
                title,
                issuer,
                urljoin(url, m.group(2)),
            )
        )

    rows.sort(key=lambda r: (r[0], r[1]))
    if window is not None:
        start, end = window
        rows = [
            r
            for r in rows
            if (start is None or r[0] >= start)
            and (end is None or r[0] <= end)
        ]

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=doc_id,
            published_on=published_on,
            title=title,
            issuer=issuer,
            discovery_url=doc_url,
            rank=i,
        )
        for i, (published_on, doc_id, title, issuer, doc_url) in enumerate(
            rows
        )
    ]


# DOGC Socrata (analisi.transparenciacatalunya.cat/resource/n6hn-rmy7):
# verified live 2026-09-16 — record fields ``t_tol_de_la_norma[_es]``,
# ``data_de_publicaci_del_diari``, ``n_mero_de_diari``,
# ``vig_ncia_de_la_norma``, ``url_format_xml.url`` (ELI cat XML).
_DOGC_ELI_RE = re.compile(
    r"/eli/(es-ct/[a-z]/\d{4}/\d{2}/\d{2}/[^/\"'\s]+)"
)


def _dogc_socrata(
    profile: SourceProfile,
    payload: Any,
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """Socrata records array → DocumentRef[].

    The stable doc id is the ELI path (``es-ct/d/YYYY/MM/DD/N``) taken from
    the record's own ``url_format_xml`` link — never reconstructed. The
    Spanish title field is preferred so that an ES-language cite matches.
    """
    records = payload.get("results") if isinstance(payload, dict) else None
    if records is None and isinstance(payload, list):
        records = payload
    if not isinstance(records, list):
        raise DiscoveryError(
            "dogc_socrata payload requires a records array"
        )

    rows = []
    for i, rec in enumerate(records):
        where = f"records[{i}]"
        if not isinstance(rec, dict):
            raise DiscoveryError(f"{where}: record must be an object")
        title = rec.get("t_tol_de_la_norma_es") or _require_str(
            rec, "t_tol_de_la_norma", where
        )
        if not isinstance(title, str) or not title.strip():
            raise DiscoveryError(f"{where}: empty normative title")
        link = rec.get("url_format_xml")
        if isinstance(link, dict):
            link = link.get("url")
        if not isinstance(link, str) or not link.strip():
            raise DiscoveryError(
                f"{where}: missing or empty field 'url_format_xml'"
            )
        xml_url = link.strip()
        eli_m = _DOGC_ELI_RE.search(xml_url)
        if eli_m is None:
            raise DiscoveryError(
                f"{where}: cannot derive ELI doc id from {xml_url!r}"
            )
        published_on = _iso_date(
            _require_str(rec, "data_de_publicaci_del_diari", where),
            where,
            "data_de_publicaci_del_diari",
        )
        rows.append(
            (published_on, eli_m.group(1), title.strip(), xml_url)
        )

    rows.sort(key=lambda r: (r[0], r[1]))
    if window is not None:
        start, end = window
        rows = [
            r
            for r in rows
            if (start is None or r[0] >= start)
            and (end is None or r[0] <= end)
        ]

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=doc_id,
            published_on=published_on,
            title=title,
            issuer="Generalitat de Catalunya",
            discovery_url=xml_url,
            rank=i,
        )
        for i, (published_on, doc_id, title, xml_url) in enumerate(rows)
    ]


# BOC Canarias doc page (…/boc/YYYY/NNN/[pda/]NNNN.html): bulletin line in
# <h2>, announcement title in <h3>, issuer in <h5>, signed-PDF link carries
# the stable BOC-A-YYYY-NNN-NNNN id.
_BOC_CN_TITLE_RE = re.compile(r"<h3>\s*\d+\s*-\s*(.*?)</h3>", re.DOTALL)
_BOC_CN_DATE_RE = re.compile(
    r"BOC\s*-\s*\d{4}/\d+\.\s*[^-<]*?(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})"
)
_BOC_CN_ISSUER_RE = re.compile(r"<h5>(.*?)</h5>", re.DOTALL)
_BOC_CN_PDF_RE = re.compile(
    r"sede\.gobiernodecanarias\.org/boc/(boc-a-\d{4}-\d+-\d+)\.pdf",
    re.IGNORECASE,
)

_ES_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _boc_canarias_doc(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """BOC Canarias document page → single DocumentRef.

    Discovery here is ID-keyed: the archive URL was preregistered in G0 and
    the page itself proves the ``BOC-A-YYYY-NNN-NNNN`` id via its signed-PDF
    link, the bulletin date via its ``<h2>`` line and the title via ``<h3>``.
    """
    url, body = _envelope(payload, "boc_canarias_doc")
    text = body.decode("utf-8", "replace")

    pdf_m = _BOC_CN_PDF_RE.search(text)
    if pdf_m is None:
        raise DiscoveryError(
            "boc_canarias_doc: no signed-PDF link carrying the BOC-A id"
        )
    doc_id = pdf_m.group(1).upper()

    date_m = _BOC_CN_DATE_RE.search(text)
    if date_m is None:
        raise DiscoveryError(
            "boc_canarias_doc: no 'BOC - YYYY/NNN. <date>' bulletin line"
        )
    day, month_name, year = date_m.groups()
    month = _ES_MONTHS.get(month_name.lower())
    if month is None:
        raise DiscoveryError(
            f"boc_canarias_doc: unknown month name {month_name!r}"
        )
    published_on = f"{year}-{month:02d}-{int(day):02d}"

    title_m = _BOC_CN_TITLE_RE.search(text)
    if title_m is None:
        raise DiscoveryError("boc_canarias_doc: no <h3> announcement title")
    title = _strip_tags(title_m.group(1))
    if not title:
        raise DiscoveryError("boc_canarias_doc: empty announcement title")

    issuer_m = _BOC_CN_ISSUER_RE.search(text)
    issuer = _strip_tags(issuer_m.group(1)) if issuer_m else ""

    if window is not None:
        start, end = window
        if (start and published_on < start) or (
            end and published_on > end
        ):
            return []

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=doc_id,
            published_on=published_on,
            title=title,
            issuer=issuer,
            discovery_url=url,
            rank=0,
        )
    ]


_PROVIDERS: dict[str, Callable[..., list[DocumentRef]]] = {
    "bocyl_opendatasoft": _bocyl_opendatasoft,
    "boa_cgi": _boa_cgi,
    "boc_toc_post": _boc_toc_post,
    "dogc_socrata": _dogc_socrata,
    "boc_canarias_doc": _boc_canarias_doc,
}


def discover(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None = None,
) -> list[DocumentRef]:
    """Interpret a discovery payload for ``profile`` into DocumentRef[].

    ``window`` is an optional inclusive ``(start, end)`` ISO-date filter on
    ``published_on`` supplied by the caller; either bound may be ``None``.
    """
    provider = profile.discovery.get("provider")
    handler = _PROVIDERS.get(provider)
    if handler is None:
        raise DiscoveryError(
            f"unsupported discovery provider {provider!r} — add an "
            "interpreter here only if the response shape requires it"
        )
    return handler(profile, payload, window=window)
