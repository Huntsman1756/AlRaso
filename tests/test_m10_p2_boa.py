"""M10.1 Task 11 — P2 BOA (Aragón): boa_cgi discovery + boa_html parse.

BOA's stable key is the DOCN identifier; the VERDOC CGI page is both the
preregistered lookup response (discovery) and the fetched document.
Replay uses the G0-verified fixture; no network.
"""

import json
from pathlib import Path

import pytest

from pipeline.models import FetchOutcome, ReachabilityObserved
from pipeline.profiles import load_profile
from pipeline.providers.discovery import DiscoveryError, discover
from pipeline.providers.parse import parse
from pipeline.run import run_pilot

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "pipeline" / "sources" / "boa.profile.json"
FIXTURES = ROOT / "discovery" / "evidence" / "m10.1-p2-boa" / "fixtures"
DOC = ROOT / "discovery" / "evidence" / "spain-coverage-g0" / (
    "boa-decreto-16-2022-doc.html"
)


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


def test_boa_cgi_discovery_from_verdoc_page():
    refs = discover(_profile(), _payload())
    assert len(refs) == 1
    ref = refs[0]
    assert ref.doc_id == "007922169"
    assert ref.source_id == "boa"
    assert ref.published_on == "2022-02-08"
    assert "16/2022" in ref.title
    assert "DOCN=007922169" in ref.discovery_url


def test_boa_cgi_rejects_page_without_docn():
    with pytest.raises(DiscoveryError, match="DOCN"):
        discover(
            _profile(),
            {"url": "https://www.boa.aragon.es/x", "body": b"<html/>"},
        )


def test_boa_html_parse():
    profile = _profile()
    refs = discover(profile, _payload())
    from pipeline.providers.fetch import TransportResponse, TransportRequest

    body = DOC.read_bytes()

    def transport(req: TransportRequest) -> TransportResponse:
        return TransportResponse(
            status=200, body=body,
            content_type="text/html; charset=ISO-8859-1",
        )

    from pipeline.providers.fetch import fetch

    ev = fetch(
        profile, refs[0], transport=transport,
        clock=lambda: "2026-09-13T00:00:00Z", runner_network="fixture",
    )
    assert ev.fetch_outcome is FetchOutcome.SUCCESS
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    parsed = parse(
        profile, ev, body, clock=lambda: "2026-09-13T00:00:00Z"
    )
    assert parsed.doc_id == "007922169"
    assert parsed.format == "boa_html"
    assert len(parsed.articles) > 0
    assert any("49/2015" in c for c in parsed.citations)


def test_p2_end_to_end(tmp_path):
    packet = run_pilot(
        "boa", "pn-ordesa-y-monte-perdido",
        out_dir=tmp_path / "out", fixtures_dir=FIXTURES,
        clock=lambda: "2026-09-13T00:00:00Z",
    )
    assert packet.space_id == "pn-ordesa-y-monte-perdido"
    assert packet.publication_readiness == "NO"
    bundle = json.loads(
        (tmp_path / "out" / "bundle.json").read_text("utf-8")
    )
    assert bundle["authority"] == {
        "jurisdiction": "ES-AR", "gazette": "boa",
        "cite": "Decreto 16/2022", "doc_key": "007922169",
    }
    assert bundle["fetch"]["doc_ref"]["doc_id"] == "007922169"
    assert bundle["parse"]["format"] == "boa_html"
    assert bundle["version"]["status"] == "REQUIRES_MANUAL_REVIEW"
