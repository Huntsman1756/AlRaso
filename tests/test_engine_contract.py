"""F02 — SHARED engine contract suite.

The exact same battery runs against OwnEvaluatorAdapter and (when the real
binary is provided) AxiomCliAdapter. Every case a given adapter declares
unsupported must fail closed with UnsupportedEngineCapability — never a
silent approximation, never a PERMITTED.
"""

from __future__ import annotations

import os

import pytest

from alraso.bitemporal import VersionRow
from alraso.engine import OwnEvaluatorAdapter
from alraso.engine_axiom import AxiomCliAdapter
from alraso.errors import EngineFailure, UnsupportedEngineCapability

BIN = os.environ.get("ALRASO_AXIOM_BIN", "")
ROOT = os.environ.get("ALRASO_AXIOM_ROOT", "")
AXIOM_READY = bool(BIN and ROOT and os.path.exists(BIN)
                   and os.path.basename(ROOT.rstrip("/\\")).startswith("rulespec-"))


def axiom_adapter(tmp_path) -> AxiomCliAdapter:
    return AxiomCliAdapter(BIN, ROOT, tmp_path / "axiom-cache")


def make_version(seq=1, rule_id="alraso:es:t/c#a", effect="PERMITTED", condition=None,
                 activity="VIVAC_AL_RASO"):
    return VersionRow(seq=seq, rule_id=rule_id, activity=activity,
                      spatial_scope_id="s-x", effect=effect, condition=condition,
                      effective_from="2020-01-01", effective_to=None,
                      recorded_at="2020-06-01", recorded_until=None,
                      evidence=["lf-x"], interpretation_note=None,
                      review_status="VERIFIED", legal_review_complete=True,
                      evidence_required=True)


def adapters():
    yield pytest.param("own", OwnEvaluatorAdapter(), id="own")
    if AXIOM_READY:
        yield pytest.param("axiom", None, id="axiom")  # adapter built per-test (cache dir)


def evaluate(adapter, versions, facts):
    return adapter.evaluate(versions, facts)


def holds_ids(result):
    return sorted(j.rule_id for j in result.judgments if j.outcome == "holds")


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

def test_condition_true(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        cond = {"const": True}
        if not _supports_conditions(adapter):
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, [make_version(condition=cond)], {})
            continue
        res = evaluate(adapter, [make_version(condition=cond)], {})
        assert holds_ids(res) == ["alraso:es:t/c#a"]


def test_condition_false(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        if not _supports_conditions(adapter):
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, [make_version(condition={"const": False})], {})
            continue
        res = evaluate(adapter, [make_version(condition={"const": False})], {})
        assert holds_ids(res) == []


def test_condition_missing_fact_fails_closed(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        cond = {"field": "altitude_m", "op": "gte", "value": 1800}
        if not _supports_conditions(adapter):
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, [make_version(condition=cond)], {})
            continue
        with pytest.raises(EngineFailure):
            evaluate(adapter, [make_version(condition=cond)], {})


def test_condition_invalid_never_permits(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        cond = {"field": "altitude_m", "op": "gte", "value": "abc"}
        if not _supports_conditions(adapter):
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, [make_version(condition=cond)], {})
            continue
        with pytest.raises(EngineFailure):
            evaluate(adapter, [make_version(condition=cond)],
                     {"altitude_m": "abc"})


# ---------------------------------------------------------------------------
# Effects (all modelled in M1: PERMITTED / PROHIBITED / AUTHORIZATION_REQUIRED)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("effect", ["PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED"])
def test_effects_identity_and_support(tmp_path, effect):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        caps = adapter.capabilities()
        v = make_version(effect=effect)
        if effect not in caps.supports_effects:
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, [v], {})
            continue
        res = evaluate(adapter, [v], {})
        assert holds_ids(res) == ["alraso:es:t/c#a"]
        j = res.judgments[0]
        assert j.effect == effect


