"""M9.1 visual-system contracts.

These checks stay deliberately small: they protect the approved token and
semantic-state vocabulary without asserting implementation details of the
legal engine or the map data.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "webapp/static/style.css").read_text(encoding="utf-8")
HTML = (ROOT / "webapp/static/index.html").read_text(encoding="utf-8")
APP = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
ICON_ROOT = ROOT / "webapp/static/icons/outline"


def test_m91_has_small_semantic_token_vocabulary():
    required = (
        "--color-bg",
        "--color-surface",
        "--color-surface-raised",
        "--color-border",
        "--color-text",
        "--color-muted",
        "--color-focus",
        "--color-permitted",
        "--color-prohibited",
        "--color-authorization",
        "--color-undetermined",
        "--space-1",
        "--space-2",
        "--space-3",
        "--space-4",
        "--space-5",
        "--space-6",
        "--radius-sm",
        "--radius-md",
        "--radius-lg",
        "--shadow-card",
        "--shadow-sheet",
    )
    missing = [token for token in required if token not in CSS]
    assert not missing, f"missing M9.1 tokens: {missing}"


def test_m91_has_semantic_legal_state_primitives():
    for state in ("permitted", "prohibited", "authorization", "undetermined"):
        assert f"legal-status--{state}" in CSS


def test_m91_has_shared_focus_and_reduced_motion_primitives():
    assert ":focus-visible" in CSS
    assert "prefers-reduced-motion: reduce" in CSS


def test_m91_result_order_prioritizes_place_and_legal_answer():
    order = (
        "id=\"place-identity\"",
        "id=\"legal-section\"",
        "id=\"weather-block\"",
        "id=\"action-buttons\"",
        "id=\"detail-box\"",
    )
    positions = [HTML.index(marker) for marker in order]
    assert positions == sorted(positions), "primary result order must be place, legal, weather, actions, detail"


def test_m91_place_identity_has_a_semantic_heading_hook():
    assert 'id="place-heading"' in HTML
    assert 'class="place-identity"' in HTML


def test_m91_reason_copy_has_explicit_spatial_and_publishability_paths():
    assert "NO_PUBLISHABLE_RULE_COVERAGE" in APP
    assert "NO_APPLICABLE_SCOPE" in APP
    assert "La zona está delimitada, pero falta una condición verificable" in APP
    assert "Tenemos normativa de la zona, pero la comprobación espacial" in APP


def test_m91_place_heading_is_rendered_from_existing_selection_state():
    assert "function renderPlaceHeading()" in APP
    assert "state.selectedName" in APP
    assert "renderPlaceHeading();" in APP


def test_m91_weather_forecast_is_a_native_disclosure():
    assert 'className = "weather-forecast"' in APP
    assert 'textContent = "Próximas 24 h"' in APP
    assert "forecast.appendChild(summary)" in APP


def test_m91_detail_disclosures_keep_actions_primary_and_detail_secondary():
    assert '<details id="detail-box"><summary>Ver fuentes y detalle</summary>' in HTML
    for summary in (
        "Contexto del lugar",
        "Ajustar la consulta",
        "Por qué damos esta respuesta",
        "Normas y fuentes",
        "Detalle técnico",
    ):
        assert f"<summary>{summary}</summary>" in HTML
    assert HTML.index('id="action-buttons"') < HTML.index('id="detail-box"')


def test_m91_mobile_sheet_exposes_controlled_panel_and_peek_contract():
    assert 'id="sheet-handle"' in HTML
    assert 'aria-controls="card-result"' in HTML
    assert "--sheet-peek-height" in CSS
    assert "sheetPeekHeight" in APP
    assert "handle.focus" in APP


def test_m91_tabler_subset_is_vendored_without_runtime_dependency():
    icons = (
        "map-pin.svg",
        "layers-subtract.svg",
        "bookmark.svg",
        "route.svg",
        "cloud.svg",
        "chevron-down.svg",
        "x.svg",
        "current-location.svg",
    )
    for icon in icons:
        path = ICON_ROOT / icon
        assert path.is_file(), icon
        source = path.read_text(encoding="utf-8")
        assert 'stroke="currentColor"' in source
        assert "viewBox=\"0 0 24 24\"" in source
    notice = (ROOT / "webapp/static/icons/NOTICE-TABLER.txt").read_text(encoding="utf-8")
    assert "MIT License" in notice
    assert "tabler/tabler-icons" in notice
    assert "npm" not in notice.lower()


def test_m91_control_icons_keep_visible_labels_and_no_icon_only_meaning():
    for icon in (
        "map-pin",
        "layers-subtract",
        "current-location",
        "bookmark",
        "route",
        "x",
    ):
        assert f'data-icon="{icon}"' in HTML
    assert ">Explorar<" in HTML
    assert ">Guardados<" in HTML
    assert ">Salidas<" in HTML
    assert "aria-hidden=\"true\"" in HTML
    assert 'data-icon="cloud"' in APP
