"""M10.2-A atlas probe tooling — live probe writer + offline verifier.

Usage:
    # live probe (only this mode touches the network):
    python tooling/m102_atlas_probe.py probe \\
        --evidence-dir discovery/evidence/m10.2-atlas/es-pv \\
        --domain ES-PV --probe-id portal --surface portal \\
        --kind portal --url https://www.euskadi.eus/web01-bopv/es/ \\
        [--marker BOLETIN] [--soft-404-marker ...] \\
        [--runner-network es_local|foreign_ci|unknown]

    # offline verification of a domain's probe log (tests / CI):
    python tooling/m102_atlas_probe.py verify \\
        --evidence-dir discovery/evidence/m10.2-atlas/es-pv

    # executable exit gate over the aggregate atlas:
    python tooling/m102_atlas_probe.py gate \\
        --atlas discovery/evidence/m10.2-atlas/source-atlas.json

Every probe appends one record to ``probes.json`` inside the evidence dir
and stores the raw response body as ``<probe_id>.body``. ``verify`` and
``gate`` never touch the network: they re-hash stored bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.atlas import check_gate, load_atlas
from pipeline.providers.fetch import (
    TransportError,
    TransportRequest,
    TransportTimeout,
    urllib_transport,
)

ROOT = Path(__file__).resolve().parents[1]


def _utc_now_iso() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_probe(
    *,
    evidence_dir: Path,
    domain_id: str,
    probe_id: str,
    surface_id: str,
    kind: str,
    url: str,
    body: bytes,
    http_status: int | None,
    content_type: str | None,
    marker: bytes | None,
    soft_404_marker: bytes | None = None,
    runner_network: str = "unknown",
    now=lambda: _utc_now_iso(),
    detail: str = "",
    transport_error: str | None = None,
) -> dict:
    """Record one probe observation and persist the raw body.

    ``transport_error`` set means no HTTP response arrived
    (TIMEOUT/TRANSPORT_ERROR → UNREACHABLE, never absence).
    """
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if transport_error is not None:
        outcome = (
            "TIMEOUT" if "timed out" in transport_error.lower()
            or "timeout" in transport_error.lower()
            else "TRANSPORT_ERROR"
        )
        record = {
            "probe_id": probe_id,
            "surface_id": surface_id,
            "kind": kind,
            "url": url,
            "observed_at": now(),
            "runner_network": runner_network,
            "reachability_observed": "UNREACHABLE",
            "fetch_outcome": outcome,
            "http_status": None,
            "content_marker_ok": None,
            "raw_sha256": "",
            "bytes": None,
            "content_type": None,
            "evidence_path": "",
            "detail": detail or transport_error,
        }
    else:
        sha = hashlib.sha256(body).hexdigest()
        body_name = f"{probe_id}.body"
        (evidence_dir / body_name).write_bytes(body)

        if not 200 <= (http_status or 0) <= 299:
            outcome = "HTTP_ERROR"
            marker_ok = False
        elif soft_404_marker and soft_404_marker in body:
            outcome = "SOFT_404"
            marker_ok = False
        elif marker is None:
            outcome = "SUCCESS"
            marker_ok = None
        elif marker in body:
            outcome = "SUCCESS"
            marker_ok = True
        else:
            outcome = "CONTENT_MARKER_MISMATCH"
            marker_ok = False

        record = {
            "probe_id": probe_id,
            "surface_id": surface_id,
            "kind": kind,
            "url": url,
            "observed_at": now(),
            "runner_network": runner_network,
            "reachability_observed": "REACHABLE",
            "fetch_outcome": outcome,
            "http_status": http_status,
            "content_marker_ok": marker_ok,
            "raw_sha256": sha,
            "bytes": len(body),
            "content_type": content_type,
            "evidence_path": str(
                (evidence_dir / body_name).relative_to(ROOT)
            ).replace("\\", "/")
            if evidence_dir.resolve().is_relative_to(ROOT.resolve())
            else body_name,
            "detail": detail,
        }

    log_path = evidence_dir / "probes.json"
    log = []
    if log_path.is_file():
        log = json.loads(log_path.read_text(encoding="utf-8"))
    log = [r for r in log if r.get("probe_id") != probe_id]
    log.append(record)
    log_path.write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return record


def verify_probe_log(evidence_dir: Path) -> tuple[bool, list[tuple[str, str, str]]]:
    """Offline: re-hash every stored body against its recorded digest."""
    evidence_dir = Path(evidence_dir)
    log_path = evidence_dir / "probes.json"
    if not log_path.is_file():
        return False, [("*", "FAIL", "no probes.json")]
    log = json.loads(log_path.read_text(encoding="utf-8"))
    rows = []
    ok = True
    for rec in log:
        rel = rec.get("evidence_path") or ""
        if not rec.get("raw_sha256"):
            rows.append((rec["probe_id"], "PASS",
                         f"no-response observation: {rec['fetch_outcome']}"))
            continue
        candidates = [evidence_dir / Path(rel).name, ROOT / rel]
        body_path = next((c for c in candidates if c.is_file()), None)
        if body_path is None:
            rows.append((rec["probe_id"], "FAIL", f"missing body {rel}"))
            ok = False
            continue
        actual = hashlib.sha256(body_path.read_bytes()).hexdigest()
        if actual == rec["raw_sha256"]:
            rows.append((rec["probe_id"], "PASS",
                         f"sha256 {actual[:16]}… verified"))
        else:
            rows.append((rec["probe_id"], "FAIL",
                         f"digest mismatch recorded={rec['raw_sha256'][:16]}… "
                         f"actual={actual[:16]}…"))
            ok = False
    return ok, rows


def _cmd_probe(args) -> int:
    request = TransportRequest("GET", args.url)
    try:
        resp = urllib_transport(request, timeout=args.timeout)
    except TransportTimeout as exc:
        rec = record_probe(
            evidence_dir=args.evidence_dir,
            domain_id=args.domain,
            probe_id=args.probe_id,
            surface_id=args.surface,
            kind=args.kind,
            url=args.url,
            body=b"",
            http_status=None,
            content_type=None,
            marker=None,
            runner_network=args.runner_network,
            transport_error=f"TransportTimeout: {exc}",
        )
    except TransportError as exc:
        rec = record_probe(
            evidence_dir=args.evidence_dir,
            domain_id=args.domain,
            probe_id=args.probe_id,
            surface_id=args.surface,
            kind=args.kind,
            url=args.url,
            body=b"",
            http_status=None,
            content_type=None,
            marker=None,
            runner_network=args.runner_network,
            transport_error=f"TransportError: {exc}",
        )
    else:
        rec = record_probe(
            evidence_dir=args.evidence_dir,
            domain_id=args.domain,
            probe_id=args.probe_id,
            surface_id=args.surface,
            kind=args.kind,
            url=args.url,
            body=resp.body,
            http_status=resp.status,
            content_type=resp.content_type,
            marker=args.marker.encode() if args.marker else None,
            soft_404_marker=(
                args.soft_404_marker.encode() if args.soft_404_marker else None
            ),
            runner_network=args.runner_network,
        )
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


def _cmd_verify(args) -> int:
    ok, rows = verify_probe_log(args.evidence_dir)
    for probe_id, status, detail in rows:
        print(f"  {status:5s} {probe_id:20s} {detail}")
    print(f"VERIFY={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def _cmd_gate(args) -> int:
    atlas = load_atlas(args.atlas)
    ok, rows = check_gate(atlas, repo_root=args.repo_root or ROOT)
    for domain_id, status, detail in rows:
        print(f"  {status:5s} {domain_id:7s} {detail}")
    proven = sum(1 for r in atlas["domains"] if r["domain_status"] == "PROVEN")
    blocked = sum(
        1 for r in atlas["domains"]
        if r["domain_status"] == "BLOCKED_WITH_EVIDENCE"
    )
    unprobed = sum(
        1 for r in atlas["domains"] if r["domain_status"] == "UNPROBED"
    )
    print(f"PROVEN={proven} BLOCKED_WITH_EVIDENCE={blocked} "
          f"UNPROBED={unprobed}")
    print(f"GATE={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="m102_atlas_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="live probe (network)")
    p.add_argument("--evidence-dir", required=True, type=Path)
    p.add_argument("--domain", required=True)
    p.add_argument("--probe-id", required=True)
    p.add_argument("--surface", required=True)
    p.add_argument("--kind", required=True,
                   choices=["portal", "discovery", "document", "sumario",
                            "api", "feed", "other"])
    p.add_argument("--url", required=True)
    p.add_argument("--marker")
    p.add_argument("--soft-404-marker")
    p.add_argument("--runner-network", default="unknown")
    p.add_argument("--timeout", type=float, default=30.0)
    p.set_defaults(fn=_cmd_probe)

    v = sub.add_parser("verify", help="offline digest verification")
    v.add_argument("--evidence-dir", required=True, type=Path)
    v.set_defaults(fn=_cmd_verify)

    g = sub.add_parser("gate", help="executable atlas exit gate")
    g.add_argument("--atlas", required=True, type=Path)
    g.add_argument("--repo-root", type=Path)
    g.set_defaults(fn=_cmd_gate)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
