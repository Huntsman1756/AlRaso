"""InventorySource: pilot space seed → SpaceRecord[] + authority refs.

Boundary (Task 8): reconciles the space inventory (seeded from the OAPN
administrative layer, G0-verified) with the gazette authorities that
publish for each space. ``authority_refs()`` returns raw cite strings —
discovery pointers for the providers, never resolved legal claims.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from types import MappingProxyType

from pipeline.models import SpaceRecord


class InventoryError(ValueError):
    """Seed document is malformed — explicit failure, never partial records."""


def _freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_freeze(v) for v in obj)
    return obj


def load_seed(path: Path | str) -> Mapping[str, Any]:
    """Load the pilot-spaces seed into an immutable mapping."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != "alraso.m10.pilot-spaces/v1":
        raise InventoryError("pilot-spaces seed has an unexpected schema")
    if not isinstance(doc.get("spaces"), list) or not doc["spaces"]:
        raise InventoryError("pilot-spaces seed requires a non-empty 'spaces'")
    doc["evidence_sha256"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return _freeze(doc)


def _require(space: Mapping[str, Any], key: str, kind: type) -> Any:
    value = space.get(key)
    if not isinstance(value, kind) or (kind is str and not value.strip()):
        raise InventoryError(f"space {space.get('space_id')!r}: bad {key!r}")
    return value


def list_spaces(seed: Mapping[str, Any]) -> list[SpaceRecord]:
    """SpaceRecord[] from the seed — sorted by space_id for determinism."""
    records = []
    for space in seed["spaces"]:
        space_id = _require(space, "space_id", str)
        name = _require(space, "name", str)
        ccaa = _require(space, "ccaa", tuple)
        authorities = _require(space, "authorities", tuple)
        if not all(isinstance(c, str) and c.strip() for c in ccaa):
            raise InventoryError(f"space {space_id!r}: bad 'ccaa'")
        if not authorities:
            raise InventoryError(f"space {space_id!r}: no 'authorities'")
        records.append(
            SpaceRecord(
                space_id=space_id,
                name=name,
                figure_type="PN",
                ccaa=tuple(sorted(ccaa)),
                source=seed["source"],
                source_id=name,
                admin_geom_ref=name,
                observed_at=seed["seeded_at"],
                evidence_sha256=seed["evidence_sha256"],
            )
        )
    return sorted(records, key=lambda s: s.space_id)


def authority_refs(
    space_id: str, seed: Mapping[str, Any]
) -> tuple[Mapping[str, str], ...]:
    """Authority references for a space: ``{jurisdiction, gazette, cite}``.

    Order follows the seed (deterministic); each entry is validated for the
    required keys. The cite is a discovery pointer — not a resolved norm.
    """
    for space in seed["spaces"]:
        if space.get("space_id") != space_id:
            continue
        refs = []
        for ref in space["authorities"]:
            for key in ("jurisdiction", "gazette", "cite"):
                if not isinstance(ref.get(key), str) or not ref[key].strip():
                    raise InventoryError(
                        f"space {space_id!r}: authority ref missing {key!r}"
                    )
            refs.append(dict(ref))
        return tuple(refs)
    raise InventoryError(f"unknown space_id {space_id!r}")
