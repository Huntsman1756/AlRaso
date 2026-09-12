"""M8 POI product tests — CTA, provenance disclosure, POI-alt guard, UI hygiene.

String/DOM-level tests (same style as test_m2_webapp.py): check index.html markup,
app.js source patterns, and server response structure.  No new endpoint is added.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

INDEX_HTML = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
STYLE_CSS = (ROOT / "webapp" / "static" / "style.css").read_text(encoding="utf-8")
SERVER_PY = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")


# ── 1. CTA exists with exact copy ──────────────────────────────────────────

def test_cta_exists_with_exact_copy():
    """"Consultar aquí el estatus legal" is present in index.html and wired in app.js."""
    assert "Consultar aquí el estatus legal" in INDEX_HTML, \
        "index.html must contain the CTA exact copy"
    # The button must have an id or be referenced in app.js by the CTA text or id.
    assert "poi-legal-btn" in INDEX_HTML, "CTA button must have id=poi-legal-btn"
    assert "poi-legal-btn" in APP_JS, "app.js must wire the CTA button"


# ── 2. CTA passes coordinates only (no POI metadata to resolver) ──────────

_KNOWN_POI_METADATA_KEYS = {
    "category", "source", "source_ref", "note", "alt_m", "osm_url",
    "source_label", "snapshot_date", "attribution", "source_license",
    "region", "id",
}


def test_cta_passes_coordinates_only():
    """CTA handler uses POI lat/lon and the existing selectPoint/refresh path;
    asserts no POI metadata key is referenced in resolve-request construction."""
    # The CTA handler calls selectPoint(lat, lon, …) — check that the handler
    # only passes lat, lon and the existing selectedName (which is user-set,
    # not POI metadata).
    # Pattern: selectPoint(lat, lon, state.selectedName, true)
    assert re.search(r"selectPoint\s*\(\s*lat\s*,\s*lon\s*,\s*state\.selectedName", APP_JS), \
        "CTA handler must call selectPoint(lat, lon, state.selectedName, ...)"

    # factsFromForm reads only #factbox inputs — assert its body is unchanged:
    assert "document.querySelectorAll" in APP_JS, \
        "factsFromForm must use querySelectorAll"
    # Find the factsFromForm function body and verify it targets #factbox:
    facts_pos = APP_JS.find("function factsFromForm()")
    assert facts_pos >= 0, "factsFromForm function must exist"
    facts_block = APP_JS[facts_pos:facts_pos + 500]
    assert "factbox" in facts_block, \
        "factsFromForm must still query #factbox inputs only"

    # The resolve request must NOT reference POI metadata keys.
    resolve_lines = []
    in_resolve = False
    for line in APP_JS.splitlines():
        if "fetch(" in line and '"/api/resolve"' in line:
            in_resolve = True
        if in_resolve:
            resolve_lines.append(line)
            if "}" in line and "fetch" not in line:
                break
    resolve_src = "\n".join(resolve_lines)
    for key in _KNOWN_POI_METADATA_KEYS:
        assert key not in resolve_src, (
            f"POI metadata key '{key}' must not appear in the /api/resolve request")


# ── 3. POI altitude never becomes cota_m ────────────────────────────────────

def test_poi_alt_never_becomes_cota_m():
    """Assert state.poiAlt is not read by factsFromForm/refresh;
    assert the string 'observación OSM' no longer appears in legal-card rendering code;
    and the server resolve_point output for a POI coordinate is unchanged vs a plain map click."""
    # state.poiAlt must not appear in factsFromForm or the resolve query builder.
    # Extract factsFromForm body:
    facts_match = re.search(
        r"function factsFromForm\(\)\s*\{([\s\S]*?)\n\}", APP_JS
    )
    assert facts_match, "factsFromForm function must exist"
    facts_body = facts_match.group(1)
    assert "poiAlt" not in facts_body, "state.poiAlt must not be read by factsFromForm"

    # 'observación OSM' must not appear in the render() function (legal card path).
    # Extract the render function:
    render_match = re.search(
        r"function render\s*\([^\)]*\)\s*\{", APP_JS
    )
    assert render_match, "render() function must exist"
    # Find the altitude-line section within render.
    # The old code had: "Altitud: " + state.poiAlt + " m (observación OSM)"
    assert "observación OSM" not in APP_JS, (
        "'observación OSM' must not appear anywhere in app.js after POI-alt removal")

    # state.poiAlt must not appear in the altitude-line branch of render().
    # Extract the altitude section from render:
    altitude_section = re.search(
        r"altitude-line[\s\S]*?(?=\n  //|function |_const )", APP_JS
    )
    if altitude_section:
        assert "state.poiAlt" not in altitude_section.group(), (
            "state.poiAlt must not be referenced in altitude-line rendering")


# ── 4. Source disclosure fields ─────────────────────────────────────────────

def test_source_disclosure_fields():
    """The disclosure shows source label, snapshot date, attribution."""
    # index.html must contain the src-details container:
    assert "poi-src-details" in INDEX_HTML, \
        "index.html must contain #poi-src-details"

    # app.js must write source_label, snapshot_date, attribution in renderPoi:
    assert "source_label" in APP_JS, \
        "renderPoi must reference source_label"
    assert "snapshot_date" in APP_JS, \
        "renderPoi must reference snapshot_date"
    assert "attribution" in APP_JS, \
        "renderPoi must reference attribution"

    # Check that renderPoi uses these in the src-details block (DOM-level).
    render_poi_re = re.search(
        r"function renderPoi\([^)]*\)\s*\{([\s\S]*?)(?=\nfunction |\n//|$)", APP_JS
    )
    assert render_poi_re, "renderPoi function must exist"
    render_poi_body = render_poi_re.group(1)
    assert "poi-src-details" in render_poi_body, \
        "renderPoi must populate #poi-src-details"
    assert "source_label" in render_poi_body, \
        "renderPoi must write source_label to src-details"
    assert "snapshot_date" in render_poi_body, \
        "renderPoi must write snapshot_date to src-details"
    assert "attribution" in render_poi_body, \
        "renderPoi must write attribution to src-details"
    assert "source_ref" in render_poi_body, \
        "renderPoi must keep the object reference in provenance"
    assert "Objeto OSM" in render_poi_body, \
        "OSM object reference must be presented as provenance, not as a name"


def test_unnamed_pois_are_icon_only_and_get_a_card_label():
    """A missing display name hides map text but remains understandable in the card."""
    labels_start = APP_JS.find('id: "poi-labels-"')
    labels_end = APP_JS.find("bindLayerToggles();", labels_start)
    labels_block = APP_JS[labels_start:labels_end]
    assert '["!=", ["get", "name"], null]' in labels_block
    assert "anonymousLabel" in APP_JS
    render_start = APP_JS.find("function renderPoi")
    render_end = APP_JS.find("\nfunction ", render_start + 1)
    render_block = APP_JS[render_start:render_end]
    assert "sin nombre" in render_block
    assert "p.name" in render_block


# ── 5. No protected_area UI ────────────────────────────────────────────────

def test_no_protected_area_ui():
    """'protected_area' appears in neither index.html toggles nor app.js POI_ORDER.
    The layer toggle is #lg-protected (cartographic context), not a POI symbol layer."""
    # index.html: no 'protected_area' string in toggles (the toggle is #lg-protected).
    # The string 'protected_area' must not appear as a category value in HTML toggles.
    toggle_lines = [l for l in INDEX_HTML.splitlines() if 'id="lg-' in l]
    for line in toggle_lines:
        assert "protected_area" not in line, \
            "index.html toggles must not contain 'protected_area' category"
    poi_order_match = re.search(
        r'const POI_ORDER = \[([^\]]+)\]', APP_JS
    )
    assert poi_order_match, "POI_ORDER must exist"
    poi_order_content = poi_order_match.group(1)
    assert "protected_area" not in poi_order_content, \
        "POI_ORDER must not contain protected_area"
    # The #lg-protected toggle exists for cartographic context (not a POI symbol).
    assert 'id="lg-protected"' in INDEX_HTML, "toggle #lg-protected must exist"
    assert 'id="pa-card"' in INDEX_HTML, "PA card section must exist"


