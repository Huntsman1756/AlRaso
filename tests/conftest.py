"""Shared hermetic helpers: build corpora that are ELIGIBLE by default, so
each test can break exactly ONE safety axis and prove the outcome."""

from __future__ import annotations

from typing import Any

from alraso.bitemporal import BitemporalStore, VersionRow


def make_version(seq=1, rule_id="alraso:es:t/c#a", effect="PERMITTED", condition=None,
                 activity="VIVAC_AL_RASO"):
    return VersionRow(seq=seq, rule_id=rule_id, activity=activity,
                      spatial_scope_id="s-x", effect=effect, condition=condition,
                      effective_from="2020-01-01", effective_to=None,
                      recorded_at="2020-06-01", recorded_until=None,
                      evidence=["lf-x"], interpretation_note=None,
                      review_status="VERIFIED", legal_review_complete=True,
                      evidence_required=True)

DOC = {
    "id": "sd-test", "authority": "Test Authority", "jurisdiction": "ES-TEST",
    "document_type": "TEST", "title": "Test corpus", "canonical_url": "https://example.test/a",
}


def new_store() -> BitemporalStore:
    return BitemporalStore.connect(":memory:")


def ensure_doc(s: BitemporalStore, doc_id: str = DOC["id"]) -> None:
    if s.conn.execute("SELECT 1 FROM source_document WHERE id=?", (doc_id,)).fetchone() is None:
        s.add_source_document({**DOC, "id": doc_id})


def frag(s: BitemporalStore, frag_id: str, doc_id: str = DOC["id"]) -> str:
    ensure_doc(s, doc_id)
    if s.conn.execute("SELECT 1 FROM legal_fragment WHERE id=?", (frag_id,)).fetchone() is None:
        s.add_legal_fragment({"id": frag_id, "source_document_id": doc_id,
                              "locator": f"art. {frag_id}"})
    return frag_id


def scope(s: BitemporalStore, scope_id: str, *, parent: str | None = None,
          scope_type: str = "PARK_SECTOR", review_status: str | None = None,
          geometry: str | None = None) -> str:
    if s.get_scope(scope_id) is None:
        s.add_spatial_scope({"id": scope_id, "scope_type": scope_type,
                             "parent_scope": parent, "official_name": scope_id,
                             "geometry_source": geometry, "review_status": review_status})
    return scope_id


def rule(s: BitemporalStore, rule_id: str, scope_id: str, effect: str, *,
         activity: str = "VIVAC_AL_RASO", condition: dict[str, Any] | None = None,
         ef: str = "2020-01-01", et: str | None = None, rec: str = "2020-06-01",
         rec_until: str | None = None, review: str = "VERIFIED", legal: bool = True,
         spatial: bool | None = True, evidence: tuple[str, ...] | None = ("lf-test",),
         ) -> None:
    """Fully eligible rule by default (review + evidence resolvable)."""
    ev = list(evidence or ())
    for f in ev:
        frag(s, f)
    s.add_rule_version({
        "rule_id": rule_id, "activity": activity, "spatial_scope_id": scope_id,
        "effect": effect, "condition": condition, "effective_from": ef, "effective_to": et,
        "recorded_at": rec, "recorded_until": rec_until, "review_status": review,
        "legal_review_complete": legal, "spatial_review_complete": spatial,
        "evidence": ev})


def relation(s: BitemporalStore, relation_id: str, from_rule: str, to_rule: str, **kw: Any) -> None:
    ev = list(kw.pop("evidence", ["lf-test"]))
    for f in ev:
        frag(s, f)
    s.add_relation({
        "relation_id": relation_id,
        "relation_type": kw.pop("relation_type", "OVERRIDES"),
        "from_rule_id": from_rule, "to_rule_id": to_rule,
        "from_effect": kw.pop("from_effect", None), "to_effect": kw.pop("to_effect", None),
        "effective_from": kw.pop("effective_from", "2020-01-01"),
        "effective_to": kw.pop("effective_to", None),
        "recorded_at": kw.pop("recorded_at", "2020-06-01"),
        "recorded_until": kw.pop("recorded_until", None),
        "review_status": kw.pop("review_status", "VERIFIED"),
        "legal_review_complete": kw.pop("legal_review_complete", True),
        "ai_proposed": kw.pop("ai_proposed", False),
        "human_verified": kw.pop("human_verified", True),
        "evidence": ev, **kw})
