# AlRaso M10 — Spain Coverage Scaling (diseño)

**Estado:** APROBADA por el owner (2026-09-13) con tres correcciones de
contrato aplicadas — ver §P.
**Fecha:** 2026-09-13
**Base de diseño:** `origin/main` = `48146cf` (merge PR #36, cierre M10-G0)
**Rama de trabajo:** `docs/spain-coverage-scaling-design` (worktree `.worktrees/m10-design`)
**Clasificación:** ARQUITECTÓNICO + PIPELINE DE EVIDENCIA. No es una feature de producto,
no publica reglas legales nuevas y no toca el resolver.

Esta spec es el entregable de la fase de diseño posterior a M10-G0. No implementa
ingestión de producción, no crea reglas legales nuevas y no modifica
`alraso/resolver.py`, `alraso/engine*.py`, `webapp/` ni el corpus publicado.
Su único propósito es fijar la arquitectura de la pipeline de cobertura nacional
antes de escribir una sola línea de pipeline.

## 0. Decisión resumida

Se diseña una **pipeline de evidencia legal reproducible** compuesta por cinco
capacidades funcionales desacopladas, orquestadas mediante `SourceProfile`
declarativos, con una puerta de revisión humana obligatoria entre "evidencia
preparada" y "regla publicable":

```text
InventorySource      → catálogo de espacios (MITECO ENP / OAPN / CDDA control)
GeometryProvider     → geometría administrativa + provenance (OAPN WFS, WFS CCAA)
DiscoveryProvider    → por gaceta: búsqueda/sumario → doc IDs estables
DocumentFetcher      → por gaceta: doc ID → bytes + formato + provenance hash
DocumentParser       → por FORMATO (no por gaceta): AKN | daily-XML | BOCyL-XML |
                       BOE-XML | PDF(pdftotext) | HTML
VersionResolver      → por gaceta: versión vigente | REQUIRES_MANUAL_REVIEW
ReviewGate           → PR humano obligatorio: provenance + last_verified + diff
```

El `SourceAdapter` monolítico queda **descartado por evidencia** (P3 Cantabria:
discovery y fetch son dimensiones independientes; el mismo documento es 200 desde
red ES y timeout desde runner extranjero).

El primer milestone de implementación (M10.1) NO cubre España: demuestra que la
misma pipeline prepara evidencia reproducible para las **cinco jurisdicciones ya
sondeadas** sin lógica específica de parque/jurisdicción en el motor legal.
Escala 5 → 17 CCAA → nacional solo después.

## A. Base de evidencia (M10-G0, mergeado en `48146cf`)

Toda afirmación arquitectónica de esta spec cita evidencia en
`discovery/evidence/spain-coverage-g0/` y `docs/spain-coverage-g0/`:

| Artefacto G0 | Qué fija |
|---|---|
| `source-matrix.json` | inventario de fuentes, IDs estables, formatos, autoridad |
| `access-matrix.json` | reachability por clase, WAF, fallbacks, sha256 de evidencia |
| `G0-DISCOVERY.md` | síntesis, 13 gaps, límites de adapter |
| `PROBES.md` | cadena completa de los 5 probes territoriales |
| `OSS-REUSE-GATE.md` | clasificación ADOPT/ADAPT/COPY_PATTERN/REJECT por candidato |
| `tooling/g0_probe_verify.py` | 13/13 probes reproducibles en vivo |

Hallazgos que **cambian el diseño** respecto a la hipótesis inicial:

1. **Reachability es dimensión de la fuente** (P3): `ES_ONLY | REACHABLE |
   WAF_BLOCKED | MANUAL_ONLY | UNREACHABLE` va en el perfil, no en el código.
2. **El método HTTP es parte del contrato**: BOC Cantabria exige
   `POST boletines.do → TOC → verXmlAction.do?idBlob=N` (XML diario full-text).
   No se degrada a scraper HTML genérico.
3. **BOE consolidada no es corpus nacional único**: los PRUGs autonómicos
   recientes no están (6/6 probes `numero_oficial` → 0 hits); sí contiene los
   PRUGs de la era estatal (RD 384/2002 Picos…) → **doble era temporal**.
4. **Anexos PDF-only**: BOCyL XML trae el decreto pero el PRUG (430 pp) solo en
   PDF; BOC diario marca `anexos="1"`. El parser PDF no es opcional.
5. **Soft-404s confirmados** (BOE ELI, BOC anuncios): HTTP 200 no valida;
   siempre marcador de contenido.
6. **OAPN `Normativa` = semilla de discovery**: 1.915 zonas citan gaceta+decreto.
7. **Licencia de código ≠ licencia de datos**: se registra por fuente y
   artefacto; nunca se hereda del `LICENSE` del repo OSS.
8. **CENDOJ = auxiliar/manual**: sin API, con WAF; fuera del camino crítico.
9. **No existe atajo OSS** para `actividad × espacio × jurisdicción × vigencia ×
   geometría`: el núcleo de resolución sigue siendo propio (barrido negativo
   documentado).

## B. Decisiones congeladas (no renegociables en M10)

```text
DISCOVERY != FETCH
FETCH != PARSE
PARSE != VERSION_RESOLUTION
GEOMETRY_DISCOVERY != LEGAL_SCOPE
AUTOMATED_EXTRACTION != PUBLICATION
SOURCE_UNREACHABLE != SOURCE_ABSENT

BOE_CONSOLIDADA = SECONDARY / DISCOVERY + VERSION SIGNAL
AUTONOMIC_GAZETTE = PRIMARY WHEN APPLICABLE
OAPN_NORMATIVA = DISCOVERY_SEED
CENDOJ = AUXILIARY / MANUAL
OSS = INFRASTRUCTURE REUSE, NOT LEGAL TRUTH

PERMITTED = NEVER inferred from missing coverage
LEGAL_RULE_PUBLICATION = REVIEWED (PR humano, siempre)
```

## C. Arquitectura funcional

### C.1 Capacidades y contratos

```text
InventorySource.list_spaces()  → [SpaceRecord]
  SpaceRecord: {space_id, name, figure_type, ccaa[], source, source_id,
                admin_geom_ref, observed_at, evidence_sha256}

GeometryProvider.fetch_geometry(space_id) → GeometryEvidence
  GeometryEvidence: {space_id, provider, layer, retrieved_at, crs,
                     digest_sha256, feature_props, source_url,
                     redistribution_policy,
                     scope_evidence_status}
  # scope_evidence_status ∈ {CONTEXT_ONLY, OFFICIAL_SCOPE_CANDIDATE,
  #   OFFICIAL_SCOPE_LINK_PROVEN}; default CONTEXT_ONLY. Solo evidencia
  #   revisada puede llegar a OFFICIAL_SCOPE_LINK_PROVEN: un polígono
  #   administrativo MITECO/OAPN nunca se convierte en scope jurídico
  #   por ser "oficial".
  # La geometría completa NO se redistribuye salvo reuse verificado;
  # se almacena digest + props + URL re-fetcheada (convención M2A/M8.1).

DiscoveryProvider.discover(space_ref|authority_ref, window) → [DocumentRef]
  DocumentRef: {source_id, doc_id, published_on, title, rank, issuer,
                discovery_url, reachability_class}

DocumentFetcher.fetch(doc_ref) → DocumentEvidence
  DocumentEvidence: {doc_ref, method_recipe_id, fetched_at, fetched_from,
                     http_status, content_marker_ok, bytes_sha256,
                     content_type, reachability_observed}

DocumentParser.parse(doc_evidence) → ParsedInstrument
  ParsedInstrument: {doc_id, format, articles[], annexes_present,
                     citations[], extracted_at, parser_version}

VersionResolver.resolve(instrument_ref, as_of) → VersionClaim
  VersionClaim: {doc_id, consolidated_state, valid_from, valid_to,
                 supersession[], resolver_evidence,
                 status: RESOLVED | REQUIRES_MANUAL_REVIEW}

ReviewGate.prepare_pr(space_id, evidence_bundle) → ReviewPacket
  ReviewPacket: {space, chain_evidence, proposed_rule_artifacts,
                 provenance, last_verified, diffs}
  # NUNCA publica: abre PR. `PERMITTED` jamás se infiere por ausencia.
```

### C.2 `SourceProfile` declarativo

Cada fuente/jurisdicción se describe como **datos**, no como clase. Ejemplo
directamente derivado del probe P3 (no es implementación, es el shape):

```yaml
source_id: boc-cantabria
jurisdiction: ES-CB
kind: gazette

discovery:
  provider: boc_toc_post           # POST boletines.do → TOC del día
  recipe: toc_to_ids               # idBlob (día) + idAnuBlob (anuncio)
  ids: [CVE-YYYY-NNNN, numExpediente, BOC-YYYY-NNNN]

fetch:
  provider: boc_daily_xml          # verXmlAction.do?idBlob=N
  method: POST-then-GET            # el método HTTP es parte del contrato
  formats: [daily_xml, pdf_announcement]
  soft404_marker: "No hay documento"

parse:
  format: boc_daily_xml            # disposicion[anexos] → hybrid pdf path

versioning:
  strategy: gazette_publication    # sin consolidado → REQUIRES_MANUAL_REVIEW

reachability:
  expected:                        # expectativa, NO propiedad eterna
    spain: REACHABLE
    foreign_ci: ES_ONLY_SUSPECTED  # verificado vía fetcher externo en G0
  fallback: es_local_fetcher       # volcado versionado + push (patrón OSS)

change_detection:
  method: daily_xml_diff           # idBlob diario + sha256 disposición
  cadence: daily
```

Los perfiles viven en un directorio de configuración versionado
(p. ej. `pipeline/sources/*.profile.yaml` — ubicación exacta a decidir en
implementación) y se validan contra un schema. Un perfil nuevo **no exige código
nuevo** si reusa providers/recipes existentes; la peculiaridad de Cantabria es
configuración, no `if jurisdiction == "ES-CB"`.

### C.3 Providers compartidos por formato

Los `DocumentParser` se factorizan por formato, colapsando ~19 gacetas en ~4-5
parsers (medido en G0):

| Formato | Gacetas que lo sirven |
|---|---|
| Akoma Ntoso 3.0 | DOGC (ELI → `portaldogc …/AkomaNtoso`) |
| XML diario estructurado | BOC Cantabria (`verXmlAction`) |
| XML por disposición | BOCyL (`BOCYL-D-*-N.xml`) |
| XML consolidado + índice por bloque | BOE (`legislacion-consolidada`) |
| PDF (pdftotext) | BOPA, BOA, BOJA, BOC Canarias, anexos |
| HTML marcado | BOC Canarias, BOJA, BOCM (hasta 2026) |

### C.4 Reachability: expectativa en perfil, verdad en ejecución

Reachability **no es una propiedad permanente de la fuente**: es una relación
`fuente × runner_network × instante` (P3 lo demuestra: mismo documento, 200
desde red ES, timeout desde fetcher extranjero). Por tanto:

- El `SourceProfile` solo declara `reachability.expected` (hipótesis sembrada
  desde `access-matrix.json` de G0) + `fallback`. Si Cantabria elimina mañana
  el geo-block, el perfil no convierte un dato histórico en propiedad eterna.
- La verdad de ejecución son únicamente cuatro campos por fetch:
  `runner_network`, `reachability_observed`, `observed_at`, `evidence_sha256`.
- Un timeout extranjero produce `UNREACHABLE(ES_ONLY_SUSPECTED)`, nunca
  "fuente ausente" ni silencio. La divergencia `expected` vs `observed` es
  señal de drift a registrar, no a ignorar.

## D. Identificadores y reconciliación espacio ↔ norma

Problema demostrado por Picos: **un espacio, tres instrumentos territoriales**.
La reconciliación no puede ser `park_id → norm`; es:

```text
point → park geometry (OAPN/MITECO, administrativa)
      → jurisdiction (CCAA boundary; GISCO/NUTS aproximado → borde = UNDETERMINED)
      → authority (órgano emisor)
      → norm (doc_id en gaceta de esa jurisdicción)
      → version (vigente en as_of)
      → precept (artículo/anexo)
```

Estrategia de IDs (todas verificadas en G0):

| Nivel | ID estable | Ejemplo |
|---|---|---|
| Espacio | `space_id` propio + `OAPN feature` + ENP id | `pn-picos-de-europa` |
| Jurisdicción | ISO-3166-2:ES | `ES-AS`, `ES-CB`, `ES-CL` |
| Documento | ID nativo de gaceta | `BOCYL-D-15122025-1`, `CVE-2026-6207`, `BOC-A-2025-240-4148`, `2026-02506` (BOPA), `DOCN=007922169` (BOA), ELI `es-ct/d/2003/02/04/39` |
| Versión | gaceta: fecha pub + consolidado | `vigència=Vigent` (DOGC), `fecha_actualizacion` (BOE) |
| Evidencia | sha256 bytes + URL + timestamp | `evidence_sha256` |

`OAPN Normativa` actúa como **semilla**: cada zona PRUG cita `(gaceta, decreto)`
que el `DiscoveryProvider` de esa gaceta convierte en `DocumentRef`. La cita es
discovery, nunca verdad legal por sí sola.

## E. Bitemporalidad (no se reduce la ya existente)

El store actual ya modela (`alraso/schema.py`):

```text
VALID time:  [effective_from, effective_to]   cerrado; NULL = en vigor
SYSTEM time: [recorded_at, recorded_until)    qué sabía el sistema y cuándo
```

La pipeline alimenta exactamente estos ejes — **no hay tercer par temporal**:

```text
VALID TIME             effective_from / effective_to
                       entrada en vigor / derogación (del propio precepto:
                       "día siguiente" BOA, "15 días" BOC Canarias — heterogéneo)
SYSTEM / KNOWLEDGE TIME recorded_at / recorded_until
                       cuándo la pipeline lo observó (fetch + review)
PUBLICATION METADATA   publication_date (DocumentRef.published_on)
supersession           rule_relation_version (ya versionada)
```

`knowledge_from/to` **no existen como campos**: la semántica de conocimiento ya
la representa `recorded_at/recorded_until` (qué sabía el sistema y cuándo).

**Doble era PRUG** (G0, gap documentado): RD 384/2002 (era estatal, en BOE)
coexiste en el tiempo válido con los decretos autonómicos 2025-2026 (fuera de
BOE). El resolver temporal debe poder responder "¿qué regía el 2010-06-01?" —
la pipeline registra `effective_from` de cada era sin colapsarlas.

Toda extracción asistida lleva `recorded_at` del fetch y `recorded_until` al
ser sustituida; un fetch posterior que contradiga una regla publicada **no la
sobrescribe**: abre ReviewPacket con diff.

## F. Provenance y hashing

Por artefacto, igual que la convención vigente (M2A/M8.1/G0):

```text
source_url, retrieved_at, runner_network, http_status, content_marker,
bytes_sha256, redistribution_policy ∈ {FULL_OK, DIGEST_ONLY, METADATA_ONLY}
```

- Geometrías completas y PDFs oficiales: `DIGEST_ONLY`/`METADATA_ONLY` salvo
  reuse verificado por fuente y artefacto (licencia de datos ≠ de código).
- Toda cadena es re-verificable con `tooling/g0_probe_verify.py` (patrón a
  generalizar en implementación como verificador por perfil).

## G. Refresh y change-detection

| Fuente | Método | Fuerza |
|---|---|---|
| BOE consolidada | `from/to` sobre `fecha_actualizacion` corpus + `texto/indice` por bloque | fuerte |
| DOGC | Socrata `vigència` + `idVersion` AKN | fuerte |
| BOCyL | Opendatasoft dataset diario | fuerte |
| BOC Cantabria | `idBlob` diario + sha256 disposición (desde red ES) | media |
| BOA/BOPA/BOJA/BOC-CN | sha256 documento + búsqueda periódica | débil-media |
| OAPN WFS | snapshot sha256 capabilities/feature | débil |
| MITECO ENP | ATOM `<updated>` + sha256 descarga (gate ALTCHA) | media |

Regla: change-detection produce **ReviewPacket**, nunca auto-publicación.

## H. Revisión humana y publicación

Patrón adoptado de `lowlydba/foul-flock` (COPY_PATTERN en G0): datos refrescados
automáticamente, reglas legales explícitas, `provenance` + `last_verified`,
automatización abre PR. En AlRaso:

```text
evidence bundle → ReviewPacket (PR) → revisión humana → merge → corpus
                                                           ↓
                                    regla entra al store bitemporal
                                    con provenance completa
```

`PERMITTED` nunca sale de cobertura ausente: un espacio inventariado sin cadena
legal cerrada responde `UNDETERMINED` con contexto (mapa, POIs, tiempo) intacto.

## I. Estrategia de pilotos (M10.1)

Cinco jurisdicciones heterogéneas, ya sondeadas — elegidas por estructura
jurídica distinta, no por facilidad:

```text
P1 ES-CL Picos        BOCyL  API-grade (Opendatasoft + XML + PDF anexo)
P2 ES-AR Ordesa       BOA    CGI legado + zonificación compleja
P3 ES-CB Picos        BOC    ES_ONLY + POST→TOC→XML diario + CVE
P4 ES-CT Aigüestortes DOGC   Socrata + ELI + Akoma Ntoso consolidado
P5 ES-CN Teide        BOC    HTML+PDF firmado, cuotas vivac (insular)
```

Criterio de éxito de M10.1 (único objetivo del primer milestone):

> La misma pipeline —mismos providers, perfiles distintos— prepara un
> `ReviewPacket` reproducible para las 5 jurisdicciones sin lógica específica
> de parque o CCAA en el motor legal. Ninguna regla nueva se publica.

Escala posterior: 5 → resto de CCAA con parque nacional → inventario ENP/RN2000.

## J. OSS reuse (del gate G0)

| Pieza | Decisión | Uso |
|---|---|---|
| `legalize-dev/legalize-pipeline` | COPY_PATTERN/ADAPT | interfaces por capacidad, BOE client con cache+rate-limit+conditional requests |
| `ComputingVictor/MCP-BOE` | ADAPT | patrones de cliente API BOE |
| `indigo-akn` / `akn-profiler` | ADAPT | parsing Akoma Ntoso (DOGC) sin reinventarlo |
| `Asensio94/observatorio-alegaciones` | COPY_PATTERN | fetcher ES-local + cruce norma↔territorio en producción |
| `lowlydba/foul-flock` | COPY_PATTERN | refresh→PR + provenance |
| `martgnz/es-atlas` | PATTERN | pipeline geo oficial → formatos web |
| `projecte-aina/docg-pipeline` | PATTERN | DOGC como dato |
| `ioseobcn/normativa-dev` | REFERENCE_ONLY | retrieval por artículos |
| `iderioja/base_datos_geografica` | REJECT | sin licencia |
| `leyabierta/leyes` + engine | REJECT | datos sin LICENSE; engine AGPL-3.0; huecos heredables de BOE |
| `bettercallclaude-espana` | REJECT | AGPL-3.0 |

Ningún OSS es autoridad legal; toda cita termina en documento oficial verificado.

## K. Lo que esta spec NO construye

```text
NO producción de ingestion automática (M10.1 prepara ReviewPackets, no corpus)
NO nuevas reglas PERMITTED ni expansión de cobertura publicada
NO resolver/engine/webapp changes
NO scraper monolítico "España"
NO supresión de bitemporalidad ni de fail-closed
NO CENDOJ en el camino crítico
NO republicación de geometrías/PDFs oficiales sin reuse verificado
```

## L. Impacto previsto en archivos (forecast, no implementación)

```text
pipeline/                      (nuevo; fuera de alraso/ y webapp/)
  sources/*.profile.yaml       perfiles declarativos
  schemas/                     SourceProfile + DocumentEvidence schemas
tooling/m10_*_verify.py        verificadores por perfil (patrón g0_probe_verify)
discovery/evidence/m10-*/      evidencia de pilots
tests/test_m10_*.py            contratos de pipeline + file-scope whitelist
docs/spain-coverage-scaling/   notas de diseño posteriores
```

`alraso/`, `webapp/`, `qa/browser/`: **diff cero esperado en M10.1**. Si un piloto
exigiera tocar el resolver, eso es una señal de diseño erróneo, no una tarea.

## M. Riesgos y preguntas abiertas

1. **Fetcher ES-local**: la infra del fetcher en España (runner propio, proceso
   local con push, o cache versionado) es decisión operativa de M10.1, no de
   esta spec — pero el `SourceProfile` ya la representa.
2. **ALTCHA de MITECO**: proof-of-work resoluble pero frágil; CDDA/EEA queda
   como cross-check de inventario (licencia compatible).
3. **AIGEST/PRUG fuera de OAPN**: Picos y Sierra de las Nieves ausentes del
   layer de zonificación (lag de datos) — la semilla `Normativa` es parcial;
   discovery por gaceta sigue siendo la vía completa.
4. **Anexos PDF-only**: coste de `pdftotext` + OCR eventual en PRUGs centenarios
   de páginas; se mide en el piloto P1 (430 pp BOCyL).
5. **Schemas de `SourceProfile`**: los campos exactos se fijan al implementar el
   primer perfil real (P1), con los otros 4 como contraste inmediato.

## N. Gates de la fase de diseño (este PR)

- Spec + whitelist de `tests/test_m2b_official_boundary.py` (estrofa M10).
- Ningún otro archivo tocado: diff = spec + test whitelist.
- Tras aprobación: plan de implementación M10.1 (piloto P1 primero), con el
  mismo gate atómico que M9.2 — cada capacidad demuestra comportamiento antes
  de la siguiente.

## O. Self-review de la spec

- ¿Alguna afirmación sin evidencia G0? Revisado: cada decisión arquitectónica
  cita un probe o un hallazgo OSS concreto; las cosas no probadas (schema
  exacto de perfil, infra ES-local) quedan explícitamente abiertas en §M.
- ¿Se cuela implementación? No: los `SourceProfile` de §C.2 son shape, no
  código; no hay `pipeline/` creado.
- ¿Reduce garantías existentes? No: bitemporalidad, fail-closed,
  `CONTEXT_ONLY` explícito y revisión humana se conservan o refuerzan.
- ¿Es reproducible? La evidencia base está mergeada en `48146cf` con verificador
  en vivo (`g0_probe_verify.py`, 13/13 PASS).

## P. Registro de aprobación

**APROBADA por el owner (2026-09-13) con tres correcciones de contrato,
todas documentales y aplicadas en esta misma revisión:**

1. **Reachability = expectativa, no propiedad** (§C.2, §C.4): el perfil declara
   `reachability.expected` + `fallback`; la verdad de ejecución es solo
   `runner_network` / `reachability_observed` / `observed_at` /
   `evidence_sha256`.
2. **Ejes temporales congelados** (§E): `VALID = effective_from/to`,
   `SYSTEM/KNOWLEDGE = recorded_at/until`, `PUBLICATION = publication_date`.
   `knowledge_from/to` eliminados: no existe tercer par temporal.
3. **`scope_evidence_status` en `GeometryEvidence`** (§C.1): `CONTEXT_ONLY`
   (default) | `OFFICIAL_SCOPE_CANDIDATE` | `OFFICIAL_SCOPE_LINK_PROVEN`;
   solo evidencia revisada alcanza el último estado. Protege contra convertir
   geometría administrativa en scope jurídico por ser "oficial".

Nit adicional: comentario del whitelist M10 corregido para describir lo que
realmente protege (docs de diseño); la implementación M10.1 añadirá su propia
estrofa acotada.

Estado tras aprobación:

```text
ARCHITECTURE=APPROVED
MONOLITHIC_SOURCE_ADAPTER=REJECTED
FUNCTIONAL_CAPABILITIES=APPROVED
SOURCE_PROFILE=APPROVED
REVIEW_GATE=APPROVED
BITEMPORALITY=PRESERVED
LEGAL_ENGINE=FROZEN
NEW_RULE_PUBLICATION=FORBIDDEN_IN_M10.1
IMPLEMENTATION=NOT_AUTHORIZED
NEXT=M10.1_IMPLEMENTATION_PLAN
```
