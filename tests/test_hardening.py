"""M1 final hardening round (H1-H6): the safety properties that the remediation
round left as residuals, each pinned by a test that fails on the pre-hardening
behaviour.

  H1/D2  same rule_id, simultaneously visible versions -> ambiguity, never a
         silent ranking (write-time refusal + read-time gate + verify_integrity)
  H2/D3  cited evidence must itself be publishable
  H3/D4  an applicable REGULATORY jurisdiction without publishable coverage is
         not permission; CONTEXT_ONLY is an explicit human declaration
  H4/D1  malformed input never escapes resolve() as a traceback
"""

from __future__ import annotations

import json
import math

import pytest

from alraso.bitemporal import PUBLISHABLE_FRAGMENT_STATUSES, BitemporalStore
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.errors import InvalidScope, OverlappingRuleVersions
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider
from conftest import DOC, ensure_doc, frag, new_store, raw_version, rule, scope

S = "s-hard"
ACT = "VIVAC_AL_RASO"
BASE = dict(activity=ACT, activity_date="2021-07-15",
            knowledge_date="2023-06-15", spatial_scope_id=S)
BOX_A = [[(42.00, 0.00), (42.00, 0.10), (42.10, 0.10), (42.10, 0.00)]]
BOX_B = [[(42.05, 0.05), (42.05, 0.15), (42.15, 0.15), (42.15, 0.05)]]
POINT_IN_BOTH = dict(lat=42.07, lon=0.07)


def q(**kw):
    return Query(**{**BASE, **kw})


def provider(*pairs) -> InMemorySpatialProvider:
    p = InMemorySpatialProvider()
    for scope_id, box in pairs:
        p.add_scope(scope_id, scope_id, "PARK_SECTOR", box)
    return p


# ==== H1/D2: overlapping visible versions of one rule_id are ambiguity ========
def test_write_refuses_contradictory_overlapping_lineage():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h1#a", S, "PERMITTED", ef="2020-01-01", et=None)
    with pytest.raises(OverlappingRuleVersions) as exc:
        rule(s, "alraso:es:t/h1#a", S, "PROHIBITED", ef="2021-01-01", et=None)
    assert exc.value.reason_code == "OVERLAPPING_RULE_VERSIONS"
    # a refused write leaves no trace: the earlier answer is untouched
    res = Resolver(s).resolve(q())
    assert res.legal_status is LegalStatus.PERMITTED


def test_write_refusal_is_rollback_safe_inside_transaction():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h1#b", S, "PERMITTED", ef="2020-01-01")
    with pytest.raises(OverlappingRuleVersions):
        with s.transaction():
            rule(s, "alraso:es:t/h1#b", S, "AUTHORIZATION_REQUIRED", ef="2021-06-01")
    rows = s.conn.execute("SELECT COUNT(*) FROM legal_rule_version").fetchone()[0]
    assert rows == 1


def test_legitimate_successor_lineage_is_not_a_conflict():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h1#c", S, "PERMITTED", ef="2020-01-01", et="2022-02-08")
    rule(s, "alraso:es:t/h1#c", S, "PROHIBITED", ef="2022-02-09", et=None)
    assert Resolver(s).resolve(q(activity_date="2021-07-15")).legal_status \
        is LegalStatus.PERMITTED
    assert Resolver(s).resolve(q(activity_date="2023-06-15")).legal_status \
        is LegalStatus.PROHIBITED


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
@pytest.mark.parametrize("recs", [("2020-06-01", "2020-07-01"),
                                  ("2020-07-01", "2020-06-01"),
                                  ("2023-01-01", "2020-06-01")])
def test_crafted_overlap_is_conflict_in_every_order(order, recs):
    """Read-side defence (legacy dump): never a winner by seq, recorded_at,
    insertion order, restrictiveness or permissiveness."""
    s = new_store()
    scope(s, S)
    rows = [("PERMITTED", "2020-01-01", None), ("PROHIBITED", "2021-01-01", None)]
    for idx in order:
        effect, ef, et = rows[idx]
        raw_version(s, "alraso:es:t/h1#d", effect, ef=ef, et=et, rec=recs[idx], scope_id=S)
    res = Resolver(s).resolve(q())
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert "OVERLAPPING_RULE_VERSIONS" in res.reason_codes
    assert res.unresolved_conflicts
    with pytest.raises(Exception):
        s.verify_integrity()


def test_identical_double_entry_is_reported_not_conflicting():
    s = new_store()
    scope(s, S)
    raw_version(s, "alraso:es:t/h1#e", "PERMITTED", ef="2020-01-01", et="2021-12-31",
                rec="2020-06-01", scope_id=S)
    raw_version(s, "alraso:es:t/h1#e", "PERMITTED", ef="2020-06-01", et="2022-12-31",
                rec="2020-07-01", scope_id=S)
    assert s.overlapping_duplicate_groups()
    res = Resolver(s).resolve(q())
    assert res.legal_status is LegalStatus.PERMITTED      # same legal content
    assert any("doble registro" in w for w in res.warnings)   # but never silent
    stages = [t["stage"] for t in res.precedence_trace]
    assert "overlapping_versions_duplicates" in stages


