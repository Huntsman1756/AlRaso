"""M8-F holdout sealing tool — run LOCALLY by a HUMAN CUSTODIAN.

Seals the blind Madrid holdout preregistered in
`docs/validation/m8/M8-HOLDOUT.md`. The custodian selects the real cases
(coordinate + date + activity + expected class per stratum) in a SECRET
file that must NEVER enter the public repository; this tool validates the
structure, computes the canonical SHA-256 commitment and writes a public
commitment record containing NO case contents (no coordinates, no
expected answers).

    python tooling/m8_holdout_seal.py \
        --input m8f-cases.json \
        --custodian "Full Name, role/contact" \
        --output m8f-commitment.json

The commitment is computed over the CANONICAL form of the case list
(json.dumps with sort_keys=True, ensure_ascii=True, separators=(",", ":")),
so formatting or key-ordering differences never change holdout_sha256.

Exit codes: 0 sealed; 1 invalid input; 2 argparse usage error.

Reminder (same as M7 protocol section 12): the SHA-256 commitment
demonstrates non-substitution after commitment. It does NOT prove
independent sample design and does NOT prove that the implementer was
ignorant of the strata. Hashing does not create blindness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "alraso-m8-holdout-commitment-v1"
PROTOCOL = "M8-HOLDOUT.md"

EXPECTED_CLASSES = frozenset(
    {"PERMITTED", "CONDITIONAL", "BLOCKED", "UNDETERMINED", "UNKNOWN"})

REQUIRED_STRATA = frozenset({
    "pn_guadarrama_interior",
    "vivac_zone_anexo3",
    "zpp",
    "hole_or_exclusion",
    "boundary",
    "pr_cuenca_alta_manzanares",
    "pr_curso_medio_guadarrama",
    "pr_sureste",
    "territorio_general",
    "temporal_variant",
    "expected_undetermined",
    "expected_unknown",
})

# Comunidad de Madrid rough bounding box (sanity check, not a gate).
_LAT_RANGE = (39.7, 41.3)
_LON_RANGE = (-4.7, -2.9)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_bytes(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")


def _load_cases(path: Path) -> list:
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


def _validate_cases(cases: list) -> dict:
    """Validate structure + strata coverage; return stats for the public
    record (ids + per-stratum counts only — never coordinates/expected)."""
    case_ids: list[str] = []
    strata_counts: dict[str, int] = {}
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise SystemExit(f"seal: case #{i + 1} is not a JSON object")
        cid = case.get("case_id")
        if not isinstance(cid, str) or not cid.strip():
            raise SystemExit(
                f"seal: case #{i + 1} lacks a non-empty string 'case_id'")
        if cid in case_ids:
            raise SystemExit(f"seal: duplicate case_id {cid!r}")
        case_ids.append(cid)

        for field in ("lat", "lon"):
            v = case.get(field)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise SystemExit(f"seal: case {cid!r} lacks numeric '{field}'")
        lat, lon = float(case["lat"]), float(case["lon"])
        if not (_LAT_RANGE[0] <= lat <= _LAT_RANGE[1]
                and _LON_RANGE[0] <= lon <= _LON_RANGE[1]):
            raise SystemExit(
                f"seal: case {cid!r} coordinate ({lat}, {lon}) outside the "
                "Comunidad de Madrid sanity box; verify CRS (expect EPSG:4326)")

        date = case.get("date")
        if not isinstance(date, str) or len(date) != 10:
            raise SystemExit(
                f"seal: case {cid!r} lacks 'date' in YYYY-MM-DD form")
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(f"seal: case {cid!r} has invalid date {date!r}")

        if case.get("activity") != "VIVAC_AL_RASO":
            raise SystemExit(
                f"seal: case {cid!r} activity must be 'VIVAC_AL_RASO' "
                "(M8 scope)")

        stratum = case.get("stratum")
        if stratum not in REQUIRED_STRATA:
            raise SystemExit(
                f"seal: case {cid!r} has unknown stratum {stratum!r}; "
                f"expected one of {sorted(REQUIRED_STRATA)}")
        strata_counts[stratum] = strata_counts.get(stratum, 0) + 1

        expected = case.get("expected_class")
        if expected not in EXPECTED_CLASSES:
            raise SystemExit(
                f"seal: case {cid!r} has unknown expected_class "
                f"{expected!r}; expected one of {sorted(EXPECTED_CLASSES)}")

    missing = REQUIRED_STRATA - set(strata_counts)
    if missing:
        raise SystemExit(
            f"seal: holdout misses required strata: {sorted(missing)} "
            "(M8-HOLDOUT.md section 3)")
    return {"case_ids": case_ids, "strata_counts": strata_counts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="m8_holdout_seal",
        description=(
            "Seal the M8-F blind Madrid holdout (HUMAN CUSTODIAN only). "
            "Computes the SHA-256 commitment over the canonical case list "
            "and writes a public commitment record with NO case contents."
        ),
    )
    ap.add_argument("--input", required=True,
                    help="JSON file with the holdout cases (SECRET; "
                    "custodian-selected, NOT in the repo)")
    ap.add_argument("--custodian", required=True,
                    help="custodian identity string recorded publicly "
                    "(name + role/contact)")
    ap.add_argument("--output", required=True,
                    help="path for the public commitment record JSON")
    ap.add_argument("--sealed-at", default=None,
                    help="override sealing timestamp (UTC ISO-8601); "
                    "default: now. Does NOT affect holdout_sha256.")
    args = ap.parse_args(argv)

    cases = _load_cases(Path(args.input))
    stats = _validate_cases(cases)

    sealed_at = args.sealed_at or _utc_now_iso()
    holdout_sha256 = hashlib.sha256(_canonical_bytes(cases)).hexdigest()

    record = {
        "schema": SCHEMA,
        "protocol": PROTOCOL,
        "custodian": args.custodian,
        "sealed_at": sealed_at,
        "holdout_sha256": holdout_sha256,
        "case_count": len(cases),
        "case_ids": stats["case_ids"],
        "strata_counts": stats["strata_counts"],
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    print("M8-F holdout sealed. Hand these fields back for")
    print("docs/validation/m8/holdout-manifest-v1.json:")
    print()
    print(f"  CUSTODIAN            = {args.custodian}")
    print(f"  COMMITMENT_SHA256    = {holdout_sha256}")
    print(f"  SEALED_AT            = {sealed_at}")
    print(f"  CASE_COUNT           = {len(cases)}")
    print(f"  STRATA_COUNTS        = {json.dumps(stats['strata_counts'], sort_keys=True)}")
    print("  STATUS               = SEALED")
    print()
    print(f"  commitment record written to: {out_path}")
    print()
    print("REMINDERS:")
    print("  - The input file with the real cases is SECRET. Do NOT commit it")
    print("    and do NOT share it with the implementer before execution.")
    print("  - The SHA-256 commitment demonstrates non-substitution after")
    print("    commitment. It does NOT prove independent sample design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
