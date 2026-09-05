"""Ordesa acceptance (remediated contract)."""

from alraso.bitemporal import BitemporalStore
from alraso.domain import KnowledgeStatus, Query
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver, STANDING_WARNING

SECTOR = "ss-ordesa-sector-ordesa"


def resolver() -> Resolver:
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    return Resolver(s)


def q(date, knowledge="2023-06-15"):
    return Query(activity="VIVAC_AL_RASO", activity_date=date, knowledge_date=knowledge,
                 spatial_scope_id=SECTOR)


def test_ordesa_vivac_2021_permitted_and_2023_prohibited():
    r = resolver()
    a = r.resolve(q("2021-07-15"))
    b = r.resolve(q("2023-06-15"))
    assert a.legal_status.value == "PERMITTED"
    assert b.legal_status.value == "PROHIBITED"
    # material identity of the winners
    assert a.basis["rule_seqs"] == [2] and b.basis["rule_seqs"] == [3]


def test_contract_fields_populated():
    r = resolver()
    res = r.resolve(q("2023-06-15")).to_dict()
    assert res["legalStatus"] == "PROHIBITED"
    assert res["knowledgeStatus"] == "CURRENT"
    assert res["applicableScope"][0]["scope_id"] == SECTOR
    assert res["ruleVersions"][0]["effective_from"] == "2022-02-09"
    ids = {e["id"] for e in res["evidence"]}
    assert "lf-d16-2022-pernocta" in ids
    urls = {e["canonical_url"] for e in res["evidence"]}
    assert any("pnomp.es" in u for u in urls)
    stages = [t["stage"] for t in res["precedenceTrace"]]
    assert stages[:5] == ["activity_vocab", "spatial", "bitemporal_select",
                          "eligibility", "engine_eval"]
    assert "eligibility" in stages
    assert res["unresolvedConflicts"] == []
    assert STANDING_WARNING in res["warnings"]
    assert res["decisionReason"]
    # judgments traceable to real rule/version ids
    eval_stage = next(t for t in res["precedenceTrace"] if t["stage"] == "engine_eval")
    assert all(rid.startswith("alraso:") for rid in eval_stage["outcomes"])


def test_pre_override_version_carries_both_sources_of_the_transition():
    r = resolver()
    res = r.resolve(q("2021-07-15")).to_dict()
    assert res["ruleVersions"][0]["effective_to"] == "2022-02-08"
    frag_ids = {e["id"] for e in res["evidence"]}
    assert {"lf-rd409-anexo1-da", "lf-d16-2022-pernocta"} <= frag_ids


def test_override_relation_registered_and_human_verified():
    r = resolver()
    rels = r.store.relations_at(["alraso:es-ar/pn-ordesa/pernocta#vivac-sector-ordesa"],
                                "2023-06-15", "2023-06-15")
    assert rels and rels[0].relation_type == "OVERRIDES"
    assert rels[0].human_verified is True
    assert rels[0].review_status == "VERIFIED"


def test_fixture_scopes_are_explicit_about_pending_geometry_review():
    r = resolver()
    scope = r.store.get_scope(SECTOR)
    assert scope["review_status"] == "SPATIAL_REVIEW_PENDING_GEOMETRY"


def test_eligibility_gate_visible_in_trace_and_excludes_nothing_here():
    r = resolver()
    res = r.resolve(q("2023-06-15"))
    elig = next(t for t in res.precedence_trace if t["stage"] == "eligibility")
    assert elig["excluded"] == []           # Ordesa corpus is fully publishable
    assert elig["eligible"] == [3]


def test_full_fixture_answers_prohibited_at_future_knowledge():
    # vigilante store: nothing expires, so at 2028 the answer stays PROHIBITED
    # (the gap scenario of the fixture belongs to the late-discovery store;
    # see tests/test_replay.py and tests/test_failclosed.py::test_temporal_gap)
    r = resolver()
    res = r.resolve(q("2023-06-15", knowledge="2028-01-01"))
    assert res.legal_status.value == "PROHIBITED"
