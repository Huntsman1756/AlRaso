"""Rule-engine adapters behind an explicit capability contract (F02).

The resolver never talks to any engine directly. Beyond the evaluate()
protocol, every adapter MUST declare its capabilities, and the resolver MUST
verify compatibility BEFORE delegating — limitations may never be discovered
after an answer comes back.

Contract rules:

  * UnsupportedEngineCapability is raised when a required capability is
    missing; the resolver maps it to UNDETERMINED + reason code. It can never
    produce PERMITTED.
  * Every JudgmentResult carries the MATERIAL identity of its source:
    rule_id AND rule_version_id (store seq). Identity laundering — replacing
    rule ids with an engine label — is forbidden: judgments must stay
    traceable to the rules and evidence that produced them.
  * The same EngineError taxonomy (alraso.errors) is raised by all adapters.

Implementations:
  * OwnEvaluatorAdapter - pure-Python, zero deps, the DEFAULT engine
    (DEFAULT_ENGINE="own"). Full condition/effect/multi-rule support.
  * AxiomCliAdapter     - EXPERIMENTAL (see alraso.engine_axiom).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from alraso.bitemporal import VersionRow
from alraso import conditions
from alraso.errors import EngineMissingInput, EngineFailure, UnsupportedEngineCapability

# re-exported so existing imports keep working during the remediation
EngineError = EngineFailure
Outcome = Literal["holds", "not_holds", "undetermined"]

DEFAULT_ENGINE = "own"
OWN_EVALUATOR_VERSION = "own-evaluator/1"

CONDITION_KINDS = frozenset({"const", "all", "any", "not", "field"})
CONDITION_OPS = frozenset({"eq", "neq", "gte", "gt", "lte", "lt", "in", "is_true", "is_false"})
MODELLED_EFFECTS = frozenset({"PERMITTED", "PROHIBITED", "AUTHORIZATION_REQUIRED"})


@dataclass(frozen=True)
class EngineCapabilities:
    """What an adapter HONESTLY claims to support. The resolver pre-checks."""
    supports_activity: bool
    supports_condition_kinds: frozenset[str]
    supports_condition_ops: frozenset[str]
    supports_effects: frozenset[str]
    supports_multiple_rules: bool
    supports_explain: bool
    supports_rule_identity: bool

    def check(self, *, kinds: set[str], ops: set[str], effects: set[str],
              n_versions: int, mode: str) -> str | None:
        """Return the first unsupported requirement, or None if compatible."""
        if not self.supports_activity:
            return "supports_activity"
        missing_kinds = kinds - self.supports_condition_kinds
        if missing_kinds:
            return "condition_kinds:" + ",".join(sorted(missing_kinds))
        missing_ops = ops - self.supports_condition_ops
        if missing_ops:
            return "condition_ops:" + ",".join(sorted(missing_ops))
        missing_effects = effects - self.supports_effects
        if missing_effects:
            return "effects:" + ",".join(sorted(missing_effects))
        if n_versions > 1 and not self.supports_multiple_rules:
            return "supports_multiple_rules"
        if mode == "explain" and not self.supports_explain:
            return "supports_explain"
        if not self.supports_rule_identity:
            return "supports_rule_identity"
        return None


@dataclass
class JudgmentResult:
    rule_id: str
    rule_version_id: int
    effect: str
    outcome: Outcome
    conditions: list[dict[str, Any]] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "rule_version_id": self.rule_version_id,
                "effect": self.effect, "outcome": self.outcome,
                "conditions": self.conditions, "trace": self.trace}


@dataclass
class EngineResult:
    judgments: list[JudgmentResult]

    def by_rule(self) -> dict[str, JudgmentResult]:
        return {j.rule_id: j for j in self.judgments}


def collect_requirements(versions: list[VersionRow]) -> tuple[set[str], set[str], set[str]]:
    """Condition kinds/ops and effects an evaluation will actually need."""
    kinds: set[str] = set()
    ops: set[str] = set()

    def walk(cond: Any) -> None:
        if not isinstance(cond, dict):
            return
        for kind in ("const", "all", "any", "not", "field"):
            if kind in cond:
                kinds.add(kind)
                if kind == "field":
                    ops.add(cond.get("op", "eq"))
        for key in ("all", "any"):
            for sub in cond.get(key, []):
                walk(sub)
        if "not" in cond:
            walk(cond["not"])

    for v in versions:
        if v.condition is not None:
            walk(v.condition)
    return kinds, ops, {v.effect for v in versions}


class RuleEngineAdapter(Protocol):
    name: str
    version: str

    def capabilities(self) -> EngineCapabilities:
        ...

    def evaluate(self, versions: list[VersionRow], facts: dict[str, Any],
                 mode: str = "fast") -> EngineResult:
        ...


class OwnEvaluatorAdapter:
    """Evaluates store versions natively. Effect-only versions always hold;
    conditional versions hold iff their (strictly validated) AST evaluates true
    over the facts. A missing referenced fact raises EngineMissingInput
    (fail-closed: never a guess, never PERMITTED)."""

    name = "own"
    version = OWN_EVALUATOR_VERSION

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            supports_activity=True,
            supports_condition_kinds=CONDITION_KINDS,
            supports_condition_ops=CONDITION_OPS,
            supports_effects=MODELLED_EFFECTS,
            supports_multiple_rules=True,
            supports_explain=True,
            supports_rule_identity=True,
        )

    def evaluate(self, versions: list[VersionRow], facts: dict[str, Any],
                 mode: str = "fast") -> EngineResult:
        judgments: list[JudgmentResult] = []
        for v in versions:
            if v.condition is None:
                judgments.append(JudgmentResult(
                    rule_id=v.rule_id, rule_version_id=v.seq, effect=v.effect,
                    outcome="holds",
                    conditions=[{"kind": "effect_only"}],
                    trace=["no condition: effect asserted directly"]))
                continue
            cond_trace: list[dict[str, Any]] = []
            try:
                holds = conditions.evaluate(v.condition, facts)
            except conditions.MissingFact as e:
                raise EngineMissingInput(
                    str(e), detail={"field": e.field, "rule_id": v.rule_id,
                                    "rule_version_id": v.seq}) from e
            except conditions.BadCondition as e:
                raise EngineFailure(f"bad condition in {v.rule_id}: {e}") from e
            cond_trace.append({"kind": "condition", "holds": holds, "ast": v.condition})
            judgments.append(JudgmentResult(
                rule_id=v.rule_id, rule_version_id=v.seq, effect=v.effect,
                outcome="holds" if holds else "not_holds",
                conditions=cond_trace,
                trace=[f"condition evaluated to {holds}"]))
        return EngineResult(judgments=judgments)
