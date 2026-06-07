"""Shared DeepSeek LLM client using the OpenAI-compatible API.

All model-backed LLM calls in the API go through this module so text emotion,
kinetic typography, diary reflection, and body-sensation advice share one
configuration path.

Configure with environment variables:
- DEEPSEEK_API_KEY, or legacy LLM_API_KEY
- DEEPSEEK_MODEL, or legacy LLM_MODEL
- DEEPSEEK_BASE_URL, or legacy LLM_API_BASE_URL
- DEEPSEEK_TIMEOUT_SECONDS, or legacy LLM_TIMEOUT_SECONDS

If no API key is configured, callers receive ``None`` and use their local
fallbacks.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("LLM_API_KEY", ""))
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", os.getenv("LLM_MODEL", "deepseek-v4-flash"))
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com"))
DEEPSEEK_TIMEOUT_SECONDS = os.getenv("DEEPSEEK_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "30"))


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _base_url() -> str:
    return (DEEPSEEK_BASE_URL or "https://api.deepseek.com").strip()


def default_model() -> str:
    return (DEEPSEEK_MODEL or "deepseek-v4-flash").strip()


def _timeout() -> float:
    try:
        return float(DEEPSEEK_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return 30.0


def _resolve_api_key() -> str:
    key = (DEEPSEEK_API_KEY or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def llm_enabled() -> bool:
    """True only when LLM calls are enabled and an API key is configured."""
    return _env_bool("LLM_ENABLED", True) and bool(_resolve_api_key())


_CLIENT: Any = None
_CLIENT_SIGNATURE: tuple[str, str, float] | None = None


def get_client():
    """Return a cached OpenAI client pointed at DeepSeek, or ``None``."""
    global _CLIENT, _CLIENT_SIGNATURE

    if not _env_bool("LLM_ENABLED", True):
        return None

    api_key = _resolve_api_key()
    if not api_key:
        return None

    signature = (api_key, _base_url(), _timeout())
    if _CLIENT is not None and _CLIENT_SIGNATURE == signature:
        return _CLIENT

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - import guard
        print(f"[llm_client] openai SDK not available: {exc}")
        return None

    try:
        _CLIENT = OpenAI(
            api_key=api_key,
            base_url=_base_url(),
            timeout=_timeout(),
            max_retries=1,
        )
        _CLIENT_SIGNATURE = signature
        return _CLIENT
    except Exception as exc:
        print(f"[llm_client] failed to build OpenAI client: {exc}")
        _CLIENT = None
        _CLIENT_SIGNATURE = None
        return None


def strip_content(content: str) -> str:
    """Clean an assistant message by dropping thinking blocks and code fences."""
    content = str(content or "").strip()
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    if "```" in content:
        content = content.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    return content


def extract_json(content: str) -> Any:
    """Best-effort JSON parse from an assistant message. Returns ``None`` on failure."""
    content = strip_content(content)
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        pass

    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = content.find(open_ch)
        end = content.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except Exception:
                continue
    return None


def chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> str | None:
    """Call DeepSeek chat completions and return raw assistant content."""
    client = get_client()
    if client is None:
        return None

    request: dict[str, Any] = {
        "model": model or default_model(),
        "messages": messages,
    }
    if temperature is not None:
        request["temperature"] = temperature
    if max_tokens is not None:
        request["max_tokens"] = max_tokens
    if json_mode:
        request["response_format"] = {"type": "json_object"}
    request.update(kwargs)

    try:
        response = client.chat.completions.create(**request)
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[llm_client] chat call failed: {exc}")
        return None


def chat_json(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    retries: int = 1,
    **kwargs: Any,
) -> Any:
    """Call Gemini (primary) or DeepSeek (fallback) in JSON mode; return parsed JSON."""
    last_content: str | None = None
    for _ in range(max(1, retries + 1)):
        content = chat(
            messages,
            model=model,
            temperature=temperature,
            json_mode=True,
            max_tokens=max_tokens,
            **kwargs,
        )
        if content and content.strip():
            parsed = extract_json(content)
            if parsed is not None:
                return parsed
            last_content = content
    if last_content is not None:
        print(f"[llm_client] JSON parse failed. preview={strip_content(last_content)[:300]}")
    return None
