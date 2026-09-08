# ALRASO-F2-CLOSURE

**Fase:** cierre de la ronda F2 (los 4 `must solve before implementation` de §J del discovery)
**Fecha:** 2026-09-05
**Referencia base:** `VIVAC-TECHNICAL-DISCOVERY.md` (no reescrito; aquí solo nueva evidencia, cambios y cierre de incertidumbres)
**Estado del discovery al inicio:** `PROJECT_STATUS=TECHNICALLY_VALIDATED (condicionado a F2)`

Método: pruebas reales ejecutadas en esta sesión (engine Axiom compilado/ejecutado en docker
sobre el binario Linux de los spikes; probes HTTP reales contra fuentes oficiales; ejecución del
fixture). Nada concluido por lectura de documentación cuando pudo ejecutarse.

## 0. Verificación de inconsistencias documentales previas

- Fecha del discovery: **ya figuraba 2026-09-05** (búsqueda de `2025-09-05` en todo el repo: 0
  coincidencias). Sin cambios.
- Recuentos de F2: no existe ningún resumen que diga 3 items; §J y la línea BLOCKERS listan los
  **4** correctos. Sin cambios.

---

## 1. F2.1 — Compatibilidad real con Axiom

### A. Activity como tipo cerrado (Spike F2.1A ampliado)

Evidencia: `discovery/spikes/f2-axiom/activity-spike.yaml` + `F2A-RESULTS.txt` (6 casos
originales + 2 probes nuevos ejecutados en esta sesión sobre el artefacto compilado real).

Modelo: un único input `activity_name` de tipo `Text` + `match` exhaustivo sobre las 7
modalidades + rama por defecto `_ => false`.

| Probe | Resultado observado (ejecutado) | Comportamiento |
|---|---|---|
| valor conocido (VIVAC_AL_RASO / PERNOCTA_REFUGIO / TIENDA_NOCTURNA) | casos correctos, `resolucion_unica=holds` | correcto |
| valor desconocido (`CAMPING_LIBRE`) | todos `not_holds`, `resolucion_unica=not_holds` | **fail-closed** → wrapper: UNDETERMINED |
| casing incorrecto (`vivac_al_raso`) | igual que desconocido | **fail-closed** |
| valor compuesto (`"VIVAC_AL_RASO;ACAMPADA"`) (nuevo p2) | todos `not_holds` | **fail-closed** |
| input ausente | HARD ERROR `missing input ...` (exit 1) | mapeable a UNDETERMINED+INCOMPLETE |
| dos modalidades (hechos duplicados, valores en conflicto) (nuevo p1) | HARD ERROR `ambiguous input ... conflicting values` (exit 1) | **estructuralmente irrepresentable; forzado = error duro** |

No existe modelo de múltiples booleanos: el estado imposible `vivac=true ∧ acampada=true` no es
introducible en este esquema. No se necesitó el fallback de booleanos.

**`AXIOM_ACTIVITY_MODEL=TEXT_MATCH_ACCEPTABLE`** (el `match` sobre `Text` está realmente
soportado, es nativo del lenguaje de fórmulas y da semántica de enumerado cerrado con
fail-closed; no es un workaround).

### B. Compile-cache por knowledge-state (Benchmark F2.1B ejecutado)

Spike reproducible: `gen-f2b-ruleset.js` (rulesets sintéticos de 10/100/500/1000 reglas con la
forma de nuestro dominio: flag `match` + condición-juicio con umbral por versión),
`bench-f2b-full.sh`, salida completa en `F2B-BENCH-RESULTS.txt` (contenedor Linux x86_64,
`rust:1-slim`, mismo binario release de los spikes).

| N reglas | compile cold | 2ª compilación | run `fast` | run `explain` | artefacto |
|---|---|---|---|---|---|
| 10 | 0.315 s | 0.292 s | 0.034 s | 0.036 s | 100 KB |
| 100 | 0.315 s | 0.320 s | 0.043 s | 0.047 s | 971 KB |
| 500 | 0.391 s | 0.433 s | 0.15–0.21 s | 0.11–0.15 s | 4.8 MB |
| 1000 | 0.432 s | 0.442 s | ~0.20 s | ~0.20 s | 9.7 MB |

