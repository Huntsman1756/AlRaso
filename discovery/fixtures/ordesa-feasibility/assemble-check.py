"""ORDESA_FEASIBILITY_ACCEPTANCE_FIXTURE — assembly check (disposable, not product).

Loads discovery/fixtures/ordesa-feasibility/fixture.json and verifies that the
F2 decisions can assemble into the Milestone 1 resolver contract:
  - bitemporal selection (valid time x system time) over legal_rule_versions
  - RuleRelation OVERRIDES not needed for basic cases (versioning suffices) but
    present as evidence graph
  - closed activity vocabulary (single Text input)
  - expected answers: 2021 -> PERMITTED, 2023 -> PROHIBITED, replay/STALE cases
"""
import json
import sqlite3
import sys
from pathlib import Path

FIX = Path(__file__).with_name("fixture.json")
data = json.loads(FIX.read_text(encoding="utf-8"))

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE legal_rule_version (
  id INTEGER PRIMARY KEY,
  rule_id TEXT NOT NULL,
  activity TEXT NOT NULL,
  spatial_scope_id TEXT NOT NULL,
  effect TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  recorded_at TEXT NOT NULL,
  evidence TEXT NOT NULL
);
""")
ins = "INSERT INTO legal_rule_version (rule_id,activity,spatial_scope_id,effect,effective_from,effective_to,recorded_at,evidence) VALUES (?,?,?,?,?,?,?,?)"
for i, v in enumerate(data["legal_rule_versions"], start=1):
    db.execute(ins, (v["rule_id"], v["activity"], v["spatial_scope_id"], v["effect"],
                     v["effective_from"], v["effective_to"], v["recorded_at"], ",".join(v["evidence"])))

ACTIVITY_VOCAB = {"VIVAC_AL_RASO", "FUNDA_VIVAC", "TIENDA_NOCTURNA", "TARP",
                  "ACAMPADA", "PERNOCTA_REFUGIO", "VEHICULO"}

def resolve(activity_date, knowledge_date, activity, scope):
    if activity not in ACTIVITY_VOCAB:
        return ("UNDETERMINED", "UNKNOWN_ACTIVITY (fail-closed, F2.1A)", None)
    # Bitemporal selection (two phases):
    #  1) SYSTEM TIME: for each (rule_id, effective_from) lineage, keep only the
    #     row with max recorded_at <= knowledge_date (the lineage's description
    #     as known then — a later closure supersedes the earlier open row).
    #  2) VALID TIME: among surviving lineage descriptions, keep those whose
    #     effective range covers activity_date; latest effective_from wins.
    lineages = db.execute("""
      SELECT rule_id, effective_from, effect, evidence, recorded_at, effective_to
      FROM legal_rule_version
      WHERE recorded_at = (
        SELECT MAX(recorded_at) FROM legal_rule_version l2
        WHERE l2.rule_id = legal_rule_version.rule_id
          AND l2.effective_from = legal_rule_version.effective_from
          AND l2.recorded_at <= ?
      )
      AND recorded_at <= ?
    """, (knowledge_date, knowledge_date)).fetchall()
    covering = [
        r for r in lineages
        if r[1] <= activity_date and (r[5] is None or activity_date <= r[5])
    ]
    if not covering:
        if lineages:
            return ("UNDETERMINED", "INCOMPLETE: knowledge ends before activity date (gap)", None)
        return ("UNDETERMINED", "no version visible at that knowledge date", None)
    best = max(covering, key=lambda r: (r[1], r[4]))
    return (best[2], f"effective {best[1]}.., recorded {best[4]}, evidence={best[3]}", best[3])

failures = []
def check(name, got, want_effect):
    ok = got[0] == want_effect
    print(f"  [{'OK' if ok else 'FAIL'}] {name}: {got[0]} (want {want_effect}) :: {got[1]}")
    if not ok:
        failures.append(name)

R = "alraso:es-ar/pn-ordesa/pernocta#vivac-sector-ordesa"
S = "ss-ordesa-sector-ordesa"
A = "VIVAC_AL_RASO"
exp = data["expected"]

print("== basic queries")
for q in exp["basic_queries"]:
    check(f"{q['query']['activity_date']}@{q['query']['knowledge_date']}",
          resolve(q["query"]["activity_date"], q["query"]["knowledge_date"], A, S),
          q["expected_legal_status"])

print("== knowledge replay (vigilante baseline)")
check("vigilante 2023@2023", resolve("2023-06-15", "2023-06-15", A, S), "PROHIBITED")

print("== late discovery: R1 abierta, decreto solo visible desde 2027")
db.execute("DELETE FROM legal_rule_version WHERE recorded_at = '2022-02-20'")
check("2023@2023 (antes de descubrir)", resolve("2023-06-15", "2023-06-15", A, S), "PERMITTED")
db.execute("INSERT INTO legal_rule_version (rule_id,activity,spatial_scope_id,effect,effective_from,effective_to,recorded_at,evidence) VALUES (?,?,?,?,?,?,?,?)",
           (R, A, S, "PROHIBITED", "2022-02-09", None, "2027-05-10", "lf-d16-2022-pernocta"))
check("2023@2028 (tras descubrir)", resolve("2023-06-15", "2028-01-01", A, S), "PROHIBITED")

print("== gap: cierre retroactivo visible sin sucesor")
db.execute("DELETE FROM legal_rule_version WHERE effect = 'PROHIBITED'")
db.execute("INSERT INTO legal_rule_version (rule_id,activity,spatial_scope_id,effect,effective_from,effective_to,recorded_at,evidence) VALUES (?,?,?,?,?,?,?,?)",
           (R, A, S, "PERMITTED", "2020-01-01", "2022-02-08", "2027-05-10", "lf-d16-2022-pernocta (cierre retroactivo)"))
check("2023@2028 (expirada, sin sucesor)", resolve("2023-06-15", "2028-01-01", A, S), "UNDETERMINED")

print("== fail-closed activity (F2.1A)")
check("actividad desconocida", resolve("2023-06-15", "2023-06-15", "CAMPING_LIBRE", S), "UNDETERMINED")

print("== RuleRelation evidence graph")
for rr in data["rule_relations"]:
    print(f"  [OK] {rr['relation_type']}: {rr['from_effect']} -> {rr['to_effect']} (evidence={rr['evidence']}, human_verified={rr['human_verified']})")

if failures:
    print(f"\nRESULT: FAIL ({failures})")
    sys.exit(1)
print("\nRESULT: ASSEMBLY_CHECK_PASS — fixture listo para Milestone 1")
