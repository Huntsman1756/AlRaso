"""F01 — eligibility gate: rules that are not publishable can NEVER take part
in a conclusion, and their presence never changes a prior public answer."""

from __future__ import annotations

import sqlite3

import pytest

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.eligibility import is_rule_version_eligible
from alraso.resolver import Resolver
from conftest import DOC, make_version, new_store, rule, scope

S = "s-el"
BASE = dict(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
            knowledge_date="2023-06-15", spatial_scope_id=S)


def q(**kw):
    return Query(**{**BASE, **kw})


def resolver_with(*rules_setup):
    s = new_store()
    scope(s, S)
    for setup in rules_setup:
        setup(s)
    return Resolver(s)


def eligible_permit(s):
    rule(s, "alraso:es:t/p#ok", S, "PERMITTED")


def test_review_required_cannot_permit():
    r = resolver_with(lambda s: rule(s, "alraso:es:t/p#rr", S, "PERMITTED",
                                     review="REVIEW_REQUIRED", legal=False))
    res = r.resolve(q())
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert res.reason_codes == ["NO_PUBLISHABLE_RULE_COVERAGE"]


def test_legal_reviewed_without_publishable_status_cannot_permit():
    # LEGAL_REVIEWED is a mid-pipeline state: NOT publishable.
    r = resolver_with(lambda s: rule(s, "alraso:es:t/p#lr", S, "PERMITTED",
                                     review="LEGAL_REVIEWED"))
    assert r.resolve(q()).legal_status is LegalStatus.UNDETERMINED
    assert r.resolve(q()).reason_codes == ["NO_PUBLISHABLE_RULE_COVERAGE"]


def test_missing_evidence_cannot_permit():
    r = resolver_with(lambda s: rule(s, "alraso:es:t/p#ne", S, "PERMITTED", evidence=None))
    res = r.resolve(q())
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    # H2/D3: absent evidence is reported as non-publishable evidence, not just
    # as a generic coverage hole.
    assert res.reason_codes == ["NO_PUBLISHABLE_RULE_COVERAGE", "EVIDENCE_NOT_PUBLISHABLE"]
    elig = next(t for t in res.precedence_trace if t["stage"] == "eligibility")
    assert any("EVIDENCE_MISSING" in r for e in elig["excluded"] for r in e["reasons"])


def test_unresolvable_evidence_ref_cannot_permit():
    def setup(s):
        rule(s, "alraso:es:t/p#ue", S, "PERMITTED", evidence=None)
        # re-add manually with a dangling ref (bypass helper's frag creation)
        s.add_rule_version({
            "rule_id": "alraso:es:t/p#ue2", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": S, "effect": "PERMITTED",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-does-not-exist"]})
    res = resolver_with(setup).resolve(q())
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["NO_PUBLISHABLE_RULE_COVERAGE", "EVIDENCE_NOT_PUBLISHABLE"]


def test_evidence_cannot_be_orphaned_under_a_determination():
    """H6: replaces the earlier, misleading test_source_document_removal_breaks_resolution.

    The failure mode that name claimed to test is UNREACHABLE by construction,
    so testing it "by assertion of a control case" was dishonest. Evidence rows
    are append-only (BEFORE DELETE triggers) and a fragment pointing at a
    missing document cannot even be inserted (foreign_keys=ON). What resolution
    must guarantee is that a corpus that arrives ALREADY broken (legacy dump,
    hand-made store) makes the rule ineligible instead of permitting. Both
    halves are asserted here.
    """
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/p#sd", S, "PERMITTED")
    assert Resolver(s).resolve(q()).legal_status is LegalStatus.PERMITTED  # control

    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute("DELETE FROM source_document WHERE id=?", (DOC["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute("DELETE FROM legal_fragment WHERE id='lf-test'")
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute("INSERT INTO legal_fragment (id, source_document_id, locator) "
                       "VALUES ('lf-orphan', 'sd-nope', 'art. 1')")

    # a dangling reference can therefore only come from outside the store
    v = make_version(rule_id="alraso:es:t/p#sd", evidence=["lf-gone"])
    reasons = is_rule_version_eligible(v, s)
    assert any(r.startswith("EVIDENCE_UNRESOLVABLE") for r in reasons)


def test_spatial_review_required_cannot_permit_via_version_flag():
    # spatial review explicitly pending on the version -> never publishable
    r = resolver_with(lambda s: rule(s, "alraso:es:t/p#sr", S, "PERMITTED",
                                     spatial=False))
    assert r.resolve(q()).legal_status is LegalStatus.UNDETERMINED


def test_spatial_review_required_cannot_permit_via_geometry_query():
    from alraso.spatial import InMemorySpatialProvider
    s = new_store()
    scope(s, S, review_status="SPATIAL_REVIEW_PENDING_GEOMETRY", geometry="src")
    rule(s, "alraso:es:t/p#geo", S, "PERMITTED")
    prov = InMemorySpatialProvider()
    prov.add_scope(S, S, "PARK_SECTOR", [[(42.0, 0.0), (42.0, 0.1), (42.1, 0.1), (42.1, 0.0)]])
    res = Resolver(s, spatial=prov).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2021-07-15", knowledge_date="2023-06-15",
        lat=42.05, lon=0.05))
    # geometry-backed PERMITTED over unreviewed geometry is impossible
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["PERMITTED_INVARIANT_VIOLATION"]


def test_fully_eligible_rule_participates():
    r = resolver_with(eligible_permit)
    res = r.resolve(q())
    assert res.legal_status is LegalStatus.PERMITTED
    assert res.evidence and res.rule_versions


def test_adding_ineligible_rule_does_not_change_public_result():
    s = new_store()
    scope(s, S)
    rule(s, "alraso:es:t/p#base", S, "PROHIBITED")
    r = Resolver(s)
    before = r.resolve(q())
    assert before.legal_status is LegalStatus.PROHIBITED
    # late-corpus: an ineligible PERMITTED rule appears
    rule(s, "alraso:es:t/p#noise", S, "PERMITTED", review="REVIEW_REQUIRED",
         legal=False, evidence=None)
    after = r.resolve(q())
    assert after.legal_status is before.legal_status == LegalStatus.PROHIBITED


def test_absence_of_publishable_rules_is_not_prohibited():
    r = resolver_with(lambda s: rule(s, "alraso:es:t/p#x", S, "PROHIBITED",
                                     review="EXTRACTED", legal=False, evidence=None))
    res = r.resolve(q())
    # no publishable law at all: UNDETERMINED+INCOMPLETE, never PROHIBITED
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