(Proceso vacío = 0.013 s de arranque; la compilación domina ~0.3 s fijos + crecimiento
casi lineal leve.)

Propiedades verificadas:

1. **Determinismo byte-a-byte**: sha256 del artefacto idéntico entre compilaciones del mismo
   knowledge-state (los 4 tamaños). Esto hace que el cache por contenido sea trivial.
2. **Invalidación**: cambiar 1 umbral en 1 regla → sha256 del knowledge-state distinto →
   artefacto distinto (probado `ruleset-bench-10` vs `-10v2`). Pipeline
   `knowledge-state hash → cache → artefacto` funciona.
3. **Reutilización**: `run-compiled` carga el artefacto en procesos separados (semántica de
   cache-hit) sin recompilar.

No se extrapola más allá de N=1000 (no medido; escala ~lineal en lo observado).

- **`AXIOM_COMPILE_CACHE=VIABLE_CONTENT_ADDRESSED`** — hash estable del conjunto de
  `LegalRuleVersion` visibles por knowledge-date como clave; artefactos inmutables regenerables.
- **`AXIOM_COLD_COMPILE=0.31-0.43s (N=10-1000, linux x86_64)`**
- **`AXIOM_WARM_LOAD=0.03-0.20s run fast desde artefacto (sin proceso residente)`**
- **`AXIOM_EXPLAIN_COST=+5-15% sobre fast; trace ~15 KB por consulta de 10 salidas`**
- Conclusión: **PASS** (a escala de nuestros pilotos — cientos de reglas por knowledge-state —
  compilar cuesta menos que una consulta SQL mal indexada; el cache es una optimización
  limpia, no un salvavidas).

### C. Binding / integración (Spike F2.1C ejecutado)

Evidencia: `F2C-BINDING-RESULTS.txt`. El binding Python **oficial existe y funciona** (probado
contra el binario real en contenedor): es literalmente un envoltorio `subprocess` + modelos
pydantic sobre el contrato CLI; **no publicado en PyPI** y empaquetado con pin `python==3.14.*`
(el código funcionó en 3.12 sin tocarlo). WASM existe en-repo (solo navegador, no aplica a M1).
Servicio: no existe servidor oficial.

Decisión de integración: **el contrato CLI JSON-in/JSON-out es la interfaz canónica**; nuestro
adapter la implementa delgado (≤100 líneas, errores normalizados
`MISSING_INPUT/AMBIGUOUS_INPUT/COMPILE/...` mapeados a UNDETERMINED/INCOMPLETE/CONFLICT — el
RuntimeError del binding oficial probado confirma que el stderr del engine llega íntegro).
La BD bitemporal (PostgreSQL) no conoce Axiom; mañana otro evaluador implementa el mismo
protocolo.

### Gate F2.1

**`AXIOM_FINAL_DECISION=YES_WITH_WRAPPER`** — el wrapper sigue siendo correcto: ni Activity ni
el compile-cache ni la integración han requerido los planes de contingencia. No es sunk cost:
los tres puntos que quedaron abiertos en §J se cerraron a favor, con prueba ejecutada.

---

## 2. F2.2 — Licencia rulespec-es y layout propio

### A. Estado de licencia (re-verificado 2026-09-05)

- GitHub API `repos/.../rulespec-es` → `license: null`; `.../license` → 404.
- Clon local: sin LICENSE, sin `LICENSE.md`; README sin mención; **cero menciones a
  SPDX/Copyright/licencia en cualquier fichero** (grep completo del clon).
- Issues: ninguno (abiertos y cerrados = 0). Commits recientes no aclaran nada.

**`RULESPEC_ES_LICENSE_STATUS=NO_LICENSE_VERIFIABLE`** →
**`RULESPEC_ES_CODE_REUSE=PROHIBITED`**. No copiamos ni derivamos ficheros, directorios ni
contenido del repo (el clon de trabajo se usó solo como scratch para spikes locales y no entra
en nuestro corpus). El *layout* de directorios del discovery se rediseña desde cero (abajo).

### B. Layout y namespace (diseñados, no copiados)

