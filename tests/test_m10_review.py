"""M10.1 Task 9 — ReviewGate: bundle → ReviewPacket (JSON + markdown).

Boundary: assembles the full evidence chain into a review artifact.
publication_readiness is hardcoded NO; proposed artifacts are stamped
NOT_PUBLISHED; PERMITTED is never inferred. A prior bundle produces
deterministic per-link diffs.
"""

import ast
import hashlib
import inspect
import json

import pytest

import pipeline.review as review_mod
from pipeline.models import (
    DocumentEvidence,
    DocumentRef,
    FetchOutcome,
    GeometryEvidence,
    ParsedInstrument,
    ReachabilityObserved,
    RunnerNetwork,
    SpaceRecord,
    VersionClaim,
)
from pipeline.review import ReviewGateError, prepare_pr

CHAIN_LINKS = (
    "inventory",
    "geometry",
    "authority",
    "discovery",
    "fetch",
    "parse",
    "version",
    "change_detection",
    "publication",
)


def _bundle() -> dict:
    space = SpaceRecord(
        space_id="pn-picos-de-europa",
        name="Parque Nacional de los Picos de Europa",
        figure_type="PN",
        ccaa=("ES-AS", "ES-CB", "ES-CL"),
        source="oapn-red-pn",
        source_id="Parque Nacional de los Picos de Europa",
        observed_at="2026-09-13",
        evidence_sha256="a" * 64,
        admin_geom_ref="Parque Nacional de los Picos de Europa",
    )
    geom = GeometryEvidence(
        space_id="pn-picos-de-europa",
        provider="oapn_wfs",
        layer="LimitesParquesNacionalesZPP:view_red_oapn_limite_pn",
        retrieved_at="2026-09-13",
        crs="EPSG:4326",
        digest_sha256="b" * 64,
        feature_props={"Nombre": "Parque Nacional de los Picos de Europa"},
        source_url="https://sigred.oapn.es/geoserverOAPN/ows",
    )
    ref = DocumentRef(
        source_id="bocyl",
        doc_id="BOCYL-D-15122025-1",
        published_on="2025-12-15",
        title="Decreto 17/2025",
        issuer="Consejería de Medio Ambiente",
        discovery_url="https://example.test/discovery",
        rank=0,
    )
    ev = DocumentEvidence(
        doc_ref=ref,
        method_recipe_id="get_simple",
        fetched_at="2026-09-13T00:00:00Z",
        fetched_from="https://example.test/doc.xml",
        http_status=200,
        content_marker_ok=True,
        bytes_sha256="c" * 64,
        content_type="application/xml",
        fetch_outcome=FetchOutcome.SUCCESS,
        observed_at="2026-09-13T00:00:00Z",
        evidence_sha256="c" * 64,
        runner_network=RunnerNetwork.FIXTURE,
        reachability_observed=ReachabilityObserved.REACHABLE,
    )
    parsed = ParsedInstrument(
        doc_id="BOCYL-D-15122025-1",
        format="bocyl_xml",
        annexes_present=True,
        extracted_at="2026-09-13T00:00:00Z",
        parser_version="bocyl_xml/1",
        articles=({"order": 0, "heading": "Artículo 51"},),
        citations=("Ley 42/2007",),
    )
    claim = VersionClaim(
        doc_id="BOCYL-D-15122025-1",
        recorded_at="2026-09-13T00:00:00Z",
        publication_date="2025-12-15",
    )
    return {
        "space": space,
        "geometry": (geom,),
        "authority": {
            "jurisdiction": "ES-CL",
            "gazette": "bocyl",
            "cite": "Decreto 17/2025",
        },
        "discovery": (ref,),
        "fetch": ev,
        "parse": parsed,
        "version": claim,
        "change_detection": {"method": "dataset_diff", "cadence": "daily"},
    }


def test_complete_bundle_produces_nine_link_packet():
    packet, md = prepare_pr("pn-picos-de-europa", _bundle())
    assert [link["link"] for link in packet.chain_evidence] == list(CHAIN_LINKS)
    assert packet.publication_readiness == "NO"
    assert packet.space_id == "pn-picos-de-europa"
    assert packet.last_verified is not None
    # Every link carries evidence + its sha256 for the provenance chain.
    for link in packet.chain_evidence:
        assert len(link["sha256"]) == 64
        assert link["evidence"] is not None


def test_publication_link_is_no_and_proposed_artifacts_not_published():
    packet, _ = prepare_pr("pn-picos-de-europa", _bundle())
    pub = packet.chain_evidence[-1]
    assert pub["link"] == "publication"
    assert pub["evidence"]["publication_readiness"] == "NO"
    for art in packet.proposed_rule_artifacts:
        assert art["status"] == "NOT_PUBLISHED"


def test_markdown_renders_chain_and_hashes():
    packet, md = prepare_pr("pn-picos-de-europa", _bundle())
    assert "pn-picos-de-europa" in md
    assert "publication_readiness" in md and "NO" in md
    for link in packet.chain_evidence:
        assert link["link"] in md
    assert "REQUIRES_MANUAL_REVIEW" in md  # version claim status visible


def test_missing_link_fails_explicit():
    bundle = _bundle()
    del bundle["parse"]
    with pytest.raises(ReviewGateError, match="parse"):
        prepare_pr("pn-picos-de-europa", bundle)


def test_empty_discovery_still_records_link():
    """A link may legitimately be empty (no hits) — recorded, not skipped."""
    bundle = _bundle()
    bundle["discovery"] = ()
    packet, _ = prepare_pr("pn-picos-de-europa", bundle)
    links = {l["link"]: l for l in packet.chain_evidence}
    assert links["discovery"]["evidence"] == []


def test_diffs_against_prior_bundle():
    packet, _ = prepare_pr("pn-picos-de-europa", _bundle())
    prior = dict(_bundle())
    # Same space but the fetch evidence differs → 'changed'.
    ev = prior["fetch"]
    prior["fetch"] = DocumentEvidence(
        doc_ref=ev.doc_ref,
        method_recipe_id=ev.method_recipe_id,
        fetched_at=ev.fetched_at,
        fetched_from=ev.fetched_from,
        http_status=ev.http_status,
        content_marker_ok=ev.content_marker_ok,
        bytes_sha256="d" * 64,
        content_type=ev.content_type,
        fetch_outcome=ev.fetch_outcome,
        observed_at=ev.observed_at,
        evidence_sha256="d" * 64,
        runner_network=ev.runner_network,
        reachability_observed=ev.reachability_observed,
    )
    packet2, _ = prepare_pr(
        "pn-picos-de-europa", _bundle(), prior_bundle=prior
    )
    diffs = {d["link"]: d["status"] for d in packet2.diffs}
    assert diffs["fetch"] == "changed"
    assert diffs["inventory"] == "same"
    assert set(diffs) == set(CHAIN_LINKS) - {"publication"}


def test_deterministic_output():
    p1, md1 = prepare_pr("pn-picos-de-europa", _bundle())
    p2, md2 = prepare_pr("pn-picos-de-europa", _bundle())
    assert p1.to_dict() == p2.to_dict()
    assert md1 == md2
    json.dumps(p1.to_dict(), sort_keys=True)  # serializable


def test_no_network_no_jurisdiction_branches():
    src = inspect.getsource(review_mod)
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not imported & {
        "providers.discovery", "providers.fetch", "providers.parse",
        "providers.version", "providers.geometry", "providers.inventory",
    }
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
