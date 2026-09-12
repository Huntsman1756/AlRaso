#!/usr/bin/env python3
"""M8.1 Official cross-check: OSM protected-area relations vs OAPN WFS (digest-only).

Fetches the OAPN WFS layer `view_red_oapn_limite_pn`, computes official
park areas in memory, compares with OSM relation areas from the fixtures,
and writes a digest-only results file.

Guard: |delta_pct| > 5 -> STOP and report (wrong relation suspected).
Never writes official geometry coordinates into any output file —
only digests, areas and metadata.

Usage:
    python tooling/m81_official_crosscheck.py
"""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

RESULTS = Path(__file__).parent / "m81_official_crosscheck_results.json"
ORDESA_FIXTURE = Path(__file__).parent / "pa_ordesa_overpass.json"
PICOS_FIXTURE = Path(__file__).parent / "pa_picos_overpass.json"
OAPN_WFS = "https://sigred.oapn.es/geoserverOAPN/ows"
OAPN_LAYER = "LimitesParquesNacionalesZPP:view_red_oapn_limite_pn"
OAPN_URL = (
    f"{OAPN_WFS}?service=WFS&version=2.0.0&request=GetFeature"
    f"&typeName={urllib.parse.quote(OAPN_LAYER)}"
    f"&outputFormat=application/json"
)

ORDESA_NAMES = ["ordesa", "monte perdido"]
PICOS_NAMES = ["picos de europa"]

# ── Helpers ────────────────────────────────────────────────────────────────────


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_oapn(max_retries: int = 3) -> bytes:
    """Fetch OAPN WFS layer. Returns raw bytes."""
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(
            OAPN_URL, headers={"User-Agent": "AlRaso-M8.1-crosscheck"}
        )
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            return r.read()
    except Exception:
        pass
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                OAPN_URL, headers={"User-Agent": "AlRaso-M8.1-crosscheck"}
            )
            ctx2 = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=120, context=ctx2) as r:
                return r.read()
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            raise RuntimeError(
                f"OAPN WFS unreachable after {max_retries} attempts: {e}"
            ) from e


def _area_ha(geom: dict) -> float:
    """Compute area in hectares from a GeoJSON-like geometry dict using shapely.

    Handles both WGS84 (lon/lat) and projected CRS (e.g. EPSG:25830 UTM).
    If coordinates look projected (values > 1000), use them directly in m2.
    Otherwise reproject to EPSG:6933 for accurate area.
    """
    from shapely.geometry import shape
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    g = shape(geom)
    if g.is_empty:
        return 0.0

    # Check if coordinates are projected (UTM-like, values > 1000)
    projected = False
    try:
        sample = list(g.exterior.coords)[0]
    except AttributeError:
        # MultiPolygon: check first sub-polygon's exterior
        for pg in g.geoms:
            try:
                sample = list(pg.exterior.coords)[0]
                break
            except AttributeError:
                continue
        else:
            sample = (0, 0)

    if len(sample) >= 2 and (abs(sample[0]) > 1000 or abs(sample[1]) > 1000):
        return g.area / 10000.0  # m² -> ha

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
    g_aea = shp_transform(transformer.transform, g)
    return g_aea.area / 10000.0  # m² -> ha


def _find_park_feature(
    features: list[dict], name_patterns: list[str]
) -> dict | None:
    """Find the OAPN feature matching one of the name patterns (case-insensitive)."""
    for f in features:
        props = f.get("properties") or {}
        name = str(props.get("Nombre", "")).lower()
        for pattern in name_patterns:
            if pattern in name:
                return f
    return None


