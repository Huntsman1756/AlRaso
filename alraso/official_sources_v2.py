"""Strict structural validator for EvidencePacket v2.1.

Vendored JSON Schema (embedded as a module constant) and runtime validation
using only the Python standard library (json + re).  No external deps.

Contract:
  - All fields declared in the v2.1 schema are **required** exactly; no extra
    keys are allowed (additionalProperties=false everywhere).
  - Known enum values are enforced verbatim; any unknown value → rejection.
  - SHA-256 fields must be 64-char hex lowercase strings.
  - IDs that are hex identifiers (packet_id, evidence_id) must be 64-char
    hex lowercase.
  - Date fields use YYYY-MM-DD; RFC-3339 UTC datetime fields use the
    pattern from the schema.
  - Consistency: artifact refs inside blocks must reference an artifact_id
    present in the artifacts array.
  - review_status must be one of the three known values.
  - integrity_status must be one of the five known values.
  - block_id_status must be one of the three known values.
  - publication_date_status, effective_from_status, effective_to_status all
    use their declared enum sets.

Rejection is always via a raised exception (EvidencePacketValidationError)
that carries structured reasons — there are never silent defaults.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

# ---- vendored JSON Schema (SHA-256 anchor) ---------------------------------

# This is the EvidencePacket v2 schema as published by official-sources-esp.
# The constant below must match the SHA-256 of the canonical file.
# SHA-256 of the embedded schema (vendored from official-sources-esp)
VENDOR_SCHEMA_SHA256 = (
    "eea5fd0914a3242208c21f5b6c2f62ab6798f8ed908237b6d358de95e9cab665"
)

SCHEMA_JSON = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://official-sources.local/schemas/evidence-packet-v2.schema.json",
  "title": "EvidencePacket v2",
  "description": "Stable, auditable evidence packet for official-source evidence produced by official-sources-esp. Version 2.1 contract: adds consumer-independent evidence_id; packet_id is the representation identity. additionalProperties is false everywhere: unknown fields are contract violations.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "packet_id",
    "evidence_id",
    "provenance",
    "version",
    "temporal",
    "artifacts",
    "blocks",
    "review"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "2.1"
    },
    "packet_id": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$",
      "description": "Representation identity: SHA-256 of the canonical JSON of the packet excluding packet_id, generator, and generated_at."
    },
    "evidence_id": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$",
      "description": "Consumer-independent identity of the observed evidence."
    },
    "provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source_code",
        "source_name",
        "jurisdiction",
        "resource_type",
        "official_identifier",
        "official_url",
        "publication_date_status"
      ],
      "properties": {
        "source_code": { "type": "string", "minLength": 1 },
        "source_name": { "type": "string", "minLength": 1 },
        "jurisdiction": { "type": "string", "enum": ["state", "autonomous", "provincial", "local", "european", "other"] },
        "region_code": { "type": ["string", "null"] },
        "resource_type": {
          "type": "string",
          "enum": ["official_document", "consolidated_law", "consolidated_law_block", "grant_call", "registry_entry"]
        },
        "official_identifier": { "type": "string", "minLength": 1 },
        "official_url": {
          "type": "string",
          "pattern": "^https://",
          "description": "Official URL the evidence comes from."
        },
        "title": { "type": ["string", "null"] },
        "document_type": { "type": ["string", "null"] },
        "publisher": { "type": ["string", "null"] },
        "publication_date": {
          "type": ["string", "null"],
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "publication_date_status": {
          "type": "string",
          "enum": ["known", "unknown", "withheld_by_source"]
        }
      }
    },
    "version": {
      "type": "object",
      "additionalProperties": false,
      "required": ["version_id", "version_date_status"],
      "properties": {
        "version_id": { "type": "string", "minLength": 1 },
        "version_identifier": { "type": ["string", "null"] },
        "version_date": {
          "type": ["string", "null"],
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "version_date_status": {
          "type": "string",
          "enum": ["known", "unknown"]
        },
        "consolidation_status": { "type": ["string", "null"] }
      }
    },
    "temporal": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "effective_from_status",
        "effective_to_status",
        "retrieved_at",
        "recorded_at"
      ],
      "properties": {
        "effective_from": {
          "type": ["string", "null"],
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "effective_from_status": {
          "type": "string",
          "enum": ["known", "unknown"]
        },
        "effective_to": {
          "type": ["string", "null"],
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "effective_to_status": {
          "type": "string",
          "enum": ["open", "known", "unknown"]
        },
        "retrieved_at": { "$ref": "#/$defs/rfc3339_utc" },
        "recorded_at": { "$ref": "#/$defs/rfc3339_utc" }
      }
    },
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "artifact_id",
          "artifact_type",
          "official_url",
          "source_snapshot_hash",
          "integrity_status",
          "local_available"
        ],
        "properties": {
          "artifact_id": { "type": "string", "minLength": 1 },
          "artifact_type": {
            "type": "string",
            "enum": ["xml", "html", "pdf", "json", "raw_api_response", "text"]
          },
          "official_url": { "type": "string", "pattern": "^https://" },
          "media_type": { "type": ["string", "null"] },
          "size_bytes": { "type": ["integer", "null"], "minimum": 0 },
          "artifact_hash": { "$ref": "#/$defs/sha256_hex" },
          "source_snapshot_hash": { "$ref": "#/$defs/sha256_hex" },
          "previous_hash": { "$ref": "#/$defs/sha256_hex_or_null" },
          "integrity_status": {
            "type": "string",
            "enum": [
              "ok",
              "changed_since_previous",
              "missing_artifact",
              "unverifiable",
              "metadata_only"
            ]
          },
          "last_integrity_check_at": {
            "oneOf": [{ "$ref": "#/$defs/rfc3339_utc" }, { "type": "null" }]
          },
          "local_available": { "type": "boolean" }
        }
      }
    },
    "blocks": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["block_id", "block_id_status", "block_type"],
        "properties": {
          "block_id": { "type": "string", "minLength": 1 },
          "block_id_status": {
            "type": "string",
            "enum": ["official", "local", "unknown"]
          },
          "block_path": { "type": ["string", "null"], "pattern": "^[^/]+(/[^/]+)*$" },
          "block_type": {
            "type": "string",
            "enum": [
              "preamble", "article", "additional_provision",
              "transitional_provision", "derogatory_provision",
              "final_provision", "annex", "summary", "index",
              "full_text", "section", "unknown"
            ]
          },
          "block_identifier": { "type": ["string", "null"] },
          "block_title": { "type": ["string", "null"] },
          "content_sha256": { "$ref": "#/$defs/sha256_hex_or_null" },
          "order_index": { "type": ["integer", "null"], "minimum": 0 },
          "artifact_id": { "type": ["string", "null"] },
          "official_url": {
            "oneOf": [{ "type": "string", "pattern": "^https://" }, { "type": "null" }]
          }
        }
      }
    },
    "review": {
      "type": "object",
      "additionalProperties": false,
      "required": ["review_status"],
      "properties": {
        "review_status": {
          "type": "string",
          "enum": ["not_reviewed", "evidence_reviewed", "needs_more_evidence"]
        },
        "reviewed_at": {
          "oneOf": [{ "$ref": "#/$defs/rfc3339_utc" }, { "type": "null" }]
        },
        "reviewed_by": { "type": ["string", "null"] },
        "review_notes": { "type": ["string", "null"] }
      }
    },
    "consumer_context": {
      "oneOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "consumer": { "type": ["string", "null"] },
            "case_ref": { "type": ["string", "null"] }
          }
        },
        { "type": "null" }
      ]
    },
    "generator": {
      "oneOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["tool"],
          "properties": {
            "tool": { "type": "string", "minLength": 1 },
            "version": { "type": ["string", "null"] }
          }
        },
        { "type": "null" }
      ]
    },
    "generated_at": {
      "oneOf": [{ "$ref": "#/$defs/rfc3339_utc" }, { "type": "null" }]
    }
  },
  "$defs": {
    "sha256_hex": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$"
    },
    "sha256_hex_or_null": {
      "oneOf": [
        { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        { "type": "null" }
      ]
    },
    "rfc3339_utc": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?Z$"
    }
  }
}"""


