# M10.2-B Refresh Core — canned transition evidence

Each `<scenario>/` contains `scenario.json` (declared observation
sequence + expected outcome), the body fixtures it references, and the
generated `run-log.json` + `packets/`. All replay is offline.

## Reproduce

```bash
# single scenario
python tooling/m102_refresh_run.py replay \
  --scenario discovery/evidence/m10.2-refresh/<scenario>

# executable gate: replay all scenarios, assert expected states
python tooling/m102_refresh_run.py gate \
  --evidence-root discovery/evidence/m10.2-refresh
```

## Scenario → transition coverage (spec §G)

| Scenario | Demonstrates |
|---|---|
| `baseline-then-same` | FIRST_OBSERVATION→BASELINE_CREATED, SAME — no packet |
| `transport-only` | CHANGED_TRANSPORT_ONLY — canonical same, etag changed |
| `changed-content` | CHANGED_CONTENT → deterministic alert packet |
| `unreachable-degraded` | UNREACHABLE×2 → ACCESS_DEGRADED at degraded_threshold |
| `absence-404` | reachable 404/410 → DISAPPEARED_SUSPECTED at absence_threshold |
| `invalid-persistent` | CONTENT_MARKER_MISMATCH×3 → INVALID alert |
| `canonicalizer-bump` | canonicalizer v1→v2 → REBASELINE_REQUIRED |
| `runner-isolation` | foreign_ci failures never contaminate es_local counters |

Evidence-only: `NEW_RULES=0`, packets carry `publication_readiness=NO`,
prior snapshots are append-only and never deleted.
