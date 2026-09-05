# VIVAC-TECHNICAL-DISCOVERY

**Fase:** confirmación técnica y architectural discovery
**Fecha:** 2026-09-05
**Alcance:** capa normativa geoespacial verificable para pernocta en naturaleza (España). Pilotos: Picos de Europa, Ordesa y Monte Perdido, Sierra de Guadarrama.
**Método:** inspección directa de repositorios (código, LICENSE, issues, actividad), verificación de fuentes oficiales (BOE/ELI, webs de parques, servicios GIS con GetCapabilities), y 3 spikes ejecutados (Axiom, PostGIS, bitemporalidad). Spikes en `discovery/spikes/`.

Marcas: **VERIFICADO** = probado en esta sesión. **PARCIAL** = múltiples fuentes o leído por índice. **NO_VERIFICADO** = no probado. **INCONCLUSO** = sin evidencia suficiente. Los informes de subagentes se han contrastado punto por punto; las licencias críticas se han verificado contra el archivo LICENSE real.

---

## A. Executive conclusion

### `GO_WITH_CHANGES`

El proyecto es técnicamente viable y la investigación lo confirma con evidencia empírica, pero **la arquitectura candidata inicial tenía tres supuestos falsos** que hay que corregir antes de implementar:

1. **"Axiom puede ser el Rule engine" — parcialmente falso.** El motor de Axiom Foundation es real, de calidad de ingeniería notable y Apache-2.0, y el Spike A demuestra que el paradigma encaja (hechos tipados → juicio + traza). Pero **la bitemporalidad está diseñada y NO implementada**: `assessment_date` se parsea y se hace eco, sin efecto en la selección de versiones (confirmado empíricamente en el spike; `docs/bitemporal.md` lo declara). Nuestro eje de system time (`recorded_at`/`recorded_until`) **será nuestro, sí o sí**. Además: no existe el período `day` (solo `month/benefit_week/tax_year/custom` — sesgo fiscal), y no hay grafo de relaciones de precedencia (OVERRIDES/EXCEPTION): eso lo resolvemos nosotros aguas arriba.
   → Decisión: **YES_WITH_WRAPPER** (ver E).

2. **"PostGIS como spatial fact resolver" — verificado y mejor de lo esperado.** El Spike B cargó los límites oficiales reales de los 17 parques nacionales vía **WFS GeoJSON de OAPN** (`sigred.oapn.es`), con metadatos normativos incrustados por feature (ley declarativa incluida), resolvió `lat/lon → scopes` para Picos y Guadarrama y descartó correctamente un punto fuera, todo con procedencia (URL + SHA-256 + retrieved_at). La hipótesis espacial está validada end-to-end con dato oficial real.

3. **"Hermes/ESData como patrón de evidencia" — reforzado por OpenTermsArchive, no sustituido.** OTA es el único proyecto con el ciclo snapshot inmutable → hash → diff → `validFrom/validUntil` → alerta de inaccesibilidad **probado en producción diaria**. Su engine (EUPL-1.2, Node/Mongo/git) es adaptable; su patrón conceptual (commits tipificados que separan "cambió la fuente" de "cambió mi extractor", principios *never trust the source / never trust the maintainer*) es copiable tal cual.

**Cambios obligatorios al plan:**
- La **fuente de verdad normativa es nuestra BD bitemporal** (LegalRuleVersion append-only). Axiom compila vistas ejecutables de esa verdad por fecha de conocimiento; nunca al revés.
- Corregir las hipótesis normativas del brief (ver I): Picos no tiene "Ley 1/2014"; Ordesa no fue redeclarada por la Ley 30/2014 (que es la ley marco); el PRUG de Guadarrama no es RD 595/2014 (son decretos autonómicos de 2019/2020 modificados por 3 sentencias del TSJM que **anulan el art. 48.2 de pernocta** — el caso de nulidad judicial que este piloto debía cubrir existe y está verificado).
- El primer milestone se mantiene como **PURE_BITEMPORAL_GEOSPATIAL_LEGAL_RESOLVER** (ver L), con un motor wrapper sobre Axiom o fallback propio decidido en una segunda ronda de spikes (F2).

---

## B. Build vs reuse matrix

| Subsistema | Decisión | Base | Por qué |
|---|---|---|---|
| **rules** (evaluación normativa) | **REUSE (Axiom) + BUILD wrapper** | axiom-rules-engine (Apache-2.0) | Spike A validado; falta wrapper de fail-closed, selección temporal por knowledge_date y precedencia |
| **bitemporality** | **BUILD** | patrón propio validado en Spike C | Axiom no lo implementa; es el núcleo diferencial del producto |
| **provenance** | **BUILD (patrón OTA)** | OpenTermsArchive | Commits tipificados, SHA como ID, validFrom/validUntil; ninguna otra dependencia lo da |
| **source monitoring** | **ADAPT (OpenTermsArchive) o COPIAR_PATRÓN** | OTA engine (EUPL-1.2) | Si aceptamos stack Node+Mongo+git: adaptar; si no, copiar el patrón. Decidir en F2 |
| **GIS** | **BUILD sobre PostGIS** | osmpoidb (Apache-2.0) como patrón de pipeline | GeoJSON/WFS oficial verificado en Spike B; patrón flex→PostGIS→ST_Intersects→triggers de osmpoidb es replicable 1:1 |
| **OSM** | **ADAPT (patrón osmpoidb)** | osm2pgsql flex + replicación | Solo para capas de contexto (refugios, barreras, carteles); nunca legalidad desde OSM |
| **offline maps** | **REUSE (MapLibre RN + PMTiles)** | maplibre-react-native (MIT), PMTiles (BSD-3) | Plugin Expo oficial, OfflineManager, soporte pmtiles:// nativo; caveat #1130 (memoria iOS con PMTiles grandes) |
| **community observations** | **BUILD (patrón StreetComplete)** | StreetComplete (GPL-3, solo patrón) | Contrato quest: filtro + formulario cerrado + applyAnswer determinista + check_date; el código GPL-3 no se toca |
| **refuges** | **REUSE (API refuges.info)** | código WTFPL / datos CC BY-SA 2.0 | API viva verificada (último commit 31-ago-2026), GeoJSON + sync incremental `depuis`; no crear BD paralela |
| **mobile app** | **REUSE (Expo + MapLibre RN)** | Expo SDK 54+, maplibre-react-native v11 | Requiere dev client (no Expo Go); 100cims solo inspiración de UX, sin licencia verificable → DO_NOT_USE como código |
| **UI revisión de reglas** | **SOLO_REFERENCIA (Blawx)** | Blawx (MIT) | Referencia de UI visual para no programadores; el repo está latente (último commit nov-2024) y es alpha declarada |

