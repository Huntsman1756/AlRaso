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

## Resultado M1.1-B: `D2` — rama CERRADA (2026-09-05)

Evidencia fijada: `tooling/m11b_prug_annex.evidence.json` (URLs canónicas,
`retrieved_at`, SHA-256 y verbatim por página, extraídos del PDF oficial).

Documentos: "Actualización del PRUG. Febrero 2022" (95 págs.) y
**Anexo 11.5. Cartografía** (`ORDESA_PRUG_MAPAS.pdf`, 101 págs., vector, CRS
declarado en todos los mapas: `ETRS'89/GRS80/UTM huso 30T`, fecha del anexo
2013; contenido de aragon.es bajo **CC BY 4.0**).

Cadena normativa verificada:

```text
PRUG 9.2.1 (p.33): "el Parque Nacional se divide en cuatro sectores, definidos
  por las cuencas hidrográficas de los ríos Arazas (Sector Ordesa), Bellós
  (Sector Añisclo), Yaga (Sector Escuaín) y Cinca (Sector Pineta)"
    -> PRUG 9.2.1.3.1 (p.39): vivac PROHIBIDO en el sector Ordesa (excepción
       cupo Góriz); en el resto, restringido sobre cotas 1.650/1.800/2.550 m
       "(Véase Anexo 11.5 Cartografía. Mapa 88)"
        -> Mapa 88 (Anexo p.92): leyenda = Zonas de Vivac por cotas
           (Ordesa 2.500 / Añisclo 1.650 / Escuaín 1.800 / Pineta 2.550)
```

Por qué `D2` y no `D1`:

1. **El Mapa 88 no delimita el Sector Ordesa**: sus polígonos son *bandas de
   altitud* (zonas de vivac), no la frontera sectorial. Ninguna de las 101
   páginas del anexo dibuja la cuenca del Arazas como línea: la frontera
   sectorial está definida jurídicamente por cuenca, pero **no cartografiada**.
2. **El mapa está obsoleto y contradice la norma vigente.** Mapa 88 lleva
   `Fecha: 2013` y su leyenda admite vivac "Ordesa: cota 2.500 m"; el texto
   operativo de 2022 lo **prohíbe** en todo el Sector Ordesa salvo Góriz. Usar
   ese mapa como geometría operativa sería aplicar una regla muerta — y
   *parecería* correcto, que es el peor fallo posible.
3. El anexo arrastra un registro OCG huérfano (2.231 entradas, 174 nombres)
   donde **ninguna página pinta** una capa `sector`/`vivac`/`acampada`: la
   geometría está aplanada, así que ni siquiera una conversión podría separarla
   de forma fiable por etiqueta.

Góriz, aparte y ahora con cadena jurídica: la propia norma (p.20) cita
*"Zona de acampada de alta montaña adyacente al refugio de Góriz (Anexo 11.5
Cartografía. Mapa 29)"* → el vínculo `NORMA → Mapa 29 → polígono` **sí está
probado** (sube de candidato B a A *para ese ámbito concreto*, que no es el
sector). Sigue prohibido mezclarlo con la delimitación sectorial.

Consecuencia: se mantiene **`SPATIAL_EVIDENCE_INCOMPLETE`** y la rama espacial
de M1.1 queda **cerrada** según lo acordado. Si algún día se reabre, el único
camino honesto es la derivación de la cuenca del Arazas (PRUG 9.2.1) mediante
protocolo explícito + revisión humana independiente, etiquetada siempre como
*derivado propio a partir de cartografía normativa oficial*. El runtime no
cambia: la regla de pernocta de Sector Ordesa seguirá devolviendo `UNDETERMINED`
por cobertura espacial incompleta antes que inventar una frontera.