# ---- compile patterns once --------------------------------------------------

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_OR_NULL_RE = re.compile(r"^[0-9a-f]{64}$")  # value is None or sha256
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HTTPS_RE = re.compile(r"^https://")
_BLOCK_PATH_RE = re.compile(r"^[^/]+(/[^/]+)*$")


# ---- data structures --------------------------------------------------------

@dataclass
class ValidationResult:
    """Immutable validation result: either ok or a list of failure reasons."""

    ok: bool
    reasons: list[str] = field(default_factory=list)

    @classmethod
    def ok_result(cls) -> "ValidationResult":
        return cls(ok=True)

    @classmethod
    def fail_result(cls, reason: str) -> "ValidationResult":
        return cls(ok=False, reasons=[reason])

    @classmethod
    def accumulate(cls, results: list["ValidationResult"]) -> "ValidationResult":
        failed = [r for r in results if not r.ok]
        if not failed:
            return cls(ok=True)
        all_reasons = []
        for r in failed:
            all_reasons.extend(r.reasons)
        return cls(ok=False, reasons=all_reasons)


@dataclass
class PacketPayload:
    """Parsed and validated packet payload for downstream use."""

    schema_version: str
    packet_id: str
    evidence_id: str
    provenance: dict[str, Any]
    version: dict[str, Any]
    temporal: dict[str, Any]
    artifacts: list[dict[str, Any]]
    blocks: list[dict[str, Any]]
    review: dict[str, Any]
    consumer_context: dict[str, Any] | None
    generator: dict[str, Any] | None
    generated_at: str | None

    # Derived convenience accessors
    @property
    def block_ids(self) -> list[str]:
        return [b["block_id"] for b in self.blocks]

    @property
    def artifact_ids(self) -> set[str]:
        return {a["artifact_id"] for a in self.artifacts}


