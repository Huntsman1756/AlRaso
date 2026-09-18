# M8-F — Holdout ciego Madrid (preregistrado)

Estado: `M8_F_PREREG` · Sellado: `PENDING` (custodio humano)
Compromiso: `docs/validation/m8/holdout-manifest-v1.json`

> Preregistrado **antes** de implementar M8-E (point resolver) y antes de
> adaptar reglas candidatas. Igual que en M7: el commitment demuestra
> no-sustitución; NO demuestra diseño independiente ni ceguera del autor.

## 1. Formato de caso

Cada caso del holdout es un objeto secreto:

```json
{
  "case_id": "M8F-xx",
  "lat": 40.0,
  "lon": -4.0,
  "date": "2026-10-03",
  "activity": "VIVAC_AL_RASO",
  "stratum": "vivac_zone_anexo3",
  "expected_class": "PERMITTED|CONDITIONAL|BLOCKED|UNDETERMINED|UNKNOWN",
  "notes": "justificación del custodio (opcional)"
}
```

El fichero completo de casos es **SECRETO**: nunca entra al repo público ni
se comparte con el implementador antes de la ejecución del holdout. Solo el
commitment (sha256 canónico + ids + conteos por estrato) es público.

## 2. Clases esperadas (vocabulario preregistrado)

| Clase | Significado |
|---|---|
| `PERMITTED` | todas las condiciones determinantes evaluadas y satisfechas |
| `CONDITIONAL` | la norma permite si se cumplen condiciones que AlRaso no puede verificar automáticamente |
| `BLOCKED` | una regla aplicable lo impide |
| `UNDETERMINED` | hay cobertura pero la evidencia/regla no permite decidir |
| `UNKNOWN` | fuera de cobertura |

`CONDITIONAL` es el término preregistrado para la decisión de vocabulario de
§6 del prereg M8 (pendiente de adjudicación técnica en M8-E).

## 3. Estratos obligatorios

El holdout DEBE contener al menos un caso por cada estrato:

| Estrato | Descripción |
|---|---|
| `pn_guadarrama_interior` | dentro del PN-CM, fuera de zonas de vivac |
| `vivac_zone_anexo3` | dentro de un polígono oficial de vivac (Anexo III) |
| `zpp` | dentro de la ZPP-CM (interpretación abierta — candidato natural a UNDETERMINED/CONDITIONAL) |
| `hole_or_exclusion` | dentro de un hueco/exclusión de una geometría oficial |
| `boundary` | sobre una arista de geometría oficial (debe degradar, nunca determinación limpia) |
| `pr_cuenca_alta_manzanares` | PR Cuenca Alta del Manzanares |
| `pr_curso_medio_guadarrama` | PR Curso Medio del Guadarrama |
| `pr_sureste` | PR del Sureste |
| `territorio_general` | CAM fuera de todo ENP (regla general / laguna) |
| `temporal_variant` | mismo/loco punto en fecha con restricción temporal relevante (p.ej. periodo Peñalara) |
| `expected_undetermined` | caso cuya clase correcta es deliberadamente UNDETERMINED |
| `expected_unknown` | fuera de cobertura conocida |

Recomendado 20–30 casos totales (2–3 por estrato).

## 4. Procedimiento de sellado (HUMANO)

```bash
# 1. El custodio crea m8f-cases.json FUERA del repo con los casos reales.
# 2. Sellado:
python tooling/m8_holdout_seal.py \
    --input m8f-cases.json \
    --custodian "Nombre <contacto>" \
    --output m8f-commitment.json
# 3. El custodio devuelve los campos públicos y se guardan en
#    docs/validation/m8/holdout-manifest-v1.json
# 4. El fichero de casos queda fuera del repo hasta la ejecución.
```

La herramienta valida campos, estratos completos y rangos razonables de
coordenadas CAM, pero NO sustituye al criterio del custodio.

## 5. Reglas de evaluación (preregistradas)

- El holdout solo se ejecuta **después** de congelar el resolver M8-E.
- Prohibido ajustar reglas/umbrales/geometría contra los resultados del
  holdout. Si falla, el resultado se conserva como evidencia y la
  remediación es un trabajo separado.
- Un caso `boundary` que produzca una determinación limpia (no-flagged)
  cuenta como fallo.
- La métrica es por clase y por estrato; el gate es la explicación
  correcta de lo que el sistema sabe y no sabe, no un score global.

## 6. Ejecución (tras congelar el resolver)

```bash
python tooling/m8_holdout_run.py \
    --cases m8f-cases.json \
    --commitment m8f-commitment.json \
    --manifest discovery/evidence/m8-madrid-layers.json \
    --corpus <corpus_publicado.json> [--corpus ...] \
    --knowledge-date YYYY-MM-DD \
    --out docs/validation/m8/holdout-results.json
```

- El runner **recomputa el commitment** sobre la lista de casos y aborta
  (exit 1) si difiere del sellado — no-sustitución verificada en ejecución.
- `--corpus` ingiere únicamente corpus publicado; ejecutar sin corpus o
  con reglas `REVIEW_REQUIRED` produce `UNDETERMINED` (estado honesto
  pre-adjudicación, no un fallo del runner).
- Mapeo preregistrado: `PERMITTED`→PERMITTED, `CONDITIONAL`→CONDITIONAL,
  `PROHIBITED`/`AUTHORIZATION_REQUIRED`→BLOCKED, reason
  `NO_APPLICABLE_SCOPE`→UNKNOWN, resto→UNDETERMINED.
- Un caso `boundary` con determinación limpia no-flagged se reporta como
  `protocol_failures`.
- Los resultados son evidencia: los mismatches se conservan y la
  remediación es trabajo separado (§5).

## 7. Commitment

```json
// docs/validation/m8/holdout-manifest-v1.json
{
  "schema": "alraso-m8-holdout-manifest-v1",
  "status": "PENDING",
  "custodian": "PENDING",
  "commitment_sha256": "PENDING",
  "sealed_at": null,
  "case_count": null,
  "strata_counts": null
}
```
