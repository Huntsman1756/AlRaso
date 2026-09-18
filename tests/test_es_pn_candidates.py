"""es-pn coverage candidate-corpus safety tests.

The candidate fixtures under discovery/evidence/es-pn-*/ are evidence
proposals pending HUMAN legal review (post-M10.3 national-park coverage
program). These tests prove — at the code level — that none of them can
ever produce a publishable effect:

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
    ("es-pn-donana", "ss-pn-donana"),
    ("es-pn-sierra-nieves", "ss-pn-sierra-de-las-nieves"),
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
    store, _fx = _load(evidence_dir)
    res = Resolver(store).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2026-09-01",
        knowledge_date="2026-09-18", spatial_scope_id=scope))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE


def test_sierra_nieves_permitted_facts_still_undetermined():
    """Facts satisfying the PROPOSED PERMITTED conditions cannot produce
    PERMITTED while review is pending (no silent launder)."""
    store, _fx = _load("es-pn-sierra-nieves")
    res = Resolver(store).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2026-09-01",
        knowledge_date="2026-09-18", spatial_scope_id="ss-pn-sierra-de-las-nieves",
        facts={"group_size": 4, "tent_count": 1, "prior_notification_done": True,
               "nights_same_location": 1, "distance_km_to_urban_nucleus": 5,
               "distance_km_to_tourist_lodging": 5, "distance_km_to_refuge": 3,
               "mount_within_dusk_dawn_window": True}))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.legal_status is not LegalStatus.PERMITTED


def test_donana_no_prohibited_leak_for_any_facts():
    """The Doñana candidate proposes PROHIBITED — under review it must not
    produce PROHIBITED either: fail-closed means UNDETERMINED."""
    store, _fx = _load("es-pn-donana")
    for facts in ({}, {"event_type": "scientific"}, {"purpose": "ocio"}):
        res = Resolver(store).resolve(Query(
            activity="VIVAC_AL_RASO", activity_date="2026-09-01",
            knowledge_date="2026-09-18", spatial_scope_id="ss-pn-donana",
            facts=facts))
        assert res.legal_status is not LegalStatus.PERMITTED
        assert res.legal_status is not LegalStatus.PROHIBITED


def test_review_cases_pending_with_real_extracts():
    """Provenance: review_case extract files exist and recorded sha256
    matches bytes on disk; decision stays PENDING."""
    import hashlib
    for evidence_dir, extract, sha in [
        ("es-pn-donana", "boe-ley8-1999-art44-extract.txt",
         "b0338f25ca193280075ba2bb293d80ba8b7daab868da91f405efa206e8029a7b"),
        ("es-pn-sierra-nieves", "boja-162-2018-vivaqueo-extract.txt",
         "4bfffcbb511706bd68325ca226f00bbbf2fb83d8b0bd070add416751c5f5b4ba"),
    ]:
        rc = json.loads(io.open(
            EVIDENCE_ROOT / evidence_dir / "review_case.json",
            encoding="utf-8").read())
        p = EVIDENCE_ROOT / evidence_dir / rc["source"]["extract_file"]
        assert p.exists()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == sha
        assert rc["reviewer_decision"] == "PENDING"
        assert rc["automated_state"] == "READY_FOR_HUMAN_REVIEW"
