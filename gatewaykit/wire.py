"""Translate the two wire formats the gateway speaks to and from llmkit types.

Inbound:  OpenAI Chat Completions body  -> (model alias, ChatRequest, metadata)
          Anthropic Messages body       -> (model alias, ChatRequest, metadata)
Outbound: ChatResult -> the same format the client used; errors likewise.

Only text is supported. Anything else (tools, images, streaming, logprobs...) is
REJECTED with 400, never silently dropped: a gateway that quietly drops parameters
changes the behavior of the app behind its back (the Thoughtworks Radar warns about
exactly this in LiteLLM's drop_params mode).
"""

from __future__ import annotations

import time
from typing import Any, Optional

from llmkit.types import ChatRequest, ChatResult, Message

OPENAI_ALLOWED = {"model", "messages", "max_tokens", "max_completion_tokens", "stream", "metadata", "user", "n"}
ANTHROPIC_ALLOWED = {"model", "messages", "max_tokens", "system", "stream", "metadata"}
DEFAULT_MAX_TOKENS = 1024


class WireError(ValueError):
    def __init__(self, message: str, status: int = 400, kind: str = "invalid_request_error"):
        super().__init__(message)
        self.message, self.status, self.kind = message, status, kind


def _text(content: Any, where: str) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if not isinstance(p, dict) or p.get("type") != "text":
                kind = p.get("type") if isinstance(p, dict) else type(p).__name__
                raise WireError(f"{where}: only text content is supported by gatewaykit (got {kind!r})")
            parts.append(p.get("text", ""))
        return "\n\n".join(parts)
    raise WireError(f"{where}: content must be a string or a list of text blocks")


def _common(body: dict, allowed: set, flavor: str) -> None:
    if not isinstance(body, dict):
        raise WireError("request body must be a JSON object")
    if body.get("stream"):
        raise WireError("streaming is not supported by gatewaykit; send stream=false")
    extra = sorted(set(body) - allowed)
    if extra:
        raise WireError(f"unsupported parameter(s) for gatewaykit ({flavor}): {', '.join(extra)}. "
                        "They are rejected, not dropped silently.")
    if not body.get("model"):
        raise WireError("model is required")
    if not isinstance(body.get("messages"), list) or not body["messages"]:
        raise WireError("messages must be a non-empty list")


def parse_openai(body: dict) -> tuple[str, ChatRequest, dict]:
    _common(body, OPENAI_ALLOWED, "chat.completions")
    if body.get("n", 1) != 1:
        raise WireError("n must be 1")
    system_parts, messages = [], []
    for i, m in enumerate(body["messages"]):
        role = m.get("role")
        text = _text(m.get("content", ""), f"messages[{i}]")
        if role in ("system", "developer"):
            system_parts.append(text)
        elif role in ("user", "assistant"):
            messages.append(Message(role, text))
        else:
            raise WireError(f"messages[{i}]: role {role!r} is not supported (tools are not)")
    if not messages or messages[0].role != "user":
        raise WireError("the first non-system message must have role 'user'")
    max_tokens = int(body.get("max_completion_tokens") or body.get("max_tokens") or DEFAULT_MAX_TOKENS)
    req = ChatRequest(messages=messages, system="\n\n".join(system_parts), max_tokens=max_tokens)
    meta = dict(body.get("metadata") or {})
    if body.get("user"):
        meta.setdefault("end_user", body["user"])
    return body["model"], req, meta


def parse_anthropic(body: dict) -> tuple[str, ChatRequest, dict]:
    _common(body, ANTHROPIC_ALLOWED, "messages")
    if "max_tokens" not in body:
        raise WireError("max_tokens: Field required")
    messages = []
    for i, m in enumerate(body["messages"]):
        role = m.get("role")
        if role not in ("user", "assistant"):
            raise WireError(f"messages[{i}]: role must be user or assistant")
        messages.append(Message(role, _text(m.get("content", ""), f"messages[{i}]")))
    if messages[0].role != "user":
        raise WireError('messages: first message must use the "user" role')
    system = _text(body.get("system", ""), "system") if body.get("system") else ""
    req = ChatRequest(messages=messages, system=system, max_tokens=int(body["max_tokens"]))
    return body["model"], req, dict(body.get("metadata") or {})


FINISH_OPENAI = {"end": "stop", "max_tokens": "length", "stop_sequence": "stop", "refusal": "content_filter",
                 "tool_use": "tool_calls", "other": "stop"}
STOP_ANTHROPIC = {"end": "end_turn", "max_tokens": "max_tokens", "stop_sequence": "stop_sequence",
                  "refusal": "refusal", "tool_use": "tool_use", "other": "end_turn"}


def render_openai(result: ChatResult, model: str, request_id: str) -> dict:
    u = result.usage
    return {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": result.text},
                     "finish_reason": FINISH_OPENAI.get(result.stop_reason, "stop")}],
        "usage": {"prompt_tokens": u.input_tokens, "completion_tokens": u.output_tokens,
                  "total_tokens": u.input_tokens + u.output_tokens,
                  "prompt_tokens_details": {"cached_tokens": u.cached_input_tokens}},
    }


def render_anthropic(result: ChatResult, model: str, request_id: str) -> dict:
    u = result.usage
    return {
        "id": f"msg_{request_id}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": result.text}],
        "stop_reason": STOP_ANTHROPIC.get(result.stop_reason, "end_turn"),
        "stop_sequence": None,
        # Anthropic semantics: input_tokens excludes cache reads and writes.
        "usage": {"input_tokens": u.uncached_input_tokens, "output_tokens": u.output_tokens,
                  "cache_read_input_tokens": u.cached_input_tokens,
                  "cache_creation_input_tokens": u.cache_creation_tokens},
    }


def error_body(flavor: str, status: int, kind: str, message: str, request_id: Optional[str] = None) -> dict:
    if flavor == "anthropic":
        body = {"type": "error", "error": {"type": kind, "message": message}}
    else:
        body = {"error": {"message": message, "type": kind, "code": kind}}
    if request_id:
        body["request_id"] = request_id
    return body
