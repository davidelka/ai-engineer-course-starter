"""Load test for Company Brain API: streaming answers, TTFT measured at the client.

Each simulated user loops: ask a question on /v1/answer/stream, read the SSE
stream to the end, think for a moment, repeat. Two numbers per request go into
locust's statistics:

    "stream total"   time from sending the request to the `done` event
    "TTFT"           time from sending the request to the first `token` event

Both are recorded by hand through locust's request event (with stream=True,
locust's own timer stops when the response HEADERS arrive, which it reports as
"headers"). Only completed streams enter "stream total" and "TTFT", so the
percentiles describe the requests the server accepted. Responses with 429 are
recorded as failures named "429 shed", so you can count load shedding.

Run (the service must use --load-test-keys >= the number of users):
    locust -f labs/26-llm-serving/locustfile.py --host http://127.0.0.1:8000
    locust -f labs/26-llm-serving/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 16 -r 16 -t 30s --csv labs/26-llm-serving/results/u16
"""

from __future__ import annotations

import itertools
import random
import time

from locust import HttpUser, between, task

QUESTIONS = [
    "How many vacation days do I get in my first year?",
    "Can I work remotely from abroad?",
    "Who approves admin access to GitHub?",
    "What is the home office allowance?",
    "Where is the Haifa office?",
]
_ids = itertools.count()


class BrainUser(HttpUser):
    wait_time = between(0.2, 0.6)  # think time between questions

    def on_start(self):
        self.key = f"load-{next(_ids)}"  # one API key per user, so per-key rate limits don't merge

    def _record(self, name: str, ms: float, length: int = 0, exc: Exception | None = None):
        # A synthetic "request" in locust's statistics. response_time is in milliseconds.
        self.environment.events.request.fire(request_type="SSE", name=name, response_time=ms,
                                             response_length=length, exception=exc, context={})

    @task
    def stream_answer(self):
        body = {"question": random.choice(QUESTIONS), "max_tokens": 300}
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "text/event-stream"}
        t0 = time.perf_counter()
        ttft = None
        tokens = 0
        # With stream=True, locust's own timing stops when the HEADERS arrive. That is
        # why the numbers that matter are measured here and recorded by hand.
        with self.client.post("/v1/answer/stream", json=body, headers=headers, stream=True,
                              catch_response=True, name="headers") as resp:
            if resp.status_code == 429:
                resp.success()  # shedding is the server doing its job; counted separately below
                self._record("429 shed", (time.perf_counter() - t0) * 1000, exc=Exception("429"))
                return
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            resp.success()
            event, done, failed = None, False, None
            for raw in resp.iter_lines(decode_unicode=True):
                if raw.startswith("event:"):
                    event = raw[6:].strip()
                elif raw.startswith("data:"):
                    if event == "token":
                        tokens += 1
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                    elif event == "done":
                        done = True
                    elif event == "error":
                        failed = "in-stream error"
                        break
        total_ms = (time.perf_counter() - t0) * 1000
        if failed or not done:
            self._record("stream total", total_ms, tokens, Exception(failed or "stream ended without done"))
            return
        self._record("stream total", total_ms, tokens)
        if ttft is not None:
            self._record("TTFT", ttft * 1000, tokens)
