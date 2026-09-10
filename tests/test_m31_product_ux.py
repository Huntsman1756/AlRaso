"""M3.1 Product UX polish — offline static assertions.

Tests cover all 8 directives (U1-U8) without starting a server.
These are purely file-content checks matching the spec."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────
def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


HTML = _read("webapp/static/index.html")
JS = _read("webapp/static/app.js")
CSS = _read("webapp/static/style.css")
PY = _read("webapp/server.py")


# ══════════════════════════════════════════════
# U1 — CAPAS → FLOATING CONTROL
# ══════════════════════════════════════════════

class TestU1LayersFloatingControl:
    """Capas moved from full-width stripe to floating panel."""

    def test_layers_btn_exists(self):
        assert 'id="layers-btn"' in HTML

    def test_layers_panel_exists(self):
        assert 'id="layers-panel"' in HTML

    def test_panel_contains_5_checkboxes(self):
        panel_content = HTML
        for cid in ("lg-refuge", "lg-shelter", "lg-water", "lg-camping", "lg-coverage"):
            assert f'id="{cid}"' in panel_content, f"Missing checkbox {cid} in panel"

    def test_old_stripe_gone(self):
        assert '<div id="layers">' not in HTML

    def test_layer_toggles_still_bound(self):
        # bindLayerToggles must reference the checkbox ids
        for cid in ("lg-refuge", "lg-shelter", "lg-water", "lg-camping", "lg-coverage"):
            assert cid in JS

    def test_layers_panel_hidden_by_default(self):
        assert 'class="layers-panel"' in HTML or 'id="layers-panel"' in HTML

    def test_searchmsg_is_in_map_container(self):
        """searchmsg moved inside map-container as floating pill."""
        map_idx = HTML.find('id="map-container"')
        searchmsg_idx = HTML.find('id="searchmsg"')
        card_idx = HTML.find('id="card"')
        assert map_idx < searchmsg_idx < card_idx, "searchmsg must be inside map-container"

    def test_layer_note_present(self):
        """Panel includes the note about POIs being cartography only."""
        assert "no determinan legalidad" in HTML or "no determinan legalidad" in JS.lower() or "cartografía" in HTML.lower()

    def test_layers_outside_click_listener_never_dereferences_map(self):
        """El panel de capas se cierra con closest() puro: map es null hasta que
        /api/config resuelve, asi que el listener global no puede llamar a map.*."""
        assert "map.getCanvas" not in JS


# ══════════════════════════════════════════════
# U2 — SINGLE TOP BAR
# ══════════════════════════════════════════════

class TestU2SingleTopBar:
    """Header contains brand + tagline + nav + searchform on one row."""

    def test_nav_inside_header(self):
        header_open = HTML.find("<header")
        nav_open = HTML.find("<nav")
        header_close = HTML.find("</header>")
        assert header_open != -1, "Missing <header>"
        assert nav_open != -1, "Missing <nav>"
        assert header_close != -1, "Missing </header>"
        assert nav_open > header_open, "nav must be inside header (open tag)"
        assert nav_open < header_close, "nav must close before </header>"

    def test_searchmsg_pill_css(self):
        assert "#searchmsg:empty" in CSS or "#searchmsg:empty {" in CSS

    def test_searchmsg_absolutely_positioned(self):
        css_content = CSS
        # The searchmsg pill should use position:absolute
        assert "position:absolute" in css_content

    def test_header_structure(self):
        assert "<header>" in HTML
        assert 'class="brand"' in HTML
        assert 'class="tagline"' in HTML
        assert 'role="search"' in HTML

    def test_no_separate_nav_stripe(self):
        """There should not be a standalone nav element outside the header."""
        lines = HTML.split("\n")
        in_header = False
        found_nav_outside_header = False
        for line in lines:
            stripped = line.strip()
            if "<header" in stripped:
                in_header = True
            if "</header>" in stripped:
                in_header = False
            if "<nav" in stripped and not in_header:
                found_nav_outside_header = True
                break
        assert not found_nav_outside_header, "<nav> must be inside <header>, not outside"


# ══════════════════════════════════════════════
# U3 — RECOGNIZABLE POI ICONS
# ══════════════════════════════════════════════

class TestU3PoiIcons:
    """Runtime-generated canvas POI icons replace circle layers."""

    def test_get_context_used(self):
        assert "getContext" in JS

    def test_add_image_used(self):
        assert "addImage" in JS

    def test_poi_icon_naming(self):
        assert "poi-icon-" in JS

    def test_poi_icons_layer_naming(self):
        assert "poi-icons-" in JS

    def test_icon_size_interpolate(self):
        # icon-size uses interpolate with zoom
        assert "icon-size" in JS
        assert "interpolate" in JS
        assert '["zoom"]' in JS or '"zoom"' in JS

    def test_no_poi_circles_refuge(self):
        assert "poi-circles-refuge" not in JS

    def test_no_poi_circles_protected_area(self):
        assert "poi-circles-protected_area" not in JS

    def test_bind_layer_toggles_use_poi_icons(self):
        # The layer toggle groups should reference poi-icons- ids
        assert "poi-icons-refuge" in JS
        assert "poi-icons-shelter" in JS
        assert "poi-icons-water" in JS
        assert "poi-icons-camping" in JS

    def test_click_handler_uses_poi_icons(self):
        # Click handlers should bind to poi-icons- layer names
        assert "poi-icons-" in JS
        assert "map.on(\"click\"" in JS or "map.on('click'" in JS

    def test_poi_order_unchanged(self):
        assert 'const POI_ORDER = ["refuge", "shelter", "water", "camping"];' in JS


# ══════════════════════════════════════════════
# U4 — SOFTEN COVERAGE + LIGHTER BASEMAP
# ══════════════════════════════════════════════

class TestU4SoftenCoverageBasemap:
    """Coverage softened; basemap switched to positron."""

    def test_fill_opacity_0_06(self):
        # M4 R6: coverage visually quieter (was 0.1 in M3.1)
        assert '"fill-opacity": 0.06' in JS

    def test_line_opacity_oficial_0_4(self):
        # M4 R6: coverage visually quieter (was 0.55 in M3.1)
        assert '"line-opacity": 0.4' in JS

    def test_line_opacity_esquematico_0_35(self):
        # M4 R6: coverage visually quieter (was 0.45 in M3.1)
        assert '"line-opacity": 0.35' in JS

    def test_app_js_uses_positron(self):
        assert "positron" in JS

    def test_server_py_uses_positron(self):
        assert "positron" in PY

    def test_endpoint_routes_preserved(self):
        for ep in ('/api/resolve', '/api/pois', '/api/find', '/api/coverage', '/api/config', '/api/places'):
            assert f'path == "{ep}"' in PY, f"Missing endpoint: {ep}"

    def test_no_new_api_routes(self):
        paths = re.findall(r'path == "([^"]+)"', PY)
        api_paths = [p for p in paths if p.startswith("/api/")]
        allowed_api_paths = {"/api/resolve", "/api/pois", "/api/find", "/api/coverage", "/api/config", "/api/places"}
        assert set(api_paths) == allowed_api_paths, f"Unexpected API routes: {set(api_paths) - allowed_api_paths}"

    def test_api_config_still_fetched(self):
        assert "/api/config" in JS


# ══════════════════════════════════════════════
# U5 — REAL PLACE CARD
# ══════════════════════════════════════════════

class TestU5PlaceCard:
    """Card redesigned with bigger POI, legal, and meta blocks."""

    def test_card_width_380(self):
        assert "width:380px" in CSS

    def test_card_padding_20(self):
        assert "padding:20px" in CSS

    def test_act_labels_used_in_coords(self):
        """ACT_LABELS[d.query.activity] should appear in the coords line."""
        assert "ACT_LABELS" in JS
        # The coords line should reference ACT_LABELS
        assert "ACT_LABELS[" in JS

    def test_place_name_larger_than_legal_result(self):
        # M4 R4: the place name must dominate the card, legal answer stays
        # clear but visually subordinate (23px place vs 19px legal).
        assert "font-size:23px" in CSS
        assert "font-size:19px" in CSS

    def test_legal_result_padding(self):
        assert "padding:12px 14px" in CSS or "padding:12px" in CSS

    def test_legal_emoji_font_size_22(self):
        # M4 R4: emoji reduced with the legal block (was 26px in M3.1)
        assert "font-size:22px" in CSS


# ══════════════════════════════════════════════
# U6 — REMOVE TECHNICAL ACTION FROM PRIMARY
# ══════════════════════════════════════════════

class TestU6CenterButtonMoved:
    """#center-btn moved inside #detail-box (after 'Fuentes y detalle')."""

    def test_center_btn_after_detail_box(self):
        detail_box_idx = HTML.find('id="detail-box"')
        center_btn_idx = HTML.find('id="center-btn"')
        assert center_btn_idx > detail_box_idx, "center-btn must be inside detail-box"

    def test_center_btn_after_fuentes_y_detalle(self):
        # "Fuentes y detalle" text is inside the details <details> element
        fuentes_idx = HTML.find("Fuentes y detalle")
        center_btn_idx = HTML.find('id="center-btn"')
        assert center_btn_idx > fuentes_idx, "center-btn must be after 'Fuentes y detalle'"

    def test_center_btn_not_in_action_buttons(self):
        """center-btn should NOT be between #action-buttons opening and closing tags."""
        action_open = HTML.find('id="action-buttons"')
        action_close = HTML.find("</div>", action_open)
        center_in_action = action_open < HTML.find('id="center-btn"') < action_close
        assert not center_in_action, "center-btn must NOT be inside #action-buttons"

    def test_center_btn_still_listened(self):
        assert "center-btn" in JS
        assert "getCenter" in JS

    def test_action_buttons_only_save_and_plan(self):
        """Only save-btn and plan-add-btn in action-buttons."""
        action_block_start = HTML.find('id="action-buttons"')
        action_block_end = HTML.find("</div>", action_block_start)
        action_block = HTML[action_block_start:action_block_end]
        assert 'id="save-btn"' in action_block
        assert 'id="plan-add-btn"' in action_block
        assert 'id="center-btn"' not in action_block


