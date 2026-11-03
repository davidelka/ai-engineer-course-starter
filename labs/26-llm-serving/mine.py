"""Your code for lesson 26. Each part is checked by tests in ./tests.

servekit/ has reference versions (ratelimit.py, gate.py, idempotency.py).
Try not to peek before your tests pass. When they pass, run the service on
YOUR code and watch it work:

    python -m pytest -q labs/26-llm-serving/tests
    python labs/26-llm-serving/serve.py --mine limiter,gate,idem
"""

from __future__ import annotations

import asyncio  # noqa: F401  (exercise 3)
import hashlib  # noqa: F401  (exercise 6)
import json  # noqa: F401  (exercise 6)
import math  # noqa: F401
import time
from contextlib import asynccontextmanager
from typing import Callable, Optional

from servekit.gate import GateRejected  # the exception exercise 3 raises
from servekit.idempotency import Begin  # the result type exercise 6 returns


# ------------------------------------------------------------------ exercise 2
class TokenBucket:
    """A token bucket for ONE API key.

    - Holds up to `burst` tokens. A new bucket starts FULL (tokens == burst).
    - Refills continuously at `rate` tokens per second, never above `burst`.
      Refill lazily: on every call, add (now - self.updated) * rate, cap at burst,
      and set self.updated = now. If `now` is earlier than self.updated (a clock
      that went backwards), add nothing.
    - try_acquire(cost, now) takes `cost` tokens if available and returns
      (True, 0.0). Otherwise it takes NOTHING and returns (False, wait), where
      wait = seconds until the bucket will hold `cost` tokens:
      (cost - tokens) / rate.
    - A cost larger than burst can never succeed: return (False, math.inf).
    - `now` defaults to self.clock(). Tests pass explicit times.
    - Keep the current level in self.tokens (a float): the service reads it to
      fill the RateLimit header.

    Example, rate=2/s, burst=3: at t=0 three calls pass, the 4th returns
    (False, 0.5); at t=0.5 one call passes again.
    """

    def __init__(self, rate: float, burst: float, clock: Callable[[], float] = time.monotonic):
        if rate <= 0 or burst <= 0:
            raise ValueError("rate and burst must be positive")
        self.rate = float(rate)
        self.burst = float(burst)
        self.clock = clock
        # TODO(ex2): initial state (tokens, updated)
        raise NotImplementedError("exercise 2: implement TokenBucket.__init__ state")

    def try_acquire(self, cost: float = 1.0, now: Optional[float] = None) -> tuple[bool, float]:
        # TODO(ex2)
        raise NotImplementedError("exercise 2: implement TokenBucket.try_acquire")


# ------------------------------------------------------------------ exercise 3
class ConcurrencyGate:
    """At most `limit` requests inside at once; up to `max_queue` more may wait,
    each at most `queue_timeout` seconds; everyone else is refused at once.

    acquire() rules:
      1. If a slot is free AND nobody is waiting, take it immediately.
         (Don't jump the queue: if someone is waiting, you wait behind them.)
      2. Else, if self.waiting >= self.max_queue: count it in
         self.rejected["queue_full"] and raise GateRejected("queue_full", self.retry_after()).
         This must happen WITHOUT awaiting anything: shedding has to be instant.
      3. Else wait for a slot for at most queue_timeout seconds, keeping
         self.waiting correct (+1 while waiting, -1 when done waiting, whatever
         the outcome). On timeout: count it in self.rejected["queue_timeout"]
         and raise GateRejected("queue_timeout", self.retry_after()).
      4. On success: self.active += 1 and self.admitted += 1.
    Use self._sem (an asyncio.Semaphore(limit)); asyncio.wait_for gives you the timeout.

    retry_after(): whole seconds a refused client should wait before retrying:
      ceil(self._avg_service * (self.waiting + 1) / self.limit), and at least 1.
    (avg_service is the moving average of how long a request holds a slot; the
    formula is "how long until the queue in front of you drains".)

    release() and slot() are given.
    """

    def __init__(self, limit: int, max_queue: int = 0, queue_timeout: float = 1.0):
        if limit < 1 or max_queue < 0 or queue_timeout < 0:
            raise ValueError("limit >= 1, max_queue >= 0, queue_timeout >= 0")
        self.limit = limit
        self.max_queue = max_queue
        self.queue_timeout = queue_timeout
        self._sem = asyncio.Semaphore(limit)
        self.active = 0
        self.waiting = 0
        self.admitted = 0
        self.rejected = {"queue_full": 0, "queue_timeout": 0}
        self._avg_service = 1.0

    def retry_after(self) -> int:
        # TODO(ex3)
        raise NotImplementedError("exercise 3: implement ConcurrencyGate.retry_after")

    async def acquire(self) -> None:
        # TODO(ex3)
        raise NotImplementedError("exercise 3: implement ConcurrencyGate.acquire")

    # ---- given
    def release(self, service_time: Optional[float] = None) -> None:
        self.active -= 1
        if service_time is not None:
            self._avg_service = 0.8 * self._avg_service + 0.2 * service_time
        self._sem.release()

    @asynccontextmanager
    async def slot(self):
        await self.acquire()
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.release(time.perf_counter() - t0)

    def stats(self) -> dict:
        return {"limit": self.limit, "max_queue": self.max_queue, "queue_timeout": self.queue_timeout,
                "active": self.active, "waiting": self.waiting, "admitted": self.admitted,
                "rejected": dict(self.rejected), "avg_service_s": round(self._avg_service, 3)}


# ------------------------------------------------------------------ exercise 6
def fingerprint(body: dict) -> str:
    """sha256 hex digest of the body as CANONICAL JSON, so that key order and
    whitespace don't matter: json.dumps(body, sort_keys=True, separators=(",", ":"),
    ensure_ascii=False), encoded as UTF-8."""
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement fingerprint")


class IdempotencyStore:
    """Remembers POST /v1/answer results by (scope, Idempotency-Key).

    scope is the client id (two clients may choose the same key string).
    Entries live `ttl` seconds from creation (use self.clock()); expired entries
    behave as if they never existed.

    begin(scope, key, fp) returns a Begin (from servekit.idempotency):
      - unknown key           -> remember (fp, created now, not done); Begin("new")
      - known, different fp   -> Begin("mismatch")      (the API answers 422)
      - known, same fp, running -> Begin("in_progress") (the API answers 409)
      - known, same fp, done  -> Begin("replay", status, response, headers)
    complete(scope, key, status, response, headers=None): mark done and store them.
      (complete on an unknown key does nothing.)
    abandon(scope, key): forget the key (the first attempt failed; let a retry run).
    __len__: number of live entries.
    """

    def __init__(self, ttl: float = 86_400, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl
        self.clock = clock
        self._d: dict = {}

    def begin(self, scope: str, key: str, fp: str) -> Begin:
        # TODO(ex6)
        raise NotImplementedError("exercise 6: implement IdempotencyStore.begin")

    def complete(self, scope: str, key: str, status: int, response, headers: Optional[dict] = None) -> None:
        # TODO(ex6)
        raise NotImplementedError("exercise 6: implement IdempotencyStore.complete")

    def abandon(self, scope: str, key: str) -> None:
        # TODO(ex6)
        raise NotImplementedError("exercise 6: implement IdempotencyStore.abandon")

    def __len__(self) -> int:
        # TODO(ex6)
        raise NotImplementedError("exercise 6: implement IdempotencyStore.__len__")
