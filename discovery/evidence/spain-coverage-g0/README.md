# Evidence index — spain-coverage-g0

Todos los probes ejecutados 2026-09-13 desde la rama `docs/spain-coverage-g0` (baseline `f15b62c`).
Re-ejecutable con `python tooling/g0_probe_verify.py` (sin red ⇒ `INCONCLUSIVE`, nunca falso OK).
Política: geometría completa NO redistribuida (reuse NOT_VERIFIED) — digests + properties.
Excepción: XML BOE (datos abiertos con reutilización explícita).

| Fichero | Fuente / URL | Status | Interpretación |
|---|---|---|---|
| `source-matrix.json` | síntesis G0 | — | matriz máquina de todas las fuentes |
| `boe-api-consolidada-doc.pdf` | `boe.es/datosabiertos/api/` doc oficial (2025-09-02) | 200 | contrato API consolidada: endpoints, query_string, from/to, per-block fecha_actualizacion |
| `boe-ley-42-2007.xml` | `GET /legislacion-consolidada/id/BOE-A-2007-21490` (Accept: xml) | 200 | texto consolidado íntegro Ley 42/2007 — formato real del canal legal estatal |
| `boe-analisis-ley-42-2007.xml` | `GET .../analisis` | 200 | metadatos/análisis de la misma norma |
| `boe-eli-es-cl-17-2025.html` | `boe.es/eli/es-cl/d/2025/12/11/17` | 200 **soft-404** | página "Error 404" con HTTP 200 — los ELI autonómicos ausentes no devuelven 404 real |
| `miteco-atom-feed.xml` | `mapama.gob.es/ide/inspire/atom/downloadservice.xml` | 200 | feed ATOM nivel servicio; cláusula de derechos (uso libre con atribución); `<updated>2026-08-20` |
| `miteco-enp-download-altcha-gate.html` | `gis.miteco.gob.es/descargas/app/DescargaFichero?f=gml_enp.zip` | 200 | **NO es el zip**: página con widget ALTCHA + token `__RequestVerificationToken` + POST `?handler=Download` |
| `enp-wms-capabilities.xml` | `wms.mapama.gob.es/sig/Biodiversidad/ENP/wms.aspx?...GetCapabilities` | 200 | `ServiceExceptionReport` — **NullReferenceException** ASP.NET/Jenkins; endpoint frágil |
| `mapama-ogc-collections.json` | `wmts.mapama.gob.es/sig-api/ogc/features/v1/collections` | 200 | 30 colecciones, **ninguna ENP/RN2000** — dominio agroalimentario/pesca |
| `oapn-wfs-capabilities.xml` | `sigred.oapn.es/geoserverOAPN/ows?WFS GetCapabilities` | 200 | inventario completo de capas OAPN (límites PN, ZPP, zonificación PRUG, AIS, itinerarios) |
| `oapn-limites-pn.digest.json` | WFS `LimitesParquesNacionalesZPP:view_red_oapn_limite_pn` | 200 | 17 features; props incl. `Declaración` (cita legal) + `Fecha Declaración`; sin ID máquina |
| `oapn-zonificacion-prug.digest.json` | WFS `ZonificacionPRUG:view_zon_zonificacion_prug` | 200 | 1.915 features; props incl. `Normativa` (cita por zona); geometría = digest solamente |
| `bocyl-dataset-meta.json` | `jcyl.opendatasoft.com/api/explore/v2.1/.../datasets/bocyl` | 200 | esquema del dataset: campos + `enlace_fichero_pdf/xml/html` |
| `bocyl-17-2025-head.xml` | `bocyl.jcyl.es/.../xml/BOCYL-D-15122025-1.xml` | 200 | disposición XML Decreto 17/2025 — texto del decreto sí, anexo PRUG (430 pp) solo en PDF |
| `dogc` (inline, sin fichero) | `analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json` + ELI `portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39/dof/cat/xml` | 200 / 302→200 | Socrata con `vigència`; ELI resuelve a **Akoma Ntoso XML** (`portaldogc .../AkomaNtoso?...`) |
| `dogc-39-2003-akn.xml` | ELI DECRET 39/2003 → `portaldogc .../AkomaNtoso?idNumber=309790&idVersion=318062&format=xml` | 200 | Akoma Ntoso 3.0 íntegro; contiene el Plan completo (art. 25.4 prohibición bivac/acampada) |
| `access-matrix.json` | síntesis G0 | — | matriz de acceso por fuente (reachability, waf, ids, change-detection, fallback, sha) |
| `boc-cantabria-toc-20260804-post.html` | POST `boc.cantabria.es/boces/boletines.do` (fecBolString=04/08/2026&boton=Buscar) | 200 | TOC del día → `idBlob=46085` + lista anuncios `idAnuBlob` |
| `boc-cantabria-2026-08-04.xml` | `boc.cantabria.es/boces/verXmlAction.do?idBlob=46085` | 200 | **XML diario full-text**: Decreto 57/2026 = `disposicion numExpediente=2026-6207`, CVE-2026-6207, `anexos=1` |
| `boc-cantabria-anuncio-435888.html` | `verAnuncioAction.do?idAnuBlob=435888` | 200 | **soft-404**: "No hay documento que mostrar" con HTTP 200 |
| `boc-cantabria-home.html` | `boc.cantabria.es/boces/` | 200 | homepage: formulario con campo CVE (código verificación electrónica) |
| `boa-decreto-16-2022-doc.html` | `boa.aragon.es BRSCGI?CMD=VERDOC&DOCN=007922169` | 200 | doc Decreto 16/2022 (régimen pernocta Ordesa), vigencia "día siguiente" |
| `boc-canarias-182-2025.html` | `gobiernodecanarias.org/boc/2025/240/pda/4148.html` | 200 | página Decreto 182/2025 (PRUG Teide) con enlace PDF firmado |
| `boc-182-2025-vivac-extract.txt` | `sede.gobiernodecanarias.org/boc/boc-a-2025-240-4148.pdf` (58,3 MB, sha256 45df0cd3…) | 200 | extract §6.3.2.7 VIVAC + prohibiciones; PDF NO redistribuido |

## Probe de reachability externa

| Probe | Resultado | Lectura |
|---|---|---|
| `r.jina.ai/https://boc.cantabria.es/boces/verAnuncioAction.do?...` | **422 TimeoutError** (navegación desde infra Jina, fuera de ES) | BOC Cantabria ES_ONLY verificado empíricamente — el mismo doc da 200 desde red ES |

## Sondas negativas registradas (no sustituir silenciosamente)

| Probe | Resultado | Lectura |
|---|---|---|
| BOE consolidada × `numero_oficial` de 6 decretos PRUG | 0 hits o normas estatales ajenas | PRUGs **no** están en BOE consolidada |
| `atom.cnig.es` | 000 timeout | INCONCLUSIVE — CNIG queda en rol de control |
| BOC Canarias URL inventada `boc-a-2017-924-904` | 200 html/pdfs vacíos | soft-404 — patrón real: `/boc/YYYY/NNN/[pda/]NNNN` |
| BOPA guesses iniciales | 404 | patrón real verificado: `sede.asturias.es/bopa/YYYY/MM/DD/CODE.pdf` |
| `mapama ... wfs.aspx` | 200 con ServiceException | misma fragilidad que el WMS |
