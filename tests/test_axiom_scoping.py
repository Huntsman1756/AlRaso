"""F02/F23 — Axiom adapter scope: honest capabilities, rejection of
unsupported constructs (conditions/multi-rule/effects), preserved identity,
normalized engine errors, atomic and invalidated cache."""

from __future__ import annotations

import hashlib
import json
import threading

import pytest

from alraso.engine_axiom import (
    AXIOM_PARITY,
    AXIOM_STATUS,
    PARITY_CLAIM,
    RULESPEC_CONTRACT_VERSION,
    AxiomCliAdapter,
    _parse,
    generate_rulespec,
)
from alraso.errors import (
    EngineBinaryNotFound,
    EngineInvalidJson,
    EngineSchemaMismatch,
    UnsupportedEngineCapability,
)
from conftest import make_version


def adapter(tmp_path) -> AxiomCliAdapter:
    # binary intentionally bogus: unsupported-capability paths must fail
    # BEFORE any subprocess use; supported paths here are exercised via
    # compiler injection (the real binary is covered in the Docker run).
    root = tmp_path / "rulespec-es"
    return AxiomCliAdapter(str(tmp_path / "no-such-axiom-binary"), root,
                           tmp_path / "cache")


def compiler_ok(path):
    path.write_text(json.dumps({"compiled": True}), encoding="utf-8")


def test_status_constants_are_honest():
    assert AXIOM_STATUS == "EXPERIMENTAL_ADAPTER"
    assert AXIOM_PARITY == "NOT_PROVEN"
    assert PARITY_CLAIM is False


def test_capabilities_are_restricted_and_declared(tmp_path):
    caps = adapter(tmp_path).capabilities()
    assert caps.supports_condition_kinds == frozenset()
    assert caps.supports_multiple_rules is False
    assert caps.supports_effects == frozenset({"PERMITTED", "PROHIBITED"})
    assert caps.supports_rule_identity is True


def test_root_naming_hard_requirement(tmp_path):
    with pytest.raises(Exception):
        AxiomCliAdapter("bin", tmp_path / "wrong-name", tmp_path / "c")


@pytest.mark.parametrize("version_kw,reason_fragment", [
    ({"condition": {"const": True}}, "conditions"),
    ({"condition": {"field": "altitude_m", "op": "gte", "value": 1}}, "conditions"),
    ({"effect": "AUTHORIZATION_REQUIRED"}, "AUTHORIZATION_REQUIRED"),
])
def test_generate_rulespec_refuses_unencodable(tmp_path, version_kw, reason_fragment):
    v = make_version(**version_kw)
    with pytest.raises(UnsupportedEngineCapability) as e:
        generate_rulespec(v)
    assert reason_fragment.lower() in str(e.value).lower()


def test_conditions_never_silently_ignored(tmp_path):
    a = adapter(tmp_path)
    v = make_version(condition={"field": "inside_park", "op": "is_true"})
    with pytest.raises(UnsupportedEngineCapability):
        a.evaluate([v], {"inside_park": True})


def test_multiple_versions_refused(tmp_path):
    a = adapter(tmp_path)
    vs = [make_version(seq=1), make_version(seq=2, rule_id="alraso:es:t/m#b")]
    with pytest.raises(UnsupportedEngineCapability):
        a.evaluate(vs, {})


def test_missing_binary_maps_to_normalized_error(tmp_path):
    a = adapter(tmp_path)
    with pytest.raises(EngineBinaryNotFound):
        a.evaluate([make_version()], {})


def test_parse_preserves_identity_and_checks_consistency(tmp_path):
    v = make_version(rule_id="alraso:es:t/id#real", seq=42, effect="PROHIBITED")
    module_id = "es:policies/vivac/ksTEST"

    def out(perm, proh, unico="holds"):
        return json.dumps({"results": [{"outputs": {
            f"{module_id}#status_permitted": {"outcome": perm},
            f"{module_id}#status_prohibited": {"outcome": proh},
            f"{module_id}#resolucion_unica": {"outcome": unico}}}]})

    good = out("not_holds", "holds")
    j = _parse(module_id, good, v).judgments[0]
    assert j.rule_id == "alraso:es:t/id#real" and j.rule_version_id == 42
    assert j.effect == "PROHIBITED"
    # disagreement between engine and bitemporal selection
    with pytest.raises(EngineSchemaMismatch):
        _parse(module_id, out("holds", "not_holds"), v)
    # missing keys
    with pytest.raises(EngineSchemaMismatch):
        _parse(module_id, json.dumps({"results": [{"outputs": {}}]}), v)
    # invalid json
    with pytest.raises(EngineInvalidJson):
        _parse(module_id, "this is not json", v)
    # resolucion_unica not holding -> never a silent pick
    with pytest.raises(EngineSchemaMismatch):
        _parse(module_id, out("holds", "holds", "not_holds"), v)


