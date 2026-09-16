# AlRaso EvidencePacket v2.1 Consumer Proof

**Date:** 2026-09-09
**Remediated:** 2026-09-16 (PR #40 review — legal boundary P0 + hermetic tests P1)
**Branch:** `feat/evidence-packet-v2-consumer` (from `main` 4718b04)

## 0. Remediation note (PR #40 blocking review)

The original proof (branch `feat/evidence-packet-v2-consumer-proof`) crossed
the legal boundary: the adapter derived a legal effect from text keywords
(`_determine_effect_for_activity`), wrote a `VERIFIED` regulatory scope from
document jurisdiction alone, auto-completed `legal_review_complete` /
`spatial_review_complete`, mapped `consolidated_law` to `VERIFIED`, and
fabricated `effective_from="2000-01-01"`. It also depended on machine-local
paths (`G:\_Proyectos\mcp\...`), breaking hermetic CI.

The remediated adapter is **evidence-only**:

```text
EvidencePacket v2.1
    -> strict validation (fail-closed)
    -> content provider (read-only snapshot, SHA-256 verified)
    -> source_document + legal_fragment (REVIEW_REQUIRED)
       + spatial_scope candidate (REVIEW_REQUIRED)
    -> human review (outside this adapter)
    -> only then a publishable legal_rule_version
```

It never writes `legal_rule_version`, never infers an effect, never marks
anything publishable, and never fabricates dates.

## 1. Objetivo

Implementar el consumo de EvidencePacket v2.1 en AlRaso sin modificar el core
`official-sources`:

- **M4.1**: Validador estructural estricto del contrato v2.1 (fail-closed, sin defaults).
- **M4.2**: Adapter evidence-only packet → BitemporalStore con verificación SHA-256 del contenido.
- **M4.2**: Gate de publicación: la evidencia ingerida queda REVIEW_REQUIRED y no es consumible por el resolver hasta revisión humana.

## 2. Flujo implementado

```
JSONL corpus → validator (EvidencePacketValidationError)
                  ↓ validado
               adapter + content_provider
                  ↓ (lee snapshot DB read-only, verifica SHA-256)
               BitemporalStore:
                 source_document  (provenance; official_status NULL)
                 legal_fragment   (REVIEW_REQUIRED)
                 spatial_scope    (REVIEW_REQUIRED, REGULATORY)
                  ↓
               Resolver → UNDETERMINED (nada publishable sin revisión humana)
```

### Validador (alraso/official_sources_v2.py)

- Schema vendored como constante SCHEMA_JSON + SHA-256 anclado.
- Validación estricta: campos requeridos, tipos, enums, patrones regex.
- `additionalProperties=false` en cada objeto → campos desconocidos rechazados.
- `EvidencePacketValidationError` con razones estructuradas.
- Cero defaults silenciosos.

### Adapter (alraso/ingest/evidence_packet.py)

- `make_snapshot_content_provider()`: abre DB en modo `file:...?mode=ro` (stdlib sqlite3, solo lectura).
- Lookup: `consolidated_laws` → `consolidated_law_versions` → `consolidated_law_text_blocks` por `official_block_id`.
- Verificación SHA-256 del contenido ANTES de ingesta del fragmento.
- Mismatch → fragmento NO ingerido (rejected_block_ids + warning).
- Ingesta atómica en una transacción F07 (BitemporalStore.transaction).
- Mapeo: provenance → source_document, block → legal_fragment REVIEW_REQUIRED, jurisdiction → spatial_scope candidato REVIEW_REQUIRED.
- **No crea `legal_rule_version`.** La regla publicable la escribe la revisión humana.

## 3. Casos y resultados de tests

Tests herméticos: paquetes sintéticos en memoria + snapshot DB generado en
runtime (`tmp_path`). Sin rutas de máquina, sin red, sin credenciales.

### M4.1 Validator — Positivos (6 tests): PASS

### M4.1 Validator — Negativos (11 tests): PASS
(schema 3.0, sha256 no-hex, campo requerido ausente, campo desconocido,
enums inválidos: review_status/jurisdiction/block_type/block_id_status/
effective_to_status, artifacts/blocks no-lista)

### M4.2 Adapter — evidence ingest (7 tests): PASS
(ingesta REVIEW_REQUIRED, provenance de fragmento, effective_from ausente →
NULL, official_status NULL, verificación SHA-256, cero rule_version)

### M4.2 Hash mismatch (3 tests): PASS
(fragmento rechazado, UNDETERMINED, provider None → UNDETERMINED)

### Negativos de frontera legal — obligatorios (3 tests): PASS
- `"Se permite..."` raw → NUNCA PERMITED (UNDETERMINED).
- jurisdiction del documento → NUNCA scope VERIFIED (REVIEW_REQUIRED).
- EvidencePacket sin revisar → NUNCA regla consumible por el resolver
  (0 filas legal_rule_version, UNDETERMINED).

### Gate de revisión humana (3 tests): PASS
- Regla que cita fragmento REVIEW_REQUIRED → inelegible
  (EVIDENCE_NOT_PUBLISHABLE), UNDETERMINED.
- Canal humano (nuevo fragmento VERIFIED + scope VERIFIED + regla
  human-authored) → PROHIBITED con evidencia trazable.
- packet_id preservado en la identidad del fragmento.

### Negativos end-to-end (2 tests): PASS
(schema 3.0 antes de ingest; fallo de provider → ingesta rechazada limpia)

**Total: 35 tests — ALL PASSING, hermetic.**

## 4. Hashes anclados

| Campo | Valor |
|-------|-------|
| VENDOR_SCHEMA_SHA256 | `eea5fd0914a3242208c21f5b6c2f62ab6798f8ed908237b6d358de95e9cab665` |

Los hashes del corpus externo (`G:\_Proyectos\mcp\m4-alraso\...`) quedaron
como artefacto de ejecución del 2026-09-09; los tests actuales no dependen de
ese corpus — la verificación SHA-256 se ejerce sobre contenido sintético cuyo
hash se calcula en runtime.

## 5. Limitaciones conocidas

- El scope candidato registra la jurisdicción *declarada* por el packet; la
  revisión humana decide el ámbito jurídico real.
- No hay canal de revisión implementado (las transiciones VERIFIED las
  escribe un ingest human-gated futuro); el test lo simula con escritura
  directa.

## 6. Archivos nuevos / modificados

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `alraso/official_sources_v2.py` | NEW | Validador estricto EvidencePacket v2.1, schema vendored |
| `alraso/ingest/evidence_packet.py` | NEW | Adapter evidence-only packet → BitemporalStore |
| `tests/test_evidence_packet_v2.py` | NEW | 35 tests herméticos |
| `tests/test_m2b_official_boundary.py` | MOD | stanza whitelist de esta rama |
