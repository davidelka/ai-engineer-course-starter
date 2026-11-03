"""Exercise 7: the error contract. Provoke every error type and print what a client sees.

    python labs/26-llm-serving/errors_tour.py

Prints, for each case: status, Content-Type, the problem `type`, and the body.
A client should be able to switch on `type` (stable) and show `detail` (human).
The upstream cases need the mock to fail: the script switches mockllm's faults
on through /__admin/config and back off at the end.
"""

from __future__ import annotations

import argparse
import json

import httpx

AUTH = {"Authorization": "Bearer dev-key-alice"}
BOB = {"Authorization": "Bearer dev-key-bob"}  # a second client, so the tour itself stays under the rate limit


def show(title: str, r: httpx.Response) -> None:
    print(f"--- {title}")
    print(f"HTTP {r.status_code}   content-type: {r.headers.get('content-type')}"
          + (f"   Retry-After: {r.headers['retry-after']}" if "retry-after" in r.headers else ""))
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(r.text[:300])
    print()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--mock", default="http://127.0.0.1:8765")
    a = p.parse_args()
    c = httpx.Client(base_url=a.url, timeout=30)
    show("no API key", c.post("/v1/answer", json={"question": "hi"}))
    show("invalid body (empty question, unknown field)",
         c.post("/v1/answer", json={"question": "", "temperature": 2}, headers=AUTH))
    show("unknown path", c.get("/v2/answer"))
    show("wrong method", c.get("/v1/answer"))
    k = {"Idempotency-Key": "tour-1", **AUTH}
    c.post("/v1/answer", json={"question": "vacation days?"}, headers=k)
    show("Idempotency-Key reused with a different body",
         c.post("/v1/answer", json={"question": "something else"}, headers=k))
    try:
        httpx.post(a.mock + "/__admin/config", json={"fail_rate": 1.0, "status": 529})
        show("upstream overloaded (mock returns 529)", c.post("/v1/answer", json={"question": "x"}, headers=BOB))
        httpx.post(a.mock + "/__admin/config", json={"fail_rate": 1.0, "status": 400})
        show("upstream rejects the request (mock returns 400)",
             c.post("/v1/answer", json={"question": "x"}, headers=BOB))
        httpx.post(a.mock + "/__admin/config", json={"fail_rate": 0.0, "error_after": 3})
        with c.stream("POST", "/v1/answer/stream", json={"question": "x"}, headers=BOB) as r:
            print("--- error AFTER the stream started (mock sends an in-stream error after 3 tokens)")
            print(f"HTTP {r.status_code} (already sent, cannot change now)   the last events:")
            print("\n".join(list(r.iter_lines())[-4:]))
    finally:
        httpx.post(a.mock + "/__admin/config", json={"fail_rate": 0.0, "error_after": 0, "status": 529})


if __name__ == "__main__":
    main()
