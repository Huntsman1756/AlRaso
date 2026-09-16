"""EvidencePacket v2.1 -> BitemporalStore adapter (evidence-only ingest).

Consumes a *validated* EvidencePacket v2.1 and materialises its provenance
into BitemporalStore evidence entities within a single atomic transaction
(F07):

    source_document -> legal_fragment (REVIEW_REQUIRED)
                    -> spatial_scope candidate (REVIEW_REQUIRED)

Legal boundary (PR #40 remediation): this adapter NEVER interprets legal
effect and NEVER creates publishable state:

  - no ``legal_rule_version`` rows are written — an unreviewed packet
    cannot produce a resolver-consumable rule;
  - no ``PERMITTED`` / ``PROHIBITED`` / ``AUTHORIZATION_REQUIRED`` is
    derived from text keywords;
  - fragments and the claimed scope stay ``REVIEW_REQUIRED`` — only a
    human review can move them to a publishable status;
  - no dates are fabricated: absent ``effective_from`` stays NULL.

Target flow:

    EvidencePacket -> validated evidence (this module)
                   -> REVIEW_REQUIRED -> human review -> publishable rule

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

Hash mismatch -> fail-closed: the fragment is NOT ingested. Since no rule
is ever created here, the resolver can only answer UNDETERMINED over
packet-ingested evidence — NEVER PERMITTED.

Module-level API:
    ingest_evidence_packet(store, packet, content_provider) -> IngestionResult
"""

from __future__ import annotations

import hashlib
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
    """Immutable result of a single packet ingestion.

    ``review_pending`` is always True: everything this adapter writes is
    evidence awaiting human review. No legal determination can be derived
    from an IngestionResult.
    """

    success: bool
    packet_id: str
    evidence_id: str
    source_document_ingested: bool = False
    fragment_ids: list[str] = field(default_factory=list)
    rejected_block_ids: list[str] = field(default_factory=list)
    scope_candidate_id: str | None = None
    review_pending: bool = True
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_fragments(self) -> bool:
        return bool(self.fragment_ids)


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
    """Derive a spatial scope candidate id from the claimed provenance."""
    source_code = provenance.get("source_code", "UNKNOWN")
    jurisdiction = provenance.get("jurisdiction", "other")
    return f"ep-scope-{source_code.lower()}-{jurisdiction}"


def ingest_evidence_packet(
    store: BitemporalStore,
    packet: dict[str, Any],
    content_provider: ContentProvider,
) -> IngestionResult:
    """Ingest an EvidencePacket v2.1 as *unreviewed evidence*.

    Writes (in one atomic transaction, F07):
      - the source_document describing the packet's provenance;
      - one legal_fragment per block whose content resolves AND verifies
        against ``content_sha256`` — always ``REVIEW_REQUIRED``;
      - a spatial_scope *candidate* capturing the jurisdiction the packet
        claims — always ``REVIEW_REQUIRED``.

    It never writes ``legal_rule_version`` and never infers an effect from
    block text. Publication requires a separate human review step.
    """
    evidence_id = packet["evidence_id"]
    packet_id = packet["packet_id"]
    provenance = packet["provenance"]
    temporal = packet["temporal"]
    blocks = packet["blocks"]

    reasons: list[str] = []
    warnings: list[str] = []
    fragment_ids: list[str] = []
    rejected_block_ids: list[str] = []
    source_doc_ingested = False
    scope_candidate_id: str | None = None

    official_identifier = provenance.get("official_identifier", "")
    effective_from = temporal.get("effective_from")

    try:
        with store.transaction():
            # 1. Source document (provenance). official_status is left NULL:
            #    the packet cannot prove the instrument is in force.
            sd_id = _build_source_document_id(provenance)
            store.add_source_document({
                "id": sd_id,
                "authority": provenance.get("publisher") or "Estado",
                "jurisdiction": provenance.get("jurisdiction", "other").upper(),
                "document_type": provenance.get("document_type"),
                "title": (provenance.get("title")
                          or provenance.get("official_identifier")
                          or "Desconocido"),
                "canonical_url": provenance.get("official_url", ""),
                "official_status": None,
                "retrieved_at": temporal.get("retrieved_at"),
                "content_hash": None,
            })
            source_doc_ingested = True

            # 2. Legal fragments (one per block): evidence only.
            #    Content is read from the provider and its SHA-256 verified
            #    before ingest; on mismatch or unresolvable content the block
            #    is rejected, never guessed.
            for block in blocks:
                block_id = block.get("block_id", "unknown")
                block_sha_expected = block.get("content_sha256")

                content_result = content_provider(block_id, effective_from,
                                                  official_identifier)
                if content_result is None:
                    rejected_block_ids.append(block_id)
                    warnings.append(
                        f"content_provider returned None for block {block_id}")
                    continue

                content, content_sha = content_result

                if block_sha_expected and content_sha != block_sha_expected:
                    rejected_block_ids.append(block_id)
                    warnings.append(
                        f"SHA-256 mismatch for block {block_id}: "
                        f"expected {block_sha_expected}, got {content_sha}. "
                        f"Fragment rejected.")
                    continue

                frag_id = _build_fragment_id(packet_id, block_id)
                store.add_legal_fragment({
                    "id": frag_id,
                    "source_document_id": sd_id,
                    "locator": f"{official_identifier}:{block_id}",
                    "exact_text_hint": content[:200] if content else "",
                    "extracted_at": temporal.get("retrieved_at"),
                    "review_status": "REVIEW_REQUIRED",
                    "provision_ref": block.get("block_identifier"),
                    "validity_from": effective_from,
                    "validity_to": temporal.get("effective_to"),
                })
                fragment_ids.append(frag_id)

            # 3. Spatial scope candidate: records the jurisdiction the packet
            #    claims. REVIEW_REQUIRED — a document's provenance is not a
            #    verified legal scope. REGULATORY keeps the fail-closed
            #    default (coverage required before any PERMITTED).
            scope_id = _build_scope_id(provenance)
            if store.get_scope(scope_id) is None:
                store.add_spatial_scope({
                    "id": scope_id,
                    "scope_type": "OTHER",
                    "official_name": (
                        f"EvidencePacket claimed scope: "
                        f"{provenance.get('source_name', '')} "
                        f"[{provenance.get('jurisdiction', 'other')}]"),
                    "geometry_source": provenance.get("official_url", ""),
                    "review_status": "REVIEW_REQUIRED",
                    "relevance": "REGULATORY",
                })
            scope_candidate_id = scope_id

    except Exception as e:
        reasons.append(f"ingestion error: {type(e).__name__}: {e}")
        return IngestionResult(
            success=False, packet_id=packet_id, evidence_id=evidence_id,
            source_document_ingested=source_doc_ingested,
            fragment_ids=fragment_ids,
            rejected_block_ids=rejected_block_ids,
            scope_candidate_id=scope_candidate_id,
            reasons=reasons, warnings=warnings)

    return IngestionResult(
        success=True, packet_id=packet_id, evidence_id=evidence_id,
        source_document_ingested=source_doc_ingested,
        fragment_ids=fragment_ids,
        rejected_block_ids=rejected_block_ids,
        scope_candidate_id=scope_candidate_id,
        warnings=warnings)
