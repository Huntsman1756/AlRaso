"""M8.1 Protected-area data contract — builder-driven tests.

These tests exercise `tooling/m81_protected_area_build.py` purely from
fixture files. No network at test time.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tooling"
BUILD_PY = TOOLS / "m81_protected_area_build.py"
ORDESA_FIXTURE = TOOLS / "pa_ordesa_overpass.json"
PICOS_FIXTURE = TOOLS / "pa_picos_overpass.json"
CROSSCHECK_JSON = TOOLS / "m81_official_crosscheck_results.json"
PA_JSON = ROOT / "webapp" / "protected_areas.json"
SCHEMA_JSON = ROOT / "schemas" / "alraso-m2-protected-areas-v1.schema.json"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build(snapshot_date: str = "2026-09-11") -> Path:
    """Run the builder from fixtures and return the output path."""
    out = Path(__file__).parent / f"_m81_pa_test_{snapshot_date.replace('-','')}.json"
    cmd = [
        sys.executable, str(BUILD_PY),
        "--ordesa", str(ORDESA_FIXTURE),
        "--picos", str(PICOS_FIXTURE),
        "--snapshot-date", snapshot_date,
        "--out", str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"Builder failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Step 1: Contract completeness ───────────────────────────────────────────


def test_required_properties_per_feature():
    """Every feature must have all required M8.1 properties."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    required = {
        "id", "name", "category", "region", "source",
        "source_label", "source_ref", "source_license",
        "snapshot_date", "attribution", "osm_url", "note",
    }
    for f in doc["features"]:
        for key in required:
            assert key in f["properties"], (
                f"Feature {f['id']} missing {key}"
            )


def test_exactly_2_features():
    """Output must contain exactly 2 features."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    assert len(doc["features"]) == 2


def test_expected_relation_ids():
    """Features must reference the 2 expected OSM relation IDs."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    refs = {f["properties"]["source_ref"] for f in doc["features"]}
    assert "relation/10036292" in refs, "Ordesa relation missing"
    assert "relation/2401595" in refs, "Picos relation missing"


def test_source_license_snapshot_date_attribution():
    """source_license, snapshot_date, attribution present and correct."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        p = f["properties"]
        assert p["source_license"] == "ODbL-1.0"
        assert p["snapshot_date"] == "2026-09-11"
        assert p["attribution"] == "© OpenStreetMap contributors"


def test_no_legal_evidence_fields():
    """Properties must NOT contain any legal-evidence fields."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    forbidden = {"rules", "evidence", "legal_status", "permitted",
                 "review_status", "normative_basis"}
    for f in doc["features"]:
        props = f["properties"]
        found = forbidden & set(props.keys())
        assert not found, (
            f"Feature {f['id']} has forbidden fields: {found}"
        )


def test_geometry_validity():
    """Geometry must be valid Polygon/MultiPolygon with lon/lat ranges."""
    import math
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        geom = f["geometry"]
        assert geom["type"] in ("Polygon", "MultiPolygon")
        coords = geom["coordinates"]

        def check_coords(lst):
            for item in lst:
                if (
                    isinstance(item, list)
                    and len(item) >= 1
                    and isinstance(item[0], list)
                    and len(item[0]) >= 1
                    and isinstance(item[0][0], list)
                ):
                    # Deeper nesting: recurse
                    check_coords(item)
                elif (
                    isinstance(item, list)
                    and len(item) == 2
                    and isinstance(item[0], (int, float))
                    and isinstance(item[1], (int, float))
                ):
                    # Leaf: [lon, lat] coordinate pair
                    lon = float(item[0])
                    lat = float(item[1])
                    assert -180 <= lon <= 180, f"lon out of range: {lon}"
                    assert -90 <= lat <= 90, f"lat out of range: {lat}"
                    assert math.isfinite(lon), f"lon not finite: {lon}"
                    assert math.isfinite(lat), f"lat not finite: {lat}"
                else:
                    # Intermediate level (ring): recurse into pairs
                    check_coords(item)

        check_coords(coords)


def test_metadata_stubs_now_real():
    """Metadata source_digests must be real hex digests (not zeros)."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    digests = doc["metadata"]["source_digests"]
    for key, val in digests.items():
        assert len(val) == 64, f"{key} not 64 hex chars"
        assert int(val, 16) != 0, f"{key} is all zeros"


def test_official_crosscheck_block_present():
    """Metadata must have an official_crosscheck block with redistribution=NO."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    cc = doc["metadata"].get("official_crosscheck", {})
    assert cc, "official_crosscheck block missing"
    assert cc.get("guard_passed") is True, "guard_passed not True"
    for park_name, park_data in cc.get("parks", {}).items():
        assert park_data.get("official_redistribution") == "NO (digest-only)"


