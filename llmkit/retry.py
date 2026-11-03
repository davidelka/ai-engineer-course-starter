"""Retries with capped exponential backoff and full jitter.

    sleep = random(0, min(cap, base * 2 ** attempt))

and never less than what the server asked for in retry-after.
See: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

from .errors import LLMError, RetryDecision, classify_error

T = TypeVar("T")


def backoff_delay(
    attempt: int,
    base: float = 0.5,
    cap: float = 20.0,
    retry_after: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> float:
    """Reference implementation. Exercise 4 asks you to write your own in mine.py.

    attempt is 0 for the wait after the first failure, 1 after the second, ...
    """
    rng = rng or random
    delay = rng.uniform(0, min(cap, base * 2**attempt))
    if retry_after is not None:
        delay = max(delay, retry_after)
    return delay


@dataclass
class RetryPolicy:
    max_attempts: int = 4  # total tries, including the first one
    base: float = 0.5
    cap: float = 20.0
    # Pluggable so exercises can swap in their own implementations.
    classify: Callable[[LLMError], RetryDecision] = classify_error
    delay: Callable[..., float] = backoff_delay
    sleep: Callable[[float], None] = time.sleep
    rng: random.Random = field(default_factory=random.Random)

    @classmethod
    def none(cls) -> "RetryPolicy":
        return cls(max_attempts=1)


def call_with_retry(
    fn: Callable[[], T],
    policy: RetryPolicy,
    on_retry: Optional[Callable[[int, LLMError, float], None]] = None,
) -> tuple[T, int]:
    """Run fn until it succeeds, the error is not retryable, or attempts run out.

    Returns (value, attempts_used). Raises the last LLMError otherwise.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn(), attempt
        except LLMError as err:
            decision = policy.classify(err)
            if not decision.retry or attempt >= policy.max_attempts:
                raise
            wait = policy.delay(attempt - 1, policy.base, policy.cap, decision.retry_after, policy.rng)
            if on_retry:
                on_retry(attempt, err, wait)
            policy.sleep(wait)
