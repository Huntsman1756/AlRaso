"""M9.1 visual-system contracts.

These checks stay deliberately small: they protect the approved token and
semantic-state vocabulary without asserting implementation details of the
legal engine or the map data.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "webapp/static/style.css").read_text(encoding="utf-8")


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
