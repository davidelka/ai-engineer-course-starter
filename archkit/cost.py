"""Cost model (lesson 19): from token estimates to dollars per request and per month.

Reference implementation of the functions in labs/19-ai-architecture/mine.py.
Prices come from llmkit.pricing (USD per 1M tokens); cost_usd() there already
knows about cached input and long-context multipliers.

Two different caches, two different effects:
  - prompt cache (provider side): the stable prefix of a call (system prompt,
    policy, few-shot examples) is read at the cached price. A miss WRITES the
    cache, billed at the model's "cache_write" price (Anthropic: 1.25x input for
    the 5-minute TTL; OpenAI before GPT-5.6: no write charge). llmkit.pricing
    knows both prices, and cost_usd() bills Usage.cache_creation_tokens.
  - response cache (our side): the whole request is answered from our cache,
    so no model call happens at all.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Optional

from llmkit.pricing import PRICES, cost_usd
from llmkit.types import Usage


@dataclass
class CallProfile:
    name: str
    model: str                  # key in llmkit.pricing.PRICES, e.g. "claude-haiku-5-5"
    input_tokens: int           # all input tokens of one call, cacheable prefix included
    output_tokens: int
    cacheable_tokens: int = 0   # part of input_tokens that is a stable, cacheable prefix
    calls_per_request: float = 1.0


def call_cost(call: CallProfile, prompt_cache_hit_rate: float = 0.0, *,
              prices: Optional[dict] = None) -> float:
    """Expected USD of ONE call (not multiplied by calls_per_request).

    hit:  the prefix is read from the cache.
    miss: with caching on (h > 0) the prefix is WRITTEN to the cache; with caching
          off (h == 0) it is plain input.
    """
    table = prices or PRICES
    if call.model not in table:
        raise ValueError(f"unknown model {call.model!r}: add it to llmkit/pricing.py")
    h = prompt_cache_hit_rate
    k = min(call.cacheable_tokens, call.input_tokens)
    i, o = call.input_tokens, call.output_tokens
    hit = cost_usd(call.model, Usage(input_tokens=i, cached_input_tokens=k, output_tokens=o), table)
    miss = cost_usd(call.model, Usage(input_tokens=i, cache_creation_tokens=k if h > 0 else 0,
                                      output_tokens=o), table)
    return h * hit + (1 - h) * miss


def request_cost(calls: Iterable[CallProfile], prompt_cache_hit_rate: float = 0.0, *,
                 prices: Optional[dict] = None) -> float:
    """Expected USD of one request that makes all these calls."""
    return sum(c.calls_per_request * call_cost(c, prompt_cache_hit_rate, prices=prices) for c in calls)


def monthly_cost(calls: Iterable[CallProfile], requests_per_day: float, *, days: int = 30,
                 prompt_cache_hit_rate: float = 0.0, response_cache_hit_rate: float = 0.0,
                 fixed_monthly_usd: float = 0.0, prices: Optional[dict] = None) -> dict:
    calls = list(calls)
    per_request = request_cost(calls, prompt_cache_hit_rate, prices=prices)
    requests = requests_per_day * days
    llm_requests = requests * (1 - response_cache_hit_rate)
    llm = per_request * llm_requests
    return {
        "per_request_usd": per_request,
        "requests_month": requests,
        "llm_requests_month": llm_requests,
        "llm_monthly_usd": llm,
        "fixed_monthly_usd": fixed_monthly_usd,
        "total_monthly_usd": llm + fixed_monthly_usd,
    }


def with_model(calls: Iterable[CallProfile], model: str, only: Optional[str] = None) -> list[CallProfile]:
    """What-if helper: the same calls, on another model (all of them, or only the call named `only`)."""
    return [replace(c, model=model) if only in (None, c.name) else c for c in calls]


def profiles_from_spec(path_budget) -> list[CallProfile]:
    """archkit.spec.PathBudget -> CallProfile list. Accepts 'provider:model' or a bare model name."""
    return [CallProfile(name=c.name, model=c.model.split(":", 1)[-1], input_tokens=c.input_tokens,
                        output_tokens=c.output_tokens, cacheable_tokens=c.cacheable_tokens,
                        calls_per_request=c.calls_per_request) for c in path_budget.calls]
