"""M10.2-B shipped evidence — the committed scenario set must satisfy
the executable refresh gate (hermetic: replays into a temp store, no
network, no reliance on generated run-log.json files)."""

from __future__ import annotations

from pathlib import Path

from tooling.m102_refresh_run import _run_scenario
from pipeline.refresh.snapshots import SnapshotStore

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "discovery" / "evidence" / "m10.2-refresh"

import json
import tempfile


def test_scenario_coverage_complete():
    """Every spec §G transition must have a committed scenario."""
    names = {p.name for p in EVIDENCE.iterdir() if p.is_dir()}
    required = {
        "baseline-then-same",      # FIRST_OBSERVATION + SAME
        "transport-only",          # CHANGED_TRANSPORT_ONLY
        "changed-content",         # CHANGED_CONTENT + packet
        "unreachable-degraded",    # UNREACHABLE -> ACCESS_DEGRADED
        "absence-404",             # absence -> DISAPPEARED_SUSPECTED
        "invalid-persistent",      # INVALID >= threshold -> alert
        "canonicalizer-bump",      # REBASELINE_REQUIRED
        "runner-isolation",        # counters per runner_network
    }
    assert required <= names, required - names


def test_shipped_scenarios_gate(tmp_path):
    failures = []
    for scenario_dir in sorted(p for p in EVIDENCE.iterdir() if p.is_dir()):
        spec_path = scenario_dir / "scenario.json"
        if not spec_path.is_file():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        expect = spec.get("expect", {})
        log = _run_scenario(scenario_dir, SnapshotStore(tmp_path))
        if expect.get("final_states") is not None and (
            log["final_states"] != expect["final_states"]
        ):
            failures.append(
                (scenario_dir.name, log["final_states"],
                 expect["final_states"])
            )
        if expect.get("packets") is not None and (
            log["packets_emitted"] != expect["packets"]
        ):
            failures.append(
                (scenario_dir.name, log["packets_emitted"],
                 expect["packets"])
            )
    assert not failures, failures


def test_packets_deterministic_bytes(tmp_path):
    """Replay changed-content twice: packet JSON must be byte-identical."""
    scenario_dir = EVIDENCE / "changed-content"
    log1 = _run_scenario(scenario_dir, SnapshotStore(tmp_path / "a"))
    pkt1 = (scenario_dir / "packets" /
            "packet-0-changed_content.json").read_bytes()
    log2 = _run_scenario(scenario_dir, SnapshotStore(tmp_path / "b"))
    pkt2 = (scenario_dir / "packets" /
            "packet-0-changed_content.json").read_bytes()
    assert pkt1 == pkt2
    assert b'"publication_readiness": "NO"' in pkt1
