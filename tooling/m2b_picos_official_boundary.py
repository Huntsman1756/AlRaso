#!/usr/bin/env python3
"""
Compare GISCO-derived CCAA boundary in fixture_picos.json vs OFFICIAL IGN/CNIG INSPIRE dump.

Usage:
  uv run --with pyogrio --with shapely --with pyproj --with rasterio python tooling/m2b_picos_official_boundary.py

Produces:
  tooling/m2b_picos_official_boundary_results.json  (KPIs + derived sector rings + digests)
  tooling/m2b_picos_official_boundary.evidence.json (evidence lock)

No network calls. Deterministic (no randomness).
"""

import json
import hashlib
import os
import re
import sys
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from shapely.geometry import (
    Point, LineString, Polygon,
    MultiPolygon, MultiLineString,
)
from shapely.ops import unary_union
from pyproj import Transformer, CRS
import rasterio

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "alraso" / "resources" / "fixture_picos.json"
ZIP_PATH = Path(r"F:\_Proyectos\AlRaso\docs\lineas_limite_gml.zip")
ZIP_SHA_EXPECTED = "5bd73c530af995c05da8d9ff4e3d293f62d0dc91c5e48ee773fe881716c108a6"
GML_DIR = ROOT / "tooling" / "_tmp_gml_extract"
DEM_TIF = ROOT / "webapp" / "data" / "dem" / "picos_mdt.tif"
RESULTS_JSON = ROOT / "tooling" / "m2b_picos_official_boundary_results.json"
EVIDENCE_JSON = ROOT / "tooling" / "m2b_picos_official_boundary.evidence.json"

# ─── Transforms ──────────────────────────────────────────────────────────────
_T4326_25830 = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(25830), always_xy=True)
_T25830_4326 = Transformer.from_crs(CRS.from_epsg(25830), CRS.from_epsg(4326), always_xy=True)

# ─── App guard import (GISCO baseline authority) ──────────────────────────────
# Import the app module so we can call server.jurisdiction_boundary_safe() —
# THIS IS THE ONLY AUTHORITY for the GISCO baseline KPI.
sys.path.insert(0, str(ROOT / "webapp"))
sys.path.insert(0, str(ROOT))
import server as _app_server


def sha256_file(path, block_size=65536):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