---

## C. Repository assessment

### C.1 Axiom Foundation (TheAxiomFoundation/*)

- **Propósito:** rules-as-code para dominios legales/beneficios; motor Rust + bindings Python; RuleSpec como formato canónico; corpus inmutable firmado; codificación supervisada (axiom-encode).
- **Actividad:** muy activa (push diario en varios repos; engine v0.2.2; DECISIONS.md con entradas de jul-2026). **Tracción mínima: 4 estrellas en el engine, 0-3 en el resto.** Bus factor: una sola organización.
- **Licencia:** engine, corpus, encode, axiom.org: **Apache-2.0** (verificada en el clon). `rulespec-es`: **SIN LICENCIA** (verificado: no hay LICENSE; CC-BY-4.0 en lanes US/NZ/BE).
- **Arquitectura (leída del código):** RuleSpec YAML (`format: rulespec/v1`) → compilación a `ProgramSpec` → artefacto compilado v2 con `metadata.input_catalog`; ejecución explain (traza completa: `executed_expression`, `parameter_reads`, `dependencies`, `not_evaluated_dependencies`) y fast/dense; IDs duraderos `<jurisdiction>:<root>/<path>#<rule>`; reglas `parameter` (con tablas `indexed_by`), `derived` (juicio o escalar), `data_relation`, `derived_relation`, `source_relation` (`defines/delegates/implements/sets/amends/restates/cites`); provenance por módulo (`corpus_citation_path`, `source_sha256`, `encoding_provenance.reviewed_by`, `validation` de oráculos); juicios de primera clase con `holds/not_holds/undetermined`; `exactly_one` como gate.
- **Bitemporalidad:** `docs/bitemporal.md` define valid time + assessment time y el camino (versiones con `enacted_on`/`known_from`). **Hoy `assessment_date` se valida y se hace eco pero NO filtra versiones** (confirmado en Spike A, caso 8). Alineación conceptual 1:1 con nuestro modelo (effective↔valid, recorded↔system).
- **Fail-closed:** correcto y deliberado: artefacto v1 rechazado ruidosamente; `effective_to` ejecutable y fail-closed (DECISIONS 2026-07-21); **hecho faltante → error duro** (`missing input 'altitude_m'`, verificado), no interpretación silenciosa → el wrapper debe capturar y mapear a UNDETERMINED/INCOMPLETE.
- **Corpus España:** `rulespec-es` es un **scaffold vacío** (`es`, `es-an`, `es-ga`, `es-md` con `.gitkeep`) orientado al impuesto de patrimonio 2022, con pipeline fuertemente gated (corpus firmado Ed25519, encoding supervisado, "do not hand-author RuleSpec"). Sin licencia.
- **Qué reutilizar:** el formato RuleSpec, el binario compilable, la disciplina de IDs/provenance, la traza explain.
- **Qué no:** su corpus como fuente de nuestro dominio (vacío para naturaleza); su pipeline de codificación supervisada completo para un equipo pequeño en fase inicial (peso operativo alto); confiar la bitemporalidad al engine (no existe).
- **Riesgos:** madurez organizativa (org joven, tracción mínima, API en churn con política de versionado estricta); saludable pero real. Mitigación: nuestra BD es la fuente de verdad; los artefactos se regeneran; si el proyecto muere, las reglas son datos y un fallback evaluador propio es factible (las reglas de este dominio son condicionales simples sobre hechos tipados).
- **Decisión:** **REUSE con wrapper (YES_WITH_WRAPPER)**, condicionado a la ronda F2 (ver E y L).

### C.2 OpenFisca

- **Actividad:** muy viva (PyPI 44.7.1, sep-2026; 236★). **Licencia: AGPL-3.0 con cláusula de red** (verificada).
- **Modelo:** variables por entidad con `definition_period`, fórmulas fechadas, parámetros YAML versionados con `reference` legal, trace endpoint, tests YAML. **Un solo eje temporal** (validity). Sin soporte espacial. **No existe openfisca-spain** (404 verificado; retirado).
- **Veredicto:** **SOLO_REFERENCIA**. Mejor patrón del mundo para parámetros versionados con cita legal (lo copiamos conceptualmente en `conditions` y evidencia), pero su núcleo NumPy fiscal no casa con juicios geoespaciales, y AGPL-de-red añade obligaciones que no necesitamos asumir.

### C.3 L4 / SMU Computational Law

- **Estado:** investigación con derrama a producto privado (`legalese/l4-ide`, Haskell, muy activo pero comercial; `smucclaw/l4-lp`, Clojure→Prolog con trazas). Repos históricos eliminados (404 verificados). Licencias Apache-2.0.
- **Veredicto:** **SOLO_REFERENCIA**. Sus trazas audit-grade (GraphViz) y la semántica de `Period` de Catala son el mejor material de diseño para nuestra capa de explicación. Como motor: no (research en transición, sin continuidad garantizada).

### C.4 Catala (hallazgo adicional)

- Apache-2.0, 2.4k★, releases 1.2.1 (jul-2026) + nightlies firmadas. Literate legislative programming, default logic, `Period` nativo con operaciones, `--trace`. Declaradamente "research project… unstable".
- **Veredicto:** **SOLO_REFERENCIA** (la mejor semántica temporal del espacio; no motor productivo para nosotros).

### C.5 Blawx

