"""M10.1 Task 12 — P3 BOC Cantabria: POST->TOC->verXmlAction chain.

The TOC is reached by form POST (boletines.do); it publishes the bulletin
date, one verAnuncioAction?idAnuBlob link per announcement carrying the
BOC-YYYY-NNNN print id, and the daily full-text XML behind
verXmlAction?idBlob. Fetch replays POST->GET; parse selects the target
<disposicion> from the daily XML by its own emitted ids. No network.
"""

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
PROFILE = ROOT / "pipeline" / "sources" / "boc-cantabria.profile.json"
FIXTURES = (
    ROOT / "discovery" / "evidence" / "m10.1-p3-boc-cantabria" / "fixtures"
)
G0_XML = ROOT / "discovery" / "evidence" / "spain-coverage-g0" / (
    "boc-cantabria-2026-08-04.xml"
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


def test_toc_post_discovery_extracts_all_announcements():
    refs = discover(_profile(), _payload())
    assert len(refs) == 22
    ref = next(r for r in refs if r.doc_id == "BOC-2026-6207")
    assert ref.source_id == "boc-cantabria"
    assert ref.published_on == "2026-08-04"
    assert "Decreto 57/2026" in ref.title
    assert "Picos de Europa" in ref.title
    assert ref.issuer == "Consejo de Gobierno"
    assert "idAnuBlob=438988" in ref.discovery_url


def test_toc_post_requires_bulletin_header_and_idblob():
    profile = _profile()
    with pytest.raises(DiscoveryError, match="bulletin header"):
        discover(
            profile,
            {
                "url": "https://boc.cantabria.es/boces/boletines.do",
                "body": b"<html>verXmlAction.do?idBlob=1</html>",
            },
        )
    with pytest.raises(DiscoveryError, match="idBlob"):
        discover(
            profile,
            {
                "url": "https://boc.cantabria.es/boces/boletines.do",
                "body": b"BOC 04/08/2026 N&uacute;m. 148",
            },
        )


def test_discovery_request_is_profile_driven_post():
    profile = _profile()
    authority = {"bulletin_date": "04/08/2026", "cite": "x", "gazette": "g"}
    req = discovery_request(profile, authority)
    assert req.method == "POST"
    assert req.url == "https://boc.cantabria.es/boces/boletines.do"
    assert req.body == (
        b"boletinBean.fecBolString=04%2F08%2F2026"
        b"&boletinBean.tipoBol=&boton=Buscar"
    )
    assert req.headers["Content-Type"] == (
        "application/x-www-form-urlencoded"
    )


def test_post_then_get_fetch_replays_toc_then_xml():
    profile = _profile()
    ref = discover(profile, _payload())
    ref = next(r for r in ref if r.doc_id == "BOC-2026-6207")

    calls: list[TransportRequest] = []

    def transport(req: TransportRequest) -> TransportResponse:
        calls.append(req)
        if req.method == "POST":
            return TransportResponse(
                status=200,
                body=(FIXTURES / "toc-post.html").read_bytes(),
                content_type="text/html",
            )
        return TransportResponse(
            status=200,
            body=(FIXTURES / "document.bin").read_bytes(),
            content_type="application/xml; charset=utf-8",
        )

    ev = fetch(
        profile, ref, transport=transport,
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    assert ev.fetch_outcome is FetchOutcome.SUCCESS
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert [c.method for c in calls] == ["POST", "GET"]
    assert calls[0].url == "https://boc.cantabria.es/boces/boletines.do"
    assert b"boletinBean.fecBolString=04%2F08%2F2026" in calls[0].body
    assert calls[1].url == (
        "https://boc.cantabria.es/boces/verXmlAction.do?idBlob=46085"
    )
    assert ev.fetched_from == calls[1].url


def test_boc_daily_xml_parse_selects_target_disposicion():
    from pipeline.run import _fixture_transport

    profile = _profile()
    ref = discover(profile, _payload())
    ref = next(r for r in ref if r.doc_id == "BOC-2026-6207")
    body = (FIXTURES / "document.bin").read_bytes()

    ev = fetch(
        profile, ref,
        transport=_fixture_transport(FIXTURES),
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    parsed = parse(
        profile, ev, body, clock=lambda: "2026-09-16T00:00:00Z"
    )
    assert parsed.doc_id == "BOC-2026-6207"
    assert parsed.format == "boc_daily_xml"
    assert parsed.annexes_present is True  # anexos="1" on the disposition
    assert len(parsed.articles) > 0
    assert any("16/1995" in c for c in parsed.citations)


def test_boc_daily_xml_rejects_unknown_doc_id():
    from pipeline.run import _fixture_transport

    profile = _profile()
    ref = discover(profile, _payload())[0]
    ref = type(ref)(
        source_id=ref.source_id, doc_id="BOC-2999-9999",
        published_on=ref.published_on, title=ref.title,
        issuer=ref.issuer, discovery_url=ref.discovery_url,
    )
    body = (FIXTURES / "document.bin").read_bytes()
    ev = fetch(
        profile, ref,
        transport=_fixture_transport(FIXTURES),
        clock=lambda: "2026-09-16T00:00:00Z", runner_network="fixture",
    )
    with pytest.raises(ParseError, match="no <disposicion>"):
        parse(profile, ev, body, clock=lambda: "2026-09-16T00:00:00Z")


def test_timeout_is_unreachable_not_absent():
    from pipeline.providers.fetch import TransportTimeout

    profile = _profile()
    ref = discover(profile, _payload())[0]

    def transport(req):
        raise TransportTimeout("timed out")

    ev = fetch(
        profile, ref, transport=transport,
        clock=lambda: "2026-09-16T00:00:00Z",
        runner_network="foreign_ci",
    )
    assert ev.fetch_outcome is FetchOutcome.TIMEOUT
    assert ev.reachability_observed is ReachabilityObserved.UNREACHABLE
    assert ev.runner_network == "foreign_ci"


def test_p3_end_to_end(tmp_path):
    packet = run_pilot(
        "boc-cantabria", "pn-picos-de-europa",
        out_dir=tmp_path / "out", fixtures_dir=FIXTURES,
        clock=lambda: "2026-09-16T00:00:00Z",
    )
    assert packet.space_id == "pn-picos-de-europa"
    assert packet.publication_readiness == "NO"
    assert len(packet.chain_evidence) == 9
    bundle = json.loads(
        (tmp_path / "out" / "bundle.json").read_text("utf-8")
    )
    assert bundle["fetch"]["doc_ref"]["doc_id"] == "BOC-2026-6207"
    assert bundle["fetch"]["fetch_outcome"] == "SUCCESS"
    assert bundle["fetch"]["fetched_from"].endswith(
        "verXmlAction.do?idBlob=46085"
    )
    import hashlib
    assert bundle["fetch"]["evidence_sha256"] == hashlib.sha256(
        G0_XML.read_bytes()
    ).hexdigest()
    assert bundle["parse"]["format"] == "boc_daily_xml"
    assert bundle["parse"]["annexes_present"] is True
    assert bundle["version"]["status"] == "REQUIRES_MANUAL_REVIEW"


def test_replay_is_byte_deterministic(tmp_path):
    kw = dict(
        fixtures_dir=FIXTURES, clock=lambda: "2026-09-16T00:00:00Z"
    )
    a, b = tmp_path / "a", tmp_path / "b"
    run_pilot("boc-cantabria", "pn-picos-de-europa", out_dir=a, **kw)
    run_pilot("boc-cantabria", "pn-picos-de-europa", out_dir=b, **kw)
    for name in ("bundle.json", "packet.json", "packet.md"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
