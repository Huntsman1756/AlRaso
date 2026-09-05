"""Core domain vocabulary and value objects (stdlib only, JSON-serializable).

This module is the only place legal semantics are named. Dates are ISO strings
(YYYY-MM-DD) so comparisons are lexicographically correct and storage stays
portable across SQLite/PostgreSQL. Fail-closed is encoded at every boundary:
an unrecognised activity/scope/fact never becomes PERMITTED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Activity(str, Enum):
    """Closed modality vocabulary (F2.1A: a single closed Text, not booleans).

    The resolver accepts any string but only these values are actionable; an
    unknown modality fails closed to UNDETERMINED (never PERMITTED).
    """

    VIVAC_AL_RASO = "VIVAC_AL_RASO"
    FUNDA_VIVAC = "FUNDA_VIVAC"
    TIENDA_NOCTURNA = "TIENDA_NOCTURNA"
    TARP = "TARP"
    ACAMPADA = "ACAMPADA"
    PERNOCTA_REFUGIO = "PERNOCTA_REFUGIO"
    VEHICULO = "VEHICULO"

    @classmethod
    def parse(cls, value: str) -> "Activity | None":
        try:
            return cls(value)
        except ValueError:
            return None


class Effect(str, Enum):
    """Effect a LegalRuleVersion asserts for an activity within a scope."""

    PERMITTED = "PERMITTED"
    PROHIBITED = "PROHIBITED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"


class LegalStatus(str, Enum):
    """Public outcome axis: what the law allows for this activity+scope+date."""

    PERMITTED = "PERMITTED"
    PROHIBITED = "PROHIBITED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    UNDETERMINED = "UNDETERMINED"
    CONFLICT = "CONFLICT"


class KnowledgeStatus(str, Enum):
    """Epistemic axis: how complete/trustworthy our knowledge is at query time.

    CONFLICTING (M1 remediation F04): incompatible normative effects remain
    unresolved after precedence; the legal axis then reports UNDETERMINED.
    """

    CURRENT = "CURRENT"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"


class ReviewStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    EXTRACTED = "EXTRACTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LEGAL_REVIEWED = "LEGAL_REVIEWED"
    SPATIAL_REVIEWED = "SPATIAL_REVIEWED"
    VERIFIED = "VERIFIED"
    PUBLISHED = "PUBLISHED"

    @classmethod
    def default(cls) -> "ReviewStatus":
        return cls.REVIEW_REQUIRED


class ScopeType(str, Enum):
    NATIONAL_PARK = "NATIONAL_PARK"
    PARK_SECTOR = "PARK_SECTOR"
    ZONA_SERVICIOS = "ZONA_SERVICIOS"
    ZPP = "ZPP"
    AREA_ESPECIAL_PROTECCION = "AREA_ESPECIAL_PROTECCION"
    OTHER = "OTHER"

    @classmethod
    def parse(cls, value: str) -> "ScopeType":
        try:
            return cls(value)
        except ValueError:
            return cls.OTHER


class EngineMode(str, Enum):
    FAST = "fast"
    EXPLAIN = "explain"


class FactKind(str, Enum):
    BOOL = "bool"
    TEXT = "text"
    DECIMAL = "decimal"
    INTEGER = "integer"


@dataclass(frozen=True)
class Fact:
    """A caller-supplied observation about a place during a period.

    Mirrors the engine's InputRecord shape (durable name, typed value) so the
    same facts feed both the own evaluator and the Axiom adapter.
    """

    name: str
    kind: FactKind
    value: Any

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind.value, "value": self.value}


@dataclass(frozen=True)
class Query:
    """A resolution request.

    Provide either ``spatial_scope_id`` (scope already resolved) or ``lat``/
    ``lon`` (a SpatialFactsProvider resolves the scope list). Dates are ISO.
    """

    activity: str
    activity_date: str
    knowledge_date: str
    spatial_scope_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    facts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "activity": self.activity,
            "activity_date": self.activity_date,
            "knowledge_date": self.knowledge_date,
            "spatial_scope_id": self.spatial_scope_id,
            "lat": self.lat,
            "lon": self.lon,
            "facts": dict(self.facts),
        }


@dataclass
class ResolveResult:
    """The full resolver contract (discovery §L)."""

    legal_status: LegalStatus
    knowledge_status: KnowledgeStatus
    query: dict[str, Any]
    applicable_scope: list[dict[str, Any]] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    rule_versions: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    precedence_trace: list[dict[str, Any]] = field(default_factory=list)
    unresolved_conflicts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    decision_reason: str = ""
    # canonical material basis used for replay drift (F05): scope/rule/relation/
    # evidence ids that actually backed the conclusion.
    basis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legalStatus": self.legal_status.value,
            "knowledgeStatus": self.knowledge_status.value,
            "query": self.query,
            "applicableScope": self.applicable_scope,
            "conditions": self.conditions,
            "ruleVersions": self.rule_versions,
            "evidence": self.evidence,
            "precedenceTrace": self.precedence_trace,
            "unresolvedConflicts": self.unresolved_conflicts,
            "warnings": self.warnings,
            "reasonCodes": self.reason_codes,
            "decisionReason": self.decision_reason,
            "basis": self.basis,
        }