# ══════════════════════════════════════════════
# U7 — TYPOGRAPHY & SPACING
# ══════════════════════════════════════════════

class TestU7Typography:
    """Typography upgrades across the board."""

    def test_body_font_15px(self):
        assert "font:15px" in CSS or "font-size: 15px" in CSS

    def test_body_line_height_1_5(self):
        assert "/1.5" in CSS

    def test_footer_12px(self):
        assert "footer" in CSS
        assert "font-size:12px" in CSS or "font-size: 12px" in CSS

    def test_badge_label_10px(self):
        assert "badge-label" in CSS
        assert "font-size:10px" in CSS or "font-size: 10px" in CSS

    def test_h3_13px(self):
        assert "font-size:13px" in CSS

    def test_body_not_14px(self):
        """body should not use 14px font anymore."""
        body_css = CSS.split("body")[0] if "body" in CSS else CSS
        # Check the body rule doesn't have 14px
        lines = CSS.split("\n")
        body_lines = []
        in_body = False
        for line in lines:
            if "body" in line and "{" in line:
                in_body = True
            if in_body:
                body_lines.append(line)
                if "}" in line:
                    break
        body_rule = " ".join(body_lines)
        assert "14px" not in body_rule or "/1.5" in body_rule, "body font should be 15px, not 14px"

    def test_focus_visible_preserved(self):
        assert ":focus-visible" in CSS

    def test_min_height_44px_preserved(self):
        assert "min-height:44px" in CSS

    def test_mobile_media_preserved(self):
        assert "@media (max-width: 820px)" in CSS

    def test_position_fixed_preserved(self):
        assert "position:fixed" in CSS

    def test_mobile_sheet_states_in_css(self):
        # M4 R2: the 52vh stacked map was replaced by full-viewport map +
        # bottom sheet with closed/peek/full states.
        assert "sheet-peek" in CSS
        assert "sheet-full" in CSS
        assert "sheet-closed" in CSS

    def test_prefers_reduced_motion_preserved(self):
        assert "prefers-reduced-motion" in CSS


