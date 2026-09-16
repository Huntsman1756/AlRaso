"""M10.1 pilot runner: ``python -m pipeline.run``.

Assembles the evidence bundle for one (space, source-profile) pilot and
writes ``bundle.json`` + ``packet.json`` + ``packet.md`` under the output
directory. Two execution modes:

- ``--fixtures DIR`` (offline replay — the merge gate): discovery payload,
  document bytes and transport truth are read from recorded fixtures; the
  clock is injectable so output is byte-deterministic.
- ``--live``: discovery and document are actually fetched over
  ``urllib_transport``; ``runner_network`` records where the attempt ran.

Geometry always comes from the recorded OAPN layer digest — the WFS live
check belongs to ``tooling/m10_probe_verify.py``.

No jurisdiction logic: the authority ref is selected by matching the
profile's ``source_id`` against the space's seed authorities.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote

from pipeline.models import ReviewPacket, RunnerNetwork
from pipeline.profiles import load_profile
from pipeline.providers.discovery import discover
from pipeline.providers.fetch import (
    TransportRequest,
    TransportResponse,
    fetch,
    urllib_transport,
)
from pipeline.providers.geometry import geometry_from_layer_digest
from pipeline.providers.inventory import authority_refs, load_seed, list_spaces
from pipeline.providers.parse import parse
from pipeline.providers.version import resolve
from pipeline.review import prepare_pr

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "pipeline" / "sources" / "pilot-spaces.json"
OAPN_WFS = "https://sigred.oapn.es/geoserverOAPN/ows"
OAPN_LIMITES_LAYER = "LimitesParquesNacionalesZPP:view_red_oapn_limite_pn"


class RunError(ValueError):
    """Pilot inputs are incomplete or inconsistent — explicit failure."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _fixture_transport(fixtures: Path) -> Callable:
    meta = json.loads((fixtures / "transport.json").read_text("utf-8"))
    if "responses" in meta:
        # Sequential replay: the i-th transport call gets responses[i]
        # (last one repeated if the recipe performs extra requests).
        responses = [
            (
                item["status"],
                (fixtures / item["body_file"]).read_bytes(),
                item.get("content_type"),
            )
            for item in meta["responses"]
        ]
        if not responses:
            raise RunError("transport.json 'responses' must be non-empty")

        def transport(request: TransportRequest) -> TransportResponse:
            item = responses[
                min(len(transport.calls), len(responses) - 1)
            ]
            transport.calls.append(request)
            return TransportResponse(
                status=item[0], body=item[1], content_type=item[2]
            )

        transport.calls: list[TransportRequest] = []
        return transport

    body = (fixtures / "document.bin").read_bytes()

    def single_transport(request: TransportRequest) -> TransportResponse:
        return TransportResponse(
            status=meta["status"],
            body=body,
            content_type=meta.get("content_type"),
        )

    return single_transport


class _Capture:
    """Wraps a transport and retains the last response body for parsing —
    DocumentEvidence keeps only the digest, the parser needs the bytes."""

    def __init__(self, inner: Callable) -> None:
        self._inner = inner
        self.last: TransportResponse | None = None

    def __call__(self, request: TransportRequest) -> TransportResponse:
        self.last = self._inner(request)
        return self.last


def _select_ref(refs, authority: Mapping[str, str]):
    doc_key = authority.get("doc_key")
    if doc_key:
        keyed = [r for r in refs if r.doc_id == doc_key]
        if keyed:
            return keyed[0]
    cite = authority["cite"]
    hits = [r for r in refs if _norm(cite) in _norm(r.title)]
    if not hits:
        raise RunError(
            f"no discovered ref matches authority cite {cite!r} — "
            "the pilot never fetches an unverified document"
        )
    return hits[0]


def _expand_kv(
    template: str, mapping: Mapping[str, str], *, safe: str = ""
) -> str:
    """Replace ``{key}`` placeholders with URL-quoted values."""
    for key, value in mapping.items():
        template = template.replace(
            "{" + key + "}", quote(str(value), safe=safe)
        )
    return template


def discovery_request(
    profile, authority: Mapping[str, str]
) -> TransportRequest:
    """Build the live discovery request declared by the profile.

    Three declarative shapes, all profile-driven:
    - ``doc_url_template`` → GET on the expanded URL (id-keyed archives).
    - ``method: POST`` + ``body_template`` → form POST (TOC lookups).
    - ``endpoint`` + ``query_template`` → GET on ``endpoint?query``.
    """
    disc = profile.discovery
    template = disc.get("doc_url_template")
    if template:
        return TransportRequest(
            "GET", _expand_kv(template, authority, safe="/")
        )
    endpoint = disc.get("endpoint")
    if not endpoint:
        raise RunError(
            "live discovery requires profile.discovery.endpoint or "
            "doc_url_template"
        )
    if disc.get("method") == "POST":
        body = _expand_kv(
            disc.get("body_template", "{doc_key}"), authority, safe=""
        )
        return TransportRequest(
            "POST",
            endpoint,
            body=body.encode("utf-8"),
            headers=dict(disc.get("post_headers") or {}),
        )
    template = disc.get("query_template", "limit=100")
    for key, value in authority.items():
        template = template.replace("{" + key + "}", str(value))
    url = f"{endpoint}?{quote(template, safe='={}&/:')}"
    return TransportRequest(method="GET", url=url)


