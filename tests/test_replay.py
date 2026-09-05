"""F05 — replay preserves the MATERIAL question (facts, coordinates) and
classifies drift instead of comparing only legal status."""

from __future__ import annotations

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import LegalStatus, Query
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider
from conftest import new_store, relation, rule, scope

SECTOR = "ss-ordesa-sector-ordesa"
RULE = "alraso:es-ar/pn-ordesa/pernocta#vivac-sector-ordesa"


def build_unaware_store() -> BitemporalStore:
    """Late-discovery world: only the open PERMITTED row is known."""
    from alraso.ingest.ordesa import load_fixture_json
    fx = load_fixture_json()
    s = new_store()
    for d in fx["source_documents"]:
        s.add_source_document(d)
    for f in fx["legal_fragments"]:
        s.add_legal_fragment(f)
    for sc in fx["spatial_scopes"]:
        s.add_spatial_scope(sc)
    s.add_rule_version({
        "rule_id": RULE, "activity": "VIVAC_AL_RASO", "spatial_scope_id": SECTOR,
        "effect": "PERMITTED", "effective_from": "2020-01-01", "effective_to": None,
        "recorded_at": "2020-06-01", "review_status": "VERIFIED",
        "legal_review_complete": True, "spatial_review_complete": True,
        "evidence": ["lf-rd409-anexo1-da"]})
    return s


def late_discover(s: BitemporalStore) -> None:
    s.add_rule_version({"rule_id": RULE, "activity": "VIVAC_AL_RASO", "spatial_scope_id": SECTOR,
                        "effect": "PERMITTED", "effective_from": "2020-01-01",
                        "effective_to": "2022-02-08", "recorded_at": "2027-05-10",
                        "review_status": "VERIFIED", "legal_review_complete": True,
                        "spatial_review_complete": True,
                        "evidence": ["lf-rd409-anexo1-da"]})
    s.add_rule_version({"rule_id": RULE, "activity": "VIVAC_AL_RASO", "spatial_scope_id": SECTOR,
                        "effect": "PROHIBITED", "effective_from": "2022-02-09",
                        "recorded_at": "2027-05-10", "review_status": "VERIFIED",
                        "legal_review_complete": True, "spatial_review_complete": True,
                        "evidence": ["lf-d16-2022-pernocta"]})


def test_replay_preserves_facts_and_is_stable():
    s = new_store()
    scope(s, "s-f")
    rule(s, "alraso:es:t/f#cond", "s-f", "PERMITTED",
         condition={"field": "altitude_m", "op": "gte", "value": 1800})
    r = Resolver(s)
    q = Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
              knowledge_date="2023-06-15", spatial_scope_id="s-f",
              facts={"altitude_m": 2000})
    res = r.resolve(q, record=True)
    assert res.legal_status is LegalStatus.PERMITTED
    rec = s.determinations()[0]
    assert rec["canonical_query"]["facts"] == {"altitude_m": 2000}
    # replay with SAME knowledge date: fully stable
    out = r.replay("2023-06-15")
    assert out[0]["drift"] == ["NO_MATERIAL_CHANGE"]
    assert out[0]["stale"] is False


def test_replay_preserves_coordinates_and_is_stable():
    s = new_store()
    scope(s, "s-c", review_status="VERIFIED", geometry="src")
    rule(s, "alraso:es:t/c#proh", "s-c", "PROHIBITED")
    prov = InMemorySpatialProvider()
    prov.add_scope("s-c", "s-c", "PARK_SECTOR",
                   [[(42.0, 0.0), (42.0, 0.1), (42.1, 0.1), (42.1, 0.0)]])
    r = Resolver(s, spatial=prov)
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", lat=42.05, lon=0.05), record=True)
    assert res.legal_status is LegalStatus.PROHIBITED
    rec = s.determinations()[0]["canonical_query"]
    assert rec["queryMode"] == "coordinates"
    assert rec["latitude"] == 42.05 and rec["longitude"] == 0.05
    out = r.replay("2023-06-15")
    assert out[0]["drift"] == ["NO_MATERIAL_CHANGE"]


