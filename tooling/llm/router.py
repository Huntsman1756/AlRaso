"""tooling/llm/router.py — stdlib-only free-LLM router for auxiliary tasks.

Isolated from `alraso/` core. It is NEVER a source of legal evidence. Its output
is only a hint that must flow through SOURCE_DISCOVERY -> OFFICIAL_SOURCE ->
EXISTING_REVIEW_PIPELINE before anything becomes verified.

Design:
  - stdlib only (urllib + json + hashlib + time + os).
  - OpenAI-compatible /chat/completions POST; no OpenAI SDK, no adapters.
  - Fallback: PRIMARY -> FALLBACK_1 -> FALLBACK_2, at most 1 attempt each.
  - Timeout capped at 30 s. No loops, no retry storms.
  - Secrets come only from env vars (never providers.json, never logs).
  - Logs only safe metadata to runs.jsonl (which is gitignored).

Usage:
  from tooling.llm.router import run_llm
  result = run_llm("oss_discovery", "Find OSS for offline MapLibre + PMTiles.")
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROVIDERS_PATH = HERE / "providers.json"
RUNS_PATH = HERE / "runs.jsonl"

DEFAULT_TIMEOUT_S = 30
MAX_ATTEMPTS_PER_PROVIDER = 1
_MAX_TIMEOUT_S = 30


class LlmRouterError(Exception):
    """Base error for the router (not surfaced as a crash; maps to error_class)."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_providers() -> dict:
    try:
        return json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - config error
        raise LlmRouterError(f"providers.json unreadable: {exc}") from exc


def _get_key(env_key: str) -> str:
    return (os.environ.get(env_key) or "").strip()


def _extract_content(raw: str) -> str:
    """Best-effort extraction of the assistant text from an OpenAI-style body."""
    data = json.loads(raw)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRouterError("unexpected response shape") from exc


