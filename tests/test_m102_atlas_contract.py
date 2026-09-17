"""M10.2-A atlas contract — domain records, schema validation, gate.

RED-first contract suite for the National Source Atlas machinery:

- ``pipeline/schemas/source-atlas.schema.json`` — domain record contract
- ``pipeline/atlas.py`` — canonical domain set + executable exit gate
- ``tooling/m102_atlas_probe.py`` — probe evidence writer/verifier

Pinned invariants (spec M10.2 §B/§C.1/§G, approved plan M10.2-A):

- ``domain_status`` ∈ {PROVEN, BLOCKED_WITH_EVIDENCE, UNPROBED}
- ATLAS_SCOPE = exactly 20 canonical jurisdiction domains
  (17 CCAA + Ceuta + Melilla + State) — no more, no less
- gate PASS ⟺ 20/20 in {PROVEN, BLOCKED_WITH_EVIDENCE} AND 0 UNPROBED
- PROVEN requires ≥1 REACHABLE probe whose recorded sha256 matches the
  stored evidence bytes — status is demonstrated, never declared
- BLOCKED_WITH_EVIDENCE requires identified surface(s) + preserved
  evidence of the limitation + a limitation description
- tests NEVER touch the network; all fixtures are local
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.atlas import (
    CANONICAL_DOMAINS,
    DomainGateError,
    check_gate,
    validate_atlas,
)
from pipeline.profiles import ProfileValidationError

ROOT = Path(__file__).resolve().parents[1]
ATLAS_SCHEMA = ROOT / "pipeline" / "schemas" / "source-atlas.schema.json"


def _probe(probe_id="p1", sha="", outcome="SUCCESS", reach="REACHABLE"):
    return {
        "probe_id": probe_id,
        "surface_id": "portal",
        "kind": "portal",
        "url": "https://example.es/boletin",
        "observed_at": "2026-09-18T08:00:00Z",
        "runner_network": "unknown",
        "reachability_observed": reach,
        "fetch_outcome": outcome,
        "http_status": 200 if reach == "REACHABLE" else None,
        "content_marker_ok": outcome == "SUCCESS",
        "raw_sha256": sha,
        "bytes": 10 if sha else None,
        "content_type": "text/html" if sha else None,
        "evidence_path": "",
        "detail": "",
    }


def _domain(domain_id, status="PROVEN", probes=None, surfaces=None):
    return {
        "domain_id": domain_id,
        "gazette_id": "test-gazette",
        "gazette_name": "Boletín de Prueba",
        "domain_status": status,
        "surfaces": (
            [{"surface_id": "portal", "kind": "portal",
              "url": "https://example.es/boletin"}]
            if surfaces is None
            else surfaces
        ),
        "probes": [_probe()] if probes is None else probes,
        "discovery_mechanism": "stable_url_by_id",
        "fetch_mechanism": "get_simple",
        "doc_id_scheme": "TEST-YYYY-N",
        "formats": ["html", "pdf"],
        "parser_family": "html_marker",
        "version_signal": "gazette_publication",
        "change_detection": {
            "mechanism": "issue_per_day_url",
            "strength": "medium",
            "cadence": "daily",
        },
        "reachability_expected": {
            "es_local": "REACHABLE",
            "foreign_ci": "REACHABLE",
        },
        "fallback": None,
        "license": {"terms": "public sector information reuse", "url": ""},
        "candidate_profile": None,
        "evidence_dir": "discovery/evidence/m10.2-atlas/test/",
        "status_evidence": "probe executed and recorded",
        "notes": "",
    }


def _atlas(domains):
    return {
        "version": 1,
        "generated_at": "2026-09-18T09:00:00Z",
        "domains": domains,
        "notes": "",
    }


# -------------------------------------------------------------------
# Canonical domain set
# -------------------------------------------------------------------


def test_canonical_domains_exactly_20():
    assert len(CANONICAL_DOMAINS) == 20
    assert len(set(CANONICAL_DOMAINS)) == 20
    # State + 17 CCAA + Ceuta + Melilla
    assert "ES" in CANONICAL_DOMAINS
    assert "ES-CE" in CANONICAL_DOMAINS  # Ceuta
    assert "ES-ML" in CANONICAL_DOMAINS  # Melilla
    for ccaa in (
        "ES-AN", "ES-AR", "ES-AS", "ES-CB", "ES-CL", "ES-CM", "ES-CN",
        "ES-CT", "ES-EX", "ES-GA", "ES-IB", "ES-MC", "ES-MD", "ES-NC",
        "ES-PV", "ES-RI", "ES-VC",
    ):
        assert ccaa in CANONICAL_DOMAINS


# -------------------------------------------------------------------
# Schema validation
# -------------------------------------------------------------------


def test_schema_accepts_valid_domain_record():
    validate_atlas(_atlas([_domain(d) for d in CANONICAL_DOMAINS]))


def test_schema_rejects_unknown_domain_status():
    dom = _domain("ES", status="MAYBE")
    with pytest.raises(ProfileValidationError):
        validate_atlas(_atlas([dom]))


def test_schema_rejects_missing_required_fields():
    dom = _domain("ES")
    del dom["domain_status"]
    with pytest.raises(ProfileValidationError):
        validate_atlas(_atlas([dom]))


def test_schema_rejects_unknown_top_level_key():
    dom = _domain("ES")
    dom["surprise"] = True
    with pytest.raises(ProfileValidationError):
        validate_atlas(_atlas([dom]))


def test_schema_rejects_bad_domain_id():
    with pytest.raises(ProfileValidationError):
        validate_atlas(_atlas([_domain("FR-75")]))


def test_probe_outcome_enum():
    dom = _domain("ES")
    dom["probes"][0]["fetch_outcome"] = "GIBBERISH"
    with pytest.raises(ProfileValidationError):
        validate_atlas(_atlas([dom]))


# -------------------------------------------------------------------
# Executable gate
# -------------------------------------------------------------------


def _write_body(tmp_path: Path, rel: str, body: bytes) -> str:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def _full_atlas(tmp_path: Path, *, mutate=None) -> dict:
    """20-domain atlas with verified on-disk evidence per PROVEN domain."""
    domains = []
    for d in CANONICAL_DOMAINS:
        rec = _domain(d)
        body = f"body-{d}".encode()
        sha = _write_body(tmp_path, f"ev/{d}/p1.body", body)
        rec["probes"][0]["raw_sha256"] = sha
        rec["probes"][0]["evidence_path"] = f"ev/{d}/p1.body"
        rec["evidence_dir"] = f"ev/{d}/"
        domains.append(rec)
    if mutate:
        mutate(domains)
    return _atlas(domains)


def test_gate_passes_20_proven(tmp_path):
    ok, rows = check_gate(_full_atlas(tmp_path), repo_root=tmp_path)
    assert ok, rows
    assert len(rows) == 20


def test_gate_rejects_missing_domain(tmp_path):
    atlas = _full_atlas(tmp_path)
    atlas["domains"] = atlas["domains"][:-1]
    ok, rows = check_gate(atlas, repo_root=tmp_path)
    assert not ok


def test_gate_rejects_unprobed(tmp_path):
    def mutate(domains):
        domains[3]["domain_status"] = "UNPROBED"
        domains[3]["probes"] = []

    ok, rows = check_gate(_full_atlas(tmp_path, mutate=mutate),
                          repo_root=tmp_path)
    assert not ok


def test_gate_rejects_extra_domain(tmp_path):
    def mutate(domains):
        domains.append(_domain("ES-XX"))

    with pytest.raises((ProfileValidationError, DomainGateError)):
        check_gate(_full_atlas(tmp_path, mutate=mutate),
                   repo_root=tmp_path)


def test_gate_proven_requires_reachable_probe(tmp_path):
    def mutate(domains):
        domains[0]["probes"] = [
            _probe(sha="", outcome="TIMEOUT", reach="UNREACHABLE")
        ]

    ok, rows = check_gate(_full_atlas(tmp_path, mutate=mutate),
                          repo_root=tmp_path)
    assert not ok
    assert any(r[0] == "ES" and r[1] == "FAIL" for r in rows)


def test_gate_proven_requires_verified_evidence_bytes(tmp_path):
    def mutate(domains):
        domains[1]["probes"][0]["raw_sha256"] = "0" * 64  # digest mismatch

    ok, rows = check_gate(_full_atlas(tmp_path, mutate=mutate),
                          repo_root=tmp_path)
    assert not ok
    assert any(r[0] == "ES-AN" and r[1] == "FAIL" for r in rows)


def test_gate_proven_requires_evidence_file(tmp_path):
    def mutate(domains):
        domains[2]["probes"][0]["evidence_path"] = "ev/missing.body"

    ok, rows = check_gate(_full_atlas(tmp_path, mutate=mutate),
                          repo_root=tmp_path)
    assert not ok


def test_gate_accepts_blocked_with_evidence(tmp_path):
    def mutate(domains):
        ceuta = domains[CANONICAL_DOMAINS.index("ES-CE")]
        ceuta["domain_status"] = "BLOCKED_WITH_EVIDENCE"
        ceuta["probes"] = [
            _probe(sha="", outcome="TIMEOUT", reach="UNREACHABLE")
        ]
        ceuta["status_evidence"] = (
            "portal reachable? no — timeout from runner_network=unknown; "
            "no machine-readable document surface identified"
        )

    ok, rows = check_gate(_full_atlas(tmp_path, mutate=mutate),
                          repo_root=tmp_path)
    assert ok, rows


def test_gate_blocked_requires_surfaces_and_limitation(tmp_path):
    def mutate(domains):
        melilla = domains[CANONICAL_DOMAINS.index("ES-ML")]
        melilla["domain_status"] = "BLOCKED_WITH_EVIDENCE"
        melilla["surfaces"] = []
        melilla["probes"] = []
        melilla["status_evidence"] = ""

    # schema requires status_evidence minLength — may fail validation,
    # or the gate must fail it; either way it cannot PASS.
    try:
        ok, rows = check_gate(_full_atlas(tmp_path, mutate=mutate),
                              repo_root=tmp_path)
    except (ProfileValidationError, DomainGateError):
        return
    assert not ok


# -------------------------------------------------------------------
# Probe tooling (offline halves — no network)
# -------------------------------------------------------------------


def test_probe_writer_records_and_verifies(tmp_path):
    """A probe record + stored body verifies; a tampered body fails."""
    from tooling.m102_atlas_probe import record_probe, verify_probe_log

    body = b"<html>BOLETIN</html>"
    rec = record_probe(
        evidence_dir=tmp_path,
        domain_id="ES-XX",
        probe_id="portal",
        surface_id="portal",
        kind="portal",
        url="https://example.test/boletin",
        body=body,
        http_status=200,
        content_type="text/html",
        marker=b"BOLETIN",
        runner_network="fixture",
        now=lambda: "2026-09-18T00:00:00Z",
    )
    assert rec["raw_sha256"] == hashlib.sha256(body).hexdigest()
    assert rec["fetch_outcome"] == "SUCCESS"

    ok, rows = verify_probe_log(tmp_path)
    assert ok, rows

    # tamper: stored bytes no longer match the recorded digest
    (tmp_path / "portal.body").write_bytes(b"changed")
    ok, rows = verify_probe_log(tmp_path)
    assert not ok


def test_probe_writer_soft_404_and_marker_miss(tmp_path):
    from tooling.m102_atlas_probe import record_probe

    rec = record_probe(
        evidence_dir=tmp_path,
        domain_id="ES-XX",
        probe_id="doc",
        surface_id="doc",
        kind="document",
        url="https://example.test/doc/1",
        body=b"<html>nothing here</html>",
        http_status=200,
        content_type="text/html",
        marker=b"<disposicion",
        soft_404_marker=b"nothing here",
        runner_network="fixture",
        now=lambda: "2026-09-18T00:00:00Z",
    )
    assert rec["fetch_outcome"] == "SOFT_404"
    assert rec["reachability_observed"] == "REACHABLE"
    assert rec["content_marker_ok"] is False
