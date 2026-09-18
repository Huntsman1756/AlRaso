"""M8-F holdout runner — executes the SEALED blind Madrid holdout.

Runs the secret case list (custodian-held, outside the repo) against the
FROZEN point resolver and reports per-case / per-stratum / per-class
outcomes. Protocol: docs/validation/m8/M8-HOLDOUT.md.

    python tooling/m8_holdout_run.py \
        --cases m8f-cases.json \
        --commitment m8f-commitment.json \
        --manifest discovery/evidence/m8-madrid-layers.json \
        --corpus path/to/published_corpus.json [--corpus ...] \
        --knowledge-date 2026-10-03 \
        --out holdout-results.json

Protocol guarantees enforced here:

  * NON-SUBSTITUTION: the canonical SHA-256 over the case list is
    recomputed and MUST equal the commitment's holdout_sha256; mismatch
    aborts (exit 1). This reuses the seal's canonical form byte-for-byte.
  * RESOLVER FROZEN: the runner does not mutate rules, geometry or
    expected answers; results are evidence, mismatches are reported, not
    fixed (M8-HOLDOUT.md §5).
  * BOUNDARY: a `boundary` stratum case whose determination is NOT
    boundary-flagged is reported as a protocol failure.

Actual-class mapping (preregistered §2 vocabulary):
    PERMITTED -> PERMITTED; CONDITIONAL -> CONDITIONAL;
    PROHIBITED / AUTHORIZATION_REQUIRED -> BLOCKED;
    NO_APPLICABLE_SCOPE reason -> UNKNOWN; everything else -> UNDETERMINED.

Exit codes: 0 ran (report written); 1 protocol violation (commitment
mismatch, bad inputs); 2 argparse usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from m8_holdout_seal import _canonical_bytes, _load_cases, _validate_cases  # noqa: E402

from alraso.bitemporal import BitemporalStore  # noqa: E402
from alraso.domain import LegalStatus, Query  # noqa: E402
from alraso.geojson_provider import load_manifest_provider  # noqa: E402
from alraso.ingest.ordesa import ingest_corpus  # noqa: E402
from alraso.resolver import Resolver  # noqa: E402
from alraso.resolver import RESOLVER_VERSION, SCHEMA_VERSION  # noqa: E402

COMMITMENT_SCHEMA = "alraso-m8-holdout-commitment-v1"


def _actual_class(status: LegalStatus, reason_codes: list[str]) -> str:
    if "NO_APPLICABLE_SCOPE" in reason_codes:
        return "UNKNOWN"
    if status is LegalStatus.PERMITTED:
        return "PERMITTED"
    if status is LegalStatus.CONDITIONAL:
        return "CONDITIONAL"
    if status in (LegalStatus.PROHIBITED, LegalStatus.AUTHORIZATION_REQUIRED):
        return "BLOCKED"
    return "UNDETERMINED"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="m8_holdout_run",
        description="Execute the sealed M8-F blind Madrid holdout.")
    ap.add_argument("--cases", required=True,
                    help="SECRET case list (custodian-held; never committed)")
    ap.add_argument("--commitment", required=True,
                    help="public commitment record written by "
                    "m8_holdout_seal.py")
    ap.add_argument("--manifest", required=True,
                    help="layer manifest (e.g. discovery/evidence/"
                    "m8-madrid-layers.json)")
    ap.add_argument("--corpus", action="append", default=[],
                    help="published corpus fixture(s) to ingest "
                    "(repeatable)")
    ap.add_argument("--knowledge-date", required=True,
                    help="knowledge date for all queries (YYYY-MM-DD)")
    ap.add_argument("--out", default=None,
                    help="write the JSON report here (optional)")
    args = ap.parse_args(argv)

    cases = _load_cases(Path(args.cases))
    stats = _validate_cases(cases)

    try:
        commitment = json.loads(Path(args.commitment).read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"run: cannot read commitment {args.commitment}: {exc}")
        return 1
    if commitment.get("schema") != COMMITMENT_SCHEMA:
        print(f"run: commitment schema is not {COMMITMENT_SCHEMA}")
        return 1
    digest = hashlib.sha256(_canonical_bytes(cases)).hexdigest()
    if digest != commitment.get("holdout_sha256"):
        print("run: PROTOCOL VIOLATION — case list sha256 does not match "
              "the sealed commitment (substituted or edited cases)")
        return 1
    if stats["case_ids"] != commitment.get("case_ids"):
        print("run: PROTOCOL VIOLATION — case_id list differs from the "
              "sealed commitment")
        return 1

    store = BitemporalStore.connect(":memory:")
    for c in args.corpus:
        ingest_corpus(store, json.loads(Path(c).read_text("utf-8")))
    provider = load_manifest_provider(Path(args.manifest))
    manifest_sha = hashlib.sha256(
        Path(args.manifest).read_bytes()).hexdigest()
    resolver = Resolver(store, spatial=provider)

    results = []
    protocol_failures = []
    for case in cases:
        res = resolver.resolve(Query(
            activity=case["activity"], activity_date=case["date"],
            knowledge_date=args.knowledge_date,
            lat=case["lat"], lon=case["lon"]))
        boundary_flagged = any(
            h.get("on_boundary") for h in res.applicable_scope)
        actual = _actual_class(res.legal_status, res.reason_codes)
        match = actual == case["expected_class"]
        boundary_clean = (
            case["stratum"] == "boundary" and not boundary_flagged
            and res.legal_status in (
                LegalStatus.PERMITTED, LegalStatus.PROHIBITED,
                LegalStatus.AUTHORIZATION_REQUIRED))
        if boundary_clean:
            protocol_failures.append(case["case_id"])
        results.append({
            "case_id": case["case_id"], "stratum": case["stratum"],
            "expected_class": case["expected_class"],
            "actual_class": actual, "match": match,
            "legal_status": res.legal_status.value,
            "reason_codes": res.reason_codes,
            "boundary_flagged": boundary_flagged,
            "scopes": [h["scope_id"] for h in res.applicable_scope],
        })

    by_stratum: dict[str, dict[str, int]] = {}
    by_class: dict[str, dict[str, int]] = {}
    for r in results:
        s = by_stratum.setdefault(r["stratum"], {"n": 0, "ok": 0})
        s["n"] += 1
        s["ok"] += int(r["match"])
        c = by_class.setdefault(r["expected_class"], {"n": 0, "ok": 0})
        c["n"] += 1
        c["ok"] += int(r["match"])

    report = {
        "schema": "alraso-m8-holdout-results-v1",
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commitment_sha256": digest,
        "manifest_sha256": manifest_sha,
        "resolver_version": RESOLVER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "knowledge_date": args.knowledge_date,
        "corpora": args.corpus,
        "case_count": len(results),
        "matched": sum(1 for r in results if r["match"]),
        "by_stratum": by_stratum,
        "by_class": by_class,
        "protocol_failures": protocol_failures,
        "cases": results,
    }

    print(f"M8-F holdout: {report['matched']}/{len(results)} cases matched "
          f"expected class")
    for stratum in sorted(by_stratum):
        s = by_stratum[stratum]
        print(f"  {stratum:32s} {s['ok']}/{s['n']}")
    if protocol_failures:
        print(f"  PROTOCOL FAILURES (clean determination on boundary): "
              f"{protocol_failures}")
    if args.out:
        Path(args.out).write_text(
            json.dumps(report, indent=2, sort_keys=True,
                       ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"report written to: {args.out}")
    print("NOTE: mismatches are EVIDENCE. Do not tune rules or geometry "
          "against this holdout (M8-HOLDOUT.md §5).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
