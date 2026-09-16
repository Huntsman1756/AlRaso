"""M10.1 Task 7 — GeometryProvider OAPN + scope_evidence_status contract.

Boundary: turn a persisted layer digest artifact (G0 ``*.digest.json``
shape — the WFS-derived, re-fetchable representation) into
``GeometryEvidence[]``. Digest-only redistribution: geometry itself is
never emitted. ``scope_evidence_status`` is always CONTEXT_ONLY — an
administrative polygon never becomes legal scope by being official.
"""

import ast
import inspect
import json
from pathlib import Path

import pytest

import pipeline.providers.geometry as geometry_mod
from pipeline.models import (
    GeometryEvidence,
    RedistributionPolicy,
    ScopeEvidenceStatus,
)
from pipeline.providers.geometry import GeometryError, geometry_from_layer_digest

ROOT = Path(__file__).resolve().parents[1]
G0 = ROOT / "discovery" / "evidence" / "spain-coverage-g0"
LIMITES = G0 / "oapn-limites-pn.digest.json"
ZONIFICACION = G0 / "oapn-zonificacion-prug.digest.json"

OAPN_WFS = "https://sigred.oapn.es/geoserverOAPN/ows"
LAYER_LIMITES = "LimitesParquesNacionalesZPP:view_red_oapn_limite_pn"
LAYER_ZONIF = "ZonificacionPRUG:view_zon_zonificacion_prug"


def _limites() -> dict:
    return json.loads(LIMITES.read_text(encoding="utf-8"))


def _zonificacion() -> dict:
    return json.loads(ZONIFICACION.read_text(encoding="utf-8"))


def test_limites_picos_produces_evidence_with_digest():
    evs = geometry_from_layer_digest(
        space_id="pn-picos-de-europa",
        space_name="Parque Nacional de los Picos de Europa",
        layer_doc=_limites(),
        layer=LAYER_LIMITES,
        source_url=OAPN_WFS,
    )
    assert len(evs) == 1
    ev = evs[0]
    assert isinstance(ev, GeometryEvidence)
    assert ev.space_id == "pn-picos-de-europa"
    assert ev.provider == "oapn_wfs"
    assert ev.layer == LAYER_LIMITES
    assert len(ev.digest_sha256) == 64
    assert ev.feature_props["Nombre"] == (
        "Parque Nacional de los Picos de Europa"
    )
    assert ev.source_url == OAPN_WFS
    assert ev.crs == "EPSG:4326"


def test_scope_evidence_status_is_always_context_only():
    for name in (
        "Parque Nacional de los Picos de Europa",
        "Parque Nacional de Ordesa y Monte Perdido",
        "Parque Nacional de Aigüestortes i Estany de Sant Maurici",
        "Parque Nacional del Teide",
    ):
        for ev in geometry_from_layer_digest(
            space_id="x",
            space_name=name,
            layer_doc=_limites(),
            layer=LAYER_LIMITES,
            source_url=OAPN_WFS,
        ):
            assert ev.scope_evidence_status is ScopeEvidenceStatus.CONTEXT_ONLY
            assert ev.redistribution_policy is RedistributionPolicy.DIGEST_ONLY


def test_zonificacion_ordesa_multiple_features():
    evs = geometry_from_layer_digest(
        space_id="pn-ordesa-y-monte-perdido",
        space_name="Parque Nacional de Ordesa y Monte Perdido",
        layer_doc=_zonificacion(),
        layer=LAYER_ZONIF,
        source_url=OAPN_WFS,
    )
    assert len(evs) > 1
    assert all(
        ev.scope_evidence_status is ScopeEvidenceStatus.CONTEXT_ONLY
        for ev in evs
    )
    # Deterministic canonical order regardless of feature order in the doc.
    digests = [ev.digest_sha256 for ev in evs]
    assert digests == sorted(digests)


def test_picos_absent_from_zonificacion_is_honest_empty():
    """Picos has no PRUG zoning features in the G0 layer — the provider
    reports [], never invents evidence."""
    evs = geometry_from_layer_digest(
        space_id="pn-picos-de-europa",
        space_name="Parque Nacional de los Picos de Europa",
        layer_doc=_zonificacion(),
        layer=LAYER_ZONIF,
        source_url=OAPN_WFS,
    )
    assert evs == []


def test_malformed_layer_doc_fails_explicit():
    with pytest.raises(GeometryError, match="features"):
        geometry_from_layer_digest(
            space_id="x",
            space_name="y",
            layer_doc={"no_features": True},
            layer=LAYER_LIMITES,
            source_url=OAPN_WFS,
        )


def test_matched_feature_without_digest_fails():
    doc = {
        "retrieved_at": "2026-09-13",
        "features": [
            {
                "properties": {"Nombre": "Parque Nacional X"},
                "geometry_meta": {},
            }
        ],
    }
    with pytest.raises(GeometryError, match="digest"):
        geometry_from_layer_digest(
            space_id="x",
            space_name="Parque Nacional X",
            layer_doc=doc,
            layer=LAYER_LIMITES,
            source_url=OAPN_WFS,
        )


def test_deterministic_output():
    a = geometry_from_layer_digest(
        space_id="pn-picos-de-europa",
        space_name="Parque Nacional de los Picos de Europa",
        layer_doc=_limites(),
        layer=LAYER_LIMITES,
        source_url=OAPN_WFS,
    )
    b = geometry_from_layer_digest(
        space_id="pn-picos-de-europa",
        space_name="Parque Nacional de los Picos de Europa",
        layer_doc=_limites(),
        layer=LAYER_LIMITES,
        source_url=OAPN_WFS,
    )
    assert a == b


def test_no_network_and_no_layer_violations():
    tree = ast.parse(inspect.getsource(geometry_mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
    assert not imported & {"urllib", "http", "socket", "requests", "httpx"}
    src = inspect.getsource(geometry_mod)
    for layer in ("providers.discovery", "providers.fetch",
                  "providers.parse", "providers.version"):
        assert layer not in src


def test_no_jurisdiction_branching():
    src = inspect.getsource(geometry_mod)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
