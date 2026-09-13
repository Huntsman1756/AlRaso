"""M10.1 Task 5 — DocumentParser contract (bocyl_xml + pdf_text route).

Boundary: parse turns already-fetched bytes into ParsedInstrument —
structural parsing only. No network, no reachability, no version
resolution, no effective dates, no legal interpretation, no publication.

``annexes_present`` comes only from real structural evidence in the XML:
an ``<anexos>``/``<anexo>`` element, or the publisher's own completeness
marker ``Este documento contiene imágenes`` (BOCyL emits it when the XML
is not the complete official rendering — G0: PRUG 430pp is PDF-only).
"""

import ast
import hashlib
import inspect
from pathlib import Path

import pytest

import pipeline.providers.parse as parse_mod
from pipeline.models import (
    DocumentEvidence,
    DocumentRef,
    FetchOutcome,
    ReachabilityObserved,
)
from pipeline.profiles import SourceProfile, load_profile
from pipeline.providers.parse import (
    ParseError,
    PdfText,
    extract_pdf_text,
    parse,
    pdf_text_available,
)

ROOT = Path(__file__).resolve().parents[1]
G0 = ROOT / "discovery" / "evidence" / "spain-coverage-g0"
PROFILE_JSON = ROOT / "pipeline" / "sources" / "bocyl.profile.json"
XML_FIXTURE = G0 / "bocyl-17-2025-head.xml"

FIXED_NOW = "2026-09-13T13:00:00Z"


def _body() -> bytes:
    return XML_FIXTURE.read_bytes()


def _evidence(body: bytes) -> DocumentEvidence:
    ref = DocumentRef(
        source_id="bocyl",
        doc_id="BOCYL-D-15122025-1",
        published_on="2025-12-15",
        title="Decreto 17/2025",
        issuer="JCyL",
        discovery_url="https://bocyl.jcyl.es/x/BOCYL-D-15122025-1.xml",
    )
    return DocumentEvidence(
        doc_ref=ref,
        method_recipe_id="get_simple",
        fetched_at=FIXED_NOW,
        fetched_from=ref.discovery_url,
        http_status=200,
        content_marker_ok=True,
        bytes_sha256=hashlib.sha256(body).hexdigest(),
        content_type="application/xml",
        fetch_outcome=FetchOutcome.SUCCESS,
        observed_at=FIXED_NOW,
        evidence_sha256=hashlib.sha256(body).hexdigest(),
        reachability_observed=ReachabilityObserved.REACHABLE,
    )


def _profile() -> SourceProfile:
    return load_profile(PROFILE_JSON)


def test_bocyl_fixture_parses_to_instrument():
    inst = parse(
        _profile(), _evidence(_body()), _body(), clock=lambda: FIXED_NOW
    )
    assert inst.doc_id == "BOCYL-D-15122025-1"
    assert inst.format == "bocyl_xml"
    assert inst.extracted_at == FIXED_NOW
    assert inst.parser_version.startswith("bocyl_xml/")
    refs = [a["ref"] for a in inst.articles]
    assert any("Artículo único" in r for r in refs)


def test_annexes_present_from_structural_marker():
    inst = parse(
        _profile(), _evidence(_body()), _body(), clock=lambda: FIXED_NOW
    )
    # The fixture carries the publisher completeness marker — G0 proves the
    # 430pp PRUG annex lives only in the sibling PDF.
    assert inst.annexes_present is True


def test_annexes_absent_without_marker():
    body = _body().replace(b"Este documento contiene im", b"Este documento no dice nada")
    assert b"contiene im" not in body
    inst = parse(_profile(), _evidence(body), body, clock=lambda: FIXED_NOW)
    assert inst.annexes_present is False


def test_articles_order_is_deterministic():
    a = parse(_profile(), _evidence(_body()), _body(), clock=lambda: FIXED_NOW)
    b = parse(_profile(), _evidence(_body()), _body(), clock=lambda: FIXED_NOW)
    assert a == b
    assert [x["order"] for x in a.articles] == list(range(len(a.articles)))


def test_citations_are_mechanical_and_deduped():
    inst = parse(
        _profile(), _evidence(_body()), _body(), clock=lambda: FIXED_NOW
    )
    assert "Ley 16/1995" in inst.citations
    assert len(inst.citations) == len(set(inst.citations))


def test_malformed_xml_fails_explicit():
    body = _body()[:2000]  # truncated mid-document
    with pytest.raises(ParseError):
        parse(_profile(), _evidence(body), body, clock=lambda: FIXED_NOW)


