"""NORM_VALIDITY_COVERAGE / PRECEPT_LEVEL_NORMATIVE_BASIS — mandated test battery.

Tests the new normative validity gate: every rule version that carries a
non-empty normative_basis must reference fragments with provision_ref and
validity_from; if activity_date is provided it must fall within the
intersection of the basis fragments' validity windows.
"""

from __future__ import annotations

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.eligibility import is_rule_version_eligible
from alraso.errors import InvalidRule
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver
from conftest import new_store, rule, scope


# ---- helpers ---------------------------------------------------------------

def q(date, knowledge="2023-06-15", activity="VIVAC_AL_RASO", scope_id=None):
    return Query(activity=activity, activity_date=date, knowledge_date=knowledge,
                 spatial_scope_id=scope_id)


def _load_fixture(name):
    from importlib import resources
    import json
    from alraso.ingest.ordesa import ingest_corpus
    s = BitemporalStore.connect(":memory:")
    ref = resources.files("alraso.resources").joinpath(f"fixture_{name}.json")
    fx = json.loads(ref.read_text(encoding="utf-8"))
    ingest_corpus(s, fx)
    return s


# ---- Instance-level (real fixtures) ----------------------------------------

class TestOrdesaInstance:
    """Real Ordesa fixture: 2021 UNDETERMINED, 2023 PROHIBITED."""

    def _resolver(self):
        return Resolver(_load_fixture("ordesa"))

    def test_ORDESA_2021_GENERAL_PERMITTED_REMOVED(self):
        r = self._resolver()
        res = r.resolve(q("2021-07-15", scope_id="ss-ordesa-sector-ordesa"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
        assert "NO_PUBLISHABLE_RULE_COVERAGE" in res.reason_codes
        assert "NORMATIVE_BASIS_OUTSIDE_VALIDITY" in res.reason_codes
        elig = next(t for t in res.precedence_trace if t["stage"] == "eligibility")
        assert elig["excluded"]
        excluded_seqs = {e["seq"] for e in elig["excluded"]}
        assert 2 in excluded_seqs

    def test_ORDESA_2500_ONLY_SHORTCUT_BLOCKED(self):
        r = self._resolver()
        res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                               knowledge_date="2023-06-15",
                               spatial_scope_id="ss-ordesa-sector-ordesa",
                               facts={"altitude_m": 2600}))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_BASIS_OUTSIDE_VALIDITY" in res.reason_codes
        res2 = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                               knowledge_date="2023-06-15",
                               spatial_scope_id="ss-ordesa-sector-ordesa",
                               facts={"altitude_m": 999}))
        assert res2.legal_status is LegalStatus.UNDETERMINED

    def test_ORDESA_2023_PROHIBITED(self):
        r = self._resolver()
        res = r.resolve(q("2023-06-15", scope_id="ss-ordesa-sector-ordesa"))
        assert res.legal_status is LegalStatus.PROHIBITED