- MIT verificada. **Latente**: último commit nov-2024, releases alpha 2023, 198 issues abiertos, "not production-quality" (su propio README). Arquitectura: Django + Blockly + SWI-Prolog/s(CASP) + explicaciones NLG con Akoma Ntoso.
- **Veredicto:** **SOLO_REFERENCIA (UI)**. El patrón de editor visual + escenario + explicaciones enlazadas al texto legal es exactamente nuestra futura UI de revisión jurídica. Como motor: no.

### C.6 OpenTermsArchive

- **Actividad:** engine v15.1.0 (jul-2026), 134★; **ecosistema de datos vivo a diario** (instancias DSA en producción). **Licencia: engine EUPL-1.2; datos ODC-BY 1.0** (verificadas).
- **Arquitectura (leída del código):** 3 repos git por colección (declaraciones / snapshots / versiones); fetch (node-fetch, puppeteer como fallback); snapshot SIEMPRE antes de extraer; SHA de commit = ID; author date = fecha de observación; metadatos en trailers de commit; commits tipificados (`First record`, `new changes`, **`technical upgrade`** — re-extracción sin afirmar cambio de fuente); PDFs binarios versionados; reporter de fallos con issues y labels (`DOCUMENT_NOT_FOUND`, `DOCUMENT_STRUCTURE_CHANGE`…); `validFrom/validUntil` derivados del historial.
- **Principios transferibles:** *"Never trust the services"* (documentan sustitución de contenido sin cambio de fecha y respuestas geolocalizadas); *"do not require trust in maintainers"* (firmas criptográficas); *obtain documents like a user would*.
- **Veredicto:** **ADAPT** (si aceptamos Node/Mongo/git) o **COPIAR_PATRÓN** si exigimos cadena de custodia propia (S3/WORM + firmas Ed25519 alineadas con Axiom). Decisión en F2. En cualquier caso, los 6 patrones listados arriba se adoptan sin discusión. → `DO NOT REIMPLEMENT` el ciclo snapshot+diff+versioning desde cero.

### C.7 Navi (Supermagnum/Navi)

- App Android offline (Rust+Kotlin), GPL-3, creada jul-2026, 5★, 1 autor, coautoría IA declarada. `docs/plugins/right-to-roam-camping-spec.md` existe (VERIFICADO) y es **spec sin implementar**.
- **Valor real:** `docs/jurisdiction-rules.md` + el spec de camping documentan el patrón fail-closed por jurisdicción con precedentes implementados (EC 561/2006, radares): *"decline rather than guess"*, hard-filter vs guidance, granularidad país+región, constantes legales en el core, citas obligatorias por parámetro, re-verificación periódica, disclaimers.
- **Veredicto:** **SOLO_REFERENCIA**. No adoptar conclusiones legales ni código. Sus edge cases (jurisdicción desconocida → declinar; semillas de acceso dudosa → downrank; "no se puede verificar desde cartografía") van directo a nuestro registro de warnings.

### C.8 OpenCampingMap / osmpoidb

- `giggls/osmpoidb` (Apache-2.0 verificada, activo ago-2026): patrón verificado en código — osm2pgsql flex → PostGIS 3.3 → vistas derivadas con `ST_Intersects` (patrón POI-in-POI) → triggers incrementales → GIST → swap tables; actualización con `osm2pgsql-replication` (diffs por minuto).
- `giggls/opencampsitemap`: frontend Leaflet/ráster (irrelevante); su `taginfo.json` es taxonomía útil de campamento. `campsite-features`: sin licencia → no copiar.
- **Veredicto:** **COPIAR_PATRÓN** (pipeline) — es el único FOSS que replica nuestro caso de uso espacial. Frontend: NO.

### C.9 TerriaJS

- Apache-2.0, muy activo (push sep-2026). Conectores verificados en `lib/Models/Catalog/CatalogItems/` (GeoJSON, Shapefile, CSV, KML, WMS/WFS/WMTS, ArcGIS MapServer/FeatureServer, COG…), `TerriaError` con severidad y encadenamiento, catálogo declarativo con esquema validado.
- Peso: ~150 dependencias, web-only (Cesium fork), no viable en RN.
- **Veredicto:** **COPIAR_PATRÓN** (checklist de conectores + modelo de errores normalizados para ingestión heterogénea INSPIRE). No como librería.

### C.10 MapLibre React Native

- MIT verificada; fork oficial separado de @rnmapbox; v11 solo New Architecture, peer `expo >= 54`; **plugin Expo oficial** (dev client, no Expo Go); `OfflineManager` con packs, delta-updates y sideload; vector tiles + clustering completos; releases mensuales; 661★; issues saneadas.
- PMTiles: soporte nativo `pmtiles://` en MapLibre Native (PRs integrados); bugs históricos iOS parcheados; **issue #1130: spike de memoria con PMTiles grandes** (pendiente de Spike D).
- **Veredicto:** **REUSE** — opción por defecto confirmada. `react-native-maps` solo fallback simple; `react-native-boundary` **DO_NOT_USE** (abandonado 2019); geofencing con `expo-location` (100/20 límites Android/iOS) + `@turf/boolean-point-in-polygon` (MIT) offline.

### C.11 PMTiles / Protomaps

- PMTiles: BSD-3 + spec dominio público; single-file con range requests; `pmtiles extract` por región; serverless sobre S3/R2; empaquetable en la app. Basemaps: BSD-3 código / CC0 diseño / **ODbL tiles** (atribución "© OpenStreetMap" obligatoria). España: extract diario; tamaño a medir empíricamente (planeta 120 GB z0-15).
- Nuestros polígonos normativos como PMTiles: **sí** (tippecanoe).
- **Veredicto:** **REUSE** (formato de distribución) + COPIAR_PATRÓN (Planetiler). Evita tile server propio. Verificar en Spike D el caso archivo-local en iOS.

### C.12 StreetComplete

