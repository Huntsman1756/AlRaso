"""M10.1 Task 4 — generic recipe-driven DocumentFetcher contract.

Boundary: fetch turns a DocumentRef into DocumentEvidence via an injected
transport. No parsing, no legal interpretation, no version resolution, no
discovery, no jurisdiction branching. Marker checks are mechanical byte
containment only — real parsing starts in Task 5.

Frozen result table (plan §7 fix 2): reachability_observed and fetch_outcome
are separate dimensions — an HTTP 404 is REACHABLE + HTTP_ERROR.
"""

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import pipeline.providers.fetch as fetch_mod
from pipeline.models import (
    DocumentRef,
    FetchOutcome,
    ReachabilityObserved,
    RunnerNetwork,
)
from pipeline.profiles import SourceProfile, load_profile
from pipeline.providers.fetch import (
    FetchError,
    TransportError,
    TransportRequest,
    TransportResponse,
    TransportTimeout,
    fetch,
)

ROOT = Path(__file__).resolve().parents[1]
G0 = ROOT / "discovery" / "evidence" / "spain-coverage-g0"
PROFILE_JSON = ROOT / "pipeline" / "sources" / "bocyl.profile.json"
XML_FIXTURE = G0 / "bocyl-17-2025-head.xml"

FIXED_NOW = "2026-09-13T12:00:00Z"


def _doc_ref() -> DocumentRef:
    return DocumentRef(
        source_id="bocyl",
        doc_id="BOCYL-D-15122025-1",
        published_on="2025-12-15",
        title="Decreto 17/2025 PRUG Picos",
        issuer="JCyL",
        discovery_url="https://bocyl.jcyl.es/boletines/2025/12/15/xml/BOCYL-D-15122025-1.xml",
        rank=0,
    )


def _fixture_body() -> bytes:
    return XML_FIXTURE.read_bytes()


def _queue_transport(responses):
    """Deterministic fake transport: pops one canned response per request."""
    calls = []

    def _transport(request: TransportRequest) -> TransportResponse:
        calls.append(request)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    _transport.calls = calls
    return _transport


def _ok(body: bytes, status: int = 200) -> TransportResponse:
    return TransportResponse(status=status, body=body, content_type="application/xml")


def _profile_with(fetch_overrides: dict) -> SourceProfile:
    base = load_profile(PROFILE_JSON)
    fetch_cfg = {**base.fetch, **fetch_overrides}
    return SourceProfile(
        source_id=base.source_id,
        jurisdiction=base.jurisdiction,
        kind=base.kind,
        discovery=base.discovery,
        fetch=fetch_cfg,
        parse=base.parse,
        versioning=base.versioning,
        reachability=base.reachability,
        change_detection=base.change_detection,
        provenance=base.provenance,
    )


def test_success_fixture_exact_hash():
    body = _fixture_body()
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(body)]),
        clock=lambda: FIXED_NOW,
    )
    digest = hashlib.sha256(body).hexdigest()
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetch_outcome is FetchOutcome.SUCCESS
    assert ev.http_status == 200
    assert ev.content_marker_ok is True
    # evidence_sha256 is the hash of the raw received bytes (G0 convention),
    # never of normalized text.
    assert ev.evidence_sha256 == digest
    assert ev.bytes_sha256 == digest
    assert ev.observed_at == FIXED_NOW
    assert ev.fetched_at == FIXED_NOW
    assert ev.method_recipe_id == "get_simple"


def test_http_404_is_reachable_http_error():
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(b"<html>not found</html>", status=404)]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetch_outcome is FetchOutcome.HTTP_ERROR
    assert ev.http_status == 404
    assert ev.content_marker_ok is False


def test_http_500_also_reachable_http_error():
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(b"oops", status=500)]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetch_outcome is FetchOutcome.HTTP_ERROR


