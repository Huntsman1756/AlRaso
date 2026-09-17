"""Deterministic refresh classifier — spec M10.2 §C.2 state machine.

Inputs: previous baseline snapshot (latest SUCCESS only — failures never
replace evidence), the new observation, the canonical digest of the new
bytes (when a fetch succeeded), the counters for
``(surface_id, runner_network)`` and the profile thresholds.

The function is pure: it mutates ``counters`` in place and returns a
``RefreshVerdict``; persistence is the caller's job. Nothing here
fetches, deletes, or publishes.

State mapping (frozen contract):

    no response (TIMEOUT/TRANSPORT_ERROR, reachability UNREACHABLE)
        -> counters.unreachable += 1
        >= degraded_threshold -> ACCESS_DEGRADED   (alert packet)
        else                  -> UNREACHABLE       (log)
        UNREACHABLE never feeds DISAPPEARED_SUSPECTED

    reachable 404/410 or SOFT_404 (absence evidence)
        -> counters.absent += 1
        >= absence_threshold  -> DISAPPEARED_SUSPECTED (alert packet)
        else                  -> ABSENT_OBSERVED       (log)

    reachable marker/contract failure (CONTENT_MARKER_MISMATCH, or
    HTTP_ERROR other than 404/410 — a 500 is a contract failure, not
    absence evidence)
        -> counters.invalid += 1
        >= invalid_threshold  -> INVALID + alert packet
        else                  -> INVALID (log)

    SUCCESS
        -> counters.reset()
        prev None                                  -> BASELINE_CREATED
        canonicalizer id/version != prev           -> REBASELINE_REQUIRED
        canonical same + raw same + etag/last_modified same -> SAME
        canonical same + (raw OR transport metadata changed)
                                                   -> CHANGED_TRANSPORT_ONLY
        canonical changed                          -> CHANGED_CONTENT (packet)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pipeline.models import FetchOutcome, ReachabilityObserved
from pipeline.refresh.snapshots import Counters, SnapshotRecord


class RefreshState(str, Enum):
    FIRST_OBSERVATION = "FIRST_OBSERVATION"
    BASELINE_CREATED = "BASELINE_CREATED"
    SAME = "SAME"
    CHANGED_TRANSPORT_ONLY = "CHANGED_TRANSPORT_ONLY"
    CHANGED_CONTENT = "CHANGED_CONTENT"
    REBASELINE_REQUIRED = "REBASELINE_REQUIRED"
    UNREACHABLE = "UNREACHABLE"
    ACCESS_DEGRADED = "ACCESS_DEGRADED"
    ABSENT_OBSERVED = "ABSENT_OBSERVED"
    DISAPPEARED_SUSPECTED = "DISAPPEARED_SUSPECTED"
    INVALID = "INVALID"


# States that emit a review packet (spec §G).
PACKET_STATES = frozenset(
    {
        RefreshState.CHANGED_CONTENT,
        RefreshState.ACCESS_DEGRADED,
        RefreshState.DISAPPEARED_SUSPECTED,
    }
)

_ABSENCE_STATUSES = frozenset({404, 410})

DEFAULT_THRESHOLDS = {"absence": 3, "invalid": 3, "degraded": 3}


@dataclass(frozen=True)
class Thresholds:
    """Per-profile persistence thresholds (spec: absence/invalid/degraded
    live in the source profile; missing values fail closed to 3)."""

    absence: int = DEFAULT_THRESHOLDS["absence"]
    invalid: int = DEFAULT_THRESHOLDS["invalid"]
    degraded: int = DEFAULT_THRESHOLDS["degraded"]

    @classmethod
    def from_profile(cls, refresh_cfg: dict[str, Any] | None) -> "Thresholds":
        cfg = refresh_cfg or {}
        return cls(
            absence=int(cfg.get("absence_threshold",
                                DEFAULT_THRESHOLDS["absence"])),
            invalid=int(cfg.get("invalid_threshold",
                                DEFAULT_THRESHOLDS["invalid"])),
            degraded=int(cfg.get("degraded_threshold",
                                 DEFAULT_THRESHOLDS["degraded"])),
        )


@dataclass(frozen=True)
class RefreshObservation:
    """One fresh observation of a tracked document — what the runner saw.
    ``canonical_sha256``/canonicalizer fields are filled only when the
    fetch succeeded (there are bytes to canonicalize)."""

    fetch_outcome: FetchOutcome
    reachability_observed: ReachabilityObserved
    observed_at: str
    runner_network: str
    http_status: int | None = None
    raw_sha256: str | None = None
    canonical_sha256: str | None = None
    canonicalizer_id: str | None = None
    canonicalizer_version: int | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class RefreshVerdict:
    """Classifier output: the state, whether a packet must be emitted,
    and the counter values after this observation."""

    state: RefreshState
    emits_packet: bool
    counters: dict[str, int]
    detail: str = ""


def _is_absence(obs: RefreshObservation) -> bool:
    """Reachable-absence evidence ONLY: 404/410 or preregistered soft-404
    with the server responding. Never transport failure."""
    if obs.reachability_observed is not ReachabilityObserved.REACHABLE:
        return False
    if obs.fetch_outcome is FetchOutcome.SOFT_404:
        return True
    return (
        obs.fetch_outcome is FetchOutcome.HTTP_ERROR
        and obs.http_status in _ABSENCE_STATUSES
    )


def _is_unreachable(obs: RefreshObservation) -> bool:
    return (
        obs.reachability_observed is ReachabilityObserved.UNREACHABLE
        or obs.fetch_outcome
        in (FetchOutcome.TIMEOUT, FetchOutcome.TRANSPORT_ERROR)
    )


def classify(
    prev: SnapshotRecord | None,
    obs: RefreshObservation,
    counters: Counters,
    thresholds: Thresholds,
) -> RefreshVerdict:
    """One observation → one verdict. Deterministic, no I/O."""

    if _is_unreachable(obs):
        counters.unreachable += 1
        if counters.unreachable >= thresholds.degraded:
            return RefreshVerdict(
                RefreshState.ACCESS_DEGRADED,
                emits_packet=True,
                counters=counters.to_dict(),
                detail=(
                    f"UNREACHABLE x{counters.unreachable} "
                    f">= degraded_threshold {thresholds.degraded}"
                ),
            )
        return RefreshVerdict(
            RefreshState.UNREACHABLE,
            emits_packet=False,
            counters=counters.to_dict(),
            detail=f"UNREACHABLE x{counters.unreachable} — never absence",
        )

    if _is_absence(obs):
        counters.absent += 1
        if counters.absent >= thresholds.absence:
            return RefreshVerdict(
                RefreshState.DISAPPEARED_SUSPECTED,
                emits_packet=True,
                counters=counters.to_dict(),
                detail=(
                    f"reachable absence x{counters.absent} "
                    f">= absence_threshold {thresholds.absence}; "
                    "prior evidence preserved"
                ),
            )
        return RefreshVerdict(
            RefreshState.ABSENT_OBSERVED,
            emits_packet=False,
            counters=counters.to_dict(),
            detail=f"reachable absence x{counters.absent} "
                   f"(threshold {thresholds.absence})",
        )

    if obs.fetch_outcome is not FetchOutcome.SUCCESS:
        # REACHABLE but no valid content: HTTP_ERROR (non-404/410) or
        # CONTENT_MARKER_MISMATCH — a contract failure, not absence.
        counters.invalid += 1
        emits = counters.invalid >= thresholds.invalid
        return RefreshVerdict(
            RefreshState.INVALID,
            emits_packet=emits,
            counters=counters.to_dict(),
            detail=(
                f"invalid observation x{counters.invalid} "
                f"(threshold {thresholds.invalid})"
            ),
        )

    # SUCCESS — real content arrived; consecutive failure counters reset.
    counters.reset()

    if prev is None:
        return RefreshVerdict(
            RefreshState.BASELINE_CREATED,
            emits_packet=False,
            counters=counters.to_dict(),
            detail="FIRST_OBSERVATION -> baseline persisted, no packet",
        )

    if (
        obs.canonicalizer_id != prev.canonicalizer_id
        or obs.canonicalizer_version != prev.canonicalizer_version
    ):
        return RefreshVerdict(
            RefreshState.REBASELINE_REQUIRED,
            emits_packet=False,
            counters=counters.to_dict(),
            detail=(
                f"canonicalizer {prev.canonicalizer_id}"
                f"@{prev.canonicalizer_version} -> "
                f"{obs.canonicalizer_id}@{obs.canonicalizer_version}: "
                "manual re-baseline; never a content change"
            ),
        )

    if obs.canonical_sha256 == prev.canonical_sha256:
        transport_same = (
            obs.raw_sha256 == prev.raw_sha256
            and obs.etag == prev.etag
            and obs.last_modified == prev.last_modified
        )
        if transport_same:
            return RefreshVerdict(
                RefreshState.SAME,
                emits_packet=False,
                counters=counters.to_dict(),
                detail="canonical + raw + transport metadata identical",
            )
        return RefreshVerdict(
            RefreshState.CHANGED_TRANSPORT_ONLY,
            emits_packet=False,
            counters=counters.to_dict(),
            detail="canonical identical; raw bytes or etag/last_modified "
                   "changed — transport-level only",
        )

    return RefreshVerdict(
        RefreshState.CHANGED_CONTENT,
        emits_packet=True,
        counters=counters.to_dict(),
        detail="canonical sha256 changed under the same canonicalizer",
    )
