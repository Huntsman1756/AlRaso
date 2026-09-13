"""DiscoveryProvider: discovery responses → ``DocumentRef[]``.

Boundary (Task 3): this module only interprets discovery responses. It does
not fetch document bytes, does not evaluate content markers, does not parse
instrument contents and does not derive effective dates. Reachability
expectation stays in the profile; execution truth is recorded later by the
fetcher on ``DocumentEvidence``.

No dynamic plugin framework: a small dispatch table maps
``profile.discovery["provider"]`` to its interpreter. New sources add a
function here only when their response shape actually differs.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Callable, Mapping

from pipeline.models import DocumentRef
from pipeline.profiles import SourceProfile


class DiscoveryError(ValueError):
    """The discovery payload or profile is unusable — fail explicit, never
    emit a partially invented DocumentRef."""


# Stable native gazette id, preregistered in G0 access-matrix
# (stable_document_id = BOCYL-D-DDMMYYYY-N).
_BOCYL_DOC_ID_RE = re.compile(r"BOCYL-D-\d{8}-\d+")


def _require_str(rec: Mapping[str, Any], key: str, where: str) -> str:
    value = rec.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"{where}: missing or empty field {key!r}")
    return value.strip()


def _iso_date(raw: str, where: str, key: str) -> str:
    try:
        return dt.date.fromisoformat(raw.strip()[:10]).isoformat()
    except ValueError as exc:
        raise DiscoveryError(
            f"{where}: invalid {key} {raw!r}"
        ) from exc


def _bocyl_opendatasoft(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """Opendatasoft ``records`` response → DocumentRef[].

    Verified record fields (G0 ``bocyl-dataset-meta.json``):
    ``enlace_fichero_xml|pdf|html``, ``no_oficial``, ``fecha_publicacion``,
    ``titulo``, ``organismo``, ``rango``, ``no_edicion``.
    """
    results = payload.get("results")
    if not isinstance(results, list):
        raise DiscoveryError("opendatasoft payload requires a 'results' array")

    rows = []
    for i, rec in enumerate(results):
        where = f"results[{i}]"
        if not isinstance(rec, dict):
            raise DiscoveryError(f"{where}: record must be an object")
        xml_url = _require_str(rec, "enlace_fichero_xml", where)
        title = _require_str(rec, "titulo", where)
        issuer = _require_str(rec, "organismo", where)
        published_on = _iso_date(
            _require_str(rec, "fecha_publicacion", where),
            where,
            "fecha_publicacion",
        )
        match = _BOCYL_DOC_ID_RE.search(xml_url)
        if match is None:
            raise DiscoveryError(
                f"{where}: cannot derive doc_id from enlace_fichero_xml "
                f"{xml_url!r}"
            )
        rows.append((published_on, match.group(0), title, issuer, xml_url))

    rows.sort(key=lambda r: (r[0], r[1]))

    if window is not None:
        start, end = window
        rows = [
            r
            for r in rows
            if (start is None or r[0] >= start)
            and (end is None or r[0] <= end)
        ]

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=doc_id,
            published_on=published_on,
            title=title,
            issuer=issuer,
            discovery_url=url,
            rank=i,
        )
        for i, (published_on, doc_id, title, issuer, url) in enumerate(rows)
    ]


_PROVIDERS: dict[str, Callable[..., list[DocumentRef]]] = {
    "bocyl_opendatasoft": _bocyl_opendatasoft,
}


def discover(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None = None,
) -> list[DocumentRef]:
    """Interpret a discovery payload for ``profile`` into DocumentRef[].

    ``window`` is an optional inclusive ``(start, end)`` ISO-date filter on
    ``published_on`` supplied by the caller; either bound may be ``None``.
    """
    provider = profile.discovery.get("provider")
    handler = _PROVIDERS.get(provider)
    if handler is None:
        raise DiscoveryError(
            f"unsupported discovery provider {provider!r} — add an "
            "interpreter here only if the response shape requires it"
        )
    return handler(profile, payload, window=window)
