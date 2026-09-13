# G0 — 5 probes empíricos (cadena completa)

Fecha: 2026-09-13. Criterio de selección: **heterogeneidad** (no facilidad).
Cadena exigida por probe: `SPACE_ID → geometría → autoridad → discovery → documento →
versión/vigencia → precepto → provenance → parser → change-detection → publication_readiness=NO`.

Evidencia: `discovery/evidence/spain-coverage-g0/` (+ `m2a-picos/`, `m11c-goriz/` previas).

---

## P1 — Castilla y León / Picos de Europa (control conocido)

```text
SPACE_ID       pn-picos-de-europa (OAPN name; CCAA split: ES12/ES13/ES41)
geometry       OAPN view_red_oapn_limite_pn + GISCO NUTS2 (Δ<0,05 % verificado M2A)
authority      Junta de Castilla y León — Consejería Medio Ambiente (ámbito CyL)
discovery      BOCyL Opendatasoft API: titulo like "Picos de Europa" → 11 hits
document       DECRETO 17/2025 → BOCYL-D-15122025-1 (xml+pdf+html), pub 2025-12-15
version        entrada en vigor 2026-01-04 (20 días; art. 59.4 → 3 años) — verificado en texto
provision      arts. 51-52 verbatim (extract m2a-picos; XML de disposición, anexo 430 pp → PDF)
provenance     XML sha/evidence bocyl-17-2025-head.xml f3837c8f…; pdf sha en m2a lock
parser         BOCyL-XML estructurado (metadatos) + pdftotext (anexo)
change-detect  dataset Opendatasoft diario — STRONG
publication    NO
```

## P2 — Aragón / Ordesa (zonificación compleja)

```text
SPACE_ID       pn-ordesa (OAPN; zonas ENP101_* en WFS Aragón)
geometry       OAPN límite+ZPP+zonificación PRUG (266 features, Normativa="Decreto 49/2015 (BOA 80, 29/04/2015)")
authority      Gobierno de Aragón
discovery      BOA BRSCGI búsqueda TITU-C → DOCN
document       Decreto 16/2022 (modif. PRUG, régimen pernocta) → DOCN=007922169, 200 text/plain
               Decreto 49/2015 (PRUG base) citado por OAPN + fetch vía misma vía
version        vigencia: día siguiente publicación BOA (08/02/2022 → 09/02/2022)
provision      modif. apartado 9.2.1.3 — pernocta Góriz/vivac/acampada Ordesa (extract m11c)
provenance     boa-decreto-16-2022-doc.html sha 3c560f0a…
parser         text/plain→regex/HTML; consolidado aragonés s/API verificada
change-detect  polling BOA — WEAK-MEDIUM
publication    NO
```

## P3 — Cantabria / Picos (geo-block + reachability)

```text
SPACE_ID       pn-picos-de-europa, ámbito es-cb
geometry       OAPN + GISCO ES13 (Δ+0,04 % M2A)
authority      Comunidad Autónoma de Cantabria — Consejo de Gobierno
discovery      POST boletines.do (fecBolString=04/08/2026, boton=Buscar) → TOC html
               → idBlob=46085 → verXmlAction.do → XML DIARIO FULL-TEXT con CVE+emisor
document       Decreto 57/2026 → disposicion numExpediente=2026-6207, CVE-2026-6207,
               BOC núm. 148 (04/08/2026), PDF idAnuBlob (BOC-2026-6207)
version        vigencia 2026-08-24 (20 días; art. 59.4 → 1 año) — verificado M2A
provision      arts. 51-52 idénticos verbatim (diff M2A); anexo flag anexos=1 (PDF)
provenance     boc-cantabria-2026-08-04.xml sha 656bf953… + toc post 258297c0…
parser         XML diario estructurado (disposicion/titulo_text/texto) — parseable
reachability   ES_ONLY — verificado: r.jina.ai (fetch externo) → TimeoutError;
               observatorio-alegaciones documenta el mismo bloqueo en GitHub Actions;
               workaround probado por ellos: fetch local ES + push
change-detect  MEDIUM — XML diario diff, requiere fetcher en red ES
publication    NO
```

