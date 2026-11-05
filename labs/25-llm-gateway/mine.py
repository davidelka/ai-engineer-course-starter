"""Your code for lesson 25. Each part is checked by tests in ./tests.

    python -m pytest -q labs/25-llm-gateway/tests

Four pieces of a gateway, each one plugged into the real gatewaykit when you run
    python labs/25-llm-gateway/run_gateway.py --with-mocks --mine all
so after the tests pass you can watch YOUR code make the decisions.

Reference solutions: gatewaykit/budget.py, router.py, redact.py, policy.py.
Try not to peek before your tests pass. Stuck? HINTS.md in this folder has graded hints.
"""

from __future__ import annotations

import hashlib  # noqa: F401  (exercise 4)
import re  # noqa: F401  (exercise 4)
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from llmkit.errors import LLMError, RetryDecision, classify_error  # noqa: F401
from llmkit.pricing import PRICES, cost_usd  # noqa: F401
from llmkit.types import Usage

# The data types are shared with gatewaykit, so the gateway can use your functions.
from gatewaykit.budget import BudgetDecision, BudgetLimit, UnknownPriceError  # noqa: F401
from gatewaykit.policy import PolicyDecision  # noqa: F401
from gatewaykit.redact import Finding, Redaction  # noqa: F401
from gatewaykit.router import AllDeploymentsFailed, Attempt, RouteResult  # noqa: F401


# ====================================================================== exercise 2: budgets
# BudgetLimit(hard_usd=None, soft_usd=None, period_s=None)            (gatewaykit/budget.py)
# BudgetDecision(allowed, status, spent_usd, remaining_usd, warning=None, reason="")

def spend_from_usage(model: str, usage: Usage, prices: Optional[dict] = None) -> float:
    """USD for one call, computed from the usage the provider reported, with the
    course's price table (`prices`, default llmkit.pricing.PRICES).

    A model with no price -> UnknownPriceError. Never return 0 for an unknown model,
    because a model the gateway cannot price is a free pass around every budget.

    Stuck? HINTS.md -> spend_from_usage
    """
    raise NotImplementedError("exercise 2")


def estimate_max_cost(model: str, prompt_chars: int, max_tokens: int, prices: Optional[dict] = None) -> float:
    """Worst-case USD of a request BEFORE it is sent.

    Assumptions: about 4 characters per input token (rounded UP), the model writes all
    `max_tokens`, no cache discount. Prices in (prices or PRICES)[model] are USD per
    million tokens, with keys "input" and "output". Unknown model -> UnknownPriceError.

    Stuck? HINTS.md -> estimate_max_cost
    """
    raise NotImplementedError("exercise 2")


class MyBudgetLedger:
    """Spend per virtual key, with a hard and a soft limit and an optional period.

    __init__(limits: dict[key_id, BudgetLimit], clock=time.time)
        Keep `self.limits` as a public dict: the gateway adds limits for keys created
        at runtime. A key that is not in limits has no limits (always allowed).

    spent(key_id) -> float
        Spend in the CURRENT window (0.0 for a key never seen).

    check(key_id, estimated_cost=0.0) -> BudgetDecision
        - Blocked (allowed=False, status=402, reason="budget_exceeded") when a hard
          limit is already reached, or would be passed by this request's estimate.
        - Otherwise allowed (status=200, reason=""), with warning="soft_limit" once a
          soft limit is reached, else warning=None.
        - spent_usd = current spend; remaining_usd = what is left under the hard limit
          (never negative), or None without a hard limit.
        - check never changes the spend.

    record(key_id, cost_usd) -> float
        Add the cost and return the new spend. A negative cost -> ValueError.

    Periods: a key's window starts the first time the ledger sees the key (check,
    record or spent) and lasts period_s seconds; then the spend starts again from 0.
    Windows stay aligned to that first start ([0,100), [100,200), ...) even after a
    long idle gap. period_s None: the budget never resets.

    Why 402 and not 429: see the lesson. In one line: clients retry 429.

    Stuck? HINTS.md -> MyBudgetLedger
    """

    def __init__(self, limits: dict, clock: Callable[[], float] = time.time):
        raise NotImplementedError("exercise 2")

    def spent(self, key_id: str) -> float:
        raise NotImplementedError("exercise 2")

    def check(self, key_id: str, estimated_cost: float = 0.0) -> BudgetDecision:
        raise NotImplementedError("exercise 2")

    def record(self, key_id: str, cost_usd: float) -> float:
        raise NotImplementedError("exercise 2")


# ====================================================================== exercise 3: fallback + breaker

class MyCircuitBreaker:
    """One per deployment. Three states, as strings in `self.state`:

    "closed"     allow() -> True. Each record_failure() counts a CONSECUTIVE failure;
                 record_success() resets the count to 0. When the count reaches
                 failure_threshold, the state becomes "open" and the time is noted.
    "open"       allow() -> False, until cooldown_s has passed since it opened. The
                 first allow() call after that switches to "half_open" and returns
                 True: that request is the single trial.
    "half_open"  allow() -> False for everyone else while the trial is in flight.
                 record_success() -> "closed" (count 0). record_failure() -> "open"
                 again, with a new opening time (a full new cooldown).

    The open -> half_open transition happens only inside allow(): reading `state`
    never changes it. Use self.clock() for time (tests pass a fake clock).

    Stuck? HINTS.md -> MyCircuitBreaker
    """

    def __init__(self, failure_threshold: int = 3, cooldown_s: float = 30.0,
                 clock: Callable[[], float] = time.monotonic):
        raise NotImplementedError("exercise 3")

    def allow(self) -> bool:
        raise NotImplementedError("exercise 3")

    def record_success(self) -> None:
        raise NotImplementedError("exercise 3")

    def record_failure(self) -> None:
        raise NotImplementedError("exercise 3")


