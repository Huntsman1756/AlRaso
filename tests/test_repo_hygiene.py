"""Tests de higiene de repositorio público (chore/repo-public-hygiene).

Estos tests verifican que el repo presenta archivos adecuados para ser público:
documentos internos movidos, archivos de comunidad presentes, README honesto,
y .gitignore que cubre artefactos locales.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_has_only_public_markdown():
    """Root .md debe contener solo archivos públicos (README, NOTICE, CONTRIBUTING, SECURITY)."""
    root_md = {f.name for f in ROOT.glob("*.md")}
    allowed = {"README.md", "NOTICE.md", "CONTRIBUTING.md", "SECURITY.md"}
    assert root_md == allowed


def test_internal_docs_moved():
    """Los tres docs internos deben existir en docs/internal/."""
    internal = ROOT / "docs" / "internal"
    assert (internal / "VIVAC-TECHNICAL-DISCOVERY.md").exists()
    assert (internal / "ALRASO-F2-CLOSURE.md").exists()
    assert (internal / "MILESTONE-1.md").exists()


def test_community_files_exist():
    """CONTRIBUTING.md, SECURITY.md y docs/internal/README.md deben existir."""
    assert (ROOT / "CONTRIBUTING.md").exists()
    assert (ROOT / "SECURITY.md").exists()
    assert (ROOT / "docs" / "internal" / "README.md").exists()


def test_readme_mentions_product_and_webapp():
    """README debe mencionar el producto, la webapp y la licencia, sin afirmaciones prohibidas."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_lower = readme.lower()

    # menciones esperadas (case-sensitive)
    assert "webapp/server.py" in readme, "README debe referenciar webapp/server.py"
    assert "¿Puedo dormir al raso" in readme, "README debe contener el pitch del producto"
    assert "Apache-2.0" in readme, "README debe mencionar la licencia"

    # GÓRIZ_* distinction tokens (post-#20 + hygiene reconciliation)
    assert "GÓRIZ_GEOMETRY=VERIFIED" in readme, "README debe contener GÓRIZ_GEOMETRY=VERIFIED"
    assert "GÓRIZ_RULE_PUBLICATION=BLOCKED" in readme, "README debe contener GÓRIZ_RULE_PUBLICATION=BLOCKED"
    assert "GÓRIZ_USER_RESULT=UNDETERMINED" in readme, "README debe contener GÓRIZ_USER_RESULT=UNDETERMINED"

    # afirmaciones prohibidas (check case-insensitive, espejo de test_packaging)
    for forbidden in ("postgres semantics ==", "full parity", "production-ready"):
        assert forbidden not in readme_lower, (
            f"README no debe contener la afirmación prohibida: '{forbidden}'"
        )

    # forbidden: 2021 Ordesa must NOT be claimed as PERMITTED (NORM_VALIDITY microfix)
    for bad_claim in ["2021-07-15 --knowledge 2023-06-15   # PERMITTED"]:
        assert bad_claim not in readme, (
            f"README no debe contener la afirmación prohibida: '{bad_claim}'"
        )


def test_gitignore_covers_local_tooling():
    """.gitignore debe incluir las entradas de tooling local."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".opencode/", "opencode.jsonc", "deploy/", "tooling/_*.py"):
        assert pattern in gitignore, f".gitignore debe incluir '{pattern}'"