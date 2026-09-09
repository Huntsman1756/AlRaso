# Protocolo M7 — Piloto de validación jurídica independiente (v1)

- Estado: `M7_PROTOCOL_STATUS = CANDIDATE_READY_FOR_HUMAN_FREEZE_INPUT`
- `M7_PROTOCOL_FREEZE = NO` (hasta que se cumplan las 14 condiciones de la sección 16)
- `LEGAL = FROZEN` — este protocolo NO toca el corpus, el resolver ni ninguna regla legal
- Alcance de este documento: metodología pre-registrada ANTES de ejecutar R0 y antes de cualquier remediación legal

## 1. Objetivo y principios innegociables

M7 existe porque:

```text
TEST_PASS != LEGAL_TRUTH
VERIFIED_SOURCE != TRUE_INTERPRETATION
DIFFERENTIAL_ENGINE_AGREEMENT != LEGAL_TRUTH
```

La suite automatizada demuestra invariantes de implementación y del corpus, no corrección jurídica externa. M7 somete las conclusiones legales de casos concretos a una revisión humana jurídica independiente, a ciegas y basada en fuentes primarias oficiales.

Reglas innegociables:

1. M7 NO debe ser diseñado para pasar.
2. Resultados terminales válidos y publicables: `M7_PASS`, `M7_FAIL`, `M7_INCONCLUSIVE`, `M7_ABORTED_PROTOCOL_DEVIATION`. Un FAIL es un resultado legítimo.
3. R0 es evidencia inmutable; nunca se sobrescribe.
4. El revisor trabaja a ciegas y solo con fuentes primarias oficiales.
5. Ningún desacuerdo se resuelve borrando la voz del revisor.
6. El estado vivo operativo (meteorología, aforos, avisos) nunca se convierte en un booleano controlado por el caller que habilite un resultado favorable (ver sección 3.5).

## 2. Alcance pre-registrado

| Parámetro | Valor pre-registrado |
|---|---|
| ZONE | Picos de Europa (Parque Nacional de los Picos de Europa) |
| PRIMARY_ACTIVITY | `VIVAC_AL_RASO` |
| MAIN_SET_N | 24 |
| HOLDOUT_N | 4 |
| TOTAL_PLANNED_N | 28 |

- NO se equilibran casos para llenar valores del enum. No hay obligación de fabricar `PERMITTED`, `PROHIBITED`, `AUTHORIZATION_REQUIRED` ni `UNDETERMINED`.
- Todos los resultados deben surgir naturalmente de los estratos normativos (`normative-case-frame-v1.md`).
- Si un estado legal no ocurre naturalmente en el alcance definido: `STATUS = N/A` para ese estado. No se inventa un caso para ejercitar un valor del enum.
- Población de casos: personas que pernoctan al raso (vivac) en el interior del PNPE, en cualquiera de las tres CCAA (Asturias, Cantabria, Castilla y León), en fechas alrededor y después de las entradas en vigor de los decretos 17/2025 (BOCyL), 21/2026 (BOPA) y 57/2026 (BOC), con sonda de ámbito fuera del parque donde esté metodológicamente justificado.

## 3. Definiciones operativas

### 3.1 Vocabulario de salida del revisor

| Valor | Significado |
|---|---|
| `PERMITTED` | El precepto aplicable autoriza el hecho descrito en la fecha indicada |
| `PROHIBITED` | El precepto aplicable prohíbe o no autoriza el hecho descrito |
| `AUTHORIZATION_REQUIRED` | El hecho requiere autorización administrativa para ser lícito |
| `UNDETERMINED_LEGAL` | Las fuentes no sostienen una conclusión suficientemente fuerte |
| `UNDETERMINED_FACTUAL` | La regla puede ser clara, pero falta un hecho requerido o es inverificable |
| `OUT_OF_SCOPE` | El caso queda fuera del ámbito de la norma invocada (p. ej., fuera del parque) |

### 3.2 Conclusión jurídica FUERTE

Una conclusión es FUERTE solo si incluye los cuatro elementos:

1. precepto exacto (artículo / apartado / letra) de la fuente primaria;
2. redacción aplicable (cita literal del texto oficial);
3. razonamiento de que el precepto es válido y aplicable en `activity_date` (vigencia);
4. razonamiento interpretativo breve (por qué el precepto conduce al estado).

