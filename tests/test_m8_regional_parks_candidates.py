"""M8 regional-parks candidate-corpus safety tests.

The three candidate fixtures under discovery/evidence/m8-pr-*/ are evidence
proposals pending HUMAN legal review (RC-M8-ES-MD-PRCAM-VIVAC,
RC-M8-ES-MD-PRCMG-VIVAC, RC-M8-ES-MD-PRSE-VIVAC). These tests prove — at the
code level — that none of them can produce a publishable effect:

  * every rule version is REVIEW_REQUIRED with legal/spatial review incomplete
  * the eligibility gate rejects every version
  * the resolver answers UNDETERMINED/INCOMPLETE for every scope, even when
    caller-supplied facts would satisfy the PROPOSED conditions
  * no PERMITTED/PROHIBITED/AUTHORIZATION_REQUIRED can leak pre-review
  * the annulled Sureste PRUG is never used as normative basis
"""

from __future__ import annotations

import hashlib
import io
import json
import pathlib

import pytest

from alraso.bitemporal import BitemporalStore, VersionRow
from alraso.domain import KnowledgeStatus, LegalStatus, Query
from alraso.eligibility import is_rule_version_eligible
from alraso.ingest.ordesa import ingest_corpus
from alraso.resolver import Resolver

EVIDENCE = pathlib.Path(__file__).resolve().parent.parent / "discovery" / "evidence"

CASES = {
    "m8-pr-manzanares": {
        "scopes": ["ss-prcam-parque", "ss-prcam-reserva-natural"],
        "rule_count": 3,
    },
    "m8-pr-guadarrama-medio": {
        "scopes": ["ss-prcmg-parque"],
        "rule_count": 2,
    },
    "m8-pr-sureste": {
        "scopes": ["ss-prse-parque", "ss-prse-zona-a",
                   "ss-prse-zonas-b-e", "ss-prse-zonas-fg"],
        "rule_count": 4,
    },
}


def _load(case: str) -> tuple[BitemporalStore, dict]:
    fx = json.loads(io.open(EVIDENCE / case / "candidate_fixture.json",
                            encoding="utf-8").read())
    store = BitemporalStore.connect(":memory:")
    ingest_corpus(store, fx)
    return store, fx


def _query(scope: str, activity: str = "VIVAC_AL_RASO",
           facts: dict | None = None) -> Query:
    return Query(activity=activity, activity_date="2026-09-17",
                 knowledge_date="2026-09-17", spatial_scope_id=scope,
                 facts=facts or {})


@pytest.mark.parametrize("case", sorted(CASES))
def test_no_review_complete_flags(case):
    _store, fx = _load(case)
    blob = json.dumps(fx)
    assert '"legal_review_complete": true' not in blob
    assert '"spatial_review_complete": true' not in blob
    assert '"PUBLISHED"' not in blob
    for v in fx["legal_rule_versions"]:
        assert v["review_status"] == "REVIEW_REQUIRED"
        assert v["legal_review_complete"] is False
        assert v["spatial_review_complete"] is False
    for f in fx["legal_fragments"]:
        assert f["review_status"] == "REVIEW_REQUIRED"


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_candidate_version_is_ineligible(case):
    store, fx = _load(case)
    rows = store.conn.execute("SELECT * FROM legal_rule_version").fetchall()
    assert len(rows) == len(fx["legal_rule_versions"]) == CASES[case]["rule_count"]
    cols = [c[1] for c in store.conn.execute(
        "PRAGMA table_info(legal_rule_version)")]
    for row in rows:
        v = dict(zip(cols, row))
        vr = VersionRow(
            seq=v["seq"], rule_id=v["rule_id"], activity=v["activity"],
            spatial_scope_id=v["spatial_scope_id"], effect=v["effect"],
            condition=json.loads(v["condition"]) if v["condition"] else None,
            effective_from=v["effective_from"], effective_to=v["effective_to"],
            recorded_at=v["recorded_at"], recorded_until=v["recorded_until"],
            evidence=json.loads(v["evidence"]),
            interpretation_note=v["interpretation_note"],
            review_status=v["review_status"],
            legal_review_complete=bool(v["legal_review_complete"]),
            spatial_review_complete=(None if v["spatial_review_complete"]
                                     is None
                                     else bool(v["spatial_review_complete"])),
            evidence_required=bool(v["evidence_required"]),
            normative_basis=json.loads(v["normative_basis"]))
        reasons = is_rule_version_eligible(vr, store,
                                           activity_date="2026-09-17")
        assert reasons, f"{v['rule_id']} unexpectedly eligible"
        assert any(r.startswith("REVIEW_NOT_PUBLISHABLE") for r in reasons)
        assert "LEGAL_REVIEW_INCOMPLETE" in reasons
        assert "SPATIAL_REVIEW_INCOMPLETE" in reasons


