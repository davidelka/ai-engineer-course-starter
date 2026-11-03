"""Exercise 4: prove that a client disconnect stops the upstream LLM stream.

Needs the counting mock and the service (two terminals):
    python -m servekit.mock --ttft 0.2 --tps 20 --words 100      # a 5-second answer
    python -m servekit --stream-mode async                        # then thread, then leaky

Then:
    python labs/26-llm-serving/cancel_demo.py --after 10

It opens one stream, reads `--after` token events, and hangs up. Then it reads
two sets of counters:
  - the mock's /__admin/stats "streams_detail": did the UPSTREAM stream end
    early ("aborted") or run to the end ("completed") although nobody was reading?
  - the service's /admin/stats "upstream": what the service thinks happened.
It reads them right after the disconnect and again after the answer would have
finished, so a leak (text_events_sent still growing) is visible.
"""

from __future__ import annotations

import argparse
import json
import time

import httpx


def mock_streams(mock: str) -> dict:
    return httpx.get(mock + "/__admin/stats").json().get("streams_detail", {})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--mock", default="http://127.0.0.1:8765")
    p.add_argument("--after", type=int, default=10, help="token events to read before hanging up")
    p.add_argument("--wait", type=float, default=6.0, help="seconds to wait before the second look")
    a = p.parse_args()

    try:
        httpx.post(a.mock + "/__admin/reset")
        if "streams_detail" not in httpx.get(a.mock + "/__admin/stats").json():
            print("note: this mock has no stream counters; start it with: python -m servekit.mock\n")
    except httpx.ConnectError:
        raise SystemExit(f"no mock at {a.mock}: python -m servekit.mock --ttft 0.2 --tps 20 --words 100")

    before = httpx.get(a.url + "/admin/stats").json()["upstream"]
    mode = httpx.get(a.url + "/readyz").json().get("stream_mode")
    print(f"service stream_mode = {mode}")
    got = 0
    t0 = time.perf_counter()
    with httpx.Client(timeout=30) as c:
        with c.stream("POST", a.url + "/v1/answer/stream", json={"question": "How many vacation days do I get?"},
                      headers={"Authorization": "Bearer dev-key-alice"}) as r:
            event = None
            for line in r.iter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:") and event == "token":
                    got += 1
                    if got >= a.after:
                        break
        # leaving the `with` blocks closes the connection: this is the "user closed the tab"
    print(f"read {got} tokens in {time.perf_counter() - t0:.2f}s, then disconnected\n")

    time.sleep(0.5)
    print("0.5s after disconnect")
    print("  mock (upstream truth): ", json.dumps(mock_streams(a.mock)))
    up = httpx.get(a.url + "/admin/stats").json()["upstream"]
    delta = {k: up[k] - before.get(k, 0) for k in ("opened", "finished", "closed_early", "events")}
    print("  service (its own view):", json.dumps({**delta, "active": up["active"]}))
    time.sleep(a.wait)
    print(f"\n{a.wait:g}s later")
    ms = mock_streams(a.mock)
    print("  mock (upstream truth): ", json.dumps(ms))
    if ms.get("aborted"):
        print("\nverdict: the upstream stream was ABORTED shortly after the disconnect. No leak.")
    elif ms.get("completed"):
        print(f"\nverdict: LEAK. The upstream sent {ms.get('text_events_sent')} token events, the client read {got}.")
        print("The service stopped writing to the client, but the upstream stream ran to the end (and was billed).")


if __name__ == "__main__":
    main()
