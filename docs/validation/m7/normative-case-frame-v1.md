# Marco normativo de casos M7 (v1)

- Estado: pre-registrado ANTES del muestreo y ANTES de R0.
- Derivado de la ESTRUCTURA DE LA LEY, no de resultados del motor.
- Fuentes: extractos literales registrados de los tres decretos autonómicos + evidencia espacial oficial registrada. Referencias y SHAs más abajo.
- Regla anti-deriva: ninguna interpretación nueva se introduce silenciosamente. Toda premisa sin soporte primario exacto se registra como `UNRESOLVED_FRAME_ITEM` (sección 5).

## 1. Base de derivación (evidencia registrada)

| Documento | Diario oficial | Fecha publicación | Entrada en vigor | SHA-256 del PDF oficial |
|---|---|---|---|---|
| Decreto 17/2025 (PRUG PNPE en el ámbito de CyL) | BOCyL núm. 240, 15/12/2025 | 2025-12-15 | 2026-01-04 (+20 días) | `70b07b6da908c873dc3c3fc6ff7dfe8f984e55493b40b4a690de49bc9a4edbca` |
| Decreto 21/2026 (PRUG PNPE en el ámbito de Asturias) | BOPA 30/03/2026, Cód. 2026-02506 | 2026-03-30 | 2026-04-19 (+20 días) | `a1e374e5dcc12c5de2de653abf1f4da2635c620a10ac17e4f43ffd709d5210bd` |
| Decreto 57/2026 (PRUG PNPE en el ámbito de Cantabria) | BOC núm. 148, 04/08/2026 | 2026-08-04 | 2026-08-24 (+20 días) | `28ad80f99b44278153ee928e83efd27b8187049285891556db0e2381797c62c2` |

Extractos literales registrados (texto plegado sin tildes):

- `discovery/evidence/m2a-picos/cyl-17-2025-extract.txt` (sha256 `a94dcc0653551933a078b35ddde18bc0c09fdd42d31dca6ff4492803f47b3890`)
- `discovery/evidence/m2a-picos/as-21-2026-extract.txt` (sha256 `6578d896347fb4ee8f9f1a3772a2ecb705dc5eafd8d95989920440fd60e8eb34`)
- `discovery/evidence/m2a-picos/cb-57-2026-extract.txt` (sha256 `e67bd485f882b3ae2174648686b60e82dd162a62e9366e9a8b0c7a3c14b36e25`)

Candados de evidencia: `tooling/m2a_picos_discovery.evidence.json`, `tooling/m2b_picos_official_boundary.evidence.json` (frontera IGN/CNIG BDDAE/INSPIRE, guard 100 m, incertidumbre oficial ~40 m).

Evidencia espacial oficial referenciable (para el revisor):

- Límites autonómicos: IGN/CNIG BDDAE/INSPIRE — `https://centrodedescargas.cnig.es/CentroDescargas/limites-municipales-provinciales-autonomicos` (línea límite autonómica; sha256 del zip registrado en `tooling/m2b_picos_official_boundary.evidence.json`).
- Límite del Parque Nacional: OAPN WFS — `https://sigred.oapn.es/geoserverOAPN/ows` (`LimitesParquesNacionalesZPP:view_red_oapn_limite_pn`).
- Elevaciones: IGN MDT05 (portal oficial `centrodedescargas.cnig.es`).
- URLs de los diarios oficiales: BOCyL `https://bocyl.jcyl.es/boletin.do?fechaBoletin=15/12/2025`; BOPA `https://miprincipado.asturias.es/bopa`; BOC `https://www.cantabria.es/web/boc`.

Nota: los PDFs oficiales completos NO se redistribuyen (términos de reutilización NOT_VERIFIED; ver NOTICE.md). El revisor los obtiene de los portales oficiales citados.

## 2. Estratos de régimen (CCAA)

El PRUG se aprueba por decreto SEPARADO en cada CCAA, con ámbito territorial propio y entrada en vigor propia:

