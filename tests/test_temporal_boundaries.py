"""§30 — exact temporal boundaries for LegalRuleVersion AND
RuleRelationVersion. Documented conventions:

  VALID time:   [effective_from, effective_to]  CLOSED at both ends
  SYSTEM time:  [recorded_at, recorded_until)   closed start, OPEN end

ISO strings are compared lexically ONLY because every boundary is calendar-
validated strictly at write and read time (tests/test_validation.py).
"""

from __future__ import annotations

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.resolver import Resolver
from conftest import new_store, relation, rule, scope

S = "s-tb"


def store_with_rule(ef="2021-01-01", et="2021-12-31", rec="2020-06-01", rec_until=None):
    s = new_store()
    scope(s, S)
    s.add_rule_version({"rule_id": "r-tb", "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": S, "effect": "PROHIBITED",
                        "effective_from": ef, "effective_to": et,
                        "recorded_at": rec, "recorded_until": rec_until,
                        "review_status": "VERIFIED", "legal_review_complete": True,
                        "evidence": []})
    return s


def sel(s, ad, kd):
    return s.select("VIVAC_AL_RASO", S, ad, kd).covering


def test_rule_version_valid_time_closed_boundaries():
    s = store_with_rule()
    assert sel(s, "2021-01-01", "2023-06-15")            # effective_from inclusive
    assert sel(s, "2021-12-31", "2023-06-15")            # effective_to inclusive
    assert not sel(s, "2020-12-31", "2023-06-15")        # one day before
    assert not sel(s, "2022-01-01", "2023-06-15")        # one day after


def test_rule_version_system_time_boundaries():
    s = store_with_rule(rec="2020-06-01", rec_until="2023-06-15")
    assert sel(s, "2021-06-15", "2020-06-01")            # recorded_at inclusive
    assert not sel(s, "2021-06-15", "2020-05-31")        # before recorded_at
    assert sel(s, "2021-06-15", "2023-06-14")            # recorded_until - epsilon
    assert not sel(s, "2021-06-15", "2023-06-15")        # recorded_until exclusive


def test_relation_version_bitemporal_boundaries():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/tb#winner", S, "PERMITTED")
    rule(s, "alraso:es:t/tb#loser", S, "PROHIBITED")
    relation(s, "rr-tb", "alraso:es:t/tb#winner", "alraso:es:t/tb#loser",
             effective_from="2021-01-01", effective_to="2021-12-31",
             recorded_at="2020-06-01", recorded_until="2023-06-15")

    def rels(kd, ad="2021-06-15"):
        return [r.relation_id for r in s.relations_at(
            ["alraso:es:t/tb#winner", "alraso:es:t/tb#loser"], ad, kd)]

    assert "rr-tb" in rels("2021-06-15")                  # visible
    assert "rr-tb" in rels("2020-06-01")                  # recorded_at inclusive
    assert "rr-tb" not in rels("2020-05-31")              # before recorded_at
    assert "rr-tb" in rels("2023-06-14")                  # recorded_until - epsilon
    assert "rr-tb" not in rels("2023-06-15")              # recorded_until exclusive
    assert "rr-tb" in rels("2021-06-15", ad="2021-01-01")  # effective_from inclusive
    assert "rr-tb" in rels("2021-06-15", ad="2021-12-31")  # effective_to inclusive
    assert "rr-tb" not in rels("2021-06-15", ad="2022-01-01")  # validity ended


def test_relation_replacement_lineage():
    # a NEW description of the same relation_id (lineage collapse) supersedes
    # the old one at later knowledge dates, without any UPDATE
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/tb2#w", S, "PERMITTED")
    rule(s, "alraso:es:t/tb2#l", S, "PROHIBITED")
    relation(s, "rr-lin", "alraso:es:t/tb2#w", "alraso:es:t/tb2#l",
             effective_from="2020-01-01", recorded_at="2020-06-01")
    relation(s, "rr-lin", "alraso:es:t/tb2#w", "alraso:es:t/tb2#l",
             effective_from="2020-01-01", recorded_at="2024-01-01",
             effective_to="2020-12-31")  # retrospective: it actually ended
    early = [r for r in s.relations_at(["alraso:es:t/tb2#w", "alraso:es:t/tb2#l"],
                                       "2021-06-15", "2023-06-15")]
    late = [r for r in s.relations_at(["alraso:es:t/tb2#w", "alraso:es:t/tb2#l"],
                                      "2021-06-15", "2025-01-01")]
    assert early and early[0].effective_to is None
    assert late == []  # at late knowledge the relation no longer covers 2021


def test_relation_bitemporal_replay_question():
    # "what precedences did the system know on that date?" — with knowledge
    # 2023 the override did not exist yet; with 2028 it does.
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/tb3#a", S, "PERMITTED")
    rule(s, "alraso:es:t/tb3#b", S, "PROHIBITED")
    relation(s, "rr-rp", "alraso:es:t/tb3#a", "alraso:es:t/tb3#b",
             recorded_at="2027-05-10")
    r = Resolver(s)
    q = dict(activity="VIVAC_AL_RASO", activity_date="2021-07-15", spatial_scope_id=S)
    early = r.resolve(Query(**q, knowledge_date="2023-06-15"))
    late = r.resolve(Query(**q, knowledge_date="2028-01-01"))
    assert early.knowledge_status is KnowledgeStatus.CONFLICTING
    assert late.legal_status is LegalStatus.PERMITTED
