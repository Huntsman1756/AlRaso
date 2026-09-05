"""R4 — safety invariants: every clause of the PERMITTED contract is
attacked; every conflict rule is checked; ineligible corpus additions never
move the public answer."""

from __future__ import annotations

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.engine import EngineCapabilities, EngineResult, JudgmentResult
from alraso.resolver import Resolver
from conftest import frag, new_store, relation, rule, scope

S = "s-inv"
Q = Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
          knowledge_date="2023-06-15", spatial_scope_id=S)


def good_store():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/inv#perm", S, "PERMITTED")
    return s


def test_baseline_permitted():
    res = Resolver(good_store()).resolve(Q)
    assert res.legal_status is LegalStatus.PERMITTED


# ---- clause-by-clause attacks on the invariant gate -----------------------------

class MutatingEngine:
    """Returns a PERMITTED judgment but violates one clause of the contract."""

    name = "mutant"
    version = "mutant/1"

    def __init__(self, violation):
        self.violation = violation

    def capabilities(self):
        return EngineCapabilities(True, frozenset({"const", "all", "any", "not", "field"}),
                                  frozenset({"eq", "neq", "gte", "gt", "lte", "lt", "in",
                                             "is_true", "is_false"}),
                                  frozenset({"PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED"}),
                                  True, True, True)

    def evaluate(self, versions, facts, mode="fast"):
        v = versions[0]
        if self.violation == "laundered_identity":
            j = JudgmentResult(rule_id="", rule_version_id=0, effect="PERMITTED",
                               outcome="holds")
        elif self.violation == "undetermined_outcome":
            j = JudgmentResult(rule_id=v.rule_id, rule_version_id=v.seq, effect="PERMITTED",
                               outcome="undetermined")
            return EngineResult(judgments=[j])
        else:
            j = JudgmentResult(rule_id=v.rule_id, rule_version_id=v.seq, effect="PERMITTED",
                               outcome="holds")
        return EngineResult(judgments=[j])


def test_identity_laundering_blocks_permitted():
    # layer 1: foreign/absent version ids are caught as ENGINE_IDENTITY_MISMATCH
    res = Resolver(good_store(), engine=MutatingEngine("laundered_identity")).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["ENGINE_IDENTITY_MISMATCH"]

    # layer 2 (invariant gate): right seq but laundered rule_id string
    class LaunderedSeq:
        name = "laundered"
        version = "l/1"

        def capabilities(self):
            return EngineCapabilities(True, frozenset(), frozenset(),
                                      frozenset({"PERMITTED"}), True, True, True)

        def evaluate(self, versions, facts, mode="fast"):
            v = versions[0]
            return EngineResult(judgments=[JudgmentResult(
                rule_id="axiom", rule_version_id=v.seq, effect="PERMITTED", outcome="holds")])

    res2 = Resolver(good_store(), engine=LaunderedSeq()).resolve(Q)
    assert res2.legal_status is LegalStatus.UNDETERMINED
    assert res2.reason_codes == ["PERMITTED_INVARIANT_VIOLATION"]


def test_undetermined_outcome_never_promoted():
    res = Resolver(good_store(), engine=MutatingEngine("undetermined_outcome")).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED


def test_ineligible_participant_blocks_permitted(monkeypatch):
    # simulate an eligibility race: the gate re-checks participants
    import alraso.resolver as R
    res = Resolver(good_store()).resolve(Q)
    assert res.legal_status is LegalStatus.PERMITTED
    monkeypatch.setattr(R, "is_rule_version_eligible",
                        lambda v, store: ["RACE_SIMULATED"])
    res2 = Resolver(good_store()).resolve(Q)
    assert res2.legal_status is LegalStatus.UNDETERMINED   # excluded upstream


def test_broken_evidence_blocks_permitted():
    # rule claims an evidence id that exists nowhere: eligibility excludes it
    s = new_store()
    scope(s, S)
    s.add_rule_version({"rule_id": "alraso:es:t/inv#broken", "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": S, "effect": "PERMITTED",
                        "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                        "review_status": "PUBLISHED", "legal_review_complete": True,
                        "evidence": ["lf-vanished"]})
    res = Resolver(s).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED


# ---- conflict invariant ------------------------------------------------------------

def test_conflict_is_never_permissive():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/cf#perm", S, "PERMITTED")
    rule(s, "alraso:es:t/cf#proh", S, "PROHIBITED")
    res = Resolver(s).resolve(Q)
    assert (res.legal_status, res.knowledge_status) == (LegalStatus.UNDETERMINED,
                                                        KnowledgeStatus.CONFLICTING)


def test_three_way_conflict_requires_full_resolution():
    s = new_store()
    scope(s, S)
    for rid, eff in (("p", "PERMITTED"), ("q", "PROHIBITED"), ("r", "AUTHORIZATION_REQUIRED")):
        rule(s, f"alraso:es:t/cf3#{rid}", S, eff)
    relation(s, "rr-pq", "alraso:es:t/cf3#p", "alraso:es:t/cf3#q")
    res = Resolver(s).resolve(Q)
    # p beats q, but r remains: two distinct surviving effects -> conflict
    assert res.knowledge_status is KnowledgeStatus.CONFLICTING
    assert res.legal_status is LegalStatus.UNDETERMINED


