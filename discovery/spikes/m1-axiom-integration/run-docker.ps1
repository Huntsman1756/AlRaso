# Runs the FULL AlRaso test suite (including the real-Axiom integration tests)
# in Docker, using the Linux x86_64 binary previously built under rust:1-slim.
#
# Preconditions:
#   * Docker running.
#   * Binary at  $env:TEMP\opencode\axiom-rules-engine\target\release\axiom-rules-engine
#     (ELF Linux x86_64; if missing, rebuild once inside rust:1-slim via
#     `cargo build --release` in a clone of the axiom-rules-engine repository).
#   * Repo root is the current directory (or pass -Repo).
param([string]$Repo = (Get-Location).Path)

$scratch = Join-Path $env:TEMP "opencode"
$bin = Join-Path $scratch "axiom-rules-engine\target\release\axiom-rules-engine"
if (-not (Test-Path -LiteralPath $bin)) {
    Write-Error "Axiom Linux binary not found at $bin - see header for how to build it."
    exit 1
}

docker run --rm -v "${Repo}:/repo" -v "${scratch}:/work" -w /repo `
  -e "ALRASO_AXIOM_BIN=/work/axiom-rules-engine/target/release/axiom-rules-engine" `
  -e "ALRASO_AXIOM_ROOT=/work/rs_root/rulespec-es" `
  python:3.12-slim bash -c "mkdir -p /work/rs_root/rulespec-es && pip install --quiet pyyaml pytest && python -m pytest -q"
