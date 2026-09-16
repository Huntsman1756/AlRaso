"""ReviewGate: evidence bundle → ReviewPacket (JSON + human markdown).

Boundary (Task 9): assembles the 9-link chain that mirrors the G0 probe
chain (PROBES.md) into a ReviewPacket for human review. It NEVER
publishes: ``publication_readiness`` is hardcoded ``NO`` in the model,
every proposed artifact is stamped ``NOT_PUBLISHED``, and ``PERMITTED``
is never inferred — the packet is evidence, not a rule.

The 9 links (G0 chain with ``precepto`` folded into ``parse`` and
``provenance`` carried per-link as sha256):

    inventory → geometry → authority → discovery → fetch → parse
    → version → change_detection → publication
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pipeline.models import ReviewPacket


class ReviewGateError(ValueError):
    """Bundle is incomplete or malformed — explicit failure."""


CHAIN_LINKS = (
    "inventory",
    "geometry",
    "authority",
    "discovery",
    "fetch",
    "parse",
    "version",
    "change_detection",
    "publication",
)

_BUNDLE_KEYS = {
    "inventory": "space",
    "geometry": "geometry",
    "authority": "authority",
    "discovery": "discovery",
    "fetch": "fetch",
    "parse": "parse",
    "version": "version",
    "change_detection": "change_detection",
}


def _link_evidence(name: str, bundle: Mapping[str, Any]) -> Any:
    """JSON-shaped evidence for one chain link."""
    if name == "publication":
        return {
            "publication_readiness": "NO",
            "note": "M10.1 prepares review packets only — no rule is "
            "published and PERMITTED is never inferred.",
        }
    key = _BUNDLE_KEYS[name]
    if key not in bundle:
        raise ReviewGateError(f"bundle missing required link {name!r}")
    value = bundle[key]
    if isinstance(value, (tuple, list)):
        return [
            v.to_dict() if hasattr(v, "to_dict") else dict(v) for v in value
        ]
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def _link_sha256(evidence: Any) -> str:
    blob = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _link(name: str, bundle: Mapping[str, Any]) -> dict[str, Any]:
    evidence = _link_evidence(name, bundle)
    return {
        "link": name,
        "evidence": evidence,
        "sha256": _link_sha256(evidence),
    }


def _diffs(
    current: Sequence[Mapping[str, Any]],
    prior_bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Per-link diff vs a prior bundle: same | changed | added | removed.

    ``publication`` is constant by contract — excluded from the diff.
    """
    cur = {l["link"]: l["sha256"] for l in current}
    out = []
    for name in CHAIN_LINKS[:-1]:
        in_cur = name in cur
        try:
            prior_ev = _link_evidence(name, prior_bundle)
            in_prior = True
        except ReviewGateError:
            in_prior = False
        if in_cur and not in_prior:
            status = "added"
        elif in_prior and not in_cur:
            status = "removed"
        elif _link_sha256(prior_ev) == cur[name]:
            status = "same"
        else:
            status = "changed"
        out.append({"link": name, "status": status})
    return tuple(out)


def _last_verified(bundle: Mapping[str, Any]) -> str | None:
    """Latest observation timestamp across the bundle (deterministic)."""
    stamps: list[str] = []
    space = bundle.get("space")
    if space is not None:
        stamps.append(space.observed_at)
    for g in bundle.get("geometry", ()):
        stamps.append(g.retrieved_at)
    for r in bundle.get("discovery", ()):
        stamps.append(r.published_on)
    ev = bundle.get("fetch")
    if ev is not None:
        stamps.append(ev.observed_at)
    parsed = bundle.get("parse")
    if parsed is not None:
        stamps.append(parsed.extracted_at)
    claim = bundle.get("version")
    if claim is not None:
        stamps.append(claim.recorded_at)
    return max(stamps) if stamps else None


def _proposed_artifacts(bundle: Mapping[str, Any]) -> tuple[dict, ...]:
    """Reviewable artifacts derived from the bundle — all NOT_PUBLISHED."""
    out = []
    parsed = bundle.get("parse")
    if parsed is not None:
        out.append(
            {
                "kind": "parsed_instrument",
                "doc_id": parsed.doc_id,
                "format": parsed.format,
                "status": "NOT_PUBLISHED",
            }
        )
    claim = bundle.get("version")
    if claim is not None:
        out.append(
            {
                "kind": "version_claim",
                "doc_id": claim.doc_id,
                "status": "NOT_PUBLISHED",
                "claim_status": claim.status.value,
            }
        )
    return tuple(out)


def _render_markdown(packet: ReviewPacket) -> str:
    lines = [
        f"# ReviewPacket — {packet.space_id}",
        "",
        f"publication_readiness: **{packet.publication_readiness}**",
        f"last_verified: {packet.last_verified}",
        "",
        "## Chain",
        "",
    ]
    for link in packet.chain_evidence:
        lines.append(f"### {link['link']}")
        lines.append(f"- sha256: `{link['sha256']}`")
        ev = link["evidence"]
        if link["link"] == "version" and isinstance(ev, dict):
            lines.append(f"- status: {ev.get('status')}")
        if isinstance(ev, dict):
            for key in ("doc_id", "fetch_outcome", "reachability_observed",
                        "runner_network", "jurisdiction", "gazette",
                        "method", "publication_readiness"):
                if key in ev:
                    lines.append(f"- {key}: {ev[key]}")
        elif isinstance(ev, list):
            lines.append(f"- items: {len(ev)}")
        lines.append("")
    if packet.proposed_rule_artifacts:
        lines.append("## Proposed artifacts (NOT_PUBLISHED)")
        lines.append("")
        for art in packet.proposed_rule_artifacts:
            lines.append(f"- {art['kind']}: {art.get('doc_id')}")
        lines.append("")
    if packet.diffs:
        lines.append("## Diff vs prior bundle")
        lines.append("")
        for d in packet.diffs:
            lines.append(f"- {d['link']}: {d['status']}")
        lines.append("")
    return "\n".join(lines)


def prepare_pr(
    space_id: str,
    bundle: Mapping[str, Any],
    *,
    prior_bundle: Mapping[str, Any] | None = None,
) -> tuple[ReviewPacket, str]:
    """Assemble a ReviewPacket + human-readable markdown.

    Requires every bundle link (``space``, ``geometry``, ``authority``,
    ``discovery``, ``fetch``, ``parse``, ``version``,
    ``change_detection``). Returns ``(packet, markdown)``; the JSON
    artifact is ``packet.to_dict()``.
    """
    space = bundle.get("space")
    if space is None or space.space_id != space_id:
        raise ReviewGateError(
            f"bundle space does not match space_id={space_id!r}"
        )
    chain = tuple(_link(name, bundle) for name in CHAIN_LINKS)
    diffs = _diffs(chain, prior_bundle) if prior_bundle is not None else ()
    packet = ReviewPacket(
        space_id=space_id,
        chain_evidence=chain,
        proposed_rule_artifacts=_proposed_artifacts(bundle),
        provenance={
            "chain": list(CHAIN_LINKS),
            "bundle_sha256": _link_sha256(
                [l["sha256"] for l in chain]
            ),
        },
        last_verified=_last_verified(bundle),
        diffs=diffs,
    )
    return packet, _render_markdown(packet)
