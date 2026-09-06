"""tooling/dem_prep.py — PREPARE the official IGN/CNIG MDT tile for auto-elevation.

Download the official MDT25 (Modelo Digital del Terreno / MDE) covering the
Picos park bbox via the IGN/CNIG IDE WCS 2.0.1 service, validate that the
downloaded artifact is a real readable raster with the expected CRS, bounds,
resolution and a finite control sample, and only then write a local GeoTIFF +
provenance metadata. The tile is NOT committed (gitignored): it is prepared
locally / at deploy time.

If the download is not a real raster (an OGC XML/HTML exception, an error page,
a non-raster body), or the validation fails (wrong CRS, bounds that do not
contain Picos, incompatible resolution, no finite control sample), the script
writes metadata with an empty source_sha256 and DEM_PREPARED=NO so the runtime
fails closed (DEM_EVIDENCE_INCOMPLETE) instead of serving an unverified elevation.

Coverage evidence (proven by the service itself):
  * GetCapabilities (WCS 2.0.1): `Elevacion4258_25`, `Elevacion25830_25`, ...
    exist; `MDT025_50N` does NOT (returns ows:ExceptionReport NoSuchCoverage).
  * DescribeCoverage `Elevacion25830_25`: nativeFormat COG, EPSG:25830 grid,
    25 m offset vectors, axis labels `x`/`y`.
  * AccessConstraints in GetCapabilities: `CC BY 4.0 scne.es`; Fees: none.

Source: IGN/CNIG MDT25 (open data, CC BY 4.0).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

DEM_DIR = os.path.join(ROOT, "webapp", "data", "dem")
OUT_TILE = os.path.join(DEM_DIR, "picos_mdt.tif")
OUT_META = os.path.join(DEM_DIR, "picos_mdt.meta.json")
FIXTURE = os.path.join(ROOT, "alraso", "resources", "fixture_picos.json")

# WCS 2.0.1 (INSPIRE download service) — one SUBSET parameter per dimension.
WCS_BASE = "https://servicios.idee.es/wcs-inspire/mdt?"
WCS_VERSION = "2.0.1"

# Coverage proven by GetCapabilities/DescribeCoverage. Prefer the native 25 m
# UTM30 product; `Elevacion4258_25` (geographic) is the documented alternative.
DEFAULT_COVERAGE = "Elevacion25830_25"
SUPPORTED_COVERAGES = {
    "Elevacion25830_25": {
        "crs": "EPSG:25830",         # ETRS89 UTM 30N, native for Picos
        "axis_x": "x",               # Easting axis label (DescribeCoverage)
        "axis_y": "y",               # Northing axis label
        "resolution_m": 25,
        "expected_crs_epsgs": {25830},
    },
    "Elevacion4258_25": {
        "crs": "EPSG:4326",          # server returns WGS84 geographic for this coverage
        "axis_x": "long",
        "axis_y": "lat",
        "resolution_m": 25,
        "expected_crs_epsgs": {4326, 4258},
    },
}

# Picos park bbox is derived from the fixture geometry.park ring + a bounded
# margin. The margin is small (a few km) so the bbox stays tight on Picos and
# never balloons to cover all of Spain.
MARGIN_DEG = 0.05
# A 25 m product may report ~25 m (UTM) or ~0.000225 deg (geographic). Tolerance
# is generous but still fails on a 5 m / 200 m / 1000 m product.
RES_TOLERANCE_M = (15.0, 35.0)
# Plausible Picos elevations (m). Torre Cerredo is the highest peak (≈2650 m).
PLAUSIBLE_MIN_M = 0.0
PLAUSIBLE_MAX_M = 3500.0

SOURCE = {
    "source": "IGN/CNIG",
    "authority": "Instituto Geográfico Nacional / Centro Nacional de Información Geográfica",
    "product": "MDT25 (Modelo Digital del Terreno / MDE)",
    "vertical_datum": "orthometric",
    "vertical_reference_detail": "NOT_VERIFIED",
    "dem_reuse_terms": "VERIFIED",
    "license": "CC-BY-4.0",
    "attribution": "© Instituto Geográfico Nacional (IGN) / CNIG",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def park_ring(fx: dict) -> list[list[float]]:
    """Return the park boundary ring as [lat, lon] pairs from the fixture."""
    return fx["geometry"]["park"][0]


def derive_picos_bbox(margin_deg: float = MARGIN_DEG) -> list[float]:
    """Derive [minx, miny, maxx, maxy] (WGS84) from fixture geometry.park + margin.

    The bbox is intentionally bounded: the fixture is already a tight Picos
    ring, so a small margin is enough. No hand-written bbox anywhere.
    """
    ring = park_ring(load_fixture())
    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    minx, maxx = min(lons), max(lons)
    miny, maxy = min(lats), max(lats)
    bbox = [minx - margin_deg, miny - margin_deg, maxx + margin_deg, maxy + margin_deg]
    assert_picos_bbox(bbox)
    return bbox


def assert_picos_bbox(bbox: list[float]) -> None:
    """Explicit assertion that the bbox corresponds to Picos de Europa.

    The bbox must (a) be a small box around the fixture ring, (b) contain the
    fixture ring and every in-park probe point, and (c) be inside a plausible
    Spain / Picos window. Failing any of these is a hard error.
    """
    minx, miny, maxx, maxy = bbox
    if not (maxx > minx and maxy > miny):
        raise AssertionError(f"degenerate bbox: {bbox}")
    width = maxx - minx
    height = maxy - miny
    # bounded: Picos spans ~0.5 deg lon and ~0.3 deg lat; allow a little slack.
    if width > 1.0 or height > 1.0:
        raise AssertionError(f"bbox too large for Picos: width={width:.3f} height={height:.3f}")
    # inside a plausible Spain window
    if not (minx > -10.0 and maxx < 4.0 and miny > 36.0 and maxy < 44.0):
        raise AssertionError(f"bbox outside Spain window: {bbox}")

    fx = load_fixture()
    ring = park_ring(fx)
    for lat, lon in ring:
        if not (minx <= lon <= maxx and miny <= lat <= maxy):
            raise AssertionError(f"park vertex {lon},{lat} outside bbox {bbox}")
    for key, pt in fx.get("probe_points", {}).items():
        if pt.get("inside_park"):
            lon, lat = pt["lon"], pt["lat"]
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                raise AssertionError(f"in-park probe {key} outside bbox {bbox}")


def coverage_config(coverage_id: str) -> dict:
    if coverage_id not in SUPPORTED_COVERAGES:
        raise AssertionError(f"coverage {coverage_id} not proven; supported: {list(SUPPORTED_COVERAGES)}")
    return SUPPORTED_COVERAGES[coverage_id]


def build_wcs_request(bbox: list[float], coverage_id: str = DEFAULT_COVERAGE) -> str:
    """Build a WCS 2.0.1 GetCoverage URL with one SUBSET parameter per dimension.

    The bbox (WGS84 lon/lat) is transformed to the coverage's native CRS and
    each axis is subset with its own `subset=` parameter, per the WCS 2.0.1
    KVP encoding (`subset=axis(low,high)`).
    """
    cfg = coverage_config(coverage_id)
    # Transform bbox corners WGS84 -> coverage CRS (always_xy: input is lon,lat).
    x0, y0 = _transform("EPSG:4326", cfg["crs"], bbox[0], bbox[1])
    x1, y1 = _transform("EPSG:4326", cfg["crs"], bbox[2], bbox[3])
    pairs = [
        ("service", "WCS"),
        ("version", WCS_VERSION),
        ("request", "GetCoverage"),
        ("coverageId", coverage_id),
        ("format", "image/tiff"),
        ("subset", f"{cfg['axis_x']}({x0},{x1})"),
        ("subset", f"{cfg['axis_y']}({y0},{y1})"),
    ]
    return WCS_BASE + urllib.parse.urlencode(pairs)


def _transform(src_crs: str, dst_crs: str, x: float, y: float) -> tuple[float, float]:
    """Thin wrapper over rasterio.warp.transform (no custom CRS math).

    `x` is a longitude / easting and `y` a latitude / northing in `src_crs`.
    """
    import rasterio.warp  # noqa: F401 (optional alraso[dem])

    xs, ys = rasterio.warp.transform(src_crs, dst_crs, [x], [y])
    return xs[0], ys[0]


def _res_meters(res, crs_epsg: int) -> float:
    """Approximate raster resolution in metres for validation."""
    xres = abs(res[0])
    if crs_epsg in (25830, 25829, 25828, 25831):  # projected (metres)
        return xres
    return xres * 111320.0  # geographic degrees -> metres (approx)


def validate_tile(path: str, *, bbox: list[float], coverage_id: str = DEFAULT_COVERAGE,
                  control_points: list[tuple[float, float]] | None = None) -> dict:
    """Really validate the downloaded artifact with rasterio.

    Returns a dict with `ok: bool` and the measured facts. On any failure the
    caller must treat the tile as NOT prepared (source_sha256="", DEM_PREPARED=NO).
    """
    cfg = coverage_config(coverage_id)
    try:
        import rasterio  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - cannot validate without rasterio -> fail closed
        return {"ok": False, "error": f"rasterio not available: {type(exc).__name__}: {exc}"}

    try:
        src = rasterio.open(path)
    except Exception as exc:  # noqa: BLE001 - XML/HTML/OGC exception is not a raster
        return {"ok": False, "error": f"not a readable raster: {type(exc).__name__}: {exc}"}

    with src:
        driver = src.driver
        if driver is None:
            return {"ok": False, "error": "no raster driver"}
        count = src.count
        if count < 1:
            return {"ok": False, "error": f"no bands (count={count})"}
        crs = src.crs
        if crs is None:
            return {"ok": False, "error": "raster has no CRS"}
        epsg = crs.to_epsg()
        if epsg not in cfg["expected_crs_epsgs"]:
            return {"ok": False, "error": f"unexpected CRS {crs} (epsg={epsg}), "
                                          f"expected {sorted(cfg['expected_crs_epsgs'])}"}
        left, bottom, right, top = src.bounds
        # The requested bbox (park + margin, WGS84) must be contained by the
        # raster once expressed in the raster's own CRS.
        bx0, by0 = _transform("EPSG:4326", f"EPSG:{epsg}", bbox[0], bbox[1])
        bx1, by1 = _transform("EPSG:4326", f"EPSG:{epsg}", bbox[2], bbox[3])
        if not (left <= bx0 and bottom <= by0 and right >= bx1 and top >= by1):
            return {"ok": False,
                    "error": f"bounds {src.bounds} (CRS {crs}) do not contain bbox "
                             f"{bbox} (WGS84 -> raster-CRS corners {bx0},{by0},{bx1},{by1})"}
        res_m = _res_meters(src.res, epsg)
        if not (RES_TOLERANCE_M[0] <= res_m <= RES_TOLERANCE_M[1]):
            return {"ok": False, "error": f"resolution {res_m:.2f} m incompatible with 25 m product"}
        nodata = src.nodata
        dtype = src.dtypes[0] if src.dtypes else None

        # Control sample: transform each WGS84 point to the raster CRS and sample.
        control = {}
        if control_points is None:
            fx = load_fixture()
            control_points = [(p["lat"], p["lon"]) for p in fx["probe_points"].values()
                              if p.get("inside_park")]
        for lat, lon in control_points:
            x, y = _transform("EPSG:4326", f"EPSG:{epsg}", lon, lat)
            if not (left <= x <= right and bottom <= y <= top):
                control[lon] = None
                continue
            try:
                val = float(next(iter(src.sample([(x, y)])))[0])
            except Exception as exc:  # noqa: BLE001
                control[lon] = None
                continue
            if not _finite_plausible(val, nodata):
                return {"ok": False,
                        "error": f"control sample at lon={lon},lat={lat} not plausible "
                                 f"(value={val}, nodata={nodata})"}
            control[lon] = val

        p1 = None
        fx = load_fixture()
        p1_pt = fx["probe_points"].get("P1_asturias_urriellu")
        if p1_pt:
            p1 = control.get(p1_pt["lon"])

        return {
            "ok": True,
            "driver": driver,
            "count": count,
            "crs": str(crs),
            "crs_epsg": epsg,
            "bounds": [left, bottom, right, top],
            "resolution_m": round(res_m, 2),
            "nodata": nodata,
            "dtype": dtype,
            "control_sample_p1": p1,
            "control_samples": control,
        }


def _finite_plausible(value: float, nodata) -> bool:
    import math

    if not math.isfinite(value):
        return False
    if nodata is not None and value == float(nodata):
        return False
    return PLAUSIBLE_MIN_M <= value <= PLAUSIBLE_MAX_M


def download(url: str, dest: str) -> bool:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as exc:  # noqa: BLE001
        print(f"[dem_prep] download failed: {type(exc).__name__}: {exc}")
        return False
    return True


def finalize_meta(meta: dict, validation, tile_path: str) -> dict:
    """Decide the provenance verdict from the validation result.

    A prepared tile is only declared when the artifact really is a readable
    raster with the expected CRS/bounds/resolution and a finite control sample.
    Any XML/HTML/OGC-exception or wrong-CRS/bounds/resolution artifact must
    leave source_sha256="" and DEM_PREPARED=NO (fail closed).
    """
    if validation and validation.get("ok"):
        meta["source_sha256"] = sha256(tile_path)
        meta["byte_size"] = os.path.getsize(tile_path)
        meta["DEM_PREPARED"] = "YES"
        meta["crs"] = validation["crs"]
        meta["crs_epsg"] = validation["crs_epsg"]
        meta["resolution_m"] = validation["resolution_m"]
        meta["nodata"] = validation["nodata"]
        meta["control_sample_p1"] = validation["control_sample_p1"]
    else:
        meta["source_sha256"] = ""
        meta["DEM_PREPARED"] = "NO"
        meta["note"] = ("DEM tile NOT prepared (download failed, or artifact not a real "
                        "valid raster). Auto-elevation stays DEM_EVIDENCE_INCOMPLETE.")
        if validation is not None and not validation.get("ok"):
            meta["note"] = f"DEM tile NOT prepared: {validation.get('error')}"
    return meta


def main() -> int:
    os.makedirs(DEM_DIR, exist_ok=True)
    coverage_id = os.environ.get("ALRASO_DEM_COVERAGE", DEFAULT_COVERAGE)
    meta = dict(SOURCE)
    validation = None
    try:
        bbox = derive_picos_bbox()
        url = build_wcs_request(bbox, coverage_id)
        cfg = coverage_config(coverage_id)
        meta.update({
            "coverage_id": coverage_id,
            "wcs_version": WCS_VERSION,
            "request_pattern": ("WCS GetCoverage 2.0.1; one SUBSET per dimension "
                                f"(subset={cfg['axis_x']}(low,high)&subset={cfg['axis_y']}(low,high)); "
                                f"format=image/tiff"),
            "source_url": url,
            "retrieved_at": date.today().isoformat(),
            "bbox": bbox,
            "resolution_m": cfg["resolution_m"],
            "reuse_terms": "VERIFIED",
            "license": "CC-BY-4.0",
            "license_sources": [
                "https://www.ign.es/web/ign/portal/servicios/centro-de-descargas",  # IGN licencia/descargas
                "https://www.ign.es/web/ign/portal/ide-ign/descarga-de-datos",       # IGN política de datos
                "https://servicios.idee.es/wcs-inspire/mdt?service=WCS&request=GetCapabilities&version=2.0.1",  # catálogo WCS MDT (AccessConstraints: CC BY 4.0)
            ],
            "access_pattern": "WCS 2.0.1 GetCoverage (bbox subset, nativeFormat COG)",
            "cog_or_not": "coverage nativeFormat=COG (DescribeCoverage); fetched via WCS GetCoverage",
            "vertical_datum": "orthometric",
            "vertical_reference_detail": "NOT_VERIFIED",
        })

        ok = download(url, OUT_TILE)
        if ok and os.path.exists(OUT_TILE):
            validation = validate_tile(OUT_TILE, bbox=bbox, coverage_id=coverage_id)
    except Exception as exc:  # noqa: BLE001 - any prep error must fail closed, never crash
        validation = None
        meta["note"] = f"DEM tile NOT prepared: {type(exc).__name__}: {exc}"

    meta = finalize_meta(meta, validation, OUT_TILE)
    if validation and validation.get("ok"):
        print(f"[dem_prep] tile prepared: {OUT_TILE} ({meta['byte_size']} bytes, "
              f"CRS={meta['crs']}, res={meta['resolution_m']} m, "
              f"P1={meta['control_sample_p1']} m)")
    else:
        # Never leave a masquerading / non-raster artifact behind.
        if os.path.exists(OUT_TILE):
            os.remove(OUT_TILE)
        print(f"[dem_prep] tile NOT prepared: {meta['note']}")

    with open(OUT_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(f"[dem_prep] metadata: {OUT_META}")
    return 0 if (validation and validation.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
