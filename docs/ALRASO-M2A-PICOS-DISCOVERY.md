# ALRASO — M2-A Discovery: Picos de Europa multi-jurisdicción

Estado del documento: **Fase A (discovery) completada**. Ninguna regla de Picos entra en runtime en este commit.
Baseline: `main` = `7650dace51f6c8c17fc43fcfb979ec5d0e57f43e`.

## 1. Hallazgo central

El PRUG del Parque Nacional de los Picos de Europa (aprobado 2025-2026) **no es una norma única estatal**:
se aprueba por **tres decretos autonómicos coordinados**, cada uno válido **solo en su ámbito territorial**,
con el mismo cuerpo articulado (arts. 50-54 reproducidos verbatim e idénticos en los tres textos, verificado
por diff de los extracts). La unidad del parque se gestiona por convenio interautonómico y Ley 30/2014.

Consecuencia de diseño: **una consulta de pernocta dentro del PN es irresoluble sin jurisdicción**.
El resolver necesita (a) punto dentro del parque y (b) CCAA de ese punto → norma aplicable = decreto de esa CCAA.

## 2. Matriz jurisdicción × norma × vigencia × geometría

| Ámbito | Norma | Diario oficial | Publicación | Vigencia desde | Geometría verificada | Modelable en Phase B |
|---|---|---|---|---|---|---|
| Principado de Asturias (es-as) | Decreto 21/2026, de 16/03/2026 | BOPA 30/03/2026, Cód. 2026-02506 (cabecera PDF; INAP cita 31/03 — **discrepancia registrada**) | 2026-03-30 | **2026-04-19** (20 días; art. 59.4 PRUG: 3 años) | sí (OAPN + GISCO ES12; Δsuperficie −0.02 %) | **SÍ** |
| Cantabria (es-cb) | Decreto 57/2026, de 30/07/2026 | BOC núm. 148, 04/08/2026 | 2026-08-04 | **2026-08-24** (20 días; art. 59.4: 1 año) | sí (OAPN + GISCO ES13; Δ+0.04 %) | **SÍ** |
| Castilla y León (es-cl) | Decreto 17/2025, de 11/12/2025 | BOCyL núm. 240, 15/12/2025 | 2025-12-15 | **2026-01-04** (20 días; art. 59.4: 1 año) | sí (OAPN + GISCO ES41; Δ−0.01 %) | **SÍ** |
| Estado (estatal) | Ley 16/1995, Ley 30/2014, RD 389/2016 (Plan Director) | BOE | — | vigente | n/a (marco) | **NO** — marco sin regla de uso autónoma verificada; scope `pn-pe-picos` solo como contenedor |
| Estado — PRUG anterior | RD 384/2002 | BOE-A-2002-9576 | 19/04/2002 | **NO PROBADADA** (vigencia 6 años + DF única anulada por STS 27/04/2005; los decretos 2025/2026 **no lo mencionan ni derogan**) | n/a | **NO** — cualquier `as_of` anterior a la fecha efectiva de la CCAA ⇒ `UNDETERMINED` |

Hoy (2026-09-06) los tres decretos están **simultáneamente en vigor**: primera ventana con cobertura completa.

Regla material común (art. 51, verbatim en los tres): vivac/pernocta al raso **solo** vinculada a actividades de
montaña/escalada, **máx. 3 noches**, **siempre > cota 1.800 m** (excepciones: pared; invierno Vega La Sotin);
tiendas solo por meteorología adversa sobre 1.800 m en franja ocaso±1 h. Art. 52: acampada solo en recintos
autorizados; pernocta en vehículo prohibida fuera de núcleos.

## 3. Evidencia (política NOT_VERIFIED — NOTICE §4)

- `tooling/m2a_picos_discovery.evidence.json` — lock con URLs canónicas, identificadores de diario, sha256 de
  PDFs oficiales (NO redistribuidos: 76.5/55.8/38.5 MB), digests de geometría y puntos de sondeo.
- `discovery/evidence/m2a-picos/{cyl-17-2025,as-21-2026,cb-57-2026}-extract.txt` — extracts verbatim
  (ámbito, superficies del preámbulo, disposición de vigencia, derogatoria, arts. 51-52).
- Herramienta de re-verificación: `python tooling/m2a_picos_verify.py` (online; `OFFLINE=1` o sin red ⇒ `INCONCLUSIVE`, exit 2, nunca falso OK).

## 4. Geometría

| Fuente | Rol | Verificación |
|---|---|---|
| OAPN WFS `view_red_oapn_limite_pn` (EPSG:25830) | límite oficial del PN | 3.519 puntos; **66.032,4 ha** vs 66.030 ha preámbulos (Δ **0,004 %**); bbox/properties fijados |
| GISCO NUTS2 01M 2024 (ES12/ES13/ES41) | identificador de jurisdicción punto→CCAA | split parque: ES12 27.483,1 / ES41 23.582,1 / ES13 14.967,2 ha vs 27.477/23.580/14.973 oficiales (**Δ<0,05 %**); residuo dentro del parque fuera de CCAA: **0,00 ha** |

