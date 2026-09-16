# M10.1 P2 — BOA (ES-AR) × pn-ordesa-y-monte-perdido

Pilot evidence packet: `Decreto 16/2022` (PRUG Ordesa y Monte Perdido).
Stable key is the preregistered `DOCN=007922169`; the VERDOC CGI page is
both the discovery response and the fetched document.

## Chain

| link | state | detail |
|------|-------|--------|
| inventory | PASS | `pilot-spaces.json` authority ES-AR/boa |
| geometry | PASS | OAPN layer digest `dcf2fc4a…` (digest-only) |
| authority | PASS | cite `Decreto 16/2022`, `doc_key=007922169` |
| discovery | PASS | `boa_cgi` docn_lookup → `007922169` |
| fetch | PASS | `cgi` GET VERDOC (ISO-8859-1 page) |
| parse | PASS | `boa_html` — 4 headings, 9 citations |
| version | PASS | `REQUIRES_MANUAL_REVIEW`, `effective_from=None` |
| change_detection | PASS | profile-declared `boa_polling` |
| publication | PASS | `publication_readiness=NO` — zero rules published |

## Evidence

- `fetched_from`: `https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI?...DOCN=007922169...`
- `evidence_sha256`: `3c560f0a44447d7d3f8054855efd9e680fad6c5354bed7f7bc0e8b7a35a16ef1`
- bytes: `fixtures/document.bin` = G0 `boa-decreto-16-2022-doc.html`

## Reachability

- `runner_network`: `fixture` (replay) / `es_local` (live 2026-09-16)
- `reachability_observed`: `REACHABLE`
- `fetch_outcome`: `SUCCESS`
- LIVE_VERIFY 2026-09-16: WFS 200, discovery refs=1, document 200/25274B
