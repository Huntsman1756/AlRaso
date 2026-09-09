# Contribuir a AlRaso

AlRaso es una webapp outdoor con motor jurídico-geoespacial bitemporal: el mapa te dice qué podemos afirmar con fuentes oficiales — y qué no podemos determinar.

---

## Setup local

```powershell
git clone <repo>
cd AlRaso
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

`pytest` se instala con el extra `dev`; el paquete `alraso` es stdlib-only (sin dependencias de runtime).

## Ejecutar la webapp

```powershell
python webapp/server.py --host 127.0.0.1 --port 8765
```

Abre http://127.0.0.1:8765. El servidor usa solo stdlib; MapLibre está vendorizado en `webapp/static/vendor/`.

## Ejecutar tests

```powershell
python -m pytest -q
```

La suite es hermética: sin red, sin motor externo. 580 passed / 8 skipped (al día de hoy).

## Gates de CI

CI ejecuta 7 gates (`.github/workflows/gates.yml`): 4 herméticos (py3.11/3.12 × audit/stdlib-only)
+ 2 clean-wheel (linux+windows) + 1 DEM auto-elevación; Axiom = workflow manual aparte,
no bloqueante (`axiom-integration.yml`): prueba comportamiento contra el motor real,
nunca paridad.

## Reglas del proyecto

1. **Core `alraso/` es stdlib-only y fail-closed.** Un bug jamás debe producir un traceback al usuario; produce `UNDETERMINED` normalizado.
2. **Cualquier regla jurídica nueva exige evidencia verificada con fuente oficial + digests.** Ver `NOTICE.md` y `docs/internal/VIVAC-TECHNICAL-DISCOVERY.md` para el patrón de procedencia.
3. **Los POIs son observacionales y jamás determinan legalidad.** Son contexto visual, nunca evidencia normativa.
4. **El estado legal se re-resuelve, nunca se persiste como autoridad.** Los favoritos y salidas viven en `localStorage`; el motor siempre consulta el corpus vigente.

## PR flow

1. Crear rama `feat/<descripción-corta>` o `fix/<descripción-corta>`.
2. Abrir PR contra `main`.
3. CI ejecuta los 7 jobs del gate; todos deben pasar.
4. Merge tras revisión y aprobación.

## Convención de commits

Commits cortos y descriptivos, estilo convencional:

```
type(scope): descripción breve

type: feat | fix | docs | chore | test | refactor
```

## UI: español y accesibilidad

- Todos los textos de la interfaz en español.
- Accesibilidad básica obligatoria: foco visible, targets táctiles ≥ 44 px, labels semánticos, `aria-live` para actualizaciones dinámicas. No depender solo del color para transmitir información.

## Estándares y herramientas OSS (capa estándar)

Adopción de cinco herramientas commodity, maduras y verificables — nada de auditorías hechas a mano:

| Herramienta | Qué previene |
|---|---|
| `pre-commit` (pre-commit-hooks v5.0.0) | JSON corrupto, conflictos de merge, líneas sin LF, BOM, whitespace colgando |
| `check-jsonschema` (v0.38.0) | Deriva de `coverage.json` y `places.json` respecto a los esquemas M2 |
| `markdownlint-cli2` (v0.23.x) | Markdown inconsistente: URLs sueltas, tablas rotas, cabeceras duplicadas, código sin lenguaje |
| `actionlint` (v1.7.x) | Errores en GitHub Actions (jobs rotos, sintaxis yfta) |
| `lychee` (v2.9.x) | Links rotos en docs (no bloqueante; se salta `mailto:`) |

Cada herramienta es reemplazable por una equivalente o superior; la barrera es **madurez**, no vendor-lock-in.

### REVIEW_POLICY (una sola ronda)

Revisión de PR acotada a una ronda para eliminar la fricción burocrática:

1. **Cualquier revisor** abre un PR con un acotamiento mínimo y claro (qué cambia y por qué).
2. **CI + tests**: el PR debe tener ≥2 tests (nuevos + existentes) y el CI debe estar verde (gates + lint).
3. **Revisión adversarial**: el revisor busca errores, no forma. Si encuentra un problema → un comentario con el hallazgo P0/P1.
4. **Blockers**: P0/P1 = reproducibles en CI o local. El autor corrige y push directo a la rama del PR (sin nueva ronda completa).
5. **CI verde + revisión aprobada** → MERGE.
6. Hallazgos no bloqueantes (cosméticos, style, nitpicks) → issue o backlog. **Nunca otra ronda de revisión completa.**

El foso que separa a AlRaso del OSS commodity es irreemplazable: corpus PRUG verificado, vigencia por precepto legal, scopes legales, replay bitemporal, gates. Eso no existe en ningún proyecto OSS estándar; la capa estándar solo acota la base de herramientas, no el dominio.
