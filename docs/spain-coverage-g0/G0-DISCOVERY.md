# ALRASO — SPAIN COVERAGE G0: Source + OSS Discovery

Estado: **descubrimiento completado, evidencia registrada, arquitectura NO congelada**.
Baseline: `main` = `f15b62c0ffb05779fca6710a71dad4c9d831f8a5` (post-M9.2).
Rama: `docs/spain-coverage-g0`. Alcance congelado:

```text
PRODUCT_CODE = FROZEN        LEGAL_PUBLICATION = FROZEN
NO NEW PARK RULES            NO SOURCEADAPTER IMPLEMENTATION
NO production ingestion      NO new PERMITTED               NO corpus publication
```

Toda la evidencia cruda vive en `discovery/evidence/spain-coverage-g0/` (índice en su README.md).
Matriz legible por máquina: `discovery/evidence/spain-coverage-g0/source-matrix.json`.

---

## 1. Hallazgo central

**La cadena legal nacional no existe en ninguna fuente única.** El resultado de los probes es:

```text
inventario nacional     → MITECO ENP (anual, descarga con gate ALTCHA, WMS frágil)
                          + OAPN WFS (solo Red de Parques Nacionales, fiable)
geometría administrativa → MITECO ENP / OAPN / WFS autonómicos (Aragón probado)
autoridad competente     → derivable del tipo de figura + CCAA; NO es un campo de datos
norma marco + declaración → BOE consolidada (API fuerte) ✔
norma operativa (PRUG)   → SÓLO boletines autonómicos — NO están en BOE consolidada ✔ (probado)
versión vigente          → BOE (fuerte), DOGC (fuerte), BOCyL (fuerte),
                           resto: débil o manual
```

Conclusión estructural: el problema nacional es **heterogeneidad de boletines autonómicos**,
no falta de inventario ni de geometría. MITECO/OAPN dan el "qué existe y dónde"; el "qué norma
vige y qué dice" exige un canal por boletín, con calidades muy distintas (de API-grade en
DOGC/BOCyL a document-grade en BOPA/BOC-Cantabria).

### 1.1 Probes empíricos clave (reproducibles)

