"""USD per 1M tokens. Prices change: verify before quoting.

Checked: Anthropic, November 2026 (platform.claude.com/docs/en/build-with-claude/prompt-caching
and the Haiku 5.5 model page); OpenAI and Gemini, October 2026.
Sources: anthropic.com/pricing, openai.com/api/pricing, ai.google.dev/pricing

Keys per model:
  input, output       normal prices
  cached_input        cache READ price (Anthropic: 0.1x input, 0.05x on Opus/Sonnet 5.5)
  cache_write         5-minute cache WRITE price (Anthropic: 1.25x input). Missing = input
                      price, which is right for OpenAI models before GPT-5.6: no write charge.
  cache_write_1h      1-hour cache WRITE price (Anthropic: 2x input)
  long_threshold, long_multiplier
                      above this many prompt tokens, every price above is multiplied
                      (Haiku 5.5: x5 above 100K prompt tokens, cache prices included)
Gemini's explicit cache also bills storage per token-hour; that is not a per-request
cost, so it is not modeled here.
"""

from __future__ import annotations

from typing import Optional

from .types import Usage

PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cached_input": 0.01,
                         "cache_write": 0.125, "cache_write_1h": 0.20,
                         "long_threshold": 100_000, "long_multiplier": 5.0},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cached_input": 0.10,
                         "cache_write": 1.25, "cache_write_1h": 2.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cached_input": 0.10,
                          "cache_write": 2.50, "cache_write_1h": 4.00},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cached_input": 0.20,
                        "cache_write": 5.00, "cache_write_1h": 8.00},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50, "cached_input": 0.075},
    "gemini-3.6-flash": {"input": 1.50, "output": 7.50, "cached_input": 0.15},
    # The mock server: priced like Haiku 5.5 so cost code paths (cache included) are exercised.
    "mock-model": {"input": 0.10, "output": 0.50, "cached_input": 0.01,
                   "cache_write": 0.125, "cache_write_1h": 0.20},
}


def cost_usd(model: str, usage: Usage, prices: Optional[dict] = None) -> Optional[float]:
    table = prices or PRICES
    p = table.get(model)
    if not p:
        return None
    mult = 1.0
    # usage.input_tokens is already the whole prompt (cached parts included).
    if p.get("long_threshold") and usage.input_tokens > p["long_threshold"]:
        mult = p.get("long_multiplier", 1.0)
    write_1h = min(usage.cache_creation_1h_tokens, usage.cache_creation_tokens)
    write_5m = usage.cache_creation_tokens - write_1h
    total = (
        usage.uncached_input_tokens * p["input"]
        + usage.cached_input_tokens * p.get("cached_input", p["input"])
        + write_5m * p.get("cache_write", p["input"])
        + write_1h * p.get("cache_write_1h", p.get("cache_write", p["input"]))
        + usage.output_tokens * p["output"]
    )
    return total * mult / 1_000_000