- GPL-3-only, 4.8k★, v63.4 (jul-2026), migración KMP. Patrón quest verificado en código: `elementFilter` DSL + formulario cerrado atómico + `applyAnswerTo` determinista + `check_date`/resurvey + `enabledInCountries`. **Fotos solo en notes** (no dato de quest).
- **Veredicto:** **COPIAR_PATRÓN** (contrato quest) — el esqueleto de nuestras micro-observaciones (¿hay cartel?, ¿refugio abierto?, ¿acceso cerrado?). Código: no (GPL-3 + acoplado OSM). Legalidad jamás como tag OSM.

### C.13 MapComplete

- Repo GitHub **archivado feb-2025**; desarrollo vivo en Forgejo propio (v0.62.7, sep-2026). GPLv3 + licencias REUSE por fichero (heterogéneas, con `ALL-RIGHTS-RESERVED` en assets). Themes JSON validables; TagRendering bidireccional; **`source.geoJson` acepta capas externas** (verificado); Studio como editor GUI.
- **Veredicto:** **ADAPT** (esquema JSON como lenguaje de configuración del prototipo de observaciones; prototipo de visualización sin backend). Riesgo estructural: escribe todo en OSM bajo ODbL → jamás para interpretación jurídica.

### C.14 Refuges.info

- Código WTFPL / **datos CC BY-SA 2.0** (+ ODbL para lo derivado de OSM). Activo (último commit 31-ago-2026, 3 mantenedores). PHP+PostGIS; modelo con `points` (plazas, estado), `point_type` con estados de cierre, `polygones` con `message_information_polygone` ("pas de bivouac…" — precedente directo de nuestro SpatialScope) y `url_exterieure` a la regulación.
- **API pública verificada**: `/api/bbox|massif|point` en GeoJSON/GPX/KMZ/CSV, parámetro incremental `depuis`, `/api/polygones`, `/api/commentaires`.
- **Veredicto:** **REUSE** (consumir API como baseline de refugios con caché incremental `depuis` + idempotencia por `derniere_modif`). No fork del PHP (acoplado a phpBB3). No BD paralela de refugios. → `DO NOT REIMPLEMENT`.

### C.15 100cims

- Expo SDK 56 + RN 0.85 + `@rnmapbox/maps` 10.3.1; 75★; 1 dev + coautoría IA masiva. **Sin LICENSE en raíz; package.json app "MIT" sin texto; api `private:true` sin licencia** → jurídicamente frágil.
- **Veredicto:** **SOLO_REFERENCIA** (UX: retos regionales, planes, i18n ca/es). **DO_NOT_USE como código**; fork descartado (licencia + Mapbox comercial + bus factor 1).

---

## D. Validated target architecture

Correcciones respecto a la arquitectura candidata: (1) la BD bitemporal es el centro, no un anexo; (2) el resolver es un **wrapper** con la selección temporal aguas arriba del engine; (3) la capa comunitaria nunca toca legalidad.

```text
                    APP / WEB (futuro)
                       │
              Expo + MapLibre RN + PMTiles
              (offline: base OSM + polígonos normativos)
                       │
                       │  HTTPS resolver API
                       ▼
   ┌───────────────────────────────────────────────────────┐
   │  RESOLVER WRAPPER (nuestro)                           │
   │  1. PostGIS: lat/lon → scopes aplicables + hechos     │
   │     (inside_park, altitude, sector, zona_servicios)   │
   │  2. BD bitemporal: SELECT versiones visibles en       │
   │     knowledge_date Y aplicables en activity_date      │
   │  3. genera RuleSpec compilado por knowledge-state     │
   │     (cacheado por hash de versiones)                  │
   │  4. Axiom explain → status + conditions + trace       │
   │  5. post-proceso: errores/missing → UNDETERMINED,     │
   │     exactly_one fallido → CONFLICT, warnings Navi-style│
   └───────────────┬───────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
     PostGIS            BD LEGAL BITEMPORAL
   (spatial facts,      (SourceDocument, LegalFragment,
    scopes + OSM          SpatialScope + versiones,
    context layers)       LegalRuleVersion append-only,
        │                 RuleRelation, ReviewEvents)
        │                     ▲
        │                     │ publicación (human-in-the-loop)
        │                     │
   GIS oficiales ──┐   EVIDENCE PIPELINE (patrón OTA)
   WFS/GeoJSON/    │   discovery → acquisition → immutable
   Shapefile/      │   snapshot (git/SHA) → change detection
   ArcGIS          │   → extraction (IA: candidatos) →
                   │   LEGAL review → SPATIAL review → publish
   BOE/BOA/BOCM/   │   → stale/review cycle
   BOC/PRUG PDF ───┘
                        ▲
                 MONITORING (check_date, hashes,
                 DOCUMENT_STRUCTURE_CHANGE → issues)
```

---

## E. Resolver decision

> **¿Adoptamos Axiom RuleSpec?** → **YES_WITH_WRAPPER**

**Evidencia del Spike A** (artefactos en `discovery/spikes/spike-a-axiom/`): módulo `es:policies/vivac/picos-spike` compilado y ejecutado con 8 casos:

1. Vivac 1742 m en 2023 → prohibido (umbral 1800 de la versión post-2022). ✓
2. Vivac 1850 m en 2023 → permitido. ✓
3. Mismo punto, período 2021 → permitido (umbral 1600): **selección de versión por valid time funciona y es auditable en la traza**. ✓
4. Tienda → `AUTHORIZATION_REQUIRED` modelado como juicio separado. ✓
5. Grupo de 12 → prohibido (condición de tamaño falla). ✓
6. Fuera del ámbito → `resolucion_unica = not_holds` → el wrapper lo mapea a **UNDETERMINED** (fail-closed fuera del alcance modelado). ✓
7. **Hecho faltante → error duro del motor** (`missing input 'altitude_m'…`, exit 1): no hay interpretación silenciosa; el wrapper debe capturar → UNDETERMINED + knowledge_status INCOMPLETE. ✓
8. `assessment_date` → se valida (`>= period.start`) y se hace eco, **sin efecto en la selección**: bitemporalidad no implementada, confirmado. ✓

**Qué responde a las preguntas 1-10:**

