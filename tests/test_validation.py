"""F06 — strict validation. No ambiguous coercions, no lexical date tricks,
no NaN/Infinity, full AST validation, canonical booleans only."""

from __future__ import annotations

import math

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.conditions import BadCondition, evaluate
from alraso.errors import InvalidCondition, InvalidDate, InvalidFact, InvalidRelation, InvalidRule
from alraso.validation import (
    parse_bool_strict,
    parse_date_strict,
    parse_number_strict,
    validate_condition,
    validate_facts,
)
from conftest import new_store, scope

# ---- booleans ------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["true", "false", "False", "no", "off", "yes", "1.0", "",
                                 None, 2, -1, 1.0, [], {}, object()])
def test_noncanonical_boolean_rejected(bad):
    with pytest.raises(InvalidFact):
        parse_bool_strict(bad, field="human_verified")


@pytest.mark.parametrize("ok,val", [(True, True), (False, False), (0, False), (1, True)])
def test_canonical_boolean_accepted(ok, val):
    assert parse_bool_strict(ok, field="x") is val


def test_relation_human_verified_false_string_rejected():
    s = new_store()
    scope(s, "s-v")
    with pytest.raises(InvalidFact):
        s.add_relation({"relation_id": "r1", "relation_type": "OVERRIDES",
                        "from_rule_id": "a", "to_rule_id": "b",
                        "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                        "human_verified": "false"})


# ---- dates ----------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["2021-02-31", "2021-13-01", "2021-3-4", "2021-02-29",
                                 "not-a-date", "2021-02-01T00:00:00", "", None, 20210201,
                                 "2021-00-10", "0000-01-01x"])
def test_invalid_dates_rejected(bad):
    with pytest.raises(InvalidDate):
        parse_date_strict(bad, field="d")


@pytest.mark.parametrize("good", ["2020-02-29", "2021-07-15", "1900-01-01", "2100-12-31"])
def test_valid_dates_accepted(good):
    assert parse_date_strict(good, field="d").isoformat() == good


def test_rule_write_rejects_invalid_dates():
    s = new_store()
    scope(s, "s-v")
    with pytest.raises(InvalidDate):
        s.add_rule_version({"rule_id": "r", "activity": "VIVAC_AL_RASO",
                            "spatial_scope_id": "s-v", "effect": "PERMITTED",
                            "effective_from": "2021-02-31", "recorded_at": "2020-06-01"})


def test_query_dates_validated_by_resolver():
    from alraso.domain import LegalStatus, Query
    from alraso.resolver import Resolver
    s = new_store()
    scope(s, "s-v")
    res = Resolver(s).resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-02-31",
                                    knowledge_date="2023-06-15", spatial_scope_id="s-v"))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["INVALID_DATE"]


def test_selection_dates_validated():
    s = new_store()
    with pytest.raises(InvalidDate):
        s.select("VIVAC_AL_RASO", "s", "2021-02-31", "2023-06-15")


# ---- numbers ----------------------------------------------------------------------

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "1800", "abc",
                                 True, False, None, [], {}])
def test_nonfinite_or_nonnumeric_rejected(bad):
    with pytest.raises(InvalidFact):
        parse_number_strict(bad, field="altitude_m")


def test_fact_nan_rejected_end_to_end():
    from alraso.domain import LegalStatus, Query
    from alraso.resolver import Resolver
    s = new_store()
    scope(s, "s-v")
    s.add_rule_version({
        "rule_id": "r", "activity": "VIVAC_AL_RASO", "spatial_scope_id": "s-v",
        "effect": "PERMITTED", "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
        "condition": {"field": "altitude_m", "op": "gte", "value": 1800},
        "review_status": "VERIFIED", "legal_review_complete": True,
        "evidence": ["lf-x"]})
    res = Resolver(s).resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                                    knowledge_date="2023-06-15", spatial_scope_id="s-v",
                                    facts={"altitude_m": float("nan")}))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["INVALID_FACT"]


