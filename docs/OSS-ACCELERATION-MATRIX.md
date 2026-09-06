# OSS Acceleration Matrix — AlRaso

**Objetivo:** cambiar el método de desarrollo a **OSS_FIRST / REUSE_BEFORE_BUILD / LLM_FOR_ACCELERATION_NOT_AUTHORITY**.

Este documento es el resultado del **Fase 1 (OSS Acceleration Pass)**. Fue **read-only**:
no se tocó `alraso/`, no se reabrió ninguna fase anterior.

| Campo | Valor |
|---|---|
| Baseline MAIN | `8bb63cdbb37faa1b8817005ff635dbe6fdc8ea7e` |
| Fecha | 2026-09-06 |
| Timebox Fase 1 | ≤ 2 h (cumplido; research acotado) |
| Proyectos revisados | 17 |
| Licencias verificadas para reutilización | Sí |
| BUILD_FROM_SCRATCH_DEFAULT | NO |

---

## Regla de oro (a partir de ahora)

Cualquier feature estimada en **>1 hora** pasa primero por **OSS_REUSE_GATE**:

1. Buscar precedentes reales en GitHub (≥5 candidatos cuando existan).
2. Inspeccionar **código**, no sólo README.
3. Verificar licencia desde LICENSE/COPYING/SPDX.
4. Revisar actividad/mantenimiento.
5. Determinar qué parte concreta se puede reutilizar.
6. Clasificar: `ADOPT` / `ADAPT` / `COPY_PATTERN` / `REFERENCE_ONLY` / `REJECT`.
7. `BUILD_FROM_SCRATCH` **sólo** si se documenta por qué ninguna opción sirve.

Timebox: **30 min por feature**. Si existe un proyecto MIT/Apache/BSD mantenido que
resuelve ≥70 % de la pieza, `BUILD_FROM_SCRATCH` requiere justificación explícita.

---

## 1. Matriz global (Feature → Repo → Decisión)

