"""EvidencePacket v2.1 consumer: validator + evidence-only adapter tests.

Hermetic: packets are synthetic in-memory dicts and the snapshot DB is
generated at runtime in ``tmp_path`` — no machine-local paths, no network.

PR #40 remediation — the adapter is evidence-only:
  - it NEVER writes ``legal_rule_version``;
  - it NEVER maps text keywords to a legal effect;
  - fragments and the claimed scope stay ``REVIEW_REQUIRED``;
  - absent ``effective_from`` stays NULL (no fabricated dates).

Mandatory negatives pinned here:
  raw "se permite..."      -> NEVER creates PERMITTED
  document jurisdiction    -> NEVER creates VERIFIED legal scope
  unreviewed EvidencePacket -> NEVER creates a resolver-consumable rule
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alraso.bitemporal import BitemporalStore  # noqa: E402
from alraso.domain import Query  # noqa: E402
from alraso.ingest.evidence_packet import (  # noqa: E402
    ingest_evidence_packet,
    make_snapshot_content_provider,
)
from alraso.official_sources_v2 import (  # noqa: E402
    EvidencePacketValidationError,
    PacketPayload,
    VENDOR_SCHEMA_SHA256,
    validate_evidence_packet_v2_1,
    validate_schema_json_sha256,
)
from alraso.resolver import Resolver  # noqa: E402

# ---- synthetic corpus --------------------------------------------------------

LECO_LIKE_CONTENT = (
    "Articulo 50. Infracciones leves.\n"
    "1. Se consideran infracciones administrativas leves:\n"
    "f) La acampada, el vivac y la pernocta al aire libre, sin "
    "autorizacion o incumpliendo las condiciones establecidas."
)
PERMISSIVE_CONTENT = (
    "Se permite la acampada, el vivac y la pernocta al aire libre "
    "en las zonas habilitadas a tal efecto."
)

LAW_ID = "BOE-A-2005-11132"
VERSION_DATE = "2005-06-30"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_packet(
    block_id: str = "a50",
    *,
    content: str = LECO_LIKE_CONTENT,
    jurisdiction: str = "state",
    resource_type: str = "consolidated_law_block",
    review_status: str = "not_reviewed",
    effective_from: str | None = VERSION_DATE,
) -> dict:
    """A schema-valid synthetic EvidencePacket v2.1."""
    return {
        "schema_version": "2.1",
        "packet_id": _sha256(f"packet-{block_id}-{jurisdiction}"),
        "evidence_id": _sha256(f"evidence-{block_id}-{jurisdiction}"),
        "provenance": {
            "source_code": "BOE",
            "source_name": "Boletin Oficial del Estado",
            "jurisdiction": jurisdiction,
            "resource_type": resource_type,
            "official_identifier": LAW_ID,
            "official_url": "https://www.boe.es/eli/es-ib/l/2005/06/30/4",
            "title": "Ley autonomica de ejemplo",
            "document_type": "LAW",
            "publisher": "Comunidad Autonoma ficticia",
            "publication_date": "2005-07-15",
            "publication_date_status": "known",
        },
        "version": {
            "version_id": "v1",
            "version_date": VERSION_DATE,
            "version_date_status": "known",
        },
        "temporal": {
            "effective_from": effective_from,
            "effective_from_status": "known" if effective_from else "unknown",
            "effective_to": None,
            "effective_to_status": "open",
            "retrieved_at": "2026-09-09T00:00:00Z",
            "recorded_at": "2026-09-09T00:00:00Z",
        },
        "artifacts": [],
        "blocks": [
            {
                "block_id": block_id,
                "block_id_status": "official",
                "block_type": "article",
                "block_identifier": f"Art. {block_id.upper()}",
                "content_sha256": _sha256(content),
            }
        ],
        "review": {"review_status": review_status},
    }


# ---- fixtures ---------------------------------------------------------------

@pytest.fixture(scope="module")
def snapshot_db(tmp_path_factory):
    """Runtime-generated snapshot DB with the provider's expected schema."""
    db_path = tmp_path_factory.mktemp("snap") / "snapshot.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE consolidated_laws (
            id INTEGER PRIMARY KEY,
            official_identifier TEXT NOT NULL
        );
        CREATE TABLE consolidated_law_versions (
            id INTEGER PRIMARY KEY,
            consolidated_law_id INTEGER NOT NULL,
            version_date TEXT
        );
        CREATE TABLE consolidated_law_text_blocks (
            consolidated_law_id INTEGER NOT NULL,
            version_id INTEGER NOT NULL,
            official_block_id TEXT NOT NULL,
            content TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO consolidated_laws (id, official_identifier) VALUES (1, ?)",
        (LAW_ID,),
    )
    conn.execute(
        "INSERT INTO consolidated_law_versions "
        "(id, consolidated_law_id, version_date) VALUES (1, 1, ?)",
        (VERSION_DATE,),
    )
    conn.execute(
        "INSERT INTO consolidated_law_text_blocks "
        "(consolidated_law_id, version_id, official_block_id, content) "
        "VALUES (1, 1, 'a50', ?)",
        (LECO_LIKE_CONTENT,),
    )
    conn.execute(
        "INSERT INTO consolidated_law_text_blocks "
        "(consolidated_law_id, version_id, official_block_id, content) "
        "VALUES (1, 1, 'a99', ?)",
        (PERMISSIVE_CONTENT,),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def packet_leco():
    return make_packet("a50", content=LECO_LIKE_CONTENT)


@pytest.fixture()
def packet_permissive():
    return make_packet("a99", content=PERMISSIVE_CONTENT)


@pytest.fixture()
def content_provider(snapshot_db):
    return make_snapshot_content_provider(snapshot_db)


@pytest.fixture()
def mock_content_provider():
    return MagicMock()


def _resolve(store, scope_id: str, activity_date: str = "2010-06-15"):
    resolver = Resolver(store)
    return resolver.resolve(Query(
        activity="VIVAC_AL_RASO",
        activity_date=activity_date,
        knowledge_date="2026-09-09",
        spatial_scope_id=scope_id,
    ))


def _rule_version_count(store) -> int:
    return store.conn.execute(
        "SELECT COUNT(*) AS n FROM legal_rule_version").fetchone()["n"]


# ---- M4.1: validator tests --------------------------------------------------

class TestValidatorPositive:
    """Valid packets must pass."""

    def test_leco_packet_valid(self, packet_leco):
        result = validate_evidence_packet_v2_1(packet_leco)
        assert result.ok is True
        assert result.reasons == []

    def test_permissive_packet_valid(self, packet_permissive):
        result = validate_evidence_packet_v2_1(packet_permissive)
        assert result.ok is True
        assert result.reasons == []

    def test_schema_version_is_2_1(self, packet_leco):
        assert packet_leco["schema_version"] == "2.1"

    def test_schema_sha256_anchor_matches(self):
        assert len(VENDOR_SCHEMA_SHA256) == 64

    def test_packet_payload_parse(self, packet_leco):
        payload = PacketPayload(
            schema_version=packet_leco["schema_version"],
            packet_id=packet_leco["packet_id"],
            evidence_id=packet_leco["evidence_id"],
            provenance=packet_leco["provenance"],
            version=packet_leco["version"],
            temporal=packet_leco["temporal"],
            artifacts=packet_leco["artifacts"],
            blocks=packet_leco["blocks"],
            review=packet_leco["review"],
            consumer_context=packet_leco.get("consumer_context"),
            generator=packet_leco.get("generator"),
            generated_at=packet_leco.get("generated_at"),
        )
        assert payload.block_ids == [b["block_id"] for b in packet_leco["blocks"]]

    def test_validate_schema_json_sha256(self):
        from alraso.official_sources_v2 import SCHEMA_JSON
        result = validate_schema_json_sha256(SCHEMA_JSON)
        assert result is not None
        assert len(VENDOR_SCHEMA_SHA256) == 64
        assert len(SCHEMA_JSON) > 1000


class TestValidatorNegative:
    """Structural defects must be rejected (fail-closed)."""

    def test_schema_version_3_0_rejected(self):
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1({
                "schema_version": "3.0",
                "packet_id": "a" * 64,
                "evidence_id": "b" * 64,
                "provenance": {},
                "version": {"version_id": "v1", "version_date_status": "known"},
                "temporal": {
                    "effective_from_status": "known",
                    "effective_to_status": "open",
                    "retrieved_at": "2026-09-09T00:00:00Z",
                    "recorded_at": "2026-09-09T00:00:00Z",
                },
                "artifacts": [],
                "blocks": [],
                "review": {"review_status": "not_reviewed"},
            })
        assert any("2.1" in str(r) for r in exc_info.value.reasons)

    def test_altered_content_sha256_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["blocks"][0]["content_sha256"] = "G" + pkt["blocks"][0]["content_sha256"][1:]
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("content_sha256" in str(r) for r in exc_info.value.reasons)

    def test_missing_required_field_rejected(self):
        pkt = {
            "schema_version": "2.1",
            "packet_id": "a" * 64,
            "evidence_id": "b" * 64,
            "version": {"version_id": "v1", "version_date_status": "known"},
            "temporal": {
                "effective_from_status": "known",
                "effective_to_status": "open",
                "retrieved_at": "2026-09-09T00:00:00Z",
                "recorded_at": "2026-09-09T00:00:00Z",
            },
            "artifacts": [],
            "blocks": [],
            "review": {"review_status": "not_reviewed"},
        }
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("provenance" in str(r) for r in exc_info.value.reasons)

    def test_unknown_top_level_field_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["fake_external_field"] = "oops"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("fake_external_field" in str(r) for r in exc_info.value.reasons)

    def test_invalid_review_status_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["review"]["review_status"] = "fake_status_value"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("review_status" in str(r) for r in exc_info.value.reasons)

    def test_invalid_jurisdiction_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["provenance"]["jurisdiction"] = "fake_jurisdiction"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("jurisdiction" in str(r) for r in exc_info.value.reasons)

    def test_invalid_block_type_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["blocks"][0]["block_type"] = "nonexistent_type"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("block_type" in str(r) for r in exc_info.value.reasons)

    def test_invalid_block_id_status_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["blocks"][0]["block_id_status"] = "nonexistent"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("block_id_status" in str(r) for r in exc_info.value.reasons)

    def test_invalid_effective_to_status_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["temporal"]["effective_to_status"] = "nonexistent"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("effective_to_status" in str(r) for r in exc_info.value.reasons)

    def test_non_list_artifacts_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["artifacts"] = "not_a_list"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("artifacts" in str(r) for r in exc_info.value.reasons)

    def test_non_list_blocks_rejected(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["blocks"] = "not_a_list"
        with pytest.raises(EvidencePacketValidationError) as exc_info:
            validate_evidence_packet_v2_1(pkt)
        assert any("blocks" in str(r) for r in exc_info.value.reasons)


# ---- M4.2: adapter (evidence-only) tests ------------------------------------

class TestAdapterIngest:
    """The adapter materialises provenance as unreviewed evidence."""

    def test_packet_ingests_as_unreviewed_evidence(self, packet_leco,
                                                   content_provider):
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        assert result.success is True
        assert result.evidence_id == packet_leco["evidence_id"]
        assert result.source_document_ingested is True
        assert result.fragment_ids == [
            f"ep-frag-{packet_leco['packet_id']}-a50"]
        assert result.scope_candidate_id == "ep-scope-boe-state"
        assert result.review_pending is True
        for w in result.warnings:
            assert "SHA-256 mismatch" not in w

    def test_fragment_is_review_required(self, packet_leco, content_provider):
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        frags = store.get_fragments(result.fragment_ids)
        assert len(frags) == 1
        assert frags[0]["review_status"] == "REVIEW_REQUIRED"

    def test_fragment_provenance_preserved(self, packet_leco, content_provider):
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        frag = store.get_fragments(result.fragment_ids)[0]
        assert frag["locator"] == f"{LAW_ID}:a50"
        assert frag["provision_ref"] == "Art. A50"
        assert "infraccion" in frag["exact_text_hint"].lower()
        assert frag["validity_from"] == VERSION_DATE
        assert frag["validity_to"] is None

    def test_missing_effective_from_stays_null(self, content_provider):
        """No fabricated validity window: absent effective_from -> NULL."""
        pkt = make_packet("a50", content=LECO_LIKE_CONTENT,
                          effective_from=None)
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, pkt, content_provider)
        frag = store.get_fragments(result.fragment_ids)[0]
        assert frag["validity_from"] is None

    def test_source_document_does_not_claim_vigente(self, packet_leco,
                                                    content_provider):
        """official_status stays NULL: the packet cannot prove the
        instrument is in force."""
        store = BitemporalStore.connect(":memory:")
        ingest_evidence_packet(store, packet_leco, content_provider)
        row = store.conn.execute(
            "SELECT official_status FROM source_document WHERE id=?",
            (f"ep-src-{LAW_ID}",)).fetchone()
        assert row is not None
        assert row["official_status"] is None

    def test_content_sha256_verified_before_ingest(self, content_provider):
        result = content_provider("a50", VERSION_DATE, LAW_ID)
        assert result is not None
        content, sha = result
        assert sha == _sha256(LECO_LIKE_CONTENT)
        assert "infraccion" in content.lower()

    def test_no_rule_version_created(self, packet_leco, content_provider):
        store = BitemporalStore.connect(":memory:")
        ingest_evidence_packet(store, packet_leco, content_provider)
        assert _rule_version_count(store) == 0


class TestAdapterHashMismatch:
    """SHA-256 mismatch -> fragment rejected; resolution stays UNDETERMINED."""

    def test_hash_mismatch_rejects_fragment(self, packet_leco,
                                            mock_content_provider):
        mock_content_provider.return_value = (
            "Manipulated content that does not match the hash.",
            "0" * 64,
        )
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco,
                                        mock_content_provider)
        assert result.success is True
        assert result.fragment_ids == []
        assert result.rejected_block_ids == ["a50"]
        assert any("SHA-256 mismatch" in w for w in result.warnings)

    def test_hash_mismatch_leads_to_undetermined(self, packet_leco,
                                                 mock_content_provider):
        mock_content_provider.return_value = ("fake content", "0" * 64)
        store = BitemporalStore.connect(":memory:")
        ingest_evidence_packet(store, packet_leco, mock_content_provider)
        res = _resolve(store, "ep-scope-boe-state")
        assert res.legal_status.value == "UNDETERMINED"

    def test_missing_content_provider_returns_undetermined(
            self, packet_leco, mock_content_provider):
        mock_content_provider.return_value = None
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco,
                                        mock_content_provider)
        assert result.fragment_ids == []
        res = _resolve(store, "ep-scope-boe-state")
        assert res.legal_status.value == "UNDETERMINED"