Problema del árbol jurisdiccional puro: Picos y Guadarrama **cruzan CC.AA.** y cada parque
mezcla normas estatales/autonómicas; el árbol propuesto en la orden colocaría cada parque bajo
una sola comunidad, mintiendo sobre la jurisdicción. Solución (Opción 3): **dos árboles con
semánticas distintas**, enlazados por evidencia/relaciones — nunca por ubicación de fichero:

```text
legal/
  corpus/                         # DOCUMENTOS oficiales — espejo de la jerarquia oficial
    es/national/{boe,boe-eli}/
    es/ccaa/{aragon/boa,madrid/bocom,cantabria/boc,asturias,bocyl}/
    es/parks/{ordesa/pnomp,picos-europa,guadarrama}/
    es/state-gis/oapn/
  rules/                          # MODULOS DE REGLAS — por ambito de aplicacion (el nuestro)
    parks/{ordesa,picos-europa,guadarrama}/
    ccaa/{aragon,madrid,cantabria,asturias,castilla_y_leon}/
    national/
```

Un módulo de parque referencia documentos del corpus de varias jurisdicciones; la ubicación no
codifica soberanía. Los bundles RuleSpec para compilar son **proyecciones generadas y
deterministas** desde la BD (fuente de verdad: `LegalRuleVersion`); nadie autoría YAML a mano.

**`OUR_RULE_LAYOUT=CORPUS_JURISDICTION_TREE__RULES_SCOPE_TREE (monorepo propio)`**

### C. IDs duraderos (namespace propio, independiente del motor)

```text
alraso:<jur>/<scope>/<subject>#<rule-slug>
  jur    = es | es-ar | es-cb | es-as | es-cl | es-md        (autoridad que PUEDE modificar)
  scope  = pn-ordesa | pn-picu | pn-guad | ...
  subject= pernocta | acceso | sobrevuelo | escalada | ...
  slug   = kebab-case, semantico
Ej. alraso:es-ar/pn-ordesa/pernocta#vivac-sector-ordesa
```

Reglas de durabilidad: el ID no cambia jamás al revisar contenido (una revisión = nuevo
`LegalRuleVersion`); renombrar concepto = ID nuevo + `RuleRelation RESTATES`; el binding a IDs
internos del motor (formato `jur:root/path#rule` de Axiom) es una **proyección de compilación**
reversible y con tabla de equivalencias versionada: mañana cambiar de motor no mueve ni un ID.

**`DURABLE_RULE_ID_SCHEME=alraso:<jur>/<scope>/<subject>#<slug>`**

---

## 3. F2.3 — Fuentes bloqueadas y evidencia judicial

### A. GIS/portales — hallazgo importante

Los hostnames que el discovery §J registró como "bloqueados del entorno"
(`geoportal.comunidad.madrid`, `ide.cantabria.es`, `www.idearagon.es`,
`reservasonline.aragon.es`) son **NXDOMAIN a nivel global** (verificado por DNS-over-HTTPS):
eran **endpoints mal identificados, no bloqueos**. El único bloqueo real demostrado es
`api.datos.gob.es` (existe globalmente; el DNS de este entorno no lo resuelve —
CURRENT_ENVIRONMENT_BLOCKED; `www.datos.gob.es` sí funciona).

Matriz completa en `discovery/evidence/gis-access/F2-GIS-ACCESS-RESULTS.md`. Resumen de
accesibilidad demostrada con probes de esta sesión:

| Fuente | Resultado |
|---|---|
| OAPN WFS (límites PN+ZPP) | **200 OK** (GetCapabilities 133 KB) |
| Aragón: `opendata.aragon.es` CKAN API | **200 OK** (ENP/PORN/APPE/Reservas/Biosfera/Humedales) |
| Aragón: descarga oficial `idearagon.aragon.es/.../rednat_enp.json.zip` | **200 OK**, zip→GeoJSON 33 features + metadatos INSPIRE |
| Aragón: `idearagon.aragon.es/geoserver/wfs` GetCapabilities | **200 OK** |
| Aragón: BOA (portal) | **200 OK** (deep-link D 16/2022 = tarea de ingesta; título exacto verificado en pnomp.es oficial 200) |
| pnomp.es (legislación/pernocta) | **200 OK** (título exacto de D 16/2022 presente) |
| reservasparquesnacionales.es | **200 OK** |
| Madrid: `datos.comunidad.madrid` CKAN API | **200 OK** (sin capa vectorial PRUG; texto → BOCM http ✓) |
| Madrid: BOCM | **200 OK por http** (TLS roto: curl exit 35 — registrar en conectores) |
| Cantabria: `mapas.cantabria.es` (IDE oficial) + BOC | **200 OK** (endpoints OGC exactos tras config JS → ingesta M2) |
| Asturias: `www.asturias.es` | **200 OK** |
| `api.datos.gob.es` | CURRENT_ENVIRONMENT_BLOCKED (DNS local vs DoH global demostrado) |

