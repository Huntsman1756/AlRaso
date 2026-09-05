"""F04 — precedence resolves the COMPLETE active set. No first-wins, no
latest-wins, no partial overrides hiding third-party conflicts, cycles are
conflicts, and relation applicability (review/verification/temporality) is
enforced."""

from __future__ import annotations

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.resolver import Resolver
from conftest import new_store, relation, rule, scope

S = "s-prec"
Q = Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
          knowledge_date="2023-06-15", spatial_scope_id=S)


def base_store():
    s = new_store()
    scope(s, S)
    return s


def test_partial_override_does_not_hide_third_conflict():
    s = base_store()
    rule(s, "alraso:es:t/x#a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#b", S, "PROHIBITED")
    rule(s, "alraso:es:t/x#c", S, "PROHIBITED")
    relation(s, "rr-a-over-b", "alraso:es:t/x#a", "alraso:es:t/x#b")
    res = Resolver(s).resolve(Q)
    # A defeats B, but C (PROHIBITED) is untouched -> A vs C conflict remains
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert any("a" in c["note"].lower() or c["effects"] == ["PERMITTED", "PROHIBITED"]
               for c in res.unresolved_conflicts)


def test_full_override_of_every_conflicting_rule_resolves():
    s = base_store()
    rule(s, "alraso:es:t/x#a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#b", S, "PROHIBITED")
    rule(s, "alraso:es:t/x#c", S, "PROHIBITED")
    relation(s, "rr-a-over-b", "alraso:es:t/x#a", "alraso:es:t/x#b")
    relation(s, "rr-a-over-c", "alraso:es:t/x#a", "alraso:es:t/x#c")
    res = Resolver(s).resolve(Q)
    assert res.legal_status is LegalStatus.PERMITTED
    assert len(res.basis["relation_seqs"]) == 2


def test_precedence_cycle_conflicts():
    s = base_store()
    rule(s, "alraso:es:t/x#loopa", S, "PERMITTED")
    rule(s, "alraso:es:t/x#loopb", S, "PROHIBITED")
    relation(s, "rr-a-b", "alraso:es:t/x#loopa", "alraso:es:t/x#loopb")
    relation(s, "rr-b-a", "alraso:es:t/x#loopb", "alraso:es:t/x#loopa")
    res = Resolver(s).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert any("CYCLE" in c["note"] for c in res.unresolved_conflicts)


def test_override_chain_does_not_transitively_win():
    # A overrides B; B overrides C. Grounded semantics: A in, B out, C in.
    # If A and C disagree the conflict must surface (B's victory over C does
    # not launder A's non-decision about C).
    s = base_store()
    rule(s, "alraso:es:t/x#chain-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#chain-b", S, "PROHIBITED")
    rule(s, "alraso:es:t/x#chain-c", S, "PERMITTED")
    relation(s, "rr-ab", "alraso:es:t/x#chain-a", "alraso:es:t/x#chain-b")
    relation(s, "rr-bc", "alraso:es:t/x#chain-b", "alraso:es:t/x#chain-c")
    res = Resolver(s).resolve(Q)
    assert res.legal_status is LegalStatus.PERMITTED   # A and C both survive, same effect
    # and the B->C edge never made C PROHIBITED:
    assert res.basis["rule_seqs"] != []


def test_relation_effect_filters_apply():
    # relation claims to defeat a PROHIBITED target, but the active B is
    # AUTHORIZATION_REQUIRED: the relation must NOT apply.
    s = base_store()
    rule(s, "alraso:es:t/x#f-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#f-b", S, "AUTHORIZATION_REQUIRED")
    relation(s, "rr-f", "alraso:es:t/x#f-a", "alraso:es:t/x#f-b",
             from_effect="PERMITTED", to_effect="PROHIBITED")
    res = Resolver(s).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_unverified_relation_cannot_resolve():
    s = base_store()
    rule(s, "alraso:es:t/x#uv-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#uv-b", S, "PROHIBITED")
    relation(s, "rr-uv", "alraso:es:t/x#uv-a", "alraso:es:t/x#uv-b",
             human_verified=False)
    res = Resolver(s).resolve(Q)
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_unreviewed_relation_cannot_resolve():
    s = base_store()
    rule(s, "alraso:es:t/x#ur-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#ur-b", S, "PROHIBITED")
    relation(s, "rr-ur", "alraso:es:t/x#ur-a", "alraso:es:t/x#ur-b",
             review_status="REVIEW_REQUIRED", legal_review_complete=False)
    res = Resolver(s).resolve(Q)
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_relation_not_yet_effective_is_not_used():
    s = base_store()
    rule(s, "alraso:es:t/x#ne-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#ne-b", S, "PROHIBITED")
    relation(s, "rr-ne", "alraso:es:t/x#ne-a", "alraso:es:t/x#ne-b",
             effective_from="2022-01-01")
    res = Resolver(s).resolve(Q)  # activity_date 2021-07-15
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_expired_relation_is_not_used():
    s = base_store()
    rule(s, "alraso:es:t/x#ex-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#ex-b", S, "PROHIBITED")
    relation(s, "rr-ex", "alraso:es:t/x#ex-a", "alraso:es:t/x#ex-b",
             effective_to="2021-01-01")
    res = Resolver(s).resolve(Q)
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING


def test_relation_discovered_later_only_matters_later_knowledge():
    # The relation exists but was recorded 2027: with knowledge 2023 it may
    # not be used; with knowledge 2028 it may (classic bitemporal replay).
    s = base_store()
    rule(s, "alraso:es:t/x#ld-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#ld-b", S, "PROHIBITED")
    relation(s, "rr-ld", "alraso:es:t/x#ld-a", "alraso:es:t/x#ld-b",
             recorded_at="2027-05-10")
    r = Resolver(s)
    early = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                            knowledge_date="2023-06-15", spatial_scope_id=S))
    late = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                           knowledge_date="2028-01-01", spatial_scope_id=S))
    assert early.knowledge_status is KnowledgeStatus.CONFLICTING
    assert late.legal_status is LegalStatus.PERMITTED


def test_relation_insertion_order_irrelevant():
    a = base_store()
    relation(a, "rr-1", "alraso:es:t/x#o-a", "alraso:es:t/x#o-b")
    rule(a, "alraso:es:t/x#o-a", S, "PERMITTED")
    rule(a, "alraso:es:t/x#o-b", S, "PROHIBITED")
    b = base_store()
    rule(b, "alraso:es:t/x#o-a", S, "PERMITTED")
    rule(b, "alraso:es:t/x#o-b", S, "PROHIBITED")
    relation(b, "rr-1", "alraso:es:t/x#o-a", "alraso:es:t/x#o-b")
    ra, rb = Resolver(a).resolve(Q), Resolver(b).resolve(Q)
    assert ra.legal_status is rb.legal_status is LegalStatus.PERMITTED


def test_unknown_relation_type_never_resolves():
    import pytest

    from alraso.errors import InvalidRelation
    s = base_store()
    rule(s, "alraso:es:t/x#ut-a", S, "PERMITTED")
    rule(s, "alraso:es:t/x#ut-b", S, "PROHIBITED")
    with pytest.raises(InvalidRelation):
        s.add_relation({
            "relation_id": "rr-ut", "relation_type": "SOMETHING_NOVEL",
            "from_rule_id": "alraso:es:t/x#ut-a", "to_rule_id": "alraso:es:t/x#ut-b",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "human_verified": True})
    # nothing leaked into the DB: no relation exists to resolve with
    assert s.relations_at(["alraso:es:t/x#ut-a", "alraso:es:t/x#ut-b"],
                          "2021-07-15", "2023-06-15") == []