def test_altitude_string_fact_not_silently_compared():
    from alraso.domain import LegalStatus, Query
    from alraso.resolver import Resolver
    from conftest import frag
    s = new_store()
    scope(s, "s-v")
    frag(s, "lf-x")
    s.add_rule_version({
        "rule_id": "r", "activity": "VIVAC_AL_RASO", "spatial_scope_id": "s-v",
        "effect": "PERMITTED", "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
        "condition": {"field": "altitude_m", "op": "gte", "value": 1800},
        "review_status": "VERIFIED", "legal_review_complete": True,
        "evidence": ["lf-x"]})
    # altitude_m="abc": valid string fact, but numeric op on a string is a hard
    # condition error (never a guess, never PERMITTED)
    res = Resolver(s).resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                                    knowledge_date="2023-06-15", spatial_scope_id="s-v",
                                    facts={"altitude_m": "abc"}))
    assert res.legal_status is LegalStatus.UNDETERMINED


# ---- AST -----------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"op": "eq"},                                              # no node kind
    {"const": "true"},                                         # const not bool
    {"const": True, "extra": 1},                               # unexpected key
    {"all": {"field": "x"}},                                   # all must be list
    {"all": [{"op": "wat"}]},                                  # nested garbage
    {"field": "", "op": "eq", "value": 1},                     # empty field
    {"field": "x", "op": "matches", "value": 1},               # unknown op
    {"field": "x", "op": "gte", "value": "abc"},               # numeric op w/ text
    {"field": "x", "op": "gte", "value": float("nan")},        # numeric op w/ NaN
    {"field": "x", "op": "in", "value": []},                   # empty membership
    {"field": "x", "op": "in", "value": "abc"},                # membership not list
    {"not": {}},                                               # empty not
    [],                                                        # not an object
    "nope",
])
def test_invalid_ast_rejected(bad):
    with pytest.raises(InvalidCondition):
        validate_condition(bad)


def test_write_boundary_rejects_invalid_condition():
    s = new_store()
    scope(s, "s-v")
    with pytest.raises(InvalidCondition):
        s.add_rule_version({"rule_id": "r", "activity": "VIVAC_AL_RASO",
                            "spatial_scope_id": "s-v", "effect": "PERMITTED",
                            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                            "condition": {"field": "x", "op": "sneaky", "value": 1}})


def test_evaluator_revalidates_even_stored_rows():
    with pytest.raises(BadCondition):
        evaluate({"field": "x", "op": "sneaky", "value": 1}, {"x": 1})


# ---- evaluator strictness --------------------------------------------------------------

def test_bool_never_equals_number():
    assert evaluate({"field": "flag", "op": "eq", "value": True}, {"flag": True}) is True
    assert evaluate({"field": "flag", "op": "eq", "value": True}, {"flag": 1}) is False


def test_is_true_requires_real_bool():
    with pytest.raises(BadCondition):
        evaluate({"field": "flag", "op": "is_true"}, {"flag": "true"})
    with pytest.raises(BadCondition):
        evaluate({"field": "flag", "op": "is_false"}, {"flag": 0})


def test_unknown_fact_types_rejected():
    with pytest.raises(InvalidFact):
        validate_facts({"x": {"nested": 1}})
    with pytest.raises(InvalidFact):
        validate_facts({"x": None})


def test_cli_fact_coercion_canonical_only():
    from alraso.cli import _parse_facts
    got = _parse_facts("inside_park=true,refuge=false,altitude_m=2100.5,note=hello")
    assert got == {"inside_park": True, "refuge": False, "altitude_m": 2100.5,
                   "note": "hello"}
    tricky = _parse_facts("a=TRUE,b=False,c=nan,d=inf")
    assert tricky["a"] == "TRUE"          # NOT canonical -> opaque text
    assert tricky["b"] == "False"         # never True
    assert isinstance(tricky["c"], str)   # NaN never becomes a float fact
    assert isinstance(tricky["d"], str)
    assert not any(isinstance(v, float) and not math.isfinite(v) for v in tricky.values())
