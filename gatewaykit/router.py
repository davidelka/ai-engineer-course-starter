"""Fallback routing with a circuit breaker per deployment.

Reference implementation. Exercise 3 of lab 25 asks you to write your own in mine.py.

Two layers, two jobs:
- llmkit's retries (lesson 2) retry the SAME deployment a few times with backoff.
- This router moves to the NEXT deployment when one fails with a retryable error, and
  the circuit breaker stops sending traffic to a deployment that keeps failing, so
  requests do not each pay a timeout to rediscover that it is down.

A non-retryable error (400, 401, 404, 413...) is the request's fault, not the
provider's: it is raised at once, without fallback (the next provider would reject
the same request) and without counting against the breaker.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from llmkit.errors import LLMError, RetryDecision, classify_error


class CircuitBreaker:
    """closed -> (failure_threshold consecutive failures) -> open
    open -> (cooldown_s passed, inside allow()) -> half_open: ONE trial request
    half_open -> success -> closed;  half_open -> failure -> open again (new cooldown)."""

    def __init__(self, failure_threshold: int = 3, cooldown_s: float = 30.0,
                 clock: Callable[[], float] = time.monotonic):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.clock = clock
        self.state = "closed"
        self.failures = 0
        self.opened_at: Optional[float] = None
        self._trial_in_flight = False
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.state == "closed":
                return True
            if self.state == "open":
                if self.clock() - (self.opened_at or 0.0) >= self.cooldown_s:
                    self.state = "half_open"
                    self._trial_in_flight = True
                    return True
                return False
            # half_open: only the one trial request goes through
            if not self._trial_in_flight:
                self._trial_in_flight = True
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self.state = "closed"
            self.failures = 0
            self.opened_at = None
            self._trial_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._trial_in_flight = False
            if self.state == "half_open":
                self.state, self.opened_at = "open", self.clock()
                return
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.state, self.opened_at = "open", self.clock()


@dataclass
class Attempt:
    deployment: str
    outcome: str  # "ok" | "error" | "skipped_open"
    status: Optional[int] = None
    error: str = ""


@dataclass
class RouteResult:
    value: Any
    deployment: str
    attempts: list[Attempt] = field(default_factory=list)


class AllDeploymentsFailed(Exception):
    def __init__(self, attempts: list[Attempt]):
        self.attempts = attempts
        summary = ", ".join(f"{a.deployment}:{a.outcome}{'/' + str(a.status) if a.status else ''}" for a in attempts)
        super().__init__(f"all deployments failed or were skipped: {summary or 'none configured'}")


def route_with_fallback(deployments: list[str], call: Callable[[str], Any], breakers: dict,
                        classify: Callable[[LLMError], RetryDecision] = classify_error) -> RouteResult:
    attempts: list[Attempt] = []
    for dep in deployments:
        breaker = breakers[dep]
        if not breaker.allow():
            attempts.append(Attempt(dep, "skipped_open"))
            continue
        try:
            value = call(dep)
        except LLMError as err:
            attempts.append(Attempt(dep, "error", err.status, err.message[:200]))
            if not classify(err).retry:
                breaker.record_success()  # the provider answered: it is up, the request is bad
                raise
            breaker.record_failure()
            continue
        breaker.record_success()
        attempts.append(Attempt(dep, "ok"))
        return RouteResult(value, dep, attempts)
    raise AllDeploymentsFailed(attempts)
