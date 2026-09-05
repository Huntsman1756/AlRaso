# M1.1 — Descubrimiento de geometría oficial (WFS/CSW de ICEARAGON)

Prueba negativa reproducible. Fecha de ejecución: 2026-09-05 (UTC). Herramienta:
`tooling/m11_vector_discovery.py`. Evidencia fijada por hash:
`tooling/m11_vector_discovery.lock.json`.

## Pregunta única

> ¿Existe una geometría vectorial **oficial y jurídicamente identificable** que
> represente el ámbito exacto al que se aplica la regla de pernocta/vivac de
> Ordesa (Sector Ordesa)?

No basta el perímetro del parque. PORN, Natura 2000 u otra figura coincidente no
son sustitutos del sector. La cadena exigida es:

```text
NORMA -> nombra/delimita ambito X -> dataset oficial identifica X -> feature representa X
```

`"parece coincidir"` no es evidencia espacial.

## Fuentes y método (solo oficiales)

Endpoints descubiertos desde las páginas oficiales `idearagon.aragon.es/portal/wfs.jsp`
y `csw.jsp` (cero URLs adivinadas):

| Servicio | URL |
|---|---|
| WFS cartografía básica | `https://icearagon.aragon.es/Visor2D` |
| WFS documentos informativos territoriales | `https://icearagon.aragon.es/DIT` |
| WFS urbanismo (SIUa) | `https://icearagon.aragon.es/SIUa_WMS` |
| CSW (Registro Cartográfico de Aragón) | `https://icearagon.aragon.es/RCA/srv/spa/csw` |

Método: `GetCapabilities` en los tres WFS (1.001 feature types publicados),
`DescribeFeatureType` de las capas candidatas, `GetFeature` sobre la ventana del
PNOMP (`bbox` EPSG:25830, CRS nativo según Norma Cartográfica de Aragón) y
`GetRecords` en el CSW. Todo artefacto queda con `retrieved_at` + SHA-256 en el
lock. Re-verificación: `python tooling/m11_vector_discovery.py --verify`
(si la administración publicara mañana la capa del sector, el verify **falla**
y obliga a reabrir la decisión; si un endpoint no responde, el resultado es
`DISCOVERY_INCONCLUSIVE`, nunca una C silenciosa).

Excluido por diseño: OSM, Wikiloc, digitalización manual, inferencia por
topónimos, polígonos aproximados, geocodificación de textos legales.

## Registro de candidatos

| Capa | Título | Abstract | Identificador/legal | CRS/geom | Hecho decisivo |
|---|---|---|---|---|---|
| `VISOR2D:ENP_ES24` | Espacios Naturales Protegidos (ENP) | vacío | `codigo=ENP101`, `enp_id=201`, `legalfoundationdate=1982-07-12`, `legalfoundationdocument=BOE 1982-07-30 (Ley 15/1982)` | EPSG:25830 / MultiPolygon | **Ámbito: parque completo.** Cadena jurídica demostrada, ámbito equivocado para la regla de sector. Sustituto: PROHIBIDO |
| `VISOR2D:ZENP` (duplicado: `V112_RZ_ENPZonificacion`) | Zonificación ENPs | vacío | sin referencia legal, sin versión | EPSG:25830 | 153 features para `ENP101` = infraestructuras (refugios, fuentes, abrevaderos, pistas, centros de visitantes). **0 features "Sector"**. `planificationzone` vacío en todas |
| `VISOR2D:PORN_ES24` | PORN | vacío | campos `aprobacion/inicio/revision` | EPSG:25830 | **0 features** en la ventana del PNOMP |
| `VISOR2D:ZPORNs` | Zonificación PORNs | vacío | idem | EPSG:25830 | **0 features** en la ventana del PNOMP |
| `DIT:DIT_8_005_a` | Parques Nacionales | — | `codigo=ENP101` + `ZENP101` | — | parque + zona periférica de protección; nada sectorial |
| CSW RCA `AnyText like '%ordesa%'` | — | — | — | — | **0 registros** |

`términos de reutilización`: **no declarada por el servicio** (el portal enlaza
aviso legal, LIGA y precios públicos; verificar antes de redistribuir). Ninguna
capa candidata publica abstract, referencia legal ni versión de dataset.

## Clasificación: `NO_OFFICIAL_VECTOR_SCOPE_FOUND`

Estado espacial: **`SPATIAL_EVIDENCE_INCOMPLETE`**. Rama espacial de M1.1 parada.

Qué significa y qué no:

- NO afirma que el Sector Ordesa no exista jurídicamente: existe y se aplica
  (reglas de vivac distintas por sector desde 2022-02-09).
- AFIRMA que hoy no hay geometría vectorial oficial **publicada** que podamos
  usar como ese ámbito, tras enumerar la totalidad de los servicios oficiales.
- Diagnóstico: la capa ZENP **sí modela** zonificación jurídica en otros espacios
  de Aragón (`Zona de uso limitado`, `ZUG`, `ZUC2`, zonas PORN). La ausencia en
  PNOMP es un **hueco de publicación**, no de modelo.

## Candidato mantenido aparte (grado B, no mezclar)

`ZENP zonecode=ENP101_137` — "Zona de acampada adyacente al refugio de Góriz":
polígono oficial de una zona de acampada oficial. Potencial para *otra* regla.
Su vínculo jurídico con la norma de pernocta está **sin probar**; no se usa para
`PERMITTED`/`PROHIBITED` y nunca se fusiona con la delimitación sectorial.

## Siguiente fase (decisión explícita, no fallback): M1.1-B

Cartografía normativa anexa del PRUG (enlace oficial "Actualización del PRUG.
Febrero 2022" → "Anexo 11.5. Cartografía"; las correcciones del Decreto 49/2015
remiten a mapas concretos del anexo, p. ej. 60/61 y 87/88). Criterio:

```text
PRUG/Decreto -> referencia explicita a cartografia -> mapa del anexo
  -> delimitacion inequivoca del Sector Ordesa -> cadena juridica demostrable
```

Resultados posibles: `D1` frontera explícita (proponer protocolo de vectorización
reproducible + revisión humana independiente; el derivado será SIEMPRE "derivado
nuestro de cartografía normativa oficial", nunca "geometría oficial vectorial", y
no llegará a `SPATIAL_REVIEWED` sin segunda comprobación humana contra el mapa
original) / `D2` mapa oficial sin frontera inequívoca / `D3` sin frontera. Con
D2/D3 se mantiene `SPATIAL_EVIDENCE_INCOMPLETE` y la rama queda cerrada.

Provenance obligatoria de cualquier derivado futuro: `source_document`,
`source_map_number`, `source_page`, `source_sha256`, `source_crs`,
`digitization_method`, `digitization_tool_version`, `operator`, `reviewer`,
`derived_geometry_sha256`.
