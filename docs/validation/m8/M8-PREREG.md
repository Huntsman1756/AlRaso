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
CONDITIONAL                 ← ADJUDICADO en §6 (antes "PERMITTED_WITH_CONDITIONS")
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

El enum original (`alraso/domain.py`) era `PERMITTED | PROHIBITED |
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

**ADJUDICADA (2026-09-17, mandato M8):** se adopta la opción (a) con el
nombre `LegalStatus.CONDITIONAL`. `PERMITTED` significa ahora
*exclusivamente* "todos los requisitos materiales han sido comprobados y
satisfechos"; una condición no verificable nunca colapsa en `PERMITTED`.
Semántica implementada y testeada:

- `PERMITTED` — todo requisito material comprobado y satisfecho.
- `CONDITIONAL` — una norma aplicable permite la actividad pero al menos un
  requisito material no es verificable automáticamente (hecho ausente del
  llamante o restricción operativa no verificada). Un consumidor nunca puede
  presentar `CONDITIONAL` como un "sí" desnudo.
- Hecho ausente en regla restrictiva (PROHIBITED/AUTHORIZATION_REQUIRED) →
  `UNDETERMINED` + `MISSING_FACT` (no se descarta que rija).
- Hecho ausente en regla permisiva sin otra regla activa → `CONDITIONAL` +
  `MISSING_FACT` + campos ausentes en `conditions`.
- Restricciones operativas (`operational_restriction`, M8-D): observaciones
  append-only versionadas por system-time, NUNCA reglas normativas.
  `verified+active+BLOCK` → `PROHIBITED`; `verified+active+RESTRICT` o check
  `required` sin verificar → `CONDITIONAL`. Solo degradan, nunca crean
  respuesta afirmativa. Todos los checks observados se exponen en
  `result.dynamic_checks` (verificados o no).
- `month_window` modela checks estacionales recurrentes (régimen estival de
  Peñalara); fuera de ventana el check no aplica.
- `RESOLVER_VERSION`/`SCHEMA_VERSION` → `0.3.0rc1-m8d`/`m1r3`.

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
| 2026-09-17 | M8-D temporal/excepcional | DONE — `operational_restriction` separado de `legal_rule_version`; checks declarados en los 4 fixtures (incendio + régimen estival Peñalara); demote-only, `dynamic_checks` expuestos; contrato `CONDITIONAL` adjudicado (§6) |
| 2026-09-17 | M8-C PRs | DONE (candidatos) — `m8-pr-manzanares/` (`RC-M8-ES-MD-PRCAM-VIVAC`: Ley 1/1985 art. 14.2.h + D 96/2009 §4.4.8.6/DT1, PRUG-PRCAM sin extraer = laguna), `m8-pr-guadarrama-medio/` (`RC-M8-ES-MD-PRCMG-VIVAC`: prohibición acampada libre D 26/1999+D 124/2002; **verificado que la remisión vivac→PRUG NO existe en este PORN** y que el PRUG nunca fue aprobado), `m8-pr-sureste/` (`RC-M8-ES-MD-PRSE-VIVAC`: régimen zonal Ley 6/1994+D 27/1999; **PRUG D 9/2009 ANULADO** — excluido como base). 9 reglas `REVIEW_REQUIRED`, 14 tests fail-closed verdes. Territorio general CAM: PENDING |
| 2026-09-18 | M8-E resolución por punto | DONE (núcleo) — `alraso/geojson_provider.py`: `GeoJsonLayer` + `load_geojson_provider`/`load_manifest_provider`; capas IDEM hash-pinned (sha256 verificado en carga; mismatch/JSON inválido/geometría ausente → `SpatialFactsError`); emisión constante y por propiedad (`scope_property`+`scope_map`, `unmapped` error/skip, `scope_names`); unión de partes por scope con holes preservados; conflicto de metadatos → error. Manifiesto declarativo `discovery/evidence/m8-madrid-layers.json` (9 entradas → 13 scopes: vivac Anexo III, PN-CM, ZPP, 3 PRs + sus sectores). Gate de boundary consumido en `resolver.py`: hit `on_boundary` en scope REGULATORY → `UNDETERMINED` + `BOUNDARY_AMBIGUOUS` + `INCOMPLETE` antes de evaluar reglas; boundary en CONTEXT_ONLY → warning. 21 tests verdes incl. e2e sobre geometría real (Zabala PERMITTED, ZPP PROHIBITED, hole → NO_SCOPE). |
| — | M8-F/G | PENDING |
