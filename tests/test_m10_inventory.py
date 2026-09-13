"""M10.1 Task 8 — InventorySource seed + space↔authority reconciliation.

Boundary: load the pilot space inventory (seeded from G0/OAPN) into
SpaceRecord[] and expose each space's authority references (jurisdiction +
gazette + cite) as discovery seeds. No fetch, no parse, no legal claims —
a cite string is a pointer to look up, not a resolved norm.
"""

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import pipeline.providers.inventory as inventory_mod
from pipeline.models import SpaceRecord
from pipeline.providers.inventory import (
    InventoryError,
    authority_refs,
    load_seed,
    list_spaces,
)

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "pipeline" / "sources" / "pilot-spaces.json"


def test_seed_loads_and_is_frozen():
    seed = load_seed(SEED)
    with pytest.raises(TypeError):
        seed["spaces"] = []


def test_list_spaces_covers_five_pilots_four_spaces():
    spaces = list_spaces(load_seed(SEED))
    by_id = {s.space_id: s for s in spaces}
    assert set(by_id) == {
        "pn-picos-de-europa",
        "pn-ordesa-y-monte-perdido",
        "pn-aiguestortes-i-estany-de-sant-maurici",
        "pn-teide",
    }
    for s in spaces:
        assert isinstance(s, SpaceRecord)
        assert s.figure_type == "PN"
        assert s.ccaa
        assert s.source == "oapn-red-pn"
        assert s.observed_at == "2026-09-13"
        assert len(s.evidence_sha256) == 64


def test_space_evidence_hash_is_seed_file_hash():
    seed = load_seed(SEED)
    expect = hashlib.sha256(SEED.read_bytes()).hexdigest()
    assert all(s.evidence_sha256 == expect for s in list_spaces(seed))


def test_picos_one_space_three_authorities():
    """One space → N jurisdictions: Picos de Europa spans AS/CB/CL and each
    publishes its own instrument — modeled as three authority_refs."""
    refs = authority_refs("pn-picos-de-europa", load_seed(SEED))
    assert [(r["jurisdiction"], r["gazette"]) for r in refs] == [
        ("ES-AS", "bopa"),
        ("ES-CB", "boc-cantabria"),
        ("ES-CL", "bocyl"),
    ]
    cites = {r["jurisdiction"]: r["cite"] for r in refs}
    assert cites["ES-CL"] == "Decreto 17/2025"


def test_pilot_authority_refs():
    seed = load_seed(SEED)
    assert authority_refs("pn-ordesa-y-monte-perdido", seed)[0] == {
        "jurisdiction": "ES-AR",
        "gazette": "boa",
        "cite": "Decreto 16/2022",
    }
    assert authority_refs("pn-aiguestortes-i-estany-de-sant-maurici", seed)[0][
        "gazette"
    ] == "dogc"
    assert authority_refs("pn-teide", seed)[0]["gazette"] == "boc-canarias"


def test_admin_geom_ref_matches_oapn_feature_name():
    """admin_geom_ref is the lookup key into the OAPN limites digest layer."""
    spaces = {s.space_id: s for s in list_spaces(load_seed(SEED))}
    assert spaces["pn-picos-de-europa"].admin_geom_ref == (
        "Parque Nacional de los Picos de Europa"
    )
    assert spaces["pn-teide"].admin_geom_ref == "Parque Nacional del Teide"


def test_unknown_space_fails_explicit():
    with pytest.raises(InventoryError, match="pn-desconocido"):
        authority_refs("pn-desconocido", load_seed(SEED))


def test_malformed_seed_fails():
    with pytest.raises(InventoryError):
        list_spaces({"schema": "alraso.m10.pilot-spaces/v1", "spaces": [{}]})


def test_no_network_no_layers_no_jurisdiction_branches():
    src = inspect.getsource(inventory_mod)
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not imported & {
        "providers.discovery", "providers.fetch", "providers.parse",
        "providers.version", "providers.geometry",
    }
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