def test_three_way_conflict_full_resolution_wins():
    s = new_store()
    scope(s, S)
    for rid, eff in (("p", "PERMITTED"), ("q", "PROHIBITED"), ("r", "AUTHORIZATION_REQUIRED")):
        rule(s, f"alraso:es:t/cf3b#{rid}", S, eff)
    relation(s, "rr-pq", "alraso:es:t/cf3b#p", "alraso:es:t/cf3b#q")
    relation(s, "rr-pr", "alraso:es:t/cf3b#p", "alraso:es:t/cf3b#r")
    res = Resolver(s).resolve(Q)
    assert res.legal_status is LegalStatus.PERMITTED


# ---- corpus eligibility invariant ------------------------------------------------------

def test_adding_relation_unreviewed_does_not_change_result():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/ci#a", S, "PERMITTED")
    rule(s, "alraso:es:t/ci#b", S, "PROHIBITED")
    r = Resolver(s)
    before = r.resolve(Q)
    assert before.knowledge_status is KnowledgeStatus.CONFLICTING
    relation(s, "rr-ci", "alraso:es:t/ci#a", "alraso:es:t/ci#b",
             human_verified=False, review_status="REVIEW_REQUIRED",
             legal_review_complete=False)
    after = r.resolve(Q)
    assert (after.legal_status, after.knowledge_status) == \
        (before.legal_status, before.knowledge_status)


def test_adding_ineligible_permitted_rule_does_not_change_result():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/ci2#a", S, "PROHIBITED")
    r = Resolver(s)
    before = r.resolve(Q)
    s.add_rule_version({"rule_id": "alraso:es:t/ci2#ghost", "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": S, "effect": "PERMITTED",
                        "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                        "review_status": "DISCOVERED", "evidence": []})
    after = r.resolve(Q)
    assert after.legal_status is before.legal_status is LegalStatus.PROHIBITED


# ---- engine invariants (§28) ------------------------------------------------------------

def test_engine_failures_never_permitted():
    exc = RuntimeError("engine exploded")

    class Failing:
        name = "fail"
        version = "fail/1"

        def capabilities(self):
            return EngineCapabilities(True, frozenset(), frozenset(),
                                      frozenset({"PERMITTED"}), True, True, True)

        def evaluate(self, versions, facts, mode="fast"):
            raise exc
    res = Resolver(good_store(), engine=Failing()).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED


def test_capability_mismatch_never_permitted():
    class OnlyProhibited:
        name = "proh-only"
        version = "p/1"

        def capabilities(self):
            return EngineCapabilities(True, frozenset(), frozenset(),
                                      frozenset({"PROHIBITED"}), True, True, True)

        def evaluate(self, versions, facts, mode="fast"):
            raise AssertionError("must never be called")
    res = Resolver(good_store(), engine=OnlyProhibited()).resolve(Q)
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes[0].startswith("UNSUPPORTED_ENGINE_CAPABILITY")


# ---- spatial invariant (§29): same canonical answer under every provider order ----------

def test_same_canonical_result_under_every_scope_order():
    import itertools
    from alraso.spatial import InMemorySpatialProvider
    A = "s-oa"
    B = "s-ob"
    rings = {
        A: [[(42.0, 0.0), (42.0, 0.2), (42.2, 0.2), (42.2, 0.0)]],
        B: [[(42.05, 0.05), (42.05, 0.15), (42.15, 0.15), (42.15, 0.05)]],
    }
    answers = set()
    for order in itertools.permutations([A, B]):
        s = new_store()
        scope(s, A)
        scope(s, B, parent=A)
        rule(s, "alraso:es:t/or#a", A, "PROHIBITED")
        rule(s, "alraso:es:t/or#b", B, "PROHIBITED")
        prov = InMemorySpatialProvider()
        for sid in order:
            prov.add_scope(sid, sid, "OTHER", rings[sid])
        res = Resolver(s, spatial=prov).resolve(
            Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                  knowledge_date="2023-06-15", lat=42.1, lon=0.1))
        answers.add((res.legal_status.value, res.knowledge_status.value,
                     tuple(res.basis["scope_ids"]), tuple(res.basis["rule_seqs"])))
    assert len(answers) == 1


# ---- never-permit sweep over adversarial corpora ------------------------------------------

def test_adversarial_sweep_no_false_permitted():
    """Any corpus mutation that breaks a safety axis must not yield
    PERMITTED where the safe answer is not established."""
    variants = {
        "no_evidence": dict(evidence=None),
        "review_required": dict(review="REVIEW_REQUIRED", legal=False),
        "legal_reviewed_only": dict(review="LEGAL_REVIEWED"),
        "spatial_pending_flag": dict(spatial=False),
        "relation_unverified": dict(rel_kw=dict(human_verified=False)),
        "relation_unreviewed": dict(rel_kw=dict(review_status="LEGAL_REVIEWED",
                                                legal_review_complete=False)),
        "relation_expired": dict(rel_kw=dict(effective_to="2020-12-31")),
        "relation_not_visible": dict(rel_kw=dict(recorded_at="2027-01-01")),
    }
    for name, kw in variants.items():
        s = new_store()
        scope(s, S)
        perm_kw = {k: v for k, v in kw.items() if k != "rel_kw"}
        if perm_kw:
            rule(s, "alraso:es:t/sw#perm", S, "PERMITTED", **perm_kw)
        else:
            rule(s, "alraso:es:t/sw#perm", S, "PERMITTED")
        rule(s, "alraso:es:t/sw#proh", S, "PROHIBITED")
        if "rel_kw" in kw:
            relation(s, "rr-sw", "alraso:es:t/sw#perm", "alraso:es:t/sw#proh",
                     **kw["rel_kw"])
        res = Resolver(s).resolve(Q)
        assert res.legal_status is not LegalStatus.PERMITTED, \
            f"variant {name} produced unsafe PERMITTED"