**Precisión**: GISCO 01M ≈ ±1 km en frontera (caso observado: estación superior de Fuente Dé asignada a ES41).
Regla fail-closed: punto a <~1 km de una frontera CCAA ⇒ solo permisible con re-verificación IDE de la CCAA
(Phase B); punto exactamente sobre frontera ⇒ `UNDETERMINED`. Los límites CCAA **no** son límites del parque.

## 5. Casos de diseño Phase B (fixtures propuestas — NO fusionadas)

| Caso | Punto | Esperado |
|---|---|---|
| P1 | Urriellu, asturiano | dentro+ES12 → norma es-as; cota 2.400 m ⇒ efecto por art. 51 (condiciones de hecho: actividad de montaña, noches ≤ 3) |
| P2 | Macizo Oriental interior | dentro+ES13 → norma es-cb |
| P3 | Caín de Valdeón | dentro+ES41 → norma es-cl |
| P4×2 / P5×2 | pares a 300 m y 1 km a cada lado de las 2 fronteras internas dentro del parque | jurisdicciones distintas y mutuamente excluyentes; sin superposición ni vacío |
| P6 | punto ES13, `as_of=2026-08-01` | Cantabria aún sin PRUG vigente ⇒ cobertura incompleta ⇒ `UNDETERMINED` + `INCOMPLETE_JURISDICTION_COVERAGE_NEVER_PERMITS` |
| P7 | Cangas de Onís (fuera del PN) | `NO_APPLICABLE_SCOPE` (nunca `PROHIBITED` sectorial) |
| Extra | frontera exacta GISCO | `UNDETERMINED` (ambigüedad de límite, nunca adivinar) |

Invariantes que heredan de M1.1 y se re-testean: una norma por consulta; ámbito ≠ jurisdicción; sin precedente
asumido (Estado↔CCAA: solo normas autonómicas vigentes sobre PN; conflicto futuro ⇒ `CONFLICTING`+`UNDETERMINED`);
dato geométrico (cota≥1800 m vía DEM oficial — aún no fijado) ≠ hecho jurídico; cobertura incompleta jamás
`PERMITTED`; punto sin jurisdicción jamás jurisdicción inventada; reutilización de datos sin verificación ⇒ solo
extracts + hashes.

## 6. Corpus IDs previstos (no creados en discovery)

`alraso:es-as/pn-picos/pernocta#vivac-cota-1800`, `alraso:es-cb/...`, `alraso:es-cl/...` (una regla por CCAA,
ids propios AlRaso; cero copias de rulespec-es); scopes: `ss-pnpe-limits` (OAPN) + `ss-ccaa-as|cb|cl` (GISCO,
solo como identificador jurisdiccional con caveat).

## 7. Clasificación gate

**GATE = A — MULTI_JURISDICTION_EVIDENCE_READY (condicionado).**

- `PICOS_LEGAL_CHAIN=PARTIAL_VIGENTE` (presente 2026: 3 normas probadas; pre-2026 no probado ⇒ `UNDETERMINED` fail-closed).
- `AUTONOMOUS_BOUNDARIES=OFFICIAL_ENOUGH_FOR_DESIGN` (OAPN+GISCO cross-checked; ±1 km de frontera exige re-verificación IDE en Phase B antes de fixtures borde).
- `IMPLEMENTATION_ALLOWED=YES` **solo tras aprobar estas fixtures**; implementación completa NO incluida en este PR.

### Blockers (runtime completo)
1. Vectores IDE oficiales de límites interautonómicos (IDEPA / SICTEX-IDERC / IDCyL) sin localizar ⇒ DEFERRED Phase B (bloquea solo fixtures <1 km de frontera).
2. Relación jurídica RD 384/2002 ↔ decretos 2025/2026 sin cadena probada ⇒ consultas históricas `UNDETERMINED`.
3. DEM oficial para la condición "cota 1.800 m" sin fijar ⇒ el `PERMITTED` de art. 51 no puede activarse todavía.
4. Términos de reutilización de PDFs de diarios y WFS OAPN sin verificación formal (igual que M1.1) ⇒ solo extracts.

### DEFERRED
convenio interautonómico (texto), Ley 16/1995 íntegra fijada, cartografía de zonificación del nuevo PRUG,
refugios/vivacs del Anexo X, ZPP (área periférica), BOPA número de disposición exacto (30 vs 31/03/2026).

## 8. Salida final

```
M2A_DISCOVERY_STATUS=COMPLETE
PICOS_LEGAL_CHAIN=PARTIAL_VIGENTE (presente=PROBADO x3 CCAA; historico_pre2026=UNRESOLVED => UNDETERMINED fail-closed)
MULTI_JURISDICTION_CLASSIFICATION=A
AUTONOMOUS_BOUNDARIES=OFFICIAL_ENOUGH_FOR_DESIGN (frontera-interna ±1km => re-verificar IDE Phase B)
IMPLEMENTATION_ALLOWED=YES (condicionado: fixtures de este doc aprobadas antes de implementar; no auto-merge de implementación completa)
BLOCKERS=IDE-fronteras-no-localizados; RD384-2002-cadena-no-probada; DEM-cota1800-sin-fijar; reuse-terms-diarios-no-verificados
DEFERRED=convenio-interautonómico; Ley16/1995-íntegra; zonificación-PRUG; AnexoX-refugios; ZPP; BOPA-num-disposición
PR=referencia en el commit de esta rama
```
