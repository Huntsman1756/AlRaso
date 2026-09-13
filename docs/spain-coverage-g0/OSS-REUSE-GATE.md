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

## No encontrados / verificación negativa

- **`official-sources-esp`**: la búsqueda en GitHub no devuelve ese repo; los candidatos cercanos
  no encajan (`fedec65/bettercallclaude-espana` AGPL-3.0 — copyleft, REJECT por licencia;
  MCP wrappers sin licencia). Registrar como `NOT_FOUND` — no contar con él.

## Síntesis

```text
ADOPT directo:            0  (nada listo para enchufar)
ADAPT puntual:            legalize-pipeline → cliente BOE con ETag/rate-limit (si se ingiere BOE)
PATTERN (arquitectura):   legalize-pipeline (interfaces por función),
                          foul-flock (refresh→PR + provenance + reglas explícitas),
                          es-atlas (geo oficial → artefacto web),
                          docg-pipeline (DOGC), normativa-dev (recuperación por dominio)
REJECT:                   iderioja (sin licencia), bettercallclaude-espana (AGPL)
```

Decisión estructural: **ningún OSS resuelve la parte dura** (gacetas autonómicas + consolidación +
enlace norma↔geometría). OSS aporta patrones de arquitectura y de gobernanza de datos — que es
justo lo que el G0 necesitaba validar. El trabajo real es código propio con interfaces estrechas,
alineado con el hallazgo §6 de G0-DISCOVERY.
