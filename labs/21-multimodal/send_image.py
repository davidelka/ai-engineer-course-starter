"""Exercise 1: send an image to Claude, first as raw HTTP, then through llmkit.

    python labs/21-multimodal/send_image.py                       # Claude Haiku 5.5 (needs ANTHROPIC_API_KEY)
    python labs/21-multimodal/send_image.py --mock                # free: the local mock server
    python labs/21-multimodal/send_image.py --image error_dialog.png --question "What error code is shown?"
    python labs/21-multimodal/send_image.py --mock --provider openai   # the same image in OpenAI's shape
    python labs/21-multimodal/send_image.py --count-only          # free: Anthropic count_tokens, no answer

Prints the request JSON (the base64 cut short), the reply, and the usage: how many input tokens
the image cost, next to the formula's estimate.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time

import httpx

import _lab  # noqa: F401  (paths)
from _lab import ROOT, for_model, make_llm
from acme_vision import IMAGES
from llmkit import ChatRequest, Image, Message, load_dotenv
from llmkit.media import image_info, image_tokens

MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.6-flash"}


def short(obj):
    """The request with every long base64 string cut, so it fits on screen."""
    if isinstance(obj, dict):
        return {k: short(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [short(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 120:
        return obj[:60] + f"...<{len(obj):,} chars>"
    return obj


def raw_anthropic(base: str, key: str, data: bytes, question: str, count_only: bool) -> None:
    info = image_info(data)
    body = {
        "model": MODELS["anthropic"], "max_tokens": 300,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": info.media_type,
                                         "data": base64.b64encode(data).decode("ascii")}},
            {"type": "text", "text": question}]}],
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    print("===== request 1: raw HTTP, POST /v1/messages")
    print(json.dumps(short(body), indent=2, ensure_ascii=False))
    print(f"(request body: {len(json.dumps(body)):,} bytes; the image file is {len(data):,} bytes, "
          f"base64 makes it ~4/3 larger)")
    est = image_tokens("anthropic", MODELS["anthropic"], info.width, info.height)
    if count_only:  # free endpoint: the exact prompt size, no answer
        r = httpx.post(base + "/v1/messages/count_tokens", headers=headers,
                       json={k: v for k, v in body.items() if k != "max_tokens"}, timeout=60)
        r.raise_for_status()
        text_only = httpx.post(base + "/v1/messages/count_tokens", headers=headers, timeout=60, json={
            "model": body["model"], "messages": [{"role": "user", "content": question}]}).json()["input_tokens"]
        total = r.json()["input_tokens"]
        print(f"\ncount_tokens: {total} with the image, {text_only} without -> the image costs "
              f"{total - text_only} tokens; the formula says {est.tokens} ({est.method})")
        return
    t0 = time.perf_counter()
    r = httpx.post(base + "/v1/messages", headers=headers, json=body, timeout=120)
    r.raise_for_status()
    out = r.json()
    print(f"\n===== reply ({time.perf_counter() - t0:.2f}s)")
    print("".join(b.get("text", "") for b in out["content"] if b.get("type") == "text"))
    u = out["usage"]
    print(f"\nusage: input_tokens={u['input_tokens']} output_tokens={u['output_tokens']}")
    print(f"formula estimate for the image alone: {est.tokens} tokens ({est.method})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="receipt.png", help="a file in data/images/ or any path")
    ap.add_argument("--question", default="What is the total amount on this receipt, and in which currency?")
    ap.add_argument("--provider", choices=list(MODELS), default="anthropic")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--count-only", action="store_true", help="Anthropic count_tokens (free), no answer")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    path = IMAGES / a.image if (IMAGES / a.image).exists() else a.image
    data = open(path, "rb").read()
    info = image_info(data)
    print(f"image: {path}  {info.media_type} {info.width}x{info.height}  {len(data) / 1024:.0f} KB\n")

    llm = make_llm(f"mock-{a.provider}" if a.mock else f"{a.provider}:{MODELS[a.provider]}")
    data = for_model(data, llm)  # a real model gets the image without metadata

    if a.provider == "anthropic":
        if a.mock:
            raw_anthropic(llm.base_url, "mock", data, a.question, False)
        else:
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                sys.exit("ANTHROPIC_API_KEY is not set in .env (or use --mock)")
            raw_anthropic("https://api.anthropic.com", key, data, a.question, a.count_only)
        if a.count_only:
            return

    print("\n===== request 2: the same through llmkit")
    req = ChatRequest(messages=[Message.user_with(Image(data=data), a.question)], max_tokens=300)
    call = llm.provider.build(req, llm.model, "KEY", False)
    print(f"llmkit sends to {call.path}:")
    print(json.dumps(short(call.body), indent=2, ensure_ascii=False)[:2500])
    r = llm.complete(req)
    print(f"\n===== reply ({r.latency_s:.2f}s, {r.usage.input_tokens} input tokens, "
          f"cost ${r.cost_usd or 0:.5f})\n{r.text}")


if __name__ == "__main__":
    main()
