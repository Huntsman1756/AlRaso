"""Integration tests against the REAL Axiom binary (EXPERIMENTAL adapter).

Skipped unless ALRASO_AXIOM_BIN (executable) and ALRASO_AXIOM_ROOT (directory
named rulespec-<country>) are provided. Run inside Docker with:
  discovery/spikes/m1-axiom-integration/run-docker.ps1

Parity is NOT claimed: AXIOM_PARITY=NOT_PROVEN until this suite plus the
shared contract suite (tests/test_engine_contract.py) pass end-to-end and the
gate is explicitly lifted (which M1 does not do).
"""

import os

import pytest

from alraso.bitemporal import BitemporalStore
from alraso.domain import LegalStatus, Query
from alraso.engine_axiom import AXIOM_PARITY, AxiomCliAdapter, generate_rulespec
from alraso.errors import UnsupportedEngineCapability
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver

BIN = os.environ.get("ALRASO_AXIOM_BIN", "")
ROOT = os.environ.get("ALRASO_AXIOM_ROOT", "")
SECTOR = "ss-ordesa-sector-ordesa"

pytestmark = pytest.mark.skipif(
    not (BIN and ROOT and os.path.exists(BIN)
         and os.path.basename(ROOT.rstrip("/\\")).startswith("rulespec-")),
    reason="provide ALRASO_AXIOM_BIN + ALRASO_AXIOM_ROOT (run via m1-axiom-integration/run-docker.ps1)")


def axiom_resolver(tmp_path) -> Resolver:
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    return Resolver(s, engine=AxiomCliAdapter(BIN, ROOT, tmp_path / "axiom-cache"))


def q(date):
    return Query(activity="VIVAC_AL_RASO", activity_date=date, knowledge_date="2023-06-15",
                 spatial_scope_id=SECTOR)


def test_axiom_agrees_with_wrapper_selection_on_ordesa(tmp_path):
    r = axiom_resolver(tmp_path)
    pre = r.resolve(q("2021-07-15"))
    post = r.resolve(q("2023-06-15"))
    assert pre.legal_status is LegalStatus.PERMITTED
    assert post.legal_status is LegalStatus.PROHIBITED
    evals = [t for t in pre.to_dict()["precedenceTrace"] if t["stage"] == "engine_eval"]
    assert evals and evals[0]["engine"] == "axiom-cli"
    # identity preserved on the real engine path
    assert pre.basis["rule_seqs"]


def test_axiom_refuses_conditional_rules_end_to_end(tmp_path):
    # ACAMPADA rule carries a real condition -> the resolver must refuse via
    # the capability contract (never a silent condition drop).
    r = axiom_resolver(tmp_path)
    res = r.resolve(Query(activity="ACAMPADA", activity_date="2021-07-15",
                          knowledge_date="2023-06-15", spatial_scope_id=SECTOR,
                          facts={"altitude_m": 2500}))
    assert res.legal_status is LegalStatus.UNDETERMINED
    assert any(code.startswith("UNSUPPORTED_ENGINE_CAPABILITY") for code in res.reason_codes)


def test_axiom_rule_identity_survives_real_roundtrip(tmp_path):
    r = axiom_resolver(tmp_path)
    res = r.resolve(q("2023-06-15"))
    j = res.to_dict()  # sanity serialize
    assert res.legal_status.value == "PROHIBITED"
    # the store row behind the judgment carries the durable rule id
    assert res.rule_versions[0]["rule_id"].startswith("alraso:")


def test_compile_cache_is_content_addressed(tmp_path):
    s = BitemporalStore.connect(":memory:")
    load_ordesa(s)
    adapter = AxiomCliAdapter(BIN, ROOT, tmp_path / "cache")
    sel = s.select("VIVAC_AL_RASO", SECTOR, "2023-06-15", "2023-06-15")
    _, yaml_text = generate_rulespec(sel.covering[0])
    c1 = adapter.compile_bundle(yaml_text, "es:policies/vivac/cachetest")
    c2 = adapter.compile_bundle(yaml_text, "es:policies/vivac/cachetest")
    assert c1.path == c2.path
    import json
    assert json.loads(c2.path.read_text(encoding="utf-8"))  # valid, reused
    other = s.select("VIVAC_AL_RASO", SECTOR, "2021-07-15", "2023-06-15")
    _, y2 = generate_rulespec(other.covering[0])
    c3 = adapter.compile_bundle(y2, "es:policies/vivac/cachetest2")
    assert c3.path != c1.path                    # knowledge-state change -> new artifact


def test_parity_flag_stays_false_while_gate_closed():
    assert AXIOM_PARITY == "NOT_PROVEN"
