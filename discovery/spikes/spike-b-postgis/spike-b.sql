-- SPIKE B: official OAPN geometry -> PostGIS -> scopes for a point
\set ON_ERROR_STOP on
CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS source_document CASCADE;
DROP TABLE IF EXISTS spatial_scope CASCADE;

-- Immutable source registry (Spike B minimal version of SourceDocument)
CREATE TABLE source_document (
  id              uuid PRIMARY KEY,
  authority       text NOT NULL,
  jurisdiction    text NOT NULL,
  document_type   text NOT NULL,
  title           text NOT NULL,
  canonical_url   text NOT NULL,
  retrieved_at    timestamptz NOT NULL,
  content_hash    text NOT NULL
);

CREATE TABLE spatial_scope (
  id                  bigserial PRIMARY KEY,
  source_document_id  uuid NOT NULL REFERENCES source_document(id),
  scope_type          text NOT NULL,          -- e.g. NATIONAL_PARK / SPECIAL_PROTECTION
  official_name       text NOT NULL,
  declaracion         text,                    -- declarative law (official metadata)
  feature_id          text NOT NULL,           -- WFS layer + feature identity
  geom                geometry(MultiPolygon, 4258) NOT NULL
);
CREATE INDEX spatial_scope_gix ON spatial_scope USING gist (geom);

DROP TABLE IF EXISTS spatial_scope_stage;
CREATE TABLE spatial_scope_stage (
  source_document_id  uuid,
  scope_type          text,
  official_name       text,
  declaracion         text,
  feature_id          text,
  geom_json           text
);

\set gsrc 'file:"/work/oapn-limites.geojson"'
INSERT INTO source_document (id, authority, jurisdiction, document_type, title, canonical_url, retrieved_at, content_hash)
VALUES ('11111111-1111-1111-1111-111111111111',
        'OAPN / MITECO', 'ES', 'OFFICIAL_GIS_LAYER',
        'Límites de Parques Nacionales (Red de Parques Nacionales)',
        'https://sigred.oapn.es/geoserverOAPN/LimitesParquesNacionalesZPP/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=LimitesParquesNacionalesZPP%3Aview_red_oapn_limite_pn&outputFormat=application%2Fjson',
        now()::timestamptz,
        :'picos_hash');

\copy spatial_scope_stage (source_document_id, scope_type, official_name, declaracion, feature_id, geom_json) FROM '/work/scopes.csv' WITH (FORMAT csv)

INSERT INTO spatial_scope (source_document_id, scope_type, official_name, declaracion, feature_id, geom)
SELECT source_document_id, scope_type, official_name, declaracion, feature_id,
       ST_Multi(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(geom_json), 25830), 4258))
FROM spatial_scope_stage
WHERE geom_json LIKE '{"type":"MultiPolygon"%';;

-- Point-in-polygon resolution with provenance
WITH p AS (
  SELECT ST_SetSRID(ST_MakePoint(-4.8444, 43.1961), 4258) AS picos_fuente_de,
         ST_SetSRID(ST_MakePoint(-3.9576, 40.8483), 4258) AS guadarrama_penalara,
         ST_SetSRID(ST_MakePoint(-5.8494, 43.3619), 4258) AS oviedo_outside
)
SELECT 'fuente_de_picos' AS probe, s.scope_type, s.official_name, s.declaracion, s.feature_id, d.canonical_url, d.content_hash
FROM p, spatial_scope s JOIN source_document d ON d.id = s.source_document_id
WHERE ST_Intersects(s.geom, p.picos_fuente_de)
UNION ALL
SELECT 'penalara_guadarrama', s.scope_type, s.official_name, s.declaracion, s.feature_id, d.canonical_url, d.content_hash
FROM p, spatial_scope s JOIN source_document d ON d.id = s.source_document_id
WHERE ST_Intersects(s.geom, p.guadarrama_penalara)
UNION ALL
SELECT 'oviedo_outside', s.scope_type, s.official_name, s.declaracion, s.feature_id, d.canonical_url, d.content_hash
FROM p, spatial_scope s JOIN source_document d ON d.id = s.source_document_id
WHERE ST_Intersects(s.geom, p.oviedo_outside)
ORDER BY 1, 2;