**`GIS_SOURCE_ACCESS_STATUS=ORDESA_PILOT_READY`** — para el piloto Ordesa (M1) cada fuente
necesaria tiene camino reproducible demostrado; lo pendiente (endpoints vectoriales exactos de
Cantabria/CM) pertenece a M2 y es trabajo de ingesta, no incógnita arquitectónica.
SOURCE_UNAVAILABLE: **ninguna fuente pública evaluada**.

### B. Sentencias TSJM Guadarrama

Registro estructurado en `discovery/evidence/guadarrama-prug/tsjm-evidence-registry.json`
(court/number/date/recurso/afectación/efecto para las tres). Las tres quedan **identificadas con
certeza** vía prioridad-3 (texto consolidado administrativo oficial, que el propio discovery ya
tenía descargado y que ahora se anota jurídicamente):

- **1135/2021 (7-oct-2021), rec. 431/2020**: anula art. 49 (sobrevuelo sin motor) + art. 38.1.x).
- **1003/2022 (4-nov-2022), rec. 197/2022**: anula inciso del art. 47.b).5, extremo de "cambio
  de uso" en 3 fichas, **y el extremo del art. 48.2 que fija 2.000 m para vivac** — la hipótesis
  del discovery §I queda **confirmada con evidencia primaria** (antes: secundaria + PDF), y se
  amplía: la misma sentencia toca vías de escalada y fichas ganaderas.
- **135/2023 (2-feb-2023), rec. 455/2020**: anula último inciso del art. 38.1.w).

ECLI (prioridad-1): **diferido explícitamente** — `poderjudicial.es` alcanzable pero su CENDOJ
no expone contrato estable (openSearch 404; rest/doSearch 500 sin sesión UI). Procedimiento de
obtención documentado en el registro (búsqueda por sala 8ª + número de recurso). Ninguna
afectación a Ordesa.

**`TSJM_EVIDENCE_READY=YES`** (campos exigidos completos salvo ECLI, diferido con procedimiento
escrito y sin impacto en el piloto).

---

## 4. F2.4 — OpenTermsArchive vs patrón propio

Análisis técnico-operacional sobre las restricciones nuestras (Hermes/ESData con fetchers
Python ya en producción —incluido BOE–, PostgreSQL/PostGIS como núcleo, volumen: boletines +
webs de parques + ficheros GIS, no millones de ToS):

| Criterio | OTA completo (Node+Mongo+git) | Patrón propio (fetchers+object storage+PostgreSQL) |
|---|---|---|
| Runtimes nuevos | Node **y** MongoDB (backup, upgrades, monitorización) | **cero** (Python + PostgreSQL + S3/WORM) |
| Snapshot inmutable de PDFs grandes | git con binarios — **73 MB ya observado en un PRUG**; historial git se degrada | object storage versionado/WORM + SHA-256; escala bien |
| Fuente de verdad normativa | seguiría siendo PostgreSQL → **Mongo = segundo sistema de metadatos** o puente de sincronización (coste recurrente) | uno solo (PostgreSQL) |
| Los 6 patrones obligatorios | los da probados (commits tipificados incl. `technical upgrade`, reporter de inaccesibilidad con labels, `validFrom/validUntil`, firmas) | se replican como log de eventos tipificados `FIRST_RECORD / SOURCE_CHANGE / EXTRACTOR_CHANGE / INACCESSIBLE / STRUCTURE_CHANGE` + hashes + issues con labels + firmas Ed25519 sobre bundles |
| Licencia | EUPL-1.2 (asumible; obliga a publicar modificaciones al engine) | sin obligación nueva (el patrón conceptual no es código copiado) |
| Ahorro estimado | ~2–4 semanas de desarrollo inicial | −(1–2 semanas) de desarrollo de pipeline fino a cambio de cero deuda operativa de stack |
| Riesgo | acoplarse a un stack ajeno para un volumen donde git+Mongo son sobredimensionados | reimplementar "lo justo" (deliberado: snapshot/hash/diff/eventos/firmas, NO re-hacer su reporter multi-colección ni su ecosistema de instancias) |

