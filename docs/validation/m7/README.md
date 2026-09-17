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

## Execution readiness

Todo lo resoluble por herramientas está listo; la ejecución queda bloqueada SOLO por los dos pasos humanos de abajo.

| Herramienta | Rol |
|---|---|
| [tooling/m7_seal_holdout.py](../../../tooling/m7_seal_holdout.py) | sellado del holdout por el custodio humano (commitment SHA-256 sobre la forma canónica de los 4 casos) |
| [tooling/m7_reviewer_bundle.py](../../../tooling/m7_reviewer_bundle.py) | construcción + verificación del paquete ciego del revisor (con escaneo de ceguera y manifest sha256) |
| [tests/test_m7_readiness.py](../../../tests/test_m7_readiness.py) | puerta automatizada: determinismo del sellado, integridad del bundle, ceguera del main set |

Comandos:

```bash
# 1) Custodio humano (en su máquina, con los 4 casos SECRETOS fuera del repo):
python tooling/m7_seal_holdout.py \
    --input holdout-cases.json \
    --custodian "Nombre Custodio <contacto>" \
    --output holdout-commitment.json

# 2) Autor (genera y verifica el paquete ciego del revisor):
python tooling/m7_reviewer_bundle.py build  --out-dir <dir-paquete>
python tooling/m7_reviewer_bundle.py verify --dir <dir-paquete>
```

Bloqueos restantes, exclusivamente humanos:

1. **Custodia del holdout.** Un custodio humano neutral (o el revisor independiente) selecciona y sella 4 casos desde `normative-case-frame-v1.md` con el comando (1). El custodio devuelve SOLO `HOLDOUT_CUSTODIAN`, `HOLDOUT_COMMITMENT_SHA256` y `SEALED_AT`, que el autor registra en `holdout-manifest-v1.json` (`STATUS = SEALED`). Los contenidos sellados NUNCA se commitean al repositorio público.
2. **Revisor independiente verificado.** Selección y verificación privada según la checklist de protocol-v1.md sección 4.1: `qualification_verified`, `independence_verified`, `conflict_of_interest_checked`, `estimated_effort_accepted`, `blind_review_protocol_accepted`, `adjudication_annotation_right_accepted` — todos YES con evidencia humana real. El paquete del revisor se genera con el comando (2) y se entrega tras la verificación.

Mientras cualquiera de los dos falte:

```text
REVIEWER_STATUS = PENDING
HOLDOUT_COMMITMENT_SHA256 = PENDING
M7_PROTOCOL_FREEZE = NO
```