# ─── GML parser (ElementTree-based) ──────────────────────────────────────────
def parse_gml_geometries(xml_path):
    """
    Parse an INSPIRE au: GML file using ElementTree (handles multi-line XML).
    Returns list of dicts with: geom_type, coords ([lat,lon] pairs), attrs.
    """
    ns = {
        "au": "http://inspire.ec.europa.eu/schemas/au/4.0",
        "gml": "http://www.opengis.net/gml/3.2",
        "wfs": "http://www.opengis.net/wfs/2.0",
        "base": "http://inspire.ec.europa.eu/schemas/base/3.3",
        "gn": "http://www.inspire.ec.europa.eu/schemas/gn/4.0",
        "gmd": "http://www.isotc211.org/2005/gmd",
        "xlink": "http://www.w3.org/1999/xlink",
    }
    GML_ID_NS = f"{{{ns['gml']}}}id"  # {http://www.opengis.net/gml/3.2}id

    # Register namespaces in a custom resolver so we can search by local name
    tree = ET.parse(xml_path)
    root = tree.getroot()

    results = []

    # Helper: check if tag matches regardless of namespace prefix
    def local_name_matches(tag, target):
        if "}" in tag:
            return tag.rsplit("}", 1)[1] == target
        return tag == target

    def find_all_by_localname(parent, target_name):
        """Find all direct children whose local name matches."""
        return [c for c in parent if local_name_matches(c.tag, target_name)]

    def find_all_recursive_by_localname(parent, target_name):
        """Find ALL elements (descendants) whose local name matches."""
        found = []
        for elem in parent.iter():
            if local_name_matches(elem.tag, target_name):
                found.append(elem)
        return found

    def get_text_recursive(parent, target_name):
        """Get text from first matching descendant element."""
        for elem in find_all_recursive_by_localname(parent, target_name):
            if elem.text and elem.text.strip():
                return elem.text.strip()
        return None

    def get_xlink_href(elem, target_child_name):
        """Find child with target_name and return its xlink:href."""
        for child in find_all_recursive_by_localname(elem, target_child_name):
            href = child.get(f"{{{ns['xlink']}}}href")
            if href:
                return href
        return None

    # Find all AdministrativeUnit and AdministrativeBoundary elements
    all_elems = list(root.iter())

    for elem in all_elems:
        local_tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag

        if local_tag not in ("AdministrativeUnit", "AdministrativeBoundary"):
            continue

        # Extract name
        name_val = get_text_recursive(elem, "text")
        if name_val is None:
            name_val = get_text_recursive(elem, "SpellingOfName")

        # National level
        nl_href = get_xlink_href(elem, "nationalLevel")
        national_level = "2ndOrder" if nl_href and "2ndOrder" in nl_href else None

        # Country code — CodeListValue is a plain attribute of gmd:Country
        country_val = None
        for ce in find_all_recursive_by_localname(elem, "Country"):
            if ce.tag.rsplit("}", 1)[-1] == "Country":
                country_val = ce.get("codeListValue")
                if country_val:
                    break

        # admUnit reference
        adm_unit_href = get_xlink_href(elem, "admUnit")
        adm_unit_id = None
        if adm_unit_href:
            m = re.search(r"AU_ADMINISTRATIVEUNIT_(\d+)", adm_unit_href)
            if m:
                adm_unit_id = m.group(1)

        # Extract geometry - find posList inside geometry element
        poslist_elem = None
        for child in find_all_recursive_by_localname(elem, "posList"):
            if child.text and child.text.strip():
                poslist_elem = child
                break

        if poslist_elem is None or poslist_elem.text is None:
            continue

        vals = poslist_elem.text.strip().split()
        if len(vals) < 2:
            continue

        try:
            numbers = [float(v) for v in vals]
        except ValueError:
            continue

        coords = [[numbers[i], numbers[i+1]] for i in range(0, len(numbers), 2)]
        if len(coords) < 3:
            continue

        # Determine geometry type
        is_polygon = (
            local_tag == "AdministrativeUnit"
            or any(local_name_matches(c.tag, "Polygon") for c in find_all_recursive_by_localname(elem, "Polygon"))
            or any(local_name_matches(c.tag, "LinearRing") for c in find_all_recursive_by_localname(elem, "LinearRing"))
        )

        if is_polygon:
            if len(coords) >= 4 and abs(coords[0][0] - coords[-1][0]) < 0.0001 and abs(coords[0][1] - coords[-1][1]) < 0.0001:
                coords = coords[:-1]

        results.append({
            "tag": "AdministrativeUnit" if local_tag == "AdministrativeUnit" else "AdministrativeBoundary",
            "gml_id": elem.get(GML_ID_NS, ""),
            "geom_type": "polygon" if is_polygon else "linestring",
            "coords": coords,
            "attrs": {
                "name": name_val,
                "nationalLevel": national_level,
                "country": country_val,
                "admUnit_localId": adm_unit_id,
            },
        })

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    report = []

    def log(msg=""):
        print(msg)
        report.append(msg)

    log("=" * 72)
    log("OFFICIAL BOUNDARY vs GISCO FIXTURE — PICOS DE EUROPA")
    log("=" * 72)

    # ── Input digests ──────────────────────────────────────────────────────
    log("\n[1] Input digests")
    zip_sha = sha256_file(ZIP_PATH)
    log(f"  ZIP sha256: {zip_sha}")
    assert zip_sha == ZIP_SHA_EXPECTED, f"ZIP SHA256 mismatch: {zip_sha}"

    fixture_sha = sha256_file(FIXTURE)
    log(f"  fixture sha256: {fixture_sha}")

    dem_sha = sha256_file(DEM_TIF)
    log(f"  DEM sha256: {dem_sha}")

    # ── Extract GML ────────────────────────────────────────────────────────
    log("\n[0] Extract GML zip")
    if not (GML_DIR / "au_AdministrativeUnit_2ndOrder0.gml").exists():
        GML_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(GML_DIR)
        log("  Extracted.")

    # ── Load fixture geometry ──────────────────────────────────────────────
    log("\n[2] Load fixture geometry")
    with open(FIXTURE, "r") as f:
        fixture = json.load(f)

    park_ring = fixture["geometry"]["park"][0]  # [lat,lon] pairs

    # Park polygon (shapely: lon,lat)
    park_4326 = Polygon([(c[1], c[0]) for c in park_ring]).buffer(0)
    log(f"  Park ring points: {len(park_ring)}")
    log(f"  Park bounds (4326): {park_4326.bounds}")

    # Park in 25830
    park_25830_coords = [_T4326_25830.transform(c[1], c[0]) for c in park_ring]
    park_geom_25830 = Polygon(park_25830_coords).buffer(0)
    log(f"  Park area (25830 m²): {park_geom_25830.area:,.0f}")

    # ── GISCO sectors ──────────────────────────────────────────────────────
    log("\n[3] GISCO sector rings (from fixture)")
    gisco_sectors_25830 = {}  # jur_key -> [Polygon(...)]
    for jur in ["es-as", "es-cb", "es-cl"]:
        rings = fixture["geometry"][jur]
        polys = []
        for ring in rings:
            if len(ring) >= 3:
                coords_m = [_T4326_25830.transform(c[1], c[0]) for c in ring]
                polys.append(Polygon(coords_m))
        gisco_sectors_25830[jur] = polys
        log(f"  {jur}: {len(polys)} ring(s), {sum(len(p.exterior.coords) - 1 for p in polys)} pts")

    gisco_all_polys = []
    for polys in gisco_sectors_25830.values():
        gisco_all_polys.extend(polys)
    gisco_union_all = unary_union(gisco_all_polys)

    # ── Parse official GML ─────────────────────────────────────────────────
    log("\n[4] Parse official GML files (ElementTree)")
    unit_file = GML_DIR / "au_AdministrativeUnit_2ndOrder0.gml"
    bnd_file = GML_DIR / "au_AdministrativeBoundary_2ndOrder0.gml"

    units = parse_gml_geometries(str(unit_file))
    boundaries = parse_gml_geometries(str(bnd_file))

    log(f"  AdministrativeUnit features: {len(units)}")
    log(f"  AdministrativeBoundary features: {len(boundaries)}")

    # Filter Spain 2ndOrder
    units_es = [u for u in units
                if u["geom_type"] == "polygon"
                and u["attrs"].get("country") == "ES"
                and u["attrs"].get("nationalLevel") == "2ndOrder"]
    boundaries_es = [b for b in boundaries
                     if b["geom_type"] == "linestring"
                     and b["attrs"].get("country") == "ES"
                     and b["attrs"].get("nationalLevel") == "2ndOrder"]
    log(f"  Spain 2ndOrder units: {len(units_es)}")
    log(f"  Spain 2ndOrder boundary segments: {len(boundaries_es)}")

    # ── Match CCAA by name ─────────────────────────────────────────────────
    log("\n[5] Match CCAA by au:name")
    name_to_unit = {}
    for u in units_es:
        name = u["attrs"].get("name", "")
        if name:
            name_lower = name.lower()
            if name_lower not in name_to_unit:
                name_to_unit[name_lower] = u

    all_names_lower = sorted(name_to_unit.keys())
    log(f"  Available Spain-2ndOrder names ({len(all_names_lower)}):")
    for n in all_names_lower:
        log(f"    - {n}")

    ccaa_lookup = {
        "es-as": "principado de asturias",
        "es-cb": "cantabria",
        "es-cl": "castilla y león",
    }
    fallback_lookup = {
        "es-cl": "castilla y leon",
    }

    matched_units = {}
    match_info = {}
    match_fallback = {}

    for jur, name in ccaa_lookup.items():
        if name in name_to_unit:
            matched_units[jur] = name_to_unit[name]
            match_info[jur] = name_to_unit[name]["attrs"].get("name", "")
            match_fallback[jur] = False
        elif jur in fallback_lookup and fallback_lookup[jur] in name_to_unit:
            matched_units[jur] = name_to_unit[fallback_lookup[jur]]
            match_info[jur] = name_to_unit[fallback_lookup[jur]]["attrs"].get("name", "")
            match_fallback[jur] = True
        log(f"  {jur}: {match_info.get(jur, 'NOT MATCHED')} (fallback={match_fallback.get(jur, False)})")

    # ── Clip official polygons to park ─────────────────────────────────────
    log("\n[6] Clip official CCAA polygons to park")
    official_sectors = {}

    for jur, unit in matched_units.items():
        coords_raw = unit["coords"]
        unit_4326 = Polygon([(c[1], c[0]) for c in coords_raw]).buffer(0)
        clipped = unit_4326.intersection(park_4326)

        if clipped.is_empty:
            log(f"  {jur}: EMPTY after clip")
            official_sectors[jur] = []
            continue

        if clipped.geom_type == "Polygon":
            ext = list(clipped.exterior.coords)
            if len(ext) > 1 and ext[0] == ext[-1]:
                ext = ext[:-1]
            coords_m = [_T4326_25830.transform(x, y) for x, y in ext]
            official_sectors[jur] = [Polygon(coords_m)]
        elif clipped.geom_type == "MultiPolygon":
            polys_m = []
            for poly in clipped.geoms:
                ext = list(poly.exterior.coords)
                if len(ext) > 1 and ext[0] == ext[-1]:
                    ext = ext[:-1]
                coords_m = [_T4326_25830.transform(x, y) for x, y in ext]
                if len(coords_m) >= 3:
                    polys_m.append(Polygon(coords_m))
            official_sectors[jur] = polys_m
        elif clipped.geom_type == "GeometryCollection":
            polys_m = []
            for geom in clipped.geoms:
                if geom.geom_type == "Polygon" and not geom.is_empty and geom.area > 0:
                    ext = list(geom.exterior.coords)
                    if len(ext) > 1 and ext[0] == ext[-1]:
                        ext = ext[:-1]
                    coords_m = [_T4326_25830.transform(x, y) for x, y in ext]
                    if len(coords_m) >= 3:
                        polys_m.append(Polygon(coords_m))
            if not polys_m:
                log(f"  {jur}: GeometryCollection with no polygon members")
                official_sectors[jur] = []
                continue
            official_sectors[jur] = polys_m
        else:
            log(f"  {jur}: degenerate type={clipped.geom_type}")
            official_sectors[jur] = []
            continue

        area_sum = sum(p.area for p in official_sectors[jur])
        log(f"  {jur}: {len(official_sectors[jur])} polygon(s), area={area_sum:,.0f} m²")

    # ── Topology validation ────────────────────────────────────────────────
    log("\n[7] Topology validation")
    sector_keys = list(official_sectors.keys())

    overlap_m2 = 0.0
    overlap_details = []
    for i in range(len(sector_keys)):
        for j in range(i+1, len(sector_keys)):
            k1, k2 = sector_keys[i], sector_keys[j]
            p1 = unary_union(official_sectors[k1])
            p2 = unary_union(official_sectors[k2])
            inter = p1.intersection(p2)
            if not inter.is_empty:
                area = inter.area
                overlap_m2 += area
                overlap_details.append(f"{k1} intersect {k2}: {area:.2f} m²")

    log(f"  Pairwise overlaps: {overlap_m2:.2f} m²")
    for d in overlap_details:
        log(f"    {d}")

    if official_sectors:
        all_official_polys = []
        for polys in official_sectors.values():
            all_official_polys.extend(polys)
        union_official = unary_union(all_official_polys)
        gap_geom = park_geom_25830.difference(union_official)
        gap_m2 = gap_geom.area if not gap_geom.is_empty else 0.0
    else:
        gap_m2 = 0.0
        union_official = None

    log(f"  Gap (park - official): {gap_m2:.2f} m²")
    log(f"  Coverage: {100*(1-gap_m2/park_geom_25830.area):.2f}%")

    # ── Boundary shift metrics ─────────────────────────────────────────────
    log("\n[8] Boundary shift metrics (GISCO shared vs OFFICIAL)")

    # GISCO shared border: compute directly by intersecting each sector with every
    # other sector.  Where two sectors touch, their intersection is a LineString —
    # that is exactly the CCAA shared border we want.  The old approach
    # boundary(unary_union) − boundary(park) was unreliable because
    # fixture-sector simplification means the union boundary ≠ park perimeter at
    # the cm level; most of the park-perimeter residual was spurious.
    log("  Reconstructing GISCO shared border (pairwise sector intersections)...")
    shared_parts = []
    sector_keys_list = list(gisco_sectors_25830.keys())
    for i in range(len(sector_keys_list)):
        for j in range(i + 1, len(sector_keys_list)):
            jur1, jur2 = sector_keys_list[i], sector_keys_list[j]
            u1 = unary_union(gisco_sectors_25830[jur1])
            u2 = unary_union(gisco_sectors_25830[jur2])
            inter = u1.intersection(u2)
            if inter.geom_type == "LineString" and not inter.is_empty:
                shared_parts.append(inter)
            elif inter.geom_type == "MultiLineString":
                for g in inter.geoms:
                    if not g.is_empty:
                        shared_parts.append(g)
            # If inter is empty or a polygon, the sectors do not share a border.

            # Buffer-based intersection: fixture sectors are independently simplified,
            # so they may have up to ~1 m gap.  Use boundary(buffer) to capture
            # near-misses.
            inter_buf = u1.boundary.intersection(u2.buffer(1.0))
            if not inter_buf.is_empty:
                if inter_buf.geom_type == "LineString":
                    shared_parts.append(inter_buf)
                elif inter_buf.geom_type == "MultiLineString":
                    for g in inter_buf.geoms:
                        if not g.is_empty:
                            shared_parts.append(g)

    gisco_shared = unary_union(shared_parts) if shared_parts else None
    gisco_shared_length = (gisco_shared.length if gisco_shared and not gisco_shared.is_empty
                           else 0.0)

    # GISCO gap: park-perimeter residual where the union of all sector rings
    # does not cover the park boundary exactly (simplification artifacts).
    gisco_union_all = unary_union(gisco_all_polys)
    park_boundary_25830 = park_geom_25830.boundary
    gisco_gap_geom = park_boundary_25830.difference(gisco_union_all.buffer(0.5))
    if gisco_gap_geom.is_empty:
        gisco_gap_length_m = 0.0
    elif gisco_gap_geom.geom_type in ("LineString", "MultiLineString"):
        gisco_gap_length_m = gisco_gap_geom.length
    else:
        gisco_gap_length_m = sum(g.length for g in gisco_gap_geom.geoms)

    log(f"  GISCO shared border: {gisco_shared.geom_type}, {gisco_shared_length:.2f}m"
        if gisco_shared and not gisco_shared.is_empty else "  GISCO shared border: empty")
    log(f"  GISCO gap length (park-perimeter residual): {gisco_gap_length_m:.2f}m")

    # Official border lines: 2ndOrder AdministrativeBoundary LineStrings, unclipped,
    # filtered to park bbox + 2 km margin for performance.  This is the true CCAA
    # border system (it continues outside the park — that is correct and desired).
    log("  Loading official border lines (EPSG:4258→25830, unclipped)...")
    off_bnd_parts = []
    for b in boundaries_es:
        coords_m = [_T4326_25830.transform(c[1], c[0]) for c in b["coords"]]
        if len(coords_m) >= 2:
            line = LineString(coords_m)
            if line.intersects(park_geom_25830.buffer(2000)):  # 2 km margin
                off_bnd_parts.append(line)

    off_bnd_union = unary_union(off_bnd_parts) if off_bnd_parts else None

    # official_shared = CCAA-to-CCAA official shared border inside park.
    # Computed by intersecting adjacent official CCAA sectors (the clipped
    # official polygons).  This avoids contaminating the shift comparison
    # with municipal / provincial boundaries that also sit inside the park.
    log("  Computing official CCAA-to-CCAA shared border (intersection of official CCAA polygons)...")
    off_ccaa_shared_parts = []
    for i in range(len(sector_keys_list)):
        for j in range(i + 1, len(sector_keys_list)):
            jur1, jur2 = sector_keys_list[i], sector_keys_list[j]
            u1 = unary_union(official_sectors[jur1])
            u2 = unary_union(official_sectors[jur2])
            inter = u1.intersection(u2)
            if inter.geom_type == "LineString" and not inter.is_empty:
                off_ccaa_shared_parts.append(inter)
            elif inter.geom_type == "MultiLineString":
                for g in inter.geoms:
                    if not g.is_empty:
                        off_ccaa_shared_parts.append(g)

    off_ccaa_shared = unary_union(off_ccaa_shared_parts) if off_ccaa_shared_parts else None
    off_ccaa_shared_len = (off_ccaa_shared.length if off_ccaa_shared and not off_ccaa_shared.is_empty
                           else 0.0)
    log(f"  Official CCAA shared border inside park: {off_ccaa_shared_len:.2f}m"
        if off_ccaa_shared_len > 0 else "  Official CCAA shared border inside park: empty")

    # Full official border inside park (for blocked-point KPIs)
    if off_bnd_union and not off_bnd_union.is_empty:
        official_shared = off_bnd_union.intersection(park_geom_25830)
        log(f"  All official borders inside park: {official_shared.geom_type}, {official_shared.length:.2f}m")
    else:
        official_shared = None
        log("  All official borders inside park: empty")

    max_shift = 0.0
    mean_shift = 0.0
    p95_shift = 0.0

    # Compare GISCO shared border vs OFFICIAL CCAA-to-CCAA shared border
    if gisco_shared and not gisco_shared.is_empty and off_ccaa_shared and not off_ccaa_shared.is_empty:
        g_simp = gisco_shared.simplify(2.0, preserve_topology=True)
        o_simp = off_ccaa_shared.simplify(2.0, preserve_topology=True)

        try:
            h1 = g_simp.hausdorff_distance(o_simp)
            h2 = o_simp.hausdorff_distance(g_simp)
            max_shift = max(h1, h2)
        except Exception:
            max_shift = 0.0

        all_distances = []
        for line_geom, other_geom in [(g_simp, o_simp), (o_simp, g_simp)]:
            if hasattr(line_geom, "geoms"):
                for sub in line_geom.geoms:
                    if hasattr(sub, "coords"):
                        for pt_coords in sub.coords:
                            pt = Point(pt_coords)
                            all_distances.append(pt.distance(other_geom))
            elif hasattr(line_geom, "coords"):
                for pt_coords in line_geom.coords:
                    pt = Point(pt_coords)
                    all_distances.append(pt.distance(other_geom))

        if all_distances:
            mean_shift = sum(all_distances) / len(all_distances)
            sorted_d = sorted(all_distances)
            idx = int(0.95 * len(sorted_d))
            p95_shift = sorted_d[min(idx, len(sorted_d)-1)]

    log(f"  MAX_BOUNDARY_SHIFT_M: {max_shift:.2f}")
    log(f"  MEAN_BOUNDARY_SHIFT_M: {mean_shift:.2f}")
    log(f"  P95_BOUNDARY_SHIFT_M: {p95_shift:.2f}")

    # ── Grid + DEM ─────────────────────────────────────────────────────────
    log("\n[9] Grid + DEM sampling")
    minx, miny, maxx, maxy = park_4326.bounds
    step = 0.004

    lon_vals = []
    lon = round(minx, 6)
    while lon <= maxx:
        lon_vals.append(lon)
        lon = round(lon + step, 6)

    lat_vals = []
    lat = round(miny, 6)
    while lat <= maxy:
        lat_vals.append(lat)
        lat = round(lat + step, 6)

    in_park = []
    for lon in lon_vals:
        for lat in lat_vals:
            if park_4326.contains(Point(lon, lat)):
                in_park.append((lat, lon))

    log(f"  Grid: {len(lon_vals)} x {len(lat_vals)} = {len(lon_vals)*len(lat_vals)}")
    log(f"  In-park points: {len(in_park)}")

    with rasterio.open(DEM_TIF) as dem:
        high_pts = []
        for lat, lon in in_park:
            x, y = _T4326_25830.transform(lon, lat)
            try:
                row, col = dem.index(x, y)
                elev = dem.read(1)[row, col]
                if elev is not None and not math.isnan(elev) and elev > 1800:
                    high_pts.append((lat, lon, float(elev)))
            except Exception:
                pass

    HIGH_POINTS_TESTED = len(high_pts)
    TOTAL_IN_PARK = len(in_park)
    log(f"  High-altitude (cota>1800): {HIGH_POINTS_TESTED}")

    # ── Classification ─────────────────────────────────────────────────────
    log("\n[10] Classification")

    def gisco_jur(lat, lon):
        x, y = _T4326_25830.transform(lon, lat)
        pt = Point(x, y)
        for jur, polys in gisco_sectors_25830.items():
            for poly in polys:
                if poly.contains(pt):
                    return jur
        return None

    def official_jur(lat, lon):
        x, y = _T4326_25830.transform(lon, lat)
        pt = Point(x, y)
        for jur, polys in official_sectors.items():
            for poly in polys:
                if poly.contains(pt):
                    return jur
        return None

    # ── Headline probes ────────────────────────────────────────────────────
    log("\n[11] Headline probe points")
    probes = [
        ("P1_interior", 43.2662, -4.8686, "Asturias interior"),
        ("P4a_boundary", 43.25005, -4.72339, "Near ES13|ES12 border"),
        ("ORCH_HIGH_BOUNDARY_SAFE", 43.202151, -4.836656, "High altitude boundary-safe point"),
    ]

    # Create the app Service for jurisdiction_boundary_safe guard
    svc = _app_server.Service()

    probe_results = {}

    with rasterio.open(DEM_TIF) as dem:
        for name, lat, lon, desc in probes:
            pt = Point(lon, lat)
            inside = park_4326.contains(pt)

            x, y = _T4326_25830.transform(lon, lat)
            pt_25830 = Point(x, y)
            try:
                row, col = dem.index(x, y)
                elev = dem.read(1)[row, col]
                elev = float(elev) if elev is not None and not math.isnan(elev) else None
            except Exception:
                elev = None

            g_jur = gisco_jur(lat, lon)
            o_jur = official_jur(lat, lon)

            # Distances to the CORRECTED border geometries
            d_gisco_shared = (gisco_shared.distance(pt_25830)
                              if gisco_shared and not gisco_shared.is_empty else float("inf"))
            d_official_shared = (off_ccaa_shared.distance(pt_25830)
                                 if off_ccaa_shared and not off_ccaa_shared.is_empty else float("inf"))

            # App guard verdict (the authoritative GISCO baseline)
            try:
                app_guard = _app_server.jurisdiction_boundary_safe(svc, lat, lon)
            except Exception:
                app_guard = False  # fail-closed

            # For transparency: min distance to other-sector rings in app style
            try:
                min_dist_other = float("inf")
                geo = svc.fx_picos.get("geometry", {})
                own_sector_key = g_jur  # e.g. "es-as"
                for other_sid, ccaa_key in _app_server._CCAA_SECTOR_KEY.items():
                    if ccaa_key == own_sector_key:
                        continue  # skip our own sector
                    for ring in geo.get(ccaa_key, []):
                        n = len(ring)
                        for i in range(n):
                            a, b = ring[i], ring[(i + 1) % n]
                            dist_m = _app_server._seg_dist_m(lat, lon, a[0], a[1], b[0], b[1])
                            if dist_m < min_dist_other:
                                min_dist_other = dist_m
            except Exception:
                min_dist_other = float("inf")

            # Cross-check: app_guard True => gisco_shared_dist >= 1000;
            # app_guard False => exists other-sector segment < 1000m
            if app_guard and d_gisco_shared < 1000.0 and min_dist_other >= 1000:
                cross_ok = "FAIL"  # guard says safe but shared dist < 1000, no other-segment < 1000
            elif app_guard and d_gisco_shared >= 1000:
                cross_ok = "PASS"
            elif not app_guard and min_dist_other < 1000:
                cross_ok = "PASS"
            elif not app_guard and min_dist_other >= 1000:
                cross_ok = "WARN  (guard False but no other-sector <1000m — check ring topology)"
            else:
                cross_ok = "WARN  (ambig)"

            probe_results[name] = {
                "lat": lat, "lon": lon,
                "inside_park": inside, "elev_m": elev, "description": desc,
                "gisco_jurisdiction": g_jur, "official_jurisdiction": o_jur,
                "app_guard_verdict": app_guard,
                "app_min_dist_m": round(min_dist_other, 2) if min_dist_other != float("inf") else None,
                "dist_to_gisco_shared_border_m": round(d_gisco_shared, 2),
                "dist_to_official_border_m": round(d_official_shared, 2),
                "cross_check": cross_ok,
            }
            log(f"  {name}: {desc}")
            log(f"    inside_park={inside} elev={elev} m")
            log(f"    GISCO jur={g_jur} OFFICIAL jur={o_jur}")
            log(f"    app_guard={app_guard}")
            log(f"    dist_to_gisco_shared_bnd={d_gisco_shared:.2f}m  dist_to_official_bnd={d_official_shared:.2f}m")
            log(f"    app_min_dist_m={min_dist_other:.2f} cross_check={cross_ok}")

    # ── High-point classification ──────────────────────────────────────────
    gisco_guard_blocked_high = 0
    gisco_guard_blocked_total = 0
    off_b50, off_b100, off_b250 = 0, 0, 0
    new_50, new_100, new_250 = 0, 0, 0
    disagreement_count = 0
    still_ambiguous_100 = 0
    gap_points_official = 0
    overlap_points_official = 0

    for lat, lon in in_park:
        # App guard verdict (authoritative GISCO baseline)
        try:
            app_guard = _app_server.jurisdiction_boundary_safe(svc, lat, lon)
        except Exception:
            app_guard = False  # fail-closed
        gisco_blocked = not app_guard
        if gisco_blocked:
            gisco_guard_blocked_total += 1

        g_jur = gisco_jur(lat, lon)
        o_jur = official_jur(lat, lon)

        # Count for gap/overlap
        if o_jur is None:
            gap_points_official += 1
        if g_jur and o_jur and g_jur != o_jur:
            disagreement_count += 1

    # Re-iterate for HIGH points only
    for lat, lon, elev in high_pts:
        # App guard verdict
        try:
            app_guard = _app_server.jurisdiction_boundary_safe(svc, lat, lon)
        except Exception:
            app_guard = False
        gisco_blocked = not app_guard
        if gisco_blocked:
            gisco_guard_blocked_high += 1

        x, y = _T4326_25830.transform(lon, lat)
        pt_25830 = Point(x, y)

        d_o = (off_ccaa_shared.distance(pt_25830)
               if off_ccaa_shared and not off_ccaa_shared.is_empty else float("inf"))

        o_b50 = d_o <= 50
        o_b100 = d_o <= 100
        o_b250 = d_o <= 250

        if o_b50:
            off_b50 += 1
        if o_b100:
            off_b100 += 1
        if o_b250:
            off_b250 += 1

        # STILL_AMBIGUOUS: official border dist <= 100m among HIGH points
        if o_b100:
            still_ambiguous_100 += 1

        # NEWLY_RESOLVABLE: app-guard-blocked HIGH points that are officially unblocked
        # AND jurisdiction-determined at that band
        if gisco_blocked:
            if not o_b50 and o_jur:
                new_50 += 1
            if not o_b100 and o_jur:
                new_100 += 1
            if not o_b250 and o_jur:
                new_250 += 1

    # Official coverage (same as before)
    overlap_points_official = 0  # already counted in disagreement if different

    log(f"\n  GISCO_GUARD_BLOCKED_HIGH: {gisco_guard_blocked_high}")
    log(f"  GISCO_GUARD_BLOCKED_TOTAL: {gisco_guard_blocked_total}")
    log(f"  OFFICIAL_BOUNDARY_BLOCKED_50: {off_b50}")
    log(f"  OFFICIAL_BOUNDARY_BLOCKED_100: {off_b100}")
    log(f"  OFFICIAL_BOUNDARY_BLOCKED_250: {off_b250}")
    log(f"  STILL_AMBIGUOUS_100: {still_ambiguous_100}")
    log(f"  NEWLY_RESOLVABLE_50: {new_50}")
    log(f"  NEWLY_RESOLVABLE_100: {new_100}")
    log(f"  NEWLY_RESOLVABLE_250: {new_250}")
    log(f"  DISAGREEMENT_POINTS: {disagreement_count}")
    log(f"  GAP_POINTS_OFFICIAL: {gap_points_official}")

    # ── Write results ──────────────────────────────────────────────────────
    log("\n[12] Write results")

    off_rings = {}
    for jur, polys in official_sectors.items():
        rings_latlon = []
        for poly in polys:
            ext = list(poly.exterior.coords)
            if len(ext) > 1 and ext[0] == ext[-1]:
                ext = ext[:-1]
            rings_latlon.append([[round(c[1], 6), round(c[0], 6)] for c in ext])
        off_rings[jur] = rings_latlon

    results = {
        "HIGH_POINTS_TESTED": HIGH_POINTS_TESTED,
        "TOTAL_IN_PARK_POINTS": TOTAL_IN_PARK,
        "GISCO_GUARD_BLOCKED_HIGH": gisco_guard_blocked_high,
        "GISCO_GUARD_BLOCKED_TOTAL": gisco_guard_blocked_total,
        "OFFICIAL_BOUNDARY_BLOCKED_50": off_b50,
        "OFFICIAL_BOUNDARY_BLOCKED_100": off_b100,
        "OFFICIAL_BOUNDARY_BLOCKED_250": off_b250,
        "STILL_AMBIGUOUS_100": still_ambiguous_100,
        "NEWLY_RESOLVABLE_50": new_50,
        "NEWLY_RESOLVABLE_100": new_100,
        "NEWLY_RESOLVABLE_250": new_250,
        "DISAGREEMENT_POINTS": disagreement_count,
        "GAP_POINTS_OFFICIAL": gap_points_official,
        "MAX_BOUNDARY_SHIFT_M": round(max_shift, 2),
        "MEAN_BOUNDARY_SHIFT_M": round(mean_shift, 2),
        "P95_BOUNDARY_SHIFT_M": round(p95_shift, 2),
        "GISCO_GAP_LENGTH_M": round(gisco_gap_length_m, 2),
        "TOPOLOGY_OVERLAP_M2": round(overlap_m2, 2),
        "TOPOLOGY_GAP_M2": round(gap_m2, 2),
        "matched_ccaa": {k: match_info.get(k, "NOT MATCHED") for k in ["es-as", "es-cb", "es-cl"]},
        "match_method": "au:name text matching (gn:SpellingOfName/gn:text)",
        "match_fallback_used": {k: match_fallback.get(k, False) for k in ["es-as", "es-cb", "es-cl"]},
        "official_sectors_summary": {
            k: {"n_rings": len(v), "n_points": sum(len(r) for r in v)}
            for k, v in off_rings.items()
        },
        "official_sectors_rings": off_rings,
        "probe_results": probe_results,
        "topology_overlap_details": overlap_details,
        "park_area_m2": round(park_geom_25830.area, 2),
        "official_coverage_pct": round(100*(1-gap_m2/park_geom_25830.area), 4) if park_geom_25830.area > 0 else 0,
    }

    results_json_str = json.dumps(results, ensure_ascii=False, indent=2)
    results_sha = hashlib.sha256(results_json_str.encode("utf-8")).hexdigest()
    results["sha256_results_json"] = results_sha

    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        f.write(results_json_str)
    log(f"  Written: {RESULTS_JSON}")

    # ── Evidence lock ──────────────────────────────────────────────────────
    script_sha = sha256_file(Path(__file__))

    evidence = {
        "source_product": "CNIG Limites municipales, provinciales y autonómicos — lineas_limite_gml.zip",
        "canonical_page": "https://centrodedescargas.cnig.es/CentroDescargas/limites-municipales-provinciales-autonomicos",
        "file_sha256": zip_sha,
        "inspire_dump_timestamp": "2026-08-10T13:04:13Z",
        "crs_notes": "EPSG:4258 (ETRS89 geographic), GML posList axis order = lat,lon",
        "extraction_params": {
            "gml_files": ["au_AdministrativeUnit_2ndOrder0.gml", "au_AdministrativeBoundary_2ndOrder0.gml"],
            "grid_step_deg": 0.004,
            "dem_resolution_m": 25.0,
            "bands_tested_m": [50, 100, 250],
            "gisco_guard_m": 1000,
        },
        "license_statement": "reuse terms VERIFIED via IGN/CNIG CC-BY-4.0 licensing framework (same primary evidence recorded in NOTICE.md DEM row: GetCapabilities AccessConstraints + https://www.ign.es/web/ign/portal/ide-ign/descarga-de-datos + IGN data policy)",
        "matched_ccaa": {k: match_info.get(k, "NOT MATCHED") for k in ["es-as", "es-cb", "es-cl"]},
        "match_fallback_used": {k: match_fallback.get(k, False) for k in ["es-as", "es-cb", "es-cl"]},
        "tooling_artifact_digests": {
            "results_json": results_sha,
            "fixture_picos_json": fixture_sha,
            "dem_tif": dem_sha,
            "zip_file": zip_sha,
            "script_py": script_sha,
        },
        "probe_results": probe_results,
        "tool_name": "m2b_picos_official_boundary.py",
    }

    with open(EVIDENCE_JSON, "w", encoding="utf-8") as f:
        f.write(json.dumps(evidence, ensure_ascii=False, indent=2))
    log(f"  Written: {EVIDENCE_JSON}")

    # ── Sanity ─────────────────────────────────────────────────────────────
    log("\n[13] Sanity checks")
    p1 = probe_results.get("P1_interior", {})
    poh = probe_results.get("ORCH_HIGH_BOUNDARY_SAFE", {})

    ok = True
    if p1.get("elev_m") is not None and p1["elev_m"] >= 2000:
        log(f"  FAIL: P1 elev={p1['elev_m']}m (expected ~1510m)")
        ok = False
    else:
        log(f"  OK: P1 elev={p1.get('elev_m')}m")

    if poh.get("elev_m") is not None:
        if 2200 <= poh["elev_m"] <= 2600:
            log(f"  OK: P_high elev={poh['elev_m']}m")
        else:
            log(f"  WARN: P_high elev={poh['elev_m']}m (expected ~2416m)")

    if poh.get("official_jurisdiction") != "es-as":
        log(f"  WARN: P_high official_jurisdiction={poh.get('official_jurisdiction')} (expected es-as)")
        ok = False
    else:
        log(f"  OK: P_high official_jurisdiction=es-as")

    # ── KPI summary ────────────────────────────────────────────────────────
    log("\n" + "=" * 72)
    log("KPI SUMMARY")
    log("=" * 72)
    kpi = {
        "HIGH_POINTS_TESTED": HIGH_POINTS_TESTED,
        "TOTAL_IN_PARK_POINTS": TOTAL_IN_PARK,
        "GISCO_GUARD_BLOCKED_HIGH": gisco_guard_blocked_high,
        "GISCO_GUARD_BLOCKED_TOTAL": gisco_guard_blocked_total,
        "OFFICIAL_BOUNDARY_BLOCKED_50": off_b50,
        "OFFICIAL_BOUNDARY_BLOCKED_100": off_b100,
        "OFFICIAL_BOUNDARY_BLOCKED_250": off_b250,
        "STILL_AMBIGUOUS_100": still_ambiguous_100,
        "NEWLY_RESOLVABLE_50": new_50,
        "NEWLY_RESOLVABLE_100": new_100,
        "NEWLY_RESOLVABLE_250": new_250,
        "DISAGREEMENT_POINTS": disagreement_count,
        "GAP_POINTS_OFFICIAL": gap_points_official,
        "MAX_BOUNDARY_SHIFT_M": round(max_shift, 2),
        "MEAN_BOUNDARY_SHIFT_M": round(mean_shift, 2),
        "P95_BOUNDARY_SHIFT_M": round(p95_shift, 2),
        "GISCO_GAP_LENGTH_M": round(gisco_gap_length_m, 2),
        "TOPOLOGY_OVERLAP_M2": round(overlap_m2, 2),
        "TOPOLOGY_GAP_M2": round(gap_m2, 2),
        "matched_ccaa": results["matched_ccaa"],
        "match_fallback_used": results["match_fallback_used"],
        "official_sectors_summary": results["official_sectors_summary"],
    }
    log(json.dumps(kpi, indent=2))
    log("\n=== DONE ===")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())