1. **¿RuleSpec representa los pilotos?** Sí como paradigma (juicios versionados, condiciones tipadas, gates `exactly_one`). Pendiente F2: verificación de `match` sobre `Text` para modelar Activity como enum (hoy lo modelamos como booleans/juicios separados — viable).
2. **¿Traza suficiente?** Sí: `executed_expression`, `parameter_reads` (celdas exactas leídas), `dependencies`, `not_evaluated_dependencies`, `source/source_url` por nodo. Es la base del `precedenceTrace`.
3. **¿Hechos geográficos externos?** Sí — el dataset es caller-supplied (`InputRecord` con nombre duradero, entidad, intervalo, valor tipado). PostGIS entrega exactamente ese shape.
4. **¿Tiempo y versiones?** Valid time completo y robusto (`effective_from/to` ejecutables, fail-closed sobre gaps). Assessment time: **reservado, no implementado**.
5. **¿Bitemporalidad propia?** Toda la de system time (`recorded_at/recorded_until`, replay histórico, retro-auditoría STALE). Axiom's future fields (`enacted_on/known_from`) validan el diseño, no lo sustituyen.
6. **¿Overrides/exceptions claros?** Los modelamos como juicios compuestos + `source_relation` (types `amends/restates` como metadato); la **precedencia real es nuestra** (selección de qué versiones entran al artefacto). No hay motor de relaciones OVERRIDES/REPEALS.
7. **¿Fallo ante desconocidos?** Error duro (bien). Con `exactly_one` fallido → `not_holds` (señal de conflicto modelable). Ambos mapeados a UNDETERMINED/CONFLICT por el wrapper.
8. **¿Fail-closed configurable?** Sí por diseño del sistema (nuestro wrapper) + disciplina del engine (artefactos exactos, gaps → error).
9. **¿Cuánto código ahorra?** Ahorra el evaluador + trazas + selección de versiones valid-time + tests golden + compilación cacheable. No ahorra: bitemporalidad, precedencia, fail-closed de negocio, GIS, pipeline de evidencia. Estimación honesta: evita ~30-40% del motor, no más.
10. **¿Riesgos como dependencia?** Bus factor organizativo (4★), churn de API (mitigado por artefactos versionados exactos), ausencia de binarios Windows (compilar vía CI Linux/Docker — verificado en spike), `rulespec-es` sin licencia ni contenido de nuestro dominio.

**Wrapper obligatorio (diseño):** BD legal → selección (knowledge_date, activity_date) → emisión RuleSpec → `compile` cacheado por hash del conjunto de versiones → `run-compiled` explain → captura de errores → composición de `legalStatus` + `knowledgeStatus` + `evidence` + `precedenceTrace` + `warnings`. Nunca publicar sin revisión humana los Estados REVIEW→VERIFIED aguas arriba.

**Plan F2 (antes de implementar):** spike de 2 días con `match` sobre `Text` (Activity enum), rendimiento de compile-cache, y binding Python oficial; si alguno falla estructuralmente → fallback documentado a evaluador propio copiando el modelo (las reglas de este dominio son condicionales simples; el riesgo de NO-GO es bajo).

---

## F. GIS decision

- **Almacenamiento:** PostGIS 3.4 (verificado en spike) como única fuente de verdad espacial. SRID de trabajo 4258 (ETRS89) + transformación desde fuentes nativas (OAPN entrega UTM 30N / EPSG:25830 — verificado en el spike). Restricciones de tipo por tabla (`geometry(MultiPolygon,4258)`).
- **Importación:** WFS GeoJSON cuando exista (OAPN: verificado, 17 features con metadatos normativos); Shapefiles (OAPN .rar, IDE de CC.AA.) vía ogr2ogr; servicios que solo dan WMS → buscar WFS/Atom/descarga, WMS solo para visualización. Conectores inspirados en TerriaJS (checklist WMS/WFS/ArcGIS/GeoJSON + errores normalizados).
- **Normalización:** pipeline propio ligero: CRS unificado → `ST_MakeValid` → simplificación controlada → detección de solapes entre scopes (no se fusionan: se conservan todos como capas independientes — el resolver los devuelve todos). Patrones de osmpoidb: staging → derived con `ST_Intersects` → GIST → swap tables.
- **Procedencia (validada en Spike B):** cada geometría referencia `source_document_id` (autoridad, URL canónica, `retrieved_at`, SHA-256 del fichero descargado, `document_type`) + `feature_id` (identidad en la capa origen) + registro de transformación (CRS origen/destino). Los 17 polígonos oficiales OAPN ya se cargaron así (SHA-256 `7fc5077b…678770`).
- **Spatial query:** `ST_Intersects` punto→polígono con índice GIST; cotas de altitud como condiciones tipadas (fact `altitude_m`) alimentadas por DEM, nunca por interpolación ad hoc; distancias (`distance` condition) con `ST_Distance` sobre geography.
- **Actualizaciones:** inmutabilidad: nueva versión de capa = nuevo `source_document` + nueva geometría versionada + `recorded_at`; nunca UPDATE in-place. Detección de cambios: re-descarga periódica + hash (los .rar de OAPN **no están versionados** — riesgo documentado).

**Respuestas 11-17:** (11) sí, suficiente y demostrada; (12) todos los scopes que intersecan se devuelven como lista `applicableScope`; la resolución es del motor de reglas con relaciones explícitas, nunca del GIS; (13) OAPN SIG (WMS/WFS/shapefiles, verificado) + IDEARAGON WMS (verificado GetCapabilities) + IDEs autonómicas (Madrid/Cantabria/IDEAsturias: bloqueadas desde este entorno, NO_VERIFICADO); (14) WFS 2.0.0 GeoJSON (verificado), WMS 1.3.0, shapefile/kmz en .rar; (15) de TerriaJS: checklist de conectores, `TerriaError`, catálogo declarativo con esquema; (16) sí — mínimo pero obligatorio (CRS + MakeValid + registro de transformación); (17) con el patrón del Spike B (URL+hash+retrieved_at+feature_id por geometría).

---

## G. Bitemporal design

**Confirmado por Spike C** (`discovery/spikes/spike-c-bitemporal/`) con el patrón exacto de descubrimiento tardío:

