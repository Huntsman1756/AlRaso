import pytest

from alraso.bitemporal import BitemporalStore
from alraso.schema import POSTGRES_DDL, SQLITE_DDL

SCOPE = {"id": "ss-t", "scope_type": "PARK_SECTOR", "official_name": "T"}


def store() -> BitemporalStore:
    s = BitemporalStore.connect(":memory:")
    s.add_spatial_scope(SCOPE)
    return s


def rv(s, rule_id, effect, ef, et, rec):
    s.add_rule_version({"rule_id": rule_id, "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": SCOPE["id"], "effect": effect,
                        "effective_from": ef, "effective_to": et, "recorded_at": rec})


def test_ddl_keywords_expanded_correctly():
    for ddl in (SQLITE_DDL, POSTGRES_DDL):
        assert "IF NOT EXISTS" in ddl
        assert "NOT NULL" in ddl
        assert "__" not in ddl
    assert "PRIMARY KEY" in SQLITE_DDL
    assert "timestamptz" in POSTGRES_DDL
    assert "timestamptz" not in SQLITE_DDL


def test_append_only_blocks_update_and_delete():
    s = store()
    rv(s, "r1", "PERMITTED", "2020-01-01", None, "2020-06-01")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute("UPDATE legal_rule_version SET effect='PROHIBITED'")
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute("DELETE FROM legal_rule_version")


def test_open_row_covers_future_until_discovered():
    s = store()
    rv(s, "r1", "PERMITTED", "2020-01-01", None, "2020-06-01")
    sel = s.select("VIVAC_AL_RASO", SCOPE["id"], "2023-06-15", "2023-06-15")
    assert [v.effect for v in sel.covering] == ["PERMITTED"]


def test_late_discovery_changes_answer_at_later_knowledge_date():
    s = store()
    rv(s, "r1", "PERMITTED", "2020-01-01", None, "2020-06-01")
    # decree discovered only in 2027: closure + successor appended, recorded 2027
    rv(s, "r1", "PERMITTED", "2020-01-01", "2022-02-08", "2027-05-10")
    rv(s, "r1", "PROHIBITED", "2022-02-09", None, "2027-05-10")
    assert s.select("VIVAC_AL_RASO", SCOPE["id"], "2023-06-15", "2023-06-15").covering[0].effect == "PERMITTED"
    assert s.select("VIVAC_AL_RASO", SCOPE["id"], "2023-06-15", "2028-01-01").covering[0].effect == "PROHIBITED"
    assert s.select("VIVAC_AL_RASO", SCOPE["id"], "2021-07-15", "2028-01-01").covering[0].effect == "PERMITTED"


def test_vigilant_system_answers_today_prohibited_then_too():
    s = store()
    rv(s, "r1", "PERMITTED", "2020-01-01", "2022-02-08", "2022-02-20")
    rv(s, "r1", "PROHIBITED", "2022-02-09", None, "2022-02-20")
    assert s.select("VIVAC_AL_RASO", SCOPE["id"], "2023-06-15", "2023-06-15").covering[0].effect == "PROHIBITED"
    assert s.select("VIVAC_AL_RASO", SCOPE["id"], "2021-07-15", "2023-06-15").covering[0].effect == "PERMITTED"


def test_gap_detected_when_knowledge_ends_before_activity():
    s = store()
    rv(s, "r1", "PERMITTED", "2020-01-01", "2022-02-08", "2022-02-20")  # closure known, no successor yet
    sel = s.select("VIVAC_AL_RASO", SCOPE["id"], "2023-06-15", "2023-06-15")
    assert sel.covering == [] and sel.is_gap


def test_empty_when_nothing_known_for_scope():
    s = store()
    sel = s.select("VIVAC_AL_RASO", SCOPE["id"], "2023-06-15", "2023-06-15")
    assert sel.is_empty and not sel.saw_lineage
