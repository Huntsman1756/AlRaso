# M9.0 — Baseline de arquitectura

Inventario estático del producto congelado en `2491d7d5e4e90d380b45c4baee3f2d023008b1a4`. Las métricas describen el estado observado; no prescriben todavía una migración ni una partición de módulos.

## Tamaño y acoplamiento principal

| Archivo | Bytes | LOC | Funciones/defs | Fetch | Listeners | DOM lookups | Try/catch o except |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `webapp/static/app.js` | 77,540 | 1,867 | 64 | 12 | 43 | 162 | 26 |
| `webapp/static/style.css` | 20,453 | 309 | — | — | — | — | — |
| `webapp/static/index.html` | 12,858 | 229 | — | — | — | — | — |
| `webapp/static/store.js` | 6,206 | 184 | 6 | 0 | 0 | 0 | 6 |
| `webapp/static/sw.js` | 4,975 | 132 | 5 | 2 | 3 | 0 | 1 |
| `webapp/server.py` | 31,590 | 696 | 29 | 0 | 0 | 0 | 19 |
| `webapp/dem.py` | 5,563 | 129 | 4 | 0 | 0 | 0 | 9 |

El inventario completo de `alraso/` se conserva en `qa/browser/.m9-runs/run-2/analysis/architecture.json` dentro del artifact de ejecución. Los módulos de dominio de mayor tamaño observados fueron `bitemporal.py` (41,771 bytes, 837 LOC, 35 defs), `resolver.py` (41,621 bytes, 774 LOC, 20 defs), `engine_axiom.py` (17,558 bytes, 392 LOC, 20 defs) y `schema.py` (12,372 bytes, 311 LOC).

## Responsabilidades reales

### Frontend

`app.js` concentra las siguientes responsabilidades detectadas por marcadores reales:

- boot de MapLibre, capas, geolocalización y controles de mapa;
- carga y presentación de POIs y áreas protegidas;
- búsqueda y sugerencias mediante `/api/find`;
- selección de coordenadas y render de la determinación legal;
- bottom sheet (`peek`, `full`, `closed`), favoritos y salidas;
- conectividad/PWA, service worker y banner de conexión;
- consulta y presentación de weather desde Open-Meteo.

La señal objetiva de acoplamiento es la combinación de 12 puntos `fetch`, 43 listeners y 162 accesos DOM dentro de un único archivo de 1,867 líneas. Es evidencia para M9.2, no una decisión de framework.

### Backend y dominio

`server.py` implementa en el mismo servidor stdlib:

- serving HTTP/static y configuración;
- routing y serialización JSON;
- `/api/config`, `/api/coverage`, `/api/find`, `/api/places`, `/api/pois`, `/api/protected-areas` y `/api/resolve`;
- lectura de datasets, búsqueda, cobertura y puente al resolver;
- validación de entradas y manejo de errores.

El paquete `alraso/` contiene las fronteras de dominio que ya existen: bitemporalidad, resolución, precedencia, condiciones, elegibilidad, engine, esquema, validación, espacialidad y CLI. M9.0 no las reordena.

## Dependencias entre superficies

```text
index.html + style.css
        ↓
app.js ── fetch ──> server.py ──> alraso/* / corpus / datasets
  │                      ├──────> /api/resolve
  ├──> Open-Meteo         ├──────> /api/pois + /api/protected-areas
  ├──> MapLibre            └──────> /api/config + /api/find + /api/coverage
  └──> store.js + sw.js
```

El diagrama representa el acoplamiento observado, no una arquitectura objetivo. Cualquier extracción posterior debe preservar primero las fronteras legales y el aislamiento entre cartografía, POIs y determinación.
