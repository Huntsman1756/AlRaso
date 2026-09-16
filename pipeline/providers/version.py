"""VersionResolver (minimal): structured data → conservative VersionClaim.

Boundary (Task 6 + plan §7 fix 4): this module never interprets legal text.
``effective_from`` is populated only from structured or exactly
preregistered effective-date evidence, keeping the source fragment in
``resolver_evidence``. Free-text or ambiguous vacatio ("entrará en vigor al
día siguiente...", multi-term formulas) stays ``None``.

In M10.1 every claim is ``REQUIRES_MANUAL_REVIEW``: a structured candidate
is evidence for the reviewer, not a resolution. ``consolidated_api`` is an
honest stub — the consolidated corpus resolver is M10.2+.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Mapping

from pipeline.models import DocumentRef, VersionClaim
from pipeline.profiles import SourceProfile


class VersionError(ValueError):
    """Resolver strategy or supplied evidence is unusable — explicit
    failure, never a fabricated claim."""


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _structured_effective_from(
    evidence: Mapping[str, Any] | None,
) -> tuple[str | None, dict[str, Any]]:
    """Validate preregistered effective-date evidence.

    Only a mapping carrying an ISO ``effective_from`` plus a kept source
    ``fragment`` produces a candidate. Anything else leaves the field null.
    """
    if evidence is None:
        return None, {}
    if "effective_from" not in evidence or evidence["effective_from"] is None:
        # Fragment-only evidence is recorded but never becomes a date.
        return None, dict(evidence)
    raw = evidence["effective_from"]
    try:
        effective_from = dt.date.fromisoformat(str(raw)[:10]).isoformat()
    except ValueError as exc:
        raise VersionError(
            f"structured_evidence.effective_from {raw!r} is not an ISO date"
        ) from exc
    fragment = evidence.get("fragment")
    if not isinstance(fragment, str) or not fragment.strip():
        raise VersionError(
            "structured_evidence.effective_from requires a non-empty "
            "'fragment' preserving the source text"
        )
    return effective_from, dict(evidence)


def _gazette_publication(
    doc_ref: DocumentRef,
    *,
    now: str,
    structured_evidence: Mapping[str, Any] | None,
) -> VersionClaim:
    effective_from, evidence = _structured_effective_from(structured_evidence)
    return VersionClaim(
        doc_id=doc_ref.doc_id,
        recorded_at=now,
        publication_date=doc_ref.published_on,
        effective_from=effective_from,
        resolver_evidence={
            "strategy": "gazette_publication",
            **evidence,
        },
    )


def _consolidated_api_stub(
    doc_ref: DocumentRef,
    *,
    now: str,
    structured_evidence: Mapping[str, Any] | None,
) -> VersionClaim:
    effective_from, evidence = _structured_effective_from(structured_evidence)
    return VersionClaim(
        doc_id=doc_ref.doc_id,
        recorded_at=now,
        publication_date=doc_ref.published_on,
        effective_from=effective_from,
        resolver_evidence={
            "strategy": "consolidated_api",
            "note": "consolidated_api resolver not implemented in M10.1 — "
            "claim left for manual review",
            **evidence,
        },
    )


_STRATEGIES = {
    "gazette_publication": _gazette_publication,
    "consolidated_api": _consolidated_api_stub,
}


def resolve(
    profile: SourceProfile,
    doc_ref: DocumentRef,
    *,
    clock: Callable[[], str] = _utc_now_iso,
    structured_evidence: Mapping[str, Any] | None = None,
) -> VersionClaim:
    """Produce the conservative VersionClaim for ``doc_ref``.

    ``structured_evidence`` is the only way ``effective_from`` can be set:
    an exact preregistered ISO date plus its source fragment. Everything
    else — including absent evidence — yields ``None``.
    """
    strategy = profile.versioning.get("strategy")
    handler = _STRATEGIES.get(strategy)
    if handler is None:
        raise VersionError(f"unsupported versioning strategy {strategy!r}")
    return handler(doc_ref, now=clock(), structured_evidence=structured_evidence)
