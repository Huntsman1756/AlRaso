# M10.3 — Aigüestortes i Estany de Sant Maurici (ES-CT / DOGC)

Evidence package for the M10.3 legal-scaling case on
`pn-aiguestortes-i-estany-de-sant-maurici`. Strongest prior coverage in the
repo: full M10.1 P4 chain (discovery→fetch→parse) + M10.2-C version signal
+ OAPN zoning digest.

## Governing instrument

- `Decret 39/2003, de 4 de febrer` — approves the **PRUG** (Pla rector d'ús
  i gestió) of the Parc Nacional. DOGC núm. 3825, 19/02/2003.
- ELI doc key `es-ct/d/2003/02/04/39`; canonical:
  `https://portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39`
- AKN capture sha256
  `96f9a5452c956337b45284a705de90858173acef43d3a33b2fd8454c7e517792`
  (byte-identical M10.1 fetch and G0 capture; bytes not redistributed —
  see `fixtures/document.bin` in `m10.1-p4-dogc/`).

## Overnight-activity provision

- **PRUG art. 25.4** (verbatim in `dogc-39-2003-art25-extract.txt`):
  prohibits overnight stays outside the Annex 2 refuges AND camping AND
  **bivac** throughout the national park and peripheral protection zone,
  including parking and special-use areas, except the enabled zones of
  Estallos and Riumalo (ZPP) and holders of special stay permits for
  research/management/control.
- **Annex 2** lists 17 refuge/huts inside the PN and 15 in the ZPP;
  `(*)` = public overnight use.

## Validity

- DOGC consolidated (M10.2-C): `vigència=Vigent`, `idVersion=318062`,
  `effective_from=None` — the decree carries **no express entry-into-force
  clause**; only a derogation clause (repeals Decret 82/1993).
- **PRUG art. 6 (verbatim in extract):** "El Pla rector d'ús i gestió té
  una vigència de sis anys. A partir del cinquè any s'iniciarà el procés
  per a la seva revisió." — nominal validity exhausted ~2009; MITECO
  describes the plan as "prorrogado" but **no extension instrument has
  been located**. Open validity question for the human reviewer (same
  pattern as Teide's expired-but-continued 2002 PRUG).
- Art. 22.3.d: exceptional camping permits for research stays
  (alternative channel to the 25.4 permit exemption).
- Provisional `effective_from=2003-02-20` (day-after-publication default)
  is a modelling placeholder for the candidate, flagged for the reviewer.

## Geometry

- OAPN PRUG-zoning digest: 27 features, `Normativa` cites Decreto 39/2003
  uniformly. Actual classes: **1 Uso Restringido envelope ~park-wide
  (13.559,8 ha ≈96%) + 19 Uso Moderado + 5 Uso Especial + 2 Reserva**
  (Bony del Graller 283,6 ha; Estany de Trescuro 29,4 ha). No ZPP
  polygons exist in this layer.
- PN boundary digest `709079ce6b…06c9` (`oapn-limites-pn.digest.json`).
- Digest-only (CONTEXT_ONLY per `pipeline/providers/geometry.py`): cannot
  place a point inside/outside the PN or the ZPP enclaves. Art. 25.4 is a
  park-wide prohibition, so the *proposed* outcome does not depend on
  zone geometry — but the PN/ZPP boundary and Estallos/Riumalo locations
  remain unverifiable from digests.

## Files

- `dogc-39-2003-art25-extract.txt` — verbatim art. 6 (vigència) + art.
  22.3(d) + art. 25.1–25.8 íntegro + normalized Annex 2 refuge list.
  sha256 `2dd2b364bf3d4de44f9923967727c1d166ca040dac9c33d9a498dd06af585061`
- `candidate_fixture.json` — fixture-shaped candidate corpus
  (all `REVIEW_REQUIRED`, non-publishable by construction).
- `review_case.json` — human-adjudication case (mandate §9 fields).

## Status

`READY_FOR_HUMAN_REVIEW` — automated evidence complete; no human legal
review claimed. Proposed effect: `PROHIBITED` (VIVAC_AL_RASO, PN scope).
