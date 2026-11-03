"""OpenAI Responses API: POST /v1/responses."""

from __future__ import annotations

import json
from typing import Iterator, Optional

from ..errors import LLMError
from ..schema import strict_schema
from ..sse import SSEEvent
from ..media import to_data_url
from ..types import (Block, ChatRequest, Document, Image, Message, StopReason, Tool, ToolCall, ToolResult, Usage,
                     content_text)
from .base import (HTTPCall, Parsed, StreamEnd, StreamItem, TextDelta, ToolCallDelta, ToolCallDone, check_media,
                   generic_error, header, load_json, parse_arguments, sort_results_first)


def usage_from(u: Optional[dict]) -> Usage:
    u = u or {}
    details = u.get("input_tokens_details") or {}
    return Usage(
        input_tokens=u.get("input_tokens", 0),  # total, including cached reads and writes
        output_tokens=u.get("output_tokens", 0),  # includes reasoning tokens
        cached_input_tokens=details.get("cached_tokens") or 0,
        # Billed cache writes exist only on GPT-5.6+ (explicit breakpoints); 0 elsewhere.
        cache_creation_tokens=details.get("cache_write_tokens") or 0,
        thinking_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0),
    )


def raw_stop_from(response: dict) -> str:
    """'completed', or the incomplete reason such as 'max_output_tokens'."""
    if response.get("status") == "incomplete":
        return (response.get("incomplete_details") or {}).get("reason", "incomplete")
    return response.get("status", "")


def event_to_item(event_type: str, data: dict, provider: str = "openai") -> Optional[StreamItem]:
    """Reference implementation. Exercise 5 asks you to write your own in mine.py.

    Map ONE Responses-API stream event to a TextDelta, a StreamEnd, None (ignore),
    or raise LLMError for failure events.
    """
    if event_type == "response.output_text.delta":
        return TextDelta(data.get("delta", ""))
    if event_type in ("response.completed", "response.incomplete"):
        resp = data.get("response", {})
        return StreamEnd(raw_stop_from(resp), usage_from(resp.get("usage")), resp.get("id"))
    if event_type == "response.failed":
        err = (data.get("response") or {}).get("error") or {}
        raise LLMError(err.get("message", "response failed"), provider=provider,
                       kind=err.get("code") or "server_error")
    if event_type == "error":
        raise LLMError(data.get("message", "stream error"), provider=provider,
                       kind=data.get("code") or data.get("type") or "server_error")
    return None


def media_part(m) -> dict:
    """Image -> input_image (image_url = an https URL or a base64 data URL, or file_id);
    Document -> input_file (file_data = data URL + filename, file_url, or file_id)."""
    if isinstance(m, Image):
        part: dict = {"type": "input_image"}
        if m.data is not None:
            part["image_url"] = to_data_url(m.media_type, m.data)
        elif m.url:
            part["image_url"] = m.url
        else:
            part["file_id"] = m.file_id
    else:
        part = {"type": "input_file"}
        if m.data is not None:
            part["filename"] = m.filename
            part["file_data"] = to_data_url(m.media_type, m.data)
        elif m.url:
            part["file_url"] = m.url
        else:
            part["file_id"] = m.file_id
    if m.detail:
        part["detail"] = m.detail
    return part


def input_items(m: Message) -> list[dict]:
    """One Message -> Responses-API input items.

    A plain string is one {"role", "content"} item (unchanged since lesson 2).
    An assistant turn that came from OpenAI is replayed verbatim (its output items:
    reasoning, message, function_call), as the docs require for reasoning models.
    Otherwise: text -> role items, ToolCall -> function_call, ToolResult ->
    function_call_output (matched by call_id, output is a string).
    Lesson 21: when a run of parts contains an Image or Document, that role item gets a
    content LIST of input_text / input_image / input_file parts, in the order given.
    Without media the content stays one joined string, exactly as before."""
    if isinstance(m.content, str):
        return [{"role": m.role, "content": m.content}]
    if m.raw is not None and m.raw_provider == "openai":
        return list(m.raw)
    items: list[dict] = []
    run: list = []  # consecutive Blocks and media

    def flush():
        if not run:
            return
        if any(isinstance(p, (Image, Document)) for p in run):
            if m.role != "user":
                raise ValueError("images and documents can only be sent in user messages")
            parts = [media_part(p) if isinstance(p, (Image, Document)) else {"type": "input_text", "text": p.text}
                     for p in run]
            items.append({"role": m.role, "content": parts})
        else:
            items.append({"role": m.role, "content": "\n\n".join(p.text for p in run)})
        run.clear()

    for p in sort_results_first(list(m.content)):
        if isinstance(p, ToolCall):
            flush()
            items.append({"type": "function_call", "call_id": p.id, "name": p.name,
                          "arguments": p.raw_arguments or json.dumps(p.arguments, ensure_ascii=False)})
        elif isinstance(p, ToolResult):
            flush()
            # No is_error field in the Responses API: the error travels in the text.
            out = p.text if not p.is_error else (p.text if p.text.lower().startswith("error") else "ERROR: " + p.text)
            items.append({"type": "function_call_output", "call_id": p.call_id, "output": out})
        elif isinstance(p, (Block, Image, Document)):
            run.append(p)
    flush()
    return items


def tool_def(t: Tool) -> dict:
    schema = strict_schema(t.input_schema, "openai", keep_root_title=False)[0] if t.strict else t.input_schema
    # strict is sent explicitly: when it is omitted the Responses API may normalize the
    # schema and decide for you.
    return {"type": "function", "name": t.name, "description": t.description,
            "parameters": schema, "strict": bool(t.strict)}


