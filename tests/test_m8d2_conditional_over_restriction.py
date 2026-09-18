"""M8-D2: CONDITIONAL-over-restriction + activity_date temporal conditions.

Contract being proved (post-REJECT remodel of RC-M8-ES-MD-GUADARRAMA-VIVAC):

  * A held restrictive effect (PROHIBITED / AUTHORIZATION_REQUIRED) must NOT
    be asserted while an applicable PERMITTED rule stayed undetermined for
    missing facts — absence of evidence that a permission condition holds is
    not evidence the permission is absent. The answer degrades to
    CONDITIONAL, never to a clean prohibition.
  * Once the pending permission is affirmatively excluded (fact supplied
    false / condition evaluates false), the restrictive answer stands clean.
  * A PERMITTED outcome reached through declared precedence is NOT degraded
    by other undetermined permissions.
  * The `date_in_range` op gates rules on the query's own activity_date — a
    deterministic derived fact injected by the resolver (never caller data).
"""

from __future__ import annotations

import pytest

from alraso import conditions
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.errors import InvalidCondition
from alraso.resolver import Resolver

from conftest import new_store, scope, rule, relation


def q(scope_id: str = "s-x", facts: dict | None = None,
      activity_date: str = "2026-08-01") -> Query:
    return Query(activity="VIVAC_AL_RASO", activity_date=activity_date,
                 knowledge_date="2026-08-01", spatial_scope_id=scope_id,
                 facts=facts or {})


# --------------------------------------------------------------------------
# date_in_range: op semantics + validation
# --------------------------------------------------------------------------

def test_date_in_range_basic_and_wraparound():
    cond = {"field": "activity_date", "op": "date_in_range",
            "value": ["06-15", "10-15"]}
    assert conditions.evaluate(cond, {"activity_date": "2026-08-01"}) is True
    assert conditions.evaluate(cond, {"activity_date": "2026-06-15"}) is True
    assert conditions.evaluate(cond, {"activity_date": "2026-10-15"}) is True
    assert conditions.evaluate(cond, {"activity_date": "2026-06-14"}) is False
    assert conditions.evaluate(cond, {"activity_date": "2026-10-16"}) is False
    wrap = {"field": "activity_date", "op": "date_in_range",
            "value": ["10-16", "06-14"]}
    assert conditions.evaluate(wrap, {"activity_date": "2026-01-15"}) is True
    assert conditions.evaluate(wrap, {"activity_date": "2026-08-01"}) is False


def test_date_in_range_strictness():
    bad_val = {"field": "activity_date", "op": "date_in_range",
               "value": ["06-15", "x"]}
    with pytest.raises(InvalidCondition):
        from alraso.validation import validate_condition
        validate_condition(bad_val)
    # evaluate wraps validation errors as BadCondition (defence in depth)
    with pytest.raises(conditions.BadCondition):
        conditions.evaluate(bad_val, {"activity_date": "2026-08-01"})
    not_a_date = {"field": "activity_date", "op": "date_in_range",
                  "value": ["06-15", "10-15"]}
    with pytest.raises(conditions.BadCondition):
        conditions.evaluate(not_a_date, {"activity_date": "verano"})
    with pytest.raises(conditions.MissingFact):
        conditions.evaluate(not_a_date, {})


# --------------------------------------------------------------------------
# resolver: date_in_range via the injected activity_date fact
# --------------------------------------------------------------------------

def test_seasonal_rule_binds_by_activity_date():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED",
         condition={"field": "activity_date", "op": "date_in_range",
                    "value": ["10-16", "06-14"]})
    assert Resolver(s).resolve(q(activity_date="2026-01-15")).legal_status \
        is LegalStatus.PERMITTED
    # outside the window the permission simply does not fire
    r = Resolver(s).resolve(q(activity_date="2026-08-01"))
    assert r.legal_status is LegalStatus.UNDETERMINED


def test_caller_cannot_forge_activity_date_fact():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED",
         condition={"field": "activity_date", "op": "date_in_range",
                    "value": ["10-16", "06-14"]})
    # caller claims a winter date fact; the query's own August date wins
    r = Resolver(s).resolve(q(activity_date="2026-08-01",
                              facts={"activity_date": "2026-01-15"}))
    assert r.legal_status is LegalStatus.UNDETERMINED


# --------------------------------------------------------------------------
# resolver: CONDITIONAL-over-restriction (missing fact != prohibition)
# --------------------------------------------------------------------------

def test_undetermined_permission_over_held_prohibition_yields_conditional():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/d#a", "s-x", "PROHIBITED")
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_full", "op": "is_true"})
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.CONDITIONAL
    assert r.knowledge_status is KnowledgeStatus.CURRENT
    assert "CONDITIONAL_UNVERIFIED_REQUIREMENTS" in r.reason_codes
    assert "MISSING_FACT" in r.reason_codes
    fields = {f for c in r.conditions for f in c.get("fields", [])}
    assert "refuge_full" in fields


def test_permission_excluded_by_fact_lets_prohibition_stand():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/d#a", "s-x", "PROHIBITED")
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_full", "op": "is_true"})
    r = Resolver(s).resolve(q(facts={"refuge_full": False}))
    assert r.legal_status is LegalStatus.PROHIBITED


def test_undetermined_permission_over_held_auth_required_yields_conditional():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/e#a", "s-x", "AUTHORIZATION_REQUIRED")
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_full", "op": "is_true"})
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.CONDITIONAL


def test_permitted_via_declared_override_not_degraded():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/d#a", "s-x", "PROHIBITED")
    rule(s, "alraso:t/a#a", "s-x", "PERMITTED",
         condition={"field": "nights_ok", "op": "is_true"})
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_full", "op": "is_true"})
    relation(s, "rel-a-over-d", "alraso:t/a#a", "alraso:t/d#a")
    r = Resolver(s).resolve(q(facts={"nights_ok": True}))
    assert r.legal_status is LegalStatus.PERMITTED


def test_restrictive_undetermined_still_fails_closed():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/d#a", "s-x", "PROHIBITED",
         condition={"field": "in_zone_a", "op": "is_true"})
    rule(s, "alraso:t/b#a", "s-x", "PERMITTED",
         condition={"field": "refuge_full", "op": "is_true"})
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.UNDETERMINED
    assert "MISSING_FACT" in r.reason_codes
