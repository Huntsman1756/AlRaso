# Spike A — Axiom rules engine (desechable)

Hipótesis: ¿el paradigma RuleSpec de Axiom representa un caso vivac/pernocta con hechos geoespaciales, versionado temporal y fail-closed?

## Qué hay aquí
- `picos-spike.yaml` — módulo RuleSpec SINTÉTICO (valores placeholder, no es derecho codificado real). Se copió a `rulespec-es/es/policies/vivac/picos-spike.yaml` en un clon temporal para ejercitar IDs duraderos `es:policies/vivac/picos-spike#...`.
- `spike-a-req-case2_bivouac_above_threshold.json` / `spike-a-res-case2_...json` — ejemplo de petición explain y respuesta con traza.
- 8 casos ejecutados (resumen completo en `VIVAC-TECHNICAL-DISCOVERY.md` §E).

## Cómo se ejecutó (entorno sin linker MSVC)
```bash
docker run --rm -v <tmp>:/work -w /work/axiom-rules-engine rust:1-slim \
  cargo run --release -- compile \
    --program /work/rulespec-es/es/policies/vivac/picos-spike.yaml \
    --rulespec-root /work/rulespec-es --output /work/spike-a.compiled.json

docker run --rm -v <tmp>:/work rust:1-slim \
  /work/axiom-rules-engine/target/release/axiom-rules-engine \
  run-compiled --artifact /work/spike-a.compiled.json < spike-a-req-case2.json
```

## Hallazgos clave
1. Selección de versión por valid time funciona (period 2021 vs 2023, umbrales 1600/1800).
2. `assessment_date` se valida y hace eco, NO filtra versiones → bitemporalidad no implementada.
3. Hecho faltante → error duro (`missing input 'altitude_m'`), no interpretación silenciosa.
4. No existe período `day` (solo month/benefit_week/tax_year/custom con `name`).
5. Outputs exigen ID duradero completo; bare names rechazados.
6. Fuera del ámbito modelado → `exactly_one` falla → el wrapper debe mapear a UNDETERMINED.
7. Traza explain auditable (`executed_expression`, `parameter_reads`, `dependencies`).
8. Engine Apache-2.0; `rulespec-es` SIN licencia; no hay binarios Windows publicados.
