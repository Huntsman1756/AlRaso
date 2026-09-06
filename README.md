# AlRaso — Milestone 1 (remediation M1 closed + hardened)

Resolutor jurídico-geoespacial bitemporal (CLI, sin mapa). Piloto: Parque Nacional de
Ordesa y Monte Perdido. Base: `VIVAC-TECHNICAL-DISCOVERY.md` + `ALRASO-F2-CLOSURE.md`.
Evidencia de la remediación F01–F25 y de la ronda final de endurecimiento H1–H6:
`docs/ALRASO-M1-REMEDIATION.md`. `MILESTONE-1.md` es **histórico** (estado anterior a
ambas rondas; no citar sus tokens como vigentes).

## Qué es (y qué no es)

Una consulta `(actividad, lugar, activity_date, knowledge_date)` recibe una
determinación: `legalStatus ∈ {PERMITTED, AUTHORIZATION_REQUIRED, PROHIBITED,
UNDETERMINED}` + `knowledgeStatus ∈ {CURRENT, INCOMPLETE, STALE, CONFLICTING}` +
ámbitos aplicables, versiones de regla, evidencia, trazas y warnings.
`PERMITTED` solo es publicable si una versión de regla **elegible** (revisión
legal y espacial completas, evidencia resolvable **y con procedencia verificada**)
lo afirma de forma trazable, ningún ámbito **REGULATORY** aplicable queda sin
cobertura, y ninguna versión simultáneamente visible de la misma regla está en
desacuerdo; nunca se infiere desde la ausencia de información (fail-closed). Un
input malformado produce `UNDETERMINED` normalizado, jamás un traceback.

## Estatus de las capacidades (honesto)

| Capacidad | Estatus | Verificación |
|---|---|---|
| Almacén bitemporal SQLite append-only + triggers + FK | **IMPLEMENTED / VALIDATED** | `tests/test_storage_integrity.py` |
| Motor propio (pure-Python, sin deps) | **IMPLEMENTED / VALIDATED** | suite hermetica (276 passed; paquete stdlib-only, ver nota de perfiles abajo) |
| Contrato de motor (capabilities, identidad, invariante PERMITTED) | **IMPLEMENTED / VALIDATED** | `tests/test_engine_contract.py`, `tests/test_invariants.py` |
| Precedencia bitemporal (grounded, ciclos→conflicto) | **IMPLEMENTED / VALIDATED** | `tests/test_precedence.py` |
| Composición multi-ámbito con orden canónico | **IMPLEMENTED / VALIDATED** | `tests/test_spatial_composition.py` |
| Replay determinista + detección de drift | **IMPLEMENTED / VALIDATED** | `tests/test_replay.py` |
| Ingesta atómica fixture Ordesa | **IMPLEMENTED / VALIDATED** | `tests/test_storage_integrity.py` |
| Motor Axiom (binario real v0.2.2) | **EXPERIMENTAL_ADAPTER** — solo reglas simples sin condición; `AXIOM_PARITY=NOT_PROVEN` | battery compartida en Docker (271 passed, 0 skipped) |
| Ambigüedad de versiones de la misma regla (H1) | **IMPLEMENTED / VALIDATED** — refusado al escribir, `UNDETERMINED+CONFLICTING` al leer, corrupción declarada por `verify_integrity()` | `tests/test_hardening.py` (6 permutaciones de orden/`recorded_at`), sweep en `test_invariants.py` |
| Procedencia publicable de la evidencia (H2) | **IMPLEMENTED / VALIDATED** — fragmentos: default `REVIEW_REQUIRED`, publicable solo `{VERIFIED, PUBLISHED}` | `tests/test_hardening.py`, `tests/test_eligibility.py` |
| Relación de ámbito `REGULATORY`/`CONTEXT_ONLY` (H3) | **IMPLEMENTED / VALIDATED** — default `REGULATORY`, nunca inferido; permiso bloqueado si falta cobertura regulatoria | `tests/test_hardening.py`, safety smoke del clean wheel |
| Entradas malformadas (H4) | **IMPLEMENTED / VALIDATED** — 12 variantes (`facts="nope"`, `[]`, `7`, `None`, NaN…) → `UNDETERMINED` + registro JSON-estricto | `tests/test_hardening.py` |
| Identidad de caché Axiom incluye SHA-256 del binario (H5) | **IMPLEMENTED / VALIDATED** — sin identidad verificable no se reutiliza caché | `tests/test_axiom_scoping.py` |
| PostgreSQL / PostGIS como almacén normativo | **NOT_IMPLEMENTED** (`POSTGRES_NORMATIVE_STORE_STATUS`) | DDL de referencia solo; sin verificación |
| Geometría oficial con polyfill real | **DEFERRED** (M2) | fixture declara `SPATIAL_REVIEW_PENDING_GEOMETRY` |

