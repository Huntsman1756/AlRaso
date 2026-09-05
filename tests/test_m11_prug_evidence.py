"""M1.1-B evidence: the PRUG annex study reached D2 and the spatial branch is
closed. These tests read committed evidence only; no network, no PDF parsing."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "tooling" / "m11b_prug_annex.evidence.json"
DOC = ROOT / "docs" / "ALRASO-M11-VECTOR-DISCOVERY.md"


@pytest.fixture(scope="module")
def ev() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_classification_and_stop_policy(ev):
    assert ev["schema"] == "alraso-m11b-prug-cartography-evidence/v1"
    assert ev["classification"] == "D2"
    assert "NOT_UNAMBIGUOUS" in ev["classification_label"]
    assert "SPATIAL_EVIDENCE_INCOMPLETE" in ev["spatial_status_after"]
    assert ev["policy"]["digitization_allowed"] is False
    assert "FORBIDDEN" in ev["policy"]["mapa_88_as_operative_geometry"]
    assert ev["policy"]["goriz_polygon_must_stay_separate_from_sector_delimitation"] is True


def test_pinned_documents_are_reproducible(ev):
    docs = ev["normative_documents"]
    annex = docs["annex_11_5_cartography"]
    assert re.fullmatch(r"[0-9a-f]{64}", annex["sha256"])
    assert annex["bytes"] == 54497898 and annex["pages"] == 101
    assert "ETRS" in annex["format"]
    assert docs["prug_update_2022"]["bytes"] == 1049218
    for d in (annex, docs["prug_update_2022"]):
        assert d["url"].startswith("https://www.aragon.es/documents/")
    assert ev["retrieved_at"].startswith("2026-09-05")


def test_normative_chain_is_recorded_verbatim(ev):
    norma = ev["chain"]["norma"]
    assert "cuencas hidrográficas" in norma["sectors_defined_by_basins"]["verbatim"]
    assert "Arazas (Sector Ordesa)" in norma["sectors_defined_by_basins"]["verbatim"]
    vivac = norma["vivac_rule"]["verbatim"]
    assert "prohibida en el sector Ordesa" in vivac
    assert "Véase Anexo 11.5 Cartogra" in vivac          # norma -> explicit cartography ref
    assert "1.650" in vivac and "1.800" in vivac and "2.550" in vivac
    assert "Mapa 29" in norma["goriz_camping_zone"]["verbatim"]  # goriz legal chain closed


def test_mapa_88_staleness_is_frozen_in_the_record(ev):
    m88 = ev["chain"]["mapa_88"]
    assert m88["source_map_number"] == 88 and m88["annex_page"] == 92
    assert m88["stated_date"] == "2013"
    assert "Ordesa: cota 2.500 metros" in m88["legend_verbatim"]   # the dead rule
    assert "Zona de Vivac en Ordesa" in m88["legend_verbatim"]     # bands, not a sector line
    joined = " ".join(ev["findings"])
    assert "does NOT draw a Sector Ordesa boundary" in joined
    assert "STALENESS" in joined


def test_documentation_records_the_closure():
    doc = DOC.read_text(encoding="utf-8")
    assert "Resultado M1.1-B: `D2`" in doc
    assert "rama CERRADA" in doc
    assert "Fecha: 2013" in doc or "2013" in doc
    assert "UNDETERMINED" in doc
