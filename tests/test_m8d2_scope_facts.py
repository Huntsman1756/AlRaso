"""M8-D2b: derived scope:<id> facts + declared-fact provenance +
split-fixture corpus ingest.

Contract being proved:

  * The resolver injects ``scope:<scope_id>`` membership facts from the
    spatial provider catalog — True for hit scopes, False for catalog
    misses. A rule can therefore express "not in Zona de Reserva" as a
    condition instead of needing a general prohibition rule.
  * Caller-supplied ``scope:*`` / ``activity_date`` facts are stripped and
    recomputed — users cannot declare themselves inside/outside a scope.
  * A determination that consumes caller-declared facts (not observable by
    the system) is marked DEPENDS_ON_DECLARED_FACTS — provenance, never
    silent trust.
  * Split-fixture publication: independently adjudicated fixtures may cite
    identical documents/fragments/scopes; identical redeclarations are
    no-ops, divergent ones are refused.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.errors import InvalidRule, InvalidScope
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider

from conftest import new_store, scope, rule

EV = Path("discovery/evidence/m8-guadarrama")


def sq(latl=(40.5, -4.0)):
    """Square provider: s-x contains the test point, s-res does not."""
    return [((latl[0] - 0.5, latl[1] - 0.5), (latl[0] + 0.5, latl[1] + 0.5))]


def provider_two_scopes():
    p = InMemorySpatialProvider()
    p.add_scope("s-x", "scope x", "PARK_SECTOR",
                rings=[[(39.0, -5.0), (41.0, -5.0), (41.0, -3.0), (39.0, -3.0)]])
    p.add_scope("s-res", "reserve", "PARK_SECTOR",
                rings=[[(40.9, -4.5), (41.5, -4.5), (41.5, -3.5), (40.9, -3.5)]])
    return p


def cq(facts=None, lat=40.0, lon=-4.0, activity_date="2026-01-15"):
    return Query(activity="VIVAC_AL_RASO", activity_date=activity_date,
                 knowledge_date=activity_date, lat=lat, lon=lon,
                 facts=facts or {})


# --------------------------------------------------------------------------
# derived scope:<id> facts
# --------------------------------------------------------------------------

def test_scope_fact_gates_condition_by_geometry():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    scope(s, "s-res", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/c#a", "s-x", "PERMITTED",
         condition={"field": "scope:s-res", "op": "is_false"})
    r = Resolver(s, spatial=provider_two_scopes()).resolve(cq())
    assert r.legal_status is LegalStatus.PERMITTED


def test_scope_fact_excludes_when_inside_declared_scope():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    scope(s, "s-res", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/c#a", "s-x", "PERMITTED",
         condition={"field": "scope:s-res", "op": "is_false"})
    # point inside BOTH s-x and s-res -> permission affirmatively excluded
    r = Resolver(s, spatial=provider_two_scopes()).resolve(cq(lat=41.0, lon=-4.0))
    assert r.legal_status is LegalStatus.UNDETERMINED


def test_caller_cannot_forge_scope_fact():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    scope(s, "s-res", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/c#a", "s-x", "PERMITTED",
         condition={"field": "scope:s-res", "op": "is_false"})
    # caller claims "not in reserve" while inside it — derived fact wins
    r = Resolver(s, spatial=provider_two_scopes()).resolve(
        cq(facts={"scope:s-res": False}, lat=41.0, lon=-4.0))
    assert r.legal_status is LegalStatus.UNDETERMINED


def test_scope_fact_without_catalog_fails_closed():
    """A provider that cannot enumerate scopes cannot prove is_false —
    the condition fails closed, never assumed."""
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/c#a", "s-x", "PERMITTED",
         condition={"field": "scope:s-res", "op": "is_false"})
    q = Query(activity="VIVAC_AL_RASO", activity_date="2026-01-15",
              knowledge_date="2026-01-15", spatial_scope_id="s-x", facts={})
    r = Resolver(s).resolve(q)   # no spatial provider -> no catalog
    assert r.legal_status is not LegalStatus.PERMITTED


# --------------------------------------------------------------------------
# declared-fact provenance (DEPENDS_ON_DECLARED_FACTS)
# --------------------------------------------------------------------------

def test_permitted_via_declared_fact_is_marked():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_has_free_places", "op": "is_false"})
    q = Query(activity="VIVAC_AL_RASO", activity_date="2026-01-15",
              knowledge_date="2026-01-15", spatial_scope_id="s-x",
              facts={"refuge_has_free_places": False})
    r = Resolver(s).resolve(q)
    assert r.legal_status is LegalStatus.PERMITTED
    assert "DEPENDS_ON_DECLARED_FACTS" in r.reason_codes
    assert any("refuge_has_free_places" in w for w in r.warnings)


def test_prohibition_reached_via_declared_exclusion_is_marked():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/d#a", "s-x", "PROHIBITED")
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_has_free_places", "op": "is_false"})
    q = Query(activity="VIVAC_AL_RASO", activity_date="2026-01-15",
              knowledge_date="2026-01-15", spatial_scope_id="s-x",
              facts={"refuge_has_free_places": True})
    r = Resolver(s).resolve(q)
    assert r.legal_status is LegalStatus.PROHIBITED
    assert "DEPENDS_ON_DECLARED_FACTS" in r.reason_codes


def test_derived_facts_are_not_declared():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    rule(s, "alraso:t/c#a", "s-x", "PERMITTED",
         condition={"all": [
             {"field": "scope:s-res", "op": "is_false"},
             {"not": {"field": "activity_date", "op": "date_in_range",
                      "value": ["06-15", "10-15"]}}]})
    r = Resolver(s, spatial=provider_two_scopes()).resolve(cq())
    assert r.legal_status is LegalStatus.PERMITTED
    assert "DEPENDS_ON_DECLARED_FACTS" not in r.reason_codes


# --------------------------------------------------------------------------
# split-fixture ingest: identical redeclare no-op, divergent refused
# --------------------------------------------------------------------------

def test_scope_identical_redeclare_is_noop_divergent_refused():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    # identical redeclaration tolerated (second published fixture)
    scope(s, "s-x", review_status="VERIFIED", geometry="test-layer")
    with pytest.raises(InvalidScope):
        s.add_spatial_scope({"id": "s-x", "scope_type": "PARK_SECTOR",
                             "official_name": "DIFFERENT NAME"})


def test_document_fragment_identical_redeclare_noop_divergent_refused():
    from conftest import DOC, frag
    s = new_store()
    s.add_source_document(DOC)
    s.add_source_document(DOC)                       # identical -> no-op
    with pytest.raises(InvalidRule):
        s.add_source_document({**DOC, "title": "different"})
    frag(s, "lf-x")
    frag(s, "lf-x")                                  # identical -> no-op
    with pytest.raises(InvalidRule):
        s.add_legal_fragment({"id": "lf-x", "source_document_id": DOC["id"],
                              "locator": "different locator"})


# --------------------------------------------------------------------------
# split fixtures: structural contract
# --------------------------------------------------------------------------

FIXTURE_FILES = ["candidate_fixture.v2b-a.json",
                 "candidate_fixture.v2b-b.json",
                 "candidate_fixture.v2b-c.json",
                 "candidate_fixture.v2b-cierre.json"]


def _load(name):
    return json.loads((EV / name).read_text(encoding="utf-8"))


def test_split_fixtures_structure():
    fixtures = [_load(n) for n in FIXTURE_FILES]
    rule_ids = {r["rule_id"] for f in fixtures
                for r in f["legal_rule_versions"]}
    # every relation endpoint resolves to a rule that exists in the union
    for f in fixtures:
        for rel in f["rule_relations"]:
            assert rel["from_rule_id"] in rule_ids
            assert rel["to_rule_id"] in rule_ids
    # every rule's spatial scope is declared in its own fixture (FK order)
    for f in fixtures:
        declared = {s["id"] for s in f["spatial_scopes"]}
        for r in f["legal_rule_versions"]:
            assert r["spatial_scope_id"] in declared
    # every condition validates under the current grammar
    from alraso.validation import validate_condition
    for f in fixtures:
        for r in f["legal_rule_versions"]:
            if r.get("condition"):
                validate_condition(r["condition"])


def test_split_fixtures_publish_independently_and_compose():
    """All four fixtures approved -> one coherent corpus: the residual
    prohibition stands where no branch permits, branches override where
    they hold, >10 answers AUTHORIZATION_REQUIRED, and nothing published
    without every part of the art-48 apparatus being adjudicated."""
    from alraso.ingest.ordesa import ingest_corpus
    from alraso.publish_reviewed import apply_decision
    from alraso.review_decision import _required_evidence, object_sha256
    from alraso.geojson_provider import load_manifest_provider

    s = new_store()
    for name in FIXTURE_FILES:
        fx = _load(name)
        case = _load(name.replace("candidate_fixture", "review_case"))
        required, req_reasons = _required_evidence(case, EV, None)
        assert not req_reasons, req_reasons
        decision = {
            "schema": "alraso/review-decision@1",
            "review_case_id": case["review_case_id"],
            "case_sha256": object_sha256(case),
            "candidate_fixture_sha256": object_sha256(fx),
            "decision": "APPROVE",
            "reviewer": {"name": "TEST", "reference": "TEST",
                         "qualification": "TEST"},
            "decided_at": "2026-09-18T00:00:00Z",
            "reviewed_evidence": required,
            "spatial_disposition": "REVIEWED",
            "annotation": "test-only simulated approval",
        }
        published = apply_decision(decision, case, fx, case_dir=EV)
        ingest_corpus(s, published)

    prov = load_manifest_provider(EV.parent / "m8-madrid-layers.json")
    res = Resolver(s, spatial=prov)

    def go(lat, lon, date, facts=None):
        return res.resolve(Query(
            activity="VIVAC_AL_RASO", activity_date=date,
            knowledge_date="2026-09-18", lat=lat, lon=lon, facts=facts or {}))

    # Zabala (annex3), full declared facts -> PERMITTED-class answer only
    # via declared-fact dependence; the fire check is unverified so it can
    # never be unconditional PERMITTED.
    zabala = go(40.837697, -3.958714, "2026-01-15",
                {"nights_same_zone": 1, "group_size": 4})
    assert zabala.legal_status in (LegalStatus.CONDITIONAL,
                                  LegalStatus.PERMITTED)
    if zabala.legal_status is LegalStatus.PERMITTED:
        assert "DEPENDS_ON_DECLARED_FACTS" in zabala.reason_codes

    # annex3 group>10 -> AUTHORIZATION_REQUIRED (never PROHIBITED)
    g15 = go(40.837697, -3.958714, "2026-01-15",
             {"nights_same_zone": 1, "group_size": 15})
    assert g15.legal_status is LegalStatus.AUTHORIZATION_REQUIRED

    # interior PN summer, refuge excluded, group<=10 -> PROHIBITED
    interior = go(40.78740, -4.07142, "2026-08-01",
                  {"near_unguarded_refuge": False, "group_size": 4})
    assert interior.legal_status is LegalStatus.PROHIBITED

    # interior PN summer, refuge branch pending -> CONDITIONAL/UNDETERMINED
    pending = go(40.78740, -4.07142, "2026-08-01")
    assert pending.legal_status in (LegalStatus.CONDITIONAL,
                                    LegalStatus.UNDETERMINED)
    assert pending.legal_status is not LegalStatus.PROHIBITED

    # interior PN winter, <=5, not reserve -> seasonal branch fires
    winter = go(40.78740, -4.07142, "2026-01-15",
                {"group_size": 4, "nights_same_zone": 1,
                 "near_unguarded_refuge": False})
    assert winter.legal_status in (LegalStatus.CONDITIONAL,
                                  LegalStatus.PERMITTED)

    # reserve point in winter -> not permitted (scope-fact excludes C)
    reserve = go(40.83692, -3.95630, "2026-01-15",
                 {"group_size": 4, "nights_same_zone": 1,
                  "near_unguarded_refuge": False})
    assert reserve.legal_status is not LegalStatus.PERMITTED
