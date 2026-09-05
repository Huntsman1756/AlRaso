"""Precedence resolution over the COMPLETE active set (M1 remediation F04).

Replaces "first OVERRIDES wins". Inputs:

    active rule versions (all scopes, all judged holds) +
    relation versions visible at knowledge_date and effective at activity_date
    (already bitemporally selected by the store).

Semantics:

  * relation A OVERRIDES B defeats ONLY B (never C);
  * grounded (stratified) evaluation of the defeat graph:
      - nodes with no applicable defeater survive (in);
      - nodes defeated by a surviving node are out;
      - nodes whose every defeater is out become in;
      - nodes left undecided belong to cycles/ungrounded sets;
  * cycles / undecided nodes => CONFLICT (never resolved by order);
  * surviving nodes with incompatible effects => CONFLICT (never a winner);
  * only relations that are fully APPLICABLE may attack:
      relation_type == OVERRIDES, human_verified, review publishable,
      legal_review_complete, and declared from_/to_effect (if set) matching
      the effects actually asserted by the active versions.

There is no "first override wins", no "latest rule wins", no
"most-specific wins" and no "permissive wins" anywhere in this module.

Ambiguous relations (M1 hardening H1): if the same relation_id is visible
through two lineages whose material content disagrees, the relation is inert
and a CONFLICT is reported (AMBIGUOUS_RELATION_VERSIONS). Deciding which
description "wins" would let the ordering of rows pick a permissive or a
restrictive outcome, which is exactly what this module exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alraso.bitemporal import (
    PUBLISHABLE_REVIEW_STATUSES,
    KNOWN_RELATION_TYPES,
    RelationVersionRow,
    VersionRow,
    relation_material_signature,
)


@dataclass
class Judgment:
    """An active (holds) judgment keyed by unique participating version seq."""
    version: VersionRow
    outcome: str


@dataclass
class PrecedenceOutcome:
    survivors: list[VersionRow]
    relations_used: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    trace: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_relation_ids: list[str] = field(default_factory=list)

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicts)

    @property
    def unique_effect(self) -> str | None:
        effects = {v.effect for v in self.survivors}
        return effects.pop() if len(effects) == 1 else None


def ambiguous_relation_groups(relations: list[RelationVersionRow]) -> list[dict[str, Any]]:
    """Visible descriptions of the same relation_id that disagree materially
    (H1-adjacent: same class of defect as overlapping rule versions).

    Duplicate identical descriptions are not a conflict; contradictory ones are,
    and neither may be resolved by ranking: a permissive relation and a
    restrictive relation of the same id would otherwise decide the answer by
    accident of ordering.
    """
    by_id: dict[str, list[RelationVersionRow]] = {}
    for r in relations:
        by_id.setdefault(r.relation_id, []).append(r)
    out = []
    for relation_id, rows in sorted(by_id.items()):
        sigs = {relation_material_signature(r) for r in rows}
        if len(sigs) > 1:
            out.append({
                "relation_id": relation_id,
                "seqs": sorted(r.seq for r in rows),
                "endpoints": sorted({(r.from_rule_id, r.to_rule_id) for r in rows}),
            })
    return out


def dedupe_relation_descriptions(
        relations: list[RelationVersionRow]) -> list[RelationVersionRow]:
    """One description per relation_id for edge building: among byte-identical
    descriptions the choice is material-neutral (any works); contradictory ones
    are handled by ambiguous_relation_groups, never silently merged."""
    best: dict[str, RelationVersionRow] = {}
    for r in relations:
        prev = best.get(r.relation_id)
        if prev is None or r.seq > prev.seq:
            best[r.relation_id] = r
    return [best[k] for k in sorted(best)]


def relation_is_applicable(rel: RelationVersionRow,
                           by_rule: dict[str, list[VersionRow]]) -> str | None:
    """Return a not-applicable reason, or None when the relation may attack."""
    if rel.relation_type not in KNOWN_RELATION_TYPES:
        return f"RELATION_TYPE_UNKNOWN:{rel.relation_type}"
    if not rel.human_verified:
        return "RELATION_NOT_HUMAN_VERIFIED"
    if rel.review_status not in PUBLISHABLE_REVIEW_STATUSES:
        return f"RELATION_REVIEW_NOT_PUBLISHABLE:{rel.review_status}"
    if not rel.legal_review_complete:
        return "RELATION_LEGAL_REVIEW_INCOMPLETE"
    if rel.relation_type == "OVERRIDES":
        from_versions = by_rule.get(rel.from_rule_id, [])
        to_versions = by_rule.get(rel.to_rule_id, [])
        if not from_versions or not to_versions:
            return "RELATION_ENDPOINT_NOT_ACTIVE"
        if rel.from_effect is not None and not any(v.effect == rel.from_effect
                                                   for v in from_versions):
            return f"RELATION_FROM_EFFECT_MISMATCH:{rel.from_effect}"
        if rel.to_effect is not None and not any(v.effect == rel.to_effect
                                                 for v in to_versions):
            return f"RELATION_TO_EFFECT_MISMATCH:{rel.to_effect}"
    return None


def resolve_precedence(active: list[Judgment],
                       relations: list[RelationVersionRow]) -> PrecedenceOutcome:
    """Grounded evaluation over the full active set. Order-independent."""
    trace: list[dict[str, Any]] = []
    versions_by_seq = {j.version.seq: j.version for j in active}
    by_rule: dict[str, list[VersionRow]] = {}
    for j in active:
        by_rule.setdefault(j.version.rule_id, []).append(j.version)

    ambiguous = ambiguous_relation_groups(relations)
    ambiguous_ids = {g["relation_id"] for g in ambiguous}
    for g in ambiguous:
        trace.append({"stage": "precedence_relation", "relation_id": g["relation_id"],
                      "seqs": g["seqs"], "applicable": False,
                      "reason": "AMBIGUOUS_RELATION_VERSIONS"})

    applicable: list[RelationVersionRow] = []
    for rel in dedupe_relation_descriptions(relations):
        if rel.relation_id in ambiguous_ids:
            continue  # never attack with an undecidable precedence
        reason = relation_is_applicable(rel, by_rule)
        if reason is None:
            applicable.append(rel)
            trace.append({"stage": "precedence_relation", "relation_id": rel.relation_id,
                          "seq": rel.seq, "applicable": True})
        else:
            trace.append({"stage": "precedence_relation", "relation_id": rel.relation_id,
                          "seq": rel.seq, "applicable": False, "reason": reason})

    # defeat edges: seq(from winner) -> seq(to defeated). A relation defeats
    # exactly the active version(s) of its to_rule matching to_effect (or all
    # when unspecified), and is itself sourced from from_rule matching
    # from_effect (or all).
    edges: dict[int, set[int]] = {seq: set() for seq in versions_by_seq}
    used: list[dict[str, Any]] = []
    for rel in applicable:
        attackers = [v.seq for v in by_rule[rel.from_rule_id]
                     if rel.from_effect is None or v.effect == rel.from_effect]
        targets = [v.seq for v in by_rule[rel.to_rule_id]
                   if rel.to_effect is None or v.effect == rel.to_effect]
        for t in targets:
            for a in attackers:
                if a != t:
                    edges[t].add(a)
        used.append({"relation_id": rel.relation_id, "seq": rel.seq,
                     "defeats": sorted(targets), "via": sorted(attackers)})

    # stratified grounded evaluation
    state: dict[int, str] = {}          # seq -> "in" | "out"
    attackers_of = edges                 # seq -> set(attacker seqs) [defeated-by]
    changed = True
    while changed:
        changed = False
        for seq in versions_by_seq:
            if seq in state:
                continue
            att = attackers_of[seq]
            if any(state.get(a) == "in" for a in att):
                state[seq] = "out"
                changed = True
            elif all(state.get(a) == "out" for a in att if a in versions_by_seq) \
                    and all(a in state for a in att if a in versions_by_seq):
                state[seq] = "in"
                changed = True
    undecided = [s for s in versions_by_seq if state.get(s) not in ("in", "out")]

    survivors = [versions_by_seq[s] for s in sorted(versions_by_seq) if state.get(s) == "in"]
    conflicts: list[dict[str, Any]] = []

    if undecided:
        conflicts.append({
            "rules": sorted(versions_by_seq[s].rule_id for s in undecided),
            "seqs": sorted(undecided),
            "effects": sorted({versions_by_seq[s].effect for s in undecided}),
            "note": "PRECEDENCE_CYCLE: ciclo o conjunto no fundamentado en el grafo de precedencia",
        })

    for g in ambiguous:
        conflicts.append({
            "rules": sorted({rid for pair in g["endpoints"] for rid in pair}),
            "seqs": g["seqs"],
            "effects": [],
            "note": (f"AMBIGUOUS_RELATION_VERSIONS: relaciones {g['relation_id']!r} con "
                     "descripciones visibles contradictorias; ninguna es canónica, "
                     "no se decide por orden"),
        })

    survivor_effects = sorted({v.effect for v in survivors})
    if len(survivor_effects) > 1:
        conflicts.append({
            "rules": sorted(v.rule_id for v in survivors),
            "seqs": sorted(v.seq for v in survivors),
            "effects": survivor_effects,
            "note": "CONFLICTO_SUPERVIVIENTE: efectos incompatibles sobreviven a la precedencia",
        })
    if undecided and survivor_effects:
        undecided_effects = {versions_by_seq[s].effect for s in undecided}
        if undecided_effects - set(survivor_effects):
            # an undecided (cyclic/ungrounded) rule still asserts an effect
            # the survivors do not share -> the conflict is not resolved.
            conflicts.append({
                "rules": sorted({versions_by_seq[s].rule_id for s in undecided}),
                "seqs": sorted(undecided),
                "effects": sorted(undecided_effects),
                "note": "CONFLICTO_NO_FUNDAMENTADO: reglas en disputa con efecto no cubierto por los supervivientes",
            })

    trace.append({"stage": "precedence_solve", "state": {str(k): v for k, v in sorted(state.items())},
                  "survivors": sorted(versions_by_seq[s].rule_id for s in versions_by_seq
                                      if state.get(s) == "in")})
    return PrecedenceOutcome(survivors=survivors, relations_used=used,
                             conflicts=conflicts, trace=trace,
                             ambiguous_relation_ids=sorted(ambiguous_ids))
