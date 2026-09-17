# M10.2-C — Version-signal evidence (BOE/DOGC)

Live-verified mechanical document-version signals, captured `es_local`
2026-09-18 by `tooling/m102_version_probe.py probe`. Each directory
holds `evidence.json` (request, endpoint, retrieved_at, response
sha256, http_status, runner_network, payload) + `claim.json` (the
resolved `VersionClaim`).

`RESOLVED` means ONLY "the document version was mechanically resolved"
— it asserts nothing about legal validity, applicability, or
permissibility, and creates no `legal_rule_version`.

## Signals

| Source | Endpoint(s) | Mechanical signal |
|---|---|---|
| BOE | `GET /datosabiertos/api/legislacion-consolidada/id/{id}/metadatos` (Accept: application/json) | `identificador`, `fecha_actualizacion`, `fecha_vigencia`, `vigencia_agotada`, `estado_consolidacion`, `url_eli` |
| DOGC | Socrata `n6hn-rmy7` row + `GET <eli>/dof/cat/xml` (redirect) | `vig_ncia_de_la_norma`, ELI path, `idNumber`/`idVersion` in effective URL |

Note: BOE `/id/{id}` bare endpoint is XML-only — returns 400 under
`Accept: application/json`; the resolver targets `/metadatos`.
DOGC `idVersion` is NOT inside the AKN body — it arrives in the
redirect target URL (`portaldogc ...AkomaNtoso?idNumber=&idVersion=`),
so the transport must expose `effective_url`.

## Results

- `boe/BOE-A-2007-21490` — Ley 42/2007 PNB: RESOLVED, effective_from
  2007-12-15 (structured `fecha_vigencia`), consolidacion Finalizado.
- `boe/BOE-A-1985-5392` — Ley 7/1985 LBRL: RESOLVED, effective_from
  1985-04-23, consolidacion Finalizado.
- `dogc/es-ct-d-2003-02-04-39` — DECRET 39/2003 PRUG Aigüestortes:
  RESOLVED, vigència Vigent, idVersion 318062.
- `dogc/es-ct-d-2015-10-06-223` — DECRET 223/2015: RESOLVED, vigència
  Vigent, idVersion 1793598.

`effective_from` is populated ONLY for BOE (structured `fecha_vigencia`
field). DOGC exposes no structured effective-date field — it stays
`null`; the version signal is `idVersion` + `vigència` only.

Reproduce:

    python tooling/m102_version_probe.py gate \
        --evidence-root discovery/evidence/m10.2-version

    VERSION_GATE=PASS
