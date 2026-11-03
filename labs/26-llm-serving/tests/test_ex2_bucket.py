"""Exercise 2: a token bucket per API key."""

import math

import pytest
from fastapi.testclient import TestClient

from mine import TokenBucket


def test_starts_full_and_allows_a_burst():
    b = TokenBucket(rate=2, burst=3, clock=lambda: 0.0)
    assert b.tokens == pytest.approx(3.0)
    assert [b.try_acquire(now=0.0) for _ in range(3)] == [(True, 0.0)] * 3


def test_refusal_says_how_long_to_wait_and_takes_nothing():
    b = TokenBucket(rate=2, burst=3, clock=lambda: 0.0)
    for _ in range(3):
        b.try_acquire(now=0.0)
    ok, wait = b.try_acquire(now=0.0)
    assert ok is False and wait == pytest.approx(0.5)
    ok, wait = b.try_acquire(now=0.0)  # a refused call must not consume (or "borrow") tokens
    assert wait == pytest.approx(0.5)


def test_refills_at_rate_and_caps_at_burst():
    b = TokenBucket(rate=2, burst=3, clock=lambda: 0.0)
    for _ in range(3):
        b.try_acquire(now=0.0)
    assert b.try_acquire(now=0.5) == (True, 0.0)
    assert b.try_acquire(now=0.5)[0] is False
    b.try_acquire(now=1000.0)
    assert b.tokens == pytest.approx(2.0)  # refilled to 3 (not 2000), then one taken


def test_cost_and_partial_tokens():
    b = TokenBucket(rate=1, burst=4, clock=lambda: 0.0)
    assert b.try_acquire(cost=3, now=0.0) == (True, 0.0)
    ok, wait = b.try_acquire(cost=2, now=0.0)  # 1 token left, need 2
    assert not ok and wait == pytest.approx(1.0)
    assert b.try_acquire(cost=2, now=0.25)[1] == pytest.approx(0.75)


def test_impossible_cost_and_backwards_clock():
    b = TokenBucket(rate=1, burst=2, clock=lambda: 10.0)
    assert b.try_acquire(cost=5, now=10.0) == (False, math.inf)
    b.try_acquire(cost=2, now=10.0)
    assert b.try_acquire(now=3.0)[0] is False  # time went backwards: no refill
    assert b.try_acquire(now=11.0) == (True, 0.0)


def test_uses_the_clock_when_now_is_omitted():
    t = [0.0]
    b = TokenBucket(rate=1, burst=1, clock=lambda: t[0])
    assert b.try_acquire()[0] is True
    assert b.try_acquire()[0] is False
    t[0] = 1.0
    assert b.try_acquire()[0] is True


def test_the_service_runs_on_your_bucket(mock):
    from servekit.app import Settings, create_app
    from servekit.ratelimit import KeyedRateLimiter

    _, url = mock
    s = Settings(base_url=url, rate=0.5, burst=2)
    app = create_app(s, rate_limiter=KeyedRateLimiter(s.rate, s.burst, bucket_factory=TokenBucket))
    with TestClient(app) as c:
        h = {"Authorization": "Bearer dev-key-alice"}
        codes = [c.post("/v1/answer", json={"question": "vacation"}, headers=h) for _ in range(3)]
        assert [r.status_code for r in codes] == [200, 200, 429]
        assert codes[2].headers["retry-after"] == "2"
        assert codes[2].headers["content-type"] == "application/problem+json"
