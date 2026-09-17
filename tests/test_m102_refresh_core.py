"""M10.2-B refresh core — contract tests (hermetic, no network).

Covers the frozen spec §C.2 state machine end to end:

- FIRST_OBSERVATION -> BASELINE_CREATED (no packet)
- SAME / CHANGED_TRANSPORT_ONLY (no packet)
- CHANGED_CONTENT -> deterministic packet
- canonicalizer bump -> REBASELINE_REQUIRED (never content change)
- UNREACHABLE -> logged; persistent -> ACCESS_DEGRADED; never feeds
  DISAPPEARED_SUSPECTED
- reachable 404/410/SOFT_404 >= absence_threshold -> DISAPPEARED_SUSPECTED
- INVALID persistent -> alert packet
- counters isolated per (surface_id x runner_network)
- CANONICALIZER_GATE: 0 FP on known noise + 0 FN on semantic mutation
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.models import FetchOutcome, ReachabilityObserved
from pipeline.refresh.canonicalize import (
    canonical_sha256,
    canonical_bytes,
    CanonicalizerError,
)
from pipeline.refresh.classify import (
    RefreshObservation,
    RefreshState,
    Thresholds,
)
from pipeline.refresh.runner import observe
from pipeline.refresh.snapshots import (
    Counters,
    SnapshotRecord,
    SnapshotStore,
    doc_key,
)

T3 = Thresholds(absence=3, invalid=3, degraded=3)


def _obs(
    outcome=FetchOutcome.SUCCESS,
    reach=ReachabilityObserved.REACHABLE,
    *,
    body: bytes | None = b"doc-v1",
    status=200,
    runner="es_local",
    at="2026-09-18T10:00:00Z",
    canon_id="identity",
    canon_ver=1,
    etag=None,
    last_modified=None,
):
    raw = hashlib.sha256(body).hexdigest() if body is not None else None
    if body is not None:
        try:
            canon = canonical_sha256(canon_id, canon_ver, body)
        except CanonicalizerError:
            # bumped/unknown version: no digest is recorded — never
            # fabricate one. The classifier short-circuits on the
            # id/version mismatch before comparing digests.
            canon = None
    else:
        canon = None
    return RefreshObservation(
        fetch_outcome=outcome,
        reachability_observed=reach,
        observed_at=at,
        runner_network=runner,
        http_status=status,
        raw_sha256=raw,
        canonical_sha256=canon,
        canonicalizer_id=canon_id if body is not None else None,
        canonicalizer_version=canon_ver if body is not None else None,
        etag=etag,
        last_modified=last_modified,
    )


def _store(tmp_path):
    return SnapshotStore(tmp_path / "store")


def _observe(store, obs, **ids):
    ids.setdefault("source_id", "bocyl")
    ids.setdefault("surface_id", "bocyl-doc")
    ids.setdefault("doc_id", "BOCYL-D-01012026-1")
    return observe(store, obs=obs, thresholds=T3, **ids)


# ---------------------------------------------------------------------
# baseline / same / transport-only / content change
# ---------------------------------------------------------------------


def test_first_observation_creates_baseline_no_packet(tmp_path):
    store = _store(tmp_path)
    res = _observe(store, _obs())
    assert res.verdict.state is RefreshState.BASELINE_CREATED
    assert res.packet is None
    assert store.latest("bocyl", "bocyl-doc", "BOCYL-D-01012026-1") is not None


def test_same_observation_no_packet(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    res = _observe(store, _obs(at="2026-09-19T10:00:00Z"))
    assert res.verdict.state is RefreshState.SAME
    assert res.packet is None


def test_changed_transport_only_no_packet(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs(body=b"<html>content</html>", canon_id="html_volatile"))
    res = _observe(
        store,
        _obs(
            body=b"<html><!-- regenerated 2026-09-19 -->content</html>",
            canon_id="html_volatile",
            etag='"v2"',
            at="2026-09-19T10:00:00Z",
        ),
    )
    # canonical identical (comment stripped), etag changed
    assert res.verdict.state is RefreshState.CHANGED_TRANSPORT_ONLY
    assert res.packet is None


def test_changed_content_emits_deterministic_packet(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs(body=b"v1"))
    res = _observe(store, _obs(body=b"v2-changed", at="2026-09-19T10:00:00Z"))
    assert res.verdict.state is RefreshState.CHANGED_CONTENT
    assert res.packet is not None
    assert res.packet.packet_kind == "content_change"
    assert res.packet.publication_readiness == "NO"

    # determinism: same inputs on a fresh store → identical JSON
    store2 = _store(tmp_path / "second")
    _observe(store2, _obs(body=b"v1"))
    res2 = _observe(store2, _obs(body=b"v2-changed", at="2026-09-19T10:00:00Z"))
    assert res.packet.to_json() == res2.packet.to_json()


def test_canonicalizer_bump_is_rebaseline_never_change(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs(body=b"v1", canon_ver=1))
    res = _observe(
        store, _obs(body=b"v2-changed", canon_ver=2, at="2026-09-19T10:00:00Z")
    )
    assert res.verdict.state is RefreshState.REBASELINE_REQUIRED
    assert res.packet is None


def test_rebaseline_is_manual_not_implicit(tmp_path):
    """REBASELINE_REQUIRED must never silently promote the bumped
    observation to baseline (spec: re-baseline manual). Until a human
    calls set_baseline/rebaseline, every new-canonicalizer observation
    keeps raising REBASELINE_REQUIRED — a real content change coinciding
    with the bump cannot be absorbed invisibly."""
    store = _store(tmp_path)
    _observe(store, _obs(body=b"v1", canon_ver=1))
    _observe(store, _obs(body=b"v2", canon_ver=2, at="2026-09-19T10:00:00Z"))
    # the bumped SUCCESS record was appended as evidence...
    assert len(store.history("bocyl", "bocyl-doc",
                             "BOCYL-D-01012026-1")) == 2
    # ...but the baseline pointer still targets the v1 record
    assert store.baseline("bocyl", "bocyl-doc",
                          "BOCYL-D-01012026-1").canonicalizer_version == 1
    # next observation under the new canonicalizer re-alerts, not SAME
    res = _observe(
        store, _obs(body=b"v2", canon_ver=2, at="2026-09-19T11:00:00Z")
    )
    assert res.verdict.state is RefreshState.REBASELINE_REQUIRED
    # explicit human re-baseline → now the new canonicalizer compares
    store.set_baseline("bocyl", "bocyl-doc", "BOCYL-D-01012026-1")
    res = _observe(
        store, _obs(body=b"v2", canon_ver=2, at="2026-09-19T12:00:00Z")
    )
    assert res.verdict.state is RefreshState.SAME


# ---------------------------------------------------------------------
# unreachable / degraded / never-absence
# ---------------------------------------------------------------------


def _timeout(runner="es_local", at="2026-09-19T10:00:00Z"):
    return _obs(
        outcome=FetchOutcome.TIMEOUT,
        reach=ReachabilityObserved.UNREACHABLE,
        body=None,
        status=None,
        runner=runner,
        at=at,
    )


def test_unreachable_logged_never_absence(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    res = _observe(store, _timeout())
    assert res.verdict.state is RefreshState.UNREACHABLE
    assert res.packet is None
    # counters: unreachable counted, absent untouched
    assert res.verdict.counters["unreachable"] == 1
    assert res.verdict.counters["absent"] == 0
    # baseline evidence preserved
    assert store.latest("bocyl", "bocyl-doc", "BOCYL-D-01012026-1") is not None


def test_persistent_unreachable_access_degraded(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    states = [
        _observe(store, _timeout(at=f"2026-09-19T1{i}:00:00Z")).verdict.state
        for i in range(3)
    ]
    assert states == [
        RefreshState.UNREACHABLE,
        RefreshState.UNREACHABLE,
        RefreshState.ACCESS_DEGRADED,
    ]


def test_unreachable_never_feeds_disappeared(tmp_path):
    """After degraded-threshold timeouts, a real 404 still needs its own
    absence_threshold observations — counters are per-class."""
    store = _store(tmp_path)
    _observe(store, _obs())
    for i in range(3):
        _observe(store, _timeout(at=f"2026-09-19T1{i}:00:00Z"))
    # one reachable 404 must NOT trigger DISAPPEARED_SUSPECTED
    res = _observe(
        store,
        _obs(outcome=FetchOutcome.HTTP_ERROR, status=404, body=b"",
             at="2026-09-19T13:00:00Z"),
    )
    assert res.verdict.state is RefreshState.ABSENT_OBSERVED
    assert res.verdict.counters["absent"] == 1


# ---------------------------------------------------------------------
# absence / invalid thresholds
# ---------------------------------------------------------------------


def _absent(status=404, at="2026-09-19T10:00:00Z", outcome=FetchOutcome.HTTP_ERROR):
    return _obs(outcome=outcome, status=status, body=b"not found", at=at)


def test_disappeared_suspected_at_threshold(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    res = None
    for i in range(3):
        res = _observe(store, _absent(at=f"2026-09-19T1{i}:00:00Z"))
    assert res.verdict.state is RefreshState.DISAPPEARED_SUSPECTED
    assert res.packet is not None
    assert res.packet.packet_kind == "alert"
    # prior evidence preserved — baseline still in store
    hist = store.history("bocyl", "bocyl-doc", "BOCYL-D-01012026-1")
    assert len(hist) == 4


def test_soft_404_counts_as_absence(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    for i in range(2):
        res = _observe(
            store,
            _absent(outcome=FetchOutcome.SOFT_404, status=200,
                    at=f"2026-09-19T1{i}:00:00Z"),
        )
    assert res.verdict.state is RefreshState.ABSENT_OBSERVED
    res = _observe(
        store,
        _absent(outcome=FetchOutcome.SOFT_404, status=200,
                at="2026-09-19T13:00:00Z"),
    )
    assert res.verdict.state is RefreshState.DISAPPEARED_SUSPECTED


def test_http_500_is_invalid_not_absence(tmp_path):
    """A reachable 500 is a contract failure — it must not feed the
    disappearance counter (SOURCE_UNREACHABLE != SOURCE_ABSENT, and a
    server error is not absence evidence either)."""
    store = _store(tmp_path)
    _observe(store, _obs())
    res = _observe(store, _absent(status=500))
    assert res.verdict.state is RefreshState.INVALID
    assert res.verdict.counters["absent"] == 0
    assert res.verdict.counters["invalid"] == 1


def test_invalid_persistent_emits_alert(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    res = None
    for i in range(3):
        res = _observe(
            store,
            _obs(outcome=FetchOutcome.CONTENT_MARKER_MISMATCH,
                 body=b"captcha", status=200, at=f"2026-09-19T1{i}:00:00Z"),
        )
    assert res.verdict.state is RefreshState.INVALID
    assert res.packet is not None
    assert res.packet.packet_kind == "alert"


# ---------------------------------------------------------------------
# counter isolation: surface x runner_network
# ---------------------------------------------------------------------


def test_counters_isolated_per_runner_network(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    # foreign_ci times out twice — es_local counter stays clean
    _observe(store, _timeout(runner="foreign_ci", at="2026-09-19T10:00:00Z"))
    _observe(store, _timeout(runner="foreign_ci", at="2026-09-19T11:00:00Z"))
    res = _observe(store, _obs(at="2026-09-19T12:00:00Z"))
    assert res.verdict.state is RefreshState.SAME
    # es_local never saw a failure
    assert store.counters("bocyl", "bocyl-doc", "BOCYL-D-01012026-1",
                          "es_local").unreachable == 0
    assert store.counters("bocyl", "bocyl-doc", "BOCYL-D-01012026-1",
                          "foreign_ci").unreachable == 2


def test_counters_isolated_per_doc_id(tmp_path):
    """Same surface, different doc_ids: pooled counters would alert the
    wrong doc (FP) or erase a vanished doc's streak (FN). Counters are
    keyed per document — a strict refinement of surface x runner."""
    store = _store(tmp_path)
    for doc in ("doc-A", "doc-B", "doc-C"):
        _observe(store, _obs(), doc_id=doc)
    # three DIFFERENT docs each absent once → no doc hits threshold 3
    for i, doc in enumerate(("doc-A", "doc-B", "doc-C")):
        res = _observe(store, _absent(at=f"2026-09-19T1{i}:00:00Z"),
                       doc_id=doc)
        assert res.verdict.state is RefreshState.ABSENT_OBSERVED
        assert res.packet is None
    # and doc-A absent twice more DOES alert on doc-A only
    _observe(store, _absent(at="2026-09-19T14:00:00Z"), doc_id="doc-A")
    res = _observe(store, _absent(at="2026-09-19T15:00:00Z"),
                   doc_id="doc-A")
    assert res.verdict.state is RefreshState.DISAPPEARED_SUSPECTED
    assert res.packet is not None
    # doc-B/doc-C counters unaffected
    assert store.counters("bocyl", "bocyl-doc", "doc-B",
                          "es_local").absent == 1


def test_success_resets_counters(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    _observe(store, _timeout())
    res = _observe(store, _obs(at="2026-09-19T11:00:00Z"))
    assert res.verdict.counters == {"unreachable": 0, "absent": 0,
                                  "invalid": 0}


# ---------------------------------------------------------------------
# store mechanics
# ---------------------------------------------------------------------


def test_store_append_only_and_doc_key(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs(body=b"v1"))
    _observe(store, _timeout())
    _observe(store, _absent(at="2026-09-19T11:00:00Z"))
    hist = store.history("bocyl", "bocyl-doc", "BOCYL-D-01012026-1")
    assert len(hist) == 3
    # baseline survives failures
    assert store.latest(
        "bocyl", "bocyl-doc", "BOCYL-D-01012026-1"
    ).raw_sha256 == hashlib.sha256(b"v1").hexdigest()
    assert store.baseline(
        "bocyl", "bocyl-doc", "BOCYL-D-01012026-1"
    ).raw_sha256 == hashlib.sha256(b"v1").hexdigest()


def test_doc_key_injective_and_safe(tmp_path):
    """doc_key must be injective — distinct ids never share an evidence
    file — and can never escape the store root."""
    ids = ["a/b", "a:b", "a b", "a_b", "a.b", "..", "."]
    keys = {}
    for i in ids:
        if i in (".", ".."):
            with pytest.raises(ValueError):
                doc_key(i)
            continue
        keys[i] = doc_key(i)
    assert len(set(keys.values())) == len(keys)  # no collisions
    assert all("." not in k[:2] for k in keys.values())
    # percent-encoded keys cannot contain path separators
    assert all("/" not in k and "\\" not in k for k in keys.values())


def test_snapshot_record_roundtrip(tmp_path):
    store = _store(tmp_path)
    _observe(store, _obs())
    rec = store.latest("bocyl", "bocyl-doc", "BOCYL-D-01012026-1")
    assert SnapshotRecord.from_dict(rec.to_dict()) == rec


# ---------------------------------------------------------------------
# CANONICALIZER_GATE — bidirectional
# ---------------------------------------------------------------------


def test_gate_zero_fp_known_noise():
    """html_volatile@1 removes only demonstrated noise: comments, csrf
    tokens, nonces, viewstate — canonical must not change."""
    base = (
        b'<html><head><meta name="csrf-token" content="AAA"/></head>'
        b'<body><!-- gen 2026-09-18 --><p>Article 1 stays</p>'
        b'<div nonce="xyz"></div>'
        b'<input type="hidden" name="__VIEWSTATE" value="zzz"/></body>'
        b"</html>"
    )
    noisy = (
        b'<html><head><meta name="csrf-token" content="BBB"/></head>'
        b'<body><!-- gen 2026-09-19 --><p>Article 1 stays</p>'
        b'<div nonce="qwe"></div>'
        b'<input type="hidden" name="__VIEWSTATE" value="yyy"/></body>'
        b"</html>"
    )
    assert canonical_sha256("html_volatile", 1, base) == canonical_sha256(
        "html_volatile", 1, noisy
    )


def test_gate_zero_fn_semantic_mutation():
    base = b"<html><body><p>Article 1 stays</p></body></html>"
    mutations = [
        b"<html><body><p>Article 1 amended</p></body></html>",
        b"<html><body><p>Article 1 stays</p><p>Article 2 added</p></body></html>",
        b"<html><body><p>rticle 1 stays</p></body></html>",  # 1-char
    ]
    for mut in mutations:
        assert canonical_sha256(
            "html_volatile", 1, base
        ) != canonical_sha256("html_volatile", 1, mut), mut


def test_identity_is_passthrough():
    assert canonical_bytes("identity", 1, b"abc") == b"abc"


def test_unknown_canonicalizer_fails_explicit():
    with pytest.raises(CanonicalizerError):
        canonical_bytes("html_volatile", 99, b"x")
    with pytest.raises(CanonicalizerError):
        canonical_bytes("nonexistent", 1, b"x")


# ---------------------------------------------------------------------
# config guards + live body classification (hermetic — bytes only)
# ---------------------------------------------------------------------


def test_thresholds_reject_non_positive():
    """A threshold of 0 would alert on the first failure — fail closed."""
    with pytest.raises(ValueError):
        Thresholds.from_profile({"absence_threshold": 0})
    with pytest.raises(ValueError):
        Thresholds.from_profile({"invalid_threshold": -1})


def test_live_body_classification_uses_profile_markers():
    """_classify_live_body mirrors the fetch contract on 2xx bodies:
    interstitial and soft-404 guards run unconditionally; a configured
    content_marker must be present — error pages can never be SUCCESS."""
    from tooling.m102_refresh_run import _classify_live_body

    assert _classify_live_body(
        b"<html>Radware Captcha Page hcaptcha.com</html>", {}
    ) is FetchOutcome.CONTENT_MARKER_MISMATCH
    assert _classify_live_body(
        b"requested page not found",
        {"soft_404_marker": "not found"},
    ) is FetchOutcome.SOFT_404
    assert _classify_live_body(
        b"<html>landing page</html>", {"content_marker": "%PDF"}
    ) is FetchOutcome.CONTENT_MARKER_MISMATCH
    assert _classify_live_body(
        b"%PDF-1.4 real bytes", {"content_marker": "%PDF"}
    ) is FetchOutcome.SUCCESS