def test_soft_404_marker():
    profile = _profile_with({"soft_404_marker": "No hay documento"})
    ev = fetch(
        profile,
        _doc_ref(),
        transport=_queue_transport([_ok(b"<html>No hay documento</html>")]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetch_outcome is FetchOutcome.SOFT_404
    assert ev.content_marker_ok is False


def test_missing_content_marker_is_mismatch_never_success():
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(b"<html>unrelated page</html>")]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetch_outcome is FetchOutcome.CONTENT_MARKER_MISMATCH
    assert ev.content_marker_ok is False


def test_timeout_is_unreachable():
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([TransportTimeout("timed out")]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.reachability_observed is ReachabilityObserved.UNREACHABLE
    assert ev.fetch_outcome is FetchOutcome.TIMEOUT
    assert ev.http_status is None
    assert ev.bytes_sha256 == ""
    assert ev.evidence_sha256 == ""


def test_transport_error_is_unreachable():
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([TransportError("connection refused")]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.reachability_observed is ReachabilityObserved.UNREACHABLE
    assert ev.fetch_outcome is FetchOutcome.TRANSPORT_ERROR


def test_runner_network_defaults_to_unknown(monkeypatch):
    monkeypatch.delenv("ALRASO_RUNNER_NETWORK", raising=False)
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(_fixture_body())]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.runner_network is RunnerNetwork.UNKNOWN


def test_runner_network_from_env(monkeypatch):
    monkeypatch.setenv("ALRASO_RUNNER_NETWORK", "foreign_ci")
    ev = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(_fixture_body())]),
        clock=lambda: FIXED_NOW,
    )
    assert ev.runner_network is RunnerNetwork.FOREIGN_CI


def test_same_input_same_clock_same_evidence():
    body = _fixture_body()
    a = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(body)]),
        clock=lambda: FIXED_NOW,
    )
    b = fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=_queue_transport([_ok(body)]),
        clock=lambda: FIXED_NOW,
    )
    assert a == b
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(
        b.to_dict(), sort_keys=True
    )


def test_post_then_get_recipe():
    profile = _profile_with(
        {
            "recipe": "post_then_get",
            "method": "POST-then-GET",
            "endpoint": "https://boc.example/verXmlAction.do",
            "post_body_template": "idBlob={doc_id}",
            "response_url_pattern": r"https://\S+/\d+\.xml",
        }
    )
    transport = _queue_transport(
        [
            _ok(b'<a href="https://boc.example/xml/435888.xml">xml</a>'),
            _ok(_fixture_body()),
        ]
    )
    ev = fetch(profile, _doc_ref(), transport=transport, clock=lambda: FIXED_NOW)
    first, second = transport.calls
    assert first.method == "POST"
    assert first.url == "https://boc.example/verXmlAction.do"
    assert first.body == b"idBlob=BOCYL-D-15122025-1"
    assert second.method == "GET"
    assert second.url == "https://boc.example/xml/435888.xml"
    assert ev.fetch_outcome is FetchOutcome.SUCCESS


def test_post_then_get_without_url_fails_explicit():
    profile = _profile_with(
        {
            "recipe": "post_then_get",
            "method": "POST-then-GET",
            "endpoint": "https://boc.example/verXmlAction.do",
            "post_body_template": "idBlob={doc_id}",
            "response_url_pattern": r"https://\S+\.xml",
        }
    )
    with pytest.raises(FetchError, match="response_url_pattern|url"):
        fetch(
            profile,
            _doc_ref(),
            transport=_queue_transport([_ok(b"no link here")]),
            clock=lambda: FIXED_NOW,
        )


def test_cgi_recipe_expands_template():
    profile = _profile_with(
        {
            "recipe": "cgi",
            "doc_url_template": "https://boa.example/cgi-bin/doc?id={doc_id}",
        }
    )
    transport = _queue_transport([_ok(_fixture_body())])
    fetch(profile, _doc_ref(), transport=transport, clock=lambda: FIXED_NOW)
    assert transport.calls[0].url == (
        "https://boa.example/cgi-bin/doc?id=BOCYL-D-15122025-1"
    )
    assert transport.calls[0].method == "GET"


def test_unknown_recipe_fails_explicit():
    profile = _profile_with({"recipe": "teleport"})
    with pytest.raises(FetchError, match="teleport"):
        fetch(
            profile,
            _doc_ref(),
            transport=_queue_transport([_ok(b"")]),
            clock=lambda: FIXED_NOW,
        )


def test_fetch_issues_requests_via_injected_transport_only():
    body = _fixture_body()
    transport = _queue_transport([_ok(body)])
    fetch(
        load_profile(PROFILE_JSON),
        _doc_ref(),
        transport=transport,
        clock=lambda: FIXED_NOW,
    )
    assert len(transport.calls) == 1
    req = transport.calls[0]
    assert req.method == "GET"
    assert req.url == _doc_ref().discovery_url


def test_no_third_party_network_imports():
    tree = ast.parse(inspect.getsource(fetch_mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    forbidden = {"requests", "httpx", "aiohttp", "urllib3"}
    assert not imported & forbidden


def test_no_layer_violations_and_no_jurisdiction():
    tree = ast.parse(inspect.getsource(fetch_mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    forbidden = {
        "pipeline.providers.discovery",
        "pipeline.providers.parse",
        "pipeline.providers.version",
    }
    assert not imported & forbidden
    src = inspect.getsource(fetch_mod)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
