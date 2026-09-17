"""RefreshPacket — deterministic human-review artifact for refresh events.

Emitted only for packet states (spec §G): ``CHANGED_CONTENT``,
``ACCESS_DEGRADED``, ``DISAPPEARED_SUSPECTED``, persistent ``INVALID``.

Deterministic: the packet is a pure function of the verdict inputs —
same observation tuple produces byte-identical JSON. The only timestamp
is the observation's own ``observed_at``. ``publication_readiness`` is
hardcoded ``"NO"``: a packet is evidence for a human, never a publish
request, and PR opening stays human-controlled (spec §C.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Any, Mapping

from pipeline.models import _to_json
from pipeline.refresh.classify import RefreshState, RefreshVerdict
from pipeline.refresh.snapshots import SnapshotRecord


@dataclass(frozen=True)
class RefreshPacket:
    packet_kind: str  # "content_change" | "alert"
    outcome: str  # RefreshState value
    source_id: str
    surface_id: str
    doc_id: str
    runner_network: str
    observed_at: str
    counters: dict[str, int]
    thresholds: dict[str, int]
    detail: str
    prev_snapshot: dict[str, Any] | None = None
    new_snapshot: dict[str, Any] | None = None
    publication_readiness: str = field(default="NO", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {f.name: _to_json(getattr(self, f.name)) for f in fields(self)}

    def to_json(self) -> str:
        return (
            json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False,
                       indent=2)
            + "\n"
        )


def _snapshot_projection(rec: SnapshotRecord | None) -> dict[str, Any] | None:
    if rec is None:
        return None
    d = rec.to_dict()
    return {
        k: d[k]
        for k in (
            "raw_sha256",
            "canonical_sha256",
            "canonicalizer_id",
            "canonicalizer_version",
            "fetch_outcome",
            "reachability_observed",
            "observed_at",
            "runner_network",
            "http_status",
        )
    }


def build_packet(
    *,
    verdict: RefreshVerdict,
    source_id: str,
    surface_id: str,
    doc_id: str,
    obs: Mapping[str, Any],
    prev: SnapshotRecord | None,
    thresholds: Mapping[str, int],
) -> RefreshPacket:
    """Assemble the deterministic packet for a packet-emitting verdict."""
    kind = (
        "content_change"
        if verdict.state is RefreshState.CHANGED_CONTENT
        else "alert"
    )
    return RefreshPacket(
        packet_kind=kind,
        outcome=verdict.state.value,
        source_id=source_id,
        surface_id=surface_id,
        doc_id=doc_id,
        runner_network=str(obs.get("runner_network", "unknown")),
        observed_at=str(obs.get("observed_at", "")),
        counters=dict(verdict.counters),
        thresholds=dict(thresholds),
        detail=verdict.detail,
        prev_snapshot=_snapshot_projection(prev),
        new_snapshot={
            "raw_sha256": obs.get("raw_sha256"),
            "canonical_sha256": obs.get("canonical_sha256"),
            "canonicalizer_id": obs.get("canonicalizer_id"),
            "canonicalizer_version": obs.get("canonicalizer_version"),
            "fetch_outcome": str(obs.get("fetch_outcome", "")),
            "reachability_observed": str(
                obs.get("reachability_observed", "")
            ),
            "http_status": obs.get("http_status"),
            "etag": obs.get("etag"),
            "last_modified": obs.get("last_modified"),
        },
    )


def render_markdown(packet: RefreshPacket) -> str:
    """Human-readable rendering of the packet."""
    lines = [
        f"# RefreshPacket — {packet.doc_id}",
        "",
        f"publication_readiness: **{packet.publication_readiness}**",
        f"outcome: `{packet.outcome}`",
        f"source/surface: `{packet.source_id}` / `{packet.surface_id}`",
        f"runner_network: `{packet.runner_network}`",
        f"observed_at: {packet.observed_at}",
        "",
        f"detail: {packet.detail}",
        "",
        "## Evidence",
        "",
    ]
    for label, snap in (
        ("previous", packet.prev_snapshot),
        ("current", packet.new_snapshot),
    ):
        if snap is None:
            lines.append(f"- {label}: none recorded")
            continue
        lines.append(
            f"- {label}: raw `{snap['raw_sha256']}` canonical "
            f"`{snap['canonical_sha256']}` "
            f"({snap['canonicalizer_id']}@{snap['canonicalizer_version']})"
        )
    lines += [
        "",
        "## Counters",
        "",
        f"```json\n{json.dumps(packet.counters, sort_keys=True)}\n```",
        "",
        "Evidence for human review only — nothing is published, deleted, "
        "or auto-merged.",
    ]
    return "\n".join(lines) + "\n"
