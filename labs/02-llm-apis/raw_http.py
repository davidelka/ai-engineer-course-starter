"""Exercises 1-2: call a provider with plain httpx, no SDK, and look at everything.

    python labs/02-llm-apis/raw_http.py --provider anthropic
    python labs/02-llm-apis/raw_http.py --provider anthropic --stream
    python labs/02-llm-apis/raw_http.py --provider openai --stream --mock      # no key, no cost
    python labs/02-llm-apis/raw_http.py --provider gemini --mock --show-body

Prints the request (key masked), every response header, and then either the
JSON body or every SSE event with the time it arrived.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from llmkit import load_dotenv  # noqa: E402

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.6-flash"}
MOCK = os.environ.get("MOCKLLM_URL", "http://127.0.0.1:8765")


def build(provider: str, model: str, key: str, prompt: str, stream: bool, max_tokens: int):
    """Written out by hand per provider on purpose: compare the three shapes."""
    if provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        body = {"model": model, "max_tokens": max_tokens, "system": "Answer in one short sentence.",
                "messages": [{"role": "user", "content": prompt}]}
        if stream:
            body["stream"] = True
    elif provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers = {"authorization": f"Bearer {key}", "content-type": "application/json"}
        body = {"model": model, "instructions": "Answer in one short sentence.",
                "input": prompt, "max_output_tokens": max_tokens}
        if stream:
            body["stream"] = True
    else:
        verb = "streamGenerateContent?alt=sse" if stream else "generateContent"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{verb}"
        headers = {"x-goog-api-key": key, "content-type": "application/json"}
        body = {"systemInstruction": {"parts": [{"text": "Answer in one short sentence."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens}}
    return url, headers, body


def mask(headers: dict) -> dict:
    secret = {"x-api-key", "authorization", "x-goog-api-key"}
    return {k: (v[:7] + "…" if k.lower() in secret else v) for k, v in headers.items()}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=list(DEFAULT_MODELS), default="anthropic")
    p.add_argument("--model")
    p.add_argument("--prompt", default="Name two colors.")
    p.add_argument("--stream", action="store_true")
    p.add_argument("--max-tokens", type=int, default=300)
    p.add_argument("--mock", action="store_true", help=f"send to the mock server at {MOCK}")
    p.add_argument("--show-body", action="store_true", help="print the request body")
    a = p.parse_args()

    load_dotenv(str(ROOT / ".env"))
    env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[a.provider]
    key = "mock-key" if a.mock else os.environ.get(env, "")
    if not key:
        sys.exit(f"{env} is not set in .env. Use --mock to try against the mock server.")
    model = a.model or ("mock-model" if a.mock else DEFAULT_MODELS[a.provider])
    url, headers, body = build(a.provider, model, key, a.prompt, a.stream, a.max_tokens)
    if a.mock:
        url = MOCK + url[url.index("/v1"):]

    print(f"POST {url}")
    for k, v in mask(headers).items():
        print(f"  {k}: {v}")
    if a.show_body:
        print(json.dumps(body, indent=2, ensure_ascii=False))

    t0 = time.perf_counter()
    with httpx.Client(timeout=httpx.Timeout(60, connect=5)) as http:
        if not a.stream:
            r = http.post(url, headers=headers, json=body)
            print(f"\nHTTP {r.status_code}  ({time.perf_counter() - t0:.2f}s)")
            for k, v in r.headers.items():
                print(f"  {k}: {v}")
            print()
            try:
                print(json.dumps(r.json(), indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(r.text)
            return

        with http.stream("POST", url, headers=headers, json=body) as r:
            print(f"\nHTTP {r.status_code}  headers after {time.perf_counter() - t0:.2f}s")
            for k, v in r.headers.items():
                print(f"  {k}: {v}")
            print("\n--- raw stream (t = seconds since request) ---")
            n = 0
            for line in r.iter_lines():
                if line:
                    n += 1
                    print(f"{time.perf_counter() - t0:6.2f}  {line[:160]}")
            print(f"--- connection closed after {time.perf_counter() - t0:.2f}s, {n} non-empty lines ---")
            print("Did you see the provider's end-of-stream event? If not, the stream was cut.")


if __name__ == "__main__":
    main()
