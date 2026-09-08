# AlRaso

¿Puedo dormir al raso aquí? Una app outdoor con una capa jurídica verificable: el mapa te dice qué podemos afirmar con fuentes oficiales — y qué no podemos determinar.

---

## Qué es

AlRaso es una webapp con mapa interactivo ([MapLibre](https://maplibre.org/)) donde cada punto del mapa devuelve una **determinación jurídica-geoespacial**: una actividad (p. ej. `VIVAC_AL_RASO`) en un lugar concreto se resuelve contra el corpus normativo vigente y el resultado es `PERMITTED`, `PROHIBITED`, `AUTHORIZATION_REQUIRED` o `UNDETERMINED`, siempre acompañado de evidencia, trazas y warnings.

El mapa muestra POIs de OpenStreetMap (refugios, agua, abrigos, campings, espacios protegidos) como contexto; cada POI tiene una ficha de lugar con la respuesta legal principal en lenguaje llano, condiciones aplicables, fuentes y explicación. Los usuarios pueden guardar favoritos y salidas con persistencia local del navegador, activar "Mi ubicación" y usar la app en modo responsive.

El **motor jurídico** es una capa bitemporal fail-closed que solo publica `PERMITTED` cuando una versión de regla elegible (revisión legal y espacial completas, evidencia resolvable con procedencia verificada y **base normativa explícita (`normative_basis` ⊆ evidencia: precepto + redacción + ventana de validez que cubra `activity_date`)**) lo afirma de forma trazable, ningún ámbito REGULATORY aplicable queda sin cobertura, y ninguna versión simultáneamente visible de la misma regla está en desacuerdo. **Jamás infiere permisos de la ausencia de datos.** Una entrada malformada produce `UNDETERMINED` normalizado, nunca un traceback.

Además, **NORM_VALIDITY_COVERAGE**: toda versión de regla exige que su base normativa cubra `activity_date`; sin ella, fail-closed a `UNDETERMINED`. El modelo de garantía completo (3 clases: motor, corpus, interpretación) está en [`docs/LEGAL-ASSURANCE-MODEL.md`](docs/LEGAL-ASSURANCE-MODEL.md).

## Pruébalo

```powershell
python webapp/server.py --host 127.0.0.1 --port 8765
```

→ http://127.0.0.1:8765

Requisitos: Python 3.11+; el núcleo no tiene dependencias externas (MapLibre vendorizado, tiles vía OpenFreeMap). El estado legal de cada punto se re-resuelve en vivo contra el motor; los favoritos y salidas viven en el `localStorage` del navegador y **nunca guardan conclusiones legales**.

## Motor jurídico (CLI)

```powershell
python -m alraso load-ordesa --db ordesa.db
python -m alraso resolve --db ordesa.db --activity VIVAC_AL_RASO `
    --scope ss-ordesa-sector-ordesa --date 2021-07-15 --knowledge 2023-06-15   # UNDETERMINED (base normativa RD 409/1995 agotada 30-04-2015 — corrección NORM_VALIDITY 2026-09-08)
python -m alraso resolve --db ordesa.db --activity VIVAC_AL_RASO `
    --scope ss-ordesa-sector-ordesa --date 2023-06-15 --knowledge 2023-06-15   # PROHIBITED (D 16/2022)
python -m alraso replay  --db ordesa.db --new-knowledge 2028-01-01             # determinaciones STALE
```

## Cobertura (honesta)

| Zona | Estado | Detalle |
|---|---|---|
| Góriz (ZUM, PN Ordesa) | VERIFIED (geometría) / RULE BLOCKED | geometría oficial identity-proven (IoU `0.999844`, Hausdorff `0,005 m`); regla NO publicable (trigger vivo no verificable) → determinación UNDETERMINED |
| Picos de Europa | PARTIAL | 3 decretos autonómicos (BOCyL D 17/2025, BOPA D 21/2026, BOC D 57/2026) con regla art. 51 por CCAA; fixtures Phase B cargados; frontera CCAA por IGN/CNIG BDDAE/INSPIRE con guard de 100 m (incertidumbre oficial ~40 m); GISCO retirado del runtime; PARTIAL: excepciones del art. 51 no codificadas (vivac en pared, invierno en Vega La Sotin, tiendas por meteorología adversa) |
| Ordesa (resto) | PARTIAL | fixture M1 cargado, geometría de sectores pendiente (SPATIAL_REVIEW_PENDING_GEOMETRY) |
| Resto del mapa | UNKNOWN | "no sabemos; eso no es una prohibición" |

**Góriz — distinción tres vías** (evidencia espacial ≠ conclusión legal pública):
- `GÓRIZ_GEOMETRY=VERIFIED` — geometría oficial identity-proven (IoU 0.999844)
- `GÓRIZ_RULE_PUBLICATION=BLOCKED` — la regla permanece en corpus pero NO publicable
  (review_status=REVIEW_REQUIRED) mientras el trigger vivo (aforo del refugio) no sea verificable
- `GÓRIZ_USER_RESULT=UNDETERMINED` — con o sin hechos aportados por el caller, nunca PERMITTED

**No implementado / diferido** (NO son carencias de diseño, son próximos hitos):

| Capacidad | Estatus |
|---|---|
| PostgreSQL / PostGIS como almacén normativo | `NOT_IMPLEMENTED` (DDL de referencia en `schema.py`, sin verificación funcional) |
| Axiom adapter | `EXPERIMENTAL_ADAPTER` — solo reglas simples sin condición; `AXIOM_PARITY=NOT_PROVEN` |
| Routing / GPX / offline | `DEFERRED` (no existe) |

## Arquitectura

```text
alraso/
  domain.py           vocabulario cerrado y objetos del contrato
  validation.py       validación estricta (fechas ISO, booleanos, efectos, condiciones)
  eligibility.py      única puerta de elegibilidad de versiones de regla
  precedence.py       grafo de precedencia bitemporal (semántica grounded)
  schema.py           DDL SQLite (append-only + triggers) + DDL PostgreSQL/PostGIS de referencia
  bitemporal.py       almacén append-only, transacciones, selección bitemporal
  conditions.py       AST de condiciones y evaluador total (sin eval)
  errors.py           taxonomía de fallos → reason_codes
  engine.py           protocolo EngineCapabilities + OwnEvaluatorAdapter
  engine_axiom.py     adapter Axiom EXPERIMENTAL (frontera acotada, cache atómico, sha pinning)
  spatial.py          protocolo SpatialProvider + impl in-memory (ray casting)
  ingest/ordesa.py    carga transaccional del fixture empaquetado
  resolver.py         resolve(): pipeline completo + invariante PERMITTED + replay
  cli.py              CLI: load-ordesa | resolve | replay
  resources/          fixture de aceptación Ordesa (paquete incluido)

webapp/
  server.py           servidor local stdlib (http.server), sin dependencias; sin backend remoto/SaaS
  static/             index.html, app.js, store.js (persistencia local de favoritos/salidas;
                      nunca almacena determinaciones legales), style.css, MapLibre vendorizado
  dem.py              elevación auto IGN/CNIG (extra dem, rasterio); fail-closed sin rasterio
  pois.json           POIs OSM observacionales (Ordesa, Picos, protegidos)
  places.json         fichas de lugar con respuesta legal en lenguaje llano
```

## Verificación

```powershell
python -m pytest -q
# 580 passed / 8 skipped hoy; la suite es hermética (sin red ni motor externo)
```

Perfiles de la suite:

| Perfil | Instalado | Resultado |
|---|---|---|
| `audit` (auditoría) | `pytest` + extra opcional `alraso[axiom]` (PyYAML), **sin** binario Axiom | 580 passed, 8 skipped |
| `stdlib-only` | solo `pytest` | un subconjunto corre; el resto se salta con motivo explícito (los números exactos son los de CI) |

el número crece con cada hito; CI es la referencia.

CI ejecuta 7 gates y 1 job de lint (pre-commit: JSON/esquemas/EOF/whitespace + actionlint + lychee no bloqueante).

## Registro interno

Este repositorio conserva la evidencia cronológica del proceso de desarrollo:
descubrimiento técnico, remediación, cierres de hitos y experimentos. Los documentos
relevantes se encuentran en `docs/` (remediación M1, descubrimientos geométricos,
product slice, preview readiness) y en `docs/internal/` (el archivo de historial
cronológico: discovery F2, hitos históricos). Ver
[docs/internal/README.md](docs/internal/README.md) para un índice.

## Licencia y atribuciones

- Código propio de AlRaso: **Apache-2.0** → [`LICENSE`](LICENSE).
- Datos, textos oficiales, material judicial y componentes externos: →
  [`NOTICE.md`](NOTICE.md), con procedencia, hash y estado de verificación de las
  condiciones de reutilización de cada fuente (Apache-2.0 **no** relicencia esos
  materiales).

## Advertencia permanente

Este software determina regímenes normativos codificados en el corpus. Las restricciones
operativas (reservas, accesos, avisos de la dirección del parque) NO están cubiertas y
el resultado SIEMPRE lleva ese warning. No es asesoramiento jurídico. El software se
proporciona "TAL CUAL", sin garantías de ningún tipo (sección 8 de Apache-2.0).
