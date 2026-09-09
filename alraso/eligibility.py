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
  5b. EVERY cited fragment is itself publishable (H2/D3,
      alraso.bitemporal.PUBLISHABLE_FRAGMENT_STATUSES): the rule's own review
      state can never launder a citation that has not been checked against its
      source document.
  6. the version's condition AST is structurally valid.
  7. NORM_VALIDITY_COVERAGE / PRECEPT_LEVEL_NORMATIVE_BASIS: if normative_basis
      is non-empty, every basis fragment must have a provision_ref and
      validity_from; if activity_date is provided, it must fall within the
      intersection of the basis fragments' validity windows.

Geometry precision itself is policed separately: the PERMITTED invariant
gate in the resolver additionally refuses a coordinate-resolved PERMITTED
over scopes whose spatial review is incomplete (alraso.resolver).
Temporal visibility/applicability is owned by BitemporalStore.select.

Failure mode at the resolver: ineligible versions are excluded and the result
degrades to UNDETERMINED (+INCOMPLETE) with precise reason codes — NEVER to
PROHIBITED (absence of known law is not prohibition) and NEVER to PERMITTED.

APPLICABLE_DOCUMENT != APPLICABLE_PRECEPT: a document's existence is not
equivalent to a valid, current precept. The gate operates on the normative
fragment/redaction; document status alone never makes a rule eligible.

NORM_VALIDITY_COVERAGE applies equally to PERMITTED, PROHIBITED,
AUTHORIZATION_REQUIRED; evidence NOT in normative_basis never requires
validity fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alraso.bitemporal import KNOWN_EFFECTS, PUBLISHABLE_REVIEW_STATUSES, VersionRow

if TYPE_CHECKING:
    from alraso.bitemporal import BitemporalStore


def is_rule_version_eligible(
    version: VersionRow,
    store: "BitemporalStore",
    *,
    activity_date: str | None = None,
) -> list[str]:
    """Return the list of ineligibility reasons ([] == eligible).

    ``activity_date`` is always passed by the resolver (runtime enforcement of
    the validity interval).  When activity_date is None structural checks
    (provision_ref, validity_from presence) still run; interval coverage is
    skipped — the resolver is the only caller and always passes it.
    """
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
        for frag in store.unpublishable_fragments(version.evidence):
            reasons.append(f"EVIDENCE_NOT_PUBLISHABLE:{frag}")

    if version.condition is not None:
        from alraso.errors import InvalidCondition
        from alraso.validation import validate_condition
        try:
            validate_condition(version.condition)
        except InvalidCondition as e:
            reasons.append(f"CONDITION_INVALID:{e}")

    # NORM_VALIDITY_COVERAGE / PRECEPT_LEVEL_NORMATIVE_BASIS checks
    if not version.normative_basis:
        reasons.append("NORMATIVE_BASIS_MISSING")
    else:
        frag_map = {f["id"]: f for f in store.get_fragments(version.normative_basis)}
        for fid in version.normative_basis:
            frag = frag_map.get(fid)
            if frag is None:
                reasons.append(f"NORMATIVE_PRECEPT_MISSING:{fid}")
            elif not frag.get("provision_ref"):
                reasons.append(f"NORMATIVE_PRECEPT_MISSING:{fid}")
            elif frag.get("validity_from") is None:
                reasons.append(f"NORMATIVE_VALIDITY_UNKNOWN:{fid}")
            elif activity_date is not None:
                vf = frag["validity_from"]
                vt = frag.get("validity_to")
                if activity_date < vf or (vt is not None and activity_date > vt):
                    reasons.append(f"NORMATIVE_BASIS_OUTSIDE_VALIDITY:{fid}")

    return reasons
