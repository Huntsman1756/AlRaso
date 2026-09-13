# SPAIN COVERAGE G0 — OSS_REUSE_GATE

Inspección real de repositorios (API GitHub + lectura de código), no sólo README.
Fecha: 2026-09-13. Convención de decisión: `ADOPT` / `ADAPT` / `PATTERN` / `REJECT`.

## Resultados

| Repo | Licencia | Actividad | Qué hace realmente | Decisión | Motivo / trigger de revisión |
|---|---|---|---|---|---|
| `legalize-dev/legalize-pipeline` | MIT | activo (push 2026-09-04) | Pipeline multi-país legislación→Git: fetcher `es/` sobre **API BOE** (`BOEClient` rate-limit+ETag cache, `BOEDiscovery` catálogo+sumarios, parsers XML→`Block`/`NormMetadata`), transformer genérico→Markdown, committer git con `GIT_AUTHOR_DATE` histórico e idempotencia por trailer `Source-Id` | **PATTERN** (+ADAPT puntual) | La separación `LegislativeClient/NormDiscovery/TextParser/MetadataParser` es exactamente el split que proponemos por función — patrón validado en 25+ países. Su España = **solo BOE**; no resuelve gacetas autonómicas (nuestro problema real). ADAPT si se quiere su cliente BOE con cache ETag. Trigger: cuando el spec pida ingesta BOE diaria |
| `legalize-es` (datos publicados por el pipeline) | MIT (según proyecto) | activo | Leyes españolas como Markdown versionado en Git (cada reforma = commit) | **PATTERN** | Señal de descubrimiento y diff histórico. Nunca sustituto de fuente oficial ni auto-publicador (regla del proyecto). Trigger: validar diffs contra BOE antes de cualquier uso |
| `ioseobcn/normativa-dev` | MIT | baja (push 2026-08-19, 1★) | MCP server + CLI sobre legislación consolidada española con dominios temáticos | **PATTERN** | Patrón de recuperación por artículo/dominio; madurez insuficiente para ADOPT. Trigger: si crece comunidad/cobertura autonómica |
| `martgnz/es-atlas` | MIT | inactivo (push 2024-02-11) | TopoJSON pre-construido desde datos oficiales IGN | **PATTERN** | Ingeniería commodity "descargar geo oficial → transformar → publicar artefacto web". Dataset concreto es administrativo, no legal. No mantenido → no adoptar pipeline tal cual |
| `lowlydba/foul-flock` | MIT | activo (push 2026-09-07) | Cross-reference cámaras ALPR vs estatutos estatales: reglas YAML con `confidence`/`last_verified`/`source_url`, refresh automático que **abre PR** (no publica), heurísticas separadas de ley | **PATTERN** (fuerte) | Modelo "datos refrescados automáticamente + reglas legales explícitas + provenance + revisión humana por PR" = exactamente el modelo de confianza de AlRaso. Copiar el *flujo*, no el código (dominio US) |
| `iderioja/base_datos_geografica` | **sin licencia** | inactivo (2020-01) | GeoJSONs de La Rioja (incl. Red Natura, hábitats, Ramsar) | **REJECT** | Sin licencia → no reutilizar nada. Valor residual: demuestra que las IDE autonómicas publican capas ENP/RN2000 (patrón de dónde buscar). Trigger: relicenciado o sustituido por IDE activa equivalente |
| `projecte-aina/docg-pipeline` | Apache-2.0 | inactivo (2023-12, 0★) | Pipeline de procesamiento DOGC | **PATTERN** | Referencia para DOGC si se necesita más que la API Socrata+ELI ya verificada. Trigger: si Socrata/ELI resultan insuficientes para texto completo estructurado |

## Segunda pasada (búsqueda amplia GitHub, 2026-09-13)

