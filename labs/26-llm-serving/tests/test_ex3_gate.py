"""Exercise 3: a concurrency gate with a bounded queue and a queue timeout."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from mine import ConcurrencyGate
from servekit.gate import GateRejected


def run(coro):
    return asyncio.run(coro)


def test_admits_up_to_limit():
    async def go():
        g = ConcurrencyGate(limit=3, max_queue=0)
        for _ in range(3):
            await g.acquire()
        assert g.active == 3 and g.admitted == 3
    run(go())


def test_queue_full_is_refused_instantly():
    async def go():
        g = ConcurrencyGate(limit=1, max_queue=1, queue_timeout=5)
        await g.acquire()
        waiter = asyncio.create_task(g.acquire())
        await asyncio.sleep(0.01)
        assert g.waiting == 1
        t0 = time.perf_counter()
        with pytest.raises(GateRejected) as e:
            await g.acquire()
        assert time.perf_counter() - t0 < 0.05, "shedding must not wait"
        assert e.value.reason == "queue_full" and g.rejected["queue_full"] == 1
        waiter.cancel()
    run(go())


def test_zero_queue_means_no_waiting_at_all():
    async def go():
        g = ConcurrencyGate(limit=1, max_queue=0, queue_timeout=5)
        await g.acquire()
        with pytest.raises(GateRejected) as e:
            await g.acquire()
        assert e.value.reason == "queue_full"
    run(go())


def test_waiter_gets_the_slot_when_released():
    async def go():
        g = ConcurrencyGate(limit=1, max_queue=2, queue_timeout=1)
        await g.acquire()
        waiter = asyncio.create_task(g.acquire())
        await asyncio.sleep(0.01)
        g.release(0.1)
        await asyncio.wait_for(waiter, 1)
        assert g.active == 1 and g.waiting == 0 and g.admitted == 2
    run(go())


def test_queue_timeout_refuses_and_cleans_up():
    async def go():
        g = ConcurrencyGate(limit=1, max_queue=3, queue_timeout=0.1)
        await g.acquire()
        t0 = time.perf_counter()
        with pytest.raises(GateRejected) as e:
            await g.acquire()
        assert 0.08 < time.perf_counter() - t0 < 0.5
        assert e.value.reason == "queue_timeout" and g.rejected["queue_timeout"] == 1
        assert g.waiting == 0 and g.active == 1
        g.release()
        await asyncio.wait_for(g.acquire(), 0.5)  # the timed-out waiter did not steal the slot
    run(go())


def test_no_queue_jumping():
    async def go():
        g = ConcurrencyGate(limit=1, max_queue=5, queue_timeout=1)
        await g.acquire()
        order = []

        async def take(name):
            await g.acquire()
            order.append(name)

        first = asyncio.create_task(take("first"))
        await asyncio.sleep(0.01)
        g.release()  # the slot is free for a moment, but "first" is waiting for it
        second = asyncio.create_task(take("second"))
        await asyncio.sleep(0.01)
        assert order == ["first"]
        g.release()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert order == ["first", "second"]
    run(go())


def test_retry_after():
    g = ConcurrencyGate(limit=4, max_queue=10)
    g._avg_service = 2.0
    g.waiting = 7
    assert g.retry_after() == 4  # ceil(2.0 * 8 / 4)
    g.waiting = 0
    g._avg_service = 0.1
    assert g.retry_after() == 1  # never below 1
    assert isinstance(g.retry_after(), int)


def test_the_service_sheds_with_your_gate(mock):
    from servekit.app import Settings, create_app

    _, url = mock
    gate = ConcurrencyGate(limit=1, max_queue=0, queue_timeout=0.1)
    app = create_app(Settings(base_url=url), gate=gate)

    async def release():
        gate.release()

    with TestClient(app) as c:
        h = {"Authorization": "Bearer dev-key-alice"}
        c.portal.call(gate.acquire)  # occupy the only slot, as a long request would (on the app's event loop)
        for path in ("/v1/answer", "/v1/answer/stream"):
            r = c.post(path, json={"question": "vacation"}, headers=h)
            assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
            assert r.headers["content-type"] == "application/problem+json"
            assert r.json()["type"].endswith("/overloaded")
        c.portal.call(release)
        assert c.post("/v1/answer", json={"question": "vacation"}, headers=h).status_code == 200
        assert c.post("/v1/answer/stream", json={"question": "vacation"}, headers=h).status_code == 200
        assert gate.active == 0 and gate.rejected["queue_full"] == 2
