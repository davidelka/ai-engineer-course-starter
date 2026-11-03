"""Idempotency-Key for POST /v1/answer (reference for lab 26, exercise 6).

Follows draft-ietf-httpapi-idempotency-key-header-08 (October 2026):
  - same key + same body, first request finished  -> replay the stored response
  - same key + same body, first request still running -> 409 Conflict
  - same key + DIFFERENT body                     -> 422 Unprocessable Content
  - keys expire after `ttl` seconds (our documented policy: 24 hours)

Why an LLM API wants this: a client that times out and retries a POST pays
twice and may get a different answer. With a key, the retry gets the first
answer back, byte for byte, for free.

In-memory and single-process: with replicas the store lives in Redis with
SET key value NX EX ttl, which gives the same "first writer wins" rule.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional


def fingerprint(body: Any) -> str:
    """sha256 of canonical JSON: key order and whitespace do not matter."""
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass
class _Entry:
    fp: str
    created: float
    done: bool = False
    status: int = 0
    response: Any = None
    headers: dict = field(default_factory=dict)


@dataclass
class Begin:
    outcome: Literal["new", "replay", "in_progress", "mismatch"]
    status: int = 0
    response: Any = None
    headers: dict = field(default_factory=dict)


class IdempotencyStore:
    def __init__(self, ttl: float = 86_400, clock: Callable[[], float] = time.monotonic,
                 max_entries: int = 50_000):
        self.ttl, self.clock, self.max_entries = ttl, clock, max_entries
        self._d: dict[tuple[str, str], _Entry] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        dead = [k for k, e in self._d.items() if now - e.created >= self.ttl]
        for k in dead:
            del self._d[k]

    def begin(self, scope: str, key: str, fp: str) -> Begin:
        """scope is the API key's owner: two clients may pick the same key string."""
        now = self.clock()
        with self._lock:
            self._purge(now)
            e = self._d.get((scope, key))
            if e is None:
                if len(self._d) >= self.max_entries:
                    oldest = min(self._d, key=lambda k: self._d[k].created)
                    del self._d[oldest]
                self._d[(scope, key)] = _Entry(fp, now)
                return Begin("new")
            if e.fp != fp:
                return Begin("mismatch")
            if not e.done:
                return Begin("in_progress")
            return Begin("replay", e.status, e.response, dict(e.headers))

    def complete(self, scope: str, key: str, status: int, response: Any,
                 headers: Optional[dict] = None) -> None:
        with self._lock:
            e = self._d.get((scope, key))
            if e is not None:
                e.done, e.status, e.response, e.headers = True, status, response, dict(headers or {})

    def abandon(self, scope: str, key: str) -> None:
        """The first attempt failed in a way worth retrying (timeout, 5xx): forget
        the key so the client's retry runs again instead of replaying an error."""
        with self._lock:
            self._d.pop((scope, key), None)

    def __len__(self) -> int:
        return len(self._d)
