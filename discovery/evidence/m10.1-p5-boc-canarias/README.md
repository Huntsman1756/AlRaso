# M10.1 P5 — BOC Canarias (ES-CN) × pn-teide

Pilot evidence packet: `Decreto 182/2025` (PRUG Teide). The archive is
ID-keyed: the doc page itself publishes the stable `BOC-A-2025-240-4148`
id via its signed-PDF link. The PDF is digest/text-extract evidence
(`pdf_text` route over `pdf-text-extract.txt`) — PDF bytes are not
redistributed.

## Chain

| link | state | detail |
|------|-------|--------|
| inventory | PASS | `pilot-spaces.json` authority ES-CN/boc-canarias |
| geometry | PASS | OAPN layer digest `dcf2fc4a…` (digest-only) |
| authority | PASS | cite `Decreto 182/2025`, `doc_key=BOC-A-2025-240-4148`, `archive_path=2025/240/pda/4148` |
| discovery | PASS | `boc_canarias_doc` → `BOC-A-2025-240-4148` from the signed-PDF link |
| fetch | PASS | `get_simple` GET doc page; marker = signed-PDF link (soft-404 safe) |
| parse | PASS | `boc_canarias_html` — 7 citations, annexes=True (signed-PDF exists) |
| version | PASS | `REQUIRES_MANUAL_REVIEW`, `effective_from=None` |
| change_detection | PASS | profile-declared `stable_id_archive_polling` |
| publication | PASS | `publication_readiness=NO` — zero rules published |

## Evidence

- `fetched_from`: `https://www.gobiernodecanarias.org/boc/2025/240/pda/4148.html`
- `evidence_sha256`: `d49782a4a53c86b159a2808796a4e02035f9184d30225933415e71c90ceb46d6`
- bytes: `fixtures/document.bin` = G0 `boc-canarias-182-2025.html`
- PDF text layer: `fixtures/pdf-text-extract.txt` = G0 `boc-182-2025-vivac-extract.txt`

## Reachability

- `runner_network`: `fixture` (replay) / `es_local` (live 2026-09-16)
- `reachability_observed`: `REACHABLE`
- `fetch_outcome`: `SUCCESS`
- Soft-404 guard: guessed doc URLs may return HTTP 200 with empty/error
  content — `content_marker` is the signed-PDF link; tests assert a
  markerless 200 never reaches `SUCCESS`.
- LIVE_VERIFY 2026-09-16: WFS 200, discovery refs=1, document
  200/14939B — byte-identical to the G0 capture
