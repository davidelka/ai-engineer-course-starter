"""Per-API-key rate limiting with a token bucket (reference for lab 26, exercise 2).

A bucket holds up to `burst` tokens and refills at `rate` tokens per second.
Each request takes `cost` tokens. If there are not enough, the request is
refused and the caller is told how long until enough tokens will exist.

Why a token bucket and not "N requests per fixed minute": a fixed window lets
a client send 2N requests across a window boundary (N at 00:59, N at 01:00).
The bucket allows short bursts up to `burst`, and a steady rate of `rate`.

Single-process and in-memory on purpose. With several replicas you keep the
bucket in Redis (one Lua script does refill+take atomically) or at the gateway
(lesson 25); the arithmetic is the same.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Optional


class TokenBucket:
    def __init__(self, rate: float, burst: float, clock: Callable[[], float] = time.monotonic):
        if rate <= 0 or burst <= 0:
            raise ValueError("rate and burst must be positive")
        self.rate = float(rate)
        self.burst = float(burst)
        self.clock = clock
        self.tokens = float(burst)  # a new client starts with a full bucket
        self.updated = clock()

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.updated)  # a clock that goes backwards adds nothing
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.updated = now

    def try_acquire(self, cost: float = 1.0, now: Optional[float] = None) -> tuple[bool, float]:
        """Take `cost` tokens if available. Returns (allowed, retry_after_seconds).

        retry_after is 0.0 when allowed; otherwise the exact time until the bucket
        will hold `cost` tokens. A cost larger than `burst` can never succeed:
        retry_after is math.inf.
        """
        now = self.clock() if now is None else now
        self._refill(now)
        if cost > self.burst:
            return False, math.inf
        if self.tokens >= cost:
            self.tokens -= cost
            return True, 0.0
        return False, (cost - self.tokens) / self.rate

    @property
    def remaining(self) -> int:
        return int(self.tokens)


@dataclass
class RateDecision:
    allowed: bool
    retry_after: float  # seconds; 0 when allowed
    remaining: int
    limit: int  # the burst size
    window: int  # seconds to refill a full bucket (informational, for RateLimit-Policy)
    reset: float = 0.0  # seconds until the bucket is full again


class KeyedRateLimiter:
    """One TokenBucket per key, created on first use, oldest evicted past max_keys."""

    def __init__(self, rate: float, burst: float, *, max_keys: int = 10_000,
                 clock: Callable[[], float] = time.monotonic,
                 bucket_factory: Callable[..., object] = TokenBucket):
        self.rate, self.burst, self.max_keys, self.clock = rate, burst, max_keys, clock
        self.bucket_factory = bucket_factory
        self._buckets: OrderedDict[str, object] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, cost: float = 1.0) -> RateDecision:
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = self.bucket_factory(self.rate, self.burst, clock=self.clock)
                self._buckets[key] = b
                if len(self._buckets) > self.max_keys:
                    self._buckets.popitem(last=False)
            else:
                self._buckets.move_to_end(key)
            ok, wait = b.try_acquire(cost)
            tokens = float(getattr(b, "tokens", 0.0))
            return RateDecision(ok, wait, int(tokens), int(self.burst),
                                max(1, math.ceil(self.burst / self.rate)),
                                max(0.0, (self.burst - tokens) / self.rate))

    def __len__(self) -> int:
        return len(self._buckets)


def ratelimit_headers(policy: str, d: RateDecision) -> dict:
    """RateLimit-Policy / RateLimit header fields, draft-ietf-httpapi-ratelimit-headers-11.

    RateLimit-Policy: "per-key";q=5;w=3      (quota 5 per 3-second window)
    RateLimit: "per-key";r=2;t=1             (2 left; full again within t seconds)
    """
    t = math.ceil(d.reset)
    return {
        "RateLimit-Policy": f'"{policy}";q={d.limit};w={d.window}',
        "RateLimit": f'"{policy}";r={d.remaining};t={t}',
    }
