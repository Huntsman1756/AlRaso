"""Refresh runner glue — observation -> verdict -> store -> packet.

``observe()`` is the single entry point the tooling calls per document:
it loads the isolated counters for ``(source_id, surface_id,
runner_network)``, classifies the observation, appends the snapshot
record (every observation is preserved evidence — failures included),
persists the counters, and builds a RefreshPacket when the verdict
requires one. No network here; the observation is constructed upstream
by tooling (live fetch) or by fixtures (replay).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.models import FetchOutcome, RunnerNetwork
from pipeline.refresh.classify import (
    RefreshObservation,
    RefreshVerdict,
    Thresholds,
    classify,
)
from pipeline.refresh.packets import RefreshPacket, build_packet
from pipeline.refresh.snapshots import SnapshotRecord, SnapshotStore


@dataclass(frozen=True)
class ObserveResult:
    verdict: RefreshVerdict
    record: SnapshotRecord
    packet: RefreshPacket | None


def observe(
    store: SnapshotStore,
    *,
    source_id: str,
    surface_id: str,
    doc_id: str,
    obs: RefreshObservation,
    thresholds: Thresholds,
) -> ObserveResult:
    """Record one observation and classify it against the baseline."""
    counters = store.counters(source_id, surface_id, obs.runner_network)
    prev = store.latest(source_id, surface_id, doc_id)
    verdict = classify(prev, obs, counters, thresholds)

    record = SnapshotRecord(
        source_id=source_id,
        surface_id=surface_id,
        doc_id=doc_id,
        raw_sha256=obs.raw_sha256 or "",
        canonical_sha256=obs.canonical_sha256 or "",
        canonicalizer_id=obs.canonicalizer_id or "",
        canonicalizer_version=obs.canonicalizer_version or 0,
        fetch_outcome=obs.fetch_outcome,
        reachability_observed=obs.reachability_observed,
        observed_at=obs.observed_at,
        runner_network=RunnerNetwork(obs.runner_network),
        etag=obs.etag,
        last_modified=obs.last_modified,
        http_status=obs.http_status,
    )
    store.append(record)
    store.save_counters(
        source_id, surface_id, obs.runner_network, counters
    )

    packet = None
    if verdict.emits_packet:
        packet = build_packet(
            verdict=verdict,
            source_id=source_id,
            surface_id=surface_id,
            doc_id=doc_id,
            obs={
                "runner_network": obs.runner_network,
                "observed_at": obs.observed_at,
                "raw_sha256": obs.raw_sha256,
                "canonical_sha256": obs.canonical_sha256,
                "canonicalizer_id": obs.canonicalizer_id,
                "canonicalizer_version": obs.canonicalizer_version,
                "fetch_outcome": obs.fetch_outcome.value,
                "reachability_observed": obs.reachability_observed.value,
                "http_status": obs.http_status,
                "etag": obs.etag,
                "last_modified": obs.last_modified,
            },
            prev=prev,
            thresholds={
                "absence": thresholds.absence,
                "invalid": thresholds.invalid,
                "degraded": thresholds.degraded,
            },
        )
    return ObserveResult(verdict=verdict, record=record, packet=packet)
