# Informe de validación M7 (PLANTILLA v1)

> Estado: PLANTILLA creada ANTES de R0. La estructura de este informe queda congelada antes de que existan resultados. NO rellenar resultados aquí: los resultados van a `r0-results-v1.json` (inmutable) y sus sucesores R1/R2.
> Sin titular agregado de "accuracy": este informe reporta dimensiones, no un score global.

## 0. Declaración de límites (obligatoria, sin cambios)

Esta validación NO:

- valida AlRaso en toda España;
- valida Ordesa;
- valida Góriz;
- valida cambios futuros del corpus;
- establece que todo `UNKNOWN` es legalmente irresoluble;
- convierte el éxito automatizado de tests en verdad jurídica;
- valida condiciones operativas en vivo;
- constituye asesoramiento jurídico;
- valida solo los casos, fuentes, fechas y estado de conocimiento declarados;
- convierte el holdout en una validación estadística positiva;
- establece la independencia del diseño de la muestra meramente mediante SHA-256.

Está PROHIBIDO el lenguaje genérico "AlRaso ha sido legalmente validado". La afirmación final (sección 21) queda acotada por caso/ámbito/fecha/estado de conocimiento.

## 1. Alcance

| Parámetro | Valor |
|---|---|
| Zona | Parque Nacional de los Picos de Europa |
| Actividad | `VIVAC_AL_RASO` |
| Main set | 24 casos (`main-set-v1.json`) |
| Holdout | 4 casos, TRIPWIRE_ONLY (`holdout-manifest-v1.json`) |
| Total planificado | 28 |
| Estados `N/A` | [lista de estados que no ocurrieron naturalmente] |

## 2. Protocolo: versión y SHA

| Campo | Valor |
|---|---|
| Protocolo | protocol-v1 |
| SHA-256 del protocolo al ejecutar R0 | [rellenar en ejecución] |
| Fecha de freeze del protocolo | [rellenar al freeze] |
| Desviaciones | [enlazar protocol-deviations.md; debe decir NO_DEVIATIONS_AS_OF_FREEZE al freeze] |

## 3. Attestation pública del revisor

[Insertar reviewer-attestation-public rellenada. Debe incluir la frase de verificación privada. Sin PII innecesaria.]

## 4. Ceguera del revisor

- Qué recibió el revisor: [entradas neutras + fuentes primarias oficiales]
- Qué NO recibió: [fixtures, reglas codificadas, resultados esperados, aserciones, trazas, determinación de AlRaso, notas internas]
- Momento del sellado de respuestas: [fecha/hora] — ANTES de la revelación de resultados del motor.

## 5. Construcción de la muestra

- Regla de selección: NORMATIVE_STRUCTURE (derivada del marco normativo, no de resultados del motor).
- Prohibición de usar resultados del motor para seleccionar: FORBIDDEN (cumplida/no cumplida; si no cumplida → PROTOCOL_DEVIATION).

## 6. Divulgación del conocimiento del autor de la muestra

```text
SAMPLE_AUTHOR = autor del proyecto
SAMPLE_AUTHOR_KNEW_ENGINE_OUTPUTS = YES
SELECTION_BASIS = NORMATIVE_STRUCTURE
ENGINE_RESULT_USED_FOR_SELECTION = FORBIDDEN
```

Sesgo residual declarado y mitigaciones: [resumen de sample-generation-v1.md sección 1].

## 7. Autoridad de fuentes

- Fuentes primarias oficiales (BOCyL, BOPA, BOC, BOE; IGN/CNIG BDDAE/INSPIRE; OAPN; IGN MDT05): autoridad.
- Materiales secundarios/consolidados: solo ayudas de descubrimiento, etiquetadas como tales.

## 8. Estratos normativos cubiertos

| Estrato | Casos (main set) | Resultado (rellenar tras R0) |
|---|---|---|
| S1 / S2 / S3 / S-UNKNOWN | [mapear] | |
| P-51.1 y condiciones | [mapear] | |
| Excepciones pared / Sotín | [mapear] | |
| P-51.2 | [mapear] | |
| P-51-GROUP / P-51-PROHIB | [mapear] | |
| C-GEO-INBAND / C-GEO-RESOLVED | [mapear] | |
| C-TEMP | [mapear] | |
| O1-FUERA-PN | [mapear] | |

`UNRESOLVED_FRAME_ITEM` publicados antes del freeze: [lista del marco, sección 5].

## 9. Resultados R0