# (scope, activity) pairs that carry a pending candidate rule — for those the
# resolver must also report INCOMPLETE knowledge; pairs without candidates may
# legitimately report CURRENT (nothing pending for that query).
_RULED_PAIRS = {
    "m8-pr-manzanares": {
        ("ss-prcam-reserva-natural", "ACAMPADA"),
        ("ss-prcam-reserva-natural", "VIVAC_AL_RASO"),
        ("ss-prcam-parque", "VIVAC_AL_RASO"),
    },
    "m8-pr-guadarrama-medio": {
        ("ss-prcmg-parque", "ACAMPADA"),
        ("ss-prcmg-parque", "VIVAC_AL_RASO"),
    },
    "m8-pr-sureste": {
        ("ss-prse-zona-a", "ACAMPADA"),
        ("ss-prse-zonas-b-e", "ACAMPADA"),
        ("ss-prse-zona-a", "VIVAC_AL_RASO"),
        ("ss-prse-zonas-b-e", "VIVAC_AL_RASO"),
    },
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_resolver_still_undetermined_with_satisfying_facts(case):
    """Facts satisfying the PROPOSED conditions cannot produce any outcome
    while review is pending — in either direction."""
    store, _fx = _load(case)
    facts = {"nights_same_zone": 1, "group_size": 4,
             "public_or_communal_land": True,
             "private_landowner_authorization": True}
    for scope in CASES[case]["scopes"]:
        for activity in ("VIVAC_AL_RASO", "ACAMPADA"):
            res = Resolver(store).resolve(
                _query(scope, activity=activity, facts=facts))
            assert res.legal_status is LegalStatus.UNDETERMINED, \
                f"{case}/{scope}/{activity}"
            if (scope, activity) in _RULED_PAIRS[case]:
                assert res.knowledge_status is KnowledgeStatus.INCOMPLETE, \
                    f"{case}/{scope}/{activity}"


@pytest.mark.parametrize("case", sorted(CASES))
def test_review_case_provenance_and_pending(case):
    rc = json.loads(io.open(EVIDENCE / case / "review_case.json",
                            encoding="utf-8").read())
    extract = EVIDENCE / case / rc["source"]["extract_file"]
    assert extract.exists()
    assert hashlib.sha256(extract.read_bytes()).hexdigest() \
        == rc["source"]["extract_sha256"]
    geo = EVIDENCE / case / next(iter(
        rc["geometry_evidence"]["layers"].values()))["file"]
    layer = next(iter(rc["geometry_evidence"]["layers"].values()))
    assert hashlib.sha256(geo.read_bytes()).hexdigest() == layer["sha256"]
    assert rc["reviewer_decision"] == "PENDING"
    assert rc["automated_state"] == "READY_FOR_HUMAN_REVIEW"


def test_sureste_annulled_prug_not_normative_basis():
    """The annulled Decreto 9/2009 PRUG must never ground a rule."""
    _store, fx = _load("m8-pr-sureste")
    prug_frags = {f["id"] for f in fx["legal_fragments"]
                  if f["source_document_id"] == "sd-decreto-9-2009-prug"}
    for v in fx["legal_rule_versions"]:
        assert not (set(v["evidence"]) & prug_frags), v["rule_id"]
        assert not (set(v["normative_basis"]) & prug_frags), v["rule_id"]
    sd = next(s for s in fx["source_documents"]
              if s["id"] == "sd-decreto-9-2009-prug")
    assert "ANULADO" in sd["official_status"]


def test_curso_medio_no_phantom_vivac_remision():
    """The verified finding: the Curso Medio PORN has NO vivac provision —
    the remission clause lives in Decreto 96/2009 (different PORN)."""
    _store, fx = _load("m8-pr-guadarrama-medio")
    gap = next(f for f in fx["legal_fragments"]
               if f["id"] == "lf-d26-vivac-ausencia")
    assert "NO existe" in gap["exact_text_hint"]
    # No rule may cite a PRUG that does not exist
    blob = json.dumps(fx)
    assert "prug-curso-medio" not in blob
