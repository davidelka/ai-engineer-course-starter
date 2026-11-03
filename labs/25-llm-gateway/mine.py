"""Your code for lesson 25. Each part is checked by tests in ./tests.

    python -m pytest -q labs/25-llm-gateway/tests

Four pieces of a gateway, each one plugged into the real gatewaykit when you run
    python labs/25-llm-gateway/run_gateway.py --with-mocks --mine all
so after the tests pass you can watch YOUR code make the decisions.

Reference solutions: gatewaykit/budget.py, router.py, redact.py, policy.py.
Try not to peek before your tests pass.
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
    """USD for one call, computed from the usage the provider reported.

    Use llmkit.pricing.cost_usd(model, usage, prices or PRICES). It returns None for a
    model it has no price for: then raise UnknownPriceError. Never return 0 for an
    unknown model, because a model the gateway cannot price is a free pass around
    every budget.
    """
    raise NotImplementedError("exercise 2")


def estimate_max_cost(model: str, prompt_chars: int, max_tokens: int, prices: Optional[dict] = None) -> float:
    """Worst-case USD of a request BEFORE it is sent.

    input tokens  = ceil(prompt_chars / 4)
    output tokens = max_tokens (the most the model may write)
    cost = (input_tokens * price["input"] + max_tokens * price["output"]) / 1_000_000
    using (prices or PRICES)[model]. No cache discount (worst case). Unknown model ->
    UnknownPriceError.
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
        - Blocked (allowed=False, status=402, reason="budget_exceeded") when there is
          a hard limit and either spent >= hard, or spent + estimated_cost > hard.
        - Otherwise allowed (status=200, reason=""), with warning="soft_limit" when
          there is a soft limit and spent >= soft; warning=None otherwise.
        - spent_usd = current spend; remaining_usd = max(0, hard - spent), or None
          when there is no hard limit.
        - check never changes the spend.

    record(key_id, cost_usd) -> float
        Add the cost and return the new spend. A negative cost -> ValueError.

    Periods: a key's window starts the first time the ledger sees the key (check,
    record or spent). When clock() - window_start >= period_s, the spend goes back
    to 0 and the window moves forward by whole periods (so it stays aligned). With
    period_s None the budget never resets.

    Why 402 and not 429: see the lesson. In one line: clients retry 429.
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
    """Try deployments in order; return RouteResult(value, deployment, attempts).

    For each deployment id `dep`, with breaker = breakers[dep]:
      - breaker.allow() is False -> append Attempt(dep, "skipped_open"), go on.
      - value = call(dep) succeeds -> breaker.record_success(),
        append Attempt(dep, "ok"), return RouteResult(value, dep, attempts).
      - call(dep) raises LLMError err -> append Attempt(dep, "error", err.status, err.message[:200]):
          * classify(err).retry is True (429, 5xx, 529, timeout...): the provider is
            in trouble. breaker.record_failure(), go on to the next deployment.
          * otherwise (400, 401, 404...): the REQUEST is the problem, and the next
            provider would reject it too. breaker.record_success() (the provider did
            answer, so it is up) and re-raise err immediately: no fallback.
    When the list is exhausted (or empty): raise AllDeploymentsFailed(attempts).
    Other exception types are not caught.
    """
    raise NotImplementedError("exercise 3")


# ====================================================================== exercise 4: PII redaction

def israeli_id_valid(digits: str) -> bool:
    """True for exactly 9 digits whose check digit is valid.

    Multiply the digits by 1,2,1,2,1,2,1,2,1 (left to right). When a product is
    greater than 9, use (product - 9), which equals the sum of its two digits.
    Valid when the total is divisible by 10.
        "123456782" -> True      "123456789" -> False      "12345678" -> False
    """
    raise NotImplementedError("exercise 4")


def redact(text: str, types: Iterable[str] = ("email", "phone_il", "il_id"), salt: str = "",
           known: Optional[dict] = None) -> Redaction:
    """Replace PII with placeholders; return Redaction(text, findings).

    Types (any other name -> ValueError):
      email     something@domain.tld, e.g. r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
      phone_il  an optional "+972" or "972" (which replaces the leading 0) or a leading
                "0"; then a mobile prefix 5X, a VoIP prefix 7X, or a one-digit landline
                area code 2, 3, 4, 8 or 9; then 7 digits written as 3+4. One "-" or " "
                may separate the groups. Not preceded or followed by another digit.
                Matches: 054-1234567, 0541234567, 054-123-4567, +972-54-123-4567,
                +972 54 1234567, 03-5550199, +972-3-555-0199.
      il_id     exactly 9 digits (no digit right before or after) WITH a valid check
                digit (israeli_id_valid). Nine digits without one are NOT redacted.

    Rules:
      - Priority: email, then phone_il, then il_id, whatever order `types` has. A
        match that overlaps a span already taken by a higher-priority type is skipped.
      - Placeholders: "[EMAIL_n]", "[PHONE_IL_n]", "[IL_ID_n]", numbered per type from 1
        in order of first appearance in the text. The same value gets the same
        placeholder. "Same" means after normalizing: emails lowercased; phones as digits
        only with a leading 972 turned into 0 ("+972-54-123-4567" == "0541234567");
        IDs as they are.
      - known: an optional dict {(type, normalized_value): placeholder}. Look values up
        in it first, add new ones to it, and continue the numbering after the
        placeholders of that type already in it. The gateway passes one dict for all
        the messages of a request, so [EMAIL_1] means the same person everywhere.
      - findings: one Finding per occurrence, sorted by start, with start/end offsets
        in the ORIGINAL text, the placeholder, and
        fingerprint = sha256((salt + normalized_value).encode()).hexdigest()[:12].
        Never put the raw value in a Finding: findings go to the audit log.
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
    Check in this order and return at the first match:
      1. classification not in policy["classifications"]
             -> PolicyDecision(False, "unknown_classification", <reason>)
      2. no entry for it in policy["rules"]         -> (False, "no_rule", <reason>)
      3. the rule has deny: true                    -> (False, f"{c}.deny", rule's reason or a default)
      4. providers present and deployment.provider not in it -> (False, f"{c}.providers", <reason>)
      5. models present and deployment.model not in it       -> (False, f"{c}.models", <reason>)
      6. regions present and deployment.region not in it     -> (False, f"{c}.regions", <reason>)
      7. otherwise                                  -> (True, f"{c}.allow", "")
    The reason is free text for humans (tests only check it is non-empty on denials).
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
    """
    raise NotImplementedError("exercise 5")