| Probe | Resultado |
|---|---|
| BOE consolidada `?query=numero_oficial:"238/2011"` | 0 hits — PRUG Sierra Nevada **no está** en BOE |
| idem para 49/2015 (Ordesa), 17/2025 y 21/2026 y 57/2026 (Picos), 182/2025 (Teide), 39/2003 (Aigüestortes) | 0 hits o normas estatales no relacionadas |
| BOE consolidada `ambito@codigo:2 and titulo:rector` | 0 hits — ningún PRUG autonómico consolidado. PERO `titulo:plan and titulo:rector` devuelve **RDs estatales históricos** (RD 384/2002 Picos —derogado/anulado—, RD 277/1995, RD 1621/1990, RD 1531/1986…): la era pre-transferencia sí está en BOE |
| BOE consolidada acepta IDs nativos de gaceta | `BOJA-b-2020-90080`, `BOCL-h-2013-90254` responden 200 — la consolidada indexa normas CCAA bajo su ID autonómico (pero solo las consolidadas: leyes, no PRUGs) |
| BOE consolidada Ley 1/2007 Monfragüe / Ley 3/1999 Sierra Nevada | `BOE-A-2007-4461`, `BOE-A-1999-782` — las leyes de **declaración** sí están |
| BOE list `?from&to` sobre `fecha_actualizacion` | Devuelve normas con timestamp de consolidación — **change detection corpus-wide resuelto** |
| BOE `texto/indice` | `fecha_actualizacion` **por bloque/artículo** — change detection granular resuelto |
| BOE ELI `es-cl/d/2025/12/11/17` | **HTTP 200 con página "Error 404"** — soft-404; verificar contenido, no status |
| DOGC Socrata `titol like %aigüestortes%` | DECRET 39/2003 (PRUG), `vigència=Vigent`, ELI → **Akoma Ntoso XML** (302→`portaldogc ... AkomaNtoso?...&format=xml`) |
| BOCyL Opendatasoft `titulo like "Picos de Europa"` | DECRETO 17/2025 con `enlace_fichero_pdf/xml/html`; doc `BOCYL-D-15122025-1` 200 XML (metadatos completos; anexo PRUG 430 pp solo en PDF) |
| MITECO ENP `DescargaFichero?f=gml_enp.zip` | Devuelve HTML con **widget ALTCHA** (proof-of-work) + token ASP.NET — descarga NO es GET directo (página guardada como evidencia) |
| MITECO ENP WMS GetCapabilities | **NullReferenceException** ASP.NET — endpoint vivo pero frágil |
| MITECO ATOM `downloadservice.xml` | Feed de nivel servicio; derechos: "uso libre y gratuito ... mención al Ministerio"; `<updated>2026-08-20` |
| OAPN WFS GetCapabilities | 200, 133 KB — capas: `view_red_oapn_limite_pn` (17 PN), `view_red_oapn_zpp`, `view_zon_zonificacion_prug` (**1.915 zonas**, con atributo `Normativa` = cita legal por zona) |
| OAPN límites PN | 17 features; `Declaración`="Ley 1/2007, de 2 de marzo" — **puntero a la norma**, sin ID de máquina (nombre = identidad) |
| BOPA `sede.asturias.es/bopa/2026/03/30/2026-02506.pdf` | 200 application/pdf — URL estable por código (55,8 MB ya fijado por sha256 en M2A) |
| BOC Cantabria `verAnuncioAction.do?idAnuBlob=` | 200 JSP ISO-8859-1 — acceso por anuncio, sin API |
| BOA `BRSCGI?...DOCN=007922169` | 200 text/plain ISO-8859-1 — CGI legado |
| BOJA `juntadeandalucia.es/boja/2011/155/41` | 200 html; existe portal `sedeboja` de textos consolidados (Liferay, sin API limpia verificada) |
| BOC Canarias `gobiernodecanarias.org/boc/2025/240/pda/4148.html` | 200 html — Decreto 182/2025 PRUG Teide; IDs `BOC-A-YYYY-NNN-NNNN`; PDF firmado |
| BOCM `BOCM-YYYYMMDD-N.PDF` | 200 application/pdf; desde 2026-01 también XML+JSON-LD por anuncio |
| CNIG `atom.cnig.es` | **000 (timeout)** — INCONCLUSIVE en esta sesión; `centrodedescargas.cnig.es` 200 |

## 2. Los 5 probes territoriales heterogéneos

Cadena completa por probe en `docs/spain-coverage-g0/PROBES.md`
(SPACE_ID → geometría → autoridad → discovery → documento → versión → precepto →
provenance → parser → change-detection → publication_readiness=NO).

### 2.1 Ordesa y Monte Perdido (Aragón — BOA)

```text
espacio    : PN Ordesa — OAPN view_red_oapn_limite_pn (feature propia)
geometría  : OAPN límite + ZPP + zonificación PRUG (266 features; Normativa="Decreto 49/2015...")
autoridad  : Gobierno de Aragón (gestión) / OAPN (red)
norma      : Decreto 49/2015 (PRUG) + Decreto 16/2022 (modificación régimen pernocta Góriz)
gaceta     : BOA BRSCGI — document-grade (text/plain), IDs DOCN
versión    : BOA document-grade; consolidado aragonés NO API-verificado → revisión manual
precepto   : extract verbatim ya en evidence/m11c-goriz + aragon-wfs ENP101_025/137
revisión   : posible (polling BOA) pero manual; cadena CERRADA como discovery, ABIERTA como versión
```

### 2.2 Picos de Europa (Asturias BOPA + Cantabria BOC + CyL BOCyL)

```text
espacio    : PN Picos — OAPN layer (1 feature, 3 jurisdicciones)
geometría  : OAPN + GISCO NUTS2 ES12/ES13/ES41 (Δ<0,05 % verificado en M2A); jurisdicción OBLIGATORIA
autoridad  : 3 CCAA — misma estructura de PRUG, 3 decretos
norma      : Ast Decreto 21/2026 (BOPA 2026-02506, PDF) · Cant Decreto 57/2026 (BOC 148;
             CVE-2026-6207 en XML diario) · CyL Decreto 17/2025 (BOCyL-D-15122025-1, API+XML+PDF)
versión    : heterogénea — BOCyL API-grade, BOC XML-diario (ES_ONLY), BOPA PDF-grade
precepto   : arts. 51-52 verbatim idénticos en los 3 (verificado por diff en M2A)
revisión   : CyL automatizable (Opendatasoft daily); Cant automatizable desde red ES; Ast manual
```

