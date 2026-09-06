"""webapp/dem.py — AUTO-ELEVATION from an official DEM via the OSS raster stack.

DEPENDENCY IS OPTIONAL (extra `alraso[dem]` -> rasterio). If rasterio is not
installed, or the prepared DEM tile is missing/invalid, EVERYTHING fails closed
to `DemEvidenceIncomplete`: no `cota_m` is injected, so the resolver returns
UNDETERMINED. There is never a silent fallback (no 0, no last value, no SRTM).

DEM produces a FACT_SOURCE (elevation + provenance). It NEVER decides legality:
the resolver still evaluates `cota_m > 1800`.

Sampling: `rasterio.sample` -> NEAREST pixel (no custom interpolation; rasterio
does not expose bilinear point sampling, and the task forbids writing our own).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent
DEM_DIR = WEBAPP / "data" / "dem"
DEM_TILE = os.environ.get("ALRASO_DEM_TILE", str(DEM_DIR / "picos_mdt.tif"))
DEM_META = os.environ.get("ALRASO_DEM_META", str(DEM_DIR / "picos_mdt.meta.json"))

SAMPLING_METHOD = "nearest_pixel"
_REQUIRED_CRS_EPSG = 4326
_INVALID_LOW = -100.0  # plausible Picos elevations are well above this; fail-closed below


class DemEvidenceIncomplete(Exception):
    """Fail-closed marker: elevation cannot be trusted -> do NOT inject cota_m."""


def _load_meta() -> dict:
    try:
        return json.loads(Path(DEM_META).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - uninitialized -> fail closed
        return {}


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sample_elevation(lat: float, lon: float) -> dict:
    """Return provenance dict {value_m, source, ...} or raise DemEvidenceIncomplete."""
    meta = _load_meta()
    if not meta.get("source_sha256"):
        raise DemEvidenceIncomplete("DEM metadata not initialized")
    try:
        import rasterio  # noqa: F401  (optional)
    except Exception as exc:  # noqa: BLE001
        raise DemEvidenceIncomplete(f"rasterio not available: {type(exc).__name__}") from exc
    if not os.path.exists(DEM_TILE):
        raise DemEvidenceIncomplete("DEM tile not present")
    if _sha256_file(DEM_TILE) != meta["source_sha256"]:
        raise DemEvidenceIncomplete("DEM hash mismatch")
    try:
        with rasterio.open(DEM_TILE) as src:  # noqa: F821
            epsg = src.crs.to_epsg() if src.crs else None
            if epsg != _REQUIRED_CRS_EPSG:
                raise DemEvidenceIncomplete(f"unexpected CRS: {src.crs}")
            left, bottom, right, top = src.bounds
            if not (left <= lon <= right and bottom <= lat <= top):
                raise DemEvidenceIncomplete("point out of raster coverage")
            values = [v[0] for v in src.sample([(lon, lat)])]
            if not values:
                raise DemEvidenceIncomplete("no sample returned")
            value = float(values[0])
            if not math.isfinite(value):
                raise DemEvidenceIncomplete("non-finite elevation")
            if value < _INVALID_LOW:
                raise DemEvidenceIncomplete("implausible elevation (nodata-like)")
            if src.nodata is not None and value == float(src.nodata):
                raise DemEvidenceIncomplete("nodata")
    except DemEvidenceIncomplete:
        raise
    except Exception as exc:  # noqa: BLE001 - library error -> fail closed
        raise DemEvidenceIncomplete(f"raster read error: {type(exc).__name__}") from exc
    return {
        "value_m": value,
        "source": meta.get("source", "IGN/CNIG"),
        "product": meta.get("product", ""),
        "authority": meta.get("authority", ""),
        "source_url": meta.get("source_url", ""),
        "source_artifact_id": meta.get("source_artifact_id", ""),
        "source_sha256": meta["source_sha256"],
        "retrieved_at": meta.get("retrieved_at", ""),
        "crs": f"EPSG:{_REQUIRED_CRS_EPSG}",
        "vertical_datum": meta.get("vertical_datum", ""),
        "resolution_m": meta.get("resolution_m", ""),
        "sampling_method": SAMPLING_METHOD,
        "sample_lat": lat,
        "sample_lon": lon,
        "elevation_m": value,
    }


def dem_available() -> bool:
    """Cheap probe (does not read the tile): whether the DEM stack is configured."""
    meta = _load_meta()
    if not meta.get("source_sha256") or not os.path.exists(DEM_TILE):
        return False
    try:
        import rasterio  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False
