"""Concurrency gate with a bounded wait queue (reference for lab 26, exercise 3).

    gate = ConcurrencyGate(limit=8, max_queue=16, queue_timeout=2.0)
    async with gate.slot():
        ...call the LLM...

At most `limit` requests run at once. Up to `max_queue` more may wait for a
slot, each for at most `queue_timeout` seconds. Anything beyond that is shed
immediately with GateRejected, which the API turns into 429 + Retry-After.

Why bound the queue at all: an unbounded queue never says no, so under
overload every request waits longer and longer, clients time out and retry,
and the server spends its capacity on answers nobody is waiting for any more.
Refusing early and cheaply ("load shedding") keeps latency bounded for the
requests you do accept. That is backpressure: pushing the overload back to
the caller instead of absorbing it in memory.
"""

from __future__ import annotations

import asyncio
import math
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator


class GateRejected(Exception):
    def __init__(self, reason: str, retry_after: int):
        super().__init__(f"{reason}: retry after {retry_after}s")
        self.reason = reason  # "queue_full" or "queue_timeout"
        self.retry_after = retry_after


class ConcurrencyGate:
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
        self._avg_service = 1.0  # seconds, exponentially weighted moving average

    def retry_after(self) -> int:
        """Whole seconds a refused client should wait: roughly the time for the
        current queue to drain, (waiting + 1) / limit service times. At least 1."""
        return max(1, math.ceil(self._avg_service * (self.waiting + 1) / self.limit))

    async def acquire(self) -> None:
        # Fast path: a free slot and nobody queued ahead of us (keeps FIFO fairness).
        if self.waiting == 0 and not self._sem.locked():
            await self._sem.acquire()
            self.active += 1
            self.admitted += 1
            return
        if self.waiting >= self.max_queue:
            self.rejected["queue_full"] += 1
            raise GateRejected("queue_full", self.retry_after())
        self.waiting += 1
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self.queue_timeout)
        except asyncio.TimeoutError:
            self.rejected["queue_timeout"] += 1
            raise GateRejected("queue_timeout", self.retry_after()) from None
        finally:
            self.waiting -= 1
        self.active += 1
        self.admitted += 1

    def release(self, service_time: float | None = None) -> None:
        self.active -= 1
        if service_time is not None:
            self._avg_service = 0.8 * self._avg_service + 0.2 * service_time
        self._sem.release()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
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
