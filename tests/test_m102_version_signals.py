"""M10.2-C version signals — contract tests (hermetic, no network).

Pins the frozen §C.3 contract:

- BOE metadatos: verified response -> RESOLVED candidate (document
  version only); fecha_actualizacion + provenance retained;
  effective_from <- structured fecha_vigencia.
- DOGC socrata+ELI: verified row + idVersion redirect -> RESOLVED;
  ELI + idVersion provenance retained; effective_from stays null.
- Every malformed/missing/contradictory/failed case ->
  REQUIRES_MANUAL_REVIEW with the evidence preserved.
- Same fixture -> deterministic VersionClaim.
- No legal_rule_version / review-complete writes — the resolver returns
  a VersionClaim and nothing else.
"""

from __future__ import annotations

import copy

import pytest

from pipeline.models import DocumentRef, VersionClaimStatus
from pipeline.providers.version import resolve

FIXED_NOW = "2026-09-18T12:00:00Z"

BOE_PAYLOAD = {
    "status": {"code": "200", "text": "ok"},
    "data": [
        {
            "fecha_actualizacion": "20260313T122740Z",
            "identificador": "BOE-A-2007-21490",
            "rango": {"codigo": "1300", "texto": "Ley"},
            "fecha_disposicion": "20071213",
            "numero_oficial": "42/2007",
            "titulo": "Ley 42/2007, del Patrimonio Natural.",
            "fecha_publicacion": "20071214",
            "fecha_vigencia": "20071215",
            "estatus_derogacion": "N",
            "estatus_anulacion": "N",
            "vigencia_agotada": "N",
            "estado_consolidacion": {"codigo": "3", "texto": "Finalizado"},
            "url_eli": "https://www.boe.es/eli/es/l/2007/12/13/42",
        }
    ],
}

DOGC_ROW = {
    "n_mero_de_control": "309790",
    "t_tol_de_la_norma": "DECRET 39/2003",
    "data_del_document": "2003-02-04T00:00:00.000",
    "data_de_publicaci_del_diari": "2003-02-19T00:00:00.000",
    "vig_ncia_de_la_norma": "Vigent",
    "url_format_xml": {
        "url": "https://portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39/dof/cat/xml"
    },
}

DOGC_REDIRECT = {
    "request_url": "https://portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39/dof/cat/xml",
    "effective_url": (
        "https://portaldogc.gencat.cat/utilsEADOP/AppJava/AkomaNtoso"
        "?idNumber=309790&idVersion=318062&format=xml"
    ),
    "http_status": 200,
}


def _boe_bundle(payload=BOE_PAYLOAD, **over):
    bundle = {
        "signal_source": "boe_metadatos",
        "endpoint": "https://www.boe.es/datosabiertos/api/"
                    "legislacion-consolidada/id/BOE-A-2007-21490/metadatos",
        "retrieved_at": "2026-09-18T11:00:00Z",
        "response_sha256": "ab12" * 16,
        "runner_network": "es_local",
        "fetch_outcome": "SUCCESS",
        "payload": payload,
    }
    bundle.update(over)
    return bundle


def _dogc_bundle(row=DOGC_ROW, redirect=DOGC_REDIRECT, **over):
    bundle = {
        "signal_source": "dogc_socrata_eli",
        "endpoint": DOGC_REDIRECT["request_url"],
        "retrieved_at": "2026-09-18T11:00:00Z",
        "response_sha256": "cd34" * 16,
        "runner_network": "es_local",
        "fetch_outcome": "SUCCESS",
        "payload": {"socrata_row": row, "eli_redirect": redirect},
    }
    bundle.update(over)
    return bundle


class _P:
    """Minimal profile stub — only `versioning` is consumed."""

    def __init__(self, signal):
        self.versioning = {
            "strategy": "consolidated_api",
            "signal_source": signal,
        }


def _boe_doc():
    return DocumentRef(
        source_id="boe",
        doc_id="BOE-A-2007-21490",
        published_on="2007-12-14",
        title="Ley 42/2007",
        issuer="Jefatura del Estado",
        discovery_url="https://www.boe.es/buscar/doc.php?id=BOE-A-2007-21490",
    )


def _dogc_doc():
    return DocumentRef(
        source_id="dogc",
        doc_id="es-ct/d/2003/02/04/39",
        published_on="2003-02-19",
        title="DECRET 39/2003",
        issuer="Generalitat de Catalunya",
        discovery_url=DOGC_REDIRECT["request_url"],
    )


def _boe(bundle=None):
    return resolve(
        _P("boe_metadatos"), _boe_doc(), clock=lambda: FIXED_NOW,
        structured_evidence={"consolidated": bundle or _boe_bundle()},
    )


def _dogc(bundle=None):
    return resolve(
        _P("dogc_socrata_eli"), _dogc_doc(), clock=lambda: FIXED_NOW,
        structured_evidence={"consolidated": bundle or _dogc_bundle()},
    )


MANUAL = VersionClaimStatus.REQUIRES_MANUAL_REVIEW
RESOLVED = VersionClaimStatus.RESOLVED

# ---------------------------------------------------------------------
# BOE
# ---------------------------------------------------------------------