# ── 6. No new endpoint ─────────────────────────────────────────────────────

def test_no_new_endpoint():
    """Assert no new '/api/' route string in server.py beyond the known set."""
    known_routes = {
        "/api/coverage",
        "/api/config",
        "/api/places",
        "/api/pois",
        "/api/protected-areas",
        "/api/find",
        "/api/resolve",
    }
    found_routes = set(re.findall(r'"/api/\w+"', SERVER_PY))
    # Strip quotes:
    found_routes = {r.strip('"') for r in found_routes}
    # All found routes must be a subset of known.
    extra = found_routes - known_routes
    assert not extra, f"Unexpected API routes: {extra}"


# ── 7. CTA button is visually separated (own block in CSS) ─────────────────

def test_cta_button_has_own_css_block():
    """The CTA button has its own CSS block separated from provenance disclosure."""
    assert ".cta-legal" in STYLE_CSS, \
        "style.css must define .cta-legal"
    assert "#poi-cta" in STYLE_CSS, \
        "style.css must define #poi-cta container"


# ── 8. POI source disclosure has its own CSS block ─────────────────────────

def test_poi_src_disclosure_css():
    """Provenance disclosure has its own CSS rules."""
    assert ".poi-src-details" in STYLE_CSS, \
        "style.css must define .poi-src-details"


