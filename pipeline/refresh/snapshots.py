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

import json
import re
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


_DOC_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def doc_key(doc_id: str) -> str:
    """Deterministic filesystem-safe key for a document id."""
    return _DOC_KEY_SAFE.sub("_", doc_id)


class SnapshotStore:
    """Append-only snapshot log + isolated persistence counters."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _log_path(self, source_id: str, surface_id: str, doc_id: str) -> Path:
        return (
            self.root
            / doc_key(source_id)
            / doc_key(surface_id)
            / f"{doc_key(doc_id)}.jsonl"
        )

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
        """Latest *successful-fetch* snapshot — the comparison baseline.
        Failure observations never replace baseline evidence."""
        ok = [
            r
            for r in self.history(source_id, surface_id, doc_id)
            if r.fetch_outcome is FetchOutcome.SUCCESS
        ]
        return ok[-1] if ok else None

    # -- counters -----------------------------------------------------

    @staticmethod
    def _counter_key(
        source_id: str, surface_id: str, runner_network: str
    ) -> str:
        return f"{source_id}|{surface_id}|{runner_network}"

    def _counters_path(self) -> Path:
        return self.root / "counters.json"

    def _load_counters(self) -> dict[str, Any]:
        path = self._counters_path()
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def counters(
        self, source_id: str, surface_id: str, runner_network: str
    ) -> Counters:
        data = self._load_counters()
        return Counters.from_dict(
            data.get(self._counter_key(source_id, surface_id,
                                       runner_network), {})
        )

    def save_counters(
        self,
        source_id: str,
        surface_id: str,
        runner_network: str,
        counters: Counters,
    ) -> None:
        data = self._load_counters()
        data[
            self._counter_key(source_id, surface_id, runner_network)
        ] = counters.to_dict()
        path = self._counters_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True,
                       ensure_ascii=False)
            + "\n",
            "utf-8",
        )
