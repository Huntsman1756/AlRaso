"""M8 Guadarrama candidate-corpus safety tests.

The candidate fixture under discovery/evidence/m8-guadarrama/ is an evidence
proposal pending HUMAN legal review (RC-M8-ES-MD-GUADARRAMA-VIVAC). These
tests prove — at the code level — that none of it can ever produce a
publishable effect:

  * every rule version is REVIEW_REQUIRED with legal/spatial review incomplete
  * the eligibility gate rejects every version
  * the resolver answers UNDETERMINED/INCOMPLETE for every scope, even when
    caller-supplied facts would satisfy the PROPOSED conditions
  * no PERMITTED (nor PROHIBITED) can leak out of unreviewed candidates
"""

from __future__ import annotations

import hashlib
import io
import json
import pathlib

from alraso.bitemporal import BitemporalStore, VersionRow
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.eligibility import is_rule_version_eligible
from alraso.ingest.ordesa import ingest_corpus
from alraso.resolver import Resolver

EVIDENCE_DIR = (pathlib.Path(__file__).resolve().parent.parent
                / "discovery" / "evidence" / "m8-guadarrama")


def _load() -> tuple[BitemporalStore, dict]:
    fx = json.loads(io.open(EVIDENCE_DIR / "candidate_fixture.json",
                            encoding="utf-8").read())
    store = BitemporalStore.connect(":memory:")
    ingest_corpus(store, fx)
    return store, fx


def _query(scope: str, facts: dict | None = None) -> Query:
    return Query(activity="VIVAC_AL_RASO", activity_date="2026-09-17",
                 knowledge_date="2026-09-17", spatial_scope_id=scope,
                 facts=facts or {})


def test_candidate_fixture_declares_no_review_complete():
    _store, fx = _load()
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


def test_every_candidate_version_is_ineligible():
    store, fx = _load()
    rows = store.conn.execute("SELECT * FROM legal_rule_version").fetchall()
    assert len(rows) == len(fx["legal_rule_versions"])
    cols = [c[1] for c in store.conn.execute(
        "PRAGMA table_info(legal_rule_version)")]
    for row in rows:
        v = dict(zip(cols, row))
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
            spatial_review_complete=(None if v["spatial_review_complete"]
                                     is None
                                     else bool(v["spatial_review_complete"])),
            evidence_required=bool(v["evidence_required"]),
            normative_basis=json.loads(v["normative_basis"]))
        reasons = is_rule_version_eligible(vr, store,
                                           activity_date="2026-09-17")
        assert reasons, f"{v['rule_id']} unexpectedly eligible"
        assert any(r.startswith("REVIEW_NOT_PUBLISHABLE") for r in reasons)
        assert "LEGAL_REVIEW_INCOMPLETE" in reasons
        assert "SPATIAL_REVIEW_INCOMPLETE" in reasons


def test_vivac_zone_facts_still_undetermined():
    """Facts satisfying the PROPOSED Anexo III PERMITTED conditions cannot
    produce PERMITTED while review is pending."""
    store, _fx = _load()
    res = Resolver(store).resolve(_query(
        "ss-pnsg-vivac-anexo3",
        facts={"nights_same_zone": 1, "group_size": 4}))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert res.legal_status is not LegalStatus.PERMITTED


def test_pn_scope_still_undetermined_not_prohibited():
    """The proposed PROHIBITED on the park scope cannot leak either —
    nothing is publishable pre-review, in either direction."""
    store, _fx = _load()
    for facts in ({}, {"vivac_zone_anexo3": False},
                  {"vivac_zone_anexo3": True,
                   "nights_same_zone": 1, "group_size": 4}):
        res = Resolver(store).resolve(_query("ss-pnsg-pn-cm", facts))
        assert res.legal_status is LegalStatus.UNDETERMINED
        assert res.legal_status is not LegalStatus.PROHIBITED
        assert res.legal_status is not LegalStatus.PERMITTED


def test_review_case_provenance_and_pending():
    """Extract sha256 on disk matches the recorded digest; case stays
    PENDING/READY_FOR_HUMAN_REVIEW."""
    rc = json.loads(io.open(EVIDENCE_DIR / "review_case.json",
                            encoding="utf-8").read())
    extract = EVIDENCE_DIR / rc["source"]["extract_file"]
    assert extract.exists()
    digest = hashlib.sha256(extract.read_bytes()).hexdigest()
    assert digest == rc["source"]["extract_sha256"]
    assert rc["reviewer_decision"] == "PENDING"
    assert rc["automated_state"] == "READY_FOR_HUMAN_REVIEW"
    # The annulled 2.000 m clause must not be modelled as a live condition
    fx = json.loads(io.open(EVIDENCE_DIR / "candidate_fixture.json",
                            encoding="utf-8").read())
    blob = json.dumps(fx)
    assert '"altitude_m"' not in blob
