"""Hermetic tests for tooling/llm/router.py.

No network: `_post_chat` is monkeypatched. These prove the bounded fallback,
the structured output contract, secret-only env config, and the safe-metadata
logging invariant.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from tooling.llm import router as llm_router


def _openai_body(content: str) -> str:
    return json.dumps({"choices": [{"message": {"content": content}}]})


def _fake_success_primary(base_url: str, api_key: str, model: str, prompt: str,
                          timeout: int):
    assert "groq" in base_url
    return _openai_body("primary answer"), 200


def test_run_llm_success_primary(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm_router, "_post_chat", _fake_success_primary)

    result = llm_router.run_llm("oss_discovery", "Find OSS for offline maps.", log=False)

    assert result["success"] is True
    assert result["provider"] == "groq"
    assert result["model"] == "openai/gpt-oss-120b"
    assert result["response"] == "primary answer"
    assert result["error"] is None
    assert result["latency_ms"] >= 0


def test_run_llm_falls_back_to_cerebras_on_429(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("CEREBRAS_API_KEY", "dummy")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _fake(base_url, api_key, model, prompt, timeout):
        if "groq" in base_url:
            raise urllib.error.HTTPError(base_url, 429, "Too Many Requests", {}, None)
        assert "cerebras" in base_url
        return _openai_body("fallback answer"), 200

    monkeypatch.setattr(llm_router, "_post_chat", _fake)

    result = llm_router.run_llm("oss_discovery", "prompt", log=False)

    assert result["success"] is True
    assert result["provider"] == "cerebras"
    assert result["response"] == "fallback answer"


def test_run_llm_no_credentials_returns_no_credentials(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = llm_router.run_llm("oss_discovery", "prompt", log=False)

    assert result["success"] is False
    assert result["error"] == "NO_CREDENTIALS"
    assert result["provider"] is None


def test_run_llm_all_providers_fail(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("CEREBRAS_API_KEY", "dummy")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")

    def _fake(base_url, api_key, model, prompt, timeout):
        raise urllib.error.HTTPError(base_url, 500, "Server Error", {}, None)

    monkeypatch.setattr(llm_router, "_post_chat", _fake)

    result = llm_router.run_llm("oss_discovery", "prompt", log=False)

    assert result["success"] is False
    assert result["error"] == "ALL_PROVIDERS_FAILED"


def test_run_llm_bad_response_marks_error_class(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")

    def _fake(base_url, api_key, model, prompt, timeout):
        return "not json", 200

    monkeypatch.setattr(llm_router, "_post_chat", _fake)

    result = llm_router.run_llm("oss_discovery", "prompt", log=False)

    assert result["success"] is False
    assert result["error"] in ("ALL_PROVIDERS_FAILED", "BAD_RESPONSE")


def test_run_llm_logs_only_safe_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    runlog = tmp_path / "runs.jsonl"
    monkeypatch.setattr(llm_router, "RUNS_PATH", runlog)
    monkeypatch.setattr(llm_router, "_post_chat", _fake_success_primary)

    result = llm_router.run_llm("oss_discovery", "secret-prompt-text", log=True)

    assert result["success"] is True
    line = json.loads(runlog.read_text(encoding="utf-8").strip())
    assert line["task"] == "oss_discovery"
    assert line["provider"] == "groq"
    assert line["success"] is True
    assert "prompt_sha256" in line and "response_sha256" in line
    # The log must never contain the raw prompt or response text.
    assert "secret-prompt-text" not in runlog.read_text(encoding="utf-8")
    assert "primary answer" not in runlog.read_text(encoding="utf-8")


def test_run_llm_timeout_is_bounded(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    called = {}

    def _fake(base_url, api_key, model, prompt, timeout):
        called["timeout"] = timeout
        return _openai_body("ok"), 200

    monkeypatch.setattr(llm_router, "_post_chat", _fake)

    # Request a huge timeout; the router must clamp it to the max (30 s).
    result = llm_router.run_llm("oss_discovery", "prompt", timeout=99999, log=False)

    assert result["success"] is True
    assert called["timeout"] == llm_router._MAX_TIMEOUT_S
