"""M7 execution-readiness tooling gates.

Proves that the two human-facing tools behave as the frozen-candidate
protocol requires:

(a) tooling/m7_seal_holdout.py produces a deterministic SHA-256 commitment
    (canonical JSON: dict key ordering must not change the hash) and writes
    the sealed-commitment record the custodian hands back;

(b) tooling/m7_reviewer_bundle.py produces a bundle whose manifest.json
    hashes verify, and the blindness scan FAILS if engine-output material
    is injected into the bundle directory;

(c) docs/validation/m7/main-set-v1.json remains blind: no case carries
    expected*/engine*/resolver* fields.

Hermetic: tmp_path only, stdlib + pytest, no network.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEAL_TOOL = ROOT / "tooling" / "m7_seal_holdout.py"
BUNDLE_TOOL = ROOT / "tooling" / "m7_reviewer_bundle.py"
MAIN_SET = ROOT / "docs" / "validation" / "m7" / "main-set-v1.json"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


# ---------------------------------------------------------- seal holdout --


def _holdout_cases() -> list[dict]:
    return [
        {
            "case_id": f"M7-H{i:02d}",
            "activity": "VIVAC_AL_RASO",
            "activity_date": "2026-09-12",
            "known_facts": {"nights": 1, "elevation_m": 1900 + i},
            "factual_location": f"punto secreto {i}",
        }
        for i in range(1, 5)
    ]


def _reordered(obj):
    """Same semantic content, different key ordering (and reversed list of
    dict key insertion order) — canonical form must be identical."""
    if isinstance(obj, dict):
        return {k: _reordered(obj[k]) for k in reversed(list(obj))}
    if isinstance(obj, list):
        return [_reordered(v) for v in obj]
    return obj


def _seal(tmp_path: Path, cases_obj, name: str) -> tuple[Path, dict]:
    src = tmp_path / f"{name}.json"
    src.write_text(
        json.dumps(cases_obj, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    out = tmp_path / f"{name}-commitment.json"
    result = _run(
        SEAL_TOOL,
        "--input",
        str(src),
        "--custodian",
        "Custodia Neutral <custodia@example.org>",
        "--output",
        str(out),
        "--sealed-at",
        "2026-09-20T00:00:00Z",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return out, json.loads(out.read_text(encoding="utf-8"))


def test_seal_holdout_deterministic_under_key_reordering(tmp_path):
    _, rec_a = _seal(tmp_path, _holdout_cases(), "a")
    _, rec_b = _seal(tmp_path, _reordered(_holdout_cases()), "b")
    assert rec_a["holdout_sha256"] == rec_b["holdout_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", rec_a["holdout_sha256"])


def test_seal_holdout_sha_matches_canonical_form(tmp_path):
    cases = _holdout_cases()
    _, rec = _seal(tmp_path, cases, "c")
    canonical = json.dumps(
        cases, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    assert rec["holdout_sha256"] == hashlib.sha256(canonical).hexdigest()


def test_seal_holdout_writes_commitment_record(tmp_path):
    out, rec = _seal(tmp_path, {"cases": _holdout_cases()}, "wrapped")
    assert out.is_file()
    assert rec["schema"] == "alraso-m7-holdout-commitment-v1"
    assert rec["custodian"] == "Custodia Neutral <custodia@example.org>"
    assert rec["sealed_at"] == "2026-09-20T00:00:00Z"
    assert rec["case_ids"] == [f"M7-H{i:02d}" for i in range(1, 5)]
    # the record must not leak case contents
    blob = out.read_text(encoding="utf-8")
    assert "punto secreto" not in blob


def test_seal_holdout_rejects_wrong_count(tmp_path):
    src = tmp_path / "three.json"
    src.write_text(json.dumps(_holdout_cases()[:3]), encoding="utf-8")
    result = _run(
        SEAL_TOOL,
        "--input",
        str(src),
        "--custodian",
        "X",
        "--output",
        str(tmp_path / "o.json"),
    )
    assert result.returncode != 0
    assert "exactly 4" in (result.stderr + result.stdout)


def test_seal_holdout_rejects_missing_case_id(tmp_path):
    cases = _holdout_cases()
    del cases[2]["case_id"]
    src = tmp_path / "noid.json"
    src.write_text(json.dumps(cases), encoding="utf-8")
    result = _run(
        SEAL_TOOL,
        "--input",
        str(src),
        "--custodian",
        "X",
        "--output",
        str(tmp_path / "o.json"),
    )
    assert result.returncode != 0
    assert "case_id" in (result.stderr + result.stdout)


# ------------------------------------------------------- reviewer bundle --


def _build(tmp_path: Path) -> Path:
    out_dir = tmp_path / "bundle"
    result = _run(BUNDLE_TOOL, "build", "--out-dir", str(out_dir))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "BLINDNESS_SCAN=PASS" in result.stdout
    return out_dir


def test_bundle_builds_and_manifest_hashes_verify(tmp_path):
    bundle = _build(tmp_path)
    manifest_path = bundle / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected = {
        "main-set-v1.json",
        "primary-sources.md",
        "reviewer-instructions-v1.md",
        "reviewer-attestation-public.template.md",
    }
    listed = {e["path"] for e in manifest["files"]}
    assert listed == expected
    assert "manifest.json" not in listed

    for entry in manifest["files"]:
        blob = (bundle / entry["path"]).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == entry["sha256"]
        assert len(blob) == entry["bytes"]

    # verify subcommand agrees on a clean bundle
    result = _run(BUNDLE_TOOL, "verify", "--dir", str(bundle))
    assert result.returncode == 0, result.stdout
    assert "BUNDLE_VERIFY=PASS" in result.stdout


def test_bundle_cases_are_neutral_entries_only(tmp_path):
    bundle = _build(tmp_path)
    doc = json.loads((bundle / "main-set-v1.json").read_text(encoding="utf-8"))
    assert len(doc["cases"]) == 24
    # internal audit metadata must not be shipped to the reviewer
    for key in ("status", "pre_registered_at", "blindness"):
        assert key not in doc
    assert doc["cases"][0]["case_id"] == "M7-R0-C01"


def test_bundle_blindness_fails_on_injected_engine_output(tmp_path):
    bundle = _build(tmp_path)
    leak = bundle / "engine-results.json"
    leak.write_text(
        json.dumps({"M7-R0-C01": {"expected_engine_result": "PERMITTED"}}),
        encoding="utf-8",
    )
    result = _run(BUNDLE_TOOL, "verify", "--dir", str(bundle))
    assert result.returncode != 0
    assert "BLINDNESS_SCAN=FAIL" in result.stdout
    assert "expected_engine_result" in result.stdout


def test_bundle_blindness_fails_on_injected_fixture_reference(tmp_path):
    bundle = _build(tmp_path)
    (bundle / "notes.md").write_text(
        "ver alraso/resources/fixture_picos.json para las reglas\n",
        encoding="utf-8",
    )
    result = _run(BUNDLE_TOOL, "verify", "--dir", str(bundle))
    assert result.returncode != 0
    assert "BLINDNESS_SCAN=FAIL" in result.stdout


def test_bundle_verify_fails_on_tampered_file(tmp_path):
    bundle = _build(tmp_path)
    target = bundle / "reviewer-instructions-v1.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nanadido\n", encoding="utf-8"
    )
    result = _run(BUNDLE_TOOL, "verify", "--dir", str(bundle))
    assert result.returncode != 0
    assert "sha256 mismatch" in result.stdout


# ------------------------------------------------------- main set blind --


FORBIDDEN_KEY = re.compile(r"expected|engine|resolver", re.IGNORECASE)


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def test_main_set_has_24_cases_and_no_engine_fields():
    data = json.loads(MAIN_SET.read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) == 24
    assert len({c["case_id"] for c in cases}) == 24
    for case in cases:
        bad = [k for k in _walk_keys(case) if FORBIDDEN_KEY.search(k)]
        assert not bad, f"{case['case_id']} leaks engine fields: {bad}"
        # minimal neutral-entry contract (protocol-v1 section 5)
        for key in (
            "case_id",
            "activity",
            "activity_date",
            "known_facts",
            "primary_source_references",
        ):
            assert key in case, f"{case['case_id']} missing {key}"
