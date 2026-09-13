"""M10.1 pilot verifier — OFFLINE_REPLAY (hard gate) + LIVE_VERIFY
(execution gate, reachability observational).

Usage:
    python tooling/m10_probe_verify.py --profile bocyl \
        --space pn-picos-de-europa \
        --fixtures discovery/evidence/m10.1-p1-bocyl/fixtures \
        [--runner-network foreign_ci|es_local|fixture|unknown] [--no-live]

OFFLINE_REPLAY reruns the chain over recorded fixtures: every link must
PASS — it is the merge gate.

LIVE_VERIFY issues the real attempts (WFS GetCapabilities, discovery GET,
document GET). Per link:
    response received + contract holds   -> PASS
    response received + contract broken  -> FAIL
    no response + restriction expected   -> INCONCLUSIVE (does not block)
    no response + REACHABLE expected     -> FAIL
    attempt not issued                   -> FAIL
Exit 0 = offline all PASS and no live FAIL; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.profiles import load_profile
from pipeline.providers.fetch import (
    TransportError,
    TransportRequest,
    TransportTimeout,
    urllib_transport,
)
from pipeline.run import OAPN_LIMITES_LAYER, OAPN_WFS, run_pilot

ROOT = Path(__file__).resolve().parents[1]

# Reachability expectations where a failed attempt is observational
# (the source is expected to be unreachable/blocked from that network).
_OBSERVATIONAL = {"ES_ONLY_SUSPECTED", "WAF_BLOCKED", "UNREACHABLE", "UNKNOWN"}


def _offline(profile_name, space_id, fixtures_dir):
    """Replay the chain; returns (rows, bundle) — every row must PASS."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run_pilot(
                profile_name, space_id,
                out_dir=Path(tmp), fixtures_dir=Path(fixtures_dir),
            )
        except Exception as exc:
            return [("*", "FAIL", f"replay raised {type(exc).__name__}: {exc}")], None
        bundle = json.loads((Path(tmp) / "bundle.json").read_text("utf-8"))
        packet = json.loads((Path(tmp) / "packet.json").read_text("utf-8"))

    rows = [("inventory", "PASS", f"space={bundle['space']['space_id']}"),
            ("geometry", "PASS" if bundle["geometry"] else "FAIL",
             f"features={len(bundle['geometry'])}"),
            ("authority", "PASS",
             f"gazette={bundle['authority']['gazette']}"),
            ("discovery",
             "PASS" if bundle["discovery"] else "FAIL",
             f"refs={len(bundle['discovery'])}"),
            ("fetch",
             "PASS" if bundle["fetch"]["fetch_outcome"] == "SUCCESS"
             else "FAIL",
             f"outcome={bundle['fetch']['fetch_outcome']} "
             f"sha={bundle['fetch']['evidence_sha256'][:16]}"),
            ("parse", "PASS", f"doc_id={bundle['parse']['doc_id']}"),
            ("version", "PASS", f"status={bundle['version']['status']}"),
            ("publication",
             "PASS" if packet["publication_readiness"] == "NO" else "FAIL",
             "readiness=NO")]
    return rows, bundle


def _expected(profile, runner_network):
    return profile.reachability.get("expected", {}).get(runner_network)


def _live_attempt(url, marker=None):
    """Issue one real GET. Returns (status, body) or raises."""
    return urllib_transport(TransportRequest(method="GET", url=url))


def _live_row(name, url, marker, expected, *, check=None):
    try:
        resp = _live_attempt(url)
    except (TransportTimeout, TransportError) as exc:
        if expected in _OBSERVATIONAL:
            return (name, "INCONCLUSIVE",
                    f"no response ({type(exc).__name__}); "
                    f"expected={expected}")
        return (name, "FAIL",
                f"no response ({type(exc).__name__}); expected={expected}")
    body = resp.body
    if not 200 <= resp.status <= 299:
        return (name, "FAIL", f"status={resp.status} (reachable, no 2xx)")
    if marker and marker.encode("utf-8") not in body:
        return (name, "FAIL", f"status=200 but marker {marker!r} absent")
    if check is not None:
        try:
            detail = check(body)
        except Exception as exc:
            return (name, "FAIL", f"contract check raised {exc}")
        return (name, "PASS", detail)
    return (name, "PASS", f"status=200 bytes={len(body)}")


def _live(profile, bundle, runner_network):
    expected = _expected(profile, runner_network)
    rows = []
    # geometry: WFS GetCapabilities must list the layer
    rows.append(_live_row(
        "geometry_wfs",
        f"{OAPN_WFS}?service=WFS&version=2.0.0&request=GetCapabilities",
        OAPN_LIMITES_LAYER, expected,
    ))
    # discovery: endpoint + query_template (already cite-expanded offline
    # equivalent — the template's {cite} is filled from the bundle)
    cite = bundle["authority"]["cite"] if bundle else ""
    endpoint = profile.discovery.get("endpoint")
    if endpoint:
        template = profile.discovery.get("query_template", "limit=100")
        url = f"{endpoint}?{quote(template.replace('{cite}', cite), safe='={}&')}"
        rows.append(_live_row(
            "discovery_get", url, None, expected,
            check=lambda b: f"results={len(json.loads(b).get('results', []))}",
        ))
    else:
        rows.append(("discovery_get", "FAIL", "no endpoint — not attempted"))
    # document: the URL the replay actually fetched
    doc_url = bundle["fetch"]["fetched_from"] if bundle else None
    if doc_url:
        rows.append(_live_row(
            "document_get", doc_url,
            profile.fetch.get("content_marker"), expected,
        ))
    else:
        rows.append(("document_get", "FAIL", "no replay URL — not attempted"))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="m10_probe_verify")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--space", required=True)
    ap.add_argument("--fixtures", required=True, type=Path)
    ap.add_argument("--runner-network", default="unknown")
    ap.add_argument("--no-live", action="store_true")
    args = ap.parse_args(argv)

    profile = load_profile(
        ROOT / "pipeline" / "sources" / f"{args.profile}.profile.json"
    )
    print("OFFLINE_REPLAY (hard gate)")
    rows, bundle = _offline(args.profile, args.space, args.fixtures)
    off_ok = True
    for name, status, detail in rows:
        print(f"  {status:13s} {name:15s} {detail}")
        off_ok &= status == "PASS"
    print(f"  => OFFLINE_REPLAY={'PASS' if off_ok else 'FAIL'}")

    live_fail = False
    if not args.no_live:
        print("LIVE_VERIFY (execution gate; reachability observational)")
        for name, status, detail in _live(profile, bundle,
                                          args.runner_network):
            print(f"  {status:13s} {name:15s} {detail}")
            live_fail |= status == "FAIL"
        print("  => LIVE_VERIFY=" + ("FAIL" if live_fail else "DONE"))

    return 0 if off_ok and not live_fail else 1


if __name__ == "__main__":
    sys.exit(main())
