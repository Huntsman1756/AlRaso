"""Re-verificacion online del lock M2-A (Picos). Solo stdlib.

Uso:  python tooling/m2a_picos_verify.py
Salida: OK / FAIL / INCONCLUSIVE (sin red => INCONCLUSIVE, exit 2; jamas OK falso).
"""
import hashlib
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK_PATH = os.path.join(HERE, "m2a_picos_discovery.evidence.json")

OAPN = "https://sigred.oapn.es/geoserverOAPN/ows"
TYPE_NAME = "LimitesParquesNacionalesZPP:view_red_oapn_limite_pn"
GISCO = ("https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
         "NUTS_RG_01M_2024_4326_LEVL_2.geojson")
UA = {"User-Agent": "AlRaso-M2A-verify"}


def get(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]


def digest(coords_by_ring, nd):
    flat = sorted([[round(float(c[0]), nd), round(float(c[1]), nd)] for r in coords_by_ring for c in r])
    return hashlib.sha256(json.dumps(flat, separators=(",", ":")).encode()).hexdigest()


def area_ha(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    total = 0.0
    for poly in polys:
        for i, r in enumerate(poly):
            s = 0.0
            for (x1, y1), (x2, y2) in zip(r, list(r[1:]) + [r[0]]):
                s += x1 * y2 - x2 * y1
            total += (abs(s) / 2.0) * (1 if i == 0 else -1)
    return total / 10000.0


def gisco_digest(geom):
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    else:
        polys = geom["coordinates"]
    rings = sorted([[[round(c[0], 4), round(c[1], 4)] for c in p[0]] for p in polys],
                   key=lambda r: (r[0][0], r[0][1]))
    return hashlib.sha256(json.dumps(rings, separators=(",", ":")).encode()).hexdigest()


def main():
    lock = json.load(open(LOCK_PATH, encoding="utf-8"))
    fails = []

    try:
        if os.environ.get("OFFLINE") == "1":
            raise urllib.error.URLError("OFFLINE=1")
        p = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
             "outputFormat": "application/json", "typeName": TYPE_NAME}
        j = json.loads(get(OAPN + "?" + urllib.parse.urlencode(p)).decode("utf-8"))
        feat = next(f for f in j["features"] if "picos" in str(f["properties"].get("Nombre", "")).lower())
        rings = rings_of(feat["geometry"])
        exp = lock["spatial"]["park_oapn"]
        got_n = sum(len(r) for r in rings)
        got_area = round(area_ha(feat["geometry"]), 1)
        got_dig = digest(rings, 2)
        if got_n != exp["n_points"]:
            fails.append(f"park n_points {got_n} != {exp['n_points']}")
        if abs(got_area - exp["area_ha_computed"]) / exp["area_ha_computed"] > 0.0001:
            fails.append(f"park area_ha {got_area} != {exp['area_ha_computed']}")
        if got_dig != exp["coord_digest_25830_2dp"]:
            fails.append("park coord_digest_25830_2dp mismatch")

        raw = get(GISCO, timeout=180)
        if hashlib.sha256(raw).hexdigest() != lock["spatial"]["ccaa_gisco_nuts2"]["file_sha256"]:
            fails.append("gisco file_sha256 mismatch")
        gj = json.loads(raw)
        for f in gj["features"]:
            nid = f["properties"]["NUTS_ID"]
            if nid in ("ES12", "ES13", "ES41"):
                got = gisco_digest(f["geometry"])
                expd = lock["spatial"]["ccaa_gisco_nuts2"]["per_unit_digests"][nid]
                if got != expd["coord_digest_4dp"]:
                    fails.append(f"gisco {nid} digest mismatch")
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        print(f"INCONCLUSIVE: fuente oficial no alcanzable ({e}); no se afirma OK sin evidencia")
        return 2

    for d in lock["legal_documents"].values():
        pth = os.path.join(os.path.dirname(HERE), d["artifact"]["path"].replace("/", os.sep))
        b = open(pth, "rb").read()
        if hashlib.sha256(b).hexdigest() != d["artifact"]["sha256"]:
            fails.append(f"extract artifact mismatch: {d['artifact']['path']}")
        if len(b) != d["artifact"]["bytes"]:
            fails.append(f"extract bytes mismatch: {d['artifact']['path']}")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("OK: lock M2-A Picos coherente con fuentes oficiales y extracts comiteados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
