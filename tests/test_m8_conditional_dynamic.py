"""M8-D: CONDITIONAL semantics + operational/current restrictions.

Contract being proved:
  * PERMITTED means every material requirement was checked and satisfied.
  * CONDITIONAL means an applicable norm permits the activity but a material
    requirement (missing fact or unchecked operational restriction) cannot be
    verified automatically — never rendered as an unqualified yes.
  * Operational restrictions are demote-only: they can turn PERMITTED into
    CONDITIONAL or PROHIBITED, never create an affirmative answer.
  * A missing fact on a restrictive rule fails closed to UNDETERMINED.
"""

from __future__ import annotations

import pytest

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.errors import InvalidRule
from alraso.resolver import Resolver

from conftest import new_store, scope, rule


def q(scope_id: str = "s-x", facts: dict | None = None,
      activity_date: str = "2026-08-01", activity: str = "VIVAC_AL_RASO") -> Query:
    return Query(activity=activity, activity_date=activity_date,
                 knowledge_date="2026-08-01", spatial_scope_id=scope_id,
                 facts=facts or {})


def restriction(store, rid="chk-fire", scope_id="s-x", **kw) -> None:
    base = {"restriction_id": rid, "kind": "FIRE_RISK", "activity": None,
            "spatial_scope_id": scope_id, "effect": "RESTRICT",
            "required": True, "verified": False,
            "description": "test check", "recorded_at": "2026-01-01"}
    base.update(kw)
    store.add_operational_restriction(base)


# --------------------------------------------------------------------------
# store-level: write validation, append-only, temporal/month/activity filters
# --------------------------------------------------------------------------

def test_restriction_write_validation():
    s = new_store()
    scope(s, "s-x")
    with pytest.raises(InvalidRule):
        restriction(s, kind="BOGUS")
    with pytest.raises(InvalidRule):
        restriction(s, effect="ALLOW")  # no affirmative effects exist
    with pytest.raises(InvalidRule):
        restriction(s, verified=False, restriction_active=True)
    with pytest.raises(InvalidRule):
        restriction(s, month_window=[0])
    with pytest.raises(InvalidRule):
        restriction(s, month_window=[13])
    restriction(s)  # valid baseline


def test_restriction_append_only():
    s = new_store()
    scope(s, "s-x")
    restriction(s)
    with pytest.raises(Exception):
        s.conn.execute("UPDATE operational_restriction SET verified=1")
    with pytest.raises(Exception):
        s.conn.execute("DELETE FROM operational_restriction")


def test_restriction_selection_filters():
    s = new_store()
    scope(s, "s-x")
    restriction(s, rid="all-year")
    restriction(s, rid="summer", month_window=[6, 7, 8])
    restriction(s, rid="other-activity", activity="VEHICULO")
    ids = {c.restriction_id for c in s.operational_restrictions_at(
        ["s-x"], "VIVAC_AL_RASO", "2026-01-15", "2026-01-15")}
    assert ids == {"all-year"}  # summer out of window, other activity excluded
    ids = {c.restriction_id for c in s.operational_restrictions_at(
        ["s-x"], "VIVAC_AL_RASO", "2026-07-15", "2026-07-15")}
    assert ids == {"all-year", "summer"}


def test_restriction_superseded_by_new_observation():
    s = new_store()
    scope(s, "s-x")
    restriction(s, rid="chk", verified=False, recorded_at="2026-01-01")
    s.add_operational_restriction({
        "restriction_id": "chk", "kind": "FIRE_RISK", "activity": None,
        "spatial_scope_id": "s-x", "effect": "BLOCK", "required": True,
        "verified": True, "restriction_active": True,
        "observed_at": "2026-06-01", "description": "verified active",
        "recorded_at": "2026-06-01", "recorded_until": "2026-08-01"})
    # knowledge before the update sees the old unverified observation
    rows = s.operational_restrictions_at(["s-x"], "VIVAC_AL_RASO",
                                         "2026-06-15", "2026-05-15")
    assert len(rows) == 1 and rows[0].verified is False
    # knowledge inside the update window sees it
    rows = s.operational_restrictions_at(["s-x"], "VIVAC_AL_RASO",
                                         "2026-06-15", "2026-06-15")
    assert len(rows) == 1 and rows[0].verified and rows[0].restriction_active
    # after the correction's recorded_until, belief reverts to the earlier
    # still-visible observation (system-time semantics, not a deletion)
    rows = s.operational_restrictions_at(["s-x"], "VIVAC_AL_RASO",
                                         "2026-06-15", "2026-09-01")
    assert len(rows) == 1 and rows[0].verified is False