**Lección**: un mismo parque exige 3 canales de gaceta distintos — el peor caso ya está probado y resoluble.

### 2.3 Teide (Canarias — BOC)

```text
espacio    : PN Teide — OAPN layer (49 zonas PRUG)
norma      : Decreto 182/2025, 1-dic (BOC 240, 03/12/2025, anuncio 4148) — PRUG nuevo tras 23 años
gaceta     : BOC gobiernodecanarias.org — doc-grade con IDs estables BOC-A-YYYY-NNN-NNNN + PDF firmado
extra      : documento normativo también en IDECanarias (idecanarias.es/resources/PLA_ENP_URB/...)
versión    : sin consolidado verificado → revisión manual; doc IDs estables permiten polling
revisión   : media — URLs estables, sin feed máquina verificado
```

### 2.4 Sierra Nevada (Andalucía — BOJA)

```text
espacio    : PN Sierra Nevada — OAPN layer (442 zonas PRUG)
norma      : marco Ley 3/1999 → BOE-A-1999-782 (consolidada, estatal ✔)
             PRUG Decreto 238/2011 → BOJA 155 (09/08/2011) — NO en BOE consolidada ✔ probado
gaceta     : BOJA doc-grade + portal textos consolidados (sedeboja, Liferay) — sin API limpia
versión    : consolidado existe pero portlet; modificaciones vía Ordenes (ej. BOJA 2022/107/41)
revisión   : media — consolidado consultable manualmente
```

### 2.5 Aigüestortes (Catalunya — DOGC)

```text
espacio    : PN Aigüestortes — OAPN layer (27 zonas PRUG)
norma      : DECRET 39/2003 (PRUG) — encontrado vía Socrata API, vigència=Vigent
gaceta     : DOGC + Portal Jurídic — API-grade: Socrata + ELI estable + Akoma Ntoso XML + RDF/Turtle
versión    : vigència explícita por API (Vigent/Derogada) — la mejor del conjunto
revisión   : alta — change detection vía dataset Socrata + ELI versionado
```

### 2.6 Síntesis de probes

| Caso | Gaceta | Acceso doc | Consolidado | Change-detection | Cadena |
|---|---|---|---|---|---|
| Ordesa | BOA | CGI text/plain | portal s/API verif. | débil-media | reproducible |
| Picos ×3 | BOPA+BOC+BOCyL | PDF/**XML diario**/**API** | — | CyL fuerte; Cant media (ES_ONLY); Ast débil | reproducible (3 canales) |
| Teide | BOC | HTML+PDF firmado | no verif. | media | reproducible |
| Sierra Nevada | BOJA | HTML/PDF | portal Liferay | media | reproducible |
| Aigüestortes | DOGC | **API+Akoma Ntoso** | vigència por API | fuerte | reproducible |

**≥5 probes heterogéneos: reproducibles.** Los 5 casos cubren alta montaña, interautonómico (peor caso),
insular, zonificación compleja y gaceta API-grade.

## 3. Clasificación de autoridad

| Rol | Fuentes |
|---|---|
| **Legal autoritativa** | BOE (estatal + lo autonómico republicado en BOE); cada gaceta autonómica para su norma |
| **Administrativa oficial (geo)** | MITECO ENP/RN2000 (inventario nacional); OAPN (red PN + zonificación PRUG + citas de norma); WFS autonómicos (ICEAragón ZENP probado; IDECanarias) |
| **Control/validación** | CNIG/IGN (límites administrativos, BTN, MDT); GISCO NUTS (jurisdicción punto→CCAA, ±1 km); EEA CDDA (cross-check inventario) |
| **Agregación secundaria** | datos.gob.es (catálogo), legalize-es (señal/diff), normativa-dev |
| **Insuficiente para PERMITTED** | cualquier geometría administrativa sin norma+versión; cualquier ausencia de cobertura |

