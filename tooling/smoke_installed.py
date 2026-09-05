"""Installed-package smoke battery (M1 gate F09 + hardening H1-H4).

Run this with a Python interpreter that imports `alraso` from site-packages and
with the current directory OUTSIDE the checkout: the property under test is that
the built artifact behaves, not that the working tree works.

    python tooling/smoke_installed.py        # exit 0 = all smokes passed

Covered:
  - packaged fixture resolves the canonical Ordesa pair (PERMITTED / PROHIBITED)
  - F01: an unreviewed rule cannot permit
  - H1: overlapping visible lineages of one rule_id are refused
  - H2: evidence with unverified provenance cannot back a permit
  - H3: a REGULATORY jurisdiction without publishable coverage is not permission
  - H4: malformed facts fail closed instead of raising
"""

from __future__ import annotations

import sys

from alraso.bitemporal import BitemporalStore
from alraso.domain import LegalStatus, Query
from alraso.engine_axiom import AXIOM_PARITY, AXIOM_STATUS
from alraso.errors import OverlappingRuleVersions
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver
from alraso.spatial import InMemorySpatialProvider

Q = dict(activity="VIVAC_AL_RASO", activity_date="2021-01-01", knowledge_date="2023-01-01",
         spatial_scope_id="s")
DOC = {"id": "sd", "authority": "A", "jurisdiction": "ES", "document_type": "T",
       "title": "T", "canonical_url": "https://example.test/t"}


def store_with_scope(fragment_status: str = "VERIFIED") -> BitemporalStore:
    store = BitemporalStore.connect(":memory:")
    store.add_spatial_scope({"id": "s", "scope_type": "OTHER", "official_name": "S"})
    store.add_source_document(DOC)
    store.add_legal_fragment({"id": "lf", "source_document_id": "sd", "locator": "art. 1",
                              "review_status": fragment_status})
    return store


def add_rule(store: BitemporalStore, rid: str, effect: str, *, ef: str = "2020-01-01",
             review: str = "VERIFIED", evidence: tuple[str, ...] = ("lf",)) -> None:
    store.add_rule_version({"rule_id": rid, "activity": "VIVAC_AL_RASO",
                            "spatial_scope_id": "s", "effect": effect,
                            "effective_from": ef, "recorded_at": "2020-06-01",
                            "review_status": review, "legal_review_complete": True,
                            "evidence": list(evidence)})


def packaged_fixture_resolves() -> None:
    store = BitemporalStore.connect(":memory:")
    load_ordesa(store)                       # packaged resource via importlib.resources
    r = Resolver(store)
    pre = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                          knowledge_date="2023-06-15",
                          spatial_scope_id="ss-ordesa-sector-ordesa"))
    post = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2023-06-15",
                           knowledge_date="2023-06-15",
                           spatial_scope_id="ss-ordesa-sector-ordesa"))
    assert pre.legal_status is LegalStatus.PERMITTED, pre.legal_status
    assert post.legal_status is LegalStatus.PROHIBITED, post.legal_status
    print("OK fixture: 2021 PERMITTED / 2023 PROHIBITED")


def unreviewed_rule_cannot_permit() -> None:
    store = store_with_scope()
    add_rule(store, "alraso:es:t#w#rr", "PERMITTED", review="REVIEW_REQUIRED", evidence=())
    res = Resolver(store).resolve(Query(**Q))
    assert res.legal_status is LegalStatus.UNDETERMINED, "unreviewed rule permitted!"
    print("OK F01: unreviewed rule cannot permit")


def overlapping_lineages_are_refused() -> None:
    store = store_with_scope()
    add_rule(store, "alraso:es:t#w#ov", "PERMITTED")
    try:
        add_rule(store, "alraso:es:t#w#ov", "PROHIBITED", ef="2020-06-01")
        raise AssertionError("overlapping rule versions were accepted")
    except OverlappingRuleVersions:
        pass
    assert Resolver(store).resolve(Query(**Q)).legal_status is LegalStatus.PERMITTED
    print("OK H1: overlapping visible lineages refused, earlier answer intact")


def unverified_evidence_cannot_back_a_permit() -> None:
    store = store_with_scope(fragment_status="DISCOVERED")
    add_rule(store, "alraso:es:t#w#ev", "PERMITTED")
    res = Resolver(store).resolve(Query(**Q))
    assert res.legal_status is LegalStatus.UNDETERMINED, "unverified fragment permitted!"
    assert "EVIDENCE_NOT_PUBLISHABLE" in res.reason_codes, res.reason_codes
    print("OK H2: unpublishable evidence cannot permit")


def uncovered_regulatory_jurisdiction_is_not_permission() -> None:
    store = BitemporalStore.connect(":memory:")
    store.add_source_document(DOC)
    store.add_legal_fragment({"id": "lf", "source_document_id": "sd", "locator": "art. 1",
                              "review_status": "VERIFIED"})
    for sid in ("s", "s2"):
        store.add_spatial_scope({"id": sid, "scope_type": "OTHER", "official_name": sid,
                                 "geometry_source": "sd", "review_status": "VERIFIED"})
    store.add_rule_version({"rule_id": "alraso:es:t#w#cov", "activity": "VIVAC_AL_RASO",
                            "spatial_scope_id": "s", "effect": "PERMITTED",
                            "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                            "review_status": "VERIFIED", "legal_review_complete": True,
                            "spatial_review_complete": True, "evidence": ["lf"]})
    prov = InMemorySpatialProvider()
    prov.add_scope("s", "s", "OTHER", [[(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]])
    prov.add_scope("s2", "s2", "OTHER", [[(0.5, 0.5), (0.5, 1.5), (1.5, 1.5), (1.5, 0.5)]])
    res = Resolver(store, spatial=prov).resolve(
        Query(activity="VIVAC_AL_RASO", activity_date="2021-01-01",
              knowledge_date="2023-01-01", lat=0.7, lon=0.7))
    assert res.legal_status is LegalStatus.UNDETERMINED, "PERMITTED over uncovered scope"
    assert "INCOMPLETE_SCOPE_COVERAGE" in res.reason_codes, res.reason_codes
    print("OK H3: uncovered regulatory scope blocks PERMITTED")


def malformed_facts_fail_closed() -> None:
    store = store_with_scope()
    add_rule(store, "alraso:es:t#w#ok", "PERMITTED")
    res = Resolver(store).resolve(Query(**Q, facts="nope"))
    assert res.legal_status is LegalStatus.UNDETERMINED and res.reason_codes, res
    assert Resolver(store).resolve(Query(**Q)).legal_status is LegalStatus.PERMITTED
    print("OK H4: malformed facts fail closed, valid facts still permit")


def honesty_constants() -> None:
    assert AXIOM_STATUS == "EXPERIMENTAL_ADAPTER", AXIOM_STATUS
    assert AXIOM_PARITY == "NOT_PROVEN", AXIOM_PARITY
    print("OK status constants: AXIOM_STATUS/AXIOM_PARITY honest")


def main() -> int:
    print(f"python:     {sys.version.split()[0]}")
    import alraso
    print(f"alraso at:  {alraso.__file__}")
    for check in (packaged_fixture_resolves, unreviewed_rule_cannot_permit,
                  overlapping_lineages_are_refused,
                  unverified_evidence_cannot_back_a_permit,
                  uncovered_regulatory_jurisdiction_is_not_permission,
                  malformed_facts_fail_closed, honesty_constants):
        check()
    print("INSTALLED_PACKAGE_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
