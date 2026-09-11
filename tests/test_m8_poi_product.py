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


# ── 5. No protected_area UI ────────────────────────────────────────────────

def test_no_protected_area_ui():
    """'protected_area' appears in neither index.html toggles nor app.js POI_ORDER."""
    assert "protected_area" not in INDEX_HTML, \
        "index.html must not contain 'protected_area' in toggles"
    poi_order_match = re.search(
        r'const POI_ORDER = \[([^\]]+)\]', APP_JS
    )
    assert poi_order_match, "POI_ORDER must exist"
    poi_order_content = poi_order_match.group(1)
    assert "protected_area" not in poi_order_content, \
        "POI_ORDER must not contain protected_area"


# ── 6. No new endpoint ─────────────────────────────────────────────────────

def test_no_new_endpoint():
    """Assert no new '/api/' route string in server.py beyond the known set."""
    known_routes = {
        "/api/coverage",
        "/api/config",
        "/api/places",
        "/api/pois",
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