## 4. Estrategia de identificadores

Problema probado: **no hay ID universal**. OAPN usa nombres, Aragón usa `ENP101`, BOCyL `BOCYL-D-*`,
BOE `BOE-A-*`, DOGC control number+ELI. Propuesta derivada de evidencia:

```text
space_id   = "enp:" + código ENP MITECO cuando accesible;
             fallback "pn:" + slug OAPN + ccaa (estable, humano)
             cross-refs: codeara/CCAA codes, CDDA sitecode
norm_id    = gaceta-id nativo por boletín:
             boe: BOE-A-YYYY-NNNNN (+ ELI)
             bocyl: BOCYL-D-DDMMYYYY-N
             boc-canarias: BOC-A-YYYY-NNN-NNNN
             bopa: YYYY-NNNNN + fecha
             boa: DOCN
             boja: año/número/doc
             dogc: ELI es-ct + idNumber
rule_ref   = {space_id, norm_id, article_id, version_date, last_verified, gazette_url}
```

Regla: `rule_ref` siempre compuesto — nunca inferir equivalencia entre IDs de fuentes distintas.

## 5. Matriz de actualización / detección de cambios

| Fuente | Mecanismo | Fuerza | Cadencia realista |
|---|---|---|---|
| BOE consolidada | `from/to` sobre `fecha_actualizacion` (corpus) + por bloque en `texto/indice` | **fuerte** | diaria |
| BOE sumario | `/boe/sumario/AAAAMMDD` | fuerte | diaria |
| DOGC | dataset Socrata + vigència + ELI | **fuerte** | diaria |
| BOCyL | dataset Opendatasoft diario | **fuerte** | diaria |
| BOCM | boletín diario + XML/JSON-LD | media-fuerte | diaria |
| BOJA | portal consolidado manual | media | semanal |
| BOC Canarias | IDs estables + archivo | media | semanal |
| BOA | polling CGI | media-débil | semanal |
| BOPA | PDF por doc + buscador | débil | manual |
| BOC Cantabria | viewer JSP | débil | manual |
| MITECO ENP | ATOM `<updated>` + sha256 de descarga (gate ALTCHA) | media | anual/semestral |
| OAPN WFS | sin versión → snapshot sha256 | débil | semestral |

## 6. Límites de adapter recomendados (derivados de evidencia)

La evidencia **descarta un `SourceAdapter` monolítico**: Cantabria demuestra que discovery y
fetch son dimensiones independientes (el sumario existe y es consultable, pero el fetch falla
por geolocalización desde CI extranjero). El split que emerge de los 5 probes:

```text
InventorySource      MITECO ENP (o CDDA fallback) — lista de espacios + figura + ccaa
GeometryProvider     OAPN WFS / WFS autonómico / descarga MITECO — por espacio
DiscoveryProvider    por gaceta — buscar/sumario → doc IDs   (heterogéneo real)
DocumentFetcher      por gaceta — doc ID → bytes + formato   (con reachability propia)
DocumentParser       por formato — Akoma Ntoso | daily-XML (BOC) | BOCyL-XML | BOE-XML | PDF
VersionResolver      por gaceta — consolidado/vigència       (DOGC/BOE fuerte; resto débil)
ReviewGate           humano — toda regla entra por PR con provenance + last_verified
```

Cada interfaz reporta su propio estado, incluyendo **reachability por clase**
(`REACHABLE | ES_ONLY | WAF_BLOCKED | MANUAL_ONLY | UNREACHABLE`) — un timeout extranjero
nunca se traduce en "fuente ausente" (ver `access-matrix.json`).

Justificación empírica:

1. `DiscoveryProvider`/`DocumentFetcher` separados: P3 (Cantabria) prueba que discovery puede
   funcionar donde fetch no — y que el fetcher correcto puede ser un proceso local en España
   que publica el volcado (patrón observado en `observatorio-alegaciones`).