def _build_geojson_from_overpass_rel(
    rel: dict, fixture: dict
) -> dict | None:
    """Build a GeoJSON MultiPolygon from an Overpass relation fixture.

    Overpass `out geom` adds a `geometry` field to each element:
      - nodes: {lat, lon}
      - ways: [{lat, lon}, ...]  (list of coordinate dicts)

    Chains outer way segments into rings, and handles inner ways as holes.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    ways_map: dict[int, dict] = {}
    for e in fixture.get("elements", []):
        if e.get("type") == "way":
            ways_map[e["id"]] = e

    # Collect outer and inner members
    outer_members = [
        m for m in rel.get("members", [])
        if m.get("role") == "outer" and m.get("type") == "way"
        and m["ref"] in ways_map
    ]
    inner_members = [
        m for m in rel.get("members", [])
        if m.get("role") == "inner" and m.get("type") == "way"
        and m["ref"] in ways_map
    ]

    # Build outer rings by chaining contiguous outer way segments
    outer_rings: list[list[list[float]]] = []
    i = 0
    while i < len(outer_members):
        m = outer_members[i]
        if m["type"] != "way" or m["ref"] not in ways_map:
            i += 1
            continue
        chain: list[list[float]] = []
        while i < len(outer_members):
            m = outer_members[i]
            if m["type"] != "way" or m["ref"] not in ways_map:
                break
            w = ways_map[m["ref"]]
            geom = w.get("geometry", [])
            coords = [[c.get("lon", 0), c.get("lat", 0)] for c in geom]
            if chain:
                coords = coords[1:]  # skip first point (connects)
            chain.extend(coords)
            i += 1
        if chain and chain[0] != chain[-1]:
            chain.append(chain[0])
        if len(chain) >= 4:
            outer_rings.append(chain)

    # Build inner rings (holes)
    inner_rings: list[list[list[float]]] = []
    for m in inner_members:
        if m["type"] != "way" or m["ref"] not in ways_map:
            continue
        w = ways_map[m["ref"]]
        geom = w.get("geometry", [])
        coords = [[c.get("lon", 0), c.get("lat", 0)] for c in geom]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        if len(coords) >= 4:
            inner_rings.append(coords)

    if not outer_rings:
        return None

    # Build polygons with holes
    polygons = []
    for outer in outer_rings:
        holes = []
        for inner in inner_rings:
            try:
                p_outer = Polygon(outer)
                p_inner = Polygon(inner)
                if p_outer.contains(p_inner) or p_outer.touches(p_inner):
                    holes.append(inner)
            except Exception:
                pass
        try:
            if holes:
                poly = Polygon(outer, holes).buffer(0)
            else:
                poly = Polygon(outer).buffer(0)
            if poly.is_valid and not poly.is_empty:
                polygons.append(poly)
        except Exception:
            pass

    if not polygons:
        return None

    if len(polygons) == 1:
        # Single polygon -> GeoJSON Polygon
        poly = polygons[0]
        outer_coords = [list(c) for c in list(poly.exterior.coords)]
        if poly.interiors:
            inner_coords = [
                [list(c) for c in h.coords] for h in poly.interiors
            ]
            coords = [outer_coords] + inner_coords
        else:
            coords = [outer_coords]
        return {"type": "Polygon", "coordinates": coords}
    else:
        # MultiPolygon
        geoms = []
        for poly in polygons:
            outer_coords = [list(c) for c in list(poly.exterior.coords)]
            if poly.interiors:
                inner_coords = [
                    [list(c) for c in h.coords] for h in poly.interiors
                ]
                geoms.append([outer_coords] + inner_coords)
            else:
                geoms.append([outer_coords])
        return {"type": "MultiPolygon", "coordinates": geoms}


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> int:
    # 1. Fetch OAPN WFS
    print("Fetching OAPN WFS layer...")
    try:
        raw_oapn = fetch_oapn()
    except Exception as e:
        print(f"ERROR: OAPN WFS unreachable: {e}", file=sys.stderr)
        return 1

    oapn_sha = _sha256_bytes(raw_oapn)
    oapn_data = json.loads(raw_oapn.decode("utf-8", "replace"))
    oapn_features = oapn_data.get("features", [])
    print(f"  OAPN features: {len(oapn_features)}, sha256={oapn_sha[:16]}...")

    # 2. Load OSM fixtures
    with open(ORDESA_FIXTURE, encoding="utf-8") as f:
        ordesa_fixture = json.load(f)
    with open(PICOS_FIXTURE, encoding="utf-8") as f:
        picos_fixture = json.load(f)

    # 3. Find OSM relation elements and build geometries
    def find_relation(elements: list[dict], rel_id: str) -> dict | None:
        for e in elements:
            if e.get("type") == "relation" and str(e["id"]) == str(rel_id):
                return e
        return None

    results: dict = {}

    # Ordesa
    ordesa_rel = find_relation(
        ordesa_fixture.get("elements", []), "10036292"
    )
    if ordesa_rel is None:
        print(
            "ERROR: Ordesa relation 10036292 not found in fixture",
            file=sys.stderr,
        )
        return 1

    ordesa_geom = _build_geojson_from_overpass_rel(ordesa_rel, ordesa_fixture)
    ordesa_area_ha = _area_ha(ordesa_geom) if ordesa_geom else 0.0
    print(f"  Ordesa OSM relation area: {ordesa_area_ha:.2f} ha")

    # Picos
    picos_rel = find_relation(
        picos_fixture.get("elements", []), "2401595"
    )
    if picos_rel is None:
        print(
            "ERROR: Picos relation 2401595 not found in fixture",
            file=sys.stderr,
        )
        return 1

    picos_geom = _build_geojson_from_overpass_rel(picos_rel, picos_fixture)
    picos_area_ha = _area_ha(picos_geom) if picos_geom else 0.0
    print(f"  Picos OSM relation area: {picos_area_ha:.2f} ha")

    # 4. Find official park features and compute areas
    ordesa_official = _find_park_feature(oapn_features, ORDESA_NAMES)
    picos_official = _find_park_feature(oapn_features, PICOS_NAMES)

    ordesa_official_area_ha = 0.0
    picos_official_area_ha = 0.0

    if ordesa_official:
        ordesa_official_area_ha = _area_ha(ordesa_official["geometry"])
        print(
            f"  Ordesa OAPN official area: {ordesa_official_area_ha:.2f} ha"
        )
    else:
        print("  WARNING: Ordesa not found in OAPN layer")

    if picos_official:
        picos_official_area_ha = _area_ha(picos_official["geometry"])
        print(
            f"  Picos OAPN official area: {picos_official_area_ha:.2f} ha"
        )
    else:
        print("  WARNING: Picos not found in OAPN layer")

    # 5. Compute deltas
    def delta_pct(osm_area: float, official_area: float) -> float | None:
        if official_area == 0:
            return None
        return ((osm_area - official_area) / official_area) * 100.0

    ordesa_delta = delta_pct(ordesa_area_ha, ordesa_official_area_ha)
    picos_delta = delta_pct(picos_area_ha, picos_official_area_ha)

    print(f"  Ordesa delta: {ordesa_delta}")
    print(f"  Picos delta: {picos_delta}")

    # 6. Guard: |delta_pct| > 5
    guard_ok = True
    if ordesa_delta is not None and abs(ordesa_delta) > 5:
        print(
            f"STOP: Ordesa delta {ordesa_delta:.2f}% exceeds 5% threshold",
            file=sys.stderr,
        )
        guard_ok = False
    if picos_delta is not None and abs(picos_delta) > 5:
        print(
            f"STOP: Picos delta {picos_delta:.2f}% exceeds 5% threshold",
            file=sys.stderr,
        )
        guard_ok = False

    if not guard_ok:
        print(
            "WRONG RELATION suspected — STOP. Review manually.",
            file=sys.stderr,
        )
        return 3

    # 7. Build results
    now = datetime.now(timezone.utc).isoformat()
    self_sha = _sha256_file(Path(__file__))

    output = {
        "script": "m81_official_crosscheck.py",
        "script_sha256": self_sha,
        "retrieved_at": now,
        "official_source_url": OAPN_URL,
        "official_redistribution": "NO (digest-only)",
        "parks": {
            "ordesa": {
                "osm_relation_id": "relation/10036292",
                "osm_area_ha": round(ordesa_area_ha, 2),
                "official_area_ha": round(ordesa_official_area_ha, 2),
                "delta_pct": (
                    round(ordesa_delta, 4)
                    if ordesa_delta is not None
                    else None
                ),
                "official_response_sha256": oapn_sha,
                "official_source_url": OAPN_URL,
                "official_redistribution": "NO (digest-only)",
            },
            "picos": {
                "osm_relation_id": "relation/2401595",
                "osm_area_ha": round(picos_area_ha, 2),
                "official_area_ha": round(picos_official_area_ha, 2),
                "delta_pct": (
                    round(picos_delta, 4)
                    if picos_delta is not None
                    else None
                ),
                "official_response_sha256": oapn_sha,
                "official_source_url": OAPN_URL,
                "official_redistribution": "NO (digest-only)",
            },
        },
        "guard": {
            "threshold_pct": 5,
            "passed": guard_ok,
        },
    }

    RESULTS.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Results written to {RESULTS}")

    # Print summary table
    print("\n=== Cross-check summary ===")
    print(
        f"{'Park':<10} {'OSM (ha)':>10} "
        f"{'Official (ha)':>14} {'Delta%':>10}"
    )
    print("-" * 46)
    for park_name in ("ordesa", "picos"):
        p = output["parks"][park_name]
        print(
            f"{park_name:<10} "
            f"{p['osm_area_ha']:>10.2f} "
            f"{p['official_area_ha']:>14.2f} "
            f"{p['delta_pct']:>9.2f}%"
        )
    print(f"\nOfficial sha256: {oapn_sha}")
    print(f"Guard: {'PASS' if guard_ok else 'FAIL'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())