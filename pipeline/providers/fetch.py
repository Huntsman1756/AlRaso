"""DocumentFetcher: DocumentRef + fetch recipe → DocumentEvidence.

Boundary (Task 4): this module executes the fetch recipe declared in the
profile against an *injected* transport and records execution truth. It does
not parse content, interpret legally, resolve versions or rediscover — the
only content check is the mechanical ``content_marker`` /
``soft_404_marker`` byte containment required by the contract.

Frozen result mapping (plan §7 fix 2):

- 2xx + content_marker present  → REACHABLE + SUCCESS
- 4xx/5xx                       → REACHABLE + HTTP_ERROR
- 2xx + soft_404_marker         → REACHABLE + SOFT_404
- 2xx + content_marker absent   → REACHABLE + CONTENT_MARKER_MISMATCH
- timeout                       → UNREACHABLE + TIMEOUT
- transport error (no response) → UNREACHABLE + TRANSPORT_ERROR

``evidence_sha256``/``bytes_sha256`` are sha256 of the raw received bytes —
never of normalized text (G0 convention). ``observed_at`` comes from an
injectable clock so offline replay is byte-deterministic.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.parse import urljoin

from pipeline.models import (
    DocumentEvidence,
    DocumentRef,
    FetchOutcome,
    ReachabilityObserved,
    RunnerNetwork,
)
from pipeline.profiles import SourceProfile


class FetchError(ValueError):
    """Recipe or profile fetch configuration is unusable — explicit
    failure, never a fabricated DocumentEvidence."""


class TransportError(Exception):
    """Transport-level failure: no HTTP response was received."""


class TransportTimeout(TransportError):
    """The attempt timed out before any response."""


@dataclass(frozen=True)
class TransportRequest:
    method: str
    url: str
    body: bytes | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: bytes
    content_type: str | None = None
    # Final URL after redirects, when the transport captures it. None
    # means "not captured" — callers must never assume it equals the
    # request URL. (DOGC ELI resolution needs it: idNumber/idVersion
    # arrive via the redirect to the AkomaNtoso servlet.)
    effective_url: str | None = None


# A transport is any callable TransportRequest → TransportResponse that
# raises TransportTimeout/TransportError on failure. Tests inject fakes;
# the live verifier uses urllib_transport below.
Transport = Callable[[TransportRequest], TransportResponse]


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_runner_network(
    runner_network: RunnerNetwork | str | None,
) -> RunnerNetwork:
    if runner_network is not None:
        return RunnerNetwork(runner_network)
    raw = os.environ.get("ALRASO_RUNNER_NETWORK", "unknown")
    try:
        return RunnerNetwork(raw)
    except ValueError:
        return RunnerNetwork.UNKNOWN


def _expand(template: str, doc_ref: DocumentRef, fetch_cfg: Mapping) -> str:
    """Expand {doc_id}/{source_id}/date/N/ext placeholders from the ref."""
    published = dt.date.fromisoformat(doc_ref.published_on)
    values = {
        "doc_id": doc_ref.doc_id,
        "source_id": doc_ref.source_id,
        "YYYY": f"{published.year:04d}",
        "MM": f"{published.month:02d}",
        "DD": f"{published.day:02d}",
        "DDMMYYYY": f"{published.day:02d}{published.month:02d}{published.year:04d}",
        "N": doc_ref.doc_id.rsplit("-", 1)[-1],
        "ext": fetch_cfg.get("formats", ["xml"])[0],
    }
    try:
        return template.format(**values)
    except KeyError as exc:
        raise FetchError(
            f"doc_url_template placeholder {exc} not expandable from "
            f"DocumentRef {doc_ref.doc_id!r}"
        ) from exc


def _classify(
    status: int, body: bytes, fetch_cfg: Mapping[str, Any]
) -> tuple[FetchOutcome, bool]:
    """Frozen outcome table. Marker checks are byte containment only."""
    if not 200 <= status <= 299:
        return FetchOutcome.HTTP_ERROR, False
    soft = fetch_cfg.get("soft_404_marker")
    if soft and soft.encode("utf-8") in body:
        return FetchOutcome.SOFT_404, False
    if fetch_cfg["content_marker"].encode("utf-8") in body:
        return FetchOutcome.SUCCESS, True
    return FetchOutcome.CONTENT_MARKER_MISMATCH, False


def _failure_evidence(
    doc_ref: DocumentRef,
    recipe: str,
    url: str,
    *,
    now: str,
    runner_network: RunnerNetwork,
    outcome: FetchOutcome,
) -> DocumentEvidence:
    return DocumentEvidence(
        doc_ref=doc_ref,
        method_recipe_id=recipe,
        fetched_at=now,
        fetched_from=url,
        http_status=None,
        content_marker_ok=False,
        bytes_sha256="",
        content_type=None,
        fetch_outcome=outcome,
        observed_at=now,
        evidence_sha256="",
        runner_network=runner_network,
        reachability_observed=ReachabilityObserved.UNREACHABLE,
    )


def _success_evidence(
    doc_ref: DocumentRef,
    recipe: str,
    url: str,
    *,
    now: str,
    runner_network: RunnerNetwork,
    response: TransportResponse,
    fetch_cfg: Mapping[str, Any],
) -> DocumentEvidence:
    outcome, marker_ok = _classify(response.status, response.body, fetch_cfg)
    digest = hashlib.sha256(response.body).hexdigest()
    return DocumentEvidence(
        doc_ref=doc_ref,
        method_recipe_id=recipe,
        fetched_at=now,
        fetched_from=url,
        http_status=response.status,
        content_marker_ok=marker_ok,
        bytes_sha256=digest,
        content_type=response.content_type,
        fetch_outcome=outcome,
        observed_at=now,
        evidence_sha256=digest,
        runner_network=runner_network,
        reachability_observed=ReachabilityObserved.REACHABLE,
    )


def fetch(
    profile: SourceProfile,
    doc_ref: DocumentRef,
    *,
    transport: Transport,
    clock: Callable[[], str] = _utc_now_iso,
    runner_network: RunnerNetwork | str | None = None,
) -> DocumentEvidence:
    """Execute the profile's fetch recipe for ``doc_ref``.

    ``transport`` is injected (tests use fakes; live runs use
    ``urllib_transport``). ``clock`` is injectable for deterministic replay.
    ``runner_network`` defaults to env ``ALRASO_RUNNER_NETWORK`` else
    ``unknown``.
    """
    fetch_cfg = profile.fetch
    recipe = fetch_cfg.get("recipe")
    network = _resolve_runner_network(runner_network)
    now = clock()

    if recipe == "get_simple":
        url = doc_ref.discovery_url
        request = TransportRequest(method="GET", url=url)
        try:
            response = transport(request)
        except TransportTimeout:
            return _failure_evidence(
                doc_ref, recipe, url, now=now,
                runner_network=network, outcome=FetchOutcome.TIMEOUT,
            )
        except TransportError:
            return _failure_evidence(
                doc_ref, recipe, url, now=now,
                runner_network=network,
                outcome=FetchOutcome.TRANSPORT_ERROR,
            )
        return _success_evidence(
            doc_ref, recipe, url, now=now,
            runner_network=network, response=response, fetch_cfg=fetch_cfg,
        )

    if recipe == "cgi":
        template = fetch_cfg.get("doc_url_template")
        if not template:
            raise FetchError("recipe 'cgi' requires fetch.doc_url_template")
        url = _expand(template, doc_ref, fetch_cfg)
        request = TransportRequest(method="GET", url=url)
        try:
            response = transport(request)
        except TransportTimeout:
            return _failure_evidence(
                doc_ref, recipe, url, now=now,
                runner_network=network, outcome=FetchOutcome.TIMEOUT,
            )
        except TransportError:
            return _failure_evidence(
                doc_ref, recipe, url, now=now,
                runner_network=network,
                outcome=FetchOutcome.TRANSPORT_ERROR,
            )
        return _success_evidence(
            doc_ref, recipe, url, now=now,
            runner_network=network, response=response, fetch_cfg=fetch_cfg,
        )

    if recipe == "post_then_get":
        endpoint = fetch_cfg.get("endpoint")
        pattern = fetch_cfg.get("response_url_pattern")
        if not endpoint or not pattern:
            raise FetchError(
                "recipe 'post_then_get' requires fetch.endpoint and "
                "fetch.response_url_pattern"
            )
        body_template = fetch_cfg.get("post_body_template", "{doc_id}")
        post = TransportRequest(
            method="POST",
            url=endpoint,
            body=_expand(body_template, doc_ref, fetch_cfg).encode("utf-8"),
            headers=dict(fetch_cfg.get("post_headers") or {}),
        )
        try:
            first = transport(post)
        except TransportTimeout:
            return _failure_evidence(
                doc_ref, recipe, endpoint, now=now,
                runner_network=network, outcome=FetchOutcome.TIMEOUT,
            )
        except TransportError:
            return _failure_evidence(
                doc_ref, recipe, endpoint, now=now,
                runner_network=network,
                outcome=FetchOutcome.TRANSPORT_ERROR,
            )
        match = re.search(pattern, first.body.decode("utf-8", "replace"))
        if match is None:
            raise FetchError(
                f"response_url_pattern {pattern!r} not found in POST "
                "response — cannot derive document URL"
            )
        url = urljoin(endpoint, match.group(0))
        get = TransportRequest(method="GET", url=url)
        try:
            response = transport(get)
        except TransportTimeout:
            return _failure_evidence(
                doc_ref, recipe, url, now=now,
                runner_network=network, outcome=FetchOutcome.TIMEOUT,
            )
        except TransportError:
            return _failure_evidence(
                doc_ref, recipe, url, now=now,
                runner_network=network,
                outcome=FetchOutcome.TRANSPORT_ERROR,
            )
        return _success_evidence(
            doc_ref, recipe, url, now=now,
            runner_network=network, response=response, fetch_cfg=fetch_cfg,
        )

    raise FetchError(f"unsupported fetch recipe {recipe!r}")


def _live_ssl_context():
    """TLS context for the read-only public-document live transport.

    Several Spanish public administration servers still present legacy
    cipher suites that OpenSSL 3.x rejects at SECLEVEL=2 with a handshake
    alert (verified: portaljuridic.gencat.cat, 2026-09-16). The transport
    is verification-only — it fetches published documents and never sends
    credentials — so SECLEVEL=1 keeps coverage honest without weakening
    any authenticated channel.
    """
    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_default_certs()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    return ctx


def urllib_transport(
    request: TransportRequest, *, timeout: float = 30.0
) -> TransportResponse:
    """Live transport over stdlib urllib — used only by the manual/CI
    verify tooling (``tooling/m10_*_verify.py``). Tests always inject fakes.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        request.url,
        data=request.body,
        method=request.method,
        headers=dict(request.headers),
    )
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_live_ssl_context()
        ) as resp:
            return TransportResponse(
                status=resp.status,
                body=resp.read(),
                content_type=resp.headers.get("Content-Type"),
                effective_url=resp.geturl(),
            )
    except urllib.error.HTTPError as exc:
        # An HTTP error status IS a response: server was reached.
        return TransportResponse(
            status=exc.code,
            body=exc.read() or b"",
            content_type=exc.headers.get("Content-Type") if exc.headers else None,
        )
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason or "timeout" in reason.lower():
            raise TransportTimeout(reason) from exc
        raise TransportError(reason) from exc
    except TimeoutError as exc:
        raise TransportTimeout(str(exc)) from exc
    except OSError as exc:
        raise TransportError(str(exc)) from exc
