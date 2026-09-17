"""SourceProfile loader + structural validation (stdlib only).

Profiles are plain JSON files (``pipeline/sources/*.profile.json``); the
core deliberately carries zero parser dependencies. The validator below is a
small explicit subset checker — it understands ``type``, ``required``,
``properties``, ``additionalProperties``, ``enum``, ``items``,
``minLength``, ``minItems``, ``minProperties`` and ``pattern`` — and fails
loudly on any other schema keyword so a constraint can never silently go
unchecked. It is not a schema-engine reimplementation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

SCHEMA_PATH = Path(__file__).parent / "schemas" / "source-profile.schema.json"

_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "title",
        "description",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "enum",
        "items",
        "minLength",
        "minItems",
        "minProperties",
        "pattern",
    }
)

_JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}

_EMPTY_MAP: Mapping[str, Any] = MappingProxyType({})


class ProfileValidationError(ValueError):
    """A profile (or the schema subset used to check it) is invalid."""


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    py = _JSON_TYPES.get(expected)
    if py is None:
        raise ProfileValidationError(f"unsupported schema type {expected!r}")
    return isinstance(value, py)


def _fail(path: str, msg: str) -> None:
    raise ProfileValidationError(f"{path or '<root>'}: {msg}")


def _check_schema(node: Mapping[str, Any], path: str) -> None:
    """Pre-pass over the whole schema tree: every keyword used anywhere must
    be one this validator implements — even in branches the current data
    never reaches."""
    unknown_keys = set(node) - _SUPPORTED_SCHEMA_KEYS
    if unknown_keys:
        raise ProfileValidationError(
            f"{path or '<root>'}: unsupported schema keyword(s) "
            f"{sorted(unknown_keys)} — extend the validator explicitly or "
            "simplify the schema"
        )
    for key, sub in node.get("properties", {}).items():
        _check_schema(sub, f"{path}.{key}" if path else key)
    items = node.get("items")
    if isinstance(items, dict):
        _check_schema(items, f"{path}[]")


def _validate(value: Any, node: Mapping[str, Any], path: str) -> None:
    if "type" in node:
        expected = node["type"]
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, t) for t in types):
            _fail(path, f"expected type {expected!r}, got {value!r}")

    if "enum" in node and value not in node["enum"]:
        _fail(path, f"{value!r} not in enum {node['enum']!r}")

    if isinstance(value, str):
        if "minLength" in node and len(value) < node["minLength"]:
            _fail(path, "string shorter than minLength")
        if "pattern" in node and not re.search(node["pattern"], value):
            _fail(path, f"{value!r} does not match /{node['pattern']}/")

    if isinstance(value, list):
        if "minItems" in node and len(value) < node["minItems"]:
            _fail(path, "array shorter than minItems")
        item_schema = node.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{i}]")

    if isinstance(value, dict):
        if "minProperties" in node and len(value) < node["minProperties"]:
            _fail(path, "object has fewer properties than minProperties")
        for key in node.get("required", ()):
            if key not in value:
                _fail(f"{path}.{key}" if path else key, "required property missing")
        props = node.get("properties", {})
        if node.get("additionalProperties") is False:
            extra = sorted(set(value) - set(props))
            if extra:
                _fail(path, f"unknown properties {extra}")
        for key, sub in props.items():
            if key in value:
                _validate(value[key], sub, f"{path}.{key}" if path else key)


def validate_profile(data: Mapping[str, Any], schema: Mapping | None = None) -> None:
    """Validate a parsed profile dict against the SourceProfile schema.

    Raises ProfileValidationError with a dotted path on the first problem.
    """
    if schema is None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    _check_schema(schema, "")
    _validate(data, schema, "")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class SourceProfile:
    """Validated, immutable per-source configuration (spec C.2).

    Jurisdiction is data, never a branch condition: a new source only needs
    code when its format requires a new provider/recipe.
    """

    source_id: str
    jurisdiction: str
    kind: str
    discovery: Mapping[str, Any]
    fetch: Mapping[str, Any]
    parse: Mapping[str, Any]
    versioning: Mapping[str, Any]
    reachability: Mapping[str, Any]
    change_detection: Mapping[str, Any] = field(
        default_factory=lambda: _EMPTY_MAP
    )
    provenance: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAP)
    refresh: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAP)


def load_profile(path: str | Path) -> SourceProfile:
    """Load and validate a ``*.profile.json`` file into a SourceProfile."""
    path = Path(path)
    if path.suffix != ".json":
        raise ProfileValidationError(
            f"{path.name}: profiles are plain JSON — use *.profile.json"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_profile(data)
    return SourceProfile(
        source_id=data["source_id"],
        jurisdiction=data["jurisdiction"],
        kind=data["kind"],
        discovery=_freeze(data["discovery"]),
        fetch=_freeze(data["fetch"]),
        parse=_freeze(data["parse"]),
        versioning=_freeze(data["versioning"]),
        reachability=_freeze(data["reachability"]),
        change_detection=_freeze(data.get("change_detection", {})),
        provenance=_freeze(data.get("provenance", {})),
        refresh=_freeze(data.get("refresh", {})),
    )
