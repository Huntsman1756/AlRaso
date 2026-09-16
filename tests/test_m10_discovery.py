"""M10.1 Task 3 — DiscoveryProvider ``bocyl_opendatasoft`` contract.

Strict boundary: the provider interprets an Opendatasoft records payload and
returns ``DocumentRef[]``. It never fetches document bytes, never evaluates
content markers, never parses decree contents, never derives effective
dates.

The record payload below is assembled from G0-verified values only:
field names come from ``bocyl-dataset-meta.json`` (real dataset metadata)
and the values from ``bocyl-17-2025-head.xml`` + the verified doc URL in
``source-matrix.json``. The XML head is used as a cross-check fixture —
discovery does NOT open or parse it.
"""

import ast
import inspect
import json
import re
from pathlib import Path

import pytest

import pipeline.providers.discovery as discovery
from pipeline.models import DocumentRef
from pipeline.profiles import load_profile
from pipeline.providers.discovery import DiscoveryError, discover

ROOT = Path(__file__).resolve().parents[1]
G0 = ROOT / "discovery" / "evidence" / "spain-coverage-g0"
PROFILE_JSON = ROOT / "pipeline" / "sources" / "bocyl.profile.json"
DATASET_META = G0 / "bocyl-dataset-meta.json"
XML_HEAD = G0 / "bocyl-17-2025-head.xml"

DOC_URL_XML = (
    "https://bocyl.jcyl.es/boletines/2025/12/15/xml/BOCYL-D-15122025-1.xml"
)

# Values verified in G0 (bocyl-17-2025-head.xml / source-matrix.json).
G0_RECORD = {
    "no_edicion": "240/2025",
    "fecha_publicacion": "2025-12-15",
    "seccion": "I. COMUNIDAD DE CASTILLA Y LEÓN",
    "subseccion": "A. DISPOSICIONES GENERALES",
    "organismo": "CONSEJERÍA DE MEDIO AMBIENTE, VIVIENDA Y ORDENACIÓN DEL TERRITORIO",
    "rango": "DECRETO",
    "no_oficial": "17/2025",
    "fecha_disposicion": "2025-12-11",
    "titulo": "DECRETO 17/2025, de 11 de diciembre, por el que se aprueba el Plan Rector de uso y gestión del Parque Nacional de los Picos de Europa en el ámbito territorial de la Comunidad de Castilla y León.\n",
    "pagina_inicial": "48213",
    "pagina_final": "48220",
    "enlace_fichero_xml": DOC_URL_XML,
    "enlace_fichero_pdf": "https://bocyl.jcyl.es/boletines/2025/12/15/pdf/BOCYL-D-15122025-1.pdf",
    "enlace_fichero_html": "https://bocyl.jcyl.es/boletines/2025/12/15/htm/BOCYL-D-15122025-1.htm",
}


def _payload(*records: dict) -> dict:
    return {"total_count": len(records), "results": list(records)}


def _profile():
    return load_profile(PROFILE_JSON)


def _xml_head() -> str:
    return XML_HEAD.read_text(encoding="iso-8859-15")


def test_valid_fixture_returns_expected_docref():
    refs = discover(_profile(), _payload(G0_RECORD))
    assert len(refs) == 1
    ref = refs[0]
    assert isinstance(ref, DocumentRef)
    assert ref.source_id == "bocyl"
    assert ref.doc_id == "BOCYL-D-15122025-1"
    assert ref.published_on == "2025-12-15"
    assert ref.title.startswith("DECRETO 17/2025")
    assert ref.issuer.startswith("CONSEJERÍA DE MEDIO AMBIENTE")
    assert ref.rank == 0
    assert ref.discovery_url == DOC_URL_XML


def test_doc_id_is_the_g0_stable_native_id():
    """G0 preregisters BOCYL-D-DDMMYYYY-N as the stable gazette id — it is
    derived from the verified document URL, not invented."""
    refs = discover(_profile(), _payload(G0_RECORD))
    assert re.fullmatch(r"BOCYL-D-\d{8}-\d+", refs[0].doc_id)


def test_docref_crosschecked_against_g0_xml_head():
    """Cross-fixture: the DocumentRef points at the same instrument the G0
    XML head proves (same numeroOficial inside title, same fechaPublicacion).
    The provider itself never opens the XML — the test does."""
    xml = _xml_head()
    numero = re.search(r"<numeroOficial>([^<]+)", xml).group(1).strip()
    fecha = re.search(r"<fechaPublicacion>([^<]+)", xml).group(1).strip()
    refs = discover(_profile(), _payload(G0_RECORD))
    assert refs[0].published_on == fecha
    assert numero in refs[0].title


