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

# WAF/anti-bot interstitial signatures observed in live probes (BORM
# returned "Radware Captcha Page" + hCaptcha). A 2xx carrying any of
# these is a soft block — CONTENT_MARKER_MISMATCH, never SUCCESS.
_INTERSTITIAL_SIGNATURES = (
    b"Radware Captcha",
    b"hcaptcha.com",
    b"ShieldSquare",
    b"cf-chl-bypass",
    b"Just a moment...",  # Cloudflare challenge title
)


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
    store_body: bool = True,
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
        if store_body:
            (evidence_dir / body_name).write_bytes(body)

        if not 200 <= (http_status or 0) <= 299:
            outcome = "HTTP_ERROR"
            marker_ok = False
        elif any(sig in body for sig in _INTERSTITIAL_SIGNATURES):
            # WAF/anti-bot interstitial (e.g. Radware/hCaptcha): a soft
            # block, never source content — regardless of markers.
            outcome = "CONTENT_MARKER_MISMATCH"
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
            "evidence_path": (
                str(
                    (evidence_dir.resolve() / body_name).relative_to(
                        ROOT.resolve()
                    )
                ).replace("\\", "/")
                if (evidence_dir.resolve() / body_name).is_relative_to(
                    ROOT.resolve()
                )
                else body_name
            )
            if store_body
            else "",
            "detail": (
                detail + ("; " if detail else "")
                + "DIGEST_ONLY: body not redistributed"
                if not store_body
                else detail
            ),
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
        if not rel:
            rows.append((rec["probe_id"], "PASS",
                         f"digest-only: sha256 {rec['raw_sha256'][:16]}… "
                         "recorded, body not redistributed"))
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
    headers = {}
    for h in args.header or ():
        name, _, value = h.partition(":")
        headers[name.strip()] = value.strip()
    request = TransportRequest("GET", args.url, headers=headers)
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
            store_body=not args.digest_only,
        )
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


def _cmd_build(args) -> int:
    """Assemble source-atlas.json: per-domain domain.json + probes.json."""
    base = args.evidence_root.resolve()
    domains = []
    for domain_json in sorted(base.glob("*/domain.json")):
        record = json.loads(domain_json.read_text(encoding="utf-8"))
        probes_log = domain_json.parent / "probes.json"
        record["probes"] = (
            json.loads(probes_log.read_text(encoding="utf-8"))
            if probes_log.is_file()
            else []
        )
        record["evidence_dir"] = str(
            domain_json.parent.resolve().relative_to(ROOT)
        ).replace("\\", "/") + "/"
        domains.append(record)
    atlas = {
        "version": 1,
        "generated_at": _utc_now_iso(),
        "domains": domains,
        "notes": "M10.2-A National Source Atlas — evidence-only, no legal "
                 "ingestion. domain_status is verified by the executable "
                 "gate (pipeline.atlas.check_gate), not by declaration.",
    }
    out = base / "source-atlas.json"
    out.write_text(
        json.dumps(atlas, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    print(f"wrote {out} ({len(domains)} domains)")
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


def _cmd_matrices(args) -> int:
    """Derive family-clustering, reachability/fallback and
    change-detection matrices deterministically from the atlas."""
    atlas = load_atlas(args.atlas)
    families: dict[str, list[str]] = {}
    reach: list[dict[str, Any]] = []
    change: dict[str, list[str]] = {}
    for d in atlas["domains"]:
        did = d["domain_id"]
        families.setdefault(d["discovery_mechanism"], []).append(did)
        observed = {
            p["runner_network"]: p["reachability_observed"]
            for p in d.get("probes", [])
            if p.get("reachability_observed")
        }
        reach.append({
            "domain_id": did,
            "expected": d.get("reachability_expected", {}),
            "observed": observed,
            "fallback": d.get("fallback"),
        })
        cd = d.get("change_detection") or {}
        change.setdefault(
            f"{cd.get('mechanism', '?')} [{cd.get('strength', '?')}]",
            [],
        ).append(did)
    out = {
        "generated_at": _utc_now_iso(),
        "family_clustering": {
            k: sorted(v) for k, v in sorted(families.items())
        },
        "reachability_fallback": sorted(
            reach, key=lambda r: r["domain_id"]
        ),
        "change_detection": {
            k: sorted(v) for k, v in sorted(change.items())
        },
    }
    out_path = args.atlas.parent / "matrices.json"
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    print(f"wrote {out_path}")
    return 0


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
    p.add_argument("--header", action="append",
                   help="HTTP request header 'Name: value' (repeatable)")
    p.add_argument("--runner-network", default="unknown")
    p.add_argument("--digest-only", action="store_true",
                   help="record sha256+bytes but do not store the body")
    p.add_argument("--timeout", type=float, default=30.0)
    p.set_defaults(fn=_cmd_probe)

    b = sub.add_parser("build", help="assemble source-atlas.json from "
                                     "per-domain evidence dirs")
    b.add_argument("--evidence-root", required=True, type=Path)
    b.set_defaults(fn=_cmd_build)

    v = sub.add_parser("verify", help="offline digest verification")
    v.add_argument("--evidence-dir", required=True, type=Path)
    v.set_defaults(fn=_cmd_verify)

    g = sub.add_parser("gate", help="executable atlas exit gate")
    g.add_argument("--atlas", required=True, type=Path)
    g.add_argument("--repo-root", type=Path)
    g.set_defaults(fn=_cmd_gate)

    m = sub.add_parser("matrices", help="derive family/reachability/"
                                        "change-detection matrices")
    m.add_argument("--atlas", required=True, type=Path)
    m.set_defaults(fn=_cmd_matrices)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
