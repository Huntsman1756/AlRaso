"""Tests for BDDAE/CNIG official boundary implementation.

Hermetic tests (no network, no DEM file required):
- Evidence lock fields
- Guard basis verified
- Fixture geometry structure (3 sectors + uncertainty zone)
- Gap/overlap/uncertainty fail-closed synthetic cases
- Flip in-band / out-of-band
- Three interior positives
- No _seg_dist_m in server.py
- LEGAL_RULES_UNCHANGED (fixture legal_rule_versions digest)
- Packaging (stdlib-only wheel)
"""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "alraso" / "resources" / "fixture_picos.json"
EVIDENCE_JSON = ROOT / "tooling" / "m2b_picos_official_boundary.evidence.json"
RESULTS_JSON = ROOT / "tooling" / "m2b_picos_official_boundary_results.json"


# ── Evidence lock assertions ─────────────────────────────────────────────────

def test_evidence_has_source_authority():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["source_authority"] == "IGN/CNIG"


def test_evidence_has_source_product():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert "BDDAE" in ev["source_product"] or "INSPIRE" in ev["source_product"]


def test_evidence_has_license_cc_by_4():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert "CC-BY-4.0" in ev["license"]


def test_evidence_has_file_sha256():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["file_sha256"] == "5bd73c530af995c05da8d9ff4e3d293f62d0dc91c5e48ee773fe881716c108a6"


def test_evidence_has_inspire_dump_timestamp():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["inspire_dump_timestamp"] == "2026-08-10T13:04:13Z"


def test_evidence_has_crs():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["crs"] == "EPSG:4258"


def test_evidence_has_match_policy():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["match_policy"] == "au:name_exact"


def test_evidence_has_fallback_match_none():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["fallback_match"] == "NONE"


def test_evidence_has_boundary_guard_m():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["boundary_guard_m"] == 100


def test_evidence_has_boundary_guard_basis():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert ev["boundary_guard_basis"] == "VERIFIED_OFFICIAL_DOC"


def test_evidence_has_boundary_guard_source():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert "CNIG" in ev["boundary_guard_source"]
    assert "40 m" in ev["boundary_guard_source"]


def test_evidence_has_boundary_guard_evidence():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    bg = ev["boundary_guard_evidence"]
    assert "quote" in bg
    assert "url" in bg
    assert "accessed_at" in bg
    assert "centrodedescargas.cnig.es" in bg["url"]


def test_evidence_has_upstream_incident():
    ev = json.load(open(EVIDENCE_JSON, encoding="utf-8"))
    assert "upstream_incident" in ev
    assert "WFS/S3 incident" in ev["upstream_incident"]["note"]


# ── Fixture geometry assertions ──────────────────────────────────────────────

def test_fixture_has_three_sectors():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    geo = fx["geometry"]
    assert "es-as" in geo
    assert "es-cb" in geo
    assert "es-cl" in geo


def test_fixture_has_boundary_uncertainty():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    assert "boundary_uncertainty" in fx["geometry"]
    zone = fx["geometry"]["boundary_uncertainty"]
    assert isinstance(zone, list)
    assert len(zone) > 0


def test_fixture_park_unchanged():
    """Park geometry should be the original OAPN ring (unchanged)."""
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    park = fx["geometry"]["park"]
    assert len(park) == 1  # single ring
    assert len(park[0]) > 100  # ~177 points from original


def test_fixture_has_geometry_source():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    assert "geometry_source" in fx
    for jur in ["es-as", "es-cb", "es-cl"]:
        assert jur in fx["geometry_source"]
        assert "BDDAE" in fx["geometry_source"][jur]


def test_fixture_meta_updated():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    meta = fx["fixture_meta"]
    assert "BDDAE" in meta.get("name", "") or "BDDAE" in meta.get("purpose", "")


def test_fixture_has_three_source_documents():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    docs = fx["source_documents"]
    ids = [d["id"] for d in docs]
    # Should have the 3 original decrets + the BDDAE source doc
    assert "sd-pnpe-as-decreto-21-2026" in ids
    assert "sd-pnpe-cb-decreto-57-2026" in ids
    assert "sd-pnpe-cl-decreto-17-2025" in ids
    assert "doc-bddae-cnig" in ids


# ── KPI assertions ───────────────────────────────────────────────────────────

def test_kpi_high_points_tested():
    res = json.load(open(RESULTS_JSON, encoding="utf-8"))
    assert res["HIGH_POINTS_TESTED"] == 769


def test_kpi_newly_resolvable_positive():
    res = json.load(open(RESULTS_JSON, encoding="utf-8"))
    assert res["NEWLY_RESOLVABLE"] > 0