def test_late_discovery_of_contradiction_flips_the_later_answer():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h1#f", S, "PERMITTED", ef="2020-01-01", et=None,
         rec="2020-06-01")
    # discovered years later, overlapping lineage: ingestion refuses it outright
    with pytest.raises(OverlappingRuleVersions):
        rule(s, "alraso:es:t/h1#f", S, "PROHIBITED", ef="2021-01-01", et=None,
             rec="2027-05-10")
    assert Resolver(s).resolve(q(knowledge_date="2023-06-15")).legal_status \
        is LegalStatus.PERMITTED
    assert Resolver(s).resolve(q(knowledge_date="2028-01-01")).legal_status \
        is LegalStatus.PERMITTED     # the contradictory lineage was never accepted


# ==== H2/D3: evidence must itself be publishable =============================
def test_publishable_fragment_statuses_are_explicit_and_not_rule_vocabulary():
    assert PUBLISHABLE_FRAGMENT_STATUSES == frozenset({"VERIFIED", "PUBLISHED"})
    assert "REVIEW_REQUIRED" not in PUBLISHABLE_FRAGMENT_STATUSES


def test_fragment_default_is_not_publishable():
    s = new_store()
    ensure_doc(s)
    s.add_legal_fragment({"id": "lf-def", "source_document_id": DOC["id"],
                          "locator": "art. 1"})
    assert s.unpublishable_fragments(["lf-def"]) == ["lf-def"]


def test_verified_rule_over_unverified_fragment_cannot_permit():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h2#a", S, "PERMITTED", evidence=("lf-raw",),
         frag_status="DISCOVERED")
    res = Resolver(s).resolve(q())
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert "EVIDENCE_NOT_PUBLISHABLE" in res.reason_codes
    elig = next(t for t in res.precedence_trace if t["stage"] == "eligibility")
    assert any(r.startswith("EVIDENCE_NOT_PUBLISHABLE:lf-raw")
               for e in elig["excluded"] for r in e["reasons"])


def test_publishable_fragment_backs_a_normal_permit():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h2#b", S, "PERMITTED", evidence=("lf-ok",),
         frag_status="PUBLISHED")
    assert Resolver(s).resolve(q()).legal_status is LegalStatus.PERMITTED


def test_unpublishable_fragment_never_changes_a_prior_answer():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h2#c", S, "PERMITTED", evidence=("lf-ok2",))
    before = Resolver(s).resolve(q())
    assert before.legal_status is LegalStatus.PERMITTED
    rule(s, "alraso:es:t/h2#c2", S, "PROHIBITED", evidence=("lf-raw2",),
         frag_status="REVIEW_REQUIRED")
    after = Resolver(s).resolve(q())
    assert after.legal_status is LegalStatus.PERMITTED
    assert before.rule_versions == after.rule_versions


# ==== H3/D4: REGULATORY scopes demand coverage ===============================
def test_unmarked_scope_is_regulatory_and_uncovered_blocks_permit():
    s = new_store()
    scope(s, "s-a", geometry="src", review_status="VERIFIED")
    scope(s, "s-b", geometry="src", review_status="VERIFIED")   # no relevance given
    assert s.get_scope("s-b")["relevance"] == "REGULATORY"
    rule(s, "alraso:es:t/h3#a", "s-a", "PERMITTED")
    res = Resolver(s, spatial=provider(("s-a", BOX_A), ("s-b", BOX_B))).resolve(
        Query(activity=ACT, activity_date="2021-07-15", knowledge_date="2023-06-15",
              **POINT_IN_BOTH))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert "INCOMPLETE_SCOPE_COVERAGE" in res.reason_codes
    assert {u["scope_id"] for u in
            next(t for t in res.precedence_trace if t["stage"] == "scope_coverage")
            ["uncovered_regulatory"]} == {"s-b"}


def test_context_only_scope_does_not_block_permit():
    s = new_store()
    scope(s, "s-a", geometry="src", review_status="VERIFIED")
    scope(s, "s-b", geometry="src", relevance="CONTEXT_ONLY", review_status="VERIFIED")
    rule(s, "alraso:es:t/h3#b", "s-a", "PERMITTED")
    res = Resolver(s, spatial=provider(("s-a", BOX_A), ("s-b", BOX_B))).resolve(
        Query(activity=ACT, activity_date="2021-07-15", knowledge_date="2023-06-15",
              **POINT_IN_BOTH))
    assert res.legal_status is LegalStatus.PERMITTED
    assert "s-b" in next(t for t in res.precedence_trace
                         if t["stage"] == "scope_coverage")["context_only_scopes"]