def test_check_mode_determinism():
    """Builder --check must exit 0 (byte-identical)."""
    cmd = [
        sys.executable, str(BUILD_PY),
        "--ordesa", str(ORDESA_FIXTURE),
        "--picos", str(PICOS_FIXTURE),
        "--snapshot-date", "2026-09-11",
        "--out", str(PA_JSON),
        "--check",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, (
        f"Check mode failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_note_contains_no_legal_scope_disclaimer():
    """Feature notes must contain the no-legal-scope disclaimer."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        note = f["properties"].get("note", "")
        assert "NO" in note.upper(), (
            f"Feature {f['id']} note missing NO disclaimer"
        )
        assert "legal" in note.lower() or "juridico" in note.lower(), (
            f"Feature {f['id']} note missing legal reference"
        )


def test_schema_validation():
    """webapp/protected_areas.json must validate against the schema."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)


def test_schema_registered_in_precommit():
    """protected_areas.json must be in pre-commit check-jsonschema files list."""
    precommit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "protected_areas" in precommit, (
        "protected_areas.json not registered in .pre-commit-config.yaml"
    )


def test_feature_ids():
    """Feature IDs must be pa-ordesa and pa-picos."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    ids = {f["id"] for f in doc["features"]}
    assert "pa-ordesa" in ids
    assert "pa-picos" in ids


def test_category_all_protected_area():
    """All features must have category=protected_area."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        assert f["category"] == "protected_area"


def test_region_values():
    """Feature regions must be 'ordesa' or 'picos'."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        assert f["properties"]["region"] in ("ordesa", "picos")


def test_source_is_openstreetmap():
    """All features must have source=openstreetmap."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        assert f["properties"]["source"] == "openstreetmap"


def test_source_label_is_osm():
    """All features must have source_label=OSM."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        assert f["properties"]["source_label"] == "OSM"


def test_osm_url_present():
    """Each feature must have a valid OSM URL."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    for f in doc["features"]:
        url = f["properties"]["osm_url"]
        assert url.startswith("https://www.openstreetmap.org/relation/")


def test_simplification_metadata():
    """Metadata must include simplification block with tolerance and vertex counts."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    simp = doc["metadata"].get("simplification", {})
    assert simp.get("method"), "simplification.method missing"
    assert "tolerance_degrees" in simp, "simplification.tolerance_degrees missing"
    per_feature = simp.get("per_feature", {})
    assert "pa-ordesa" in per_feature
    assert "pa-picos" in per_feature
    for fid in ("pa-ordesa", "pa-picos"):
        info = per_feature[fid]
        assert "vertices_before" in info
        assert "vertices_after" in info
        assert "vertices_reduced" in info


def test_builder_self_digest():
    """Metadata must include builder_self_sha256."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    self_sha = doc["metadata"].get("builder_self_sha256", "")
    assert len(self_sha) == 64
    assert int(self_sha, 16) != 0


def test_fixture_digests():
    """Metadata must include fixture_digests with real hashes."""
    doc = json.loads(PA_JSON.read_text(encoding="utf-8"))
    fd = doc["metadata"].get("fixture_digests", {})
    assert len(fd.get("ordesa_fixture_sha256", "")) == 64
    assert len(fd.get("picos_fixture_sha256", "")) == 64


def test_pics_area_crosscheck_delta_within_5():
    """Official cross-check delta must be within 5%."""
    assert CROSSCHECK_JSON.exists(), "Crosscheck results file missing"
    cc = json.loads(CROSSCHECK_JSON.read_text(encoding="utf-8"))
    for park_name, park_data in cc.get("parks", {}).items():
        delta = park_data.get("delta_pct")
        if delta is not None:
            assert abs(delta) <= 5, (
                f"{park_name} delta {delta}% exceeds 5% threshold"
            )


def test_guard_passed():
    """Guard must have passed."""
    assert CROSSCHECK_JSON.exists()
    cc = json.loads(CROSSCHECK_JSON.read_text(encoding="utf-8"))
    assert cc.get("guard", {}).get("passed") is True