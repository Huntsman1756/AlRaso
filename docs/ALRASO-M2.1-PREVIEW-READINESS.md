# ALRASO — M2.1 Product Preview Readiness

## Objetivo (único)

> Una persona abre AlRaso, busca o pulsa un lugar, y entiende en menos de 10 segundos
> qué sabemos sobre dormir allí, qué NO sabemos y de dónde sale la información.

Validamos **producto**, no ingeniería. El core M1/M2 no se toca: `alraso/` sigue
inalterado; `VERIFIED/PARTIAL/UNKNOWN` sigue separado del resolver; los contornos
`esquematico` siguen sin poder mintar `PERMITTED` (tests M2 intactos y en verde).

## Qué se ha construido (rama feat/m2.1-preview-readiness)

1. **Titular en lenguaje llano** (`ui_texto` en `webapp/server.py`, campo `ui` en
   `/api/resolve`). Los códigos canónicos (`PERMITTED`, `CURRENT`, `VERIFIED`…)
   **nunca desaparecen** de la respuesta: se muestran en «Detalle técnico».
   Regla dura del titular `UNDETERMINED`: siempre dice *«no es un permiso, pero
   tampoco una prohibición»* (testeado para los tres estados de cobertura).
2. **Búsqueda** (`/api/places`, `/api/find`): coordenadas (`42.66, -0.01` /
   `42,66; -0,01` / `42.66 -0.01`) o nombre aproximado (sin acentos/mayúsculas)
   sobre una lista curta y honesta en `webapp/places.json`. Sin coincidencia
   clara → `kind=none`/mensaje; nunca adivina. La lista no afirma nada legal:
   el estado lo decide el resolver, y un test bloquea cualquier `PERMITTED`
   inesperado en los sitios curados.
3. **Accesibilidad/responsive**: foco visible, etiquetas `label/for`, `role=search`,
   `aria-live` en tarjeta y mensajes, controles táctiles ≥44 px en móvil, contraste
   de texto atenuado subido. Botón «Usar el centro del mapa» = camino accesible
   por teclado para determinar un punto sin puntero fino.

## Checklist de revisión humana (esto NO lo puede hacer el CI)

Abrir `python webapp/server.py` y responder SÍ/NO en escritorio y móvil:

- [ ] ¿Se entiende la diferencia entre situación legal / estado de la información / cobertura **sin** leer el detalle técnico?
- [ ] ¿Un punto UNKNOWN (busca «Punto de control») se entiende como «no sabemos» y NO como «prohibido»?
- [ ] ¿El titular de Góriz con «refugio sin capacidad» + noches se entiende en <10 s?
- [ ] ¿Fuentes y condiciones son legibles (tamaño, contraste, enlaces)?
- [ ] ¿El mapa invita a pulsar? ¿La búsqueda se descubre?
- [ ] En móvil: ¿mapa usable, tarjeta alcanzable, teclado táctil cómodo?

Cualquier NO genera issues concretos de copy/UX; no se abre ninguna otra revisión
técnica ni jurídica.

## Preview pública: bloqueado hasta resolver deuda de teselas

```text
PREVIEW_DEPLOY=BLOCKED
TILE_DEBT=tile.openstreetmap.org_usado_directamente (ok local/demo con atribucion; NO para trafico publico)
ACTION_BEFORE_DEPLOY=cambiar a proveedor/tiles propios + revisar politica de uso
OSM_TILE_POLICY_VERIFIED=NOT_VERIFIED
```

La atribución «© OpenStreetMap contributors» ya aparece en el mapa; aun así,
`tile.openstreetmap.org` no está pensado para producto público.

## Ampliación de cobertura (mientras tanto)

Sigue el presupuesto M2: **2–4 h por zona → A(`VERIFIED`)/B(`PARTIAL`)/C(`UNKNOWN`) → seguir**.
Prohibido volver al proceso Ordesa. Cada zona nueva: fila en `webapp/coverage.json`
(+ sitio curado en `places.json` si procede) y sus tests de invariantes.

## Fuera de alcance (explicito, no reabrir)

```text
auth / perfiles / comunidad / chat / retos / offline / app nativa
PostgreSQL productivo / Axiom parity
```

## Estado

```text
M2_STATUS=CLOSED (main 603f642)
M21_PLAIN_LANGUAGE=SHIPPED_CODES_PRESERVED
M21_SEARCH=PLACES_AND_COORDS_FAILCLOSED
M21_A11Y=BASIC_HOOKS_IN (foco/labels/aria-live/44px)
M21_HUMAN_UX_REVIEW=PENDING (checklist de arriba)
ALRASO_CORE_TOUCHED=NO
PREVIEW_DEPLOY=BLOCKED_TILE_DEBT
```
