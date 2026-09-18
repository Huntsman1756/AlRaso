"""M8-F holdout sealing tool tests (tooling/m8_holdout_seal.py).

Contract: the tool validates the secret case file, computes a canonical
SHA-256 commitment and writes a public record containing NO case contents
(no coordinates, no expected classes). It never fabricates the seal.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tooling" / "m8_holdout_seal.py"

STRATA = [
    "pn_guadarrama_interior", "vivac_zone_anexo3", "zpp",
    "hole_or_exclusion", "boundary", "pr_cuenca_alta_manzanares",
    "pr_curso_medio_guadarrama", "pr_sureste", "territorio_general",
    "temporal_variant", "expected_undetermined", "expected_unknown",
]


def _case(i: int, stratum: str, **kw) -> dict:
    c = {"case_id": f"M8F-{i:02d}", "lat": 40.6, "lon": -3.9,
         "date": "2026-10-03", "activity": "VIVAC_AL_RASO",
         "stratum": stratum, "expected_class": "UNDETERMINED"}
    c.update(kw)
    return c


def _full_cases() -> list[dict]:
    return [_case(i + 1, s) for i, s in enumerate(STRATA)]


def _run(tmp_path: Path, cases) -> subprocess.CompletedProcess:
    secret = tmp_path / "cases.json"
    secret.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(TOOL), "--input", str(secret),
         "--custodian", "Test Custodian", "--output",
         str(tmp_path / "commit.json")],
        capture_output=True, text=True)


def test_seal_succeeds_and_leaks_no_contents(tmp_path):
    r = _run(tmp_path, _full_cases())
    assert r.returncode == 0, r.stderr
    rec = json.loads((tmp_path / "commit.json").read_text(encoding="utf-8"))
    assert len(rec["holdout_sha256"]) == 64
    assert rec["case_count"] == len(STRATA)
    # No coordinates or expected classes in the public record
    blob = json.dumps(rec)
    assert "40.6" not in blob and "-3.9" not in blob
    assert "expected_class" not in blob and "UNDETERMINED" not in blob.replace(
        '"expected_undetermined"', "")


def test_missing_stratum_fails_closed(tmp_path):
    cases = _full_cases()[:-1]  # drop expected_unknown
    r = _run(tmp_path, cases)
    assert r.returncode == 1
    assert "missing" in r.stderr.lower() or "strata" in r.stderr.lower()


def test_unknown_expected_class_fails(tmp_path):
    cases = _full_cases()
    cases[0]["expected_class"] = "MAYBE"
    r = _run(tmp_path, cases)
    assert r.returncode == 1


def test_out_of_region_coordinate_fails(tmp_path):
    cases = _full_cases()
    cases[0]["lat"] = 36.0  # Andalucía — outside the CAM sanity box
    r = _run(tmp_path, cases)
    assert r.returncode == 1


def test_commitment_is_canonical(tmp_path):
    """Field order in the input must not change the commitment."""
    import hashlib
    cases = _full_cases()
    r = _run(tmp_path, cases)
    rec = json.loads((tmp_path / "commit.json").read_text(encoding="utf-8"))
    canon = json.dumps(cases, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")).encode("utf-8")
    assert rec["holdout_sha256"] == hashlib.sha256(canon).hexdigest()
