"""Normalized error taxonomy (M1 remediation F06 / error normalization).

Every expected infrastructure/validation failure carries a machine-readable
reason code. The resolver maps ALL of them to fail-closed outcomes
(UNDETERMINED + reason code); none may escape as an arbitrary traceback and
NONE may ever yield PERMITTED.
"""

from __future__ import annotations

from typing import Any


class AlRasoError(Exception):
    """Base for all normalized errors. Carries a stable reason code."""

    reason_code = "INTERNAL_ERROR"

    def __init__(self, message: str = "", *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.reason_code)
        self.detail = detail or {}


# ---- validation errors (writer-side raise; reader-side fail-closed) ----------
class InvalidDate(AlRasoError):
    reason_code = "INVALID_DATE"


class InvalidFact(AlRasoError):
    reason_code = "INVALID_FACT"


class InvalidCondition(AlRasoError):
    reason_code = "INVALID_CONDITION"


class InvalidRule(AlRasoError):
    reason_code = "INVALID_RULE"


class InvalidRelation(AlRasoError):
    reason_code = "INVALID_RELATION"


class InvalidScope(AlRasoError):
    reason_code = "INVALID_SCOPE"


# ---- spatial ------------------------------------------------------------------
class SpatialResolutionError(AlRasoError):
    reason_code = "SPATIAL_RESOLUTION_ERROR"


# ---- engine errors (subclass the legacy EngineError taxonomy too) -------------
class EngineFailure(AlRasoError):
    reason_code = "ENGINE_FAILURE"


class EngineBinaryNotFound(EngineFailure):
    reason_code = "ENGINE_BINARY_NOT_FOUND"


class EngineTimeout(EngineFailure):
    reason_code = "ENGINE_TIMEOUT"


class EngineNonZeroExit(EngineFailure):
    reason_code = "ENGINE_NONZERO_EXIT"


class EngineInvalidJson(EngineFailure):
    reason_code = "ENGINE_INVALID_JSON"


class EngineSchemaMismatch(EngineFailure):
    reason_code = "ENGINE_SCHEMA_MISMATCH"


class UnsupportedEngineCapability(EngineFailure):
    reason_code = "UNSUPPORTED_ENGINE_CAPABILITY"


class EngineMissingInput(EngineFailure):
    reason_code = "ENGINE_MISSING_INPUT"


class EngineAmbiguousInput(EngineFailure):
    reason_code = "ENGINE_AMBIGUOUS_INPUT"


# reason codes for non-error fail-closed outcomes (traceable, greppable)
REASON_NO_SCOPE = "NO_APPLICABLE_SCOPE"
REASON_NO_KNOWLEDGE = "NO_KNOWLEDGE_AT_DATE"
REASON_TEMPORAL_GAP = "TEMPORAL_GAP_IN_KNOWLEDGE"
REASON_NO_ELIGIBLE_RULE = "NO_PUBLISHABLE_RULE_COVERAGE"
REASON_RULES_INELIGIBLE = "RULES_NOT_ELIGIBLE"
REASON_NO_ACTIVE_RULE = "NO_CONDITION_SATISFIED"
REASON_UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
REASON_PRECEDENCE_CYCLE = "PRECEDENCE_CYCLE"
REASON_SPATIAL_REVIEW = "SPATIAL_REVIEW_INCOMPLETE"
REASON_ACTIVITY_VOCAB = "ACTIVITY_OUTSIDE_VOCABULARY"
REASON_INVARIANT_VIOLATION = "PERMITTED_INVARIANT_VIOLATION"