| Estrato | Régimen | Precepto instance | Ámbito territorial |
|---|---|---|---|
| `S1` | Principado de Asturias — Decreto 21/2026 | art. 51/52 del PRUG (BOPA) | "en el ámbito territorial del Principado de Asturias" |
| `S2` | Cantabria — Decreto 57/2026 | art. 51/52 del PRUG (BOC) | "en el ámbito territorial de la Comunidad Autónoma de Cantabria" |
| `S3` | Castilla y León — Decreto 17/2025 | art. 51/52 del PRUG (BOCyL) | "en el ámbito territorial de la Comunidad de Castilla y León" |
| `S-UNKNOWN` | jurisdicción no determinada en el marco | — | se delega al revisor (con fuentes oficiales) o queda `UNDETERMINED_FACTUAL` |

Los tres textos del art. 51 son materialmente idénticos (verificado en los tres extractos; diffs no detectados en arts. 50–54 según candado `tooling/m2a_picos_discovery.evidence.json`), pero son TRES preceptos-jurídicamente-distintos con tres ventanas de vigencia distintas.

## 3. Estratos de precepto (texto común a S1–S3)

### P-51.1 — Regla base del vivac

Texto registrado (extracto, texto plegado):

> "Articulo 51. Vivaqueo 1. En el ambito del Parque Nacional unicamente se permitira el vivac o la pernocta al raso vinculada a las actividades de montana y escalada, hasta un maximo de 3 noches. El vivaqueo se realizara siempre por encima de la cota 1.800 m, con la excepcion del vivac en pared y en epoca invernal en la Vega La Sotin para la escalada en el Friero."

Predicados fácticos requeridos: (a) vínculo con actividad de montaña y escalada; (b) noches ≤ 3; (c) cota > 1.800 m; (d) punto en el ámbito del Parque Nacional (y régimen CCAA aplicable).

- Clasificación: `IN_SCOPE_RESOLVABLE`
- Razón factual: texto literal registrado en los tres decretos con vigencia verificable por fecha.
- Fuente: art. 51.1 en cada decreto (S1/S2/S3).

### P-51.1-EXC-PARED — Excepción "vivac en pared"

Texto: la excepción al requisito de cota es "el vivac en pared".

- Clasificación: `IN_SCOPE_RESOLVABLE` (existencia textual registrada).
- Predicado fáctico: que el vivac sea efectivamente "en pared" (durante la escalada), hecho que debe constar en los hechos del caso. El marco NO verifica "en pared" por sí mismo; lo aporta el caso y lo valora el revisor.
- Fuente: art. 51.1 (excepción 1).

### P-51.1-EXC-SOTIN — Excepción "época invernal en la Vega La Sotín para la escalada en el Friero"

Texto: la excepción al requisito de cota es "en época invernal en la Vega La Sotín para la escalada en el Friero".

- Clasificación textual: `IN_SCOPE_RESOLVABLE` (existencia textual registrada).
- Clasificación de aplicación: `IN_SCOPE_BUT_FACTUALLY_UNVERIFIABLE`
- Razón factual: (i) no hay evidencia espacial oficial registrada que precise la localización de la Vega La Sotín ni del Friero; (ii) "época invernal" carece de definición codificada en el precepto (sin fechas); (iii) el marco no puede establecer la premisa (¿dónde y cuándo es "época invernal"?) desde la evidencia registrada. El revisor valora con fuentes oficiales; si no puede, `UNDETERMINED_*`.
- Fuente: art. 51.1 (excepción 2).

### P-51.2 — Tiendas por meteorología adversa / fuerza mayor

Texto registrado (extracto, texto plegado):

> "2. Ante condiciones meteorologicas adversas o de fuer za mayor, y siempre por encima de la cota 1.800 m., con la excepcion de lo dispuesto en el punto anterior, se podra pernoctar en tiendas de campana, pudiendo instalar las mismas en el periodo comprendido entre una hora antes del ocaso y una hora despues del orto. En caso de que perduren las circunstancias que hicieron necesaria su instalacion, las tiendas de campana se podran dejar instaladas fuera del periodo nocturno, siendo obligatorio desmontarlas en cuanto dichas condicione[s cesen]"

