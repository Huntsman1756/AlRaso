# ALRASO — M1 Remediation Evidence (SAFETY CONTRACT CLOSURE)

Fecha: 2026-09-05 · Base auditada: repo sin commits previos (baseline = working tree
audited F01–F09) · `RESOLVER_VERSION=0.2.0-remediation` · `SCHEMA_VERSION=m1r2` ·
`RULESPEC_CONTRACT_VERSION=rulespec/v1+m1r1`

## Resultado global

| Gate | Resultado |
|---|---|
| Suite hermetica (host, Python 3.11.15, 0 dependencias) | **203 passed, 5 skipped** (los 5 requieren binario Axiom) |
| Suite completa con Axiom real (Docker, python:3.12-slim, `run-docker.ps1`) | **214 passed, 0 skipped** |
| Clean-wheel gate (`tooling/clean_wheel.ps1`, venv limpio fuera del checkout) | **PASS** (build, install, import desde site-packages, CLI help, fixture empaquetado, resolve PERMITTED/PROHIBITED, safety smoke "unreviewed rule cannot permit") |
| Identidad binario Axiom | SHA-256 `d4078c4659344c7ac07cc53d5e512e5dffb74c0e08f06885aeb6b7d38d93f229` == lock (v0.2.2 commit `d142c64`) |
| Falsos PERMITTED | **0** (barridos adversariales en `tests/test_invariants.py`) |

## Finding por finding

| ID | Before (audit) | Fix | Verificacion | Status |
|---|---|---|---|---|
| F01 | Reglas sin publicar/validar (solo `review_status` string libre) podian producir PERMITTED | `alraso/eligibility.py`: puerta unica; publishable `{VERIFIED, PUBLISHED}` + `legal_review_complete` + `spatial_review_complete` (False=excluye, None=n/a) + evidencia resolvable + efecto conocido + condicion validable; rechequeo del invariante usa el mismo modulo | `tests/test_eligibility.py` (todas las combinaciones), `test_invariants.py::test_adding_ineligible_permitted_rule_does_not_change_result`, safety smoke del clean wheel | CLOSED |
| F02 | Motor externo podia devolver identidades ajenas / capacidades no declaradas | `EngineCapabilities` obligatorio + `check_capable` ANTES de invocar; cada `EngineResult` pasa por compatibilidad declarada; el motor solo ve versiones ya elegibles; Axiom acotado a un subconjunto honesto (ver R2) con `AXIOM_STATUS=EXPERIMENTAL_ADAPTER`, `AXIOM_PARITY=NOT_PROVEN` | `tests/test_engine_contract.py` (bateria compartida Own/Axiom, 214 en Docker con binario real), `tests/test_axiom_scoping.py` (hermetico), `test_invariants.py::test_capability_mismatch_never_permitted` | CLOSED (paridad Axiom sigue NOT_PROVEN por diseno) |
| F03 | Multi-ambito con `_pick_scope` (ultimo/primero gana) | Se evaluan TODOS los ambitos contenedores; orden canonico `scope_id`; composicion determinista; proveedor espacial detras de `SpatialProvider` | `tests/test_spatial_composition.py` (permutaciones de orden -> mismo resultado canonico), `test_invariants.py::test_same_canonical_result_under_every_scope_order`, `test_resolver_ordesa.py` verifica ausencia de `_pick_scope` | CLOSED |
| F04 | Precedencia first-wins sobre lista sin semantica de conflicto; relaciones sin bitemporalidad ni revision | `rule_relation_version` bitemporal (effective/recorded, review, human_verified); resolucion grounded estratificada; ciclos -> `UNDETERMINED+CONFLICTING`; relacion no elegible = inerte (no cambia resultado) | `tests/test_precedence.py`, `test_invariants.py` (conflicto a 3 bandas, relaciones no elegibles inertes, barrido adversarial) | CLOSED |
| F05 | Replay sin query canonica; STALE solo por fecha | Tabla `determination` con `canonical_query` canonico + basis (scope/rule/relation/evidence ids) + `knowledge_state_hash`; drift tipado (`LEGAL_STATUS_CHANGED`->STALE, `KNOWLEDGE_STATUS_CHANGED`, `RULE_SET_CHANGED`, `EVIDENCE_CHANGED`, `PRECEDENCE_CHANGED`, `SPATIAL_SCOPE_CHANGED`, `FACT_SOURCE_CHANGED` sin productor en M1, `NO_MATERIAL_CHANGE`) | `tests/test_replay.py` (round-trip canonico por cada tipo de drift, determinismo byte a byte) | CLOSED |
| F06 | Feenas/booleanos condicionados debiles; hechos con strings; condiciones malformadas toleradas | `alraso/validation.py`: fechas ISO estrictas antes de comparar, booleanos solo `bool/0/1` (`"true"` rechazado), efectos/estados por vocabulario cerrado, AST validado (hechos declarados, operadores por capability) | `tests/test_validation.py`, `test_failclosed.py` | CLOSED |
| F07 | Ingesta sin transaccion (estados parciales ante fallo); anidamiento roto | `store.transaction()` (joinable, rollback integro); `load_ordesa` entero en una transaccion; duplicado -> `IntegrityError` sin huella parcial | `test_storage_integrity.py` (atomicidad ingesta, nesting, rollback por excepcion) | CLOSED |
| F08 | Sin FK activas; append-only no forzado; integridad no verificada | `PRAGMA foreign_keys=ON` por conexion + `integrity_check` en `validate()`; triggers append-only (no UPDATE/DELETE) en TODAS las tablas normativas incl. `determination` | `test_storage_integrity.py::test_append_only_protection_on_every_normative_table` (recorre el catalogo real), `test_temporal_boundaries.py` | CLOSED |
| F09 | Fixture fuera del paquete (`../discovery`), extras/identidades sin declarar ni fijar | fixture empaquetado en `alraso.resources` via `importlib.resources` (copia discovery preservada como evidencia historica); `pyproject` con package-data + extras `axiom/postgis/dev`; `tooling/DEPENDENCIES.lock.json` con pines (Python, pytest, PyYAML, Axiom v0.2.2/d142c64/sha256); gate reproducible | `tests/test_packaging.py` (6 checks estaticos incl. lock==constantes), ejecucion real `tooling/clean_wheel.ps1` = PASS | CLOSED |