class TestGorizInstance:
    """Real Góriz fixture: UNDETERMINED without facts; UNDETERMINED with caller-supplied live facts.

    GORIZ_LIVE_TRIGGER_PUBLICATION_BLOCKED=REVIEW_REQUIRED: the rule stays in corpus but is NOT
    publishable while the live-state trigger (refuge capacity) is unverifiable.
    """

    def _resolver(self):
        return Resolver(_load_fixture("goriz"))

    def test_GORIZ_WITHOUT_LIVE_ENABLEMENT_NEVER_PERMITTED(self):
        r = self._resolver()
        res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2026-01-15",
                               knowledge_date="2026-09-06",
                               spatial_scope_id="ss-ordesa-goriz-zum", facts={}))
        assert res.legal_status is LegalStatus.UNDETERMINED
        res2 = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2026-01-15",
                               knowledge_date="2026-09-06",
                               spatial_scope_id="ss-ordesa-goriz-zum",
                               facts={"nights": 2}))
        assert res2.legal_status is LegalStatus.UNDETERMINED

    def test_GORIZ_CALLER_SUPPLIED_LIVE_FACT_NEVER_PERMITTED(self):
        """The caller-supplied live fact (refuge_capacity_full=True) NEVER unblocks PERMITTED."""
        r = self._resolver()
        res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2026-01-15",
                               knowledge_date="2026-09-06",
                               spatial_scope_id="ss-ordesa-goriz-zum",
                               facts={"refuge_capacity_full": True, "nights": 2}))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
        elig = next(t for t in res.precedence_trace if t["stage"] == "eligibility")
        excluded_seqs = {e["seq"] for e in elig["excluded"]}
        # At 2026-01-15 only seq 2 is active (seq 1 effective_to=2023-12-31)
        assert 2 in excluded_seqs
        # Check the exclusion reason contains REVIEW_NOT_PUBLISHABLE
        excluded_reasons = [r for e in elig["excluded"] for r in e["reasons"]]
        assert any("REVIEW_NOT_PUBLISHABLE:REVIEW_REQUIRED" in r for r in excluded_reasons)

    def test_goriz_quota_temporal_windows_documented(self):
        """GORIZ_QUOTA_TEMPORAL_WINDOWS=DOCUMENTED: windows are in rule-version validity;
        GORIZ_QUOTA_ENFORCEMENT=NOT_IMPLEMENTED: the engine does not evaluate the quota."""
        from alraso.bitemporal import BitemporalStore
        from alraso.ingest.ordesa import ingest_corpus
        from importlib import resources
        import json
        fx = json.loads(resources.files("alraso.resources").joinpath("fixture_goriz.json").read_text(encoding="utf-8"))
        s = BitemporalStore.connect(":memory:")
        ingest_corpus(s, fx)
        # At 2023-12-31: covering row is seq 1 (effective_from 2022-02-09, effective_to 2023-12-31)
        sel1 = s.select("VIVAC_AL_RASO", "ss-ordesa-goriz-zum", "2023-12-31", "2026-09-06")
        assert len(sel1.covering) == 1
        c1 = sel1.covering[0]
        assert c1.seq == 1
        assert c1.effective_from == "2022-02-09"
        assert c1.effective_to == "2023-12-31"
        # At 2024-01-01: covering row is seq 2 (effective_from 2024-01-01, effective_to None)
        sel2 = s.select("VIVAC_AL_RASO", "ss-ordesa-goriz-zum", "2024-01-01", "2026-09-06")
        assert len(sel2.covering) == 1
        c2 = sel2.covering[0]
        assert c2.seq == 2
        assert c2.effective_from == "2024-01-01"
        assert c2.effective_to is None
        # Both selected rows are NOT eligible for publication (REVIEW_REQUIRED)
        from alraso.eligibility import is_rule_version_eligible
        r1_reasons = is_rule_version_eligible(c1, s)
        r2_reasons = is_rule_version_eligible(c2, s)
        assert any("REVIEW_NOT_PUBLISHABLE" in r for r in r1_reasons)
        assert any("REVIEW_NOT_PUBLISHABLE" in r for r in r2_reasons)


# ---- Class-level (synthetic stores) ----------------------------------------

