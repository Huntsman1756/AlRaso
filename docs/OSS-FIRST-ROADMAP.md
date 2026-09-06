# OSS-FIRST Roadmap — AlRaso

Reescritura del **roadmap futuro** a partir de los resultados del
OSS Acceleration Pass (`docs/OSS-ACCELERATION-MATRIX.md`).

- **Método:** cada frente empieza por `OSS_REUSE_GATE` (≤30 min por feature;
  buscar ≥5 candidatos, inspeccionar código, verificar licencia, clasificar
  ADOPT/ADAPT/COPY_PATTERN/REFERENCE_ONLY/REJECT).
- **No se modifican funcionalidades existentes.** `alraso/` intacto.
- **Regla:** si existe un proyecto MIT/Apache/BSD mantenido que cubre ≥70 %,
  `BUILD_FROM_SCRATCH` requiere justificación explícita.

---

## Frentes (máximo 5), en orden de impacto × evidencia

### Frente 1 — Preview pública (desbloquear el host mínimo)

**Objetivo:** salir de `PREVIEW_DEPLOY=READY_PENDING_HOST` con la infraestructura
mínima y reversible que ya está escrita.

**OSS_REUSE_GATE:** no aplica a código nuevo — la infra ya existe.

**Opción mínima documentada (sin desplegar en esta fase):**
- Host propio (VPS Debian/Ubuntu), app stdlib-only (sin pip, sin venv).
- `git clone ... /srv/alraso && sudo ALRASO_DOMAIN=_ bash deploy/provision.sh`.
- nginx → `127.0.0.1:8765` (`deploy/nginx/alraso-preview.conf`), systemd
  (`deploy/systemd/alraso-webapp.service`).
- Basemap **OpenFreeMap** (sin API key), ya es el default
  (`ALRASO_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty`).
- Rollback total documentado en `docs/ALRASO-M2.2-VPS-PREVIEW.md`.

**Definición de hecho:** la preview pública pasa el gate
`DIRECT_OSMF_TILE_USAGE=0 / ATTRIBUTION_VISIBLE / COVERAGE_LAYERS / GORIZ /
UNKNOWN / MAP_CLICK / MOBILE / CONSOLE_ERRORS=0`.

---

### Frente 2 — Refugios / POIs + supercapa de espacios protegidos

**Objetivo:** enriquecer el mapa con refugios, puntos de agua y abrigos, más la
supercapa de espacios protegidos. Datos con proveniencia, no como evidencia legal.

**OSS_REUSE_GATE:**
- Candidatos: `Bist0uille/survival_map` (MIT), `giggls/opencampsitemap` (MIT),
  `giggls/osmpoidb` (Apache-2.0), `cidrlab/boondock_map` (GPL-3.0 → REFERENCE_ONLY).
- **Decisión:** `ADAPT` `survival_map` (consulta OSM de refugios/agua/abrigo +
  `Refuges.info` al clic, CC-BY-SA sin redistribución) + `osmpoidb` (patrón SQL).
- **Qué NO reutilizar:** el frontend React de survival_map; los POIs de terceros
  sin proveniencia propia.
- **Nota:** `boondock_map` es GPL-3.0 → sólo patrón conceptual (carreteras
  forestales legales), nunca importar código a un repo Apache-2.0.

**Definición de hecho:** capa de POIs + áreas protegidas visibles y clicables,
con `source_url`/licencia de datos estampada.

---

### Frente 3 — PMTiles / offline (zonas descargables)

**Objetivo:** servir la propia capa en PMTiles y permitir descarga de zona
(offline-first). Sin backend, sin cuenta.

**OSS_REUSE_GATE:**
- Candidatos: `mploscos/map-zero` (MIT, build), `Bist0uille/survival_map` (MIT,
  cliente), `Mobile-Artificial-Intelligence/atlas` (MIT, móvil),
  `sami-djouhri/karten` (MIT, SQLite/geocoding).
- **Decisión:** `ADAPT` `map-zero` (generación de PMTiles desde OSM/open data) +
  `survival_map` (cliente MapLibre + service worker + descarga de zona).
- **Qué NO reutilizar:** importar el runtime de terceros; AlRaso emite sus propios
  tiles desde datos verificables.
- **Nota:** `atlas` (Kotlin) y `karten` (portal) sólo como patrón offline móvil.

**Definición de hecho:** los datos del producto se sirven como PMTiles y una zona
se puede descargar y ver sin red.

---

### Frente 4 — Routing / GPX

**Objetivo:** crear/cargar rutas que siguen senderos e importar/exportar GPX.

**OSS_REUSE_GATE:**
- Candidatos: `Bist0uille/survival_map` (MIT, BRouter + GPX), `atlas` (MIT,
  BeeRouter offline).
- **Decisión:** `ADAPT` `survival_map` (cliente **BRouter**, servicio gratuito sin
  clave, + import/export GPX + grabación de traza).
- **Qué NO reutilizar:** motor de routing propio (BRouter/BeeRouter ya cubren);
  no añadir backend de rutas.

**Definición de hecho:** ruta por senderos con perfil altimétrico y GPX
importable/exportable.

---

### Frente 5 — Refresh automatizado de coverage y de fuentes

**Objetivo:** mantener la honestidad de coverage y las fuentes al día, sin tocar
main automáticamente.

**OSS_REUSE_GATE:**
- Candidatos: `lowlydba/foul-flock` (MIT), `Bist0uille/survival_map` (MIT).
- **Decisión:** `ADAPT` `foul-flock`: GitHub Action que refresca datos y **abre
  PR** (no mergea), más el patrón de estado `last_checked` ("miramos y no hay" ≠
  "no hemos mirado").
- **Qué NO reutilizar:** las reglas de ALPR/EEUU; la taxonomía de Overture de
  estados; el dominio legal de AlRaso es propio y verificable.

**Definición de hecho:** hay un workflow que regenera coverage/POIs y abre un PR
con los diffs; un humano revisa y mergea.

---

## Preview — opción mínima (sin desplegar en esta tarea)

La infraestructura ya existe y es trivialmente utilizable:
`deploy/provision.sh` + `deploy/nginx/*` + `deploy/systemd/*`. Único requisito:
un host (VPS propio). NO se investigan 10 proveedores cloud; la opción autorizada
y mínima es la del VPS propio ya escrito.

---

## No objetivos (deliberadamente)

- No implementar auth, cuentas, PostgreSQL, microservicios ni agentes autónomos.
- No migrar a React/FastAPI/PostgreSQL ni a `survival_map` entero.
- No implementar PWA/offline/routing todavía — aparecen como frentes 3 y 4,
  no como trabajo inmediato de esta fase.
- Los LLM auxiliares **no** pueden aprobar PR, mergear ni marcar
  `LEGAL_REVIEWED`/`SPATIAL_REVIEWED`.

---

## GATES

```
OSS_REUSE_GATE=YES (per front)
BUILD_FROM_SCRATCH_DEFAULT=NO
PREVIEW_DEPLOY=READY_PENDING_HOST (host mínimo documentado; no desplegado)
```
