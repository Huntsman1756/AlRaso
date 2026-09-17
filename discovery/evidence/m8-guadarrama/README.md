# M8 — PN Sierra de Guadarrama (ámbito CAM) — paquete de evidencia

**Estado:** `READY_FOR_HUMAN_REVIEW` — candidato `REVIEW_REQUIRED`, no publicable.
**Milestone:** M8 Madrid personal-utility vertical (`docs/validation/m8/M8-PREREG.md`)

## Contenido

| Archivo | Contenido |
|---|---|
| `candidate_fixture.json` | Corpus candidato ingerible (`alraso-corpus-candidate-v1`) — 2 reglas propuestas, todo `REVIEW_REQUIRED` |
| `review_case.json` | `RC-M8-ES-MD-GUADARRAMA-VIVAC` — preceptos verbatim, vigencia, cuestiones abiertas para el revisor |
| `prug-d18-2020-art48-extract.txt` | Extracto verbatim del régimen de pernocta/vivac (arts. 38.1.o, 48.a, 92.3.e, nota de nulidad, D 26/2025 art. 4) |
| `IDEM_MA_PNSG_ZON_VIVAC_ANUA.geojson` | Capa oficial de zonas de vivac Anexo III (5 polígonos, EPSG:4326, CC-BY 4.0) |
| `IDEM_MA_PN_GUADARRAMA_CM.geojson` | Límite PN-CM + ZPP-CM (EPSG:4326) |
| `IDEM_MA_PNSG_ZONIFICACION.geojson` | Zonificación PRUG (165 features — contexto; 14 Zona de Reserva) |
| `IDEM_MA_ENP.geojson`, `IDEM_MA_PR_*.geojson`, `IDEM_MA_RED_NATURA_*.geojson` | Contexto territorial CAM (ENPs, PRs, RN2000) |

## Fuentes

- **Decreto 18/2020** (PRUG-PNSG ámbito CAM), BOCM núm. 51 ext., 29/02/2020.
  PDF: `https://www.bocm.es/boletin/CM_Orden_BOCM/2020/02/29/BOCM-20200229-1.PDF`
  sha256 `f34a023e…` (no redistribuido, 49 MB). Texto consolidado oficial con
  nulidades: parquenacionalsierraguadarrama.es/legislacion.
- **Decreto 238/2023** (BOCM 222, 18/09/2023) — modifica arts. 29.2/45.2 +
  Anexos X–XII; NO toca art. 48. sha256 `15616e02…`.
- **Decreto 26/2025** (BOCM 121, 22/05/2025) — regla general CAM;
  art. 4: acampada libre prohibida en toda la CAM; deroga D 3/1993.
- **STSJM 1003/2022** (rec. 197/2022, firme 09/02/2023) — nulidad del límite
  de 2.000 m del art. 48.a.2. No re-legislado.
- **IDEM WFS**: `https://idem.comunidad.madrid/geoidem/{Zonas,LugaresProtegidos}/ows`
  — geometría real adquirida 2026-09-17, licencia CC-BY 4.0.

## Propuesta pendiente de decisión humana

- `PERMITTED` condicionado (≤1 noche/zona, ≤10 pax) en `ss-pnsg-vivac-anexo3`
  (5 polígonos oficiales).
- `PROHIBITED` en `ss-pnsg-pn-cm` fuera de zonas Anexo III / entorno inmediato
  de refugios no guardados sin plazas libres.
- **Cuestiones abiertas** (ver `review_case.json` →
  `contrary_or_ambiguous_evidence`): alcance de la nulidad del límite 2000 m,
  interpretación del art. 92.3.e en la ZPP, laguna definicional del vivac puro
  frente a la prohibición de acampada libre, régimen administrativo Peñalara,
  huecos ZPP no representables en el modelo de anillos.
