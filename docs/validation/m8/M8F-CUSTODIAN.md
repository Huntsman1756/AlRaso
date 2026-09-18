# M8-F — Instrucciones operativas para el CUSTODIO humano

> Documento para la persona real que sella el holdout ciego de Madrid.
> El implementador NO ve el fichero de casos. Protocolo completo:
> `M8-HOLDOUT.md`. Preregistro: `M8-PREREG.md`.
>
> **Secuencia preregistrada**: sellado → adjudicación de los 4 casos
> Madrid → publicación de APPROVE → ejecución M8-F (una sola vez) →
> M8-G. El sellado ocurre ANTES de la adjudicación: los casos no deben
> construirse con conocimiento de las decisiones de revisión.

## 0. Regla de ceguera

- El custodio **no debería ser la misma persona que adjudica** los casos
  regulatorios M8 (Guadarrama, PRCAM, PRCMG, PRSE), si es posible. Los
  `expected_class` son la información que hace ciega la evaluación:
  quien los conoce puede ajustar reglas hacia ellos sin querer.
- Si la misma persona debe hacer ambos papeles, seleccionar los casos y
  sellar ANTES de abrir cualquier `review_case.json`, y no revisar el
  fichero de casos durante la adjudicación.
- Limitación honesta (misma advertencia del tooling): el commitment
  demuestra **no-sustitución** tras el sellado. NO demuestra diseño
  independiente de la muestra ni ignorancia del implementador.

## 1. Fichero secreto `m8f-cases.json`

Crear **FUERA del repositorio** (p.ej. `F:\_Proyectos\m8f-cases.json`
o cualquier ruta no versionada). Nunca bajo `AlRaso\`.

Formato: array JSON (también admite `{"cases": [...]}`) de objetos:

```json
{
  "case_id": "M8F-01",
  "lat": 40.837697,
  "lon": -3.958714,
  "date": "2026-10-03",
  "activity": "VIVAC_AL_RASO",
  "stratum": "vivac_zone_anexo3",
  "expected_class": "PERMITTED",
  "notes": "justificación del custodio (opcional)"
}
```

Campos obligatorios y validados por el seal:

| Campo | Requisito |
|---|---|
| `case_id` | string único no vacío |
| `lat`, `lon` | numéricos, EPSG:4326, dentro de la caja CAM (lat 39.7–41.3, lon −4.7…−2.9) — sanity check, no gate |
| `date` | `YYYY-MM-DD` válida |
| `activity` | exactamente `"VIVAC_AL_RASO"` (ámbito M8) |
| `stratum` | uno de los 12 estratos de §3 |
| `expected_class` | `PERMITTED` \| `CONDITIONAL` \| `BLOCKED` \| `UNDETERMINED` \| `UNKNOWN` |
| `notes` | opcional |

**Mínimo: ≥1 caso por cada uno de los 12 estratos** (el seal aborta si
falta alguno). Recomendado 20–30 casos totales (2–3 por estrato).

Estratos obligatorios (verbatim de `M8-HOLDOUT.md` §3):
`pn_guadarrama_interior`, `vivac_zone_anexo3`, `zpp`,
`hole_or_exclusion`, `boundary`, `pr_cuenca_alta_manzanares`,
`pr_curso_medio_guadarrama`, `pr_sureste`, `territorio_general`,
`temporal_variant`, `expected_undetermined`, `expected_unknown`.

## 2. Qué es público y qué es secreto

| Secreto (fuera del repo, nunca compartido antes de la ejecución) | Público (entra al repo vía manifest) |
|---|---|
| `lat`, `lon`, `date` de cada caso | `case_id`s |
| `stratum` asignado a cada caso | conteos por estrato (`strata_counts`) |
| `expected_class` | `case_count`, `custodian`, `sealed_at` |
| `notes` | `holdout_sha256` (el commitment) |
| el fichero completo | |

## 3. Sellado (comando único)

```bash
cd F:\_Proyectos\AlRaso
python tooling/m8_holdout_seal.py \
    --input F:\_Proyectos\m8f-cases.json \
    --custodian "Nombre Apellido, rol/contacto" \
    --output F:\_Proyectos\m8f-commitment.json
