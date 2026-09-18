"""Gated publication path for human-reviewed candidate fixtures.

The ONLY route from an M10.3 candidate fixture (REVIEW_REQUIRED,
non-publishable) to a publishable corpus fixture is a valid human
ReviewDecision artifact with decision=APPROVE (alraso.review_decision).

There is no flag, env var or argument that skips the decision: a REJECT or
EXTERNAL_REVIEW decision — or an artifact that fails binding validation —
produces NO output. The reviewer never edits the fixture by hand; this tool
applies the decision mechanically so the published content is provably the
content the reviewer approved (candidate_fixture_sha256 binding).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from alraso.errors import DecisionNotApproved, InvalidDecision
from alraso.review_decision import (
    canonical_json,
    object_sha256,
    sha256_hex,
    validate_decision,
)


def apply_decision(
    decision: dict[str, Any],
    case: dict[str, Any],
    candidate_fixture: dict[str, Any],
    *,
    case_dir: str | Path = ".",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the publishable fixture derived from an APPROVE decision.

    Raises InvalidDecision (with the full reason list in ``detail``) when the
    artifact does not validate, and DecisionNotApproved for REJECT /
    EXTERNAL_REVIEW. Never returns a publishable fixture otherwise.
    """
    reasons = validate_decision(
        decision, case, candidate_fixture=candidate_fixture,
        case_dir=case_dir, repo_root=repo_root)
    if reasons:
        raise InvalidDecision(
            "review decision failed validation",
            detail={"reasons": reasons})
    if decision.get("decision") != "APPROVE":
        raise DecisionNotApproved(
            f"decision is {decision.get('decision')!r}; "
            "only APPROVE may publish",
            detail={"decision": decision.get("decision")})

    out = copy.deepcopy(candidate_fixture)
    provenance = {
        "review_case_id": case.get("review_case_id"),
        "case_sha256": decision["case_sha256"],
        "candidate_fixture_sha256": decision["candidate_fixture_sha256"],
        "decision_sha256": object_sha256(decision),
        "decided_at": decision["decided_at"],
        "reviewer_name": decision["reviewer"]["name"],
        "reviewer_reference": decision["reviewer"]["reference"],
        "spatial_disposition": decision["spatial_disposition"],
        "annotation": decision["annotation"],
    }

    meta = out.setdefault("fixture_meta", {})
    meta["name"] = str(meta.get("name", "CANDIDATE")).replace(
        "CANDIDATE", "REVIEWED")
    meta["publishable"] = True
    meta["review_decision"] = provenance

    for frag in out.get("legal_fragments", []):
        frag["review_status"] = "VERIFIED"

    spatial_done = decision["spatial_disposition"] == "REVIEWED"
    for scope in out.get("spatial_scopes", []):
        scope["review_status"] = (
            "SPATIAL_REVIEWED" if spatial_done
            else "SPATIAL_REVIEW_NOT_APPLICABLE")

    for version in out.get("legal_rule_versions", []):
        version["review_status"] = "VERIFIED"
        version["legal_review_complete"] = True
        version["spatial_review_complete"] = (
            True if spatial_done else None)

    # Rule relations are part of the adjudicated content: an APPROVE decision
    # binds the fixture hash INCLUDING declared precedence, so the relation
    # becomes human-verified and publishable exactly like the rule versions.
    for rel in out.get("rule_relations", []):
        rel["review_status"] = "VERIFIED"
        rel["legal_review_complete"] = True
        rel["human_verified"] = True

    # Candidate-era assertions were written to prove non-publishability; they
    # are not valid expectations for the reviewed fixture. Publication-time
    # expectations live in tests, not in product data.
    out.pop("expected", None)
    return out


def publish_files(
    decision_path: str | Path,
    case_path: str | Path,
    candidate_path: str | Path,
    out_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """File-level entry point: validate, apply, write canonical JSON.

    The output is written in canonical form so ``candidate_fixture_sha256``-
    style commitments on the published artifact are reproducible.
    """
    from alraso.review_decision import load_json

    decision = load_json(decision_path)
    case = load_json(case_path)
    candidate = load_json(candidate_path)
    published = apply_decision(
        decision, case, candidate,
        case_dir=Path(case_path).resolve().parent, repo_root=repo_root)
    payload = canonical_json(published)
    Path(out_path).write_bytes(payload + b"\n")
    return {
        "out": str(out_path),
        "published_sha256": sha256_hex(payload + b"\n"),
        "review_case_id": case.get("review_case_id"),
        "rules": len(published.get("legal_rule_versions", [])),
    }