- Clasificación: `IN_SCOPE_BUT_FACTUALLY_UNVERIFIABLE`
- Razón factual: el disparador ("condiciones meteorológicas adversas o de fuerza mayor") es un ESTADO VIVO OPERATIVO no demostrable de forma reproducible desde datos codificados; la franja de instalación (ocaso/orto) depende de hechos horarios no registrados. Disciplina preservada (ver `docs/LEGAL-ASSURANCE-MODEL.md`, NORMATIVA vs `LIVE_OPERATIONAL_STATE`): este disparador NO se convierte en un booleano controlado por el caller que desbloquee un PERMITTED; no se usa para construir una conclusión PERMITTED fuerte. Resultados conservadores (`UNDETERMINED_FACTUAL`) son legítimos aquí.
- Fuente: art. 51.2 (S1/S2/S3).

### P-51-GROUP — Requisito de autorización por tamaño de grupo

- Clasificación: `IN_SCOPE_RESOLVABLE` con reserva.
- Soporte: el candado `tooling/m2a_picos_discovery.evidence.json` registra, para el bloque común de arts. 50–54 verificado en los tres extractos, que "grupos >10 requieren autorización". EL APARTADO VERBATIM NO ESTÁ incluido en los extractos registrados → el revisor DEBE verificar el precepto exacto y el umbral contra el diario oficial correspondiente antes de apoyar una conclusión en él. El marco NO fija el umbral numérico.
- Fuente: art. 51 (apartado de grupos), S1/S2/S3 (a verificar por el revisor).

### P-51-PROHIB — Prohibición de zanjas/parapetos en el vivac

- Clasificación: `IN_SCOPE_RESOLVABLE` con reserva (mismo régimen que P-51-GROUP: existencia registrada por el candado de evidencia; redacción verbatim pendiente de verificación del revisor contra el diario oficial).
- Fuente: art. 51 (apartado de prohibiciones), S1/S2/S3 (a verificar por el revisor).

### P-52 — Acampada / pernocta en vehículos (precepto adyacente)

Texto registrado (extracto, texto plegado):

> "Articulo 52. Acampada y pernocta 1. Fuera de los nucleos de poblacion unicamente se permite la acampada en los campings legalmente autorizados y para los campamentos a los que se refiere el apartado siguiente, con la excepcion de lo dispuesto en el articulo 53.7. Asimismo, fuera de estos lugares no se permite la pernocta en cualquier tipo de vehiculo, caravana, autocaravana o similar."

- Clasificación: `OUT_OF_SCOPE`
- Razón factual: regula una figura jurídica distinta (acampada / pernocta en vehículo), no el `VIVAC_AL_RASO`; la única vía para que tiendas entren en el análisis del vivac es el art. 51.2 (P-51.2). Se justifica metodológicamente como precepto ADYACENTE: si un caso describe instalación de campamento/acampada, el revisor puede valorar si el hecho dejó de ser vivac.
- Fuente: art. 52.1 (S1/S2/S3).

## 4. Estratos de condición

| Estrato | Contenido | Clasificación | Razón factual / fuente |
|---|---|---|---|
| `C-ACT` | Vínculo con actividad de montaña y escalada (presente/ausente en los hechos) | `IN_SCOPE_RESOLVABLE` | art. 51.1: "vinculada a las actividades de montaña y escalada"; hecho aportado por el caso |
| `C-NIGHTS` | Límite "hasta un máximo de 3 noches" | `IN_SCOPE_RESOLVABLE` | art. 51.1; sonda de frontera: exactamente 3 vs 4 noches |
| `C-ALT` | Requisito "siempre por encima de la cota 1.800 m" (satisfecho/incumplido) | `IN_SCOPE_RESOLVABLE` | art. 51.1; hechos: cota registrada (IGN MDT05) o aportada |
| `C-ALT-BOUNDARY` | Semántica del umbral en cota EXACTAMENTE 1.800 m ("por encima": ¿exclusivo?) | `IN_SCOPE_RESOLVABLE` (sonda interpretativa) | art. 51.1; caso diseñado sin coordenadas y con cota medida como hecho |
| `C-GEO-RESOLVED` | Jurisdicción CCAA determinable oficialmente (punto a >100 m de la línea límite autonómica) | `IN_SCOPE_RESOLVABLE` | BDDAE/INSPIRE; guard 100 m; incertidumbre oficial ~40 m (`tooling/m2b_picos_official_boundary.evidence.json`) |
| `C-GEO-INBAND` | Punto DENTRO de la banda de incertidumbre (≤100 m de la línea límite autonómica) | `IN_SCOPE_BUT_FACTUALLY_UNVERIFIABLE` | a esa proximidad la jurisdicción no es fiablemente determinable (guard 100 m sobre incertidumbre oficial ~40 m); resultado conservador legítimo |
| `C-TEMP` | Vigencia: entrada en vigor +20 días por CCAA; `activity_date` anterior | `IN_SCOPE_RESOLVABLE` (determinación de no-vigencia) — el RÉGIMEN APLICABLE ANTERIOR es `UNRESOLVED_FRAME_ITEM` (sección 5) | disposiciones finales de los tres decretos: "entrará en vigor a los veinte días de su publicación"; fechas 2026-01-04 / 2026-04-19 / 2026-08-24 |
| `C-ALT-MISSING` | Cota ausente/inverificable en los hechos | `IN_SCOPE_BUT_FACTUALLY_UNVERIFIABLE` | sin cota no puede aplicarse C-ALT; fail-closed legítimo |
| `NIGHTS-MISSING` | Noches ausentes en los hechos | `IN_SCOPE_BUT_FACTUALLY_UNVERIFIABLE` | sin nº de noches no puede aplicarse C-NIGHTS; fail-closed legítimo |