[Tabla por caso: case_id, estado motor, estado revisor, categoría de desacuerdo, excluir/incluir en acuerdo legal. Fuente inmutable: r0-results-v1.json.]

## 10. Resultados R1 (si existe)

[Cada remediación preserva: motor antes, revisor, categoría, adjudicación/causa raíz, cambio exacto de corpus/regla/evidencia, motor después, anotación del revisor si aplica.]

## 11. Resultados R2 (si existe)

[Idéntica disciplina. Después de R2 NO hay más tuning dentro de M7.]

## 12. Matriz de desacuerdo (resultados)

| Par (motor → revisor) | Categoría | Casos |
|---|---|---|
| PERMITTED → débil/desacuerdo | CRITICAL_FALSE_PERMISSION | |
| PERMITTED → OUT_OF_SCOPE | CRITICAL_SCOPE_OVERREACH | |
| PROHIBITED/AUTHORIZATION_REQUIRED → desacuerdo material | MAJOR_DISAGREEMENT | |
| PROHIBITED/AUTHORIZATION_REQUIRED → OUT_OF_SCOPE | MAJOR_SCOPE_DISAGREEMENT | |
| UNDETERMINED → conclusión fuerte | CONSERVATIVE_FALSE_NEGATIVE | |
| UNDETERMINED → UNDETERMINED_LEGAL | acuerdo de incertidumbre legal | |
| UNDETERMINED_FACTUAL → UNDETERMINED_FACTUAL (mismo hecho) | FAIL_CLOSED_AGREEMENT (excluido del acuerdo legal) | |
| UNDETERMINED → OUT_OF_SCOPE | SCOPE_ALIGNMENT_OR_CASE_DESIGN_FINDING | |

## 13. Falsos permisos críticos

[conteo + casos; un solo caso basta para M7_FAIL]

## 14. Desacuerdos de ámbito

[CRITICAL_SCOPE_OVERREACH y MAJOR_SCOPE_DISAGREEMENT; adjudicación explícita de ámbito cuando proceda]

## 15. Falsos negativos conservadores

[conteo + casos; candidatos a remediación/backlog; NO equivalen en severidad a falsos permisos]

## 16. Acuerdos fail-closed factuales

[conteo + casos; EXCLUIDOS de las métricas de acuerdo legal; evidencia de comportamiento conservador, no de corrección interpretativa]

## 17. Adjudicación y anotaciones del revisor

- Secuencia: [revisión a ciegas → sellado → revelación → adjudicación del autor → anotación del revisor]
- Anotaciones del revisor publicadas INTACTAS: [sí/no; si no → PROTOCOL_DEVIATION]
- Desacuerdos explícitos (p. ej. author=CORPUS_ERROR vs reviewer=DISAGREE: INTERPRETATION_ERROR → final_status=ADJUDICATION_DISPUTED): [listar]

## 18. Holdout (tripwire)

| Campo | Valor |
|---|---|
| Custodio | [rellenar] |
| Compromiso SHA-256 | [rellenar; si PENDING, el holdout no se ejecutó] |
| Resultado | [HOLDOUT_PASS / CRITICAL_FALSE_PERMISSION / CRITICAL_SCOPE_OVERREACH / OTHER_MATERIAL_STRONG_DISAGREEMENT / CONSERVATIVE_FALSE_NEGATIVE] |

Declaración obligatoria: "The SHA-256 commitment demonstrates non-substitution after commitment. It does NOT prove independent sample design and does NOT prove that the author was ignorant of the normative strata."
HOLDOUT_PASS NO añade reclamación de accuracy.

## 19. Desviaciones de protocolo

[enlazar protocol-deviations.md; cualquier desviación con fecha, autor, razón, visibilidad de resultados y efecto esperado]

## 20. Limitaciones

[además de la sección 0: sesgo residual del autor, no-independencia demostrable por SHA, tamaño muestral (28 casos), ventana temporal de los hechos, materiales con redacción pendiente de verificación del revisor (P-51-GROUP, P-51-PROHIB), etc.]

## 21. Estado final y afirmación exacta permitida

| Campo | Valor |
|---|---|
| M7_PASS / M7_FAIL / M7_INCONCLUSIVE / M7_ABORTED_PROTOCOL_DEVIATION | [rellenar] |
| Piloto pasó en | [R0 / R1 / R2 — distinguir SIEMPRE] |
| Afirmación exacta permitida por la evidencia | [una frase acotada por casos, ámbito, fechas y estado de conocimiento] |
