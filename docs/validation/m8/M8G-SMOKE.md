# M8-G — Smoke de producto real: "¿puedo hacer vivac aquí esta noche?"

Estado: `EJECUTADO (camino CLI)` · Fecha: 2026-09-18 · Resolver: `0.3.0rc1-m8d` + gate boundary (main `ee9b638`)

> Smoke ejecutado sobre geometría oficial IDEM hash-pinned
> (`discovery/evidence/m8-madrid-layers.json`) y los 4 corpus candidatos
> M8-C (`REVIEW_REQUIRED`, no publicables). La respuesta correcta del
> producto en este estado es **UNDETERMINED**: la norma existe como
> candidata pero ningún humano la ha adjudicado todavía. Un `PERMITTED`
> aquí sería un fallo de seguridad jurídica, no un éxito.

## 1. Procedimiento

```bash
# Corpus candidato (4 fixtures M8-C) — reglas REVIEW_REQUIRED
python -m alraso load-corpus --db m8-smoke.db \
    --fixture discovery/evidence/m8-guadarrama/candidate_fixture.json \
    --fixture discovery/evidence/m8-pr-manzanares/candidate_fixture.json \
    --fixture discovery/evidence/m8-pr-guadarrama-medio/candidate_fixture.json \
    --fixture discovery/evidence/m8-pr-sureste/candidate_fixture.json

# Consulta real por coordenada (capas oficiales hash-pinned)
python -m alraso resolve --db m8-smoke.db --activity VIVAC_AL_RASO \
    --date 2026-10-03 --knowledge 2026-09-18 \
    --lat <lat> --lon <lon> \
    --layers-manifest discovery/evidence/m8-madrid-layers.json
```

## 2. Resultados reales

| # | Punto | Scopes resueltos | Resultado | Lectura de producto |
|---|---|---|---|---|
| 1 | Zabala, zona vivac Anexo III (40.83770, -3.95871) | `ss-pnsg-vivac-anexo3` + `ss-pnsg-pn-cm` | UNDETERMINED · INCOMPLETE · `NO_PUBLISHABLE_RULE_COVERAGE` + `EVIDENCE_NOT_PUBLISHABLE` | "La zona está delimitada y hay norma candidata, pero está pendiente de revisión jurídica humana. No es un sí ni un no." |
| 2 | Interior ZPP (40.84224, -3.88060) | `ss-pnsg-zpp-cm` | UNDETERMINED · `NO_KNOWLEDGE_AT_DATE` | "Zona identificada; no hay regla modelada para ella." |
| 3 | Hueco del ZPP — municipio excluido (40.91480, -3.85455) | *(ninguno)* | UNDETERMINED · `NO_APPLICABLE_SCOPE` → clase UNKNOWN | "Fuera de cobertura." (P0: el hueco NO se trata como territorio protegido) |
| 4 | Vértice real del polígono Zabala (40.83850, -3.95822) | `vivac-anexo3` `on_boundary=True` + `pn-cm` | UNDETERMINED · INCOMPLETE · `BOUNDARY_AMBIGUOUS` | "El punto cae justo en el borde oficial; la pertenencia es ambigua y no sostiene ninguna determinación." |
| 5 | Reserva Natural PRCAM (40.75185, -3.90086) | `prcam-reserva-natural` + `prcam-parque` + `zpp-cm` | UNDETERMINED · INCOMPLETE · `NO_PUBLISHABLE_RULE_COVERAGE` | "Tres ámbitos superpuestos detectados; norma candidata pendiente de revisión." |
| 6 | Territorio general CAM (40.4, -3.7) | *(ninguno)* | UNDETERMINED · `NO_APPLICABLE_SCOPE` → UNKNOWN | "Fuera de cobertura." |

## 3. Verificaciones del smoke

- **Scopes correctos por punto** — el resolver reporta TODOS los ámbitos
  aplicables (incl. solapamientos PN/zona-vivac y PR/reserva/ZPP), nunca
  escoge uno silenciosamente.
- **P0 huecos** — el punto 3 cae dentro de un anillo interior del
  MultiPolygon ZPP y NO produce hit (regresión de los 7 huecos).
- **Gate de boundary en producto** — el punto 4 es un vértice REAL de la
  capa oficial; el resolver degrada a `BOUNDARY_AMBIGUOUS` +
  `INCOMPLETE` antes de evaluar reglas, sin determinación limpia.
- **Fail-closed pre-adjudicación** — ningún punto produce `PERMITTED` ni
  `PROHIBITED`: las reglas candidatas son `REVIEW_REQUIRED` y el pipeline
  las excluye con razón explícita (`EVIDENCE_NOT_PUBLISHABLE`).
- **Lenguaje llano** — `ui_texto()` y `legal.js` distinguen los 5
  estados; `CONDITIONAL` nunca se renderiza como un "sí" desnudo
  ("Permitido solo si se cumplen unas condiciones…").
- **Trazabilidad** — cada resultado expone `applicableScope`,
  `reasonCodes`, `ruleVersions`, `evidence` y `dynamicChecks` para
  inspección técnica.

## 4. Pendiente para M8-G completo

- Ejecutar el mismo smoke tras la **adjudicación humana** de las reglas
  candidatas (entonces los puntos 1 y 5 deben producir la clase
  adjudicada — PERMITTED/CONDITIONAL/BLOCKED — y el holdout M8-F podrá
  correr con corpus publicado).
- Integración webapp-Madrid (mapa + tarjeta) como vertical de producto —
  la webapp actual sigue sirviendo Picos/Goriz; el wiring del manifiesto
  de capas a `Service` es trabajo propio (frontend), no bloquea la
  corrección del pipeline.
