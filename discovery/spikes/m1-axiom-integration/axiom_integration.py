import os, sys
sys.path.insert(0, "/repo")
from alraso.bitemporal import BitemporalStore
from alraso.ingest.ordesa import load_ordesa
from alraso.engine_axiom import AxiomCliAdapter, generate_rulespec
import hashlib

BIN = os.environ["ALRASO_AXIOM_BIN"]
ROOT = "/work/rs_root/rulespec-es"  # Axiom requires root named rulespec-<country>
os.makedirs(ROOT, exist_ok=True)

store = BitemporalStore.connect(":memory:")
load_ordesa(store)

adapter = AxiomCliAdapter(BIN, ROOT, ROOT + "/cache")
SCOPE = "ss-ordesa-sector-ordesa"
ok = True
seen_hashes = {}
for act_date, label, want in [("2021-07-15", "pre-override", "PERMITTED"),
                              ("2023-06-15", "post-override", "PROHIBITED")]:
    sel = store.select("VIVAC_AL_RASO", SCOPE, act_date, "2023-06-15")
    mid, yaml_text, _ = generate_rulespec(sel.covering)
    ks = hashlib.sha256(yaml_text.encode()).hexdigest()[:12]
    res = adapter.evaluate(sel.covering, {"activity_name": "VIVAC_AL_RASO"})
    eff = res.judgments[0].effect
    seen_hashes[ks] = eff
    good = eff == want
    ok = ok and good
    print(f"{label:13} activity_date={act_date} knowledge=2023-06-15 -> {eff} (want {want}) ks={ks} [{'OK' if good else 'MISMATCH'}]")

artifacts = sorted(os.listdir(ROOT + "/cache"))
print("cached_compiled_artifacts:", len(artifacts), artifacts)
print("distinct knowledge-states:", len(seen_hashes), "->", list(seen_hashes.values()))
print("AXIOM_INTEGRATION:", "PASS" if (ok and len(seen_hashes) == 2 and len(artifacts) == 2) else "FAIL")
