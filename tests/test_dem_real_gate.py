"""Optional REAL-WORLD IGN/CNIG gate (opt-in, never hermetic / never blocking).

The hermetic CI suite uses a synthetic fixture. This gate proves the real path
against the official IGN/CNIG WCS service and is run LOCALLY (or in a network-
allowed runner), because the IGN service may be unreachable from CI and the
tile must never be committed.

Run locally:
    ALRASO_REAL_IGN_GATE=1 python -m pytest -q tests/test_dem_real_gate.py

What it proves:
  * tooling/dem_prep.py runs against IGN/CNIG and prepares a REAL raster;
  * rasterio opens the artifact (real readable raster, >=1 band, has CRS);
  * the metadata hash matches the tile on disk;
  * the P1 control sample is a plausible elevation;
  * the raster and metadata are deleted afterwards (never committed).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")  # noqa: F841

pytestmark = pytest.mark.skipif(
    os.environ.get("ALRASO_REAL_IGN_GATE") != "1",
    reason="real-world IGN gate is opt-in; run locally with ALRASO_REAL_IGN_GATE=1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tooling.dem_prep as dp  # noqa: E402


def test_real_ign_gate():
    try:
        rc = dp.main()
        assert rc == 0, f"dem_prep.main() failed against real IGN (rc={rc})"
        assert os.path.exists(dp.OUT_TILE), "no real raster produced"
        meta = json.loads(Path(dp.OUT_META).read_text(encoding="utf-8"))
        assert meta["DEM_PREPARED"] == "YES", "tile not declared prepared"
        assert meta["source_sha256"], "no source_sha256 recorded for a prepared tile"
        assert meta["crs"].startswith("EPSG:"), meta["crs"]
        # rasterio opens the artifact
        import rasterio  # noqa: F401

        with rasterio.open(dp.OUT_TILE) as src:
            assert src.count >= 1
            assert src.crs is not None, "raster has no CRS"
        # metadata hash matches the tile
        assert dp.sha256(dp.OUT_TILE) == meta["source_sha256"], "hash mismatch"
        # P1 sample plausible (real IGN MDT25)
        p1 = meta.get("control_sample_p1")
        assert p1 is not None and 0 < p1 < 3500, f"implausible P1 sample: {p1}"
        print(f"[real-ign-gate] PASS coverage={meta['coverage_id']} crs={meta['crs']} "
              f"res={meta['resolution_m']}m P1={p1}m sha256={meta['source_sha256']}")
    finally:
        # Never commit the raster: clean up after the gate.
        for p in (dp.OUT_TILE, dp.OUT_META):
            if os.path.exists(p):
                os.remove(p)
