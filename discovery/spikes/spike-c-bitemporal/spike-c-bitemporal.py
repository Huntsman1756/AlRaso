"""SPIKE C — Bitemporal rule storage (valid time vs system time), corrected pattern.

Scenario (Ordesa-shaped, synthetic values for the spike):
  Our DB recorded R1 = "vivac PERMITTED" effective 2020-01-01..OPEN, recorded 2020-06-01.
  A 2022 decree prohibited it. We DISCOVERED the decree only in 2027 (late discovery).
  Discovery is append-only: we add (a) a retrospective closure of R1 (effective_to
  2022-02-08, recorded_at 2027) and (b) R2 = PROHIBITED effective 2022-02-09..OPEN,
  recorded_at 2027.

Questions the two axes must answer:
  1. What did our system answer for 2023-06-15 given knowledge as of 2023-06-15?
     -> PERMITTED (hindsight-wrong, correct-as-known-then).
  2. What do we answer today for that same 2023 activity date?
     -> PROHIBITED (late-discovered decree).
  3. What would a vigilant system (recorded the decree in 2022) have answered?
     -> PROHIBITED.
  4. Retro-audit: which past determinations must be flagged STALE?
     -> all answered PERMITTED for activity dates >= 2022-02-09.
"""
import sqlite3

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE legal_rule_version (
  id INTEGER PRIMARY KEY,
  rule_id TEXT NOT NULL,
  activity TEXT NOT NULL,
  effect TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,          -- valid time end (open = NULL until discovered otherwise)
  recorded_at TEXT NOT NULL,  -- system time: when this row became visible to the system
  evidence TEXT NOT NULL
);
INSERT INTO legal_rule_version VALUES
 (1,'vivac_sector_ordesa','VIVAC_AL_RASO','PERMITTED','2020-01-01',NULL,'2020-06-01','RD 409/1995 anexo I D.a');
""")

def resolve(activity_date, knowledge_date):
    row = db.execute("""
      SELECT effect, evidence, recorded_at, effective_from
      FROM legal_rule_version
      WHERE recorded_at <= ?                       -- SYSTEM TIME filter
        AND effective_from <= ?                    -- VALID TIME start
        AND (effective_to IS NULL OR ? <= effective_to)
      ORDER BY effective_from DESC, recorded_at DESC
      LIMIT 1
    """, (knowledge_date, activity_date, activity_date)).fetchone()
    if not row:
        return ("UNDETERMINED", "no version visible at that knowledge date", None)
    return (row[0], f"effective {row[3]}.., recorded {row[2]}", row[1])

print("== 1. resolve(activity_date=2023-06-15, knowledge_date=2023-06-15)  [before discovery]")
print("  ->", resolve("2023-06-15", "2023-06-15"))

print("== late discovery in 2027: append-only correction")
db.executescript("""
INSERT INTO legal_rule_version VALUES
 (2,'vivac_sector_ordesa','VIVAC_AL_RASO','PERMITTED','2020-01-01','2022-02-08','2027-05-10',
    'RD 409/1995 anexo I D.a (retrospective closure)'),
 (3,'vivac_sector_ordesa','VIVAC_AL_RASO','PROHIBITED','2022-02-09',NULL,'2027-05-10',
    'D 16/2022 BOA 8-2-2022');
""")

print("== 2. resolve(activity_date=2023-06-15, knowledge_date=2028-01-01)  [after discovery]")
print("  ->", resolve("2023-06-15", "2028-01-01"))
answered_then = resolve("2023-06-15", "2023-06-15")[0]

print("== 3. vigilant counterfactual: decree recorded 2022-02-20, knowledge 2023-06-15")
db.executescript("""
INSERT INTO legal_rule_version VALUES
 (4,'vivac_sector_ordesa','VIVAC_AL_RASO','PERMITTED','2020-01-01','2022-02-08','2022-02-20',
    'RD 409/1995 anexo I D.a (vigilant closure)'),
 (5,'vivac_sector_ordesa','VIVAC_AL_RASO','PROHIBITED','2022-02-09',NULL,'2022-02-20',
    'D 16/2022 BOA 8-2-2022 (vigilant)');
""")
print("  ->", resolve("2023-06-15", "2023-06-15"))

print("== 4. retro-audit: replay 2023 determination under both knowledge dates")
print("  answered then:", answered_then,
      "| in force (today's knowledge):", resolve("2023-06-15", "2028-01-01")[0],
      "-> flag STALE + re-review")
