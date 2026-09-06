# ALRASO — M2 Product Vertical Slice

## Promesa del producto (esto NO es una promesa de cobertura)

> Te mostramos exactamente qué podemos afirmar, con qué fuente y qué partes todavía no podemos determinar.

`UNDETERMINED` y `UNKNOWN` no son fallos de la app: son la respuesta cuando la evidencia no da para más. El core fail-closed
de M1 se expone sin suavizar: ningún punto sin geometría oficial + norma publicable + condiciones puede devolver `PERMITTED`.

## Superficie

```
python webapp/server.py            # http://127.0.0.1:8765 (stdlib, cero dependencias)
mapa (MapLibre vendorizado) → clic → GET /api/resolve → tarjeta
```

- `GET /api/resolve?lat&lon&activity&date&knowledge&<hechos>` → determination (legal/knowledge) + coverage + fuentes.
- `GET /api/coverage` → GeoJSON de regiones de cobertura con `coverage` y `boundary` (`oficial` | `esquematico`).

## Los tres estados de cobertura (capa humana, visible en producto)

| Estado | Significado | Regla dura |
|---|---|---|
| `VERIFIED` | norma vigente verificada en fuente oficial **y** geometría oficial enlazada al motor | solo Góriz ZUM hoy |
| `PARTIAL` | hay verificación pero la determinación punto a punto no está completa | los contornos `esquematico` son SOLO informativos: nunca generan `PERMITTED` |
| `UNKNOWN` | sin corpus: el sistema no afirma nada | `legalStatus=UNDETERMINED` por ausencia, jamás `PROHIBITED` por defecto |

Estado actual: Góriz `VERIFIED` · PN Ordesa `PARTIAL` (geometría de sectores no enlazada) · Picos `PARTIAL`
(3 normas 2026 verificadas en diarios oficiales, sin motor ni DEM de cota) · resto `UNKNOWN`.

## Presupuesto de investigación para nuevas zonas (regla del proyecto desde M2)

**2–4 horas de discovery máximo antes de clasificar cobertura.** Después: gate A→`VERIFIED`, B→`PARTIAL`, C→`UNKNOWN`,
y se sigue construyendo producto. Solo se invierten más días en subir B/C→A si la zona es muy usada, afecta a una
funcionalidad clave, o hay una fuente claramente localizada que merezca perseguirse. El descubrimiento profundo de
M1/M2-A queda como patrón de excepción, no como proceso por defecto.

## Invariante de producto

La capa de cobertura (humana, en `webapp/coverage.json`) **no toca la determinación legal**: el resolver no la lee.
Un contorno esquemático jamás puede producir `PERMITTED`; un `PERMITTED` siempre viene con fuente oficial enlazada.

```
M2_WEB=RUNNING_LOCAL (python webapp/server.py)
M2_COVERAGE=VERIFIED:1 PARTIAL:2 UNKNOWN:resto
M2_RUNTIME_DEPS=zero (stdlib + MapLibre vendorizado)
RESEARCH_BUDGET_PER_ZONE=2-4h_then_A/B/C
M2_STATUS=CLOSED_MAIN=603f642 (PR #8; licencia MapLibre vendida+declarada; CI 6/6)
NEXT_FRONT=M2.1_PRODUCT_PREVIEW_READINESS (docs/ALRASO-M2.1-PREVIEW-READINESS.md)
```
