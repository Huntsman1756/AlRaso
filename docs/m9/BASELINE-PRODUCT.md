# M9.0 — Baseline de producto

Estado de cierre local: `M9.0 BASELINE COMPLETE`

Publicación CI: pendiente de ejecutar en GitHub; el workflow está committeado, pero esta sesión no hace push.

Decisión de programa: `M9 PROGRAM BLOCKED` por tres reproducciones del mismo P0 de integridad legal en S14. M9.0 queda cerrado como baseline; no se ha aplicado ningún fix de producto.

## Identidad de la evidencia

| Campo | Valor |
| --- | --- |
| Product commit | `2491d7d5e4e90d380b45c4baee3f2d023008b1a4` |
| QA harness commit | `44d807690630c0710700f1bd72a5aed7eaf6df2b` |
| Baseline now | `2026-09-12T07:20:00+02:00` |
| Locale / timezone | `es-ES` / `Europe/Madrid` |
| Viewports | `1440x900`, `390x844`, `360x800` |
| DEM / Rasterio | ausente / ausente |

La ejecución local usada para generar esta evidencia fue Windows x64, Node `v24.19.0`, Python `3.12.10`, Playwright `1.63.0` y Chromium `153.0.8010.12`. El workflow canónico fija el mismo runtime; su ejecución CI queda pendiente de publicar porque esta sesión no hace push.

## Resultado de ejecución

| Gate | Resultado |
| --- | --- |
| Combinaciones ejecutadas | 42/42 en cada corrida |
| Playwright tests | 42/42 passed en run 1 y run 2 |
| Resultados estructurados | 42/42 por corrida |
| Contratos reproducibles | 42/42 |
| `HARNESS_ERROR` | 0 |
| `ENVIRONMENT_ERROR` | 0 |
| `NON_REPRODUCIBLE` | 0 |
| Scenario status | 39 `PASS`, 3 `FAIL` |
| Findings | 3 instancias P0, una causa raíz |
| Product files changed | no |

`PASS` aquí significa que las aserciones estables de la ejecución fueron reproducibles. No es una valoración de calidad visual, accesibilidad o readiness.

## Catálogo ejecutado

Cada enlace apunta al screenshot final canónico de run 2. Las tres columnas cubren exactamente la matriz de viewports.