| Repo | Licencia | Actividad | Qué hace realmente | Decisión | Motivo / trigger |
|---|---|---|---|---|---|
| `ComputingVictor/MCP-BOE` | MIT | activo (48★) | Servidor MCP sobre la API oficial del BOE: consolidada + sumarios + tablas auxiliares + lectura de PDFs | **ADAPT** | Wrapper MCP maduro; reutilizar sus patrones de cliente BOE (no el MCP como tal). Trigger: implementación del canal BOE |
| `leyabierta/leyes` | **SIN licencia** | activo | Legislación consolidada en Markdown por jurisdicción (`es/`, `es-an`, `es-cl`...) — pero alimentado esencialmente desde BOE: `es-cl` solo contiene `BOCL-h-*` históricos (sin Decreto 17/2025 Picos) | **REJECT** (datos) + **PATTERN** (modelo) | Sin licencia → los datos no son reutilizables aunque sean "abiertos". Confirma además que quien basa la cobertura CCAA en BOE hereda su agujero de PRUGs |
| `leyabierta/leyabierta` (engine) | **AGPL-3.0** | activo | Motor TS que genera el repo anterior | **REJECT** | Copyleft incompatible con el codebase del proyecto |
| `knockatnight/es-legis` | **SIN licencia** | activo | Histórico git de leyes consolidadas | **REJECT** | Sin licencia |
| `Asensio94/observatorio-alegaciones` | MIT | activo | Lee BOE+BOC Cantabria diario, geolocaliza por municipio, **cruza con Red Natura 2000** y GBIF; GitHub Actions → commit → Pages | **ADAPT/PATTERN** | Demuestra el cruce norma↔geometría en producción y documenta un **problema operativo real: los servidores del Gobierno de Cantabria bloquean IPs de runners de GitHub** — solucionan con fetch local en España + push. Su `boc_cantabria.py` es referencia directa |
| `unepwcmc/ProtectedPlanet` (WDPA) | BSD-3 (código) / **datos con restricción de uso comercial** | activo | Base mundial de áreas protegidas | **REJECT** como fuente de datos | Los **términos de WDPA restringen uso comercial** — no usar como fallback del inventario ENP; EEA CDDA sigue siendo el cross-check libre |
| `edusu/spanish-jurisprudence-search` | NOASSERTION | activo | Cliente single-shot del buscador CENDOJ (sin API oficial; WAF) | **PATTERN** | Confirma: **CENDOJ no tiene API** — la cadena de jurisprudencia es scraping frágil con WAF; diseñar para degradación, no para feed |
| `JIBANEZSA/mcp-cendoj-sentencias` | MIT | reciente | MCP para CENDOJ | **PATTERN** | Mismo techo: scraping del portal CGPJ |
| `hadronomy/canary` | MIT | activo | Asistente legal IA que parsea BOE | **PATTERN** | Referencia de parsing BOE; dominio distinto |
| `TwinConsult-AS/akn-profiler` | MIT | activo | Toolkit de perfiles/validación Akoma Ntoso | **ADAPT** | DOGC sirve AKN — este toolkit ayuda a validar/parsear ese XML. Trigger: parser DOGC |
| `laws-africa/indigo-akn` | MIT | activo | Librerías AKN de la plataforma Indigo (madura) | **ADAPT** | Referencia seria para parsear Akoma Ntoso (canal DOGC) |
| `es-property-data/es-boe-subastas` | Apache-2.0 | activo | Collector de subastas BOE | **PATTERN** | Solo dominio subastas; patrón de fetch BOE |
| `matematicsolutions/it-eli-mcp`, `lu-eli-mcp` | Apache-2.0 | activos | MCP sobre ELI de Normattiva/Legilux | **PATTERN** | Patrón ELI-resolver para otros países; España ELI vía BOE/DOGC ya probado |

## No encontrados / verificación negativa

- **`official-sources-esp`**: la búsqueda en GitHub no devuelve ese repo; los candidatos cercanos
  no encajan (`fedec65/bettercallclaude-espana` AGPL-3.0 — copyleft, REJECT por licencia;
  MCP wrappers sin licencia). Registrar como `NOT_FOUND` — no contar con él.
- Búsquedas `vivac legal`, `acampada libre`, `bivouac legal spain`, `montaña regulacion` →
  **0 repositorios**. Nadie ha resuelto públicamente el problema específico de AlRaso
  (regla de vivac/acampada por espacio protegido con provenance) — confirma el valor del
  proyecto y que no hay atajo OSS para el núcleo legal.

## Síntesis

```text
ADOPT directo:            0  (nada listo para enchufar)
ADAPT puntual:            MCP-BOE (patrones cliente BOE), legalize-pipeline (cliente BOE ETag),
                          akn-profiler / indigo-akn (Akoma Ntoso para DOGC),
                          observatorio-alegaciones (boc_cantabria.py + cruce geo)
PATTERN (arquitectura):   legalize-pipeline (interfaces por función),
                          foul-flock (refresh→PR + provenance + reglas explícitas),
                          observatorio-alegaciones (diario→geo→RN2000→commit),
                          leyabierta (modelo ley=fichero/reforma=commit, sin reutilizar datos),
                          es-atlas, docg-pipeline, normativa-dev, canary, CENDOJ clients
REJECT:                   leyabierta/leyes (sin licencia), leyabierta engine (AGPL),
                          es-legis (sin licencia), iderioja (sin licencia),
                          bettercallclaude-espana (AGPL), WDPA (uso comercial restringido)
```

## Problemas destapados por la pasada amplia

1. **Geo-bloqueo de gacetas**: el Gobierno de Cantabria no responde a runners de GitHub
   (probado en producción por `observatorio-alegaciones` — workaround: fetch local en España + push).
   Implicación: la automatización de gacetas autonómicas no puede asumir CI en cloud extranjero;
   el spec debe contemplar fetchers locales/ES o tolerancia a `UNREACHABLE` con reintento fuera de banda.
2. **Licencias trampa en datos "abiertos"**: `leyes`, `es-legis`, `iderioja` parecen open data pero
   carecen de LICENSE → legalmente no reutilizables. WDPA restringe uso comercial.
   Regla: dato sin licencia explícita = `REJECT` aunque sea descargable.
3. **CENDOJ sin API** (WAF + scraping) — la cadena jurisprudencia es inherentemente frágil;
   el modelo de confianza debe admitir evidencia judicial como `MANUAL/INCONCLUSIVE`, no como feed.
4. **Heredar el agujero de BOE**: cualquier proyecto que indexe "España" desde BOE consolidada
   (leyabierta incluido) no contiene los PRUGs autonómicos — verificado con Decreto 17/2025 ausente
   en `es-cl` de leyabierta pese a estar publicado. Los datos OSS de legislación española NO cubren
   el corpus que AlRaso necesita.

Decisión estructural: **ningún OSS resuelve la parte dura** (gacetas autonómicas + consolidación +
enlace norma↔geometría). OSS aporta patrones de arquitectura y de gobernanza de datos — que es
justo lo que el G0 necesitaba validar. El trabajo real es código propio con interfaces estrechas,
alineado con el hallazgo §6 de G0-DISCOVERY.
