import csv, hashlib, json, sys, io

fc = json.load(open("/work/oapn-limites.geojson", encoding="utf-8"))
w = csv.writer(sys.stdout, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
doc_id = "11111111-1111-1111-1111-111111111111"
for f in fc["features"]:
    p = f["properties"]
    name = p.get("Nombre") or p.get("nombre") or ""
    dec = p.get("Declaración") or p.get("declaracion") or ""
    fid = f"{name}"
    scope = "SPECIAL_PROTECTION" if "Especial" in name else "NATIONAL_PARK"
    w.writerow([doc_id, scope, name, dec, fid, json.dumps(f["geometry"], separators=(",", ":"))])
