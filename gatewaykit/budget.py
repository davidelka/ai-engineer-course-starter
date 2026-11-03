"""Budgets per virtual key: spend from usage, hard and soft limits, periodic reset.

Reference implementation. Exercise 2 of lab 25 asks you to write your own in mine.py.

Design decisions (explained in the lesson):
- A HARD limit rejects with 402, not 429. 429 means "try again soon", and every
  well-behaved client (llmkit included) retries it with backoff. A spent budget does
  not come back in a few seconds, so 429 would only produce a retry storm.
- The check includes an ESTIMATE of the worst-case cost of the request (prompt size
  plus max_tokens). Without it, a key with $0.001 left can send one huge request and
  overshoot by dollars, because the real cost is known only after the call.
- A SOFT limit never rejects. It adds a warning (a response header, an alert).
- Unknown price = fail closed. A model the gateway cannot price would otherwise be
  free, which is a way around every budget.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from llmkit.pricing import PRICES, cost_usd
from llmkit.types import Usage

CHARS_PER_TOKEN = 4  # rough, deliberately pessimistic enough for an estimate


class UnknownPriceError(ValueError):
    """The model has no price: refuse to treat it as free."""


@dataclass
class BudgetLimit:
    hard_usd: Optional[float] = None  # None = no hard limit
    soft_usd: Optional[float] = None  # None = no warning
    period_s: Optional[float] = None  # None = the budget never resets


@dataclass
class BudgetDecision:
    allowed: bool
    status: int  # 200 when allowed, 402 when the hard limit blocks the request
    spent_usd: float
    remaining_usd: Optional[float]  # None when there is no hard limit
    warning: Optional[str] = None  # "soft_limit" once spent >= soft_usd
    reason: str = ""  # "budget_exceeded" when blocked


def spend_from_usage(model: str, usage: Usage, prices: Optional[dict] = None) -> float:
    """USD for one call, from the usage the provider reported. Unknown model -> UnknownPriceError."""
    value = cost_usd(model, usage, prices or PRICES)
    if value is None:
        raise UnknownPriceError(f"no price for model {model!r}: refusing to count it as free")
    return value


def estimate_max_cost(model: str, prompt_chars: int, max_tokens: int, prices: Optional[dict] = None) -> float:
    """Worst-case USD before the call: prompt_chars/4 input tokens (rounded up) at the
    input price, plus max_tokens output tokens at the output price. No cache discount."""
    table = prices or PRICES
    p = table.get(model)
    if not p:
        raise UnknownPriceError(f"no price for model {model!r}")
    in_tok = -(-prompt_chars // CHARS_PER_TOKEN)
    return (in_tok * p["input"] + max_tokens * p["output"]) / 1_000_000


class BudgetLedger:
    """Spend per key, in memory. The gateway rebuilds it from the audit log at startup."""

    def __init__(self, limits: dict[str, BudgetLimit], clock: Callable[[], float] = time.time):
        self.limits = dict(limits)
        self.clock = clock
        self._spent: dict[str, float] = {}
        self._window_start: dict[str, float] = {}
        self._lock = threading.Lock()

    def _roll(self, key_id: str) -> None:
        """Start the window on first use; zero the spend when a period has passed."""
        now = self.clock()
        limit = self.limits.get(key_id)
        start = self._window_start.setdefault(key_id, now)
        if limit and limit.period_s and now - start >= limit.period_s:
            periods = int((now - start) // limit.period_s)
            self._window_start[key_id] = start + periods * limit.period_s
            self._spent[key_id] = 0.0

    def spent(self, key_id: str) -> float:
        with self._lock:
            self._roll(key_id)
            return self._spent.get(key_id, 0.0)

    def check(self, key_id: str, estimated_cost: float = 0.0) -> BudgetDecision:
        with self._lock:
            self._roll(key_id)
            spent = self._spent.get(key_id, 0.0)
            limit = self.limits.get(key_id) or BudgetLimit()
            remaining = None if limit.hard_usd is None else max(0.0, limit.hard_usd - spent)
            if limit.hard_usd is not None and (spent >= limit.hard_usd or spent + estimated_cost > limit.hard_usd):
                return BudgetDecision(False, 402, spent, remaining, None, "budget_exceeded")
            warning = "soft_limit" if limit.soft_usd is not None and spent >= limit.soft_usd else None
            return BudgetDecision(True, 200, spent, remaining, warning, "")

    def record(self, key_id: str, cost_usd: float) -> float:
        if cost_usd < 0:
            raise ValueError("cost cannot be negative")
        with self._lock:
            self._roll(key_id)
            self._spent[key_id] = self._spent.get(key_id, 0.0) + cost_usd
            return self._spent[key_id]
