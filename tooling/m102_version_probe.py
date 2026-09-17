"""M10.2-C version-signal verifier — live probe + evidence + gate.

Modes:

    probe --profile <p> --doc-id <id> --published-on <date>
          --evidence-dir <d> [--socrata-row <file>] [--eli-url <u>]

        Live verification (verifier only — tests never call this):
        fetches the signal surfaces via urllib_transport, preserves the
        response sha256/timestamps/runner_network, builds the evidence
        bundle, calls resolve(), writes evidence.json + claim.json.

        BOE (signal_source=boe_metadatos): fetches
            /datosabiertos/api/legislacion-consolidada/id/{id}/metadatos
        DOGC (signal_source=dogc_socrata_eli): requires --socrata-row
            (a pre-fetched Socrata row JSON file) and --eli-url; fetches
            the ELI URL and captures the effective redirect URL
            (idNumber/idVersion).

    gate --evidence-root <d>

        Asserts >= 2 RESOLVED claims per signal source with complete
        provenance; every claim file is re-checked against its evidence.
        The executable M10.2-C exit check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.models import DocumentRef  # noqa: E402
from pipeline.profiles import load_profile  # noqa: E402
from pipeline.providers.fetch import (  # noqa: E402
    TransportError,
    TransportRequest,
    TransportTimeout,
    urllib_transport,
)
from pipeline.providers.version import resolve  # noqa: E402

_BOE_METADATOS = (
    "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
    "/id/{doc_id}/metadatos"
)

_PROVENANCE_KEYS = (
    "signal_source",
    "endpoint",
    "retrieved_at",
    "response_sha256",
    "runner_network",
    "fetch_outcome",
)


def _utc_now_iso() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url: str, headers: dict | None = None):
    """One live GET. Returns (outcome, status, body, effective_url)."""
    req = TransportRequest("GET", url, headers=headers or {})
    try:
        resp = urllib_transport(req, timeout=30.0)
    except (TransportTimeout, TransportError) as exc:
        kind = (
            "TIMEOUT" if isinstance(exc, TransportTimeout)
            else "TRANSPORT_ERROR"
        )
        return kind, None, b"", None
    outcome = "SUCCESS" if 200 <= resp.status <= 299 else "HTTP_ERROR"
    return outcome, resp.status, resp.body, resp.effective_url


def _probe_boe(doc_id: str, runner: str) -> dict:
    """Fetch BOE metadatos; returns the consolidated evidence bundle."""
    url = _BOE_METADATOS.format(doc_id=doc_id)
    outcome, status, body, _ = _get(url, {"Accept": "application/json"})
    bundle = {
        "signal_source": "boe_metadatos",
        "endpoint": url,
        "retrieved_at": _utc_now_iso(),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "http_status": status,
        "runner_network": runner,
        "fetch_outcome": outcome,
        "payload": None,
    }
    if outcome == "SUCCESS":
        try:
            bundle["payload"] = json.loads(body)
        except json.JSONDecodeError:
            bundle["fetch_outcome"] = "INVALID"
            bundle["parse_error"] = "response is not JSON"
    return bundle


def _probe_dogc(doc_id: str, eli_url: str, socrata_row_path: str,
                runner: str) -> dict:
    """DOGC: pre-fetched Socrata row + live ELI redirect resolution."""
    row = json.loads(Path(socrata_row_path).read_text(encoding="utf-8"))
    if isinstance(row, list):
        row = row[0] if row else {}
    outcome, status, body, effective_url = _get(eli_url)
    bundle = {
        "signal_source": "dogc_socrata_eli",
        "endpoint": eli_url,
        "retrieved_at": _utc_now_iso(),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "http_status": status,
        "runner_network": runner,
        "fetch_outcome": outcome,
        "payload": {
            "socrata_row": row,
            "eli_redirect": {
                "request_url": eli_url,
                "effective_url": effective_url,
                "http_status": status,
            },
        },
    }
    return bundle


def _cmd_probe(args) -> int:
    profile = load_profile(args.profile)
    signal = profile.versioning.get("signal_source")
    runner = args.runner_network
    if signal == "boe_metadatos":
        bundle = _probe_boe(args.doc_id, runner)
    elif signal == "dogc_socrata_eli":
        if not args.socrata_row or not args.eli_url:
            print("probe: dogc requires --socrata-row and --eli-url")
            return 1
        bundle = _probe_dogc(
            args.doc_id, args.eli_url, args.socrata_row, runner
        )
    else:
        print(f"probe: unsupported signal_source {signal!r}")
        return 1

    doc_ref = DocumentRef(
        source_id=profile.source_id,
        doc_id=args.doc_id,
        published_on=args.published_on,
        title=args.title or "",
        issuer=args.issuer or "",
        discovery_url=bundle["endpoint"],
    )
    claim = resolve(
        profile,
        doc_ref,
        structured_evidence={"consolidated": bundle},
    )

    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "evidence.json").write_text(
        json.dumps(
            {
                "doc_id": args.doc_id,
                "published_on": args.published_on,
                "bundle": bundle,
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )
    (evidence_dir / "claim.json").write_text(
        json.dumps(claim.to_dict(), indent=2, sort_keys=True,
                   ensure_ascii=False)
        + "\n",
        "utf-8",
    )
    print(json.dumps({
        "doc_id": args.doc_id,
        "status": claim.status.value,
        "effective_from": claim.effective_from,
        "consolidated_state": claim.consolidated_state,
    }, indent=2))
    return 0


def _cmd_gate(args) -> int:
    """Assert >=2 RESOLVED per signal source with complete provenance."""
    root = Path(args.evidence_root)
    counts: dict[str, int] = {"boe_metadatos": 0, "dogc_socrata_eli": 0}
    failures = []
    for claim_path in sorted(root.rglob("claim.json")):
        evidence_path = claim_path.parent / "evidence.json"
        if not evidence_path.is_file():
            failures.append(f"{claim_path.parent.name}: no evidence.json")
            continue
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        ev = json.loads(evidence_path.read_text(encoding="utf-8"))
        bundle = ev.get("bundle", {})
        missing = [k for k in _PROVENANCE_KEYS if k not in bundle]
        if missing:
            failures.append(
                f"{claim_path.parent.name}: provenance missing {missing}"
            )
            continue
        src = bundle.get("signal_source")
        if claim.get("status") == "RESOLVED":
            if claim.get("doc_id") != ev.get("doc_id"):
                failures.append(
                    f"{claim_path.parent.name}: claim doc_id != evidence"
                )
                continue
            counts[src] = counts.get(src, 0) + 1
        else:
            reason = (claim.get("resolver_evidence") or {}).get(
                "manual_review_reason", "?"
            )
            print(f"  manual: {claim_path.parent.name} ({reason})")
    ok = all(counts.get(s, 0) >= 2 for s in counts)
    for s, n in counts.items():
        print(f"  {s}: {n} RESOLVED (need >= 2)")
    print(f"VERSION_GATE={'PASS' if ok and not failures else 'FAIL'}")
    for f in failures:
        print(f"  FAIL {f}")
    return 0 if ok and not failures else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="m102_version_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="one live version-signal probe")
    p.add_argument("--profile", required=True)
    p.add_argument("--doc-id", required=True)
    p.add_argument("--published-on", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--issuer", default="")
    p.add_argument("--evidence-dir", required=True)
    p.add_argument("--socrata-row", help="pre-fetched Socrata row JSON")
    p.add_argument("--eli-url", help="DOGC ELI /xml URL")
    p.add_argument("--runner-network", default="es_local")
    p.set_defaults(fn=_cmd_probe)

    g = sub.add_parser("gate", help="verify >=2 RESOLVED per source")
    g.add_argument("--evidence-root", required=True)
    g.set_defaults(fn=_cmd_gate)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
