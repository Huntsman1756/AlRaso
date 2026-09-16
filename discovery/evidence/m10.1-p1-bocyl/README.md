# M10.1 P1 — BOCyL (ES-CL) × pn-picos-de-europa

Pilot evidence packet: `Decreto 17/2025` (PRUG Picos de Europa, tramo
Castilla y León). Reproducible offline from `fixtures/`; live-verify
observational.

## Chain

| link | state | detail |
|------|-------|--------|
| inventory | PASS | `pilot-spaces.json` authority ES-CL/bocyl |
| geometry | PASS | OAPN layer digest `dcf2fc4a…` (digest-only, no redistribution) |
| authority | PASS | cite `Decreto 17/2025` |
| discovery | PASS | `bocyl_opendatasoft` dataset query → `BOCYL-D-15122025-1` |
| fetch | PASS | `get_simple` GET per-doc XML URL |
| parse | PASS | `bocyl_xml` — 3 headings, 6 citations, annexes=True (PRUG is PDF-only) |
| version | PASS | `REQUIRES_MANUAL_REVIEW`, `effective_from=None` |
| change_detection | PASS | profile-declared `opendatasoft_dataset_daily` |
| publication | PASS | `publication_readiness=NO` — zero rules published |

## Evidence

- `fetched_from`: `https://bocyl.jcyl.es/boletines/2025/12/15/xml/BOCYL-D-15122025-1.xml`
- `evidence_sha256`: `f3837c8f0e1ddb350cc14c8b11f94be91ad07f867ffc4152d91e8a7058a3d65e`
- bytes: `fixtures/document.bin` = G0 `bocyl-17-2025-head.xml`

## Reachability

- `runner_network`: `fixture` (replay) / `es_local` (live 2026-09-16)
- `reachability_observed`: `REACHABLE`
- `fetch_outcome`: `SUCCESS`
- LIVE_VERIFY 2026-09-16: WFS 200, discovery refs=3, document 200/15473B
