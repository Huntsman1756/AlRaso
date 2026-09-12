# M9 — Backlog derivado de la baseline

Este backlog contiene únicamente findings con evidencia. M9.0 no implementa sus propuestas.

## M9.3 — Backend/runtime y frontera legal

### P0 · determinación legal stale tras fallo de resolve

La misma causa raíz se reprodujo en los tres viewports:

| ID | Viewport | Evidencia | Gate |
| --- | --- | --- | --- |
| `M9-LEGAL-BOUNDARY-001` | `1440x900` | [S14](evidence/baseline/desktop-1440x900/S14_LEGAL_SERVER_DOWN.png) | `blocking_p0=true` |
| `M9-LEGAL-BOUNDARY-002` | `390x844` | [S14](evidence/baseline/mobile-390x844/S14_LEGAL_SERVER_DOWN.png) | `blocking_p0=true` |
| `M9-LEGAL-BOUNDARY-003` | `360x800` | [S14](evidence/baseline/mobile-360x800/S14_LEGAL_SERVER_DOWN.png) | `blocking_p0=true` |

Reproducción común:

1. Resolver Picos con los hechos canónicos hasta obtener `PERMITTED`.
2. Armar el aborto del siguiente `/api/resolve` real.
3. Buscar `41.9, -2.4`.
4. Observar que la ficha conserva `Permitido`, `PERMITTED` y las coordenadas anteriores.

Resultado esperado: un fallo del nuevo resolve no puede presentar una determinación anterior como resultado de la coordenada nueva.

Evidencia completa y campos estructurados: [`findings.json`](evidence/baseline/findings.json). El finding se mantiene sin propuesta de implementación detallada; la solución pertenece a M9.3 y debe conservar el fail-closed legal.

## Sin findings P1–P3 promovidos en M9.0

La revisión de las capturas canónicas y de los resultados estructurados no promovió otros findings con reproducción y evidencia suficientes. Esto no significa que la UX sea definitiva ni que no existan oportunidades P2/P3; significa que no se han convertido en backlog sin un criterio reproducible equivalente al P0 anterior.
