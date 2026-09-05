"""Axiom CLI adapter — EXPERIMENTAL, capability-scoped (M1 remediation F02).

Status constants (single source of truth, asserted by tests):

    AXIOM_STATUS = "EXPERIMENTAL_ADAPTER"
    AXIOM_PARITY = "NOT_PROVEN"
    PARITY_CLAIM = False

The adapter is deliberately restricted until a shared contract suite proves
parity with the own evaluator:

  * It encodes ONLY effect-asserting (unconditional) rule versions. A version
    carrying a condition is REJECTED with UnsupportedEngineCapability — the
    old behaviour (silently ignoring conditions) is exactly the forbidden
    "ignore condition and execute anyway" path and is gone.
  * Multiple simultaneously-active rules are not representable in the M1
    projection: supports_multiple_rules=False, and evaluate() refuses them.
  * AUTHORIZATION_REQUIRED is not encoded in the M1 RuleSpec projection:
    unsupported effect -> UnsupportedEngineCapability.
  * Judgment identity is preserved: the real rule_id and rule_version_id are
    carried on the judgment. Identity laundering (rule_id="axiom") is removed.

The wrapper never lets the engine override the bitemporal store: the compiled
projection re-derives the store-selected effect from the closed activity match
and the result is cross-checked; any disagreement fails closed.

Cache (F09-adjacent, hardened by H5/D5): publication is atomic (temp file +
fsync + os.replace). The cache identity is

    rulespec/compiler contract version
    + axiom version label
    + SHA-256 of the axiom BINARY itself
    + canonical RuleSpec/content hash

so two different binaries that claim the same version label can never share an
artifact. If the binary identity cannot be established (missing/unreadable
binary), NO cached artifact is reused: the artifact is written to a one-shot
path instead. A cached artifact is validated (parseable JSON) before reuse;
corrupt artifacts are recompiled.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alraso.bitemporal import VersionRow
from alraso.engine import EngineCapabilities, EngineResult, JudgmentResult
from alraso.errors import (
    EngineBinaryNotFound,
    EngineInvalidJson,
    EngineNonZeroExit,
    EngineSchemaMismatch,
    EngineTimeout,
    UnsupportedEngineCapability,
)

AXIOM_STATUS = "EXPERIMENTAL_ADAPTER"
AXIOM_PARITY = "NOT_PROVEN"
PARITY_CLAIM = False

RULESPEC_CONTRACT_VERSION = "rulespec/v1+m1r1"
MODULE_JUR = "es"  # projection namespace; durable IDs stay alraso:...
_KNOWN = ("VIVAC_AL_RASO", "FUNDA_VIVAC", "TIENDA_NOCTURNA", "TARP", "ACAMPADA",
          "PERNOCTA_REFUGIO", "VEHICULO")
_ENCODED_EFFECTS = frozenset({"PERMITTED", "PROHIBITED"})


def _match_formula() -> str:
    lines = ["match activity_name:"]
    lines += [f'    "{a}" => 1' for a in _KNOWN]
    lines.append("    _ => 0")
    return "\n".join(lines)


def _rule(name: str, dtype: str, formula: str) -> dict[str, Any]:
    return {"name": name, "kind": "derived", "entity": "Location", "dtype": dtype,
            "period": "Day", "versions": [{"effective_from": "2020-01-01", "formula": formula}]}


def assert_encodable(version: VersionRow) -> None:
    """Capability pre-check usable WITHOUT yaml/binary: the resolver and the
    adapter both reject before doing any engine work."""
    if version.condition is not None:
        raise UnsupportedEngineCapability(
            f"axiom projection cannot encode conditions (rule {version.rule_id} "
            f"seq {version.seq}); conditions are NOT silently ignored",
            detail={"rule_id": version.rule_id, "rule_version_id": version.seq})
    if version.effect not in _ENCODED_EFFECTS:
        raise UnsupportedEngineCapability(
            f"axiom projection encodes only PERMITTED/PROHIBITED, not {version.effect}",
            detail={"effect": version.effect})


def generate_rulespec(version: VersionRow) -> tuple[str, str]:
    """Project ONE unconditional rule version into a compilable RuleSpec.

    Raises UnsupportedEngineCapability for anything the M1 projection cannot
    faithfully encode (conditions, unmodelled effects). Never drops a
    condition silently.
    """
    assert_encodable(version)
    ks_payload = {
        "contract": RULESPEC_CONTRACT_VERSION,
        "rule_id": version.rule_id,
        "rule_version_id": version.seq,
        "activity": version.activity,
        "effect": version.effect,
    }
    ks = hashlib.sha256(json.dumps(ks_payload, sort_keys=True).encode()).hexdigest()[:12]
    module_id = f"{MODULE_JUR}:policies/vivac/ks{ks}"
    effect = version.effect

    permitted = "vivac_known == 1" if effect == "PERMITTED" else "vivac_known == 0"
    prohibited = "vivac_known == 0" if effect == "PERMITTED" else "vivac_known == 1"

    spec = {
        "format": "rulespec/v1",
        "module": {"summary": ("AlRaso wrapper projection (bitemporal-selected). NOT encoded law.\n"
                                f"knowledge-state {ks}; effect upstream = {effect}\n")},
        "rules": [
            _rule("vivac_known", "Integer", _match_formula()),
            _rule("status_permitted", "Judgment", permitted),
            _rule("status_prohibited", "Judgment", prohibited),
            _rule("resolucion_unica", "Judgment", "exactly_one(status_permitted, status_prohibited)"),
        ],
    }
    import yaml  # optional extra (alraso[axiom]): only needed to talk to Axiom

    return module_id, yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)


@dataclass
class CompiledRef:
    path: Path
    sha256: str
    knowledge_state: str


def _publish(src: Path, dst: Path, attempts: int = 100) -> None:
    """os.replace with bounded retry: Windows momentarily denies replacing
    a destination another thread/process has open. Atomicity is preserved in
    all cases: readers see only complete old-or-new content."""
    last: OSError | None = None
    for _ in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:  # transient share violation
            last = e
            time.sleep(0.01)
    raise last if last else OSError(f"publish failed: {src} -> {dst}")


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # best effort on platforms without dir fsync


class AxiomCliAdapter:
    name = "axiom-cli"

    def __init__(self, binary_path: str | Path, rulespec_root: str | Path,
                 cache_dir: str | Path, axiom_version: str = "unpinned",
                 binary_sha256: str | None = None) -> None:
        self.binary = str(binary_path)
        self.version = f"axiom-cli/{axiom_version}"
        self.axiom_version = axiom_version
        self.root = Path(rulespec_root)
        self.cache = Path(cache_dir)
        if not self.root.name.startswith("rulespec-"):
            raise EngineNonZeroExit(
                "rulespec root must be named rulespec-<country> (Axiom hard requirement)")
        if binary_sha256 is not None:
            self._verify_binary(binary_sha256)
            self.binary_sha256: str | None = binary_sha256
        else:
            # H5/D5: identity is never optional in the cache key. When the
            # caller did not pin it, we measure the binary we are about to
            # execute; if that is impossible, the identity stays None and the
            # cache is disabled for this adapter.
            self.binary_sha256 = self._observed_binary_sha256()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def _observed_binary_sha256(self) -> str | None:
        try:
            p = Path(self.binary)
            if not p.is_file():
                return None
            return hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            return None

    def cache_identity_verified(self) -> bool:
        return self.binary_sha256 is not None

    def _verify_binary(self, expected_sha256: str) -> None:
        p = Path(self.binary)
        if not p.exists():
            raise EngineBinaryNotFound(f"axiom binary not found: {self.binary}")
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != expected_sha256:
            raise EngineBinaryNotFound(
                f"axiom binary SHA-256 mismatch: got {digest}, pinned {expected_sha256}")

    def capabilities(self) -> EngineCapabilities:
        """Honest claim: effect-only single-version PERMITTED/PROHIBITED."""
        return EngineCapabilities(
            supports_activity=True,
            supports_condition_kinds=frozenset(),
            supports_condition_ops=frozenset(),
            supports_effects=frozenset(_ENCODED_EFFECTS),
            supports_multiple_rules=False,
            supports_explain=True,
            supports_rule_identity=True,
        )

    # ---- process handling (normalized errors) ---------------------------------
    def _run(self, argv: list[str], stdin: str | None = None) -> str:
        try:
            proc = subprocess.run(argv, input=stdin, text=True, capture_output=True,
                                  check=False, timeout=120)
        except FileNotFoundError as e:
            raise EngineBinaryNotFound(f"axiom binary not executable: {argv[0]}") from e
        except subprocess.TimeoutExpired as e:
            raise EngineTimeout(f"axiom timed out: {' '.join(argv[:2])}") from e
        if proc.returncode != 0:
            raise EngineNonZeroExit((proc.stderr or proc.stdout).strip()[:400])
        return proc.stdout

    # ---- atomic cache ----------------------------------------------------------
    def _cache_key(self, yaml_text: str) -> str:
        """Identity of a compiled artifact (H5/D5).

        Two binaries that claim the same version label produce different keys;
        an adapter whose binary identity cannot be established produces a key
        that is never reused (see compile_bundle)."""
        material = json.dumps({"contract": RULESPEC_CONTRACT_VERSION,
                               "axiom": self.axiom_version,
                               "axiom_binary_sha256": self.binary_sha256 or "unverified",
                               "yaml": hashlib.sha256(yaml_text.encode()).hexdigest()},
                              sort_keys=True)
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _artifact_valid(path: Path) -> bool:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return True
        except (OSError, ValueError):
            return False

    def _atomic_publish(self, tmp: Path, final: Path) -> None:
        with open(tmp, "a", encoding="utf-8") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        # The property under test is atomicity: readers never observe a torn
        # artifact, only complete old-or-new content. _publish retries the
        # transient Windows share violations.
        _publish(tmp, final)
        _fsync_dir(final)

    def compile_bundle(self, yaml_text: str, module_id: str,
                       compiler: Any | None = None) -> CompiledRef:
        """Compile with atomic, identity-keyed caching.

        ``compiler`` (tests) is a callable(tmp_path) writing the artifact;
        production uses the real binary. A cached artifact is validated before
        reuse; corrupt entries are discarded and recompiled. Concurrent writers
        are safe: only fully-fsynced temp files are os.replace()-d into place.

        Identity rule (H5/D5): reuse requires a VERIFIED binary identity. With
        no verifiable SHA-256 the adapter neither reads nor feeds the shared
        cache (one-shot artifact path), so an artifact compiled by an unknown
        binary can never answer for another one.
        """
        rel = module_id.replace(":", "/") + ".yaml"
        src = self.root / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        tmp_src = src.with_name(f".{src.stem}.{uuid.uuid4().hex}.tmp")
        tmp_src.write_text(yaml_text, encoding="utf-8")
        _publish(tmp_src, src)

        key = self._cache_key(yaml_text)
        verified = self.cache_identity_verified()
        if verified:
            artifact = self.cache / (key[:16] + ".compiled.json")
        else:
            artifact = self.cache / f"{key[:16]}.unverified-{uuid.uuid4().hex}.compiled.json"
        if verified and artifact.exists():
            if self._artifact_valid(artifact):
                return CompiledRef(path=artifact, sha256=key, knowledge_state=module_id)
            try:  # corrupt cache entry: drop and recompile
                artifact.unlink()
            except OSError:
                pass
        tmp = artifact.with_suffix(f".{os.getpid()}-{uuid.uuid4().hex}.tmp")
        if compiler is not None:
            compiler(tmp)
        else:
            self._run([self.binary, "compile", "--program", str(src),
                       "--rulespec-root", str(self.root), "--output", str(tmp)])
        if not self._artifact_valid(tmp):
            try:
                tmp.unlink()
            except OSError:
                pass
            raise EngineInvalidJson("axiom compile produced invalid JSON artifact")
        self._atomic_publish(tmp, artifact)
        return CompiledRef(path=artifact, sha256=key, knowledge_state=module_id)

    # ---- evaluation -------------------------------------------------------------
    def evaluate(self, versions: list[VersionRow], facts: dict[str, Any],
                 mode: str = "fast") -> EngineResult:
        if not versions:
            return EngineResult(judgments=[])
        if len(versions) > 1:
            raise UnsupportedEngineCapability(
                "axiom M1 projection handles a single active rule version; multiple "
                "active rules are rejected, never collapsed silently",
                detail={"rule_ids": sorted(v.rule_id for v in versions)})
        v = versions[0]
        assert_encodable(v)
        # binary availability checked BEFORE any encoding work: a missing
        # engine is a normalized failure, never a silent fallback
        if not os.path.exists(self.binary):
            raise EngineBinaryNotFound(f"axiom binary not found: {self.binary}")
        activity = facts.get("activity_name", v.activity)
        if activity not in _KNOWN:
            raise EngineSchemaMismatch(f"activity outside closed vocabulary: {activity}")
        module_id, yaml_text = generate_rulespec(v)
        compiled = self.compile_bundle(yaml_text, module_id)
        out = self._run([self.binary, "run-compiled", "--artifact", str(compiled.path)],
                        stdin=json.dumps(_request(module_id, activity)))
        return _parse(module_id, out, v)


def _request(module_id: str, activity: str) -> dict[str, Any]:
    inp = {"name": f"{module_id}#input.activity_name", "entity": "Location", "entity_id": "loc:p1",
           "interval": {"start": "2023-07-15", "end": "2023-07-16"},
           "value": {"kind": "text", "value": activity}}
    outputs = [f"{module_id}#status_permitted", f"{module_id}#status_prohibited",
               f"{module_id}#resolucion_unica"]
    q = {"entity_id": "loc:p1",
         "period": {"period_kind": "custom", "name": "day", "start": "2023-07-15", "end": "2023-07-16"},
         "outputs": outputs}
    return {"mode": "explain", "dataset": {"inputs": [inp]}, "queries": [q]}


def _parse(module_id: str, raw: str, version: VersionRow) -> EngineResult:
    try:
        doc = json.loads(raw)
        outputs = doc["results"][0]["outputs"]
    except (ValueError, KeyError, IndexError) as e:
        kind = EngineInvalidJson if isinstance(e, ValueError) else EngineSchemaMismatch
        raise kind(f"axiom output failed schema expectations: {e}") from e

    def outcome(name: str) -> str:
        node = outputs.get(f"{module_id}#{name}")
        if not isinstance(node, dict) or "outcome" not in node:
            raise EngineSchemaMismatch(f"axiom output missing {name!r}")
        return node["outcome"]

    if outcome("resolucion_unica") != "holds":
        raise EngineSchemaMismatch(
            "resolucion_unica did not hold (engine output self-inconsistent)",
            detail={"outputs": {k: v.get("outcome") if isinstance(v, dict) else None
                                for k, v in outputs.items()}})
    final = "PERMITTED" if outcome("status_permitted") == "holds" else "PROHIBITED"
    if final != version.effect:
        raise EngineSchemaMismatch(
            f"engine disagreed with bitemporal selection: {final} vs {version.effect}")
    # material identity preserved: real rule + version ids (no laundering)
    return EngineResult(judgments=[JudgmentResult(
        rule_id=version.rule_id, rule_version_id=version.seq, effect=final,
        outcome="holds",
        conditions=[{"kind": "axiom_explain", "engine": "axiom"}],
        trace=[f"axiom explain -> {final}"])])
