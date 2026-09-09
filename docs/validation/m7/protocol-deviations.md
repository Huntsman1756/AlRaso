# Registro de desviaciones del protocolo M7

Estado inicial:

```text
NO_DEVIATIONS_AS_OF_PROTOCOL_CANDIDATE
```

Al congelarse el protocolo, esta línea debe actualizarse a:

```text
NO_DEVIATIONS_AS_OF_FREEZE
```

## Formato de registro de desviación

Cada desviación posterior registra, sin excepción:

- `date`: fecha
- `proposed_by`: quién propone
- `description`: qué cambia
- `reason`: por qué
- `results_already_visible`: si los resultados ya eran visibles cuando se propuso (sí/no)
- `expected_effect`: efecto esperado sobre validez/sesgo
- `disposition`: aceptada / rechazada / escalada a NEEDS_HUMAN_DECISION

Regla: NO se modifica la metodología silenciosamente después de ver resultados. Toda modificación del marco, del main set, del paquete del revisor, de la matriz de desacuerdo o de la puerta de freeze pasa por aquí.

## Desviaciones

(ninguna)

## Correcciones pre-freeze del candidato (no son desviaciones de protocolo)

Correcciones aplicadas durante la revisión del candidato, ANTES del freeze y ANTES de ejecutar R0. Ningún resultado de validación era visible cuando se propusieron. Se registran aquí por transparencia; la línea de estado superior se mantiene mientras no existan desviaciones de un protocolo congelado.

### C-1 (2026-09-09) — Corrección de provenance DEM

- `proposed_by`: gate review externo del candidato (PR #26)
- `description`: sustitución de la referencia "IGN MDT05" por el servicio DEM realmente verificado del repositorio, IGN/CNIG **MDT25** (WCS 2.0.1 `https://servicios.idee.es/wcs-inspire/mdt`, cobertura `Elevacion25830_25`; reuse terms VERIFIED, CC BY 4.0), en marco normativo, sample-generation, main-set (referencia compartida y etiquetas de fuente de elevación), reviewer-instructions y plantilla de informe. Las propias mediciones de elevación registradas (2416/1942/1510/1390 m) NO cambian.
- `reason`: P1_1 `MDT05_UNREGISTERED_PROVENANCE` — el corpus verifica y registra MDT25 (`webapp/dem.py`, `NOTICE.md` §4, `tooling/dem_prep.py`); citar MDT05 fingía una fuente raster no registrada.
- `results_already_visible`: NO
- `expected_effect`: corrige la procedencia; sin efecto sobre la estructura jurídica del marco ni sobre los hechos de los casos.
- `disposition`: ACCEPTED (corrección)

### C-2 (2026-09-09) — Soporte primario completo para P-51-GROUP y P-51-PROHIB

- `proposed_by`: gate review externo del candidato (PR #26)
- `description`: los estratos P-51-GROUP y P-51-PROHIB estaban clasificados `IN_SCOPE_RESOLVABLE` con soporte solo indirecto (resumen del candado de evidencia) y verbatim pendiente. Verificación primaria ejecutada (OPTION_A): descarga de la copia oficial registrada del Decreto 21/2026 y verificación byte-idéntica (sha256 `a1e374e5…` == candado); extracción del texto íntegro del art. 51 → preceptos exactos art. 51.3.a ("No se permitirá, salvo autorización expresa, el vivac de grupos organizados con más de 10 componentes") y art. 51.3.b (prohibición de zanjas de drenaje y parapetos). El marco ahora cita precepto, verbatim y provenance; ambos estratos mantienen `IN_SCOPE_RESOLVABLE` con soporte completo; C06/C07 se conservan. Eliminado el correspondiente `UNRESOLVED_FRAME_ITEM`.
- `reason`: P1_2 `GROUP_PROHIB_MARKED_RESOLVABLE_WITHOUT_EXACT_PRIMARY_SUPPORT`
- `results_already_visible`: NO
- `expected_effect`: el marco queda preregistrado íntegramente desde evidencia primaria verificada; ninguna premisa se completa durante la validación.
- `disposition`: ACCEPTED (corrección)

### C-3 (2026-09-09) — Nits documentales

- `description`: protocol-v1.md: "16 condiciones" → "14 condiciones" en la cabecera; semántica corregida ("Hasta que exista un revisor y haya aceptado:" en §4.4).
- `proposed_by`: gate review externo del candidato (PR #26)
- `results_already_visible`: NO
- `expected_effect`: ninguno sobre validez (documental)
- `disposition`: ACCEPTED (corrección)
