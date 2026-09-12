#!/usr/bin/env python3
"""M8.1 Protected-area builder — deterministic GeoJSON from Overpass fixtures.

Usage:
    python tooling/m81_protected_area_build.py \\
        --ordesa tooling/pa_ordesa_overpass.json \\
        --picos tooling/pa_picos_overpass.json \\
        --snapshot-date YYYY-MM-DD \\
        --out webapp/protected_areas.json [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import OrderedDict
from datetime import date, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
DISCLAIMER = (
    "Referencia cartográfica de OpenStreetMap para contexto visual; "
    "el límite mostrado NO es la delimitación legal oficial; "
    "no determina el ámbito jurídico de AlRaso."
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_tag(element: dict, key: str) -> str | None:
    tags = element.get("tags") or {}
    return tags.get(key)


# ── Geometry building ─────────────────────────────────────────────────────────


def _build_geojson_from_overpass_rel(
    rel: dict, fixture: dict
) -> dict | None:
    """Build a GeoJSON geometry from an Overpass relation fixture.

    Overpass `out geom` adds a `geometry` field to each element:
      - ways: [{lat, lon}, ...]  (list of coordinate dicts)

    Chains outer way segments into rings, handles inner ways as holes.
    """
    from shapely.geometry import Polygon

    ways_map: dict[int, dict] = {}
    for e in fixture.get("elements", []):
        if e.get("type") == "way":
            ways_map[e["id"]] = e

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

    # Chain outer way segments into rings
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
                coords = coords[1:]
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


def _vertex_count(geom: dict) -> int:
    """Count total vertices in a GeoJSON geometry.

    GeoJSON coords nesting:
      Polygon: [[[lon,lat],...], [[lon,lat],...], ...]  (outer + holes)
      MultiPolygon: [[[[lon,lat],...], ...], [[[[lon,lat],...], ...], ...]]
    Each leaf [lon,lat] is one vertex.
    """
    coords = geom.get("coordinates", [])

    def _count(lst: list) -> int:
        if not lst:
            return 0
        # If elements are lists of 2 numbers, this is a vertex list
        if len(lst) >= 1 and isinstance(lst[0], list):
            first = lst[0]
            if len(first) == 2:
                # Leaf: list of [lon, lat] pairs
                return len(lst)
            # Nested deeper
            return sum(_count(sub) for sub in lst)
        return len(lst)

    return _count(coords)


def _simplify_geom(geom: dict, tolerance: float) -> tuple[dict, int, int]:
    """Simplify a GeoJSON geometry using shapely, return (simplified, before, after)."""
    from shapely.geometry import shape
    from shapely.ops import transform as shp_transform
    from pyproj import Transformer

    g = shape(geom)
    before = 0
    if hasattr(g, "geoms"):
        before = sum(len(list(pg.coords)) for pg in g.geoms)
    elif hasattr(g, "exterior"):
        before = len(list(g.exterior.coords))
        if g.interiors:
            before += sum(len(h.coords) for h in g.interiors)
    else:
        before = len(list(g.coords)) if hasattr(g, "coords") else 0
    # Reproject to a projected CRS for simplification, simplify, reproject back
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)
    g_proj = shp_transform(transformer.transform, g)
    g_simp = g_proj.simplify(tolerance, preserve_topology=True)
    inv = Transformer.from_crs("EPSG:6933", "EPSG:4326", always_xy=True)
    g_final = shp_transform(inv.transform, g_simp)
    after = 0
    if hasattr(g_final, "geoms"):
        after = sum(len(list(pg.coords)) for pg in g_final.geoms)
    elif hasattr(g_final, "exterior"):
        after = len(list(g_final.exterior.coords))
        if g_final.interiors:
            after += sum(len(h.coords) for h in g_final.interiors)
    else:
        after = len(list(g_final.coords)) if hasattr(g_final, "coords") else 0

    # Convert back to GeoJSON
    if g_final.geom_type == "Polygon":
        outer = [list(c) for c in list(g_final.exterior.coords)]
        if g_final.interiors:
            inner = [[list(c) for c in h.coords] for h in g_final.interiors]
            return {"type": "Polygon", "coordinates": [outer] + inner}, before, after
        return {"type": "Polygon", "coordinates": [outer]}, before, after
    elif g_final.geom_type == "MultiPolygon":
        geoms = []
        for pg in g_final.geoms:
            outer = [list(c) for c in list(pg.exterior.coords)]
            if pg.interiors:
                inner = [[list(c) for c in h.coords] for h in pg.interiors]
                geoms.append([outer] + inner)
            else:
                geoms.append([outer])
        return {"type": "MultiPolygon", "coordinates": geoms}, before, after
    return geom, before, after


# ── Build ─────────────────────────────────────────────────────────────────────


def build(args: argparse.Namespace) -> dict:
    """Build the protected-area document from Overpass fixtures."""

    with open(args.ordesa, encoding="utf-8") as f:
        ordesa_data = json.load(f)
    with open(args.picos, encoding="utf-8") as f:
        picos_data = json.load(f)

    ordesa_sha = _sha256_file(Path(args.ordesa))
    picos_sha = _sha256_file(Path(args.picos))

    snapshot_date = args.snapshot_date or date.today(timezone.utc).strftime("%Y-%m-%d")

    # Overpass queries
    query_ordesa = (
        '[out:json][timeout:30];'
        '(relation(10036292);'
        'relation(10036292)->.r;'
        'way(r);'
        'node(w);'
        ');out geom;'
    )
    query_picos = (
        '[out:json][timeout:30];'
        '(relation(2401595);'
        'relation(2401595)->.r;'
        'way(r);'
        'node(w);'
        ');out geom;'
    )

    # Load cross-check results if available
    crosscheck_path = Path(__file__).parent / "m81_official_crosscheck_results.json"
    crosscheck_data: dict | None = None
    if crosscheck_path.exists():
        with open(crosscheck_path, encoding="utf-8") as f:
            crosscheck_data = json.load(f)

    # ── Select relations by ID ───────────────────────────────────────────
    def find_relation(elements: list[dict], rel_id: str) -> dict | None:
        for e in elements:
            if e.get("type") == "relation" and str(e["id"]) == str(rel_id):
                return e
        return None

    ordesa_rel = find_relation(ordesa_data.get("elements", []), "10036292")
    picos_rel = find_relation(picos_data.get("elements", []), "2401595")

    if ordesa_rel is None:
        print("ERROR: Ordesa relation 10036292 not found", file=sys.stderr)
        sys.exit(1)
    if picos_rel is None:
        print("ERROR: Picos relation 2401595 not found", file=sys.stderr)
        sys.exit(1)

    # Validate tags
    for rel, name in [(ordesa_rel, "Ordesa"), (picos_rel, "Picos")]:
        boundary = _get_tag(rel, "boundary")
        if boundary != "protected_area":
            print(
                f"ERROR: {name} relation has boundary={boundary}, "
                f"expected protected_area",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── Build features ───────────────────────────────────────────────────
    park_configs = [
        {
            "id": "pa-ordesa",
            "name": "Parque Nacional de Ordesa y Monte Perdido",
            "region": "ordesa",
            "rel": ordesa_rel,
            "fixture": ordesa_data,
        },
        {
            "id": "pa-picos",
            "name": "Parque Nacional de Picos de Europa",
            "region": "picos",
            "rel": picos_rel,
            "fixture": picos_data,
        },
    ]

    tolerance = 0.00001
    features: list[dict] = []
    simplification_info: dict = {}

    for cfg in park_configs:
        raw_geom = _build_geojson_from_overpass_rel(cfg["rel"], cfg["fixture"])
        if raw_geom is None:
            print(
                f"ERROR: Could not build geometry for {cfg['name']}",
                file=sys.stderr,
            )
            sys.exit(1)

        before_verts = _vertex_count(raw_geom)
        simp_geom, before, after = _simplify_geom(raw_geom, tolerance)
        after_verts = _vertex_count(simp_geom)

        simplification_info[cfg["id"]] = {
            "tolerance": tolerance,
            "vertices_before": before,
            "vertices_after": after,
            "vertices_reduced": before - after,
        }

        feat: dict = OrderedDict()
        feat["id"] = cfg["id"]
        feat["type"] = "Feature"
        feat["category"] = "protected_area"
        feat["name"] = cfg["name"]
        feat["geometry"] = simp_geom
        feat["properties"] = OrderedDict([
            ("id", cfg["id"]),
            ("name", cfg["name"]),
            ("category", "protected_area"),
            ("region", cfg["region"]),
            ("source", "openstreetmap"),
            ("source_label", "OSM"),
            ("source_ref", f"relation/{cfg['rel']['id']}"),
            ("source_license", "ODbL-1.0"),
            ("snapshot_date", snapshot_date),
            ("attribution", "© OpenStreetMap contributors"),
            ("osm_url", f"https://www.openstreetmap.org/relation/{cfg['rel']['id']}"),
            ("note", DISCLAIMER),
        ])
        features.append(feat)

    # ── Build metadata ───────────────────────────────────────────────────
    metadata: dict = OrderedDict()
    metadata["schema"] = "alraso-m2-protected-areas/v1"
    metadata["snapshot"] = True
    metadata["may_be_stale"] = True
    metadata["retrieved_at"] = snapshot_date
    metadata["source"] = "OpenStreetMap"
    metadata["source_url"] = "https://www.openstreetmap.org/copyright"
    metadata["overpass_endpoint"] = OVERPASS_ENDPOINT
    metadata["query_ordesa"] = query_ordesa
    metadata["query_picos"] = query_picos
    metadata["source_digests"] = OrderedDict([
        ("ordesa_overpass_response_sha256", ordesa_sha),
        ("picos_overpass_response_sha256", picos_sha),
    ])
    metadata["license"] = "ODbL-1.0"
    metadata["license_url"] = "https://opendatacommons.org/licenses/odbl/1-0/"
    metadata["attribution"] = "© OpenStreetMap contributors"
    metadata["note"] = (
        "Capa de áreas protegidas de OpenStreetMap para contexto visual. "
        "Los límites mostrados son referencia cartográfica y NO constituyen "
        "delimitación legal oficial ni determinan el ámbito jurídico de AlRaso."
    )

    # Simplification block
    metadata["simplification"] = OrderedDict([
        ("method", "shapely.simplify(tolerance, preserve_topology=True)"),
        ("tolerance_degrees", tolerance),
    ])
    metadata["simplification"]["per_feature"] = OrderedDict(
        sorted(simplification_info.items())
    )

    # Official cross-check block
    if crosscheck_data:
        parks_cc = {}
        for park_name in ("ordesa", "picos"):
            park_data = crosscheck_data.get("parks", {}).get(park_name, {})
            if park_data:
                parks_cc[park_name] = OrderedDict([
                    ("osm_relation_id", park_data.get("osm_relation_id")),
                    ("osm_area_ha", park_data.get("osm_area_ha")),
                    ("official_area_ha", park_data.get("official_area_ha")),
                    ("delta_pct", park_data.get("delta_pct")),
                    ("official_response_sha256", park_data.get("official_response_sha256")),
                    ("official_source_url", park_data.get("official_source_url")),
                    ("official_redistribution", park_data.get("official_redistribution")),
                ])
        metadata["official_crosscheck"] = OrderedDict([
            ("source", "OAPN/MITECO SIGRED"),
            ("source_url", crosscheck_data.get("official_source_url")),
            ("retrieved_at", crosscheck_data.get("retrieved_at")),
        ])
        metadata["official_crosscheck"]["parks"] = OrderedDict(
            sorted(parks_cc.items())
        )
        metadata["official_crosscheck"]["guard_threshold_pct"] = 5
        metadata["official_crosscheck"]["guard_passed"] = crosscheck_data.get(
            "guard", {}
        ).get("passed")

    # Builder self-digest
    metadata["builder_self_sha256"] = _sha256_file(Path(__file__))
    metadata["fixture_digests"] = OrderedDict([
        ("ordesa_fixture_sha256", ordesa_sha),
        ("picos_fixture_sha256", picos_sha),
    ])

    # ── Assemble document ────────────────────────────────────────────────
    doc = OrderedDict()
    doc["$schema"] = "alraso-m2-protected-areas/v1"
    doc["metadata"] = metadata
    doc["attribution"] = (
        "Datos de áreas protegidas de OpenStreetMap. "
        "© contribuidores de OpenStreetMap (licencia ODbL 1.0). "
        "Fuente: OpenStreetMap vía Overpass. "
        "Referencia cartográfica para contexto visual — NO delimitación legal."
    )
    doc["policy"] = (
        "Capa de ÁREAS PROTEGIDAS de carácter OBSERVACIONAL. "
        "Los límites mostrados se obtienen de OpenStreetMap (relaciones "
        "boundary=protected_area) y representan una referencia cartográfica "
        "para contexto visual. NUNCA afirman nada legal: la existencia de "
        "un espacio protegido NO implica una prohibición automática. "
        "La determinación legal de cualquier punto la decide exclusivamente "
        "el resolver de AlRaso sobre corpus verificado. "
        "El límite oficial de cada parque se consulta mediante digest "
        "cross-check con OAPN SIGRED (NO redistribuido)."
    )
    doc["features"] = features

    return doc


# ── Check mode ─────────────────────────────────────────────────────────────────


def check_mode(doc_path: Path, ordesa: Path, picos: Path, snapshot_date: str) -> bool:
    """Rebuild from inputs and check byte-identical match."""
    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, dir=str(doc_path.parent)
    ) as tmp:
        tmp_path = Path(tmp.name)

    args = argparse.Namespace(
        ordesa=str(ordesa),
        picos=str(picos),
        snapshot_date=snapshot_date,
        out=str(tmp_path),
        check=True,
    )
    new_doc = build(args)
    new_content = json.dumps(new_doc, indent=2, ensure_ascii=False) + "\n"
    tmp_path.write_bytes(new_content.encode("utf-8"))

    committed = doc_path.read_bytes()
    regenerated = tmp_path.read_bytes()

    committed_sha = _sha256_file(doc_path)
    regenerated_sha = hashlib.sha256(regenerated).hexdigest()

    tmp_path.unlink(missing_ok=True)

    if committed == regenerated:
        return True
    print(
        f"FAIL: committed sha256={committed_sha} "
        f"vs regenerated sha256={regenerated_sha}",
        file=sys.stderr,
    )
    return False


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="M8.1 Protected-area builder")
    parser.add_argument("--ordesa", required=True, help="Overpass fixture JSON (Ordesa)")
    parser.add_argument("--picos", required=True, help="Overpass fixture JSON (Picos)")
    parser.add_argument("--snapshot-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output GeoJSON path")
    parser.add_argument(
        "--check", action="store_true",
        help="Regenerate and compare against committed file (byte-identical)",
    )
    args = parser.parse_args()

    doc_path = Path(args.out)

    if args.check:
        if not Path(args.ordesa).exists():
            print(f"ERROR: --ordesa input not found: {args.ordesa}", file=sys.stderr)
            sys.exit(1)
        if not Path(args.picos).exists():
            print(f"ERROR: --picos input not found: {args.picos}", file=sys.stderr)
            sys.exit(1)
        if not doc_path.exists():
            print(f"ERROR: committed output not found: {doc_path}", file=sys.stderr)
            sys.exit(1)

        if check_mode(doc_path, Path(args.ordesa), Path(args.picos), args.snapshot_date):
            print(f"OK: {doc_path} is byte-identical to regenerated output")
            sys.exit(0)
        else:
            print(f"FAIL: {doc_path} differs from regenerated output", file=sys.stderr)
            sys.exit(1)

    if not Path(args.ordesa).exists():
        print(f"ERROR: --ordesa input not found: {args.ordesa}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.picos).exists():
        print(f"ERROR: --picos input not found: {args.picos}", file=sys.stderr)
        sys.exit(1)

    doc = build(args)
    content = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    Path(args.out).write_bytes(content.encode("utf-8"))
    print(f"Built {doc_path} with {len(doc['features'])} features")


if __name__ == "__main__":
    main()