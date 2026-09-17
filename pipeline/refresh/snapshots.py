"""Snapshot store — versioned evidence records + persistence counters.

Spec M10.2 §C.2: ``SnapshotRecord`` is the canonical evidence unit; the
store is append-only (previous evidence is always preserved, never
mutated or deleted) and persistence counters are isolated by
``(source_id, surface_id, runner_network)`` so that failures observed
from ``foreign_ci`` never contaminate the ``es_local`` history.

Layout (local-first, git-friendly, deterministic):

    <root>/<source_id>/<surface_id>/<doc_key>.jsonl   one record per line
    <root>/counters.json                              consecutive counts

``doc_key`` is a deterministic filesystem-safe encoding of ``doc_id``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from pipeline.models import (
    FetchOutcome,
    ReachabilityObserved,
    RunnerNetwork,
    _to_json,
)


@dataclass(frozen=True)
class SnapshotRecord:
    """One recorded observation of a source document (spec §C.2 shape).

    ``http_status`` is preserved beyond the spec minimum because the
    classifier must distinguish reachable 404/410 (absence evidence) from
    reachable 5xx (contract failure) — the record keeps the truth.
    """

    source_id: str
    surface_id: str
    doc_id: str
    raw_sha256: str
    canonical_sha256: str
    canonicalizer_id: str
    canonicalizer_version: int
    fetch_outcome: FetchOutcome | None
    reachability_observed: ReachabilityObserved
    observed_at: str
    runner_network: RunnerNetwork
    etag: str | None = None
    last_modified: str | None = None
    http_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: _to_json(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SnapshotRecord":
        return cls(
            source_id=data["source_id"],
            surface_id=data["surface_id"],
            doc_id=data["doc_id"],
            raw_sha256=data["raw_sha256"],
            canonical_sha256=data["canonical_sha256"],
            canonicalizer_id=data["canonicalizer_id"],
            canonicalizer_version=int(data["canonicalizer_version"]),
            fetch_outcome=(
                None
                if data.get("fetch_outcome") is None
                else FetchOutcome(data["fetch_outcome"])
            ),
            reachability_observed=ReachabilityObserved(
                data["reachability_observed"]
            ),
            observed_at=data["observed_at"],
            runner_network=RunnerNetwork(data["runner_network"]),
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            http_status=data.get("http_status"),
        )


@dataclass
class Counters:
    """Consecutive-observation counters for one (surface, runner) pair."""

    unreachable: int = 0
    absent: int = 0
    invalid: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "unreachable": self.unreachable,
            "absent": self.absent,
            "invalid": self.invalid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Counters":
        return cls(
            unreachable=int(data.get("unreachable", 0)),
            absent=int(data.get("absent", 0)),
            invalid=int(data.get("invalid", 0)),
        )

    def reset(self) -> None:
        """A successful observation clears all consecutive counters."""
        self.unreachable = self.absent = self.invalid = 0


def doc_key(doc_id: str) -> str:
    """Deterministic, injective, filesystem-safe key for a document id.

    Percent-encoding is injective (distinct ids never collide) and the
    ``q`` prefix guarantees the key can never be ``.``/``..`` or a bare
    reserved name. Long ids are truncated with a sha256 suffix to stay
    collision-free inside the filesystem limit.
    """
    from urllib.parse import quote

    if not doc_id or doc_id in (".", ".."):
        raise ValueError(f"invalid doc_id for storage key: {doc_id!r}")
    key = "q" + quote(doc_id, safe="")
    if len(key) > 120:
        digest = hashlib.sha256(doc_id.encode("utf-8")).hexdigest()[:16]
        key = key[:80] + "-" + digest
    return key


class SnapshotStore:
    """Append-only snapshot log + isolated persistence counters."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _log_path(self, source_id: str, surface_id: str, doc_id: str) -> Path:
        path = (
            self.root
            / doc_key(source_id)
            / doc_key(surface_id)
            / f"{doc_key(doc_id)}.jsonl"
        )
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError(
                f"store key escapes root: {source_id}/{surface_id}/{doc_id}"
            )
        return path

    def append(self, record: SnapshotRecord) -> Path:
        path = self._log_path(
            record.source_id, record.surface_id, record.doc_id
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(record.to_dict(), sort_keys=True,
                           ensure_ascii=False)
                + "\n"
            )
        return path

    def history(
        self, source_id: str, surface_id: str, doc_id: str
    ) -> list[SnapshotRecord]:
        path = self._log_path(source_id, surface_id, doc_id)
        if not path.is_file():
            return []
        return [
            SnapshotRecord.from_dict(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def latest(
        self, source_id: str, surface_id: str, doc_id: str
    ) -> SnapshotRecord | None:
        """Latest *successful-fetch* snapshot.

        Failure observations never replace success evidence. This is the
        raw last-success record — NOT the comparison baseline; use
        ``baseline()`` for that so a REBASELINE_REQUIRED record cannot
        silently become the baseline.
        """
        ok = [
            r
            for r in self.history(source_id, surface_id, doc_id)
            if r.fetch_outcome is FetchOutcome.SUCCESS
        ]
        return ok[-1] if ok else None

    def _baseline_path(
        self, source_id: str, surface_id: str, doc_id: str
    ) -> Path:
        return self._log_path(source_id, surface_id, doc_id).with_suffix(
            ".baseline.json"
        )

    def baseline(
        self, source_id: str, surface_id: str, doc_id: str
    ) -> SnapshotRecord | None:
        """Current comparison baseline via an explicit pointer.

        The pointer advances only on BASELINE_CREATED (first success) or
        on an explicit human ``rebaseline()`` — never implicitly. A
        canonicalizer bump therefore keeps raising REBASELINE_REQUIRED
        until a human confirms the new baseline, and a concurrent real
        content change cannot be absorbed silently.
        """
        path = self._baseline_path(source_id, surface_id, doc_id)
        if not path.is_file():
            return None
        index = int(
            json.loads(path.read_text(encoding="utf-8"))["index"]
        )
        hist = self.history(source_id, surface_id, doc_id)
        if not 0 <= index < len(hist):
            raise ValueError(
                f"baseline pointer {index} out of range for "
                f"{source_id}/{surface_id}/{doc_id} "
                f"({len(hist)} records) — store corrupted"
            )
        return hist[index]

    def set_baseline(
        self,
        source_id: str,
        surface_id: str,
        doc_id: str,
        index: int | None = None,
    ) -> None:
        """Point the baseline at a history index (default: last record).

        Called internally on BASELINE_CREATED, and by the explicit
        ``rebaseline`` tooling action — the only two legitimate ways a
        baseline is created or moved.
        """
        hist_len = len(self.history(source_id, surface_id, doc_id))
        if index is None:
            index = hist_len - 1
        if not 0 <= index < hist_len:
            raise ValueError(
                f"baseline index {index} out of range "
                f"({hist_len} records)"
            )
        path = self._baseline_path(source_id, surface_id, doc_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"index": index}, sort_keys=True) + "\n",
            "utf-8",
        )

    # -- counters -----------------------------------------------------

    @staticmethod
    def _counter_key(
        source_id: str, surface_id: str, doc_id: str,
        runner_network: str,
    ) -> str:
        # Per-document persistence counters — a strict refinement of the
        # spec's "por superficie x runner_network" isolation (a superset
        # of the required key): pooling across doc_ids on one surface
        # would misattribute DISAPPEARED_SUSPECTED to whichever doc
        # crossed the pooled threshold, and interleaved successes of
        # other docs would erase a genuinely vanished doc's streak.
        return (
            f"{source_id}|{surface_id}|{doc_id}|{runner_network}"
        )

    def _counters_path(self) -> Path:
        return self.root / "counters.json"

    def _load_counters(self) -> dict[str, Any]:
        path = self._counters_path()
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def counters(
        self,
        source_id: str,
        surface_id: str,
        doc_id: str,
        runner_network: str,
    ) -> Counters:
        data = self._load_counters()
        return Counters.from_dict(
            data.get(
                self._counter_key(
                    source_id, surface_id, doc_id, runner_network
                ),
                {},
            )
        )

    def save_counters(
        self,
        source_id: str,
        surface_id: str,
        doc_id: str,
        runner_network: str,
        counters: Counters,
    ) -> None:
        data = self._load_counters()
        data[
            self._counter_key(
                source_id, surface_id, doc_id, runner_network
            )
        ] = counters.to_dict()
        path = self._counters_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True,
                       ensure_ascii=False)
            + "\n",
            "utf-8",
        )
