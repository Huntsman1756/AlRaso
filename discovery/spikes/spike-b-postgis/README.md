# Spike B — PostGIS con geometría oficial real (desechable)

Hipótesis: lat/lon → scopes aplicables con procedencia completa, usando geometrías oficiales.

## Qué hay aquí
- `spike-b.sql` — esquema mínimo `source_document` + `spatial_scope` y consultas de resolución.
- `load_scopes.py` — helper (el CSV final se generó con `gen-scopes-csv.js`, en temp; patrón: quoting CSV).
- `oapn-limites.geojson` — descarga real del 2026-09-05: WFS GeoJSON de OAPN (17 parques nacionales + Área de Especial Protección de Guadarrama).
- SHA-256 de la descarga: `7fc5077b223475d69287e2121ed37b7f56b691d7a6df6aa16c7a90be5d678770`.

## Cómo se ejecutó
```bash
curl "https://sigred.oapn.es/geoserverOAPN/LimitesParquesNacionalesZPP/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=LimitesParquesNacionalesZPP%3Aview_red_oapn_limite_pn&outputFormat=application%2Fjson" -o oapn-limites.geojson
docker run --name spikeb-postgis -e POSTGRES_PASSWORD=spike -v <tmp>:/work -d postgis/postgis:16-3.4
docker exec spikeb-postgis psql -U postgres -d spike -v picos_hash=<sha256> -f /work/spike-b.sql
```

## Resultados
| Sonda | Resultado |
|---|---|
| 43.1961,-4.8444 (Fuente Dé) | `NATIONAL_PARK` Picos de Europa + ley declarativa + URL + hash |
| 40.8483,-3.9576 (Peñalara) | `NATIONAL_PARK` Sierra de Guadarrama + ley declarativa |
| 43.3619,-5.8494 (Oviedo) | sin scopes (correcto) |

## Hallazgos clave
1. OAPN expone WFS 2.0.0 con GeoJSON y **metadatos normativos por feature** (ley declarativa, fecha).
2. Las geometrías llegan en EPSG:25830 (UTM 30N) → transformación documentada a ETRS89 4258.
3. Procedencia por geometría (URL+hash+retrieved_at+feature_id) cabe en PostGIS sin fricción.
4. Los shapefiles/rar de OAPN no están versionados: el hash por descarga es imprescindible.
