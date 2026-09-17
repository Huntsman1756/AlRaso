# M10.3 — Teide (ES-CN / BOC Canarias)

Evidence package for the M10.3 legal-scaling case on `pn-teide`.

## Governing instrument

`Decreto 182/2025, de 1 de diciembre, por el que se aprueba el Plan Rector
de Uso y Gestión del Parque Nacional del Teide` — BOC núm. 240,
03/12/2025, anuncio 4148, stable id `BOC-A-2025-240-4148`.

- Doc page: `https://www.gobiernodecanarias.org/boc/2025/240/pda/4148.html`
  (byte-identical to the M10.1-P5 fixture; sha256 `d49782a4…`).
- Signed PDF: `https://sede.gobiernodecanarias.org/boc/boc-a-2025-240-4148.pdf`
  (58.332.199 B, sha256 `45df0cd3…` — identical to the G0-recorded digest;
  bytes NOT committed).
- `boc-182-2025-prug-extract.txt`: clean UTF-8 verbatim text-layer extract
  (2026-09-17, `pdftotext -enc UTF-8`) covering the dispositive part
  (Primero–Cuarto), §6.2.1 incompatibles list (incl. `l. La acampada`,
  `m. La pernoctación en vehículos`, `ff.` reserve-zone access ban),
  §5 zoning access regimes, §6.3.2.7 VIVAC (full), §8.2 vigencia.
  It supersedes `spain-coverage-g0/boc-182-2025-vivac-extract.txt` for
  citation purposes — the G0 extract carries irreversible U+FFFD mojibake
  and covers only §6.3.2.6–6.3.2.8.

## Validity

- Vacatio (verbatim, dispositivo Cuarto): "El Plan Rector de Uso y Gestión
  del Parque Nacional del Teide entrará en vigor a los 15 días de su
  publicación en el Boletín Oficial de Canarias." Published 2025-12-03 →
  derived effective_from **2025-12-18** (manual derivation from the
  verbatim clause; the version pipeline deliberately leaves free-text
  vacatio `effective_from=null` → flagged for the human reviewer).
- §8.2: PRUG vigencia 10 años + automatic prórroga until replaced.
- No consolidated corpus or machine-readable amendment signal exists for
  BOC Canarias (`version_signal: none_verified` in atlas domain ES-CN).

## Geometry

OAPN `view_zon_zonificacion_prug` — 49 Teide zone features, each citing
`Normativa: Decreto 182/2025`. Digest-only provenance
(`oapn-zonificacion-prug.digest.json`); the four named vivac areas are
administratively deferred ("la administración gestora delimitará las
zonas concretas") → zone polygons are NOT mechanically provable from the
instrument. Affected cases fail closed.

## Status

`READY_FOR_HUMAN_REVIEW` — candidate corpus + ReviewCase pending owner
decision in `docs/validation/m10.3/M10.3-HUMAN-REVIEW.md`.