def test_valid_xml_missing_required_fields_fails():
    body = (
        b'<?xml version="1.0"?><disposicion>'
        b"<numeroEdicion>1/2025</numeroEdicion><contenido>"
        b"<titulo>x</titulo><texto><p>y</p></texto></contenido>"
        b"</disposicion>"
    )
    with pytest.raises(ParseError, match="numeroOficial"):
        parse(_profile(), _evidence(body), body, clock=lambda: FIXED_NOW)


def test_wrong_root_fails():
    body = b'<?xml version="1.0"?><other><x/></other>'
    with pytest.raises(ParseError, match="disposicion"):
        parse(_profile(), _evidence(body), body, clock=lambda: FIXED_NOW)


def test_doctype_and_entities_rejected():
    body = (
        b'<?xml version="1.0"?>\n'
        b'<!DOCTYPE disposicion [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n'
        b"<disposicion><numeroOficial>1</numeroOficial>"
        b"<fechaPublicacion>2025-01-01</fechaPublicacion><contenido>"
        b"<titulo>&xxe;</titulo><texto><p>t</p></texto></contenido>"
        b"</disposicion>"
    )
    with pytest.raises(ParseError, match="DOCTYPE|ENTITY"):
        parse(_profile(), _evidence(body), body, clock=lambda: FIXED_NOW)


def test_parse_requires_successful_fetch_and_matching_bytes():
    # Fetch failure evidence must not be parsed.
    bad = DocumentEvidence(
        doc_ref=_evidence(b"x").doc_ref,
        method_recipe_id="get_simple",
        fetched_at=FIXED_NOW,
        fetched_from="https://x.invalid",
        http_status=None,
        content_marker_ok=False,
        bytes_sha256="",
        content_type=None,
        fetch_outcome=FetchOutcome.TIMEOUT,
        observed_at=FIXED_NOW,
        evidence_sha256="",
        reachability_observed=ReachabilityObserved.UNREACHABLE,
    )
    with pytest.raises(ParseError, match="SUCCESS"):
        parse(_profile(), bad, b"", clock=lambda: FIXED_NOW)

    # Bytes must match the evidence digest — no parsing alien content.
    with pytest.raises(ParseError, match="sha256|digest"):
        parse(
            _profile(), _evidence(_body()), b"different bytes",
            clock=lambda: FIXED_NOW,
        )


def test_unknown_format_fails_explicit():
    profile = SourceProfile(
        source_id="x",
        jurisdiction="ES-CL",
        kind="gazette",
        discovery={},
        fetch={},
        parse={"format": "wat"},
        versioning={},
        reachability={},
    )
    with pytest.raises(ParseError, match="wat"):
        parse(profile, _evidence(_body()), _body(), clock=lambda: FIXED_NOW)


def test_pdf_text_with_fake_runner():
    def fake_runner(cmd, stdin_bytes):
        assert cmd[0] == "pdftotext"
        return 0, b"Texto del anexo PRUG\n"

    result = extract_pdf_text(b"%PDF-1.4 fake", runner=fake_runner)
    assert isinstance(result, PdfText)
    assert result.available is True
    assert result.text == "Texto del anexo PRUG"


def test_pdf_text_missing_binary_is_clean_false():
    def no_pdftotext(cmd, stdin_bytes):
        raise FileNotFoundError("pdftotext")

    result = extract_pdf_text(b"%PDF-1.4 fake", runner=no_pdftotext)
    assert result.available is False
    assert result.reason == "pdftotext_missing"
    assert result.text == ""


def test_pdf_without_text_layer_is_explicit_not_ocr():
    def empty_runner(cmd, stdin_bytes):
        return 0, b"   \n"

    result = extract_pdf_text(b"%PDF-1.4 empty", runner=empty_runner)
    assert result.available is True
    assert result.text == ""
    assert result.reason == "empty_text_layer"


def test_pdf_text_failure_is_explicit():
    def failing(cmd, stdin_bytes):
        return 1, b""

    result = extract_pdf_text(b"%PDF-1.4 bad", runner=failing)
    assert result.available is False
    assert result.reason == "pdftotext_failed"


def test_pdf_text_available_helper_reflects_binary(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert pdf_text_available() is False
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftotext")
    assert pdf_text_available() is True


def test_no_network_and_no_layer_violations():
    tree = ast.parse(inspect.getsource(parse_mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
    forbidden = {"urllib", "http", "socket", "requests", "httpx"}
    assert not imported & forbidden
    src = inspect.getsource(parse_mod)
    for layer in ("providers.discovery", "providers.fetch", "providers.version"):
        assert layer not in src


def test_no_jurisdiction_branching():
    src = inspect.getsource(parse_mod)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
