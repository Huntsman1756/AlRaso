"""M1.1-C Góriz scope-identity verifier: is the official Góriz ZUM vector still
the same legal scope (gate A) as recorded in the evidence lock?

Manual tool, never part of the test suite: it hits official services
(OAPN SIGRED WFS + ICEAragon WFS).

  python tooling/m11c_goriz_identity.py           # fresh check + report
  python tooling/m11c_goriz_identity.py --verify  # compare with the evidence lock

Re-checks, without any third-party dependency:
  * the OAPN feature still exists with the SAME legal attributes (Zona,
    Normativa, Observaciones) - this is the legal link itself;
  * the ICEAragon feature ENP101_137 still exists with the same zone name;
  * geometry stability via normalized coordinate digests (full geometry
    identity OAPN<->ICEAragon, IoU/Hausdorff, was proven with shapely offline
    in the builder recorded by the lock; this tool re-confirms existence,
    attributes and digests, not a fresh geometric overlay);
  * the three probe points (inside/outside/inside-3m) against the live ring.

Classification is only ever one of:

  OFFICIAL_SCOPE_LINK_PROVEN            every re-check passed
  SCOPE_IDENTITY_DRIFT                  sources changed: the lock's verdict is
                                        no longer confirmed (re-open M1.1-C)
  VERIFICATION_INCONCLUSIVE             an endpoint was unreachable: NEVER read
                                        this as "the link is gone"
"""
from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "m11c_goriz_scope.evidence.json")
ARAGON = "https://icearagon.aragon.es/Visor2D"
OAPN = "https://sigred.oapn.es/geoserverOAPN/ows"


def fetch(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "AlRaso-M11C-verify"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def wfs(base: str, layer: str, extra: dict | None = None) -> dict:
    p = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
         "outputFormat": "application/json", "typeName": layer}
    p.update(extra or {})
    raw = fetch(base + "?" + urllib.parse.urlencode(p))
    return json.loads(raw.decode("utf-8", "replace"))