def _post_chat(base_url: str, api_key: str, model: str, prompt: str,
               timeout: int) -> tuple[str, int]:
    """POST to an OpenAI-compatible chat completions endpoint. Returns (raw, status).

    Kept as a module-level function so tests can monkeypatch it (no network).
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return raw, resp.status


def _log(entry: dict) -> None:
    """Append one line of safe metadata to runs.jsonl. Never stores prompts/responses."""
    if not entry:
        return
    try:
        with RUNS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:  # pragma: no cover - logging must never break a call
        pass


def _metadata(task: str, provider: str, model: str, latency_ms: int, success: bool,
              error_class: str | None, prompt: str, response: str | None) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "task": task,
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "success": success,
        "error_class": error_class,
        "prompt_sha256": _sha256(prompt),
        "response_sha256": _sha256(response or ""),
    }


def _attempt(provider_id: str, prov: dict, task: str, prompt: str, timeout: int,
             log: bool) -> dict | None:
    """One attempt. Returns a structured result, or None on failure."""
    key = _get_key(prov.get("env_key", ""))
    if not key:
        return None
    model = prov.get("model")
    base_url = prov.get("base_url")
    started = time.monotonic()
    try:
        raw, _status = _post_chat(base_url, key, model, prompt, timeout)
        content = _extract_content(raw)
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        error_class = "RATE_LIMIT" if exc.code == 429 else f"HTTP_{exc.code}"
        if log:
            _log(_metadata(task, provider_id, model, latency_ms, False, error_class,
                           prompt, None))
        return {"provider": provider_id, "model": model, "success": False,
                "latency_ms": latency_ms, "response": None, "error": error_class}
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        error_class = "TIMEOUT" if isinstance(exc, (socket.timeout, TimeoutError)) else "NETWORK"
        if log:
            _log(_metadata(task, provider_id, model, latency_ms, False, error_class,
                           prompt, None))
        return {"provider": provider_id, "model": model, "success": False,
                "latency_ms": latency_ms, "response": None, "error": error_class}
    except (json.JSONDecodeError, LlmRouterError, KeyError, TypeError, ValueError) as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        error_class = "BAD_RESPONSE"
        if log:
            _log(_metadata(task, provider_id, model, latency_ms, False, error_class,
                           prompt, None))
        return {"provider": provider_id, "model": model, "success": False,
                "latency_ms": latency_ms, "response": None, "error": error_class}
    except Exception:  # noqa: BLE001 - fail-closed to a structured error
        latency_ms = int((time.monotonic() - started) * 1000)
        error_class = "UNKNOWN"
        if log:
            _log(_metadata(task, provider_id, model, latency_ms, False, error_class,
                           prompt, None))
        return {"provider": provider_id, "model": model, "success": False,
                "latency_ms": latency_ms, "response": None, "error": error_class}

    latency_ms = int((time.monotonic() - started) * 1000)
    if log:
        _log(_metadata(task, provider_id, model, latency_ms, True, None, prompt, content))
    return {"provider": provider_id, "model": model, "success": True,
            "latency_ms": latency_ms, "response": content, "error": None}


def run_llm(task: str, prompt: str, timeout: int = DEFAULT_TIMEOUT_S,
            log: bool = True) -> dict:
    """Route a prompt to the first provider with credentials, with a bounded fallback.

    Returns a structured dict:
      {provider, model, success, latency_ms, response, error}
    """
    if timeout <= 0:
        timeout = DEFAULT_TIMEOUT_S
    timeout = min(timeout, _MAX_TIMEOUT_S)

    cfg = _load_providers()
    providers = cfg.get("providers", {})
    order = cfg.get("order", [])
    if not order:
        order = list(providers.keys())

    total_started = time.monotonic()
    last_error = None
    saw_any_key = False

    for provider_id in order:
        prov = providers.get(provider_id)
        if not prov or not prov.get("enabled", True):
            continue
        if not _get_key(prov.get("env_key", "")):
            continue  # no credential for this provider: skip, not a failure yet
        saw_any_key = True
        for _ in range(MAX_ATTEMPTS_PER_PROVIDER):
            result = _attempt(provider_id, prov, task, prompt, timeout, log)
            if result is None:
                continue
            if result["success"]:
                return result
            last_error = result
            break  # exactly one attempt per provider

    if not saw_any_key:
        total_ms = int((time.monotonic() - total_started) * 1000)
        if log:
            _log(_metadata(task, None, None, total_ms, False, "NO_CREDENTIALS", prompt, None))
        return {"provider": None, "model": None, "success": False,
                "latency_ms": total_ms, "response": None, "error": "NO_CREDENTIALS"}

    total_ms = int((time.monotonic() - total_started) * 1000)
    if last_error:
        if log:
            _log(_metadata(task, last_error["provider"], last_error["model"], total_ms,
                           False, "ALL_PROVIDERS_FAILED", prompt, None))
        return {"provider": last_error["provider"], "model": last_error["model"],
                "success": False, "latency_ms": total_ms, "response": None,
                "error": "ALL_PROVIDERS_FAILED"}
    # Defensive: enabled providers but nothing attempted (all disabled).
    if log:
        _log(_metadata(task, None, None, total_ms, False, "NO_AVAILABLE_PROVIDER", prompt, None))
    return {"provider": None, "model": None, "success": False,
            "latency_ms": total_ms, "response": None, "error": "NO_AVAILABLE_PROVIDER"}


def llm_status() -> str:
    """Returns the provider file status field, e.g. CONFIGURED_NOT_LIVE."""
    return _load_providers().get("status", "UNKNOWN")


def _cli_main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Free-LLM auxiliary router (stdlib only)")
    parser.add_argument("--task", default="adhoc")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()
    result = run_llm(args.task, args.prompt, timeout=args.timeout, log=not args.no_log)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":  # pragma: no cover - manual CLI
    raise SystemExit(_cli_main())
