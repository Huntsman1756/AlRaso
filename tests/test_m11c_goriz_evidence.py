"""M1.1-C Góriz: gate A evidence is self-consistent (committed artifacts re-hash
to the lock) and the first REAL-WORLD scope resolves end-to-end offline.

These tests read committed evidence only and drive the in-memory resolver with
the official geometry. They NEVER touch the network (live re-check is the
manual tool tooling/m11c_goriz_identity.py)."""
from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from pathlib import Path

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import Query
from alraso.ingest.ordesa import ingest_corpus
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "tooling" / "m11c_goriz_scope.evidence.json"
TOOL_PATH = ROOT / "tooling" / "m11c_goriz_identity.py"
DOC = ROOT / "docs" / "ALRASO-M11C-GORIZ-SCOPE.md"


def _lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _fixture() -> dict:
    ref = resources.files("alraso.resources").joinpath("fixture_goriz.json")
    return json.loads(ref.read_text(encoding="utf-8"))


def _store_and_resolver() -> Resolver:
    fx = _fixture()
    store = BitemporalStore.connect(":memory:")
    ingest_corpus(store, fx)
    provider = InMemorySpatialProvider()
    scope = fx["spatial_scopes"][0]
    provider.add_scope(scope["id"], scope["official_name"], scope["scope_type"],
                       [ [(lat, lon) for lat, lon in ring]
                         for ring in fx["geometry"]["rings_latlon"] ])
    return Resolver(store, spatial=provider)


@pytest.fixture(scope="module")
def lock() -> dict:
    return _lock()


# ---------- evidence lock ----------

def test_committed_artifacts_hash_to_the_lock(lock):
    for name, art in lock["artifacts"].items():
        if name == "mapa_pdf_anchor_sha256_m11b":
            # cross-phase anchor: same PDF pinned by M1.1-B
            m11b = json.loads((ROOT / "tooling" / "m11b_prug_annex.evidence.json")
                              .read_text(encoding="utf-8"))
            assert (m11b["normative_documents"]["annex_11_5_cartography"]["sha256"]
                    == art)
            continue
        path = ROOT / art["path"]
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == art["sha256"], art["path"]
        assert len(data) == art["bytes"], art["path"]


def test_gate_a_classification_and_identity_numbers_are_exact(lock):
    assert lock["schema"] == "alraso-m11c-goriz-scope-evidence/v1"
    assert lock["classification"] == "A"
    assert lock["classification_label"] == "OFFICIAL_SCOPE_LINK_PROVEN"
    id3 = lock["identity_chain"]["3_autonomous_vector_identity"]
    assert id3["iou"] >= 0.9998 and id3["hausdorff_m"] <= 0.01
    assert id3["symdiff_m2"] < 5 and id3["centroid_distance_m"] < 0.01
    assert abs(id3["aragon_area_m2"] - 12505.91) < 0.1
    assert abs(id3["oapn_area_m2"] - 12505.94) < 0.1
    assert id3["parts_aragon"] == id3["parts_oapn"] == 2
    ref = lock["identity_chain"]["4_refuge_anchor"]
    assert ref["oapn_vs_aragon_refuge"]["hausdorff_m"] <= 0.01
    assert ref["distance_polygon_to_polygon_m"] < 10


def test_legal_link_is_the_state_registers_own_attribute(lock):
    feat = lock["identity_chain"]["2_official_state_vector_with_legal_attribute"]
    assert feat["zona"] == "Zona de Uso Moderado"
    assert feat["normativa"] == "Decreto 49/2015, de 8 de abril,(BOA 80, 29/04/2015)"
    assert feat["observaciones"] == "Uso público. Área vivac. Sector Ordesa"
    assert feat["superficie_ha"] == 1.251
    cc = lock["cross_checks"]
    assert cc["zum_features_ordesa_oapn"] == 130
    assert cc["zum_within_250m_of_refuge"] == 1
    assert abs(cc["zum_total_area_ha_oapn"] - 115.48) < 0.01
    assert cc["zum_total_area_ha_prug_text"] == 115.89  # discrepancy recorded, not hidden


def test_current_rule_is_pinned_verbatim_and_declared_current(lock):
    v = lock["verbatim_rule"]
    for token in ("prohibida en el sector Ordesa", "Zona de Uso Moderado de Góriz",
                  "aforo completo del refugio", "reducido a 50 personas",
                  "no excederá de tres noches"):
        assert token in v, token
    assert lock["identity_chain"]["1_norma"]["no_later_modification"]
    boa = lock["identity_chain"]["1_norma"]
    assert re.fullmatch(r"[0-9a-f]{64}", boa["boa_pdf_sha256"])


def test_dead_channels_are_recorded_not_erased(lock):
    joined = " | ".join(lock["failed_channels_recorded"])
    for token in ("403", "0 datasets", "DNS", "NO extraible", "1:5.000"):
        assert token in joined, token


def test_boundary_semantics_decision_is_locked(lock):
    bs = lock["boundary_semantics"]
    assert "ST_Intersects" in bs["decision"]
    assert bs["border_vertex_shapely"] == {"contains": False, "covers": True,
                                           "intersects": True}
    points = {p["label"]: p for p in lock["three_points"]}
    ins = points["inside_centroid"]
    assert ins["shapely_contains"] and ins["shapely_covers"]
    out = points["outside_east"]
    assert not any(out[k] for k in ("shapely_contains", "shapely_covers",
                                    "shapely_intersects"))
    assert out["distance_to_polygon_m"] > 400
    assert points["inside_3m_from_border_vertex"]["shapely_contains"]


