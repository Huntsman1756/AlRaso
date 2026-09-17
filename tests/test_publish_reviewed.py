"""Gated publication path: a publishable fixture can only be produced from
an explicit, valid human APPROVE decision.

These tests use SYNTHETIC decisions. They prove the mechanics — binding,
gating, fail-closed output — not that any real review happened. The real
M10.3 cases remain REVIEW_REQUIRED until a human produces the artifact.
"""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.errors import DecisionNotApproved, InvalidDecision
from alraso.ingest.ordesa import ingest_corpus
from alraso.publish_reviewed import apply_decision, publish_files
from alraso.resolver import Resolver
from alraso.review_decision import object_sha256, sha256_hex

EVIDENCE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "discovery" / "evidence"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(case_dir: str):
    base = EVIDENCE_ROOT / case_dir
    case = json.loads(io.open(base / "review_case.json", encoding="utf-8").read())
    fixture = json.loads(
        io.open(base / "candidate_fixture.json", encoding="utf-8").read())
    return base, case, fixture


def _decision(case, fixture, case_dir, decision="APPROVE",
              disposition="NOT_APPLICABLE"):
    extract = case["source"]["extract_file"]
    reviewed = {extract: sha256_hex((case_dir / extract).read_bytes())}
    src = case["source"]
    for field in ("akn_sha256", "pdf_sha256"):
        if src.get(field):
            reviewed["source:" + field] = src[field]
            break
    geom_ref = case["geometry_evidence"]["reference"]
    reviewed[geom_ref] = sha256_hex((REPO_ROOT / geom_ref).read_bytes())
    return {
        "schema": "alraso/review-decision@1",
        "review_case_id": case["review_case_id"],
        "case_sha256": object_sha256(case),
        "candidate_fixture_sha256": object_sha256(fixture),
        "decision": decision,
        "reviewer": {"name": "Synthetic Test Reviewer",
                     "reference": "pytest-fixture-only"},
        "decided_at": "2026-09-17T00:00:00Z",
        "reviewed_evidence": reviewed,
        "spatial_disposition": disposition,
        "annotation": "Synthetic decision for gated-publication tests only.",
    }


def test_approve_produces_publishable_aiguestortes_fixture():
    """APPROVE (synthetic) flips the candidate into an eligible fixture:
    PROHIBITED then resolves inside the park scope."""
    base, case, fixture = _load("m10.3-aiguestortes")
    decision = _decision(case, fixture, base)
    published = apply_decision(decision, case, fixture,
                               case_dir=base, repo_root=REPO_ROOT)

    assert published["fixture_meta"]["publishable"] is True
    prov = published["fixture_meta"]["review_decision"]
    assert prov["review_case_id"] == case["review_case_id"]
    assert prov["case_sha256"] == object_sha256(case)
    for v in published["legal_rule_versions"]:
        assert v["review_status"] == "VERIFIED"
        assert v["legal_review_complete"] is True
        assert v["spatial_review_complete"] is None  # NOT_APPLICABLE
    for f in published["legal_fragments"]:
        assert f["review_status"] == "VERIFIED"

    store = BitemporalStore.connect(":memory:")
    ingest_corpus(store, published)
    res = Resolver(store).resolve(Query(
        activity="VIVAC_AL_RASO", activity_date="2026-09-01",
        knowledge_date="2026-09-12",
        spatial_scope_id="ss-pn-aiguestortes"))
    assert res.legal_status is LegalStatus.PROHIBITED
    assert res.knowledge_status is KnowledgeStatus.CURRENT


def test_spatial_reviewed_disposition_marks_scope_reviewed():
    base, case, fixture = _load("m10.3-aiguestortes")
    decision = _decision(case, fixture, base, disposition="REVIEWED")
    published = apply_decision(decision, case, fixture,
                               case_dir=base, repo_root=REPO_ROOT)
    for v in published["legal_rule_versions"]:
        assert v["spatial_review_complete"] is True
    for s in published["spatial_scopes"]:
        assert s["review_status"] == "SPATIAL_REVIEWED"


@pytest.mark.parametrize("decision", ["REJECT", "EXTERNAL_REVIEW"])
def test_non_approve_decisions_publish_nothing(decision):
    base, case, fixture = _load("m10.3-teide")
    dec = _decision(case, fixture, base, decision=decision)
    dec.pop("candidate_fixture_sha256")
    with pytest.raises(DecisionNotApproved):
        apply_decision(dec, case, fixture, case_dir=base, repo_root=REPO_ROOT)


def test_invalid_decision_never_publishes():
    base, case, fixture = _load("m10.3-teide")
    dec = _decision(case, fixture, base)
    dec["reviewer"] = {"name": "", "reference": ""}
    with pytest.raises(InvalidDecision) as exc:
        apply_decision(dec, case, fixture, case_dir=base, repo_root=REPO_ROOT)
    assert "REVIEWER_NAME_MISSING" in exc.value.detail["reasons"]


def test_publish_files_writes_canonical_output(tmp_path):
    base, case, fixture = _load("m10.3-aiguestortes")
    dec = _decision(case, fixture, base)
    dec_path = tmp_path / "decision.json"
    dec_path.write_text(json.dumps(dec), encoding="utf-8")
    out = tmp_path / "published.json"
    summary = publish_files(dec_path, base / "review_case.json",
                            base / "candidate_fixture.json", out,
                            repo_root=REPO_ROOT)
    assert summary["rules"] == 1
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["fixture_meta"]["publishable"] is True


def test_publish_files_refuses_reject(tmp_path):
    base, case, fixture = _load("m10.3-sierra-nevada")
    dec = _decision(case, fixture, base, decision="REJECT")
    dec.pop("candidate_fixture_sha256")
    dec_path = tmp_path / "decision.json"
    dec_path.write_text(json.dumps(dec), encoding="utf-8")
    out = tmp_path / "published.json"
    with pytest.raises(DecisionNotApproved):
        publish_files(dec_path, base / "review_case.json",
                      base / "candidate_fixture.json", out,
                      repo_root=REPO_ROOT)
    assert not out.exists()


def test_original_candidates_remain_undetermined_without_artifact():
    """Regression anchor: absent any decision artifact the candidates still
    resolve UNDETERMINED — the pipeline adds no backdoor."""
    for case_dir, scope in (("m10.3-aiguestortes", "ss-pn-aiguestortes"),
                            ("m10.3-teide", "ss-pn-teide"),
                            ("m10.3-sierra-nevada", "ss-pn-sierra-nevada")):
        _base, _case, fixture = _load(case_dir)
        store = BitemporalStore.connect(":memory:")
        ingest_corpus(store, fixture)
        res = Resolver(store).resolve(Query(
            activity="VIVAC_AL_RASO", activity_date="2026-09-01",
            knowledge_date="2026-09-12", spatial_scope_id=scope))
        assert res.legal_status is LegalStatus.UNDETERMINED