# --------------------------------------------------------------------------
# resolver: PERMITTED semantics hardened
# --------------------------------------------------------------------------

def test_permitted_clean_when_no_checks():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.PERMITTED
    assert r.dynamic_checks == []


def test_unverified_required_check_demotes_to_conditional():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    restriction(s)
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.CONDITIONAL
    assert "CONDITIONAL_UNVERIFIED_REQUIREMENTS" in r.reason_codes
    assert r.dynamic_checks and r.dynamic_checks[0]["verified"] is False


def test_verified_clear_check_keeps_permitted_and_is_exposed():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    restriction(s, verified=True, restriction_active=False,
                observed_at="2026-08-01")
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.PERMITTED
    assert r.dynamic_checks[0]["verified"] is True
    assert r.dynamic_checks[0]["restriction_active"] is False


def test_verified_active_block_demotes_to_prohibited():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    restriction(s, effect="BLOCK", verified=True, restriction_active=True,
                observed_at="2026-08-01")
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.PROHIBITED
    assert "OPERATIONAL_RESTRICTION_ACTIVE" in r.reason_codes


def test_verified_active_restrict_demotes_to_conditional():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    restriction(s, effect="RESTRICT", verified=True, restriction_active=True,
                observed_at="2026-08-01")
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.CONDITIONAL


def test_non_required_unverified_check_does_not_demote():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    restriction(s, required=False)
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.PERMITTED
    assert r.dynamic_checks  # still exposed


def test_restriction_never_creates_permission():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PROHIBITED")
    restriction(s, verified=True, restriction_active=False,
                observed_at="2026-08-01")
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.PROHIBITED


def test_seasonal_check_only_binds_in_window():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED")
    restriction(s, month_window=[6, 7, 8, 9, 10])
    assert Resolver(s).resolve(q(activity_date="2026-08-01")).legal_status \
        is LegalStatus.CONDITIONAL
    assert Resolver(s).resolve(q(activity_date="2026-01-15")).legal_status \
        is LegalStatus.PERMITTED


# --------------------------------------------------------------------------
# resolver: missing facts -> CONDITIONAL (permission) / UNDETERMINED (restrictive)
# --------------------------------------------------------------------------

def test_missing_fact_on_permission_yields_conditional():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED",
         condition={"field": "no_fire_risk_notice", "op": "is_true"})
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.CONDITIONAL
    assert r.knowledge_status is KnowledgeStatus.CURRENT
    assert "MISSING_FACT" in r.reason_codes
    assert "CONDITIONAL_UNVERIFIED_REQUIREMENTS" in r.reason_codes
    fields = {f for c in r.conditions for f in c.get("fields", [])}
    assert "no_fire_risk_notice" in fields


def test_missing_fact_on_restriction_fails_closed():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/x#a", "s-x", "PROHIBITED",
         condition={"field": "in_zone_a", "op": "is_true"})
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.UNDETERMINED
    assert r.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert "MISSING_FACT" in r.reason_codes


def test_satisfied_permission_with_unevaluable_extra_permission_stays_permitted():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p1#a", "s-x", "PERMITTED")
    rule(s, "alraso:t/p2#a", "s-x", "PERMITTED",
         condition={"field": "group_size_ok", "op": "is_true"})
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.PERMITTED


def test_missing_fact_satisfied_yields_permitted():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/p#a", "s-x", "PERMITTED",
         condition={"field": "no_fire_risk_notice", "op": "is_true"})
    r = Resolver(s).resolve(q(facts={"no_fire_risk_notice": True}))
    assert r.legal_status is LegalStatus.PERMITTED


def test_authorization_required_survives_unverified_check():
    s = new_store()
    scope(s, "s-x")
    rule(s, "alraso:t/a#a", "s-x", "AUTHORIZATION_REQUIRED")
    restriction(s)
    r = Resolver(s).resolve(q())
    assert r.legal_status is LegalStatus.AUTHORIZATION_REQUIRED
    assert r.dynamic_checks  # check still exposed to the caller