```

Exit 0 = sellado; exit 1 = validación fallida (corregir el fichero y
resellar — el commitment anterior queda inválido si cambian los casos).

El seal escribe `m8f-commitment.json` **sin contenido de casos** (solo
los campos públicos de §2) e imprime los valores a devolver:

```text
CUSTODIAN            = ...
COMMITMENT_SHA256    = ...
SEALED_AT            = ...
CASE_COUNT           = ...
STRATA_COUNTS        = {...}
STATUS               = SEALED
```

## 4. Registrar el commitment (público)

Copiar esos campos en `docs/validation/m8/holdout-manifest-v1.json`
(sustituir los `PENDING`). Ese fichero sí se commitea.

Baseline contra el que se evaluará (identificado por commit+hash, no por
descripción):

```text
BASELINE_TAG         = m8-pre-human  (commit 65e6a67)
RESOLVER_VERSION     = 0.3.0rc1-m8d
SCHEMA_VERSION       = m1r3
LAYERS_MANIFEST_SHA256 = 788b05f31f90ec3d1be44b1dde6d3c08bcd6703c11a08e4e08c9380e1839f8e6
```

Nota: `main` ha avanzado a `1c02685` (paquetes de evidencia es-pn);
el código del resolver es idéntico al del tag — los commits posteriores
solo añadieron evidencia, no código. Si cualquier commit tocara
`alraso/resolver.py`, `alraso/spatial.py`, `alraso/geojson_provider.py`,
`alraso/domain.py`, `alraso/engine.py`, `alraso/bitemporal.py`,
`alraso/schema.py`, `alraso/ingest/ordesa.py` o las capas hash-pinned,
el run debe declararse inválido y tratarse como nueva evaluación.

## 5. Garantías que el sistema ya implementa (verificado en código)

- **Commitment detecta cualquier cambio**: `sha256` sobre la forma
  canónica de la lista (`json.dumps(sort_keys=True, separators=(",",":"))`).
  Editar un campo, añadir/quitar/reordenar casos → digest distinto → el
  runner aborta (exit 1) con `PROTOCOL VIOLATION`.
- **Doble check**: el runner también compara la lista ordenada de
  `case_id`s contra el commitment.
- **Formato no altera el hash**: espacios/orden de claves del fichero no
  afectan (la canonicalización es byte-estable).
- **Baseline identificado**: el runner registra `resolver_version`,
  `schema_version` y `manifest_sha256` en el informe; las capas del
  manifiesto están hash-pinned individualmente (`load_manifest_provider`
  aborta ante hash mismatch).
- **Boundary**: un caso `boundary` con determinación limpia no-flagged
  se reporta como `protocol_failures`.

## 6. Checklist del custodio antes de devolver el commitment

- [ ] `m8f-cases.json` está FUERA del repo (verificar: no aparece en
      `git status` ni en ninguna ruta bajo `AlRaso\`)
- [ ] ≥1 caso por cada uno de los 12 estratos; `case_id`s únicos
- [ ] coordenadas reales comprobadas contra las capas oficiales o un
      mapa (el seal solo valida la caja CAM, no la pertenencia a estratos)
- [ ] estrato `boundary`: coordenada sobre una arista real de una capa
      oficial (p.ej. un vértice del GeoJSON hash-pinned)
- [ ] estrato `hole_or_exclusion`: coordenada dentro del hueco real de
      la ZPP-CM u otro anillo interior
- [ ] estrato `temporal_variant`: fecha con restricción temporal
      relevante documentada en `notes`
- [ ] expected outcomes NO escritos en ningún fichero del repo
- [ ] el custodio no usará los `expected_class` para orientar las
      adjudicaciones regulatorias
- [ ] `git status` del repo: solo cambia `holdout-manifest-v1.json`

## 7. Ejecución (después de la adjudicación y publicación, UNA vez)

```bash
python tooling/m8_holdout_run.py \
    --cases F:\_Proyectos\m8f-cases.json \
    --commitment F:\_Proyectos\m8f-commitment.json \
    --manifest discovery/evidence/m8-madrid-layers.json \
    --corpus <published_fixture_1.json> [--corpus ...] \
    --knowledge-date YYYY-MM-DD \
    --out docs/validation/m8/holdout-results.json
```

## 8. Si el run da FAIL

- **Conservar el informe completo** (incluidos los fallos) — es
  evidencia, no un defecto a ocultar.
- **Prohibido recalibrar** reglas, umbrales, precedencias o geometría
  contra los resultados del holdout.
- Remediación = trabajo separado: diagnosticar causa raíz (regla
  defectuosa adjudicada, geometría, gap del modelo, expectativa del
  custodio errónea) y decidir.
- Si la remediación requiere un cambio material del resolver/geometría/
  clases, el run queda **inválido** y la nueva evaluación usa casos
  nuevos sellados de nuevo (no se "re-ejecuta" el mismo holdout).
- Un `expected_class` del custodio también puede estar mal: los
  mismatches se revisan caso a caso, pero el criterio de corrección es
  la norma y el corpus publicado, no el holdout.
