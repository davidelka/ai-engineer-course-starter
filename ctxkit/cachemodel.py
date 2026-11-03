"""Expected cost of prompt caching for a traffic pattern.

Model: requests that share a prefix arrive at random (a Poisson process) at `calls_per_hour`.
A cache entry lives `ttl_s` seconds and every hit refreshes it (true for Anthropic). So a
request hits when the previous request came less than ttl_s ago:

    P(hit) = 1 - exp(-rate * ttl)

A miss pays a cache WRITE for the prefix, a hit pays a cache READ. The dynamic suffix
and the output are paid in full either way. Real traffic is burstier than Poisson
(work hours, retries), so treat this as a first estimate and measure the real hit rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class CacheScenario:
    calls_per_hour: float
    prefix_tokens: int  # the stable part (system, tools, documents)
    suffix_tokens: int  # the part that changes every call (question, history tail)
    output_tokens: int
    ttl_s: float = 300.0
    price_input: float = 0.10  # USD per 1M tokens (Claude Haiku 5.5 by default)
    price_output: float = 0.50
    price_write: float = 0.125  # 5m write = 1.25x input; 1h write = 2x input
    price_read: float = 0.01  # 0.1x input


def hit_probability(calls_per_hour: float, ttl_s: float) -> float:
    rate = calls_per_hour / 3600.0
    return 1.0 - math.exp(-rate * ttl_s) if rate > 0 else 0.0


def scenario_cost(s: CacheScenario) -> dict:
    """Cost per call and per hour, with and without caching. All USD."""
    p = hit_probability(s.calls_per_hour, s.ttl_s)
    m = 1e-6
    common = (s.suffix_tokens * s.price_input + s.output_tokens * s.price_output) * m
    no_cache = s.prefix_tokens * s.price_input * m + common
    cached = (p * s.prefix_tokens * s.price_read + (1 - p) * s.prefix_tokens * s.price_write) * m + common
    return {
        "hit_rate": p,
        "per_call_no_cache": no_cache,
        "per_call_cached": cached,
        "per_hour_no_cache": no_cache * s.calls_per_hour,
        "per_hour_cached": cached * s.calls_per_hour,
        "saving": 1 - cached / no_cache if no_cache else 0.0,
    }


def break_even_hit_rate(price_input: float, price_write: float, price_read: float) -> float:
    """The hit rate above which caching the prefix is cheaper than not caching it:
    p*read + (1-p)*write < input  =>  p > (write - input) / (write - read)."""
    if price_write <= price_input:
        return 0.0  # no write premium (e.g. OpenAI before GPT-5.6): caching never costs more
    return (price_write - price_input) / (price_write - price_read)