Una conclusión desnuda tipo "creo que está permitido" NO es una conclusión jurídica fuerte.

### 3.3 Distinción UNDETERMINED

- `UNDETERMINED_LEGAL`: las fuentes/la ley no sostienen una conclusión suficientemente fuerte (incertidumbre jurídica).
- `UNDETERMINED_FACTUAL`: la regla puede estar clara pero falta un hecho requerido (cota, noches, posición, jurisdicción) o es inverificable.

Métrica importante: si el motor y el revisor se detienen por el MISMO predicado fáctico ausente, el resultado es `CASE_DESIGN / FAIL_CLOSED_AGREEMENT`: evidencia útil de comportamiento conservador, pero DEBE excluirse de las métricas de acuerdo legal. No prueba corrección interpretativa.

### 3.4 OUT_OF_SCOPE

`OUT_OF_SCOPE` se define en la sección 6 del marco normativo. Sus celdas en la matriz de desacuerdo están definidas en la sección 9.

### 3.5 Condición normativa vs. estado vivo operativo

Se preserva la disciplina existente (ver `docs/LEGAL-ASSURANCE-MODEL.md`, sección Góriz):

- **Condición normativa**: condición que el texto legal exige (p. ej., "por encima de la cota 1.800 m", "máximo 3 noches").
- **Estado vivo operativo** (`LIVE_OPERATIONAL_STATE`): hecho operativo que AlRaso no puede demostrar de forma reproducible (p. ej., "condiciones meteorológicas adversas o de fuerza mayor" del art. 51.2, aforos, avisos de dirección).

Regla: si un disparador no puede demostrarse de forma reproducible, NO se usa para construir una conclusión PERMITTED fuerte. El art. 51.2 no se convierte en un booleano controlado por el caller que desbloquee un resultado favorable. Los casos que involucren el art. 51.2 se evalúan con `UNDETERMINED_FACTUAL` como resultado conservador legítimo.

## 4. Revisor: cualificación, independencia y verificación privada

El revisor DEBE estar seleccionado ANTES de la congelación final del protocolo. NO se fabrica un revisor. NO se marca cualificación como verificada sin evidencia humana.

### 4.1 Verificación privada requerida antes de freeze

| Campo | Valor requerido |
|---|---|
| `qualification_verified` | YES |
| `independence_verified` | YES |
| `conflict_of_interest_checked` | YES |
| `estimated_effort_accepted` | YES |
| `blind_review_protocol_accepted` | YES |
| `adjudication_annotation_right_accepted` | YES |

### 4.2 Perfil deseado

- No es autor del corpus.
- No participó en revisiones legales internas previas.
- Formación jurídica demostrable.
- Competencia/experiencia relevante en derecho administrativo, derecho ambiental y/o regulación de espacios protegidos.
- Sin conflicto de interés material.

### 4.3 Esfuerzo estimado

Aproximadamente **6–10 horas cualificadas para 28 casos**. Es solo una estimación de planificación; el revisor debe aceptar la carga real antes del freeze.

### 4.4 Wording público obligatorio

> "Independent legal review; the reviewer's identity and qualification were verified privately. The public report describes the relevant experience and scope without publishing unnecessary personal data."

NO se usa el wording débil "qualified review" a secas. La plantilla pública de attestation no contiene PII innecesaria (`reviewer-attestation-public.template.md`).

Hasta que exista un revisor y haya aceptado:

```text
REVIEWER_STATUS = PENDING
M7_PROTOCOL_FREEZE = NO
```

Este es un prerrequisito HUMANO, no resoluble por el agente.

## 5. Ceguera del revisor

El revisor independiente NO recibe:

- `alraso/resources/fixture_picos.json`;
- objetos codificados `LegalRule` / `LegalRuleVersion`;
- resultados esperados;
- aserciones de tests;
- trazas del resolver;
- la determinación existente de AlRaso;
- notas de interpretación interna que revelen el resultado esperado.

El paquete del revisor contiene solo lo necesario para responder la pregunta jurídica de forma independiente:

