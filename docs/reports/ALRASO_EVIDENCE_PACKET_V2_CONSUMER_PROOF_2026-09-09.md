# AlRaso EvidencePacket v2.1 Consumer Proof

**Date:** 2026-09-09  
**Branch:** `feat/evidence-packet-v2-consumer-proof` (from f9a021a)

## 1. Objetivo

Implementar el consumo proof de EvidencePacket v2.1 en AlRaso sin modificar el core `official-sources`:

- **M4.1**: Validador estructural estricto del contracto v2.1 (fail-closed, sin defaults).
- **M4.2**: Adapter que mapea packet → BitemporalStore con verificacion SHA-256 del contenido.
- **M4.2**: Challenge semantico real con la norma LECO (BOE-A-2005-11132) ingestada desde el snapshot DB.

## 2. Flujo implementado

```
JSONL corpus → validator (EvidPacktErr)
                  ↓ validado
               adapter + content_provider
                  ↓ (lee snapshot DB, verifica SHA-256)
               BitemporalStore (source_doc, fragment, scope, rule_version)
                  ↓
               Resolver.resolve(VIVAC_AL_RASO)
                  ↓
               PROHIBITED (LECO Art. 50 = infraccion leve)
```

### Validador (alraso/official_sources_v2.py)

- Schema vendored como constante SCHEMA_JSON + SHA-256 anclado.
- Validacion estricta: campos requeridos, tipos, enums, patrones regex.
- `additionalProperties=false` en cada objeto → campos desconocidos rechazados.
- `EvidencePacketValidationError` raise con razones estructuradas.
- Cero defaults silenciosos.

### Adapter (alraso/ingest/evidence_packet.py)

- `make_snapshot_content_provider()`: abre DB en modo `file:...?mode=ro` (stdlib sqlite3, solo lectura).
- Lookup: `consolidated_laws` → `consolidated_law_versions` → `consolidated_law_text_blocks` por `official_block_id`.
- Verificacion SHA-256 del contenido ANTES de ingesta del fragmento.
- Mismatch → fragmento NO ingestado, determinacion → UNDETERMINED.
- Ingesta atomica en una transaccion F07 (BitemporalStore.transaction).
- Mapeo: provenance → source_document, block → legal_fragment, jurisdiction → spatial_scope, → legal_rule_version (activity=VIVAC_AL_RASO).
- Deteccion de efecto via heuristicas de contenido: "infraccion" + actividad → PROHIBITED.

## 3. Casos y resultados de tests

### M4.1 Validator — Positivos (6 tests)

| # | Test | Resultado |
|---|------|-----------|
| 1 | Fiscal packet valid | PASS |
| 2 | Dominio packet valid | PASS |
| 3 | schema_version == "2.1" | PASS |
| 4 | Schema SHA-256 anchor matches | PASS |
| 5 | PacketPayload parse | PASS |
| 6 | validate_schema_json_sha256 | PASS |

### M4.1 Validator — Negativos (12 tests)

| # | Test | Fallo detectado |
|---|------|-----------------|
| 1 | schema_version "3.0" | Rejected: enum mismatch |
| 2 | content_sha256 alterado (char no-hex) | Rejected: pattern mismatch |
| 3 | Campo requeriente faltante | Rejected: missing required field |
| 4 | Campo desconocido (additionalProperties) | Rejected: unknown top-level key |
| 5 | review_status inventado | Rejected: enum mismatch |
| 6 | jurisdiction inventada | Rejected: enum mismatch |
| 7 | block_type no existente | Rejected: enum mismatch |
| 8 | block_id_status no existente | Rejected: enum mismatch |
| 9 | effective_to_status no existente | Rejected: enum mismatch |
| 10 | artifacts no es lista | Rejected: type mismatch |
| 11 | blocks no es lista | Rejected: type mismatch |

### M4.2 Adapter — Ingesta (6 tests)

| # | Test | Resultado |
|---|------|-----------|
| 1 | Dominio packet ingests successfully | PASS |
| 2 | Fiscal packet ingests successfully | PASS |
| 3 | Fragment has correct provenance | PASS |
| 4 | Content SHA-256 verified before ingest | PASS |
| 5 | Rule version has normative_basis | PASS |
| 6 | Effect determined for LECO | PASS (PROHIBITED) |

### M4.2 Adapter — Hash mismatch (3 tests)

| # | Test | Resultado |
|---|------|-----------|
| 1 | Hash mismatch rejects fragment | PASS (fragment_ingested=False) |
| 2 | Hash mismatch → UNDETERMINED | PASS |
| 3 | Missing content_provider → UNDETERMINED | PASS |

### M4.2 Semantic Challenge (3 tests)

| # | Test | Resultado |
|---|------|-----------|
| 1 | Challenge: resolve PROHIBITED | PASS |
| 2 | Trace preserves evidence_id/packet_id | PASS |
| 3 | Dominio involves a50 blocks | PASS |

### M4.2 Negatives end-to-end (3 tests)

| # | Test | Resultado |
|---|------|-----------|
| 1 | schema_version 3.0 → rejected before ingest | PASS |
| 2 | activity_date before effective_from → UNDETERMINED | PASS |
| 3 | activity_date within window → resolved | PASS |

### Helper functions (7 tests)

