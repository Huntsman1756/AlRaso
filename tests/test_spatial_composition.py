"""F03 — ALL applicable scopes compose. Legality never depends on provider
order, and no applicable scope may be silently dropped."""

from __future__ import annotations

import itertools

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider
from conftest import new_store, relation, rule, scope

PARK = "s-park"
SECTOR = "s-sector"
DEEP = "s-deep"

RING = {
    PARK:    [[(42.60, -0.10), (42.60, 0.10), (42.70, 0.10), (42.70, -0.10)]],
    SECTOR:  [[(42.64, -0.02), (42.64, 0.02), (42.66, 0.02), (42.66, -0.02)]],
    DEEP:    [[(42.645, -0.005), (42.645, 0.005), (42.655, 0.005), (42.655, -0.005)]],
}


def provider(insertion_order: list[str]) -> InMemorySpatialProvider:
    prov = InMemorySpatialProvider()
    for sid in insertion_order:
        prov.add_scope(sid, sid, "OTHER", RING[sid])
    return prov


def inside_point_query(lat=42.65, lon=0.0):
    return Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                 knowledge_date="2023-06-15", lat=lat, lon=lon)


def three_scope_store():
    s = new_store()
    scope(s, PARK, scope_type="NATIONAL_PARK")
    scope(s, SECTOR, parent=PARK)
    scope(s, DEEP, parent=SECTOR)
    return s


def test_parent_prohibition_child_permission_conflicts_not_specificity_wins():
    s = three_scope_store()
    rule(s, "alraso:es:t/park#proh", PARK, "PROHIBITED")
    rule(s, "alraso:es:t/sector#perm", SECTOR, "PERMITTED")
    res = Resolver(s, spatial=provider([PARK, SECTOR])).resolve(inside_point_query())
    assert res.legal_status is LegalStatus.UNDETERMINED          # never PERMITTED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert res.unresolved_conflicts
    # both scopes were evaluated and reported
    assert {h["scope_id"] for h in res.applicable_scope} == {PARK, SECTOR}


def test_parent_permission_child_prohibition_conflicts():
    s = three_scope_store()
    rule(s, "alraso:es:t/park#perm", PARK, "PERMITTED")
    rule(s, "alraso:es:t/sector#proh", SECTOR, "PROHIBITED")
    res = Resolver(s, spatial=provider([SECTOR, PARK])).resolve(inside_point_query())
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_explicit_override_relation_resolves_parent_child():
    s = three_scope_store()
    rule(s, "alraso:es:t/park#proh", PARK, "PROHIBITED")
    rule(s, "alraso:es:t/sector#perm", SECTOR, "PERMITTED")
    relation(s, "rr-sector-overrides-park", "alraso:es:t/sector#perm",
             "alraso:es:t/park#proh")
    res = Resolver(s, spatial=provider([PARK, SECTOR])).resolve(inside_point_query())
    # coordinate-mode PERMITTED additionally requires declared, reviewed
    # geometry provenance (none here) -> still not PERMITTED via coordinates.
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["PERMITTED_INVARIANT_VIOLATION"]
    res2 = Resolver(s).resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                                     knowledge_date="2023-06-15", spatial_scope_id=SECTOR))
    # scope-id mode sees only the sector (one scope declared): PERMITTED
    assert res2.legal_status is LegalStatus.PERMITTED


def test_three_levels_all_compose():
    s = three_scope_store()
    rule(s, "alraso:es:t/park#a", PARK, "PERMITTED")
    rule(s, "alraso:es:t/sector#b", SECTOR, "PERMITTED")
    rule(s, "alraso:es:t/deep#c", DEEP, "PROHIBITED")
    res = Resolver(s, spatial=provider([PARK, SECTOR, DEEP])).resolve(inside_point_query())
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    rules_in_conflict = {r for c in res.unresolved_conflicts for r in c["rules"]}
    assert "alraso:es:t/deep#c" in rules_in_conflict
    assert {h["scope_id"] for h in res.applicable_scope} == {PARK, SECTOR, DEEP}


def test_two_independent_overlapping_scopes():
    s = three_scope_store()
    rule(s, "alraso:es:t/sector#perm", SECTOR, "PERMITTED")
    rule(s, "alraso:es:t/deep#proh", DEEP, "AUTHORIZATION_REQUIRED")
    res = Resolver(s, spatial=provider([DEEP, SECTOR])).resolve(inside_point_query())
    # PERMITTED vs AUTHORIZATION_REQUIRED: different normative effects -> conflict
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert res.legal_status is LegalStatus.UNDETERMINED


def test_spatial_order_independent_all_permutations():
    expected = ("UNDETERMINED", "CONFLICTING", sorted([PARK, SECTOR, DEEP]))
    for order in itertools.permutations([PARK, SECTOR, DEEP]):
        s = three_scope_store()
        rule(s, "alraso:es:t/park#a", PARK, "PROHIBITED")
        rule(s, "alraso:es:t/sector#b", SECTOR, "PERMITTED")
        rule(s, "alraso:es:t/deep#c", DEEP, "PROHIBITED")
        res = Resolver(s, spatial=provider(list(order))).resolve(inside_point_query())
        canon = (res.legal_status.value, res.knowledge_status.value,
                 sorted(h["scope_id"] for h in res.applicable_scope))
        assert canon == expected, order


def test_provider_order_reversed_same_canonical_scope_set():
    s = three_scope_store()
    rule(s, "alraso:es:t/park#a", PARK, "PROHIBITED")
    rule(s, "alraso:es:t/sector#b", SECTOR, "PROHIBITED")
    q = inside_point_query()
    a = Resolver(s, spatial=provider([PARK, SECTOR])).resolve(q)
    b = Resolver(s, spatial=provider([SECTOR, PARK])).resolve(q)
    assert a.legal_status is b.legal_status is LegalStatus.PROHIBITED
    assert ([h["scope_id"] for h in a.applicable_scope]
            == [h["scope_id"] for h in b.applicable_scope])
    assert a.basis["rule_seqs"] == b.basis["rule_seqs"]


def test_no_pick_scope_helper_exists_anymore():
    assert not hasattr(Resolver, "_pick_scope")
    assert not hasattr(Resolver, "_has_parent_in")
