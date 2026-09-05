# Clean-wheel install gate (M1 remediation F09).
# Builds the wheel, installs it into a FRESH venv OUTSIDE the checkout, and
# verifies: import, CLI help, packaged fixture, minimal OwnEvaluator resolve,
# and the hermetic smoke tests against the INSTALLED package.
#
# Usage:  powershell -ExecutionPolicy Bypass -File tooling\clean_wheel.ps1
# Optional: -AxiomExtra to also build an env with the alraso[axiom] extra
#           (PyYAML pinned by tooling\DEPENDENCIES.lock.json).

param(
    [switch]$AxiomExtra
)

$ErrorActionPreference = "Continue"  # native tools log to stderr; gates check $LASTEXITCODE
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$work = Join-Path $env:TEMP "alraso-clean-wheel"
if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
New-Item -ItemType Directory -Path $work | Out-Null
$venv = Join-Path $work "venv"
$dist = Join-Path $work "dist"

Write-Host "== [1/5] build wheel (clean output dir) ==" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
& uv build --wheel --out-dir $dist $repo
$rc = $LASTEXITCODE
if ($rc -ne 0) { & python -m pip wheel --no-deps --wheel-dir $dist $repo; $rc = $LASTEXITCODE }
if ($rc -ne 0) { Write-Error "wheel build failed (need uv or python -m pip)"; exit 1 }
$wheel = (Get-ChildItem -LiteralPath $dist -Filter "alraso-*.whl" | Select-Object -First 1).FullName
Write-Host "wheel: $wheel"

Write-Host "== [2/5] fresh venv OUTSIDE the checkout ==" -ForegroundColor Cyan
& uv venv $venv --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed"; exit 1 }
$py = Join-Path $venv "Scripts\python.exe"
& uv pip install --python $py --quiet $wheel
if ($LASTEXITCODE -ne 0) { Write-Error "wheel install failed"; exit 1 }
if ($AxiomExtra) {
    & uv pip install --python $py --quiet "$wheel[axiom]"
    if ($LASTEXITCODE -ne 0) { Write-Error "axiom extra install failed"; exit 1 }
}

Write-Host "== [3/5] import + CLI help from outside the repo ==" -ForegroundColor Cyan
$smoke = Join-Path $work "smoke"
New-Item -ItemType Directory -Path $smoke | Out-Null
Push-Location $smoke
try {
    & $py -c "import alraso; print('import ok, alraso at', alraso.__file__)"
    if ($LASTEXITCODE -ne 0) { Write-Error "import failed"; exit 1 }
    if ((& $py -c "import alraso,sys; print(alraso.__file__)") -notlike "*$venv*") {
        Write-Error "imported alraso from OUTSIDE the clean venv: gate would be dishonest"; exit 1
    }
    & $py -m alraso --help | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "cli help failed"; exit 1 }

    Write-Host "== [4/5] packaged fixture + minimal resolve (own evaluator) ==" -ForegroundColor Cyan
    $code = @'
import json
from alraso.bitemporal import BitemporalStore
from alraso.domain import Query
from alraso.ingest.ordesa import load_ordesa
from alraso.resolver import Resolver

store = BitemporalStore.connect(":memory:")
load_ordesa(store)  # packaged fixture via importlib.resources
r = Resolver(store)
pre = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2021-07-15",
                      knowledge_date="2023-06-15",
                      spatial_scope_id="ss-ordesa-sector-ordesa"))
post = r.resolve(Query(activity="VIVAC_AL_RASO", activity_date="2023-06-15",
                       knowledge_date="2023-06-15",
                       spatial_scope_id="ss-ordesa-sector-ordesa"))
assert pre.legal_status.value == "PERMITTED", pre.legal_status
assert post.legal_status.value == "PROHIBITED", post.legal_status
print("wheel smoke OK:", pre.legal_status.value, "/", post.legal_status.value)
'@
    $codeFile = Join-Path $smoke "smoke.py"
    Set-Content -LiteralPath $codeFile -Value $code -Encoding UTF8
    & $py $codeFile
    if ($LASTEXITCODE -ne 0) { Write-Error "resolve smoke failed"; exit 1 }

    Write-Host "== [5/5] safety smoke battery against the INSTALLED package ==" -ForegroundColor Cyan
    $safety = @'
from alraso.bitemporal import BitemporalStore
from alraso.domain import LegalStatus, Query
from alraso.errors import OverlappingRuleVersions
from alraso.resolver import Resolver
from alraso.engine_axiom import AXIOM_STATUS, AXIOM_PARITY

Q = dict(activity="VIVAC_AL_RASO", activity_date="2021-01-01", knowledge_date="2023-01-01",
         spatial_scope_id="s")

DOC = {"id": "sd", "authority": "A", "jurisdiction": "ES", "document_type": "T",
       "title": "T", "canonical_url": "https://example.test/t"}


