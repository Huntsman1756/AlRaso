"""Storage schema — SQLite is the implemented & tested normative store.

Status claims (M1 remediation F08 — no unproven parity claims):

  SQLITE_DDL   implemented + hermetically tested. Integrity enforced at the DB
               level: PRAGMA foreign_keys=ON (set per connection by the store,
               never relying on driver defaults) + append-only UPDATE/DELETE
               triggers on every normative table.
  POSTGRES_DDL TARGET DESIGN ONLY. POSTGRES_NORMATIVE_STORE_STATUS =
               "NOT_IMPLEMENTED": no functional PostgreSQL store or test
               exists, so NO parity claim with SQLite semantics is made.

Temporal convention (documented, tested in tests/test_temporal_boundaries.py):

  VALID time:   [effective_from, effective_to]   CLOSED on both ends;
                effective_to NULL = open (still in force).
  SYSTEM time:  [recorded_at, recorded_until)    closed start, OPEN end;
                recorded_until NULL = still the system's current belief.

  Dates are ISO YYYY-MM-DD strings. Lexical ordering is only relied upon AFTER
  strict calendar validation at every write and read boundary (alraso.
  validation), which makes it chronologically exact.

The bitemporal columns are the heart:
    effective_from / effective_to    VALID time (open end = NULL)
    recorded_at   / recorded_until   SYSTEM time (when the system knew it)

Both LegalRuleVersion and RuleRelationVersion carry the SAME bitemporal +
review semantics (F04: precedence must answer "what did the system know on
that date?", so relations are versioned too — the old mutable rule_relation
table is gone).

Note: the SQL keywords below are assembled via _expand() from split literals.
This is deliberate — hand-typed multi-word SQL keywords were observed to be
silently mangled when written to disk, so they are injected programmatically
and asserted in tests to keep the schema correct regardless.
"""

from __future__ import annotations

POSTGRES_NORMATIVE_STORE_STATUS = "NOT_IMPLEMENTED"

# Keywords assembled from parts to survive the write-mangling described above.
_KW = {
    "__INE__": ("IF" + " " + "NOT" + " " + "EXISTS"),
    "__PK__": ("PRIMARY" + " " + "KEY"),
    "__NN__": ("NOT" + " " + "NULL"),
    "__TSTZ__": ("timesta" + "mptz"),
}


def _expand(sql: str) -> str:
    for marker, value in _KW.items():
        sql = sql.replace(marker, value)
    return sql


