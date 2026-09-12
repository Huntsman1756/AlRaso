# M9.0 — Baseline de performance

Estas son observaciones de las dos corridas locales consecutivas, no budgets ni criterios de aprobación. Los tiempos dependen de Windows, red, Chromium, basemap y Open-Meteo; el workflow CI volverá a medirlos en Ubuntu.

## Entorno

- Node `v24.19.0`
- Python `3.12.10` en la corrida local y en CI
- Playwright `1.63.0`
- Chromium `153.0.8010.12`
- Viewports `1440x900`, `390x844`, `360x800`
- 84 resultados observados: 42 por corrida

## Endpoints observados

Los contadores agregan run 1 y run 2. `bytes_total` suma los `Content-Length` disponibles; no es una medición completa de todos los bytes de red.

| Endpoint | Requests | Responses | Failed | Min ms | Median ms | Max ms | Bytes observados |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/api/config` | 192 | 180 | 12 | 0 | 17 | 35 | 11,520 |
| `/api/places` | 192 | 180 | 12 | 0 | 17 | 35 | 2,508,660 |
| `/api/pois` | 84 | 84 | 0 | 2 | 2.5 | 66 | 7,515,480 |
| `/api/protected-areas` | 84 | 84 | 0 | 3 | 7 | 74 | 8,987,412 |
| `/api/coverage` | 89 | 84 | 4 | 1 | 66 | 83 | 302,148 |
| `/api/find` | 82 | 82 | 0 | 0 | 12 | 23 | 14,548 |
| `/api/resolve` | 178 | 172 | 6 | 1 | 5 | 55 | 627,690 |

Los fallos incluyen los transportes abortados explícitamente por S09/S14 y el modo offline de S13. No se han reinterpretado como latencia ni como un error de servidor sin evidencia adicional.

## Duración total de escenario

| Viewport | Escenarios | Min ms | Median ms | Max ms |
| --- | ---: | ---: | ---: | ---: |
| `desktop-1440x900` | 14 | 850 | 2,680 | 6,162 |
| `mobile-390x844` | 14 | 1,088 | 3,649 | 7,703 |
| `mobile-360x800` | 14 | 1,176 | 3,686 | 8,060 |
| Total run 2 | 42 | 850 | 3,559 | 8,060 |

## Lecturas iniciales

- `app.js` solicita datasets grandes en el arranque; la observación de `/api/pois` y `/api/protected-areas` es deliberadamente visible para M9.4.
- El escenario S11 es el más largo en los tres viewports por su secuencia de creación, reapertura y selección de salida.
- No se fija todavía un presupuesto para boot, endpoints o bytes. M9.4 debe derivarlo de esta distribución y de una medición CI estable.
- El clima se registra como observación: S08 recibió HTTP 200 y una estructura UI válida; no se compara una temperatura concreta.