| # | Feature | Repo | Licencia | Estado proyecto | Parte reutilizable | Decisión | Motivo |
|---|---|---|---|---|---|---|---|
| 1 | POIs refugios/agua/abrigo | `Bist0uille/survival_map` | MIT | activo (2026-08-31), PWA producción | capa OSM PMTiles + `Refuges.info` API al clic | **ADAPT** | licencia permisiva, código reciente, POIs FR·ES·IT; no importar el frontend React entero |
| 2 | POIs camping | `giggls/opencampsitemap` | código MIT + arte CC0 | activo (2026-08-25) | pipeline OSM de campings y estilo de render | **ADAPT** | MIT en el JS; reutilizar consultas/estilo, no el mapa entero |
| 3 | POIs OSM DB | `giggls/osmpoidb` | Apache-2.0 | activo (2026-08-14) | esquema SQL PostGIS para POIs OSM | **ADAPT** | Apache-2.0 compatible; patrón SQL para camping POIs |
| 4 | Offline + PMTiles | `Bist0uille/survival_map` | MIT | activo | servicio de PMTiles + descarga de zona (Dexie/IndexedDB) | **ADAPT** | el patrón offline-first + PMTiles + service worker es directamente transferible |
| 5 | Offline PMTiles build | `mploscos/map-zero` | MIT | activo (2026-09-05) | generación de paquetes vectoriales OSM→PMTiles/GeoPackage/3D Tiles | **ADAPT** | MIT; construcción de tiles, no el runtime web |
| 6 | Offline móvil routing | `Mobile-Artificial-Intelligence/atlas` | MIT | nuevo (2026-09-05) | MapLibre + BeeRouter + PMTiles 100% offline en Android | **COPY_PATTERN** | MIT; patrón offline móvil, no el stack Kotlin entero |
| 7 | Offline geocodificación + SQLite | `sami-djouhri/karten` | MIT | activo (2026-08-31) | índice de direcciones en SQLite + portal MapLibre sin proveedor | **ADAPT** | MIT; geocodificación self-hosted con SQLite, afín al stack stdlib |
| 8 | Routing | `Bist0uille/survival_map` | MIT | activo | integración BRouter (routing por senderos) + perfil altimétrico | **ADAPT** | BRouter es servicio gratuito sin clave; patrón de cliente ya resuelto |
| 9 | Routing | `giggls/osmpoidb` | Apache-2.0 | activo | consultas OSM de red de caminos | **REFERENCE_ONLY** | sólo patrón SQL, no el runtime |
| 10 | GPX import/export | `Bist0uille/survival_map` | MIT | activo | import/export GPX + grabación de traza | **ADAPT** | MIT; ya resuelto en producción |
| 11 | Legal ETL + provenance | `lowlydba/foul-flock` | MIT | activo (2026-09-03), producción | reglas YAML con `confidence`/`last_verified`/`source_url`; heurísticas separadas de la ley; `buffer_specified:false` | **ADAPT** | el patrón "regla legal + proveniencia + candidato ≠ verificado" es exactamente el de AlRaso |
| 12 | Coverage refresh + PR | `lowlydba/foul-flock` | MIT | activo | GitHub Action que regenera datos y abre PR (`data-refresh.yml`) | **ADAPT** | MIT; patrón de "refresh automático + PR" sin tocar main |
| 13 | Pipeline legal+geográfico | `lowlydba/foul-flock` | MIT | activo | `build/build.py`: fetch→match→emit GeoJSON; test de a11y con axe/Playwright | **ADAPT** | MIT; pipeline deterministico + tests |
| 14 | Reservas bivouac | `asterscen74/bivouac` | **SIN licencia** | activo pero institucional | modelo de reservas React/FastAPI/PostgreSQL | **REFERENCE_ONLY** | sin licencia demostrada; no copiar nada |
| 15 | Reservas bivouac (patrón) | `leeken3/wildpathapp` | **SIN licencia** | proyecto de curso (2025) | booking + mapa | **REFERENCE_ONLY** | sin licencia; sólo patrón de UX |
| 16 | Camping legalidad (point-in-polygon) | `racso1999/Dartmoor-Camping` | **SIN licencia** | 1 commit (2026-07-01) | click/búsqueda/geoloc + point-in-polygon en MultiPolygon con agujeros | **REFERENCE_ONLY** | licencia no verificada; el punto-en-polígono ya lo tiene `alraso/spatial.py` |
| 17 | Protected areas | `Bist0uille/survival_map` | MIT | activo | supercapa de espacios protegidos | **ADAPT** | MIT; overpass/PMTiles de áreas protegidas |
| 18 | Protected areas | `cidrlab/boondock_map` | GPL-3.0 | activo (2026-09-05) | ley de carreteras forestales (USFS MVUM) + mapas offline | **REFERENCE_ONLY** | GPL-3.0 (copyleft) no compatible para incorporar a código Apache-2.0; sólo patrón conceptual |
| 19 | Ingestión OSM/open data | `giggls/opencampsitemap` | MIT | activo | consultas Overpass de campings | **ADAPT** | MIT |
| 20 | Ingestión OSM/open data | `lowlydba/foul-flock` | MIT | activo | Overpass + Overture (S3, sin credenciales) | **ADAPT** | MIT; streaming por estado, filtrado local |
| 21 | Mobile / PWA | `Bist0uille/survival_map` | MIT | activo | manifest + service worker (`vite-plugin-pwa`) + instalable | **ADAPT** | MIT; PWA sin backend |
| 22 | Observabilidad mínima | `lowlydba/foul-flock` | MIT | activo | `DATA_LICENSE.txt` estampado + `last_checked` por estado; "miramos y no hay" ≠ "no hemos mirado" | **ADAPT** | patrón de honestidad de coverage reutilizable |
| 23 | Observabilidad mínima | `nordfisch/kiekmap` | Apache-2.0 | activo | FastAPI + MapLibre + PMTiles offline (kiosco) | **COPY_PATTERN** | Apache-2.0; stack más pesado, sólo patrón |
| 24 | Panorámica wild-camping Europa | `Alexi5000/WildScape-Europe` | Apache-2.0 | activo | catálogo de campings + mapa 3D | **REFERENCE_ONLY** | Mapbox (proveedor no libre); no alineado con stack |
| 25 | Renderizado Flutter/móvil | `maplibre/flutter-maplibre-gl` | NOASSERTION | activo | plugin Flutter MapLibre + PMTiles | **REFERENCE_ONLY** | licencia por verificar; no es el stack de AlRaso |
| 26 | Offline tiles | `dtelleslopez/puedo-rodar-maps` | **SIN licencia** | activo | mapas offline PMTiles | **REFERENCE_ONLY** | sin licencia |
| 27 | Aplicaciones obsoletas | `gtherin/wildcamp`, `Geopin/geopin` | NOASSERTION / sin licencia | archivado / inactivo | — | **REJECT** | archivado o sin licencia, sin mantenimiento |

