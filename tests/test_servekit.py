"""servekit (lesson 26): rate limiting, concurrency gate, idempotency, problem+json,
the Company Brain API end to end against the counting mock, and cancellation."""

from __future__ import annotations

import asyncio
import json
import math
import socket
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from mockllm import MockConfig
from servekit import brain
from servekit.app import ClientGone, Settings, create_app, run_until_disconnect
from servekit.async_llm import AsyncLLM, threaded_stream
from servekit.gate import ConcurrencyGate, GateRejected
from servekit.idempotency import IdempotencyStore, fingerprint
from servekit.loadtest import Level, find_knee, level_from_stats, read_locust_stats
from servekit.mock import long_reply, start_counting_in_thread
from servekit.problems import Problem
from servekit.ratelimit import KeyedRateLimiter, TokenBucket, ratelimit_headers

ALICE = {"Authorization": "Bearer dev-key-alice"}


# ------------------------------------------------------------------ token bucket
def test_bucket_burst_then_refill():
    b = TokenBucket(rate=2, burst=3, clock=lambda: 0.0)
    assert [b.try_acquire(now=0.0)[0] for _ in range(3)] == [True, True, True]
    ok, wait = b.try_acquire(now=0.0)
    assert not ok and wait == pytest.approx(0.5)
    assert b.try_acquire(now=0.5) == (True, 0.0)
    assert b.try_acquire(now=100.0)[0] and b.tokens == pytest.approx(2.0)  # capped at burst, minus one


def test_bucket_edge_cases():
    b = TokenBucket(rate=1, burst=2, clock=lambda: 10.0)
    assert b.try_acquire(cost=3, now=10.0) == (False, math.inf)
    b.try_acquire(cost=2, now=10.0)
    assert b.try_acquire(now=5.0)[0] is False  # clock went backwards: no free tokens
    with pytest.raises(ValueError):
        TokenBucket(0, 1)


def test_keyed_limiter_isolates_keys_and_headers():
    t = [0.0]
    lim = KeyedRateLimiter(rate=1, burst=2, clock=lambda: t[0])
    assert lim.check("a").allowed and lim.check("a").allowed
    d = lim.check("a")
    assert not d.allowed and d.retry_after == pytest.approx(1.0)
    assert lim.check("b").allowed  # another key has its own bucket
    h = ratelimit_headers("per-key", d)
    assert h["RateLimit-Policy"] == '"per-key";q=2;w=2'
    assert h["RateLimit"].startswith('"per-key";r=0;t=')


def test_keyed_limiter_evicts_oldest():
    lim = KeyedRateLimiter(rate=1, burst=1, max_keys=2)
    for k in "abc":
        lim.check(k)
    assert len(lim) == 2


# ------------------------------------------------------------------ concurrency gate
def test_gate_admits_queues_and_sheds():
    async def run():
        g = ConcurrencyGate(limit=2, max_queue=1, queue_timeout=0.2)
        await g.acquire()
        await g.acquire()
        waiter = asyncio.create_task(g.acquire())
        await asyncio.sleep(0.01)
        assert g.waiting == 1
        with pytest.raises(GateRejected) as e:  # queue full: refused without waiting
            t0 = time.perf_counter()
            await g.acquire()
        assert e.value.reason == "queue_full" and time.perf_counter() - t0 < 0.05
        assert e.value.retry_after >= 1
        g.release(0.5)
        await asyncio.wait_for(waiter, 1)
        assert g.active == 2 and g.waiting == 0
        with pytest.raises(GateRejected) as e2:  # waits queue_timeout, then refused
            await g.acquire()
        assert e2.value.reason == "queue_timeout"
        assert g.rejected == {"queue_full": 1, "queue_timeout": 1} and g.admitted == 3

    asyncio.run(run())


def test_gate_slot_releases_on_error():
    async def run():
        g = ConcurrencyGate(limit=1)
        with pytest.raises(RuntimeError):
            async with g.slot():
                raise RuntimeError("boom")
        assert g.active == 0
        async with g.slot():
            assert g.active == 1

    asyncio.run(run())


