"""docs/LEGAL-ASSURANCE-MODEL.md — mandated token assertions.

This test asserts the presence of required literal tokens and the absence of
misleading-claim patterns in the legal assurance model document.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_doc() -> str:
    return (ROOT / "docs" / "LEGAL-ASSURANCE-MODEL.md").read_text(encoding="utf-8")


# ---- Required tokens (must be present) ---------------------------------------

_REQUIRED_TOKENS = [
    "CATALA_ROLE=ENGINE_DIFFERENTIAL_TESTING",
    "CATALA_CAN_DETECT=ENGINE_OR_SEMANTIC_DIVERGENCE",
    "CATALA_CANNOT_DETECT=FALSE_LEGAL_PREMISE_BY_ITSELF",
    "VERIFIED_SOURCE != TRUE_INTERPRETATION",
    "TEST_PASS != LEGAL_TRUTH",
    "DIFFERENTIAL_ENGINE_AGREEMENT != LEGAL_TRUTH",
    "APPLICABLE_DOCUMENT != APPLICABLE_PRECEPT",
    "CONSOLIDATED_TEXT_ROLE=DISCOVERY_AND_READING_AID",
    "PRIMARY_GAZETTE_ROLE=AUTHORITY_FOR_VERIFIED_REDACTION",
    "LEGALIZE_ES_ROLE=CANDIDATE_DISCOVERY_AND_CHANGE_SIGNAL",
    "LEGALIZE_ES_AUTHORITY=NONE",
    "LEGALIZE_ES_AUTO_PUBLISH=FORBIDDEN",
    "SIGNAL=YES",
    "EVIDENCE=NO",
    "NORM_VALIDITY_COVERAGE",
    "PRECEPT_LEVEL_NORMATIVE_BASIS",
    "NORMATIVE_BASIS_MISSING",
    "NORMATIVE_VALIDITY_UNKNOWN",
    "NORMATIVE_BASIS_OUTSIDE_VALIDITY",
    "NORMATIVE_PRECEPT_MISSING",
    "RULE_INTERVAL_CHECK=DIAGNOSTIC_REPORTED_NOT_ENFORCED",
    "ACTIVITY_DATE_RUNTIME_GATE=ENFORCED",
    "ORDESA_2500_ONLY_SHORTCUT=FORBIDDEN",
    "CORPUS_DEFECT",
    "GORIZ_LIVE_TRIGGER_PUBLICATION_BLOCKED=REVIEW_REQUIRED",
    "GORIZ_QUOTA_TEMPORAL_WINDOWS=DOCUMENTED",
    "GORIZ_QUOTA_ENFORCEMENT=NOT_IMPLEMENTED",
]


def test_required_tokens_present():
    """All mandated tokens must appear literally in the doc."""
    text = _read_doc()
    for token in _REQUIRED_TOKENS:
        assert token in text, f"Missing required token: {token!r}"


# ---- Mapping rows (three specific pairs) -------------------------------------

_MAPPING_PAIRS = [
    ("ENGINE_DIFFERENTIAL_TESTING", "Garantía de implementación"),
    ("NORM_VALIDITY", "Garantía estructural"),
    ("HUMAN_REVIEW", "Garantía de interpretación"),
]


def test_mapping_rows_present():
    """Three mapping rows must each contain both columns."""
    text = _read_doc()
    for key, role in _MAPPING_PAIRS:
        assert key in text, f"Mapping row key missing: {key!r}"
        assert role in text, f"Mapping row role missing: {role!r} (for {key!r})"


# ---- Forbidden misleading-claim patterns -------------------------------------

# These regexes must NOT match — except inside the explicit rejection sentence.
_FORBIDDEN_PATTERNS = [
    # Claims Catala/Axiom would have caught false premises
    re.compile(r"(?i)(catala|axiom)[^\n]{0,80}(habr[ií]a detectado|would have caught)", re.DOTALL),
    # Claims differential testing proves legal truth
    re.compile(r"(?i)differential (testing|engine agreement)[^\n]{0,40}(proves|demuestra)[^\n]{0,40}(correcci|truth)", re.DOTALL),
]


def test_no_misleading_claims():
    """No misleading claims about motor detection of legal falsehoods."""
    text = _read_doc()
    for pat in _FORBIDDEN_PATTERNS:
        matches = pat.findall(text)
        assert matches == [], f"Found misleading pattern: {matches}"