def tool_choice(choice):
    if choice is None:
        return None
    if choice == "any":
        return "required"
    if choice in ("auto", "none"):
        return choice
    return {"type": "function", "name": choice}


def tool_calls_from(output: list) -> list[ToolCall]:
    calls = []
    for item in output or []:
        if item.get("type") == "function_call":
            raw = item.get("arguments") or ""
            args, err = parse_arguments(raw)
            calls.append(ToolCall(id=item.get("call_id", ""), name=item.get("name", ""), arguments=args,
                                  raw_arguments=raw, parse_error=err))
    return calls


class OpenAIProvider:
    name = "openai"
    default_base_url = "https://api.openai.com"
    key_env = ("OPENAI_API_KEY",)
    # Swappable so exercise 5 can plug in its own event mapper.
    event_mapper = staticmethod(event_to_item)

    def build(self, req: ChatRequest, model: str, api_key: str, stream: bool) -> HTTPCall:
        check_media(req, self.name)
        body: dict = {
            "model": model,
            "input": [item for m in req.messages for item in input_items(m)],
            "max_output_tokens": req.max_tokens,
        }
        if req.tools:
            body["tools"] = [tool_def(t) for t in req.tools]
            tc = tool_choice(req.tool_choice)
            if tc is not None:
                body["tool_choice"] = tc
            if req.parallel_tool_calls is not None:
                body["parallel_tool_calls"] = req.parallel_tool_calls
        if req.system:
            body["instructions"] = content_text(req.system)
        if req.cache_key:
            # Prefix caching is automatic; the key helps route requests that share a
            # prefix to the same cache machine.
            body["prompt_cache_key"] = req.cache_key
        if req.effort:
            body["reasoning"] = {"effort": req.effort}
        if req.response_schema is not None:
            body["text"] = {"format": {"type": "json_schema", "name": req.schema_name,
                                       "schema": req.response_schema, "strict": True}}
        if stream:
            body["stream"] = True
        body.update(req.extra_body)
        headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
        return HTTPCall("/v1/responses", headers, body)

    def parse(self, body: dict, headers: dict) -> Parsed:
        if "output" not in body:
            raise LLMError(f"unexpected response shape: {str(body)[:200]}", provider=self.name,
                           kind="malformed_response")
        parts = [part for item in body["output"] if item.get("type") == "message"
                 for part in item.get("content", [])]
        refusal = next((p.get("refusal", "") for p in parts if p.get("type") == "refusal"), None)
        if refusal is not None:  # status is still "completed"; the refusal is a content part
            return Parsed(refusal, "refusal", usage_from(body.get("usage")),
                          header(headers, "x-request-id") or body.get("id"))
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "output_text")
        calls = tool_calls_from(body["output"])
        # A function call still has status "completed": the call itself is the signal.
        raw_stop = "function_call" if calls and body.get("status") == "completed" else raw_stop_from(body)
        return Parsed(text, raw_stop, usage_from(body.get("usage")),
                      header(headers, "x-request-id") or body.get("id"),
                      tool_calls=calls, raw_output=body["output"])

    def parse_stream(self, events: Iterator[SSEEvent], headers: dict) -> Iterator[StreamItem]:
        rid = header(headers, "x-request-id")
        done_items: dict[int, dict] = {}  # output_index -> finished output item
        calls: list[ToolCall] = []
        names: dict[str, tuple[str, str]] = {}  # item id -> (call_id, name)
        for ev in events:
            if not ev.data:
                continue
            data = load_json(ev.data, self.name)
            etype = ev.event or data.get("type", "")
            # Tool-call events are handled here, before the (swappable) event mapper,
            # so lesson 2's exercise mapper keeps working unchanged.
            if etype == "response.output_item.added":
                it = data.get("item") or {}
                if it.get("type") == "function_call":
                    names[it.get("id", "")] = (it.get("call_id", ""), it.get("name", ""))
                continue
            if etype == "response.function_call_arguments.delta":
                call_id, name = names.get(data.get("item_id", ""), ("", ""))
                yield ToolCallDelta(call_id, name, data.get("delta", ""))
                continue
            if etype == "response.output_item.done":
                it = data.get("item") or {}
                done_items[data.get("output_index", len(done_items))] = it
                if it.get("type") == "function_call":
                    call = tool_calls_from([it])[0]
                    calls.append(call)
                    yield ToolCallDone(call)
                continue
            item = self.event_mapper(etype, data, self.name)
            if isinstance(item, StreamEnd):
                item.request_id = rid or item.request_id
                resp = data.get("response") or {}
                output = resp.get("output") or [done_items[i] for i in sorted(done_items)]
                item.raw_output = output
                item.tool_calls = calls or tool_calls_from(output)
                if item.tool_calls and item.raw_stop == "completed":
                    item.raw_stop = "function_call"
                yield item
                return
            if item is not None:
                yield item
        raise LLMError("stream ended before response.completed", provider=self.name,
                       kind="stream_truncated", request_id=rid)

    def error(self, status: int, text: str, headers: dict) -> LLMError:
        return generic_error(self.name, status, text, headers, "x-request-id")

    def map_stop(self, raw: str) -> StopReason:
        # "function_call" is llmkit's marker (set in parse) for a completed response
        # that asks for tools; OpenAI itself reports "completed".
        return {"completed": "end", "max_output_tokens": "max_tokens", "function_call": "tool_use",
                "content_filter": "refusal", "refusal": "refusal"}.get(raw, "other")