# ------------------------------------------------------------------ idempotency
def test_fingerprint_is_canonical():
    assert fingerprint({"a": 1, "b": "ש"}) == fingerprint({"b": "ש", "a": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})


def test_idempotency_states_and_expiry():
    t = [0.0]
    st = IdempotencyStore(ttl=10, clock=lambda: t[0])
    fp = fingerprint({"q": 1})
    assert st.begin("alice", "k", fp).outcome == "new"
    assert st.begin("alice", "k", fp).outcome == "in_progress"
    assert st.begin("alice", "k", fingerprint({"q": 2})).outcome == "mismatch"
    assert st.begin("bob", "k", fp).outcome == "new"  # scoped per client
    st.complete("alice", "k", 200, {"answer": "x"})
    b = st.begin("alice", "k", fp)
    assert b.outcome == "replay" and b.response == {"answer": "x"} and b.status == 200
    t[0] = 10.0
    assert st.begin("alice", "k", fp).outcome == "new"  # expired
    st.abandon("alice", "k")
    assert st.begin("alice", "k", fp).outcome == "new"


def test_problem_body_shape():
    p = Problem("rate-limited", "slow down", retry_after=2)
    body = p.body("/v1/answer", "rid1")
    assert body["type"].endswith("/rate-limited") and body["status"] == 429
    assert body["title"] and body["retry_after"] == 2 and body["request_id"] == "rid1"


# ------------------------------------------------------------------ app against the counting mock
@pytest.fixture(scope="module")
def counting_mock():
    server, url = start_counting_in_thread(MockConfig(ttft=0, tps=0))
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(counting_mock):
    server, url = counting_mock
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1, reply=long_reply(12))
    server.state.reset()
    server.counters.reset()
    return server, url


def make_client(url, **kw):
    s = Settings(base_url=url, **kw)
    return TestClient(create_app(s))


def test_answer_json_contract(mock):
    _, url = mock
    with make_client(url) as c:
        r = c.post("/v1/answer", json={"question": "How many vacation days do I get?"},
                   headers={**ALICE, "X-Request-ID": "my-trace-1"})
        assert r.status_code == 200
        assert r.headers["x-request-id"] == "my-trace-1"
        assert "ratelimit" in r.headers and "ratelimit-policy" in r.headers
        body = r.json()
        assert body["answer"].startswith("According to the Acme vacation policy")
        assert body["citations"][0]["doc"] == "hr_policies"
        assert body["usage"]["output_tokens"] > 0 and body["stop_reason"] == "end"


def test_errors_are_problem_json(mock):
    _, url = mock
    with make_client(url) as c:
        r = c.post("/v1/answer", json={"question": "hi"})
        assert r.status_code == 401 and r.headers["content-type"] == "application/problem+json"
        assert r.json()["type"].endswith("/unauthenticated") and r.json()["request_id"]
        r = c.post("/v1/answer", json={"question": "", "extra": 1}, headers=ALICE)
        assert r.status_code == 422 and r.headers["content-type"] == "application/problem+json"
        assert {tuple(e["loc"]) for e in r.json()["errors"]} == {("body", "question"), ("body", "extra")}
        assert c.get("/v1/nope").json()["status"] == 404


