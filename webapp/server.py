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
import os
import re
import sys
import threading
import unicodedata
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

import dem  # optional auto-elevation (extra alraso[dem]); fail-closed if absent

WEBAPP = Path(__file__).resolve().parent
STATIC = WEBAPP / "static"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COVERAGE_PRIORITY = {"VERIFIED": 0, "PARTIAL": 1}
ALLOWED_FACT_KEYS = {"refuge_capacity_full", "nights", "actividad_montana_o_escalada",
                     "cota_m", "noches"}
SEMICOLON_DECIMAL_RE = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*;\s*(-?\d+(?:[.,]\d+)?)$")
COMMA_OR_SPACE_RE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$")

# Capa de lenguaje llano para personas. Los codigos canonicos NUNCA desaparecen
# de la respuesta (determination.*); esto es solo presentacion y no puede
# cambiar ninguna determinacion. Codigo desconocido -> se muestra tal cual.
PLAIN_LEGAL = {
    "PERMITTED": "Permitido según la normativa verificada",
    "PROHIBITED": "Prohibido según la normativa verificada",
    "AUTHORIZATION_REQUIRED": "Necesitas una autorización previa",
    "UNDETERMINED": "No lo podemos determinar",
}
PLAIN_KNOWLEDGE = {
    "CURRENT": "Información normativa verificada para la fecha consultada",
    "INCOMPLETE": "Información normativa incompleta",
    "CONFLICTING": "Fuentes normativas en conflicto",
}
PLAIN_COVERAGE = {
    "VERIFIED": "Cobertura completa para este punto",
    "PARTIAL": "Cobertura parcial: normativa de la zona verificada, respuesta punto a punto sin cerrar",
    "UNKNOWN": "Sin información en esta zona",
}

# Proveedor de basemap desacoplado. El navegador NO puede leer variables de
# entorno del servidor, asi que la unica configuracion limpia para esta app
# stdlib es: server lee ALRASO_MAP_STYLE_URL, expone /api/config, y el
# frontend la consume antes de crear el mapa. Rollback real: cambiar el env y
# reiniciar. Sin claves: OpenFreeMap no las necesita. No se hardcodea el
# proveedor en el frontend.
DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"


def map_style_url() -> str:
    """URL del estilo MapLibre. Defensivo: solo se acepta un http(s) absoluto;
    un valor malformed cae al default aprobado (OpenFreeMap) en vez de romper
    el arranque o servir algo que MapLibre no pueda consumir."""
    raw = (os.environ.get("ALRASO_MAP_STYLE_URL") or "").strip()
    if not raw:
        return DEFAULT_MAP_STYLE_URL
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return DEFAULT_MAP_STYLE_URL
    if parsed.scheme in ("https", "http") and parsed.netloc:
        return raw
    return DEFAULT_MAP_STYLE_URL


def ui_texto(legal: str, knowledge: str, coverage: str, conditions: list) -> dict:
    if legal == "UNDETERMINED":
        if coverage == "UNKNOWN":
            headline = ("No sabemos: aquí no hay ninguna normativa estudiada todavía. "
                        "No es un permiso, pero tampoco una prohibición.")
        elif coverage == "PARTIAL":
            headline = ("Todavía no podemos afirmarlo: conocemos la normativa de esta zona, "
                        "pero la comprobación punto a punto no está cerrada. "
                        "No es un permiso, pero tampoco una prohibición.")
        else:
            headline = ("No podemos afirmarlo con los datos actuales: faltan condiciones "
                        "por confirmar. No es un permiso, pero tampoco una prohibición.")
    elif legal == "PERMITTED":
        headline = "Permitido según la normativa verificada" + \
                   (" — bajo las condiciones indicadas" if conditions else "")
    elif legal == "PROHIBITED":
        headline = "Prohibido según la normativa verificada"
    elif legal == "AUTHORIZATION_REQUIRED":
        headline = "Solo con autorización previa"
    else:
        headline = legal
    # Capa de presentación contextualiza ambos ejes. Si no hay corpus (UNKNOWN),
    # el eje de "estado de la información" no puede leerse como "verificada",
    # aunque internamente knowledgeStatus=CURRENT venga del resolver. El código
    # canónico (determination.knowledgeStatus) NO cambia; solo se ajusta el plain.
    if coverage == "UNKNOWN":
        knowledge_plain = "No disponemos de información normativa para esta zona"
    else:
        knowledge_plain = PLAIN_KNOWLEDGE.get(knowledge, knowledge)
    return {
        "headline": headline,
        "legal": PLAIN_LEGAL.get(legal, legal),
        "knowledge": knowledge_plain,
        "coverage": PLAIN_COVERAGE.get(coverage, coverage),
    }