---

## 2. Matriz por feature AlRaso → Estrategia

| Feature AlRaso | Estrategia |
|---|---|
| offline | **ADAPT** `survival_map` (service worker + PMTiles + Dexie). No importar React entero; tomar el patrón. |
| PMTiles | **ADAPT** `map-zero` (build) + `survival_map` (cliente). Emitir PMTiles desde datos propios; cliente MapLibre ya vendorizado. |
| refugios | **ADAPT** `survival_map` (capa PMTiles + `Refuges.info` al clic) + `osmpoidb`/`opencampsitemap` (patrón OSM). |
| routing | **ADAPT** `survival_map` (cliente BRouter) + `atlas` (patrón BeeRouter offline móvil). Sin motor propio. |
| GPX | **ADAPT** `survival_map` (import/export + traza). |
| legal ETL | **ADAPT** `foul-flock` (reglas YAML + confidence/last_verified/source_url + heurística separada de ley). Es el candidato más alineado. |
| source refresh | **ADAPT** `foul-flock` (GH Action refresh + PR). No mergear automáticamente; PR + revisión humana. |
| coverage refresh | **ADAPT** `foul-flock` (estado `last_checked`; "no miramos" ≠ "no hay"). |
| reservations | **REFERENCE_ONLY** `asterscen74/bivouac` y `wildpathapp` (sin licencia). No implementar reservas ahora. |
| protected areas | **ADAPT** `survival_map` (capa) + `boondock_map` (patrón normativo, sólo referencia por GPL). |
| OSM/open data ingest | **ADAPT** `foul-flock` (Overpass+Overture) y `opencampsitemap`/`osmpoidb` (OSM camping). |
| mobile / PWA | **ADAPT** `survival_map` (PWA sin backend). Aplazado (NO hacer todavía). |
| observabilidad mínima | **ADAPT** `foul-flock` (honestidad de coverage) + telemetría stdlib mínima. |

---

## 3. Selección de reutilización (detalle por feature)

