"""M8-E — GeoJsonLayerProvider over official IDEM layers + boundary gate e2e.

Layers are hash-pinned official downloads under discovery/evidence/m8-guadarrama/.
Reference points were derived from the real geometries (verified against
alraso.spatial._part_locate):

- ZABALA_PT   inside the Anexo III "Zabala" vivac polygon AND the PN-CM scope
- ZPP_PT      inside the ZPP scope, outside every hole, outside the PN
- ZPP_HOLE_PT centroid of a ZPP interior ring (excluded municipality): no scope
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.geojson_provider import GeoJsonLayer, load_geojson_provider
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider, SpatialFactsError

from conftest import new_store, rule, scope

EV = Path(__file__).resolve().parent.parent / "discovery" / "evidence" / "m8-guadarrama"

VIVAC = EV / "IDEM_MA_PNSG_ZON_VIVAC_ANUA.geojson"
VIVAC_SHA = "b6fa71b24927a5a44229e0363773c67e309a773c9e20649fa5d710f9f63958b6"
PNCM = EV / "IDEM_MA_PN_GUADARRAMA_CM.geojson"
PNCM_SHA = "d64025a17861c33dc9a84bed082c8cbb75b4446ad5c44bcb686646436ccfb833"
MANZ = EV / "IDEM_MA_PR_CA_MANZANARES.geojson"
MANZ_SHA = "560b349880eeb96a20b6f85583006dc9995a138424b1036bf48c379c44da1c63"
PRG = EV / "IDEM_MA_PR_GUADARRAMA.geojson"
PRG_SHA = "d05c249f28325f26c074ac8b0eb142d26e4fc712f36ef97db0a305b202bedced"

ZABALA_PT = (40.837697, -3.958714)
ZPP_PT = (40.842235, -3.880597)
ZPP_HOLE_PT = (40.914796, -3.854548)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- spec validation ---------------------------------------------------------


def test_spec_requires_an_emission_mode():
    with pytest.raises(SpatialFactsError):
        GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR")


def test_spec_rejects_bad_unmapped_and_bad_sha():
    with pytest.raises(SpatialFactsError):
        GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR", scope_property="p",
                     scope_map={"a": "b"}, unmapped="maybe", official_name="n")
    with pytest.raises(SpatialFactsError):
        GeoJsonLayer(VIVAC, "nothex" * 8, "PARK_SECTOR",
                     scope_id="s", official_name="n")


def test_property_emission_requires_map_and_names():
    with pytest.raises(SpatialFactsError):
        GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR",
                     scope_property="p", official_name="n")
    with pytest.raises(SpatialFactsError):
        GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR",
                     scope_property="p", scope_map={"a": "b"})


# --- integrity / malformed input --------------------------------------------


def test_hash_mismatch_fails_closed():
    spec = GeoJsonLayer(VIVAC, "0" * 64, "PARK_SECTOR",
                        scope_id="s-x", official_name="n")
    with pytest.raises(SpatialFactsError, match="sha256"):
        load_geojson_provider([spec])


def test_malformed_geojson_fails_closed(tmp_path):
    bad = tmp_path / "bad.geojson"
    bad.write_bytes(b"{not json")
    spec = GeoJsonLayer(bad, _sha(bad), "PARK_SECTOR",
                        scope_id="s", official_name="n")
    with pytest.raises(SpatialFactsError, match="invalid JSON"):
        load_geojson_provider([spec])


def test_non_feature_collection_fails_closed(tmp_path):
    bad = tmp_path / "bad.geojson"
    bad.write_text(json.dumps({"type": "Feature", "geometry": None,
                               "properties": {}}))
    spec = GeoJsonLayer(bad, _sha(bad), "PARK_SECTOR",
                        scope_id="s", official_name="n")
    with pytest.raises(SpatialFactsError, match="FeatureCollection"):
        load_geojson_provider([spec])


def test_missing_geometry_fails_closed(tmp_path):
    bad = tmp_path / "bad.geojson"
    bad.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": None, "properties": {}}],
    }))
    spec = GeoJsonLayer(bad, _sha(bad), "PARK_SECTOR",
                        scope_id="s", official_name="n")
    with pytest.raises(SpatialFactsError, match="no geometry"):
        load_geojson_provider([spec])


# --- emission modes on the real layers --------------------------------------


def test_constant_emission_loads_all_vivac_zones():
    spec = GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR",
                        scope_id="ss-pnsg-vivac-anexo3",
                        official_name="Zonas de vivac Anexo III")
    prov = load_geojson_provider([spec])
    hits = prov.resolve(*ZABALA_PT)
    assert [h.scope_id for h in hits] == ["ss-pnsg-vivac-anexo3"]
    assert hits[0].on_boundary is False
    # five Anexo III polygons unioned under one scope
    assert len(prov._scopes["ss-pnsg-vivac-anexo3"]["parts"]) == 5


def test_property_emission_maps_scopes_and_official_names():
    spec = GeoJsonLayer(PNCM, PNCM_SHA, "PARK_SECTOR",
                        scope_property="CD_ZONA",
                        scope_map={"PN": "ss-pnsg-pn-cm", "ZPP": "ss-pnsg-zpp-cm"},
                        official_name="PN Guadarrama (lado CM)",
                        name_property="DS_ZONA")
    prov = load_geojson_provider([spec])
    assert {h.scope_id for h in prov.resolve(*ZPP_PT)} == {"ss-pnsg-zpp-cm"}
    assert {h.scope_id for h in prov.resolve(*ZABALA_PT)} == {"ss-pnsg-pn-cm"}
    assert prov._scopes["ss-pnsg-zpp-cm"]["official_name"].startswith(
        "Zona Periférica de Protección")


def test_zpp_holes_are_not_scope_interior():
    """P0 regression: the 7 interior rings of the ZPP multipolygon are excluded
    municipalities — a point in a hole is NOT inside the scope."""
    spec = GeoJsonLayer(PNCM, PNCM_SHA, "PARK_SECTOR",
                        scope_property="CD_ZONA",
                        scope_map={"PN": "ss-pnsg-pn-cm", "ZPP": "ss-pnsg-zpp-cm"},
                        official_name="PN Guadarrama (lado CM)")
    prov = load_geojson_provider([spec])
    assert prov.resolve(*ZPP_HOLE_PT) == []


def test_unmapped_property_error_vs_skip():
    base = dict(scope_property="CD_TIPO_ZONA", official_name="Manzanares",
                scope_map={"A1": "s-res", "A2": "s-res"})
    with pytest.raises(SpatialFactsError, match="unmapped"):
        load_geojson_provider(
            [GeoJsonLayer(MANZ, MANZ_SHA, "PARK_SECTOR", **base)])
    prov = load_geojson_provider(
        [GeoJsonLayer(MANZ, MANZ_SHA, "PARK_SECTOR",
                      unmapped="skip", **base)])
    assert set(prov._scopes) == {"s-res"}


def test_union_emission_merges_feature_parts():
    spec = GeoJsonLayer(PRG, PRG_SHA, "REGIONAL_PARK",
                        scope_id="ss-prcmg-parque",
                        official_name="PR Curso Medio del Guadarrama")
    prov = load_geojson_provider([spec])
    # 3 features, each a MultiPolygon — all parts union under one scope
    assert len(prov._scopes["ss-prcmg-parque"]["parts"]) == 75


def test_conflicting_scope_metadata_fails_closed():
    a = GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR",
                     scope_id="s-x", official_name="a")
    b = GeoJsonLayer(VIVAC, VIVAC_SHA, "REGIONAL_PARK",
                     scope_id="s-x", official_name="a")
    with pytest.raises(SpatialFactsError, match="conflicting metadata"):
        load_geojson_provider([a, b])


# --- resolver e2e over the real Guadarrama geometry --------------------------


def _guadarrama_resolver() -> Resolver:
    prov = load_geojson_provider([
        GeoJsonLayer(VIVAC, VIVAC_SHA, "PARK_SECTOR",
                     scope_id="ss-pnsg-vivac-anexo3",
                     official_name="Zonas de vivac Anexo III"),
        GeoJsonLayer(PNCM, PNCM_SHA, "PARK_SECTOR",
                     scope_property="CD_ZONA",
                     scope_map={"PN": "ss-pnsg-pn-cm", "ZPP": "ss-pnsg-zpp-cm"},
                     official_name="PN Guadarrama (lado CM)",
                     name_property="DS_ZONA"),
    ])
    s = new_store()
    for sid, stype in (("ss-pnsg-vivac-anexo3", "PARK_SECTOR"),
                       ("ss-pnsg-pn-cm", "NATIONAL_PARK"),
                       ("ss-pnsg-zpp-cm", "PARK_SECTOR")):
        scope(s, sid, scope_type=stype, review_status="VERIFIED",
              geometry="IDEM_MA_PNSG_ZON_VIVAC_ANUA@" + VIVAC_SHA[:12])
    rule(s, "alraso:es-md:vivac/anexo3#p", "ss-pnsg-vivac-anexo3", "PERMITTED",
         evidence=("lf-anexo3",))
    rule(s, "alraso:es-md:vivac/pn#p", "ss-pnsg-pn-cm", "PERMITTED",
         evidence=("lf-pn",))
    rule(s, "alraso:es-md:vivac/zpp#p", "ss-pnsg-zpp-cm", "PROHIBITED",
         evidence=("lf-zpp",))
    return Resolver(s, spatial=prov)


def _q(lat: float, lon: float) -> Query:
    return Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                 knowledge_date="2023-06-15", lat=lat, lon=lon)


def test_e2e_point_inside_vivac_zone_permitted():
    res = _guadarrama_resolver().resolve(_q(*ZABALA_PT))
    assert res.legal_status is LegalStatus.PERMITTED
    assert {h["scope_id"] for h in res.applicable_scope} == {
        "ss-pnsg-vivac-anexo3", "ss-pnsg-pn-cm"}


def test_e2e_point_inside_zpp_prohibited():
    res = _guadarrama_resolver().resolve(_q(*ZPP_PT))
    assert res.legal_status is LegalStatus.PROHIBITED
    assert {h["scope_id"] for h in res.applicable_scope} == {"ss-pnsg-zpp-cm"}


def test_e2e_point_in_zpp_hole_no_scope():
    res = _guadarrama_resolver().resolve(_q(*ZPP_HOLE_PT))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.reason_codes == ["NO_APPLICABLE_SCOPE"]


# --- boundary ambiguity gate -------------------------------------------------


def test_boundary_hit_on_regulatory_scope_fails_closed():
    s = new_store()
    scope(s, "s-x", review_status="VERIFIED", geometry="src")
    rule(s, "alraso:es:t/p#b", "s-x", "PERMITTED")
    prov = InMemorySpatialProvider()
    prov.add_scope("s-x", "s-x", "PARK_SECTOR",
                   [[(42.0, 0.0), (42.0, 0.1), (42.1, 0.1), (42.1, 0.0)]])
    res = Resolver(s, spatial=prov).resolve(_q(42.0, 0.05))  # exactly on edge
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert res.knowledge_status is KnowledgeStatus.INCOMPLETE
    assert res.reason_codes == ["BOUNDARY_AMBIGUOUS"]
    assert res.applicable_scope[0]["on_boundary"] is True


def test_boundary_hit_on_context_only_scope_is_warning_not_failure():
    s = new_store()
    scope(s, "s-reg", review_status="VERIFIED", geometry="src")
    scope(s, "s-ctx", relevance="CONTEXT_ONLY")
    rule(s, "alraso:es:t/p#c", "s-reg", "PERMITTED")
    prov = InMemorySpatialProvider()
    # point (42.05, 0.05): inside s-reg, exactly on the edge of s-ctx
    prov.add_scope("s-reg", "s-reg", "PARK_SECTOR",
                   [[(42.0, 0.0), (42.0, 0.2), (42.2, 0.2), (42.2, 0.0)]])
    prov.add_scope("s-ctx", "s-ctx", "PARK_SECTOR",
                   [[(42.05, 0.0), (42.05, 0.1), (42.1, 0.1), (42.1, 0.0)]])
    res = Resolver(s, spatial=prov).resolve(_q(42.05, 0.05))
    assert res.legal_status is LegalStatus.PERMITTED
    assert any("CONTEXT_ONLY" in w for w in res.warnings)
    assert {h["scope_id"] for h in res.applicable_scope} == {"s-reg", "s-ctx"}


# --- declarative layer manifest ----------------------------------------------

MANIFEST = EV.parent / "m8-madrid-layers.json"

ALL_MANIFEST_SCOPES = {
    "ss-pnsg-vivac-anexo3", "ss-pnsg-pn-cm", "ss-pnsg-zpp-cm",
    "ss-prcam-parque", "ss-prcam-reserva-natural",
    "ss-prcmg-parque", "ss-prcmg-max-proteccion",
    "ss-prcmg-proteccion-mejora", "ss-prcmg-mantenimiento",
    "ss-prse-parque", "ss-prse-zona-a", "ss-prse-zonas-b-e",
    "ss-prse-zonas-fg",
}


def test_manifest_loads_all_madrid_scopes():
    from alraso.geojson_provider import load_manifest_provider
    prov = load_manifest_provider(MANIFEST)
    assert set(prov._scopes) == ALL_MANIFEST_SCOPES
    # nested emission: a Zabala point hits the vivac zone AND the PN scope
    assert {h.scope_id for h in prov.resolve(*ZABALA_PT)} == {
        "ss-pnsg-vivac-anexo3", "ss-pnsg-pn-cm"}
    assert prov.resolve(*ZPP_HOLE_PT) == []


def test_manifest_rejects_bad_schema(tmp_path):
    from alraso.geojson_provider import load_manifest_provider
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({"schema": "other", "layers": []}))
    with pytest.raises(SpatialFactsError, match="schema"):
        load_manifest_provider(bad)


def test_manifest_rejects_missing_layer_field(tmp_path):
    from alraso.geojson_provider import load_manifest_provider
    bad = tmp_path / "m.json"
    bad.write_text(json.dumps({
        "schema": "alraso-m8-layer-manifest-v1",
        "layers": [{"id": "x", "path": "a.geojson"}],
    }))
    with pytest.raises(SpatialFactsError, match="missing/invalid field"):
        load_manifest_provider(bad)
