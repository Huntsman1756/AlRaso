"""Assemble the full Picos Phase B fixture from the generated geometry + verified
legal content from tooling/m2a_picos_discovery.evidence.json."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GEN = os.path.join(ROOT, "alraso/resources/fixture_picos.json")
EVID = os.path.join(ROOT, "tooling/m2a_picos_discovery.evidence.json")
OUT = os.path.join(ROOT, "alraso/resources/fixture_picos.json")

geo = json.load(open(GEN, encoding="utf-8"))["geometry"]
ev = json.load(open(EVID, encoding="utf-8"))

DECREES = {
    "es-as": ("sd-pnpe-as-decreto-21-2026", "lf-pnpe-as-art51", "ss-pnpe-es-as",
              "Principado de Asturias", "BOPA 30/03/2026, Cód. 2026-02506",
              "https://miprincipado.asturias.es/bopa",
              "https://parquenacionalpicoseuropa.es/wp-content/uploads/2026/06/prug-pnpe-as-decreto-21_2026.pdf",
              "a1e374e5dcc12c5de2de653abf1f4da2635c620a10ac17e4f43ffd709d5210bd",
              "2026-04-19"),
    "es-cb": ("sd-pnpe-cb-decreto-57-2026", "lf-pnpe-cb-art51", "ss-pnpe-es-cb",
              "Comunidad Autónoma de Cantabria", "BOC núm. 148, 04/08/2026",
              "https://www.cantabria.es/web/boc",
              "https://parquenacionalpicoseuropa.es/wp-content/uploads/2026/08/prug-pnpe-ca-decreto-57_2026.pdf",
              "28ad80f99b44278153ee928e83efd27b8187049285891556db0e2381797c62c2",
              "2026-08-24"),
    "es-cl": ("sd-pnpe-cl-decreto-17-2025", "lf-pnpe-cl-art51", "ss-pnpe-es-cl",
              "Junta de Castilla y León", "BOCyL núm. 240, 15/12/2025",
              "https://bocyl.jcyl.es/boletin.do?fechaBoletin=15/12/2025",
              "https://parquenacionalpicoseuropa.es/wp-content/uploads/2026/06/prug-pnpe-cyl-decreto-17_2025.pdf",
              "70b07b6da908c873dc3c3fc6ff7dfe8f984e55493b40b4a690de49bc9a4edbca",
              "2026-01-04"),
}

ART51_TEXT = ("Art. 51 (común): el vivac/pernocta al raso solo se permite vinculado a "
              "actividades de montaña y escalada, por un máximo de 3 noches y siempre "
              "por encima de la cota 1.800 m. Excepciones (vivac en pared; invierno en "
              "Vega La Sotin) y tiendas por meteorología adversa no se codifican aquí.")

source_documents = []
legal_fragments = []
spatial_scopes = []
legal_rule_versions = []

for jur, (sd_id, lf_id, scope_id, authority, ident, gazette_url, pdf_url, sha, eff) in DECREES.items():
    source_documents.append({
        "id": sd_id, "authority": authority, "jurisdiction": jur,
        "canonical_url": gazette_url, "official_copy_url": pdf_url,
        "official_copy_sha256": sha, "official_identifier": ident,
        "document_type": "PRUG_AUTONOMIC_DECREE",
        "official_status": "VIGENTE",
        "title": f"Decreto PRUG PN Picos de Europa — ámbito {authority} ({ident})",
    })
    legal_fragments.append({
        "id": lf_id, "source_document_id": sd_id,
        "exact_text_hint": ART51_TEXT,
        "locator": "art. 51 (verbatim en los tres decretos; diff de arts. 50-54 sin diferencias)",
        "extracted_at": "2026-09-06", "review_status": "VERIFIED",
    })
    spatial_scopes.append({
        "id": scope_id, "official_name": f"Sector {authority} del PN Picos de Europa",
        "scope_type": "OTHER", "relevance": "REGULATORY",
        "parent_scope": "ss-pnpe-limits",
        "geometry_source": ("GISCO NUTS2 {nid} 01M 2024 intersección con el límite OAPN "
                            "(simplificado; caveat: precisión frontera ±1 km, re-verificar IDE "
                            "para <1 km)").format(nid=ev["spatial"]["ccaa_gisco_nuts2"]["units"].get(
                                jur.upper(), jur)),
        "srid_native": 4326, "review_status": "VERIFIED",
    })
    legal_rule_versions.append({
        "rule_id": f"alraso:{jur}/pn-picos/pernocta#vivac-cota-1800",
        "activity": "VIVAC_AL_RASO", "spatial_scope_id": scope_id,
        "effect": "PERMITTED",
        "condition": {"all": [
            {"field": "actividad_montana_o_escalada", "op": "is_true"},
            {"field": "nights", "op": "lte", "value": 3},
            # art. 51: "siempre por encima de la cota 1.800 m" -> ESTRICTAMENTE > 1800
            {"field": "cota_m", "op": "gt", "value": 1800},
            # hecho INTERNO (calculado por la app, nunca aportable por query):
            # si se reutiliza el fixture sin el guard de frontera, falla cerrado.
            {"field": "jurisdiction_boundary_safe", "op": "is_true"},
        ]},
        "effective_from": eff, "effective_to": None,
        "recorded_at": "2026-09-06", "recorded_until": None,
        "review_status": "VERIFIED", "legal_review_complete": True,
        "spatial_review_complete": True,
        "evidence": [lf_id],
        "interpretation_note": ("Lectura literal del art. 51 común (verificado verbatim en los tres "
                                "decretos): PERMITTED solo si actividad de montaña/escalada Y ≤3 noches "
                                "Y cota ESTRICTAMENTE > 1.800 m (art. 51 'por encima de la cota 1.800 m'; "
                                "exactamente 1.800 m NO satisface). El hecho interno "
                                "jurisdiction_boundary_safe lo calcula la app (guard de incertidumbre "
                                "de frontera CCAA <1 km = BOUNDARY_EVIDENCE_INCOMPLETE); quien use el "
                                "fixture sin ese hecho falla cerrado (ENGINE_MISSING_INPUT). Excepciones "
                                "(pared; Vega La Sotin) y tiendas por meteorología adversa NO se "
                                "codifican. La cota la aporta el hecho cota_m (auto-elevación vía DEM = C)."),
    })

# park context scope (geometry = park boundary)
spatial_scopes.insert(0, {
    "id": "ss-pnpe-limits", "official_name": "Parque Nacional de los Picos de Europa",
    "scope_type": "OTHER", "relevance": "CONTEXT_ONLY", "parent_scope": None,
    "geometry_source": ("OAPN WFS view_red_oapn_limite_pn (EPSG:25830→4326, simplificado; "
                        "66.032,4 ha vs 66.030 ha preámbulos, Δ0,004 %)"),
    "srid_native": 25830, "review_status": "VERIFIED",
})

fixture = {
    "$schema": "https://alraso.example/schemas/picos-phaseb-fixture-v1.json",
    "expected": {
        "P1_asturias_urriellu": "PERMITTED con condiciones (montaña, ≤3 noches, cota 2.400 m)",
        "P2_cantabria_interior": "UNDETERMINED sin hechos (fail-closed); PERMITTED con hechos",
        "P3_cyl_cain_valdeon": "UNDETERMINED sin hechos; PERMITTED con hechos",
        "P6_bitemporal_gap": "UNDETERMINED (Cantabria sin PRUG vigente antes de 2026-08-24)",
        "P7_outside": "NO_APPLICABLE_SCOPE (nunca PROHIBITED sectorial)",
        "invariant": "PERMITTED jamás desde ausencia; cota_m faltante → UNDETERMINED",
    },
    "fixture_meta": {
        "created": "2026-09-06",
        "identity_evidence": "tooling/m2a_picos_discovery.evidence.json (gate A)",
        "name": "PICOS_PHASEB_FIXTURE",
        "purpose": ("Phase B incremental: art. 51 común (3 decretos autonómicos) + jurisdicción "
                    "por CCAA. Geométria mínima justificada (límite OAPN simplificado + intersección "
                    "GISCO NUTS2). DEM (cota auto) y vectores IDE <1 km quedan B/C."),
        "semantics": {
            "boundary_policy": "InMemory raycast; NO fiable en bordes exactos (coordenada cerca de frontera CCAA → re-verificar IDE)",
            "condition_facts": "actividad_montana_o_escalada, nights, cota_m son hechos aportados; faltan → fail-closed UNDETERMINED",
            "not_encoded": "excepciones art.51 (pared, Vega La Sotin), tiendas por meteorología, acampada art.52, pernocta en vehículo",
            "jurisdiction": "ámbito (park, CONTEXT_ONLY) ≠ jurisdicción (CCAA, REGULATORY); una norma por consulta",
        },
    },
    "geometry": geo,
    "source_documents": source_documents,
    "legal_fragments": legal_fragments,
    "spatial_scopes": spatial_scopes,
    "legal_rule_versions": legal_rule_versions,
    "probe_points": ev["probe_points"],
    "rule_relations": [],
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(fixture, fh, ensure_ascii=False, indent=1)
print("WROTE", OUT, "bytes", os.path.getsize(OUT))
print("scopes", len(spatial_scopes), "rules", len(legal_rule_versions), "sources", len(source_documents))
