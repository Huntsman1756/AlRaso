import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider
from conftest import new_store, relation, rule, scope

SECTOR = "ss-ordesa-sector-ordesa"


def fixture_resolver() -> Resolver:
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    return Resolver(s)


def test_unknown_activity_fails_closed_never_permitted():
    r = fixture_resolver()
    res = r.resolve(Query(activity="EXCURSIONISMO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id=SECTOR))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert "vocabulario" in res.decision_reason


def test_out_of_modelled_scope_is_undetermined():
    r = fixture_resolver()
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id="ss-no-existe"))
    assert res.legal_status is LegalStatus.UNDETERMINED


def test_temporal_gap_is_undetermined_and_incomplete():
    r = fixture_resolver()
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2019-12-31",
                          knowledge_date="2023-06-15", spatial_scope_id=SECTOR))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status.value == "INCOMPLETE"


def test_missing_fact_on_conditional_rule_fails_closed():
    r = fixture_resolver()
    base = dict(activity="ACAMPADA", activity_date="2021-07-15",
                knowledge_date="2023-06-15", spatial_scope_id=SECTOR)
    missing = r.resolve(Query(**base, facts={}))
    assert missing.legal_status is LegalStatus.UNDETERMINED
    assert missing.knowledge_status.value == "INCOMPLETE"
    above = r.resolve(Query(**base, facts={"altitude_m": 2200}))
    assert above.legal_status is LegalStatus.PERMITTED
    below = r.resolve(Query(**base, facts={"altitude_m": 1500}))
    assert below.legal_status is LegalStatus.UNDETERMINED


def test_conflicting_rules_without_verified_override_are_conflict():
    S = "s-y"
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/y#a#perm", S, "PERMITTED")
    rule(s, "alraso:es:t/y#b#proh", S, "PROHIBITED")
    r = Resolver(s)
    q = Query(activity="VIVAC_AL_RASO", activity_date="2021-01-01",
              knowledge_date="2023-06-15", spatial_scope_id=S)
    res = r.resolve(q)
    assert res.legal_status is LegalStatus.UNDETERMINED      # never PERMITTED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert res.unresolved_conflicts
    relation(s, "rel-1", "alraso:es:t/y#b#proh", "alraso:es:t/y#a#perm",
             human_verified=True)
    res2 = r.resolve(q)
    assert res2.legal_status is LegalStatus.PROHIBITED


def test_unverified_override_does_not_resolve():
    S = "s-y2"
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/y2#perm", S, "PERMITTED")
    rule(s, "alraso:es:t/y2#proh", S, "PROHIBITED")
    relation(s, "rel-u", "alraso:es:t/y2#perm", "alraso:es:t/y2#proh",
             human_verified=False)
    res = Resolver(s).resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-01-01",
                                    knowledge_date="2023-06-15", spatial_scope_id=S))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_spatial_point_resolution_composes_all_scopes_and_fails_outside():
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    prov = InMemorySpatialProvider()
    park_ring = [(42.60, -0.10), (42.60, 0.10), (42.70, 0.10), (42.70, -0.10)]
    sector_ring = [(42.64, -0.02), (42.64, 0.02), (42.66, 0.02), (42.66, -0.02)]
    prov.add_scope("ss-ordesa-park", "Parque Nacional", "NATIONAL_PARK", [park_ring])
    prov.add_scope(SECTOR, "Sector Ordesa", "PARK_SECTOR", [sector_ring],
                   parent="ss-ordesa-park")
    r = Resolver(s, spatial=prov)
    inside = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2023-06-15",
                             knowledge_date="2023-06-15", lat=42.65, lon=0.0))
    assert inside.legal_status is LegalStatus.PROHIBITED   # restrictive: allowed
    assert {h["scope_id"] for h in inside.applicable_scope} == {"ss-ordesa-park", SECTOR}
    outside = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2023-06-15",
                              knowledge_date="2023-06-15", lat=43.50, lon=0.50))
    assert outside.legal_status is LegalStatus.UNDETERMINED


def test_coordinate_permitted_over_unreviewed_geometry_is_impossible():
    # The Ordesa scopes carry SPATIAL_REVIEW_PENDING_GEOMETRY: a PERMITTED
    # derived from coordinates must be refused (restrictive answers pass).
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    prov = InMemorySpatialProvider()
    prov.add_scope(SECTOR, "Sector Ordesa", "PARK_SECTOR",
                   [[(42.64, -0.02), (42.64, 0.02), (42.66, 0.02), (42.66, -0.02)]])
    r = Resolver(s, spatial=prov)
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", lat=42.65, lon=0.0))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["PERMITTED_INVARIANT_VIOLATION"]


def test_unexpected_engine_failure_never_permitted():
    class Boom:
        name = "boom"
        version = "boom/0"

        def capabilities(self):
            from alraso.engine import EngineCapabilities
            return EngineCapabilities(True, frozenset({"const", "all", "any", "not", "field"}),
                                      frozenset({"eq", "neq", "gte", "gt", "lte", "lt", "in",
                                                 "is_true", "is_false"}),
                                      frozenset({"PERMITTED", "PROHIBITED",
                                                 "AUTHORIZATION_REQUIRED"}),
                                      True, True, True)

        def evaluate(self, versions, facts, mode="fast"):
            raise RuntimeError("engine exploded")
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    r = Resolver(s, engine=Boom())
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id=SECTOR))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["UNEXPECTED_FAILURE"]


# ---- H6: normalized engine / spatial failure paths (explicit coverage) ------
from alraso.engine import OwnEvaluatorAdapter           # noqa: E402
from alraso.errors import (EngineBinaryNotFound, EngineNonZeroExit,  # noqa: E402
                           EngineTimeout, SpatialResolutionError)


class _FailingEngine(OwnEvaluatorAdapter):
    def __init__(self, error: Exception) -> None:
        self._error = error

    def evaluate(self, versions, facts, mode="fast"):
        raise self._error


@pytest.mark.parametrize("error,code", [
    (EngineTimeout("axiom timed out"), "ENGINE_TIMEOUT"),
    (EngineNonZeroExit("axiom exited 1"), "ENGINE_NONZERO_EXIT"),
    (EngineBinaryNotFound("no binary"), "ENGINE_BINARY_NOT_FOUND"),
])
def test_engine_process_failures_are_normalized_not_permitted(error, code):
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    res = Resolver(s, engine=_FailingEngine(error)).resolve(
        Query(activity="VIVAC_AL_RASO", activity_date="2023-06-15",
              knowledge_date="2023-06-15", spatial_scope_id=SECTOR))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert res.reason_codes == [code]           # named failure, not a traceback
    assert res.reason_codes != ["UNEXPECTED_FAILURE"]
    assert res.decision_reason


class _BrokenProvider:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def resolve(self, lat, lon):
        raise self._error


@pytest.mark.parametrize("error", [RuntimeError("wfs unreachable"),
                                   SpatialResolutionError("postgis is down")])
def test_spatial_provider_failure_fails_closed(error):
    S = "s-geo-boom"
    s = new_store()
    scope(s, S, geometry="src", review_status="VERIFIED")
    rule(s, "alraso:es:t/geo#a", S, "PERMITTED")
    res = Resolver(s, spatial=_BrokenProvider(error)).resolve(
        Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
              knowledge_date="2023-06-15", lat=42.05, lon=0.05))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert res.reason_codes == ["SPATIAL_RESOLUTION_ERROR"]
