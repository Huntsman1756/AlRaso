"""M10.1 Task 2 — SourceProfile schema + loader contract.

RED-first suite for ``pipeline/profiles.py`` +
``pipeline/schemas/source-profile.schema.json`` +
``pipeline/sources/bocyl.profile.json``.

Pinned contract (plan §7 fix 1): profiles are JSON, validated by a small
explicit stdlib structural validator — no PyYAML (axiom extra only), no JSON
Schema reimplementation. ``reachability`` is an expectation block
(``expected`` + ``fallback``), never a flat property.
"""

import inspect
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

import pipeline.profiles as profiles
from pipeline.profiles import SourceProfile, load_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE_JSON = ROOT / "pipeline" / "sources" / "bocyl.profile.json"
SCHEMA_JSON = ROOT / "pipeline" / "schemas" / "source-profile.schema.json"


def _minimal_profile() -> dict:
    return {
        "source_id": "test-src",
        "jurisdiction": "ES-CL",
        "kind": "gazette",
        "discovery": {"provider": "p", "recipe": "r"},
        "fetch": {
            "provider": "p",
            "recipe": "get_simple",
            "method": "GET",
            "formats": ["xml"],
            "content_marker": "<doc",
        },
        "parse": {"format": "xml"},
        "versioning": {"strategy": "gazette_publication"},
        "reachability": {"expected": {"foreign_ci": "REACHABLE"}},
    }


def test_bocyl_profile_loads():
    profile = load_profile(PROFILE_JSON)
    assert isinstance(profile, SourceProfile)
    assert profile.source_id == "bocyl"
    assert profile.jurisdiction == "ES-CL"
    assert profile.fetch["recipe"] == "get_simple"
    assert profile.fetch["content_marker"]
    assert isinstance(profile.reachability["expected"], Mapping)
    assert profile.reachability["expected"]["foreign_ci"] == "REACHABLE"


def test_profile_files_are_json_not_yaml():
    assert PROFILE_JSON.suffix == ".json"
    assert not PROFILE_JSON.with_suffix(".yaml").exists()
    assert not PROFILE_JSON.with_suffix(".yml").exists()


def test_no_pyyaml_dependency():
    src = inspect.getsource(profiles)
    assert "yaml" not in src.lower()


def test_missing_fetch_recipe_rejected():
    data = _minimal_profile()
    del data["fetch"]["recipe"]
    with pytest.raises(ValueError, match="fetch"):
        profiles.validate_profile(data)


def test_flat_reachability_rejected():
    data = _minimal_profile()
    data["reachability"] = {"foreign_ci": "REACHABLE"}  # no "expected" block
    with pytest.raises(ValueError, match="expected"):
        profiles.validate_profile(data)


def test_reachability_expected_enum_enforced():
    data = _minimal_profile()
    data["reachability"]["expected"]["foreign_ci"] = "MAYBE"
    with pytest.raises(ValueError, match="foreign_ci"):
        profiles.validate_profile(data)


def test_unknown_top_level_key_rejected():
    data = _minimal_profile()
    data["jurisdiction_notes"] = "x"
    with pytest.raises(ValueError, match="jurisdiction_notes"):
        profiles.validate_profile(data)


def test_missing_content_marker_rejected():
    data = _minimal_profile()
    del data["fetch"]["content_marker"]
    with pytest.raises(ValueError, match="content_marker"):
        profiles.validate_profile(data)


def test_validator_is_explicit_subset_not_jsonschema():
    """The validator must fail loudly on schema keywords it does not
    implement — it must never silently pass an unchecked constraint."""
    with pytest.raises(ValueError, match="ref|unsupported"):
        profiles.validate_profile(
            _minimal_profile(),
            schema={"type": "object", "properties": {"x": {"$ref": "#/$defs/y"}}},
        )


def test_profile_mapping_is_immutable():
    profile = load_profile(PROFILE_JSON)
    with pytest.raises(TypeError):
        profile.fetch["recipe"] = "tampered"


def test_schema_is_valid_json_and_covers_required_sections():
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    for section in ("discovery", "fetch", "parse", "versioning", "reachability"):
        assert section in schema["properties"]
        assert section in schema["required"]


def test_bocyl_profile_validates_against_schema_with_jsonschema():
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    doc = json.loads(PROFILE_JSON.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)


def test_no_jurisdiction_branching_in_loader():
    src = inspect.getsource(profiles)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