| # | Test | Resultado |
|---|------|-----------|
| 1 | LECO Art. 50 → PROHIBITED | PASS |
| 2 | "prohibido" keyword → PROHIBITED | PASS |
| 3 | "permitido" keyword → PERMITTED | PASS |
| 4 | "autorizacion" → AUTHORIZATION_REQUIRED | PASS |
| 5 | Default unknown → AUTHORIZATION_REQUIRED | PASS |
| 6 | consolidate_law_block → VERIFIED | PASS |
| 7 | official_document → REVIEW_REQUIRED | PASS |

**Total tests added: 39 — ALL PASSING.**

## 4. Baseline vs Final

### Baseline (f9a021a)

```
606 passed, 1 failed, 7 skipped
FAILED: test_git_diff_vs_main_only_allowed_files (pre-existing)
```

### Final (feat/evidence-packet-v2-consumer-proof, estado reparado 7eafa92)

`` 
645 passed, 1 failed, 7 skipped
  39 new tests from tests/test_evidence_packet_v2.py: ALL PASSING
  FAILED: test_git_diff_vs_main_only_allowed_files (pre-existing at baseline f9a021a)
`` 

**NEW_FAILURES = 0** (verificado de forma independiente sobre la rama final reparada).

### Nota de reparacion de la rama (2026-09-09)

Durante la ejecucion, una sesion paralela (M5 PWA, worktree dedicado) hizo commit
accidental de su trabajo (ec22e98) sobre esta rama, quedando intercalado entre la
base f9a021a y el commit del proof. Reparacion aplicada: la rama quedo como
f9a021a + cherry-pick del proof (7eafa92), con exactamente los 4 ficheros de este
proof. El trabajo PWA permanece intacto y publicado en su rama canonica
feat/m5-offline-pwa (bca1398 + 93a622a, en origin); ec22e98 era un duplicado
redundante y no se perdio nada.


## 5. Hashes anclados

| Campo | Valor |
|-------|-------|
| VENDOR_SCHEMA_SHA256 | `eea5fd0914a3242208c21f5b6c2f62ab6798f8ed908237b6d358de95e9cab665` |
| Packet fiscal evidence_id | `36d653657d077a1d8593cc894959795347ac078c74ecc45500feb25d9ad34511` |
| Packet fiscal packet_id | `30030456ddcabdff92422e001730249e5b758e368a6f30bb72d66a61457ab041` |
| Packet fiscal block a1 SHA-256 | `4bf62e7ab5a2c7cdc84304b204ac3c3d07ffa717d833aba5a76edf70ad9852fe` |
| Packet dominio evidence_id | `0d2371393ffb94b07ada217633241766228230cbb84fbbcf77aa0c4680069888` |
| Packet dominio packet_id | `25613c9195ddda8e76614d3434ebcd5131de74699c8a3a21ffb4ccec332d7463` |
| Packet dominio block a50 SHA-256 | `6df05e04369f9d8875f5b986c4e02e3a8b72911b1a1607ee610f7ab0147957ea` |

## 6. Hallazgos

### 6.1 LECO — Jurisdiccion y version bitemporal

El dominio packet (BOE-A-2005-11132) tiene:
- `provenance.jurisdiction = "state"` (BOE es estatal)
- `provenance.publisher = "Comunidad Autonoma de las Illes Balears"` (la ley es balear, consolidada en BOE)
- `version.version_date = "2005-06-30"` (version ORIGINAL del Art. 50, letra f)
- `effective_from = "2005-06-30"` (honestidad bitemporal: usa la version original, no la consolidacion 2026)

La DB snapshot tiene 106 bloques para BOE-A-2005-11132 (version 24), y el bloque a50 con hash `6df05e04...` corresponde al Art. 50 original de 2005.

### 6.2 Determinacion del challenge

```
Actividad: VIVAC_AL_RASO
Scope: ep-scope-boe-state (regulatory)
Fecha: 2010-06-15 (dentro de [2005-06-30, open))
K-date: 2026-09-09

Determinacion: PROHIBITED
Razon: LECO Art. 50 letra f — "La acampada, el vivac y la pernocta al aire libre, 
       sin autorizacion o incumpliendo las condiciones" → infraccion leve → PROHIBITED.
```

La trazabilidad preserva:
- `evidence_id` del packet verbatim en el resultado.
- `packet_id` del packet en el campo interpretation_note de la rule_version.
- Fragment ID: `ep-frag-{packet_id}-a50` con locator `BOE-A-2005-11132:a50`.

### 6.3 Limitaciones y desviaciones

- No se implemento un proveedor de contenido real con coordenadas geograficas; el scope se consulta por scope_id, no por lat/lon. Esto es suficiente para el challenge semantico (query por scope_id).
- El efecto se determina via heuristicas de texto (keyword matching). Para un sistema de produccion, se usaria un motor de logica juridica mas robusto.
- Nota: los fallos de test_m5_offline_pwa citados durante la ejecucion pertenecian al estado de working-tree contaminado; en la rama reparada final no existen (ver seccion 4).

## 7. Archivos nuevos / modificados

| Archivo | Estado | Descripcion |
|---------|--------|-------------|
| `alraso/official_sources_v2.py` | NEW | Validador estricto EvidPacket v2.1, schema vendored |
| `alraso/ingest/evidence_packet.py` | NEW | Adapter packet → BitemporalStore, content provider snapshot |
| `tests/test_evidence_packet_v2.py` | NEW | 39 tests: validator, adapter, semantic challenge, negatives |

## 8. Commits

Un commit unico al final: `feat(official-sources): consume EvidencePacket v2.1 normative proof`

No se hace push (constraint del task).