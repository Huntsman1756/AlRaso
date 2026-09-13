"""M10.1 Task 6 — minimal VersionResolver contract.

Boundary: produce a conservative VersionClaim from structured data only.
The pipeline produces evidence for human review, not legal rules — so in
M10.1 ``status`` is always REQUIRES_MANUAL_REVIEW (a candidate is not a
resolution) and ``effective_from`` is only populated from structured or
exactly preregistered effective-date evidence with a kept source fragment.
Free-text or ambiguous vacatio never becomes a date.
"""

import ast
import inspect
from pathlib import Path

import pytest

import pipeline.providers.version as version_mod
from pipeline.models import DocumentRef, VersionClaimStatus
from pipeline.profiles import SourceProfile, load_profile
from pipeline.providers.version import VersionError, resolve

ROOT = Path(__file__).resolve().parents[1]
PROFILE_JSON = ROOT / "pipeline" / "sources" / "bocyl.profile.json"

FIXED_NOW = "2026-09-13T14:00:00Z"


def _doc_ref() -> DocumentRef:
    return DocumentRef(
        source_id="bocyl",
        doc_id="BOCYL-D-15122025-1",
        published_on="2025-12-15",
        title="Decreto 17/2025 PRUG Picos",
        issuer="JCyL",
        discovery_url="https://bocyl.jcyl.es/x/BOCYL-D-15122025-1.xml",
    )


def _profile() -> SourceProfile:
    return load_profile(PROFILE_JSON)


def test_bocyl_claim_is_conservative():
    claim = resolve(_profile(), _doc_ref(), clock=lambda: FIXED_NOW)
    assert claim.doc_id == "BOCYL-D-15122025-1"
    assert claim.publication_date == "2025-12-15"
    # Free-text vacatio ("día siguiente a su publicación" + excepciones de
    # 3 años) never becomes an effective date automatically.
    assert claim.effective_from is None
    assert claim.effective_to is None
    assert claim.status is VersionClaimStatus.REQUIRES_MANUAL_REVIEW
    assert claim.consolidated_state is None
    assert claim.supersession == ()
    assert claim.recorded_at == FIXED_NOW
    assert claim.recorded_until is None


def test_preregistered_structured_evidence_yields_candidate():
    evidence = {
        "effective_from": "2025-12-16",
        "fragment": "entrará en vigor el día siguiente al de su publicación",
        "source": "disposicion final primera, Decreto 17/2025",
    }
    claim = resolve(
        _profile(),
        _doc_ref(),
        clock=lambda: FIXED_NOW,
        structured_evidence=evidence,
    )
    assert claim.effective_from == "2025-12-16"
    # Candidate, not resolution: human review still required in M10.1.
    assert claim.status is VersionClaimStatus.REQUIRES_MANUAL_REVIEW
    assert claim.resolver_evidence["fragment"] == evidence["fragment"]
    assert claim.resolver_evidence["source"] == evidence["source"]


def test_malformed_structured_evidence_fails_explicit():
    with pytest.raises(VersionError, match="effective_from"):
        resolve(
            _profile(),
            _doc_ref(),
            clock=lambda: FIXED_NOW,
            structured_evidence={
                "effective_from": "mañana",
                "fragment": "x",
            },
        )
    with pytest.raises(VersionError, match="fragment"):
        resolve(
            _profile(),
            _doc_ref(),
            clock=lambda: FIXED_NOW,
            structured_evidence={"effective_from": "2025-12-16"},
        )


def test_fragment_without_date_stays_null():
    claim = resolve(
        _profile(),
        _doc_ref(),
        clock=lambda: FIXED_NOW,
        structured_evidence={
            "fragment": "entrará en vigor el día siguiente al de su "
            "publicación en el BOCyL",
            "source": "disposicion final",
        },
    )
    assert claim.effective_from is None
    assert claim.status is VersionClaimStatus.REQUIRES_MANUAL_REVIEW
    assert claim.resolver_evidence["fragment"]


def test_consolidated_api_is_an_honest_stub():
    profile = SourceProfile(
        source_id="x",
        jurisdiction="ES-CT",
        kind="gazette",
        discovery={},
        fetch={},
        parse={},
        versioning={"strategy": "consolidated_api"},
        reachability={},
    )
    claim = resolve(profile, _doc_ref(), clock=lambda: FIXED_NOW)
    assert claim.status is VersionClaimStatus.REQUIRES_MANUAL_REVIEW
    assert claim.effective_from is None
    assert "consolidated_api" in claim.resolver_evidence["note"]


def test_unknown_strategy_fails_explicit():
    profile = SourceProfile(
        source_id="x",
        jurisdiction="ES-CL",
        kind="gazette",
        discovery={},
        fetch={},
        parse={},
        versioning={"strategy": "guess"},
        reachability={},
    )
    with pytest.raises(VersionError, match="guess"):
        resolve(profile, _doc_ref(), clock=lambda: FIXED_NOW)


def test_deterministic_output():
    a = resolve(_profile(), _doc_ref(), clock=lambda: FIXED_NOW)
    b = resolve(_profile(), _doc_ref(), clock=lambda: FIXED_NOW)
    assert a == b
    assert a.to_dict() == b.to_dict()


def test_no_network_and_no_layer_violations():
    tree = ast.parse(inspect.getsource(version_mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
    assert not imported & {"urllib", "http", "socket", "requests", "httpx"}
    src = inspect.getsource(version_mod)
    for layer in ("providers.discovery", "providers.fetch", "providers.parse"):
        assert layer not in src


def test_no_jurisdiction_branching():
    src = inspect.getsource(version_mod)
    assert "if jurisdiction" not in src
    assert "jurisdiction ==" not in src