## 5. Registro de UNRESOLVED_FRAME_ITEM (publicado antes del freeze)

1. **Régimen aplicable ANTES de las entradas en vigor (2025-12-15/2026-04-19/2026-08-24).** El candado de descubrimiento registra el PRUG anterior (RD 384/2002, `https://www.boe.es/buscar/act.php?id=BOE-A-2002-9576`) con estado `LEGACY_STATUS_UNRESOLVED`: los decretos 2025/2026 NO lo mencionan ni lo derogan expresamente y su relación jurídica no está probada en la evidencia registrada. El marco NO infiere qué regla regía el vivac antes de cada entrada en vigor. El revisor puede investigarlo con fuentes primarias (BOE); si no puede, `UNDETERMINED_LEGAL`. En ningún caso un caso pre-vigencia puede producir PERMITTED fuerte sobre el RD 384/2002 dentro de este marco.
2. **Redacción verbatim de P-51-GROUP y P-51-PROHIB.** Existencia registrada por el candado de evidencia (bloque común arts. 50–54), pero el texto de esos apartados no está en los extractos registrados. Se exige verificación del revisor contra el diario oficial. El marco NO fija umbral numérico ni redacción.
3. **Localización oficial de la Vega La Sotín / el Friero y definición de "época invernal".** Sin evidencia espacial oficial registrada para el topónimo y sin definición temporal en el precepto (ver P-51.1-EXC-SOTIN).

Estos ítems NO se cierran por inferencia. Se presentan al revisor como espacios abiertos y se publican aquí antes del freeze.

## 6. Celdas OUT_OF_SCOPE (definición)

`OUT_OF_SCOPE` procede cuando, por los hechos, el caso no queda gobernado por el marco invocado. Celdas definidas:

| Celda | Definición | Justificación metodológica |
|---|---|---|
| `O1-FUERA-PN` | Punto fuera del límite del PNPE (p. ej., valle/pueblo exterior): el PRUG del parque no gobierna | sonda de disciplina de ámbito; el motor debe responder sin scope aplicable, el revisor debe reconocer la falta de ámbito |
| `O2-FIGURA-DISTINTA` | Hechos que describen acampada/pernocta en vehículo (art. 52) y no vivac al raso | precepto adyacente; el revisor puede reclasificar la figura |
| `O3-DEVOLUCION-POR-AMBITO` | Cualquier caso donde el revisor estime que la norma invocada no gobierna | salida legítima de la revisión |

## 7. Espacio de estados que cada estrato puede producir NATURALMENTE

Esto es una descripción de CAPACIDAD del marco (qué estados son jurídicamente posibles), NO una predicción de resultados del motor ni del revisor:

- P-51.1 con predicados satisfechos → `PERMITTED` capaz.
- P-51.1 con C-ALT incumplida sin excepción; C-NIGHTS > 3; P-51-PROHIB; excepciones con predicado ausente (pared no "en pared", Sotín sin invierno) → `PROHIBITED` capaz (el revisor decide el estado exacto).
- P-51-GROUP con grupo sobre el umbral → `AUTHORIZATION_REQUIRED` capaz.
- P-51.2; C-GEO-INBAND; C-TEMP pre-vigencia; C-ALT-MISSING; NIGHTS-MISSING; C-ALT-BOUNDARY según interpretación → `UNDETERMINED_*` capaz.
- O1/O2/O3 → `OUT_OF_SCOPE` capaz.

