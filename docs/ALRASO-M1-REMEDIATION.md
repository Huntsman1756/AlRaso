# ALRASO — M1 Remediation Evidence (SAFETY CONTRACT CLOSURE)

Fecha: 2026-09-05 · Base auditada: repo sin commits previos (baseline = working tree
audited F01–F09) · `RESOLVER_VERSION=0.2.1-hardening` (la remediacion publico
`0.2.0-remediation`; la ronda final H1–H6 la sucedio) · `SCHEMA_VERSION=m1r2` ·
`RULESPEC_CONTRACT_VERSION=rulespec/v1+m1r1`

## Resultado global

| Gate | Resultado |
|---|---|
| Suite hermetica (host, Python 3.11.15, sin red ni motor externo) | **266 passed, 5 skipped** (los 5 requieren binario Axiom). Perfil de dependencias, dicho con precision: el **paquete** es stdlib-only; la suite usa ademas el extra opcional `alraso[axiom]` (PyYAML) para los 20 tests de proyeccion RuleSpec, que **se saltan con motivo explicito** si PyYAML no esta instalado (246 passed, 6 skipped). CI verifica los dos perfiles |
| Suite completa con Axiom real (Docker, python:3.12-slim, `run-docker.ps1`) | **271 passed, 0 skipped** |
| Clean-wheel gate (`tooling/clean_wheel.ps1`, venv limpio fuera del checkout) | **PASS** (build, install, import desde site-packages, CLI help, fixture empaquetado, resolve PERMITTED/PROHIBITED, y safety smoke F01+H1+H2+H3+H4 contra el paquete INSTALADO) |
| Identidad binario Axiom | SHA-256 `d4078c4659344c7ac07cc53d5e512e5dffb74c0e08f06885aeb6b7d38d93f229` == lock (v0.2.2 commit `d142c64`) |
| Falsos PERMITTED | **0** (barridos adversariales en `tests/test_invariants.py`: ejes F25 + ejes de endurecimiento H1–H4) |

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
| F08 | Sin FK activas; append-only no forzado; integridad no verificada | `PRAGMA foreign_keys=ON` por conexion + `store.verify_integrity()` (verificacion EXPLÍCITA, no un `validate()` imaginario): `PRAGMA integrity_check` + `foreign_key_check` + triggers append-only; los triggers prohíben UPDATE/DELETE en `source_document`, `legal_fragment`, `legal_rule_version`, `rule_relation_version`, `spatial_scope` y `determination`; `spatial_scope` admite EXCLUSIVAMENTE `UPDATE` de metadatos no normativos (p. ej. `relevance`/`review_status`) y aun así nunca `DELETE` — el detalle está documentado en `schema.py`, no se afirma "append-only absoluto en todas las tablas" | `test_storage_integrity.py::test_append_only_protection_on_every_normative_table` (recorre el catalogo real), `test_temporal_boundaries.py`, `test_eligibility.py::test_evidence_cannot_be_orphaned_under_a_determination` | CLOSED |
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

## Ronda final de endurecimiento (H1-H6) sobre la remediacion

Residuales detectados al re-revisar el arbol `0.2.0-remediation` (D1-D6) y su
cierre. No cambian el alcance: siguen en pie `DEFAULT_ENGINE=own`,
`AXIOM_STATUS=EXPERIMENTAL_ADAPTER`, `AXIOM_PARITY=NOT_PROVEN`,
`POSTGRES_NORMATIVE_STORE_STATUS=NOT_IMPLEMENTED`,
`M1_ORDESA_REAL_WORLD_SPATIAL=NOT_VALIDATED`.

