"""Safe condition AST and evaluator (no eval(), no coercions).

A LegalRuleVersion may carry a JSON condition that must hold for its effect to
apply. Deliberately tiny, non-Turing-complete grammar; the FULL structure is
validated (alraso.validation.validate_condition) before evaluation and missing
facts are a hard fail-closed signal (MissingFact).

Strictness rules (M1 remediation F06):
  * numeric ops require finite real numbers on BOTH sides (bool rejected);
  * is_true/is_false require a real bool fact (bool("false") is never consulted);
  * eq/neq compare within a closed type set with no cross-type numeric coercion
    between bool and numbers; int/float compare numerically;
  * membership ('in') compares scalars only.

Grammar:
    {"const": <bool>}
    {"all": [cond, ...]}          # empty -> False (cannot establish a rule)
    {"any": [cond, ...]}          # empty -> False
    {"not": cond}
    {"field": name, "op": op, "value": v}
      op in: eq neq gte gt lte lt in is_true is_false
"""

from __future__ import annotations

from typing import Any

from alraso.validation import parse_number_strict, validate_condition


class MissingFact(Exception):
    def __init__(self, field: str) -> None:
        super().__init__(f"missing input `{field}`")
        self.field = field


class BadCondition(Exception):
    pass


def _scalar_eq(a: Any, b: Any) -> bool:
    """Type-strict equality: bool never equals a number; numbers compare
    numerically; strings compare as strings; no other cross-type equality."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return False


def _op_eq(a: Any, b: Any) -> bool:
    return _scalar_eq(a, b)


def _op_neq(a: Any, b: Any) -> bool:
    return not _scalar_eq(a, b)


def _num(x: Any, *, where: str) -> float:
    try:
        return parse_number_strict(x, field=where)
    except Exception as e:  # InvalidFact -> BadCondition at the evaluator boundary
        raise BadCondition(str(e)) from e


def _cmp(op_name: str) -> Any:
    def run(a: Any, b: Any) -> bool:
        left = _num(a, where="fact")
        right = _num(b, where="condition.value")
        return {"gte": left >= right, "gt": left > right,
                "lte": left <= right, "lt": left < right}[op_name]
    return run


def _op_in(a: Any, b: Any) -> bool:
    if not isinstance(b, list):
        raise BadCondition("'in' requires a list value in the condition")
    return any(_scalar_eq(a, item) for item in b)


def _op_is_true(a: Any, _b: Any) -> bool:
    if not isinstance(a, bool):
        raise BadCondition("is_true requires a bool fact")
    return a


def _op_is_false(a: Any, _b: Any) -> bool:
    if not isinstance(a, bool):
        raise BadCondition("is_false requires a bool fact")
    return not a


_OPS: dict[str, Any] = {
    "eq": _op_eq,
    "neq": _op_neq,
    "gte": _cmp("gte"),
    "gt": _cmp("gt"),
    "lte": _cmp("lte"),
    "lt": _cmp("lt"),
    "in": _op_in,
    "is_true": _op_is_true,
    "is_false": _op_is_false,
}


def evaluate(cond: dict[str, Any], facts: dict[str, Any]) -> bool:
    """Total evaluator over the validated grammar. Never guesses: unknown
    structures raise BadCondition; absent facts raise MissingFact."""
    try:
        validate_condition(cond)  # defence in depth even for already-ingested rows
    except Exception as e:
        raise BadCondition(str(e)) from e
    return _eval_validated(cond, facts)


def _eval_validated(cond: dict[str, Any], facts: dict[str, Any]) -> bool:
    if "const" in cond:
        return cond["const"]
    if "all" in cond:
        return bool(cond["all"]) and all(_eval_validated(c, facts) for c in cond["all"])
    if "any" in cond:
        return bool(cond["any"]) and any(_eval_validated(c, facts) for c in cond["any"])
    if "not" in cond:
        return not _eval_validated(cond["not"], facts)
    field = cond["field"]
    op = cond.get("op", "eq")
    if op not in _OPS:
        raise BadCondition("unknown op " + repr(op))
    if field not in facts:
        raise MissingFact(field)
    return bool(_OPS[op](facts[field], cond.get("value")))


def referenced_fields(cond: dict[str, Any]) -> set[str]:
    """Fields a condition needs — used to pre-check facts and build warnings."""
    out: set[str] = set()
    if "field" in cond:
        out.add(cond["field"])
    for key in ("all", "any"):
        for sub in cond.get(key, []):
            out |= referenced_fields(sub)
    if "not" in cond:
        out |= referenced_fields(cond["not"])
    return out
