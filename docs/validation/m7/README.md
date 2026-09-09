# Piloto de validación jurídica independiente M7 — índice

Protocolo pre-registrado (candidato) para validar jurídicamente las conclusiones del motor sobre casos concretos de vivac (`VIVAC_AL_RASO`) en el Parque Nacional de los Picos de Europa, mediante revisión humana independiente a ciegas y solo con fuentes primarias oficiales.

Estado: `M7_PROTOCOL_STATUS = CANDIDATE_READY_FOR_HUMAN_FREEZE_INPUT` · `M7_PROTOCOL_FREEZE = NO` · `LEGAL = FROZEN`

| Artefacto | Rol |
|---|---|
| [protocol-v1.md](protocol-v1.md) | protocolo completo (matriz de desacuerdo, R0/R1/R2, holdout, adjudicación, puerta de freeze de 14 condiciones) |
| [normative-case-frame-v1.md](normative-case-frame-v1.md) | marco normativo derivado de la estructura de la ley (estratos, clasificaciones, UNRESOLVED_FRAME_ITEM) |
| [sample-generation-v1.md](sample-generation-v1.md) | regla de selección + divulgación del sesgo del autor de la muestra |
| [main-set-v1.json](main-set-v1.json) | 24 casos, solo entradas neutras al revisor (sin datos del motor) |
| [holdout-manifest-v1.json](holdout-manifest-v1.json) | manifest del holdout tripwire (custodia y compromiso SHA-256, PENDING) |
| [reviewer-instructions-v1.md](reviewer-instructions-v1.md) | instrucciones para el revisor independiente |
| [reviewer-attestation-public.template.md](reviewer-attestation-public.template.md) | plantilla de attestation pública (PII mínima) |
| [r0-results.template.json](r0-results.template.json) | plantilla de resultados R0 (inmutables tras ejecución) |
| [validation-report-v1.template.md](validation-report-v1.template.md) | plantilla del informe final (creada antes de R0) |
| [protocol-deviations.md](protocol-deviations.md) | registro de desviaciones |

Prerrequisitos humanos pendientes (válidos, no fallos de implementación): selección/verificación del revisor independiente y custodia/compromiso real del holdout. La congelación requiere las 14 condiciones de protocol-v1.md sección 16.
