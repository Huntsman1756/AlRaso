"""Official-geometry spatial provider (M8-E).

Builds an InMemorySpatialProvider from GeoJSON FeatureCollections whose
integrity is PINNED by sha256: the file bytes must match the declared digest
or loading fails closed (SpatialFactsError). A tampered or stale official
layer can never silently resolve coordinates.

Each GeoJsonLayer declares how features emit scopes:

  * CONSTANT — every feature in the layer contributes its parts to one
    scope (e.g. the whole PN-CM vivac layer -> ss-pnsg-vivac-anexo3).
  * PROPERTY — a feature property selects the scope via scope_map
    (e.g. CD_ZONA=PN -> pn scope, CD_ZONA=ZPP -> zpp scope). Values not
    present in the map are governed by ``unmapped``: "error" (default,
    fail-closed — a silently dropped zone would falsify coverage) or
    "skip" (explicitly declared ignorable, e.g. zones with no corpus entry).

Features mapping to the same scope contribute a UNION of parts. Interior
rings (holes) are preserved end-to-end by parts_from_geojson — never
approximated. Two specs disagreeing on a scope's type/name is a
SpatialFactsError, never a silent pick.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from alraso.spatial import (
    InMemorySpatialProvider,
    SpatialFactsError,
    parts_from_geojson,
)

EmissionMode = Literal["constant", "property"]
UnmappedPolicy = Literal["error", "skip"]


@dataclass(frozen=True)
class GeoJsonLayer:
    """One integrity-pinned GeoJSON layer -> scope emission rule."""

    path: Path
    sha256: str                      # required: lowercase hex digest of file bytes
    scope_type: str
    official_name: str | None = None  # fallback when name_property is unset
    name_property: str | None = None  # feature property carrying the scope name
    # CONSTANT emission: every feature feeds this scope
    scope_id: str | None = None
    # PROPERTY emission: feature property -> scope_id via scope_map
    scope_property: str | None = None
    scope_map: dict[str, str] = field(default_factory=dict)
    # Optional canonical names per emitted scope (wins over name_property /
    # official_name for that scope; needed when several codes map to one
    # named scope, e.g. A1+A2 -> reserva-natural)
    scope_names: dict[str, str] = field(default_factory=dict)
    unmapped: UnmappedPolicy = "error"

    def __post_init__(self) -> None:
        if self.scope_id is None and not self.scope_property:
            raise SpatialFactsError(
                "GeoJsonLayer needs scope_id (constant) or scope_property")
        if self.scope_property and not self.scope_map:
            raise SpatialFactsError("scope_property requires a non-empty scope_map")
        if self.unmapped not in ("error", "skip"):
            raise SpatialFactsError(f"bad unmapped policy {self.unmapped!r}")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise SpatialFactsError("sha256 must be a 64-hex pinned digest")
        if self.scope_id is None and self.official_name is None \
                and self.name_property is None and not self.scope_names:
            raise SpatialFactsError(
                "layer needs official_name, name_property or scope_names")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _feature_scopes(spec: GeoJsonLayer, props: dict[str, Any],
                    index: int) -> list[tuple[str, str, str]]:
    """(scope_id, official_name, scope_type) emissions for one feature."""
    out: list[tuple[str, str, str]] = []
    feat_name = spec.official_name or ""
    if spec.name_property:
        feat_name = str(props.get(spec.name_property) or feat_name)
    if spec.scope_id is not None:
        name = spec.scope_names.get(spec.scope_id) or spec.official_name \
            or feat_name
        if not name:
            raise SpatialFactsError(
                f"{spec.path.name} feature #{index}: no official name resolvable")
        out.append((spec.scope_id, name, spec.scope_type))
    if spec.scope_property:
        value = props.get(spec.scope_property)
        key = "" if value is None else str(value)
        target = spec.scope_map.get(key)
        if target is None:
            if spec.unmapped == "error":
                raise SpatialFactsError(
                    f"{spec.path.name} feature #{index}: unmapped "
                    f"{spec.scope_property}={key!r}")
        else:
            name = spec.scope_names.get(target) or feat_name or target
            out.append((target, name, spec.scope_type))
    return out


def load_geojson_provider(specs: list[GeoJsonLayer]) -> InMemorySpatialProvider:
    """Pinned-hash GeoJSON layers -> InMemorySpatialProvider (parts union)."""
    provider = InMemorySpatialProvider()
    parts_by_scope: dict[str, list] = {}
    meta_by_scope: dict[str, tuple[str, str]] = {}
    for spec in specs:
        digest = file_sha256(spec.path)
        if digest.lower() != spec.sha256.lower():
            raise SpatialFactsError(
                f"{spec.path.name}: sha256 mismatch "
                f"(expected {spec.sha256[:16]}…, got {digest[:16]}…)")
        with open(spec.path, encoding="utf-8") as fh:
            try:
                collection = json.load(fh)
            except json.JSONDecodeError as exc:
                raise SpatialFactsError(
                    f"{spec.path.name}: invalid JSON ({exc})") from exc
        if collection.get("type") != "FeatureCollection":
            raise SpatialFactsError(f"{spec.path.name}: not a FeatureCollection")
        for i, feature in enumerate(collection.get("features") or []):
            geometry = feature.get("geometry")
            if not geometry:
                raise SpatialFactsError(
                    f"{spec.path.name} feature #{i}: no geometry")
            parts = parts_from_geojson(geometry)
            for scope_id, name, scope_type in _feature_scopes(
                    spec, feature.get("properties") or {}, i):
                prev = meta_by_scope.get(scope_id)
                if prev is not None and prev != (name, scope_type):
                    raise SpatialFactsError(
                        f"conflicting metadata for scope {scope_id}: "
                        f"{prev} vs {(name, scope_type)}")
                meta_by_scope[scope_id] = (name, scope_type)
                parts_by_scope.setdefault(scope_id, []).extend(parts)
    for scope_id in sorted(parts_by_scope):
        name, scope_type = meta_by_scope[scope_id]
        provider.add_scope(scope_id, name, scope_type,
                           parts=parts_by_scope[scope_id])
    return provider


MANIFEST_SCHEMA = "alraso-m8-layer-manifest-v1"


def load_manifest_provider(manifest_path: Path) -> InMemorySpatialProvider:
    """Declarative layer manifest -> pinned provider.

    The manifest is the single source of truth for which official layers
    feed the point resolver and how their features map to scopes; tests,
    the product path and the M8-F holdout runner MUST share it so wiring
    can never diverge silently. Paths are resolved relative to the
    manifest file; every digest is re-verified by load_geojson_provider.
    """
    manifest_path = Path(manifest_path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpatialFactsError(
            f"{manifest_path.name}: unreadable manifest ({exc})") from exc
    if data.get("schema") != MANIFEST_SCHEMA:
        raise SpatialFactsError(
            f"{manifest_path.name}: schema must be {MANIFEST_SCHEMA!r}")
    layers = data.get("layers")
    if not isinstance(layers, list) or not layers:
        raise SpatialFactsError(
            f"{manifest_path.name}: 'layers' must be a non-empty list")
    specs: list[GeoJsonLayer] = []
    for i, e in enumerate(layers):
        if not isinstance(e, dict):
            raise SpatialFactsError(f"manifest layer #{i} is not an object")
        try:
            specs.append(GeoJsonLayer(
                path=manifest_path.parent / e["path"],
                sha256=e["sha256"],
                scope_type=e["scope_type"],
                official_name=e.get("official_name"),
                name_property=e.get("name_property"),
                scope_id=e.get("scope_id"),
                scope_property=e.get("scope_property"),
                scope_map=dict(e.get("scope_map") or {}),
                scope_names=dict(e.get("scope_names") or {}),
                unmapped=e.get("unmapped", "error"),
            ))
        except (KeyError, TypeError) as exc:
            raise SpatialFactsError(
                f"manifest layer #{i} ({e.get('id', '?')}): "
                f"missing/invalid field {exc}") from exc
    return load_geojson_provider(specs)
