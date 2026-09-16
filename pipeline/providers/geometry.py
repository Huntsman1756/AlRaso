"""GeometryProvider: OAPN layer digest artifacts → GeometryEvidence[].

Boundary (Task 7): interprets the persisted digest representation of a WFS
layer (``*.digest.json`` — properties + per-feature geometry digests,
re-fetchable from the service). Full geometry is never redistributed:
``redistribution_policy`` stays DIGEST_ONLY and ``scope_evidence_status``
is always CONTEXT_ONLY — promotion to OFFICIAL_SCOPE_* requires a
ReviewPacket and human review (spec §P).

No network here: the WFS fetch happens in the live verifier; offline the
input is the recorded digest document.
"""

from __future__ import annotations

from typing import Any, Mapping

from pipeline.models import (
    GeometryEvidence,
    RedistributionPolicy,
    ScopeEvidenceStatus,
)


class GeometryError(ValueError):
    """Layer document or feature is unusable — explicit failure, never
    fabricated geometry evidence."""


# Property keys that may carry the park name — the key differs per layer
# (limites: "Nombre"; zonificacion PRUG: "Nombre Parque", where "Nombre"
# is the zone). A feature matches when the space name equals ANY of them.
_NAME_KEYS = ("Nombre", "Nombre Parque")


def _matches_space(props: Mapping[str, Any], space_name: str) -> bool:
    return any(
        isinstance(props.get(key), str) and props[key].strip() == space_name
        for key in _NAME_KEYS
    )


def geometry_from_layer_digest(
    *,
    space_id: str,
    space_name: str,
    layer_doc: Mapping[str, Any],
    layer: str,
    source_url: str,
    provider: str = "oapn_wfs",
    crs: str = "EPSG:4326",
) -> list[GeometryEvidence]:
    """Extract GeometryEvidence for every feature named ``space_name``.

    Returns [] when the space is absent from the layer — absent evidence is
    honest, never fabricated. Features lacking a geometry digest fail
    explicitly: digest-only evidence requires a digest.
    """
    features = layer_doc.get("features")
    if not isinstance(features, list):
        raise GeometryError("layer document requires a 'features' array")
    retrieved_at = layer_doc.get("retrieved_at")
    if not isinstance(retrieved_at, str) or not retrieved_at.strip():
        raise GeometryError("layer document requires 'retrieved_at'")

    matched = []
    for i, feature in enumerate(features):
        props = feature.get("properties") or {}
        if not _matches_space(props, space_name):
            continue
        digest = (feature.get("geometry_meta") or {}).get("digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise GeometryError(
                f"features[{i}]: matched feature lacks a 64-hex geometry "
                "digest — digest-only evidence cannot be emitted"
            )
        matched.append(
            GeometryEvidence(
                space_id=space_id,
                provider=provider,
                layer=layer,
                retrieved_at=retrieved_at.strip(),
                crs=crs,
                digest_sha256=digest,
                feature_props=dict(props),
                source_url=source_url,
                redistribution_policy=RedistributionPolicy.DIGEST_ONLY,
                scope_evidence_status=ScopeEvidenceStatus.CONTEXT_ONLY,
            )
        )
    matched.sort(key=lambda ev: ev.digest_sha256)
    return matched
