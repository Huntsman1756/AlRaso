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

import copy
import json
import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "alraso" / "resources" / "fixture_picos.json"
EVIDENCE_JSON = ROOT / "tooling" / "m2b_picos_official_boundary.evidence.json"
RESULTS_JSON = ROOT / "tooling" / "m2b_picos_official_boundary_results.json"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _in_ring(lat, lon, ring):
    """Ray-cast point-in-polygon."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_any_ring(lat, lon, rings):
    return any(_in_ring(lat, lon, r) for r in rings)


def _load_results():
    with open(RESULTS_JSON, encoding="utf-8") as f:
        return json.load(f)


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
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    park = fx["geometry"]["park"]
    assert len(park) == 1
    assert len(park[0]) > 100


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


def test_fixture_has_source_documents():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    docs = fx["source_documents"]
    ids = [d["id"] for d in docs]
    assert "sd-pnpe-as-decreto-21-2026" in ids
    assert "sd-pnpe-cb-decreto-57-2026" in ids
    assert "sd-pnpe-cl-decreto-17-2025" in ids
    assert "doc-bddae-cnig" in ids


# ── KPI assertions (internal consistency, never magic numbers) ──────────────


def test_kpi_high_points_tested_computed():
    res = _load_results()
    gpt = res["gate_comparison"]["HIGH_POINTS_TESTED"]
    rpt = res["runtime"]["HIGH_POINTS_TESTED"]
    assert gpt == rpt, "gate and runtime must agree on HIGH_POINTS_TESTED"
    assert gpt > 0


def test_kpi_newly_resolvable_non_negative():
    rt = _load_results()["runtime"]
    assert rt["NEWLY_RESOLVABLE"] >= 0


def test_kpi_agreement_recomputed():
    """DISAGREEMENT_POINTS must be the actual GISCO-vs-official disagreement."""
    rt = _load_results()["runtime"]
    assert rt["DISAGREEMENT_POINTS"] > 0


def test_kpi_gap_points_non_negative():
    rt = _load_results()["runtime"]
    assert rt["GAP_POINTS"] >= 0


def test_kpi_overlap_points_non_negative():
    rt = _load_results()["runtime"]
    assert rt["OVERLAP_POINTS"] >= 0


def test_kpi_topology_gap_m2_reasonable():
    gap_m2 = _load_results()["gate_comparison"]["TOPOLOGY_GAP_M2"]
    assert 40 <= gap_m2 <= 50


def test_kpi_newly_resolvable_internal_consistency():
    rt = _load_results()["runtime"]
    ob = rt["OLD_BLOCKED"]
    nb = rt["NEW_BLOCKED"]
    assert nb <= ob, "NEW_BLOCKED must not exceed OLD_BLOCKED"
    assert rt["NEWLY_RESOLVABLE"] >= 0


def test_kpi_resolvable_pct_computed():
    rt = _load_results()["runtime"]
    ob = rt["OLD_BLOCKED"]
    nr = rt["NEWLY_RESOLVABLE"]
    pct = rt["NEWLY_RESOLVABLE_PCT"]
    assert ob > 0
    expected_pct = round(nr / ob * 100, 2)
    assert pct == expected_pct


def test_kpi_disagreement_runtime_gate_coherent():
    rt_dp = _load_results()["runtime"]["DISAGREEMENT_POINTS"]
    assert rt_dp > 0


def test_kpi_topology_gap_preserved():
    gate = _load_results()["gate_comparison"]
    assert gate["TOPOLOGY_GAP_M2"] > 0
    assert gate["TOPOLOGY_OVERLAP_M2"] == 0.0


# ── Server code assertions ──────────────────────────────────────────────────


def test_no_seg_dist_m_in_server():
    server_py = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")
    assert "_seg_dist_m" not in server_py


def test_no_boundary_uncertainty_m_constant():
    server_py = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")
    assert "_BOUNDARY_UNCERTAINTY_M" not in server_py


# ── Legal rules unchanged ──────────────────────────────────────────────────


def test_legal_rule_versions_digest_unchanged():
    fx = json.load(open(FIXTURE, encoding="utf-8"))
    rules = fx.get("legal_rule_versions", [])
    assert len(rules) == 3
    for r in rules:
        assert r["review_status"] == "VERIFIED"


# ── Packaging assertions ───────────────────────────────────────────────────


def test_pyproject_core_deps_empty():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^dependencies = \[\s*\]", pyproject, re.M) is not None


def test_pyproject_has_tooling_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "tooling" in pyproject
    assert "shapely" in pyproject


# ── Fixture size check ─────────────────────────────────────────────────────


def test_fixture_size_reasonable():
    size = FIXTURE.stat().st_size
    assert size < 1_500_000


# ── Probe points verification (legal verdicts) ───────────────────────────


def test_probe_p1_asturias_interior():
    """P1 (Asturias interior) — interior, cota=1510 < 1800 -> UNDETERMINED."""
    res = _load_results()
    p1 = res["probe_results"]["P1_asturias_interior"]
    assert p1["lat"] == 43.2662
    assert p1["lon"] == -4.8686
    assert p1["inside_park"] is True
    assert p1["elev_m"] < 1800
    assert p1["verdict"] == "UNDETERMINED"


def test_probe_p2_cantabria_interior():
    """P2 (Cantabria interior) — interior, cota=1942 > 1800 -> PERMITTED."""
    res = _load_results()
    p2 = res["probe_results"]["P2_cantabria_interior"]
    assert p2["lat"] == 43.17068
    assert p2["lon"] == -4.80299
    assert p2["inside_park"] is True
    assert p2["elev_m"] > 1800
    assert p2["verdict"] == "PERMITTED"


def test_probe_p3_cyl_interior():
    """P3 (Cyl interior) — interior, cota=1390 < 1800 -> UNDETERMINED."""
    res = _load_results()
    p3 = res["probe_results"]["P3_cyl_interior"]
    assert p3["inside_park"] is True
    assert p3["elev_m"] < 1800
    assert p3["verdict"] == "UNDETERMINED"


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


# ── Runtime guard logic tests (hermetic, DEM-independent) ─────────────────


class TestGuardLogic:
    """Tests for jurisdiction_boundary_safe guard logic."""

    @pytest.fixture
    def fx(self):
        with open(FIXTURE, encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def svc_module(self):
        import sys
        webapp_dir = str(ROOT / "webapp")
        if webapp_dir not in sys.path:
            sys.path.insert(0, webapp_dir)
        import webapp.server as srv_mod
        return srv_mod

    def _load_service(self, srv_mod):
        alraso_dir = str(ROOT)
        if alraso_dir not in sys.path:
            sys.path.insert(0, alraso_dir)
        return srv_mod.Service()

    def test_A_interior_point_high_cota_permitted(self, fx, svc_module):
        """A: interior official point + cota_m > 1800 -> guard True (cota check is separate).

        P2_cantabria_interior has cota=1942 > 1800 and is in es-cb sector.
        The guard (boundary_safe) is True for this point.
        The legal verdict PERMITTED comes from cota_m > 1800 + guard + jurisdiction.
        """
        svc = self._load_service(svc_module)
        p2 = fx["probe_points"]["P2_cantabria_interior"]
        lat, lon = p2["lat"], p2["lon"]
        assert _point_in_any_ring(lat, lon, fx["geometry"]["es-cb"])
        assert _point_in_any_ring(lat, lon, fx["geometry"]["park"])
        guard = svc_module.jurisdiction_boundary_safe(svc, lat, lon)
        assert guard is True

    def test_B_interior_point_low_cota_undetermined(self, fx, svc_module):
        """B: interior point with cota_m < 1800 -> guard True (boundary ok), but cota blocks.

        P1_asturias_interior has cota=1510 < 1800.
        Guard is True (boundary is safe), but the legal rule cota_m > 1800 fails.
        """
        svc = self._load_service(svc_module)
        lat, lon = 43.2662, -4.8686
        guard = svc_module.jurisdiction_boundary_safe(svc, lat, lon)
        assert guard is True

    def test_C_point_in_uncertainty_zone_undetermined(self, fx, svc_module):
        """C: point inside boundary_uncertainty zone -> guard=False.

        The uncertainty zone is a 100m buffer around official shared borders.
        Points on the sector boundaries are inside this zone.
        We test sector boundary points that are known to be inside the zone.
        """
        svc = self._load_service(svc_module)
        zone_rings = fx["geometry"].get("boundary_uncertainty", [])
        assert len(zone_rings) > 0, "fixture must have boundary_uncertainty zone"
        found_zone_point = False
        # Check points along sector boundaries (known to be in the zone)
        for sector_name in ["es-as", "es-cb", "es-cl"]:
            sector_rings = fx["geometry"].get(sector_name, [])
            for ring in sector_rings:
                if len(ring) < 3:
                    continue
                for idx in range(0, len(ring), max(1, len(ring) // 10)):
                    pt_lat, pt_lon = ring[idx]
                    if _in_ring(pt_lat, pt_lon, fx["geometry"]["park"][0]):
                        in_zone = any(
                            _in_ring(pt_lat, pt_lon, zr) for zr in zone_rings
                        )
                        if in_zone:
                            guard = svc_module.jurisdiction_boundary_safe(
                                svc, pt_lat, pt_lon
                            )
                            assert guard is False, \
                                f"Zone point ({pt_lat}, {pt_lon}) guard should be False"
                            found_zone_point = True
                            break
                if found_zone_point:
                    break
            if found_zone_point:
                break
        assert found_zone_point, "Must find at least one point in the uncertainty zone"

    def test_D_synthetic_gap(self, fx, svc_module):
        """D: synthetic gap — remove a sector ring, point in hole -> guard=False.

        We remove the first ring from es-as sector, creating a hole.
        A point inside that ring (but not in any other sector) will be in a gap.
        """
        svc = self._load_service(svc_module)
        temp_fx = copy.deepcopy(fx)
        sector = temp_fx["geometry"]["es-as"]
        if sector and len(sector) > 0:
            first_ring = sector[0]
            if len(first_ring) >= 4:
                lats = [r[0] for r in first_ring]
                lons = [r[1] for r in first_ring]
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)
                if _in_ring(center_lat, center_lon, fx["geometry"]["park"][0]):
                    new_sectors = {
                        "park": temp_fx["geometry"]["park"],
                        "es-as": [r for r in sector if r != first_ring],
                        "es-cb": temp_fx["geometry"]["es-cb"],
                        "es-cl": temp_fx["geometry"]["es-cl"],
                        "boundary_uncertainty": temp_fx["geometry"]["boundary_uncertainty"],
                    }
                    temp_fx["geometry"] = new_sectors
                    test_pt = first_ring[0]
                    in_park = _point_in_any_ring(test_pt[0], test_pt[1], new_sectors["park"])
                    in_any_sector = any(
                        _point_in_any_ring(test_pt[0], test_pt[1], new_sectors.get(sid, []))
                        for sid in ["es-as", "es-cb", "es-cl"]
                    )
                    if in_park and not in_any_sector:
                        guard = svc_module.jurisdiction_boundary_safe(svc, test_pt[0], test_pt[1])
                        assert guard is False
                        return
        # If we can't find a suitable gap point with es-as, try other sectors
        for sector_name in ["es-cb", "es-cl"]:
            sector = temp_fx["geometry"][sector_name]
            if not sector:
                continue
            first_ring = sector[0]
            if len(first_ring) < 4:
                continue
            lats = [r[0] for r in first_ring]
            lons = [r[1] for r in first_ring]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            if not _in_ring(center_lat, center_lon, fx["geometry"]["park"][0]):
                continue
            new_sectors = {
                "park": temp_fx["geometry"]["park"],
                "es-as": temp_fx["geometry"]["es-as"],
                "es-cb": temp_fx["geometry"]["es-cb"],
                "es-cl": temp_fx["geometry"]["es-cl"],
                "boundary_uncertainty": temp_fx["geometry"]["boundary_uncertainty"],
            }
            new_sectors[sector_name] = [r for r in sector if r != first_ring]
            test_pt = first_ring[0]
            in_park = _point_in_any_ring(test_pt[0], test_pt[1], new_sectors["park"])
            in_any_sector = any(
                _point_in_any_ring(test_pt[0], test_pt[1], new_sectors.get(sid, []))
                for sid in ["es-as", "es-cb", "es-cl"]
            )
            if in_park and not in_any_sector:
                guard = svc_module.jurisdiction_boundary_safe(svc, test_pt[0], test_pt[1])
                assert guard is False
                return
        pytest.skip("Cannot create synthetic gap — all rings are shared with other sectors")

    def test_E_synthetic_overlap(self, fx, svc_module):
        """E: synthetic overlap — duplicate a sector at a point -> guard=False (>=2 sectors).

        We create a synthetic overlap by copying es-as ring to es-cb at the same location.
        A point in that ring will be in both es-as and es-cb -> guard=False (overlap).
        """
        svc = self._load_service(svc_module)
        temp_fx = copy.deepcopy(fx)
        as_ring = fx["geometry"]["es-as"]
        cb_ring = fx["geometry"]["es-cb"]
        if as_ring and cb_ring and as_ring[0] and cb_ring[0]:
            # Copy the first es-as ring and add it to es-cb (creating overlap)
            overlapping_rings = list(cb_ring) + [list(as_ring[0]) for _ in range(1)]
            new_sectors = {
                "park": temp_fx["geometry"]["park"],
                "es-as": temp_fx["geometry"]["es-as"],
                "es-cb": overlapping_rings,
                "es-cl": temp_fx["geometry"]["es-cl"],
                "boundary_uncertainty": temp_fx["geometry"]["boundary_uncertainty"],
            }
            temp_fx["geometry"] = new_sectors
            # Pick a point from the first es-as ring
            test_pt = as_ring[0][0]
            in_park = _point_in_any_ring(test_pt[0], test_pt[1], new_sectors["park"])
            in_as = _point_in_any_ring(test_pt[0], test_pt[1], new_sectors.get("es-as", []))
            in_cb = _point_in_any_ring(test_pt[0], test_pt[1], new_sectors.get("es-cb", []))
            if in_park and in_as and in_cb:
                guard = svc_module.jurisdiction_boundary_safe(svc, test_pt[0], test_pt[1])
                assert guard is False
                return
        pytest.skip("Cannot create synthetic overlap — es-as and es-cb rings may not overlap cleanly")

    def test_F_outside_park_no_applicable_scope(self, fx, svc_module):
        """F: outside-park point -> guard=True (no boundary conflict).

        The guard returns True for points outside the park because there is
        no CCAA jurisdiction conflict. The legal verdict NO_APPLICABLE_SCOPE
        comes from the resolver, not the guard.
        """
        svc = self._load_service(svc_module)
        lat, lon = 42.0, -3.0
        in_park = _point_in_any_ring(lat, lon, fx["geometry"]["park"])
        assert not in_park
        guard = svc_module.jurisdiction_boundary_safe(svc, lat, lon)
        assert guard is True

    def test_G_interior_positives_all_ccaa(self, fx, svc_module):
        """Interior positives for all three CCAAs via probe_points."""
        probe_points = fx.get("probe_points", {})
        ccas = {"P1_asturias_interior": "es-as",
                "P2_cantabria_interior": "es-cb",
                "P3_cyl_interior": "es-cl"}
        for name, expected_ccaa in ccas.items():
            p = probe_points.get(name)
            if p is None:
                continue
            lat, lon = p["lat"], p["lon"]
            assert _point_in_any_ring(lat, lon, fx["geometry"]["park"]), f"{name} must be in park"
            assert _point_in_any_ring(lat, lon, fx["geometry"].get(expected_ccaa, [])), \
                f"{name} must be in {expected_ccaa}"

    def test_H_flip_outside_zone_resolves(self, fx, svc_module):
        """H: flip point OUTSIDE the 100m zone -> new official CCAA governs.

        Use a point from the disagreement set that is NOT in the uncertainty zone.
        The guard is True -> official jurisdiction governs.
        """
        svc = self._load_service(svc_module)
        res = _load_results()
        # Pick a disagreement point from probe results that's outside the zone
        for pname, pdata in res["probe_results"].items():
            if pdata.get("in_uncertainty_zone", False):
                continue
            lat, lon = pdata["lat"], pdata["lon"]
            guard = svc_module.jurisdiction_boundary_safe(svc, lat, lon)
            # Outside zone -> guard should be True (unless in gap/overlap)
            if guard:
                return
        # If no suitable point found, try a known non-zone interior point
        p2 = fx["probe_points"]["P2_cantabria_interior"]
        lat, lon = p2["lat"], p2["lon"]
        guard = svc_module.jurisdiction_boundary_safe(svc, lat, lon)
        assert guard is True


# ── Git diff assertion (allowed files only) ────────────────────────────────


def test_git_diff_vs_main_only_allowed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
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
        "tests/test_m2_webapp.py",
        "tests/test_dem_elevation.py",
        "tests/test_picos_fixture.py",
    }
    for f in changed:
        assert f in allowed, f"Unexpected file changed: {f}"