def test_cache_invalidates_on_content_change(tmp_path):
    a = adapter(tmp_path)
    _, y1 = generate_rulespec(make_version(rule_id="alraso:es:t/c1#a", seq=1))
    ref1 = a.compile_bundle(y1, "es:policies/vivac/m1", compiler=compiler_ok)
    _, y2 = generate_rulespec(make_version(rule_id="alraso:es:t/c1#a", seq=2,
                                           effect="PROHIBITED"))
    ref2 = a.compile_bundle(y2, "es:policies/vivac/m2", compiler=compiler_ok)
    assert ref1.path != ref2.path


def test_cache_key_embeds_axiom_version(tmp_path):
    a1 = AxiomCliAdapter("bin", tmp_path / "rulespec-es", tmp_path / "c1",
                         axiom_version="v1")
    a2 = AxiomCliAdapter("bin", tmp_path / "rulespec-es", tmp_path / "c2",
                         axiom_version="v2")
    _, y = generate_rulespec(make_version())
    r1 = a1.compile_bundle(y, "es:policies/vivac/ck", compiler=compiler_ok)
    r2 = a2.compile_bundle(y, "es:policies/vivac/ck", compiler=compiler_ok)
    assert r1.path != r2.path


def test_corrupt_cache_is_detected_and_recompiled(tmp_path):
    a = adapter(tmp_path)
    _, y = generate_rulespec(make_version())
    calls = []

    def compiler(path):
        calls.append(1)
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")

    a.compile_bundle(y, "es:policies/vivac/xx", compiler=compiler)
    art = list(a.cache.glob("*.compiled.json"))[0]
    art.write_text("{corrupt", encoding="utf-8")
    ref = a.compile_bundle(y, "es:policies/vivac/xx", compiler=compiler)
    assert len(calls) == 2
    json.loads(ref.path.read_text(encoding="utf-8"))


def test_cache_hit_does_not_recompile(tmp_path):
    a = adapter(tmp_path)
    _, y = generate_rulespec(make_version())
    calls = []

    def compiler(path):
        calls.append(1)
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")

    r1 = a.compile_bundle(y, "es:policies/vivac/hh", compiler=compiler)
    r2 = a.compile_bundle(y, "es:policies/vivac/hh", compiler=compiler)
    assert len(calls) == 1 and r1.path == r2.path
    assert json.loads(r2.path.read_text(encoding="utf-8")) == {"ok": True}


def test_concurrent_writers_publish_atomically(tmp_path):
    a = adapter(tmp_path)
    _, y = generate_rulespec(make_version())
    errors = []

    def writer():
        try:
            a.compile_bundle(y, "es:policies/vivac/cc", compiler=compiler_ok)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    arts = list(a.cache.glob("*.compiled.json"))
    assert len(arts) == 1
    assert json.loads(arts[0].read_text(encoding="utf-8")) == {"compiled": True}
    assert list(a.cache.glob("*.tmp")) == []


def test_atomic_publish_never_exposes_torn_artifacts(tmp_path):
    a = adapter(tmp_path)
    final = tmp_path / "out.json"
    payloads = [json.dumps({"w": i, "padding": "x" * 4096}) for i in range(8)]

    def writer(payload):
        tmp = tmp_path / f"t-{hashlib.sha1(payload.encode()).hexdigest()[:6]}.tmp"
        tmp.write_text(payload, encoding="utf-8")
        a._atomic_publish(tmp, final)

    threads = [threading.Thread(target=writer, args=(p,)) for p in payloads]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    data = json.loads(final.read_text(encoding="utf-8"))
    assert data in [json.loads(p) for p in payloads]


def test_binary_sha_pinning(tmp_path):
    fake = tmp_path / "axiom.bin"
    fake.write_bytes(b"binary-bytes")
    with pytest.raises(EngineBinaryNotFound):
        AxiomCliAdapter(str(fake), tmp_path / "rulespec-es", tmp_path / "c",
                        binary_sha256="0" * 64)
    good = hashlib.sha256(b"binary-bytes").hexdigest()
    AxiomCliAdapter(str(fake), tmp_path / "rulespec-es", tmp_path / "c",
                    binary_sha256=good)


def test_rulespec_contract_version_constant():
    assert RULESPEC_CONTRACT_VERSION == "rulespec/v1+m1r1"
