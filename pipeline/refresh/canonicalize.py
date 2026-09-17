"""Canonicalizers — versioned, conservative, per family.

Spec M10.2 §B: the canonicalizer removes ONLY noise demonstrated
empirically for that source family (fetch timestamps, volatile tokens,
counters). ``canonicalizer_id`` + ``canonicalizer_version`` travel in
every comparison; a bump means ``REBASELINE_REQUIRED`` and can never be
classified as source content change.

CANONICALIZER_GATE (§C.2/§G) — bidirectional, enforced by
``tests/test_m102_refresh_canonicalize.py`` against committed fixtures:

    known-noise fixtures       -> canonical output identical -> 0 FP
    semantic-mutation fixtures -> canonical output differs   -> 0 FN
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable

CANONICALIZERS: dict[str, dict[int, Callable[[bytes], bytes]]] = {}


class CanonicalizerError(ValueError):
    """Unknown canonicalizer id/version — fail explicit."""


def _register(cid: str, version: int):
    def deco(fn: Callable[[bytes], bytes]) -> Callable[[bytes], bytes]:
        CANONICALIZERS.setdefault(cid, {})[version] = fn
        return fn

    return deco


@_register("identity", 1)
def _identity_v1(body: bytes) -> bytes:
    """canonical = raw. For formats with no demonstrated volatile noise
    (PDF binaries, structured XML payloads)."""
    return body


# html_volatile@1 — demonstrated noise only, observed in M10.2-A probes:
#   - HTML comments (template generators stamp build/dates there)
#   - <meta name="csrf-token" content="..."> (rotating request token)
#   - nonce="..." attributes (CSP per-request nonce)
#   - __VIEWSTATE / __EVENTVALIDATION hidden inputs (ASP.NET per-request)
# Everything else passes through byte-identical: text, structure, ids.
_COMMENT_RE = re.compile(rb"<!--.*?-->", re.DOTALL)
_CSRF_META_RE = re.compile(
    rb'<meta\s+name="csrf-token"\s+content="[^"]*"\s*/?>',
    re.IGNORECASE,
)
_NONCE_ATTR_RE = re.compile(rb'\snonce="[^"]*"', re.IGNORECASE)
_VIEWSTATE_RE = re.compile(
    rb'<input[^>]*name="(?:__VIEWSTATE|__EVENTVALIDATION)"[^>]*>',
    re.IGNORECASE,
)


@_register("html_volatile", 1)
def _html_volatile_v1(body: bytes) -> bytes:
    out = _VIEWSTATE_RE.sub(b"<input viewstate/>", body)
    out = _CSRF_META_RE.sub(b'<meta name="csrf-token"/>', out)
    out = _NONCE_ATTR_RE.sub(b"", out)
    out = _COMMENT_RE.sub(b"", out)
    return out


def known(canonicalizer_id: str, version: int) -> bool:
    return version in CANONICALIZERS.get(canonicalizer_id, {})


def canonical_bytes(
    canonicalizer_id: str, version: int, body: bytes
) -> bytes:
    try:
        fn = CANONICALIZERS[canonicalizer_id][version]
    except KeyError as exc:
        raise CanonicalizerError(
            f"unknown canonicalizer {canonicalizer_id}@{version}"
        ) from exc
    return fn(body)


def canonical_sha256(
    canonicalizer_id: str, version: int, body: bytes
) -> str:
    return hashlib.sha256(
        canonical_bytes(canonicalizer_id, version, body)
    ).hexdigest()
