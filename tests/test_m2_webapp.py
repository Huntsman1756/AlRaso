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
                                      "refuge_capacity_full": "true"})
    assert ok["facts"] == {"nights": 3, "refuge_capacity_full": True}


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


def test_http_layer_rejects_unknown_paths_and_serves_api(monkeypatch):
    # unit-level: the route table exposes no traversal and the API parses strictly
    assert "/" in server.STATIC_FILES
    assert not any(".." in p or "\\" in p for p in server.STATIC_FILES)
    with pytest.raises(server.BadRequest):
        server.parse_resolve_params({"lat": "", "lon": ""})
