# M10.1 P4 — DOGC (ES-CT) × pn-aiguestortes-i-estany-de-sant-maurici

Pilot evidence packet: `Decreto 39/2003` (PRUG Aigüestortes i Estany de
Sant Maurici). Discovery queries the Socrata dataset
(`analisi.transparenciacatalunya.cat/resource/n6hn-rmy7`); the record's
own `url_format_xml` ELI link is the fetch target and renders Akoma Ntoso.

## Chain

| link | state | detail |
|------|-------|--------|
| inventory | PASS | `pilot-spaces.json` authority ES-CT/dogc |
| geometry | PASS | OAPN layer digest `dcf2fc4a…` (digest-only) |
| authority | PASS | cite `Decreto 39/2003`, `doc_key=es-ct/d/2003/02/04/39` |
| discovery | PASS | `dogc_socrata` → 3 records; doc id from record's own ELI |
| fetch | PASS | `get_simple` GET ELI `/xml` → Akoma Ntoso |
| parse | PASS | `akn` — 47 headings, 9 citations, Annex 1–3; FRBRthis binds the ELI |
| version | PASS | `REQUIRES_MANUAL_REVIEW`, `effective_from=None` |
| change_detection | PASS | profile-declared `socrata_dataset_vigencia` |
| publication | PASS | `publication_readiness=NO` — zero rules published |

## Evidence

- `fetched_from`: `https://portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39/dof/cat/xml`
- `evidence_sha256`: `96f9a5452c956337b45284a705de90858173acef43d3a33b2fd8454c7e517792`
- `fixtures/discovery.json` = verbatim live Socrata capture (2026-09-16)
- bytes: `fixtures/document.bin` = G0 `dogc-39-2003-akn.xml`

## Reachability

- `runner_network`: `fixture` (replay) / `es_local` (live 2026-09-16)
- `reachability_observed`: `REACHABLE`
- `fetch_outcome`: `SUCCESS`
- LIVE_VERIFY 2026-09-16: WFS 200, discovery refs=3, document
  200/114653B — byte-identical to the G0 capture
- Transport note: `portaljuridic.gencat.cat` presents legacy TLS ciphers;
  the read-only live transport runs `SECLEVEL=1` (no credentials sent).
