# MILESTONE-1 — Pure Resolver (CLI, sin mapa): estado

**Fecha:** 2026-09-05
**Alcance de referencia:** discovery §L "Milestone 1" (BD bitemporal, ingesta de evidencia
de un piloto, wrapper Axiom, resolve() con salida completa, suite de replay temporal,
casos Ordesa pre/post D 16/2022).

## Estado de cada entregable

| Entregable | Estado | Dónde / evidencia |
|---|---|---|
| BD bitemporal (SourceDocument, LegalFragment, SpatialScope, LegalRuleVersion, RuleRelation) | **HECHO** | `alraso/schema.py` (SQLite con triggers que PROHIBEN UPDATE/DELETE + DDL PostgreSQL/PostGIS de producción), `alraso/bitemporal.py` |
| Selección de versión por dos ejes (valid x system, linaje-aware, gaps) | **HECHO** | `BitemporalStore.select`; escenarios Spike C completos en `tests/test_bitemporal.py` |
| Ingesta evidencia piloto Ordesa | **HECHO** (camino de aceptacion) | `alraso/ingest/ordesa.py` sobre el fixture con URLs canonicas oficiales; la ingesta de red automatica (fetcher + snapshots) es el siguiente bloque de trabajo con el patron F2.4 |
| Wrapper Axiom (swappable, cache por knowledge-state) | **HECHO** | `alraso/engine.py` (protocolo + evaluador propio) + `alraso/engine_axiom.py`; evidencia binario real en `discovery/spikes/m1-axiom-integration/RESULTS.txt` |
| resolve() con salida completa | **HECHO** | `alraso/resolver.py` -> legalStatus, knowledgeStatus, applicableScope, conditions, ruleVersions, evidence, precedenceTrace, unresolvedConflicts, warnings, decisionReason |
| Suite replay temporal (Spike C industrializado + STALE) | **HECHO** | `tests/test_replay.py` (record determination -> late discovery -> `retro_audit` flag STALE) |
| Casos Ordesa pre/post D 16/2022 | **HECHO** | `tests/test_resolver_ordesa.py` + CLI demo (abajo) |

## Pruebas ejecutadas (2026-09-05)

- Host Windows: `python -m pytest -q` -> **23 passed, 2 skipped** (los 2 skipped son los
  de motor Axiom real, que exigen binario Linux).
- Docker (binario Axiom real v d142c64 + Python 3.12): **25 passed** — incluye
  `test_axiom_agrees_with_wrapper_selection_on_ordesa` (el motor de verdad coincide con la
  seleccion del wrapper: 2021 PERMITTED / 2023 PROHIBITED) y
  `test_compile_cache_is_content_addressed` (mismo knowledge-state no recompila).
- CLI real end-to-end sobre `ordesa.db`: 2021-07-15 -> PERMITTED (version RD 409/1995
  vigente hasta 2022-02-08); 2023-06-15 -> PROHIBITED (D 16/2022 desde 2022-02-09);
  salida JSON con evidencia canonica (BOA/pnomp.es/BOE) y traza de 5 etapas.

## Propiedades criticas verificadas por tests

- **Fail-closed en 6 caminos**: actividad fuera de vocabulario; ambito no modelado; hueco
  temporal (knowledge termina antes de la fecha); hecho ausente en regla condicional;
  conflicto sin OVERRIDES verificado por humano; punto fuera de todo ambito. Ninguno
  produce PERMITTED.
- **Append-only a nivel de BD**: UPDATE y DELETE sobre `legal_rule_version` son rechazados
  por triggers (no es una convencion, es una garantia).
- **Late discovery correcta en los dos mundos**: con conocimiento de 2023 responde
  PERMITTED (correcto-entonces); con conocimiento de 2028 responde PROHIBITED
  (correcto-ahora); el replay marca la determinación antigua STALE.
- **Motor intercambiable**: resolver no conoce Axiom; el `OwnEvaluatorAdapter` da el mismo
  resultado end-to-end y permite ejecutar todo sin el motor externo.

## Pendientes del alcance M1 para "piloto completo" (trabajo de ingesta/datos, no arquitectura)

1. Geometria oficial del sector Ordesa (paso 4 del plan spatial-review) y carga en PostGIS.
2. Fetcher con snapshots WORM + hash + registro de eventos (patron F2.4 COPY_PATTERN).
3. Deep-link BOA D 16/2022 y PDFs oficiales anclados por hash (reemplazar el placeholder
   "BOA de 8-02-2022" del fixture por URL canonica exacta).
4. Versiones de regla para el resto de modalidades del piloto (PERNOCTA_REFUGIO,
   ACAMPADA por sectores, TARP) con revisión humana.

## Tokens

```text
M1_STATUS=CORE_COMPLETE_PILOT_ACCEPTANCE_PASS
RESOLVER_CONTRACT=COMPLETE (legalStatus, knowledgeStatus, applicableScope, conditions,
ruleVersions, evidence, precedenceTrace, unresolvedConflicts, warnings, decisionReason)
ORDESA_CASES=2021->PERMITTED; 2023->PROHIBITED (CLI+tests, fixture canonico)
BITEMPORAL_GUARANTEES=append-only-db-enforced; late-discovery-replay-verified; STALE-audit-ok
FAIL_CLOSED_TESTED=6 caminos, ninguno produce PERMITTED
ENGINE_INTEGRATION=AXIOM_REAL_BINARY 25/25 PASSED (docker); evaluador propio paridad completa
TESTS=23 passed + 2 skipped (host); 25 passed (docker, motor real)
NEXT=geometria oficial sector Ordesa + fetcher/snapshots WORM + deep-link BOA + modalidades restantes
```
