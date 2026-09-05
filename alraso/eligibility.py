"""Centralized rule eligibility gate (M1 remediation F01).

ONE place decides whether a LegalRuleVersion may participate in a publishable
determination. Call sites must not scatter these checks.

A version is eligible iff ALL hold:

  1. review_status is publishable: exactly {VERIFIED, PUBLISHED}. Everything
     else (DISCOVERED/EXTRACTED/REVIEW_REQUIRED/LEGAL_REVIEWED/
     SPATIAL_REVIEWED/unknown) can NEVER contribute an effect.
  2. legal_review_complete is True.
  3. spatial_review_complete is not explicitly False (0 = "spatial review
     required and not done -> can never carry a publishable effect";
     1 = complete; NULL = not applicable because the normative scope
     attribution is human-declared, geometry precision is not consumed).
  4. effect is a modelled effect.
  5. evidence is present when the version requires it (evidence_required) and
     EVERY evidence reference resolves to a legal_fragment whose
     source_document exists (no dangling citations).
  6. the version's condition AST is structurally valid.

Geometry precision itself is policed separately: the PERMITTED invariant
gate in the resolver additionally refuses a coordinate-resolved PERMITTED
over scopes whose spatial review is incomplete (alraso.resolver).
Temporal visibility/applicability is owned by BitemporalStore.select.

Failure mode at the resolver: ineligible versions are excluded and the result
degrades to UNDETERMINED (+INCOMPLETE) with precise reason codes — NEVER to
PROHIBITED (absence of publishable law is not prohibition) and NEVER to
PERMITTED.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alraso.bitemporal import KNOWN_EFFECTS, PUBLISHABLE_REVIEW_STATUSES, VersionRow

if TYPE_CHECKING:
    from alraso.bitemporal import BitemporalStore


def is_rule_version_eligible(version: VersionRow, store: "BitemporalStore") -> list[str]:
    """Return the list of ineligibility reasons ([] == eligible)."""
    reasons: list[str] = []

    if version.review_status not in PUBLISHABLE_REVIEW_STATUSES:
        reasons.append(f"REVIEW_NOT_PUBLISHABLE:{version.review_status}")

    if not version.legal_review_complete:
        reasons.append("LEGAL_REVIEW_INCOMPLETE")

    if version.spatial_review_complete is False:
        reasons.append("SPATIAL_REVIEW_INCOMPLETE")

    if version.effect not in KNOWN_EFFECTS:
        reasons.append(f"EFFECT_UNKNOWN:{version.effect}")

    if version.evidence_required and not version.evidence:
        reasons.append("EVIDENCE_MISSING")

    if version.evidence:
        for frag in store.missing_fragments(version.evidence):
            reasons.append(f"EVIDENCE_UNRESOLVABLE:{frag}")

    if version.condition is not None:
        from alraso.errors import InvalidCondition
        from alraso.validation import validate_condition
        try:
            validate_condition(version.condition)
        except InvalidCondition as e:
            reasons.append(f"CONDITION_INVALID:{e}")

    return reasons
