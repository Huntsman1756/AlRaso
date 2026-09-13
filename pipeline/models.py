"""M10.1 pilot evidence pipeline — data contracts (value objects only).

Contracts fixed by spec M10 (§C.1, §C.4, §E) and the approved M10.1 plan (§7).
All models are frozen dataclasses with deterministic ``to_dict()`` output:
enums serialize to stable strings, dates are ISO-8601 strings, and no
non-serializable Python objects may appear.

Frozen temporal axes (spec §E — there is NO third axis):

- VALID time:       ``effective_from`` / ``effective_to``
- SYSTEM time:      ``recorded_at`` / ``recorded_until``
- PUBLICATION meta: ``publication_date`` / ``published_on``

``knowledge_from`` / ``knowledge_to`` are forbidden everywhere.

Incomplete evidence is never filled in: unknown values stay ``None`` /
``UNKNOWN`` / ``REQUIRES_MANUAL_REVIEW`` — the pipeline produces evidence for
human review, not legal rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any

FORBIDDEN_TEMPORAL_FIELDS = frozenset({"knowledge_from", "knowledge_to"})


class ReachabilityObserved(str, Enum):
    """Did the server answer? Independent dimension from ``FetchOutcome``.

    Any HTTP response (including 4xx/5xx) is REACHABLE. UNKNOWN means no
    attempt was actually issued.
    """

    REACHABLE = "REACHABLE"
    BLOCKED = "BLOCKED"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class FetchOutcome(str, Enum):
    """What the issued attempt returned. Orthogonal to reachability."""

    SUCCESS = "SUCCESS"
    HTTP_ERROR = "HTTP_ERROR"
    SOFT_404 = "SOFT_404"
    CONTENT_MARKER_MISMATCH = "CONTENT_MARKER_MISMATCH"
    TIMEOUT = "TIMEOUT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"


class RunnerNetwork(str, Enum):
    """Network the attempt ran from. Default UNKNOWN: "local" does not say
    whether the runner is inside Spain (plan §7)."""

    FIXTURE = "fixture"
    ES_LOCAL = "es_local"
    FOREIGN_CI = "foreign_ci"
    UNKNOWN = "unknown"


class ScopeEvidenceStatus(str, Enum):
    """Promotion ladder for geometry evidence (spec §P): administrative
    geometry never becomes legal scope by being "official"."""

    CONTEXT_ONLY = "CONTEXT_ONLY"
    OFFICIAL_SCOPE_CANDIDATE = "OFFICIAL_SCOPE_CANDIDATE"
    OFFICIAL_SCOPE_LINK_PROVEN = "OFFICIAL_SCOPE_LINK_PROVEN"


class VersionClaimStatus(str, Enum):
    """Conservative default: REQUIRES_MANUAL_REVIEW unless the resolver has
    structured/preregistered evidence for the claim."""

    RESOLVED = "RESOLVED"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"


class RedistributionPolicy(str, Enum):
    """Provenance convention (spec §F): official geometry/PDFs are digest-only
    unless reuse is verified per source and artifact."""

    FULL_OK = "FULL_OK"
    DIGEST_ONLY = "DIGEST_ONLY"
    METADATA_ONLY = "METADATA_ONLY"


# fetch_outcome values that can only occur when an HTTP response arrived.
_REACHABLE_OUTCOMES = frozenset(
    {
        FetchOutcome.SUCCESS,
        FetchOutcome.HTTP_ERROR,
        FetchOutcome.SOFT_404,
        FetchOutcome.CONTENT_MARKER_MISMATCH,
    }
)

# fetch_outcome values produced without a completed HTTP exchange.
_NO_RESPONSE_OUTCOMES = frozenset(
    {FetchOutcome.TIMEOUT, FetchOutcome.TRANSPORT_ERROR}
)


def _to_json(value: Any) -> Any:
    """Deterministic JSON projection: enums → str, tuples → lists, nested
    dicts emitted with sorted keys, models via their own ``to_dict()``."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, _EvidenceModel):
        return value.to_dict()
    if isinstance(value, (tuple, list)):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json(value[k]) for k in sorted(value)}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(
        f"non-serializable value in M10.1 contract: {type(value).__name__}"
    )


