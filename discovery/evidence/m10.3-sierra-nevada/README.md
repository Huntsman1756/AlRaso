# M10.3 — Sierra Nevada (ES-AN / BOJA)

Evidence package for the M10.3 legal-scaling case on `pn-sierra-nevada`.

## Governing instruments

- PORN §5.5.1.1 (verbatim in extract): access to **Zonas de Reserva** of
  the national park is limited to park staff, authorized research and
  security forces — no public access; §5.5.1.2 limits pedestrian
  circulation in **Zona de Uso Restringido** to existing
  roads/tracks/paths (+ >2.000 m traditional routes, winter ski touring).
- `Decreto 238/2011, de 12 de julio, por el que se establece la ordenación
  y gestión de Sierra Nevada` — BOJA núm. 155, 09/08/2011, doc
  `/boja/2011/155/3`, PDF `d3.pdf`. Approves PORN (Anexo I, whole Espacio
  Natural incl. the national park), PRUG Parque Nacional (Anexo II), PRUG
  Parque Natural (Anexo III), PNat boundary description (Anexo IV).
- `Ley 3/1999, de 11 de enero` (declaration law) — BOE-A-1999-782;
  consolidated metadatos RESOLVED via `tooling/m102_version_probe.py`
  (effective_from 1999-01-14, consolidación Finalizado) — see
  `discovery/evidence/m10.3-version/boe/BOE-A-1999-782/`.

## Fetches (2026-09-17, es_local)

- Issue index `…/boja/2011/155/index.html` — 200; the decree is doc 3.
- HTML doc page `…/boja/2011/155/3` — TIMEOUT ×2 (0 bytes); unusable today.
- PDF `…/boja/2011/155/d3.pdf` — 200, 44.474.989 B, sha256 `bc8b8ca1…`
  (bytes NOT committed; verbatim UTF-8 extract committed as
  `boja-238-2011-extract.txt`).

## Validity

- Disposición final segunda (verbatim): "El presente Decreto entrará en
  vigor el día siguiente al de su publicación en el Boletín Oficial de la
  Junta de Andalucía." Published 2011-08-09 → effective_from
  **2011-08-10** (matches the sedeboja consolidated version date
  "10/08/2011 - INICIAL" — the only consolidated version listed).
- Art. 2: PRUG vigencia 8 años prorrogable ≤8, AND "el régimen de usos y
  actividades previsto en el Plan mantendrá su vigencia hasta que sea
  aprobado el nuevo Plan".
- Amendments/successors observed: Resolución 30/05/2022 (BOJA 2022/107/41)
  opened public info for an Orden modifying Anexo II §5.2.3 (competition
  list — Vuelta Ciclista; unrelated to vivac/acampada); Acuerdo de
  12/01/2026 (BOJA núm. 13) approves the FORMULATION of the PORN/PRUG
  revision — a revision procedure, not a replacement. Orden 12/12/2011
  (BOJA 2012/6/14) approves authorization/communication models
  (implementing, not modifying).

## Geometry

OAPN `view_zon_zonificacion_prug` — 442 Sierra Nevada zone features citing
`Normativa: Decreto 238/2011`. Digest-only provenance. PORN §5.4.5.4.d
makes the exempted vivac regime conditional on distance (>2 km from urban
nuclei / tourist lodging / non-full refuge) — a spatial fact the digest
cannot resolve; affected cases fail closed.

## Status

`READY_FOR_HUMAN_REVIEW` — candidate corpus + ReviewCase pending owner
decision in `docs/validation/m10.3/M10.3-HUMAN-REVIEW.md`.
