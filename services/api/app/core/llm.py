"""
Groq LLM client wrapper - the first place in this codebase that talks to
an actual language model (everything before Phase 5 was deterministic
code: auth, MCP tool calls, caching).

Groq's API is OpenAI-compatible (same request/response shape), and its
free tier needs only a signup + API key, no billing - see
https://console.groq.com. Model default is llama-3.3-70b-versatile
(good balance of quality/speed on Groq's free tier).

`chat_json()` is the one function every LLM-using agent calls: give it a
system prompt + user prompt, get back a parsed dict. response_format is
forced to JSON mode so agents never have to regex-scrape an LLM's prose
reply - the model itself is constrained to emit valid JSON.
"""
from __future__ import annotations

import json
from typing import Any

from groq import AsyncGroq

from app.core.config import settings

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    """Lazy singleton - constructing AsyncGroq with an empty api_key
    would fail at import time for anyone running without a key yet
    (e.g. during early local setup, or in tests that never call an
    agent that needs the LLM)."""
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY not set. Get a free key at "
                "https://console.groq.com and put it in services/api/.env"
            )
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


async def chat_json(system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> dict[str, Any]:
    """Call the LLM, forcing a JSON object response. Raises on any
    failure (missing key, network error, invalid JSON back) - callers
    (agents) decide whether to fall back to non-LLM logic or propagate
    the error, this function does not silently swallow anything."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
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