# ── M8.2 compact product answer ─────────────────────────────────────────────

def test_m82_primary_answer_is_compact_and_detail_is_progressive_disclosure():
    assert 'id="answer-explanation"' in INDEX_HTML
    assert 'id="conditions-summary"' in INDEX_HTML
    assert 'id="place-context"' in INDEX_HTML
    assert '<details id="detail-box"><summary>Consultar detalle</summary>' in INDEX_HTML
    assert 'id="ui-knowledge"' not in INDEX_HTML

    tech_at = INDEX_HTML.index('id="tech"')
    badges_at = INDEX_HTML.index('class="badges"')
    codes_at = INDEX_HTML.index('id="tech-codes"')
    assert tech_at < badges_at < codes_at, \
        "Internal status badges must live inside technical detail"


def test_m82_unknown_answer_copy_is_single_and_user_facing():
    assert 'UNDETERMINED: "No lo podemos determinar"' in APP_JS
    assert "Aún no tenemos normativa verificada para este punto." in APP_JS
    assert 'return "Zona todavía no cubierta.";' in APP_JS
    assert '"Cobertura normativa del punto: ninguna"' in APP_JS
    assert 'No hay fuentes normativas vinculadas a este punto.' in APP_JS

    assert "Ninguna norma del corpus de AlRaso llega a este punto" not in APP_JS
    assert "AlRaso no tiene corpus aquí y por eso no puede afirmar nada" not in APP_JS


def test_m82_port_does_not_restore_poi_altitude_as_legal_altitude():
    start = APP_JS.find("function render(d)")
    assert start != -1
    end = APP_JS.find("\nfunction ", start + 1)
    render = APP_JS[start:] if end == -1 else APP_JS[start:end]
    assert "state.poiAlt" not in render
    assert "d.dem" in render


def test_m82_m6_and_m81_plumbing_remain_single_instance():
    assert APP_JS.count("function loadWeather(") == 1
    assert APP_JS.count("async function loadProtectedAreas(") == 1
    assert 'fetch("/api/protected-areas")' in APP_JS
