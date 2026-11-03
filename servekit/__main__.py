"""python -m servekit --model mock:mock-model --port 8000 --max-concurrency 8 --max-queue 16

Runs Company Brain API v0 with uvicorn. With no --model and no ANTHROPIC_API_KEY
it uses the mock server (start it first: python -m servekit.mock).
"""

from __future__ import annotations

import argparse
import os

import uvicorn

from llmkit import load_dotenv

from .app import Settings, create_app


def build_parser() -> argparse.ArgumentParser:
    d = Settings()
    p = argparse.ArgumentParser(prog="servekit", description="Company Brain API v0 (lesson 26)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--model", default=os.environ.get("SERVEKIT_MODEL", d.model),
                   help="llmkit spec, e.g. mock:mock-model or anthropic:claude-haiku-5-5")
    p.add_argument("--upstream-url", default=None, help="override the provider/mock base URL")
    p.add_argument("--stream-mode", choices=["async", "thread", "leaky"], default=d.stream_mode)
    p.add_argument("--max-concurrency", type=int, default=d.max_concurrency)
    p.add_argument("--max-queue", type=int, default=d.max_queue)
    p.add_argument("--queue-timeout", type=float, default=d.queue_timeout)
    p.add_argument("--rate", type=float, default=d.rate, help="requests/second per API key")
    p.add_argument("--burst", type=float, default=d.burst)
    p.add_argument("--request-timeout", type=float, default=d.request_timeout)
    p.add_argument("--first-token-timeout", type=float, default=d.first_token_timeout)
    p.add_argument("--load-test-keys", type=int, default=0,
                   help="also accept load-<i> keys (i < N), one client per locust user")
    return p


def settings_from_args(a) -> Settings:
    s = Settings(model=a.model, base_url=a.upstream_url, stream_mode=a.stream_mode, max_concurrency=a.max_concurrency,
                 max_queue=a.max_queue, queue_timeout=a.queue_timeout, rate=a.rate, burst=a.burst,
                 request_timeout=a.request_timeout, first_token_timeout=a.first_token_timeout)
    for i in range(a.load_test_keys):
        s.api_keys[f"load-{i}"] = f"load-{i}"
    return s


def main() -> None:
    load_dotenv()
    a = build_parser().parse_args()
    s = settings_from_args(a)
    print(f"Company Brain API on http://{a.host}:{a.port}  model={s.model}  stream_mode={s.stream_mode}  "
          f"gate={s.max_concurrency}+{s.max_queue}q/{s.queue_timeout}s  rate={s.rate}/s burst={s.burst}")
    print("docs: /docs   health: /healthz /readyz   stats: /admin/stats   dev keys: dev-key-alice, dev-key-bob")
    uvicorn.run(create_app(s), host=a.host, port=a.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