# ---- legal-boundary negatives (PR #40 remediation, mandatory) ----------------

class TestLegalBoundaryNegatives:
    """The three mandatory negatives: extraction can never self-publish."""

    def test_permissive_text_never_creates_permitted(
            self, packet_permissive, content_provider):
        """Raw 'Se permite...' text -> NEVER a PERMITTED determination."""
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_permissive,
                                        content_provider)
        assert result.success is True
        assert result.has_fragments
        res = _resolve(store, "ep-scope-boe-state")
        assert res.legal_status.value != "PERMITTED"
        assert res.legal_status.value == "UNDETERMINED"

    def test_jurisdiction_never_creates_verified_scope(
            self, packet_leco, content_provider):
        """Document jurisdiction -> NEVER a VERIFIED legal scope."""
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        scope = store.get_scope(result.scope_candidate_id)
        assert scope is not None
        assert scope["review_status"] == "REVIEW_REQUIRED"
        assert scope["review_status"] != "VERIFIED"

    def test_unreviewed_packet_never_creates_resolver_rule(
            self, packet_leco, content_provider):
        """An unreviewed EvidencePacket -> NEVER a resolver-consumable rule."""
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        assert result.success is True
        assert _rule_version_count(store) == 0
        res = _resolve(store, "ep-scope-boe-state")
        assert res.legal_status.value == "UNDETERMINED"


