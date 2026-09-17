"""VersionResolver: structured data → conservative VersionClaim.

Boundary (Task 6 + plan §7 fix 4): this module never interprets legal text.
``effective_from`` is populated only from structured or exactly
preregistered effective-date evidence, keeping the source fragment in
``resolver_evidence``. Free-text or ambiguous vacatio ("entrará en vigor al
día siguiente...", multi-term formulas) stays ``None``.

M10.2-C: ``consolidated_api`` is real for the two mechanically verified
signal sources — BOE ``metadatos`` and DOGC Socrata+ELI idVersion. A
``RESOLVED`` claim means ONLY "the document version was mechanically
resolved": it creates no ``legal_rule_version``, mutates no review flags,
and asserts nothing about validity or permissibility. Anything not
mechanically proven fails closed to ``REQUIRES_MANUAL_REVIEW``.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Callable, Mapping

from pipeline.models import (
    DocumentRef,
    VersionClaim,
    VersionClaimStatus,
)
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


# ---------------------------------------------------------------------
# consolidated_api — mechanical document-version signals (M10.2-C)
# ---------------------------------------------------------------------
#
# Evidence envelope produced by the verifier tooling
# (tooling/m102_version_probe.py); the resolver is pure — it consumes
# the recorded bundle and never fetches.
#
#   structured_evidence["consolidated"] = {
#       "signal_source": "boe_metadatos" | "dogc_socrata_eli",
#       "endpoint": <official URL>,
#       "retrieved_at": <ISO>,
#       "response_sha256": <sha256 of raw response bytes>,
#       "runner_network": <runner>,
#       "fetch_outcome": "SUCCESS" | <failure>,
#       "payload": <parsed response — shape per signal_source>,
#   }

_CONSOLIDATED_REQUIRED_KEYS = (
    "signal_source",
    "endpoint",
    "retrieved_at",
    "response_sha256",
    "runner_network",
    "fetch_outcome",
)


def _manual(
    doc_ref: DocumentRef,
    now: str,
    evidence: dict[str, Any],
    reason: str,
) -> VersionClaim:
    """Fail-closed claim: evidence preserved, reason explicit."""
    return VersionClaim(
        doc_id=doc_ref.doc_id,
        recorded_at=now,
        publication_date=doc_ref.published_on,
        resolver_evidence={
            "strategy": "consolidated_api",
            "manual_review_reason": reason,
            **evidence,
        },
    )


_BOE_DATE_SHAPE = re.compile(r"\d{8}(T\d{6}Z)?")


def _boe_date(raw: Any) -> str | None:
    """BOE compact date/datetime → ISO date, or None if malformed.

    Strict shape first (strptime accepts 1-2 digit %m/%d silently):
    exactly YYYYMMDD or YYYYMMDDTHHMMSSZ.
    """
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not _BOE_DATE_SHAPE.fullmatch(raw):
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _resolve_boe_metadatos(
    doc_ref: DocumentRef,
    *,
    now: str,
    bundle: Mapping[str, Any],
    evidence: dict[str, Any],
) -> VersionClaim:
    """BOE `/id/{id}/metadatos` → mechanical version claim.

    RESOLVED requires: HTTP-200 envelope, `identificador == doc_id`,
    well-formed `fecha_actualizacion`, `fecha_publicacion`,
    `fecha_vigencia`, `estado_consolidacion`, `vigencia_agotada`.
    ``effective_from`` ← ``fecha_vigencia`` — a structured official
    field, never parsed from prose.
    """
    payload = bundle.get("payload")
    if not isinstance(payload, Mapping):
        return _manual(doc_ref, now, evidence, "payload not a mapping")
    status = payload.get("status")
    if not isinstance(status, Mapping) or str(status.get("code")) != "200":
        code = status.get("code") if isinstance(status, Mapping) else status
        return _manual(
            doc_ref, now, evidence,
            f"api status {code!r} != 200",
        )
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(
        data[0], Mapping
    ):
        return _manual(doc_ref, now, evidence, "data[] missing/malformed")
    row = data[0]

    ident = row.get("identificador")
    if ident != doc_ref.doc_id:
        return _manual(
            doc_ref, now, evidence,
            f"identificador {ident!r} != doc_id {doc_ref.doc_id!r}",
        )
    fecha_actualizacion = row.get("fecha_actualizacion")
    if _boe_date(fecha_actualizacion) is None:
        return _manual(
            doc_ref, now, evidence,
            f"fecha_actualizacion {fecha_actualizacion!r} malformed",
        )
    fecha_publicacion = _boe_date(row.get("fecha_publicacion"))
    if fecha_publicacion is None:
        return _manual(
            doc_ref, now, evidence, "fecha_publicacion missing/malformed"
        )
    effective_from = _boe_date(row.get("fecha_vigencia"))
    if effective_from is None:
        return _manual(
            doc_ref, now, evidence, "fecha_vigencia missing/malformed"
        )
    estado = row.get("estado_consolidacion")
    vigencia_agotada = row.get("vigencia_agotada")
    if (
        not isinstance(estado, Mapping)
        or not estado.get("texto")
        or vigencia_agotada not in ("S", "N")
    ):
        return _manual(
            doc_ref, now, evidence,
            "estado_consolidacion/vigencia_agotada missing/malformed",
        )

    return VersionClaim(
        doc_id=doc_ref.doc_id,
        recorded_at=now,
        consolidated_state=str(estado["texto"]),
        effective_from=effective_from,
        publication_date=fecha_publicacion,
        status=VersionClaimStatus.RESOLVED,
        resolver_evidence={
            **evidence,
            "strategy": "consolidated_api",
            "signal": "document_version_only",
            "identificador": ident,
            "fecha_actualizacion": fecha_actualizacion,
            "vigencia_agotada": vigencia_agotada,
            "estatus_derogacion": row.get("estatus_derogacion"),
            "estatus_anulacion": row.get("estatus_anulacion"),
            "url_eli": row.get("url_eli"),
        },
    )


_ELIFE_FMT = re.compile(
    r"^https://portaljuridic\.gencat\.cat/eli/"
    r"(es-ct/d/\d{4}/\d{2}/\d{2}/\d+)(?:[/?]|$)"
)
_AKN_SERVLET = (
    "https://portaldogc.gencat.cat/utilsEADOP/AppJava/AkomaNtoso"
)
_ID_PAIR = re.compile(r"[?&]idNumber=(\d+)&idVersion=(\d+)(?=&|$)")


def _resolve_dogc_socrata_eli(
    doc_ref: DocumentRef,
    *,
    now: str,
    bundle: Mapping[str, Any],
    evidence: dict[str, Any],
) -> VersionClaim:
    """DOGC Socrata row + ELI redirect → mechanical version claim.

    RESOLVED requires: the row's ``url_format_xml`` ELI path equals the
    doc_id, ``vig_ncia_de_la_norma`` is present, and the ELI fetch's
    effective URL carries integer ``idNumber``/``idVersion``.
    ``effective_from`` stays None — DOGC exposes no structured
    effective-date field (``vigència`` is a status).
    """
    payload = bundle.get("payload")
    if not isinstance(payload, Mapping):
        return _manual(doc_ref, now, evidence, "payload not a mapping")
    row = payload.get("socrata_row")
    redirect = payload.get("eli_redirect")
    if not isinstance(row, Mapping) or not isinstance(redirect, Mapping):
        return _manual(
            doc_ref, now, evidence,
            "socrata_row/eli_redirect missing or malformed",
        )

    eli_url = row.get("url_format_xml")
    if isinstance(eli_url, Mapping):
        eli_url = eli_url.get("url")
    m = _ELIFE_FMT.match(str(eli_url))
    if not m:
        return _manual(
            doc_ref, now, evidence,
            f"url_format_xml {eli_url!r} is not a DOGC ELI",
        )
    if m.group(1) != doc_ref.doc_id:
        return _manual(
            doc_ref, now, evidence,
            f"ELI {m.group(1)!r} != doc_id {doc_ref.doc_id!r}",
        )

    vigencia = row.get("vig_ncia_de_la_norma")
    if not isinstance(vigencia, str) or not vigencia.strip():
        return _manual(
            doc_ref, now, evidence, "vig_ncia_de_la_norma missing"
        )

    pub_raw = row.get("data_de_publicaci_del_diari")
    try:
        publication_date = dt.date.fromisoformat(
            str(pub_raw)[:10]
        ).isoformat()
    except (TypeError, ValueError):
        return _manual(
            doc_ref, now, evidence,
            f"data_de_publicaci_del_diari {pub_raw!r} malformed",
        )

    # Bind the redirect observation to THIS document: the request must
    # have been the row's own ELI, and the effective URL must be the
    # official AkomaNtoso servlet — never an arbitrary URL carrying
    # idNumber/idVersion look-alike params.
    req_m = _ELIFE_FMT.match(str(redirect.get("request_url")))
    if not req_m or req_m.group(1) != doc_ref.doc_id:
        return _manual(
            doc_ref, now, evidence,
            "eli_redirect.request_url does not match this document's ELI",
        )
    effective_url = redirect.get("effective_url")
    if not str(effective_url).startswith(_AKN_SERVLET):
        return _manual(
            doc_ref, now, evidence,
            f"effective_url {effective_url!r} is not the official "
            "AkomaNtoso servlet",
        )
    vmatch = _ID_PAIR.search(str(effective_url))
    if not vmatch:
        return _manual(
            doc_ref, now, evidence,
            f"effective_url {effective_url!r} carries no "
            "idNumber/idVersion",
        )

    return VersionClaim(
        doc_id=doc_ref.doc_id,
        recorded_at=now,
        consolidated_state=vigencia.strip(),
        effective_from=None,  # no structured effective-date field — never
        publication_date=publication_date,
        status=VersionClaimStatus.RESOLVED,
        resolver_evidence={
            **evidence,
            "strategy": "consolidated_api",
            "signal": "document_version_only",
            "eli": m.group(1),
            "id_number": vmatch.group(1),
            "id_version": vmatch.group(2),
            "vigencia": vigencia.strip(),
            "data_del_document": row.get("data_del_document"),
        },
    )


def _consolidated_api(
    doc_ref: DocumentRef,
    *,
    now: str,
    structured_evidence: Mapping[str, Any] | None,
    signal_source: str | None,
) -> VersionClaim:
    """Mechanical version signals for BOE/DOGC (spec §C.3).

    ``RESOLVED`` asserts ONLY that the document version was mechanically
    resolved — no legal interpretation, no publication. Every gap fails
    closed to ``REQUIRES_MANUAL_REVIEW``.
    """
    effective_from, extra = _structured_effective_from(
        {
            k: v
            for k, v in (structured_evidence or {}).items()
            if k != "consolidated"
        }
        or None
    )

    def _fin(claim: VersionClaim) -> VersionClaim:
        """Attach a preregistered date to a NON-RESOLVED claim only —
        stamped so the channel can never be confused with the
        mechanical signal."""
        if (
            effective_from is None
            or claim.effective_from is not None
            or claim.status is VersionClaimStatus.RESOLVED
        ):
            return claim
        return VersionClaim(
            doc_id=claim.doc_id,
            recorded_at=claim.recorded_at,
            consolidated_state=claim.consolidated_state,
            effective_from=effective_from,
            effective_to=claim.effective_to,
            publication_date=claim.publication_date,
            supersession=claim.supersession,
            resolver_evidence={
                **claim.resolver_evidence,
                "effective_from_channel": "preregistered",
            },
            recorded_until=claim.recorded_until,
            status=claim.status,
        )

    bundle = (structured_evidence or {}).get("consolidated")
    base_evidence = {**extra}
    if not isinstance(bundle, Mapping):
        return _fin(_manual(
            doc_ref, now, base_evidence,
            "no consolidated evidence bundle supplied",
        ))
    missing = [k for k in _CONSOLIDATED_REQUIRED_KEYS if k not in bundle]
    if missing:
        return _fin(_manual(
            doc_ref, now, base_evidence,
            f"evidence bundle missing keys {missing}",
        ))
    evidence = {
        **base_evidence,
        "signal_source": bundle["signal_source"],
        "endpoint": bundle["endpoint"],
        "retrieved_at": bundle["retrieved_at"],
        "response_sha256": bundle["response_sha256"],
        "runner_network": bundle["runner_network"],
        "fetch_outcome": bundle["fetch_outcome"],
    }
    if bundle["signal_source"] != signal_source:
        return _fin(_manual(
            doc_ref, now, evidence,
            f"evidence signal_source {bundle['signal_source']!r} != "
            f"profile {signal_source!r}",
        ))
    if bundle["fetch_outcome"] != "SUCCESS":
        return _fin(_manual(
            doc_ref, now, evidence,
            f"fetch_outcome {bundle['fetch_outcome']!r} — signal fetch "
            "failed, no version resolvable",
        ))

    if signal_source == "boe_metadatos":
        return _fin(_resolve_boe_metadatos(
            doc_ref, now=now, bundle=bundle, evidence=evidence
        ))
    if signal_source == "dogc_socrata_eli":
        return _fin(_resolve_dogc_socrata_eli(
            doc_ref, now=now, bundle=bundle, evidence=evidence
        ))
    return _fin(_manual(
        doc_ref, now, evidence,
        f"unknown consolidated signal_source {signal_source!r}",
    ))


_STRATEGIES = {
    "gazette_publication": _gazette_publication,
    "consolidated_api": _consolidated_api,
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
    if strategy == "consolidated_api":
        return handler(
            doc_ref,
            now=clock(),
            structured_evidence=structured_evidence,
            signal_source=profile.versioning.get("signal_source"),
        )
    return handler(doc_ref, now=clock(), structured_evidence=structured_evidence)