El valor de OTA es su **patrón y su disciplina**, no su stack; nuestros snapshots son
frecuentemente binarios grandes donde su elección (git) es el componente a evitar. No hay
necesidad real de MongoDB en nuestra arquitectura.

**`EVIDENCE_ENGINE_DECISION=COPY_PATTERN_ON_EXISTING_INFRA`**
(coste operacional: OTA = +2 runtimes + 2º sistema de metadatos + riesgo git-binarios, a cambio
de 2–4 semanas; propio = 1–2 semanas de código sobre infraestructura ya operada, sin nuevos
runtimes, cadena de custodia unificada con la BD legal.)

---

## 5. Fixture de factibilidad Ordesa

`discovery/fixtures/ordesa-feasibility/` — `fixture.json` (SourceDocuments con URLs canónicas
BOE/BOA/pnomp/OAPN, LegalFragments con locator, SpatialScopes con procedencia,
LegalRuleVersions bitemporales del override D 16/2022, RuleRelation OVERRIDES) +
`assemble-check.py` que resuelve el fixture en SQLite y comprueba:

```text
activity_date=2021 -> PERMITTED            [OK]
activity_date=2023 -> PROHIBITED           [OK]
replay vigilante / descubrimiento tardio / gap INCOMPLETE / actividad desconocida fail-closed
RESULT: ASSEMBLY_CHECK_PASS  (ejecutado 2026-09-05, tras normalizar IDs al esquema final
alraso:es-ar/pn-ordesa/pernocta#vivac-sector-ordesa)
```

Sin conclusión jurídica nueva: solo regímenes ya verificados en el discovery §I.
**`ORDESA_FIXTURE_READY=YES`**. Pendiente para M1 (no bloquea F2): delimitación cartográfica
oficial del *sector Ordesa* (`SPATIAL_REVIEW_REQUIRED` en el fixture; plan: cartografía PRUG +
OAPN + DEM).

## 6. Correcciones/nueva evidencia respecto al discovery

1. **§J "IDEs bloqueadas"**: eran endpoints incorrectos (NXDOMAIN globales), salvo
   `api.datos.gob.es` (bloqueo real del entorno). Los hosts oficiales reales están accesibles.
2. **§I Guadarrama**: la nulidad del art. 48.2 (vivac 2.000 m) pasa de "verificada vía fuente
   secundaria + PDF" a **verificada en el texto consolidado oficial**; además se documenta que
   1003/2022 anula más cosas (vías de escalada, fichas ganaderas) y qué anulan exactamente las
   otras dos sentencias (sobrevuelo). El "caso de nulidad judicial" del piloto se fortalece.
3. El discovery no queda reescrito: estos puntos viven en este cierre y en
   `discovery/evidence/`.

## 7. Matriz de cierre

| Item | Antes F2 | Resultado | Evidencia | Decisión |
|---|---|---|---|---|
| F2.1 Axiom (Activity/compile-cache/binding) | YES_WITH_WRAPPER condicional; enum sin verificar; cache desconocido; binding "oficial" sin probar | Activity enum viable fail-closed; compilación <0.5 s con artefactos deterministas; binding oficial = subprocess wrapper funcional | F2A-RESULTS.txt (8+2 probes ejecutados), F2B-BENCH-RESULTS.txt, F2C-BINDING-RESULTS.txt | YES_WITH_WRAPPER confirmado |
| F2.2 Licencia/layout rulespec-es | "sin LICENSE, decidir reutilización vs propio" | Sin licencia confirmada (API+clon+headers=0) | grep clon + GitHub API (license=null, /license 404) | Reutilización PROHIBIDA; layout y IDs propios |
| F2.3 Fuentes bloqueadas + TSJM | 3 "bloqueadas" + ECLI pendiente | 2 de 3 eran URLs falsas; oficiales accesibles; Ordesa 100% cubierto; sentencias identificadas vía texto oficial consolidado | F2-GIS-ACCESS-RESULTS.md, tsjm-evidence-registry.json, DoH diagnostics | Acceso piloto OK; ECLI diferido con procedimiento |
| F2.4 OTA adapt vs pattern | abierto (implicaba stack Node/Mongo/git) | git+Mongo sobredimensionados para binarios grandes y un solo consumidor; 6 patrones replicables sobre infraestructura existente | análisis §4 (volumen, PRUG 73 MB, Hermes/ESData ya operativo) | COPY_PATTERN_ON_EXISTING_INFRA |

