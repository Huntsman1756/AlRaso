from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")


def _function_block(name: str) -> str:
    start = JS.find(f"function {name}")
    assert start != -1, f"Missing function {name}"
    end = JS.find("\nfunction ", start + 1)
    return JS[start:] if end == -1 else JS[start:end]


def test_primary_answer_is_compact_and_detail_is_progressive_disclosure():
    assert 'id="answer-explanation"' in HTML
    assert 'id="conditions-summary"' in HTML
    assert 'id="place-context"' in HTML
    assert '<details id="detail-box"><summary>Consultar detalle</summary>' in HTML
    assert 'id="ui-knowledge"' not in HTML

    tech_at = HTML.index('id="tech"')
    badges_at = HTML.index('class="badges"')
    codes_at = HTML.index('id="tech-codes"')
    assert tech_at < badges_at < codes_at, "Internal status badges must live inside technical detail"


def test_unknown_answer_copy_is_single_and_user_facing():
    assert 'UNDETERMINED: "No lo podemos determinar"' in JS
    assert "Aún no tenemos normativa verificada para este punto." in JS
    assert 'return "Zona todavía no cubierta.";' in JS
    assert '"Cobertura normativa del punto: ninguna"' in JS
    assert 'No hay fuentes normativas vinculadas a este punto.' in JS

    assert "Ninguna norma del corpus de AlRaso llega a este punto" not in JS
    assert "AlRaso no tiene corpus aquí y por eso no puede afirmar nada" not in JS


def test_port_does_not_restore_poi_altitude_as_legal_altitude():
    render = _function_block("render(d)")
    assert "state.poiAlt" not in render
    assert "d.dem" in render


def test_m6_and_m81_plumbing_remain_single_instance():
    assert JS.count("function loadWeather(") == 1
    assert JS.count("async function loadProtectedAreas(") == 1
    assert 'fetch("/api/protected-areas")' in JS
