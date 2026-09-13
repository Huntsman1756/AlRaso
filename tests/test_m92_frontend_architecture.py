"""M9.2 frontend architecture contracts.

These checks lock the native-module graph and the three-way static serving
contract: module files, server allowlist, and service-worker shell.
"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = ROOT / "webapp/static/modules"
APP = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
SW = (ROOT / "webapp/static/sw.js").read_text(encoding="utf-8")
SERVER = (ROOT / "webapp/server.py").read_text(encoding="utf-8")

MODULES = (
    "dom.js",
    "state.js",
    "api-legal.js",
    "api-cartography.js",
    "map.js",
    "place.js",
    "legal.js",
    "search.js",
    "weather.js",
    "sheet.js",
    "saved.js",
    "connectivity.js",
)

ALLOWED_IMPORTS = {
    "dom.js": set(),
    "state.js": set(),
    "api-legal.js": set(),
    "api-cartography.js": set(),
    "map.js": {"dom.js", "api-legal.js", "api-cartography.js"},
    "place.js": {"dom.js", "state.js"},
    "legal.js": {"dom.js", "state.js", "api-legal.js"},
    "search.js": {"dom.js", "state.js", "api-legal.js"},
    "weather.js": {"dom.js"},
    "sheet.js": {"dom.js"},
    "saved.js": {"dom.js", "state.js", "place.js"},
    "connectivity.js": {"dom.js"},
}

IMPORT_RE = re.compile(r"^\s*import(?:\s+[^\"']+\s+from\s+)?\s*[\"']([^\"']+)[\"']", re.MULTILINE)

FROM_IMPORT_RE = re.compile(
    r"^\s*import\s+([^;\"']+?)\s+from\s+[\"'](\./[^\"']+)[\"']", re.MULTILINE
)
BARE_IMPORT_RE = re.compile(r"^\s*import\s*[\"'](\./[^\"']+)[\"']", re.MULTILINE)


def _imported_names(source: str, specifier: str) -> set[str]:
    names: set[str] = set()
    for clause, target in FROM_IMPORT_RE.findall(source):
        if target != specifier:
            continue
        clause = clause.strip()
        assert clause.startswith("{") and clause.endswith("}"), (
            f"only named imports are allowed from {specifier}: {clause}"
        )
        for part in clause[1:-1].split(","):
            name = part.strip()
            if name:
                names.add(name.split(" as ")[0].strip())
    for target in BARE_IMPORT_RE.findall(source):
        assert target != specifier, f"bare import from {specifier} is forbidden"
    return names


def _imports(source: str, *, app: bool = False) -> set[str]:
    targets = set()
    for specifier in IMPORT_RE.findall(source):
        assert specifier.startswith("./"), specifier
        relative = specifier[2:]
        if app:
            assert relative.startswith("modules/"), specifier
            targets.add(relative.removeprefix("modules/"))
        else:
            targets.add(relative)
    return targets


def _shell_urls() -> set[str]:
    shell_start = SW.index("var SHELL_URLS = [")
    shell_end = SW.index("];", shell_start)
    return set(re.findall(r'["\']([^"\']+)["\']', SW[shell_start:shell_end]))


def _server_module_urls() -> set[str]:
    return set(re.findall(r'["\'](/modules/[^"\']+\.js)["\']\s*:', SERVER))


def test_exact_frontend_module_inventory_is_present():
    assert tuple(sorted(path.name for path in MODULE_ROOT.glob("*.js"))) == tuple(sorted(MODULES))
    assert all((MODULE_ROOT / module).is_file() for module in MODULES)


def test_dependency_matrix_has_no_forbidden_edges():
    graph = {}
    for module in MODULES:
        imports = _imports((MODULE_ROOT / module).read_text(encoding="utf-8"))
        assert imports <= ALLOWED_IMPORTS[module], f"forbidden imports in {module}: {imports}"
        graph[module] = imports

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module: str):
        if module in visiting:
            raise AssertionError(f"import cycle detected at {module}")
        if module in visited:
            return
        visiting.add(module)
        for dependency in graph[module]:
            visit(dependency)
        visiting.remove(module)
        visited.add(module)

    for module in MODULES:
        visit(module)


def test_app_is_the_only_composition_root_and_imports_all_modules():
    assert _imports(APP, app=True) == {
        "dom.js",
        "state.js",
        "legal.js",
        "place.js",
        "saved.js",
        "weather.js",
        "connectivity.js",
        "search.js",
        "map.js",
        "sheet.js",
    }
    for module in MODULES:
        source = (MODULE_ROOT / module).read_text(encoding="utf-8")
        assert "./app.js" not in source


def test_map_js_named_imports_from_api_legal_are_locked_to_fetchcoverage():
    source = (MODULE_ROOT / "map.js").read_text(encoding="utf-8")
    names = _imported_names(source, "./api-legal.js")
    assert names == {"fetchCoverage"}, f"map.js api-legal.js imports: {sorted(names)}"


def test_saved_js_named_imports_from_place_are_locked_to_poi_cats():
    source = (MODULE_ROOT / "saved.js").read_text(encoding="utf-8")
    names = _imported_names(source, "./place.js")
    assert names == {"POI_CATS"}, f"saved.js place.js imports: {sorted(names)}"


def test_dom_exports_remain_frozen_and_product_has_no_dynamic_imports():
    dom = (MODULE_ROOT / "dom.js").read_text(encoding="utf-8")
    exports = set(re.findall(r"\bexport\s+(?:const|function|let|var|class)\s+([A-Za-z_$][\w$]*)", dom))
    assert exports == {"$", "esc"}

    product_js = "\n".join(
        [APP] + [(MODULE_ROOT / module).read_text(encoding="utf-8") for module in MODULES]
    )
    assert not re.search(r"\bimport\s*\(", product_js)


def test_product_does_not_assign_new_window_members():
    product_js = "\n".join(
        [APP] + [(MODULE_ROOT / module).read_text(encoding="utf-8") for module in MODULES]
    )
    assert not re.search(r"\bwindow\.[A-Za-z_$][\w$]*\s*(?<![=!])=(?!=)", product_js)
    assert "window.AlRasoStore" in APP


def test_module_files_server_allowlist_and_shell_are_consistent():
    expected_urls = {f"/modules/{module}" for module in MODULES}
    module_files = {f"/modules/{path.name}" for path in MODULE_ROOT.glob("*.js")}
    server_urls = _server_module_urls()
    shell_urls = {url for url in _shell_urls() if url.startswith("/modules/")}

    assert module_files == expected_urls
    assert server_urls == expected_urls
    assert shell_urls == expected_urls
    for url in sorted(expected_urls):
        module = url.removeprefix("/modules/")
        assert f'"{url}": ("modules/{module}", "text/javascript; charset=utf-8")' in SERVER