```text
R1 PERMITTED effective 2020-01-01..OPEN, recorded 2020-06-01
   (descubrimiento 2027: D 16/2022 prohibía desde 2022-02-09)
→ resolve(activity=2023-06-15, knowledge=2023-06-15) = PERMITTED  (correcto-en-su-momento)
→ resolve(activity=2023-06-15, knowledge=2028-01-01) = PROHIBITED (tras descubrimiento)
→ sistema vigilante (recorded 2022) habría respondido PROHIBITED
→ retro-auditoría: determinaciones 2023 con PERMITTED → flag STALE + re-review
```

- **Valid time:** `effective_from` / `effective_to` (ABIERTO por defecto; se cierra SOLO cuando se descubre el sucesor, y ese cierre es una fila nueva). Corrección respecto al brief: cerrar `effective_to` retroactivamente **no** es un UPDATE; es un append (`recorded_at` del cierre).
- **System time:** `recorded_at` / `recorded_until` append-only. `recorded_until` solo se marca cuando la versión queda invalidada en nuestro sistema.
- **Append-only:** sí, obligatorio; ninguna mutación in-place. La corrección del spike (dos escenarios contaminados) demuestra por qué la auditoría exige separar escenarios por `recorded_at`.
- **Historical replay:** ambas preguntas del brief respondidas con la misma consulta parametrizada por `knowledge_date`. Además: la intersección vacía (versión expirada + sucesor desconocido a esa fecha de conocimiento) debe devolver **UNDETERMINED + knowledge_status INCOMPLETE** ("sabemos que nuestro conocimiento terminó aquí") — mejor que el silencio de R1 abierto.
- **Alineación con Axiom:** su `enacted_on/known_from` futuros coinciden semánticamente; cuando los implementen, podremos proyectar nuestras fechas sin cambio de modelo.

---

## H. Evidence pipeline

Patrón base: **OpenTermsArchive adaptado** (o copiado pieza a pieza si el stack no encaja):

```text
source discovery          registro de fuentes por piloto: BOE (ELI estable),
  (manual, curado)        BOA/BOCM/BOC, webs de parques, OAPN SIG
        ↓
acquisition               OTA engine adaptado: HTML (jsdom), PDFs (binarios),
                          MHTML/puppeteer fallback; "como un usuario"
        ↓
immutable snapshot        git-backed o S3+WORM; SHA-256 = ID; retrieved_at =
  (NUNCA saltar)         author date; trailers de commit con metadatos
        ↓
change detection          diff por contenido; DOCUMENT_STRUCTURE_CHANGE,
  (hash + selectors)      404/403/5xx → issue con label; validFrom/validUntil
        ↓
candidate extraction      IA propone: LegalFragments (locator + exact_text),
  (IA, NUNCA publica)     reglas candidatas, relaciones (OVERRIDES…),
                          condiciones tipadas; siempre con evidencia enlazada
        ↓
human LEGAL review        RuleReviewEvent: DISCOVERED → EXTRACTED →
                          REVIEW_REQUIRED → LEGAL_REVIEWED
        ↓
human SPATIAL review      ¿el fragmento aplica a ESTE polígono? →
  (separada, requisito)   SPATIAL_REVIEWED
        ↓
publish                   VERIFIED → PUBLISHED; append-only; hashed release
        ↓
stale/review cycle        re-crawl programado por criticidad; hash mismatch
                          o DOCUMENT_STRUCTURE_CHANGE → STALE /
                          REVIEW_REQUIRED automático; check_date estilo
                          StreetComplete para observaciones de campo
```

**Respuestas 27-31:** (27) aportan: snapshot-previo-a-extracción, SHA como ID, commits tipificados (separación cambio-fuente vs cambio-extractor), reporter de inaccesibilidad clasificado, principios anti-confianza, firmas; (28) hash estable del contenido relevante + selectores + detección de estructura (labels OTA) + issues automáticos; (29) snapshot binario del PDF bajo la misma URL de declaración (el SHA cambia; el historial git mantiene todos los binarios; recuperación por checkout); (30) re-descarga + SHA-256 por capa + `recorded_at` de la nueva versión de scope (los .rar de OAPN obligan a esto); (31) dispara `STALE`: hash mismatch, fallo estructurado, `document_status: derogated` detectado en re-crawl, GIS hash change, o check_date vencido de una observación de campo que contradice una regla (→ REVIEW_REQUIRED, no cambio automático).

---

## I. Three pilot matrix

Hallazgo importante: **el brief contenía tres hipótesis normativas incorrectas**, corregidas con verificación (subagente + BOE):

- Picos: declaratoria = **Ley 16/1995** (`BOE-A-1995-12915`), no "Ley 1/2014" (ELI 404 verificado). PRUG estatal RD 384/2002 (`BOE-A-2002-9576`), con **vigencia dudosa** (afirmación "suspendido por sentencia del TS" solo en Wikipedia con `cita requerida` → riesgo alto). **PRUG cántabro novísimo: Decreto 57/2026** (BOC 4-8-2026) — el parque ya está operando con régimen asimétrico por CC.AA.
- Ordesa: declaratoria = **Ley 52/1982** (`BOE-A-1982-19494`); la Ley 30/2014 (`BOE-A-2014-12588`) es la ley marco de la Red. PRUG actual = **Decreto 49/2015 (Aragón)**, no RD 389/2006. **Decreto 16/2022** modifica el régimen de pernocta: vivac **prohibido en todo el sector Ordesa desde 9-2-2022** (VERIFICADO en pnomp.es y MITECO); el PRUG anterior (RD 409/1995, vigencia agotada) permitía tienda ≤1,30 m sobre 2.100 m — **el override temporal Ordesa-style existe y está documentado**.
- Guadarrama: declaratoria = Ley 7/2013 (`BOE-A-2013-6900`). PRUG CM = **Decreto 18/2020**, con texto consolidado que incorpora **3 sentencias TSJM (1135/2021, 1003/2022, 135/2023)** y Decreto 238/2023; PRUG CyL = Decreto 16/2019. "RD 595/2014" refutado (era el Plan Hidrológico del Júcar). **El TSJM anuló el art. 48.2 de pernocta (cota 2.000 m vs 2.100 m)** por no regresión — el caso de nulidad judicial existe, verificado vía Europa Press + PDF consolidado del parque.

