# Generación de la muestra M7 (v1)

- Estado: pre-registrado junto al marco normativo, ANTES de R0.
- `SELECTION_BASIS = NORMATIVE_STRUCTURE`
- `ENGINE_RESULT_USED_FOR_SELECTION = FORBIDDEN`

## 1. Divulgación obligatoria del autor de la muestra

```text
SAMPLE_AUTHOR = autor del proyecto (propietario del repositorio Huntsman1756/AlRaso)
SAMPLE_AUTHOR_KNEW_ENGINE_OUTPUTS = YES
```

**Se asume que el autor del proyecto YA conoce el comportamiento del motor** (sondeos públicos del repositorio, README, suite de tests, hitos M2A/M2B/M3–M6). No se finge lo contrario.

### Sesgo residual declarado

- El autor conoce resultados del motor documentados públicamente (p. ej., que casos interiores de Cantabria >1800 m resuelven `PERMITTED` con los hechos codificados; que P1/P3 interiores <1800 m resuelven `UNDETERMINED`; que excepciones del art. 51 no están modeladas).
- Este conocimiento podría, en teoría, filtrarse en la selección de casos aunque la base de selección sea el marco normativo.
- **Mitigaciones pre-registradas**: revisor independiente a ciegas; custodia independiente del holdout (el autor NO selecciona/expone los 4 casos del holdout); R0 inmutable; matriz de pérdida asimétrica (un falso permiso es `M7_FAIL` sin negociación); publicación íntegra de R0/R1/R2; el paquete del revisor no contiene datos del motor.
- **No eliminado**: el sesgo del autor sobre la ESTRUCTURA de la muestra no puede eliminarse por diseño; se revela, se acota y se audita contra el marco.

## 2. Regla de selección (independiente de resultados del motor)

1. Se enumeran los estratos normativos del marco (`normative-case-frame-v1.md`): regímenes (S1–S3), preceptos (P-*), condiciones (C-*), excepciones, umbrales, temporalidad y ámbito.
2. Cada estrato genera familias de casos según su estructura legal (regla base satisfecha/incumplida por cada predicado; fronteras de umbral; excepciones con predicado presente/ausente; disparador vivo no reproducible; jurisdicción resuelta/in-banda; pre-vigencia por CCAA; fuera de ámbito).
3. Los hechos de cada caso (fechas, noches, cotas, posiciones, tamaño de grupo) se fijan desde datos registrados en la evidencia oficial del repositorio (coordenadas sondeadas y POIs registrados, elevaciones IGN/CNIG MDT25 registradas) o como hechos estipulados neutrales del caso.
4. **Prohibido**: ajustar, añadir o descartar un caso para provocar o evitar un resultado del motor o del revisor. Los estados emergen; no se equilibran.

## 3. Procedencia de coordenadas y datos factuales (main set)

| Caso | Coordenadas / posición | Procedencia |
|---|---|---|
| C01 | 43.202151, -4.836656 | punto registrado boundary-safe es-as, elev. 2416 m (`tooling/m2b_picos_official_boundary_results.json`) |
| C02 | 43.17068, -4.80299 | punto registrado es-cb, elev. 1942 m (mismo candado) |
| C03 | 43.0095347, -4.7170215 | POI OSM registrado "Refugio de Majada de Fuentes Carrionas" (`webapp/pois.json`); cota estipulada ~1950 m |
| C04 | 43.2662, -4.8686 | punto registrado es-as interior, elev. 1510 m |
| C05 | 43.1278, -4.9381 | punto registrado es-cl interior, elev. 1390 m |
| C06 | 43.17068, -4.80299 | reutilización de C02 (hechos distintos: grupo de 12) |
| C07 | 43.202151, -4.836656 | reutilización de C01 (hechos distintos: zanja excavada) |
| C08 | sin coordenadas (deliberado) | sonda interpretativa del umbral; hechos: interior PN, Principado de Asturias, cota 1800 m exacta |
| C09 | 43.0209738, -4.7873935 | POI OSM registrado "Casa del Pleito"; cota estipulada 1850 m |
| C10 | 43.17068, -4.80299 | reutilización de C02 (hechos distintos: 4 noches) |
| C11 | posición textual (sin coordenadas) | "pared del Picu Urriellu" — el marco no registra coordenadas oficiales del topónimo; excepción independiente de precisión espacial |
| C12 | posición textual (sin coordenadas) | "pradera al pie de la pared del Picu Urriellu" |
| C13/C14 | posición textual (sin coordenadas) | "Vega La Sotín, escalada en el Friero" — `UNRESOLVED_FRAME_ITEM` de localización |
| C15 | 43.17068, -4.80299 | reutilización de C02 (hechos distintos: pronóstico de tormenta) |
| C16 | 43.202151, -4.836656 | reutilización de C01 (hechos distintos: accidente) |
| C17 | 43.1770935, -4.7657068 | POI OSM registrado "Refugio para ganaderos"; cota estipulada 1950 m |
| C18 | 43.0095347, -4.7170215 | reutilización de C03; fecha 2025-12-20 |
| C19 | 43.202151, -4.836656 | reutilización de C01; fecha 2026-04-10 |
| C20 | 43.182691, -5.028656 | punto registrado a 2.44 m de la línea límite autonómica oficial (BDDAE), banda de incertidumbre |
| C21 | 43.210691, -4.860656 | punto registrado a 115.9 m de la línea límite autonómica oficial (BDDAE), fuera del guard de 100 m |
| C22 | 43.1213124, -4.5682027 | POI OSM registrado "Camping Liébana" (fuera del PN) |
| C23 | 43.348, -5.13 | punto registrado fuera del PN (Cangas de Onís, sondeo M2A) |
| C24 | posición textual imprecisa (±500 m) | "Vega de Liordes", sin dato de cota (deliberado) |

Las reutilizaciones de coordenadas están documentadas y son neutras: las coordenadas son hechos espaciales registrados; los HECHOS jurídicos (noches, actividad, fechas, grupo, disparadores) diferencian los casos. El paquete del revisor no contiene la tabla anterior completa (ver sección 5).

## 4. Materialización

- El main set (24 casos) se materializa AHORA, en fase de candidato, desde este marco. `main-set-v1.json` no contiene datos del motor ni resultados esperados.
- El holdout (4 casos) NO lo materializa el autor: lo selecciona y sella el custodio (revisor independiente o humano neutral) desde este marco pre-registrado. `holdout-manifest-v1.json` registra custodia y compromiso SHA-256.
- Tras la publicación del candidato, `main-set-v1.json` es inmutable; cualquier cambio exige registro en `protocol-deviations.md`.

## 5. Partición de la información

| Artefacto | Autor | Revisor | Custodio holdout |
|---|---|---|---|
| marco normativo | sí | referencias oficiales solamente (secciones de fuentes) | sí |
| `main-set-v1.json` | sí | sí (solo entradas neutras) | sí |
| `sample-generation-v1.md` | sí | NO (contiene divulgación de conocimiento del autor y provenance interna) | NO |
| fixtures/reglas/trazas del motor | sí | **NUNCA** | NO |
| holdout sellado | NO | en su momento (ejecución del tripwire) | sí |