## P4 — Cataluña / Aigüestortes (otro formato editorial: Akoma Ntoso)

```text
SPACE_ID       pn-aiguestortes (OAPN; 27 zonas PRUG, Normativa="Decreto 39/2003 (DOGC 3825)")
geometry       OAPN limite+zonificación
authority      Generalitat de Catalunya
discovery      Socrata n6hn-rmy7: titol like %aigüestortes% → DECRET 39/2003, vigència=Vigent
document       ELI portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39/dof/cat/xml
               → 302 → Akoma Ntoso XML (idNumber=309790, idVersion=318062)
version        vigència=Vigent por API; idVersion en ELI
provision      AKN contiene texto completo del Plan — art. 25.4: pernoctación/acampada/bivac
               PROHIBIDO en todo el PN y zona periférica salvo refugios del annex 2
               (detalle parser: texto HTML-entity-escaped dentro de <P>)
provenance     dogc-39-2003-akn.xml sha 96f9a545…
parser         Akoma Ntoso estándar → indigo-akn/akn-profiler como referencia (ADAPT)
change-detect  STRONG — Socrata + vigència + ELI versionado
publication    NO
```

## P5 — Canarias / Teide (insular, PRUG nuevo)

```text
SPACE_ID       pn-teide (OAPN; 49 zonas PRUG)
geometry       OAPN limite+zonificación; insular (Tenerife)
authority      Gobierno de Canarias — Consejería Transición Ecológica
discovery      BOC gobiernodecanarias.org/boc/2025/240/pda/4148.html (anuncio 4148)
document       DECRETO 182/2025, 1-dic — BOC-A-2025-240-4148, pub 03/12/2025;
               PDF firmado sede.gobiernodecanarias.org (58,3 MB)
version        vigor 15 días post-publicación → ~18/12/2025
provision      §6.3.2.7 VIVAC: solo >2.500 msnm, 4 áreas con cupos (Teide 7/15*,
               M.Blanca 20, Pico Viejo 20, Guajara 20), reserva electrónica previa,
               máx 1 noche/área, travesías ≤2 noches en áreas distintas;
               acampada en lista de prohibidas (item l); pernocta vehículo prohibida
provenance     boc-182-2025-vivac-extract.txt; pdf sha256 45df0cd3… (no redistribuido)
parser         pdftotext directo (texto real, no OCR)
change-detect  MEDIUM — IDs estables BOC-A-*, sin feed máquina verificado
publication    NO
```

---

## Síntesis de probes

| Probe | Discovery | Fetch | Formato | Versión | Reachability | Change-detect |
|---|---|---|---|---|---|---|
| P1 CyL | API Opendatasoft | GET XML/PDF | XML+PDF | API | REACHABLE | fuerte |
| P2 Aragón | CGI search | GET text/plain | text/PDF | manual | REACHABLE | débil-media |
| P3 Cantabria | POST form→TOC | XML diario + PDF | XML estructurado | manual | **ES_ONLY** | media |
| P4 Cataluña | API Socrata+ELI | GET AKN | Akoma Ntoso | **API (Vigent)** | REACHABLE | fuerte |
| P5 Canarias | archivo boc/ | GET html+PDF | HTML+PDF firmado | manual | REACHABLE | media |

Conclusiones:

1. **Reachability es parte del modelo** — P3 prueba que `discovery` (¿existe el doc?) puede
   funcionar mientras `fetch` falla por geolocalización: separación Discovery/Fetcher necesaria.
2. **Formato editorial varía por gaceta** — AKN (DOGC), XML estructurado diario (BOC Cantabria,
   BOCyL), text/plain (BOA), PDF-only (BOPA). Parsers por formato, no por gaceta.
3. **`anexos="1"`** — patrón común: XML de disposición sin anexos largos (Cantabria, CyL);
   el precepto operativo puede vivir en el PDF anexo → parser híbrido XML+pdftotext.
4. **OAPN `Normativa` = semilla de discovery** — el campo cita gaceta+decreto por parque
   → el inventory→norm link está parcialmente resuelto por el propio OAPN.
5. `publication_readiness = NO` en los 5 — nada entra a corpus sin revisión humana.
