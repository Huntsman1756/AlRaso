"""Shared hermetic helpers: build corpora that are ELIGIBLE by default, so
each test can break exactly ONE safety axis and prove the outcome."""

from __future__ import annotations

from typing import Any

from alraso.bitemporal import BitemporalStore, VersionRow


def make_version(seq=1, rule_id="alraso:es:t/c#a", effect="PERMITTED", condition=None,
                 activity="VIVAC_AL_RASO", evidence=("lf-x",),
                 spatial_scope_id="s-x", norm_basis: tuple[str, ...] | None = None):
    if norm_basis is None:
        norm_basis = list(evidence) if evidence else []
    return VersionRow(seq=seq, rule_id=rule_id, activity=activity,
                      spatial_scope_id=spatial_scope_id, effect=effect, condition=condition,
                      effective_from="2020-01-01", effective_to=None,
                      recorded_at="2020-06-01", recorded_until=None,
                      evidence=list(evidence), interpretation_note=None,
                      review_status="VERIFIED", legal_review_complete=True,
                      evidence_required=True, normative_basis=list(norm_basis))


DOC = {
    "id": "sd-test", "authority": "Test Authority", "jurisdiction": "ES-TEST",
    "document_type": "TEST", "title": "Test corpus", "canonical_url": "https://example.test/a",
}


def new_store() -> BitemporalStore:
    return BitemporalStore.connect(":memory:")


def ensure_doc(s: BitemporalStore, doc_id: str = DOC["id"]) -> None:
    if s.conn.execute("SELECT 1 FROM source_document WHERE id=?", (doc_id,)).fetchone() is None:
        s.add_source_document({**DOC, "id": doc_id})


def frag(s: BitemporalStore, frag_id: str, doc_id: str = DOC["id"],
         review_status: str = "VERIFIED", *,
         provision_ref: str | None = None,
         validity_from: str | None = None,
         validity_to: str | None = None) -> str:
    """Publishable provenance by default; pass review_status explicitly to make
    a fragment non-publishable (H2/D3 — production default is REVIEW_REQUIRED).
    When provision_ref/validity_from are set the fragment is treated as normative."""
    ensure_doc(s, doc_id)
    if s.conn.execute("SELECT 1 FROM legal_fragment WHERE id=?", (frag_id,)).fetchone() is None:
        s.add_legal_fragment({
            "id": frag_id, "source_document_id": doc_id,
            "locator": f"art. {frag_id}",
            "review_status": review_status,
            "provision_ref": provision_ref if provision_ref is not None else f"art. {frag_id}",
            "validity_from": validity_from,
            "validity_to": validity_to,
        })
    return frag_id


def scope(s: BitemporalStore, scope_id: str, *, parent: str | None = None,
          scope_type: str = "PARK_SECTOR", review_status: str | None = None,
          geometry: str | None = None,
          relevance: str | None = "REGULATORY") -> str:
    if s.get_scope(scope_id) is None:
        s.add_spatial_scope({"id": scope_id, "scope_type": scope_type,
                             "parent_scope": parent, "official_name": scope_id,
                             "geometry_source": geometry, "review_status": review_status,
                             "relevance": relevance})
    return scope_id


def rule(s: BitemporalStore, rule_id: str, scope_id: str, effect: str, *,
         activity: str = "VIVAC_AL_RASO", condition: dict[str, Any] | None = None,
         ef: str = "2020-01-01", et: str | None = None, rec: str = "2020-06-01",
         rec_until: str | None = None, review: str = "VERIFIED", legal: bool = True,
         spatial: bool | None = True, evidence: tuple[str, ...] | None = ("lf-test",),
         frag_status: str = "VERIFIED",
         norm_basis: tuple[str, ...] | None = None,  # sentinel: use evidence; pass () for empty
         ) -> None:
    """Fully eligible rule by default (review + evidence resolvable + normative basis).

    By default fragments get provision_ref and validity_from so they pass normative
    validity checks, and the version gets normative_basis equal to its evidence list.
    Pass norm_basis=() explicitly to test the NORMATIVE_BASIS_MISSING path.
    """
    ev = list(evidence or ())
    for f in ev:
        frag(s, f, review_status=frag_status,
             provision_ref=f"art. {f}", validity_from="1900-01-01", validity_to=None)
    if norm_basis is None:
        norm_basis = tuple(ev) if ev else ()
    s.add_rule_version({
        "rule_id": rule_id, "activity": activity, "spatial_scope_id": scope_id,
        "effect": effect, "condition": condition, "effective_from": ef, "effective_to": et,
        "recorded_at": rec, "recorded_until": rec_until, "review_status": review,
        "legal_review_complete": legal, "spatial_review_complete": spatial,
        "evidence": ev, "normative_basis": list(norm_basis)})


def relation(s: BitemporalStore, relation_id: str, from_rule: str, to_rule: str, **kw: Any) -> None:
    ev = list(kw.pop("evidence", ["lf-test"]))
    for f in ev:
        frag(s, f, provision_ref=f"art. {f}", validity_from="1900-01-01", validity_to=None)
    nb = list(kw.pop("norm_basis", ev))
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
        "evidence": ev, "normative_basis": nb, **kw})


def raw_version(s: BitemporalStore, rule_id: str, effect: str, *, ef: str,
                et: str | None, rec: str, scope_id: str = "s-x",
                activity: str = "VIVAC_AL_RASO",
                evidence: tuple[str, ...] = ("lf-test",),
                norm_basis: tuple[str, ...] | None = None) -> None:
    """Insert a version row directly, bypassing the writer and its ambiguity
    gate: simulates a legacy dump or a store written by a pre-hardening binary,
    so the READ side must hold the line (H1/D2)."""
    import json

    ensure_doc(s)
    frag(s, "lf-test", provision_ref="art. lf-test", validity_from="1900-01-01", validity_to=None)
    if norm_basis is None:
        norm_basis = evidence if evidence else ()
    s.conn.execute(
        "INSERT INTO legal_rule_version (rule_id,activity,spatial_scope_id,effect,condition,"
        "effective_from,effective_to,recorded_at,recorded_until,evidence,"
        "interpretation_note,review_status,legal_review_complete,spatial_review_complete,"
        "evidence_required,normative_basis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rule_id, activity, scope_id, effect, None, ef, et, rec, None,
         json.dumps(list(evidence)), None, "VERIFIED",
         1, 1, 1, json.dumps(list(norm_basis))))
    s.conn.commit()
