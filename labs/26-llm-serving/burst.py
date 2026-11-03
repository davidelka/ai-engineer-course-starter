"""Exercises 2 and 3: hit the service with a burst and look at what comes back.

    python labs/26-llm-serving/burst.py --n 12                 # 12 requests, one after another, one key
    python labs/26-llm-serving/burst.py --n 30 --parallel      # 30 streams at once, one key per request

Sequential mode shows the token bucket: the first `burst` requests pass, then
429 rate-limited with Retry-After, and requests pass again as tokens refill.
Parallel mode (use a service with a high --rate) shows the concurrency gate:
`limit` streams run, up to `max_queue` wait, the rest get 429 overloaded at once,
and some queued ones get 429 after waiting queue_timeout.
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx


def line(i: int, t: float, r: httpx.Response, extra: str = "") -> str:
    ra = r.headers.get("retry-after")
    rl = r.headers.get("ratelimit", "")
    kind = ""
    if r.headers.get("content-type", "").startswith("application/problem+json"):
        kind = r.json().get("type", "").rsplit("/", 1)[-1]
    return (f"#{i:<3} t={t:5.2f}s  HTTP {r.status_code}  {kind:<14} "
            f"{'Retry-After: ' + ra if ra else '':<15} {rl} {extra}")


def sequential(a) -> None:
    t0 = time.perf_counter()
    with httpx.Client(base_url=a.url, timeout=30) as c:
        for i in range(a.n):
            r = c.post("/v1/answer", json={"question": "How many vacation days do I get?", "max_tokens": 32},
                       headers={"Authorization": f"Bearer {a.key}"})
            print(line(i, time.perf_counter() - t0, r))
            if a.sleep:
                time.sleep(a.sleep)


async def parallel(a) -> None:
    t0 = time.perf_counter()

    async def one(c: httpx.AsyncClient, i: int):
        key = f"load-{i}" if a.load_keys else a.key
        start = time.perf_counter()
        async with c.stream("POST", "/v1/answer/stream", json={"question": "Where is the Haifa office?"},
                            headers={"Authorization": f"Bearer {key}"}) as r:
            await r.aread()
            return i, start - t0, time.perf_counter() - start, r

    async with httpx.AsyncClient(base_url=a.url, timeout=60,
                                 limits=httpx.Limits(max_connections=a.n + 5)) as c:
        results = await asyncio.gather(*[one(c, i) for i in range(a.n)])
    for i, _, dur, r in sorted(results, key=lambda x: x[2]):
        print(line(i, dur, r, "(t = time until the response ended)"))
    codes = [r.status_code for *_, r in results]
    print(f"\n200: {codes.count(200)}   429: {codes.count(429)}   other: {len(codes) - codes.count(200) - codes.count(429)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--key", default="dev-key-bob")
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--sleep", type=float, default=0.0, help="sequential: pause between requests")
    p.add_argument("--parallel", action="store_true")
    p.add_argument("--load-keys", action="store_true", help="parallel: load-<i> key per request (needs --load-test-keys)")
    a = p.parse_args()
    if a.parallel:
        asyncio.run(parallel(a))
    else:
        sequential(a)


if __name__ == "__main__":
    main()