def test_rate_limit_429_with_retry_after(mock):
    _, url = mock
    with make_client(url, rate=0.5, burst=2) as c:
        codes = [c.post("/v1/answer", json={"question": "x"}, headers=ALICE).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        r = c.post("/v1/answer", json={"question": "x"}, headers=ALICE)
        assert r.headers["retry-after"] == "2" and r.json()["type"].endswith("/rate-limited")
        # another key is not affected
        assert c.post("/v1/answer", json={"question": "x"},
                      headers={"Authorization": "Bearer dev-key-bob"}).status_code == 200


def test_gate_rejection_maps_to_429(mock):
    _, url = mock

    class FullGate(ConcurrencyGate):
        async def acquire(self):
            raise GateRejected("queue_full", 3)

    app = create_app(Settings(base_url=url), gate=FullGate(1))
    with TestClient(app) as c:
        for path in ("/v1/answer", "/v1/answer/stream"):
            r = c.post(path, json={"question": "x"}, headers=ALICE)
            assert r.status_code == 429 and r.headers["retry-after"] == "3"
            assert r.json()["type"].endswith("/overloaded") and r.json()["reason"] == "queue_full"


def test_idempotency_replay_and_mismatch(mock):
    server, url = mock
    with make_client(url) as c:
        h = {**ALICE, "Idempotency-Key": "abc"}
        r1 = c.post("/v1/answer", json={"question": "vacation?"}, headers=h)
        r2 = c.post("/v1/answer", json={"question": "vacation?"}, headers=h)
        assert r2.json() == r1.json() and r2.headers["idempotent-replayed"] == "true"
        assert server.state.requests == 1  # the replay did not call the LLM
        r3 = c.post("/v1/answer", json={"question": "other"}, headers=h)
        assert r3.status_code == 422 and r3.json()["type"].endswith("/idempotency-key-mismatch")


def test_idempotency_failure_is_not_stored(mock):
    server, url = mock
    server.state.cfg.fail_first = 1
    server.state.cfg.status = 500
    with make_client(url) as c:
        h = {**ALICE, "Idempotency-Key": "retry-me"}
        assert c.post("/v1/answer", json={"question": "x"}, headers=h).status_code == 502
        assert c.post("/v1/answer", json={"question": "x"}, headers=h).status_code == 200


@pytest.mark.parametrize("status,expected", [(529, 503), (429, 503), (400, 502)])
def test_upstream_errors(mock, status, expected):
    server, url = mock
    server.state.cfg.fail_rate = 1.0
    server.state.cfg.status = status
    with make_client(url) as c:
        r = c.post("/v1/answer", json={"question": "x"}, headers=ALICE)
        assert r.status_code == expected
        if expected == 503:
            assert int(r.headers["retry-after"]) >= 1


def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        ev = data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:])
        if ev:
            out.append((ev, data))
    return out


@pytest.mark.parametrize("mode", ["async", "thread"])
def test_stream_events(mock, mode):
    _, url = mock
    with make_client(url, stream_mode=mode) as c:
        r = c.post("/v1/answer/stream", json={"question": "vacation days"}, headers=ALICE)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(r.text)
        assert events[0][0] == "meta" and events[-1][0] == "done"
        text = "".join(d["text"] for e, d in events if e == "token")
        assert text == long_reply(12)
        assert events[-1][1]["usage"]["output_tokens"] > 0
        stats = c.get("/admin/stats").json()
        assert stats["upstream"]["finished"] == 1 and stats["gate"]["active"] == 0


def test_in_stream_error_event(mock):
    server, url = mock
    server.state.cfg.error_after = 3
    with make_client(url) as c:
        events = parse_sse(c.post("/v1/answer/stream", json={"question": "x"}, headers=ALICE).text)
        assert [e for e, _ in events].count("token") == 3
        assert events[-1][0] == "error" and events[-1][1]["type"].endswith("/upstream-unavailable")


def test_health_and_ready(mock):
    _, url = mock
    with make_client(url) as c:
        assert c.get("/healthz").json() == {"status": "ok"}
        assert c.get("/readyz").json()["ready"] is True


# ------------------------------------------------------------------ async LLM paths
def test_async_llm_complete_and_stream(mock):
    _, url = mock
    req = brain.build_request("vacation days", 200, brain.retrieve("vacation days"))

    async def run():
        llm = AsyncLLM("mock:mock-model", base_url=url)
        r = await llm.complete(req)
        parts = [ev.text async for ev in llm.stream(req) if ev.type == "text"]
        tparts = [ev.text async for ev in threaded_stream(llm.sync, req) if ev.type == "text"]
        await llm.aclose()
        return r, parts, tparts

    r, parts, tparts = asyncio.run(run())
    assert r.text == "".join(parts) == "".join(tparts) == long_reply(12)