2. `DocumentParser` se factoriza por **formato, no por gaceta**: Akoma Ntoso (DOGC),
   XML-diario-estructurado (BOC Cantabria), XML-por-disposición (BOCyL), XML consolidado (BOE),
   PDF (BOPA/BOA/BOJA/BOC-Canarias) → ~4-5 parsers reales para ~19 gacetas.
   Detalle verificado: `anexos="1"`/anexos PDF-only exige path híbrido XML+pdftotext.
3. `VersionResolver` es el cuello de botella real: sólo BOE/DOGC/BOCyL lo resuelven a máquina.
   Para el resto devuelve `REQUIRES_MANUAL_REVIEW` — compatible con fail-closed.
4. `GeometryProvider` independiente del canal legal; OAPN `Normativa` actúa además como
   **semilla de discovery** (cita gaceta+decreto por parque).
5. Patrón validado externamente: `legalize-pipeline` usa la misma separación
   (`LegislativeClient`/`NormDiscovery`/`TextParser`/`MetadataParser` por país).

## 7. Known gaps (honestos)

1. **Descarga ENP MITECO con ALTCHA** — automatizable (proof-of-work resoluble) pero con fricción y
   anti-forgery token; alternativa: réplicas autonómicas del dataset ENP o ATOM dataset-feeds (pendiente).
2. **WMS MITECO frágil** (NullReferenceException en GetCapabilities) — no asumir OGC vivo para MITECO.
3. **OAPN solo cubre la Red de Parques Nacionales** (17), no todos los ENP — para PNat/Reservas se
   necesita ENP MITECO o WFS autonómicos.
4. **Sin ID de máquina en OAPN** — join por nombre, frágil ante renombrados.
5. **Consolidación autonómica heterogénea** — la mayoría de gacetas no tienen consolidado API;
   `VersionResolver` será `REQUIRES_MANUAL_REVIEW` en la mayoría de territorios al inicio.
6. **Soft-404s** (BOE ELI, BOC) — todo probe debe validar contenido.
7. **Anexos largos solo en PDF** (BOCyL probado: PRUG 430 pp) — el XML por disposición no lleva anexos.
8. **CNIG ATOM unreachable** en esta sesión — rol de CNIG limitado a control, no crítico.
9. **Cobertura real de PRUGs por gaceta no muestreada al completo** — G0 probó 5 territorios, no 19.
10. **`query` del BOE solo busca en el corpus consolidado** — las disposiciones no consolidadas
    (resoluciones, correcciones) requieren el sumario diario, no la API de normas.
11. **Geo-bloqueo de gacetas autonómicas** — probado en producción por un tercero
    (`observatorio-alegaciones`): los servidores del Gobierno de Cantabria no responden a runners
    de GitHub. La automatización nacional no puede asumir cloud extranjero: fetchers en España
    o `UNREACHABLE` explícito con reintento fuera de banda.
12. **Trampas de licencia en datos "abiertos"** — repos de legislación española en Markdown
    (`leyabierta/leyes`, `es-legis`) no tienen LICENSE → no reutilizables aunque descargables;
    WDPA/ProtectedPlanet restringe uso comercial → no sirve como fallback del inventario ENP
    (EEA CDDA sí). CENDOJ no tiene API (WAF) — jurisprudencia será siempre evidencia manual.
13. **Doble era de los PRUGs** — los PRUGs pre-transferencia aprobados por Real Decreto SÍ están
    en BOE consolidada (RD 384/2002 Picos etc. — incl. alguno anulado judicialmente); los modernos
    por decreto autonómico NO. El resolver temporal debe distinguir ambas eras.

## 8. Veredicto del gate G0

```text
national inventory source proven          → YES (MITECO ENP catalog + OAPN WFS, con fricciones documentadas)
geometry provenance model clear           → YES (administrative ≠ legal scope; citation-pointer pattern probado)
≥5 heterogeneous legal-source probes      → YES (5 territorios, 7 gacetas, cadenas registradas)
adapter boundaries emerge from evidence   → YES (split por función, no por gaceta; parsers por formato)
```

**⇒ G0 PASA. Se recomienda escribir SPAIN COVERAGE SCALING SPEC** con estos límites de adapter
ya fijados por evidencia y con `VersionResolver → REQUIRES_MANUAL_REVIEW` como estado por defecto
fuera de BOE/DOGC/BOCyL.