def test_boe_verified_response_resolves():
    claim = _boe()
    assert claim.status is RESOLVED
    assert claim.effective_from == "2007-12-15"
    assert claim.publication_date == "2007-12-14"
    assert claim.consolidated_state == "Finalizado"
    ev = claim.resolver_evidence
    assert ev["signal"] == "document_version_only"
    assert ev["fecha_actualizacion"] == "20260313T122740Z"
    assert ev["vigencia_agotada"] == "N"
    assert ev["url_eli"].endswith("/eli/es/l/2007/12/13/42")
    for k in ("endpoint", "retrieved_at", "response_sha256",
              "runner_network", "fetch_outcome"):
        assert ev[k], k


def test_boe_deterministic():
    assert _boe().to_dict() == _boe().to_dict()


def test_boe_id_mismatch_manual():
    p = copy.deepcopy(BOE_PAYLOAD)
    p["data"][0]["identificador"] = "BOE-A-1999-1"
    assert _boe(_boe_bundle(payload=p)).status is MANUAL


def test_boe_missing_version_field_manual():
    p = copy.deepcopy(BOE_PAYLOAD)
    del p["data"][0]["fecha_vigencia"]
    claim = _boe(_boe_bundle(payload=p))
    assert claim.status is MANUAL
    assert claim.effective_from is None


def test_boe_malformed_payload_manual():
    assert _boe(_boe_bundle(payload={"status": {"code": "200"},
                                     "data": "oops"})).status is MANUAL
    assert _boe(_boe_bundle(payload="not a mapping")).status is MANUAL
    assert _boe(_boe_bundle(payload=None)).status is MANUAL


def test_boe_api_error_status_manual():
    p = copy.deepcopy(BOE_PAYLOAD)
    p["status"]["code"] = "400"
    assert _boe(_boe_bundle(payload=p)).status is MANUAL


def test_boe_transport_failure_manual():
    b = _boe_bundle(fetch_outcome="TIMEOUT", payload=None)
    claim = _boe(b)
    assert claim.status is MANUAL
    assert "fetch_outcome" in claim.resolver_evidence[
        "manual_review_reason"]


def test_boe_missing_bundle_keys_manual():
    b = _boe_bundle()
    del b["response_sha256"]
    assert _boe(b).status is MANUAL


def test_boe_signal_source_mismatch_manual():
    assert _boe(_boe_bundle(signal_source="dogc_socrata_eli")
                ).status is MANUAL


def test_boe_non_mapping_nested_fields_manual_not_crash():
    """Truthy non-dict nested fields must fail closed — never crash."""
    p = copy.deepcopy(BOE_PAYLOAD)
    p["status"] = "ok"
    assert _boe(_boe_bundle(payload=p)).status is MANUAL
    p = copy.deepcopy(BOE_PAYLOAD)
    p["data"][0]["estado_consolidacion"] = "Finalizado"
    assert _boe(_boe_bundle(payload=p)).status is MANUAL


def test_boe_lenient_date_shape_manual():
    """strptime would silently accept 1-2 digit %m/%d — the resolver
    requires the exact compact shape."""
    for bad in ("200715", "2007125", "2007-12-15", "garbage"):
        p = copy.deepcopy(BOE_PAYLOAD)
        p["data"][0]["fecha_vigencia"] = bad
        assert _boe(_boe_bundle(payload=p)).status is MANUAL, bad


# ---------------------------------------------------------------------
# DOGC
# ---------------------------------------------------------------------


def test_dogc_verified_response_resolves():
    claim = _dogc()
    assert claim.status is RESOLVED
    # no structured effective-date field -> stays null, still RESOLVED
    # (RESOLVED = document version resolved mechanically)
    assert claim.effective_from is None
    assert claim.consolidated_state == "Vigent"
    assert claim.publication_date == "2003-02-19"
    ev = claim.resolver_evidence
    assert ev["id_number"] == "309790"
    assert ev["id_version"] == "318062"
    assert ev["eli"] == "es-ct/d/2003/02/04/39"
    assert ev["vigencia"] == "Vigent"


def test_dogc_deterministic():
    assert _dogc().to_dict() == _dogc().to_dict()


def test_dogc_missing_idversion_manual():
    r = dict(DOGC_REDIRECT, effective_url=(
        "https://portaldogc.gencat.cat/utilsEADOP/AppJava/AkomaNtoso"
        "?idNumber=309790&format=xml"))
    assert _dogc(_dogc_bundle(redirect=r)).status is MANUAL


def test_dogc_eli_doc_id_mismatch_manual():
    row = copy.deepcopy(DOGC_ROW)
    row["url_format_xml"] = {
        "url": "https://portaljuridic.gencat.cat/eli/es-ct/d/2003/05/27/139/dof/cat/xml"
    }
    assert _dogc(_dogc_bundle(row=row)).status is MANUAL


def test_dogc_missing_vigencia_manual():
    row = copy.deepcopy(DOGC_ROW)
    del row["vig_ncia_de_la_norma"]
    assert _dogc(_dogc_bundle(row=row)).status is MANUAL


