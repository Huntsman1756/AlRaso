# es-pn — Sierra de las Nieves (ES-AN / BOJA + BOE)

Evidence package for the post-M10.3 national-park coverage program
(`es-pn-coverage`) on `pn-sierra-de-las-nieves`. Candidate rules for
`VIVAC_AL_RASO` / `ACAMPADA` — all `REVIEW_REQUIRED`, non-publishable
pending human review.

## Governing instruments

- **Ley 9/2021, de 1 de julio** (declaración, BOE-A-2021-10958) —
  **no contiene régimen sustantivo de vivac/pernocta**: "acampada" aparece
  una sola vez, en el tipo sancionador **art. 13.4.a)** (verbatim):
  *"La acampada en lugares distintos a los previstos o en condiciones
  diferentes a las establecidas"* = infracción leve dentro del PN.
  - **DT única**: mientras no se apruebe el PRUG del PN, siguen vigentes
    los instrumentos de los ENP preexistentes "en todo aquello que no se
    oponga a la ley".
  - **DA 2ª**: plazo de 3 años para el PRUG del PN — **vencido 03/07/2024**.
- **Decreto 162/2018, de 4 de septiembre** (BOJA núm. 184, CVE 00142234,
  PDF sha256 `aca31c83…`) — aprueba el PORN del ámbito (Anexo I) y el PRUG
  del Parque Natural (Anexo II); **vigente** (art. 2.2: vigencia
  indefinida) y, vía DT única, instrumento de gestión actual en el
  territorio del PN:
  - PORN **9.4.3.3.d)** (verbatim): vivaqueo/acampada nocturna de travesía
    → **régimen de comunicación** (por exclusión del 5.d).
  - PORN **9.4.3.5.d)** (verbatim): grupos >15 pax o >3 tiendas →
    **autorización**.
  - PRUG **5.2.5.4** (verbatim): condiciones — ≥2 km de núcleo urbano/
    alojamiento turístico/refugio (salvo refugio completo); máx. 1 noche
    por lugar; instalaciones solo 1h antes anochecer–1h después amanecer;
    residuos.
- **Decreto 15/2011** (BOJA núm. 30) — régimen general de usos en parques
  naturales: definiciones de "vivaquear"/"acampada nocturna" (art. 3.j/e)
  y mismo régimen de comunicación (art. 9.1.c). Ámbito "parques
  naturales" — aplicación dentro del PN pendiente de adjudicación.
- **Decreto 106/2024** — declara el Espacio Natural unitario
  (PN + ZPP + PNat) y crea órganos de gestión.
- **Acuerdo 21/05/2025** (BOJA 98) — aprobada solo la **formulación** del
  PRUG del Espacio Natural; **no vigente**.

## Key finding

Sin PRUG del PN: el régimen aplicable hoy es el del **Parque Natural
preexistente** (Decreto 162/2018) vía disposición transitoria. La
**inferencia central para el revisor** es si esos instrumentos rigen
dentro del PN "en lo que no se oponga a la ley". A diferencia de Sierra
Nevada, aquí **no hay laguna de umbral**: el 9.4.3.3.d se define por
exclusión, así que 15 pax / 3 tiendas exactos quedan en comunicación.

## Fetches (2026-09-18)

- BOE txt `BOE-A-2021-10958` — 200; art. 13.4 + DA 2ª + DT única verbatim
  en `boe-ley9-2021-art13-extract.txt` (sha256 `0426c3e9…`).
- BOJA `…/boja/2011/30/3` — 200; art. 3.e/j + 9.1.c verbatim en
  `boja-15-2011-art9-extract.txt` (sha256 `fcb86c19…`).
- BOJA PDF `BOJA18-184-00384-14951-01_00142234.pdf` — 15.259.272 B,
  sha256 `aca31c83…` (no redistribuido); PORN 9.4.3.3.d/5.d + PRUG
  5.2.5.4 verbatim en `boja-162-2018-vivaqueo-extract.txt`
  (sha256 `4bfffcbb…`).
- OAPN WFS — feature "Parque Nacional de la Sierra de las Nieves"
  (digest-only).

## Geometry

OAPN límites PN — feature `Parque Nacional de la Sierra de las Nieves`
(digest-only). Geometría del PNat y del Espacio Natural completo
pendientes (DERA) → `SPATIAL_REVIEW_PENDING_GEOMETRY`.

## Status

`READY_FOR_HUMAN_REVIEW` — `review_case.json`
(`RC-ESPN-ES-AN-SIERRA-NIEVES-VIVAC`) pendiente de adjudicación junto
con los casos M8/M10.3.
