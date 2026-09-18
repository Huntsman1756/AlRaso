# es-pn — Expansión de cobertura a parques nacionales españoles (post-M10.3)

Fecha: 2026-09-18. Programa de evidencia — **ninguna regla publicable**:
todos los paquetes son candidatos `REVIEW_REQUIRED` pendientes de
adjudicación humana junto con los casos M8/M10.3.

## Estado del inventario (16 PN)

Ver `discovery/evidence/es-pn-coverage/pn-coverage-matrix.json` —
construida sobre la capa oficial OAPN WFS `view_red_oapn_limite_pn`
(17 features, sha256 `2d94b12e…`, digest-only por licencia no verificada).

| Parque | CCAA | Estado | Paquete |
|---|---|---|---|
| Ordesa y Monte Perdido | AR | BASELINE | corpus histórico |
| Picos de Europa | AS/CL/CB | BASELINE | corpus histórico |
| Teide | CN | EVIDENCE_PACKAGE | m10.3-teide |
| Sierra Nevada | AN | EVIDENCE_PACKAGE | m10.3-sierra-nevada |
| Aigüestortes | CT | EVIDENCE_PACKAGE | m10.3-aiguestortes |
| Guadarrama | MD/CL | EVIDENCE_PACKAGE | m8-guadarrama |
| **Doñana** | AN | **EVIDENCE_PACKAGE (este lote)** | es-pn-donana |
| **Sierra de las Nieves** | AN | **EVIDENCE_PACKAGE (este lote)** | es-pn-sierra-nieves |
| Monfragüe | EX | PENDING | siguiente lote (DOE) |
| Cabañeros | CM | PENDING | DOCM |
| Tablas de Daimiel | CM | PENDING | DOCM |
| Garajonay | CN | PENDING | BOC (canal probado en Teide) |
| Caldera de Taburiente | CN | PENDING | BOC |
| Timanfaya | CN | PENDING | BOC |
| Islas Atlánticas | GA | PENDING | DOG |
| Cabrera | IB | PENDING | BOIB |

## Este lote (ES-AN, canal BOJA ya probado en Sierra Nevada)

### Doñana — `RC-ESPN-ES-AN-DONANA-VIVAC`

Hallazgo jurídico distinto al resto: **prohibición legal directa**.
Ley 8/1999 art. 44.c) (verbatim verificado en BOE): *"La acampada y
pernocta al aire libre, excepto las autorizadas para eventos
científicos, divulgativos o culturales"* = infracción en todo el Espacio
Natural (que integra el PN). STC 331/2005 solo anuló art. 16.7.
Candidatos: `VIVAC_AL_RASO → PROHIBITED`; `ACAMPADA + evento
científico/divulgativo/cultural → AUTHORIZATION_REQUIRED`;
`ACAMPADA vacacional/ocio → PROHIBITED` (Decreto 26/2018 art. 1.5).
Inferencia para el revisor: "vivac" ⊂ "pernocta al aire libre".
Pendientes: Anexo II del PSUP 2024 (condiciones operativas de la
acampada), texto íntegro de epígrafes PORN/PRUG 142/2016, geometría del
Espacio Natural completo.

### Sierra de las Nieves — `RC-ESPN-ES-AN-SIERRA-NIEVES-VIVAC`

Régimen transitorio: **no existe PRUG del PN** (DA 2ª de la Ley 9/2021
vencida 03/07/2024; solo formulación aprobada 21/05/2025). Vigente vía
DT única: Decreto 162/2018 (PORN ámbito + PRUG Parque Natural, PDF BOJA
verificado sha256 `aca31c83…`). Candidatos: `VIVAC_AL_RASO → PERMITTED
condicionado` (comunicación previa + umbrales ≤15 pax/≤3 tiendas +
distancias 2 km + 1 noche + ventana anochecer–amanecer);
`AUTHORIZATION_REQUIRED >15/>3`; `ACAMPADA fuera de lugares/condiciones
→ PROHIBITED` (Ley 9/2021 art. 13.4.a, base legal directa en el PN).
Sin laguna de umbral (excepción por exclusión, a diferencia de Sierra
Nevada). Inferencia central: aplicación de los instrumentos del PNat
dentro del PN vía DT única.

## Tests

`tests/test_es_pn_candidates.py` — 9 tests replicando el contrato de
seguridad M10.3: ningún candidato publicable, resolver UNDETERMINED/
INCLUSIVE con hechos que satisfacen las condiciones propuestas, ni
PERMITTED ni PROHIBITED se filtran de candidatos sin revisar, extracts
con sha256 verificado en disco. Suite completa: 1183 passed, 8 skipped.

## Siguientes lotes (orden sugerido por canal probado)

1. **ES-CN (BOC)** — Garajonay, Caldera de Taburiente, Timanfaya
   (canal BOC probado en Teide: Decreto 182/2025 patrón similar).
2. **ES-GA (DOG)** — Islas Atlánticas.
3. **ES-EX (DOE)** — Monfragüe.
4. **ES-CM (DOCM)** — Cabañeros, Tablas de Daimiel.
5. **ES-IB (BOIB)** — Cabrera.

Por lote: verificar ley de declaración en BOE + instrumento de
pernocta (PORN/PRUG) verbatim + geometría OAPN (digest) + paquete
`REVIEW_REQUIRED` + tests. Geometría real: solo si se verifica licencia
de reutilización (IDEM en Madrid era CC-BY; OAPN `not_verified`).
