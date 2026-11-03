"""Offline LLM for lesson 12: a REAL llmkit.LLM whose HTTP transport is answered locally.

    llm = replay_llm(responder)            # responder(body: dict) -> reply text
    complete_structured(llm, prompt, QueryRewrite)   # the whole request path runs, for free

The request is built by llmkit's Anthropic adapter exactly as for the real API (system prompt,
messages, output_config.format with the JSON schema); only the network hop is replaced by
httpx.MockTransport. Usage is ESTIMATED (about 4 characters per token, ragkit's approx
tokenizer) and priced like the model named in the spec, so cost numbers printed offline are
"what Haiku would roughly have cost", never a bill. Every reply says it is a replay.

Responders live next to the feature they fake: query.fixture_responder (recorded or
hand-written rewrites) and rerank.llm.overlap_responder (a lexical "judge"). dispatch() picks
one by a marker string in the system prompt, so one offline LLM can serve a whole pipeline.
"""

from __future__ import annotations

import json
from typing import Callable, Mapping

import httpx

from llmkit import LLM

from .tokens import get_tokenizer

Responder = Callable[[dict], str]


def body_text(body: dict) -> tuple[str, str]:
    """(system text, last user message text) of an Anthropic-format request body."""
    def text(c) -> str:
        if isinstance(c, str):
            return c
        return "".join(b.get("text", "") for b in c if isinstance(b, dict))
    system = text(body.get("system") or "")
    msgs = [m for m in body.get("messages", []) if m.get("role") == "user"]
    return system, (text(msgs[-1]["content"]) if msgs else "")


def dispatch(routes: Mapping[str, Responder], default: Responder) -> Responder:
    """Choose a responder by the first marker found in the system prompt."""
    def respond(body: dict) -> str:
        system, _ = body_text(body)
        for marker, fn in routes.items():
            if marker in system:
                return fn(body)
        return default(body)
    return respond


def replay_llm(responder: Responder, model: str = "claude-haiku-5-5") -> LLM:
    tok = get_tokenizer("approx")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        text = responder(body)
        out = {"id": "msg_replay", "type": "message", "role": "assistant", "model": body.get("model"),
               "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
               "usage": {"input_tokens": tok.count(json.dumps(body, ensure_ascii=False)),
                         "output_tokens": tok.count(text)}}
        return httpx.Response(200, json=out, headers={"request-id": "req_replay"})

    return LLM(f"anthropic:{model}", api_key="replay", base_url="http://replay.invalid",
               http=httpx.Client(transport=httpx.MockTransport(handler)))


__all__ = ["replay_llm", "dispatch", "body_text", "Responder"]