def test_links_are_references_not_downloads():
    """The XML link is conserved as discovery_url; the PDF/HTML siblings are
    reconstructible from the profile doc_url_template + doc_id — nothing is
    downloaded at discovery time."""
    ref = discover(_profile(), _payload(G0_RECORD))[0]
    assert ref.discovery_url.endswith("BOCYL-D-15122025-1.xml")
    template = _profile().fetch["doc_url_template"]
    assert "BOCYL-D-" in template  # fetch-time reconstruction stays possible


def test_published_on_normalized_deterministically():
    rec = dict(G0_RECORD, fecha_publicacion="2025-12-15T00:00:00+00:00")
    ref = discover(_profile(), _payload(rec))[0]
    assert ref.published_on == "2025-12-15"
    # Publication metadata only — discovery never invents effective dates.
    assert "effective_from" not in ref.to_dict()
    assert "effective_to" not in ref.to_dict()


def test_multiple_results_have_deterministic_order():
    older = dict(
        G0_RECORD,
        no_oficial="1/2025",
        fecha_publicacion="2025-01-10",
        titulo="DECRETO 1/2025 test",
        enlace_fichero_xml="https://bocyl.jcyl.es/boletines/2025/01/10/xml/BOCYL-D-10012025-2.xml",
    )
    # Input order reversed on purpose: output must not depend on it.
    refs = discover(_profile(), _payload(G0_RECORD, older))
    assert [r.doc_id for r in refs] == [
        "BOCYL-D-10012025-2",
        "BOCYL-D-15122025-1",
    ]
    assert [r.rank for r in refs] == [0, 1]


def test_window_filters_by_publication_date():
    older = dict(
        G0_RECORD,
        fecha_publicacion="2025-01-10",
        enlace_fichero_xml="https://bocyl.jcyl.es/boletines/2025/01/10/xml/BOCYL-D-10012025-2.xml",
    )
    refs = discover(
        _profile(), _payload(G0_RECORD, older), window=("2025-12-01", None)
    )
    assert [r.doc_id for r in refs] == ["BOCYL-D-15122025-1"]
    refs = discover(
        _profile(), _payload(G0_RECORD, older), window=(None, "2025-06-01")
    )
    assert [r.doc_id for r in refs] == ["BOCYL-D-10012025-2"]


def test_malformed_row_fails_explicitly():
    missing_title = {k: v for k, v in G0_RECORD.items() if k != "titulo"}
    with pytest.raises(DiscoveryError, match="titulo"):
        discover(_profile(), _payload(missing_title))

    bad_link = dict(G0_RECORD, enlace_fichero_xml="https://x.invalid/no-id")
    with pytest.raises(DiscoveryError, match="doc_id|enlace"):
        discover(_profile(), _payload(bad_link))

    bad_date = dict(G0_RECORD, fecha_publicacion="not-a-date")
    with pytest.raises(DiscoveryError, match="fecha_publicacion"):
        discover(_profile(), _payload(bad_date))

    with pytest.raises(DiscoveryError, match="results"):
        discover(_profile(), {"unexpected": "shape"})


def test_unknown_provider_fails_explicitly():
    profile = _profile()
    object.__setattr__(  # SourceProfile is frozen; build a variant instead
        profile,
        "discovery",
        {**profile.discovery, "provider": "not_a_provider"},
    )
    with pytest.raises(DiscoveryError, match="not_a_provider"):
        discover(profile, _payload(G0_RECORD))


def test_profile_declared_fields_exist_in_g0_dataset_meta():
    """Every field the profile relies on was verified present in the real
    Opendatasoft dataset during G0."""
    meta = json.loads(DATASET_META.read_text(encoding="utf-8"))
    names = {f["name"] for f in meta["fields"]}
    declared = set(_profile().discovery["fields"])
    assert declared <= names, f"profile fields not in G0 meta: {declared - names}"


def test_reachability_expectation_stays_in_profile():
    """DocumentRef does not copy reachability truth: expectation lives in the
    profile, execution truth lands on DocumentEvidence at fetch time."""
    ref = discover(_profile(), _payload(G0_RECORD))[0]
    assert ref.reachability_class is None


def test_same_fixture_same_serialization():
    a = discover(_profile(), _payload(G0_RECORD))
    b = discover(_profile(), _payload(G0_RECORD))
    assert a == b
    assert json.dumps(a[0].to_dict(), sort_keys=True) == json.dumps(
        b[0].to_dict(), sort_keys=True
    )


def test_no_network_and_no_layer_violations():
    """discovery.py imports neither network stacks nor sibling layers."""
    tree = ast.parse(inspect.getsource(discovery))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    forbidden = {
        "urllib",
        "urllib.request",
        "http",
        "http.client",
        "socket",
        "requests",
        "httpx",
        "pipeline.providers.fetch",
        "pipeline.providers.parse",
        "pipeline.providers.version",
    }
    assert not imported & forbidden, f"forbidden imports: {imported & forbidden}"


def test_no_jurisdiction_branching():
    src = inspect.getsource(discovery)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
