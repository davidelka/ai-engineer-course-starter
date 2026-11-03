"""Exercise 3: a circuit breaker per deployment, and fallback routing that uses it."""

import pytest

import mine
from gatewaykit.router import AllDeploymentsFailed
from llmkit.errors import LLMError


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def down(status=529):
    return LLMError("provider down", provider="mock", status=status, kind="overloaded_error")


# ---------------------------------------------------------------- breaker
def test_starts_closed_and_allows():
    b = mine.MyCircuitBreaker(3, 30, clock=Clock())
    assert b.state == "closed" and b.allow()


def test_opens_after_threshold_consecutive_failures():
    b = mine.MyCircuitBreaker(3, 30, clock=Clock())
    b.record_failure()
    b.record_failure()
    assert b.state == "closed"
    b.record_failure()
    assert b.state == "open"
    assert not b.allow()


def test_a_success_resets_the_consecutive_count():
    b = mine.MyCircuitBreaker(3, 30, clock=Clock())
    b.record_failure()
    b.record_failure()
    b.record_success()
    b.record_failure()
    b.record_failure()
    assert b.state == "closed", "failures must be CONSECUTIVE"


def test_stays_open_during_cooldown_then_allows_one_trial():
    clock = Clock()
    b = mine.MyCircuitBreaker(1, 30, clock=clock)
    b.record_failure()
    clock.t = 29.9
    assert not b.allow()
    assert b.state == "open"
    clock.t = 30.0
    assert b.state == "open", "reading state must not change it; allow() does"
    assert b.allow() is True
    assert b.state == "half_open"
    assert b.allow() is False, "only ONE trial request while half open"


def test_trial_success_closes():
    clock = Clock()
    b = mine.MyCircuitBreaker(1, 10, clock=clock)
    b.record_failure()
    clock.t = 10
    assert b.allow()
    b.record_success()
    assert b.state == "closed" and b.allow() and b.allow()


def test_trial_failure_reopens_with_a_new_cooldown():
    clock = Clock()
    b = mine.MyCircuitBreaker(1, 10, clock=clock)
    b.record_failure()
    clock.t = 10
    assert b.allow()
    b.record_failure()
    assert b.state == "open"
    clock.t = 19.9
    assert not b.allow(), "the cooldown restarts from the failed trial"
    clock.t = 20
    assert b.allow()


# ---------------------------------------------------------------- routing
def breakers(*names, threshold=3, cooldown=30, clock=None):
    clock = clock or Clock()
    return {n: mine.MyCircuitBreaker(threshold, cooldown, clock=clock) for n in names}


def test_first_healthy_deployment_answers():
    calls = []

    def call(dep):
        calls.append(dep)
        return f"answer from {dep}"

    r = mine.route_with_fallback(["a", "b"], call, breakers("a", "b"))
    assert r.value == "answer from a" and r.deployment == "a"
    assert calls == ["a"]
    assert [(x.deployment, x.outcome) for x in r.attempts] == [("a", "ok")]


def test_retryable_error_falls_back_and_counts_a_failure():
    br = breakers("a", "b", threshold=1)

    def call(dep):
        if dep == "a":
            raise down(529)
        return "ok"

    r = mine.route_with_fallback(["a", "b"], call, br)
    assert r.deployment == "b"
    assert [(x.deployment, x.outcome, x.status) for x in r.attempts] == [("a", "error", 529), ("b", "ok", None)]
    assert br["a"].state == "open"


def test_open_circuit_is_skipped_without_calling():
    br = breakers("a", "b", threshold=1)
    br["a"].record_failure()
    calls = []

    def call(dep):
        calls.append(dep)
        return "ok"

    r = mine.route_with_fallback(["a", "b"], call, br)
    assert calls == ["b"]
    assert r.attempts[0].deployment == "a" and r.attempts[0].outcome == "skipped_open"


def test_non_retryable_error_is_raised_without_fallback():
    br = breakers("a", "b", threshold=1)
    calls = []

    def call(dep):
        calls.append(dep)
        raise LLMError("max_tokens: too large", provider="mock", status=400, kind="invalid_request_error")

    with pytest.raises(LLMError) as exc:
        mine.route_with_fallback(["a", "b"], call, br)
    assert exc.value.status == 400
    assert calls == ["a"], "the next provider would reject the same bad request"
    assert br["a"].state == "closed", "a 400 says nothing bad about the provider's health"


def test_non_retryable_error_releases_a_half_open_trial():
    clock = Clock()
    br = breakers("a", threshold=1, cooldown=10, clock=clock)
    br["a"].record_failure()
    clock.t = 10

    def call(dep):
        raise LLMError("bad request", provider="mock", status=400)

    with pytest.raises(LLMError):
        mine.route_with_fallback(["a"], call, br)
    assert br["a"].state == "closed"


def test_all_failing_raises_with_every_attempt():
    br = breakers("a", "b", threshold=5)

    def call(dep):
        raise down(503 if dep == "a" else 429)

    with pytest.raises(AllDeploymentsFailed) as exc:
        mine.route_with_fallback(["a", "b"], call, br)
    assert [(x.deployment, x.status) for x in exc.value.attempts] == [("a", 503), ("b", 429)]


def test_timeouts_count_as_retryable():
    br = breakers("a", "b", threshold=1)

    def call(dep):
        if dep == "a":
            raise LLMError("ReadTimeout", provider="mock", kind="timeout")
        return "ok"

    assert mine.route_with_fallback(["a", "b"], call, br).deployment == "b"
    assert br["a"].state == "open"


def test_empty_list_raises():
    with pytest.raises(AllDeploymentsFailed):
        mine.route_with_fallback([], lambda d: "x", {})


def test_breaker_protects_later_requests():
    """The point of the breaker: after the primary opens, requests stop paying for it."""
    br = breakers("a", "b", threshold=2)
    calls = []

    def call(dep):
        calls.append(dep)
        if dep == "a":
            raise down()
        return "ok"

    for _ in range(5):
        mine.route_with_fallback(["a", "b"], call, br)
    assert calls.count("a") == 2 and calls.count("b") == 5