def fold(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def coord_digest(geom: dict, ndigits: int) -> str:
    polys = []
    for poly in geom["coordinates"]:
        rr = [[round(c[0], ndigits), round(c[1], ndigits)] for c in poly[0]]
        polys.append(rr)
    polys.sort(key=lambda r: (r[0][0], r[0][1]))
    return hashlib.sha256(json.dumps(polys, separators=(",", ":")).encode()).hexdigest()


def point_in_ring(lat: float, lon: float, ring: list) -> bool:
    """Even-odd ray casting on (x=lon, y=lat). NOT for exact-boundary points
    (same documented limitation as alraso/spatial.py)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i][1], ring[i][0]
        yj, xj = ring[j][1], ring[j][0]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def run_checks() -> dict:
    out: dict = {"checked_at": datetime.now(timezone.utc).isoformat()}

    zenp = wfs(ARAGON, "VISOR2D:ZENP",
               {"CQL_FILTER": "zonecode='ENP101_137'", "srsName": "EPSG:25830"})
    feats = zenp.get("features", [])
    f137 = next((f for f in feats if (f.get("properties") or {}).get("zonecode") == "ENP101_137"),
                None)
    if f137 is None:
        out["classification"] = "SCOPE_IDENTITY_DRIFT"
        out["reason"] = "ICEAragon ENP101_137 already missing"
        return out
    p137 = f137["properties"]
    out["aragon_feature"] = {k: p137.get(k) for k in ("zonecode", "zonename", "zonetype")}
    out["digest_aragon_6dp"] = coord_digest(f137["geometry"], 6)

    # OAPN: the full layer answers (maxFeatures is ignored server-side);
    # filter client-side because CQL on spaced property names returns 400.
    zon = wfs(OAPN, "ZonificacionPRUG:view_zon_zonificacion_prug",
              {"srsName": "EPSG:4326"})
    gor = None
    for f in zon.get("features", []):
        pr = f.get("properties") or {}
        if ("ordesa" in fold(pr.get("Nombre Parque"))
                and "acampada" in fold(pr.get("Nombre"))
                and "goriz" in fold(pr.get("Nombre"))):
            gor = f
            break
    if gor is None:
        out["classification"] = "SCOPE_IDENTITY_DRIFT"
        out["reason"] = "OAPN Goriz camping feature no longer published"
        return out
    pg = gor["properties"]
    out["oapn_attributes"] = {k: pg.get(k) for k in
                              ("Nombre", "Zona", "Normativa", "Observaciones", "Superficie (ha)")}
    out["digest_oapn_7dp"] = coord_digest(gor["geometry"], 7)

    # probe points in EPSG:25830 (native CRS of the live layer, as requested)
    lock = json.load(open(LOCK, encoding="utf-8"))
    pts = {p["label"]: p["utm25830"] for p in lock["three_points"]
           if p["label"] != "border_vertex"}  # exact edge: undefined for ray casting
    rings = [poly[0] for poly in f137["geometry"]["coordinates"]]
    out["probes"] = {label: any(point_in_ring(y, x, r) for r in rings)
                     for label, (x, y) in pts.items()}
    expected = {"inside_centroid": True, "outside_east": False,
                "inside_3m_from_border_vertex": True}
    if any(out["probes"][k] != v for k, v in expected.items()):
        out["classification"] = "SCOPE_IDENTITY_DRIFT"
        out["reason"] = f"probe points changed: {out['probes']}"
        return out

    out["classification"] = "OFFICIAL_SCOPE_LINK_PROVEN"
    return out


def compare_with_lock(obs: dict, lock: dict) -> list[str]:
    problems: list[str] = []
    if obs["classification"] != "OFFICIAL_SCOPE_LINK_PROVEN":
        problems.append(f"CHECK FAILED NOW: {obs['classification']} ({obs.get('reason')})")
        return problems
    idc = lock["identity_chain"]
    attr = idc["2_official_state_vector_with_legal_attribute"]
    live = obs["oapn_attributes"]
    for k_lock, k_live in (("zona", "Zona"), ("normativa", "Normativa"),
                           ("observaciones", "Observaciones")):
        if attr.get(k_lock) != live.get(k_live):
            problems.append(f"LEGAL ATTRIBUTE DRIFT {k_lock}: lock={attr.get(k_lock)!r} "
                            f"live={live.get(k_live)!r}")
    id3 = idc["3_autonomous_vector_identity"]
    if id3["coord_digest_aragon_25830_6dp"] != obs["digest_aragon_6dp"]:
        problems.append("ARAGON GEOMETRY DRIFT: normalized coord digest changed")
    if id3["coord_digest_oapn_4326_7dp"] != obs["digest_oapn_7dp"]:
        problems.append("OAPN GEOMETRY DRIFT: normalized coord digest changed")
    if fold(lock["identity_chain"]["3_autonomous_vector_identity"]["zonename"]) \
            != fold(obs["aragon_feature"].get("zonename") or ""):
        problems.append("ARAGON zonename drift")
    return problems


def main(argv: list[str]) -> int:
    verify = "--verify" in argv
    try:
        obs = run_checks()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(json.dumps({"classification": "VERIFICATION_INCONCLUSIVE",
                          "reason": f"official endpoint unreachable: {type(exc).__name__}: {exc}",
                          "meaning": "link still presumed proven; never read this as drift"},
                         indent=2))
        return 2

    report = os.path.join(os.environ.get("TEMP", "/tmp"), "m11c_goriz_verify_report.json")
    open(report, "w", encoding="utf-8").write(json.dumps(obs, indent=2) + "\n")
    print(json.dumps(obs, indent=2, ensure_ascii=False))
    print(f"report: {report}")

    if obs["classification"] != "OFFICIAL_SCOPE_LINK_PROVEN":
        print("FAIL:", obs.get("reason"))
        return 1
    if verify:
        lock = json.load(open(LOCK, encoding="utf-8"))
        problems = compare_with_lock(obs, lock)
        if problems:
            for p in problems:
                print("FAIL:", p)
            return 1
        print("verify OK: gate A still holds (attributes + geometry digests + probes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