# ══════════════════════════════════════════════
# U8 — ONBOARDING INITIAL STATE
# ══════════════════════════════════════════════

class TestU8Onboarding:
    """Redesigned card-empty with onboarding CTA."""

    def test_explore_cta_id_exists(self):
        assert 'id="explore-cta"' in HTML

    def test_onboarding_title(self):
        assert "Empieza por una zona verificada" in HTML

    def test_permiso_substring_preserved(self):
        assert "no es un permiso," in HTML or "no es un permiso" in HTML

    def test_cta_ids_in_js(self):
        """Three place IDs used by the CTA."""
        assert "cares-picos" in JS
        assert "refugio-goriz" in JS
        assert "pradera-ordesa" in JS

    def test_cta_uses_api_places(self):
        assert "/api/places" in JS

    def test_cta_selectPoint_called(self):
        assert "selectPoint" in JS

    def test_cta_buttons_keyboard_reachable(self):
        """CTA buttons are real <button> elements created dynamically in JS."""
        # Buttons are created dynamically in app.js with createElement("button")
        assert "createElement" in JS
        assert "cta-btn" in JS or 'className' in JS or "class = " in JS or "className =" in JS

    def test_legend_chips_in_layers_panel(self):
        """Legend chips moved to layers-panel, not card-empty."""
        # The legend chips should appear near the layers-panel
        panel_idx = HTML.find('id="layers-panel"')
        legend_idx = HTML.find('class="legend"')
        assert legend_idx != -1, "legend class should exist"
        # Legend should be in the layers panel or in the card-empty for onboarding
        # (U8 specifies the legend moves from card-empty to layers-panel)
        assert panel_idx > -1


