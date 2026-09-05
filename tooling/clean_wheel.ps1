# Clean-wheel install gate (M1 remediation F09).
# Builds the wheel, installs it into a FRESH venv OUTSIDE the checkout, and
# verifies: import, CLI help, and the installed-package smoke battery
# (tooling/smoke_installed.py: packaged fixture + F01/H1/H2/H3/H4 + honest
# status constants). CI runs the same smoke file.
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

Write-Host "== [1/4] build wheel (clean output dir) ==" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
& uv build --wheel --out-dir $dist $repo
$rc = $LASTEXITCODE
if ($rc -ne 0) { & python -m pip wheel --no-deps --wheel-dir $dist $repo; $rc = $LASTEXITCODE }
if ($rc -ne 0) { Write-Error "wheel build failed (need uv or python -m pip)"; exit 1 }
$wheel = (Get-ChildItem -LiteralPath $dist -Filter "alraso-*.whl" | Select-Object -First 1).FullName
Write-Host "wheel: $wheel"

Write-Host "== [2/4] fresh venv OUTSIDE the checkout ==" -ForegroundColor Cyan
& uv venv $venv --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed"; exit 1 }
$py = Join-Path $venv "Scripts\python.exe"
& uv pip install --python $py --quiet $wheel
if ($LASTEXITCODE -ne 0) { Write-Error "wheel install failed"; exit 1 }
if ($AxiomExtra) {
    & uv pip install --python $py --quiet "$wheel[axiom]"
    if ($LASTEXITCODE -ne 0) { Write-Error "axiom extra install failed"; exit 1 }
}

Write-Host "== [3/4] import + CLI help from outside the repo ==" -ForegroundColor Cyan
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

    Write-Host "== [4/4] installed-package smoke battery ==" -ForegroundColor Cyan
    # Single source of truth for the packaged-artifact behaviour: the same file
    # the CI gate runs (tooling/smoke_installed.py).
    & $py (Join-Path $repo "tooling\smoke_installed.py")
    if ($LASTEXITCODE -ne 0) { Write-Error "installed-package smoke failed"; exit 1 }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "CLEAN_WHEEL_GATE=PASS" -ForegroundColor Green
Write-Host "workdir kept at $work (delete manually to reclaim space)"
