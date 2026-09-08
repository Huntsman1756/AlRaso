# Modelo de Garantía Jurídica — AlRaso

**Fecha de revisión**: 2026-09-08

## Resumen ejecutivo

AlRaso no afirma corrección jurídica absoluta. Aporta una **garantía estratificada** que distingue entre errores de implementación (motor/semántica), errores estructurales del corpus (validez normativa) y errores de interpretación legal. Cada categoría tiene detección y mitigación específicas.

## Clasificación de errores (Taxonomía de 3 clases)

### Clase 1 — Errores de implementación (motor / divergencia semántica)

**Qué son**: El motor implementa mal la semántica de la condición (p. ej. evalúa `>=` cuando debería ser `>`, omite un campo, mezcla efectos).

**Detección**:
- `ENGINE_DIFFERENTIAL_TESTING` — múltiples motores (OwnEvaluator + Axiom) deben coincidir para cada versión de regla.
- `CATALA_ROLE=ENGINE_DIFFERENTIAL_TESTING` — Catala se integra ÚNICAMENTE como motor diferencial (Clase 1), nunca como validador de premisas legales.
- `CATALA_CAN_DETECT=ENGINE_OR_SEMANTIC_DIVERGENCE` — los motores pueden detectar divergencias de implementación o semántica.
- `CATALA_CANNOT_DETECT=FALSE_LEGAL_PREMISE_BY_ITSELF` — los motores **no** pueden detectar por sí solos premisas legales falsas (el corpus es el que contiene la premisa; los motores solo la ejecutan).

**Mitigación**:
- Diferencial testing: si Catala y Axiom coinciden, se reduce la probabilidad de errores de implementación.
- **Pero**: `DIFFERENTIAL_ENGINE_AGREEMENT != LEGAL_TRUTH` — la concordancia de motores no prueba la corrección jurídica.
- `TEST_PASS != LEGAL_TRUTH` — un test que pasa no prueba verdad legal.

### Clase 2 — Errores estructurales del corpus (validez normativa)

**Qué son**: El corpus contiene reglas cuya base normativa es inválida, inexistente o caducada.

**Detección**:
- `NORM_VALIDITY_COVERAGE` — toda versión de regla con `normative_basis` no vacío requiere que cada fragmento de la base tenga `provision_ref` y `validity_from`; si se proporciona `activity_date`, debe caer dentro de la intersección de las ventanas de validez de los fragmentos base.
- `PRECEPT_LEVEL_NORMATIVE_BASIS` — la elegibilidad opera a nivel de precepto individual, no del documento en general.
- `APPLICABLE_DOCUMENT != APPLICABLE_PRECEPT` — un documento aplicable no es equivalente a un precepto válido y vigente.

**Códigos de razón**:
- `NORMATIVE_BASIS_MISSING` — versión sin base normativa.
- `NORMATIVE_VALIDITY_UNKNOWN` — fragmento sin `validity_from`.
- `NORMATIVE_BASIS_OUTSIDE_VALIDITY` — `activity_date` fuera de la ventana de validez del fragmento base.
- `NORMATIVE_PRECEPT_MISSING` — fragmento base no resolvable o sin `provision_ref`.

**Mitigación**:
- Gate centralizado en `alraso.eligibility.is_rule_version_eligible`.
- `RULE_INTERVAL_CHECK=DIAGNOSTIC_REPORTED_NOT_ENFORCED` — el diagnóstico estructural (`.rule_intervals_outside_normative_basis()`) informa pero no bloquea; el gate runtime (`ACTIVITY_DATE_RUNTIME_GATE`) es el que fuerza el fail-closed.
- `ACTIVITY_DATE_RUNTIME_GATE=ENFORCED` — el resolver siempre pasa `activity_date` al gate de elegibilidad.

### Clase 3 — Errores de interpretación legal

**Qué son**: El texto legal se lee correctamente pero la interpretación humana que se codifica en la regla es incorrecta o demasiado permissiva/prohibitiva.

**Mitigación (proceso)**:
1. Cita de precepto exacta (número de artículo, apartado).
2. Texto literal exacto del precepto.
3. `interpretation_note` explicando la interpretación aplicada.
4. Revisor humano identificado (`review_status=VERIFIED`, `legal_review_complete=True`).
5. Segunda lectura adversarial o al menos registro de `REVIEW_SINGLE_READER`.
6. Re-verificación periódica al detectar cambios normativos.
7. Proceso de corrección: `corpus_correction.CORPUS_DEFECT` documenta el defecto y la corrección.

**Documentación explícita**:
- `VERIFIED_SOURCE != TRUE_INTERPRETATION` — verificar la fuente no prueba la interpretación.
- `TEST_PASS != LEGAL_TRUTH` — un test que pasa no prueba verdad legal.
- `DIFFERENTIAL_ENGINE_AGREEMENT != LEGAL_TRUTH` — la concordancia de motores no prueba verdad legal.

## Corrección del defecto del corpus: 2021 Ordesa

**CORPUS_DEFECT** = `"2021 Ordesa PERMITTED was based on obsolete/incorrect normative basis and an over-permissive interpretation."`