| Piloto | Casos difíciles que cubre | Fuentes oficiales necesarias |
|---|---|---|
| **Picos** | (1) ausencia/ambigüedad de PRUG estatal vigente → fail-closed; (2) **régimen distinto por CC.AA. dentro del mismo parque** (D 57/2026 solo Cantabria; el mismo punto cambia de régimen cruzando la frontera autonómica); (3) refugios federativos con reservas externas (Vega de Ario, Cabaña Verónica) como capa operativa separada; (4) acceso estacional Lagos de Covadonga (override temporal); (5) ampliación 2014/15 → geometría versionada | Ley 16/1995; RD 384/2002 + estado real de vigencia (sentencia TS a localizar); D 57/2026 BOC; PRUG Asturias/CyL (a localizar); OAPN WFS/shapefiles (VERIFICADO); IDEs Asturias/Cantabria/CyL |
| **Ordesa** | (1) **override temporal verificado** (D 16/2022 cambia vivac → prohibido); (2) cotas por sector no uniformes (1.650/1.800/2.550 m — regla de altitud parametrizada por sector + DEM); (3) excepción espacial con estado dinámico (zona Góriz, aforo/reserva, 90→50 plazas); (4) restricciones operativas de acceso (Torla/Pradera, avisos del parque); (5) cadena normativa larga (1918→1982→1995→2015→2022) para probar replay histórico | Ley 52/1982; RD 409/1995; D 49/2015 (BOA 80/2015); D 16/2022 (BOA); pnomp.es normativa+avisos; refugio Góriz (reservas); OAPN + IDEARAGON WMS (VERIFICADO) |
| **Guadarrama** | (1) **nulidad judicial parcial como override** (art. 48.2 anulado → volver al estado precedente); (2) doble PRUG territorial (CM 18/2020 vs CyL 16/2019) con versiones distintas; (3) **reglas indexadas a cartografía del propio PRUG** (Anexo III: zonas de escalada y pernocta al raso — sin esa capa, fail-closed); (4) resoluciones anuales de dirección (Pedriza 10-3-2026, BOCM); (5) solapes PN/PORN/Parque Regional/ZEPA + Área de Especial Protección Valsaín (ya en la capa OAPN, verificado) | Ley 7/2013; D 18/2020 (consolidado con sentencias, PDF del parque VERIFICADO); D 16/2019 CyL; sentencias TSJM (ECLI a obtener — evidencia débil hoy); resoluciones BOCM; OAPN (VERIFICADO) + geoportal CM (NO_VERIFICADO desde este entorno) |

---

## J. Unknowns