# ---- validation engine ------------------------------------------------------

class EvidencePacketValidationError(Exception):
    """Raised when a packet fails structural validation."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("EvidencePacket validation failed: " + "; ".join(reasons))


def _check_sha256(value: Any, field_path: str) -> ValidationResult:
    if value is None:
        return ValidationResult.fail_result(f"{field_path}: null not allowed here")
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        return ValidationResult.fail_result(
            f"{field_path}: expected 64-char lowercase hex SHA-256, got {value!r}")
    return ValidationResult.ok_result()


def _check_sha256_or_null(value: Any, field_path: str) -> ValidationResult:
    if value is None:
        return ValidationResult.ok_result()
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        return ValidationResult.fail_result(
            f"{field_path}: expected SHA-256 hex or null, got {value!r}")
    return ValidationResult.ok_result()


def _check_rfc3339(value: Any, field_path: str) -> ValidationResult:
    if value is None:
        return ValidationResult.fail_result(f"{field_path}: null not allowed here")
    if not isinstance(value, str) or not _DATETIME_RE.match(value):
        return ValidationResult.fail_result(
            f"{field_path}: expected RFC-3339 UTC datetime, got {value!r}")
    return ValidationResult.ok_result()


def _check_date_or_null(value: Any, field_path: str) -> ValidationResult:
    if value is None:
        return ValidationResult.ok_result()
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return ValidationResult.fail_result(
            f"{field_path}: expected YYYY-MM-DD date or null, got {value!r}")
    return ValidationResult.ok_result()


def _check_https(value: Any, field_path: str) -> ValidationResult:
    if value is None:
        return ValidationResult.fail_result(f"{field_path}: null not allowed here")
    if not isinstance(value, str) or not _HTTPS_RE.match(value):
        return ValidationResult.fail_result(
            f"{field_path}: expected https:// URL, got {value!r}")
    return ValidationResult.ok_result()


def _check_non_empty_str(value: Any, field_path: str) -> ValidationResult:
    if not isinstance(value, str) or not value:
        return ValidationResult.fail_result(
            f"{field_path}: expected non-empty string, got {value!r}")
    return ValidationResult.ok_result()


def _check_string_or_null(value: Any, field_path: str) -> ValidationResult:
    if value is None:
        return ValidationResult.ok_result()
    if not isinstance(value, str):
        return ValidationResult.fail_result(
            f"{field_path}: expected string or null, got {type(value).__name__}")
    return ValidationResult.ok_result()


def _check_enum(value: Any, field_path: str, allowed: set[str]) -> ValidationResult:
    if value not in allowed:
        return ValidationResult.fail_result(
            f"{field_path}: expected one of {sorted(allowed)}, got {value!r}")
    return ValidationResult.ok_result()


def _check_boolean(value: Any, field_path: str) -> ValidationResult:
    if not isinstance(value, bool):
        return ValidationResult.fail_result(
            f"{field_path}: expected boolean, got {type(value).__name__}")
    return ValidationResult.ok_result()


def _check_optional_integer(value: Any, field_path: str, minimum: int = 0) -> ValidationResult:
    if value is None:
        return ValidationResult.ok_result()
    if isinstance(value, bool) or not isinstance(value, int):
        return ValidationResult.fail_result(
            f"{field_path}: expected integer or null, got {type(value).__name__}")
    if value < minimum:
        return ValidationResult.fail_result(
            f"{field_path}: expected >= {minimum}, got {value}")
    return ValidationResult.ok_result()


def _check_optional_string_pattern(value: Any, field_path: str,
                                    pattern: re.Pattern[str]) -> ValidationResult:
    if value is None:
        return ValidationResult.ok_result()
    if not isinstance(value, str) or not pattern.match(value):
        return ValidationResult.fail_result(
            f"{field_path}: expected pattern {pattern.pattern}, got {value!r}")
    return ValidationResult.ok_result()


def _check_unknown_top_level_keys(packet: dict[str, Any]) -> ValidationResult:
    """Fail-closed: any key not in the schema root is a violation."""
    known_top = frozenset({
        "schema_version", "packet_id", "evidence_id",
        "provenance", "version", "temporal",
        "artifacts", "blocks", "review",
        "consumer_context", "generator", "generated_at",
    })
    unknown = set(packet) - known_top
    if unknown:
        return ValidationResult.fail_result(
            f"unknown top-level keys: {sorted(unknown)}")
    return ValidationResult.ok_result()


def _check_unknown_keys(data: dict[str, Any], known_keys: frozenset,
                         prefix: str) -> ValidationResult:
    unknown = set(data) - known_keys
    if unknown:
        return ValidationResult.fail_result(
            f"{prefix}: unknown keys: {sorted(unknown)}")
    return ValidationResult.ok_result()


def _validate_provenance(data: dict[str, Any]) -> ValidationResult:
    known_keys = frozenset({
        "source_code", "source_name", "jurisdiction", "region_code",
        "resource_type", "official_identifier", "official_url",
        "title", "document_type", "publisher",
        "publication_date", "publication_date_status",
    })
    result = _check_unknown_keys(data, known_keys, "provenance")
    if not result.ok:
        return result

    reasons: list[str] = []

    r1 = _check_non_empty_str(data.get("source_code"), "provenance.source_code")
    r2 = _check_non_empty_str(data.get("source_name"), "provenance.source_name")
    r3 = _check_enum(data.get("jurisdiction"), "provenance.jurisdiction",
                     {"state", "autonomous", "provincial", "local", "european", "other"})
    r4 = _check_string_or_null(data.get("region_code"), "provenance.region_code")
    r5 = _check_enum(data.get("resource_type"), "provenance.resource_type",
                     {"official_document", "consolidated_law", "consolidated_law_block",
                      "grant_call", "registry_entry"})
    r6 = _check_non_empty_str(data.get("official_identifier"),
                              "provenance.official_identifier")
    r7 = _check_https(data.get("official_url"), "provenance.official_url")
    r8 = _check_string_or_null(data.get("title"), "provenance.title")
    r9 = _check_string_or_null(data.get("document_type"), "provenance.document_type")
    r10 = _check_string_or_null(data.get("publisher"), "provenance.publisher")
    r11 = _check_date_or_null(data.get("publication_date"),
                              "provenance.publication_date")
    r12 = _check_enum(data.get("publication_date_status"),
                      "provenance.publication_date_status",
                      {"known", "unknown", "withheld_by_source"})

    for r in (r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12):
        if not r.ok:
            reasons.extend(r.reasons)

    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_version(data: dict[str, Any]) -> ValidationResult:
    known_keys = frozenset({
        "version_id", "version_identifier", "version_date",
        "version_date_status", "consolidation_status",
    })
    result = _check_unknown_keys(data, known_keys, "version")
    if not result.ok:
        return result

    reasons: list[str] = []
    r1 = _check_non_empty_str(data.get("version_id"), "version.version_id")
    r2 = _check_string_or_null(data.get("version_identifier"),
                               "version.version_identifier")
    r3 = _check_date_or_null(data.get("version_date"), "version.version_date")
    r4 = _check_enum(data.get("version_date_status"),
                     "version.version_date_status",
                     {"known", "unknown"})
    r5 = _check_string_or_null(data.get("consolidation_status"),
                               "version.consolidation_status")
    for r in (r1, r2, r3, r4, r5):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_temporal(data: dict[str, Any]) -> ValidationResult:
    known_keys = frozenset({
        "effective_from", "effective_from_status",
        "effective_to", "effective_to_status",
        "retrieved_at", "recorded_at",
    })
    result = _check_unknown_keys(data, known_keys, "temporal")
    if not result.ok:
        return result

    reasons: list[str] = []
    r1 = _check_date_or_null(data.get("effective_from"), "temporal.effective_from")
    r2 = _check_enum(data.get("effective_from_status"),
                     "temporal.effective_from_status",
                     {"known", "unknown"})
    r3 = _check_date_or_null(data.get("effective_to"), "temporal.effective_to")
    r4 = _check_enum(data.get("effective_to_status"),
                     "temporal.effective_to_status",
                     {"open", "known", "unknown"})
    r5 = _check_rfc3339(data.get("retrieved_at"), "temporal.retrieved_at")
    r6 = _check_rfc3339(data.get("recorded_at"), "temporal.recorded_at")
    for r in (r1, r2, r3, r4, r5, r6):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_artifact(data: dict[str, Any]) -> ValidationResult:
    known_keys = frozenset({
        "artifact_id", "artifact_type", "official_url",
        "media_type", "size_bytes", "artifact_hash",
        "source_snapshot_hash", "previous_hash",
        "integrity_status", "last_integrity_check_at",
        "local_available",
    })
    result = _check_unknown_keys(data, known_keys, "artifact")
    if not result.ok:
        return result

    reasons: list[str] = []
    r1 = _check_non_empty_str(data.get("artifact_id"), "artifact.artifact_id")
    r2 = _check_enum(data.get("artifact_type"), "artifact.artifact_type",
                     {"xml", "html", "pdf", "json", "raw_api_response", "text"})
    r3 = _check_https(data.get("official_url"), "artifact.official_url")
    r4 = _check_string_or_null(data.get("media_type"), "artifact.media_type")
    r5 = _check_optional_integer(data.get("size_bytes"), "artifact.size_bytes", 0)
    r6 = _check_sha256_or_null(data.get("artifact_hash"), "artifact.artifact_hash")
    r7 = _check_sha256(data.get("source_snapshot_hash"), "artifact.source_snapshot_hash")
    r8 = _check_sha256_or_null(data.get("previous_hash"), "artifact.previous_hash")
    r9 = _check_enum(data.get("integrity_status"), "artifact.integrity_status",
                     {"ok", "changed_since_previous", "missing_artifact",
                      "unverifiable", "metadata_only"})
    r10_val = data.get("last_integrity_check_at")
    r10 = ValidationResult.ok_result() if r10_val is None else _check_rfc3339(
        r10_val, "artifact.last_integrity_check_at")
    r11 = _check_boolean(data.get("local_available"), "artifact.local_available")
    for r in (r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_block(data: dict[str, Any]) -> ValidationResult:
    known_keys = frozenset({
        "block_id", "block_id_status", "block_path", "block_type",
        "block_identifier", "block_title", "content_sha256",
        "order_index", "artifact_id", "official_url",
    })
    result = _check_unknown_keys(data, known_keys, "block")
    if not result.ok:
        return result

    reasons: list[str] = []
    r1 = _check_non_empty_str(data.get("block_id"), "block.block_id")
    r2 = _check_enum(data.get("block_id_status"), "block.block_id_status",
                     {"official", "local", "unknown"})
    r3 = _check_optional_string_pattern(data.get("block_path"),
                                        "block.block_path", _BLOCK_PATH_RE)
    r4 = _check_enum(data.get("block_type"), "block.block_type",
                     {"preamble", "article", "additional_provision",
                      "transitional_provision", "derogatory_provision",
                      "final_provision", "annex", "summary", "index",
                      "full_text", "section", "unknown"})
    r5 = _check_string_or_null(data.get("block_identifier"),
                               "block.block_identifier")
    r6 = _check_string_or_null(data.get("block_title"), "block.block_title")
    r7 = _check_sha256_or_null(data.get("content_sha256"), "block.content_sha256")
    r8 = _check_optional_integer(data.get("order_index"), "block.order_index", 0)
    r9 = _check_string_or_null(data.get("artifact_id"), "block.artifact_id")
    r10_val = data.get("official_url")
    r10 = ValidationResult.ok_result() if r10_val is None else _check_https(
        r10_val, "block.official_url")
    for r in (r1, r2, r3, r4, r5, r6, r7, r8, r9, r10):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_review(data: dict[str, Any]) -> ValidationResult:
    known_keys = frozenset({
        "review_status", "reviewed_at", "reviewed_by", "review_notes",
    })
    result = _check_unknown_keys(data, known_keys, "review")
    if not result.ok:
        return result

    reasons: list[str] = []
    r1 = _check_enum(data.get("review_status"), "review.review_status",
                     {"not_reviewed", "evidence_reviewed", "needs_more_evidence"})
    r2_val = data.get("reviewed_at")
    r2 = ValidationResult.ok_result() if r2_val is None else _check_rfc3339(
        r2_val, "review.reviewed_at")
    r3 = _check_string_or_null(data.get("reviewed_by"), "review.reviewed_by")
    r4 = _check_string_or_null(data.get("review_notes"), "review.review_notes")
    for r in (r1, r2, r3, r4):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_consumer_context(data: dict[str, Any] | None) -> ValidationResult:
    if data is None:
        return ValidationResult.ok_result()
    if not isinstance(data, dict):
        return ValidationResult.fail_result(
            "consumer_context: expected object or null")
    known_keys = frozenset({"consumer", "case_ref"})
    result = _check_unknown_keys(data, known_keys, "consumer_context")
    if not result.ok:
        return result
    r1 = _check_string_or_null(data.get("consumer"), "consumer_context.consumer")
    r2 = _check_string_or_null(data.get("case_ref"), "consumer_context.case_ref")
    reasons = []
    for r in (r1, r2):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_generator(data: dict[str, Any] | None) -> ValidationResult:
    if data is None:
        return ValidationResult.ok_result()
    if not isinstance(data, dict):
        return ValidationResult.fail_result(
            "generator: expected object or null")
    known_keys = frozenset({"tool", "version"})
    result = _check_unknown_keys(data, known_keys, "generator")
    if not result.ok:
        return result
    r1 = _check_non_empty_str(data.get("tool"), "generator.tool")
    r2 = _check_string_or_null(data.get("version"), "generator.version")
    reasons = []
    for r in (r1, r2):
        if not r.ok:
            reasons.extend(r.reasons)
    return ValidationResult(ok=not reasons, reasons=reasons)


def _validate_generated_at(value: Any) -> ValidationResult:
    if value is None:
        return ValidationResult.ok_result()
    return _check_rfc3339(value, "generated_at")


def _validate_consistency(packet: dict[str, Any]) -> ValidationResult:
    """Cross-field consistency checks."""
    reasons: list[str] = []

    # Block artifact_id refs must exist in artifacts
    blocks_data = packet.get("blocks")
    artifacts_data = packet.get("artifacts")
    if isinstance(blocks_data, list) and isinstance(artifacts_data, list):
        block_artifacts = {b.get("artifact_id") for b in blocks_data
                           if isinstance(b, dict) and b.get("artifact_id") is not None}
        artifact_ids = {a["artifact_id"] for a in artifacts_data if isinstance(a, dict)}
        for bid in block_artifacts:
            if bid not in artifact_ids:
                reasons.append(
                    f"block references artifact_id {bid!r} not found in artifacts array")

    return ValidationResult(ok=not reasons, reasons=reasons)


# ---- public API -------------------------------------------------------------

def validate_evidence_packet_v2_1(packet: dict[str, Any]) -> ValidationResult:
    """Validate an EvidencePacket v2.1 dict against the strict schema.

    Raises ``EvidencePacketValidationError`` if validation fails, with
    structured reasons in the exception.
    """
    if not isinstance(packet, dict):
        raise EvidencePacketValidationError(
            [f"expected object, got {type(packet).__name__}"])

    results: list[ValidationResult] = []

    # Top-level key check (additionalProperties=false)
    results.append(_check_unknown_top_level_keys(packet))

    # Required fields present
    required_top = ["schema_version", "packet_id", "evidence_id",
                    "provenance", "version", "temporal", "artifacts", "blocks", "review"]
    for key in required_top:
        if key not in packet:
            results.append(ValidationResult.fail_result(f"missing required field: {key}"))
            # If a required parent is missing, skip sub-validation
            continue

    # schema_version must be exactly "2.1"
    results.append(_check_enum(packet.get("schema_version", ""),
                              "schema_version", {"2.1"}))

    # packet_id: 64-char hex
    results.append(_check_sha256(packet.get("packet_id"), "packet_id"))

    # evidence_id: 64-char hex
    results.append(_check_sha256(packet.get("evidence_id"), "evidence_id"))

    # Provenance
    results.append(_validate_provenance(packet.get("provenance", {})))

    # Version
    results.append(_validate_version(packet.get("version", {})))

    # Temporal
    results.append(_validate_temporal(packet.get("temporal", {})))

    # Artifacts (array of objects)
    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, list):
        results.append(ValidationResult.fail_result("artifacts: expected array"))
    else:
        for i, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                results.append(ValidationResult.fail_result(
                    f"artifacts[{i}]: expected object"))
                continue
            r = _validate_artifact(artifact)
            if not r.ok:
                results.append(ValidationResult.fail_result(
                    f"artifacts[{i}]: {'; '.join(r.reasons)}"))

    # Blocks (array of objects)
    blocks = packet.get("blocks", [])
    if not isinstance(blocks, list):
        results.append(ValidationResult.fail_result("blocks: expected array"))
    else:
        for i, block in enumerate(blocks):
            if not isinstance(block, dict):
                results.append(ValidationResult.fail_result(
                    f"blocks[{i}]: expected object"))
                continue
            r = _validate_block(block)
            if not r.ok:
                results.append(ValidationResult.fail_result(
                    f"blocks[{i}]: {'; '.join(r.reasons)}"))

    # Review
    results.append(_validate_review(packet.get("review", {})))

    # Optional fields
    results.append(_validate_consumer_context(packet.get("consumer_context")))
    results.append(_validate_generator(packet.get("generator")))
    results.append(_validate_generated_at(packet.get("generated_at")))

    # Cross-field consistency
    results.append(_validate_consistency(packet))

    aggregated = ValidationResult.accumulate(results)
    if not aggregated.ok:
        raise EvidencePacketValidationError(aggregated.reasons)
    return aggregated


def parse_validated_packet(packet: dict[str, Any]) -> PacketPayload:
    """Validate and return a ready-to-use PacketPayload."""
    validate_evidence_packet_v2_1(packet)
    return PacketPayload(
        schema_version=packet["schema_version"],
        packet_id=packet["packet_id"],
        evidence_id=packet["evidence_id"],
        provenance=packet["provenance"],
        version=packet["version"],
        temporal=packet["temporal"],
        artifacts=packet["artifacts"],
        blocks=packet["blocks"],
        review=packet["review"],
        consumer_context=packet.get("consumer_context"),
        generator=packet.get("generator"),
        generated_at=packet.get("generated_at"),
    )


def validate_schema_json_sha256(schema_json: str) -> ValidationResult:
    """Verify that the provided schema JSON matches the vendored SHA-256."""
    actual = hashlib.sha256(schema_json.encode("utf-8")).hexdigest()
    if actual != VENDOR_SCHEMA_SHA256:
        return ValidationResult.fail_result(
            f"schema SHA-256 mismatch: expected {VENDOR_SCHEMA_SHA256}, got {actual}")
    return ValidationResult.ok_result()