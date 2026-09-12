from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected one occurrence in {path}, got {text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "tests/test_m31_product_ux.py",
    '        assert "Fuentes y detalle" in HTML',
    '        assert "Consultar detalle" in HTML',
)

replace_once(
    "tests/test_m3_product.py",
    '    # "Fuentes y detalle" after "Añadir a una salida"\n    sources_idx = html.find("Fuentes y detalle")',
    '    # "Consultar detalle" after "Añadir a una salida"\n    sources_idx = html.find("Consultar detalle")',
)
