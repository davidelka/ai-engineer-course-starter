"""Anthropic Messages API: POST /v1/messages."""

from __future__ import annotations

import json
from typing import Iterator

from ..errors import LLMError
from ..schema import strict_schema
from ..sse import SSEEvent
from ..types import (Block, ChatRequest, Content, Document, Image, Message, StopReason, Tool, ToolCall, ToolResult,
                     Usage)
from .base import (HTTPCall, Parsed, StreamEnd, StreamItem, TextDelta, ToolCallDelta, ToolCallDone, check_media,
                   generic_error, header, load_json, media_source, parse_arguments, sort_results_first)

# Pinned on purpose (lesson 1): newer versions changed the request schema.
# Upgrade deliberately, run the tests, then change this line.
API_VERSION = "2023-06-01"

STOP_MAP: dict[str, StopReason] = {
    "end_turn": "end", "max_tokens": "max_tokens", "stop_sequence": "stop_sequence",
    "tool_use": "tool_use", "refusal": "refusal", "pause_turn": "other",
}


def cache_control(ttl: str) -> dict:
    """Block-level cache marker. 5 minutes is the API default, so it carries no ttl."""
    return {"type": "ephemeral", "ttl": "1h"} if ttl == "1h" else {"type": "ephemeral"}


def media_block(m) -> dict:
    """Image -> {"type": "image", "source": ...}; Document -> {"type": "document", ...}.
    source is base64 (with media_type), url, or file (Files API file_id)."""
    kind, value = media_source(m)
    if kind == "base64":
        source = {"type": "base64", "media_type": m.media_type, "data": value}
    elif kind == "url":
        source = {"type": "url", "url": value}
    else:
        source = {"type": "file", "file_id": value}
    block = {"type": "image" if isinstance(m, Image) else "document", "source": source}
    if isinstance(m, Document) and m.title:
        block["title"] = m.title
    if m.cache:
        block["cache_control"] = cache_control(m.cache)
    return block


def content_blocks(content: Content):
    """A plain string stays a string (unchanged wire format). A list of parts becomes
    content blocks: Block -> text (with cache_control on the ones that end a cached
    prefix), ToolCall -> tool_use, ToolResult -> tool_result, Image -> image,
    Document -> document (lesson 21). Tool results are moved before any text, as the
    API requires; images and text keep the order you gave them."""
    if isinstance(content, str):
        return content
    out = []
    for b in sort_results_first(list(content)):
        if isinstance(b, ToolCall):
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.arguments})
        elif isinstance(b, ToolResult):
            item = {"type": "tool_result", "tool_use_id": b.call_id, "content": b.text}
            if b.is_error:
                item["is_error"] = True
            out.append(item)
        elif isinstance(b, (Image, Document)):
            out.append(media_block(b))
        else:
            item = {"type": "text", "text": b.text}
            if isinstance(b, Block) and b.cache:
                item["cache_control"] = cache_control(b.cache)
            out.append(item)
    return out


def message_content(m: Message):
    """Replay the provider's own blocks for an assistant turn that came from Anthropic
    (keeps thinking blocks and their signatures); otherwise translate the parts."""
    if m.raw is not None and m.raw_provider == "anthropic":
        return m.raw
    return content_blocks(m.content)


def tool_def(t: Tool) -> dict:
    schema = strict_schema(t.input_schema, "anthropic", keep_root_title=False)[0] if t.strict else t.input_schema
    d = {"name": t.name, "description": t.description, "input_schema": schema}
    if t.strict:
        d["strict"] = True
    if t.cache:
        d["cache_control"] = cache_control(t.cache)
    return d


def tool_choice(choice, parallel) -> dict | None:
    """llmkit tool_choice -> Anthropic's object. disable_parallel_tool_use lives
    INSIDE tool_choice (not top level)."""
    if choice is None and parallel is not False:
        return None
    kind = choice or "auto"
    tc = {"type": kind} if kind in ("auto", "any", "none") else {"type": "tool", "name": kind}
    if parallel is False and kind != "none":
        tc["disable_parallel_tool_use"] = True
    return tc


def tool_calls_from(blocks: list) -> list[ToolCall]:
    calls = []
    for b in blocks:
        if b.get("type") == "tool_use":
            inp = b.get("input")
            calls.append(ToolCall(id=b.get("id", ""), name=b.get("name", ""),
                                  arguments=inp if isinstance(inp, dict) else {},
                                  raw_arguments=json.dumps(inp, ensure_ascii=False),
                                  parse_error=None if isinstance(inp, dict) else "input is not an object"))
    return calls


