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

## Sondas negativas registradas (no sustituir silenciosamente)

| Probe | Resultado | Lectura |
|---|---|---|
| BOE consolidada × `numero_oficial` de 6 decretos PRUG | 0 hits o normas estatales ajenas | PRUGs **no** están en BOE consolidada |
| `atom.cnig.es` | 000 timeout | INCONCLUSIVE — CNIG queda en rol de control |
| BOC Canarias URL inventada `boc-a-2017-924-904` | 200 html/pdfs vacíos | soft-404 — patrón real: `/boc/YYYY/NNN/[pda/]NNNN` |
| BOPA guesses iniciales | 404 | patrón real verificado: `sede.asturias.es/bopa/YYYY/MM/DD/CODE.pdf` |
| `mapama ... wfs.aspx` | 200 con ServiceException | misma fragilidad que el WMS |
