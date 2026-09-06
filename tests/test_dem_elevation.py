"""DEM auto-elevation with a synthetic raster (requires rasterio -> importorskip).

Proves the OFFICIAL_DEM -> cota_m -> resolver flow and the fail-closed cases
(nodata, out-of-coverage, hash mismatch, missing file). A 1x1 synthetic tile over
the Picos bbox assigns a constant elevation, so sampling is deterministic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")  # noqa: F841  (skip if not installed)
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import dem as dem_mod  # noqa: E402
import server  # noqa: E402

TODAY = "2026-09-06"
BBOX = (-5.35, 42.40, 0.35, 43.40)


def _make_tile(path: Path, value: float, nodata=None, bbox=BBOX, crs="EPSG:4326") -> str:
    from rasterio.transform import from_bounds
    left, bottom, right, top = bbox
    transform = from_bounds(left, bottom, right, top, 1, 1)
    profile = {"driver": "GTiff", "width": 1, "height": 1, "count": 1,
               "dtype": "float32", "crs": crs, "transform": transform}
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.array([[value]], dtype="float32"), 1)
    return dem_mod._sha256_file(str(path))


def _configure(monkeypatch, tmp_path, value, *, nodata=None, bbox=BBOX, crs="EPSG:4326",
               source_sha256=None):
    tile = tmp_path / "tile.tif"
    real_sha = _make_tile(tile, value, nodata=nodata, bbox=bbox, crs=crs)
    meta = {
        "source": "IGN/CNIG", "product": "MDT (synthetic test)", "authority": "test",
        "source_url": "https://example.invalid/mdt", "source_artifact_id": "test-tile",
        "source_sha256": source_sha256 or real_sha, "retrieved_at": TODAY,
        "vertical_datum": "orthometric", "vertical_reference_detail": "NOT_VERIFIED",
        "resolution_m": 25, "reuse_terms": "test",
    }
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(dem_mod, "DEM_TILE", str(tile))
    monkeypatch.setattr(dem_mod, "DEM_META", str(meta_path))
    return real_sha


@pytest.fixture(scope="module")
def svc() -> server.Service:
    return server.Service()


def _resolve(svc, lat, lon, facts=None):
    return server.resolve_point(svc, lat=lat, lon=lon, activity="VIVAC_AL_RASO",
                                activity_date=TODAY, knowledge_date=TODAY, facts=facts or {})


BASE_FACTS = {"actividad_montana_o_escalada": True, "nights": 2}


def test_p1_dem_auto_elevation_permitted(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0)
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "OFFICIAL_DEM"
    assert out["dem"]["value_m"] == pytest.approx(2400.0)
    assert out["determination"]["legalStatus"] == "PERMITTED"


def test_p2_p3_dem_auto_elevation_permitted(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0)
    assert _resolve(svc, 43.17068, -4.80299, BASE_FACTS)["determination"]["legalStatus"] == "PERMITTED"
    assert _resolve(svc, 43.1278, -4.9381, BASE_FACTS)["determination"]["legalStatus"] == "PERMITTED"


def test_p4_p5_boundary_undetermined_even_with_dem(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0)
    for lat, lon in [(43.25005, -4.72339), (43.16286, -4.83443)]:
        out = _resolve(svc, lat, lon, BASE_FACTS)
        assert out["determination"]["legalStatus"] == "UNDETERMINED"
        assert "BOUNDARY_EVIDENCE_INCOMPLETE" in out["determination"]["reasonCodes"]
        assert out["dem"]["value_m"] == pytest.approx(2400.0)  # DEM present, but boundary blocks


def test_p7_outside_no_dem_requested(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0)
    out = _resolve(svc, 43.348, -5.13, BASE_FACTS)
    assert out["cotaFactSource"] == "NONE"
    assert out["dem"] is None
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert "NO_APPLICABLE_SCOPE" in out["determination"]["reasonCodes"]


@pytest.mark.parametrize("value,expected", [(1799.0, "UNDETERMINED"),
                                            (1800.0, "UNDETERMINED"),
                                            (1801.0, "PERMITTED")])
def test_1800_boundary_with_dem(svc, monkeypatch, tmp_path, value, expected):
    _configure(monkeypatch, tmp_path, value)
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "OFFICIAL_DEM"
    assert out["determination"]["legalStatus"] == expected


def test_dem_nodata_fails_closed(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 9999.0, nodata=9999.0)
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "NONE"
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert "ENGINE_MISSING_INPUT" in out["determination"]["reasonCodes"]


def test_dem_out_of_coverage_fails_closed(svc, monkeypatch, tmp_path):
    # tiny tile in the ocean, does not cover Picos
    _configure(monkeypatch, tmp_path, 2400.0, bbox=(-2.0, 44.0, -1.0, 45.0))
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "NONE"
    assert out["determination"]["legalStatus"] == "UNDETERMINED"


def test_dem_hash_mismatch_fails_closed(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0, source_sha256="0" * 64)
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "NONE"
    assert out["determination"]["legalStatus"] == "UNDETERMINED"


def test_dem_missing_file_fails_closed(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0)
    monkeypatch.setattr(dem_mod, "DEM_TILE", str(tmp_path / "does_not_exist.tif"))
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "NONE"
    assert out["determination"]["legalStatus"] == "UNDETERMINED"


def test_dem_priority_over_user_and_diff_warning(svc, monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, 2400.0)
    out = _resolve(svc, 43.2662, -4.8686,
                   {"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 1500})
    assert out["cotaFactSource"] == "OFFICIAL_DEM"
    assert out["userVsDem"]["DIFF_M"] == pytest.approx(900.0)
    assert any("difiere materialmente" in w for w in out["determination"]["warnings"])


def test_dem_non4326_crs_is_transformed(svc, monkeypatch, tmp_path):
    # The real IGN MDT25 is EPSG:25830 (native UTM30), NOT 4326. The runtime must
    # NOT force EPSG:4326: it reads src.crs and transforms the query point via
    # rasterio.warp.transform before sampling. Prove the transform path works.
    import rasterio.warp
    from rasterio.transform import from_bounds
    x0, y0 = rasterio.warp.transform("EPSG:4326", "EPSG:25830", [-5.17066], [43.02469])
    x1, y1 = rasterio.warp.transform("EPSG:4326", "EPSG:25830", [-4.56729], [43.36586])
    bbox = (x0[0], y0[0], x1[0], y1[0])
    _configure(monkeypatch, tmp_path, 2400.0, bbox=bbox, crs="EPSG:25830")
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "OFFICIAL_DEM"
    assert out["dem"]["value_m"] == pytest.approx(2400.0)
    assert out["dem"]["crs"] == "EPSG:25830"
    assert out["dem"]["crs_epsg"] == 25830
    assert out["determination"]["legalStatus"] == "PERMITTED"


def test_dem_no_crs_fails_closed(svc, monkeypatch, tmp_path):
    # A raster with no CRS cannot be transformed -> fail closed (never inject cota_m).
    _configure(monkeypatch, tmp_path, 2400.0, crs=None)
    out = _resolve(svc, 43.2662, -4.8686, BASE_FACTS)
    assert out["cotaFactSource"] == "NONE"
    assert out["dem"] is None
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
