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
import html
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


_BOA_DOCN_RE = re.compile(r"DOCN=(\d+)")
_BOA_TITLE_RE = re.compile(
    r'<p class="boaseccion">(.*?)</p>', re.DOTALL
)
_BOA_PUB_RE = re.compile(r"Publicado el (\d{2})/(\d{2})/(\d{4})")


def _boa_cgi(
    profile: SourceProfile,
    payload: Mapping[str, Any],
    *,
    window: tuple[str | None, str | None] | None,
) -> list[DocumentRef]:
    """BRSCGI VERDOC response → DocumentRef.

    BOA's discovery key is the preregistered DOCN; the lookup response is
    the document page itself (G0 fixture ``boa-decreto-16-2022-doc.html``).
    Payload shape: ``{"url": <requested URL>, "body": <raw bytes>}`` —
    BOA serves ISO-8859-1.
    """
    url = payload.get("url")
    body = payload.get("body")
    if not isinstance(url, str) or not isinstance(body, bytes):
        raise DiscoveryError(
            "boa_cgi payload requires {'url': str, 'body': bytes}"
        )
    match = _BOA_DOCN_RE.search(url)
    if match is None:
        raise DiscoveryError(f"boa_cgi: no DOCN in request URL {url!r}")
    docn = match.group(1)

    text = body.decode("iso-8859-1", "replace")
    title_m = _BOA_TITLE_RE.search(text)
    if title_m is None:
        raise DiscoveryError("boa_cgi: no <p class=boaseccion> title")
    title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1)))
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        raise DiscoveryError("boa_cgi: empty document title")

    pub_m = _BOA_PUB_RE.search(text)
    if pub_m is None:
        raise DiscoveryError("boa_cgi: no 'Publicado el' date")
    day, month, year = pub_m.groups()
    published_on = f"{year}-{month}-{day}"
    if window is not None:
        start, end = window
        if (start and published_on < start) or (
            end and published_on > end
        ):
            return []

    return [
        DocumentRef(
            source_id=profile.source_id,
            doc_id=docn,
            published_on=published_on,
            title=title,
            issuer="Gobierno de Aragón",
            discovery_url=url,
            rank=0,
        )
    ]


_PROVIDERS: dict[str, Callable[..., list[DocumentRef]]] = {
    "bocyl_opendatasoft": _bocyl_opendatasoft,
    "boa_cgi": _boa_cgi,
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