class _EvidenceModel:
    """Shared ``to_dict()`` + strict ``from_dict()`` key checking.

    ``from_dict`` rejects unknown keys; the forbidden third temporal axis is
    called out explicitly so a schema drift cannot silently smuggle
    ``knowledge_from``/``knowledge_to`` back in.
    """

    def to_dict(self) -> dict[str, Any]:
        return {f.name: _to_json(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def _checked_keys(cls, data: dict[str, Any]) -> None:
        allowed = {f.name for f in fields(cls)}
        unknown = set(data) - allowed
        bad = unknown & FORBIDDEN_TEMPORAL_FIELDS
        if bad:
            raise ValueError(
                f"{cls.__name__}: forbidden temporal fields {sorted(bad)} — "
                "no third temporal axis exists (spec §E)"
            )
        if unknown:
            raise ValueError(
                f"{cls.__name__}: unknown keys {sorted(unknown)}"
            )


@dataclass(frozen=True)
class SpaceRecord(_EvidenceModel):
    """One inventoried protected space (one space → N jurisdictions)."""

    space_id: str
    name: str
    figure_type: str
    ccaa: tuple[str, ...]
    source: str
    source_id: str
    observed_at: str
    evidence_sha256: str
    admin_geom_ref: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpaceRecord":
        cls._checked_keys(data)
        return cls(
            space_id=data["space_id"],
            name=data["name"],
            figure_type=data["figure_type"],
            ccaa=tuple(data["ccaa"]),
            source=data["source"],
            source_id=data["source_id"],
            observed_at=data["observed_at"],
            evidence_sha256=data["evidence_sha256"],
            admin_geom_ref=data.get("admin_geom_ref"),
        )


@dataclass(frozen=True)
class GeometryEvidence(_EvidenceModel):
    """Administrative geometry observation (digest + props, not the shape).

    ``scope_evidence_status`` defaults to CONTEXT_ONLY; promotion to
    OFFICIAL_SCOPE_LINK_PROVEN requires human review.
    """

    space_id: str
    provider: str
    layer: str
    retrieved_at: str
    crs: str
    digest_sha256: str
    feature_props: dict[str, Any]
    source_url: str
    redistribution_policy: RedistributionPolicy = RedistributionPolicy.DIGEST_ONLY
    scope_evidence_status: ScopeEvidenceStatus = ScopeEvidenceStatus.CONTEXT_ONLY

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeometryEvidence":
        cls._checked_keys(data)
        return cls(
            space_id=data["space_id"],
            provider=data["provider"],
            layer=data["layer"],
            retrieved_at=data["retrieved_at"],
            crs=data["crs"],
            digest_sha256=data["digest_sha256"],
            feature_props=dict(data["feature_props"]),
            source_url=data["source_url"],
            redistribution_policy=RedistributionPolicy(
                data.get("redistribution_policy", RedistributionPolicy.DIGEST_ONLY)
            ),
            scope_evidence_status=ScopeEvidenceStatus(
                data.get(
                    "scope_evidence_status", ScopeEvidenceStatus.CONTEXT_ONLY
                )
            ),
        )


@dataclass(frozen=True)
class DocumentRef(_EvidenceModel):
    """A discovered normative document reference (pre-fetch)."""

    source_id: str
    doc_id: str
    published_on: str
    title: str
    issuer: str
    discovery_url: str
    rank: int | None = None
    reachability_class: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentRef":
        cls._checked_keys(data)
        return cls(
            source_id=data["source_id"],
            doc_id=data["doc_id"],
            published_on=data["published_on"],
            title=data["title"],
            issuer=data["issuer"],
            discovery_url=data["discovery_url"],
            rank=data.get("rank"),
            reachability_class=data.get("reachability_class"),
        )


@dataclass(frozen=True)
class DocumentEvidence(_EvidenceModel):
    """Execution truth of one fetch attempt (spec §C.4 + plan §7).

    ``reachability_observed`` and ``fetch_outcome`` are distinct dimensions:
    an HTTP 404 records REACHABLE + HTTP_ERROR; a timeout records
    UNREACHABLE + TIMEOUT. ``UNKNOWN`` reachability means no attempt was
    issued — in that case ``fetch_outcome`` must be ``None``.
    """

    doc_ref: DocumentRef
    method_recipe_id: str
    fetched_at: str
    fetched_from: str
    http_status: int | None
    content_marker_ok: bool
    bytes_sha256: str
    content_type: str | None
    fetch_outcome: FetchOutcome | None
    observed_at: str
    evidence_sha256: str
    runner_network: RunnerNetwork = RunnerNetwork.UNKNOWN
    reachability_observed: ReachabilityObserved = ReachabilityObserved.UNKNOWN

    def __post_init__(self) -> None:
        if self.http_status is not None and (
            self.reachability_observed is not ReachabilityObserved.REACHABLE
        ):
            raise ValueError(
                "a received http_status implies "
                "reachability_observed=REACHABLE"
            )
        if self.fetch_outcome in _REACHABLE_OUTCOMES and (
            self.reachability_observed is not ReachabilityObserved.REACHABLE
        ):
            raise ValueError(
                f"fetch_outcome={self.fetch_outcome} requires "
                "reachability_observed=REACHABLE"
            )
        if self.fetch_outcome in _NO_RESPONSE_OUTCOMES and (
            self.reachability_observed
            not in (ReachabilityObserved.UNREACHABLE, ReachabilityObserved.BLOCKED)
        ):
            raise ValueError(
                f"fetch_outcome={self.fetch_outcome} implies no response: "
                "reachability_observed must be UNREACHABLE or BLOCKED"
            )
        if self.reachability_observed is ReachabilityObserved.UNKNOWN and (
            self.fetch_outcome is not None
        ):
            raise ValueError(
                "reachability_observed=UNKNOWN means no attempt was issued: "
                "fetch_outcome must be None"
            )
        if (
            self.reachability_observed is not ReachabilityObserved.UNKNOWN
            and self.fetch_outcome is None
        ):
            raise ValueError(
                "an issued attempt must record a fetch_outcome"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentEvidence":
        cls._checked_keys(data)
        doc_ref = data["doc_ref"]
        return cls(
            doc_ref=(
                doc_ref
                if isinstance(doc_ref, DocumentRef)
                else DocumentRef.from_dict(doc_ref)
            ),
            method_recipe_id=data["method_recipe_id"],
            fetched_at=data["fetched_at"],
            fetched_from=data["fetched_from"],
            http_status=data.get("http_status"),
            content_marker_ok=bool(data["content_marker_ok"]),
            bytes_sha256=data["bytes_sha256"],
            content_type=data.get("content_type"),
            fetch_outcome=(
                None
                if data.get("fetch_outcome") is None
                else FetchOutcome(data["fetch_outcome"])
            ),
            observed_at=data["observed_at"],
            evidence_sha256=data["evidence_sha256"],
            runner_network=RunnerNetwork(
                data.get("runner_network", RunnerNetwork.UNKNOWN)
            ),
            reachability_observed=ReachabilityObserved(
                data.get("reachability_observed", ReachabilityObserved.UNKNOWN)
            ),
        )


@dataclass(frozen=True)
class ParsedInstrument(_EvidenceModel):
    """Parser output: metadata + structure extracted from fetched bytes.

    ``articles`` items are parser-defined records (shape is fixed per format
    recipe in Tasks 5+); ``citations`` are gazette/instrument cite strings.
    """

    doc_id: str
    format: str
    annexes_present: bool
    extracted_at: str
    parser_version: str
    articles: tuple[dict[str, Any], ...] = ()
    citations: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedInstrument":
        cls._checked_keys(data)
        return cls(
            doc_id=data["doc_id"],
            format=data["format"],
            annexes_present=bool(data["annexes_present"]),
            extracted_at=data["extracted_at"],
            parser_version=data["parser_version"],
            articles=tuple(dict(a) for a in data.get("articles", ())),
            citations=tuple(data.get("citations", ())),
        )


@dataclass(frozen=True)
class VersionClaim(_EvidenceModel):
    """Conservative version claim (spec §E + plan §7 fix 4).

    ``effective_from`` is only populated from structured or exactly
    preregistered effective-date evidence with provenance; free-text or
    ambiguous vacatio yields ``None`` + ``REQUIRES_MANUAL_REVIEW``.
    """

    doc_id: str
    recorded_at: str
    consolidated_state: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    publication_date: str | None = None
    supersession: tuple[str, ...] = ()
    resolver_evidence: dict[str, Any] = field(default_factory=dict)
    recorded_until: str | None = None
    status: VersionClaimStatus = VersionClaimStatus.REQUIRES_MANUAL_REVIEW

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionClaim":
        cls._checked_keys(data)
        return cls(
            doc_id=data["doc_id"],
            recorded_at=data["recorded_at"],
            consolidated_state=data.get("consolidated_state"),
            effective_from=data.get("effective_from"),
            effective_to=data.get("effective_to"),
            publication_date=data.get("publication_date"),
            supersession=tuple(data.get("supersession", ())),
            resolver_evidence=dict(data.get("resolver_evidence", {})),
            recorded_until=data.get("recorded_until"),
            status=VersionClaimStatus(
                data.get("status", VersionClaimStatus.REQUIRES_MANUAL_REVIEW)
            ),
        )


@dataclass(frozen=True)
class ReviewPacket(_EvidenceModel):
    """Human-review artifact prepared by the ReviewGate.

    NEVER publishes: ``publication_readiness`` is hardcoded ``"NO"`` and is
    not a constructor parameter. ``PERMITTED`` is never inferred from
    missing coverage.
    """

    space_id: str
    chain_evidence: tuple[dict[str, Any], ...] = ()
    proposed_rule_artifacts: tuple[dict[str, Any], ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    last_verified: str | None = None
    diffs: tuple[dict[str, Any], ...] = ()
    publication_readiness: str = field(default="NO", init=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewPacket":
        cls._checked_keys(data)
        if data.get("publication_readiness", "NO") != "NO":
            raise ValueError(
                "ReviewPacket.publication_readiness is hardcoded NO — "
                "the packet never publishes"
            )
        return cls(
            space_id=data["space_id"],
            chain_evidence=tuple(
                dict(link) for link in data.get("chain_evidence", ())
            ),
            proposed_rule_artifacts=tuple(
                dict(a) for a in data.get("proposed_rule_artifacts", ())
            ),
            provenance=dict(data.get("provenance", {})),
            last_verified=data.get("last_verified"),
            diffs=tuple(dict(d) for d in data.get("diffs", ())),
        )
