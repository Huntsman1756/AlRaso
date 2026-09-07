"""Picos Phase B fixture: art. 51 common rule per CCAA + jurisdiction via
simplified OAPN/GISCO boundary. Offline, no network. Fail-closed invariants:
PERMITTED never from absence; jurisdiction is exclusive; pre-effective dates
never permit; outside park never a sectorial prohibition."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alraso.bitemporal import BitemporalStore  # noqa: E402
from alraso.domain import Query  # noqa: E402
from alraso.ingest.ordesa import ingest_corpus  # noqa: E402
from alraso.resolver import Resolver  # noqa: E402
from alraso.spatial import InMemorySpatialProvider  # noqa: E402

FIXTURE = ROOT / "alraso" / "resources" / "fixture_picos.json"
GEOM_KEY = {
    "ss-pnpe-limits": "park",
    "ss-pnpe-es-as": "es-as",
    "ss-pnpe-es-cb": "es-cb",
    "ss-pnpe-es-cl": "es-cl",
}
TODAY = "2026-09-06"
FACTS = {"actividad_montana_o_escalada": True, "nights": 2, "cota_m": 2400,
         "jurisdiction_boundary_safe": True}


@pytest.fixture(scope="module")
def res():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = BitemporalStore.connect(":memory:")
    ingest_corpus(store, fx)
    provider = InMemorySpatialProvider()
    for sc in fx["spatial_scopes"]:
        rings = fx["geometry"].get(GEOM_KEY[sc["id"]], [])
        if rings:
            provider.add_scope(sc["id"], sc["official_name"], sc["scope_type"],
                               [[(float(lat), float(lon)) for lat, lon in ring] for ring in rings])
    return Resolver(store, spatial=provider), fx


def _q(res, lat, lon, facts=None, date=TODAY):
    r, _fx = res
    return r.resolve(Query(activity="VIVAC_AL_RASO", activity_date=date,
                           knowledge_date=date, lat=lat, lon=lon, facts=facts or {})).to_dict()


def test_p1_asturias_permitted_with_facts(res):
    out = _q(res, 43.2662, -4.8686, FACTS)
    assert out["legalStatus"] == "PERMITTED"
    assert [s["scope_id"] for s in out["applicableScope"]] == ["ss-pnpe-es-as", "ss-pnpe-limits"]


def test_p2_cantabria_permitted_with_facts(res):
    out = _q(res, 43.17068, -4.80299, FACTS)
    assert out["legalStatus"] == "PERMITTED"
    assert "ss-pnpe-es-cb" in [s["scope_id"] for s in out["applicableScope"]]
    assert "ss-pnpe-es-as" not in [s["scope_id"] for s in out["applicableScope"]]


def test_p3_cyl_permitted_with_facts(res):
    out = _q(res, 43.1278, -4.9381, FACTS)
    assert out["legalStatus"] == "PERMITTED"
    assert "ss-pnpe-es-cl" in [s["scope_id"] for s in out["applicableScope"]]


def test_jurisdictions_are_mutually_exclusive(res):
    # P1 (es-as) must never be governed by the es-cb or es-cl rule.
    out = _q(res, 43.2662, -4.8686, FACTS)
    assert out["legalStatus"] == "PERMITTED"
    assert "ss-pnpe-es-cb" not in [s["scope_id"] for s in out["applicableScope"]]
    assert "ss-pnpe-es-cl" not in [s["scope_id"] for s in out["applicableScope"]]


def test_without_facts_never_permitted(res):
    out = _q(res, 43.2662, -4.8686, {})
    assert out["legalStatus"] == "UNDETERMINED"
    assert "ENGINE_MISSING_INPUT" in out["reasonCodes"]


def test_below_1800_never_permitted(res):
    out = _q(res, 43.2662, -4.8686, {"actividad_montana_o_escalada": True, "nights": 2,
                                     "cota_m": 1500, "jurisdiction_boundary_safe": True})
    assert out["legalStatus"] == "UNDETERMINED"
    assert "NO_CONDITION_SATISFIED" in out["reasonCodes"]


def test_cota_exactly_1800_never_permitted(res):
    # art. 51: "por encima de la cota 1.800 m" -> ESTRICTAMENTE > 1800.
    out = _q(res, 43.2662, -4.8686, {"actividad_montana_o_escalada": True, "nights": 2,
                                     "cota_m": 1800, "jurisdiction_boundary_safe": True})
    assert out["legalStatus"] == "UNDETERMINED"
    assert "NO_CONDITION_SATISFIED" in out["reasonCodes"]


def test_cota_1801_permitted(res):
    out = _q(res, 43.2662, -4.8686, {"actividad_montana_o_escalada": True, "nights": 2,
                                     "cota_m": 1801, "jurisdiction_boundary_safe": True})
    assert out["legalStatus"] == "PERMITTED"


def test_without_boundary_fact_never_permitted(res):
    # Si se reutiliza el fixture sin el guard de frontera, falta el hecho interno
    # -> fail-closed (nunca un permiso).
    out = _q(res, 43.2662, -4.8686, {"actividad_montana_o_escalada": True,
                                     "nights": 2, "cota_m": 2400})
    assert out["legalStatus"] == "UNDETERMINED"
    assert "ENGINE_MISSING_INPUT" in out["reasonCodes"]


def test_boundary_unsafe_fact_never_permitted(res):
    out = _q(res, 43.2662, -4.8686, {"actividad_montana_o_escalada": True, "nights": 2,
                                     "cota_m": 2400, "jurisdiction_boundary_safe": False})
    assert out["legalStatus"] == "UNDETERMINED"
    assert "NO_CONDITION_SATISFIED" in out["reasonCodes"]


def test_pre_effective_never_permitted(res):
    out = _q(res, 43.17068, -4.80299, FACTS, date="2026-08-01")
    assert out["legalStatus"] == "UNDETERMINED"
    assert "NO_KNOWLEDGE_AT_DATE" in out["reasonCodes"]


def test_outside_park_not_sectorial_prohibition(res):
    out = _q(res, 43.348, -5.13, {})
    assert out["legalStatus"] == "UNDETERMINED"
    assert "NO_APPLICABLE_SCOPE" in out["reasonCodes"]
    assert out["applicableScope"] == []


def test_fixture_has_three_verified_rules_and_sources(res):
    _r, fx = res
    assert len(fx["legal_rule_versions"]) == 3
    assert len(fx["spatial_scopes"]) == 4
    assert len(fx["source_documents"]) == 3
    for v in fx["legal_rule_versions"]:
        assert v["review_status"] == "VERIFIED"
        cond_fields = [c["field"] for c in v["condition"]["all"]]
        # art. 51 exige > 1800, no >= 1800
        cota = next(c for c in v["condition"]["all"] if c["field"] == "cota_m")
        assert cota == {"field": "cota_m", "op": "gt", "value": 1800}
        # el guard de frontera es un hecho interno exigido por la regla
        assert "jurisdiction_boundary_safe" in cond_fields
    for s in fx["spatial_scopes"]:
        assert s["review_status"] == "VERIFIED"
    park = next(s for s in fx["spatial_scopes"] if s["id"] == "ss-pnpe-limits")
    assert park["relevance"] == "CONTEXT_ONLY"
    for s in fx["spatial_scopes"]:
        if s["id"] != "ss-pnpe-limits":
            assert s["relevance"] == "REGULATORY"