Ningún estado se fuerza: si un estado no aparece en los 24 casos del main set ni en los 4 del holdout, queda `STATUS = N/A`.

## 8. Mapa de casos del main set (24)

| Caso | Estratos | Resumen neutral |
|---|---|---|
| C01 | S1, P-51.1 | vivac es-as, cota 2416 m (MDT05), 1 noche, montaña |
| C02 | S2, P-51.1 | vivac es-cb, cota 1942 m (MDT05), 2 noches, escalada |
| C03 | S3, P-51.1 | vivac es-cl, cota aportada ~1950 m, 2 noches, montaña |
| C04 | S1, P-51.1, C-ALT | vivac es-as interior, cota 1510 m (MDT05), 1 noche |
| C05 | S3, P-51.1, C-ALT | vivac es-cl interior, cota 1390 m (MDT05), 1 noche |
| C06 | S2, P-51-GROUP | vivac es-cb, cota 1942 m, grupo de 12 personas, 1 noche |
| C07 | S1, P-51-PROHIB | vivac es-as, cota 2416 m, con zanja/parapeto excavado |
| C08 | S1, P-51.1, C-ALT-BOUNDARY | cota exactamente 1800 m medida, sin coordenadas |
| C09 | S3, P-51.1, C-NIGHTS | vivac es-cl, exactamente 3 noches, cota aportada 1850 m |
| C10 | S2, P-51.1, C-NIGHTS | vivac es-cb, 4 noches, cota 1942 m |
| C11 | S1, P-51.1-EXC-PARED | vivac EN PARED del Picu Urriellu durante escalada, cota < 1800 m |
| C12 | S1, P-51.1-EXC-PARED | vivac al pie de la pared (pradera), no "en pared", cota ~1300 m |
| C13 | S-UNKNOWN, P-51.1-EXC-SOTIN | vivac en Vega La Sotín, escalada en el Friero, diciembre (invierno) |
| C14 | S-UNKNOWN, P-51.1-EXC-SOTIN | mismo lugar y figura, fecha de verano |
| C15 | S2, P-51.2 | tienda por pronóstico de tormenta, es-cb, cota 1942 m, 1 noche |
| C16 | S1, P-51.2 | tienda por accidente/fuerza mayor, es-as, cota 2416 m, 1 noche |
| C17 | S-UNKNOWN, P-51.1, C-ACT | vivac de pastor en trashumancia (sin vínculo montaña/escalada), cota aportada 1950 m |
| C18 | S3, P-51.1, C-TEMP | vivac es-cl, fecha 2025-12-20 (pre-vigencia) |
| C19 | S1, P-51.1, C-TEMP | vivac es-as, fecha 2026-04-10 (pre-vigencia) |
| C20 | S-UNKNOWN, C-GEO-INBAND | punto a ~2 m de la línea límite autonómica oficial |
| C21 | S-UNKNOWN, C-GEO-RESOLVED | punto a ~116 m de la línea límite autonómica oficial |
| C22 | O1-FUERA-PN | vivac en Liébana junto a Potes, fuera del PN |
| C23 | O1-FUERA-PN | vivac en Cangas de Onís, fuera del PN |
| C24 | S3, P-51.1, C-ALT-MISSING | Vega de Liordes, posición imprecisa ±500 m, sin dato de cota |

Los datos completos de cada caso están en `main-set-v1.json` (solo entradas neutras al revisor). Detalles de provenance y sesgo en `sample-generation-v1.md`.

## 9. Reglas anti-deriva

- Este marco se materializa ANTES de cualquier remediación legal M7.
- No se introduce interpretación nueva sin registrarla aquí o como desviación de protocolo.
- Los `UNRESOLVED_FRAME_ITEM` no se cierran por inferencia.
- Cambios posteriores al marco → `protocol-deviations.md` con fecha, autor, razón, visibilidad de resultados y efecto esperado.
