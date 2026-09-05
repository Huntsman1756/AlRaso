"""M1.1 vector discovery: does official ICEARAGON vector geometry exist for the
legal scope a PNOMP overnight rule needs (Sector Ordesa)?

Manual tool, never part of the test suite: it hits official services.

  python tooling/m11_vector_discovery.py            # fresh evidence + report
  python tooling/m11_vector_discovery.py --verify    # re-run and compare to lock

Classification is only ever one of:

  OFFICIAL_LEGAL_SCOPE_FOUND       a real candidate appeared -> re-open M1.1
  NO_OFFICIAL_VECTOR_SCOPE_FOUND   nothing official for the sector (the 2026-09-05 result)
  DISCOVERY_INCONCLUSIVE           a source was unreachable: ABSENCE NOT PROVEN

The third value exists on purpose: an offline run must never be reported as
"no official vector scope exists".
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "m11_vector_discovery.lock.json")
WFS = "https://icearagon.aragon.es/Visor2D"
DIT = "https://icearagon.aragon.es/DIT"
SIUA = "https://icearagon.aragon.es/SIUa_WMS"
CAPS = {
    # (base, exact caps query verified live on 2026-09-05; SIUa only answered the
    # lowercase request spelling, so the tool reproduces exactly what was proven)
    "cartografia_basica": (WFS, "?service=WFS&version=2.0.0&request=GetCapabilities"),
    "dit": (DIT, "?service=WFS&version=2.0.0&request=GetCapabilities"),
    "urbanismo_sium": (SIUA, "?service=WFS&version=2.0.0&request=getcapabilities"),
}
# native CRS of the official layers (EPSG:25830, ETRS89 / UTM30N per the Norma
# Cartografica de Aragon); window covers PNOMP plus margin.
PNOMP_BBOX = "735000,4710000,765000,4740000,EPSG:25830"
ENP101_WINDOW_CQL = ("INTERSECTS(shape,SRID=4326;POLYGON((0.0 42.60,0.28 42.60,"
                     "0.28 42.75,0.0 42.75,0.0 42.60)))")
PLAN_NAME_RE = re.compile(r"prug|plan\s*rector|pernocta|acampad|vivac", re.IGNORECASE)
SECTOR_RE = re.compile(r"sector", re.IGNORECASE)


def fetch(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "AlRaso-M11-discovery"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def wfs(base: str, layer: str | None = None, bbox: bool = False,
        cql: str | None = None, version: str = "2.0.0") -> bytes:
    p = {"service": "WFS", "version": version, "request": "GetFeature",
         "outputFormat": "application/json", "srsName": "EPSG:4326"}
    if layer:
        p["typeName"] = layer
    if bbox:
        p["bbox"] = PNOMP_BBOX
        p["count"] = "300"
    if cql:
        p["CQL_FILTER"] = cql
    return fetch(base + "?" + urllib.parse.urlencode(p))


def run_discovery() -> dict:
    """Return observations + classification. Raises urllib errors upward."""
    out: dict = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "evidence": []}
    names: set[str] = set()
    for label, (base, caps_query) in CAPS.items():
        raw = fetch(base + caps_query)
        out["evidence"].append({"artifact": f"caps_{label}", "endpoint": base,
                                "bytes": len(raw),
                                "sha256": hashlib.sha256(raw).hexdigest()})
        names |= set(re.findall(r"<Name>([A-Za-z0-9_:]+)</Name>",
                                raw.decode("utf-8", "replace")))
    out["published_feature_types_total"] = len(names)
    out["plan_like_layers"] = sorted(n for n in names if PLAN_NAME_RE.search(n))

    def get(url_bytes: bytes) -> tuple[int | None, list[dict]]:
        j = json.loads(url_bytes.decode("utf-8", "replace"))
        return j.get("numberMatched"), [f.get("properties", {}) for f in j.get("features", [])]

    zenp_raw = wfs(WFS, "VISOR2D:ZENP", bbox=True)
    zenp_matched, zenp_feats = get(zenp_raw)
    out["evidence"].append({"artifact": "zenp_pnomp", "endpoint": WFS, "bytes": len(zenp_raw),
                            "sha256": hashlib.sha256(zenp_raw).hexdigest()})
    f101 = [p for p in zenp_feats if p.get("codeara") == "ENP101"]
    out["zenp_enp101_features"] = len(f101)
    out["zenp_enp101_zonetypes"] = sorted({str(p.get("zonetype")) for p in f101})
    out["zenp_enp101_sector_named"] = sum(1 for p in f101 if SECTOR_RE.search(str(p.get("zonename", ""))))
    out["zenp_enp101_with_planificationzone"] = sum(
        1 for p in f101 if p.get("planificationzone") not in (None, ""))

    for label, layer in (("porn_plan", "VISOR2D:PORN_ES24"), ("porn_zoning", "VISOR2D:ZPORNs")):
        raw = wfs(WFS, layer, bbox=True)
        matched, _ = get(raw)
        out["evidence"].append({"artifact": label, "endpoint": WFS, "bytes": len(raw),
                                "sha256": hashlib.sha256(raw).hexdigest()})
        out[f"{label}_features_pnomp"] = matched

    raw = wfs(WFS, "VISOR2D:ENP_ES24", cql=ENP101_WINDOW_CQL)
    _, feats = get(raw)
    out["evidence"].append({"artifact": "enp_window", "endpoint": WFS, "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest()})
    park = next((p for p in feats if p.get("codigo") == "ENP101"), None)
    out["park_polygon_present"] = park is not None

    if out["plan_like_layers"] or out["zenp_enp101_sector_named"] or (out["porn_plan_features_pnomp"] or 0) > 0:
        cls = "OFFICIAL_LEGAL_SCOPE_FOUND"
    else:
        cls = "NO_OFFICIAL_VECTOR_SCOPE_FOUND"
    out["classification"] = cls
    return out


def compare_with_lock(obs: dict, lock: dict) -> list[str]:
    problems: list[str] = []
    if obs["classification"] != lock["classification"]:
        problems.append(
            f"CLASSIFICATION CHANGED: lock={lock['classification']} now={obs['classification']}. "
            "The official data moved: re-open the M1.1 scope decision, do not trust the old verdict.")
    lock_shas = {e["artifact"]: e["sha256"] for e in lock["evidence"]}
    for e in obs["evidence"]:
        old = lock_shas.get(e["artifact"])
        if old and old != e["sha256"]:
            print(f"DRIFT (informational): {e['artifact']} sha256 changed "
                  f"{old[:12]}... -> {e['sha256'][:12]}...")
    return problems


def main(argv: list[str]) -> int:
    verify = "--verify" in argv
    try:
        obs = run_discovery()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(json.dumps({"classification": "DISCOVERY_INCONCLUSIVE",
                          "reason": f"official endpoint unreachable: {type(exc).__name__}: {exc}",
                          "meaning": "absence of evidence NOT proven; do not read this as C"},
                         indent=2))
        return 2

    report = os.path.join(os.environ.get("TEMP", "/tmp"), "m11_vector_discovery_report.json")
    open(report, "w", encoding="utf-8").write(json.dumps(obs, indent=2) + "\n")
    print(json.dumps({k: v for k, v in obs.items() if k != "evidence"}, indent=2, ensure_ascii=False))
    print(f"raw evidence hashes written to: {report}")

    if verify:
        lock = json.load(open(LOCK, encoding="utf-8"))
        problems = compare_with_lock(obs, lock)
        if problems:
            for p in problems:
                print("FAIL:", p)
            return 1
        print(f"verify OK: classification still {obs['classification']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
