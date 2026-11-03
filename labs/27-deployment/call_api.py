"""Talk to the deployed (or local) Company Brain API.

    python labs/27-deployment/call_api.py                                   # local compose, :8000
    python labs/27-deployment/call_api.py --url http://127.0.0.1:8001 -q "What is Acme's VPN policy?"
    python labs/27-deployment/call_api.py --url "$(terraform -chdir=labs/27-deployment/terraform output -raw url)" --stream
    python labs/27-deployment/call_api.py --url ... --load 300 --concurrency 20   # for the autoscaling step

Prints the health endpoints, then one answer (or a stream with time to first token), or a
small load test with latency percentiles. Every answer costs whatever the configured model
costs: with the mock it is free, with Haiku 5.5 a few hundred tokens is a fraction of a cent.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx


def show_health(c: httpx.Client) -> None:
    for path in ("/healthz", "/readyz"):
        try:
            r = c.get(path, timeout=5)
            print(f"GET {path:8} {r.status_code}  {r.text[:160]}")
        except httpx.HTTPError as exc:
            print(f"GET {path:8} FAILED  {type(exc).__name__}: {exc}")


def ask(c: httpx.Client, q: str, max_tokens: int) -> dict:
    t0 = time.perf_counter()
    r = c.post("/v1/answer", json={"question": q, "max_tokens": max_tokens}, timeout=120)
    out = {"status": r.status_code, "s": time.perf_counter() - t0}
    try:
        out.update(r.json())
    except json.JSONDecodeError:
        out["body"] = r.text[:200]
    return out


def stream(c: httpx.Client, q: str, max_tokens: int) -> None:
    t0, first = time.perf_counter(), None
    with c.stream("POST", "/v1/answer/stream", json={"question": q, "max_tokens": max_tokens}, timeout=120) as r:
        print(f"POST /v1/answer/stream {r.status_code}")
        event = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if event == "text":
                    if first is None:
                        first = time.perf_counter() - t0
                    print(data["text"], end="", flush=True)
                else:
                    print(f"\n[{event}] {data}")
    print(f"time to first chunk: {first:.2f}s, total: {time.perf_counter() - t0:.2f}s" if first else "no text received")


def load(c: httpx.Client, n: int, conc: int, max_tokens: int) -> None:
    print(f"load: {n} requests, {conc} at a time ...")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(conc) as pool:
        res = list(pool.map(lambda i: ask(c, f"Load test question {i}: name one Acme value.", max_tokens), range(n)))
    wall = time.perf_counter() - t0
    lat = sorted(r["s"] for r in res)
    codes: dict = {}
    for r in res:
        codes[r["status"]] = codes.get(r["status"], 0) + 1
    cost = sum(r.get("cost_usd") or 0 for r in res)
    p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]  # noqa: E731
    print(f"status codes: {codes}   wall: {wall:.1f}s   throughput: {n / wall:.1f} req/s")
    print(f"latency p50 {statistics.median(lat):.2f}s  p95 {p(0.95):.2f}s  max {lat[-1]:.2f}s   model cost: ${cost:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("-q", "--question", default="In one sentence: why should an API key never be baked into a container image?")
    ap.add_argument("--max-tokens", type=int, default=150)
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--load", type=int, default=0, help="number of requests for a small load test")
    ap.add_argument("--concurrency", type=int, default=10)
    a = ap.parse_args()
    with httpx.Client(base_url=a.url.rstrip("/")) as c:
        show_health(c)
        if a.load:
            load(c, a.load, a.concurrency, a.max_tokens)
        elif a.stream:
            stream(c, a.question, a.max_tokens)
        else:
            r = ask(c, a.question, a.max_tokens)
            print(f"POST /v1/answer {r['status']} in {r['s']:.2f}s")
            print(json.dumps({k: v for k, v in r.items() if k not in ("s", "status")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
