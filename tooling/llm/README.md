# tooling/llm — Free-LLM auxiliary tooling

**Aislado del core.** Todo esto vive en `tooling/llm/`, **nunca** en `alraso/`.
Es infraestructura auxiliar para acelerar tareas no diferenciales:

- discovery OSS;
- clasificación de repositorios;
- lectura/resumen de documentación;
- generación de propuestas de tests;
- búsqueda de edge cases;
- comparación de implementaciones;
- documentación;
- revisión secundaria.

## Invariante no negociable

```
FREE_LLM_OUTPUT != LEGAL_EVIDENCE
```

Un LLM puede localizar una URL, proponer una regla, comparar documentos o sugerir
tests. Pero **sólo una fuente verificable** puede convertirse en evidencia AlRaso.
El camino es siempre:

```
LLM_RESPONSE
  ↓
SOURCE_DISCOVERY
  ↓
OFFICIAL_SOURCE
  ↓
EXISTING_REVIEW_PIPELINE
```

**Los LLM auxiliares NO pueden:** mergear, aprobar PR, alterar main, publicar
reglas, marcar `SPATIAL_REVIEWED`, marcar `LEGAL_REVIEWED`, transformar un
candidato en `VERIFIED`, ni modificar el corpus automáticamente.

## Datos que no pueden salir

Nunca enviar: secrets, tokens, credenciales, datos personales, repositorios
privados, documentos no públicos, ni datos contractualmente restringidos.

## Arquitectura (mínima, stdlib-only)

```
tooling/llm/
  README.md          <- este archivo
  providers.json     <- proveedores + rol + env var + verificación (sin claves)
  router.py          <- run_llm() (stdlib only: urllib, json, hashlib)
  runs.jsonl         <- registro de metadatos seguros (gitignored)
  tasks/
    oss_discovery.md
    code_review.md
    test_ideas.md
```

Sin LangChain, sin CrewAI, sin AutoGen, sin base de datos, sin cola, sin servidor.

## API

```python
from tooling.llm.router import run_llm

result = run_llm("oss_discovery", "Find OSS for offline MapLibre + PMTiles.")
```

`run_llm(task, prompt, timeout=30)` devuelve:

```json
{
  "provider": "groq",
  "model": "openai/gpt-oss-120b",
  "success": true,
  "latency_ms": 812,
  "response": "...",
  "error": null
}
```

### Routing

```
PRIMARY -> FALLBACK_1 -> FALLBACK_2
```

- Máximo **1 intento por proveedor**.
- Timeout máximo **30 s** (acotado en `router.py`).
- Sin loops, sin reintentos infinitos.
- Si ningún proveedor tiene clave → `success=false`, `error="NO_CREDENTIALS"`.

## Proveedores

`providers.json` define hasta 3 activos. Elegidos tras verificar el directorio
`awesome-freellm-apis` **y** (donde fue posible) la fuente primaria:

| Rol | Proveedor | Base URL | Env var | Card | Verificación primaria |
|---|---|---|---|---|---|
| PRIMARY | Groq | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | No | ✅ `console.groq.com/docs/rate-limits` |
| FALLBACK_1 | Cerebras | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` | No | ⚠️ VERIFY_PENDING (docs 404 en sandbox) |
| FALLBACK_2 | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` | No | ⚠️ VERIFY_PENDING (docs bot-blocked) |

> **GitHub Models fue retirado el 2026-07-30** (`docs.github.com/en/github-models`),
> por lo que se descarta.

Todos usan el endpoint OpenAI-compatible, así que `router.py` no necesita
adapters específicos. **No** se usa el SDK de OpenAI: una llamada HTTP stdlib basta.

### Verificación

El directorio `awesome-freellm-apis` es un **directorio, no una autoridad
contractual**. Para cada proveedor activado debe verificarse contra la fuente
primaria: modelo disponible, endpoint, free tier actual, límites, requisitos de
tarjeta/teléfono, y ToS relevante.

## Secretos

- Sólo env vars: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY`.
- **Nunca** en `providers.json`, **nunca** en git, **nunca** en logs, **nunca**
  en respuestas persistidas.
- Si no existe ninguna clave: `LLM_TOOLING_STATUS=CONFIGURED_NOT_LIVE`. Eso **no**
  bloquea el resto del proyecto.

## Registro

`runs.jsonl` guarda **sólo metadatos seguros**:

```
timestamp, task, provider, model, latency_ms, success, error_class,
prompt_sha256, response_sha256
```

No se guardan prompts/respuestas completas por defecto. `runs.jsonl` está en
`.gitignore`.

## Uso

```powershell
# Sin claves -> devuelve NO_CREDENTIALS
python tooling/llm/router.py --task oss_discovery --prompt "..." --no-log

# Desde Python
python -c "from tooling.llm.router import run_llm; print(run_llm('oss_discovery','x'))"
```

## No-authority

Esta infraestructura **no puede** convertir una extracción jurídica en evidencia
verificada. Es un acelerador, no una autoridad.