def test_layer_policy_never_confuses_availability_with_legality(lock):
    lp = lock["layer_policy"]
    assert "UNDETERMINED" in lp["outside_goriz"]
    assert "NO es legalidad" in lp["LIVE_STATE"]
    assert "UNDETERMINED" in lp["OPERATIONAL_CONDITION"]


def test_no_full_official_geometry_is_redistributed(lock):
    # reuse terms are NOT_VERIFIED (NOTICE.md §4): committed extracts must hold
    # metadata + digests only, never redistributable coordinate arrays
    for name, art in lock["artifacts"].items():
        if not (name.endswith("_extract") and art["path"].endswith(".json")):
            continue
        obj = json.loads((ROOT / art["path"]).read_text(encoding="utf-8"))
        assert "coordinates" not in json.dumps(obj), art["path"]
        assert "full geometry NOT redistributed" in obj["note"]
        assert obj["source_url"].startswith("https://")


def test_data_policy_is_locked_and_documented(lock):
    dp = lock["data_policy"]
    assert "NOT_VERIFIED" in dp["rule"]
    assert "fixture_goriz.json" in dp["exception_minimal_extract"]
    doc = DOC.read_text(encoding="utf-8")
    assert '"fuera de Góriz" no significa "Sector Ordesa prohibido"' in doc
    assert "Política de artefactos" in doc
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "no se redistribuyen geometrías completas" in notice


# ---------- real-world end-to-end ----------

def test_realworld_case_inside_with_conditions_resolves_permitted():
    r = _store_and_resolver()
    lat, lon = _fixture()["probe_points"]["inside_wgs84"]
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2026-08-15",
                          knowledge_date="2026-09-05", lat=lat, lon=lon,
                          facts={"refuge_capacity_full": True, "nights": 2}))
    assert res.legal_status.value == "PERMITTED"
    assert res.knowledge_status.value == "CURRENT"
    assert [s["scope_id"] for s in res.applicable_scope] == ["ss-ordesa-goriz-zum"]
    assert res.evidence and "sd-d16-boa-pdf" in res.basis["source_document_ids"]
    assert any("reservas" in w for w in res.warnings)  # standing operational warning


@pytest.mark.parametrize("facts", [
    {},                                                     # hechos operativos ausentes
    {"refuge_capacity_full": False, "nights": 2},           # refugio con plazas libres
    {"refuge_capacity_full": True, "nights": 4},            # más de tres noches
])
def test_realworld_case_inside_never_permitted_without_the_conditions(facts):
    r = _store_and_resolver()
    lat, lon = _fixture()["probe_points"]["inside_wgs84"]
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2026-08-15",
                          knowledge_date="2026-09-05", lat=lat, lon=lon, facts=facts))
    assert res.legal_status.value == "UNDETERMINED"
    assert res.knowledge_status.value == "INCOMPLETE"


def test_realworld_case_outside_is_undetermined_never_sector_prohibited():
    r = _store_and_resolver()
    lat, lon = _fixture()["probe_points"]["outside_wgs84"]
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2026-08-15",
                          knowledge_date="2026-09-05", lat=lat, lon=lon,
                          facts={"refuge_capacity_full": True, "nights": 2}))
    assert res.legal_status.value == "UNDETERMINED"        # nunca PROHIBITED
    assert res.applicable_scope == []
    assert "NO_APPLICABLE_SCOPE" in "".join(res.reason_codes)


def test_fixture_geometry_is_wgs84_and_scope_provenance_is_verified():
    fx = _fixture()
    for ring in fx["geometry"]["rings_latlon"]:
        for lat, lon in ring:
            assert 42.6 < lat < 42.7 and -0.1 < lon < 0.2   # no UTM relabeling
    scope = fx["spatial_scopes"][0]
    assert scope["review_status"] == "VERIFIED"
    assert "ENP101_137" in scope["geometry_source"]
    cond = fx["legal_rule_versions"][0]["condition"]
    assert cond["all"][0] == {"field": "refuge_capacity_full", "op": "is_true"}
    assert "cupo" not in json.dumps(fx["legal_rule_versions"][0]) or "no se codifica" in \
        fx["legal_rule_versions"][0]["interpretation_note"]


# ---------- tool honesty + doc ----------

def test_verify_tool_compiles_and_fails_honest_offline():
    src = TOOL_PATH.read_text(encoding="utf-8")
    compile(src, str(TOOL_PATH), "exec")
    assert '"classification": "VERIFICATION_INCONCLUSIVE"' in src
    assert "return 2" in src
    assert "import pytest" not in src


def test_documentation_records_gate_a_and_the_layer_policy():
    doc = DOC.read_text(encoding="utf-8")
    for token in ("OFFICIAL_SCOPE_LINK_PROVEN", "IoU 0.999844", "Hausdorff 0,005 m",
                  "aforo completo", "ST_Intersects", "SPATIAL_EVIDENCE_INCOMPLETE",
                  "50 personas", "no extraíble", "Picos de Europa"):
        assert token in doc, token