def test_dogc_fetch_failure_manual():
    b = _dogc_bundle(fetch_outcome="TRANSPORT_ERROR", payload=None)
    assert _dogc(b).status is MANUAL


def test_dogc_redirect_not_captured_manual():
    """Transport that does not capture effective_url -> manual."""
    r = dict(DOGC_REDIRECT, effective_url=None)
    assert _dogc(_dogc_bundle(redirect=r)).status is MANUAL


def test_dogc_request_url_binding():
    """The redirect observation must belong to THIS document: a bundle
    pairing the row of doc A with the ELI fetch of doc B fails closed."""
    r = dict(DOGC_REDIRECT, request_url=(
        "https://portaljuridic.gencat.cat/eli/es-ct/d/2003/05/27/139"
        "/dof/cat/xml"))
    assert _dogc(_dogc_bundle(redirect=r)).status is MANUAL


def test_dogc_effective_url_host_anchored():
    """idNumber/idVersion params on an arbitrary host prove nothing."""
    r = dict(DOGC_REDIRECT, effective_url=(
        "https://attacker.example/x?idNumber=309790&idVersion=318062"))
    assert _dogc(_dogc_bundle(redirect=r)).status is MANUAL


def test_dogc_idversion_strict_digits():
    r = dict(DOGC_REDIRECT, effective_url=(
        DOGC_REDIRECT["effective_url"].replace("318062", "318062abc")))
    assert _dogc(_dogc_bundle(redirect=r)).status is MANUAL


def test_dogc_eli_tail_anchored():
    """…/39junk must not capture as doc …/39."""
    row = copy.deepcopy(DOGC_ROW)
    row["url_format_xml"] = {"url": (
        "https://portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39junk"
        "/dof/cat/xml")}
    assert _dogc(_dogc_bundle(row=row)).status is MANUAL


def test_dogc_url_format_xml_as_plain_string():
    """Socrata variants serialize URL columns as bare strings — still a
    valid structured ELI binding."""
    row = copy.deepcopy(DOGC_ROW)
    row["url_format_xml"] = (
        "https://portaljuridic.gencat.cat/eli/es-ct/d/2003/02/04/39"
        "/dof/cat/xml")
    assert _dogc(_dogc_bundle(row=row)).status is RESOLVED


def test_dogc_malformed_publication_date_manual():
    row = copy.deepcopy(DOGC_ROW)
    row["data_de_publicaci_del_diari"] = "garbage"
    assert _dogc(_dogc_bundle(row=row)).status is MANUAL


# ---------------------------------------------------------------------
# global invariants
# ---------------------------------------------------------------------


def test_no_bundle_is_manual_not_error():
    claim = resolve(
        _P("boe_metadatos"), _boe_doc(), clock=lambda: FIXED_NOW
    )
    assert claim.status is MANUAL


def test_free_text_vacatio_never_effective_from():
    """Free-text effective-date prose can only reach the claim via
    structured_evidence.effective_from — which demands an ISO date +
    preserved fragment. A vacatio string alone is rejected."""
    bundle = _boe_bundle()
    ev = {
        "consolidated": bundle,
        "effective_from": "al día siguiente de su publicación",
        "fragment": "entrará en vigor al día siguiente",
    }
    from pipeline.providers.version import VersionError

    with pytest.raises(VersionError):
        resolve(_P("boe_metadatos"), _boe_doc(), clock=lambda: FIXED_NOW,
                structured_evidence=ev)


def test_resolved_claim_is_document_version_only():
    """RESOLVED asserts a document version — nothing legal. The claim
    carries no fields that could be consumed as legal truth."""
    for claim in (_boe(), _dogc()):
        d = claim.to_dict()
        assert "official_status" not in d
        assert "legal_review_complete" not in d
        assert "spatial_review_complete" not in d
        assert claim.resolver_evidence["signal"] == "document_version_only"


def test_preregistered_date_never_merges_into_resolved():
    """A preregistered effective_from must not attach to a RESOLVED
    claim — on RESOLVED only the mechanical signal is authoritative."""
    ev = {
        "consolidated": _dogc_bundle(),
        "effective_from": "2003-02-19",
        "fragment": "disposicion final primera",
    }
    claim = resolve(_P("dogc_socrata_eli"), _dogc_doc(),
                    clock=lambda: FIXED_NOW, structured_evidence=ev)
    assert claim.status is RESOLVED
    assert claim.effective_from is None


def test_preregistered_date_on_manual_claim_is_stamped():
    """On a fail-closed claim a preregistered date may attach — with an
    explicit channel stamp so provenance cannot be confused."""
    ev = {
        "consolidated": _boe_bundle(fetch_outcome="TIMEOUT",
                                    payload=None),
        "effective_from": "2007-12-15",
        "fragment": "entrara en vigor el dia siguiente",
    }
    claim = resolve(_P("boe_metadatos"), _boe_doc(),
                    clock=lambda: FIXED_NOW, structured_evidence=ev)
    assert claim.status is MANUAL
    assert claim.effective_from == "2007-12-15"
    assert claim.resolver_evidence["effective_from_channel"] == (
        "preregistered")
