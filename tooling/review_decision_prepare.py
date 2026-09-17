#!/usr/bin/env python3
"""Prepare a ReviewDecision SKELETON for a human reviewer.

Computes every cryptographic binding the artifact requires (case hash,
candidate fixture hash, evidence hashes) so the human only has to fill in
the fields that are legitimately theirs: identity, decision, annotation.

The emitted skeleton is NEVER valid: ``decision`` is left as "PENDING"
(outside the APPROVE/REJECT/EXTERNAL_REVIEW enum) and reviewer fields are
blank. A human must edit those fields deliberately before the artifact can
pass ``alraso.review_decision.validate_decision``.

Usage:
    python tooling/review_decision_prepare.py \\
        --case discovery/evidence/m10.3-aiguestortes/review_case.json \\
        --candidate discovery/evidence/m10.3-aiguestortes/candidate_fixture.json \\
        --repo-root . --out decision.skeleton.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alraso.review_decision import object_sha256, sha256_hex  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--case", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--repo-root", default=".")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)

    case_path = Path(args.case)
    case = json.loads(io.open(case_path, encoding="utf-8").read())
    candidate = json.loads(
        io.open(args.candidate, encoding="utf-8").read())
    case_dir = case_path.resolve().parent
    root = Path(args.repo_root).resolve()

    reviewed: dict[str, str] = {}
    src = case.get("source") or {}
    extract = src.get("extract_file")
    if extract:
        reviewed[extract] = sha256_hex((case_dir / extract).read_bytes())
    for field in ("akn_sha256", "pdf_sha256"):
        if src.get(field):
            reviewed["source:" + field] = src[field]
            break
    geom = case.get("geometry_evidence") or {}
    ref = geom.get("reference")
    if ref and (root / ref).is_file():
        reviewed[ref] = sha256_hex((root / ref).read_bytes())

    skeleton = {
        "schema": "alraso/review-decision@1",
        "review_case_id": case.get("review_case_id"),
        "case_sha256": object_sha256(case),
        "candidate_fixture_sha256": object_sha256(candidate),
        "decision": "PENDING",
        "reviewer": {"name": "", "reference": "", "qualification": ""},
        "decided_at": "",
        "reviewed_evidence": reviewed,
        "spatial_disposition": "INCOMPLETE",
        "annotation": "",
        "_instructions": (
            "HUMAN ONLY: set decision to APPROVE|REJECT|EXTERNAL_REVIEW, "
            "fill reviewer.name + reviewer.reference + decided_at "
            "(ISO-8601) + annotation, and choose spatial_disposition "
            "REVIEWED|NOT_APPLICABLE|INCOMPLETE. This skeleton is invalid "
            "until a human completes those fields; the hashes above are "
            "pre-computed bindings and must not be edited."),
    }

    Path(args.out).write_text(
        json.dumps(skeleton, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"out": args.out, "case": case.get("review_case_id"),
                      "status": "SKELETON — human fields pending"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
