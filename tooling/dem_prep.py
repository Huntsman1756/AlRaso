"""tooling/dem_prep.py — PREPARE the official IGN/CNIG MDT tile for auto-elevation.

Download the official MDT (Modelo Digital del Terreno / MDE) covering the Picos
park bbox, clip to it, and write a local GeoTIFF + provenance metadata. The tile
is NOT committed (gitignored): it is prepared locally / at deploy time.

If the download or clipping fails, the script writes metadata with an empty
source_sha256 so the runtime fails closed (DEM_EVIDENCE_INCOMPLETE) instead of
serving an unverified elevation.

Source: IGN/CNIG MDT (open data; reuse terms to be verified formally).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

DEM_DIR = os.path.join(ROOT, "webapp", "data", "dem")
OUT_TILE = os.path.join(DEM_DIR, "picos_mdt.tif")
OUT_META = os.path.join(DEM_DIR, "picos_mdt.meta.json")

# Picos park bbox (from fixture_picos.json / discovery) with a small margin.
BBOX = [-5.35, 42.40, 0.35, 43.40]  # [minx, miny, maxx, maxy] WGS84

# Primary source: IGN/CNIG MDT via IDE WCS (GetCoverage, GeoTIFF output).
WCS_URL = (
    "https://servicios.idee.es/wcs-inspire/mdt?"
    + urllib.parse.urlencode({
        "service": "WCS", "version": "2.0.0", "request": "GetCoverage",
        "coverageId": "MDT025_50N",
        "format": "image/tiff",
        "subset": f"http://www.opengis.net/def/crs/OGC/1.3/CRS84({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]})",
        "outputCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
    })
)

SOURCE = {
    "source": "IGN/CNIG",
    "authority": "Instituto Geográfico Nacional / Centro Nacional de Información Geográfica",
    "product": "MDT (Modelo Digital del Terreno / MDE)",
    "resolution_m": 25,
    "vertical_datum": "EGM08 (ortométrico)",
    "crs": "EPSG:4326",
    "source_url": WCS_URL,
    "retrieved_at": date.today().isoformat(),
    "reuse_terms": "NOT_VERIFIED (open data CC BY 4.0 claim; primary reuse-terms page not retrievable from sandbox)",
    "attribution": "© Instituto Geográfico Nacional (IGN) / CNIG",
    "access_pattern": "WCS GetCoverage (tile/bbox); COG where available",
    "cog_or_not": "coverage served via WCS; IGN also publishes MDT as COG",
    "byte_size": None,
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download() -> bool:
    os.makedirs(DEM_DIR, exist_ok=True)
    try:
        urllib.request.urlretrieve(WCS_URL, OUT_TILE)
    except Exception as exc:  # noqa: BLE001
        print(f"[dem_prep] download failed: {type(exc).__name__}: {exc}")
        return False
    try:
        import rasterio  # noqa: F401
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[dem_prep] rasterio not available: {type(exc).__name__}")
        return False


def main() -> int:
    os.makedirs(DEM_DIR, exist_ok=True)
    ok = download()
    meta = dict(SOURCE)
    if ok and os.path.exists(OUT_TILE):
        meta["source_sha256"] = sha256(OUT_TILE)
        meta["byte_size"] = os.path.getsize(OUT_TILE)
        print(f"[dem_prep] tile prepared: {OUT_TILE} ({meta['byte_size']} bytes)")
    else:
        meta["source_sha256"] = ""  # uninitialized -> runtime fails closed
        meta["note"] = "DEM tile NOT prepared (download/rasterio unavailable). Auto-elevation stays DEM_EVIDENCE_INCOMPLETE."
        print("[dem_prep] tile NOT prepared; metadata written uninitialized (fail-closed).")
    with open(OUT_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(f"[dem_prep] metadata: {OUT_META}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