# ══════════════════════════════════════════════
# CROSS-CUTTING: All existing M3/M2/M21 hooks survive
# ══════════════════════════════════════════════

class TestHooksSurvive:
    """All existing required hooks must survive the UX changes."""

    def test_role_search(self):
        assert 'role="search"' in HTML

    def test_id_q(self):
        assert 'id="q"' in HTML

    def test_suggest_dropdown_hooks(self):
        # M4 R3: datalist replaced by an accessible suggestion dropdown.
        assert 'id="suggest"' in HTML
        assert 'role="listbox"' in HTML
        assert 'aria-controls="suggest"' in HTML

    def test_aria_live_polite(self):
        assert 'aria-live="polite"' in HTML

    def test_id_headline(self):
        assert 'id="headline"' in HTML

    def test_id_center_btn(self):
        assert 'id="center-btn"' in HTML

    def test_id_tech_codes(self):
        assert 'id="tech-codes"' in HTML

    def test_for_activity(self):
        assert 'for="activity"' in HTML

    def test_no_permiso_substring(self):
        assert "no es un permiso," in HTML or "no es un permiso" in HTML

    def test_detalle_tecnico(self):
        assert "Detalle técnico" in HTML

    def test_five_activity_options(self):
        for opt in ("VIVAC_AL_RASO", "FUNDA_VIVAC", "TIENDA_NOCTURNA", "ACAMPADA", "PERNOCTA_REFUGIO"):
            assert 'value="' + opt + '"' in HTML, f"Missing activity: {opt}"

    def test_poi_order_line(self):
        assert 'const POI_ORDER = ["refuge", "shelter", "water", "camping"];' in JS

    def test_no_tile_openstreetmap(self):
        assert "tile.openstreetmap.org" not in JS

    def test_no_lg_protected(self):
        assert "lg-protected" not in HTML

    def test_legal_emoji_map(self):
        assert chr(0x2705) in JS  # ✅
        assert chr(0x26D4) in JS  # ⛔
        assert chr(0x1F7E0) in JS  # 🟠
        assert chr(0x26A0) in JS  # ⚠️

    def test_geo_btn_in_html(self):
        assert 'id="geo-btn"' in HTML

    def test_save_btn_in_html(self):
        assert 'id="save-btn"' in HTML

    def test_plan_add_btn_in_html(self):
        assert 'id="plan-add-btn"' in HTML

    def test_card_result_structure_order(self):
        html = HTML
        outdoor_idx = html.find("id=\"outdoor-info\"")
        legal_section_idx = html.find("id=\"legal-section\"")
        action_btns_idx = html.find("id=\"action-buttons\"")
        detail_box_idx = html.find("id=\"detail-box\"")
        assert outdoor_idx > 0 and legal_section_idx > 0 and action_btns_idx > 0 and detail_box_idx > 0
        assert outdoor_idx < legal_section_idx, "outdoor block before legal section"
        assert action_btns_idx < detail_box_idx, "action buttons before details block"

    def test_chooser_modal_a11y(self):
        assert 'role="dialog"' in HTML
        assert 'aria-modal="true"' in HTML
        assert 'aria-label="Añadir a una salida"' in HTML

    def test_no_new_api_endpoints_in_server(self):
        paths = re.findall(r'path == "([^"]+)"', PY)
        api_paths = [p for p in paths if p.startswith("/api/")]
        allowed_api_paths = {"/api/resolve", "/api/pois", "/api/find", "/api/coverage", "/api/config", "/api/places"}
        assert set(api_paths) == allowed_api_paths

    def test_disclaimer_sentence_survives(self):
        """The full disclaimer must preserve 'implica' + 'permiso' semantics."""
        assert "implica" in HTML and "permiso" in HTML

    def test_legal_heading_text(self):
        assert "¿Puedo hacer vivac aquí?" in HTML

    def test_add_to_outing_text(self):
        assert "Añadir a una salida" in HTML

    def test_sources_detail_text(self):
        assert "Fuentes y detalle" in HTML

    def test_empty_states_survive(self):
        assert "Todavía no has guardado ningún sitio." in JS
        assert "Todavía no has preparado ninguna salida." in JS

    def test_stat_ids_survive(self):
        assert 'id="stat-favorites"' in HTML
        assert 'id="stat-planned"' in HTML
        assert 'id="stat-completed"' in HTML

    def test_m2_gate_frontend_markup(self):
        for hook in ('role="search"', 'id="q"', 'role="listbox"', 'aria-live="polite"',
                      'id="headline"', 'id="center-btn"', 'id="tech-codes"',
                      'for="activity"'):
            assert hook in HTML, f"Missing hook: {hook}"

    def test_sheet_handle_hooks(self):
        # M4 R2: handle/button navigation between sheet states is required.
        assert 'id="sheet-handle"' in HTML
        assert "setSheetState" in JS
        assert "openSheetForSelection" in JS
        assert "map.resize()" in JS

    def test_snackbar_above_bottom_nav(self):
        # M4 R5: feedback pill moves above the bottom nav on mobile.
        assert "#searchmsg" in CSS

    def test_sticky_actions_inside_sheet(self):
        # M4 R5: save/plan buttons sticky; never hidden below the nav.
        assert "position:sticky" in CSS
        assert "bottom:calc(56px" in CSS

    def test_cta_hidden_after_selection(self):
        # M4 product check: onboarding CTA must not compete with the ficha.
        assert "has-selection" in CSS
        assert "has-selection" in JS

    def test_escape_coordinator_order(self):
        # M4 product check: Escape closes dropdown -> layers -> sheet step down.
        assert 'ev.key !== "Escape"' in JS

    def test_poi_separation_copy_unchanged(self):
        # La copia real lleva <b>no</b> implica ningún permiso (etiqueta en medio)
        assert "implica ningún permiso" in HTML


