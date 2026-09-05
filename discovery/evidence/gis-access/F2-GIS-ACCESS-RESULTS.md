# F2.3A — Acceso a fuentes GIS/portales (probas reales 2026-09-05)

Metodología: probes HTTP reales desde el entorno (curl + urllib), diagnóstico con
DNS-over-HTTPS (cloudflare-dns.com) para separar **SOURCE_UNAVAILABLE** (el host/endpoint
no existe globalmente), **CURRENT_ENVIRONMENT_BLOCKED** (existe globalmente pero el DNS de
este entorno falla) y endpoint incorrecto (host real ≠ hostname ensayado en el discovery).

Resultado clave: los hostnames ensayados en la ronda de discovery
(`geoportal.comunidad.madrid`, `ide.cantabria.es`, `www.idearagon.es`,
`reservasonline.aragon.es`) son **NXDOMAIN globales** — eran endpoints INCORRECTOS, no
fuentes bloqueadas. Los hosts oficiales reales son alcanzables desde este entorno.

## Matriz por fuente

| authority | canonical_url (probeado) | protocolo | access_result | auth | rate_limit_known | machine_readable | fallback |
|---|---|---|---|---|---|---|---|
| OAPN/MITECO (límites PN+ZPP) | https://sigred.oapn.es/geoserverOAPN/ows?service=WFS&version=2.0.0&request=GetCapabilities | WFS 2.0.0 (GeoJSON) | **OK** 200, 133 KB caps | no | no | sí | descarga feature ya usada en Spike B (SHA verificado) |
| Gobierno de Aragón — datos abiertos | https://opendata.aragon.es/aod/api/3/action/package_search?q=espacios+naturales | CKAN REST API (JSON) | **OK** 200, 7 datasets (ENP, PORN, APPE, Reservas Biosfera, Humedales) | no | no | sí | — |
| Gobierno de Aragón — descarga vectorial oficial | https://idearagon.aragon.es/datosdescarga/descarga.php?file=MA_MedioNatural/ProtectedSites/rednat_enp.json.zip | HTTPS descarga directa (zip: geojson+xml) | **OK** 200, 441 KB, 33 features ENP (incl. codificación INSPIRE-like: zonecode/planificationzone) | no | no | sí | variantes .shp.zip/.gml.zip/.kmz.zip |
| Gobierno de Aragón — WFS/OWS | https://idearagon.aragon.es/geoserver/wfs (y /geoserver/ows) GetCapabilities | WFS/OWS | **OK** 200 (caps servido; typeNames ENP a fijar en ingesta) | no | no | sí | descarga directa (fila anterior) |
| Gobierno de Aragón — BOA | https://www.boa.aragon.es/ | HTTP (CGI propio) | **OK** portal 200; el contrato exacto de búsqueda documental queda como tarea de ingesta M1 (stubs de 87 B en CGI mal llamado) | no | no | parcial (HTML/estable por MLKOB) | referencia oficial verificada en pnomp.es/es/legislacion (200, título exacto D 16/2022) |
| Parque Nacional de Ordesa (OAPN/OAPN+Aragón) | https://pnomp.es/es/legislacion · /es/pernocta-en-el-parque-nacional | HTML | **OK** 200 | no | no | parcial (monitorizable con hash + selectores; patrón OTA) | boletines oficiales como autoridad primaria |
| reservas parques nacionales (aforos, incl. Góriz/Ordesa) | https://reservasparquesnacionales.es/ | HTTPS (app JS) | **OK** 200 | no | no | por investigar en M2 (app shell; API interna detrás) | página operativa con hash+check_date |
| Comunidad de Madrid — datos abiertos | https://datos.comunidad.madrid/api/3/action/package_search?q=guadarrama | CKAN REST API | **OK** 200 (12 paquetes, pero CSV/JSON estadísticos; sin capa vectorial del PRUG) | no | no | sí (para lo que publica) | BOCM para el texto; capa Anexo III vía portal cartográfico (endpoint real por identificar) |
| Comunidad de Madrid — BOCM | http://www.bocom.org/ | HTTP (**TLS handshake falla: curl exit 35; por HTTP 200 OK**) | **OK** vía http | no | no | parcial (buscador CGI) | — |
| Comunidad de Madrid — geoportal | (geoportal.comunidad.madrid) | — | **ENDPOINT INCORRECTO** (NXDOMAIN global verificado por DoH; nunca existió ese host) | — | — | — | portal real a identificar en M2 desde www.madrid.org (200 OK) |
| Cantabria — IDE (visor oficial) | https://mapas.cantabria.es/ | HTTPS (ESRI Experience Builder; metas declaran WMS/WFS/descargas) | **OK** portal 200; endpoints OGC exactos tras config JS dinámico — tarea de ingesta M2 | no | no | sí (declarado; a extraer el catálogo real) | boc.cantabria.es (200-302) para D 57/2026; OAPN cubre límites del PN ya |
| Cantabria — BOC | https://boc.cantabria.es/ | HTTPS | **OK** (302→ app) | no | no | parcial | — |
| Asturias — SDI | https://www.asturias.es/ | HTTPS | **OK** 200 (IDEPa bajo este dominio; endpoint exacto en M2) | no | no | a extraer | OAPN cubre límites |
| datos.gob.es — API | https://api.datos.gob.es/v1/2.2.4/catalogo/datasets?q=... | REST JSON | **CURRENT_ENVIRONMENT_BLOCKED** (resuelve globalmente por DoH Status=0; el resolver DNS de ESTE entorno devuelve Could not resolve host — exit 6) | no | conocido (público) | sí | www.datos.gob.es sí resuelve (301→OK) como portal |
| datos.gob.es — portal | https://www.datos.gob.es/ | HTTPS | **OK** 301→200 | no | no | parcial | — |

## Clasificación de fallos

- **CURRENT_ENVIRONMENT_BLOCKED**: solo `api.datos.gob.es` (DNS local vs DoH global demostrado).
- **Endpoint incorrecto en el discovery** (no bloqueo): geoportal.comunidad.madrid,
  ide.cantabria.es, www.idearagon.es, reservasonline.aragon.es, cartografia.madrid.org,
  sig.madrid.org, opendata.cantabria.es, boamadrid.org, www.pnordesa.es → hosts que NO existen
  (NXDOMAIN global). El discovery §J los citaba como "bloqueados"; en realidad eran URLs mal
  identificadas. Corregido aquí.
- **SOURCE_UNAVAILABLE**: ninguna fuente pública evaluada.

## Consecuencia por piloto

- **Ordesa (M1): acceso completo demostrado** — OAPN WFS (límites+ZPP, verificado Spike B),
  Aragón descargas oficiales + CKAN, BOA (portal OK; deep-link D 16/2022 como tarea de ingesta
  con el listado oficial de pnomp.es como anclaje), BOE ELI, reservas PN.
- **Picos/Guadarrama (M2)**: portales y boletines autonómicos accesibles; los endpoints
  vectoriales exactos (Cantabria ESRI, CM cartografía) son trabajo de ingesta, no incógnitas
  arquitectónicas.

Scripts de probe: `discovery/spikes/f2-axiom/` no aplican; los probes se ejecutaron en sesión
y su salida cruda quedó en `gis-probes-2026-09-05/` del workspace temporal.