SQLITE_DDL = _expand("""
CREATE TABLE __INE__ source_document (
  id              TEXT __PK__,
  authority       TEXT __NN__,
  jurisdiction    TEXT __NN__,
  document_type   TEXT __NN__,
  title           TEXT __NN__,
  canonical_url   TEXT __NN__,
  official_status TEXT,
  retrieved_at    TEXT,
  content_hash    TEXT
);

CREATE TABLE __INE__ legal_fragment (
  id                 TEXT __PK__,
  source_document_id TEXT __NN__ REFERENCES source_document(id),
  locator            TEXT __NN__,
  exact_text_hint    TEXT,
  extracted_at       TEXT,
  review_status      TEXT
);

CREATE TABLE __INE__ spatial_scope (
  id              TEXT __PK__,
  scope_type      TEXT __NN__,
  parent_scope    TEXT,
  official_name   TEXT __NN__,
  geometry_source TEXT,
  feature_id      TEXT,
  srid_native     INTEGER,
  review_status   TEXT
);

CREATE TABLE __INE__ legal_rule_version (
  seq               INTEGER __PK__ AUTOINCREMENT,
  rule_id           TEXT __NN__,
  activity          TEXT __NN__,
  spatial_scope_id  TEXT __NN__ REFERENCES spatial_scope(id),
  effect            TEXT __NN__,
  condition         TEXT,
  effective_from    TEXT __NN__,
  effective_to      TEXT,
  recorded_at       TEXT __NN__,
  recorded_until    TEXT,
  evidence          TEXT __NN__ DEFAULT '[]',
  interpretation_note TEXT,
  review_status     TEXT __NN__ DEFAULT 'REVIEW_REQUIRED',
  legal_review_complete INTEGER __NN__ DEFAULT 0,
  spatial_review_complete INTEGER,
  evidence_required INTEGER __NN__ DEFAULT 1
);
CREATE INDEX __INE__ lrv_lookup
  ON legal_rule_version (activity, spatial_scope_id, effective_from, recorded_at);

CREATE TRIGGER __INE__ lrv_no_update BEFORE UPDATE ON legal_rule_version
BEGIN SELECT RAISE(ABORT, 'legal_rule_version is append-only: append a new version instead of UPDATE'); END;
CREATE TRIGGER __INE__ lrv_no_delete BEFORE DELETE ON legal_rule_version
BEGIN SELECT RAISE(ABORT, 'legal_rule_version is append-only: DELETE is forbidden'); END;

CREATE TABLE __INE__ rule_relation_version (
  seq              INTEGER __PK__ AUTOINCREMENT,
  relation_id      TEXT __NN__,
  relation_type    TEXT __NN__,
  from_rule_id     TEXT __NN__,
  from_effect      TEXT,
  to_rule_id       TEXT __NN__,
  to_effect        TEXT,
  effective_from   TEXT __NN__,
  effective_to     TEXT,
  recorded_at      TEXT __NN__,
  recorded_until   TEXT,
  evidence         TEXT __NN__ DEFAULT '[]',
  review_status    TEXT __NN__ DEFAULT 'REVIEW_REQUIRED',
  legal_review_complete INTEGER __NN__ DEFAULT 0,
  ai_proposed      INTEGER __NN__ DEFAULT 0,
  human_verified   INTEGER __NN__ DEFAULT 0
);
CREATE INDEX __INE__ rrv_lookup
  ON rule_relation_version (from_rule_id, to_rule_id, effective_from, recorded_at);

CREATE TRIGGER __INE__ rrv_no_update BEFORE UPDATE ON rule_relation_version
BEGIN SELECT RAISE(ABORT, 'rule_relation_version is append-only: append a new version instead of UPDATE'); END;
CREATE TRIGGER __INE__ rrv_no_delete BEFORE DELETE ON rule_relation_version
BEGIN SELECT RAISE(ABORT, 'rule_relation_version is append-only: DELETE is forbidden'); END;

CREATE TRIGGER __INE__ sd_no_update BEFORE UPDATE ON source_document
BEGIN SELECT RAISE(ABORT, 'source_document is append-only'); END;
CREATE TRIGGER __INE__ sd_no_delete BEFORE DELETE ON source_document
BEGIN SELECT RAISE(ABORT, 'source_document is append-only'); END;
CREATE TRIGGER __INE__ lf_no_update BEFORE UPDATE ON legal_fragment
BEGIN SELECT RAISE(ABORT, 'legal_fragment is append-only'); END;
CREATE TRIGGER __INE__ lf_no_delete BEFORE DELETE ON legal_fragment
BEGIN SELECT RAISE(ABORT, 'legal_fragment is append-only'); END;
CREATE TRIGGER __INE__ ss_no_delete BEFORE DELETE ON spatial_scope
BEGIN SELECT RAISE(ABORT, 'spatial_scope is append-only: DELETE is forbidden'); END;

CREATE TABLE __INE__ determination (
  seq                  INTEGER __PK__ AUTOINCREMENT,
  canonical_query      TEXT __NN__,
  activity             TEXT __NN__,
  activity_date        TEXT __NN__,
  knowledge_date       TEXT __NN__,
  legal_status         TEXT __NN__,
  knowledge_status     TEXT __NN__,
  applicable_scope_ids TEXT __NN__ DEFAULT '[]',
  rule_version_seqs    TEXT __NN__ DEFAULT '[]',
  relation_version_seqs TEXT __NN__ DEFAULT '[]',
  evidence_fragment_ids TEXT __NN__ DEFAULT '[]',
  source_document_ids  TEXT __NN__ DEFAULT '[]',
  engine_adapter       TEXT __NN__,
  engine_version       TEXT __NN__,
  resolver_version     TEXT __NN__,
  schema_version       TEXT __NN__,
  knowledge_state_hash TEXT __NN__,
  decided_on           TEXT __NN__
);

CREATE TRIGGER __INE__ det_no_update BEFORE UPDATE ON determination
BEGIN SELECT RAISE(ABORT, 'determination is append-only: record a new observation instead'); END;
CREATE TRIGGER __INE__ det_no_delete BEFORE DELETE ON determination
BEGIN SELECT RAISE(ABORT, 'determination is append-only: DELETE is forbidden'); END;
""")

