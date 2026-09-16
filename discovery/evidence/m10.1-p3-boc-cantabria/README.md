# M10.1 P3 — BOC Cantabria (ES-CB) × pn-picos-de-europa

Pilot evidence packet: `Decreto 57/2026` (PRUG Picos de Europa, tramo
Cantabria). The chain is POST→TOC→`verXmlAction`: the form POST to
`boletines.do` returns the TOC (bulletin date, per-announcement
`idAnuBlob` links carrying the `BOC-YYYY-NNNN` print id, and the daily
`idBlob`), which the fetch recipe re-issues to resolve the full-text XML.

## Chain

| link | state | detail |
|------|-------|--------|
| inventory | PASS | `pilot-spaces.json` authority ES-CB/boc-cantabria |
| geometry | PASS | OAPN layer digest `dcf2fc4a…` (digest-only) |
| authority | PASS | cite `Decreto 57/2026`, `doc_key=BOC-2026-6207`, `bulletin_date=04/08/2026` |
| discovery | PASS | `boc_toc_post` → 22 refs; target `BOC-2026-6207` (`idAnuBlob=438988`) |
| fetch | PASS | `post_then_get` POST→TOC→GET `verXmlAction.do?idBlob=46085` |
| parse | PASS | `boc_daily_xml` — `<disposicion>` matched by `numeroExp`, `anexos="1"` |
| version | PASS | `REQUIRES_MANUAL_REVIEW`, `effective_from=None` |
| change_detection | PASS | profile-declared `daily_xml_diff` |
| publication | PASS | `publication_readiness=NO` — zero rules published |

## Evidence

- `fetched_from`: `https://boc.cantabria.es/boces/verXmlAction.do?idBlob=46085`
- `evidence_sha256`: `656bf9535b77359788f92a6a7295f04f1b6d7330ee8d94dbde1699bb9b033150`
- TOC bytes: `fixtures/toc-post.html` = G0 `boc-cantabria-toc-20260804-post.html`
- XML bytes: `fixtures/document.bin` = G0 `boc-cantabria-2026-08-04.xml`

## Reachability

- `runner_network`: `fixture` (replay) / `es_local` (live 2026-09-16)
- `reachability_observed`: `REACHABLE`
- `fetch_outcome`: `SUCCESS`
- Profile expectation `foreign_ci=ES_ONLY_SUSPECTED` (G0: foreign fetchers
  timed out — UNREACHABLE+TIMEOUT is recorded, never source absence)
- LIVE_VERIFY 2026-09-16: WFS 200, discovery POST refs=22, document
  200/149942B — byte-identical to the G0 capture
