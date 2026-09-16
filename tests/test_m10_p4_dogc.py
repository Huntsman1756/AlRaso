"""M10.1 Task 13 — P4 DOGC (Catalunya): Socrata discovery + ELI->AKN.

Discovery queries the analisi.transparenciacatalunya Socrata dataset;
the record's own ``url_format_xml`` ELI link is the fetch target, which
renders Akoma Ntoso. Parse extracts structure (Article/Disposició/Annex
headings) and mechanical citations from the ``<content period>`` text;
FRBRthis must contain the selected doc id. No network — the Socrata
fixture is a verbatim live capture.
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
from pipeline.providers.parse import ParseError, parse
from pipeline.run import discovery_request, run_pilot

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "pipeline" / "sources" / "dogc.profile.json"
FIXTURES = ROOT / "discovery" / "evidence" / "m10.1-p4-dogc" / "fixtures"
G0_XML = ROOT / "discovery" / "evidence" / "spain-coverage-g0" / (
    "dogc-39-2003-akn.xml"
)


def _profile():
    return load_profile(PROFILE)


def _payload():
    return json.loads(
        (FIXTURES / "discovery.json").read_text(encoding="utf-8")
    )


def test_socrata_fixture_is_verbatim_live_capture():
    """The fixture is the raw Socrata records array — no envelope."""
    payload = _payload()
    assert isinstance(payload, list)
    assert len(payload) == 3


def test_dogc_socrata_discovery_extracts_eli_refs():
    refs = discover(_profile(), _payload())
    assert len(refs) == 3
    ref = next(r for r in refs if r.doc_id == "es-ct/d/2003/02/04/39")
    assert ref.source_id == "dogc"
    assert ref.published_on == "2003-02-19"
    assert "DECRETO 39/2003" in ref.title  # _es title preferred
    assert ref.issuer == "Generalitat de Catalunya"
    assert ref.discovery_url == (
        "https://portaljuridic.gencat.cat"
        "/eli/es-ct/d/2003/02/04/39/dof/cat/xml"
    )


def test_dogc_socrata_rejects_record_without_eli():
    payload = _payload()
    payload[0]["url_format_xml"] = "https://example.org/not-an-eli"
    with pytest.raises(DiscoveryError, match="ELI"):
        discover(_profile(), payload)


def test_discovery_request_builds_socrata_query():
    profile = _profile()
    authority = {"query_key": "39/2003", "cite": "x", "gazette": "g"}
    req = discovery_request(profile, authority)
    assert req.method == "GET"
    assert req.url.startswith(
        "https://analisi.transparenciacatalunya.cat"
        "/resource/n6hn-rmy7.json?"
    )
    assert "39%2F2003" in req.url or "39/2003" in req.url


def test_eli_fetch_marks_akoma_ntoso():
    profile = _profile()
    ref = next(
        r for r in discover(profile, _payload())
        if r.doc_id == "es-ct/d/2003/02/04/39"
    )
    body = (FIXTURES / "document.bin").read_bytes()

    def transport(req: TransportRequest) -> TransportResponse:
        assert req.method == "GET"
        assert req.url == ref.discovery_url
        return TransportResponse(
            status=200, body=body,
            content_type="application/xml; charset=utf-8",
        )

    ev = fetch(
        profile, ref, transport=transport,
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    assert ev.fetch_outcome is FetchOutcome.SUCCESS
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetched_from == ref.discovery_url


def test_akn_parse_structure_and_citations():
    profile = _profile()
    ref = next(
        r for r in discover(profile, _payload())
        if r.doc_id == "es-ct/d/2003/02/04/39"
    )
    body = (FIXTURES / "document.bin").read_bytes()
    ev = fetch(
        profile, ref,
        transport=lambda req: TransportResponse(
            status=200, body=body, content_type="application/xml",
        ),
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    parsed = parse(
        profile, ev, body, clock=lambda: "2026-09-16T00:00:00Z"
    )
    assert parsed.doc_id == "es-ct/d/2003/02/04/39"
    assert parsed.format == "akn"
    assert parsed.annexes_present is True  # Annex 1-3 headings
    refs = [a["ref"] for a in parsed.articles]
    assert "Article únic" in refs
    assert "Article 41" in refs
    assert any(r.startswith("Annex") for r in refs)
    assert any("7/1988" in c for c in parsed.citations)  # Llei 7/1988
    assert any("1803/1999" in c for c in parsed.citations)


def test_akn_rejects_alien_document():
    """FRBRthis must contain the selected doc id — parsing a different
    ELI's bytes fails explicitly."""
    profile = _profile()
    ref = next(
        r for r in discover(profile, _payload())
        if r.doc_id == "es-ct/d/2003/10/08/239"
    )
    body = (FIXTURES / "document.bin").read_bytes()
    ev = fetch(
        profile, ref,
        transport=lambda req: TransportResponse(
            status=200, body=body, content_type="application/xml",
        ),
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    with pytest.raises(ParseError, match="FRBRthis"):
        parse(profile, ev, body, clock=lambda: "2026-09-16T00:00:00Z")


def test_akn_rejects_non_akn_bytes():
    profile = _profile()
    ref = discover(profile, _payload())[0]
    body = b"<html><body>not akn</body></html>"
    # bypass the content marker: feed bytes through SUCCESS evidence whose
    # digest matches — the parser's own format gate must fire.
    from pipeline.models import DocumentEvidence, RunnerNetwork

    digest = hashlib.sha256(body).hexdigest()
    ev = DocumentEvidence(
        doc_ref=ref,
        method_recipe_id="get_simple",
        fetched_at="2026-09-16T00:00:00Z",
        fetched_from=ref.discovery_url,
        http_status=200,
        content_marker_ok=True,
        bytes_sha256=digest,
        content_type="application/xml",
        fetch_outcome=FetchOutcome.SUCCESS,
        observed_at="2026-09-16T00:00:00Z",
        evidence_sha256=digest,
        runner_network=RunnerNetwork.FIXTURE,
        reachability_observed=ReachabilityObserved.REACHABLE,
    )
    with pytest.raises(ParseError, match="akomaNtoso"):
        parse(profile, ev, body, clock=lambda: "2026-09-16T00:00:00Z")


def test_p4_end_to_end(tmp_path):
    packet = run_pilot(
        "dogc", "pn-aiguestortes-i-estany-de-sant-maurici",
        out_dir=tmp_path / "out", fixtures_dir=FIXTURES,
        clock=lambda: "2026-09-16T00:00:00Z",
    )
    assert packet.space_id == "pn-aiguestortes-i-estany-de-sant-maurici"
    assert packet.publication_readiness == "NO"
    assert len(packet.chain_evidence) == 9
    bundle = json.loads(
        (tmp_path / "out" / "bundle.json").read_text("utf-8")
    )
    assert (
        bundle["fetch"]["doc_ref"]["doc_id"] == "es-ct/d/2003/02/04/39"
    )
    assert bundle["fetch"]["fetch_outcome"] == "SUCCESS"
    assert bundle["fetch"]["evidence_sha256"] == hashlib.sha256(
        G0_XML.read_bytes()
    ).hexdigest()
    assert bundle["parse"]["format"] == "akn"
    assert bundle["parse"]["annexes_present"] is True
    assert bundle["version"]["status"] == "REQUIRES_MANUAL_REVIEW"


def test_replay_is_byte_deterministic(tmp_path):
    kw = dict(
        fixtures_dir=FIXTURES, clock=lambda: "2026-09-16T00:00:00Z"
    )
    a, b = tmp_path / "a", tmp_path / "b"
    run_pilot(
        "dogc", "pn-aiguestortes-i-estany-de-sant-maurici",
        out_dir=a, **kw,
    )
    run_pilot(
        "dogc", "pn-aiguestortes-i-estany-de-sant-maurici",
        out_dir=b, **kw,
    )
    for name in ("bundle.json", "packet.json", "packet.md"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