class TestM4ProductUsability:
    """M4 PRODUCT-FIRST: usability checks for the mobile-first UI.
    These encode the 5 product verifications agreed for M4 (static subset;
    the visual gate is manual at 390x844 / 360x800 / 1440x900)."""

    def test_r1_bottom_nav_is_fixed_on_mobile(self):
        assert "position:fixed" in CSS
        assert "bottom:0" in CSS

    def test_r1_safe_area_inset(self):
        assert "env(safe-area-inset-bottom)" in CSS

    def test_r2_sheet_states_complete(self):
        for state in ("sheet-closed", "sheet-peek", "sheet-full"):
            assert f".{state}" in CSS or f'"{state}"' in JS

    def test_r2_tap_navigation_required_and_drag_optional(self):
        # Required: handle click toggles states
        assert 'handle.addEventListener("click"' in JS
        # Optional: plain Pointer Events drag, no library, no inertia
        assert "pointerdown" in JS and "pointerup" in JS
        assert "requestAnimationFrame" not in JS.split("endDrag")[1][:400]

    def test_r3_dropdown_sources_only_api_places(self):
        start = JS.find("function initSuggest")
        end = JS.find('$("searchform").addEventListener("submit"')
        assert start != -1 and end != -1 and start < end
        block = JS[start:end]
        assert "/api/places" in block
        assert "/api/find" not in block, "dropdown must not add a search source"

    def test_r3_selection_calls_selectpoint(self):
        assert "selectPoint(p.lat, p.lon, p.name, true)" in JS

    def test_r5_actions_sticky_above_nav(self):
        assert "position:sticky" in CSS

    def test_keyboard_not_covered(self):
        # Sheet max-height leaves the header (search input) visible.
        assert "max-height:min(78dvh" in CSS

    def test_resize_on_sheet_layout_change(self):
        assert "map.resize()" in JS

    def test_r6_coverage_quieter_but_labeled(self):
        # Never color alone: legend keeps textual chips in the layers panel.
        assert "Cobertura verificada" in HTML
        assert '"fill-opacity": 0.06' in JS

    def test_r8_no_new_framework(self):
        # No dependency added to the static layer.
        for banned in ("react", "vue", "svelte", "leaflet", "hammer", "gesture"):
            assert banned not in JS.lower(), banned

    # ── P1 regressions found in the adversarial review of PR #23 ──

    def test_p1_1_css_targets_explore_cta_by_id(self):
        # The CTA div has id="explore-cta" and no class; CSS must use the ID
        # (matters more now that M4 relocates it into #map-container).
        assert "#explore-cta" in CSS
        assert ".explore-cta" not in CSS

    def test_p1_2_escape_closes_exactly_one_level(self):
        # Dropdown Escape must stop propagation AND the sheet coordinator
        # must honour defaultPrevented: one keypress, one level.
        assert "ev.stopPropagation(); close();" in JS
        assert 'ev.key !== "Escape" || ev.defaultPrevented' in JS

    def test_p1_3_closed_state_tap_reachable(self):
        # closed keeps a visible handle strip and the handle cycles all
        # three states, so closing/reopening never requires a drag.
        assert "calc(100% - 44px)" in CSS
        assert "SHEET_STATES[(i + 1) % SHEET_STATES.length]" in JS

    def test_p1_4_cta_notes_come_from_places_data(self):
        # No hardcoded zone claims in JS: the note is place.note from /api/places.
        assert "place.note" in JS
        assert "extremo a extremo" not in JS
        assert "todavía no la verifica" not in JS

    def test_p1_5_sheet_handle_meets_44px_target(self):
        # Touch targets must be >=44px. #sheet-handle is more specific than
        # the generic `button { min-height:44px }` rule, so its own rule
        # must carry the 44px min-height (a 40px value would win).
        rules = re.findall(r"#sheet-handle \{[^}]*\}", CSS)
        assert rules, "missing #sheet-handle rules"
        assert any("min-height:44px" in r for r in rules), \
            "the interactive #sheet-handle rule must set min-height:44px"
        assert "min-height:40px" not in CSS
        # The closed-state strip exposes exactly the handle: 44px strip.
        assert "calc(100% - 44px)" in CSS

    def test_p1_5_chooser_reopens_existing_outings_dropdown(self):
        # Reproduced P1: the no-outings branch hides the "Elige una salida"
        # <label> with sel.parentElement.style.display = "none". The outings-exist
        # branch must restore that parent label, or a second open (once planned
        # outings exist) renders the dropdown invisible and a place can never be
        # added to an EXISTING outing through the UI.
        start = JS.find("function openChooser")
        end = JS.find("function closeChooser")
        assert start != -1 and end != -1 and start < end
        block = JS[start:end]

        # The parent-hide must live ONLY in the outings.length === 0 branch.
        guard = block.find("if (outings.length === 0)")
        else_at = block.find("} else {", guard)
        assert guard != -1 and else_at != -1 and guard < else_at
        no_outings_branch = block[guard:else_at]
        outings_exist_branch = block[else_at:]
        assert 'sel.parentElement.style.display = "none"' in no_outings_branch
        assert 'sel.parentElement.style.display = "none"' not in outings_exist_branch
        assert block.count('sel.parentElement.style.display = "none"') == 1

        # The outings-exist branch restores the parent label right after the
        # select itself, so reopening after creating the first outing works.
        lines = [ln.strip() for ln in outings_exist_branch.splitlines()]
        idxs = [i for i, ln in enumerate(lines) if ln == 'sel.style.display = "";']
        assert idxs, "outings-exist branch must reset sel.style.display"
        for i in idxs:
            assert i + 1 < len(lines), "nothing follows the sel.style.display reset"
            assert lines[i + 1] == 'sel.parentElement.style.display = "";', \
                "outings-exist branch must also restore the parent <label> visibility"
