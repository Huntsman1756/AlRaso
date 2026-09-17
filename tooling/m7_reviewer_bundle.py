"""M7 blind reviewer bundle — build + blindness gate.

Builds the package the independent legal reviewer receives (protocol-v1
sections 5 and 7): ONLY reviewer-neutral case entries, the neutral legal
question, official primary-source references, reviewer instructions and the
public attestation template. Never engine data, fixtures, traces, expected
results or test assertions.

    python tooling/m7_reviewer_bundle.py build  --out-dir <dir>
    python tooling/m7_reviewer_bundle.py verify --dir <dir>

build:
    1. materializes the bundle files into <dir>:

       - main-set-v1.json       reviewer-facing subset of the pre-registered
                                main set (cases verbatim + neutral question +
                                scope + shared official source references).
                                Internal audit metadata (status,
                                pre_registered_at, blindness self-check block)
                                is NOT copied.
       - primary-sources.md     official primary-source references generated
                                from shared_references (BOCyL 17/2025,
                                BOPA 21/2026, BOC 57/2026, BOE Ley 16/1995,
                                RD 384/2002 + spatial sources IGN/CNIG
                                BDDAE/INSPIRE, OAPN WFS, IGN MDT25).
       - reviewer-instructions-v1.md            verbatim copy
       - reviewer-attestation-public.template.md verbatim copy
       - manifest.json          every included file + sha256 + bundle_sha256

    2. runs the blindness scan over EVERY file in <dir>. If any forbidden
       marker is found, the build FAILS (exit 1) and reports each hit.

verify:
    re-hashes every manifest-listed file, flags unexpected/extra files, and
    re-runs the blindness scan. Use it before shipping a bundle to the
    reviewer.

Exit codes: 0 ok; 1 build/verify failure or blindness violation; 2 usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M7_DIR = ROOT / "docs" / "validation" / "m7"
MAIN_SET = M7_DIR / "main-set-v1.json"
INSTRUCTIONS = M7_DIR / "reviewer-instructions-v1.md"
ATTESTATION = M7_DIR / "reviewer-attestation-public.template.md"

CASES_NAME = "main-set-v1.json"
SOURCES_NAME = "primary-sources.md"
MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "alraso-m7-reviewer-bundle-manifest-v1"
PROTOCOL = "M7 protocol-v1"

# Top-level keys of main-set-v1.json that are reviewer-neutral and therefore
# copied into the bundle. Internal audit metadata (status,
# pre_registered_at, the blindness self-check block) stays out: its field
# names are themselves forbidden markers in the scan below.
CASES_DOC_KEYS = (
    "schema",
    "protocol",
    "neutral_question",
    "scope",
    "shared_references",
    "cases",
)

# Forbidden markers (protocol-v1 section 5: the reviewer NEVER receives
# engine results, traces, encoded rules, fixtures, test assertions or
# expected answers). Each entry: (label, compiled regex over file text).
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("expected_engine_result", re.compile(r"expected_engine_result")),
    ("expected_reviewer_result", re.compile(r"expected_reviewer_result")),
    ("expected_result_field", re.compile(r"expected_(result|status|answer|outcome|legal_status)")),
    ("engine_output_field", re.compile(r"engine_(trace|output|result|determination|reason)")),
    ("resolver_output_field", re.compile(r"resolver_(output|trace|result|evidence)")),
    ("reason_codes", re.compile(r"reason_codes")),
    ("encoded_legal_rule", re.compile(r"LegalRule|legal_rule(_version)?")),
    ("repo_fixture_reference", re.compile(r"alraso/resources/fixture_|fixture_(picos|ordesa|goriz)")),
    ("alraso_import", re.compile(r"\b(import|from)\s+alraso\b")),
    ("test_assertion_reference", re.compile(r"pytest|tests/test_|conftest\.py")),
    ("author_knowledge_disclosure", re.compile(r"SAMPLE_AUTHOR_KNEW_ENGINE_OUTPUTS")),
    (
        "status_enum_as_expected_answer",
        re.compile(
            r"(expected|engine_result|correct_answer|answer)"
            r"[\w]*[\"']?\s*[:=]\s*[\"']?\s*"
            r"(PERMITTED|PROHIBITED|AUTHORIZATION_REQUIRED|UNDETERMINED|OUT_OF_SCOPE)"
        ),
    ),
]

# A reviewer bundle contains data and prose only: any code/test file is a
# violation regardless of content.
FORBIDDEN_FILENAME = re.compile(r"(^|/)(test_[^/]*|conftest)\.py$|\.py$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


# ---------------------------------------------------------------- bundle --


def _reviewer_cases_doc() -> dict:
    """Reviewer-facing subset of the pre-registered main set."""
    data = json.loads(MAIN_SET.read_text(encoding="utf-8"))
    missing = [k for k in CASES_DOC_KEYS if k not in data]
    if missing:
        raise SystemExit(f"bundle: main-set-v1.json missing keys {missing}")
    return {k: data[k] for k in CASES_DOC_KEYS}


def _primary_sources_md(cases_doc: dict) -> str:
    """Official primary-source list generated from shared_references so the
    bundle carries exactly the references the pre-registered corpus declares
    (no hand-edited second copy that can drift)."""
    refs = cases_doc["shared_references"]
    lines = [
        "# M7 reviewer bundle — fuentes primarias oficiales",
        "",
        "Autoridad unica: fuentes primarias oficiales. Materiales secundarios",
        "o consolidados solo como ayudas de descubrimiento, etiquetados como",
        "tales (protocol-v1 seccion 5).",
        "",
        "## Fuentes normativas primarias",
        "",
    ]
    for ref_id in sorted(refs.get("primary_sources", {})):
        r = refs["primary_sources"][ref_id]
        lines.append(f"### `{ref_id}`")
        lines.append("")
        for key in sorted(r):
            lines.append(f"- `{key}`: {r[key]}")
        lines.append("")
    lines.append("## Fuentes espaciales oficiales")
    lines.append("")
    for ref_id in sorted(refs.get("spatial_sources", {})):
        r = refs["spatial_sources"][ref_id]
        lines.append(f"### `{ref_id}`")
        lines.append("")
        for key in sorted(r):
            lines.append(f"- `{key}`: {r[key]}")
        lines.append("")
    return "\n".join(lines)


def _write_bundle(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_doc = _reviewer_cases_doc()

    written: list[Path] = []

    cases_path = out_dir / CASES_NAME
    cases_path.write_text(
        json.dumps(cases_doc, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    written.append(cases_path)

    sources_path = out_dir / SOURCES_NAME
    sources_path.write_text(_primary_sources_md(cases_doc), encoding="utf-8")
    written.append(sources_path)

    for src in (INSTRUCTIONS, ATTESTATION):
        dst = out_dir / src.name
        dst.write_bytes(src.read_bytes())
        written.append(dst)

    return written


def _write_manifest(out_dir: Path, files: list[Path]) -> Path:
    entries = []
    for p in sorted(files, key=lambda x: x.name):
        entries.append(
            {
                "path": p.name,
                "sha256": _sha256_file(p),
                "bytes": p.stat().st_size,
            }
        )
    bundle_material = "\n".join(
        f"{e['sha256']}  {e['path']}" for e in entries
    ).encode("utf-8")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "protocol": PROTOCOL,
        "generated_at": _utc_now_iso(),
        "bundle_sha256": _sha256_bytes(bundle_material),
        "files": entries,
    }
    manifest_path = out_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


# ------------------------------------------------------------- blindness --


def scan_dir(bundle_dir: Path) -> list[str]:
    """Scan EVERY file under bundle_dir for forbidden markers. Returns a list
    of human-readable findings (empty == blind)."""
    findings: list[str] = []
    for path in sorted(p for p in bundle_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(bundle_dir).as_posix()
        if FORBIDDEN_FILENAME.search(rel):
            findings.append(f"{rel}: forbidden filename (code/test file)")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, rx in FORBIDDEN_PATTERNS:
                if rx.search(line):
                    findings.append(
                        f"{rel}:{lineno}: forbidden marker [{label}]: "
                        f"{line.strip()[:160]}"
                    )
    return findings


def _report_scan(findings: list[str]) -> None:
    if findings:
        print("BLINDNESS_SCAN=FAIL")
        for f in findings:
            print(f"  FORBIDDEN {f}")
    else:
        print("BLINDNESS_SCAN=PASS")


# ------------------------------------------------------------------- cli --


def _cmd_build(args) -> int:
    out_dir = Path(args.out_dir)
    files = _write_bundle(out_dir)
    manifest_path = _write_manifest(out_dir, files)

    # Scan the WHOLE directory (including manifest.json and any pre-existing
    # stray files) so the bundle cannot ship contaminated.
    findings = scan_dir(out_dir)
    _report_scan(findings)
    if findings:
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"files: {len(manifest['files'])}")
    print(f"bundle_sha256: {manifest['bundle_sha256']}")
    print(f"manifest: {manifest_path}")
    return 0


def _cmd_verify(args) -> int:
    bundle_dir = Path(args.dir)
    manifest_path = bundle_dir / MANIFEST_NAME
    failures: list[str] = []
    if not manifest_path.is_file():
        print(f"verify: missing {MANIFEST_NAME} in {bundle_dir}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    listed = {e["path"] for e in manifest.get("files", [])}
    if MANIFEST_NAME in listed:
        failures.append(f"{MANIFEST_NAME} must not list itself")

    for entry in manifest.get("files", []):
        p = bundle_dir / entry["path"]
        if not p.is_file():
            failures.append(f"missing file {entry['path']}")
            continue
        actual = _sha256_file(p)
        if actual != entry.get("sha256"):
            failures.append(
                f"sha256 mismatch on {entry['path']}: "
                f"manifest={entry.get('sha256')} actual={actual}"
            )
        if p.stat().st_size != entry.get("bytes"):
            failures.append(f"size mismatch on {entry['path']}")

    on_disk = {
        p.relative_to(bundle_dir).as_posix()
        for p in bundle_dir.rglob("*")
        if p.is_file()
    } - {MANIFEST_NAME}
    for extra in sorted(on_disk - listed):
        failures.append(f"unexpected file not in manifest: {extra}")
    for gone in sorted(listed - on_disk):
        # already reported as missing above
        pass

    findings = scan_dir(bundle_dir)
    _report_scan(findings)

    for f in failures:
        print(f"  FAIL {f}")
    ok = not failures and not findings
    print(f"BUNDLE_VERIFY={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="m7_reviewer_bundle",
        description=(
            "Build/verify the M7 blind reviewer package (protocol-v1 "
            "section 5). The bundle contains ONLY reviewer-neutral case "
            "entries, official primary-source references, instructions and "
            "the attestation template -- never engine data, fixtures, "
            "traces or expected results."
        ),
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build the bundle + blindness gate")
    b.add_argument("--out-dir", required=True, help="target directory")
    b.set_defaults(fn=_cmd_build)

    v = sub.add_parser(
        "verify", help="re-verify manifest hashes + blindness scan"
    )
    v.add_argument("--dir", required=True, help="existing bundle directory")
    v.set_defaults(fn=_cmd_verify)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