| Escenario | Desktop 1440×900 | Mobile 390×844 | Mobile 360×800 | Estado |
| --- | --- | --- | --- | --- |
| S01 `BOOT_EMPTY` | [PNG](evidence/baseline/desktop-1440x900/S01_BOOT_EMPTY.png) | [PNG](evidence/baseline/mobile-390x844/S01_BOOT_EMPTY.png) | [PNG](evidence/baseline/mobile-360x800/S01_BOOT_EMPTY.png) | PASS |
| S02 `SEARCH_KNOWN_PLACE` | [PNG](evidence/baseline/desktop-1440x900/S02_SEARCH_KNOWN_PLACE.png) | [PNG](evidence/baseline/mobile-390x844/S02_SEARCH_KNOWN_PLACE.png) | [PNG](evidence/baseline/mobile-360x800/S02_SEARCH_KNOWN_PLACE.png) | PASS |
| S03 `COORDS_UNKNOWN` | [PNG](evidence/baseline/desktop-1440x900/S03_COORDS_UNKNOWN.png) | [PNG](evidence/baseline/mobile-390x844/S03_COORDS_UNKNOWN.png) | [PNG](evidence/baseline/mobile-360x800/S03_COORDS_UNKNOWN.png) | PASS |
| S04 `PICOS_PERMITTED` | [PNG](evidence/baseline/desktop-1440x900/S04_PICOS_PERMITTED.png) | [PNG](evidence/baseline/mobile-390x844/S04_PICOS_PERMITTED.png) | [PNG](evidence/baseline/mobile-360x800/S04_PICOS_PERMITTED.png) | PASS |
| S05 `POI_NAMED` | [PNG](evidence/baseline/desktop-1440x900/S05_POI_NAMED.png) | [PNG](evidence/baseline/mobile-390x844/S05_POI_NAMED.png) | [PNG](evidence/baseline/mobile-360x800/S05_POI_NAMED.png) | PASS |
| S06 `POI_UNNAMED` | [PNG](evidence/baseline/desktop-1440x900/S06_POI_UNNAMED.png) | [PNG](evidence/baseline/mobile-390x844/S06_POI_UNNAMED.png) | [PNG](evidence/baseline/mobile-360x800/S06_POI_UNNAMED.png) | PASS |
| S07 `PROTECTED_AREA` | [PNG](evidence/baseline/desktop-1440x900/S07_PROTECTED_AREA.png) | [PNG](evidence/baseline/mobile-390x844/S07_PROTECTED_AREA.png) | [PNG](evidence/baseline/mobile-360x800/S07_PROTECTED_AREA.png) | PASS |
| S08 `WEATHER_AVAILABLE` | [PNG](evidence/baseline/desktop-1440x900/S08_WEATHER_AVAILABLE.png) | [PNG](evidence/baseline/mobile-390x844/S08_WEATHER_AVAILABLE.png) | [PNG](evidence/baseline/mobile-360x800/S08_WEATHER_AVAILABLE.png) | PASS |
| S09 `WEATHER_UNAVAILABLE` | [PNG](evidence/baseline/desktop-1440x900/S09_WEATHER_UNAVAILABLE.png) | [PNG](evidence/baseline/mobile-390x844/S09_WEATHER_UNAVAILABLE.png) | [PNG](evidence/baseline/mobile-360x800/S09_WEATHER_UNAVAILABLE.png) | PASS |
| S10 `SAVE_FAVORITE` | [PNG](evidence/baseline/desktop-1440x900/S10_SAVE_FAVORITE.png) | [PNG](evidence/baseline/mobile-390x844/S10_SAVE_FAVORITE.png) | [PNG](evidence/baseline/mobile-360x800/S10_SAVE_FAVORITE.png) | PASS |
| S11 `OUTING_FLOW` | [PNG](evidence/baseline/desktop-1440x900/S11_OUTING_FLOW.png) | [PNG](evidence/baseline/mobile-390x844/S11_OUTING_FLOW.png) | [PNG](evidence/baseline/mobile-360x800/S11_OUTING_FLOW.png) | PASS |
| S12 `MOBILE_SHEET` | [PNG](evidence/baseline/desktop-1440x900/S12_MOBILE_SHEET.png) | [PNG](evidence/baseline/mobile-390x844/S12_MOBILE_SHEET.png) | [PNG](evidence/baseline/mobile-360x800/S12_MOBILE_SHEET.png) | PASS |
| S13 `OFFLINE_VISITED` | [PNG](evidence/baseline/desktop-1440x900/S13_OFFLINE_VISITED.png) | [PNG](evidence/baseline/mobile-390x844/S13_OFFLINE_VISITED.png) | [PNG](evidence/baseline/mobile-360x800/S13_OFFLINE_VISITED.png) | PASS |
| S14 `LEGAL_SERVER_DOWN` | [PNG](evidence/baseline/desktop-1440x900/S14_LEGAL_SERVER_DOWN.png) | [PNG](evidence/baseline/mobile-390x844/S14_LEGAL_SERVER_DOWN.png) | [PNG](evidence/baseline/mobile-360x800/S14_LEGAL_SERVER_DOWN.png) | FAIL + P0 |

Detalles observados en los casos especiales:

- S04 introdujo por UI `VIVAC_AL_RASO`, `actividad_montana_o_escalada=true`, `nights=2` y `cota_m=2400`; no necesitó DEM ni Rasterio.
- S08 recibió una respuesta real de Open-Meteo; la temperatura y la hora observadas son volátiles y no participan en el comparador.
- S09 abortó el transporte real hacia `api.open-meteo.com` y mantuvo disponible la resolución legal.
- S13 controló el shell con service worker y dejó `/api/*` en red; no presentó weather stale.
- S14 abortó únicamente el segundo `/api/resolve`. El resultado `PERMITTED` anterior quedó visible para la nueva coordenada `41.9, -2.4`; el detalle está en [`findings.json`](evidence/baseline/findings.json).

## Observabilidad

No hubo `pageerror` ni fallos de red inesperados en los 42 resultados de run 2. Se observaron 31 mensajes `console.error`, asociados a respuestas 503 de Open-Meteo en POI, al abort explícito de S09, al modo offline de S13 y al abort explícito de S14. Se conservan en los artifacts completos de CI; no se han convertido en findings adicionales porque las aserciones de esos escenarios fueron reproducibles y no hubo una excepción de página.

## Alcance de la decisión

La baseline queda cerrada. El programa queda bloqueado por `blocking_p0=3`; son tres reproducciones por viewport de una misma causa de integridad legal, no tres correcciones independientes. No se ha modificado `app.js`, `style.css`, `index.html`, `server.py`, `alraso/**` ni el corpus/reglas.