| ID | Residual (D#) | Fix | Verificacion | Status |
|---|---|---|---|---|
| H1 (D2) | Dos versiones visibles del MISMO `rule_id` con ventanas de validez solapadas se resolvian por ranking implicito (seq/recorded_at) y podian producir PERMITTED | Prevencion en la ESCRITURA: `add_rule_version`/`transaction()` rechazan lineas simultaneamente visibles con contenido material distinto (`OverlappingRuleVersions`, reason `OVERLAPPING_RULE_VERSIONS`; el lote rechazado hace rollback). Defensa en la LECTURA: `_select_bitemporal` devuelve TODAS las lineas visibles (sin elegir), `overlapping_version_groups()` bloquea -> `UNDETERMINED+CONFLICTING+OVERLAPPING_RULE_VERSIONS`, y `verify_integrity()` lo declara corrupcion. Nada elige por "ultima", "seq mayor", "recorded_at mas reciente", "mas restrictiva" ni "mas permisiva" | `tests/test_hardening.py` (escritura, rollback en transaccion, linea legítima sucesora, 6 permutaciones de orden/`recorded_at` sobre volcado legado, doble alta identica, descubrimiento tardio), safety smoke del clean wheel, `test_invariants.py::test_adversarial_sweep_hardening_axes_never_permitted` | CLOSED |
| H2 (D3) | `legal_fragment.review_status` se guardaba pero no se fiscalizaba: evidencia sin verificar podia sostener una determinacion VERIFIED | `PUBLISHABLE_FRAGMENT_STATUSES={VERIFIED,PUBLISHED}` (eje de PROCEDENCIA, distinto del vocabulario de revision de reglas); default de `add_legal_fragment` pasa a `REVIEW_REQUIRED` (nada publicable por defecto); `eligibility` consulta `store.unpublishable_fragments()` -> `EVIDENCE_NOT_PUBLISHABLE`; fixture actualizado a `VERIFIED` explicito (no se relaj6 la produccion para admitir el fixture) | `tests/test_hardening.py` (default no publicable, regla VERIFIED sobre fragmento no publicable, control publicable, invariancia del resultado publico), `test_eligibility.py`, safety smoke | CLOSED |
| H3 (D4) | Un ambito aplicable sin reglas (o con hueco temporal) permitia PERMITTED con solo un aviso | `spatial_scope.relevance` (default `REGULATORY`, vocabulario cerrado, NUNCA inferido; `CONTEXT_ONLY` es declaracion humana): un ambito REGULATORY aplicable sin cobertura publicable bloquea el PERMITTED -> `UNDETERMINED+INCOMPLETE+INCOMPLETE_SCOPE_COVERAGE`; el gate anida en el invariant de PERMITTED. Semantica documentada: una respuesta RESTRICTIVA (PROHIBITED/AUTHORIZATION_REQUIRED) si puede sostenerse en una unica prohibicion positiva | `tests/test_hardening.py` (5 casos: sin cobertura, context-only, hueco temporal, prohibicion que se sostiene, vocabulario cerrado), safety smoke, sweep H3 | CLOSED |
| H4 (D1) | `facts` malformados (`"nope"`, `[]`, `7`, `None`, NaN) escapaban como traceback porque `query.as_dict()` correria antes de validar | Validacion estricta (`parse_date_strict`, `validate_facts`) ANTES de construir el resultado; `Query.safe_facts()` proyeccion que nunca lanza y siempre es JSON-segura (objetos/NaN/Inf se DESCRIBEN, no se copian); `record_determination` serializa con `allow_nan=False` | `tests/test_hardening.py` (12 entradas malformadas x 2 gates: resultado fail-closed + registro canónico JSON-estricto; hechos validos siguen evaluando y pasan literales) | CLOSED |
| H5 (D5) | La clave de cache de Axiom no incluia el binario: dos binarios que declaran la misma version compartian artefacto | Identidad de cache = contract + version + **SHA-256 del binario** + hash del RuleSpec; si la identidad del binario no es verificable, NO se reutiliza (ni se alimenta) la cache compartida: artefacto un-shot | `tests/test_axiom_scoping.py::test_cache_identity_includes_binary_sha`, `test_unverifiable_binary_identity_disables_cache_reuse`, `test_cache_hit_does_not_recompile` (ahora con identidad verificada) | CLOSED |
| H6 (D6) | Documentacion obsoleta (`MILESTONE-1.md` afirmaba paridad y `CORE_COMPLETE_PILOT_ACCEPTANCE_PASS`), test enganoso (`test_source_document_removal_breaks_resolution`: el estado que decia probar es inalcanzable por los triggers) y caminos de error sin cobertura explicita | `MILESTONE-1.md` marcado como historico/superado; contador y redaccion de F08 corregidos; test enganoso reescrito como prueba estructural real (los DELETE estan bloqueados, la evidencia huerfana solo puede venir de fuera del store y fail-closed); tests explicitos de `EngineTimeout`, `EngineNonZeroExit`, `EngineBinaryNotFound` y `SpatialResolutionError` | `tests/test_failclosed.py` (5 casos nuevos parametrizados), `test_eligibility.py`, `MILESTONE-1.md`, este documento | CLOSED |

### Decisiones de contrato que fija esta ronda

- **Doble alta materialmente identica**: no es un conflicto legal (el contenido
  material --efecto, condicion, evidencia-- es igual), asi que se permite, se
  colapsa a UNA descripcion canonica y se REPORTA (warning + stage
  `overlapping_versions_duplicates`). Lo que nunca se permite es elegir entre
  lineas de contenido DISTINTO.
- **Alcance del gate de cobertura (H3)**: solo bloquea afirmaciones de permiso
  (`PERMITTED`). Una prohibicion positiva es legalmente suficiente por si sola;
  exigir cobertura completa para PROHIBITED inventaria permisos por omision.
- `MILESTONE-1.md` es evidencia historica: su `M1_STATUS` y sus contadores NO
  describen el estado vigente.
