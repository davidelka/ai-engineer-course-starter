"""Exercise 2: spend from usage, worst-case estimates, and a budget ledger with hard/soft limits."""

import pytest

import mine
from gatewaykit.budget import BudgetLimit, UnknownPriceError
from llmkit.types import Usage

PRICES = {"cheap": {"input": 1.0, "output": 5.0, "cached_input": 0.1},
          "pricey": {"input": 10.0, "output": 50.0}}


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# ---------------------------------------------------------------- spend and estimate
def test_spend_from_usage_uses_the_provider_usage():
    u = Usage(input_tokens=1_000_000, output_tokens=200_000)
    assert mine.spend_from_usage("cheap", u, PRICES) == pytest.approx(1.0 + 1.0)


def test_spend_from_usage_counts_cache_reads_at_the_cached_price():
    u = Usage(input_tokens=1_000_000, cached_input_tokens=1_000_000, output_tokens=0)
    assert mine.spend_from_usage("cheap", u, PRICES) == pytest.approx(0.1)


def test_spend_from_usage_works_with_llmkit_prices_by_default():
    u = Usage(input_tokens=1000, output_tokens=1000)
    assert mine.spend_from_usage("claude-haiku-5-5", u) == pytest.approx((1000 * 0.10 + 1000 * 0.50) / 1e6)


def test_unknown_model_is_never_free():
    with pytest.raises(UnknownPriceError):
        mine.spend_from_usage("mystery-model", Usage(10, 10), PRICES)
    with pytest.raises(UnknownPriceError):
        mine.estimate_max_cost("mystery-model", 100, 100, PRICES)


def test_estimate_is_prompt_chars_over_four_plus_max_tokens():
    # 400 chars -> 100 input tokens; 1000 output tokens
    assert mine.estimate_max_cost("pricey", 400, 1000, PRICES) == pytest.approx((100 * 10 + 1000 * 50) / 1e6)


def test_estimate_rounds_input_tokens_up():
    assert mine.estimate_max_cost("cheap", 401, 0, PRICES) == pytest.approx(101 * 1.0 / 1e6)


# ---------------------------------------------------------------- the ledger
def test_unknown_key_has_no_limits():
    led = mine.MyBudgetLedger({}, clock=Clock())
    d = led.check("nobody", 1000.0)
    assert d.allowed and d.status == 200 and d.remaining_usd is None and d.warning is None
    assert led.spent("nobody") == 0.0


def test_record_accumulates_and_returns_the_new_total():
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0)}, clock=Clock())
    assert led.record("k", 0.25) == pytest.approx(0.25)
    assert led.record("k", 0.25) == pytest.approx(0.5)
    assert led.spent("k") == pytest.approx(0.5)


def test_negative_cost_is_rejected():
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0)}, clock=Clock())
    with pytest.raises(ValueError):
        led.record("k", -0.01)


def test_check_does_not_change_spend():
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0)}, clock=Clock())
    led.check("k", 0.5)
    led.check("k", 0.5)
    assert led.spent("k") == 0.0


def test_hard_limit_blocks_with_402():
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0)}, clock=Clock())
    led.record("k", 1.0)
    d = led.check("k")
    assert not d.allowed
    assert d.status == 402, "402, not 429: a spent budget does not come back if the client retries"
    assert d.reason == "budget_exceeded"
    assert d.remaining_usd == 0.0
    assert d.spent_usd == pytest.approx(1.0)


def test_the_estimate_blocks_a_request_that_could_overshoot():
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0)}, clock=Clock())
    led.record("k", 0.9)
    assert led.check("k", 0.05).allowed
    d = led.check("k", 0.2)  # 0.9 + 0.2 > 1.0
    assert not d.allowed and d.status == 402
    assert d.remaining_usd == pytest.approx(0.1)


def test_soft_limit_warns_but_allows():
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0, soft_usd=0.5)}, clock=Clock())
    led.record("k", 0.4)
    assert led.check("k").warning is None
    led.record("k", 0.1)
    d = led.check("k")
    assert d.allowed and d.status == 200 and d.warning == "soft_limit"


def test_soft_limit_without_hard_limit():
    led = mine.MyBudgetLedger({"k": BudgetLimit(soft_usd=0.1)}, clock=Clock())
    led.record("k", 5.0)
    d = led.check("k", 100.0)
    assert d.allowed and d.warning == "soft_limit" and d.remaining_usd is None


def test_budget_resets_after_the_period():
    clock = Clock()
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0, period_s=3600)}, clock=clock)
    led.record("k", 1.0)
    clock.t += 3599
    assert not led.check("k").allowed
    clock.t += 1
    assert led.check("k").allowed
    assert led.spent("k") == 0.0


def test_window_moves_by_whole_periods():
    clock = Clock(0.0)
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0, period_s=100)}, clock=clock)
    led.record("k", 0.3)  # window [0, 100)
    clock.t = 250  # two and a half periods later: window [200, 300)
    led.record("k", 0.5)
    clock.t = 299
    assert led.spent("k") == pytest.approx(0.5), "the window must stay aligned: [200, 300)"
    clock.t = 300
    assert led.spent("k") == 0.0


def test_no_period_means_no_reset():
    clock = Clock()
    led = mine.MyBudgetLedger({"k": BudgetLimit(hard_usd=1.0)}, clock=clock)
    led.record("k", 1.0)
    clock.t += 10 * 365 * 86400
    assert not led.check("k").allowed


def test_limits_is_a_public_dict_the_gateway_can_extend():
    led = mine.MyBudgetLedger({}, clock=Clock())
    led.limits["new-key"] = BudgetLimit(hard_usd=0.01)
    led.record("new-key", 0.01)
    assert not led.check("new-key").allowed
