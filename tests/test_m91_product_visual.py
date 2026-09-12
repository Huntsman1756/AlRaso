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