def test_replay_detects_late_discovery_drift():
    s = build_unaware_store()
    r = Resolver(s)
    before = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2023-06-15",
                             knowledge_date="2023-06-15", spatial_scope_id=SECTOR),
                       record=True)
    assert before.legal_status is LegalStatus.PERMITTED
    late_discover(s)
    out = r.replay("2028-01-01")
    assert out[0]["flag"] == "STALE"
    assert "LEGAL_STATUS_CHANGED" in out[0]["drift"]
    assert "RULE_SET_CHANGED" in out[0]["drift"]
    assert "EVIDENCE_CHANGED" in out[0]["drift"]


def test_replay_basis_change_same_effect_is_classified_not_stale():
    # The late closure changes the FOUNDATION (different version row, same
    # PERMITTED answer): classified, but NOT stale (policy: materiality).
    s = build_unaware_store()
    r = Resolver(s)
    r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                    knowledge_date="2023-06-15", spatial_scope_id=SECTOR), record=True)
    s.add_rule_version({"rule_id": RULE, "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": SECTOR, "effect": "PERMITTED",
                        "effective_from": "2020-01-01", "effective_to": "2022-02-08",
                        "recorded_at": "2027-05-10", "review_status": "VERIFIED",
                        "legal_review_complete": True, "spatial_review_complete": True,
                        "evidence": ["lf-rd409-anexo1-da", "lf-d16-2022-pernocta"]})
    out = r.replay("2028-01-01")
    drifts = out[0]["drift"]
    assert "LEGAL_STATUS_CHANGED" not in drifts
    assert "RULE_SET_CHANGED" in drifts and "EVIDENCE_CHANGED" in drifts
    assert out[0]["flag"] is None


def test_replay_records_undetermined_outcomes():
    s = new_store()
    scope(s, "s-u")
    r = Resolver(s)
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id="s-u"),
                    record=True)
    assert res.legal_status is LegalStatus.UNDETERMINED
    recs = s.determinations()
    assert len(recs) == 1
    assert recs[0]["legal_status"] == "UNDETERMINED"
    # replaying it stays coherent (UNDETERMINED -> UNDETERMINED, no drift)
    out = r.replay("2023-06-15")
    assert out[0]["drift"] == ["NO_MATERIAL_CHANGE"]


def test_early_exit_is_recorded_when_record_true():
    s = new_store()
    r = Resolver(s)
    res = r.resolve(Query(activity="EXCURSIONISMO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id="nope"),
                    record=True)
    assert res.legal_status is LegalStatus.UNDETERMINED
    recs = s.determinations()
    assert len(recs) == 1 and recs[0]["legal_status"] == "UNDETERMINED"


def test_recorded_query_keeps_engine_and_schema_identity():
    s = new_store()
    scope(s, "s-i")
    rule(s, "alraso:es:t/i#a", "s-i", "PROHIBITED")
    r = Resolver(s)
    r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                    knowledge_date="2023-06-15", spatial_scope_id="s-i"), record=True)
    rec = s.determinations()[0]
    cq = rec["canonical_query"]
    assert cq["engineAdapter"] == "own"
    assert cq["schemaVersion"] == "m1r2"
    assert rec["knowledge_state_hash"] and rec["rule_version_seqs"]
    assert rec["source_document_ids"] == ["sd-test"]


def test_scope_set_change_detected():
    s = new_store()
    scope(s, "s-a"); scope(s, "s-b", parent="s-a")
    rule(s, "alraso:es:t/sc#a", "s-a", "PROHIBITED")
    prov = InMemorySpatialProvider()
    prov.add_scope("s-a", "s-a", "PARK_SECTOR",
                   [[(42.0, 0.0), (42.0, 0.1), (42.1, 0.1), (42.1, 0.0)]])
    r = Resolver(s, spatial=prov)
    r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                    knowledge_date="2023-06-15", lat=42.05, lon=0.05), record=True)
    # provider now returns a second scope as well
    prov.add_scope("s-b", "s-b", "PARK_SECTOR",
                   [[(42.04, 0.04), (42.04, 0.06), (42.06, 0.06), (42.06, 0.04)]])
    rule(s, "alraso:es:t/sc#b", "s-b", "PROHIBITED")
    out = r.replay("2023-06-15")
    assert "SPATIAL_SCOPE_CHANGED" in out[0]["drift"]


def test_ordesa_fixture_expected_replay_semantics():
    s = new_store()
    load_ordesa(s)
    r = Resolver(s)
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id=SECTOR),
                    record=True)
    assert res.legal_status is LegalStatus.PERMITTED
    out = r.replay("2023-06-15")
    assert out[0]["stale"] is False
