"""M7 holdout sealing tool — run LOCALLY by a HUMAN CUSTODIAN.

This tool implements the custody step of `docs/validation/m7/protocol-v1.md`
section 12: a neutral human custodian selects 4 holdout cases from the
pre-registered normative frame (`normative-case-frame-v1.md`), seals them,
and hands back ONLY the public commitment fields for
`docs/validation/m7/holdout-manifest-v1.json`.

    python tooling/m7_seal_holdout.py \
        --input holdout-cases.json \
        --custodian "Full Name, role/contact" \
        --output holdout-commitment.json

Input: a JSON file containing EXACTLY the 4 holdout case objects, either as a
top-level array or as an object with a "cases" array. The input file is
SECRET: it must live outside the public repository and must never be
committed (protocol section 12: "Los contenidos secretos del holdout NO se
almacenan en el repositorio publico antes de que el tripwire deba
ejecutarse").

The commitment is computed over the CANONICAL form of the case list
(json.dumps with sort_keys=True, ensure_ascii=True, separators=(",", ":")),
so formatting or key-ordering differences in the input file never change
holdout_sha256.

Output: a sealed-commitment record JSON (safe to keep outside the repo or to
hand to the author; it contains no case contents, only the commitment):

    {"schema", "protocol", "custodian", "sealed_at", "holdout_sha256",
     "case_ids"}

Exit codes: 0 sealed; 1 invalid input/arguments; 2 argparse usage error.

Reminder (protocol section 12, mandatory declaration): the SHA-256
commitment demonstrates non-substitution after commitment. It does NOT prove
independent sample design and does NOT prove that the author was ignorant of
the normative strata. Hashing does not create blindness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "alraso-m7-holdout-commitment-v1"
PROTOCOL = "M7 protocol-v1"
HOLDOUT_N = 4  # pre-registered: protocol-v1.md section 12


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_bytes(obj) -> bytes:
    """Canonical JSON bytes: identical semantic content -> identical bytes."""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")


def _load_cases(path: Path) -> list:
    """Load the secret holdout case list. Accepts a bare array of cases or an
    object with a "cases" array."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"seal: cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"seal: {path} is not valid JSON: {exc}")
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise SystemExit(
            "seal: input must be a JSON array of case objects or an object "
            'with a "cases" array'
        )
    return cases


def _validate_cases(cases: list) -> list[str]:
    """Enforce HOLDOUT_N=4 and return the case_id list (order preserved)."""
    if len(cases) != HOLDOUT_N:
        raise SystemExit(
            f"seal: holdout must contain exactly {HOLDOUT_N} case objects "
            f"(protocol-v1 section 12, HOLDOUT_N=4); got {len(cases)}"
        )
    case_ids: list[str] = []
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise SystemExit(f"seal: case #{i + 1} is not a JSON object")
        cid = case.get("case_id")
        if not isinstance(cid, str) or not cid.strip():
            raise SystemExit(
                f"seal: case #{i + 1} lacks a non-empty string 'case_id'; "
                "the commitment must be traceable to identifiable cases"
            )
        if cid in case_ids:
            raise SystemExit(f"seal: duplicate case_id {cid!r}")
        case_ids.append(cid)
    return case_ids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="m7_seal_holdout",
        description=(
            "Seal the 4 M7 holdout cases (HUMAN CUSTODIAN only). Computes "
            "the SHA-256 commitment over the canonical case list and writes "
            "a sealed-commitment record. The input file is SECRET and must "
            "never be committed to the public repository."
        ),
    )
    ap.add_argument(
        "--input",
        required=True,
        help="JSON file with exactly 4 holdout case objects (SECRET; "
        "custodian-selected, NOT in the repo)",
    )
    ap.add_argument(
        "--custodian",
        required=True,
        help="custodian identity string recorded publicly in the manifest "
        "(name + role/contact)",
    )
    ap.add_argument(
        "--output",
        required=True,
        help="path for the sealed-commitment record JSON (contains no case "
        "contents; safe to hand to the author)",
    )
    ap.add_argument(
        "--sealed-at",
        default=None,
        help="override sealing timestamp (UTC ISO-8601); default: now. "
        "Does NOT affect holdout_sha256.",
    )
    args = ap.parse_args(argv)

    cases = _load_cases(Path(args.input))
    case_ids = _validate_cases(cases)

    sealed_at = args.sealed_at or _utc_now_iso()
    holdout_sha256 = hashlib.sha256(_canonical_bytes(cases)).hexdigest()

    record = {
        "schema": SCHEMA,
        "protocol": PROTOCOL,
        "custodian": args.custodian,
        "sealed_at": sealed_at,
        "holdout_sha256": holdout_sha256,
        "case_ids": case_ids,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("Holdout sealed. Hand these fields back to the author for")
    print("docs/validation/m7/holdout-manifest-v1.json:")
    print()
    print(f"  HOLDOUT_CUSTODIAN          = {args.custodian}")
    print(f"  HOLDOUT_COMMITMENT_SHA256  = {holdout_sha256}")
    print(f"  SEALED_AT                  = {sealed_at}")
    print("  STATUS                     = SEALED")
    print()
    print(f"  commitment record written to: {out_path}")
    print()
    print("REMINDERS (protocol-v1 section 12):")
    print("  - The input file with the 4 case contents is SECRET. Do NOT commit")
    print("    it to the public repository and do NOT share it with the author")
    print("    before the tripwire executes.")
    print("  - The SHA-256 commitment demonstrates non-substitution after")
    print("    commitment. It does NOT prove independent sample design and does")
    print("    NOT prove that the author was ignorant of the normative strata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
