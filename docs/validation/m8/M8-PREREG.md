# M8 — Madrid personal-utility vertical (pre-registro)

Estado: `M8_PREREG` · Abierto: 2026-09-17 · Rama: `feat/m8-madrid-vertical`

> El núcleo técnico y el RC `v0.3.0-rc1` quedan cerrados. La cobertura de
> producto no está cerrada; M8 es el primer vertical orientado a utilidad
> real para un residente en Madrid.

## 1. Pregunta pre-registrada

```text
Given a coordinate and date in Comunidad de Madrid,
can AlRaso return a defensible answer about overnight bivouac
using only authoritative evidence?
```

## 2. Estados que el sistema debe distinguir (mínimo)

```text
PERMITTED
PERMITTED_WITH_CONDITIONS   ← decisión de vocabulario ABIERTA (ver §6)
BLOCKED                     ← se mapea a PROHIBITED en el vocabulario actual
UNDETERMINED
UNKNOWN                     ← fuera de todo scope conocido
```

## 3. Prioridad territorial (orden fijo)

1. Sierra de Guadarrama, lado madrileño — end-to-end.
2. Parque Regional de la Cuenca Alta del Manzanares.
3. Parque Regional del Curso Medio del Guadarrama.
4. Parque Regional del Sureste.
5. Resto de ENP relevantes + Red Natura 2000 (LIC/ZEC/ZEPA).
6. Territorio sin régimen especial — regla general autonómica.

## 4. Casuística de prueba pre-registrada

- Peñalara: vivac limitado al entorno del Refugio Zabala entre 15/06 y
  15/10, una noche, prohibición de perros, grupos >10 con autorización.
- Exclusiones de zonas de vivac en 2023 (modificación de reglas).
- Regla general CAM: acampada libre prohibida en toda la región; vivac
  fuera del PN permitido con carácter general salvo reglas del espacio,
  restricciones temporales y autorización del propietario en privado.

## 5. Gates de seguridad (inalterados)

- Toda regla candidata nace `REVIEW_REQUIRED` + `legal_review_complete=false`
  + `spatial_review_complete=false` → no publicable.
- Publicación SOLO vía artefacto `ReviewDecision` humano válido
  (`alraso/review_decision.py`, `alraso/publish_reviewed.py`).
- Geometría digest-only = `CONTEXT_ONLY`, nunca base de PERMITTED.
- Fuentes: solo oficiales (BOCM, BOE, geoportal CAM, OAPN/MITECO, CNIG).

## 6. Decisión abierta: PERMITTED_WITH_CONDITIONS

El enum actual (`alraso/domain.py`) es `PERMITTED | PROHIBITED |
AUTHORIZATION_REQUIRED | UNDETERMINED | CONFLICT`. La regla general CAM
("permitido salvo condiciones no verificables por el resolver") no encaja
limpio: un `PERMITTED` absoluto sobreafirma; un `UNDETERMINED` permanente
inutiliza el producto en el caso más frecuente.

Opciones:

- **(a)** nuevo `LegalStatus.PERMITTED_WITH_CONDITIONS` — requiere tocar
  el contrato del resolver, la invariante PERMITTED y el modelo de
  garantía. Potente pero es un cambio de núcleo.
- **(b)** `PERMITTED` con condiciones estructuradas en el resultado
  (warnings/evidence ya existen) — sin cambio de vocabulario; el caveat
  queda visible pero el status sigue siendo PERMITTED.

Recomendación pre-registrada: **(b) primero**; (a) solo si la experiencia
de producto lo exige tras M8-E. La decisión final queda registrada aquí
antes de implementar.

## 7. Holdout Madrid (M8-F)

20–30 coordenadas representativas; un subconjunto se mantiene oculto
durante el desarrollo (custodia análoga a M7, menor formalismo). El gate
final es explicación correcta de lo que el sistema sabe y no sabe —
no un score artificial.

## 8. No-objetivos

- No cobertura nacional. No más parques fuera de la prioridad §3.
- No refactor de arquitectura. No nuevos motores. No frontend nuevo.
- No eludir la revisión humana: M8 produce candidatos, no auto-aprobados.

