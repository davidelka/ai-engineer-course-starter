"""mockllm with stream accounting, for the cancellation and load-test exercises.

    python -m servekit.mock --port 8765 --ttft 0.3 --tps 40 --words 120

This does not change mockllm. It subclasses mockllm's request handler and
counts, per streaming response, whether the stream ran to its end or the
client went away in the middle (the write failed). GET /__admin/stats then
has an extra "streams_detail" block:

    {"started": 3, "active": 0, "completed": 2, "aborted": 1, "text_events_sent": 260}

"aborted" is the proof that the upstream noticed the disconnect and stopped
generating. A leak shows up as "completed" streams that nobody read.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import ThreadingHTTPServer
from typing import Optional

from mockllm.server import MockConfig, State, make_handler

TEXT_EVENTS = {"content_block_delta", "response.output_text.delta"}

FILLER = ("According to the Acme vacation policy, full-time employees receive 14 paid vacation days in "
          "their first year, and the allowance grows by one day per year of service up to 24 days. "
          "Requests of three days or more go through the HR portal two weeks in advance. ")


def long_reply(words: int) -> str:
    base = FILLER.split()
    return " ".join(base[i % len(base)] for i in range(max(1, words)))


class StreamCounters:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.started = self.active = self.completed = self.aborted = self.text_events_sent = 0

    def snapshot(self) -> dict:
        with self.lock:
            return {"started": self.started, "active": self.active, "completed": self.completed,
                    "aborted": self.aborted, "text_events_sent": self.text_events_sent}


def make_counting_handler(state: State, counters: StreamCounters):
    Base = make_handler(state)

    class CountingHandler(Base):
        def _event(self, name, obj, corrupt=False):
            ok = super()._event(name, obj, corrupt)
            if not ok:
                self._aborted = True
            elif name in TEXT_EVENTS or (name is None and isinstance(obj, dict) and "candidates" in obj):
                with counters.lock:
                    counters.text_events_sent += 1
            return ok

        def do_GET(self):
            if self.path == "/__admin/stats":
                body = state.stats()
                body["streams_detail"] = counters.snapshot()
                return self._send_json(200, body)
            return super().do_GET()

        def do_POST(self):
            if self.path == "/__admin/reset":
                with counters.lock:
                    counters.reset()
            return super().do_POST()

    def wrap(orig):
        def run(self, *a, **kw):
            self._aborted = False
            with counters.lock:
                counters.started += 1
                counters.active += 1
            try:
                return orig(self, *a, **kw)
            finally:
                with counters.lock:
                    counters.active -= 1
                    if self._aborted:
                        counters.aborted += 1
                    else:
                        counters.completed += 1
        return run

    for flavor in ("anthropic", "openai", "gemini"):
        name = f"_stream_{flavor}"
        setattr(CountingHandler, name, wrap(getattr(Base, name)))
    return CountingHandler


def start_counting_in_thread(cfg: Optional[MockConfig] = None, host: str = "127.0.0.1", port: int = 0):
    """Like mockllm.start_in_thread; server.counters holds the stream counters."""
    state = State(cfg or MockConfig())
    counters = StreamCounters()
    server = ThreadingHTTPServer((host, port), make_counting_handler(state, counters))
    server.daemon_threads = True
    server.state, server.counters = state, counters
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://{host}:{server.server_address[1]}"


def main() -> None:
    p = argparse.ArgumentParser(prog="servekit.mock", description="mockllm + stream accounting (lesson 26)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--latency", type=float, default=0.0, help="seconds before any response bytes")
    p.add_argument("--ttft", type=float, default=0.3, help="streaming: seconds to the first token")
    p.add_argument("--tps", type=float, default=40.0, help="streaming: tokens per second")
    p.add_argument("--words", type=int, default=120, help="answer length in words (0 = mockllm's short echo)")
    p.add_argument("--fail-rate", type=float, default=0.0)
    p.add_argument("--status", type=int, default=529)
    p.add_argument("--retry-after", type=float, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    cfg = MockConfig(reply=long_reply(a.words) if a.words else "", latency=a.latency, ttft=a.ttft, tps=a.tps,
                     fail_rate=a.fail_rate, status=a.status, retry_after=a.retry_after)
    state = State(cfg)
    counters = StreamCounters()
    server = ThreadingHTTPServer((a.host, a.port), make_counting_handler(state, counters))
    server.daemon_threads = True
    server.verbose = a.verbose
    server.request_queue_size = 256  # the load test opens many connections at once
    print(f"servekit.mock (mockllm + stream counters) on http://{a.host}:{a.port}")
    print(f"ttft={a.ttft}s tps={a.tps} words={a.words} latency={a.latency}s  stats: GET /__admin/stats")
    print(json.dumps({"fail_rate": a.fail_rate, "status": a.status}) if a.fail_rate else "", end="")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
