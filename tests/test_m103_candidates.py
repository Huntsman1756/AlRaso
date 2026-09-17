"""M10.3 candidate-corpus safety tests.

The three candidate fixtures under discovery/evidence/m10.3-*/ are evidence
proposals pending HUMAN legal review. These tests prove — at the code level —
that none of them can ever produce a publishable effect:

  * every rule version is REVIEW_REQUIRED with legal/spatial review incomplete
  * the eligibility gate rejects every version (REVIEW_NOT_PUBLISHABLE ...)
  * the resolver answers UNDETERMINED/INCOMPLETE for every scope, even when
    caller-supplied facts would satisfy the PROPOSED conditions
  * no PERMITTED (nor PROHIBITED) can leak out of unreviewed candidates
"""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.eligibility import is_rule_version_eligible
from alraso.ingest.ordesa import ingest_corpus
from alraso.resolver import Resolver

EVIDENCE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "discovery" / "evidence"

CANDIDATES = [
    ("m10.3-aiguestortes", "ss-pn-aiguestortes"),
    ("m10.3-teide", "ss-pn-teide"),
    ("m10.3-sierra-nevada", "ss-pn-sierra-nevada"),
]


def _load(evidence_dir: str) -> tuple[BitemporalStore, dict]:
    fx = json.loads(
        io.open(EVIDENCE_ROOT / evidence_dir / "candidate_fixture.json",
                encoding="utf-8").read())
    store = BitemporalStore.connect(":memory:")
    ingest_corpus(store, fx)
    return store, fx


@pytest.mark.parametrize("evidence_dir,_scope", CANDIDATES)
def test_candidate_fixture_declares_no_review_complete(evidence_dir, _scope):
    """The JSON itself must not carry review-complete flags or publishable
    statuses anywhere — evidence-only contract (mandate §9)."""
    _store, fx = _load(evidence_dir)
    blob = json.dumps(fx)
    assert '"legal_review_complete": true' not in blob
    assert '"spatial_review_complete": true' not in blob
    assert '"PUBLISHED"' not in blob
    for v in fx["legal_rule_versions"]:
        assert v["review_status"] == "REVIEW_REQUIRED"
        assert v["legal_review_complete"] is False
        assert v["spatial_review_complete"] is False
    for f in fx["legal_fragments"]:
        assert f["review_status"] == "REVIEW_REQUIRED"


@pytest.mark.parametrize("evidence_dir,_scope", CANDIDATES)
def test_every_candidate_version_is_ineligible(evidence_dir, _scope):
    """is_rule_version_eligible must return reasons for EVERY version."""
    store, fx = _load(evidence_dir)
    rows = store.conn.execute("SELECT * FROM legal_rule_version").fetchall()
    assert len(rows) == len(fx["legal_rule_versions"])
    cols = [c[1] for c in store.conn.execute("PRAGMA table_info(legal_rule_version)")]
    for row in rows:
        v = dict(zip(cols, row))
        from alraso.bitemporal import VersionRow
        vr = VersionRow(
            seq=v["seq"], rule_id=v["rule_id"], activity=v["activity"],
            spatial_scope_id=v["spatial_scope_id"], effect=v["effect"],
            condition=json.loads(v["condition"]) if v["condition"] else None,
            effective_from=v["effective_from"], effective_to=v["effective_to"],
            recorded_at=v["recorded_at"], recorded_until=v["recorded_until"],
            evidence=json.loads(v["evidence"]),
            interpretation_note=v["interpretation_note"],
            review_status=v["review_status"],
            legal_review_complete=bool(v["legal_review_complete"]),
            spatial_review_complete=(None if v["spatial_review_complete"] is None
                                     else bool(v["spatial_review_complete"])),
            evidence_required=bool(v["evidence_required"]),
            normative_basis=json.loads(v["normative_basis"]))
        reasons = is_rule_version_eligible(vr, store, activity_date="2026-09-01")
        assert reasons, f"{v['rule_id']} unexpectedly eligible"
        assert any(r.startswith("REVIEW_NOT_PUBLISHABLE") for r in reasons)
        assert "LEGAL_REVIEW_INCOMPLETE" in reasons
        assert "SPATIAL_REVIEW_INCOMPLETE" in reasons


@pytest.mark.parametrize("evidence_dir,scope", CANDIDATES)
def test_unreviewed_candidates_resolve_undetermined(evidence_dir, scope):
    """Resolver: unreviewed candidates contribute nothing -> UNDETERMINED
    (never PERMITTED, never PROHIBITED) + INCOMPLETE knowledge."""
    store, _fx = _load(evidence_dir)
    res = Resolver(store).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2026-09-01",
        knowledge_date="2026-09-12", spatial_scope_id=scope))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE


def test_teide_permitted_facts_still_undetermined():
    """Even facts satisfying the PROPOSED Teide PERMITTED conditions cannot
    produce PERMITTED while review is pending (no silent launder)."""
    store, _fx = _load("m10.3-teide")
    res = Resolver(store).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2026-09-01",
        knowledge_date="2026-09-12", spatial_scope_id="ss-pn-teide",
        facts={"altitude_m": 3550, "vivac_area": "TEIDE",
               "prior_notification_done": True, "nights_same_area": 1,
               "traverse_consecutive_vivac_nights": 1}))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.legal_status is not LegalStatus.PERMITTED


def test_sierra_nevada_permitted_facts_still_undetermined():
    store, _fx = _load("m10.3-sierra-nevada")
    res = Resolver(store).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2026-09-01",
        knowledge_date="2026-09-12", spatial_scope_id="ss-pn-sierra-nevada",
        facts={"group_size": 4, "tent_count": 1, "prior_notification_done": True,
               "nights_same_location": 1, "distance_km_to_urban_nucleus": 5,
               "distance_km_to_tourist_lodging": 5, "distance_km_to_refuge": 3}))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.legal_status is not LegalStatus.PERMITTED


def test_no_permitted_leaks_for_any_park_any_facts():
    """Sweep: under no combination of these facts may an unreviewed
    candidate emit PERMITTED."""
    store, _fx = _load("m10.3-teide")
    for facts in ({}, {"altitude_m": 3000},
                  {"altitude_m": 3000, "vivac_area": "TEIDE",
                   "prior_notification_done": True, "nights_same_area": 1,
                   "traverse_consecutive_vivac_nights": 1}):
        res = Resolver(store).resolve(Query(
            activity="VIVAC_AL_RASO", activity_date="2026-09-01",
            knowledge_date="2026-09-12", spatial_scope_id="ss-pn-teide",
            facts=facts))
        assert res.legal_status is not LegalStatus.PERMITTED


@pytest.mark.parametrize("evidence_dir,scope", CANDIDATES)
def test_candidate_fixtures_reference_existing_extracts(evidence_dir, scope):
    """Provenance: every review_case's extract file exists and its recorded
    sha256 matches bytes on disk."""
    import hashlib
    rc = json.loads(io.open(
        EVIDENCE_ROOT / evidence_dir / "review_case.json",
        encoding="utf-8").read())
    extract = EVIDENCE_ROOT / evidence_dir / rc["source"]["extract_file"]
    assert extract.exists()
    digest = hashlib.sha256(extract.read_bytes()).hexdigest()
    assert digest == rc["source"]["extract_sha256"]
    assert rc["reviewer_decision"] == "PENDING"
    assert rc["automated_state"] == "READY_FOR_HUMAN_REVIEW"