- coordenadas / ámbito factual;
- actividad;
- `activity_date`;
- hechos conocidos;
- pregunta jurídica neutral;
- fuentes primarias oficiales: BOCyL, BOPA, BOC y evidencia espacial oficial necesaria (IGN/CNIG BDDAE/INSPIRE, OAPN, IGN MDT).

**Las fuentes primarias oficiales son la autoridad.** Materiales secundarios/consolidados solo pueden usarse como ayudas de descubrimiento/lectura y deben etiquetarse como tales.

## 6. Construcción de la muestra y sesgo residual

Ver `sample-generation-v1.md`. Puntos obligatorios pre-registrados:

```text
SAMPLE_AUTHOR = autor del proyecto (repository owner)
SAMPLE_AUTHOR_KNEW_ENGINE_OUTPUTS = YES
SELECTION_BASIS = NORMATIVE_STRUCTURE
ENGINE_RESULT_USED_FOR_SELECTION = FORBIDDEN
```

Se asume que el autor del proyecto ya conoce el comportamiento del motor. No se finge lo contrario. El sesgo residual se documenta y mitiga con: revisor a ciegas, custodia independiente del holdout, R0 inmutable, matriz de pérdida asimétrica y publicación de todas las rondas.

`main-set-v1.json` contiene SOLO entradas neutras al revisor. NO contiene `expected_engine_result`, ni traza del motor, ni interpretación de regla codificada, ni resultado esperado del revisor, ni pistas sobre lo que AlRaso cree.

## 7. Marco normativo de casos

El marco normativo (`normative-case-frame-v1.md`) se deriva de la ESTRUCTURA DE LA LEY (estratos: régimen CCAA, preceptos, condiciones, excepciones, umbrales, jurisdicción, hechos, temporalidad, ámbito), no de resultados del motor. Cada ítem del marco se clasifica ANTES de muestrear como `IN_SCOPE_RESOLVABLE`, `IN_SCOPE_BUT_FACTUALLY_UNVERIFIABLE` o `OUT_OF_SCOPE`, con razón factual y referencia de fuente/precepto. Los ítems sin soporte primario exacto se marcan `UNRESOLVED_FRAME_ITEM` y se publican antes del freeze, sin inferir la premisa ausente.

## 8. R0 / R1 / R2 — política de remediación

