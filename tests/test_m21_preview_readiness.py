"""M2.1 preview readiness: plain-language layer never lies, search is
fail-closed, curated places obey the M2 invariants, and the markup keeps the
accessibility hooks we promised. Offline: no server, no network."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402

TODAY = "2026-09-06"


@pytest.fixture(scope="module")
def svc() -> server.Service:
    return server.Service()


def _resolve(svc, lat, lon, facts=None, activity="VIVAC_AL_RASO"):
    return server.resolve_point(svc, lat=lat, lon=lon, activity=activity,
                                activity_date=TODAY, knowledge_date=TODAY,
                                facts=facts or {})


def test_plain_labels_never_remove_canonical_codes(svc):
    out = _resolve(svc, 42.6627475, 0.0159801,
                   facts={"refuge_capacity_full": True, "nights": 2})
    assert out["determination"]["legalStatus"] == "PERMITTED"
    assert out["ui"]["legal"] == "Permitido según la normativa verificada"
    assert out["ui"]["headline"].startswith("Permitido según la normativa verificada")
    assert "condiciones" in out["ui"]["headline"]


def test_all_known_codes_have_plain_labels():
    for code in ("PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED", "UNDETERMINED"):
        assert code in server.PLAIN_LEGAL
    for code in ("CURRENT", "INCOMPLETE", "CONFLICTING"):
        assert code in server.PLAIN_KNOWLEDGE
    for code in ("VERIFIED", "PARTIAL", "UNKNOWN"):
        assert code in server.PLAIN_COVERAGE
    unknown = server.ui_texto("SOMETHING_NEW", "CURRENT", "UNKNOWN", [])
    assert unknown["legal"] == "SOMETHING_NEW"
    assert unknown["headline"] == "SOMETHING_NEW"
    assert unknown["knowledge"] == "Información normativa verificada para la fecha consultada"
    assert "al dÍa".casefold() not in server.PLAIN_KNOWLEDGE["CURRENT"].casefold()


@pytest.mark.parametrize("lat,lon", [
    (42.6627475, 0.0159801),   # VERIFIED sin hechos -> UNDETERMINED
    (42.66, 0.06),             # PARTIAL
    (41.9, -2.4),              # UNKNOWN
])
def test_undetermined_never_reads_as_permission_or_prohibition(svc, lat, lon):
    out = _resolve(svc, lat, lon)
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert out["ui"]["legal"] == "No lo podemos determinar"
    headline = out["ui"]["headline"]
    assert "no es un permiso, pero tampoco una prohibición" in headline.casefold()


def test_find_accepts_coordinate_spellings(svc):
    for q in ("42.6627475, 0.0159801", "42.6627475 0.0159801", "42,6627475; 0,0159801"):
        found = server.find_query(svc, q)
        assert found["kind"] == "coords"
        assert found["lat"] == pytest.approx(42.6627475)
        assert found["lon"] == pytest.approx(0.0159801)


def test_find_place_is_accent_and_case_insensitive(svc):
    for q in ("goriz", "GÓRIZ", "refugio de goriz"):
        found = server.find_query(svc, q)
        assert found["kind"] == "place"
        assert found["id"] == "refugio-goriz"


def test_find_fails_closed_on_garbage(svc):
    assert server.find_query(svc, "no-existe-nada-parecido")["kind"] == "none"
    assert server.find_query(svc, "42.66")["kind"] == "none"
    assert server.find_query(svc, "42.66, 0.01, 3")["kind"] == "none"
    with pytest.raises(server.BadRequest):
        server.find_query(svc, "   ")
    with pytest.raises(server.BadRequest):
        server.find_query(svc, "95.0, 0.0")


def test_places_are_curated_and_obey_m2_invariants(svc):
    assert svc.places, "la lista de sitios no puede estar vacia"
    ids = {p["id"] for p in svc.places}
    assert len(ids) == len(svc.places)
    expected_coverage = {
        "refugio-goriz": "VERIFIED",
        "pradera-ordesa": "PARTIAL",
        "cares-picos": "PARTIAL",
        "torla-portal": "UNKNOWN",
        "control-sin-corpus": "UNKNOWN",
    }
    assert {p["id"] for p in svc.places} == set(expected_coverage)
    for place in svc.places:
        out = _resolve(svc, place["lat"], place["lon"])
        assert out["coverage"]["status"] == expected_coverage[place["id"]], place["id"]
        assert out["determination"]["legalStatus"] != "PERMITTED", (
            "ningun lugar conocido puede dar PERMITTED sin hechos: invariante M2")


def test_frontend_markup_keeps_accessibility_and_plain_layer_hooks():
    html = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
    for hook in ('role="search"', 'id="q"', 'list="places-list"', 'aria-live="polite"',
                 'id="headline"', 'id="center-btn"', 'id="tech-codes"',
                 'for="activity"', "no es un permiso,", "Detalle técnico"):
        assert hook in html, hook
    css = (ROOT / "webapp" / "static" / "style.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css
    assert "min-height:44px" in css
    js = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    assert "/api/find" in js and "/api/places" in js and "getCenter" in js
