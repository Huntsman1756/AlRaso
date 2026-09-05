"""Strict input validation (M1 remediation F06).

No ambiguous Python coercions on external/unvalidated data:

  * bool(value) is NEVER used to interpret external data. Only the canonical
    representations defined here are accepted; "false"/"no"/"0" are NOT true.
  * floats are accepted only if finite (NaN/Infinity rejected).
  * dates are parsed to real date objects (calendar-valid); lexical string
    comparison of unvalidated strings is forbidden. ISO ordering is relied on
    ONLY after validation, which makes it chronologically correct.

Every failure raises a specific exception from alraso.errors so the resolver
can normalize it (fail-closed to UNDETERMINED, never to PERMITTED).
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from alraso.errors import InvalidCondition, InvalidDate, InvalidFact


def parse_date_strict(value: Any, *, field: str) -> date:
    """Strictly parse a calendar-valid ISO date (YYYY-MM-DD).

    Rejects: wrong types, wrong format, lexical-but-invalid dates (2021-02-31),
    datetimes masquerading as dates, and empty strings.
    """
    if not isinstance(value, str):
        raise InvalidDate(f"{field}: expected ISO date string, got {type(value).__name__}")
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise InvalidDate(f"{field}: not a YYYY-MM-DD date: {value!r}")
    try:
        parts = [int(p) for p in value.split("-")]
    except ValueError as e:
        raise InvalidDate(f"{field}: non-numeric date components: {value!r}") from e
    try:
        parsed = date(parts[0], parts[1], parts[2])
    except ValueError as e:
        raise InvalidDate(f"{field}: calendar-invalid date: {value!r}") from e
    # round-trip catches zero-padding tricks like 2021-3-04
    if parsed.isoformat() != value:
        raise InvalidDate(f"{field}: non-canonical date form: {value!r}")
    return parsed


def parse_bool_strict(value: Any, *, field: str) -> bool:
    """Canonical boolean parsing ONLY.

    Accepted: Python bool; int 0/1 (the SQLite storage form written back by
    our own store). EVERYTHING else is rejected — notably strings:
    bool("false") == True is the exact bug class this kills. If a caller
    receives "true"/"false" text it must translate it explicitly at its own
    boundary, not smuggle strings into typed fields.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return value == 1
    raise InvalidFact(f"{field}: not a canonical boolean: {value!r}")


def parse_number_strict(value: Any, *, field: str) -> float:
    """Finite real number, no coercions. Rejects bool, NaN, ±inf, strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidFact(f"{field}: expected a number, got {type(value).__name__}")
    num = float(value)
    if not math.isfinite(num):
        raise InvalidFact(f"{field}: non-finite number rejected: {value!r}")
    return num


def parse_fact_value(value: Any, *, field: str) -> Any:
    """A fact value must be a JSON-scalar of closed type set, strictly typed."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return parse_number_strict(value, field=field)
    if isinstance(value, str):
        return value
    raise InvalidFact(f"fact {field!r}: unsupported value type {type(value).__name__}")


def validate_facts(facts: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(facts, dict):
        raise InvalidFact(f"facts must be an object, got {type(facts).__name__}")
    out: dict[str, Any] = {}
    for key, value in facts.items():
        if not isinstance(key, str) or not key:
            raise InvalidFact("fact names must be non-empty strings")
        out[key] = parse_fact_value(value, field=key)
    return out


def validate_iso_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise InvalidDate(f"{field}: expected ISO datetime string, got {type(value).__name__}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise InvalidDate(f"{field}: invalid ISO datetime: {value!r}") from e


# ---- condition AST -----------------------------------------------------------

_CONDITION_NODE_KEYS = {
    "const": {"const"},
    "all": {"all"},
    "any": {"any"},
    "not": {"not"},
    "field": {"field", "op", "value"},
}
_KNOWN_OPS = {"eq", "neq", "gte", "gt", "lte", "lt", "in", "is_true", "is_false"}
_NUM_OPS = {"gte", "gt", "lte", "lt"}


def validate_condition(cond: Any, *, where: str = "condition") -> None:
    """Validate the FULL condition AST before it can ever be evaluated.

    Structural validation at write time means a malformed AST cannot reach the
    evaluator, and an evaluator that also validates keeps a second line of
    defence against rows written outside this API.
    """
    from alraso.errors import InvalidCondition

    if not isinstance(cond, dict) or not cond:
        raise InvalidCondition(f"{where}: condition must be a non-empty object")
    kinds = [k for k in ("const", "all", "any", "not", "field") if k in cond]
    if len(kinds) != 1:
        raise InvalidCondition(f"{where}: exactly one node kind required, got {list(cond)}")
    kind = kinds[0]
    extra = set(cond) - _CONDITION_NODE_KEYS[kind]
    if extra:
        raise InvalidCondition(f"{where}: unexpected keys {sorted(extra)} on {kind} node")
    try:
        _validate_node(cond, kind, where)
    except InvalidFact as e:
        # inside an AST, a bad literal is a broken CONDITION (keep the taxonomy
        # precise: InvalidFact stays reserved for fact inputs)
        raise InvalidCondition(str(e)) from e


def _validate_node(cond: dict[str, Any], kind: str, where: str) -> None:
    if kind == "const":
        if not isinstance(cond["const"], bool):
            raise InvalidCondition(f"{where}: const must be a bool")
    elif kind in ("all", "any"):
        subs = cond[kind]
        if not isinstance(subs, list):
            raise InvalidCondition(f"{where}: {kind} must be a list")
        for i, sub in enumerate(subs):
            validate_condition(sub, where=f"{where}.{kind}[{i}]")
    elif kind == "not":
        validate_condition(cond["not"], where=f"{where}.not")
    else:  # field
        if not isinstance(cond["field"], str) or not cond["field"]:
            raise InvalidCondition(f"{where}: field name must be a non-empty string")
        op = cond.get("op", "eq")
        if op not in _KNOWN_OPS:
            raise InvalidCondition(f"{where}: unknown op {op!r}")
        if op in _NUM_OPS:
            parse_number_strict(cond.get("value"), field=f"{where}.value")
        elif op == "in":
            values = cond.get("value")
            if not isinstance(values, list) or not values:
                raise InvalidCondition(f"{where}: 'in' requires a non-empty list value")
            for v in values:
                parse_fact_value(v, field=f"{where}.value[]")
        elif op in ("is_true", "is_false"):
            pass  # fact-side bool-ness is checked at evaluation, strictly
        elif op in ("eq", "neq"):
            parse_fact_value(cond.get("value"), field=f"{where}.value")