class AnthropicProvider:
    name = "anthropic"
    default_base_url = "https://api.anthropic.com"
    key_env = ("ANTHROPIC_API_KEY",)

    def build(self, req: ChatRequest, model: str, api_key: str, stream: bool) -> HTTPCall:
        check_media(req, self.name)
        body: dict = {
            "model": model,
            "max_tokens": req.max_tokens,
            "messages": [{"role": m.role, "content": message_content(m)} for m in req.messages],
        }
        if req.tools:
            body["tools"] = [tool_def(t) for t in req.tools]
        tc = tool_choice(req.tool_choice, req.parallel_tool_calls) if req.tools else None
        if tc:
            body["tool_choice"] = tc
        if req.system:
            body["system"] = content_blocks(req.system)
        if req.cache:
            # Automatic caching: the API puts the breakpoint on the last cacheable
            # block and moves it forward as the conversation grows.
            body["cache_control"] = cache_control(req.cache)
        if req.effort:
            body["output_config"] = {"effort": req.effort}
        if req.response_schema is not None:
            # Constrained decoding: the reply text is JSON matching this schema.
            body.setdefault("output_config", {})["format"] = {
                "type": "json_schema", "schema": req.response_schema}
        if stream:
            body["stream"] = True
        body.update(req.extra_body)
        headers = {
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        return HTTPCall("/v1/messages", headers, body)

    @staticmethod
    def _usage(u: dict) -> Usage:
        """Anthropic splits the prompt in three: input_tokens is only what came AFTER
        the last cache breakpoint. Total = input + cache_read + cache_creation."""
        details = u.get("output_tokens_details") or {}
        read = u.get("cache_read_input_tokens") or 0
        write = u.get("cache_creation_input_tokens") or 0
        write_1h = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
        return Usage(
            input_tokens=(u.get("input_tokens") or 0) + read + write,
            output_tokens=u.get("output_tokens") or 0,
            cached_input_tokens=read,
            cache_creation_tokens=write,
            cache_creation_1h_tokens=write_1h,
            thinking_tokens=details.get("thinking_tokens", 0),
        )

    def parse(self, body: dict, headers: dict) -> Parsed:
        if "content" not in body:
            raise LLMError(f"unexpected response shape: {str(body)[:200]}", provider=self.name,
                           kind="malformed_response")
        # Select by type: a thinking block may come before the text.
        text = "".join(b.get("text", "") for b in body["content"] if b.get("type") == "text")
        return Parsed(text, body.get("stop_reason") or "", self._usage(body.get("usage", {})),
                      header(headers, "request-id") or body.get("id"),
                      tool_calls=tool_calls_from(body["content"]), raw_output=body["content"])

    def parse_stream(self, events: Iterator[SSEEvent], headers: dict) -> Iterator[StreamItem]:
        usage, raw_stop = Usage(), ""
        rid = header(headers, "request-id")
        # Rebuild the content blocks as they stream, so the final result has the same
        # raw_output (and tool calls) as a non-streaming call. Keyed by block index.
        blocks: dict[int, dict] = {}
        partial: dict[int, list[str]] = {}
        calls: list[ToolCall] = []
        for ev in events:
            kind = ev.event
            if kind == "ping" or not ev.data:
                continue
            data = load_json(ev.data, self.name)
            kind = kind or data.get("type")
            if kind == "message_start":
                usage = self._usage(data["message"].get("usage", {}))
            elif kind == "content_block_start":
                idx = data.get("index", len(blocks))
                blocks[idx] = dict(data.get("content_block") or {})
                if blocks[idx].get("type") == "tool_use":
                    partial[idx] = []
            elif kind == "content_block_delta":
                delta = data.get("delta", {})
                idx = data.get("index", 0)
                block = blocks.setdefault(idx, {"type": "text", "text": ""})
                if delta.get("type") == "text_delta":
                    block["text"] = block.get("text", "") + delta.get("text", "")
                    yield TextDelta(delta.get("text", ""))
                elif delta.get("type") == "input_json_delta":
                    # Fragments of the arguments JSON: concatenate, parse at content_block_stop.
                    piece = delta.get("partial_json", "")
                    partial.setdefault(idx, []).append(piece)
                    yield ToolCallDelta(block.get("id", ""), block.get("name", ""), piece)
                elif delta.get("type") == "thinking_delta":
                    block["thinking"] = block.get("thinking", "") + delta.get("thinking", "")
                elif delta.get("type") == "signature_delta":
                    block["signature"] = block.get("signature", "") + delta.get("signature", "")
            elif kind == "content_block_stop":
                idx = data.get("index", 0)
                block = blocks.get(idx, {})
                if block.get("type") == "tool_use":
                    raw = "".join(partial.get(idx, []))
                    args, err = parse_arguments(raw)
                    block["input"] = args
                    call = ToolCall(id=block.get("id", ""), name=block.get("name", ""), arguments=args,
                                    raw_arguments=raw or "{}", parse_error=err)
                    calls.append(call)
                    yield ToolCallDone(call)
            elif kind == "message_delta":
                raw_stop = data.get("delta", {}).get("stop_reason") or raw_stop
                final = self._usage({**data.get("usage", {})})
                usage.output_tokens = final.output_tokens or usage.output_tokens
                usage.thinking_tokens = final.thinking_tokens or usage.thinking_tokens
            elif kind == "message_stop":
                yield StreamEnd(raw_stop, usage, rid, tool_calls=calls,
                                raw_output=[blocks[i] for i in sorted(blocks)])
                return
            elif kind == "error":
                err = data.get("error", {})
                # Arrives after HTTP 200: the status code alone would never show it.
                raise LLMError(err.get("message", "stream error"), provider=self.name,
                               kind=err.get("type", "api_error"), request_id=rid)
        raise LLMError("stream ended before message_stop", provider=self.name,
                       kind="stream_truncated", request_id=rid)

    def error(self, status: int, text: str, headers: dict) -> LLMError:
        return generic_error(self.name, status, text, headers, "request-id")

    def map_stop(self, raw: str) -> StopReason:
        return STOP_MAP.get(raw, "other")
