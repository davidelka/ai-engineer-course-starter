"""Exercise 1: a small Python client for Company Brain API, measuring from the client side.

    python labs/26-llm-serving/client.py "How many vacation days do I get?"
    python labs/26-llm-serving/client.py --json "Who approves admin access?"
    python labs/26-llm-serving/client.py --concurrent 12 "Where is the Haifa office?"

Streaming mode prints tokens as they arrive, then:
    TTFT (client)   send -> first `token` event, as the user experiences it
    total (client)  send -> `done` event
    server says     the ttft/latency the server measured to its upstream, from `done`
The gap between the client TTFT and the server's upstream TTFT is your
service's own overhead (auth, rate limit, queueing in the gate, retrieval).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import httpx


async def stream_once(client: httpx.AsyncClient, url: str, key: str, question: str, quiet: bool) -> dict:
    t0 = time.perf_counter()
    out = {"status": 0, "ttft": None, "total": None, "tokens": 0, "server": None, "error": None}
    async with client.stream("POST", url + "/v1/answer/stream", json={"question": question},
                             headers={"Authorization": f"Bearer {key}"}) as r:
        out["status"] = r.status_code
        if r.status_code != 200:
            body = json.loads(await r.aread())
            out["error"] = f"{body.get('title')} (retry after {r.headers.get('retry-after', '-')}s)"
            return out
        event = None
        async for line in r.aiter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:])
                if event == "meta" and not quiet:
                    cites = ", ".join(f"[{c['n']}] {c['doc']}" for c in data["citations"])
                    print(f"request {r.headers.get('x-request-id')}  sources: {cites}\n")
                elif event == "token":
                    if out["ttft"] is None:
                        out["ttft"] = time.perf_counter() - t0
                    out["tokens"] += 1
                    if not quiet:
                        print(data["text"], end="", flush=True)
                elif event == "done":
                    out["server"] = data
                elif event == "error":
                    out["error"] = data.get("title")
    out["total"] = time.perf_counter() - t0
    return out


async def main_async(a) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        if a.json:
            t0 = time.perf_counter()
            r = await client.post(a.url + "/v1/answer", json={"question": a.question},
                                  headers={"Authorization": f"Bearer {a.key}"})
            print(f"HTTP {r.status_code}  content-type: {r.headers.get('content-type')}  "
                  f"request-id: {r.headers.get('x-request-id')}")
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
            print(f"\ntotal (client): {(time.perf_counter() - t0) * 1000:.0f} ms")
            return
        if a.concurrent <= 1:
            res = await stream_once(client, a.url, a.key, a.question, quiet=False)
            print("\n")
            if res["error"]:
                print(f"HTTP {res['status']}: {res['error']}")
                return
            s = res["server"] or {}
            print(f"TTFT (client): {res['ttft'] * 1000:.0f} ms   total (client): {res['total'] * 1000:.0f} ms   "
                  f"tokens: {res['tokens']}")
            print(f"server says: upstream ttft {s.get('ttft_ms')} ms, upstream latency {s.get('latency_ms')} ms, "
                  f"cost ${s.get('cost_usd')}")
            return
        results = await asyncio.gather(*[stream_once(client, a.url, f"load-{i}" if a.load_keys else a.key,
                                                     a.question, quiet=True) for i in range(a.concurrent)])
        for i, res in enumerate(results):
            if res["error"]:
                print(f"#{i:<3} HTTP {res['status']}  {res['error']}")
            else:
                print(f"#{i:<3} HTTP 200  TTFT {res['ttft'] * 1000:6.0f} ms   total {res['total'] * 1000:6.0f} ms")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="?", default="How many vacation days do I get in my first year?")
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--key", default="dev-key-alice")
    p.add_argument("--json", action="store_true", help="use POST /v1/answer instead of streaming")
    p.add_argument("--concurrent", type=int, default=1, help="send N streams at once")
    p.add_argument("--load-keys", action="store_true", help="with --concurrent: one load-<i> key per stream")
    a = p.parse_args()
    try:
        asyncio.run(main_async(a))
    except httpx.ConnectError:
        sys.exit(f"cannot connect to {a.url}: start the service first (python -m servekit)")


if __name__ == "__main__":
    main()