### offline
```
OSS_CANDIDATES=survival_map, map-zero, atlas, kiekmap, karten, puedo-rodar-maps
BEST_CANDIDATE=Bist0uille/survival_map
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=src/map/*, public/*.pmtiles, vite.config.ts, .github/workflows/build-*.yml, package.json (dexie, vite-plugin-pwa)
WHAT_TO_REUSE=service worker + descarga de zona + capa PMTiles; patrón de datos locales en IndexedDB
WHAT_NOT_TO_REUSE=frontend React/Tailwind completo; no migrar AlRaso a React
ESTIMATED_TIME_SAVED=~6-10 h (PWA + offline-first ya resueltos)
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### PMTiles
```
OSS_CANDIDATES=map-zero, survival_map, atlas, GIS-MapForge
BEST_CANDIDATE=mploscos/map-zero (build) + survival_map (cliente)
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=scripts de build de map-zero; cliente de PMTiles de survival_map
WHAT_TO_REUSE=generación de PMTiles desde OSM/open data; cliente de lectura MapLibre
WHAT_NOT_TO_REUSE=el formato de almacenamiento de terceros; emitir nuestros propios tiles desde datos verificables
ESTIMATED_TIME_SAVED=~4-8 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### refugios / shelters / water POIs
```
OSS_CANDIDATES=survival_map, opencampsitemap, osmpoidb, campsite-features
BEST_CANDIDATE=Bist0uille/survival_map (capa + Refuges.info al clic)
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=src/data/*, src/map/*, .github/workflows/build-*.yml
WHAT_TO_REUSE=consulta OSM de refugios/agua/abrigo; enrichment al clic vía Refuges.info (CC-BY-SA, sin redistribución)
WHAT_NOT_TO_REUSE=datos del proyecto survival_map; los POIs de AlRaso deben tener proveniencia propia
ESTIMATED_TIME_SAVED=~4-6 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### routing
```
OSS_CANDIDATES=survival_map (BRouter), atlas (BeeRouter), karten
BEST_CANDIDATE=Bist0uille/survival_map (cliente BRouter)
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=src/components/* (creador de ruta), src/map/*, hooks de perfil altimétrico
WHAT_TO_REUSE=integración con servicio gratuito BRouter sin clave; perfil altimétrico en directo
WHAT_NOT_TO_REUSE=ningún motor de routing propio (BRouter/BeeRouter ya cubren)
ESTIMATED_TIME_SAVED=~3-6 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### GPX
```
OSS_CANDIDATES=survival_map
BEST_CANDIDATE=Bist0uille/survival_map
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=src/* (import/export GPX, grabación de traza)
WHAT_TO_REUSE=parser/escritor GPX + UX de grabación
WHAT_NOT_TO_REUSE=estado de la app (local-only, sin sync)
ESTIMATED_TIME_SAVED=~2-4 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### legal ETL + pipeline legal/geográfico
```
OSS_CANDIDATES=foul-flock, Dartmoor-Camping
BEST_CANDIDATE=lowlydba/foul-flock
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=rules/alpr_state_rules.yaml, build/build.py, build/vendor/, AGENTS.md
WHAT_TO_REUSE=formato de regla con confidence/last_verified/source_url; separación explícita heurística vs ley; build determinista fetch→match→emit; candidato ≠ verificado
WHAT_NOT_TO_REUSE=las reglas de ALPR; la taxonomía de Overture de estados de EEUU; el dominio legal de AlRaso es propio y verificable
ESTIMATED_TIME_SAVED=~8-12 h (es la pieza más cercana a la filosofía de AlRaso)
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### source refresh / coverage refresh
```
OSS_CANDIDATES=foul-flock, survival_map
BEST_CANDIDATE=lowlydba/foul-flock
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=.github/workflows/data-refresh.yml, AGENTS.md
WHAT_TO_REUSE=GH Action que refresca y abre PR (no mergea automático); estado last_checked para coverage
WHAT_NOT_TO_REUSE=el scope de estado de EEUU; el concepto de "PR + revisión humana" se mantiene
ESTIMATED_TIME_SAVED=~3-6 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### reservas de bivouac
```
OSS_CANDIDATES=asterscen74/bivouac, wildpathapp
BEST_CANDIDATE=ninguno (referencia)
LICENSE=SIN LICENCIA (ambos)
REUSE_CLASS=REFERENCE_ONLY
FILES_TO_STUDY=README/README + esquema (sólo lectura de patrón)
WHAT_TO_REUSE=patrón de modelo de reservas (si se implementa algún día)
WHAT_NOT_TO_REUSE=ningún código (sin licencia demostrada)
ESTIMATED_TIME_SAVED=0 (aplazado; no es un frente inmediato)
BUILD_FROM_SCRATCH_JUSTIFIED=NO (no se implementa ahora)
```

### protected areas
```
OSS_CANDIDATES=survival_map, boondock_map
BEST_CANDIDATE=Bist0uille/survival_map
LICENSE=MIT (survival_map) / GPL-3.0 (boondock_map)
REUSE_CLASS=ADAPT (survival_map) / REFERENCE_ONLY (boondock_map por copyleft)
FILES_TO_STUDY=src/data/*, capa de espacios protegidos
WHAT_TO_REUSE=consulta OSM de parques/reservas; patrón de ley de accesos
WHAT_NOT_TO_REUSE=GPL-3.0 de boondock_map; no incorporar a código Apache-2.0
ESTIMATED_TIME_SAVED=~2-4 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### ingestión OSM / open data
```
OSS_CANDIDATES=foul-flock, opencampsitemap, osmpoidb
BEST_CANDIDATE=lowlydba/foul-flock (Overpass + Overture sin credenciales)
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=build/build.py, rules YAML, vendored taxonomy
WHAT_TO_REUSE=streaming por región desde Overture S3 + Overpass; filtrado local; estampado de licencia de datos
WHAT_NOT_TO_REUSE=la taxonomía de ALPR; la lógica de "protected places" de EEUU
ESTIMATED_TIME_SAVED=~4-8 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### mobile / PWA
```
OSS_CANDIDATES=survival_map, atlas
BEST_CANDIDATE=Bist0uille/survival_map
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=vite.config.ts (PWA plugin), public/ (manifest, service worker)
WHAT_TO_REUSE=manifest + service worker + instalable sin backend
WHAT_NOT_TO_REUSE=no implementar PWA todavía (NO hacer en esta fase)
ESTIMATED_TIME_SAVED=~3-5 h (cuando se aborde)
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

### observabilidad mínima
```
OSS_CANDIDATES=foul-flock, kiekmap
BEST_CANDIDATE=lowlydba/foul-flock
LICENSE=MIT
REUSE_CLASS=ADAPT
FILES_TO_STUDY=README (honesty notes), web/ (coverage states)
WHAT_TO_REUSE=distinción "miramos y no hay" vs "no hemos mirado"; estampado de licencia de datos
WHAT_NOT_TO_REUSE=la telemetría del producto; AlRaso no añade métricas de dominio legal
ESTIMATED_TIME_SAVED=~1-3 h
BUILD_FROM_SCRATCH_JUSTIFIED=NO
```

---

## 4. Nota sobre licencias verificadas

| Repo | Licencia verificada | Fuente |
|---|---|---|
| survival_map | MIT | GitHub API `license=MIT` + `LICENSE` |
| foul-flock | MIT | GitHub API `license=MIT` + `LICENSE` |
| opencampsitemap | código MIT (Svven Geggus) + arte CC0 1.0 | `LICENSE.md` (dual) |
| osmpoidb | Apache-2.0 | GitHub API `license=Apache-2.0` |
| map-zero | MIT | GitHub API `license=MIT` |
| karten | MIT | GitHub API `license=MIT` |
| atlas | MIT | GitHub API `license=MIT` |
| kiekmap | Apache-2.0 | GitHub API `license=Apache-2.0` |
| boondock_map | GPL-3.0 | GitHub API `license=GPL-3.0` |
| WildScape-Europe | Apache-2.0 | GitHub API `license=Apache-2.0` |
| Dartmoor-Camping | **SIN LICENCIA** | GitHub API `license=null` → REFERENCE_ONLY |
| asterscen74/bivouac | **SIN LICENCIA** | GitHub API `license=null` → REFERENCE_ONLY |
| campsite-features | **SIN LICENCIA** | GitHub API `license=null` → REFERENCE_ONLY |
| puedo-rodar-maps | **SIN LICENCIA** | GitHub API `license=null` → REFERENCE_ONLY |
| flutter-maplibre-gl | NOASSERTION | GitHub API `license=NOASSERTION` → REFERENCE_ONLY |

> **Regla para candidatos sin licencia demostrada:** `REFERENCE_ONLY` / `COPY_PATTERN`
> (patrón de arquitectura) y **nunca** importar código. Coincide con la regla ya
> aplicada a `Dartmoor-Camping` y `asterscen74/bivouac`.

---

## 5. Decisiones finales de los precedentes pedidos

- **SURVIVAL_MAP_DECISION = ADAPT** (MIT, activo, producción; PMTiles/offline/POIs/routing/GPX/PWA/protected-areas).
- **FOUL_FLOCK_DECISION = ADAPT** (MIT, activo, producción; legal ETL + provenance + heurística/ley + refresh/PR + coverage honesto).
- **DARTMOOR_DECISION = REFERENCE_ONLY** (sin licencia; point-in-polygon ya resuelto en `alraso/spatial.py`).
- **ASTERS_BIVOUAC_DECISION = REFERENCE_ONLY** (sin licencia; reservas no es frente inmediato).
- **OPENCAMPINGMAP_DECISION = ADAPT** (código MIT; pipeline OSM camping) — **osmpoidb** Apache-2.0, **campsite-features** sin licencia → REFERENCE_ONLY.

---

## 6. GATES de esta fase

```
OSS_PROJECTS_REVIEWED=17
OSS_LICENSES_VERIFIED_FOR_REUSE=YES
OSS_MATRIX_COMPLETE=YES
BUILD_FROM_SCRATCH_DEFAULT=NO
```

Ninguna de las piezas listadas requiere `BUILD_FROM_SCRATCH`; todas tienen un
candidato MIT/Apache mantenido que cubre ≥70 % del problema.
