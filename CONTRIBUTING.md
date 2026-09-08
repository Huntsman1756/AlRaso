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