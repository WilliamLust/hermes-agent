#!/usr/bin/env python3
"""
Shared Ollama Client — retry, fallback, think:false handling.

All ebook factory agents should import from this module instead of
calling the Ollama API directly. This provides:

1. Automatic "think": false for 35B-a3b models (content lands in
   message.thinking, not message.content, without this flag)
2. Retry with exponential backoff on transient failures
3. Model fallback chain (e.g., 35B → 27B if primary fails)
4. Consistent OLLAMA_BASE_URL env override
5. Explicit model unloading to free VRAM

Usage:
    from ollama_client import ollama_call, ollama_call_with_retry, ollama_call_with_fallback, unload_model

    # Simple call with retry (3 attempts)
    result = ollama_call_with_retry(prompt, system, model="qwen3.5:27b-16k")

    # Call with model fallback chain
    result = ollama_call_with_fallback(prompt, system, preferred_model="qwen3.5:35b-a3b-q4_k_m")

    # Unload a model from VRAM
    unload_model("qwen3.5:35b-a3b-q4_k_m")
"""

import os
import sys
import time
import requests
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_BASE}/api/chat"
DEFAULT_TIMEOUT = 600  # 10 minutes

# Models that require "think": false (Qwen 3.5 models put output in thinking, not content)
# Without think:false, these models return empty message.content and put the
# actual response in message.thinking — this is the default Ollama behavior for
# models with thinking capability enabled.
THINKING_MODEL_PATTERNS = ["35b-a3b", "qwen3.5"]

# Default fallback chain: if primary model fails, try these in order
DEFAULT_FALLBACK_CHAIN = [
    "qwen3.5:27b-16k",   # Primary drafting model (17GB, 16k context)
]


def _needs_think_false(model: str) -> bool:
    """Check if a model requires 'think': false in the API payload.
    
    Qwen 3.5 models with thinking enabled return empty message.content
    and put the actual response in message.thinking unless think:false
    is explicitly set in the payload.
    """
    return any(pattern in model.lower() for pattern in THINKING_MODEL_PATTERNS)


def ollama_call(
    prompt: str,
    system: str = "",
    model: str = "qwen3.5:27b-16k",
    num_predict: int = 6000,
    temperature: float = 0.7,
    num_ctx: int = 16384,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Call Ollama API. Returns response text or None on failure.

    Automatically adds "think": false for 35B-a3b models.
    Validates that content is non-empty (detects thinking-only responses).
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
        },
    }

    # CRITICAL: 35B-a3b model puts output in message.thinking, not message.content
    # Without think:false, content comes back empty
    if _needs_think_false(model):
        payload["think"] = False

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("message", {}).get("content", "").strip()

        # Validate content is non-empty (detects thinking-only responses)
        if not content:
            thinking = data.get("message", {}).get("thinking", "")
            if thinking:
                # Model returned thinking but no content — think:false may not have worked
                print(f"  [ollama_client] WARNING: {model} returned thinking ({len(thinking)} chars) "
                      f"but empty content. Model may need think:false.", flush=True)
            return None

        # Check for done_reason=length (truncated output)
        done_reason = data.get("done_reason", "")
        if done_reason == "length":
            print(f"  [ollama_client] WARNING: Output truncated (done_reason=length). "
                  f"Consider increasing num_predict (current: {num_predict})", flush=True)
            # Still return content — caller can decide whether to retry

        return content

    except requests.ConnectionError:
        print(f"  [ollama_client] Connection refused at {OLLAMA_URL} — is Ollama running?", flush=True)
        return None
    except requests.Timeout:
        print(f"  [ollama_client] Request timed out after {timeout}s", flush=True)
        return None
    except requests.HTTPError as e:
        print(f"  [ollama_client] HTTP error: {e}", flush=True)
        return None
    except Exception as e:
        print(f"  [ollama_client] Unexpected error: {e}", flush=True)
        return None


def ollama_call_with_retry(
    prompt: str,
    system: str = "",
    model: str = "qwen3.5:27b-16k",
    max_retries: int = 3,
    base_delay: float = 5.0,
    **kwargs,
) -> str | None:
    """Call Ollama with exponential backoff retry.

    Retries on: connection errors, timeouts, empty responses.
    Does NOT retry on HTTP 4xx (client errors).

    Args:
        prompt: The user message
        system: System prompt
        model: Ollama model name
        max_retries: Maximum number of attempts (default 3)
        base_delay: Base delay in seconds (doubles each retry: 5s, 10s, 20s)
        **kwargs: Passed to ollama_call (num_predict, temperature, etc.)

    Returns:
        Response text or None if all retries fail.
    """
    for attempt in range(max_retries):
        result = ollama_call(prompt, system, model, **kwargs)
        if result is not None:
            if attempt > 0:
                print(f"  [ollama_client] Success on attempt {attempt + 1}", flush=True)
            return result

        reason = "empty response" if result is not None and not result else "connection/timeout"
        print(f"  [ollama_client] Attempt {attempt + 1}/{max_retries} failed ({reason})", flush=True)

        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            print(f"  [ollama_client] Retrying in {delay:.0f}s...", flush=True)
            time.sleep(delay)

    print(f"  [ollama_client] All {max_retries} attempts failed for model {model}", flush=True)
    return None


def ollama_call_with_fallback(
    prompt: str,
    system: str = "",
    preferred_model: str = "qwen3.5:35b-a3b-q4_k_m",
    fallback_chain: list[str] | None = None,
    max_retries: int = 2,
    **kwargs,
) -> str | None:
    """Call Ollama with model fallback chain.

    Tries the preferred model first, then falls back through
    alternative models if the primary fails.

    Args:
        prompt: The user message
        system: System prompt
        preferred_model: Primary model to try first
        fallback_chain: List of fallback models (default: 27B only)
        max_retries: Retries per model before falling back
        **kwargs: Passed to ollama_call

    Returns:
        Response text or None if all models fail.
    """
    chain = [preferred_model]
    if fallback_chain:
        chain += [m for m in fallback_chain if m != preferred_model]
    else:
        chain += [m for m in DEFAULT_FALLBACK_CHAIN if m != preferred_model]

    for i, model in enumerate(chain):
        result = ollama_call_with_retry(prompt, system, model, max_retries=max_retries, **kwargs)
        if result is not None:
            if model != preferred_model:
                print(f"  [ollama_client] Fell back from {preferred_model} to {model}", flush=True)
            return result
        if i < len(chain) - 1:
            print(f"  [ollama_client] Model {model} failed, trying {chain[i + 1]}...", flush=True)

    print(f"  [ollama_client] All models in fallback chain failed", flush=True)
    return None


def unload_model(model: str) -> bool:
    """Ask Ollama to unload a model from VRAM.

    Ollama keeps models loaded for a few minutes after use.
    Call this to free VRAM before switching to a different model.

    Returns True if unload was successful or model wasn't loaded.
    """
    try:
        # Ollama keep_alive=0 tells it to unload immediately
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30,
        )
        if resp.ok:
            print(f"  [ollama_client] Unloaded {model} from VRAM", flush=True)
        return resp.ok
    except Exception as e:
        # Non-critical — Ollama will eventually evict on its own
        print(f"  [ollama_client] Unload notice: {e}", flush=True)
        return False


def check_ollama_running() -> bool:
    """Check if Ollama is reachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/", timeout=5)
        return resp.ok
    except Exception:
        return False


def list_loaded_models() -> list[str]:
    """List models currently loaded in Ollama VRAM."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        if resp.ok:
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    return []