def test_run_until_disconnect_cancels_the_call():
    cancelled = []

    class FakeRequest:
        t0 = time.perf_counter()

        async def is_disconnected(self):
            return time.perf_counter() - self.t0 > 0.1

    async def slow_llm_call():
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    with pytest.raises(ClientGone):
        asyncio.run(run_until_disconnect(FakeRequest(), slow_llm_call(), timeout=2))
    assert cancelled == [True]


# ------------------------------------------------------------------ cancellation over real sockets
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_service(mock):
    import uvicorn

    servers = []

    def start(mode: str):
        server, url = mock
        server.state.cfg = MockConfig(ttft=0.02, tps=100, reply=long_reply(40))
        port = _free_port()
        cfg = uvicorn.Config(create_app(Settings(base_url=url, stream_mode=mode)), host="127.0.0.1",
                             port=port, log_level="warning", access_log=False)
        srv = uvicorn.Server(cfg)
        threading.Thread(target=srv.run, daemon=True).start()
        for _ in range(100):
            if srv.started:
                break
            time.sleep(0.02)
        servers.append(srv)
        return f"http://127.0.0.1:{port}"

    yield start
    for s in servers:
        s.should_exit = True


def _read_then_hang_up(base: str, n: int) -> int:
    got = 0
    with httpx.Client(timeout=10) as c:
        with c.stream("POST", base + "/v1/answer/stream", json={"question": "vacation"}, headers=ALICE) as r:
            for line in r.iter_lines():
                if line.startswith("event: token"):
                    got += 1
                    if got >= n:
                        break
    return got


@pytest.mark.parametrize("mode", ["async", "thread"])
def test_disconnect_stops_upstream(live_service, mock, mode):
    server, _ = mock
    base = live_service(mode)
    assert _read_then_hang_up(base, 3) == 3
    time.sleep(0.8)  # the full answer would take 0.4 s
    d = server.counters.snapshot()
    assert d["aborted"] == 1 and d["completed"] == 0, d
    assert d["text_events_sent"] < 40
    st = httpx.get(base + "/admin/stats").json()
    assert st["upstream"]["closed_early"] == 1 and st["gate"]["active"] == 0


def test_leaky_mode_leaks(live_service, mock):
    server, _ = mock
    base = live_service("leaky")
    _read_then_hang_up(base, 3)
    time.sleep(0.8)
    d = server.counters.snapshot()
    assert d["completed"] == 1 and d["aborted"] == 0 and d["text_events_sent"] == 40


# ------------------------------------------------------------------ load-test helpers and retrieval
def test_locust_csv_and_knee(tmp_path):
    p = tmp_path / "u8_stats.csv"
    p.write_text(
        "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,"
        "Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,"
        "99.99%,100%\n"
        "SSE,TTFT,40,0,340,353,311,448,60,3.5,0.0,340,350,360,430,440,440,450,450,450,450,450\n"
        "SSE,stream total,40,0,1800,1850,1700,2100,60,3.5,0.0,1800,1850,1900,1900,2000,2000,2100,2100,2100,2100,2100\n"
        "SSE,429 shed,10,10,4,4,3,5,0,1.0,1.0,4,4,4,4,5,5,5,5,5,5,5\n", encoding="utf-8")
    lv = level_from_stats(8, read_locust_stats(p))
    assert (lv.p50_ms, lv.p95_ms, lv.ttft_p95_ms, lv.rps, lv.failures) == (1800, 2000, 440, 3.5, 10)
    levels = [Level(4, 1.8, 1800, 1900, 320, 360, 10, 0), lv, Level(16, 4.0, 3300, 3900, 1800, 2300, 10, 0)]
    assert find_knee(levels).users == 8


def test_brain_retrieval_finds_policy():
    hits = brain.retrieve("How many vacation days do I get in my first year?")
    assert hits and hits[0].doc == "hr_policies" and "14 paid vacation days" in hits[0].text
    req = brain.build_request("q", 100, hits)
    assert '<source id="1"' in req.messages[0].text and "Cite sources" in req.system
