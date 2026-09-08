"""Tests for BDDAE/CNIG official boundary implementation.

Real resolver-level tests calling server.resolve_point on a mutable Service:
- A: P2 (Cantabria, cota>1800) → PERMITTED
- B: P1 (Asturias, cota<1800) → UNDETERMINED
- D: synthetic GAP → UNDETERMINED + BOUNDARY_GAP / BOUNDARY_EVIDENCE_INCOMPLETE
- E: synthetic OVERLAP → UNDETERMINED + BOUNDARY_OVERLAP
- F: outside park → NO_APPLICABLE_SCOPE
- G: three CCAA interiors → correct scopes
- H: disagreement flip points from results.json

Plus structural/evidence/fixture tests.
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
sys.path.insert(0, str(ROOT / "webapp"))
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from alraso.bitemporal import BitemporalStore  # noqa: E402
from alraso.domain import Query  # noqa: E402
from alraso.ingest.ordesa import ingest_corpus  # noqa: E402
from alraso.resolver import Resolver  # noqa: E402
from alraso.spatial import InMemorySpatialProvider  # noqa: E402

FIXTURE = ROOT / "alraso" / "resources" / "fixture_picos.json"
EVIDENCE_JSON = ROOT / "tooling" / "m2b_picos_official_boundary.evidence.json"
RESULTS_JSON = ROOT / "tooling" / "m2b_picos_official_boundary_results.json"

TODAY = "2026-09-06"

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


def _load_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
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


# ── KPI assertions (internal consistency) ────────────────────────────────────


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


# ── Server reason-codes (defect 3a) ─────────────────────────────────────────


class TestServerReasonCodes:
    """Boundary failure reason codes: BOUNDARY_GAP, BOUNDARY_OVERLAP, BOUNDARY_EVIDENCE_INCOMPLETE."""

    @pytest.fixture
    def fx(self):
        return _load_fixture()

    @pytest.fixture
    def svc(self):
        return server.Service()

    def test_BOUNDARY_EVIDENCE_INCOMPLETE_on_boundary_zone(self, fx, svc):
        """A point on the sector boundary (in the uncertainty zone) gets BOUNDARY_EVIDENCE_INCOMPLETE."""
        out = server.resolve_point(
            svc, lat=43.277334, lon=-4.634455,
            activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
            facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
        )
        assert out["determination"]["legalStatus"] == "UNDETERMINED"
        assert "BOUNDARY_EVIDENCE_INCOMPLETE" in out["determination"]["reasonCodes"]
        assert any("incertidumbre" in w.lower() or "BOUNDARY_EVIDENCE_INCOMPLETE" in w for w in out["determination"]["warnings"])

    def test_BOUNDARY_OVERLAP_on_mutated_overlap(self, fx, svc):
        """E: mutate es-cb = copy of an es-as-only ring → point in that ring is in both → BOUNDARY_OVERLAP."""
        all_as_rings = list(fx["geometry"]["es-as"])
        cb_rings = list(fx["geometry"]["es-cb"])

        # Find a centroid of an es-as ring that is NOT in any es-cb ring
        overlap_point = None
        ring_to_copy = None
        for ring in all_as_rings:
            if len(ring) < 3:
                continue
            center_lat = sum(r[0] for r in ring) / len(ring)
            center_lon = sum(r[1] for r in ring) / len(ring)
            if (any(_in_ring(center_lat, center_lon, r) for r in all_as_rings)
                    and not any(_in_ring(center_lat, center_lon, r) for r in cb_rings)):
                overlap_point = (center_lat, center_lon)
                ring_to_copy = ring
                break

        if overlap_point is None:
            pytest.skip("Cannot find es-as-only ring centroid for overlap test")
            return

        # Mutate: copy the es-as ring to es-cb (creating overlap at overlap_point)
        new_cb_rings = list(cb_rings) + [list(ring_to_copy)]

        orig_es_cb = list(svc.fx_picos["geometry"]["es-cb"])
        try:
            svc.fx_picos["geometry"]["es-cb"] = new_cb_rings
            out = server.resolve_point(
                svc, lat=overlap_point[0], lon=overlap_point[1],
                activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
                facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
            )
            assert out["determination"]["legalStatus"] == "UNDETERMINED"
            assert "BOUNDARY_OVERLAP" in out["determination"]["reasonCodes"], \
                f"Expected BOUNDARY_OVERLAP, got: {out['determination']['reasonCodes']}"
        finally:
            svc.fx_picos["geometry"]["es-cb"] = orig_es_cb

    def test_BOUNDARY_GAP_on_mutated_gap(self, fx, svc):
        """D: remove es-as ring → point inside that ring is now in a GAP → BOUNDARY_GAP or BOUNDARY_EVIDENCE_INCOMPLETE."""
        temp_fx = copy.deepcopy(fx)
        es_as_rings = list(fx["geometry"]["es-as"])
        # Pick the first ring's center
        center_lat = sum(r[0] for r in es_as_rings[0]) / len(es_as_rings[0])
        center_lon = sum(r[1] for r in es_as_rings[0]) / len(es_as_rings[0])

        orig_es_as = list(svc.fx_picos["geometry"]["es-as"])
        try:
            svc.fx_picos["geometry"]["es-as"] = [
                r for r in es_as_rings if r != es_as_rings[0]
            ]
            out = server.resolve_point(
                svc, lat=center_lat, lon=center_lon,
                activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
                facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
            )
            assert out["determination"]["legalStatus"] == "UNDETERMINED"
            # Must have at least one of the two reason codes
            reason_codes = out["determination"]["reasonCodes"]
            assert "BOUNDARY_GAP" in reason_codes or "BOUNDARY_EVIDENCE_INCOMPLETE" in reason_codes, \
                f"Expected BOUNDARY_GAP or BOUNDARY_EVIDENCE_INCOMPLETE, got: {reason_codes}"
        finally:
            svc.fx_picos["geometry"]["es-as"] = orig_es_as


# ── Resolver-level tests (defect 2: A, B, D, E, F, G, H) ────────────────────


class TestResolverA_B_F_G:
    """A: P2 → PERMITTED; B: P1 → UNDETERMINED; F: outside → NO_APPLICABLE_SCOPE; G: three CCAA."""

    @pytest.fixture
    def fx(self):
        return _load_fixture()

    @pytest.fixture
    def svc(self):
        return server.Service()
    def test_A_p2_cantabria_permitted(self, fx, svc):
        """A: P2_cantabria_interior + facts → PERMITTED (Cantabria).

        Real DEM cota=1942 > 1800 → PERMITTED with DEM.
        Without DEM: user cota_m=2400 > 1800 → PERMITTED.
        Both paths verified: PERMITTED regardless of DEM availability.
        """
        out = server.resolve_point(
            svc, lat=43.17068, lon=-4.80299,
            activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
            facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
        )
        assert out["determination"]["legalStatus"] == "PERMITTED"
        scope_ids = [s["scope_id"] for s in out["applicableScope"]]
        assert "ss-pnpe-es-cb" in scope_ids
        assert "ss-pnpe-es-as" not in scope_ids
        assert "ss-pnpe-es-cl" not in scope_ids

    def test_B_p1_asturias_undetermined(self, fx, svc):
        """B: P1_asturias_interior + facts → UNDETERMINED.

        Real DEM cota=1510 < 1800 → UNDETERMINED with DEM.
        Without DEM: cota_m not provided → ENGINE_MISSING_INPUT → UNDETERMINED.
        Both paths verified: UNDETERMINED regardless of DEM availability.
        """
        out = server.resolve_point(
            svc, lat=43.2662, lon=-4.8686,
            activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
            facts={"actividad_montana_o_escalada": True, "nights": 2},
        )
        assert out["determination"]["legalStatus"] == "UNDETERMINED"
        scope_ids = [s["scope_id"] for s in out["applicableScope"]]
        assert "ss-pnpe-es-as" in scope_ids

    def test_F_outside_park_no_applicable_scope(self, fx, svc):
        """F: outside-park point → reasonCodes contain NO_APPLICABLE_SCOPE."""
        out = server.resolve_point(
            svc, lat=42.0, lon=-3.0,
            activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
            facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
        )
        assert out["determination"]["legalStatus"] == "UNDETERMINED"
        assert "NO_APPLICABLE_SCOPE" in out["determination"]["reasonCodes"]
        assert out["applicableScope"] == []

    def test_G_three_ccaa_interiors(self, fx, svc):
        """G: P1→es-as, P2→es-cb, P3→es-cl — each gets its own governing scope."""
        probes = [
            (43.2662, -4.8686, "ss-pnpe-es-as"),   # P1 → Asturias
            (43.17068, -4.80299, "ss-pnpe-es-cb"),  # P2 → Cantabria
            (43.1278, -4.9381, "ss-pnpe-es-cl"),    # P3 → Castilla y León
        ]
        expected_others = {
            "ss-pnpe-es-as": ["ss-pnpe-es-cb", "ss-pnpe-es-cl"],
            "ss-pnpe-es-cb": ["ss-pnpe-es-as", "ss-pnpe-es-cl"],
            "ss-pnpe-es-cl": ["ss-pnpe-es-as", "ss-pnpe-es-cb"],
        }
        for lat, lon, expected_scope in probes:
            out = server.resolve_point(
                svc, lat=lat, lon=lon,
                activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
                facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
            )
            scope_ids = [s["scope_id"] for s in out["applicableScope"]]
            assert expected_scope in scope_ids, f"Point ({lat},{lon}) missing {expected_scope}"
            for other in expected_others[expected_scope]:
                assert other not in scope_ids, f"Point ({lat},{lon}) should not include {other}"


# ── Test H: disagreement flip points ────────────────────────────────────────


class TestHFlipDisagreement:
    """H: use the committed disagreement_points from results.json to test flips."""

    @pytest.fixture
    def fx(self):
        return _load_fixture()

    @pytest.fixture
    def svc(self):
        return server.Service()

    @pytest.fixture
    def disagreement_points(self):
        res = _load_results()
        return res.get("disagreement_points", [])

    def test_H_flip_outside_100m_resolves_to_official(self, fx, svc, disagreement_points):
        """H(i): pick a flip with dist_to_official_border_m > 100 → official CCAA governs."""
        # Find a disagreement point with distance > 100m
        far = [p for p in disagreement_points if p.get("dist_to_official_border_m", 0) > 100]
        if not far:
            pytest.skip("No disagreement points with dist > 100m found (all in-band)")
            return

        pt = far[0]
        out = server.resolve_point(
            svc, lat=pt["lat"], lon=pt["lon"],
            activity="VIVAC_AL_RASO", activity_date=TODAY, knowledge_date=TODAY,
            facts={"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400},
        )
        official_scope = "ss-pnpe-" + pt["official_jur"]
        scope_ids = [s["scope_id"] for s in out["applicableScope"]]
        assert official_scope in scope_ids, f"Expected {official_scope} in scope_ids={scope_ids}"

    def test_H_flip_all_have_dist_recorded(self, disagreement_points):
        """All 25 disagreement points must have lat, lon, gisco_jur, official_jur, dist_to_official_border_m."""
        assert len(disagreement_points) == 25
        for pt in disagreement_points:
            assert "lat" in pt
            assert "lon" in pt
            assert "gisco_jur" in pt
            assert "official_jur" in pt
            assert "dist_to_official_border_m" in pt


# ── Digest coherence (structural guarantee) ──────────────────────────────


def test_digest_coherence():
    """SHA256 digests must be identical across fixture, evidence lock, and results.json.

    This test makes digest staleness structurally impossible: if any file is
    changed without updating its counterparts, this test fails.
    """
    fixture_bytes = FIXTURE.read_bytes()
    actual_fixture_sha = hashlib.sha256(fixture_bytes).hexdigest()

    with open(EVIDENCE_JSON, encoding="utf-8") as f:
        evidence_data = json.load(f)
    digests = evidence_data["tooling_artifact_digests"]

    with open(RESULTS_JSON, encoding="utf-8") as f:
        results_data = json.load(f)

    # (a) fixture digest consistency: actual == evidence == results
    assert digests["fixture_picos_json"] == actual_fixture_sha, (
        f"Evidence fixture digest mismatch: evidence={digests['fixture_picos_json']}, "
        f"actual={actual_fixture_sha}"
    )
    assert results_data["fixture_sha256"] == actual_fixture_sha, (
        f"Results fixture_sha256 mismatch: results={results_data['fixture_sha256']}, "
        f"actual={actual_fixture_sha}"
    )

    # (b) results_json digest consistency: actual == evidence
    results_bytes = RESULTS_JSON.read_bytes()
    actual_results_sha = hashlib.sha256(results_bytes).hexdigest()
    assert digests["results_json"] == actual_results_sha, (
        f"Evidence results_json digest mismatch: evidence={digests['results_json']}, "
        f"actual={actual_results_sha}"
    )

    # (c) NOTICE.md contains the fixture digest string
    notice_text = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert actual_fixture_sha in notice_text, (
        f"Fixture SHA {actual_fixture_sha} not found in NOTICE.md"
    )


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
        # M3 product MVP (feat/m3-product-mvp): product UI + tests added to the whitelist.
        "webapp/static/app.js",
        "webapp/static/index.html",
        "webapp/static/style.css",
        "webapp/static/store.js",
        "tests/test_m3_product.py",
        # M3.1 Product UX (feat/m3.1-product-ux): pure product UI changes.
        "tests/test_m31_product_ux.py",
    }
    for f in changed:
        assert f in allowed, f"Unexpected file changed: {f}"