def _discovery_payload(
    profile, authority: Mapping[str, str], fixtures: Path | None
) -> Mapping[str, Any]:
    """Return the discovery payload.

    JSON APIs (opendatasoft, socrata) return their parsed JSON. Document
    responses (CGI lookups, TOC pages) are delivered as an envelope
    ``{"url", "body": bytes}`` — the provider interprets the shape.
    """
    if fixtures is not None:
        doc = json.loads(
            (fixtures / "discovery.json").read_text(encoding="utf-8")
        )
        if "body_file" in doc:
            return {
                "url": doc["url"],
                "body": (fixtures / doc["body_file"]).read_bytes(),
            }
        return doc
    request = discovery_request(profile, authority)
    resp = urllib_transport(request)
    try:
        return json.loads(resp.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"url": request.url, "body": resp.body}


def run_pilot(
    profile_name: str,
    space_id: str,
    *,
    out_dir: Path,
    fixtures_dir: Path | None = None,
    live: bool = False,
    seed_path: Path = SEED_PATH,
    runner_network: str | None = None,
    clock: Callable[[], str] | None = None,
) -> ReviewPacket:
    """Run the full M10.1 chain for one pilot and write the artifacts."""
    profile = load_profile(
        ROOT / "pipeline" / "sources" / f"{profile_name}.profile.json"
    )
    seed = load_seed(seed_path)
    spaces = {s.space_id: s for s in list_spaces(seed)}
    space = spaces.get(space_id)
    if space is None:
        raise RunError(f"unknown space {space_id!r}")

    refs = [
        r
        for r in authority_refs(space_id, seed)
        if r["gazette"] == profile.source_id
    ]
    if len(refs) != 1:
        raise RunError(
            f"space {space_id!r}: expected exactly one authority for "
            f"gazette {profile.source_id!r}, found {len(refs)}"
        )
    authority = dict(refs[0])

    if fixtures_dir is None:
        raise RunError(
            "geometry digest fixtures are required — the OAPN layer digest "
            "is the recorded inventory evidence (re-fetchable, not live "
            "in the runner)"
        )
    fixtures_dir = Path(fixtures_dir)
    layer_doc = json.loads(
        (fixtures_dir / "geometry-limites.json").read_text(encoding="utf-8")
    )
    geometry = geometry_from_layer_digest(
        space_id=space_id,
        space_name=space.admin_geom_ref,
        layer_doc=layer_doc,
        layer=OAPN_LIMITES_LAYER,
        source_url=OAPN_WFS,
    )

    payload = _discovery_payload(
        profile, authority, None if live else fixtures_dir
    )
    refs_found = discover(profile, payload)
    doc_ref = _select_ref(refs_found, authority)

    if live:
        transport = _Capture(urllib_transport)
    else:
        transport = _Capture(_fixture_transport(fixtures_dir))
    net = runner_network or (
        RunnerNetwork.FIXTURE.value if not live else None
    )
    now = clock or _utc_now
    evidence = fetch(
        profile, doc_ref, transport=transport, clock=now,
        runner_network=net,
    )

    body = transport.last.body if transport.last is not None else b""
    parsed = parse(profile, evidence, body, clock=now)
    claim = resolve(profile, doc_ref, clock=now)

    bundle = {
        "space": space,
        "geometry": tuple(geometry),
        "authority": authority,
        "discovery": tuple(refs_found),
        "fetch": evidence,
        "parse": parsed,
        "version": claim,
        "change_detection": dict(profile.change_detection),
    }
    packet, md = prepare_pr(space_id, bundle)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bundle.json").write_text(
        json.dumps(
            {k: _ser(v) for k, v in bundle.items()},
            indent=2, sort_keys=True, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out_dir / "packet.json").write_text(
        json.dumps(packet.to_dict(), indent=2, sort_keys=True,
                   ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "packet.md").write_text(md, encoding="utf-8")
    return packet


def _ser(v: Any) -> Any:
    if hasattr(v, "to_dict"):
        return v.to_dict()
    if isinstance(v, (tuple, list)):
        return [_ser(x) for x in v]
    if isinstance(v, dict):
        return {k: _ser(x) for k, x in v.items()}
    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.run")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--space", required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fixtures", type=Path)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--runner-network")
    args = ap.parse_args(argv)

    out = args.out or (
        ROOT / "discovery" / "evidence"
        / f"m10.1-{args.profile}-{args.space}"
    )
    packet = run_pilot(
        args.profile,
        args.space,
        out_dir=out,
        fixtures_dir=args.fixtures,
        live=args.live,
        runner_network=args.runner_network,
    )
    print(
        f"{packet.space_id}: {len(packet.chain_evidence)} links, "
        f"publication_readiness={packet.publication_readiness} -> {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