def _norm_name(s: str) -> str:
    decomposed = unicodedata.normalize("NFD", s.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _strict_coord(text: str) -> tuple[float, float]:
    lat, lon = (float(part.replace(",", ".")) for part in text)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise BadRequest("coordenadas fuera de rango")
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise BadRequest("coordenadas no finitas")
    return lat, lon


def find_query(svc: "Service", text: str) -> dict:
    """Búsqueda de producto: coordenadas ('42.66, 0.01' / '42,66; 0,01') o
    nombre aproximado de un sitio conocido. Nunca adivina: sin coincidencia
    clara devuelve kind=none."""
    q = (text or "").strip()
    if not q:
        raise BadRequest("consulta vacia")
    m = SEMICOLON_DECIMAL_RE.match(q)
    if m:
        lat, lon = _strict_coord((m.group(1), m.group(2)))
        return {"kind": "coords", "lat": lat, "lon": lon}
    m = COMMA_OR_SPACE_RE.match(q)
    if m:
        lat, lon = _strict_coord((m.group(1), m.group(2)))
        return {"kind": "coords", "lat": lat, "lon": lon}
    needle = _norm_name(q)
    matches = [p for p in svc.places if needle in _norm_name(p["name"])]
    if len(matches) == 1:
        return {"kind": "place", **matches[0]}
    if len(matches) > 1:
        return {"kind": "ambiguous", "matches": matches[:8]}
    # Sin coincidencia en la lista curada, se consultan los POIs observacionales.
    # Son solo cartografia (OSM): su aparicion en la busqueda mueve el mapa pero
    # NUNCA suministra hechos al resolver. Se marca kind=poi + source para que la
    # UI no los trate como un lugar curado. protected_area NO se busca (no es un
    # destino interactivo).
    poi_matches = [p for p in svc.pois
                   if p["category"] != "protected_area" and needle in _norm_name(p["name"])]
    if len(poi_matches) == 1:
        p = poi_matches[0]
        return {"kind": "poi", "source": p.get("source", "openstreetmap"),
                "category": p["category"], "id": p["id"], "name": p["name"],
                "lat": p["lat"], "lon": p["lon"], "alt_m": p.get("alt_m"),
                "source_label": p.get("source_label", "OSM"),
                "source_ref": p.get("source_ref", ""),
                "osm_url": p.get("osm_url", ""), "note": p.get("note", "")}
    if len(poi_matches) > 1:
        return {"kind": "ambiguous",
                "matches": [{"kind": "poi", "source": p.get("source", "openstreetmap"),
                             "category": p["category"], "id": p["id"], "name": p["name"],
                             "lat": p["lat"], "lon": p["lon"], "note": p.get("note", "")}
                            for p in poi_matches[:8]]}
    return {"kind": "none"}


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
    if key in {"refuge_capacity_full", "actividad_montana_o_escalada"}:
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


# Picos Phase B: el fixture tiene varios scopes, cada uno con su geometria bajo
# "geometry[<clave>]". Mapea scope_id -> clave de geometria (unica por scope).
_PICOS_GEOM_KEY = {
    "ss-pnpe-limits": "park",
    "ss-pnpe-es-as": "es-as",
    "ss-pnpe-es-cb": "es-cb",
    "ss-pnpe-es-cl": "es-cl",
}


def _picos_scope_rings(fx: dict, scope_id: str) -> list[list[tuple[float, float]]]:
    key = _PICOS_GEOM_KEY.get(scope_id)
    rings = fx.get("geometry", {}).get(key) if key else None
    if not rings:
        return []
    return [[(float(lat), float(lon)) for lat, lon in ring] for ring in rings]


class Service:
    """Fixtures and coverage are loaded once; the sqlite-backed resolver is
    per-thread (sqlite3 forbids cross-thread use; ThreadingHTTPServer would
    otherwise hit STORE_FAILURE, which fail-closed correctly hid the bug)."""

    def __init__(self) -> None:
        self.fx_goriz = _load_fixture("fixture_goriz.json")
        self.fx_ordesa = _load_fixture("fixture_ordesa.json")
        self.fx_picos = _load_fixture("fixture_picos.json")
        self._local = threading.local()
        self.docs: dict[str, dict] = {}
        for fx in (self.fx_ordesa, self.fx_goriz, self.fx_picos):
            for d in fx.get("source_documents", []):
                self.docs[d["id"]] = d
        self.coverage = json.loads((WEBAPP / "coverage.json").read_text(encoding="utf-8"))
        places_doc = json.loads((WEBAPP / "places.json").read_text(encoding="utf-8"))
        self.places = [{k: p[k] for k in ("id", "name", "lat", "lon", "note")}
                       for p in places_doc["places"]]
        pois_doc = json.loads((WEBAPP / "pois.json").read_text(encoding="utf-8"))
        # POIs se guardan completos (categoria, altitud, fuente, nota) para la capa
        # observacional. NUNCA entran en el resolver: son cartografia, no derecho.
        # protected_area queda en el snapshot/provenance pero NO es interactivo.
        self.pois = list(pois_doc["features"])
        self.searchable = (self.places +
                           [{k: p[k] for k in ("id", "name", "lat", "lon", "note")}
                            for p in self.pois if p["category"] != "protected_area"])
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
            ingest_corpus(store, self.fx_picos)
            provider = InMemorySpatialProvider()
            scope = self.fx_goriz["spatial_scopes"][0]
            provider.add_scope(scope["id"], scope["official_name"], scope["scope_type"],
                               _fixture_rings(self.fx_goriz))
            # Picos: varios scopes (parque = contexto; CCAA = regulatorio) con geometria propia.
            for sc in self.fx_picos["spatial_scopes"]:
                rings = _picos_scope_rings(self.fx_picos, sc["id"])
                if rings:
                    provider.add_scope(sc["id"], sc["official_name"], sc["scope_type"], rings)
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


INTERNAL_BOUNDARY_FACT = "jurisdiction_boundary_safe"
_CCAA_SECTOR_KEY = {
    "ss-pnpe-es-as": "es-as",
    "ss-pnpe-es-cb": "es-cb",
    "ss-pnpe-es-cl": "es-cl",
}
_BOUNDARY_UNCERTAINTY_M = 1000.0


def _point_in_ring(lat: float, lon: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _seg_dist_m(lat, lon, a_lat, a_lon, b_lat, b_lon) -> float:
    """Distancia (m) punto->segmento, proyección equirectangular local."""
    R = 6371000.0
    kx = math.cos(math.radians(lat)) * R
    x, y = math.radians(lon) * kx, math.radians(lat) * R
    x1, y1 = math.radians(a_lon) * kx, math.radians(a_lat) * R
    x2, y2 = math.radians(b_lon) * kx, math.radians(b_lat) * R
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def _picos_sectors_containing(svc: "Service", lat: float, lon: float) -> list[str]:
    geo = svc.fx_picos.get("geometry", {})
    sectors = {sid: geo.get(key, []) for sid, key in _CCAA_SECTOR_KEY.items()}
    return [sid for sid, rings in sectors.items()
            if any(_point_in_ring(lat, lon, r) for r in rings)]


def jurisdiction_boundary_safe(svc: "Service", lat: float, lon: float) -> bool:
    """Hecho INTERNO, calculado por la app (nunca aportable por query).

    True si el punto NO está dentro de la franja de incertidumbre (<1 km)
    respecto al borde de OTRO sector CCAA. Fail-closed: ante cualquier duda
    (excepción, geometría ausente) -> False.
    """
    try:
        containing = _picos_sectors_containing(svc, lat, lon)
        if not containing:
            return True  # fuera de todo sector CCAA -> sin conflicto de frontera
        geo = svc.fx_picos.get("geometry", {})
        sectors = {sid: geo.get(key, []) for sid, key in _CCAA_SECTOR_KEY.items()}
        for sid in containing:
            for other_sid, rings in sectors.items():
                if other_sid == sid:
                    continue
                for ring in rings:
                    n = len(ring)
                    for i in range(n):
                        a, b = ring[i], ring[(i + 1) % n]
                        if _seg_dist_m(lat, lon, a[0], a[1], b[0], b[1]) < _BOUNDARY_UNCERTAINTY_M:
                            return False
        return True
    except Exception:  # noqa: BLE001 - fail-closed, nunca un permiso por duda
        return False


def resolve_point(svc: Service, *, lat: float, lon: float, activity: str,
                  activity_date: str, knowledge_date: str, facts: dict) -> dict:
    # Hecho INTERNO de seguridad de frontera: la app lo calcula y lo inyecta.
    # Nunca se acepta por query; si la app no lo calcula, el resolver falla
    # cerrado (ENGINE_MISSING_INPUT) -> un permiso no puede escapar al guard.
    facts = dict(facts)
    boundary_safe = jurisdiction_boundary_safe(svc, lat, lon)
    facts[INTERNAL_BOUNDARY_FACT] = boundary_safe

    # AUTO-ELEVATION (solo ámbito Picos): si el punto está en un sector CCAA de
    # Picos, se intenta el DEM oficial. DEM produce un FACT_SOURCE (cota_m +
    # provenance); NUNCA decide legalidad (el resolver evalúa cota_m > 1800).
    # Política: DEM oficial tiene prioridad cuando está disponible; si difiere
    # materialmente del valor del usuario, se muestra un warning.
    user_cota = facts.get("cota_m")
    dem_info = None
    user_vs_dem = None
    cota_fact_source = "USER" if user_cota is not None else "NONE"
    if _picos_sectors_containing(svc, lat, lon):
        try:
            dem_info = dem.sample_elevation(lat, lon)
        except dem.DemEvidenceIncomplete:
            dem_info = None
        if dem_info:
            facts["cota_m"] = dem_info["value_m"]
            cota_fact_source = "OFFICIAL_DEM"
            if user_cota is not None:
                diff = abs(float(user_cota) - float(dem_info["value_m"]))
                user_vs_dem = {"USER_COTA_M": float(user_cota),
                               "DEM_COTA_M": float(dem_info["value_m"]),
                               "DIFF_M": round(diff, 1)}

    query = Query(activity=activity, activity_date=activity_date,
                  knowledge_date=knowledge_date, spatial_scope_id=None,
                  lat=lat, lon=lon, facts=facts)
    result = svc.resolver.resolve(query).to_dict()
    regions = svc.coverage_for_point(lat, lon)
    coverage_status = regions[0]["coverage"] if regions else "UNKNOWN"
    out = {
        "determination": {
            "legalStatus": result["legalStatus"],
            "knowledgeStatus": result["knowledgeStatus"],
            "reasonCodes": result["reasonCodes"],
            "decisionReason": result["decisionReason"],
            "warnings": result["warnings"],
        },
        "ui": ui_texto(result["legalStatus"], result["knowledgeStatus"],
                       coverage_status, result["conditions"]),
        "conditions": result["conditions"],
        "applicableScope": result["applicableScope"],
        "coverage": {"status": coverage_status,
                     "regions": [{k: r.get(k) for k in
                                  ("id", "name", "coverage", "boundary", "verified_at",
                                   "summary", "norms", "notes")} for r in regions]},
        "sources": svc.sources_for(result),
        "query": result["query"],
        "cotaFactSource": cota_fact_source,
        "dem": dem_info,
        "userVsDem": user_vs_dem,
    }
    if not boundary_safe:
        # La frontera CCAA está en la franja de incertidumbre (<1 km): el
        # PERMITTED no puede sostenerse sin re-verificación IDE.
        out["determination"]["warnings"].append(
            "Punto dentro de la zona de incertidumbre de frontera CCAA (<1 km): "
            "BOUNDARY_EVIDENCE_INCOMPLETE. Se requiere re-verificación IDE.")
        if "BOUNDARY_EVIDENCE_INCOMPLETE" not in out["determination"]["reasonCodes"]:
            out["determination"]["reasonCodes"].append("BOUNDARY_EVIDENCE_INCOMPLETE")
    if user_vs_dem and user_vs_dem["DIFF_M"] > 100:
        out["determination"]["warnings"].append(
            f"La altitud indicada por el usuario ({user_vs_dem['USER_COTA_M']} m) difiere "
            f"materialmente del DEM oficial ({user_vs_dem['DEM_COTA_M']} m); se usa el DEM "
            "oficial (COTA_FACT_SOURCE=OFFICIAL_DEM).")
    return out


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


def pois_geojson(svc: Service) -> dict:
    """Capa OBSERVACIONAL de puntos de interes. Solo cartografia: describe donde
    existe algo (refugio, fuente, abrigo, camping, espacio protegido) segun OSM.
    No contiene ninguna determinacion legal y no puede modificarla."""
    features = []
    for p in svc.pois:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
            "properties": {
                "id": p["id"], "name": p["name"], "category": p["category"],
                "alt_m": p.get("alt_m"), "source": p.get("source", "openstreetmap"),
                "region": p.get("region", ""),
                "source_label": p.get("source_label", "OSM"),
                "source_ref": p.get("source_ref", ""),
                "osm_url": p.get("osm_url", ""), "note": p.get("note", ""),
            },
        })
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
                elif path == "/api/config":
                    self._json(HTTPStatus.OK, {"mapStyleUrl": map_style_url()})
                elif path == "/api/places":
                    self._json(HTTPStatus.OK, {"places": svc.searchable})
                elif path == "/api/pois":
                    self._json(HTTPStatus.OK, pois_geojson(svc))
                elif path == "/api/find":
                    params = urllib.parse.parse_qs(parsed.query)
                    q = params.get("q", [""])[-1]
                    self._json(HTTPStatus.OK, find_query(svc, q))
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
