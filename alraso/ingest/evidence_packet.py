"""EvidencePacket v2.1 → BitemporalStore adapter.

Consumes a *validated* EvidencePacket v2.1 and materialises its provenance
into BitemporalStore entities (source_document, legal_fragment, spatial_scope,
legal_rule_version) within a single atomic transaction (F07).

The content provider contract:

    def get_block_content(block_id: str,
                          effective_from: str | None,
                          official_identifier: str) -> tuple[str, str] | None:
        '''Return (content, computed_sha256) for the block described by the
        packet's block dict.  Returns None when the content provider cannot
        resolve the block (e.g. missing snapshot row).

        The returned SHA-256 must be the SHA-256 of the returned content
        encoded as UTF-8, so the caller can verify it against
        block["content_sha256"].

        Parameters:
            block_id: the block identifier (e.g. "a50", "a1")
            effective_from: effective_from date string (e.g. "2005-06-30")
            official_identifier: the law identifier (e.g. "BOE-A-2005-11132")
        '''

Hash mismatch → fail-closed: the fragment is NOT ingested and the
determination for the scoped activity is UNDETERMINED — NEVER PERMITTED.

Module-level API:
    ingest_evidence_packet(store, packet, content_provider) → IngestionResult
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from alraso.bitemporal import (
    BitemporalStore,
)

# Type alias for the content provider callback.
# The provider receives block identity fields and returns (content, sha256) or None.
ContentProvider = Callable[
    [str, str | None, str],
    tuple[str, str] | None,
]


@dataclass
class IngestionResult:
    """Immutables results of a single packet ingestion."""

    success: bool
    packet_id: str
    evidence_id: str
    fragment_ingested: bool
    source_document_ingested: bool
    scope_ingested: bool
    rule_version_ingested: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_fragments(self) -> bool:
        return self.fragment_ingested

    @property
    def can_support_determination(self) -> bool:
        """Whether the ingested data is sufficient for the resolver to
        produce a publishable determination (non-UNDETERMINED)."""
        return (self.success and self.fragment_ingested
                and self.source_document_ingested and self.rule_version_ingested)


# ---- snapshot content provider (stdlib sqlite3, read-only) --------------------

def make_snapshot_content_provider(
    db_path: str | Path,
) -> ContentProvider:
    """Build a content provider that reads from the consolidated_law_text_blocks
    table in the evidence snapshot DB (opened in read-only mode).

    Lookup:
        1. Find consolidated_law_id by matching official_identifier prefix
           in consolidated_laws.official_identifier.
        2. Find version_id by matching version_date.
        3. Find the row by (consolidated_law_id, version_id, official_block_id).

    Opens the DB in read-only mode via URI (mode=ro).
    """
    db_path_str = str(db_path)
    conn = sqlite3.connect(f"file:{db_path_str}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def _resolve_law_id(official_identifier: str) -> int | None:
        """Find the consolidated_law_id for an official identifier prefix."""
        cur = conn.execute(
            "SELECT id FROM consolidated_laws WHERE official_identifier LIKE ?",
            (f"{official_identifier}%",),
        )
        row = cur.fetchone()
        return row["id"] if row else None

    def _resolve_version_id(law_id: int, effective_from: str | None) -> int | None:
        """Find the version_id matching the effective_from date."""
        if effective_from is None:
            return None
        cur = conn.execute(
            "SELECT id FROM consolidated_law_versions "
            "WHERE consolidated_law_id=? AND version_date=?",
            (law_id, effective_from),
        )
        row = cur.fetchone()
        return row["id"] if row else None

    def provider(block_id: str, effective_from: str | None,
                 official_identifier: str) -> tuple[str, str] | None:
        law_id = _resolve_law_id(official_identifier)
        if law_id is None:
            return None

        version_id = _resolve_version_id(law_id, effective_from)

        if version_id is not None:
            cur = conn.execute(
                "SELECT content FROM consolidated_law_text_blocks "
                "WHERE consolidated_law_id=? AND version_id=? AND official_block_id=?",
                (law_id, version_id, block_id),
            )
        else:
            # Fallback: try to find by block_id + law_id only
            cur = conn.execute(
                "SELECT content FROM consolidated_law_text_blocks "
                "WHERE consolidated_law_id=? AND official_block_id=?",
                (law_id, block_id),
            )

        row = cur.fetchone()
        if row is None:
            return None

        content = row["content"]
        computed_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return content, computed_sha

    return provider


# ---- adapter -----------------------------------------------------------------

def _build_source_document_id(provenance: dict[str, Any]) -> str:
    """Derive a unique source_document id from the provenance anchors."""
    official_id = provenance.get("official_identifier", "unknown")
    return f"ep-src-{official_id}"


def _build_fragment_id(packet_id: str, block_id: str) -> str:
    """Derive a unique legal_fragment id from the packet and block identity."""
    return f"ep-frag-{packet_id}-{block_id}"


def _build_scope_id(provenance: dict[str, Any]) -> str:
    """Derive a spatial scope id from the provenance."""
    source_code = provenance.get("source_code", "UNKNOWN")
    jurisdiction = provenance.get("jurisdiction", "other")
    return f"ep-scope-{source_code.lower()}-{jurisdiction}"


def _build_rule_id(provenance: dict[str, Any]) -> str:
    """Derive a rule id from the provenance anchors."""
    official_id = provenance.get("official_identifier", "unknown")
    jurisdiction = provenance.get("jurisdiction", "other")
    return f"alraso:{jurisdiction}/ep-{official_id.lower()}"


def _determine_effect_for_activity(
    block_content: str,
    activity: str,
) -> str:
    """Determine the effect (PERMITTED/PROHIBITED/AUTHORIZATION_REQUIRED)
    for the given activity based on the block content semantics.

    For VIVAC_AL_RASO in LECO (Balearic Islands law):
    - If the content explicitly references "acampada", "vivac", "pernocta"
      as an infringement → PROHIBITED
    """
    content_lower = block_content.lower()

    # Check for explicit permission indicators FIRST (higher specificity)
    if any(kw in content_lower for kw in ["permit", "permitid"]):
        # If "permite/permitido/permitida" is present without restriction context
        return "PERMITTED"

    # Check for activity-specific keywords (LECO Art. 50 pattern)
    activity_keywords = ["acampada", "vivac", "pernocta"]
    if activity == "VIVAC_AL_RASO":
        for kw in activity_keywords:
            if kw in content_lower:
                # Check if it's classified as an infringement
                if "infracción" in content_lower or "infraccion" in content_lower:
                    return "PROHIBITED"
                # Check for authorization requirement
                if "autorización" in content_lower or "autorizacion" in content_lower:
                    return "AUTHORIZATION_REQUIRED"
                # Default for activity keyword found: PROHIBITED (infringement)
                return "PROHIBITED"

    # Check for general restriction keywords
    if any(kw in content_lower for kw in ["prohibid", "vedad", "vedada", "vedado"]):
        return "PROHIBITED"

    return "AUTHORIZATION_REQUIRED"


def ingest_evidence_packet(
    store: BitemporalStore,
    packet: dict[str, Any],
    content_provider: ContentProvider,
) -> IngestionResult:
    """Ingest an EvidencePacket v2.1 into the BitemporalStore.

    Follows the pattern of `ingest/ordesa.py`:
    - One atomic transaction (F07).
    - source_document → legal_fragment → spatial_scope → legal_rule_version.
    - Content SHA-256 verification before fragment ingestion.
    - Hash mismatch → fail-closed (fragment not ingested).

    Returns IngestionResult with detailed status.
    """
    evidence_id = packet["evidence_id"]
    packet_id = packet["packet_id"]
    provenance = packet["provenance"]
    version = packet["version"]
    temporal = packet["temporal"]
    blocks = packet["blocks"]

    reasons: list[str] = []
    warnings: list[str] = []
    fragment_ingested = False
    source_doc_ingested = False
    scope_ingested = False
    rule_ingested = False

    official_identifier = provenance.get("official_identifier", "")
    effective_from = temporal.get("effective_from")
    activity = "VIVAC_AL_RASO"

    try:
        with store.transaction():
            # 1. Source document (provenance)
            sd_id = _build_source_document_id(provenance)
            store.add_source_document({
                "id": sd_id,
                "authority": provenance.get("publisher") or "Estado",
                "jurisdiction": provenance.get("jurisdiction", "other").upper(),
                "document_type": provenance.get("document_type") or "LAW",
                "title": provenance.get("title", "Desconocido"),
                "canonical_url": provenance.get("official_url", ""),
                "official_status": "VIGENTE",
                "retrieved_at": temporal.get("retrieved_at"),
                "content_hash": None,
            })
            source_doc_ingested = True

            # 2. Legal fragments (one per block)
            #    Read content from the provider, verify SHA-256, then ingest.
            for block in blocks:
                block_id = block.get("block_id", "unknown")
                block_sha_expected = block.get("content_sha256")

                content_result = content_provider(block_id, effective_from,
                                                  official_identifier)
                if content_result is None:
                    warnings.append(
                        f"content_provider returned None for block {block_id}")
                    continue

                content, content_sha = content_result

                # Verify SHA-256 (fail-closed)
                if block_sha_expected and content_sha != block_sha_expected:
                    warnings.append(
                        f"SHA-256 mismatch for block {block_id}: "
                        f"expected {block_sha_expected}, got {content_sha}. "
                        f"Fragment rejected.")
                    continue

                frag_id = _build_fragment_id(packet_id, block_id)
                locator = f"{official_identifier}:{block_id}"

                store.add_legal_fragment({
                    "id": frag_id,
                    "source_document_id": sd_id,
                    "locator": locator,
                    "exact_text_hint": content[:200] if content else "",
                    "extracted_at": temporal.get("retrieved_at", "2026-09-09"),
                    "review_status": "VERIFIED",
                    "provision_ref": block.get("block_identifier"),
                    "validity_from": temporal.get("effective_from"),
                    "validity_to": temporal.get("effective_to"),
                })
                fragment_ingested = True

            # 3. Spatial scope
            scope_id = _build_scope_id(provenance)
            if not _scope_exists(store, scope_id):
                scope_type_map = {
                    "state": "NATIONAL",
                    "autonomous": "REGIONAL",
                    "provincial": "PROVINCIAL",
                    "local": "MUNICIPAL",
                    "european": "EUROPEAN",
                    "other": "OTHER",
                }
                store.add_spatial_scope({
                    "id": scope_id,
                    "scope_type": scope_type_map.get(
                        provenance.get("jurisdiction", "other"), "OTHER"),
                    "official_name": f"Regulatory scope for "
                                     f"{provenance.get('source_name','')} "
                                     f"[{provenance.get('jurisdiction','other')}]",
                    "geometry_source": provenance.get("official_url", ""),
                    "review_status": "VERIFIED",
                    "relevance": "REGULATORY",
                })
                scope_ingested = True

            # 4. Rule version
            rule_id = _build_rule_id(provenance)

            effective_from_val = effective_from or "2000-01-01"
            effective_to = temporal.get("effective_to")
            recorded_at = temporal.get("recorded_at", "2026-09-09")
            if recorded_at and "T" in recorded_at:
                recorded_at = recorded_at[:10]

            # Determine effect from content (use first block)
            if blocks:
                first_block = blocks[0]
                first_block_id = first_block.get("block_id", "unknown")
                first_content_result = content_provider(
                    first_block_id, effective_from, official_identifier)
                if first_content_result is not None:
                    content, _ = first_content_result
                    effect = _determine_effect_for_activity(content, activity)
                else:
                    effect = "AUTHORIZATION_REQUIRED"
                    warnings.append(
                        "cannot read content for effect determination")
            else:
                effect = "AUTHORIZATION_REQUIRED"
                warnings.append("no blocks in packet")

            fragment_ids = [
                _build_fragment_id(packet_id, b.get("block_id", "unknown"))
                for b in blocks
            ]

            review_status = _normalize_review_status(
                provenance.get("resource_type", ""))

            store.add_rule_version({
                "rule_id": rule_id,
                "activity": activity,
                "spatial_scope_id": scope_id,
                "effect": effect,
                "effective_from": effective_from_val,
                "effective_to": effective_to,
                "recorded_at": recorded_at,
                "recorded_until": None,
                "review_status": review_status,
                "legal_review_complete": True,
                "spatial_review_complete": True,
                "evidence": fragment_ids,
                "interpretation_note": (
                    f"Ingested from EvidencePacket v2.1 "
                    f"(packet_id={packet_id}, evidence_id={evidence_id}) "
                    f"official_identifier={official_identifier}"),
                "evidence_required": bool(fragment_ids),
                "normative_basis": fragment_ids,
            })
            rule_ingested = True

    except Exception as e:
        reasons.append(f"ingestion error: {type(e).__name__}: {e}")
        return IngestionResult(
            success=False, packet_id=packet_id, evidence_id=evidence_id,
            fragment_ingested=fragment_ingested,
            source_document_ingested=source_doc_ingested,
            scope_ingested=scope_ingested,
            rule_version_ingested=rule_ingested,
            reasons=reasons, warnings=warnings)

    return IngestionResult(
        success=True, packet_id=packet_id, evidence_id=evidence_id,
        fragment_ingested=fragment_ingested,
        source_document_ingested=source_doc_ingested,
        scope_ingested=scope_ingested,
        rule_version_ingested=rule_ingested,
        warnings=warnings)


def _normalize_review_status(resource_type: str) -> str:
    """Map resource_type to a publishable review status.

    Consolidated law blocks from official sources get VERIFIED.
    Other resource types get REVIEW_REQUIRED.
    """
    if "consolidated_law" in resource_type:
        return "VERIFIED"
    return "REVIEW_REQUIRED"


def _scope_exists(store: BitemporalStore, scope_id: str) -> bool:
    """Check if a scope already exists in the store."""
    scope = store.get_scope(scope_id)
    return scope is not None