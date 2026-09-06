"""M2-A Picos discovery: the multi-jurisdiction evidence lock is self-consistent
(committed extracts re-hash to the lock), legal fail-closed stances are pinned,
and no full official vector/PDF got redistributed. Offline only: live re-check is
the manual tool tooling/m2a_picos_verify.py (OK / FAIL / INCONCLUSIVE)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "tooling" / "m2a_picos_discovery.evidence.json"
DOC = ROOT / "docs" / "ALRASO-M2A-PICOS-DISCOVERY.md"
VERIFY_TOOL = ROOT / "tooling" / "m2a_picos_verify.py"
EVID_DIR = ROOT / "discovery" / "evidence" / "m2a-picos"

HEX64 = re.compile(r"[0-9a-f]{64}")
COORD_RUN = re.compile(r"-?\d+\.\d+,-?\d+\.\d+(?=-?\d+\.\d+,-?\d+\.\d+)")


@pytest.fixture(scope="module")
def lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def extracts() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(EVID_DIR.glob("*.txt"))}


# ---------- evidence lock ----------

def test_lock_schema_and_baseline(lock):
    assert lock["schema"] == "alraso-m2a-picos-discovery-evidence/v1"
    assert lock["baseline_source_main"] == "7650dace51f6c8c17fc43fcfb979ec5d0e57f43e"
    assert lock["gate"]["classification"] == "A"
    assert lock["gate"]["name"] == "MULTI_JURISDICTION_EVIDENCE_READY"


def test_committed_extracts_hash_to_the_lock(lock):
    for name, doc in lock["legal_documents"].items():
        art = doc["artifact"]
        blob = (ROOT / art["path"]).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == art["sha256"], name
        assert len(blob) == art["bytes"], name


def test_jurisdictions_are_the_three_ccaa_with_exact_effective_dates(lock):
    docs = lock["legal_documents"]
    assert {d["jurisdiction"] for d in docs.values()} == {"es-as", "es-cb", "es-cl"}
    by_j = {d["jurisdiction"]: d for d in docs.values()}
    assert by_j["es-cl"]["effective_from"] == "2026-01-04"
    assert by_j["es-as"]["effective_from"] == "2026-04-19"
    assert by_j["es-cb"]["effective_from"] == "2026-08-24"
    for d in docs.values():
        assert d["publication_date"] < d["effective_from"]
        assert HEX64.fullmatch(d["official_copy_sha256"])


# ---------- verbatim legal text ----------

def test_all_extracts_carry_the_common_substantive_rule(extracts):
    assert len(extracts) == 3
    for name, txt in extracts.items():
        assert "cota 1.800" in txt, name
        assert "maximo de 3 noches" in txt, name
        assert "veinte dias de su publicacion" in txt, name
        assert "Articulo 51. Vivaqueo 1." in txt, name
        assert "Articulo 52. Acampada y pernocta 1." in txt, name
        assert "NOT FOUND" not in txt, name


def test_each_extract_claims_only_its_own_territorial_scope(extracts):
    scope = {
        "as-21-2026-extract.txt": "principado de asturias",
        "cb-57-2026-extract.txt": "cantabria",
        "cyl-17-2025-extract.txt": "castilla y leon",
    }
    areas = {
        "as-21-2026-extract.txt": "27.477 hectareas",
        "cb-57-2026-extract.txt": "14.973 hectareas",
        "cyl-17-2025-extract.txt": "23.580 hectareas",
    }
    for fname, token in scope.items():
        low = extracts[fname].lower()
        assert token in low, fname
        assert areas[fname] in extracts[fname], fname


# ---------- spatial cross-checks ----------

def test_park_geometry_daggers_are_wellformed_and_area_matches_official_sum(lock):
    park = lock["spatial"]["park_oapn"]
    assert HEX64.fullmatch(park["coord_digest_25830_2dp"])
    assert park["n_points"] == 3519
    assert park["crosscheck_delta_pct"] < 0.01  # vs 66.030 ha from the three preambles
    assert "NOT_VERIFIED" in park["reuse_terms"]


def test_ccaa_split_is_within_tolerance_and_leaves_no_residue(lock):
    split = lock["spatial"]["split_check_ha"]
    expected = lock["spatial"]["split_expected_preambulo_ha"]
    for nid, ha in split.items():
        assert abs(ha - expected[nid]) / expected[nid] < 0.001, nid
    assert lock["spatial"]["residue_inside_park_outside_all_ccaa_ha"] < 1.0
    g = lock["spatial"]["ccaa_gisco_nuts2"]
    assert HEX64.fullmatch(g["file_sha256"])
    assert set(g["per_unit_digests"]) == {"ES12", "ES13", "ES41"}
    for d in g["per_unit_digests"].values():
        assert HEX64.fullmatch(d["coord_digest_4dp"])


def test_probe_points_always_yield_exactly_one_ccaa_inside_the_park(lock):
    pp = lock["probe_points"]
    for name, pt in pp.items():
        if pt.get("inside_park"):
            assert len(pt["ccaa"]) == pt.get("expect_ccaa_count", 1), name
    assert {pp["P4a_es13_300m"]["ccaa"][0], pp["P4b_es12_300m"]["ccaa"][0]} == {"ES12", "ES13"}
    assert {pp["P5a_es13_300m"]["ccaa"][0], pp["P5b_es41_300m"]["ccaa"][0]} == {"ES13", "ES41"}


def test_bitemporal_gap_point_must_stay_undetermined(lock):
    p6 = lock["probe_points"]["P6_bitemporal_gap"]
    assert "INCOMPLETE_JURISDICTION_COVERAGE_NEVER_PERMITS" in p6["expect"]
    assert "UNDETERMINED" in p6["expect"]
    assert p6["as_of"] < lock["legal_documents"]["Decreto_57_2026_CB"]["effective_from"]
    p7 = lock["probe_points"]["P7_outside_cangas"]
    assert p7["inside_park"] is False
    assert "NO_APPLICABLE_SCOPE" in p7["expect"]
    assert "nunca" in p7["expect"].lower()


# ---------- legal fail-closed stances ----------

def test_pre2026_legal_chain_is_unresolved_and_fail_closed(lock):
    rd = lock["state_framework_pointers"]["RD_384_2002_PRUG_anterior"]
    assert "UNDETERMINED" in rd["status"]
    assert "LEGACY_STATUS_UNRESOLVED" in rd["status"]
    assert "NO lo mencionan" in rd["facts"][2]
    assert "UNDETERMINED" in lock["gate"]["implementation_allowed_for_phaseB"]


def test_blockers_and_deferred_are_declared_not_hidden(lock):
    joined = " ".join(lock["blockers_for_full_runtime"])
    assert "IDE" in joined
    assert any("RD 384/2002" in b for b in lock["blockers_for_full_runtime"])
    assert any("1.800" in b for b in lock["blockers_for_full_runtime"])
    assert lock["deferred"]


# ---------- data redistribution guard ----------

def test_no_full_vectors_or_pdfs_are_redistributed(lock, extracts):
    assert list(EVID_DIR.glob("*.geojson")) == []
    assert list(EVID_DIR.glob("*.pdf")) == []
    for name, txt in extracts.items():
        longest_run = max((len(m.group(0)) // 22 for m in COORD_RUN.finditer(txt.replace(" ", ""))), default=0)
        assert longest_run < 5, name
    lock_text = LOCK_PATH.read_text(encoding="utf-8")
    longest_run = max((len(m.group(0)) // 22 for m in COORD_RUN.finditer(lock_text.replace(" ", ""))), default=0)
    assert longest_run < 5


# ---------- manual tool + doc ----------

def test_verify_tool_exists_and_never_claims_ok_offline():
    src = VERIFY_TOOL.read_text(encoding="utf-8")
    assert "INCONCLUSIVE" in src
    assert "return 2" in src
    assert "import requests" not in src  # stdlib-only, like the M1.1 tools


def test_discovery_doc_pins_gate_and_fail_closed_phrases():
    txt = DOC.read_text(encoding="utf-8")
    for token in (
        "MULTI_JURISDICTION_EVIDENCE_READY",
        "IMPLEMENTATION_ALLOWED=YES",
        "PICOS_LEGAL_CHAIN=PARTIAL_VIGENTE",
        "sin precedente",
        "UNDETERMINED",
        "alraso:es-as/pn-picos/pernocta#vivac-cota-1800",
        "INCOMPLETE_JURISDICTION_COVERAGE_NEVER_PERMITS",
        "NO_APPLICABLE_SCOPE",
    ):
        assert token in txt, token
