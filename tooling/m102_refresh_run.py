"""M10.2-B refresh runner — replay (offline) / live / gate.

Modes:

    replay  --scenario <dir>
        Run a canned scenario: ``scenario.json`` declares the sequence of
        observations per document; each step either references a body file
        in the scenario dir (real bytes → hashed + canonicalized) or
        declares a failure outcome. Writes ``run-log.json`` and any
        ``packets/*.json|*.md``. Zero network.

    live    --profile <file> --source-id --surface-id --doc-id --url ...
        One live refresh observation through the injected transport
        (verifier tooling only — never used by tests).

    gate    --evidence-root <dir>
        Replays every scenario under the evidence root into a fresh temp
        store and asserts each declared ``expected_final_state``. The
        executable M10.2-B exit check.

Scenario format (``scenario.json``):

    {
      "name": "...", "thresholds": {"absence": 3, ...},
      "canonicalizer": {"id": "identity", "version": 1},
      "steps": [
        {"doc_id": "...", "outcome": "SUCCESS", "body": "v1.html",
         "http_status": 200, "runner_network": "es_local",
         "observed_at": "...", "etag": "...", "last_modified": "...",
         "canonicalizer": {"id": "...", "version": N}   // optional per-step
        },
        {"doc_id": "...", "outcome": "TIMEOUT", ...}
      ],
      "expect": {"final_states": ["BASELINE_CREATED", ...],
                 "packets": ["CHANGED_CONTENT"]}
    }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.models import (  # noqa: E402
    FetchOutcome,
    ReachabilityObserved,
)
from pipeline.providers.fetch import (  # noqa: E402
    TransportRequest,
    urllib_transport,
    TransportError,
    TransportTimeout,
)
from pipeline.profiles import load_profile  # noqa: E402
from pipeline.refresh.canonicalize import (  # noqa: E402
    CanonicalizerError,
    canonical_sha256,
)
from pipeline.refresh.classify import (  # noqa: E402
    RefreshObservation,
    Thresholds,
)
from pipeline.refresh.runner import observe  # noqa: E402
from pipeline.refresh.packets import render_markdown  # noqa: E402
from pipeline.refresh.snapshots import SnapshotStore  # noqa: E402

_NO_RESPONSE = {"TIMEOUT", "TRANSPORT_ERROR"}
_UNREACHABLE_OUTCOMES = _NO_RESPONSE


def _step_to_obs(step: dict, scenario_dir: Path,
                 default_canon: dict) -> RefreshObservation:
    outcome = step["outcome"]
    body_file = step.get("body")
    body = (
        (scenario_dir / body_file).read_bytes()
        if body_file
        else None
    )
    canon = step.get("canonicalizer", default_canon)
    raw = hashlib.sha256(body).hexdigest() if body is not None else None
    if body is None:
        canon_sha = None
    else:
        try:
            canon_sha = canonical_sha256(
                canon["id"], canon["version"], body
            )
        except CanonicalizerError:
            # Unregistered id@version (e.g. a simulated bump): no digest
            # is recorded — never fabricate one. The classifier
            # short-circuits to REBASELINE_REQUIRED on the id/version
            # mismatch before any digest comparison, so None is correct.
            canon_sha = None
    unreachable = outcome in _UNREACHABLE_OUTCOMES
    return RefreshObservation(
        fetch_outcome=FetchOutcome(outcome),
        reachability_observed=ReachabilityObserved(
            "UNREACHABLE" if unreachable else "REACHABLE"
        ),
        observed_at=step["observed_at"],
        runner_network=step.get("runner_network", "es_local"),
        http_status=step.get("http_status"),
        raw_sha256=raw,
        canonical_sha256=canon_sha,
        canonicalizer_id=canon["id"] if body is not None else None,
        canonicalizer_version=(
            canon["version"] if body is not None else None
        ),
        etag=step.get("etag"),
        last_modified=step.get("last_modified"),
    )


def _run_scenario(scenario_dir: Path, store: SnapshotStore) -> dict:
    """Replay one scenario; returns the run-log dict (also persisted)."""
    scenario_dir = Path(scenario_dir)
    spec = json.loads(
        (scenario_dir / "scenario.json").read_text(encoding="utf-8")
    )
    thresholds = Thresholds.from_profile(spec.get("thresholds"))
    default_canon = spec["canonicalizer"]
    src = spec.get("source_id", scenario_dir.name)
    surface = spec.get("surface_id", "main")

    log_rows = []
    packets = []
    for i, step in enumerate(spec["steps"]):
        obs = _step_to_obs(step, scenario_dir, default_canon)
        res = observe(
            store,
            source_id=src,
            surface_id=surface,
            doc_id=step["doc_id"],
            obs=obs,
            thresholds=thresholds,
        )
        log_rows.append(
            {
                "step": i,
                "doc_id": step["doc_id"],
                "outcome": step["outcome"],
                "state": res.verdict.state.value,
                "emits_packet": res.verdict.emits_packet,
                "counters": res.verdict.counters,
                "detail": res.verdict.detail,
            }
        )
        if res.packet is not None:
            packets.append(res.packet)

    run_log = {
        "scenario": spec["name"],
        "source_id": src,
        "surface_id": surface,
        "canonicalizer": default_canon,
        "thresholds": {
            "absence": thresholds.absence,
            "invalid": thresholds.invalid,
            "degraded": thresholds.degraded,
        },
        "steps": log_rows,
        "final_states": [r["state"] for r in log_rows],
        "packets_emitted": [p.outcome for p in packets],
    }
    (scenario_dir / "run-log.json").write_text(
        json.dumps(run_log, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    pkt_dir = scenario_dir / "packets"
    if packets:
        pkt_dir.mkdir(exist_ok=True)
        for j, pkt in enumerate(packets):
            stem = f"packet-{j}-{pkt.outcome.lower()}"
            (pkt_dir / f"{stem}.json").write_text(pkt.to_json(), "utf-8")
            (pkt_dir / f"{stem}.md").write_text(
                render_markdown(pkt), "utf-8"
            )
    return run_log


def _cmd_replay(args) -> int:
    store = SnapshotStore(Path(args.store) if args.store
                          else Path(args.scenario) / "store")
    log = _run_scenario(Path(args.scenario), store)
    print(json.dumps({"final_states": log["final_states"],
                      "packets": log["packets_emitted"]}, indent=2))
    return 0


def _cmd_gate(args) -> int:
    root = Path(args.evidence_root)
    failures = []
    for scenario_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        spec_path = scenario_dir / "scenario.json"
        if not spec_path.is_file():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        expect = spec.get("expect", {})
        with tempfile.TemporaryDirectory() as tmp:
            log = _run_scenario(scenario_dir, SnapshotStore(tmp))
        got_states = log["final_states"]
        want_states = expect.get("final_states")
        got_packets = log["packets_emitted"]
        want_packets = expect.get("packets")
        ok = True
        if want_states is not None and got_states != want_states:
            ok = False
            detail = f"states {got_states} != {want_states}"
        elif want_packets is not None and got_packets != want_packets:
            ok = False
            detail = f"packets {got_packets} != {want_packets}"
        else:
            detail = "ok"
        print(f"  {'PASS' if ok else 'FAIL':5s} {scenario_dir.name:32s} "
              f"{detail}")
        if not ok:
            failures.append(scenario_dir.name)
    print(f"REFRESH_GATE={'PASS' if not failures else 'FAIL'}")
    return 0 if not failures else 1


def _classify_live_body(
    body: bytes, fetch_cfg: dict
) -> FetchOutcome:
    """Classify a 2xx response body with the same semantics as the
    atlas probe + fetch recipes: interstitial and soft-404 guards run
    unconditionally; a configured content_marker must be present."""
    from tooling.m102_atlas_probe import _INTERSTITIAL_SIGNATURES

    if any(sig in body for sig in _INTERSTITIAL_SIGNATURES):
        # WAF/anti-bot interstitial — a soft block, never source content.
        return FetchOutcome.CONTENT_MARKER_MISMATCH
    soft = fetch_cfg.get("soft_404_marker")
    if soft and soft.encode() in body:
        return FetchOutcome.SOFT_404
    marker = fetch_cfg.get("content_marker")
    if marker is not None and marker.encode() not in body:
        return FetchOutcome.CONTENT_MARKER_MISMATCH
    return FetchOutcome.SUCCESS


def _cmd_live(args) -> int:
    """One live observation via injected transport (verifier only).

    Classification mirrors the fetch contract exactly: a non-2xx is
    HTTP_ERROR (404/410 feed absence; anything else feeds INVALID), a
    2xx must survive the interstitial/soft-404/content-marker guards to
    be SUCCESS. Thresholds and canonicalizer come from the profile's
    ``refresh`` section.
    """
    profile = load_profile(args.profile)
    fetch_cfg = dict(profile.fetch)
    refresh_cfg = dict(profile.refresh)
    canon = {
        "id": refresh_cfg.get("canonicalizer_id", "identity"),
        "version": int(refresh_cfg.get("canonicalizer_version", 1)),
    }
    req = TransportRequest("GET", args.url, headers={})
    try:
        resp = urllib_transport(req, timeout=args.timeout)
    except (TransportTimeout, TransportError) as exc:
        kind = "TIMEOUT" if isinstance(exc, TransportTimeout) \
            else "TRANSPORT_ERROR"
        obs = RefreshObservation(
            fetch_outcome=FetchOutcome(kind),
            reachability_observed=ReachabilityObserved.UNREACHABLE,
            observed_at=args.observed_at,
            runner_network=args.runner_network,
            http_status=None,
        )
    else:
        body = resp.body
        if not 200 <= resp.status <= 299:
            outcome = FetchOutcome.HTTP_ERROR
        else:
            outcome = _classify_live_body(body, fetch_cfg)
        obs = RefreshObservation(
            fetch_outcome=outcome,
            reachability_observed=ReachabilityObserved.REACHABLE,
            observed_at=args.observed_at,
            runner_network=args.runner_network,
            http_status=resp.status,
            raw_sha256=(
                hashlib.sha256(body).hexdigest()
                if outcome is FetchOutcome.SUCCESS
                else None
            ),
            canonical_sha256=(
                canonical_sha256(canon["id"], canon["version"], body)
                if outcome is FetchOutcome.SUCCESS
                else None
            ),
            canonicalizer_id=(
                canon["id"] if outcome is FetchOutcome.SUCCESS else None
            ),
            canonicalizer_version=(
                canon["version"]
                if outcome is FetchOutcome.SUCCESS
                else None
            ),
            # TransportResponse carries no headers — etag/last_modified
            # stay None (honest: not captured by this transport).
        )
    store = SnapshotStore(args.store)
    res = observe(
        store,
        source_id=args.source_id,
        surface_id=args.surface_id,
        doc_id=args.doc_id,
        obs=obs,
        thresholds=Thresholds.from_profile(refresh_cfg),
    )
    print(json.dumps({"state": res.verdict.state.value,
                      "packet": res.packet is not None}, indent=2))
    return 0


def _cmd_rebaseline(args) -> int:
    """Human gate: pin the baseline at the latest stored record.

    This is the ONLY way a REBASELINE_REQUIRED observation becomes the
    comparison baseline — spec §C.2 "re-baseline manual". Records the
    action so the pointer move is auditable.
    """
    store = SnapshotStore(args.store)
    hist = store.history(args.source_id, args.surface_id, args.doc_id)
    if not hist:
        print(f"rebaseline: no records for {args.doc_id} — nothing to do")
        return 1
    store.set_baseline(args.source_id, args.surface_id, args.doc_id)
    rec = hist[-1]
    print(json.dumps({
        "rebaselined_to": {
            "doc_id": rec.doc_id,
            "canonicalizer": (
                f"{rec.canonicalizer_id}@{rec.canonicalizer_version}"
            ),
            "canonical_sha256": rec.canonical_sha256,
            "observed_at": rec.observed_at,
        }
    }, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="m102_refresh_run")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("replay", help="offline canned scenario")
    r.add_argument("--scenario", required=True)
    r.add_argument("--store", help="store root (default: <scenario>/store)")
    r.set_defaults(fn=_cmd_replay)

    g = sub.add_parser("gate", help="replay all scenarios + assert expectations")
    g.add_argument("--evidence-root", required=True)
    g.set_defaults(fn=_cmd_gate)

    lv = sub.add_parser("live", help="one live observation (verifier only)")
    lv.add_argument("--store", required=True)
    lv.add_argument("--profile", required=True,
                    help="source profile JSON — supplies refresh "
                         "thresholds, canonicalizer and fetch markers")
    lv.add_argument("--source-id", required=True)
    lv.add_argument("--surface-id", required=True)
    lv.add_argument("--doc-id", required=True)
    lv.add_argument("--url", required=True)
    lv.add_argument("--runner-network", default="es_local")
    lv.add_argument("--observed-at", required=True)
    lv.add_argument("--timeout", type=float, default=30.0)
    lv.set_defaults(fn=_cmd_live)

    rb = sub.add_parser(
        "rebaseline",
        help="HUMAN GATE: pin baseline at latest stored record",
    )
    rb.add_argument("--store", required=True)
    rb.add_argument("--source-id", required=True)
    rb.add_argument("--surface-id", required=True)
    rb.add_argument("--doc-id", required=True)
    rb.set_defaults(fn=_cmd_rebaseline)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