## Estructura

```text
alraso/
  domain.py        vocabulario cerrado y objetos del contrato
  validation.py    validación estricta (fechas ISO, booleanos, efectos, condiciones)
  eligibility.py   única puerta de elegibilidad de versiones de regla
  precedence.py    grafo de precedencia bitemporal (semántica grounded)
  schema.py        DDL SQLite (append-only + triggers) + DDL PostgreSQL/PostGIS de referencia
  bitemporal.py    almacén append-only, transacciones, selección bitemporal
  conditions.py    AST de condiciones y evaluador total (sin eval)
  errors.py        taxonomía de fallos → reason_codes
  engine.py        protocolo EngineCapabilities + OwnEvaluatorAdapter
  engine_axiom.py  adapter Axiom EXPERIMENTAL (frontera acotada, cache atómico, sha pinning)
  spatial.py       protocolo SpatialProvider + impl in-memory (ray casting)
  ingest/ordesa.py carga transaccional del fixture empaquetado
  resolver.py      resolve(): pipeline completo + invariante PERMITTED + replay
  cli.py           CLI: load-ordesa | resolve | replay
  resources/       fixture de aceptación Ordesa (paquete incluido)
```

## Uso rápido

```powershell
python -m pip install .                 # núcleo sin dependencias
python -m alraso load-ordesa --db ordesa.db
python -m alraso resolve --db ordesa.db --activity VIVAC_AL_RASO `
    --scope ss-ordesa-sector-ordesa --date 2021-07-15 --knowledge 2023-06-15   # PERMITTED
python -m alraso resolve --db ordesa.db --activity VIVAC_AL_RASO `
    --scope ss-ordesa-sector-ordesa --date 2023-06-15 --knowledge 2023-06-15   # PROHIBITED (D 16/2022)
python -m alraso replay  --db ordesa.db --new-knowledge 2028-01-01             # determinaciones STALE
```

## Verificación

```powershell
python -m pytest -q                                   # 276 hermeticos (sin red ni motor externo)
powershell -File tooling/clean_wheel.ps1              # gate de instalacion limpia (F09 + H1-H4)
powershell -File discovery/spikes/m1-axiom-integration/run-docker.ps1  # + Axiom real: 281
```

Perfiles de la suite hermética (dichos con precisión, porque "0 dependencias" solo
es cierto para el **paquete**):

| Perfil | Instalado | Resultado |
|---|---|---|
| `audit` (el de la auditoría) | `pytest` + extra opcional `alraso[axiom]` (PyYAML), **sin** binario Axiom | 276 passed, 5 skipped (los 5 piden binario Axiom) |
| `stdlib-only` | sólo `pytest` | 256 passed, 6 skipped — el módulo de proyección RuleSpec se salta entero con motivo explícito |

CI ejecuta ambos perfiles en Python 3.11 y 3.12, más el gate de wheel limpio en
Linux y el script local `tooling/clean_wheel.ps1` en Windows (`.github/workflows/gates.yml`).
La integración con Axiom real es un workflow **manual y no bloqueante**
(`axiom-integration.yml`): prueba comportamiento contra el motor real, nunca paridad.

La evidencia de descubrimiento de geometría oficial para M1.1 está en
`docs/ALRASO-M11-VECTOR-DISCOVERY.md`: WFS/CSW de ICEARAGON
(`NO_OFFICIAL_VECTOR_SCOPE_FOUND`, re-verificable con
`tooling/m11_vector_discovery.py --verify`) y estudio del Anexo 11.5 de
cartografía del PRUG (clasificación `D2`: mapa oficial sin frontera sectorial
inequívoca y obsoleta). La rama **sectorial** de M1.1 queda cerrada en
`SPATIAL_EVIDENCE_INCOMPLETE`.

