# M9.2 visual and adversarial review

Fecha: 2026-09-13
Implementación revisada: `328307bb618ed07d708f265e8e1f460072b3505c`
Base: `cfe896d766025980c75a903a3b5148501d667089` (cierre M9.1)

## Evidencia revisada

- 30 capturas M9.2: 10 escenarios × 3 viewports (`after/`).
- Viewports: `1440x900`, `390x844`, `360x800`.
- Escenarios: S02, S03, S04, S05, S06, S07, S08, S09, S12 y S14.
- La corrida completa produjo 42/42 tests Playwright y 42/42 `scenario_status=PASS` en los JSON de ejecución, con cero aserciones fallidas, cero `pageerror` y cero fallos de red inesperados (`task-15-evidence-328307b`).
- `p0-remediation` (S03/S04/S14 × 3 viewports): 9/9 PASS (`task-15-p0-328307b`).
- Las diferencias de weather entre las capturas M9.1 y M9.2 son campos volátiles documentados (temperatura, viento, precipitación); la estructura del bloque es idéntica.

## Revisión visual (vs capturas M9.1)

La comparación estructural de las capturas confirma "no visual difference intended":

- Mismo orden de lectura: lugar → respuesta legal → condiciones → weather compacto → acciones → fuentes/detalle.
- `UNDETERMINED` conserva la explicación explícita de que no significa permitido ni prohibido (S02, S03, S14).
- `Permitido` en S04 muestra las condiciones evaluadas y los facts del formulario idénticos a M9.1.
- Weather mantiene "Próximas 24 h" cerrado por defecto y el copy honesto de no-disponibilidad en S09.
- La ficha móvil (S12) conserva el estado peek, el handle accesible y el padding de cámara que mantiene el punto seleccionado visible.
- S14 mantiene el error de determinación honesto con el servidor legal caído; ningún resultado stale se presenta como actual.

## Hallazgo registrado durante la revisión (resuelto)

```text
HARNESS_FINDING_M9.2_002
severity = P0 producto / P1 QA
type = PRODUCT_REGRESSION + FALSE_GREEN
cause = shadowing de `var sheet` hoisteado dentro de selectPoint
        sobre el controlador del sheet extraído en cae9b28 (task 12)
impact = sheet.openSheetForSelection() leía el local undefined y lanzaba
         TypeError antes de legal.refresh(): /api/resolve nunca se
         disparaba y toda selección de punto quedaba sin respuesta legal
detected_by = evidencia task-15: 35/42 scenario_status=FAIL pese a
              "42 passed" de Playwright; p0-remediation 9/9 FAIL
resolution = 293de55 (rename var sheet -> sheetEl, fix mínimo) +
             4a52786 (baseline.spec rethrow on scenario_status=FAIL)
verification = task-15-evidence-328307b: 42/42 PASS, 0 page_errors;
               p0-remediation 9/9 PASS
```

Corrección del registro: el `BASELINE_AFTER = 42/42` anotado para la task 13
(`task-13-composition-4cfb1d2`) fue un false green — 35/42 JSON ya registraban
`scenario_status=FAIL` en esa corrida. El cierre válido es el de esta revisión.

## Revisión adversarial P0/P1 (checklist M.2.10)

| Control | Resultado | Evidencia |
| --- | --- | --- |
| M9.1 preservado | PASS | 30 capturas estructuralmente idénticas; `style.css` diff cero |
| Ningún módulo acoplado | PASS | matriz `ALLOWED_IMPORTS` encerrada en `test_m92_frontend_architecture.py` |
| Ciclos de imports = 0 | PASS | DFS en el test de arquitectura |
| Sin globals nuevos | PASS | test `window.*` sin nuevas asignaciones; `AlRasoStore`/`maplibregl` preexistentes |
| legal ≠ weather ≠ OSM | PASS | `weather.js` solo importa `dom.js`; `place.js` no importa canal legal; Open-Meteo solo vive en `weather.js` |
| Stale protection intacta | PASS | `resolveRequestId` monótono en closure de `legal.js`; p0-remediation 9/9 |
| Offline carga todos los ESM | PASS | `SHELL_URLS` ↔ `STATIC_FILES` ↔ ficheros consistentes por test; S13 PASS en los 3 viewports |
| Tests no debilitados | PASS | migraciones K.2 documentadas por commit; suite completa 764 passed + 8 skips |
| Sin dependencia nueva | PASS | cero paquetes nuevos; módulos ES nativos |
| app.js = composición real | PASS | 305 LOC, 9 funciones top-level, 0 fetch, 8 listeners, solo orquestación |
| Named imports M.3 | PASS | lock por nombre: `map.js`→`api-legal.js` solo `fetchCoverage`; `saved.js`→`place.js` solo `POI_CATS` (328307b) |
| `import()` dinámico ausente | PASS | test de arquitectura |
| `server.py` solo allowlist | PASS | diff = 12 entradas `STATIC_FILES` data-only; endpoints/routing/resolver intactos |

Tras la resolución del hallazgo no queda ningún P0/P1 abierto. No se abre
remediation path legal.

## Verificación ejecutada

- `PYTHONPATH=. python -m pytest -q`: 764 PASS, 8 skips esperados.
- `npm run unit` en `qa/browser`: 48/48 PASS (incluye `modules.test.mjs` de loadability sin side effects).
- `node --check` PASS en `app.js` y los 12 módulos.
- Runner browser final: 42/42 Playwright + 42/42 `scenario_status=PASS` (`task-15-evidence-328307b`).
- `p0-remediation`: 9/9 PASS (`task-15-p0-328307b`).
- Métricas BEFORE/AFTER registradas en `manifest.json` (`architecture_metrics`).
