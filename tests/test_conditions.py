import pytest

from alraso import conditions


def test_const_all_any_not():
    assert conditions.evaluate({"const": True}, {}) is True
    assert conditions.evaluate({"all": []}, {}) is False       # cannot establish
    assert conditions.evaluate({"all": [{"const": True}, {"const": True}]}, {}) is True
    assert conditions.evaluate({"any": [{"const": False}, {"const": True}]}, {}) is True
    assert conditions.evaluate({"not": {"const": False}}, {}) is True


def test_numeric_and_membership_ops():
    facts = {"altitude_m": 1850, "activity_name": "VIVAC_AL_RASO"}
    assert conditions.evaluate({"field": "altitude_m", "op": "gte", "value": 1800}, facts)
    assert not conditions.evaluate({"field": "altitude_m", "op": "gt", "value": 1850}, facts)
    assert conditions.evaluate({"field": "altitude_m", "op": "lte", "value": 1850}, facts)
    assert conditions.evaluate({"field": "activity_name", "op": "in",
                                "value": ["VIVAC_AL_RASO", "TARP"]}, facts)


def test_missing_fact_is_hard_fail_closed():
    with pytest.raises(conditions.MissingFact) as e:
        conditions.evaluate({"field": "inside_park", "op": "eq", "value": True}, {})
    assert e.value.field == "inside_park"


def test_bad_condition_forms_rejected():
    with pytest.raises(conditions.BadCondition):
        conditions.evaluate({"op": "eq"}, {})
    with pytest.raises(conditions.BadCondition):
        conditions.evaluate({"field": "x", "op": "wat", "value": 1}, {"x": 1})
    with pytest.raises(conditions.BadCondition):
        conditions.evaluate("nope", {})


def test_referenced_fields():
    cond = {"all": [{"field": "altitude_m", "op": "gte", "value": 1},
                    {"any": [{"field": "inside_park", "op": "is_true"}]},
                    {"not": {"field": "is_refuge", "op": "is_true"}}]}
    assert conditions.referenced_fields(cond) == {"altitude_m", "inside_park", "is_refuge"}