**Hechos verificados**:
- RD 409/1995 (BOE núm. 112, 11-05-1995): entrada en vigor 12-05-1995.
- Vigencia agotada: 30-04-2015, al entrar en vigor el D 49/2015 (BOA núm. 80, 29-04-2015), vigente 30-04-2015.
- En 2021 regía el D 49/2015 (nuevo PRUG), no el RD 409/1995.

**Por qué 2021 sector-Ordesa ahora es UNDETERMINED**:
- La base normativa del corpus (RD 409/1995) agotó su vigencia en 2015-04-30.
- La redacción del Anexo I.D.a era **condicionada/restrictiva**: permitía acampada por encima de cota (>2100m), en zonas específicas, máx. 3 noches. **Nunca** fue un permiso sectorial general.
- El régimen D 49/2015 contiene además exclusiones puntuales en Zonas de Reserva (p. ej. Ribereta de Cotatuero, Arrablo) cuyas geometrías oficiales no están fijadas para resolución punto a punto.
- `ORDESA_2500_ONLY_SHORTCUT=FORBIDDEN` — el hecho `altitude_m > 2500` por sí solo NO es permisión: la normativa es condicional y sectorial.

## Texto consolidado vs. fuente primaria

- `CONSOLIDATED_TEXT_ROLE=DISCOVERY_AND_READING_AID` — el texto consolidado es una ayuda para descubrimiento y lectura, no la autoridad.
- `PRIMARY_GAZETTE_ROLE=AUTHORITY_FOR_VERIFIED_REDACTION` — el BOE/BOA (gaceta oficial) es la autoridad para la redacción verificada.
- La consolidación editorial no es sustituto de la publicación original/rectificativa cuando se hacen conclusiones fuertes.

## Disciplina de fuente primaria

1. **Autoridad**: quién emitió el acto normativo (Estado, CCAA, municipio).
2. **Fuente canónica**: BOE, BOA, BOCyL, BOPA, BOC, etc.
3. **Provisión exacta**: artículo, apartado, número.
4. **Texto exacto**: cita literal.
5. **validity_from / validity_to**: fecha de entrada en vigor y fin de vigencia.
6. **Retrieved timestamp**: cuándo se consultó la fuente.
7. **Content hash**: hash del documento (SHA-256 conforme a convenciones del proyecto).
8. `VERIFIED` requiere fuente primaria oficial.
9. Fuente secundaria = `DISCOVERY/CORROBORATION` únicamente.

## Góriz: condiciones normativas vs. estado operativo

### Condiciones normativas (NORMATIVA)
- `refuge_capacity_full`: condición normativa (trigger legal del texto: "en los casos de aforo completo del refugio").
- `nights`: condición normativa (PRUG: "la pernocta no excederá de tres noches").
- El VALOR de estas condiciones es un **estado vivo no verificable por AlRaso**.

### Estado operativo (LIVE_OPERATIONAL_STATE)
- `cupo`: 90 personas (hasta 31-12-2023) / 50 personas (desde 01-01-2024). **NUNCA se codifica como hecho de motor**.
- `reserva`, `disponibilidad`, `avisos de la dirección`.
- Política: sin hecho habilitante obligatorio -> `UNDETERMINED` (nunca `PERMITTED`).
- El estado vivo no se persiste como autoridad legal.

### Cotas temporales codificadas
- Cupo de 90 personas: ventana `effective_from=2022-02-09, effective_to=2023-12-31`.
- Cupo de 50 personas: ventana `effective_from=2024-01-01, effective_to=null`.
- El cupo mismo **no se codifica como hecho** (capa operativa/viva).

## LEGALIZE-ES: papel futuro

- `LEGALIZE_ES_ROLE=CANDIDATE_DISCOVERY_AND_CHANGE_SIGNAL` — una commit de Legalize ES es un **evento de conocimiento**, no prueba de la conclusión legal.
- `LEGALIZE_ES_AUTHORITY=NONE` — no se otorga autoridad legal automática a commits de Legalize ES.
- `LEGALIZE_ES_AUTO_PUBLISH=FORBIDDEN` — prohibido publicar automáticamente basándose en un commit de Legalize ES.
- Flujo conceptual: commit -> candidato -> cola de revisión -> verificación fuente primaria -> nuevo fragmento/redacción -> replay bitemporal -> señales STALE.
- `SIGNAL=YES` — un commit de Legalize ES es una señal de cambio.
- `EVIDENCE=NO` — la señal no es evidencia verificada por sí sola.
- No hay webhook/API/poller actualmente.

## Mapeo de garantías

| Fuente de garantía | Categoría | Papel |
|---|---|---|
| `ENGINE_DIFFERENTIAL_TESTING` | Clase 1 | Garantía de implementación: detección de divergencia semántica entre motores. |
| `NORM_VALIDITY` | Clase 2 | Garantía estructural del corpus: validez de preceptos y vigencia. |
| `HUMAN_REVIEW` | Clase 3 | Garantía de interpretación: revisión humana del texto y su codificación. |

**Rechazo explícito**: "múltiples motores detectan premisas legales falsas" — los motores solo ejecutan lo que el corpus les dice; no detectan premisas legales falsas por sí solos.

## RULE_INTERVAL_CHECK

`RULE_INTERVAL_CHECK=DIAGNOSTIC_REPORTED_NOT_ENFORCED` con razón: los corpus históricos append-only deben permanecer cargables; el gate runtime es el mecanismo de aplicación, no la integridad estructural del DB.