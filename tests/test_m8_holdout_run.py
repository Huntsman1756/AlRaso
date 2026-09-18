"""M8-F holdout runner tests (tooling/m8_holdout_run.py).

Contract: the runner recomputes the canonical commitment over the secret
case list and ABORTS on mismatch (non-substitution), resolves each case
through the frozen point resolver and reports per-stratum/per-class
outcomes. It never mutates rules, geometry or expected answers.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEAL = ROOT / "tooling" / "m8_holdout_seal.py"
RUN = ROOT / "tooling" / "m8_holdout_run.py"
MANIFEST = ROOT / "discovery" / "evidence" / "m8-madrid-layers.json"

STRATA = [
    "pn_guadarrama_interior", "vivac_zone_anexo3", "zpp",
    "hole_or_exclusion", "boundary", "pr_cuenca_alta_manzanares",
    "pr_curso_medio_guadarrama", "pr_sureste", "territorio_general",
    "temporal_variant", "expected_undetermined", "expected_unknown",
]

# Real-geometry reference points (see test_m8_geojson_provider.py)
ZABALA = (40.837697, -3.958714)     # inside vivac Anexo III + PN-CM
ZPP_PT = (40.842235, -3.880597)     # inside ZPP only
HOLE_PT = (40.914796, -3.854548)    # inside a ZPP hole -> no scope
FAR_PT = (41.2, -4.5)               # outside all coverage -> UNKNOWN

_POINTS = {
    "pn_guadarrama_interior": ZABALA, "vivac_zone_anexo3": ZABALA,
    "zpp": ZPP_PT, "hole_or_exclusion": HOLE_PT, "boundary": ZABALA,
    "pr_cuenca_alta_manzanares": ZABALA,
    "pr_curso_medio_guadarrama": ZPP_PT, "pr_sureste": ZABALA,
    "territorio_general": FAR_PT, "temporal_variant": ZABALA,
    "expected_undetermined": ZPP_PT, "expected_unknown": FAR_PT,
}

_EXPECTED = {s: "UNDETERMINED" for s in STRATA}
_EXPECTED["territorio_general"] = "UNKNOWN"
_EXPECTED["expected_unknown"] = "UNKNOWN"
_EXPECTED["hole_or_exclusion"] = "UNKNOWN"


def _cases() -> list[dict]:
    return [{"case_id": f"M8F-{i + 1:02d}",
             "lat": _POINTS[s][0], "lon": _POINTS[s][1],
             "date": "2026-10-03", "activity": "VIVAC_AL_RASO",
             "stratum": s, "expected_class": _EXPECTED[s]}
            for i, s in enumerate(STRATA)]


def _seal(tmp_path: Path, cases) -> Path:
    secret = tmp_path / "cases.json"
    secret.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    commit = tmp_path / "commit.json"
    r = subprocess.run(
        [sys.executable, str(SEAL), "--input", str(secret),
         "--custodian", "Test Custodian", "--output", str(commit)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return secret, commit


def _run(tmp_path: Path, secret: Path, commit: Path,
         *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUN), "--cases", str(secret),
         "--commitment", str(commit), "--manifest", str(MANIFEST),
         "--knowledge-date", "2026-10-01",
         "--out", str(tmp_path / "results.json"), *extra],
        capture_output=True, text=True, cwd=ROOT)


def test_run_executes_and_reports(tmp_path):
    secret, commit = _seal(tmp_path, _cases())
    r = _run(tmp_path, secret, commit)
    assert r.returncode == 0, r.stderr
    rep = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert rep["case_count"] == len(STRATA)
    by_id = {c["case_id"]: c for c in rep["cases"]}
    # class mapping: no-coverage point -> UNKNOWN, in-coverage -> UNDETERMINED
    assert by_id["M8F-12"]["actual_class"] == "UNKNOWN"
    assert by_id["M8F-03"]["actual_class"] == "UNDETERMINED"
    assert by_id["M8F-03"]["scopes"] == ["ss-pnsg-zpp-cm"]
    assert rep["commitment_sha256"] == \
        json.loads(commit.read_text("utf-8"))["holdout_sha256"]
    assert rep["resolver_version"]
    assert set(rep["by_stratum"]) == set(STRATA)


def test_commitment_mismatch_aborts(tmp_path):
    cases = _cases()
    secret, commit = _seal(tmp_path, cases)
    cases[0]["lat"] += 0.01  # tamper AFTER sealing
    secret.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    r = _run(tmp_path, secret, commit)
    assert r.returncode == 1
    assert "PROTOCOL VIOLATION" in r.stdout


def test_bad_commitment_schema_aborts(tmp_path):
    secret, commit = _seal(tmp_path, _cases())
    commit.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
    r = _run(tmp_path, secret, commit)
    assert r.returncode == 1
