"""F09 — packaging identity and reproducibility (static checks).

The functional clean-install gate lives in tooling/clean_wheel.ps1 and is
executed per release (its evidence is recorded in
docs/ALRASO-M1-REMEDIATION.md); this module checks what can be verified
hermetically:

  * the fixture ships inside the package (no runtime ../discovery dependency);
  * declared extras match the real optional imports;
  * dependency lock pins match code constants (Axiom identity, contracts).
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_is_a_package_resource():
    data = json.loads(resources.files("alraso.resources")
                      .joinpath("fixture_ordesa.json").read_text(encoding="utf-8"))
    assert data["fixture_meta"]["name"] == "ORDESA_FEASIBILITY_ACCEPTANCE_FIXTURE"


def test_runtime_code_has_no_checkout_relative_fixture_path():
    offenders = []
    for py in (ROOT / "alraso").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "../discovery" in text or "discovery/fixtures" in text:
            offenders.append(py.name)
    assert offenders == []


def test_pyproject_declares_package_data_and_extras():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"alraso.resources"' in text and "*.json" in text
    assert 'axiom = ["PyYAML' in text          # yaml only as extra, core stays empty
    deps = re.search(r"^dependencies = \[[^\]]*\]", text, re.M).group(0)
    assert deps == "dependencies = []"


def test_dependency_lock_matches_code_constants():
    from alraso.engine_axiom import RULESPEC_CONTRACT_VERSION
    from alraso.resolver import RESOLVER_VERSION, SCHEMA_VERSION
    from alraso.schema import POSTGRES_NORMATIVE_STORE_STATUS
    lock = json.loads((ROOT / "tooling" / "DEPENDENCIES.lock.json")
                      .read_text(encoding="utf-8"))
    assert lock["rulespec_compiler_contract_version"] == RULESPEC_CONTRACT_VERSION
    assert lock["schema_version"] == SCHEMA_VERSION
    assert lock["resolver_version"] == RESOLVER_VERSION
    ax = lock["axiom"]
    assert ax["status"] == "EXPERIMENTAL_ADAPTER" and ax["parity_claim"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", ax["binary"]["sha256"])


def test_postgres_status_is_honest_everywhere():
    from alraso.schema import POSTGRES_NORMATIVE_STORE_STATUS
    assert POSTGRES_NORMATIVE_STORE_STATUS == "NOT_IMPLEMENTED"
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    # the README must not claim functional/complete postgres semantics
    for claim in ("postgres semantics ==", "full parity", "production-ready"):
        assert claim not in readme


def test_clean_wheel_gate_script_exists():
    assert (ROOT / "tooling" / "clean_wheel.ps1").exists()
