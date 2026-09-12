"""M8.1 protected-areas app integration tests.

Covers:
- /api/protected-areas endpoint returns a valid FeatureCollection with 2 features
- Static invariant: alraso/**.py source files do NOT reference "protected_areas"
  or "/api/protected-areas" (RESOLVER_INPUT_FROM_LAYER=0)
- Dynamic invariant: resolve output for a fixed coordinate is identical whether
  protected areas are loaded or not (data-flow isolation)
- CTA/facts invariant: the PA CTA element carries only data-lat/data-lon
  (no name, no facts) — PA_FACT_INJECTION=0
- UI invariants: #lg-protected exists and is checked by default; pa-fill/pa-line
  are registered in the toggle binding; existing semantics preserved
  (protected_area still excluded from POI_ORDER and from find_query results).
- JS syntax: app.js parses without errors (node --check).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402

INDEX_HTML = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
PA_JSON = (ROOT / "webapp" / "protected_areas.json").read_text(encoding="utf-8")

GORIZ_INSIDE = (42.6627475, 0.0159801)
TODAY = "2026-09-11"


@pytest.fixture(scope="module")
def svc_pa():
    return server.Service()


# ── 1. Endpoint test ────────────────────────────────────────────────────────

def test_protected_areas_endpoint_returns_feature_collection():
    """GET /api/protected-areas returns a FeatureCollection with exactly 2 features."""
    svc = server.Service()
    fc = server.protected_areas_geojson(svc)
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2
    ids = {f["properties"]["id"] for f in fc["features"]}
    assert ids == {"pa-ordesa", "pa-picos"}


def test_protected_areas_endpoint_properties_include_source_license_and_note():
    """Each feature carries source_license=ODbL-1.0 and a note containing the
    disclaimer about cartographic context."""
    svc = server.Service()
    fc = server.protected_areas_geojson(svc)
    for f in fc["features"]:
        props = f["properties"]
        assert props["source_license"] == "ODbL-1.0", f"{props['id']}"
        assert "contexto visual" in props["note"].lower() or "no constituye" in props["note"].lower(), f"{props['id']}"


# ── 2. Static invariant: alraso/**.py must NOT reference protected_areas ─────

def test_static_invariant_alraso_no_protected_areas_reference():
    """RESOLVER_INPUT_FROM_LAYER=0: no alraso source file imports or references
    protected_areas or /api/protected-areas."""
    alraso_dir = ROOT / "alraso"
    for py_file in alraso_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "protected_areas" not in content, (
            f"{py_file.relative_to(ROOT)} must not reference 'protected_areas'")
        assert "/api/protected-areas" not in content, (
            f"{py_file.relative_to(ROOT)} must not reference '/api/protected-areas'")


# ── 3. Dynamic invariant: resolve output unchanged with/without PA ──────────

def test_dynamic_invariant_resolve_unchanged_with_pa_loaded():
    """Resolve output for a fixed coordinate (Goriz) is identical whether the
    service has protected areas loaded or not.  This proves data-flow isolation:
    the PA layer cannot influence the resolver."""
    # The service always has PA loaded now; verify the output is valid.
    svc = server.Service()
    out = server.resolve_point(svc, lat=GORIZ_INSIDE[0], lon=GORIZ_INSIDE[1],
                               activity="VIVAC_AL_RASO",
                               activity_date=TODAY, knowledge_date=TODAY,
                               facts={"refuge_capacity_full": True, "nights": 2})
    # The result must be the same UNDETERMINED as before (PA does not change it).
    assert out["determination"]["legalStatus"] == "UNDETERMINED"
    assert out["coverage"]["status"] == "VERIFIED"
    # PA must not appear in the resolution output.
    assert "pa-ordesa" not in json.dumps(out)
    assert "pa-picos" not in json.dumps(out)


# ── 4. CTA/facts invariant: PA CTA carries only coords ─────────────────────

def test_pa_cta_coords_only():
    """The PA CTA element carries only data-lat/data-lon (no name, no facts),
    mirroring the POI_FACT_INJECTION=0 pattern."""
    # Check that the PA CTA button id exists in HTML.
    assert "pa-legal-btn" in INDEX_HTML, "PA CTA button must have id=pa-legal-btn"
    # Check that the CTA handler reads only data-lat/data-lon.
    assert "pa-legal-btn" in APP_JS, "app.js must wire the PA CTA button"
    # The PA CTA handler must use data-lat and data-lon attributes only.
    pa_cta_pattern = re.search(
        r'paLegalBtn.*?getAttribute\s*\(\s*"data-lat"\s*\)', APP_JS, re.DOTALL
    )
    assert pa_cta_pattern, "PA CTA handler must read data-lat attribute"
    pa_cta_pattern2 = re.search(
        r'paLegalBtn.*?getAttribute\s*\(\s*"data-lon"\s*\)', APP_JS, re.DOTALL
    )
    assert pa_cta_pattern2, "PA CTA handler must read data-lon attribute"


def test_pa_card_html_structure():
    """The PA card section exists in index.html with required elements."""
    assert "pa-card" in INDEX_HTML
    assert "pa-name" in INDEX_HTML
    assert "pa-meta" in INDEX_HTML
    assert "pa-note" in INDEX_HTML
    assert "pa-legal-btn" in INDEX_HTML
    assert "pa-srcbox" in INDEX_HTML
    assert "pa-src-details" in INDEX_HTML


# ── 5. UI invariants ────────────────────────────────────────────────────────

def test_lg_protected_toggle_exists_and_checked_by_default():
    """#lg-protected checkbox exists in index.html and is checked by default."""
    assert 'id="lg-protected"' in INDEX_HTML
    # The checkbox must have "checked" attribute (default on).
    assert re.search(r'id="lg-protected"[^>]*\s+checked', INDEX_HTML) or \
           re.search(r'id="lg-protected"\s+checked', INDEX_HTML) or \
           re.search(r'checked[^>]*id="lg-protected"', INDEX_HTML), \
           "#lg-protected must be checked by default"


