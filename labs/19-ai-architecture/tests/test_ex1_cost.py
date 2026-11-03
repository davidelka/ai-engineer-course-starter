"""Exercise 1: cost per request and per month.

Expected values are computed from llmkit/pricing.py, so the tests keep working when prices change.
At the time of writing, claude-haiku-5-5 is: input 0.10, cached_input 0.01, cache_write 0.125,
output 0.50 (USD per 1M tokens).
"""

import pytest

from archkit import cost as ref
from archkit.cost import CallProfile
from llmkit.pricing import PRICES
from mine import monthly_cost, request_cost

H = "claude-haiku-5-5"
P = PRICES[H]
S = PRICES["claude-sonnet-5-5"]


def approx(x):
    return pytest.approx(x, rel=1e-9, abs=1e-12)


def per_m(tokens, price):
    return tokens * price / 1e6


def test_single_call_no_cache():
    # 1000 input + 100 output
    assert request_cost([CallProfile("a", H, 1000, 100)]) == approx(per_m(1000, P["input"]) + per_m(100, P["output"]))


def test_calls_per_request_scales():
    c = CallProfile("a", H, 1000, 100, calls_per_request=0.3)
    assert request_cost([c]) == approx(0.3 * (per_m(1000, P["input"]) + per_m(100, P["output"])))


def test_sum_over_calls():
    calls = [CallProfile("a", H, 1000, 100), CallProfile("b", "claude-sonnet-5-5", 2000, 200)]
    want = per_m(1000, P["input"]) + per_m(100, P["output"]) + per_m(2000, S["input"]) + per_m(200, S["output"])
    assert request_cost(calls) == approx(want)


def hit_cost():
    # 200 uncached + 800 cache reads + 100 output
    return per_m(200, P["input"]) + per_m(800, P["cached_input"]) + per_m(100, P["output"])


def miss_with_write():
    # 200 uncached + 800 cache WRITES + 100 output
    return per_m(200, P["input"]) + per_m(800, P.get("cache_write", P["input"])) + per_m(100, P["output"])


def test_full_cache_hit():
    c = CallProfile("a", H, 1000, 100, cacheable_tokens=800)
    assert request_cost([c], prompt_cache_hit_rate=1.0) == approx(hit_cost())


def test_half_hit_pays_cache_write_on_miss():
    c = CallProfile("a", H, 1000, 100, cacheable_tokens=800)
    assert request_cost([c], prompt_cache_hit_rate=0.5) == approx(0.5 * hit_cost() + 0.5 * miss_with_write())


def test_no_write_when_caching_is_off():
    c = CallProfile("a", H, 1000, 100, cacheable_tokens=800)
    assert request_cost([c], prompt_cache_hit_rate=0.0) == approx(per_m(1000, P["input"]) + per_m(100, P["output"]))


def test_cacheable_capped_at_input():
    c = CallProfile("a", H, 500, 0, cacheable_tokens=9999)
    assert request_cost([c], prompt_cache_hit_rate=1.0) == approx(per_m(500, P["cached_input"]))


def test_long_context_multiplier_comes_from_cost_usd():
    # haiku-5-5: above long_threshold input tokens, every price is multiplied
    n = P["long_threshold"] * 2
    assert request_cost([CallProfile("a", H, n, 0)]) == approx(per_m(n, P["input"]) * P["long_multiplier"])


def test_unknown_model():
    with pytest.raises(ValueError):
        request_cost([CallProfile("a", "no-such-model", 10, 10)])


def test_monthly_keys_and_values():
    one = per_m(1000, P["input"]) + per_m(100, P["output"])
    m = monthly_cost([CallProfile("a", H, 1000, 100)], 1000, days=30, response_cache_hit_rate=0.2,
                     fixed_monthly_usd=50)
    assert set(m) == {"per_request_usd", "requests_month", "llm_requests_month", "llm_monthly_usd",
                      "fixed_monthly_usd", "total_monthly_usd"}
    assert m["per_request_usd"] == approx(one)
    assert m["requests_month"] == approx(30000)
    assert m["llm_requests_month"] == approx(24000)
    assert m["llm_monthly_usd"] == approx(24000 * one)
    assert m["fixed_monthly_usd"] == 50
    assert m["total_monthly_usd"] == approx(24000 * one + 50)


def test_matches_reference_on_company_brain(company_brain):
    for p in company_brain.budget.paths:
        calls = ref.profiles_from_spec(p)
        kw = dict(days=p.days, prompt_cache_hit_rate=p.prompt_cache_hit_rate,
                  response_cache_hit_rate=p.response_cache_hit_rate)
        assert monthly_cost(calls, p.requests_per_day, **kw) == pytest.approx(
            ref.monthly_cost(calls, p.requests_per_day, **kw))
