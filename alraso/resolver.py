"""The resolver: Query -> ResolveResult (discovery §L contract, M1-remediated).

Pipeline (each stage appended to precedenceTrace):
  1. strict query validation (facts structure FIRST) + closed activity vocab
  2. spatial resolution          -> lat/lon to ALL intersecting scopes (F03:
                                     composition, never a single "picked" scope)
  3. bitemporal selection        -> governing LegalRuleVersion per rule_id per
                                     scope (system time x valid time)
  3b. eligibility gate           -> ONLY publishable rule versions participate
                                     (F01, alraso.eligibility — single site;
                                     H2/D3 includes fragment review status)
  3c. overlap gate               -> visible+applicable versions of one rule_id
                                     that overlap in valid time are ambiguity,
                                     never a ranking (H1/D2)
  3d. coverage map               -> REGULATORY scopes must have publishable
                                     coverage; CONTEXT_ONLY is explicit (H3/D4)
  4. engine evaluation           -> capability contract pre-checked (F02), then
                                     conditions over facts via the adapter
  5. precedence                  -> grounded resolution over the COMPLETE set
                                     with bitemporal relations (F04); ambiguous
                                     relation versions are inert + conflicting
  5b. coverage gate              -> a PERMITTED may not stand on an unresolved
                                     applicable jurisdiction (H3/D4)
  6. PERMITTED invariant gate    -> defense-in-depth: a PERMITTED must prove
                                     every clause of the safety contract (F25)
  7. composition                 -> legalStatus x knowledgeStatus + evidence +
                                     trace + conflicts + warnings; canonical
                                     replay record when record=True (F05)

Safety invariants (WHEN_IN_DOUBT -> UNDETERMINED, NEVER_GUESS):
  - Nothing here can return PERMITTED from an absence: empty selection, a
    temporal gap, ineligible rules, a missing fact, an unsupported condition,
    an unresolved conflict or an engine failure never yield PERMITTED.
  - Absence of a known prohibition is not permission, and neither is an
    applicable jurisdiction whose regulation we do not (yet) publish.
  - Conflicts report legalStatus=UNDETERMINED + knowledgeStatus=CONFLICTING
    (never a winner; never first-wins/most-specific-wins/latest-wins).
  - resolve() normalizes malformed input (non-dict facts included) instead of
    leaking a traceback (H4/D1).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from alraso.bitemporal import (
    BitemporalStore,
    PUBLISHABLE_REVIEW_STATUSES,
    RelationVersionRow,
    VersionRow,
    version_material_signature,
)
from alraso.domain import (
    Activity,
    KnowledgeStatus,
    LegalStatus,
    Query,
    ResolveResult,
)
from alraso.eligibility import is_rule_version_eligible
from alraso.engine import RuleEngineAdapter, OwnEvaluatorAdapter, collect_requirements
from alraso.errors import (
    AlRasoError,
    EngineFailure,
    SpatialResolutionError,
    REASON_ACTIVITY_VOCAB,
    REASON_AMBIGUOUS_RELATIONS,
    REASON_EVIDENCE_NOT_PUBLISHABLE,
    REASON_INVARIANT_VIOLATION,
    REASON_INCOMPLETE_SCOPE_COVERAGE,
    REASON_NO_ACTIVE_RULE,
    REASON_NO_ELIGIBLE_RULE,
    REASON_NO_KNOWLEDGE,
    REASON_NO_SCOPE,
    REASON_OVERLAPPING_VERSIONS,
    REASON_TEMPORAL_GAP,
    REASON_UNRESOLVED_CONFLICT,
)
from alraso.precedence import (
    Judgment,
    ambiguous_relation_groups,
    relation_is_applicable,
    resolve_precedence,
)
from alraso.spatial import SpatialFactsProvider, ScopeHit
from alraso.validation import parse_date_strict, validate_facts

STANDING_WARNING = ("Las restricciones operativas no codificadas en el corpus "
                    "(acceso de vehiculos, reservas, cierres estacionales, avisos "
                    "de la direccion) no estan cubiertas por esta determinacion.")

RESOLVER_VERSION = "0.2.1-hardening"
SCHEMA_VERSION = "m1r2"

DRIFT_TYPES = ("LEGAL_STATUS_CHANGED", "KNOWLEDGE_STATUS_CHANGED", "RULE_SET_CHANGED",
               "EVIDENCE_CHANGED", "PRECEDENCE_CHANGED", "SPATIAL_SCOPE_CHANGED",
               "FACT_SOURCE_CHANGED", "NO_MATERIAL_CHANGE")


def _basis(scope_ids: list[str] | None = None, rule_seqs: list[int] | None = None,
           relation_seqs: list[int] | None = None,
           fragment_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "scope_ids": sorted(scope_ids or []),
        "rule_seqs": sorted(rule_seqs or []),
        "relation_seqs": sorted(relation_seqs or []),
        "fragment_ids": sorted(fragment_ids or []),
    }


def overlapping_version_groups(versions: list[VersionRow]) -> list[dict[str, Any]]:
    """Visible+applicable versions of the SAME (rule_id, activity, scope) that
    come from different lineages and overlap in valid time (H1/D2).

    Materially identical duplicates are reported separately: they do not change
    the legal answer, but they must never pass unnoticed.
    """
    groups: dict[tuple[str, str, str], list[VersionRow]] = {}
    for v in versions:
        groups.setdefault((v.rule_id, v.activity, v.spatial_scope_id), []).append(v)
    out: list[dict[str, Any]] = []
    for (rule_id, activity, scope), rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        sigs = {version_material_signature(v) for v in rows}
        out.append({
            "rule_id": rule_id, "activity": activity, "scope_id": scope,
            "seqs": sorted(v.seq for v in rows),
            "effects": sorted({v.effect for v in rows}),
            "windows": sorted([[v.effective_from, v.effective_to] for v in rows]),
            "material_identical": len(sigs) == 1,
        })
    return out


class Resolver:
    def __init__(self, store: BitemporalStore, spatial: SpatialFactsProvider | None = None,
                 engine: RuleEngineAdapter | None = None) -> None:
        self.store = store
        self.spatial = spatial
        self.engine: RuleEngineAdapter = engine or OwnEvaluatorAdapter()

    # ---- public --------------------------------------------------------------
    def resolve(self, query: Query, *, mode: str = "fast", record: bool = False) -> ResolveResult:
        """Never lets an expected failure escape as a traceback: every
        normalized error (and any unforeseen one) becomes UNDETERMINED with a
        reason code (never PERMITTED)."""
        try:
            return self._resolve_inner(query, mode=mode, record=record)
        except AlRasoError as e:
            return self._fail(query, reason=e.reason_code, message=str(e), record=record,
                              knowledge=KnowledgeStatus.INCOMPLETE)
        except sqlite3.Error as e:
            return self._fail(query, reason="STORE_FAILURE", message=str(e), record=record,
                              knowledge=KnowledgeStatus.INCOMPLETE)
        except Exception as e:  # unforeseen: still fail-closed, never PERMITTED
            return self._fail(query, reason="UNEXPECTED_FAILURE",
                              message=f"{type(e).__name__}: {e}", record=record,
                              knowledge=KnowledgeStatus.INCOMPLETE)

    # ---- pipeline --------------------------------------------------------------
    def _resolve_inner(self, query: Query, *, mode: str, record: bool) -> ResolveResult:
        trace: list[dict[str, Any]] = []

        # (0) strict query validation BEFORE anything is built (H4/D1): a
        # structurally broken query must be normalized, never crash.
        parse_date_strict(query.activity_date, field="activity_date")
        parse_date_strict(query.knowledge_date, field="knowledge_date")
        facts = validate_facts(query.facts)

        result = ResolveResult(legal_status=LegalStatus.UNDETERMINED,
                               knowledge_status=KnowledgeStatus.CURRENT,
                               query=query.as_dict())
        result.warnings.append(STANDING_WARNING)

        # (1) closed activity vocabulary -------------------------------------------
        activity = query.activity
        if Activity.parse(activity) is None:
            return self._fail(query, reason=REASON_ACTIVITY_VOCAB,
                              message=f"actividad fuera del vocabulario cerrado: {activity!r}",
                              record=record,
                              trace=trace)
        trace.append({"stage": "activity_vocab", "ok": True, "activity": activity})

        # (2) spatial resolution: ALL applicable scopes (F03) ------------------------
        hits = self._resolve_scopes(query)
        result.applicable_scope = [h.as_dict() for h in hits]
        scope_ids = [h.scope_id for h in hits]
        trace.append({"stage": "spatial", "scope_ids": scope_ids})
        if not hits:
            return self._fail(query, reason=REASON_NO_SCOPE,
                              message="no hay ambito espacial resoluble para este punto/scope",
                              record=record, scopes=hits,
                              trace=trace)

        # (3) bitemporal selection across ALL scopes (F03) ----------------------------
        covering: list[VersionRow] = []
        per_scope_covering: dict[str, list[VersionRow]] = {}
        gap_scopes: list[str] = []
        empty_scopes: list[str] = []
        for h in sorted(hits, key=lambda x: x.scope_id):
            sel = self.store.select(activity, h.scope_id, query.activity_date,
                                    query.knowledge_date)
            covering.extend(sel.covering)
            per_scope_covering[h.scope_id] = list(sel.covering)
            if sel.is_gap:
                gap_scopes.append(h.scope_id)
            elif sel.is_empty:
                empty_scopes.append(h.scope_id)
        covering.sort(key=lambda v: v.seq)
        trace.append({"stage": "bitemporal_select",
                      "covering": [(v.rule_id, v.seq) for v in covering],
                      "gap_scopes": gap_scopes, "empty_scopes": empty_scopes})
        if not covering:
            if gap_scopes:
                return self._fail(query, reason=REASON_TEMPORAL_GAP,
                                  message=("nuestro conocimiento termina antes de la "
                                           "activity_date (version expirada sin sucesor "
                                           "visible)"),
                                  record=record, scopes=hits,
                                  knowledge=KnowledgeStatus.INCOMPLETE,
                                  trace=trace)
            return self._fail(query, reason=REASON_NO_KNOWLEDGE,
                              message=("sin version conocida a esta knowledge_date "
                                       "(fuera del ambito modelado)"),
                              record=record, scopes=hits,
                              trace=trace)

        # (3b) eligibility gate: publishable rules only (F01) --------------------------
        eligible: list[VersionRow] = []
        excluded: list[dict[str, Any]] = []
        for v in covering:
            reasons = is_rule_version_eligible(v, self.store)
            if reasons:
                excluded.append({"rule_id": v.rule_id, "seq": v.seq, "reasons": reasons})
            else:
                eligible.append(v)
        trace.append({"stage": "eligibility", "eligible": [v.seq for v in eligible],
                      "excluded": excluded})
        if excluded:
            result.warnings.append(
                "reglas excluidas por no ser publicables: "
                + ", ".join(f"{e['rule_id']}(seq {e['seq']})" for e in excluded))
        if not eligible:
            codes = [REASON_NO_ELIGIBLE_RULE]
            if all(any(r.startswith("EVIDENCE_") for r in e["reasons"]) for e in excluded):
                codes.append(REASON_EVIDENCE_NOT_PUBLISHABLE)
            return self._fail(query, reason=codes[0],
                              message=("ninguna regla aplicable es publicable "
                                       "(revision/evidencia incompletas)"),
                              record=record, scopes=hits,
                              knowledge=KnowledgeStatus.INCOMPLETE, extra_codes=codes[1:],
                              trace=trace)

        # (3c) same-rule overlapping versions (H1/D2): never ranked away -------------
        groups = overlapping_version_groups(eligible)
        hard = [g for g in groups if not g["material_identical"]]
        dupes = [g for g in groups if g["material_identical"]]
        if hard:
            trace.append({"stage": "overlapping_versions", "groups": hard})
            conflict_result = self._fail(query, reason=REASON_OVERLAPPING_VERSIONS,
                                         message=("versiones simultaneamente visibles de la "
                                                  "misma regla con ventanas de validez "
                                                  "solapadas y contenido distinto: no puede "
                                                  "demostrarse la version canonica"),
                                         record=record, scopes=hits,
                                         knowledge=KnowledgeStatus.CONFLICTING,
                                         trace=trace)
            conflict_result.unresolved_conflicts = hard
            conflict_result.evidence = self._evidence_for(eligible)
            return conflict_result
        if dupes:
            # duplicate double-entry: same legal content, kept as ONE canonical
            # description and reported (never silently).
            trace.append({"stage": "overlapping_versions_duplicates", "groups": dupes})
            result.warnings.append(
                "doble registro materialmente identico (se conserva una sola descripcion "
                "equivalente y se reporta): "
                + ", ".join(f"{g['rule_id']}{g['seqs']}" for g in dupes))
            eligible = self._collapse_identical_duplicates(eligible)
        if gap_scopes or empty_scopes:
            result.warnings.append(
                "cobertura incompleta en ambitos: "
                + ", ".join(sorted(set(gap_scopes + empty_scopes))))

        # (3d) jurisdictional coverage of REGULATORY scopes (H3/D4) --------------------
        # A scope is REGULATORY unless a human declared it CONTEXT_ONLY: an
        # unresolved applicable jurisdiction is not permission. Context-only
        # scopes still contribute their rules; they just do not demand coverage.
        eligible_by_scope: dict[str, list[VersionRow]] = {sid: [] for sid in scope_ids}
        for v in eligible:
            eligible_by_scope.setdefault(v.spatial_scope_id, []).append(v)
        uncovered: list[dict[str, Any]] = []
        context_only: list[str] = []
        for sid in scope_ids:
            relevance = (self.store.get_scope(sid) or {}).get("relevance") or "REGULATORY"
            if relevance == "CONTEXT_ONLY":
                context_only.append(sid)
                continue
            if sid in gap_scopes:
                uncovered.append({"scope_id": sid, "reason": REASON_TEMPORAL_GAP})
            elif sid in empty_scopes:
                uncovered.append({"scope_id": sid, "reason": REASON_NO_KNOWLEDGE})
            elif not eligible_by_scope.get(sid):
                uncovered.append({"scope_id": sid, "reason": REASON_NO_ELIGIBLE_RULE})
        trace.append({"stage": "scope_coverage",
                      "covering_by_scope": {sid: sorted(v.seq for v in rows)
                                            for sid, rows in per_scope_covering.items()},
                      "uncovered_regulatory": uncovered,
                      "context_only_scopes": context_only})

        # (4) engine: capability contract FIRST, then evaluate (F02) --------------------
        kinds, ops, effects = collect_requirements(eligible)
        unsupported = self.engine.capabilities().check(
            kinds=kinds, ops=ops, effects=effects, n_versions=len(eligible), mode=mode)
        if unsupported is not None:
            return self._fail(query, reason=f"UNSUPPORTED_ENGINE_CAPABILITY:{unsupported}",
                              message=(f"engine {self.engine.name!r} no soporta "
                                       f"{unsupported}; no se degrada silenciosamente"),
                              record=record, scopes=hits,
                              knowledge=KnowledgeStatus.INCOMPLETE,
                              trace=trace)
        try:
            engine_result = self.engine.evaluate(eligible, facts, mode=mode)
        except EngineFailure as e:
            trace.append({"stage": "engine_error", "reason": e.reason_code,
                          "message": str(e)})
            result.warnings.append(f"motor devolvio {e.reason_code}; fail-closed a UNDETERMINED")
            return self._fail(query, reason=e.reason_code, message=str(e), record=record,
                              scopes=hits, knowledge=KnowledgeStatus.INCOMPLETE,
                              trace=trace)
        trace.append({"stage": "engine_eval", "engine": self.engine.name,
                      "outcomes": {j.rule_id: j.outcome for j in engine_result.judgments}})

        active = [j for j in engine_result.judgments if j.outcome == "holds"]
        result.conditions = [c for j in engine_result.judgments for c in j.conditions]
        result.rule_versions = [v.as_dict() for v in eligible]

        if not active:
            result.legal_status = LegalStatus.UNDETERMINED
            result.knowledge_status = KnowledgeStatus.INCOMPLETE
            result.decision_reason = ("version aplicable pero su condicion no se satisface "
                                      "(incompleto)")
            result.reason_codes = [REASON_NO_ACTIVE_RULE]
            result.precedence_trace = trace
            result.basis = _basis(scope_ids)
            self._record(result, query, record)
            return result

        # (5) precedence over the COMPLETE active set with bitemporal relations ---------
        by_seq = {v.seq: v for v in eligible}
        active_seqs = {j.rule_version_id for j in active}
        if not active_seqs <= set(by_seq):
            return self._fail(query, reason="ENGINE_IDENTITY_MISMATCH",
                              message="engine devolvio versiones ajenas a las evaluadas",
                              record=record, scopes=hits,
                              knowledge=KnowledgeStatus.INCOMPLETE,
                              trace=trace)
        active_versions = [by_seq[s] for s in sorted(active_seqs)]
        relations = self.store.relations_at([v.rule_id for v in active_versions],
                                            query.activity_date, query.knowledge_date)
        outcome = resolve_precedence(
            [Judgment(version=by_seq[j.rule_version_id], outcome=j.outcome)
             for j in sorted(active, key=lambda j: j.rule_version_id)], relations)
        trace.extend(outcome.trace)
        result.precedence_trace = trace

        if outcome.has_conflict:
            result.legal_status = LegalStatus.UNDETERMINED
            result.knowledge_status = KnowledgeStatus.CONFLICTING
            result.unresolved_conflicts = outcome.conflicts
            result.evidence = self._evidence_for(active_versions)
            result.decision_reason = ("conflicto normativo no resuelto (nunca se infiere "
                                      "PERMITTED; nunca first-wins/most-specific-wins)")
            codes = [REASON_UNRESOLVED_CONFLICT]
            if outcome.ambiguous_relation_ids:
                codes.append(REASON_AMBIGUOUS_RELATIONS)
            result.reason_codes = codes
            result.basis = _basis(scope_ids, [v.seq for v in active_versions],
                                  [r["seq"] for r in outcome.relations_used],
                                  self._fragments_of(result.evidence))
            result.precedence_trace = trace + [{"stage": "precedence",
                                                "survivors": [v.seq for v in outcome.survivors],
                                                "relations_used":
                                                    [r["seq"] for r in outcome.relations_used]}]
            self._record(result, query, record)
            return result

        effect = outcome.unique_effect
        if effect is None:
            return self._fail(query, reason=REASON_UNRESOLVED_CONFLICT,
                              message="supervivientes con efectos incompatibles", record=record,
                              scopes=hits, knowledge=KnowledgeStatus.CONFLICTING,
                              trace=trace)
        try:
            legal = LegalStatus(effect)
        except ValueError:
            return self._fail(query, reason="EFFECT_UNMAPPED",
                              message=f"efecto sin mapeo a estado legal: {effect!r}",
                              record=record, scopes=hits,
                              trace=trace)

        participating = list(outcome.survivors)
        used_rel_seqs = [r["seq"] for r in outcome.relations_used]
        result.evidence = self._evidence_for(participating)
        frag_ids = self._fragments_of(result.evidence)
        doc_ids = self._documents_of(result.evidence)

        # (5b) PERMITTED requires complete REGULATORY coverage (H3/D4) -------------------
        # Documented semantics: absence of a known prohibition is never a
        # permission, and neither is an unresolved applicable jurisdiction. A
        # restrictive answer (PROHIBITED / AUTHORIZATION_REQUIRED) may stand on a
        # single regulatory scope's positive prohibition — that is legally
        # sufficient — so this gate only blocks affirmative permission claims.
        if legal is LegalStatus.PERMITTED and uncovered:
            result.warnings.append(
                "PERMITTED bloqueado por cobertura regulatoria incompleta: "
                + ", ".join(f"{u['scope_id']}({u['reason']})" for u in uncovered))
            return self._fail(query, reason=REASON_INCOMPLETE_SCOPE_COVERAGE,
                              message=("ambitos regulatorios aplicables sin cobertura "
                                       "normativa publicable: "
                                       + ", ".join(f"{u['scope_id']}({u['reason']})"
                                                   for u in uncovered)),
                              record=record, scopes=hits,
                              knowledge=KnowledgeStatus.INCOMPLETE,
                              trace=trace)

        # (6) PERMITTED invariant gate (F25, defense in depth) ---------------------------
        if legal is LegalStatus.PERMITTED:
            violations = self._permitted_invariants(
                query=query, hits=hits, active_versions=active_versions,
                participating=participating,
                eligible_by_seq={v.seq: v.rule_id for v in eligible},
                evidence=result.evidence, relations=relations,
                used_rel_seqs=used_rel_seqs, knowledge_date=query.knowledge_date,
                engine_result=engine_result,
                via_coordinates=query.spatial_scope_id is None,
                eligible_versions=eligible, uncovered_regulatory=uncovered)
            if violations:
                result.warnings.append("PERMITTED bloqueado por el invariant: "
                                       + "; ".join(violations))
                return self._fail(query, reason=REASON_INVARIANT_VIOLATION,
                                  message="PERMITTED no demostrable: " + "; ".join(violations),
                                  record=record, scopes=hits,
                                  knowledge=KnowledgeStatus.INCOMPLETE,
                                  trace=trace)

        result.legal_status = legal
        result.decision_reason = self._decision_reason(legal, activity, participating)
        result.precedence_trace = trace + [
            {"stage": "precedence", "survivors": sorted(v.seq for v in participating),
             "relations_used": used_rel_seqs}]
        result.basis = _basis(scope_ids, [v.seq for v in participating], used_rel_seqs,
                              frag_ids)
        result.basis["source_document_ids"] = doc_ids
        self._record(result, query, record)
        return result

    # ---- spatial --------------------------------------------------------------------
    def _resolve_scopes(self, query: Query) -> list[ScopeHit]:
        """ALL applicable scopes. Never picks one (F03)."""
        if query.spatial_scope_id:
            scope = self.store.get_scope(query.spatial_scope_id)
            if scope is None:
                return []
            return [ScopeHit(query.spatial_scope_id, scope["official_name"],
                             scope["scope_type"])]
        if self.spatial is not None and query.lat is not None and query.lon is not None:
            try:
                hits = self.spatial.resolve(query.lat, query.lon)
            except Exception as e:
                raise SpatialResolutionError(f"provider fallo: {type(e).__name__}: {e}") from e
            # canonical order: scope_id (provider/ORDER BY order never matters)
            return sorted(hits, key=lambda h: h.scope_id)
        return []

    # ---- evidence helpers --------------------------------------------------------------
    def _evidence_for(self, versions: list[VersionRow]) -> list[dict[str, Any]]:
        ids: list[str] = []
        for v in versions:
            ids.extend(e for e in v.evidence if e not in ids)
        return self.store.get_fragments(ids)

    @staticmethod
    def _fragments_of(evidence: list[dict[str, Any]]) -> list[str]:
        return sorted({e["id"] for e in evidence})

    @staticmethod
    def _documents_of(evidence: list[dict[str, Any]]) -> list[str]:
        return sorted({e["source_document_id"] for e in evidence})

    def _decision_reason(self, legal: LegalStatus, activity: str,
                         participants: list[VersionRow]) -> str:
        scopes = sorted({v.spatial_scope_id for v in participants})
        base = (f"version(es) vigente(s) y publicable(s) determinan {legal.value} para "
                f"{activity} en {', '.join(scopes)}")
        if legal is LegalStatus.PERMITTED:
            base += " (invariant PERMITTED verificado)"
        return base

    # ---- PERMITTED invariant (F25) --------------------------------------------------------
    def _permitted_invariants(self, *, query: Query, hits: list[ScopeHit],
                              active_versions: list[VersionRow],
                              participating: list[VersionRow],
                              eligible_by_seq: dict[int, str],
                              evidence: list[dict[str, Any]],
                              relations: list[RelationVersionRow],
                              used_rel_seqs: list[int],
                              knowledge_date: str,
                              engine_result: Any,
                              via_coordinates: bool,
                              eligible_versions: list[VersionRow],
                              uncovered_regulatory: list[dict[str, Any]]) -> list[str]:
        """Every clause must be PROVABLE for PERMITTED to stand. This is the
        last line of defence, deliberately redundant with the pipeline."""
        v: list[str] = []
        if not hits:
            v.append("scopes omitidos")
        for p in participating:
            if p.seq not in eligible_by_seq:
                v.append(f"participante no elegible seq {p.seq}")
            elif is_rule_version_eligible(p, self.store):
                v.append(f"participante perdio elegibilidad seq {p.seq}")
        # H1/D2: an ambiguous canonical version forbids any affirmative answer
        if any(not g["material_identical"]
               for g in overlapping_version_groups(eligible_versions)):
            v.append("versiones solapadas de la misma regla (OVERLAPPING_RULE_VERSIONS)")
        required = sorted({e for p in participating for e in p.evidence})
        if not required:
            v.append("sin evidencia")
        elif self.store.missing_fragments(required):
            v.append("evidence no resoluble")
        # H2/D3: unverified citations cannot be laundered by the rule's review
        if self.store.unpublishable_fragments(sorted({e for p in participating
                                                      for e in p.evidence})):
            v.append("evidence no publicable (fragmento sin revisar)")
        if not set(required) <= {e["id"] for e in evidence}:
            v.append("evidence no materializada en el resultado")
        if any(j.outcome not in ("holds", "not_holds") for j in engine_result.judgments):
            v.append("outcome no determinable del motor")
        effects = {p.effect for p in participating}
        if len(effects) != 1 or "PERMITTED" not in effects:
            v.append("efectos no univocos o no permisivos")
        # H3/D4: every applicable REGULATORY jurisdiction must be covered
        if uncovered_regulatory:
            v.append("cobertura regulatoria incompleta: "
                     + ", ".join(f"{u['scope_id']}({u['reason']})"
                                 for u in uncovered_regulatory))
        if ambiguous_relation_groups(relations):
            v.append("relaciones de precedencia ambiguas (AMBIGUOUS_RELATION_VERSIONS)")
        by_seq = {r.seq: r for r in relations}
        by_rule: dict[str, list[VersionRow]] = {}
        for a in active_versions:
            by_rule.setdefault(a.rule_id, []).append(a)
        for seq in used_rel_seqs:
            rel = by_seq.get(seq)
            if rel is None:
                v.append(f"relacion usada no visible seq {seq}")
                continue
            if rel.recorded_at > knowledge_date:
                v.append(f"relacion no visible en knowledge_datetime seq {seq}")
            if relation_is_applicable(rel, by_rule) is not None:
                v.append(f"relacion no aplicable seq {seq}")
        for p in participating:
            scope = self.store.get_scope(p.spatial_scope_id)
            if scope is None:
                v.append("scope inexistente")
            elif via_coordinates:
                # coordinate queries CONSUME geometry: the scope must carry
                # declared geometry provenance whose spatial review is
                # complete. Scope-id queries rely on human-declared
                # attribution (policed per version by the eligibility gate).
                if not scope.get("geometry_source"):
                    v.append(f"scope sin procedencia geometrica: {p.spatial_scope_id}")
                elif scope.get("review_status") not in PUBLISHABLE_REVIEW_STATUSES:
                    v.append(f"spatial review pendiente en {p.spatial_scope_id}")
        # engine result traceable to real rule ids: every judgment must carry
        # the store's (rule_id, seq) pair it was asked about (no laundering)
        for j in engine_result.judgments:
            owner = eligible_by_seq.get(j.rule_version_id)
            if not j.rule_id or j.rule_version_id <= 0 or (
                    owner is not None and j.rule_id != owner):
                v.append("identidad de regla no trazable")
        validate_facts(query.facts)
        return v

    # ---- same-rule grouping (H1/D2) ----------------------------------------------------
    @staticmethod
    def _group_same_rule(versions: list[VersionRow]) -> dict[tuple[str, str, str],
                                                             list[VersionRow]]:
        groups: dict[tuple[str, str, str], list[VersionRow]] = {}
        for v in versions:
            groups.setdefault((v.rule_id, v.activity, v.spatial_scope_id), []).append(v)
        return groups

    @classmethod
    def _collapse_identical_duplicates(cls, versions: list[VersionRow]) -> list[VersionRow]:
        """Fold material-identical double entries into one description.

        Choosing among byte-identical descriptions is not a legal tie-break:
        every candidate asserts the same effect, condition and evidence, so the
        answer is invariant. Contradictory lineages are never folded here (they
        are a conflict, handled by the caller)."""
        out: list[VersionRow] = []
        for _, rows in sorted(cls._group_same_rule(versions).items()):
            if len(rows) == 1:
                out.append(rows[0])
                continue
            if len({version_material_signature(v) for v in rows}) == 1:
                out.append(max(rows, key=lambda v: (v.recorded_at, v.seq)))
            else:
                out.extend(rows)
        return sorted(out, key=lambda v: v.seq)

    # ---- fail-closed helper ----------------------------------------------------------------
    def _fail(self, query: Query, *, reason: str, message: str, record: bool,
              scopes: list[ScopeHit] | None = None,
              knowledge: KnowledgeStatus = KnowledgeStatus.CURRENT,
              extra_codes: list[str] | None = None,
              trace: list[dict[str, Any]] | None = None) -> ResolveResult:
        result = ResolveResult(legal_status=LegalStatus.UNDETERMINED,
                               knowledge_status=knowledge, query=query.as_dict())
        result.warnings.append(STANDING_WARNING)
        result.decision_reason = message
        result.reason_codes = [reason] + [c for c in (extra_codes or []) if c != reason]
        result.applicable_scope = [h.as_dict() for h in (scopes or [])]
        # diagnostics of the stages that got here are kept: a fail-closed answer
        # must still be auditable (which rule was excluded, and why).
        result.precedence_trace = [dict(t) for t in (trace or [])] + \
            [{"stage": "fail_closed", "reason": reason}]
        result.basis = _basis([h.scope_id for h in (scopes or [])])
        if record:
            self._record(result, query, True)
        return result

    # ---- canonical replay record (F05) --------------------------------------------------------
    def _knowledge_state_hash(self, basis: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps({k: basis[k] for k in
                                          ("scope_ids", "rule_seqs", "relation_seqs",
                                           "fragment_ids") if k in basis},
                                         sort_keys=True).encode()).hexdigest()

    def _record(self, result: ResolveResult, query: Query, record: bool) -> None:
        if not record:
            return
        basis = dict(result.basis)
        canonical = self.canonical_query(query, basis)
        self.store.record_determination(
            canonical_query=canonical,
            activity=query.activity, activity_date=query.activity_date,
            knowledge_date=query.knowledge_date,
            legal_status=result.legal_status.value,
            knowledge_status=result.knowledge_status.value,
            applicable_scope_ids=basis["scope_ids"],
            rule_version_seqs=basis["rule_seqs"],
            relation_version_seqs=basis["relation_seqs"],
            evidence_fragment_ids=basis["fragment_ids"],
            source_document_ids=sorted(basis.get("source_document_ids", [])),
            engine_adapter=self.engine.name,
            engine_version=self.engine.version,
            resolver_version=RESOLVER_VERSION,
            schema_version=SCHEMA_VERSION,
            knowledge_state_hash=self._knowledge_state_hash(basis),
        )

    def canonical_query(self, query: Query, basis: dict[str, Any]) -> dict[str, Any]:
        """Canonical material question (F05): everything needed to reproduce
        the determination, including derived-scope provenance (scope ids and
        their versions are the derived-fact source in M1)."""
        return {
            "latitude": query.lat,
            "longitude": query.lon,
            "activityDatetime": query.activity_date,
            "knowledgeDatetime": query.knowledge_date,
            "activity": query.activity,
            "queryMode": "coordinates" if query.spatial_scope_id is None else "scope",
            "spatialScopeId": query.spatial_scope_id,
            "facts": dict(sorted(query.safe_facts().items())),
            "applicableScopeIds": basis["scope_ids"],
            "ruleVersionSeqs": basis["rule_seqs"],
            "relationVersionSeqs": basis["relation_seqs"],
            "evidenceFragmentIds": basis["fragment_ids"],
            "resolverVersion": RESOLVER_VERSION,
            "schemaVersion": SCHEMA_VERSION,
            "engineAdapter": self.engine.name,
            "engineVersion": self.engine.version,
            "knowledgeStateHash": self._knowledge_state_hash(basis),
        }

    # ---- replay (F05): drift classification, not just status equality ----------------------
    def replay(self, new_knowledge_date: str) -> list[dict[str, Any]]:
        """Re-resolve every recorded determination under new knowledge and
        classify drift. Documented policy:

          LEGAL_STATUS_CHANGED    -> material -> flag STALE
          KNOWLEDGE_STATUS_CHANGED, RULE_SET_CHANGED, EVIDENCE_CHANGED,
          PRECEDENCE_CHANGED, SPATIAL_SCOPE_CHANGED, FACT_SOURCE_CHANGED
                                  -> recorded drift; NOT automatically STALE
          NO_MATERIAL_CHANGE      -> identical basis and status

        FACT_SOURCE_CHANGED (derived-fact provenance change) has no producer
        in M1 (no derived facts beyond scope resolution, which is covered by
        SPATIAL_SCOPE_CHANGED); the type is declared for the contract.
        """
        parse_date_strict(new_knowledge_date, field="new_knowledge_date")
        out: list[dict[str, Any]] = []
        for d in self.store.determinations():
            cq = d["canonical_query"]
            q_kwargs: dict[str, Any] = dict(
                activity=d["activity"], activity_date=d["activity_date"],
                knowledge_date=new_knowledge_date, facts=cq.get("facts", {}))
            if cq.get("queryMode") == "coordinates":
                q_kwargs["lat"] = cq.get("latitude")
                q_kwargs["lon"] = cq.get("longitude")
            else:
                q_kwargs["spatial_scope_id"] = cq.get("spatialScopeId")
            re_result = self.resolve(Query(**q_kwargs))
            drifts = self._classify_drift(d, re_result)
            out.append({
                "seq": d["seq"], "activity": d["activity"],
                "activity_date": d["activity_date"],
                "knowledge_date": d["knowledge_date"],
                "legal_status": d["legal_status"],
                "legal_status_now": re_result.legal_status.value,
                "drift": drifts,
                "stale": "LEGAL_STATUS_CHANGED" in drifts,
                "flag": "STALE" if "LEGAL_STATUS_CHANGED" in drifts else None,
            })
        return out

    @staticmethod
    def _classify_drift(record: dict[str, Any], new: ResolveResult) -> list[str]:
        old_basis = _basis(record["applicable_scope_ids"], record["rule_version_seqs"],
                           record["relation_version_seqs"], record["evidence_fragment_ids"])
        new_basis = new.basis or _basis()
        drifts: list[str] = []
        if record["legal_status"] != new.legal_status.value:
            drifts.append("LEGAL_STATUS_CHANGED")
        if record["knowledge_status"] != new.knowledge_status.value:
            drifts.append("KNOWLEDGE_STATUS_CHANGED")
        if sorted(old_basis["rule_seqs"]) != sorted(new_basis["rule_seqs"]):
            drifts.append("RULE_SET_CHANGED")
        if sorted(old_basis["fragment_ids"]) != sorted(new_basis["fragment_ids"]):
            drifts.append("EVIDENCE_CHANGED")
        if sorted(old_basis["relation_seqs"]) != sorted(new_basis["relation_seqs"]):
            drifts.append("PRECEDENCE_CHANGED")
        if sorted(old_basis["scope_ids"]) != sorted(new_basis["scope_ids"]):
            drifts.append("SPATIAL_SCOPE_CHANGED")
        if not drifts:
            drifts.append("NO_MATERIAL_CHANGE")
        return drifts

    # legacy entrypoint kept for CLI compatibility (maps to replay)
    def retro_audit(self, new_knowledge_date: str) -> list[dict[str, Any]]:
        return self.replay(new_knowledge_date)
