"""
LLM client wrapper - the first place in this codebase that talks to an
actual language model (everything before Phase 5 was deterministic code:
auth, MCP tool calls, caching).

Two interchangeable providers, picked by settings.LLM_PROVIDER:

  - "groq" (default): Groq's API is OpenAI-compatible (same request/
    response shape), and its free tier needs only a signup + API key, no
    billing - see https://console.groq.com. Model default is
    llama-3.3-70b-versatile.
  - "openai": for when a Groq model name gets deprecated/renamed out
    from under GROQ_MODEL (this has happened - see the 21 Aug 2026 note
    below), or when someone would rather spend OpenAI credits they
    already have. Needs OPENAI_API_KEY.

Both SDKs expose the identical `.chat.completions.create(...)` shape
(Groq's client is a fork of OpenAI's), so swapping providers is just
swapping which client class gets constructed - `chat_json()` itself
doesn't change.

NOTE (21 Aug 2026): hit in the wild - Groq deprecated/renamed the model
behind the old GROQ_MODEL default, so every LLM call started failing
with a 404 "model does not exist" until GROQ_MODEL (or LLM_PROVIDER) was
updated. Worth checking https://console.groq.com/docs/models for the
current model list if this happens again.

`chat_json()` is the one function every LLM-using agent calls: give it a
system prompt + user prompt, get back a parsed dict. response_format is
forced to JSON mode so agents never have to regex-scrape an LLM's prose
reply - the model itself is constrained to emit valid JSON.
"""
from __future__ import annotations

import json
from typing import Any

from app.core.config import settings

_client: Any = None


def _get_client() -> Any:
    """Lazy singleton - constructing a provider client with an empty
    api_key would fail at import time for anyone running without a key
    yet (e.g. during early local setup, or in tests that never call an
    agent that needs the LLM)."""
    global _client
    if _client is not None:
        return _client

    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. "
                "Add it to services/api/.env."
            )
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    elif provider == "groq":
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "LLM_PROVIDER is 'groq' but GROQ_API_KEY is not set. Get a "
                "free key at https://console.groq.com and put it in "
                "services/api/.env."
            )
        from groq import AsyncGroq

        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER {provider!r} - expected 'groq' or 'openai'.")

    return _client


def _get_model_name() -> str:
    provider = settings.LLM_PROVIDER.lower()
    return settings.OPENAI_MODEL if provider == "openai" else settings.GROQ_MODEL


async def chat_json(system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> dict[str, Any]:
    """Call the LLM, forcing a JSON object response. Raises on any
    failure (missing key, network error, invalid JSON back) - callers
    (agents) decide whether to fall back to non-LLM logic or propagate
    the error, this function does not silently swallow anything."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=_get_model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    parsed = json.loads(content)

    if not isinstance(parsed, dict):
        # response_format=json_object is supposed to guarantee a JSON
        # OBJECT back, but models occasionally emit a JSON-encoded
        # string/array anyway (e.g. a stray pair of quotes around the
        # whole thing). Every caller does parsed.get(...) immediately,
        # so failing loudly here - instead of a confusing
        # "'str' object has no attribute 'get'" two frames later - lets
        # the agent's existing try/except fall back to its non-LLM path.
        raise ValueError(f"LLM response was not a JSON object (got {type(parsed).__name__}): {content!r:.200}")

    return parsed
