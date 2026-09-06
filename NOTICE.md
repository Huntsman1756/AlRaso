# NOTICE — terceros, datos y condiciones de reutilización

Este archivo acompaña a `LICENSE` (Apache License 2.0) y **no relicencia nada de
terceros**. `LICENSE` cubre exclusivamente el código propio de AlRaso. Todo lo
listado aquí mantiene la licencia o condiciones de su propio titular, y AlRaso
declara de forma explícita qué está verificado y qué no.

Convención de honestidad usada en todo el proyecto: un hecho se afirma solo si
está comprobado; si no lo está, se marca como `NOT_VERIFIED` en lugar de
presentarse como cumplido.

## 1. Software de terceros

| Componente | Licencia | Cómo se usa | ¿Se distribuye en este repo? |
|---|---|---|---|
| [Axiom Rules Engine](https://github.com/TheAxiomFoundation/axiom-rules-engine) v0.2.2 (commit `d142c64`) | Apache-2.0 (verificado en el `LICENSE` del checkout usado) | Motor externo **opcional** vía CLI, detrás de `AxiomCliAdapter`. Estado declarado: `AXIOM_STATUS=EXPERIMENTAL_ADAPTER`, `AXIOM_PARITY=NOT_PROVEN`. El motor por defecto es el evaluador propio (`DEFAULT_ENGINE=own`). | **No**: ni código fuente ni binario. El binario Linux usado en la integración se identifica por SHA-256 en `tooling/DEPENDENCIES.lock.json` (`d4078c46…f229`) |
| Raíz de RuleSpec `rulespec-es` (usado por el adapter Axiom) | **Material propio generado por AlRaso**: el adapter escribe bajo `ALRASO_AXIOM_ROOT` módulos RuleSpec derivados de las versiones de regla ya ingestadas (archivos `es/policies/<actividad>/ks<hash-de-knowledge-state>.yaml`) | Solo en la ejecución de integración; el directorio de trabajo se crea en `TMP` y nunca se copia al paquete | **No** (y no contiene material de terceros) |
| PyYAML (`>=6,<7`) | MIT (metadatos PyPI) | Solo extra `alraso[axiom]` (serialización RuleSpec) | **No** (dependencia declarada, no empaquetada) |
| pytest (`>=8`) | MIT (metadatos PyPI) | Solo extra `dev` (suites de prueba) | **No** |
| psycopg (`>=3,<4`) | LGPL-3.0-only (metadatos PyPI) | Solo extra `postgis`, que corresponde a `POSTGRES_NORMATIVE_STORE_STATUS=NOT_IMPLEMENTED`: no hay almacén PostgreSQL funcional | **No** |
| [MapLibre GL JS](https://github.com/maplibre/maplibre-gl-js) 4.7.1 | BSD-3-Clause + avisos/licencias de terceros incluidos (mapbox-gl-js ≤v1.13 BSD-3-Clause, glfx.js MIT, d3-color BSD-3-Clause), según `LICENSE.txt` upstream | Renderizador de mapa en el navegador, **vendorizado sin modificar** en `webapp/static/vendor/maplibre-gl.js` / `maplibre-gl.css` | **Sí**: `webapp/static/vendor/maplibre-gl.js`, `webapp/static/vendor/maplibre-gl.css`, texto completo de licencia en `webapp/static/vendor/MAPLIBRE-LICENSE.txt` |

El núcleo de AlRaso es **stdlib-only por diseño**; nada de lo anterior es
necesario para la ruta por defecto.

## 2. Textos normativos oficiales (usados como evidencia)

Se reproduce texto literal de disposiciones oficiales como evidencia citable de
las determinaciones. Los textos oficiales de las Administraciones públicas
españolas están excluidos de protección por derecho de autor (art. 8.1 del
RDL 1/1996, TRLPI); aun así, las **condiciones de reutilización de cada portal
están `NOT_VERIFIED`** y su comprobación es tarea pendiente (M1.1).

| Disposición | Fuente | URL canónica registrada | Estado de la cita |
|---|---|---|---|
| Ley 52/1982 (reclasificación y ampliación del PN Ordesa y Monte Perdido) | BOE | `https://www.boe.es/eli/es/l/1982-07-13/52` | verificada |
| RD 409/1995 (PRUG originario, vigencia agotada) | BOE | `https://www.boe.es/buscar/act.php?id=BOE-A-1995-11259` | verificada |
| Decreto 49/2015 (PRUG PNOMP, Aragón) | BOA n.º 80 (29-04-2015) | PDF consolidado oficial en `aragon.es` / copia MITECO; **deep-link BOA pendiente** (`TAREA_INGESTA`) | parcial |
| Decreto 16/2022 (modifica el régimen de pernocta del sector Ordesa) | BOA (8-02-2022) | listado oficial `https://pnomp.es/es/legislacion`; **deep-link BOA pendiente** (`TAREA_INGESTA`) | parcial |
| Decreto 18/2020 (PRUG PN Sierra de Guadarrama) — extracto | BOCM extraordinario n.º 29 (29-02-2020) | texto consolidado oficial (extracto local, ver hash abajo) | evidencia M2, no usada en M1 |

## 3. Material judicial (identificación, no redistribución)

`discovery/evidence/guadarrama-prug/` contiene **registros de identificación** de
sentencias del TSJ de Madrid (Sala Contencioso-Administrativa, Sección 8.ª) que
afectan al PRUG de Guadarrama: `1135/2021` (rec. 431/2020) y `1003/2022`, entre
otras. No se distribuye el texto de las sentencias: la identificación se apoya en
las notas del **texto consolidado oficial** publicado en BOCM. La obtención del
ECLI vía CENDOJ está **diferida** y documentada como tarea (`tsjm-evidence-registry.json`).

## 4. Datos geoespaciales

Ninguno de estos datos sustenta hoy una determinación `PERMITTED` por coordenadas:
el fixture de aceptación declara `SPATIAL_REVIEW_PENDING_GEOMETRY` y
`M1_ORDESA_REAL_WORLD_SPATIAL=NOT_VALIDATED`. La validación extremo a extremo con
geometría oficial es exactamente el alcance de **M1.1**.

| Conjunto | Procedencia | Fecha de obtención | SHA-256 | Estado de las condiciones de reutilización |
|---|---|---|---|---|
| Límites de PN + ZPP (17 parques + AEP Guadarrama), GeoJSON WFS 2.0.0 | OAPN/MITECO, GeoServer: `https://sigred.oapn.es/geoserverOAPN/LimitesParquesNacionalesZPP/ows?...request=GetFeature&typeNames=LimitesParquesNacionalesZPP:view_red_oapn_limite_pn&outputFormat=application/json` → `discovery/spikes/spike-b-postgis/oapn-limites.geojson` | 2026-09-05 | `7fc5077b223475d69287e2121ed37b7f56b691d7a6df6aa16c7a90be5d678770` (coincide con el hash registrado en `discovery/spikes/spike-b-postgis/README.md`) | `NOT_VERIFIED` |
| Zonificación de espacios naturales protegidos (muestra de la descarga oficial RedNat ENP, 33 features) | Gobierno de Aragón / IDEAragon: `https://idearagon.aragon.es/datosdescarga/descarga.php?file=MA_MedioNatural/ProtectedSites/rednat_enp.json.zip` → muestra en `discovery/evidence/aragon-wfs-enp-zonificacion-muestra.geojson` (entidad `V112_RZ_ENPZonificacion`) | 2026-09-05 | `06b1dc6e4b8aece9b5bc456084a819c0…` (muestra recortada, hash propio) | `NOT_VERIFIED` |
| Extracto del PRUG de Guadarrama y contexto de sentencias (texto) | BOCM / registro propio de evidencia | 2026-09-05 | `c267b53402f8b1480fc185c703a65b55…` y `eeec4af07231ace71e4e60ab7da1a8b0…` | ver sección 2 |

| Extractos de evidencia Góriz (M1.1-C): properties + metadatos geométricos + digest de `ENP101_137`/`ENP101_025` (ICEAragon WFS) y de los features Góriz de `ZonificacionPRUG` (OAPN WFS); texto D 16/2022 (BOA); extracto de `pnomp.es/es/legislacion` | ICEAragon / OAPN-SIGRED / BOA / PNOMP, URLs canónicas fijadas en `tooling/m11c_goriz_scope.evidence.json` → `discovery/evidence/m11c-goriz/*.extract.*` | 2026-09-05 | por artefacto, en `tooling/m11c_goriz_scope.evidence.json` (`artifacts`) | `NOT_VERIFIED` — **no se redistribuyen geometrías completas**; única excepción mínima necesaria: anillo WGS84 de la ZUM (1,25 ha) en `alraso/resources/fixture_goriz.json` |

| Extractos de evidencia Picos (M2-A): verbatim de BOCyL D 17/2025 / BOPA D 21/2026 / BOC D 57/2026 (ámbito, superficies, vigencia, derogatoria, arts. 51-52); digests del límite PN (OAPN WFS, EPSG:25830) y de NUTS2 ES12/ES13/ES41 (GISCO) | BOCyL / BOPA / BOC (PDFs oficiales citados en el lock; NO redistribuidos, 38-77 MB) + OAPN-SIGRED + Eurostat GISCO, URLs canónicas fijadas en `tooling/m2a_picos_discovery.evidence.json` → `discovery/evidence/m2a-picos/*.txt` | 2026-09-06 | por artefacto en el lock; PDFs fuente: `70b07b6d…`(BOCyL) `a1e374e5…`(BOPA) `28ad80f9…`(BOC) `950cff8f…`(GISCO) | `NOT_VERIFIED` — **no se redistribuyen PDFs de diario ni geometrías completas**; solo extracts + digests |
| POIs observacionales (refugios, agua, abrigos, campings, espacios protegidos) — puntos/relaciones extraídos de OSM, curados y enlazados a su objeto | OpenStreetMap vía Overpass (`https://overpass-api.de/api/interpreter`, consultas reproducibles en `webapp/pois.json` → `metadata.query_ordesa` / `query_picos` / `query_protected_ordesa` / `query_protected_picos`) | 2026-09-06 | respuestas Overpass: `b0497550…fe79` (Ordesa nodes) `4d25dbd2…937e` (Picos nodes) `c0606a75…49f` (Ordesa protected relations) `a4341c9f…e67` (Picos protected relations); digest del snapshot curado `7c0ce55c…6f72` | **ODbL-1.0** ([licencia](https://opendatacommons.org/licenses/odbl/1-0/)) — © contribuidores de OpenStreetMap ([attribution](https://www.openstreetmap.org/copyright)). Al redistribuir **datos** OSM como `pois.json`, AlRaso atribuye de forma visible (footer de la UI + enlace a cada objeto OSM) y deja el dataset disponible en el repo para transparencia/reutilización. Snapshot **observacional** y puede quedar desactualizado (`metadata.may_be_stale=true`); **no** es evidencia normativa y no entra en el motor. `poi-goriz` **no** es dato OSM: es un ancla del proyecto (`source=alraso`, `source_ref=alraso_anchor`) |

Nota: OAPN no versiona sus descargas, por eso el hash por descarga es obligatorio
en este proyecto. Si en el futuro se incorporan datasets de OSM, PMTiles,
Refuges.info u otros, se añaden aquí con su licencia y atribución originales.

## 5. Sin garantía / no asesoramiento jurídico

El software se proporciona "TAL CUAL", sin garantías de ningún tipo, conforme a
la sección 8 de Apache-2.0. Determina regímenes normativos codificados en el
corpus ingestado; **no** cubre restricciones operativas (reservas, accesos,
avisos de la dirección del parque) y **no** es asesoramiento jurídico. Cada
resultado lleva ese warning de forma permanente.

```text
CODE_LICENSE=Apache-2.0
THIRD_PARTY_CODE_DISTRIBUTED=maplibre_gl_js_4.7.1 (BSD-3-Clause + bundled notices, see section 1)
THIRD_PARTY_DATA_DISTRIBUTED=official_gis_samples + osm_poi_points (ODbL, see section 4)
DATA_REUSE_TERMS_VERIFICATION=NOT_VERIFIED (M1.1 task)
M1.1_GORIZ_REAL_WORLD=VALIDATED
M1.1_ORDESA_SECTOR_SPATIAL=INCOMPLETE
FIRST_REAL_WORLD_E2E=PASS
M2A_PICOS_DISCOVERY=COMPLETE
M2A_MULTI_JURISDICTION_CLASSIFICATION=A_CONDITIONAL (fixtures Phase B pending approval)
M2A_RUNTIME_IMPLEMENTED=NO
DISCLAIMER=NO_WARRANTY_NOT_LEGAL_ADVICE
```
