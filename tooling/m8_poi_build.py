#!/usr/bin/env python3
"""M8 POI builder — deterministic snapshot from Overpass fixtures + anchors.

Usage:
    python tooling/m8_poi_build.py \
        --ordesa <overpass.json> --picos <overpass.json> \
        --snapshot-date YYYY-MM-DD --out webapp/pois.json [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

# ── Category mapping ─────────────────────────────────────────────────────────
# ADAPT of survival_map's CATEGORIES/categoryFor first-match (order matters).

CATEGORY_MAP = OrderedDict([
    ("amenity", {
        "drinking_water": "water",
        "fountain": "water",
        "shelter": "shelter",
    }),
    ("natural", {
        "spring": "water",
    }),
    ("tourism", {
        "alpine_hut": "refuge",
        "wilderness_hut": "refuge",
        "hut": "refuge",
        "camp_site": "camping",
        "caravan_site": "camping",
    }),
])

CAMPING_DISCLAIMER = (
    "Su estatus legal lo decide el resolver, no esta etiqueta. "
    "La existencia en OSM NO significa autorizacion legal."
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_tag(element: dict, key: str) -> str | None:
    tags = element.get("tags") or {}
    return tags.get(key)


def _coords(element: dict) -> tuple[float, float] | None:
    """Return (lat, lon) from node or way center."""
    if element.get("type") == "node":
        return element["lat"], element["lon"]
    if element.get("type") == "way" and "center" in element:
        c = element["center"]
        return float(c["lat"]), float(c["lon"])
    return None


def _round_coords(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 6), round(lon, 6)


def _make_id(e: dict) -> str:
    return f"{e['type']}/{e['id']}"


def _category_for(element: dict) -> str | None:
    """Apply CATEGORY_MAP first-match. Returns category string or None."""
    tags = element.get("tags") or {}
    for tag_type, mapping in CATEGORY_MAP.items():
        val = tags.get(tag_type)
        if val in mapping:
            return mapping[val]
    return None


def _make_note(category: str, element: dict) -> str:
    tags = element.get("tags") or {}
    name = tags.get("name", "")
    natural = tags.get("natural", "")
    amenity = tags.get("amenity", "")

    if category == "water":
        if amenity == "drinking_water":
            return "Agua potable segun OSM."
        elif natural == "spring":
            drinkable = tags.get("drinkable", "")
            if drinkable == "yes":
                return (
                    "Fuente / agua — potable segun OSM (drinkable=yes). "
                    "Potabilidad verificada por etiquetado OSM."
                )
            else:
                return (
                    "Fuente / agua — potabilidad no verificada. "
                    "La potabilidad debe ser confirmada in situ."
                )
        else:
            return "Fuente / agua."
    elif category == "camping":
        return CAMPING_DISCLAIMER
    elif category == "refuge":
        return "Refugio de montaña."
    elif category == "shelter":
        return "Abrigo de montaña."
    return ""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Main ─────────────────────────────────────────────────────────────────────


def build(args: argparse.Namespace) -> dict:
    """Build the POI document from Overpass fixtures + anchors."""

    # Load fixtures
    with open(args.ordesa, encoding="utf-8") as f:
        ordesa_data = json.load(f)
    with open(args.picos, encoding="utf-8") as f:
        picos_data = json.load(f)

    # Compute digests of input files
    ordesa_sha = _sha256_file(Path(args.ordesa))
    picos_sha = _sha256_file(Path(args.picos))

    # Dedup registry: key = type/id, value = processed feature
    seen: dict[str, dict] = {}

    def process_region(elements: list[dict], region: str) -> None:
        for elem in elements:
            cat = _category_for(elem)
            if cat is None:
                continue
            coords = _coords(elem)
            if coords is None:
                continue
            lat, lon = _round_coords(*coords)
            eid = _make_id(elem)

            # Skip if we've already seen this element (first-match wins)
            if eid in seen:
                continue

            tags = elem.get("tags") or {}
            name = tags.get("name", "")

            # Build feature
            feat: dict = OrderedDict()
            feat["id"] = eid
            feat["category"] = cat
            feat["name"] = name if name else f"POI {cat} {eid}"
            feat["lat"] = lat
            feat["lon"] = lon
            feat["source"] = "openstreetmap"
            feat["source_ref"] = eid  # e.g. "node/12345"
            feat["source_label"] = "OSM"
            feat["source_license"] = "ODbL-1.0"
            feat["snapshot_date"] = args.snapshot_date
            feat["attribution"] = "© OpenStreetMap contributors"
            feat["region"] = region
            feat["note"] = _make_note(cat, elem)
            feat["osm_url"] = f"https://www.openstreetmap.org/{eid}"

            # alt_m from ele tag only
            ele = tags.get("ele")
            if ele is not None:
                try:
                    feat["alt_m"] = int(float(ele))
                except (ValueError, TypeError):
                    feat["alt_m"] = None
            else:
                feat["alt_m"] = None

            seen[eid] = feat

    process_region(ordesa_data.get("elements", []), "ordesa")
    process_region(picos_data.get("elements", []), "picos")

    # ── Load anchors ───────────────────────────────────────────────────
    anchors_path = Path(__file__).parent / "poi_anchors.json"
    anchors: list[dict] = []
    if anchors_path.exists():
        with open(anchors_path, encoding="utf-8") as f:
            anchors = json.load(f)

    # Merge: anchors override any generated feature with same id
    for a in anchors:
        seen[a["id"]] = a

    # ── Sort: (category, id) ──────────────────────────────────────────
    features = sorted(seen.values(), key=lambda f: (f["category"], f["id"]))

    # ── Build metadata ────────────────────────────────────────────────
    metadata: dict = OrderedDict()
    metadata["snapshot"] = True
    metadata["may_be_stale"] = True
    metadata["retrieved_at"] = args.snapshot_date
    metadata["source"] = "OpenStreetMap"
    metadata["source_url"] = "https://www.openstreetmap.org/copyright"
    metadata["overpass_endpoint"] = "https://overpass-api.de/api/interpreter"
    metadata["query_ordesa"] = (
        '[out:json][timeout:25];('
        'node["tourism"~"alpine_hut|hut|camp_site"](42.5,-0.30,42.9,0.20);'
        'node["natural"="spring"](42.5,-0.30,42.9,0.20);'
        'node["amenity"="drinking_water"](42.5,-0.30,42.9,0.20);'
        'node["amenity"="shelter"](42.5,-0.30,42.9,0.20);'
        'way["tourism"~"alpine_hut|hut|camp_site"](42.5,-0.30,42.9,0.20);'
        'way["natural"="spring"](42.5,-0.30,42.9,0.20);'
        'way["amenity"="drinking_water"](42.5,-0.30,42.9,0.20);'
        'way["amenity"="shelter"](42.5,-0.30,42.9,0.20);'
        ');out body 120;'
    )
    metadata["query_picos"] = (
        '[out:json][timeout:25];('
        'node["tourism"~"alpine_hut|hut|wilderness_hut|camp_site"](43.00,-5.30,43.40,-4.40);'
        'node["amenity"="shelter"](43.00,-5.30,43.40,-4.40);'
        'way["tourism"~"alpine_hut|hut|wilderness_hut|camp_site"](43.00,-5.30,43.40,-4.40);'
        'way["amenity"="shelter"](43.00,-5.30,43.40,-4.40);'
        ');out body 100;'
    )
    # Protected area queries — dormant, not queried by builder at build time.
    metadata["query_protected_ordesa"] = (
        '[out:json][timeout:25];'
        '(rel["boundary"="protected_area"](42.5,-0.25,42.9,0.20););'
        'out center tags 100;'
    )
    metadata["query_protected_picos"] = (
        '[out:json][timeout:25];'
        '(rel["boundary"="protected_area"](43.00,-5.30,43.40,-4.40););'
        'out center tags 100;'
    )
    metadata["source_digests"] = OrderedDict([
        ("ordesa_overpass_response_sha256", ordesa_sha),
        ("picos_overpass_response_sha256", picos_sha),
        # Placeholder digests for protected_area queries (not fetched by builder).
        # These were carried over from the original snapshot build.
        ("protected_ordesa_overpass_response_sha256",
         "0" * 64),  # stub — no protected_area fixture
        ("protected_picos_overpass_response_sha256",
         "0" * 64),  # stub — no protected_area fixture
    ])
    metadata["license"] = "ODbL-1.0"
    metadata["license_url"] = "https://opendatacommons.org/licenses/odbl/1-0/"
    metadata["attribution"] = "© OpenStreetMap contributors"
    metadata["note"] = (
        "Snapshot observacional curado a partir de las respuestas Overpass "
        "(digests arriba). Puede quedar desactualizado. No es evidencia normativa "
        "y no entra en el motor. Cada feature OSM lleva `source=openstreetmap` y "
        "`source_ref` que enlaza a un objeto real (node/<id> o way/<id>). "
        "`poi-goriz` NO forma parte del snapshot OSM: es un ancla del proyecto."
    )

    # Categories
    categories = OrderedDict([
        ("refuge", {"label": "Refugio", "emoji": "🏠", "color": "#b45309"}),
        ("shelter", {"label": "Abrigo / cabaña", "emoji": "🛖", "color": "#f97316"}),
        ("water", {"label": "Agua", "emoji": "💧", "color": "#0ea5e9"}),
        ("camping", {"label": "Camping / bivouac", "emoji": "⛺", "color": "#16a34a"}),
        # protected_area is preserved in categories schema but NOT emitted as feature.
        # See tooling/poi_dormant_protected_area.json.
        ("protected_area", {
            "label": "Referencia OSM: espacio natural protegido",
            "emoji": "🌲",
            "color": "#0d9488",
        }),
    ])

    doc = OrderedDict()
    doc["$schema"] = "alraso-m2-pois/v1"
    doc["metadata"] = metadata
    doc["attribution"] = (
        "Datos de puntos de interés de OpenStreetMap. "
        "© contribuidores de OpenStreetMap (licencia ODbL 1.0). "
        "Fuente: OpenStreetMap vía Overpass (consultas reproducibles en `metadata`). "
        "Enlaces a cada objeto OSM incluidos."
    )
    doc["policy"] = (
        "Capa de PUNTOS DE INTERÉS de carácter OBSERVACIONAL. Estos elementos "
        "se obtienen de OpenStreetMap (consultas Overpass puntuales de "
        "construcción) y describen dónde EXISTE algo (un refugio, una fuente, "
        "un abrigo, un camping, un espacio natural protegido). NUNCA afirman "
        "nada legal: la existencia de un refugio NO es un permiso de vivac, "
        "un camping NO es una zona legalmente autorizada, y un espacio "
        "protegido NO implica una prohibición automática. La determinación "
        "legal de cualquier punto la decide exclusivamente el resolver de "
        "AlRaso sobre corpus verificado (ver capa de cobertura). Estos POIs "
        "no entran en el motor ni modifican ninguna resolución."
    )
    doc["categories"] = categories
    doc["features"] = features

    return doc


def check_mode(doc_path: Path, ordesa: Path, picos: Path, snapshot_date: str) -> bool:
    """Rebuild from inputs and check byte-identical match."""
    import tempfile

    # Write regenerated output to a temp file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, dir=str(doc_path.parent)) as tmp:
        tmp_path = Path(tmp.name)

    args = argparse.Namespace(
        ordesa=str(ordesa), picos=str(picos),
        snapshot_date=snapshot_date, out=str(tmp_path), check=True,
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
    print(f"FAIL: committed sha256={committed_sha} "
          f"vs regenerated sha256={regenerated_sha}", file=sys.stderr)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="M8 POI builder")
    parser.add_argument("--ordesa", required=True, help="Overpass fixture JSON (Ordesa)")
    parser.add_argument("--picos", required=True, help="Overpass fixture JSON (Picos)")
    parser.add_argument("--snapshot-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output POI JSON path")
    parser.add_argument("--check", action="store_true",
                        help="Regenerate and compare against committed file (byte-identical)")
    args = parser.parse_args()

    # Check mode: --out points to the committed file path
    doc_path = Path(args.out)

    if args.check:
        # Validate inputs exist
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

    # Normal build mode
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
