"""M10.2-A National Source Atlas — domain set, validation, exit gate.

Boundary (plan M10.2-A §4): this module owns the atlas *contract* — the
canonical 20-domain set, schema validation and the executable exit gate.
It never fetches anything (live attempts live only in
``tooling/m102_atlas_probe.py``) and never produces or mutates legal rules.

``domain_status`` is demonstrated, not declared:

- ``PROVEN`` requires identified surface(s) and at least one probe with
  ``reachability_observed=REACHABLE`` *and* ``fetch_outcome=SUCCESS`` from
  a real runner network, whose recorded ``raw_sha256`` matches the stored
  evidence bytes — the gate re-hashes the files. A REACHABLE probe with a
  non-SUCCESS outcome (CAPTCHA interstitial, HTTP_ERROR, SOFT_404) is
  reachability evidence only, never proof of source content.
- ``BLOCKED_WITH_EVIDENCE`` requires identified official surface(s), a
  non-empty ``status_evidence`` limitation description, and at least one
  probe that constitutes verifiable evidence: either a recorded
  ``raw_sha256`` matching stored bytes, or an ``UNREACHABLE`` observation
  with a transport detail — never a bare declaration.
- ``UNPROBED`` never satisfies the gate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from pipeline.profiles import _check_schema, _validate

SCHEMA_PATH = Path(__file__).parent / "schemas" / "source-atlas.schema.json"

# ATLAS_SCOPE (spec §B): 17 CCAA + Ceuta + Melilla + State, ISO 3166-2 ids
# matching the SourceProfile jurisdiction pattern.
CANONICAL_DOMAINS: tuple[str, ...] = (
    "ES",
    "ES-AN",
    "ES-AR",
    "ES-AS",
    "ES-CB",
    "ES-CE",
    "ES-CL",
    "ES-CM",
    "ES-CN",
    "ES-CT",
    "ES-EX",
    "ES-GA",
    "ES-IB",
    "ES-MC",
    "ES-MD",
    "ES-ML",
    "ES-NC",
    "ES-PV",
    "ES-RI",
    "ES-VC",
)

DOMAIN_STATUSES = frozenset({"PROVEN", "BLOCKED_WITH_EVIDENCE", "UNPROBED"})
_PASSING_STATUSES = frozenset({"PROVEN", "BLOCKED_WITH_EVIDENCE"})


class DomainGateError(ValueError):
    """The atlas document is structurally unusable — explicit failure,
    never a fabricated PASS."""


def load_atlas(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_atlas(data)
    return data


def validate_atlas(data: Mapping[str, Any]) -> None:
    """Validate a parsed atlas document against source-atlas.schema.json."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    _check_schema(schema, "")
    _validate(data, schema, "")


def _verify_probe_evidence(
    probe: Mapping[str, Any], repo_root: Path
) -> str | None:
    """Return a failure detail string, or None when evidence verifies."""
    sha = probe.get("raw_sha256") or ""
    rel = probe.get("evidence_path") or ""
    if not sha:
        return "no raw_sha256 recorded"
    if not rel:
        return "no evidence_path recorded"
    body_path = repo_root / rel
    if not body_path.is_file():
        return f"evidence file missing: {rel}"
    actual = hashlib.sha256(body_path.read_bytes()).hexdigest()
    if actual != sha:
        return f"digest mismatch: recorded {sha[:16]}… actual {actual[:16]}…"
    return None


_SYNTHETIC_RUNNERS = frozenset({"", "unknown", "fixture"})


def _real_runner(probe: Mapping[str, Any]) -> bool:
    """A probe only proves live reachability when it was recorded on a
    real runner network — 'fixture'/'unknown'/absent values are not."""
    return (probe.get("runner_network") or "") not in _SYNTHETIC_RUNNERS


def _verifiable_probe(probe: Mapping[str, Any], repo_root: Path) -> bool:
    """Probe constitutes reproducible evidence: verified stored bytes,
    or an UNREACHABLE observation carrying a transport detail."""
    if probe.get("raw_sha256") and probe.get("evidence_path"):
        return _verify_probe_evidence(probe, repo_root) is None
    return (
        probe.get("reachability_observed") == "UNREACHABLE"
        and bool(probe.get("detail"))
    )


def _check_domain(
    record: Mapping[str, Any], repo_root: Path
) -> tuple[str, str]:
    """One row of the gate table: (status, detail)."""
    domain_id = record["domain_id"]
    status = record["domain_status"]

    if status == "UNPROBED":
        return "FAIL", "UNPROBED never satisfies the exit gate"

    if not record["surfaces"]:
        return "FAIL", f"{status} requires ≥1 identified official surface"

    if status == "BLOCKED_WITH_EVIDENCE":
        if not record["probes"]:
            return "FAIL", "BLOCKED_WITH_EVIDENCE requires ≥1 probe attempt"
        if not record.get("status_evidence"):
            return "FAIL", "BLOCKED_WITH_EVIDENCE requires limitation detail"
        if not any(
            _verifiable_probe(p, repo_root) for p in record["probes"]
        ):
            return "FAIL", (
                "BLOCKED_WITH_EVIDENCE requires ≥1 probe with verifiable "
                "evidence (verified bytes or UNREACHABLE observation)"
            )
        return "PASS", "limitation documented with verified evidence"

    # PROVEN — a REACHABLE response that is not a successful fetch (e.g.
    # HTTP_ERROR, CONTENT_MARKER_MISMATCH on a CAPTCHA interstitial,
    # SOFT_404) is reachability evidence, never proof of source content.
    reachable = [
        p
        for p in record["probes"]
        if p["reachability_observed"] == "REACHABLE"
        and p["fetch_outcome"] == "SUCCESS"
        and _real_runner(p)
    ]
    if not reachable:
        return "FAIL", "PROVEN requires ≥1 REACHABLE+SUCCESS probe"
    for probe in reachable:
        problem = _verify_probe_evidence(probe, repo_root)
        if problem is None:
            return "PASS", (
                f"probe {probe['probe_id']}: REACHABLE + verified "
                f"sha256 {probe['raw_sha256'][:16]}…"
            )
    last = _verify_probe_evidence(reachable[-1], repo_root)
    return "FAIL", f"REACHABLE probe evidence does not verify: {last}"


def check_gate(
    atlas: Mapping[str, Any], *, repo_root: str | Path
) -> tuple[bool, list[tuple[str, str, str]]]:
    """Executable M10.2-A exit gate.

    Returns ``(ok, rows)``; each row is ``(domain_id, PASS|FAIL, detail)``.
    Raises DomainGateError on structurally unusable input (schema-invalid,
    wrong domain set) — a malformed atlas is a hard error, not a FAIL row.
    """
    validate_atlas(atlas)
    repo_root = Path(repo_root)

    seen = [d["domain_id"] for d in atlas["domains"]]
    extra = sorted(set(seen) - set(CANONICAL_DOMAINS))
    dupes = sorted({d for d in seen if seen.count(d) > 1})
    if extra or dupes:
        raise DomainGateError(
            f"atlas contains domains outside the canonical 20 — "
            f"extra={extra} duplicates={dupes}"
        )

    rows = []
    for record in atlas["domains"]:
        status, detail = _check_domain(record, repo_root)
        rows.append((record["domain_id"], status, detail))
    for domain_id in sorted(set(CANONICAL_DOMAINS) - set(seen)):
        rows.append((domain_id, "FAIL", "domain absent from atlas"))
    ok = all(r[1] == "PASS" for r in rows)
    return ok, rows