## 9. Salidas de ejecución

`M8-A` inventario de fuentes autoritativo · `M8-B` geometría oficial ·
`M8-C` reglas candidatas · `M8-D` restricciones temporales/excepcionales ·
`M8-E` resolución por punto + decisión de vocabulario · `M8-F` holdout ·
`M8-G` smoke de usuario real ("¿puedo dormir aquí esta noche?").

## 10. Semántica espacial preregistrada (P0 — antes de M8-E)

Política fijada **antes** de implementar el resolver de puntos:

- **Modelo**: cada scope es un conjunto de partes `[exterior, *holes]`
  (semántica GeoJSON Polygon/MultiPolygon). Dentro = dentro de un exterior
  y dentro de ningún hole de esa parte. Los holes NUNCA se aproximan ni se
  rellenan.
- **Boundary**: un punto a distancia ≤ `_EDGE_EPS` (1e-9 grados ≈ 0.1 mm)
  de cualquier arista — exterior o interior — es **ambiguo**. El scope se
  devuelve con `ScopeHit.on_boundary=True`. Un hit boundary-flagged NO
  puede sostener por sí solo una determinación favorable ni desfavorable:
  degrada a `UNDETERMINED`. Los hits no flaggeados son definitivos.
- **Serialización**: las fixtures aceptan `parts_latlon`
  (`[[ext, h1, ...], [ext2, ...]]` con pares (lat,lon)) además del formato
  legacy `rings_latlon` (cada anillo = parte exterior independiente).
  `parts_from_geojson` convierte Polygon/MultiPolygon sin pérdida.
- **Fail-closed**: geometría ausente, malformada o de tipo no soportado →
  `SpatialFactsError` → el resolver degrada a `UNDETERMINED`.

## 11. Registro de ejecución

| Fecha | Salida | Estado |
|---|---|---|
| 2026-09-17 | M8-A fuentes CAM | DONE — D 18/2020 (PRUG, sha256 `f34a023e…`), D 238/2023 (`15616e02…`), D 26/2025 art. 4 (acampada libre prohibida CAM), STSJM 1003/2022 (nulidad 2000 m) |
| 2026-09-17 | M8-B geometría oficial | DONE — IDEM WFS: 5 polígonos vivac Anexo III (`b6fa71b2…`), límite PN-CM+ZPP (`d64025a1…`), zonificación 165 feat. (`ab84aa9f…`), ENP/PRs/RN2000. Geometría real CC-BY 4.0, no digest |
| 2026-09-17 | M8-C Guadarrama | DONE — `discovery/evidence/m8-guadarrama/`: `RC-M8-ES-MD-GUADARRAMA-VIVAC`, 2 reglas propuestas `REVIEW_REQUIRED`, 5 tests fail-closed verdes |
| — | M8-D temporal/excepcional | PARTIAL — Peñalara (15 pax/día, perros) y exclusiones dic/2023 documentadas como cuestiones del revisor; restricción de incendios discrecional no modelable |
| 2026-09-17 | M8-C PRs | DONE (candidatos) — `m8-pr-manzanares/` (`RC-M8-ES-MD-PRCAM-VIVAC`: Ley 1/1985 art. 14.2.h + D 96/2009 §4.4.8.6/DT1, PRUG-PRCAM sin extraer = laguna), `m8-pr-guadarrama-medio/` (`RC-M8-ES-MD-PRCMG-VIVAC`: prohibición acampada libre D 26/1999+D 124/2002; **verificado que la remisión vivac→PRUG NO existe en este PORN** y que el PRUG nunca fue aprobado), `m8-pr-sureste/` (`RC-M8-ES-MD-PRSE-VIVAC`: régimen zonal Ley 6/1994+D 27/1999; **PRUG D 9/2009 ANULADO** — excluido como base). 9 reglas `REVIEW_REQUIRED`, 14 tests fail-closed verdes. Territorio general CAM: PENDING |
| — | M8-E/F/G | PENDING |