## Decisiones de contrato fijadas en esta remediacion

- Convencion temporal: valido `[effective_from, effective_to]` CERRADO; sistema
  `[recorded_at, recorded_until)` semiabierto. Comprobado en bordes exactos
  (`test_temporal_boundaries.py`).
- Conflicto ya no es modalidad de `legalStatus`: `UNDETERMINED + CONFLICTING`.
- Modo coordenadas: `PERMITTED` exige ambito con geometria y revision espacial
  publicable; el fixture Ordesa declara `SPATIAL_REVIEW_PENDING_GEOMETRY`, por lo
  que la aceptacion canónica usa `spatial_scope_id` (atribucion humana).
- Axiom: unica version sin condicion con efecto PERMITTED/PROHIBITED; condiciones
  -> `UnsupportedEngineCapability` ANTES de tocar el subprocess. Paridad NO
  afirmada. El adapter NO es por defecto (`DEFAULT_ENGINE=own`).
- PostgreSQL/PostGIS: `POSTGRES_NORMATIVE_STORE_STATUS=NOT_IMPLEMENTED`; el DDL
  es referencia no verificada.

## Gates reproducibles

1. `python -m pytest -q` (hermetico, sin red).
2. `powershell -File tooling/clean_wheel.ps1` (build + venv limpio + smoke).
3. `powershell -File discovery/spikes/m1-axiom-integration/run-docker.ps1`
   (binario Linux v0.2.2, sha verificado contra el lock).
