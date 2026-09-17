"""Human review-decision artifact: schema + fail-closed validator.

A ReviewDecision is the ONLY legitimate way a REVIEW_REQUIRED candidate
(M10.3 evidence packages) can become publishable. It is a deterministic,
machine-readable JSON artifact produced from an explicit HUMAN decision —
this module can validate a presented artifact but can never manufacture one.

Binding model (why a decision cannot be laundered onto different content):

  * ``case_sha256`` pins the decision to the canonical form of the exact
    review_case.json the reviewer adjudicated — editing the case after the
    decision invalidates it.
  * ``candidate_fixture_sha256`` pins APPROVE to the exact proposed rule
    content — post-decision edits to the fixture invalidate the decision.
  * ``reviewed_evidence`` pins the evidence the reviewer claims to have
    seen: entries naming on-disk files are recomputed; entries for
    non-redistributed official artifacts must match the hashes the review
    case itself declares (attestation binding, not byte verification —
    the artifact is identified by hash because e.g. a 44 MB official PDF
    is not redistributed).

Validation is fail-closed: every structural, identity, binding or evidence
defect yields a reason code; an APPROVE decision additionally requires a
closed spatial disposition and a non-empty annotation.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "alraso/review-decision@1"

DECISIONS = frozenset({"APPROVE", "REJECT", "EXTERNAL_REVIEW"})
SPATIAL_DISPOSITIONS = frozenset({"REVIEWED", "NOT_APPLICABLE", "INCOMPLETE"})

_HEX64 = frozenset("0123456789abcdef")


def canonical_json(obj: Any) -> bytes:
    """Deterministic serialization used for all commitment hashing.

    sort_keys + tight separators + UTF-8: formatting or key-order differences
    in the source file never change the commitment.
    """
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_sha256(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


def load_json(path: str | Path) -> Any:
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _is_sha256(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in _HEX64 for c in value))


def _parse_iso8601(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _resolve_evidence_file(key: str, case_dir: Path, repo_root: Path | None) -> Path | None:
    """Resolve a reviewed_evidence key to a file on disk, if it is one.

    Keys may be relative to the case directory (extract files) or to the
    repository root (shared digest artifacts). Anything that resolves to no
    file is treated as a non-redistributed artifact reference.
    """
    candidates = [case_dir / key]
    if repo_root is not None:
        candidates.append(repo_root / key)
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def _required_evidence(case: dict[str, Any], case_dir: Path,
                       repo_root: Path | None) -> tuple[dict[str, str], list[str]]:
    """Evidence keys a decision MUST cover, with their expected sha256.

    Returns (required, reasons). ``required`` maps key -> expected sha256:
    on-disk artifacts are recomputed; non-redistributed official artifacts
    are bound to the hash the case declares.
    """
    required: dict[str, str] = {}
    reasons: list[str] = []

    src = case.get("source") or {}
    extract = src.get("extract_file")
    if isinstance(extract, str) and extract:
        declared = src.get("extract_sha256")
        path = case_dir / extract
        if not path.is_file():
            reasons.append(f"CASE_EVIDENCE_MISSING:{extract}")
        else:
            actual = sha256_hex(path.read_bytes())
            if _is_sha256(declared) and declared != actual:
                reasons.append(f"CASE_EXTRACT_HASH_MISMATCH:{extract}")
            required[extract] = actual
    else:
        reasons.append("CASE_EXTRACT_UNDECLARED")

    # Non-redistributed primary source artifact: attestation binding. The
    # decision must name the same content hash the case declares.
    for field in ("akn_sha256", "pdf_sha256"):
        declared = src.get(field)
        if _is_sha256(declared):
            required["source:" + field] = declared
            break

    geom = case.get("geometry_evidence") or {}
    ref = geom.get("reference")
    if isinstance(ref, str) and ref:
        path = _resolve_evidence_file(ref, case_dir, repo_root)
        if path is None:
            reasons.append(f"CASE_GEOMETRY_REFERENCE_MISSING:{ref}")
        else:
            required[ref] = sha256_hex(path.read_bytes())

    return required, reasons


def validate_decision(
    decision: dict[str, Any],
    case: dict[str, Any],
    *,
    candidate_fixture: dict[str, Any] | None = None,
    case_dir: str | Path = ".",
    repo_root: str | Path | None = None,
) -> list[str]:
    """Return the list of rejection reasons ([] == artifact is valid).

    ``candidate_fixture`` is mandatory when the decision is APPROVE: approval
    must bind to the exact proposed rule content. ``case_dir``/``repo_root``
    locate the evidence files referenced by the case.
    """
    reasons: list[str] = []
    case_dir = Path(case_dir)
    root = Path(repo_root) if repo_root is not None else None

    if not isinstance(decision, dict):
        return ["DECISION_NOT_AN_OBJECT"]

    if decision.get("schema") != SCHEMA:
        reasons.append(f"SCHEMA_MISMATCH:{decision.get('schema')!r}")

    if decision.get("review_case_id") != case.get("review_case_id"):
        reasons.append(
            f"CASE_ID_MISMATCH:{decision.get('review_case_id')!r}")

    declared_case_sha = decision.get("case_sha256")
    if not _is_sha256(declared_case_sha):
        reasons.append("CASE_SHA256_MISSING_OR_MALFORMED")
    elif declared_case_sha != object_sha256(case):
        reasons.append("CASE_SHA256_MISMATCH")

    if case.get("reviewer_decision") != "PENDING":
        reasons.append(f"CASE_NOT_PENDING:{case.get('reviewer_decision')!r}")
    if case.get("automated_state") != "READY_FOR_HUMAN_REVIEW":
        reasons.append(
            f"CASE_NOT_READY:{case.get('automated_state')!r}")

    dec = decision.get("decision")
    if dec not in DECISIONS:
        reasons.append(f"DECISION_UNKNOWN:{dec!r}")

    reviewer = decision.get("reviewer")
    if not isinstance(reviewer, dict):
        reasons.append("REVIEWER_MISSING")
    else:
        if not (isinstance(reviewer.get("name"), str)
                and reviewer["name"].strip()):
            reasons.append("REVIEWER_NAME_MISSING")
        if not (isinstance(reviewer.get("reference"), str)
                and reviewer["reference"].strip()):
            reasons.append("REVIEWER_REFERENCE_MISSING")

    if not _parse_iso8601(decision.get("decided_at")):
        reasons.append("DECIDED_AT_INVALID")

    if not (isinstance(decision.get("annotation"), str)
            and decision["annotation"].strip()):
        reasons.append("ANNOTATION_MISSING")

    disposition = decision.get("spatial_disposition")
    if disposition not in SPATIAL_DISPOSITIONS:
        reasons.append(f"SPATIAL_DISPOSITION_UNKNOWN:{disposition!r}")

    if dec == "APPROVE":
        if disposition == "INCOMPLETE":
            reasons.append("APPROVE_WITH_SPATIAL_INCOMPLETE")
        declared_fx_sha = decision.get("candidate_fixture_sha256")
        if not _is_sha256(declared_fx_sha):
            reasons.append("FIXTURE_SHA256_MISSING_OR_MALFORMED")
        elif candidate_fixture is None:
            reasons.append("FIXTURE_REQUIRED_FOR_APPROVE")
        elif declared_fx_sha != object_sha256(candidate_fixture):
            reasons.append("FIXTURE_SHA256_MISMATCH")

    # Evidence coverage: every required artifact must be listed and every
    # listed artifact must verify.
    required, evidence_reasons = _required_evidence(case, case_dir, root)
    reasons.extend(evidence_reasons)

    reviewed = decision.get("reviewed_evidence")
    if not isinstance(reviewed, dict) or not reviewed:
        reasons.append("REVIEWED_EVIDENCE_MISSING")
    else:
        for key, expected in required.items():
            got = reviewed.get(key)
            if got is None:
                reasons.append(f"EVIDENCE_NOT_REVIEWED:{key}")
            elif got != expected:
                reasons.append(f"EVIDENCE_HASH_MISMATCH:{key}")
        for key, value in reviewed.items():
            if not _is_sha256(value):
                reasons.append(f"EVIDENCE_HASH_MALFORMED:{key}")
                continue
            if key in required:
                continue
            path = _resolve_evidence_file(key, case_dir, root)
            if path is not None and sha256_hex(path.read_bytes()) != value:
                reasons.append(f"EVIDENCE_HASH_MISMATCH:{key}")

    return reasons