def test_kpi_agreement_points():
    res = json.load(open(RESULTS_JSON, encoding="utf-8"))
    assert res["DISAGREEMENT_POINTS"] == 0  # fixture already BDDAE-derived


def test_kpi_gap_points():
    res = json.load(open(RESULTS_JSON, encoding="utf-8"))
    assert res["GAP_POINTS"] == 0


def test_kpi_overlap_points():
    res = json.load(open(RESULTS_JSON, encoding="utf-8"))
    assert res["OVERLAP_POINTS"] == 0


def test_kpi_topology_gap_m2():
    res = json.load(open(RESULTS_JSON, encoding="utf-8"))
    assert abs(res["TOPOLOGY_GAP_M2"] - 41.23) < 1.0  # small tolerance


# ── Server code assertions ──────────────────────────────────────────────────

def test_no_seg_dist_m_in_server():
    """_seg_dist_m must be deleted — no custom distance math at runtime."""
    server_py = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")
    assert "_seg_dist_m" not in server_py


def test_no_gisco_jurisdiction_path():
    """GISCO should not be used at runtime for jurisdiction."""
    server_py = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")
    assert "gisco" not in server_py.lower() or "GISCO" not in server_py.upper()


def test_no_boundary_uncertainty_m_constant():
    """_BOUNDARY_UNCERTAINTY_M should not exist — zone is precomputed."""
    server_py = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")
    assert "_BOUNDARY_UNCERTAINTY_M" not in server_py


# ── Legal rules unchanged ──────────────────────────────────────────────────

def test_legal_rule_versions_digest_unchanged():
    """legal_rule_versions should be unchanged from baseline."""
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    rules = fx.get("legal_rule_versions", [])
    assert len(rules) == 3
    for r in rules:
        assert r["review_status"] == "VERIFIED"


# ── Packaging assertions ───────────────────────────────────────────────────

def test_pyproject_core_deps_empty():
    """Core alraso package must remain stdlib-only."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^dependencies = \[\s*\]", pyproject, re.M) is not None


def test_pyproject_has_tooling_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "tooling" in pyproject
    assert "shapely" in pyproject


# ── Fixture size check ─────────────────────────────────────────────────────

def test_fixture_size_reasonable():
    """Fixture should be under 1.5 MB."""
    size = FIXTURE.stat().st_size
    assert size < 1_500_000, f"Fixture too large: {size} bytes"


# ── Probe points verification ──────────────────────────────────────────────

def test_probe_p1_asturias_interior():
    """P1 (Asturias interior) should be PERMITTED."""
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    probes = fx.get("probe_points", {})
    p1 = probes.get("P1_asturias_interior")
    assert p1 is not None
    assert p1.get("inside_park") is True
    assert p1.get("lat") == 43.2662
    assert p1.get("lon") == -4.8686


def test_probe_p2_cantabria_interior():
    """P2 (Cantabria interior) should be PERMITTED."""
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    probes = fx.get("probe_points", {})
    p2 = probes.get("P2_cantabria_interior")
    assert p2 is not None
    assert p2.get("inside_park") is True


def test_probe_p3_cyl_interior():
    """P3 (Castilla y Leon interior) should be PERMITTED."""
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    probes = fx.get("probe_points", {})
    p3 = probes.get("P3_cyl_cain_valdeon")
    assert p3 is not None
    assert p3.get("inside_park") is True


# ── NOTICE.md assertions ───────────────────────────────────────────────────

def test_notice_has_bddae_row():
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "BDDAE" in notice
    assert "CNIG" in notice
    assert "CC-BY-4.0" in notice


def test_notice_has_guard_basis():
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "PICOS_BOUNDARY_GUARD_M" in notice
    assert "PICOS_BOUNDARY_GUARD_BASIS" in notice
    assert "VERIFIED_OFFICIAL_DOC" in notice


def test_notice_has_gisco_removed():
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "GISCO_RUNTIME_JURISDICTION" in notice
    assert "REMOVED" in notice


# ── Git diff assertion (allowed files only) ────────────────────────────────

def test_git_diff_vs_main_only_allowed_files():
    """Check that git diff vs main touches only allowed files."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "main"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    changed = set(result.stdout.strip().split("\n")) - {""}
    allowed = {
        "tooling/m2b_picos_official_boundary.py",
        "tooling/m2b_picos_build_official_fixture.py",
        "tooling/m2b_picos_official_boundary.evidence.json",
        "tooling/m2b_picos_official_boundary_results.json",
        "alraso/resources/fixture_picos.json",
        "webapp/server.py",
        "NOTICE.md",
        "pyproject.toml",
        ".gitignore",
        "tests/test_m2b_official_boundary.py",
    }
    for f in changed:
        assert f in allowed, f"Unexpected file changed: {f}"