# ---- human review is the publication gate ------------------------------------

class TestHumanReviewGate:
    """Positive leg: only explicit human review makes evidence consumable.

    legal_fragment is append-only: review cannot flip a row in place. The
    honest channel is a human-gated ingest that writes a NEW fragment
    marked VERIFIED (the reviewer checked the citation against the
    source), plus the human-authored rule.
    """

    def test_rule_citing_unreviewed_fragment_stays_ineligible(
            self, packet_leco, content_provider):
        """Even a fully-marked rule_version cannot launder REVIEW_REQUIRED
        evidence: eligibility fails on EVIDENCE_NOT_PUBLISHABLE."""
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        frag_id = result.fragment_ids[0]

        store.add_rule_version({
            "rule_id": "alraso:state/leco-art50-vivac",
            "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": result.scope_candidate_id,
            "effect": "PROHIBITED",
            "effective_from": VERSION_DATE,
            "effective_to": None,
            "recorded_at": "2026-09-09",
            "recorded_until": None,
            "review_status": "VERIFIED",
            "legal_review_complete": True,
            "spatial_review_complete": True,
            "evidence": [frag_id],
            "evidence_required": True,
            "normative_basis": [frag_id],
            "interpretation_note": "attempt to cite unreviewed evidence",
        })

        res = _resolve(store, result.scope_candidate_id)
        assert res.legal_status.value == "UNDETERMINED"

    def test_human_reviewed_ingest_can_back_determination(
            self, packet_leco, content_provider):
        """Simulated adjudication channel: a human-verified citation is a
        NEW VERIFIED fragment (append-only), the claimed scope is reviewed,
        and the human writes the rule. Only then the resolver answers."""
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        frag_id = result.fragment_ids[0]
        scope_id = result.scope_candidate_id

        # Before review: nothing consumable.
        assert _resolve(store, scope_id).legal_status.value == "UNDETERMINED"

        # Human review output (never written by this adapter).
        reviewed_frag_id = f"{frag_id}-reviewed"
        original = store.get_fragments([frag_id])[0]
        store.add_legal_fragment({
            "id": reviewed_frag_id,
            "source_document_id": original["source_document_id"],
            "locator": original["locator"],
            "exact_text_hint": original["exact_text_hint"],
            "extracted_at": packet_leco["temporal"]["retrieved_at"],
            "review_status": "VERIFIED",
            "provision_ref": original["provision_ref"],
            "validity_from": original["validity_from"],
            "validity_to": original["validity_to"],
        })
        store.conn.execute(
            "UPDATE spatial_scope SET review_status='VERIFIED' WHERE id=?",
            (scope_id,))
        store.conn.commit()
        store.add_rule_version({
            "rule_id": "alraso:state/leco-art50-vivac",
            "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": scope_id,
            "effect": "PROHIBITED",
            "effective_from": VERSION_DATE,
            "effective_to": None,
            "recorded_at": "2026-09-09",
            "recorded_until": None,
            "review_status": "VERIFIED",
            "legal_review_complete": True,
            "spatial_review_complete": True,
            "evidence": [reviewed_frag_id],
            "evidence_required": True,
            "normative_basis": [reviewed_frag_id],
            "interpretation_note": (
                "Human-reviewed: LECO-like Art. 50(f) declares vivac an "
                "administrative infringement -> PROHIBITED."),
        })

        res = _resolve(store, scope_id)
        assert res.legal_status.value == "PROHIBITED"
        frag_ids = {e["id"] for e in res.evidence}
        assert reviewed_frag_id in frag_ids

    def test_packet_id_survives_in_fragment_identity(self, packet_leco,
                                                     content_provider):
        """Packet provenance stays traceable through fragment ids."""
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco, content_provider)
        assert packet_leco["packet_id"] in result.fragment_ids[0]


# ---- negative end-to-end ------------------------------------------------------

class TestNegativesEndToEnd:

    def test_schema_v3_0_rejected_before_ingest(self, packet_leco):
        pkt = copy.deepcopy(packet_leco)
        pkt["schema_version"] = "3.0"
        with pytest.raises(EvidencePacketValidationError):
            validate_evidence_packet_v2_1(pkt)

    def test_ingest_is_atomic_on_fragment_error(self, packet_leco,
                                                mock_content_provider):
        """A provider failure mid-ingest rejects the block without
        corrupting the store."""
        mock_content_provider.side_effect = RuntimeError("provider down")
        store = BitemporalStore.connect(":memory:")
        result = ingest_evidence_packet(store, packet_leco,
                                        mock_content_provider)
        assert result.success is False
        assert _rule_version_count(store) == 0