class TestSyntheticStore:
    """Synthetic stores: each test breaks exactly ONE axis."""

    def test_VALID_NORMATIVE_BASIS_PERMITTED(self):
        s = new_store()
        scope(s, "s-v")
        rule(s, "alraso:es:t/v#ok", "s-v", "PERMITTED")
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-v"))
        assert res.legal_status is LegalStatus.PERMITTED

    def test_EXPIRED_NORMATIVE_BASIS_PERMITTED(self):
        s = new_store()
        scope(s, "s-e")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-exp", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED", "provision_ref": "art. 1",
            "validity_from": "1990-01-01", "validity_to": "2020-12-31"})
        s.add_rule_version({
            "rule_id": "alraso:es:t/e#p", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-e", "effect": "PERMITTED",
            "effective_from": "2019-01-01", "recorded_at": "2019-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-exp"], "normative_basis": ["lf-exp"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-e"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_BASIS_OUTSIDE_VALIDITY" in res.reason_codes

    def test_EXPIRED_NORMATIVE_BASIS_PROHIBITED(self):
        s = new_store()
        scope(s, "s-ep")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-ep", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED", "provision_ref": "art. 1",
            "validity_from": "1990-01-01", "validity_to": "2020-12-31"})
        s.add_rule_version({
            "rule_id": "alraso:es:t/e#p", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-ep", "effect": "PROHIBITED",
            "effective_from": "2019-01-01", "recorded_at": "2019-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-ep"], "normative_basis": ["lf-ep"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-ep"))
        assert res.legal_status is LegalStatus.UNDETERMINED

    def test_EXPIRED_NORMATIVE_BASIS_AUTH_REQUIRED(self):
        s = new_store()
        scope(s, "s-ea")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-ea", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED", "provision_ref": "art. 1",
            "validity_from": "1990-01-01", "validity_to": "2020-12-31"})
        s.add_rule_version({
            "rule_id": "alraso:es:t/e#a", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-ea", "effect": "AUTHORIZATION_REQUIRED",
            "effective_from": "2019-01-01", "recorded_at": "2019-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-ea"], "normative_basis": ["lf-ea"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-ea"))
        assert res.legal_status is LegalStatus.UNDETERMINED

    def test_UNKNOWN_NORMATIVE_VALIDITY(self):
        s = new_store()
        scope(s, "s-uv")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-uv", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED", "provision_ref": "art. 1",
            "validity_from": None, "validity_to": None})
        s.add_rule_version({
            "rule_id": "alraso:es:t/u#v", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-uv", "effect": "PERMITTED",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-uv"], "normative_basis": ["lf-uv"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-uv"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_VALIDITY_UNKNOWN" in res.reason_codes

    def test_NORMATIVE_BASIS_MISSING(self):
        s = new_store()
        scope(s, "s-nb")
        rule(s, "alraso:es:t/n#b", "s-nb", "PERMITTED", norm_basis=())
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-nb"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_BASIS_MISSING" in res.reason_codes

    def test_NORMATIVE_PRECEPT_MISSING_dangling(self):
        s = new_store()
        scope(s, "s-dm")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-dm", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED"})
        s.add_rule_version({
            "rule_id": "alraso:es:t/d#m", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-dm", "effect": "PERMITTED",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-dm", "lf-gone"],
            "normative_basis": ["lf-gone"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-dm"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_PRECEPT_MISSING" in res.reason_codes

    def test_NORMATIVE_PRECEPT_MISSING_no_provision_ref(self):
        s = new_store()
        scope(s, "s-np")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-np", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED", "provision_ref": None,
            "validity_from": "1990-01-01", "validity_to": None})
        s.add_rule_version({
            "rule_id": "alraso:es:t/n#p", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-np", "effect": "PERMITTED",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-np"], "normative_basis": ["lf-np"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-np"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_PRECEPT_MISSING" in res.reason_codes

    def test_NON_NORMATIVE_EVIDENCE_NOT_BROKEN(self):
        s = new_store()
        scope(s, "s-ne")
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-a", "source_document_id": "sd", "locator": "art. 1",
            "review_status": "VERIFIED", "provision_ref": "art. 1",
            "validity_from": "1990-01-01", "validity_to": None})
        s.add_legal_fragment({
            "id": "lf-b", "source_document_id": "sd", "locator": "art. 2",
            "review_status": "VERIFIED"})
        s.add_rule_version({
            "rule_id": "alraso:es:t/n#e", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-ne", "effect": "PERMITTED",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-a", "lf-b"], "normative_basis": ["lf-a"]})
        res = Resolver(s).resolve(q("2021-01-01", scope_id="s-ne"))
        assert res.legal_status is LegalStatus.PERMITTED

    def test_OLD_RD409_2021(self):
        s = new_store()
        scope(s, "s-od")
        s.add_source_document({"id": "sd-rd409", "authority": "Estado", "jurisdiction": "ES",
                               "document_type": "PRUG", "title": "RD 409/1995",
                               "canonical_url": "http://t"})
        s.add_legal_fragment({
            "id": "lf-rd409", "source_document_id": "sd-rd409", "locator": "Anexo I",
            "review_status": "VERIFIED", "provision_ref": "Anexo I, D.a",
            "validity_from": "1995-05-12", "validity_to": "2015-04-30"})
        s.add_rule_version({
            "rule_id": "alraso:es:t/o#d", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "s-od", "effect": "PERMITTED",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
            "review_status": "VERIFIED", "legal_review_complete": True,
            "evidence": ["lf-rd409"], "normative_basis": ["lf-rd409"]})
        res = Resolver(s).resolve(q("2021-07-15", scope_id="s-od"))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert "NORMATIVE_BASIS_OUTSIDE_VALIDITY" in res.reason_codes

    def test_write_boundary_norm_basis_subset_of_evidence(self):
        s = new_store()
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        with pytest.raises(InvalidRule):
            s.add_rule_version({
                "rule_id": "alraso:es:t/w#b", "activity": "VIVAC_AL_RASO",
                "spatial_scope_id": "s", "effect": "PERMITTED",
                "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                "review_status": "VERIFIED", "legal_review_complete": True,
                "evidence": ["lf-a"], "normative_basis": ["lf-a", "lf-not-in-evidence"]})

    def test_write_boundary_validity_to_before_validity_from(self):
        s = new_store()
        s.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                               "document_type": "T", "title": "T",
                               "canonical_url": "http://t"})
        with pytest.raises(InvalidRule):
            s.add_legal_fragment({
                "id": "lf-bad", "source_document_id": "sd", "locator": "art. 1",
                "review_status": "VERIFIED", "provision_ref": "art. 1",
                "validity_from": "2025-01-01", "validity_to": "2020-01-01"})


class TestStructuralDiagnostic:
    """rule_intervals_outside_normative_basis() diagnostic."""

    def test_ordesa_flags_expired_rows(self):
        s = _load_fixture("ordesa")
        flagged = s.rule_intervals_outside_normative_basis()
        flagged_seqs = {r["seq"] for r in flagged}
        assert 1 in flagged_seqs
        assert 2 in flagged_seqs
        assert 4 in flagged_seqs

    def test_picos_flags_nothing(self):
        from importlib import resources
        import json
        from alraso.ingest.ordesa import ingest_corpus
        s = BitemporalStore.connect(":memory:")
        ref = resources.files("alraso.resources").joinpath("fixture_picos.json")
        fx = json.loads(ref.read_text(encoding="utf-8"))
        ingest_corpus(s, fx)
        flagged = s.rule_intervals_outside_normative_basis()
        assert flagged == []
