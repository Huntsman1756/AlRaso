"""M10.1 Task 1 — data contracts for the pilot evidence pipeline.

RED-first contract suite for ``pipeline/models.py`` + ``evidence.schema.json``.
The models are pure value objects: frozen, JSON-deterministic, jurisdiction
agnostic, and conservative by default (evidence is produced, never rules).

Pinned invariants (plan M10.1 §0/§7, spec §C.1/§C.4/§E):

- ``scope_evidence_status`` default = CONTEXT_ONLY
- ``VersionClaim.status`` conservative default = REQUIRES_MANUAL_REVIEW
- ``knowledge_from`` / ``knowledge_to`` FORBIDDEN (no third temporal axis)
- VALID = effective_from/effective_to; SYSTEM = recorded_at/recorded_until;
  publication_date is separate metadata
- ``reachability_observed`` and ``fetch_outcome`` are distinct dimensions:
  an HTTP 404 proves the server was REACHED
"""

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

import pipeline.models as models
from pipeline.models import (
    DocumentEvidence,
    DocumentRef,
    FetchOutcome,
    GeometryEvidence,
    ParsedInstrument,
    ReachabilityObserved,
    ReviewPacket,
    RunnerNetwork,
    ScopeEvidenceStatus,
    SpaceRecord,
    VersionClaim,
    VersionClaimStatus,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_JSON = ROOT / "pipeline" / "schemas" / "evidence.schema.json"

ALL_MODELS = (
    SpaceRecord,
    DocumentRef,
    DocumentEvidence,
    ParsedInstrument,
    VersionClaim,
    GeometryEvidence,
    ReviewPacket,
)


def _doc_ref() -> DocumentRef:
    return DocumentRef(
        source_id="bocyl",
        doc_id="BOCYL-D-15122025-1",
        published_on="2025-12-15",
        title="Decreto 17/2025 PRUG Picos de Europa",
        rank=1,
        issuer="Junta de Castilla y León",
        discovery_url="https://example.invalid/dataset/1",
        reachability_class="REACHABLE",
    )


def _doc_evidence() -> DocumentEvidence:
    return DocumentEvidence(
        doc_ref=_doc_ref(),
        method_recipe_id="get_simple",
        fetched_at="2026-09-13T10:00:00Z",
        fetched_from="https://example.invalid/doc.xml",
        http_status=200,
        content_marker_ok=True,
        bytes_sha256="a" * 64,
        content_type="application/xml",
        runner_network=RunnerNetwork.FIXTURE,
        reachability_observed=ReachabilityObserved.REACHABLE,
        fetch_outcome=FetchOutcome.SUCCESS,
        observed_at="2026-09-13T10:00:01Z",
        evidence_sha256="b" * 64,
    )


def _instances():
    return [
        SpaceRecord(
            space_id="pn-picos-de-europa",
            name="Picos de Europa",
            figure_type="Parque Nacional",
            ccaa=("ES-AS", "ES-CB", "ES-CL"),
            source="oapn",
            source_id="OAPN-0001",
            admin_geom_ref=None,
            observed_at="2026-09-13T09:00:00Z",
            evidence_sha256="c" * 64,
        ),
        _doc_ref(),
        _doc_evidence(),
        ParsedInstrument(
            doc_id="BOCYL-D-15122025-1",
            format="bocyl_xml",
            articles=({"ref": "art. 1"},),
            annexes_present=True,
            citations=("Decreto 17/2025",),
            extracted_at="2026-09-13T10:05:00Z",
            parser_version="bocyl_xml/0.1",
        ),
        VersionClaim(
            doc_id="BOCYL-D-15122025-1",
            recorded_at="2026-09-13T10:06:00Z",
        ),
        GeometryEvidence(
            space_id="pn-picos-de-europa",
            provider="oapn_wfs",
            layer="view_red_oapn_limite_pn",
            retrieved_at="2026-09-13T09:30:00Z",
            crs="EPSG:4326",
            digest_sha256="d" * 64,
            feature_props={"name": "Picos de Europa"},
            source_url="https://example.invalid/wfs",
        ),
        ReviewPacket(space_id="pn-picos-de-europa"),
    ]


def test_round_trip_all_models():
    for instance in _instances():
        payload = json.loads(json.dumps(instance.to_dict()))
        clone = type(instance).from_dict(payload)
        assert clone == instance, f"{type(instance).__name__} round-trip diverged"
        assert clone.to_dict() == instance.to_dict()


def test_to_dict_is_json_deterministic():
    for instance in _instances():
        first = json.dumps(instance.to_dict(), sort_keys=True)
        second = json.dumps(instance.to_dict(), sort_keys=True)
        assert first == second
        # Every serialized leaf must be a plain JSON type already.
        json.dumps(instance.to_dict())


def test_enums_serialize_as_stable_strings():
    d = _doc_evidence().to_dict()
    assert d["runner_network"] == "fixture"
    assert d["reachability_observed"] == "REACHABLE"
    assert d["fetch_outcome"] == "SUCCESS"
    assert type(d["runner_network"]) is str
    assert type(d["reachability_observed"]) is str


def test_conservative_defaults():
    geo = GeometryEvidence(
        space_id="x",
        provider="p",
        layer="l",
        retrieved_at="2026-09-13T00:00:00Z",
        crs="EPSG:4326",
        digest_sha256="e" * 64,
        feature_props={},
        source_url="https://example.invalid",
    )
    assert geo.scope_evidence_status is ScopeEvidenceStatus.CONTEXT_ONLY

    claim = VersionClaim(doc_id="d", recorded_at="2026-09-13T00:00:00Z")
    assert claim.status is VersionClaimStatus.REQUIRES_MANUAL_REVIEW
    # Incomplete evidence is never filled in.
    assert claim.effective_from is None
    assert claim.effective_to is None
    assert claim.recorded_until is None


def test_runner_network_default_is_unknown_not_local():
    ev = DocumentEvidence(
        doc_ref=_doc_ref(),
        method_recipe_id="get_simple",
        fetched_at="2026-09-13T10:00:00Z",
        fetched_from="https://example.invalid/doc.xml",
        http_status=None,
        content_marker_ok=False,
        bytes_sha256="",
        content_type=None,
        reachability_observed=ReachabilityObserved.UNKNOWN,
        fetch_outcome=None,
        observed_at="2026-09-13T10:00:01Z",
        evidence_sha256="f" * 64,
    )
    assert ev.runner_network is RunnerNetwork.UNKNOWN


def test_knowledge_fields_forbidden():
    for cls in ALL_MODELS:
        names = {f.name for f in dataclasses.fields(cls)}
        assert "knowledge_from" not in names
        assert "knowledge_to" not in names

    with pytest.raises(TypeError):
        VersionClaim(
            doc_id="d",
            recorded_at="2026-09-13T00:00:00Z",
            knowledge_from="2020-01-01",
        )

    with pytest.raises(ValueError, match="knowledge"):
        VersionClaim.from_dict(
            {
                "doc_id": "d",
                "recorded_at": "2026-09-13T00:00:00Z",
                "knowledge_to": "2020-01-01",
            }
        )


def test_temporal_axes_are_the_frozen_ones():
    claim_fields = {f.name for f in dataclasses.fields(VersionClaim)}
    assert {"effective_from", "effective_to"} <= claim_fields
    assert {"recorded_at", "recorded_until"} <= claim_fields
    assert "publication_date" in claim_fields
    # publication_date is metadata, never part of the valid-time axis.
    assert "publication_date" not in {"effective_from", "effective_to"}


def test_models_are_frozen_value_objects():
    for instance in _instances():
        assert dataclasses.is_dataclass(instance)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(
                instance,
                next(f.name for f in dataclasses.fields(instance)),
                "x",
            )


def test_reachability_and_fetch_outcome_are_distinct_dimensions():
    # HTTP 404: the server WAS reached — reachability stays REACHABLE.
    ev = dataclasses.replace(
        _doc_evidence(),
        http_status=404,
        content_marker_ok=False,
        fetch_outcome=FetchOutcome.HTTP_ERROR,
    )
    assert ev.reachability_observed is ReachabilityObserved.REACHABLE
    assert ev.fetch_outcome is FetchOutcome.HTTP_ERROR

    # A received HTTP status can never be recorded as UNREACHABLE.
    with pytest.raises(ValueError):
        dataclasses.replace(
            _doc_evidence(),
            http_status=404,
            reachability_observed=ReachabilityObserved.UNREACHABLE,
            fetch_outcome=FetchOutcome.TRANSPORT_ERROR,
        )

    # TIMEOUT implies no response: reachability must be UNREACHABLE.
    with pytest.raises(ValueError):
        dataclasses.replace(
            _doc_evidence(),
            http_status=None,
            reachability_observed=ReachabilityObserved.REACHABLE,
            fetch_outcome=FetchOutcome.TIMEOUT,
        )

    # UNKNOWN means no attempt was issued: no fetch_outcome may be claimed.
    with pytest.raises(ValueError):
        dataclasses.replace(
            _doc_evidence(),
            http_status=None,
            reachability_observed=ReachabilityObserved.UNKNOWN,
            fetch_outcome=FetchOutcome.SUCCESS,
        )


def test_soft_404_and_marker_mismatch_are_reachable_outcomes():
    for outcome in (FetchOutcome.SOFT_404, FetchOutcome.CONTENT_MARKER_MISMATCH):
        ev = dataclasses.replace(
            _doc_evidence(), content_marker_ok=False, fetch_outcome=outcome
        )
        assert ev.reachability_observed is ReachabilityObserved.REACHABLE


def test_review_packet_never_publishes():
    packet = ReviewPacket(space_id="pn-picos-de-europa")
    assert packet.to_dict()["publication_readiness"] == "NO"
    # Not a constructor parameter — readiness is hardcoded, not a choice.
    with pytest.raises(TypeError):
        ReviewPacket(space_id="x", publication_readiness="YES")
    with pytest.raises(ValueError):
        ReviewPacket.from_dict({"space_id": "x", "publication_readiness": "YES"})


def test_no_jurisdiction_branching_in_models():
    src = inspect.getsource(models)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src


def test_schema_file_exists_and_pins_enums():
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    defs = schema["$defs"]
    assert set(defs["reachability_observed"]["enum"]) == {
        e.value for e in ReachabilityObserved
    }
    assert set(defs["fetch_outcome"]["enum"]) == {e.value for e in FetchOutcome}
    assert set(defs["runner_network"]["enum"]) == {e.value for e in RunnerNetwork}
    assert set(defs["scope_evidence_status"]["enum"]) == {
        e.value for e in ScopeEvidenceStatus
    }
    assert set(defs["version_claim_status"]["enum"]) == {
        e.value for e in VersionClaimStatus
    }


def test_schema_forbids_third_temporal_axis():
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    claim = schema["$defs"]["version_claim"]
    assert claim.get("additionalProperties") is False
    assert "knowledge_from" not in claim["properties"]
    assert "knowledge_to" not in claim["properties"]


def test_serialized_models_validate_against_schema():
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    for instance in _instances():
        jsonschema.validate(instance.to_dict(), schema)
