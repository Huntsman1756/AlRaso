"""M2 vertical slice: the webapp service reproduces the core's fail-closed
guarantees through the product API, coverage states are honest, and nothing
schematic can ever mint a PERMITTED. Offline: no server, no network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402

GORIZ_INSIDE = (42.6627475, 0.0159801)
TODAY = "2026-09-06"


@pytest.fixture(scope="module")
def svc() -> server.Service:
    return server.Service()


def _resolve(svc, lat, lon, facts=None, activity="VIVAC_AL_RASO"):
    return server.resolve_point(svc, lat=lat, lon=lon, activity=activity,
                                activity_date=TODAY, knowledge_date=TODAY,
                                facts=facts or {})


def test_goriz_inside_with_conditions_permitted(svc):
    out = _resolve(svc, *GORIZ_INSIDE, facts={"refuge_capacity_full": True, "nights": 2})
    assert out["determination"]["legalStatus"] == "PERMITTED"
    assert out["coverage"]["status"] == "VERIFIED"
    assert out["sources"], "a PERMITTED must show its official sources"


def test_goriz_inside_without_facts_never_permitted(svc):
    out = _resolve(svc, *GORIZ_INSIDE)
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert "ENGINE_MISSING_INPUT" in out["determination"]["reasonCodes"]


def test_picos_and_ordesa_schematic_are_partial_never_permitted(svc):
    picos = _resolve(svc, 43.17068, -4.80299)
    assert picos["determination"]["legalStatus"] == "UNDETERMINED"
    assert picos["coverage"]["status"] == "PARTIAL"
    ordesa = _resolve(svc, 42.66, 0.06)
    assert ordesa["determination"]["legalStatus"] == "UNDETERMINED"
    assert ordesa["coverage"]["status"] == "PARTIAL"


def test_point_without_corpus_is_unknown_not_prohibited(svc):
    out = _resolve(svc, 41.9, -2.4)
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert out["coverage"]["status"] == "UNKNOWN"
    assert out["coverage"]["regions"] == []


def test_schematic_boundaries_cannot_determine_legality(svc):
    manifest = json.loads((ROOT / "webapp" / "coverage.json").read_text(encoding="utf-8"))
    partial = [r for r in manifest["regions"] if r["coverage"] == "PARTIAL"]
    assert partial, "coverage must disclose PARTIAL zones"
    for r in partial:
        assert r["boundary"] == "esquematico"
    verified = [r for r in manifest["regions"] if r["coverage"] == "VERIFIED"]
    assert all(r["boundary"] == "oficial" for r in verified)
    assert all(r.get("norms") for r in manifest["regions"]), "each zone names its sources"


def test_coverage_geojson_marks_boundary_kind(svc):
    fc = server.coverage_geojson(svc)
    assert fc["type"] == "FeatureCollection" and fc["features"]
    kinds = {f["properties"]["boundary"] for f in fc["features"]}
    assert kinds == {"oficial", "esquematico"}


def test_parse_params_fail_closed_on_garbage():
    for bad in ({"lat": "abc", "lon": "0"}, {"lat": "0"}, {"lat": "95", "lon": "0"},
                {"lat": "nan", "lon": "0"}, {"lat": "0", "lon": "0", "date": "06-09-2026"}):
        with pytest.raises(server.BadRequest):
            server.parse_resolve_params(bad)
    ok = server.parse_resolve_params({"lat": "1.5", "lon": "2.5", "nights": "3",
                                      "refuge_capacity_full": "true",
                                      "actividad_montana_o_escalada": "true",
                                      "cota_m": "2400"})
    assert ok["facts"] == {"nights": 3, "refuge_capacity_full": True,
                           "actividad_montana_o_escalada": True, "cota_m": 2400}
    with pytest.raises(server.BadRequest):
        server.parse_resolve_params({"lat": "1.5", "lon": "2.5",
                                     "actividad_montana_o_escalada": "1"})


def test_bool_facts_accept_only_canonical_spellings():
    with pytest.raises(server.BadRequest):
        server._coerce_fact("refuge_capacity_full", "1")
    with pytest.raises(server.BadRequest):
        server._coerce_fact("refuge_capacity_full", "yes")


def test_frontend_assets_present_and_vendor_vendored():
    static = ROOT / "webapp" / "static"
    for name in ("index.html", "app.js", "style.css"):
        assert (static / name).read_text(encoding="utf-8").strip()
    js = static / "vendor" / "maplibre-gl.js"
    css = static / "vendor" / "maplibre-gl.css"
    assert js.stat().st_size > 500_000
    assert css.stat().st_size > 10_000


def test_vendored_maplibre_license_is_shipped_and_declared():
    vendor = ROOT / "webapp" / "static" / "vendor"
    header = "\n".join((vendor / "maplibre-gl.js").read_text(encoding="utf-8")
                       .splitlines()[:5])
    assert "MapLibre GL JS" in header
    assert "https://github.com/maplibre/maplibre-gl-js/blob/v4.7.1/LICENSE.txt" in header
    license_text = (vendor / "MAPLIBRE-LICENSE.txt").read_text(encoding="utf-8")
    assert "Copyright (c) 2023, MapLibre contributors" in license_text
    assert "Copyright (c) 2020, Mapbox" in license_text
    assert "glfx.js" in license_text
    assert "d3-color" in license_text
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "MapLibre GL JS" in notice
    assert "maplibre-gl-js) 4.7.1" in notice
    assert "BSD-3-Clause" in notice
    assert "webapp/static/vendor/MAPLIBRE-LICENSE.txt" in notice
    assert "THIRD_PARTY_CODE_DISTRIBUTED=maplibre_gl_js_4.7.1" in notice


def test_http_layer_rejects_unknown_paths_and_serves_api(monkeypatch):
    # unit-level: the route table exposes no traversal and the API parses strictly
    assert "/" in server.STATIC_FILES
    assert not any(".." in p or "\\" in p for p in server.STATIC_FILES)
    with pytest.raises(server.BadRequest):
        server.parse_resolve_params({"lat": "", "lon": ""})


def test_map_style_url_defaults_to_openfreemap_without_key(monkeypatch):
    monkeypatch.delenv("ALRASO_MAP_STYLE_URL", raising=False)
    assert server.map_style_url() == "https://tiles.openfreemap.org/styles/liberty"


def test_map_style_url_is_configurable_by_env(monkeypatch):
    monkeypatch.setenv("ALRASO_MAP_STYLE_URL", "https://tiles.openfreemap.org/styles/positron")
    assert server.map_style_url() == "https://tiles.openfreemap.org/styles/positron"


def test_map_style_url_fails_closed_to_default_on_garbage(monkeypatch):
    for bad in ("javascript:alert(1)", "not a url", "ftp://example/x", "   ", "://nope"):
        monkeypatch.setenv("ALRASO_MAP_STYLE_URL", bad)
        assert server.map_style_url() == server.DEFAULT_MAP_STYLE_URL, bad


def test_frontend_provider_is_decoupled_not_hardcoded():
    js = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" not in js, "M2.2: no direct OSMF tile usage"
    assert "/api/config" in js, "the map style must come from server config"


POI_CATS = {"refuge", "shelter", "water", "camping", "protected_area"}


def test_pois_geojson_is_wellformed_and_categorized(svc):
    fc = server.pois_geojson(svc)
    assert fc["type"] == "FeatureCollection" and fc["features"]
    cats = set()
    for f in fc["features"]:
        assert f["geometry"]["type"] == "Point"
        lon, lat = f["geometry"]["coordinates"]
        assert -180 <= lon <= 180 and -90 <= lat <= 90
        cats.add(f["properties"]["category"])
    assert cats == POI_CATS


def test_pois_are_observational_never_legal(svc):
    fc = server.pois_geojson(svc)
    legal_keys = {"legalStatus", "knowledgeStatus", "determination", "permitido",
                  "permitted", "coverage", "prohibido"}
    for f in fc["features"]:
        props = set(f["properties"])
        assert not (props & legal_keys), f["properties"].get("id")


def test_poi_has_provenance(svc):
    fc = server.pois_geojson(svc)
    for f in fc["features"]:
        props = f["properties"]
        assert props["source"] in ("openstreetmap", "alraso"), props["id"]
        assert props["source_label"], props["id"]
        assert props["region"] in ("ordesa", "picos"), props["id"]
        assert props["name"], props["id"]
        if props["source"] == "openstreetmap":
            assert props["source_ref"], props["id"]
            assert props["osm_url"], props["id"]
    # goriz es ancla del proyecto, no OSM redistribuido.
    goriz = next(p for p in fc["features"] if p["properties"]["id"] == "poi-goriz")["properties"]
    assert goriz["source"] == "alraso"
    assert goriz["source_ref"] == "alraso_anchor"
    assert goriz["osm_url"] == ""


def test_every_osm_feature_has_reconstructible_source_ref(svc):
    fc = server.pois_geojson(svc)
    for f in fc["features"]:
        props = f["properties"]
        if props["source"] != "openstreetmap":
            continue
        assert props["source_ref"].startswith(("node/", "way/", "relation/")), props["id"]
        assert props["osm_url"].startswith("https://www.openstreetmap.org/"), props["id"]


def test_poi_policy_states_separation():
    doc = json.loads((ROOT / "webapp" / "pois.json").read_text(encoding="utf-8"))
    policy = doc["policy"].lower()
    assert "observacional" in policy
    assert "no es un permiso" in policy or "no implica" in policy
    # Ningun POI lleva un campo de determinacion legal en el propio dato.
    for f in doc["features"]:
        assert "legalStatus" not in f and "coverage" not in f, f["id"]


def test_poi_search_returns_poi_kind_not_place(svc):
    out = server.find_query(svc, "Turieto")
    assert out["kind"] == "poi"
    assert out["source"] == "openstreetmap"
    assert out["category"] == "refuge"
    assert out["name"] == "Refugio de Turieto"
    # La busqueda puede mover el mapa, pero nunca suministra hechos al resolver.
    for key in ("facts", "nights", "refuge_capacity_full"):
        assert key not in out


def test_curated_search_takes_precedence_over_poi(svc):
    # "goriz" coincide con el lugar curado (refugio-goriz) Y con el POI goriz:
    # debe ganar el lugar curado, no el POI.
    out = server.find_query(svc, "goriz")
    assert out["kind"] == "place"
    assert out["id"] == "refugio-goriz"


def test_poi_provenance_is_reproducible():
    doc = json.loads((ROOT / "webapp" / "pois.json").read_text(encoding="utf-8"))
    m = doc["metadata"]
    assert m["snapshot"] is True and m["may_be_stale"] is True
    assert m["retrieved_at"] == "2026-09-06"
    assert m["source"] == "OpenStreetMap"
    assert "overpass-api.de" in m["overpass_endpoint"]
    for key in ("query_ordesa", "query_picos", "query_protected_ordesa", "query_protected_picos"):
        assert m[key].startswith("[out:json]"), key
    for key in ("ordesa_overpass_response_sha256", "picos_overpass_response_sha256",
                "protected_ordesa_overpass_response_sha256",
                "protected_picos_overpass_response_sha256"):
        assert len(m["source_digests"][key]) == 64, key
    assert m["license"] == "ODbL-1.0"
    assert m["license_url"].startswith("https://")
    assert "OpenStreetMap contributors" in m["attribution"]


def test_poi_notes_do_not_claim_park_membership():
    doc = json.loads((ROOT / "webapp" / "pois.json").read_text(encoding="utf-8"))
    # No se afirma pertenencia a un parque por haber salido de un bounding box.
    banned = ("en el valle de Ordesa", "en picos de europa", "en el pirineo aragonés",
              "en el macizo central de picos", "parque nacional")
    for f in doc["features"]:
        if f.get("source") != "openstreetmap":
            continue  # goriz es ancla del proyecto
        if f["category"] == "protected_area":
            continue  # nombre oficial del objeto OSM (referencia), no inferencia
        low = f["note"].lower()
        for b in banned:
            assert b not in low, f"POI {f['id']} afirma región sin contenedor: {f['note']}"


def test_poi_no_duplicate_ids_and_valid_coords(svc):
    fc = server.pois_geojson(svc)
    ids = [f["properties"]["id"] for f in fc["features"]]
    assert len(ids) == len(set(ids)), "POI ids deben ser unicos"
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        assert -180 <= lon <= 180 and -90 <= lat <= 90
        assert isinstance(lat, float) and isinstance(lon, float)


def test_protected_area_is_osm_reference_not_legal_layer():
    doc = json.loads((ROOT / "webapp" / "pois.json").read_text(encoding="utf-8"))
    label = doc["categories"]["protected_area"]["label"]
    assert "OSM" in label, "la capa protegida debe llamarse referencia OSM, no capa juridica"
    for f in doc["features"]:
        if f["category"] == "protected_area":
            assert "No determina el ámbito jurídico" in f["note"], f["id"]
            assert "prohibición automática" in f["note"], f["id"]
            assert f["source_ref"].startswith("relation/"), f["id"]
    # protected_area queda en provenance pero NO se renderiza ni es interactivo.
    js = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    assert "poi-circles-protected_area" not in js, "no se renderiza como capa POI"
    assert "lg-protected" not in js, "no hay toggle de espacios protegidos"
    assert 'const POI_ORDER = ["refuge", "shelter", "water", "camping"];' in js
    html = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
    assert "lg-protected" not in html, "no hay checkbox de espacios protegidos"
    assert "/api/coverage" in js and "/api/pois" in js


def test_find_excludes_protected_area(svc):
    # El espacio protegido no es un destino interactivo: no debe aparecer en la busqueda.
    assert server.find_query(svc, "Parque Nacional de Ordesa")["kind"] == "none"
    assert server.find_query(svc, "Parque Nacional de Picos")["kind"] == "none"


def test_unknown_coverage_knowledge_copy(svc):
    out = server.resolve_point(svc, lat=41.9, lon=-2.4, activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY, facts={})
    assert out["coverage"]["status"] == "UNKNOWN"
    assert out["determination"]["knowledgeStatus"] == "CURRENT"  # canonico intacto
    assert out["ui"]["knowledge"] == "No disponemos de información normativa para esta zona"


def test_picos_product_is_jurisdiction_aware(svc):
    # P1 Urriellu (es-as) con hechos -> PERMITTED por art. 51; cobertura PARTIAL (DEM=C).
    out = server.resolve_point(svc, lat=43.2662, lon=-4.8686, activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY,
                               facts={"actividad_montana_o_escalada": True,
                                      "nights": 2, "cota_m": 2400})
    assert out["determination"]["legalStatus"] == "PERMITTED"
    assert out["coverage"]["status"] == "PARTIAL"
    assert any(r["scope_id"] == "ss-pnpe-es-as" for r in out["applicableScope"])


def test_picos_product_without_facts_never_permitted(svc):
    out = server.resolve_point(svc, lat=43.2662, lon=-4.8686, activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY, facts={})
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert "ENGINE_MISSING_INPUT" in out["determination"]["reasonCodes"]


def test_picos_boundary_guard_fails_closed(svc):
    # P4a: 300 m de la frontera ES13|ES12. La app calcula boundary_safe=False
    # (hecho interno) -> la regla no sostiene PERMITTED -> UNDETERMINED + motivo.
    out = server.resolve_point(svc, lat=43.25005, lon=-4.72339, activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY,
                               facts={"actividad_montana_o_escalada": True,
                                      "nights": 2, "cota_m": 2400})
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert "BOUNDARY_EVIDENCE_INCOMPLETE" in out["determination"]["reasonCodes"]
    assert any("BOUNDARY_EVIDENCE_INCOMPLETE" in w for w in out["determination"]["warnings"])


def test_internal_fact_not_accept_from_query():
    # El guard de frontera es un hecho interno calculado por la app: no puede
    # falsearse desde la URL (no está en ALLOWED_FACT_KEYS).
    params = server.parse_resolve_params({"lat": "43.2662", "lon": "-4.8686",
                                          "jurisdiction_boundary_safe": "true"})
    assert "jurisdiction_boundary_safe" not in params["facts"]


def test_pois_do_not_change_resolution(svc):
    # La existencia de un POI en unas coordenadas no altera la determinacion:
    # el POI del refugio de Goriz resuelve igual que el punto de control.
    poi = next(p for p in svc.pois if p["id"] == "poi-goriz")
    out = server.resolve_point(svc, lat=poi["lat"], lon=poi["lon"], activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY,
                               facts={"refuge_capacity_full": True, "nights": 2})
    assert out["determination"]["legalStatus"] == "PERMITTED"
    assert out["coverage"]["status"] == "VERIFIED"
    assert "poi-goriz" not in json.dumps(out), "POIs nunca aparecen en la determinacion"