def test_temporal_gap_in_regulatory_scope_blocks_permit():
    s = new_store()
    scope(s, "s-a", geometry="src", review_status="VERIFIED")
    scope(s, "s-b", geometry="src", review_status="VERIFIED")
    rule(s, "alraso:es:t/h3#c", "s-a", "PERMITTED")
    rule(s, "alraso:es:t/h3#d", "s-b", "PERMITTED", ef="2020-01-01", et="2020-12-31")
    res = Resolver(s, spatial=provider(("s-a", BOX_A), ("s-b", BOX_B))).resolve(
        Query(activity=ACT, activity_date="2021-07-15", knowledge_date="2023-06-15",
              **POINT_IN_BOTH))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert "INCOMPLETE_SCOPE_COVERAGE" in res.reason_codes
    gap = next(t for t in res.precedence_trace if t["stage"] == "scope_coverage")
    assert {"scope_id": "s-b", "reason": "TEMPORAL_GAP_IN_KNOWLEDGE"} \
        in gap["uncovered_regulatory"]


def test_documented_semantics_a_prohibition_may_stand_alone():
    """A restrictive answer rests on ONE positive prohibition and is legally
    sufficient even if a sibling jurisdiction is unmodelled: only affirmative
    permission claims demand complete REGULATORY coverage."""
    s = new_store()
    scope(s, "s-a", geometry="src", review_status="VERIFIED")
    scope(s, "s-b", geometry="src", review_status="VERIFIED")
    rule(s, "alraso:es:t/h3#e", "s-a", "PROHIBITED")
    res = Resolver(s, spatial=provider(("s-a", BOX_A), ("s-b", BOX_B))).resolve(
        Query(activity=ACT, activity_date="2021-07-15", knowledge_date="2023-06-15",
              **POINT_IN_BOTH))
    assert res.legal_status is LegalStatus.PROHIBITED
    assert any("cobertura regulatoria" in w or "cobertura incompleta" in w
               for w in res.warnings)


def test_relevance_vocabulary_is_closed():
    s = new_store()
    with pytest.raises(InvalidScope):
        scope(s, "s-x", relevance="PROBABLY_REGULATORY")
    with pytest.raises(InvalidScope):
        scope(s, "s-y", relevance="context_only")     # never inferred, never fuzzy


# ==== H4/D1: malformed facts never escape as a traceback =====================
MALFORMED = ["nope", [], 7, None, 3.5, True, {"a": float("nan")},
             {"a": float("inf")}, {"a": None}, {"a": object()},
             {1: "x"}, {"a": {"nested": 1}}]


@pytest.mark.parametrize("bad", MALFORMED)
def test_malformed_facts_fail_closed_without_traceback(bad):
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h4#a", S, "PERMITTED")
    res = Resolver(s).resolve(q(facts=bad))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert res.reason_codes and res.reason_codes[0] == "INVALID_FACT"
    assert res.decision_reason
    assert res.to_dict()             # serialization must not explode either


@pytest.mark.parametrize("bad", MALFORMED)
def test_malformed_facts_are_recorded_without_unsafe_json(bad):
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h4#b", S, "PERMITTED")
    res = Resolver(s).resolve(q(facts=bad), record=True)
    stored = s.conn.execute("SELECT canonical_query FROM determination").fetchall()
    assert len(stored) == 1
    assert "NaN" not in stored[0][0] and "Infinity" not in stored[0][0]
    canonical = json.loads(stored[0][0])          # strict JSON, replayable
    assert res.query["facts"] == canonical["facts"]
    if not isinstance(bad, dict):
        assert canonical["facts"]["__unvalidated_facts__"]["type"] == type(bad).__name__


def test_recording_a_malformed_query_does_not_raise():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h4#c", S, "PERMITTED")
    assert Resolver(s).resolve(q(facts="nope"), record=True).legal_status \
        is LegalStatus.UNDETERMINED


def test_valid_facts_still_evaluate():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/h4#d", S, "PERMITTED",
         condition={"field": "m", "op": "gte", "value": 0})
    res = Resolver(s).resolve(q(facts={"m": 5}))
    assert res.legal_status is LegalStatus.PERMITTED
    assert res.query["facts"] == {"m": 5}      # valid facts pass through verbatim


def test_non_finite_numbers_are_not_silently_accepted():
    for bad in (float("nan"), float("inf"), float("-inf")):
        assert math.isfinite(bad) is False
        s = new_store()
        scope(s, S)
        rule(s, "alraso:es:t/h4#e", S, "PERMITTED",
             condition={"field": "m", "op": "gte", "value": 0})
        res = Resolver(s).resolve(q(facts={"m": bad}))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert res.reason_codes[0] == "INVALID_FACT"


# ==== schema migration: legacy stores keep working, data untouched ===========
def test_legacy_database_gains_relevance_without_losing_rows(tmp_path):
    path = str(tmp_path / "legacy.db")
    s = BitemporalStore.connect(path)
    scope(s, S)
    rule(s, "alraso:es:t/h1#mig", S, "PERMITTED")
    s.conn.execute("ALTER TABLE spatial_scope DROP COLUMN relevance")
    s.conn.commit()
    s.conn.close()

    s2 = BitemporalStore.connect(path)          # additive migration on connect
    assert s2.get_scope(S)["relevance"] == "REGULATORY"
    assert s2.conn.execute("SELECT COUNT(*) FROM legal_rule_version").fetchone()[0] == 1
    assert Resolver(s2).resolve(q()).legal_status is LegalStatus.PERMITTED