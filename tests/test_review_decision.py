"""ReviewDecision artifact: fail-closed validation tests.

The decision artifact is the ONLY bridge between a REVIEW_REQUIRED
candidate and a publishable rule. These tests prove the validator rejects
every shortcut: wrong schema, wrong case, mutated case/fixture content,
missing reviewer identity, uncovered evidence, hash mismatches, and
APPROVE with an open spatial question.

All reviewer identities here are SYNTHETIC test data — no test asserts or
implies a real human review took place.
"""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from alraso.review_decision import (
    object_sha256,
    sha256_hex,
    validate_decision,
)

EVIDENCE_ROOT = pathlib.Path(__file__).resolve().parent.parent / "discovery" / "evidence"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

CASE_DIRS = ["m10.3-aiguestortes", "m10.3-teide", "m10.3-sierra-nevada"]


def _load(case_dir: str):
    base = EVIDENCE_ROOT / case_dir
    case = json.loads(io.open(base / "review_case.json", encoding="utf-8").read())
    fixture = json.loads(
        io.open(base / "candidate_fixture.json", encoding="utf-8").read())
    return base, case, fixture


def _valid_decision(case: dict, fixture: dict, case_dir: pathlib.Path) -> dict:
    """A structurally valid SYNTHETIC decision for validator testing."""
    extract = case["source"]["extract_file"]
    reviewed = {
        extract: sha256_hex((case_dir / extract).read_bytes()),
    }
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
        "decision": "APPROVE",
        "reviewer": {"name": "Synthetic Test Reviewer",
                     "reference": "pytest-fixture-only",
                     "qualification": "none — test data"},
        "decided_at": "2026-09-17T00:00:00Z",
        "reviewed_evidence": reviewed,
        "spatial_disposition": "NOT_APPLICABLE",
        "annotation": "Synthetic decision for validator tests only.",
    }


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_valid_synthetic_approve_validates(case_dir):
    """A well-formed artifact binding case+fixture+evidence passes."""
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    assert validate_decision(decision, case, candidate_fixture=fixture,
                             case_dir=base, repo_root=REPO_ROOT) == []


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_reject_and_external_review_validate(case_dir):
    """REJECT / EXTERNAL_REVIEW are valid terminal decisions (no fixture
    binding required)."""
    base, case, fixture = _load(case_dir)
    for dec in ("REJECT", "EXTERNAL_REVIEW"):
        decision = _valid_decision(case, fixture, base)
        decision["decision"] = dec
        decision.pop("candidate_fixture_sha256")
        assert validate_decision(decision, case, case_dir=base,
                                 repo_root=REPO_ROOT) == []


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_mutated_case_invalidates_decision(case_dir):
    """Editing the case after the decision breaks case_sha256 binding."""
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    mutated = dict(case)
    mutated["proposed_effect"] = "PROHIBITED — edited after review"
    reasons = validate_decision(decision, mutated, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert "CASE_SHA256_MISMATCH" in reasons


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_mutated_fixture_invalidates_approve(case_dir):
    """Editing the candidate after approval breaks fixture binding."""
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    mutated = json.loads(json.dumps(fixture))
    mutated["legal_rule_versions"][0]["effective_from"] = "1999-01-01"
    reasons = validate_decision(decision, case, candidate_fixture=mutated,
                                case_dir=base, repo_root=REPO_ROOT)
    assert "FIXTURE_SHA256_MISMATCH" in reasons


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_missing_reviewer_identity_fails(case_dir):
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    decision["reviewer"] = {"name": "", "reference": ""}
    reasons = validate_decision(decision, case, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert "REVIEWER_NAME_MISSING" in reasons
    assert "REVIEWER_REFERENCE_MISSING" in reasons


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_uncovered_evidence_fails(case_dir):
    """A decision that omits a required evidence hash fails closed."""
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    extract = case["source"]["extract_file"]
    del decision["reviewed_evidence"][extract]
    reasons = validate_decision(decision, case, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert f"EVIDENCE_NOT_REVIEWED:{extract}" in reasons


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_wrong_evidence_hash_fails(case_dir):
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    extract = case["source"]["extract_file"]
    decision["reviewed_evidence"][extract] = "0" * 64
    reasons = validate_decision(decision, case, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert f"EVIDENCE_HASH_MISMATCH:{extract}" in reasons


@pytest.mark.parametrize("case_dir", CASE_DIRS)
def test_approve_with_incomplete_spatial_fails(case_dir):
    base, case, fixture = _load(case_dir)
    decision = _valid_decision(case, fixture, base)
    decision["spatial_disposition"] = "INCOMPLETE"
    reasons = validate_decision(decision, case, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert "APPROVE_WITH_SPATIAL_INCOMPLETE" in reasons


def test_approve_without_fixture_fails():
    base, case, fixture = _load("m10.3-aiguestortes")
    decision = _valid_decision(case, fixture, base)
    reasons = validate_decision(decision, case, candidate_fixture=None,
                                case_dir=base, repo_root=REPO_ROOT)
    assert "FIXTURE_REQUIRED_FOR_APPROVE" in reasons


def test_wrong_schema_fails():
    base, case, fixture = _load("m10.3-aiguestortes")
    decision = _valid_decision(case, fixture, base)
    decision["schema"] = "alraso/review-decision@0"
    reasons = validate_decision(decision, case, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert any(r.startswith("SCHEMA_MISMATCH") for r in reasons)


def test_wrong_case_id_fails():
    base, case, fixture = _load("m10.3-aiguestortes")
    decision = _valid_decision(case, fixture, base)
    decision["review_case_id"] = "RC-OTHER"
    reasons = validate_decision(decision, case, candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert any(r.startswith("CASE_ID_MISMATCH") for r in reasons)


def test_decision_on_non_pending_case_fails():
    base, case, fixture = _load("m10.3-aiguestortes")
    decided_case = dict(case)
    decided_case["reviewer_decision"] = "APPROVE"
    decision = _valid_decision(decided_case, fixture, base)
    reasons = validate_decision(decision, decided_case,
                                candidate_fixture=fixture,
                                case_dir=base, repo_root=REPO_ROOT)
    assert any(r.startswith("CASE_NOT_PENDING") for r in reasons)
