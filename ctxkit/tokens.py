"""Token counting.

count_tokens(text) is offline: tiktoken's o200k_base (OpenAI's current encoding). It is an
APPROXIMATION for Claude: Claude Haiku 5.5 uses Anthropic's newer tokenizer, which counts
the same text as roughly 30% more tokens than Claude Haiku 4.5 did, and Hebrew differs even
more. Use it to compare layers and designs, and claude_count_tokens() when the exact number
matters (it calls Anthropic's free count_tokens endpoint).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def _encoding():
    try:
        import tiktoken

        return tiktoken.get_encoding("o200k_base")
    except Exception:  # tiktoken missing or its file cannot be downloaded: fall back
        return None


def count_tokens(text: str) -> int:
    """Approximate token count of text (o200k_base; falls back to len/4)."""
    if not text:
        return 0
    enc = _encoding()
    if enc is None:
        return max(1, round(len(text) / 4))
    return len(enc.encode(text, disallowed_special=()))


def claude_count_tokens(body: dict, api_key: Optional[str] = None,
                        base_url: str = "https://api.anthropic.com") -> int:
    """Exact input tokens for an Anthropic Messages request body, via POST
    /v1/messages/count_tokens. Free, but rate limited and needs ANTHROPIC_API_KEY.
    Only model, system, messages, tools (and a few others) are accepted, so other
    fields are dropped first."""
    import httpx

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (put it in .env)")
    allowed = {"model", "system", "messages", "tools", "tool_choice", "thinking"}
    payload = {k: v for k, v in body.items() if k in allowed}
    r = httpx.post(base_url + "/v1/messages/count_tokens", json=payload, timeout=30,
                   headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                            "content-type": "application/json"})
    r.raise_for_status()
    return int(r.json()["input_tokens"])
