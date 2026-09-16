"""M10.1 Task 10 — pipeline.run: P1 offline replay end-to-end.

Boundary: ``run_pilot`` assembles the full bundle from fixture artifacts
(no network), writes bundle.json + packet.json + packet.md, and the
9-link chain lands in the packet with publication_readiness=NO.
"""

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import pipeline.run as run_mod
from pipeline.models import FetchOutcome, ReachabilityObserved
from pipeline.run import RunError, run_pilot

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "discovery" / "evidence" / "m10.1-p1-bocyl" / "fixtures"
G0_XML = ROOT / "discovery" / "evidence" / "spain-coverage-g0" / (
    "bocyl-17-2025-head.xml"
)


def test_p1_offline_replay_produces_packet(tmp_path):
    out = tmp_path / "out"
    packet = run_pilot(
        "bocyl",
        "pn-picos-de-europa",
        out_dir=out,
        fixtures_dir=FIXTURES,
        clock=lambda: "2026-09-13T00:00:00Z",
    )
    assert packet.space_id == "pn-picos-de-europa"
    assert packet.publication_readiness == "NO"
    assert len(packet.chain_evidence) == 9

    bundle = json.loads((out / "bundle.json").read_text(encoding="utf-8"))
    assert bundle["fetch"]["fetch_outcome"] == "SUCCESS"
    assert bundle["fetch"]["reachability_observed"] == "REACHABLE"
    assert bundle["fetch"]["runner_network"] == "fixture"
    assert bundle["fetch"]["doc_ref"]["doc_id"] == "BOCYL-D-15122025-1"
    # Evidence digest = sha256 of the exact fixture bytes.
    assert bundle["fetch"]["evidence_sha256"] == hashlib.sha256(
        G0_XML.read_bytes()
    ).hexdigest()
    assert bundle["parse"]["doc_id"] == "BOCYL-D-15122025-1"
    assert bundle["parse"]["annexes_present"] is True
    assert bundle["version"]["status"] == "REQUIRES_MANUAL_REVIEW"
    assert bundle["version"]["effective_from"] is None

    pkt = json.loads((out / "packet.json").read_text(encoding="utf-8"))
    assert [l["link"] for l in pkt["chain_evidence"]] == [
        "inventory", "geometry", "authority", "discovery", "fetch",
        "parse", "version", "change_detection", "publication",
    ]
    md = (out / "packet.md").read_text(encoding="utf-8")
    assert "pn-picos-de-europa" in md


def test_replay_is_byte_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    kw = dict(
        fixtures_dir=FIXTURES, clock=lambda: "2026-09-13T00:00:00Z"
    )
    run_pilot("bocyl", "pn-picos-de-europa", out_dir=a, **kw)
    run_pilot("bocyl", "pn-picos-de-europa", out_dir=b, **kw)
    for name in ("bundle.json", "packet.json", "packet.md"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_cite_mismatch_fails_explicit(tmp_path):
    """If discovery returns no ref matching the authority cite, the run
    fails — it never silently fetches the wrong document."""
    fixtures = tmp_path / "fx"
    fixtures.mkdir()
    for f in FIXTURES.iterdir():
        (fixtures / f.name).write_bytes(f.read_bytes())
    payload = json.loads((fixtures / "discovery.json").read_text("utf-8"))
    payload["results"][0]["titulo"] = "DECRETO 99/2099 de otra cosa"
    (fixtures / "discovery.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    with pytest.raises(RunError, match="cite"):
        run_pilot(
            "bocyl",
            "pn-picos-de-europa",
            out_dir=tmp_path / "o",
            fixtures_dir=fixtures,
            clock=lambda: "2026-09-13T00:00:00Z",
        )


def test_no_network_and_no_jurisdiction_branches():
    src = inspect.getsource(run_mod)
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
    # urllib may only be reached through providers.fetch.urllib_transport.
    assert "urllib" not in imported
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
