"""M10.1 Task 14 — P5 BOC Canarias: BOC-A-* doc page + pdf_text annex.

Discovery is ID-keyed: the archive page itself publishes the stable
``BOC-A-YYYY-NNN-NNNN`` id via its signed-PDF link, the bulletin line
``BOC - YYYY/NNN. <date>`` and the ``<h3>`` title. Fetch is a plain GET
whose content marker is the signed-PDF link (guessed URLs returning an
HTTP-200 empty page must fail it). The PDF route stays digest/text-
extract evidence through ``pdf_text`` with an injectable runner.
"""

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.models import FetchOutcome, ReachabilityObserved
from pipeline.profiles import load_profile
from pipeline.providers.discovery import DiscoveryError, discover
from pipeline.providers.fetch import (
    TransportRequest,
    TransportResponse,
    fetch,
)
from pipeline.providers.parse import (
    ParseError,
    extract_pdf_text,
    parse,
)
from pipeline.run import discovery_request, run_pilot

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "pipeline" / "sources" / "boc-canarias.profile.json"
FIXTURES = (
    ROOT / "discovery" / "evidence" / "m10.1-p5-boc-canarias" / "fixtures"
)
G0_HTML = ROOT / "discovery" / "evidence" / "spain-coverage-g0" / (
    "boc-canarias-182-2025.html"
)
PAGE_URL = "https://www.gobiernodecanarias.org/boc/2025/240/pda/4148.html"


def _profile():
    return load_profile(PROFILE)


def _payload() -> dict:
    env = json.loads(
        (FIXTURES / "discovery.json").read_text(encoding="utf-8")
    )
    return {
        "url": env["url"],
        "body": (FIXTURES / env["body_file"]).read_bytes(),
    }


def test_doc_page_discovery_extracts_stable_id():
    refs = discover(_profile(), _payload())
    assert len(refs) == 1
    ref = refs[0]
    assert ref.doc_id == "BOC-A-2025-240-4148"
    assert ref.source_id == "boc-canarias"
    assert ref.published_on == "2025-12-03"
    assert "DECRETO 182/2025" in ref.title
    assert "Teide" in ref.title
    assert "Transición Ecológica" in ref.issuer
    assert ref.discovery_url == PAGE_URL


def test_doc_page_requires_signed_pdf_link():
    """A guessed URL returning an HTTP-200 page without the BOC-A link
    must not yield a doc id (soft-404 gate at discovery level too)."""
    with pytest.raises(DiscoveryError, match="BOC-A"):
        discover(
            _profile(),
            {"url": PAGE_URL, "body": b"<html><body>error</body></html>"},
        )


def test_discovery_request_expands_archive_path():
    profile = _profile()
    authority = {
        "archive_path": "2025/240/pda/4148", "cite": "x", "gazette": "g"
    }
    req = discovery_request(profile, authority)
    assert req.method == "GET"
    assert req.url == PAGE_URL


def test_fetch_rejects_empty_soft404_page():
    profile = _profile()
    ref = discover(profile, _payload())[0]

    def transport(req: TransportRequest) -> TransportResponse:
        return TransportResponse(
            status=200, body=b"<html><body>vacio</body></html>",
            content_type="text/html",
        )

    ev = fetch(
        profile, ref, transport=transport,
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    assert ev.fetch_outcome is not FetchOutcome.SUCCESS
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE


def test_boc_canarias_html_parse():
    profile = _profile()
    ref = discover(profile, _payload())[0]
    body = (FIXTURES / "document.bin").read_bytes()
    ev = fetch(
        profile, ref,
        transport=lambda req: TransportResponse(
            status=200, body=body, content_type="text/html",
        ),
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    parsed = parse(
        profile, ev, body, clock=lambda: "2026-09-16T00:00:00Z"
    )
    assert parsed.doc_id == "BOC-A-2025-240-4148"
    assert parsed.format == "boc_canarias_html"
    assert parsed.annexes_present is True  # signed-PDF rendering exists
    assert any("212/1991" in c for c in parsed.citations)
    assert any("21/2013" in c for c in parsed.citations)


def test_pdf_text_route_with_injected_runner():
    """The signed PDF's text layer is exercised via the pdftotext route
    with a deterministic fake runner over the G0 extract."""
    profile = _profile()
    ref = discover(profile, _payload())[0]
    extract = (FIXTURES / "pdf-text-extract.txt").read_bytes()

    def fake_runner(cmd: list[str], stdin_bytes: bytes):
        assert cmd == ["pdftotext", "-", "-"]
        assert stdin_bytes == b"%PDF-fake"
        return 0, extract

    result = extract_pdf_text(b"%PDF-fake", runner=fake_runner)
    assert result.available
    assert "Decreto 182/2025" in result.text


def test_pdf_text_missing_binary_is_explicit():
    def fake_runner(cmd, stdin_bytes):
        raise FileNotFoundError

    result = extract_pdf_text(b"%PDF", runner=fake_runner)
    assert not result.available
    assert result.reason == "pdftotext_missing"


def test_p5_end_to_end(tmp_path):
    packet = run_pilot(
        "boc-canarias", "pn-teide",
        out_dir=tmp_path / "out", fixtures_dir=FIXTURES,
        clock=lambda: "2026-09-16T00:00:00Z",
    )
    assert packet.space_id == "pn-teide"
    assert packet.publication_readiness == "NO"
    assert len(packet.chain_evidence) == 9
    bundle = json.loads(
        (tmp_path / "out" / "bundle.json").read_text("utf-8")
    )
    assert (
        bundle["fetch"]["doc_ref"]["doc_id"] == "BOC-A-2025-240-4148"
    )
    assert bundle["fetch"]["fetch_outcome"] == "SUCCESS"
    assert bundle["fetch"]["evidence_sha256"] == hashlib.sha256(
        G0_HTML.read_bytes()
    ).hexdigest()
    assert bundle["parse"]["format"] == "boc_canarias_html"
    assert bundle["version"]["status"] == "REQUIRES_MANUAL_REVIEW"


def test_replay_is_byte_deterministic(tmp_path):
    kw = dict(
        fixtures_dir=FIXTURES, clock=lambda: "2026-09-16T00:00:00Z"
    )
    a, b = tmp_path / "a", tmp_path / "b"
    run_pilot("boc-canarias", "pn-teide", out_dir=a, **kw)
    run_pilot("boc-canarias", "pn-teide", out_dir=b, **kw)
    for name in ("bundle.json", "packet.json", "packet.md"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
