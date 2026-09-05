"""F07/F08 — atomic ingest and SQLite integrity contract."""

from __future__ import annotations

import sqlite3

import pytest

from alraso.ingest.ordesa import ingest_corpus, load_fixture_json, load_ordesa
from alraso.resolver import Resolver
from alraso.domain import LegalStatus, Query
from conftest import new_store


def test_foreign_keys_enabled_and_verified():
    s = new_store()
    s.verify_integrity()  # must not raise
    assert s.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_invalid_fk_fails():
    s = new_store()
    with pytest.raises(sqlite3.IntegrityError):
        s.add_rule_version({"rule_id": "r", "activity": "VIVAC_AL_RASO",
                            "spatial_scope_id": "does-not-exist", "effect": "PERMITTED",
                            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                            "evidence": []})


def test_append_only_protection_on_every_normative_table():
    s = new_store()
    load_ordesa(s)
    # materialize a determination row so UPDATE/DELETE triggers actually fire
    Resolver(s).resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                              knowledge_date="2023-06-15",
                              spatial_scope_id="ss-ordesa-sector-ordesa"),
                        record=True)
    protected = [
        "legal_rule_version", "rule_relation_version", "source_document",
        "legal_fragment", "determination",
    ]
    for table in protected:
        col = {"legal_rule_version": "interpretation_note='x'",
               "rule_relation_version": "evidence='[]'",
               "source_document": "official_status='x'",
               "legal_fragment": "locator='x'",
               "determination": "legal_status='x'"}[table]
        with pytest.raises(sqlite3.IntegrityError):
            s.conn.execute(f"UPDATE {table} SET {col}")
    # DELETE protection (spatial_scope allows metadata UPDATE but not DELETE)
    for table in protected + ["spatial_scope"]:
        with pytest.raises(sqlite3.IntegrityError):
            s.conn.execute(f"DELETE FROM {table}")
    s.conn.rollback()


def test_ingest_batch_rolls_back_completely():
    fx = load_fixture_json()
    # poison the batch: an invalid rule version deep in the middle
    fx["legal_rule_versions"].insert(
        1, {"rule_id": "alraso:es:t#poison", "activity": "VIVAC_AL_RASO",
            "spatial_scope_id": "ss-ordesa-park", "effect": "NOT_A_REAL_EFFECT",
            "effective_from": "2020-01-01", "recorded_at": "2020-06-01"})
    s = new_store()
    with pytest.raises(Exception):
        ingest_corpus(s, fx)
    rows_added_after_failure = s.conn.execute(
        "SELECT (SELECT COUNT(*) FROM source_document) + "
        "(SELECT COUNT(*) FROM legal_fragment) + (SELECT COUNT(*) FROM spatial_scope) "
        "+ (SELECT COUNT(*) FROM legal_rule_version) "
        "+ (SELECT COUNT(*) FROM rule_relation_version)").fetchone()[0]
    assert rows_added_after_failure == 0
    s.verify_integrity()


def test_ingest_retry_after_rollback_succeeds():
    fx = load_fixture_json()
    poison = {"rule_id": "alraso:es:t#poison", "activity": "VIVAC_AL_RASO",
              "spatial_scope_id": "ss-ordesa-park", "effect": "BOGUS",
              "effective_from": "2020-01-01", "recorded_at": "2020-06-01"}
    fx["legal_rule_versions"].append(poison)
    s = new_store()
    with pytest.raises(Exception):
        ingest_corpus(s, fx)
    assert s.conn.execute("SELECT COUNT(*) FROM legal_rule_version").fetchone()[0] == 0
    # defined retry: clean corpus now loads fully
    fx["legal_rule_versions"].remove(poison)
    ingest_corpus(s, fx)
    assert s.conn.execute("SELECT COUNT(*) FROM legal_rule_version").fetchone()[0] == 4


def test_duplicate_ingest_rejected_without_partial_state():
    s = new_store()
    load_ordesa(s)
    before = s.conn.execute("SELECT COUNT(*) FROM legal_rule_version").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        load_ordesa(s)          # duplicate primary keys
    after = s.conn.execute("SELECT COUNT(*) FROM legal_rule_version").fetchone()[0]
    assert after == before      # explicit rejection, no ambiguity
    r = Resolver(s)
    res = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15",
                          spatial_scope_id="ss-ordesa-sector-ordesa"))
    assert res.legal_status is LegalStatus.PERMITTED  # corpus still usable


def test_transaction_nesting_joins_outer():
    s = new_store()
    with pytest.raises(RuntimeError):
        with s.transaction():
            s.add_spatial_scope({"id": "s-n", "scope_type": "OTHER", "official_name": "N"})
            with s.transaction():
                s.add_spatial_scope({"id": "s-n2", "scope_type": "OTHER",
                                     "official_name": "N2"})
            raise RuntimeError("boom")
    assert s.conn.execute("SELECT COUNT(*) FROM spatial_scope").fetchone()[0] == 0


def test_bitemporal_selection_correctness_guarded():
    # selection respects BOTH axes after integrity enforcement
    s = new_store()
    s.add_spatial_scope({"id": "s-bt", "scope_type": "OTHER", "official_name": "B"})
    s.add_rule_version({"rule_id": "r-bt", "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": "s-bt", "effect": "PROHIBITED",
                        "effective_from": "2022-01-01", "recorded_at": "2020-06-01",
                        "evidence": []})
    sel = s.select("VIVAC_AL_RASO", "s-bt", "2021-06-01", "2023-06-15")
    assert sel.is_gap  # row known but its validity starts later; no successor yet
