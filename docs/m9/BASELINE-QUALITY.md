# M9.0 — Baseline de calidad

La matriz registra capacidad observada en el commit de producto congelado y en el harness M9.0. `present` no significa suficiente; `partial` y `absent` son huecos para M9.1+.

| Área | Estado | Evidencia |
| --- | --- | --- |
| Unit/integration Python | present | `tests/`, `.github/workflows/gates.yml` |
| Clean wheel | present | `tooling/clean_wheel.ps1`, `.github/workflows/gates.yml` |
| Pre-commit | present | `.pre-commit-config.yaml` |
| Schema validation | present | `.pre-commit-config.yaml`, `schemas/` |
| Cross-Python CI | present | `.github/workflows/gates.yml` |
| E2E browser automatizado | present | `qa/browser/tests/baseline.spec.mjs`, 42 combinaciones ejecutadas |
| A11y automatizado | partial | `tests/test_m31_product_ux.py`; no axe en el harness M9.0 |
| Visual regression | absent | M9.0 conserva screenshots canónicos, pero no aplica comparación visual automática |
| JS lint | absent | no script de lint en `qa/browser/package.json` |
| Frontend unit tests | absent | no suite de unit tests para el runtime frontend |
| API contract tests | partial | `tests/test_m2_webapp.py` y validaciones existentes; falta una matriz de contratos desde navegador |
| Performance baseline | present | observer de Playwright y `BASELINE-PERFORMANCE.md` |
| Security headers baseline | partial | observación estática de `webapp/server.py`; no auditoría de headers dedicada |
| Browser harness unit tests | present | `qa/browser/tests/unit/`, 13/13 tests locales |

## Gates ejecutados

- El harness Node/Playwright está aislado en `qa/browser/` y no se añadió Node al runtime Python.
- El servidor real arranca en `127.0.0.1:8765` desde `webapp/server.py`.
- El guard de producto se ejecutó antes, entre y después de las dos corridas.
- Pre-commit pasó con validación JSON, esquemas M2/M8.1, conflictos, whitespace y Markdown.
- No se instaló Rasterio ni DEM para satisfacer S04.
- El workflow `.github/workflows/m9-baseline.yml` fija Ubuntu 24.04, Node 24.19.0, Python 3.12.10, Chromium de Playwright y artifact CI de 14 días.

## Huecos deliberadamente no resueltos

M9.0 no añade axe, ESLint, tests unitarios del frontend, budgets de rendimiento ni aceptación automática de cambios visuales. Esos huecos quedan medidos para que M9.4 pueda elegir herramientas y umbrales con evidencia del estado actual.
