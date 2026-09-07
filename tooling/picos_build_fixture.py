"""Build Picos Phase B fixture geometry (park boundary + CCAA sectors), simplified.
Run: uv run --with shapely --with pyproj python tooling/picos_build_fixture.py
Produces alraso/resources/fixture_picos.json (committed, justified minimal geometry).
"""
import json
import os
import urllib.request
from shapely.geometry import shape
from pyproj import Transformer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARK = os.path.join(ROOT, "discovery/spikes/spike-b-postgis/oapn-limites.geojson")
NUTS = os.environ.get("NUTS_GEOJSON", "C:/Users/rome_/AppData/Local/Temp/opencode/nuts2.json")
NUTS_URL = ("https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
            "NUTS_RG_01M_2024_4326_LEVL_2.geojson")
OUT = os.path.join(ROOT, "alraso/resources/fixture_picos.json")

CCAA = {"es-as": "ES12", "es-cb": "ES13", "es-cl": "ES41"}

# EPSG:25830 (ETRS89 UTM 30N, OAPN native) -> EPSG:4326 (WGS84 degrees)
_t = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)


def reproj_to_wgs84(geom):
    def tf(x, y):
        lon, lat = _t.transform(x, y)
        return (lon, lat)
    return shape(json.loads(json.dumps(geom.__geo_interface__))).__class__(geom)


def _reproject(geom):
    # transform all coords
    from shapely.geometry import mapping, shape as _shape
    m = mapping(geom)
    return _shape(_reproj_mapping(m))


def _reproj_mapping(m):
    if m["type"] == "Point":
        lon, lat = _t.transform(*m["coordinates"])
        return {"type": "Point", "coordinates": [lon, lat]}
    if m["type"] in ("LineString", "MultiPoint"):
        coords = [[_t.transform(x, y)[0], _t.transform(x, y)[1]] for x, y in m["coordinates"]]
        return {"type": m["type"], "coordinates": coords}
    if m["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [_reproj_ring(r) for r in m["coordinates"]]}
    if m["type"] == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": [
            [_reproj_ring(r) for r in poly] for poly in m["coordinates"]]}
    raise ValueError(m["type"])


def _reproj_ring(ring):
    return [[_t.transform(x, y)[0], _t.transform(x, y)[1]] for x, y in ring]


def load_park():
    d = json.load(open(PARK, encoding="utf-8"))
    for f in d["features"]:
        if "Picos" in str(f["properties"].get("Nombre") or ""):
            g = shape(f["geometry"])
            return _reproject(g).buffer(0)
    raise SystemExit("Picos not found")


def load_ccaa():
    if not os.path.exists(NUTS):
        print("downloading GISCO NUTS2...")
        os.makedirs(os.path.dirname(NUTS), exist_ok=True)
        urllib.request.urlretrieve(NUTS_URL, NUTS)
    d = json.load(open(NUTS, encoding="utf-8"))
    out = {}
    for f in d["features"]:
        nid = f["properties"].get("NUTS_ID")
        if nid in CCAA.values():
            out[nid] = shape(f["geometry"]).buffer(0)
    return out


def rings_latlon(geom):
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    rings = []
    for p in polys:
        if p.is_empty:
            continue
        ext = list(p.exterior.coords)
        if ext and ext[0] == ext[-1]:
            ext = ext[:-1]
        if len(ext) >= 3:
            rings.append([[round(lat, 6), round(lon, 6)] for lon, lat in ext])
    return rings


def main():
    park = load_park()
    ccaa = load_ccaa()
    print("park wgs84 area_deg2:", round(park.area, 6))
    park_simple = park.simplify(0.0015)
    geo = {"park": rings_latlon(park_simple)}
    sectors = {}
    for jur, nid in CCAA.items():
        sec = park.intersection(ccaa[nid])
        if sec.is_empty:
            print("EMPTY sector", jur)
            continue
        sec = sec.simplify(0.002)
        geo[jur] = rings_latlon(sec)
        sectors[jur] = {
            "n_rings": len(geo[jur]),
            "n_points": sum(len(r) for r in geo[jur]),
        }
    fixture = {
        "geometry": geo,
        "sectors_meta": sectors,
        "park_n_rings": len(geo["park"]),
        "park_n_points": sum(len(r) for r in geo["park"]),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(fixture, fh, ensure_ascii=False, indent=1)
    print("WROTE", OUT)
    print("park rings:", len(geo["park"]), "pts:", sum(len(r) for r in geo["park"]))
    for jur, m in sectors.items():
        print(jur, m)


if __name__ == "__main__":
    main()