def route_with_fallback(deployments: list[str], call: Callable[[str], Any], breakers: dict,
                        classify: Callable[[LLMError], RetryDecision] = classify_error) -> RouteResult:
    """Try deployments in order; return RouteResult(value, deployment, attempts) for the
    first one that answers. breakers[dep] is that deployment's circuit breaker.

    `attempts` records every deployment touched, in order, as one of:
      Attempt(dep, "skipped_open")                          its breaker refused
      Attempt(dep, "ok")                                    it answered
      Attempt(dep, "error", err.status, err.message[:200])  call(dep) raised LLMError err
    Rules:
      - A retryable error (classify(err).retry: 429, 5xx, 529, timeout...) means the
        provider is in trouble: it counts against its breaker; fall back to the next.
      - A non-retryable error (400, 401, 404...) means the REQUEST is the problem and
        the next provider would reject it too: re-raise err at once, no fallback, and
        it does NOT count against the provider's health (it did answer).
      - A success is reported to the breaker too.
      - List exhausted (or empty): raise AllDeploymentsFailed(attempts).
      - Other exception types are not caught.

    Stuck? HINTS.md -> route_with_fallback
    """
    raise NotImplementedError("exercise 3")


# ====================================================================== exercise 4: PII redaction

def israeli_id_valid(digits: str) -> bool:
    """True for exactly 9 digits whose last digit is the correct check digit of the
    official Israeli ID algorithm (a Luhn-like weighted sum). Anything else -> False.
        "123456782" -> True      "123456789" -> False      "12345678" -> False

    Stuck? HINTS.md -> israeli_id_valid
    """
    raise NotImplementedError("exercise 4")


def redact(text: str, types: Iterable[str] = ("email", "phone_il", "il_id"), salt: str = "",
           known: Optional[dict] = None) -> Redaction:
    """Replace PII with placeholders; return Redaction(text, findings).

    Types (any other name -> ValueError):
      email     something@domain.tld
      phone_il  Israeli mobile (5X), VoIP (7X) and landline (2, 3, 4, 8, 9) numbers,
                written with 0, 972 or +972, as 3+4 digits, with or without one "-" or
                " " between groups, not glued to other digits. Must match: 054-1234567,
                0541234567, 054-123-4567, +972-54-123-4567, +972 54 1234567, 03-5550199,
                +972-3-555-0199.
      il_id     a standalone 9-digit number that passes israeli_id_valid (nine digits
                without a valid check digit are NOT redacted).

    Rules:
      - Priority email > phone_il > il_id, whatever order `types` has: a match that
        overlaps text already taken by a higher-priority type is not redacted again.
      - Placeholders "[EMAIL_n]", "[PHONE_IL_n]", "[IL_ID_n]": numbered per type from 1
        in order of first appearance. The same value always gets the same placeholder,
        compared after normalizing: emails lowercased; phones as digits only with a
        leading 972 turned into 0 ("+972-54-123-4567" == "0541234567"); IDs as they are.
      - known: optional dict {(type, normalized_value): placeholder} shared by all the
        messages of one request. Reuse its placeholders, add new values to it, and
        continue each type's numbering after the ones already there.
      - findings: one Finding per occurrence, sorted by start, with start/end offsets in
        the ORIGINAL text, the placeholder, and
        fingerprint = sha256((salt + normalized_value).encode()).hexdigest()[:12].
        Never put the raw value in a Finding: findings go to the audit log.

    Stuck? HINTS.md -> redact
    """
    raise NotImplementedError("exercise 4")


# ====================================================================== exercise 5: governance policy
# The policy file is labs/25-llm-gateway/policy.yaml. Its shape:
#   classifications: [public, internal, confidential, restricted]   # low -> high
#   default_classification: internal
#   rules:
#     <classification>:
#       providers: [...]   # optional allow-list
#       models: [...]      # optional allow-list (provider model names, e.g. claude-haiku-5-5)
#       regions: [...]     # optional allow-list
#       redact: [...]      # used by the gateway, not by decide()
#       deny: true         # optional; with an optional reason: "..."

def decide(policy: dict, classification: str, deployment) -> PolicyDecision:
    """May data of this classification be sent to this deployment?

    deployment has .provider, .model and .region (gatewaykit.config.Deployment).
    Returns PolicyDecision(allowed, rule, reason). `rule` names what decided, c being
    the classification:
      "unknown_classification"   c is not one of policy["classifications"]
      "no_rule"                  policy["rules"] has no entry for c
      f"{c}.deny"                the rule denies c outright (reason: the rule's own, or a default)
      f"{c}.providers" / f"{c}.models" / f"{c}.regions"
                                 the deployment is outside that allow-list
      f"{c}.allow"               allowed (reason "")
    When several apply, the earlier one in this list wins (providers before models
    before regions). The reason is free text for humans (tests only check that it is
    non-empty on denials).

    Stuck? HINTS.md -> decide
    """
    raise NotImplementedError("exercise 5")


def effective_classification(requested: Optional[str], floor: Optional[str], policy: dict) -> str:
    """The classification a request is handled under.

      - requested None or "" -> policy.get("default_classification", "internal")
        (Acme: "Documents without a label are treated as Internal").
      - requested or floor not in policy["classifications"] -> ValueError.
      - return the HIGHER of requested and floor (floor None = no floor). Higher means
        later in policy["classifications"]. An app whose key has floor "confidential"
        cannot label its own traffic "public".

    Stuck? HINTS.md -> effective_classification
    """
    raise NotImplementedError("exercise 5")
