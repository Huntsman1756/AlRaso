"""M2 product vertical slice: map -> click -> resolver -> card. Stdlib only.

Run from a checkout:  python webapp/server.py [--host 127.0.0.1] [--port 8765]

The HTTP layer is deliberately thin and fail-closed like the core: malformed
requests become 4xx JSON errors, and every resolvable-or-not click returns a
determination that can NEVER be PERMITTED from absence. Coverage polygons with
boundary=esquematico are communication aids, never legal geometry.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import threading
import urllib.parse
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alraso.bitemporal import BitemporalStore
from alraso.domain import Query
from alraso.ingest.ordesa import ingest_corpus
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider

WEBAPP = Path(__file__).resolve().parent
STATIC = WEBAPP / "static"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COVERAGE_PRIORITY = {"VERIFIED": 0, "PARTIAL": 1}
ALLOWED_FACT_KEYS = {"refuge_capacity_full", "nights", "actividad_montana_o_escalada",
                     "cota_m", "noches"}


class BadRequest(ValueError):
    pass


def _load_fixture(name: str) -> dict:
    ref = resources.files("alraso.resources").joinpath(name)
    return json.loads(ref.read_text(encoding="utf-8"))


def _strict_bool(v: str):
    if v == "true":
        return True
    if v == "false":
        return False
    raise BadRequest(f"hecho booleano invalido: {v!r} (usa true/false)")


def _coerce_fact(key: str, raw: str):
    if key == "refuge_capacity_full":
        return _strict_bool(raw)
    if key in {"nights", "noches", "cota_m"}:
        try:
            n = int(raw)
        except ValueError:
            raise BadRequest(f"hecho numerico invalido: {key}={raw!r}") from None
        return n
    return raw  # opaque text: the core will fail it closed if used


def _fixture_rings(fx: dict) -> list[list[tuple[float, float]]]:
    return [[(float(lat), float(lon)) for lat, lon in ring]
            for ring in fx["geometry"]["rings_latlon"]]


class Service:
    """Fixtures and coverage are loaded once; the sqlite-backed resolver is
    per-thread (sqlite3 forbids cross-thread use; ThreadingHTTPServer would
    otherwise hit STORE_FAILURE, which fail-closed correctly hid the bug)."""

    def __init__(self) -> None:
        self.fx_goriz = _load_fixture("fixture_goriz.json")
        self.fx_ordesa = _load_fixture("fixture_ordesa.json")
        self._local = threading.local()
        self.docs: dict[str, dict] = {}
        for fx in (self.fx_ordesa, self.fx_goriz):
            for d in fx.get("source_documents", []):
                self.docs[d["id"]] = d
        self.coverage = json.loads((WEBAPP / "coverage.json").read_text(encoding="utf-8"))
        self.cov_provider = InMemorySpatialProvider()
        self.regions_by_id: dict[str, dict] = {}
        for region in self.coverage["regions"]:
            if "from_fixture" in region["geometry"]:
                rings = _fixture_rings(_load_fixture(region["geometry"]["from_fixture"]))
            else:
                rings = [[(float(lat), float(lon)) for lat, lon in ring]
                         for ring in region["geometry"]["rings_latlon"]]
            region["_rings"] = rings
            self.regions_by_id[region["id"]] = region
            self.cov_provider.add_scope(region["id"], region["name"], "COVERAGE", rings)

    @property
    def resolver(self) -> Resolver:
        resolver = getattr(self._local, "resolver", None)
        if resolver is None:
            store = BitemporalStore.connect(":memory:")
            ingest_corpus(store, self.fx_ordesa)
            ingest_corpus(store, self.fx_goriz)
            provider = InMemorySpatialProvider()
            scope = self.fx_goriz["spatial_scopes"][0]
            provider.add_scope(scope["id"], scope["official_name"], scope["scope_type"],
                               _fixture_rings(self.fx_goriz))
            resolver = Resolver(store, spatial=provider)
            self._local.resolver = resolver
        return resolver

    def coverage_for_point(self, lat: float, lon: float) -> list[dict]:
        try:
            hits = self.cov_provider.resolve(lat, lon)
        except Exception:  # noqa: BLE001 - coverage must never break a response
            return []
        regions = [self.regions_by_id[h.scope_id] for h in hits if h.scope_id in self.regions_by_id]
        return sorted(regions, key=lambda r: COVERAGE_PRIORITY.get(r["coverage"], 9))

    def sources_for(self, result: dict) -> list[dict]:
        out, seen = [], set()
        for ev in result.get("evidence", []):
            doc_id = ev.get("source_document_id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            doc = self.docs.get(doc_id, {})
            out.append({"id": doc_id, "title": doc.get("title", doc_id),
                        "canonical_url": doc.get("canonical_url", ""),
                        "official_status": doc.get("official_status", "")})
        return out


def resolve_point(svc: Service, *, lat: float, lon: float, activity: str,
                  activity_date: str, knowledge_date: str, facts: dict) -> dict:
    query = Query(activity=activity, activity_date=activity_date,
                  knowledge_date=knowledge_date, spatial_scope_id=None,
                  lat=lat, lon=lon, facts=facts)
    result = svc.resolver.resolve(query).to_dict()
    regions = svc.coverage_for_point(lat, lon)
    coverage_status = regions[0]["coverage"] if regions else "UNKNOWN"
    return {
        "determination": {
            "legalStatus": result["legalStatus"],
            "knowledgeStatus": result["knowledgeStatus"],
            "reasonCodes": result["reasonCodes"],
            "decisionReason": result["decisionReason"],
            "warnings": result["warnings"],
        },
        "conditions": result["conditions"],
        "applicableScope": result["applicableScope"],
        "coverage": {"status": coverage_status,
                     "regions": [{k: r.get(k) for k in
                                  ("id", "name", "coverage", "boundary", "verified_at",
                                   "summary", "norms", "notes")} for r in regions]},
        "sources": svc.sources_for(result),
        "query": result["query"],
    }


def parse_resolve_params(params: dict) -> dict:
    def _get(name: str, default=None):
        v = params.get(name)
        if isinstance(v, list):
            v = v[-1]
        return v if v not in (None, "") else default

    try:
        lat = float(_get("lat"))
        lon = float(_get("lon"))
    except (TypeError, ValueError):
        raise BadRequest("lat/lon numericos y obligatorios") from None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise BadRequest("lat/lon fuera de rango")
    if not math.isfinite(lat) or not math.isfinite(lon):
        raise BadRequest("lat/lon no finitos")
    today = date.today().isoformat()
    activity = _get("activity", "VIVAC_AL_RASO")
    for name in ("date", "knowledge"):
        v = _get(name, today)
        if not DATE_RE.match(v):
            raise BadRequest(f"{name} debe ser YYYY-MM-DD")
    facts = {}
    for key, raw in params.items():
        if key in ALLOWED_FACT_KEYS:
            facts[key] = _coerce_fact(key, raw[-1] if isinstance(raw, list) else raw)
    return {"lat": lat, "lon": lon, "activity": activity,
            "activity_date": _get("date", today), "knowledge_date": _get("knowledge", today),
            "facts": facts}


def coverage_geojson(svc: Service) -> dict:
    features = []
    for region in svc.coverage["regions"]:
        for ring in region["_rings"]:
            coords = [[lon, lat] for lat, lon in ring]
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            features.append({"type": "Feature", "geometry": {"type": "Polygon",
                           "coordinates": [coords]}, "properties": {
                "id": region["id"], "name": region["name"],
                "coverage": region["coverage"], "boundary": region["boundary"]}})
    return {"type": "FeatureCollection", "features": features}


STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/vendor/maplibre-gl.js": ("vendor/maplibre-gl.js", "text/javascript; charset=utf-8"),
    "/vendor/maplibre-gl.css": ("vendor/maplibre-gl.css", "text/css; charset=utf-8"),
}


def make_handler(svc: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AlRaso-M2/0.3"

        def log_message(self, fmt, *args):  # silencioso y seguro
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            try:
                if path == "/api/coverage":
                    self._json(HTTPStatus.OK, coverage_geojson(svc))
                elif path == "/api/resolve":
                    params = urllib.parse.parse_qs(parsed.query)
                    args = parse_resolve_params(params)
                    self._json(HTTPStatus.OK, resolve_point(svc, **args))
                elif path in STATIC_FILES:
                    rel, ctype = STATIC_FILES[path]
                    fp = STATIC / rel
                    if not fp.is_file():
                        self._json(HTTPStatus.NOT_FOUND, {"error": "asset_no_encontrado"})
                        return
                    self._send(HTTPStatus.OK, fp.read_bytes(), ctype)
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "ruta_desconocida"})
            except BadRequest as e:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "peticion_invalida", "detail": str(e)})
            except Exception as e:  # noqa: BLE001 - nunca un traceback al cliente
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                           {"error": "fallo_interno", "detail": f"{type(e).__name__}"})

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AlRaso M2 vertical slice (stdlib HTTP)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    svc = Service()
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(svc))
    print(f"ALRASO_WEB=http://{args.host}:{args.port}  (Ctrl+C para salir)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
