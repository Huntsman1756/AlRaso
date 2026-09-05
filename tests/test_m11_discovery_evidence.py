"""M1.1 discovery evidence: the lock and the documentation must keep telling the
same true story, and the discovery tool must remain safe offline. These tests
read committed evidence; they NEVER touch the network."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "tooling" / "m11_vector_discovery.lock.json"
TOOL_PATH = ROOT / "tooling" / "m11_vector_discovery.py"
DOC_PATH = ROOT / "docs" / "ALRASO-M11-VECTOR-DISCOVERY.md"


@pytest.fixture(scope="module")
def lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def test_lock_is_self_consistent(lock):
    assert lock["schema"] == "alraso-m11-vector-discovery/v1"
    assert lock["classification"] == "NO_OFFICIAL_VECTOR_SCOPE_FOUND"
    assert lock["spatial_status"] == "SPATIAL_EVIDENCE_INCOMPLETE"
    assert len(lock["evidence"]) >= 6
    for e in lock["evidence"]:
        assert re.fullmatch(r"[0-9a-f]{64}", e["sha256"]), e["artifact"]
        assert e["endpoint"].startswith("https://")
        assert "aragon" in e["endpoint"]
        assert e["bytes"] > 0
    obs = lock["observations"]
    # recorded reality (historical record; live drift is the --verify tool's job)
    assert obs["published_feature_types_total"] == 1001
    assert obs["published_layer_names_matching_prug_pernocta_acampada_vivac"] == []
    assert obs["zenp_enp101_sector_named_features"] == 0
    assert obs["zenp_enp101_features_with_nonempty_planificationzone"] == 0
    assert obs["porn_plan_layer_features_pnomp"] == 0
    assert obs["porn_zoning_layer_features_pnomp"] == 0


def test_park_polygon_is_recorded_as_the_wrong_scope(lock):
    park = lock["park_polygon_never_a_sector_substitute"]
    assert park["codigo"] == "ENP101"
    assert "WHOLE PARK" in park["scope"]
    assert "boe" in park["legalfoundationdocument"].lower()
    assert lock["policy"]["park_polygon_as_sector_substitute"] == "FORBIDDEN"
    assert lock["policy"]["digitization_allowed"] is False


def test_candidate_B_is_the_campsite_and_stays_separate(lock):
    b = lock["kept_separate_candidate_B"]
    assert b["zonecode"] == "ENP101_137"          # campsite, NOT the refuge (ENP101_025)
    assert "acampada" in b["zonename"].lower()
    assert b["grade"].startswith("B-candidate")
    assert "never be merged" in b["grade"]


def test_documentation_states_the_verdict_and_the_stop_rules():
    doc = DOC_PATH.read_text(encoding="utf-8")
    for token in ("NO_OFFICIAL_VECTOR_SCOPE_FOUND", "SPATIAL_EVIDENCE_INCOMPLETE",
                  "Anexo 11.5", "DISCOVERY_INCONCLUSIVE", "ENP101_137",
                  "SPATIAL_REVIEWED", "duplicado", "hueco de publicaci"):
        assert token in doc, token


def test_discovery_tool_compiles_and_fails_honest_offline():
    src = TOOL_PATH.read_text(encoding="utf-8")
    compile(src, str(TOOL_PATH), "exec")
    # offline honesty: an unreachable endpoint must yield INCONCLUSIVE (exit 2),
    # never the silent negative verdict
    assert '"classification": "DISCOVERY_INCONCLUSIVE"' in src
    assert "urllib.error.URLError" in src
    assert "return 2" in src
    assert "import pytest" not in src            # the tool is not a test and must not network in one