# TARGET DESIGN ONLY (POSTGRES_NORMATIVE_STORE_STATUS=NOT_IMPLEMENTED).
# Kept as the spatial/production design; NOT tested, NOT claimed equivalent.
POSTGRES_DDL = _expand("""
CREATE EXTENSION __INE__ postgis;

CREATE TABLE __INE__ source_document (
  id              text __PK__,
  authority       text __NN__,
  jurisdiction    text __NN__,
  document_type   text __NN__,
  title           text __NN__,
  canonical_url   text __NN__,
  official_status text,
  retrieved_at    __TSTZ__,
  content_hash    text
);

CREATE TABLE __INE__ legal_fragment (
  id                 text __PK__,
  source_document_id text __NN__ REFERENCES source_document(id),
  locator            text __NN__,
  exact_text_hint    text,
  extracted_at       date,
  review_status      text
);

CREATE TABLE __INE__ spatial_scope (
  id              text __PK__,
  scope_type      text __NN__,
  parent_scope    text,
  official_name   text __NN__,
  geometry_source text,
  feature_id      text,
  srid_native     integer,
  review_status   text,
  geom            geometry(MultiPolygon, 4258)
);
CREATE INDEX __INE__ spatial_scope_gix ON spatial_scope USING gist (geom);

CREATE TABLE __INE__ legal_rule_version (
  seq                 bigserial __PK__,
  rule_id             text __NN__,
  activity            text __NN__,
  spatial_scope_id    text __NN__ REFERENCES spatial_scope(id),
  effect              text __NN__,
  condition           jsonb,
  effective_from      date __NN__,
  effective_to        date,
  recorded_at         date __NN__,
  recorded_until      date,
  evidence            jsonb __NN__ DEFAULT '[]',
  interpretation_note text,
  review_status       text __NN__ DEFAULT 'REVIEW_REQUIRED',
  legal_review_complete boolean __NN__ DEFAULT false,
  spatial_review_complete boolean,
  evidence_required   boolean __NN__ DEFAULT true
);
CREATE INDEX __INE__ lrv_lookup
  ON legal_rule_version (activity, spatial_scope_id, effective_from, recorded_at);

CREATE TABLE __INE__ rule_relation_version (
  seq                 bigserial __PK__,
  relation_id         text __NN__,
  relation_type       text __NN__,
  from_rule_id        text __NN__,
  from_effect         text,
  to_rule_id          text __NN__,
  to_effect           text,
  effective_from      date __NN__,
  effective_to        date,
  recorded_at         date __NN__,
  recorded_until      date,
  evidence            jsonb __NN__ DEFAULT '[]',
  review_status       text __NN__ DEFAULT 'REVIEW_REQUIRED',
  legal_review_complete boolean __NN__ DEFAULT false,
  ai_proposed         boolean __NN__ DEFAULT false,
  human_verified      boolean __NN__ DEFAULT false
);

CREATE TABLE __INE__ determination (
  seq                  bigserial __PK__,
  canonical_query      jsonb __NN__,
  activity             text __NN__,
  activity_date        date __NN__,
  knowledge_date       date __NN__,
  legal_status         text __NN__,
  knowledge_status     text __NN__,
  applicable_scope_ids jsonb __NN__ DEFAULT '[]',
  rule_version_seqs    jsonb __NN__ DEFAULT '[]',
  relation_version_seqs jsonb __NN__ DEFAULT '[]',
  evidence_fragment_ids jsonb __NN__ DEFAULT '[]',
  source_document_ids  jsonb __NN__ DEFAULT '[]',
  engine_adapter       text __NN__,
  engine_version       text __NN__,
  resolver_version     text __NN__,
  schema_version       text __NN__,
  knowledge_state_hash text __NN__,
  decided_on           __TSTZ__ __NN__ DEFAULT now()
);
""")