def store_with_scope(relevance=None, fragment_status="VERIFIED"):
    store = BitemporalStore.connect(":memory:")
    scope = {"id": "s", "scope_type": "OTHER", "official_name": "S"}
    if relevance is not None:
        scope["relevance"] = relevance
    store.add_spatial_scope(scope)
    store.add_source_document(DOC)
    store.add_legal_fragment({"id": "lf", "source_document_id": "sd", "locator": "art. 1",
                              "review_status": fragment_status})
    return store


def add_rule(store, effect, rid, ef="2020-01-01", review="VERIFIED", evidence=("lf",)):
    store.add_rule_version({"rule_id": rid, "activity": "VIVAC_AL_RASO",
                            "spatial_scope_id": "s", "effect": effect,
                            "effective_from": ef, "recorded_at": "2020-06-01",
                            "review_status": review, "legal_review_complete": True,
                            "evidence": list(evidence)})


# F01: unreviewed rule cannot permit
store = store_with_scope()
add_rule(store, "PERMITTED", "alraso:es:t#w#rr", review="REVIEW_REQUIRED", evidence=())
res = Resolver(store).resolve(Query(**Q))
assert res.legal_status is LegalStatus.UNDETERMINED, "unreviewed rule permitted!"

# H1: two visible lineages of one rule_id with overlapping valid time are refused
store = store_with_scope()
add_rule(store, "PERMITTED", "alraso:es:t#w#ov")
try:
    add_rule(store, "PROHIBITED", "alraso:es:t#w#ov", ef="2020-06-01")
    raise AssertionError("overlapping rule versions were accepted")
except OverlappingRuleVersions:
    pass
assert Resolver(store).resolve(Query(**Q)).legal_status is LegalStatus.PERMITTED

# H2: a rule cannot be publishable on evidence that is not publishable
store = store_with_scope(fragment_status="DISCOVERED")
add_rule(store, "PERMITTED", "alraso:es:t#w#ev")
res = Resolver(store).resolve(Query(**Q))
assert res.legal_status is LegalStatus.UNDETERMINED, "unverified fragment permitted!"
assert "EVIDENCE_NOT_PUBLISHABLE" in res.reason_codes, res.reason_codes

# H3: an applicable REGULATORY scope with no publishable coverage is not permission
from alraso.spatial import InMemorySpatialProvider

store = BitemporalStore.connect(":memory:")
store.add_source_document({"id": "sd", "authority": "A", "jurisdiction": "ES",
                           "document_type": "T", "title": "T",
                           "canonical_url": "https://example.test/t"})
store.add_legal_fragment({"id": "lf", "source_document_id": "sd", "locator": "art. 1",
                          "review_status": "VERIFIED"})
for sid in ("s", "s2"):
    store.add_spatial_scope({"id": sid, "scope_type": "OTHER", "official_name": sid,
                             "geometry_source": "sd", "review_status": "VERIFIED"})
store.add_rule_version({"rule_id": "alraso:es:t#w#cov", "activity": "VIVAC_AL_RASO",
                        "spatial_scope_id": "s", "effect": "PERMITTED",
                        "effective_from": "2020-01-01", "recorded_at": "2020-06-01",
                        "review_status": "VERIFIED", "legal_review_complete": True,
                        "spatial_review_complete": True, "evidence": ["lf"]})
prov = InMemorySpatialProvider()
prov.add_scope("s", "s", "OTHER", [[(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]])
prov.add_scope("s2", "s2", "OTHER", [[(0.5, 0.5), (0.5, 1.5), (1.5, 1.5), (1.5, 0.5)]])
res = Resolver(store, spatial=prov).resolve(
    Query(activity="VIVAC_AL_RASO", activity_date="2021-01-01",
          knowledge_date="2023-01-01", lat=0.7, lon=0.7))
assert res.legal_status is LegalStatus.UNDETERMINED, "PERMITTED over uncovered jurisdiction"
assert "INCOMPLETE_SCOPE_COVERAGE" in res.reason_codes, res.reason_codes

# H4: malformed facts never escape as a traceback
store = store_with_scope()
add_rule(store, "PERMITTED", "alraso:es:t#w#ok")
res = Resolver(store).resolve(Query(**Q, facts="nope"))
assert res.legal_status is LegalStatus.UNDETERMINED and res.reason_codes, res
assert Resolver(store).resolve(Query(**Q)).legal_status is LegalStatus.PERMITTED

assert AXIOM_STATUS == "EXPERIMENTAL_ADAPTER" and AXIOM_PARITY == "NOT_PROVEN"
print("safety smoke OK: F01 unreviewed, H1 overlap, H2 fragment, H3 coverage, "
      "H4 malformed facts")
'@
    $safetyFile = Join-Path $smoke "safety_smoke.py"
    Set-Content -LiteralPath $safetyFile -Value $safety -Encoding UTF8
    & $py $safetyFile
    if ($LASTEXITCODE -ne 0) { Write-Error "safety smoke failed"; exit 1 }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "CLEAN_WHEEL_GATE=PASS" -ForegroundColor Green
Write-Host "workdir kept at $work (delete manually to reclaim space)"
