"""Append-only bitemporal store and the two-axis version-selection algorithm.

Selection answers "which LegalRuleVersion governs an activity, in a scope, on
an activity_date, as the system knew it on a knowledge_date?" along two
independent axes:

  SYSTEM TIME: a row is knowable at ``knowledge_date`` iff
      recorded_at <= knowledge_date  AND  (recorded_until IS NULL
                                           OR knowledge_date < recorded_until)
    Within a lineage (rule_id, activity, scope, effective_from) the *latest*
    recorded row is the description current at that knowledge date — this is
    how a retrospectively appended closure (effective_to set, recorded late)
    supersedes an earlier open row WITHOUT any UPDATE.

  VALID TIME: [effective_from, effective_to] CLOSED interval (documented in
    alraso.schema). Among surviving lineage descriptions we keep those whose
    effective range covers activity_date; greatest effective_from wins per
    rule_id.

The SAME algorithm governs rule RELATIONS (F04): RuleRelationVersion rows carry
effective/recorded ranges and review, so "which precedences did the system know
on that date?" is answerable. Nothing here is mutable: every writer is a pure
INSERT guarded by DB triggers.

Integrity (F08): every connection enforces PRAGMA foreign_keys=ON explicitly
(never trusting the sqlite3 default) and exposes verify_integrity(). All rows
pass strict validation (F06) before INSERT — invalid dates, effects, review
statuses, booleans or condition ASTs are rejected at the write boundary.

Transactions (F07): add_* methods never commit autonomously while a use-case
transaction is open. BitemporalStore.transaction() is the single commit unit:
a whole corpus load (documents, fragments, scopes, rules, relations) is one
atomic use case — any failure rolls the ENTIRE batch back.

Lexical date comparisons are safe because every date is calendar-validated
strictly at both write and read boundaries (alraso.validation).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterator

from alraso.errors import InvalidRelation, InvalidRule, InvalidScope
from alraso.schema import SQLITE_DDL
from alraso.validation import (
    parse_bool_strict,
    parse_date_strict,
    validate_condition,
)

PUBLISHABLE_REVIEW_STATUSES = frozenset({"VERIFIED", "PUBLISHED"})
KNOWN_EFFECTS = frozenset({"PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED"})
KNOWN_RELATION_TYPES = frozenset({"OVERRIDES"})


@dataclass
class VersionRow:
    seq: int
    rule_id: str
    activity: str
    spatial_scope_id: str
    effect: str
    condition: dict[str, Any] | None
    effective_from: str
    effective_to: str | None
    recorded_at: str
    recorded_until: str | None
    evidence: list[str]
    interpretation_note: str | None
    review_status: str
    legal_review_complete: bool
    evidence_required: bool
    # None = spatial review not applicable (human-declared normative scope);
    # False = explicitly pending (can never carry publishable effect);
    # True = complete.
    spatial_review_complete: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "rule_id": self.rule_id,
            "activity": self.activity,
            "spatial_scope_id": self.spatial_scope_id,
            "effect": self.effect,
            "has_condition": self.condition is not None,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "recorded_at": self.recorded_at,
            "evidence": list(self.evidence),
            "review_status": self.review_status,
            "legal_review_complete": self.legal_review_complete,
            "spatial_review_complete": self.spatial_review_complete,
        }


@dataclass
class RelationVersionRow:
    seq: int
    relation_id: str
    relation_type: str
    from_rule_id: str
    from_effect: str | None
    to_rule_id: str
    to_effect: str | None
    effective_from: str
    effective_to: str | None
    recorded_at: str
    recorded_until: str | None
    evidence: list[str]
    review_status: str
    legal_review_complete: bool
    ai_proposed: bool
    human_verified: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "relation_id": self.relation_id,
            "relation_type": self.relation_type,
            "from_rule_id": self.from_rule_id,
            "from_effect": self.from_effect,
            "to_rule_id": self.to_rule_id,
            "to_effect": self.to_effect,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "recorded_at": self.recorded_at,
            "review_status": self.review_status,
            "human_verified": self.human_verified,
        }


@dataclass
class Selection:
    covering: list[VersionRow]
    saw_lineage: bool

    @property
    def is_gap(self) -> bool:
        return (not self.covering) and self.saw_lineage

    @property
    def is_empty(self) -> bool:
        return not self.saw_lineage


_COLUMNS = (
    "seq, rule_id, activity, spatial_scope_id, effect, condition, effective_from, "
    "effective_to, recorded_at, recorded_until, evidence, interpretation_note, "
    "review_status, legal_review_complete, spatial_review_complete, evidence_required"
)

_R_COLUMNS = (
    "seq, relation_id, relation_type, from_rule_id, from_effect, to_rule_id, to_effect, "
    "effective_from, effective_to, recorded_at, recorded_until, evidence, review_status, "
    "legal_review_complete, ai_proposed, human_verified"
)


class BitemporalStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._tx_depth = 0

    @classmethod
    def connect(cls, path: str = ":memory:") -> "BitemporalStore":
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        # F08: never rely on the sqlite3 driver default for FK enforcement.
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise sqlite3.DatabaseError("PRAGMA foreign_keys could not be enabled")
        conn.executescript(SQLITE_DDL)
        conn.commit()
        return cls(conn)

    def verify_integrity(self) -> None:
        """Raised if FK enforcement is off or the DB reports integrity issues."""
        if self.conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise sqlite3.IntegrityError("foreign_keys pragma is OFF on this connection")
        bad = self.conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise sqlite3.IntegrityError(f"foreign key violations: {[tuple(r) for r in bad]}")

    # ---- use-case transactions (F07) -------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[None]:
        """One atomic use-case boundary. Nested calls join the outermost one.

        Writers inside commit nothing; failure anywhere rolls back the whole
        batch, so a half-ingested corpus is unobservable.
        """
        if self._tx_depth:
            yield
            return
        try:
            self._tx_depth += 1
            yield
        except BaseException:
            self._tx_depth = 0
            self.conn.rollback()
            raise
        else:
            self._tx_depth = 0
            self.conn.commit()

    def _finish(self) -> None:
        if self._tx_depth == 0:
            self.conn.commit()

    # ---- append-only writers (all strictly validated, F06) ---------------------
    def add_source_document(self, d: dict[str, Any]) -> None:
        if not d.get("id") or not d.get("title"):
            raise InvalidRule("source_document requires id and title")
        self.conn.execute(
            "INSERT INTO source_document (id,authority,jurisdiction,document_type,title,"
            "canonical_url,official_status,retrieved_at,content_hash) "
            "VALUES (:id,:authority,:jurisdiction,:document_type,:title,:canonical_url,"
            ":official_status,:retrieved_at,:content_hash)",
            {
                "id": d["id"], "authority": d["authority"], "jurisdiction": d["jurisdiction"],
                "document_type": d["document_type"], "title": d["title"],
                "canonical_url": d["canonical_url"], "official_status": d.get("official_status"),
                "retrieved_at": d.get("retrieved_at"), "content_hash": d.get("content_hash"),
            },
        )
        self._finish()

    def add_legal_fragment(self, d: dict[str, Any]) -> None:
        if not d.get("id") or not d.get("source_document_id") or not d.get("locator"):
            raise InvalidRule("legal_fragment requires id, source_document_id and locator")
        self.conn.execute(
            "INSERT INTO legal_fragment (id,source_document_id,locator,exact_text_hint,"
            "extracted_at,review_status) VALUES (?,?,?,?,?,?)",
            (d["id"], d["source_document_id"], d["locator"], d.get("exact_text_hint"),
             d.get("extracted_at"), d.get("review_status", "VERIFIED")),
        )
        self._finish()

    def add_spatial_scope(self, d: dict[str, Any]) -> None:
        if not d.get("id") or not d.get("official_name") or not d.get("scope_type"):
            raise InvalidScope("spatial_scope requires id, scope_type and official_name")
        self.conn.execute(
            "INSERT INTO spatial_scope (id,scope_type,parent_scope,official_name,"
            "geometry_source,feature_id,srid_native,review_status) VALUES (?,?,?,?,?,?,?,?)",
            (d["id"], d["scope_type"], d.get("parent_scope"), d["official_name"],
             d.get("geometry_source"), d.get("feature_id"), d.get("srid_native"),
             d.get("review_status")),
        )
        self._finish()

    def add_rule_version(self, d: dict[str, Any]) -> None:
        for key in ("rule_id", "activity", "spatial_scope_id", "effect"):
            if not d.get(key):
                raise InvalidRule(f"legal_rule_version requires {key!r}")
        if d["effect"] not in KNOWN_EFFECTS:
            raise InvalidRule(f"unknown effect {d['effect']!r}")
        for field in ("effective_from", "recorded_at"):
            parse_date_strict(d.get(field), field=field)
        for field in ("effective_to", "recorded_until"):
            if d.get(field) is not None:
                parse_date_strict(d[field], field=field)
        if d.get("effective_to") is not None and d["effective_to"] < d["effective_from"]:
            raise InvalidRule("effective_to precedes effective_from")
        if d.get("recorded_until") is not None and d["recorded_until"] < d["recorded_at"]:
            raise InvalidRule("recorded_until precedes recorded_at")
        condition = d.get("condition")
        if condition is not None:
            validate_condition(condition)
        evidence = d.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(e, str) for e in evidence):
            raise InvalidRule("evidence must be a list of fragment ids")
        review_status = d.get("review_status", "REVIEW_REQUIRED")
        # F01: a version claiming a publishable review state must show its
        # review work; the store refuses to encode publishable-but-unreviewed.
        legal_review_complete = parse_bool_strict(
            d.get("legal_review_complete", False), field="legal_review_complete")
        evidence_required = parse_bool_strict(
            d.get("evidence_required", True), field="evidence_required")
        src = d.get("spatial_review_complete", None)
        spatial_review_complete = None if src is None else parse_bool_strict(
            src, field="spatial_review_complete")
        self.conn.execute(
            "INSERT INTO legal_rule_version (rule_id,activity,spatial_scope_id,effect,condition,"
            "effective_from,effective_to,recorded_at,recorded_until,evidence,"
            "interpretation_note,review_status,legal_review_complete,spatial_review_complete,"
            "evidence_required) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d["rule_id"], d["activity"], d["spatial_scope_id"], d["effect"],
             json.dumps(condition) if condition is not None else None,
             d["effective_from"], d.get("effective_to"), d["recorded_at"],
             d.get("recorded_until"), json.dumps(evidence),
             d.get("interpretation_note"), review_status,
             int(legal_review_complete),
             None if spatial_review_complete is None else int(spatial_review_complete),
             int(evidence_required)),
        )
        self._finish()

    def add_relation(self, d: dict[str, Any]) -> None:
        """Append a RuleRelationVersion (F04: relations are bitemporal too).

        No defaults soften the contract: temporal bounds, review status and
        verification booleans are all strictly validated.
        """
        for key in ("relation_id", "relation_type", "from_rule_id", "to_rule_id"):
            if not d.get(key):
                raise InvalidRelation(f"rule_relation_version requires {key!r}")
        if d["relation_type"] not in KNOWN_RELATION_TYPES:
            raise InvalidRelation(f"unknown relation_type {d['relation_type']!r}")
        for field in ("effective_from", "recorded_at"):
            if field not in d:
                raise InvalidRelation(f"rule_relation_version requires {field!r} (bitemporal)")
            parse_date_strict(d[field], field=field)
        for field in ("effective_to", "recorded_until"):
            if d.get(field) is not None:
                parse_date_strict(d[field], field=field)
        if d.get("effective_to") is not None and d["effective_to"] < d["effective_from"]:
            raise InvalidRelation("effective_to precedes effective_from")
        if d.get("recorded_until") is not None and d["recorded_until"] < d["recorded_at"]:
            raise InvalidRelation("recorded_until precedes recorded_at")
        for key, eff in (("from_effect", d.get("from_effect")), ("to_effect", d.get("to_effect"))):
            if eff is not None and eff not in KNOWN_EFFECTS:
                raise InvalidRelation(f"unknown {key} {eff!r}")
        evidence = d.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(e, str) for e in evidence):
            raise InvalidRelation("evidence must be a list of fragment ids")
        ai_proposed = parse_bool_strict(d.get("ai_proposed", False), field="ai_proposed")
        human_verified = parse_bool_strict(d.get("human_verified", False), field="human_verified")
        legal_review_complete = parse_bool_strict(
            d.get("legal_review_complete", False), field="legal_review_complete")
        review_status = d.get("review_status", "REVIEW_REQUIRED")
        self.conn.execute(
            "INSERT INTO rule_relation_version (relation_id,relation_type,from_rule_id,from_effect,"
            "to_rule_id,to_effect,effective_from,effective_to,recorded_at,recorded_until,evidence,"
            "review_status,legal_review_complete,ai_proposed,human_verified) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d["relation_id"], d["relation_type"], d["from_rule_id"], d.get("from_effect"),
             d["to_rule_id"], d.get("to_effect"), d["effective_from"], d.get("effective_to"),
             d["recorded_at"], d.get("recorded_until"), json.dumps(evidence),
             review_status, int(legal_review_complete), int(ai_proposed), int(human_verified)),
        )
        self._finish()

    # ---- selection -------------------------------------------------------------
    @staticmethod
    def _check_dates(activity_date: str, knowledge_date: str) -> None:
        parse_date_strict(activity_date, field="activity_date")
        parse_date_strict(knowledge_date, field="knowledge_date")

    def _row_to_version(self, r: sqlite3.Row) -> VersionRow:
        cond = json.loads(r["condition"]) if r["condition"] else None
        return VersionRow(
            seq=r["seq"], rule_id=r["rule_id"], activity=r["activity"],
            spatial_scope_id=r["spatial_scope_id"], effect=r["effect"], condition=cond,
            effective_from=r["effective_from"], effective_to=r["effective_to"],
            recorded_at=r["recorded_at"], recorded_until=r["recorded_until"],
            evidence=json.loads(r["evidence"]), interpretation_note=r["interpretation_note"],
            review_status=r["review_status"],
            legal_review_complete=bool(r["legal_review_complete"]),
            evidence_required=bool(r["evidence_required"]),
            spatial_review_complete=(None if r["spatial_review_complete"] is None
                                     else bool(r["spatial_review_complete"])),
        )

    @staticmethod
    def _select_bitemporal(rows: list, lineage_key, valid_covers, rank) -> tuple[list, bool]:
        """Shared 2-phase algorithm for versions and relation versions.

        Phase 1: collapse each lineage to the latest recorded description.
        Phase 2: valid-time coverage; greatest rank wins per logical id.
        """
        lineages: dict[Any, Any] = {}
        for v in rows:
            key = lineage_key(v)
            prev = lineages.get(key)
            if prev is None or (v.recorded_at, v.seq) > (prev.recorded_at, prev.seq):
                lineages[key] = v
        by_id: dict[Any, Any] = {}
        for v in lineages.values():
            if not valid_covers(v):
                continue
            prev = by_id.get(lineage_key(v)[0])
            if prev is None or rank(v) > rank(prev):
                by_id[lineage_key(v)[0]] = v
        return list(by_id.values()), bool(lineages)

    def select(self, activity: str, scope_id: str, activity_date: str,
               knowledge_date: str) -> Selection:
        self._check_dates(activity_date, knowledge_date)
        cur = self.conn.execute(
            f"SELECT {_COLUMNS} FROM legal_rule_version "
            "WHERE activity=? AND spatial_scope_id=? AND recorded_at<=? "
            "AND (recorded_until IS NULL OR ?<recorded_until)",
            (activity, scope_id, knowledge_date, knowledge_date),
        )
        visible = [self._row_to_version(r) for r in cur.fetchall()]
        covering, saw_lineage = self._select_bitemporal(
            visible,
            lineage_key=lambda v: (v.rule_id, v.effective_from),
            valid_covers=lambda v: v.effective_from <= activity_date and (
                v.effective_to is None or activity_date <= v.effective_to),
            rank=lambda v: (v.effective_from, v.recorded_at, v.seq),
        )
        return Selection(covering=sorted(covering, key=lambda x: x.rule_id),
                         saw_lineage=saw_lineage)

    def _row_to_relation(self, r: sqlite3.Row) -> RelationVersionRow:
        return RelationVersionRow(
            seq=r["seq"], relation_id=r["relation_id"], relation_type=r["relation_type"],
            from_rule_id=r["from_rule_id"], from_effect=r["from_effect"],
            to_rule_id=r["to_rule_id"], to_effect=r["to_effect"],
            effective_from=r["effective_from"], effective_to=r["effective_to"],
            recorded_at=r["recorded_at"], recorded_until=r["recorded_until"],
            evidence=json.loads(r["evidence"]), review_status=r["review_status"],
            legal_review_complete=bool(r["legal_review_complete"]),
            ai_proposed=bool(r["ai_proposed"]), human_verified=bool(r["human_verified"]),
        )

    def relations_at(self, rule_ids: list[str], activity_date: str,
                     knowledge_date: str) -> list[RelationVersionRow]:
        """Bitemporal visibility of relations among the given rule ids (F04).

        Returns, for each relation_id, the description the system knew at
        knowledge_date, restricted to those whose validity covers activity_date.
        Ordering: by seq — callers must not rely on order for semantics.
        """
        self._check_dates(activity_date, knowledge_date)
        if not rule_ids:
            return []
        qmarks = ",".join("?" * len(rule_ids))
        cur = self.conn.execute(
            f"SELECT {_R_COLUMNS} FROM rule_relation_version "
            f"WHERE (from_rule_id IN ({qmarks}) OR to_rule_id IN ({qmarks})) "
            "AND recorded_at<=? AND (recorded_until IS NULL OR ?<recorded_until)",
            rule_ids + rule_ids + [knowledge_date, knowledge_date],
        )
        visible = [self._row_to_relation(r) for r in cur.fetchall()]
        applicable, _ = self._select_bitemporal(
            visible,
            lineage_key=lambda v: (v.relation_id, v.effective_from),
            valid_covers=lambda v: v.effective_from <= activity_date and (
                v.effective_to is None or activity_date <= v.effective_to),
            rank=lambda v: (v.effective_from, v.recorded_at, v.seq),
        )
        return sorted(applicable, key=lambda v: v.seq)

    # ---- reference reads for evidence / eligibility -----------------------------
    def get_fragments(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        qmarks = ",".join("?" * len(ids))
        cur = self.conn.execute(
            f"SELECT f.id,f.locator,f.exact_text_hint,f.review_status,f.source_document_id,"
            f"d.authority,d.title,d.canonical_url "
            f"FROM legal_fragment f JOIN source_document d ON d.id=f.source_document_id "
            f"WHERE f.id IN ({qmarks})",
            ids,
        )
        return [dict(r) for r in cur.fetchall()]

    def missing_fragments(self, ids: list[str]) -> list[str]:
        """Evidence ids that do NOT resolve to a fragment+document pair."""
        if not ids:
            return []
        found = {f["id"] for f in self.get_fragments(ids)}
        return [i for i in ids if i not in found]

    def get_scope(self, scope_id: str) -> dict[str, Any] | None:
        r = self.conn.execute(
            "SELECT id,scope_type,parent_scope,official_name,geometry_source,feature_id,"
            "review_status FROM spatial_scope WHERE id=?", (scope_id,),
        ).fetchone()
        return dict(r) if r else None

    def rule_ids_known(self) -> set[str]:
        return {r["rule_id"] for r in
                self.conn.execute("SELECT DISTINCT rule_id FROM legal_rule_version")}

    # ---- determination log (append-only, replay-grade, F05) ---------------------
    def record_determination(self, *, canonical_query: dict[str, Any], activity: str,
                             activity_date: str, knowledge_date: str, legal_status: str,
                             knowledge_status: str, applicable_scope_ids: list[str],
                             rule_version_seqs: list[int], relation_version_seqs: list[int],
                             evidence_fragment_ids: list[str], source_document_ids: list[str],
                             engine_adapter: str, engine_version: str,
                             resolver_version: str, schema_version: str,
                             knowledge_state_hash: str,
                             decided_on: str | None = None) -> None:
        decided_on = decided_on or date.today().isoformat()
        self.conn.execute(
            "INSERT INTO determination (canonical_query,activity,activity_date,knowledge_date,"
            "legal_status,knowledge_status,applicable_scope_ids,rule_version_seqs,"
            "relation_version_seqs,evidence_fragment_ids,source_document_ids,engine_adapter,"
            "engine_version,resolver_version,schema_version,knowledge_state_hash,decided_on) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (json.dumps(canonical_query, sort_keys=True), activity, activity_date,
             knowledge_date, legal_status, knowledge_status,
             json.dumps(sorted(applicable_scope_ids)), json.dumps(sorted(rule_version_seqs)),
             json.dumps(sorted(relation_version_seqs)), json.dumps(sorted(evidence_fragment_ids)),
             json.dumps(sorted(source_document_ids)), engine_adapter, engine_version,
             resolver_version, schema_version, knowledge_state_hash, decided_on),
        )
        self._finish()

    def determinations(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT seq,canonical_query,activity,activity_date,knowledge_date,legal_status,"
            "knowledge_status,applicable_scope_ids,rule_version_seqs,relation_version_seqs,"
            "evidence_fragment_ids,source_document_ids,engine_adapter,engine_version,"
            "resolver_version,schema_version,knowledge_state_hash,decided_on "
            "FROM determination").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for key in ("canonical_query",):
                d[key] = json.loads(d[key])
            for key in ("applicable_scope_ids", "rule_version_seqs", "relation_version_seqs",
                        "evidence_fragment_ids", "source_document_ids"):
                d[key] = json.loads(d[key])
            out.append(d)
        return sorted(out, key=lambda r: r["seq"])