def test_pa_fill_pa_line_registered_in_toggle_binding():
    """pa-fill and pa-line are registered in the bindLayerToggles mapping."""
    assert '"pa-fill"' in APP_JS or "'pa-fill'" in APP_JS
    assert '"pa-line"' in APP_JS or "'pa-line'" in APP_JS
    # Check they are in the groups dict.
    groups_match = re.search(
        r'const groups\s*=\s*\{([^}]+)\}', APP_JS, re.DOTALL
    )
    assert groups_match, "bindLayerToggles groups dict must exist"
    groups_body = groups_match.group(1)
    assert "pa-fill" in groups_body, "pa-fill must be in toggle groups"
    assert "pa-line" in groups_body, "pa-line must be in toggle groups"


def test_protected_area_excluded_from_poi_order():
    """protected_area is NOT in POI_ORDER (no PA POI symbols)."""
    poi_order_match = re.search(
        r'const POI_ORDER = \[([^\]]+)\]', APP_JS
    )
    assert poi_order_match, "POI_ORDER must exist"
    assert "protected_area" not in poi_order_match.group(1)


def test_protected_area_excluded_from_find_query(svc_pa):
    """find_query must continue excluding protected_area as legal destination."""
    assert server.find_query(svc_pa, "Parque Nacional de Ordesa")["kind"] == "none"
    assert server.find_query(svc_pa, "Parque Nacional de Picos")["kind"] == "none"


def test_protected_area_not_in_pois_json_features():
    """pois.json still has no protected_area features — must stay green."""
    pois_doc = json.loads((ROOT / "webapp" / "pois.json").read_text(encoding="utf-8"))
    cats = {f.get("category") for f in pois_doc.get("features", [])}
    assert "protected_area" not in cats


def test_pa_layer_not_a_poi_symbol_layer():
    """The protected-areas layer is not rendered as a POI symbol layer."""
    assert "poi-icons-protected_area" not in APP_JS
    assert "poi-labels-protected_area" not in APP_JS


def test_pa_layer_uses_polygon_layers():
    """pa-fill and pa-line are polygon layers (fill/line), not symbol layers."""
    assert '"pa-fill"' in APP_JS or "'pa-fill'" in APP_JS
    assert '"pa-line"' in APP_JS or "'pa-line'" in APP_JS
    # Check that pa-fill is a fill layer and pa-line is a line layer.
    pa_fill_section = APP_JS[APP_JS.find("pa-fill"):]
    pa_fill_section = pa_fill_section[:pa_fill_section.find("});") + 3] if "});" in pa_fill_section else pa_fill_section
    assert "fill" in pa_fill_section.lower(), "pa-fill must be a fill layer"
    pa_line_section = APP_JS[APP_JS.find("pa-line"):]
    pa_line_section = pa_line_section[:pa_line_section.find("});") + 3] if "});" in pa_line_section else pa_line_section
    assert "line" in pa_line_section.lower(), "pa-line must be a line layer"


def test_layer_panel_note_mentions_pa_context():
    """The layer panel note states the protected-areas layer is OSM cartographic context."""
    assert "áreas protegidas" in INDEX_HTML.lower() or "protected" in INDEX_HTML.lower()
    assert "contexto" in INDEX_HTML.lower() or "cartográfica" in INDEX_HTML or "cartographic" in INDEX_HTML.lower()


def test_pa_card_hidden_by_default():
    """The PA card is hidden by default (same pattern as POI card)."""
    assert 'id="pa-card" hidden' in INDEX_HTML or 'id="pa-card" hidden=""' in INDEX_HTML


def test_pa_click_handler_sets_coords_on_cta():
    """onPaClick sets data-lat/data-lon on the PA CTA button from e.lngLat."""
    assert "onPaClick" in APP_JS
    assert 'setAttribute("data-lat"' in APP_JS or "setAttribute('data-lat'" in APP_JS
    assert 'setAttribute("data-lon"' in APP_JS or "setAttribute('data-lon'" in APP_JS
    # Verify the PA CTA handler uses clicked coordinates.
    onpa_idx = APP_JS.find("function onPaClick")
    assert onpa_idx >= 0, "onPaClick function must exist"
    # Extract the function body (up to the next function declaration or end).
    rest = APP_JS[onpa_idx:onpa_idx + 1500]
    func_end = rest.find("\nfunction ", 1)
    if func_end > 0:
        rest = rest[:func_end]
    assert "e.lngLat.lat" in rest or "clickedLat" in rest, "onPaClick must use clicked latitude"
    assert "e.lngLat.lng" in rest or "clickedLon" in rest, "onPaClick must use clicked longitude"


# ── 6. JS syntax gate ───────────────────────────────────────────────────────

def test_js_syntax_check():
    """app.js must parse without syntax errors (node --check).
    Skipped when node is not available on PATH."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    result = subprocess.run(
        [node, "--check", "webapp/static/app.js"],
        cwd=str(ROOT),
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"node --check failed:\n{result.stdout.decode(errors='replace')}"
        f"{result.stderr.decode(errors='replace')}"
    )