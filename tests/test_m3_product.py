"""M3 product MVP: tabs, geolocation, favorites, outings, profile, store module.
Offline: no server, no network — static content assertions + server-level resolve tests."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402

TODAY = "2026-09-06"


# ─────────────────────────────────────────────
# Helper to read static files
# ─────────────────────────────────────────────
def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


# ══════════════════════════════════════════════
# 1. STATIC ASSETS
# ══════════════════════════════════════════════

def test_new_static_assets_registered_and_safe():
    """server.STATIC_FILES contains /store.js, no path traversal."""
    sf = server.STATIC_FILES
    assert "/store.js" in sf
    assert "/" in sf
    assert "/app.js" in sf
    assert "/style.css" in sf
    # No path traversal
    for p in sf:
        assert ".." not in p
        assert "\\" not in p


# ══════════════════════════════════════════════
# 2. STORAGE SCHEMA
# ══════════════════════════════════════════════

def test_storage_schema_persists_only_user_metadata():
    """store.js contains the two storage keys and expected fields."""
    js = _read("webapp/static/store.js")

    # Storage keys
    assert '"alraso.favorites.v1"' in js or "'alraso.favorites.v1'" in js
    assert '"alraso.outings.v1"' in js or "'alraso.outings.v1'" in js

    # Favorite fields
    for field in ("id", "name", "lat", "lon", "created_at"):
        assert field in js

    # Outing fields
    for field in ("id", "name", "date", "status", "places", "created_at"):
        assert field in js

    # Outing status values persisted
    assert '"PLANNED"' in js
    assert '"COMPLETED"' in js

    # created_at appears at least twice (favorites + outings)
    assert js.count("created_at") >= 2


def test_legal_status_never_persisted_as_authority():
    """store.js must NOT persist any resolver-derived keys."""
    js = _read("webapp/static/store.js")
    banned = ["legalStatus", "knowledgeStatus", "determination", "reasonCodes", "dem"]
    for b in banned:
        assert b not in js, f"store.js must not contain '{b}'"
    # "coverage" as a substring — only allow it in "coverageStatus" or
    # variable names that aren't the bare word. Check via regex.
    import re as _re
    # Must not have standalone "coverage" as a bare key in serialized data
    # The word "coverage" must not appear as a field name
    assert '"coverage"' not in js
    assert "'coverage'" not in js


def test_storage_fails_gracefully_on_corrupt_data():
    """store.js has try/catch around JSON.parse and validates items."""
    js = _read("webapp/static/store.js")
    assert "try {" in js
    assert "catch" in js
    assert "JSON.parse" in js
    assert "function readJson" in js or "readJson" in js
    # lat bounds
    assert "-90" in js and "90" in js
    # lon bounds
    assert "-180" in js and "180" in js
    # validation functions
    assert "_favValid" in js or "favValid" in js
    # date regex for outings
    assert r"\d{4}-\d{2}-\d{2}" in js


def test_favorites_and_outings_api_surface():
    """store.js exposes all required API functions."""
    js = _read("webapp/static/store.js")
    for fn in ("favorites", "addFavorite", "removeFavorite", "findFavoriteByPoint"):
        assert fn in js, f"Missing function: {fn}"
    for fn in ("outings", "addOuting", "addPlaceToOuting", "completeOuting", "removeOuting"):
        assert fn in js, f"Missing function: {fn}"
    assert "stats" in js


# ══════════════════════════════════════════════
# 3. TAB NAVIGATION
# ══════════════════════════════════════════════

def test_tab_navigation_and_hash_routing():
    html = _read("webapp/static/index.html")
    js = _read("webapp/static/app.js")

    assert 'data-tab="explore"' in html
    assert 'data-tab="saved"' in html
    assert 'data-tab="outings"' in html
    assert 'data-tab="profile"' in html

    assert "Explorar" in html
    assert "Guardados" in html
    assert "Salidas" in html
    assert "Perfil" in html

    assert "aria-label=\"Navegación principal\"" in html or "aria-label=\"Navegaci" in html

    assert "function showTab" in js
    assert "aria-current" in js
    assert "map.resize()" in js
    assert "location.hash" in js


# ══════════════════════════════════════════════
# 4. GEOLOCATION
# ══════════════════════════════════════════════

def test_geolocation_error_ui_states():
    js = _read("webapp/static/app.js")

    assert "geo-btn" in js
    assert "getCurrentPosition" in js
    assert "watchPosition" not in js

    assert "PERMISSION_DENIED" in js
    assert "POSITION_UNAVAILABLE" in js
    assert "TIMEOUT" in js

    # Spanish messages
    assert "Permiso de ubicación denegado" in js
    assert "No se pudo obtener tu ubicación" in js
    assert "Ubicación encontrada" in js

    assert "navigator.geolocation" in js
    # Pin no-continuous-tracking options object
    assert "{ enableHighAccuracy: false" in js


# ══════════════════════════════════════════════
# 5. LEGAL RESULT MAPPING (emoji + not color-only)
# ══════════════════════════════════════════════

def test_legal_result_mapping_and_not_color_only():
    html = _read("webapp/static/index.html")
    js = _read("webapp/static/app.js")

    assert "¿Puedo hacer vivac aquí?" in html

    # Check for emoji characters in the LEGAL_EMOJI object
    assert chr(0x2705) in js  # ✅ PERMITTED
    assert chr(0x26D4) in js  # ⛔ PROHIBITED
    assert chr(0x1F7E0) in js  # 🟠 AUTHORIZATION_REQUIRED
    assert chr(0x26A0) in js  # ⚠️ UNDETERMINED

    # Verify they appear in the LEGAL_EMOJI map
    lines = js.split("\n")
    in_emoji_map = False
    found = {}
    for line in lines:
        if "LEGAL_EMOJI" in line:
            in_emoji_map = True
        if in_emoji_map:
            if "}" in line and "{" not in line:
                in_emoji_map = False
                break
            for status in ("PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED", "UNDETERMINED"):
                if status in line:
                    found[status] = True
    for status in ("PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED", "UNDETERMINED"):
        assert status in found, f"Missing status {status} in LEGAL_EMOJI map"

    assert "legal-emoji" in html


# ══════════════════════════════════════════════
# 6. POI vs LEGAL SEPARATION (HTML order)
# ══════════════════════════════════════════════

def test_poi_vs_legal_separation_visible():
    html = _read("webapp/static/index.html")

    # POI block comes before legal heading
    outdoor_idx = html.find("id=\"outdoor-info\"")
    legal_heading_idx = html.find("¿Puedo hacer vivac aquí?")
    assert outdoor_idx != -1, "outdoor-info not found"
    assert legal_heading_idx != -1, "legal heading not found"
    assert outdoor_idx < legal_heading_idx, "POI block must appear before the legal section"

    # Disclaimer present (check parts since <b> tag may split "no")
    assert "implica" in html
    assert "permiso" in html

    # Action button text
    assert "Añadir a una salida" in html

    # "Fuentes y detalle" after "Añadir a una salida"
    sources_idx = html.find("Fuentes y detalle")
    add_btn_idx = html.find("Añadir a una salida")
    assert sources_idx > add_btn_idx, "Details block must be after action buttons"

    # "Detalle técnico" and id="tech-codes" in details
    assert "Detalle técnico" in html
    assert 'id="tech-codes"' in html


# ══════════════════════════════════════════════
# 7. SAVED ITEMS REOPEN VIA FRESH RESOLVE
# ══════════════════════════════════════════════

def test_saved_items_reopen_via_fresh_resolve():
    js = _read("webapp/static/app.js")

    assert "selectPoint" in js
    assert "findFavoriteByPoint" in js
    assert "Ver en mapa" in js
    assert "refresh()" in js


# ══════════════════════════════════════════════
# 8. OUTINGS MARK COMPLETED + STATS
# ══════════════════════════════════════════════

def test_outings_mark_completed_and_stats():
    js = _read("webapp/static/app.js")
    html = _read("webapp/static/index.html")

    assert "completeOuting" in js
    assert "Marcar realizada" in js

    assert "stat-favorites" in html
    assert "stat-planned" in html
    assert "stat-completed" in html


# ══════════════════════════════════════════════
# 9. EMPTY STATES
# ══════════════════════════════════════════════

def test_empty_states_present():
    js = _read("webapp/static/app.js")
    html = _read("webapp/static/index.html")

    assert "Todavía no has guardado ningún sitio." in (js + html)
    assert "Todavía no has preparado ninguna salida." in (js + html)


# ══════════════════════════════════════════════
# 10. RESPONSIVE AND A11Y
# ══════════════════════════════════════════════

def test_responsive_and_a11y_basics():
    css = _read("webapp/static/style.css")

    assert "@media (max-width: 820px)" in css
    assert "position:fixed" in css
    assert "min-height:44px" in css
    assert "prefers-reduced-motion" in css
    assert "sheet-peek" in css  # M4: bottom sheet replaces the 52vh stacked map

    html = _read("webapp/static/index.html")
    assert "Navegación principal" in html or "Navegaci" in html


# ══════════════════════════════════════════════
# 11. ACTIVITY OPTIONS PRESERVED
# ══════════════════════════════════════════════

def test_activity_options_preserved():
    html = _read("webapp/static/index.html")
    for opt in ("VIVAC_AL_RASO", "FUNDA_VIVAC", "TIENDA_NOCTURNA", "ACAMPADA", "PERNOCTA_REFUGIO"):
        assert 'value="' + opt + '"' in html, f"Missing activity: {opt}"


# ══════════════════════════════════════════════
# 12. NO NEW ENDPOINTS AND NO CORE FILES TOUCHED
# ══════════════════════════════════════════════

def test_no_new_endpoints_and_no_core_files_touched():
    py = _read("webapp/server.py")

    for ep in ('/api/resolve', '/api/pois', '/api/find', '/api/coverage', '/api/config', '/api/places', '/api/protected-areas'):
        assert f'path == "{ep}"' in py, f"Missing endpoint: {ep}"

    paths = re.findall(r'path == "([^"]+)"', py)
    api_paths = [p for p in paths if p.startswith("/api/")]
    allowed_api_paths = {"/api/resolve", "/api/pois", "/api/find", "/api/coverage", "/api/config", "/api/places", "/api/protected-areas"}
    assert set(api_paths) == allowed_api_paths, f"Unexpected API routes: {set(api_paths) - allowed_api_paths}"


@pytest.fixture(scope="module")
def svc():
    return server.Service()


# ══════════════════════════════════════════════
# 13. SERVER-LEVEL: UNKNOWN PLACE COPY
# ══════════════════════════════════════════════

def test_unknown_place_copy_stays_honest(svc):
    out = server.resolve_point(svc, lat=41.9, lon=-2.4, activity="VIVAC_AL_RASO",
                                activity_date=TODAY, knowledge_date=TODAY, facts={})
    assert out["ui"]["legal"] == "No lo podemos determinar"
    assert "no es un permiso" in out["ui"]["headline"].lower()


# ══════════════════════════════════════════════
# 14. SERVER-LEVEL: PICOS AUTHORIZED
# ══════════════════════════════════════════════

def test_picos_authorized_copy(svc):
    out = server.resolve_point(svc, lat=43.17068, lon=-4.80299, activity="VIVAC_AL_RASO",
                                activity_date=TODAY, knowledge_date=TODAY,
                                facts={"actividad_montana_o_escalada": True,
                                       "nights": 2, "cota_m": 2400})
    assert out["determination"]["legalStatus"] == "PERMITTED"
    assert out["ui"]["headline"].startswith("Permitido")


# ══════════════════════════════════════════════
# 15. EXISTING HOOKS SURVIVE (M2 gate tests)
# ══════════════════════════════════════════════

def test_m2_gate_protected_area_is_osm_reference():
    js = _read("webapp/static/app.js")
    assert "poi-circles-protected_area" not in js
    # M8.1: lg-protected was added for the PA cartographic context layer.
    assert "lg-protected" in js, "M8.1: #lg-protected toggle must exist"
    assert "pa-fill" in js and "pa-line" in js, "M8.1: PA polygon layers must exist"
    assert 'const POI_ORDER = ["refuge", "shelter", "water", "camping"];' in js
    assert "/api/coverage" in js
    assert "/api/pois" in js
    assert "/api/protected-areas" in js


def test_m2_gate_provider_decoupled():
    js = _read("webapp/static/app.js")
    assert "tile.openstreetmap.org" not in js
    assert "/api/config" in js


def test_m2_gate_frontend_markup():
    html = _read("webapp/static/index.html")
    for hook in ('role="search"', 'id="q"', 'role="listbox"', 'aria-live="polite"',
                  'id="headline"', 'id="center-btn"', 'id="tech-codes"',
                  'for="activity"', "no es un permiso,", "Detalle técnico"):
        assert hook in html, f"Missing hook: {hook}"

    css = _read("webapp/static/style.css")
    assert ":focus-visible" in css
    assert "min-height:44px" in css

    js = _read("webapp/static/app.js")
    assert "/api/find" in js
    assert "/api/places" in js
    assert "getCenter" in js


# ══════════════════════════════════════════════
# 16. CHOOSER MODAL ACCESSIBILITY
# ══════════════════════════════════════════════

def test_chooser_modal_accessibility():
    html = _read("webapp/static/index.html")
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-label="Añadir a una salida"' in html
    assert 'aria-label="Cerrar"' in html


# ══════════════════════════════════════════════
# 17. LEGAL RESULT STYLING NOT COLOR ONLY
# ══════════════════════════════════════════════

def test_legal_result_styling_not_color_only():
    js = _read("webapp/static/app.js")
    assert "borderLeftColor" in js or "border-left-color" in js


# ══════════════════════════════════════════════
# 18. CARD RESULT STRUCTURE ORDER
# ══════════════════════════════════════════════

def test_card_result_structure_order():
    html = _read("webapp/static/index.html")

    outdoor_idx = html.find("id=\"outdoor-info\"")
    legal_idx = html.find("id=\"legal-section\"")
    action_idx = html.find("id=\"action-buttons\"")
    detail_idx = html.find("id=\"detail-box\"")

    assert outdoor_idx > 0 and legal_idx > 0 and action_idx > 0 and detail_idx > 0
    assert outdoor_idx < legal_idx, "outdoor block must come before legal section"
    assert action_idx < detail_idx, "action buttons must come before details block"


# ══════════════════════════════════════════════
# 19. STORE.JS: IN-MEMORY SHIM
# ══════════════════════════════════════════════

def test_store_js_in_memory_shim():
    js = _read("webapp/static/store.js")
    assert "try {" in js
    assert "catch" in js
    assert "localStorage" in js
    assert "_mem" in js


# ══════════════════════════════════════════════
# 20. VIEW SECTIONS
# ══════════════════════════════════════════════

def test_view_sections_exist():
    html = _read("webapp/static/index.html")
    for vid in ("view-explore", "view-saved", "view-outings", "view-profile"):
        assert 'id="' + vid + '"' in html, f"Missing view: {vid}"


# ══════════════════════════════════════════════
# 21. GEO-BTN EXISTENCE
# ══════════════════════════════════════════════

def test_geo_button_in_html():
    html = _read("webapp/static/index.html")
    assert 'id="geo-btn"' in html
    assert "Mi ubicación" in html


# ══════════════════════════════════════════════
# 22. SAVE BUTTON AND PLAN BUTTON
# ══════════════════════════════════════════════

def test_save_and_plan_buttons_exist():
    html = _read("webapp/static/index.html")
    assert 'id="save-btn"' in html
    assert 'id="plan-add-btn"' in html
    assert "Guardar" in html


# ══════════════════════════════════════════════
# 23. ALTITUDE LINE ELEMENT
# ══════════════════════════════════════════════

def test_altitude_line_element():
    html = _read("webapp/static/index.html")
    assert "altitude-line" in html or "altitude" in html


# ══════════════════════════════════════════════
# 24. LEGAL RESULT ELEMENT
# ══════════════════════════════════════════════

def test_legal_result_element():
    html = _read("webapp/static/index.html")
    assert "legal-result" in html


# ══════════════════════════════════════════════
# 25. PLAIN CONDITIONS ELEMENT
# ══════════════════════════════════════════════

def test_plain_conditions_element():
    html = _read("webapp/static/index.html")
    assert "plain-conds" in html or "plain-cond" in html
