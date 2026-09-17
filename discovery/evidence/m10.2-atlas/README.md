# M10.2-A National Source Atlas — evidence set

Generated evidence for the M10.2-A exit gate: **20/20 jurisdiction domains**
in `{PROVEN, BLOCKED_WITH_EVIDENCE}`, 0 `UNPROBED`.

Scope: 17 autonomous communities + Ceuta + Melilla + State (ES).
Evidence-only: no legal ingestion, no publication, `NEW_RULES=0`.

## Layout

- `<domain>/domain.json` — declared record: surfaces, discovery/fetch
  mechanism, doc-id scheme, formats, change detection, license notes.
- `<domain>/probes.json` — live probe log written by
  `tooling/m102_atlas_probe.py probe` (runner `es_local`, 2026-09-18).
- `<domain>/<probe_id>.body` — stored response body for offline replay,
  unless the record is digest-only (large PDFs are not redistributed;
  sha256 + byte count preserved).
- `source-atlas.json` — assembled by `m102_atlas_probe.py build`.
- `matrices.json` — family clustering, reachability/fallback and
  change-detection matrices derived by `m102_atlas_probe.py matrices`.

## Reproduce

```bash
# offline digest verification (no network)
python tooling/m102_atlas_probe.py verify \
  --evidence-dir discovery/evidence/m10.2-atlas/<domain>

# rebuild + executable exit gate
python tooling/m102_atlas_probe.py build \
  --evidence-root discovery/evidence/m10.2-atlas
python tooling/m102_atlas_probe.py gate \
  --atlas discovery/evidence/m10.2-atlas/source-atlas.json
python tooling/m102_atlas_probe.py matrices \
  --atlas discovery/evidence/m10.2-atlas/source-atlas.json
```

## Notable observations

- **ES-MC (BORM)**: Radware WAF returns a CAPTCHA interstitial (HTTP 200 +
  captcha HTML) to headless clients. Recorded as `CONTENT_MARKER_MISMATCH`
  with stored bodies — never `SUCCESS`. A plain browser `User-Agent`
  retrieves real content; the open-data index on `transparencia.carm.es`
  is a WAF-free fallback.
- **ES-CE (BOCCE)**: issue-level acquisition proven (jDownloads PDFs);
  no document-level addressing exists. `PROVEN` at surface scope with the
  limitation documented in the record.
- **ES-AS (BOPA)**: 55.8 MB PDF recorded digest-only; sha256
  `a1e374e5dcc12c5d…` is byte-identical to the M2A provenance lock.
- **ES (BOE)**: `datosabiertos` API requires `Accept: application/json`.
  Consolidated-corpus absence never proves a CCAA instrument does not
  exist.
- **ES-CT (DOGC)**: `portaljuridic.gencat.cat` needs legacy TLS
  (SECLEVEL=1); consolidated surface verified, `RESOLVED` logic is
  M10.2-C scope.
- **ES-NC (BON)**: soft-404 confirmed — bogus friendly URLs return
  HTTP 200 empty shell; content markers are mandatory.

## Candidate profiles

`pipeline/sources/atlas/*.profile.json` — one per observed family shape
(api, doc_url_template, rss, open-data index + WAF). All marked
CANDIDATE: their `discovery.provider` interpreters are not yet
implemented; they document required shapes, not runnable config.

## OSS references (no code copied)

- `sesaba23/ope-boe-scraping` — AGPL-3.0, REFERENCE_ONLY (BOE error
  taxonomy, confirmed-absence handling, retry/backoff patterns).
- `christianpasinrey/escanerpublico-backend` — MIT-intended (no LICENSE
  file in repo; intent declared in README/metadata). ADAPT/COPY_PATTERN
  candidate for M10.2-B/C only (`content_hash` idempotency, BOE
  `fecha_vigencia`/`fecha_actualizacion`/`estado_consolidacion`/`url_eli`).