**Unknown but acceptable** (se gestionan con el pipeline, no bloquean):
- Contenido exacto de PRUG Asturias/CyL de Picos y sentencia TS sobre RD 384/2002 (se resolverán en la fase de ingesta del piloto).
- Tamaño real del extract PMTiles de España y rendimiento PMTiles-local en iOS (#1130).
- Detalles de armonización de condiciones tipadas por documento (cada norma las expresa distinto).

**Must solve before implementation** (F2, antes del milestone 1):
1. Compatibilidad de Axiom con Activity como enum (`match` sobre `Text`) y rendimiento del compile-cache por knowledge-state.
2. Licencia para nuestro uso del patrón/rulespec-es (sin LICENSE hoy) y decisión de layout: `rulespec-es` propio (fork del layout) vs módulos independientes.
3. Acceso real a geoportal.comadrid.org, ide.cantabria.es, reservasonline.aragon.es (bloqueo del entorno de esta investigación, no de las fuentes) + obtención de ECLI de las sentencias TSJM.
4. Decisión OTA-engine-adaptado vs patrón-copiado (implica stack Node/Mongo/git en producción).

**Can defer:**
- Spike D en dispositivo (Expo+PMTiles offline), capa comunitaria, app móvil, multi-idioma, España completa.

---

## K. Risk register

| Riesgo | Gravedad | Mitigación |
|---|---|---|
| **Falso positivo legal** (PERMITTED erróneo) | **Crítica** | Fail-closed global: ausencia de evidencia → UNDETERMINED; `exactly_one` obligatorio; asimetría de diseño (prohibición por defecto en cada gateway); warning permanente de "posibles restricciones operativas no capturadas" |
| Interpretación jurídica errónea (IA o humana) | Alta | IA solo propone; doble revisión (jurídica + espacial); fragmento exacto + locator + hash siempre visibles; Blawx como referencia de UI de revisión |
| Source drift (PDFs sustituidos, .rar sin versión) | Alta | Patrón OTA: snapshot+hash+diff+issues; OAPN .rar ya identificado como caso crítico |
| GIS drift (geometrías que cambian sin aviso) | Alta | hash por capa + `recorded_at` + re-verificación programada; geometría versionada append-only |
| Temporal overrides mal modelados | Alta | Spike C validado; cierre retroactivo append-only; replay obligatorio en tests por piloto |
| Cambios judiciales | Media-Alta | Guadarrama como piloto de nulidad; ingestión de sentencias con ECLI; relación `REPEALS/OVERRIDES` con evidencia |
| Offline staleness (regla local desactualizada) | Media | knowledge_status por paquete offline; aviso de edad del paquete; sincronización delta de PMTiles (nuevo build) |
| Licensing (Axiom rulespec-es sin licencia; OTA EUPL; StreetComplete GPL-3; 100cims sin licencia) | Media | F2: revisión legal; solo copiar patrones de GPL-3; nada de código de 100cims; EUPL compatible con producto público UE, decidir conscientemente |
| Dependencia inmadura (Axiom 4★, bus factor organizativo) | Media | BD como fuente de verdad; artefactos regenerables; fallback evaluador propio factible (reglas simples) |
| Community abuse / masificación de spots | Media | Micro-observaciones estructuradas (no reseñas), moderación por anomalías, ocultación de puntos sensibles por defecto (ZPP, zonas de cría), nunca transforman legalidad |
| Conflicto no resuelto mal señalizado | Media | `resolucion_unica` fallida → CONFLICT visible + unresolvedConflicts en la salida; nunca silencioso |

---

## L. Final milestone recommendation

### `PURE_BITEMPORAL_GEOSPATIAL_LEGAL_RESOLVER` — confirmado

Secuencia de implementación recomendada (si F2 confirma Axiom):

1. **F2 (2-3 días):** spikes de cierre — `match Text`/enum Activity en Axiom; compile-cache por knowledge-state; acceso a IDEs bloqueadas; decisión licencias.
2. **Milestone 1 — Pure resolver (CLI/API, sin mapa):** BD bitemporal (SourceDocument/LegalFragment/SpatialScope/LegalRuleVersion/RuleRelation/RuleReviewEvent) + ingesta de evidencia de **un solo piloto (Ordesa)** — es el que tiene override temporal verificado y cadena normativa completa — + wrapper Axiom + `resolve()` con salida completa (legalStatus, knowledgeStatus, applicableScope, conditions, ruleVersions, evidence, precedenceTrace, unresolvedConflicts, warnings, decisionReason) + suite de replay temporal (Spike C industrializado) + casos Ordesa pre/post D 16/2022.
3. **Milestone 2 — Pilotos 2 y 3:** Picos (régimen por CC.AA.) y Guadarrama (nulidad TSJM + Anexo III cartográfico) sobre el mismo esqueleto; pipeline de evidencia OTA-adaptado en producción con BOE/BOA/BOCM.
4. **Milestone 3 — Interfaz:** API HTTP + visor minimalista MapLibre (web) de scopes; Spike D offline en dispositivo.
5. **Posterior:** observaciones estructuradas (patrón quest), refugios.info, app.

---

## Respuestas rápidas 18-26 (OSM/offline)

18. OSM aporta: refugios/shelters/barreras/carteles/gates/water points como contexto y como **objetos de micro-observación**; y su derivación a scopes de contexto (núcleos, pistas). 19. **Jamás inferir de OSM**: legalidad del vivac, vigencia de normas, fronteras de espacios protegidos como fuente (solo referencia visual), condiciones normativas. 20. De osmpoidb reaprovecha el patrón completo flex→PostGIS→ST_Intersects→triggers→replicación por minuto. 21. Sí — API refuges.info evita BD propia de refugios (cacheando con `depuis` incremental). 22. Cachear localmente: polígonos normativos (PMTiles propios), POIs de pernocta cacheados con TTL + `derniere_modif`, y el estado de knowledge del paquete offline.
23. Sí (MapLibre RN + PMTiles soporte nativo verificado; caveat #1130). 24. `pmtiles extract` por región sobre builds diarios; tamaño España a medir. 25. Sí — nuestros polígonos normativos como PMTiles propio (tippecanoe) con atributos de versión normativa; **el resolver remoto sigue siendo la autoridad** — el offline solo señala y avisa de antigüedad. 26. knowledge_status por región + fecha de build del paquete + badge "verificado online el …"; offline nunca responde PERMITTED/PROHIBITED sin acceso a knowledge actual → estado presentado como "según datos de <fecha>".

## Respuestas rápidas 32-35 (comunidad)

32. El contrato quest de StreetComplete: filtro de elegibilidad + formulario cerrado atómico + mapping determinista respuesta→atributos + `check_date` + ámbito geográfico. 33. Formularios para: existencia/estado de cartel (con foto geolocalizada — patrón MapComplete/Panoramax), estado del refugio (abierto/plazas/agua), acceso cerrado (barrera/cadena), presencia de ganado/estado de campo. 34. **Nunca como "hecho legal"**: opiniones, valoraciones de riesgo, "no hay nadie vigilando", cumplimiento observado por terceros, límites imprecisos, ni cualquier cosa que no sea observable y fechable. 35. Prevenir masificación de spots: por defecto solo observaciones sobre **elementos ya públicos** (carteles, refugios, barreras), moderación estructurada con detección de anomalías, sin puntos libres, ocultación de coordenadas exactas en zonas sensibles (ZPP/avifuana), y rate-limits por zona.

---

## Cierre

```text
PROJECT_STATUS=TECHNICALLY_VALIDATED (condicionado a F2)
RULE_ENGINE_DECISION=YES_WITH_WRAPPER (Axiom RuleSpec; BD bitemporal propia como fuente de verdad; fallback evaluador propio documentado)
GIS_DECISION=PostGIS fuente de verdad espacial + patrón osmpoidb + provenance URL/hash/retrieved_at/feature_id (validado Spike B con datos OAPN oficiales)
OFFLINE_DECISION=MapLibre React Native + PMTiles (REUSE); Spike D en dispositivo diferido a Milestone 3
EVIDENCE_PIPELINE_DECISION=ADAPT OpenTermsArchive (o COPIAR_PATRÓN si el stack Node/Mongo/git no encaja; decidir en F2)
BITEMPORALITY_DECISION=BUILD propietario append-only (valid time + system time; validado Spike C); alineado con el diseño futuro (no implementado) de Axiom
PILOT_READINESS=Ordesa ALTA (normas y override verificados); Picos MEDIA (PRUGs autonómicos incompletos, vigencia RD 384/2002 sin confirmar); Guadarrama MEDIA (sentencias TSJM sin ECLI, Anexo III cartográfico por obtener)
IMPLEMENTATION_RECOMMENDATION=Milestone 1 = PURE_BITEMPORAL_GEOSPATIAL_LEGAL_RESOLVER (CLI/API, piloto Ordesa, replay temporal como suite de tests)
BLOCKERS=Ninguno duro. Pendientes F2: (1) enum Activity/Text match en Axiom + compile-cache; (2) licencia rulespec-es y layout propio; (3) acceso a IDEs CM/Cantabria/Aragón y ECLI sentencias TSJM; (4) decisión stack OTA
```