La rama **Góriz** de M1.1 (M1.1-C) sí cerró en **`OFFICIAL_SCOPE_LINK_PROVEN`
(gate A)**: la "Zona de acampada de alta montaña adyacente al refugio de Góriz"
queda identity-probada entre el WFS oficial de OAPN (registro estatal que cita el
`Decreto 49/2015` en el propio feature) y el WFS de ICEAragon (`ENP101_137`): IoU
`0.999844`, Hausdorff `0,005 m`. Es el primer ámbito con geometría oficial que
resuelve de extremo a extremo (dentro + condiciones → `PERMITTED`; sin condiciones o
fuera → `UNDETERMINED`, nunca prohibición sectorial). Ver
`docs/ALRASO-M11C-GORIZ-SCOPE.md`, `tooling/m11c_goriz_scope.evidence.json` y
re-verificación en vivo con `tooling/m11c_goriz_identity.py --verify`. Ninguna
consulta "fuera de Góriz" reabre la rama sectorial.

Estado M1.1: `M1.1_GORIZ_REAL_WORLD=VALIDATED` ·
`M1.1_ORDESA_SECTOR_SPATIAL=INCOMPLETE` · `FIRST_REAL_WORLD_E2E=PASS`. El objetivo
de M1.1 se considera cumplido; siguiente frente: **M2-A Picos de Europa**
(jurisdicciones autonómicas distintas dentro de un mismo parque).

Estado M2-A (discovery, 2026-09-06): **completada con Gate A condicionado**. El PRUG
de Picos se aprueba por tres decretos autonómicos en vigor simultáneo desde 2026-08-24
(BOCyL D 17/2025, BOPA D 21/2026, BOC D 57/2026; regla común art. 51: vivac de montaña
solo >cota 1.800 m, máx. 3 noches). Evidencia y digests en
`tooling/m2a_picos_discovery.evidence.json`, matriz jurisdicción×norma×geometría en
`docs/ALRASO-M2A-PICOS-DISCOVERY.md`, re-verificación en vivo con
`tooling/m2a_picos_verify.py` (sin red ⇒ `INCONCLUSIVE`, nunca OK falso). Ninguna regla
de Picos está en el runtime: la implementación Phase B requiere aprobar antes los
fixtures del documento.

**M2 — Product vertical slice (actual):** `python webapp/server.py` abre un mapa
(MapLibre vendorizado, cero dependencias nuevas) donde un clic resuelve por el
motor real y muestra `LEGAL / KNOWLEDGE / COVERAGE` + condiciones + fuentes +
"por qué sabemos / por qué no". Cobertura visible: `VERIFIED` (Góriz), `PARTIAL`
(Ordesa sin geometría de sectores; Picos sin motor ni DEM), `UNKNOWN` (resto).
Los contornos `esquematico` del mapa son informativos y jamás pueden producir
`PERMITTED`. Ver `docs/ALRASO-M2-PRODUCT-SLICE.md` (incluye el presupuesto de
investigación por zona: 2–4 h y clasificación A/B/C).

**M2.1 — Product Preview Readiness (actual):** la tarjeta responde en lenguaje
llano (titular + «no es un permiso, pero tampoco una prohibición» cuando
`UNDETERMINED`), hay búsqueda por coordenadas o zona conocida (`/api/find`,
`webapp/places.json`) y a11y básica (foco, labels, `aria-live`, táctil ≥44 px).
Los códigos canónicos se conservan en «Detalle técnico». Despliegue público
**bloqueado** hasta sustituir `tile.openstreetmap.org`. Ver
`docs/ALRASO-M2.1-PREVIEW-READINESS.md` (checklist de revisión humana incluida).

Versiones e identidades fijadas en `tooling/DEPENDENCIES.lock.json`
(Axiom v0.2.2 commit `d142c64`, SHA-256 del binario; `rulespec/v1+m1r1`;
`schema m1r2`; `resolver 0.2.1-hardening`).

## Licencia y atribuciones

- Código propio de AlRaso: **Apache-2.0** → [`LICENSE`](LICENSE).
- Datos, textos oficiales, material judicial y componentes externos: →
  [`NOTICE.md`](NOTICE.md), con procedencia, hash y estado de verificación de las
  condiciones de reutilización de cada fuente (Apache-2.0 **no** relicencia esos
  materiales).

## Advertencia permanente

Este software determina regímenes normativos codificados en el corpus. Las restricciones
operativas (reservas, accesos, avisos de la dirección del parque) NO están cubiertas y
el resultado SIEMPRE lleva ese warning. No es asesoramiento jurídico. El software se
proporciona "TAL CUAL", sin garantías de ningún tipo (sección 8 de Apache-2.0).
