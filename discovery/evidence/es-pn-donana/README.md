# es-pn — Doñana (ES-AN / BOJA + BOE)

Evidence package for the post-M10.3 national-park coverage program
(`es-pn-coverage`) on `pn-donana`. Candidate rules for `VIVAC_AL_RASO` /
`ACAMPADA` — all `REVIEW_REQUIRED`, non-publishable pending human review.

## Governing instruments

- **Ley 8/1999, de 27 de octubre, del Espacio Natural de Doñana**
  (BOJA núm. 137; BOE-A-1999-23524) — ley marco autonómica del Espacio
  Natural (figura integradora del PN + PNat + zonas). **Art. 44.c)**
  (verbatim in extract): *"La acampada y pernocta al aire libre, excepto
  las autorizadas para eventos científicos, divulgativos o culturales"*
  = infracción administrativa en todo el territorio del Espacio Natural.
  STC 331/2005 declared only art. 16.7 unconstitutional — art. 44 intact.
- **Decreto 2412/1969** (creación, BOE-A-1969-1252) y **Ley 91/1978**
  (reclasificación, BOE-A-1979-932) — instrumentos estatales del PN.
- **Decreto 142/2016, de 2 de agosto** (BOJA núm. 185) — amplía el PNat,
  declara la ZEC Doñana Norte y Oeste y aprueba PORN+PRUG únicos del
  Espacio Natural. **Anulaciones parciales**: STSJ Andalucía 21/11/2018
  anuló epígrafes 8.4.4.1.b), 8.4.4.2, 8.4.4.3, 8.4.4.6.a)-b), 8.4.4.9,
  8.4.4.10.a).3 y 8.6.2.1.2.n) del PORN + 6.2.1.p)/6.2.2.h) del PRUG —
  ninguno identificado como precepto de acampada/pernocta (verificado vía
  referencias oficiales; texto íntegro de anexos no recorrido — flag).
- **Orden de 28/06/2024** (BOJA 152) — Programa Sectorial de Uso Público;
  su Anexo II ordena operativamente la acampada autorizable (**no
  extraído verbatim — lectura pendiente del revisor**).
- **Decreto 26/2018** art. 1.5 (verbatim): prohibición general de
  acampada/pernocta "con fines vacacionales o de ocio" fuera de
  campamentos de turismo (ámbito autonómico general).
- Borrador de modificación del PORN/PRUG (sep 2025, información pública)
  — **NO vigente**.

## Key finding (diferente de Sierra Nevada)

Doñana tiene una **prohibición legal directa**, no un régimen de
comunicación: la pernocta al aire libre es infracción salvo autorización
para eventos científicos/divulgativos/culturales. El término "vivac" no
aparece en la ley — la subsunción de `VIVAC_AL_RASO` en "pernocta al aire
libre" es la **inferencia central que debe adjudicar el revisor**.

## Fetches (2026-09-18)

- BOE txt `BOE-A-1999-23524` — 200; art. 44.b)-e) verbatim en
  `boe-ley8-1999-art44-extract.txt` (sha256 `b0338f25…`).
- BOJA `…/boja/2018/27/1` — 200; art. 1.4-1.5 verbatim en
  `boja-26-2018-art1-extract.txt` (sha256 `e47f50e0…`).
- OAPN WFS `view_red_oapn_limite_pn` — 17 features; feature "Parque
  Nacional de Doñana" digest-only (licencia no verificada).

## Geometry

OAPN límites PN — feature `Parque Nacional de Doñana` (digest-only).
**Caveat**: el Espacio Natural integra PN+PNat+zonas; el layer solo
aporta el límite del PN. Geometría completa pendiente (DERA Junta de
Andalucía) → `SPATIAL_REVIEW_PENDING_GEOMETRY`.

## Status

`READY_FOR_HUMAN_REVIEW` — `review_case.json`
(`RC-ESPN-ES-AN-DONANA-VIVAC`) pendiente de adjudicación junto con los
casos M8/M10.3.