## 8. Gates de Milestone 1 (criterios 1-9 de la orden)

1. Activity sin ambigüedad peligrosa — **SÍ** (irrepresentabilidad estructural + fail-closed probados).
2. Compile-cache viable — **SÍ** (PASS; y si mañana pesara, el adapter permite evaluador propio).
3. Sin dependencia de código sin licencia — **SÍ** (cero contenido rulespec-es; engine Apache-2.0; OTA no usado como código).
4. Layout/ID nuestros — **SÍ** (§2C).
5. Camino reproducible a fuentes oficiales necesarias — **SÍ** para el piloto Ordesa (§3A).
6. Guadarrama identificada o diferida sin afectar a Ordesa — **SÍ** (§3B).
7. Estrategia de evidence snapshots decidida — **SÍ** (§4).
8. Fixture Ordesa listo — **SÍ** (§5, ASSEMBLY_CHECK_PASS ejecutado).
9. Sin incertidumbre arquitectónica que obligue a rehacer el núcleo — **SÍ**: las tres
   decisiones que podían reabrir el núcleo (motor, fuente de verdad, evidencias) están
   cerradas con ejecución; lo pendiente (deep-links BOA, sector Ordesa cartográfico, endpoints
   M2, ECLIs) es trabajo de ingesta/consultas, no diseño.

## 9. Estado final

```text
F2_STATUS=PASS
PROJECT_STATUS=TECHNICALLY_VALIDATED_F2_CLOSED (a la espera de orden explícita de inicio)
AXIOM_FINAL_DECISION=YES_WITH_WRAPPER
AXIOM_ACTIVITY_MODEL=TEXT_MATCH_ACCEPTABLE
AXIOM_COMPILE_CACHE=VIABLE_CONTENT_ADDRESSED
RULESPEC_ES_LICENSE_STATUS=NO_LICENSE_VERIFIABLE (RULESPEC_ES_CODE_REUSE=PROHIBITED)
OUR_RULE_LAYOUT=CORPUS_JURISDICTION_TREE__RULES_SCOPE_TREE
DURABLE_RULE_ID_SCHEME=alraso:<jur>/<scope>/<subject>#<rule-slug>
GIS_SOURCE_ACCESS_STATUS=ORDESA_PILOT_READY
TSJM_EVIDENCE_READY=YES (ECLI diferido: CENDOJ sin contrato estable; procedimiento documentado)
EVIDENCE_ENGINE_DECISION=COPY_PATTERN_ON_EXISTING_INFRA
ORDESA_FIXTURE_READY=YES
MILESTONE_1_READY=YES
BLOCKERS=Ninguno para M1. Diferidos sin afectación al piloto: (a) deep-link BOA D 16/2022 vía
buscador oficial (ingesta M1); (b) geometría oficial del sector Ordesa (SPATIAL_REVIEW en M1);
(c) ECLIs TSJM (M2 Guadarrama); (d) endpoints vectoriales exactos Cantabria/CM (M2);
(e) api.datos.gob.es bloqueado SOLO en este entorno (usar desde red no filtrada o portal
www.datos.gob.es).
Metricas F2.1: AXIOM_COLD_COMPILE=0.31-0.43s (N=10-1000); AXIOM_WARM_LOAD=0.03-0.20s;
AXIOM_EXPLAIN_COST=+5-15% sobre fast, trace ~15KB.
```

Milestone 1 **NO iniciado** — se detiene aquí conforme a la orden; a la espera de instrucción
explícita.
