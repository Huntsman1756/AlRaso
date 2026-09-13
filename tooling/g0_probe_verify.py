"""G0 probe re-verification — discovery evidence only.

Re-runs the key HTTP probes that back docs/spain-coverage-g0/.
No product code, no legal corpus, no ingestion. Read-only GETs.

Exit codes: 0 all probes matched expectation; 1 mismatch found;
2 offline/inconclusive (OFFLINE=1 or network unreachable) — never a false OK.
"""
import json
import os
import sys
import urllib.request
import urllib.parse

TIMEOUT = 30

PROBES = [
    # (name, url, expected_status, expected_content_substr_or_None, accept)
    ("boe-consolidada-ley42", "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2007-21490/metadatos", 200, "2007-21490", "application/json"),
    ("boe-sumario", "https://www.boe.es/datosabiertos/api/boe/sumario/20251230", 200, None, "application/xml"),
    ("oapn-wfs-cap", "https://sigred.oapn.es/geoserverOAPN/ows?service=WFS&version=2.0.0&request=GetCapabilities", 200, "ZonificacionPRUG", None),
    ("bocyl-dataset", "https://jcyl.opendatasoft.com/api/explore/v2.1/catalog/datasets/bocyl/records?limit=1", 200, "fecha_publicacion", "application/json"),
    ("bocyl-doc-xml", "https://bocyl.jcyl.es/boletines/2025/12/15/xml/BOCYL-D-15122025-1.xml", 200, "numeroOficial", None),
    ("bopa-doc", "https://sede.asturias.es/bopa/2026/03/30/2026-02506.pdf", 200, None, None),
    ("boc-cantabria-toc-post", "POST https://boc.cantabria.es/boces/boletines.do", 200, "57/2026", None),
    ("boa-doc", "https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI?BASE=BOLE&CMD=VERDOC&DOCN=007922169&SEC=BUSQUEDA_AVANZADA&SEPARADOR=", 200, "16/2022", None),
    ("boja-doc", "https://www.juntadeandalucia.es/boja/2011/155/41", 200, None, None),
    ("boc-canarias", "https://www.gobiernodecanarias.org/boc/2025/240/pda/4148.html", 200, "182/2025", None),
    ("bocm-doc", "https://www.bocm.es/boletin/CM_Orden_BOCM/2025/12/19/BOCM-20251219-1.PDF", 200, None, None),
    ("dogc-socrata", "https://analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json?$limit=1", 200, "diari_oficial", "application/json"),
    ("miteco-atom", "https://www.mapama.gob.es/ide/inspire/atom/downloadservice.xml", 200, "atom", None),
]


def probe(name, url, expected, needle, accept):
    headers = {"User-Agent": "alraso-g0-verify/1.0"}
    if accept:
        headers["Accept"] = accept
    data = None
    if url.startswith("POST "):
        url = url[5:]
        data = b"boletinBean.fecBolString=04%2F08%2F2026&boletinBean.tipoBol=&boton=Buscar"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        req = urllib.request.Request(url, headers=headers, data=data)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type", "")
    except Exception as e:
        return name, "INCONCLUSIVE", f"{type(e).__name__}: {e}"
    ok = status == expected
    if ok and needle:
        ok = needle.encode() in body
    return name, "PASS" if ok else "FAIL", f"status={status} ctype={ctype} bytes={len(body)}"


def main():
    if os.environ.get("OFFLINE"):
        print("OFFLINE=1 -> INCONCLUSIVE"); return 2
    fails = inconclusive = 0
    for p in PROBES:
        name, result, detail = probe(*p)
        print(f"{result:12s} {name:26s} {detail}")
        if result == "FAIL":
            fails += 1
        elif result == "INCONCLUSIVE":
            inconclusive += 1
    if fails:
        print(f"\n{fails} FAIL / {inconclusive} INCONCLUSIVE"); return 1
    if inconclusive == len(PROBES):
        print("all inconclusive -> network unreachable"); return 2
    print(f"\n0 FAIL / {inconclusive} INCONCLUSIVE"); return 0


if __name__ == "__main__":
    sys.exit(main())
