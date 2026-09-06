"""DEM preparation (tooling/dem_prep.py) hermetic tests.

These prove the *preparation* contract without hitting the network:
  * the bbox is derived from fixture_picos.json (no manual bbox);
  * the WCS 2.0.1 request uses one SUBSET parameter per dimension and a proven
    coverage (Elevacion25830_25);
  * the artifact is REALLY validated (raster driver, band count, CRS, bounds,
    resolution, nodata, finite control sample) before source_sha256 is set;
  * an XML/OGC-exception / wrong-CRS / wrong-bounds / wrong-resolution /
    non-plausible artifact must yield source_sha256="" and DEM_PREPARED=NO.

Requires rasterio -> skipped in the stdlib-only suite, run in the dem job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")  # noqa: F841
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tooling.dem_prep as dp  # noqa: E402
import rasterio.warp  # noqa: E402


PICOS_BBOX = dp.derive_picos_bbox()
P1 = (43.2662, -4.8686)  # (lat, lon)
P1_BBOX = [-4.95, 43.20, -4.75, 43.32]  # small WGS84 box around P1


def _make_raster(path, value, *, crs, left, bottom, right, top, res_m,
                 nodata=None, dtype="float32"):
    from rasterio.transform import from_bounds
    width = max(1, int(round((right - left) / res_m)))
    height = max(1, int(round((top - bottom) / res_m)))
    transform = from_bounds(left, bottom, right, top, width, height)
    profile = {"driver": "GTiff", "width": width, "height": height, "count": 1,
               "dtype": dtype, "crs": crs, "transform": transform}
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((height, width), value, dtype=dtype), 1)
    return path


def _utm_of(bbox):
    x0, y0 = rasterio.warp.transform("EPSG:4326", "EPSG:25830", [bbox[0]], [bbox[1]])
    x1, y1 = rasterio.warp.transform("EPSG:4326", "EPSG:25830", [bbox[2]], [bbox[3]])
    return x0[0], y0[0], x1[0], y1[0]


def test_derive_picos_bbox_is_tight_and_picos():
    bbox = dp.derive_picos_bbox()
    assert bbox[2] - bbox[0] < 1.0
    assert bbox[3] - bbox[1] < 1.0
    assert bbox[0] < -4.6 and bbox[2] > -5.13
    assert bbox[1] < 43.1 and bbox[3] > 43.31
    # assertion would raise if it did not correspond to Picos
    dp.assert_picos_bbox(bbox)


def test_build_wcs_request_uses_wcs201_and_one_subset_per_dimension():
    from urllib.parse import parse_qs, urlparse
    url = dp.build_wcs_request(PICOS_BBOX)
    assert "service=WCS" in url
    assert "version=2.0.1" in url
    assert "request=GetCoverage" in url
    assert "coverageId=Elevacion25830_25" in url
    assert "format=image%2Ftiff" in url
    qs = parse_qs(urlparse(url).query)
    # one SUBSET per dimension (x and y), never a single combined CRS84(...) subset
    assert len(qs["subset"]) == 2
    assert qs["subset"][0].startswith("x(")
    assert qs["subset"][1].startswith("y(")
    assert "CRS84(" not in url
    assert dp.WCS_VERSION == "2.0.1"


def test_validate_tile_accepts_valid_25830():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        left, bottom, right, top = _utm_of(P1_BBOX)
        tile = _make_raster(Path(td) / "ok.tif", 1510.0, crs="EPSG:25830",
                            left=left, bottom=bottom, right=right, top=top, res_m=25)
        res = dp.validate_tile(str(tile), bbox=P1_BBOX, control_points=[P1])
        assert res["ok"] is True
        assert res["crs_epsg"] == 25830
        assert res["count"] >= 1
        assert 15 <= res["resolution_m"] <= 35
        assert res["control_sample_p1"] == pytest.approx(1510.0)


def test_validate_tile_rejects_xml_exception_masquerading(tmp_path):
    # OGC exception/HTML body saved with a .tif name is NOT a raster -> fail closed.
    xml = Path(tmp_path) / "fake.tif"
    xml.write_text('<?xml version="1.0"?><ows:ExceptionReport><ows:Exception '
                   'exceptionCode="NoSuchCoverage">not found</ows:Exception>'
                   '</ows:ExceptionReport>', encoding="utf-8")
    res = dp.validate_tile(str(xml), bbox=PICOS_BBOX, control_points=[P1])
    assert res["ok"] is False
    assert "not a readable raster" in res["error"]


def test_validate_tile_rejects_wrong_crs(tmp_path):
    left, bottom, right, top = _utm_of(P1_BBOX)
    tile = _make_raster(Path(tmp_path) / "w.tif", 1510.0, crs="EPSG:3857",
                        left=left, bottom=bottom, right=right, top=top, res_m=25)
    res = dp.validate_tile(str(tile), bbox=P1_BBOX, control_points=[P1])
    assert res["ok"] is False
    assert "unexpected CRS" in res["error"]


def test_validate_tile_rejects_bounds_not_containing_picos(tmp_path):
    # ocean tile: bounds do not contain the Picos bbox
    tile = _make_raster(Path(tmp_path) / "ocean.tif", 0.0, crs="EPSG:25830",
                        left=300000, bottom=4600000, right=320000, top=4620000, res_m=25)
    res = dp.validate_tile(str(tile), bbox=PICOS_BBOX, control_points=[P1])
    assert res["ok"] is False
    assert "do not contain bbox" in res["error"]


def test_validate_tile_rejects_incompatible_resolution(tmp_path):
    left, bottom, right, top = _utm_of(P1_BBOX)
    tile = _make_raster(Path(tmp_path) / "coarse.tif", 1510.0, crs="EPSG:25830",
                        left=left, bottom=bottom, right=right, top=top, res_m=1000)
    res = dp.validate_tile(str(tile), bbox=P1_BBOX, control_points=[P1])
    assert res["ok"] is False
    assert "resolution" in res["error"]


def test_validate_tile_rejects_non_plausible_sample(tmp_path):
    left, bottom, right, top = _utm_of(P1_BBOX)
    tile = _make_raster(Path(tmp_path) / "neg.tif", -50.0, crs="EPSG:25830",
                        left=left, bottom=bottom, right=right, top=top, res_m=25)
    res = dp.validate_tile(str(tile), bbox=P1_BBOX, control_points=[P1])
    assert res["ok"] is False
    assert "control sample" in res["error"]


def test_finalize_meta_fail_closed_on_xml_and_yes_on_valid(tmp_path):
    xml = Path(tmp_path) / "x.tif"
    xml.write_text("<html>Service Exception</html>", encoding="utf-8")
    bad = dp.validate_tile(str(xml), bbox=PICOS_BBOX, control_points=[P1])
    meta = dp.finalize_meta({"x": 1}, bad, str(xml))
    assert meta["source_sha256"] == ""
    assert meta["DEM_PREPARED"] == "NO"

    left, bottom, right, top = _utm_of(P1_BBOX)
    tile = _make_raster(Path(tmp_path) / "ok.tif", 1510.0, crs="EPSG:25830",
                        left=left, bottom=bottom, right=right, top=top, res_m=25)
    good = dp.validate_tile(str(tile), bbox=P1_BBOX, control_points=[P1])
    meta2 = dp.finalize_meta({"x": 1}, good, str(tile))
    assert meta2["source_sha256"] == dp.sha256(str(tile))
    assert meta2["DEM_PREPARED"] == "YES"
    assert meta2["crs"] == "EPSG:25830"
