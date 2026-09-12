# M9.1 visual and adversarial review

Fecha: 2026-09-12  
Implementación revisada: `1d81d1ad23b0bc2a2675e2ca3088b518cecee9ea`  
Base: `da0a129089c2a37636c5d02c00783925231192e1`

## Evidencia revisada

- 30 capturas M9.1: 10 escenarios × 3 viewports.
- Viewports: `1440x900`, `390x844`, `360x800`.
- Escenarios: S02, S03, S04, S05, S06, S07, S08, S09, S12 y S14.
- El conjunto completo del runner produjo 42/42 escenarios PASS, con 42/42 JSON de ejecución OK, cero aserciones fallidas y cero requests inesperadas.
- Las diferencias de weather, offline y servidor legal caído son fallos controlados de los escenarios S09, S13 y S14; no se trataron como permiso ni como éxito legal.

## Revisión visual

La comparación manual de las 30 capturas confirma:

- El lugar y la respuesta legal aparecen antes que fuentes y detalle técnico.
- `UNDETERMINED` conserva una explicación explícita de que no significa permitido ni prohibido.
- El contexto OSM/área protegida permanece identificado como cartográfico y secundario.
- Weather muestra el resumen actual y mantiene la previsión de 24 h cerrada por defecto.
- Guardar y Añadir a una salida permanecen visibles como acciones primarias.
- La ficha móvil es utilizable en ambos tamaños; el punto seleccionado se mantiene por encima de la ficha mediante padding de cámara.
- Los escenarios que abren deliberadamente fuentes/detalle pueden terminar desplazados dentro de la ficha; las aserciones de estado primario se realizan antes de abrir esos detalles.

## Revisión adversarial P0/P1

| Control | Resultado | Evidencia |
| --- | --- | --- |
| `false PERMITTED` por simplificación visual | PASS | S03, S07, S14; no se cambió resolver/corpus/reglas |
| Resultado legal stale tras nueva consulta | PASS | S14 y tests del harness; el hotfix de invalidación permanece intacto |
| POI u OSM altera el scope legal | PASS | S05/S06/S07; CTA cartográfica envía sólo coordenadas |
| Weather altera legalidad | PASS | S08/S09; weather se presenta como contexto separado |
| Pérdida de provenance | PASS | S05/S06/S07 mantienen procedencia y disclaimers |
| Pérdida de fail-closed | PASS | S03/S14 mantienen `UNDETERMINED` o error de determinación |
| Framework creep o build obligatorio | PASS | vanilla HTML/CSS/JS; sólo SVG Tabler vendorizado con NOTICE MIT |
| Archivos fuera de alcance | PASS | no hay cambios en `server.py`, resolver, corpus, reglas, routing, GPX, PMTiles ni refresh de datos |

No se identificó ningún hallazgo P0 o P1 reproducible. No se abre remediation path legal.

## Verificación ejecutada

- `node --check webapp/static/app.js`: PASS.
- `npm run unit` en `qa/browser`: 24/24 PASS.
- `PYTHONPATH=. python -m pytest -q`: 755 PASS, 8 skips esperados por dependencias/entorno ausentes.
- Runner browser final: 42/42 PASS.