- **R0 es evidencia inmutable de línea base.** Nunca se sobrescribe.
- `MAX_REMEDIATION_ROUNDS = 2`. Secuencia permitida: `R0` → `R1` (remediación #1) → `R2` (remediación #2). Después de R2: **NO más tuning dentro de M7**.
- Cada iteración queda publicada.
- Cada registro de remediación debe preservar: resultado del motor antes, resultado del revisor, categoría de desacuerdo, adjudicación/causa raíz, cambio exacto de corpus/regla/evidencia, resultado del motor después, anotación del revisor si aplica.

**Distinción que el informe final DEBE preservar:** un piloto que pasa en R0 es una afirmación materialmente distinta de un piloto que pasa solo tras R1/R2.

## 9. Matriz de desacuerdo (pérdida asimétrica)

Pre-registrada. La evaluación es por caso, en cada ronda:

| Motor | Revisor | Categoría | Consecuencia |
|---|---|---|---|
| `PERMITTED` | Revisor materialmente más débil / en desacuerdo | `CRITICAL_FALSE_PERMISSION` | `M7_FAIL` |
| `PERMITTED` | `OUT_OF_SCOPE` | `CRITICAL_SCOPE_OVERREACH` | `P0`; `M7_FAIL` salvo que la adjudicación explícita de ámbito demuestre que la valoración de ámbito del propio revisor era errónea |
| `PROHIBITED` | Desacuerdo material | `MAJOR_DISAGREEMENT` | registrar y adjudicar |
| `AUTHORIZATION_REQUIRED` | Desacuerdo material | `MAJOR_DISAGREEMENT` | registrar y adjudicar |
| `PROHIBITED` o `AUTHORIZATION_REQUIRED` | `OUT_OF_SCOPE` | `MAJOR_SCOPE_DISAGREEMENT` | adjudicación explícita de ámbito requerida |
| `UNDETERMINED` | Conclusión fuerte | `CONSERVATIVE_FALSE_NEGATIVE` | candidato a remediación/backlog; NO equivale en severidad a un falso permiso |
| `UNDETERMINED` | `UNDETERMINED_LEGAL` | acuerdo de incertidumbre legal | registrar |
| `UNDETERMINED_FACTUAL` | `UNDETERMINED_FACTUAL` (mismo hecho ausente) | `CASE_DESIGN / FAIL_CLOSED_AGREEMENT` | EXCLUIDO de métricas de acuerdo legal |
| `UNDETERMINED` | `OUT_OF_SCOPE` | `SCOPE_ALIGNMENT_OR_CASE_DESIGN_FINDING` | no se cuenta automáticamente como acuerdo legal |

"Materialmente más débil / en desacuerdo": el revisor concluye un estado que no justifica el permiso que el motor publicó (p. ej., `PROHIBITED`, `AUTHORIZATION_REQUIRED`, `UNDETERMINED_LEGAL` con motivación), o desacredita el precepto invocado.

## 10. Métricas obligatorias

M7 NO se reduce a un score global de "accuracy". NO hay titular agregado único. Dimensiones obligatorias, reportadas por separado para R0, R1 y R2:

- `false_permission_count`
- `critical_scope_overreach_count`
- `major_disagreement_count`
- `major_scope_disagreement_count`
- `conservative_false_negative_count`
- `exact_agreement_count`
- `fail_closed_factual_agreement_count` (excluido del acuerdo legal)
- `agreement_by_legal_status`
- `agreement_by_normative_stratum`

## 11. Adjudicación — segunda frontera de confianza

El autor puede clasificar la causa raíz, pero no puede tener la única voz. Secuencia pre-registrada:

1. el revisor completa la revisión a ciegas de los casos;
2. las respuestas del revisor quedan inmutabilizadas/selladas;
3. los resultados del motor se revelan;
4. el autor redacta la adjudicación;
5. solo ahora el revisor recibe el borrador de adjudicación;
6. el revisor tiene derecho de anotación: `AGREE` / `DISAGREE` / `QUALIFY`;
7. la anotación del revisor se publica intacta;
8. el autor no puede sobrescribir ni reformular la anotación del revisor.

No se requiere veto del revisor. Se permite el desacuerdo explícito, p. ej.:

```text
author_classification = CORPUS_ERROR
reviewer_annotation   = DISAGREE: INTERPRETATION_ERROR
final_status          = ADJUDICATION_DISPUTED
```

No se fuerza un consenso falso. Los desacuerdos se clasifican, donde esté soportado, en la taxonomía existente (alineada con `docs/LEGAL-ASSURANCE-MODEL.md`):

- `CLASS_1_ENGINE` (error de implementación / divergencia semántica)
- `CLASS_2_CORPUS` (error estructural del corpus / validez normativa)
- `CLASS_3_INTERPRETATION` (error de interpretación legal)
- `CASE_DESIGN`
- `SCOPE`
- `OTHER` / `UNRESOLVED`

## 12. Holdout — tripwire

```text
HOLDOUT_N = 4
ROLE = TRIPWIRE_ONLY
```

Un holdout verde de 4 casos NO es evidencia positiva de validación. Semántica pre-registrada:

| Resultado holdout | Efecto |
|---|---|
| `HOLDOUT_PASS` | sin reclamación adicional de accuracy; NO "4/4 demuestra validez" |
| `HOLDOUT_CRITICAL_FALSE_PERMISSION` | `M7_FAIL`; el holdout no puede reutilizarse |
| `HOLDOUT_CRITICAL_SCOPE_OVERREACH` | `M7_FAIL`; el holdout no puede reutilizarse |
| `HOLDOUT_OTHER_MATERIAL_STRONG_DISAGREEMENT` | `M7_INCONCLUSIVE`, salvo que aplique otra condición FAIL pre-registrada |
| `HOLDOUT_CONSERVATIVE_FALSE_NEGATIVE` | se registra; NO transforma el holdout en evidencia positiva |

Custodia: los 4 casos del holdout NO deben ser seleccionados/expuestos por el autor de la remediación si puede evitarse. Custodia preferente: el revisor independiente o un custodio humano neutral selecciona y sella 4 casos del marco normativo pre-registrado. Antes del freeze se compromete solo un manifest:

```text
HOLDOUT_N = 4
HOLDOUT_CUSTODIAN = ...
HOLDOUT_COMMITMENT_SHA256 = <hash real>
SEALED_AT = ...
STATUS = SEALED
```

Mientras no exista un compromiso real:

```text
HOLDOUT_COMMITMENT_SHA256 = PENDING
STATUS = PENDING
M7_PROTOCOL_FREEZE = NO
```

Los contenidos secretos del holdout NO se almacenan en el repositorio público antes de que el tripwire deba ejecutarse.

Declaración obligatoria en protocolo e informe:

> "The SHA-256 commitment demonstrates non-substitution after commitment. It does NOT prove independent sample design and does NOT prove that the author was ignorant of the normative strata."

El hashing NO crea ceguera; no se finge que lo haga.

## 13. Terminación y stop-loss

```text
MAX_REMEDIATION_ROUNDS = 2
EXECUTION_DEADLINE = FREEZE_DATE + 30 días naturales
```

El reloj de 30 días arranca en el freeze real del protocolo; por eso el reclutamiento debe ocurrir ANTES del freeze. Si un evento externo exige prórroga, se registra una `PROTOCOL_DEVIATION`. Nunca se mueve el deadline silenciosamente. No se sigue remediando solo porque el piloto no se haya puesto verde.

## 14. Desviaciones de protocolo

Registradas en `protocol-deviations.md`. Estado inicial: `NO_DEVIATIONS_AS_OF_PROTOCOL_CANDIDATE`; al freeze: `NO_DEVIATIONS_AS_OF_FREEZE`. Toda desviación posterior registra: fecha, proposed_by, descripción, razón, si los resultados ya eran visibles, efecto esperado sobre validez/sesgo, y disposición. NO se modifica la metodología silenciosamente después de ver resultados.

## 15. Lo que esta validación NO prueba

M7 NO:

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

Está PROHIBIDO el lenguaje genérico tipo "AlRaso ha sido legalmente validado". Incluso tras un PASS, el lenguaje permitido queda acotado por caso/ámbito/fecha (sección 17).

## 16. Puerta de congelación — 14 condiciones

El protocolo solo puede etiquetarse `FROZEN` cuando TODAS sean demostrablemente verdaderas:

1. [1] marco normativo de casos existe y está anclado en fuentes
2. [2] la regla de muestreo es independiente de los resultados del motor
3. [3] el conocimiento del autor de la muestra está revelado
4. [4] la inmutabilidad de R0 está definida
5. [5] existe un holdout sellado con compromiso SHA real
6. [6] el holdout es explícitamente tripwire-only
7. [7] el paquete del revisor es ciego y solo con fuentes primarias
8. [8] la conclusión jurídica fuerte está definida operativamente
9. [9] la matriz de pérdida asimétrica está congelada
10. [10] las celdas `OUT_OF_SCOPE` están definidas
11. [11] los acuerdos factuales `UNDETERMINED` quedan excluidos del acuerdo legal
12. [12] el derecho de anotación del revisor sobre la adjudicación está aceptado
13. [13] `MAX_REMEDIATIONS=2` + deadline duro + FAIL/INCONCLUSIVE son resultados válidos
14. [14] limitaciones de la afirmación y sesgos residuales están explícitamente publicados

Además, antes del freeze:

```text
reviewer selected = YES
qualification verified = YES
independence verified = YES
workload accepted = YES
holdout custody/commitment = REAL, not placeholder
```

Si falta UNA sola condición: `M7_PROTOCOL_FREEZE = NO`. La puerta NO se debilita.

## 17. Resultados terminales y lenguaje permitido

```text
M7_PASS
M7_FAIL
M7_INCONCLUSIVE
M7_ABORTED_PROTOCOL_DEVIATION
```

Los cuatro son publicables y legítimos. El lenguaje del informe queda acotado por caso/ámbito/fecha y estado de conocimiento; p. ej.: "en los 24 casos del main set y 4 del holdout, con las fuentes citadas, a las fechas indicadas, la revisión jurídica independiente no encontró falsos permisos críticos". Nada más allá de eso.