# ---------------------------------------------------------------------------
# Multiple rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("effects,expect_holds", [
    (["PERMITTED", "PERMITTED"], 2),
    (["PERMITTED", "PROHIBITED"], 2),
    (["PROHIBITED", "AUTHORIZATION_REQUIRED"], 2),
])
def test_multiple_rules(tmp_path, effects, expect_holds):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        versions = [make_version(seq=i + 1, rule_id=f"alraso:es:t/c#m{i}", effect=e)
                    for i, e in enumerate(effects)]
        if not adapter.capabilities().supports_multiple_rules:
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, versions, {})
            continue
        res = evaluate(adapter, versions, {})
        assert len(holds_ids(res)) == expect_holds


# ---------------------------------------------------------------------------
# Facts (all facts currently supported by the own evaluator AST)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cond,facts,expect", [
    ({"field": "altitude_m", "op": "gte", "value": 1800}, {"altitude_m": 2000}, True),
    ({"field": "altitude_m", "op": "gte", "value": 1800}, {"altitude_m": 1500}, False),
    ({"field": "activity_name", "op": "in", "value": ["VIVAC_AL_RASO"]},
     {"activity_name": "VIVAC_AL_RASO"}, True),
    ({"field": "group_size", "op": "lte", "value": 3}, {"group_size": 4}, False),
    ({"field": "inside_park", "op": "is_true"}, {"inside_park": True}, True),
    ({"field": "inside_park", "op": "is_false"}, {"inside_park": False}, True),
    ({"all": [{"field": "altitude_m", "op": "gte", "value": 100},
              {"field": "flag", "op": "eq", "value": "x"}]},
     {"altitude_m": 200, "flag": "x"}, True),
    ({"not": {"field": "flag", "op": "is_true"}}, {"flag": False}, True),
])
def test_facts_matrix(tmp_path, cond, facts, expect):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        if not _supports_conditions(adapter):
            with pytest.raises(UnsupportedEngineCapability):
                evaluate(adapter, [make_version(condition=cond)], facts)
            continue
        res = evaluate(adapter, [make_version(condition=cond)], facts)
        assert (holds_ids(res) == ["alraso:es:t/c#a"]) is expect


def test_activity_fact_supported(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        assert adapter.capabilities().supports_activity is True


# ---------------------------------------------------------------------------
# Identity + evidence traceability
# ---------------------------------------------------------------------------

def test_rule_identity_never_laundered(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        assert adapter.capabilities().supports_rule_identity, name
        res = evaluate(adapter, [make_version(rule_id="alraso:es:t/keep#id", seq=77)], {})
        assert len(res.judgments) == 1
        j = res.judgments[0]
        assert j.rule_id == "alraso:es:t/keep#id"
        assert j.rule_version_id == 77
        assert j.rule_id != adapter.name  # no identity laundering


def test_judgments_map_back_to_versions_and_evidence(tmp_path):
    for name, _ in _cases(tmp_path):
        adapter = _mk(name, tmp_path)
        v = make_version(rule_id="alraso:es:t/ev#a", seq=5)
        res = evaluate(adapter, [v], {})
        j = res.by_rule()["alraso:es:t/ev#a"]
        # evidence mapping: version.seq -> judgment.rule_version_id lets the
        # resolver join back to store evidence (v.evidence is canonical)
        assert j.rule_version_id == v.seq
        assert v.evidence  # and the store row keeps the evidence ids


# ---- helpers ----------------------------------------------------------------

def _cases(tmp_path):
    if AXIOM_READY:
        return [("own", None), ("axiom", None)]
    return [("own", None)]


def _mk(name, tmp_path):
    if name == "own":
        return OwnEvaluatorAdapter()
    return axiom_adapter(tmp_path)


def _supports_conditions(adapter):
    caps = adapter.capabilities()
    # "conditions supported" means the adapter accepts BOTH const and field
    # nodes, not merely declares ops.
    return {"const", "field"} <= caps.supports_condition_kinds
