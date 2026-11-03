"""Gemini API: POST /v1beta/models/{model}:generateContent (or :streamGenerateContent?alt=sse)."""

from __future__ import annotations

from typing import Iterator

import json

from ..errors import LLMError
from ..schema import strict_schema
from ..sse import SSEEvent
from ..media import guess_type_from_url
from ..types import (LOCAL_ID_PREFIX, Block, ChatRequest, Document, Image, Message, StopReason, Tool, ToolCall,
                     ToolResult, Usage, content_text)
from .base import (HTTPCall, Parsed, StreamEnd, StreamItem, TextDelta, ToolCallDone, check_media, generic_error,
                   load_json, sort_results_first, tool_names_by_id)


def usage_from(meta: dict) -> Usage:
    thoughts = meta.get("thoughtsTokenCount", 0)
    return Usage(
        input_tokens=meta.get("promptTokenCount", 0),
        # Thinking is billed as output, but Gemini reports it separately.
        output_tokens=meta.get("candidatesTokenCount", 0) + thoughts,
        # promptTokenCount already includes the cached part (implicit or explicit cache).
        cached_input_tokens=meta.get("cachedContentTokenCount", 0),
        thinking_tokens=thoughts,
    )


def candidate_text(body: dict) -> tuple[str, str]:
    cands = body.get("candidates") or []
    if not cands:
        return "", ""
    c = cands[0]
    parts = (c.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return text, c.get("finishReason", "")


DUMMY_SIGNATURE = "skip_thought_signature_validator"  # ai.google.dev thought-signatures, Nov 2026


MEDIA_RESOLUTION = {"low": "MEDIA_RESOLUTION_LOW", "medium": "MEDIA_RESOLUTION_MEDIUM",
                    "high": "MEDIA_RESOLUTION_HIGH", "ultra_high": "MEDIA_RESOLUTION_ULTRA_HIGH"}


def media_part(m) -> dict:
    """Image / Document -> {"inlineData": {"mimeType", "data"}} for bytes, or
    {"fileData": {"mimeType", "fileUri"}} for a Files API URI (file_id) or an external
    URL. detail -> the part's mediaResolution (Gemini 3+). Notes (Nov 2026): external URLs
    are limited to 15 MB, and a forum thread reports 403s for them on Gemini 3.5+:
    prefer bytes or the Files API."""
    if m.data is not None:
        part: dict = {"inlineData": {"mimeType": m.media_type, "data": m.base64}}
    else:
        uri = m.file_id or m.url or ""
        mime = m.media_type or guess_type_from_url(uri)
        part = {"fileData": {"mimeType": mime, "fileUri": uri}}
    if m.detail in MEDIA_RESOLUTION:
        part["mediaResolution"] = {"level": MEDIA_RESOLUTION[m.detail]}
    return part


def message_parts(m: Message, names: dict[str, str]) -> list[dict]:
    """One Message -> Gemini parts.

    An assistant turn that came from Gemini is replayed verbatim: its functionCall
    parts carry the thoughtSignature that Gemini 3+ REQUIRES back (400 otherwise).
    Otherwise: text -> {"text"}, ToolCall -> {"functionCall"}, ToolResult ->
    {"functionResponse"} whose `response` must be a JSON object: a dict result is
    sent as is, anything else as {"result": ...}, and errors as {"error": ...}."""
    if isinstance(m.content, str):
        return [{"text": m.content}]
    if m.raw is not None and m.raw_provider == "gemini":
        return list(m.raw)
    parts: list[dict] = []
    first_call = True
    for p in sort_results_first(list(m.content)):
        if isinstance(p, ToolCall):
            fc = {"name": p.name, "args": p.arguments}
            if p.id and not p.id.startswith(LOCAL_ID_PREFIX):
                fc["id"] = p.id
            part = {"functionCall": fc}
            if p.signature:
                part["thoughtSignature"] = p.signature
            elif first_call:
                # A call Gemini did not produce (another provider's history, or one you
                # injected): the docs allow this dummy value to skip signature validation.
                part["thoughtSignature"] = DUMMY_SIGNATURE
            first_call = False
            parts.append(part)
        elif isinstance(p, ToolResult):
            if p.is_error:
                response = {"error": p.content}
            elif isinstance(p.content, dict):
                response = p.content
            else:
                response = {"result": p.content}
            fr = {"name": p.name or names.get(p.call_id, ""), "response": response}
            if p.call_id and not p.call_id.startswith(LOCAL_ID_PREFIX):
                fr["id"] = p.call_id
            parts.append({"functionResponse": fr})
        elif isinstance(p, (Image, Document)):
            parts.append(media_part(p))
        elif isinstance(p, Block):
            if parts and set(parts[-1]) == {"text"}:  # consecutive blocks: one text part, as before
                parts[-1] = {"text": parts[-1]["text"] + "\n\n" + p.text}
            else:
                parts.append({"text": p.text})
    return parts or [{"text": ""}]


def tool_config(choice, tools: list[Tool]) -> dict | None:
    """llmkit tool_choice -> functionCallingConfig. Gemini has no per-tool strict flag:
    strict tools turn AUTO into VALIDATED (constrained decoding for calls).
    A specific tool = ANY restricted to allowedFunctionNames. No parallel switch."""
    strict = any(t.strict for t in tools)
    if choice is None and not strict:
        return None
    kind = choice or "auto"
    if kind == "auto":
        cfg = {"mode": "VALIDATED" if strict else "AUTO"}
    elif kind == "any":
        cfg = {"mode": "ANY"}
    elif kind == "none":
        cfg = {"mode": "NONE"}
    else:
        cfg = {"mode": "ANY", "allowedFunctionNames": [kind]}
    return {"functionCallingConfig": cfg}


def function_declaration(t: Tool) -> dict:
    schema = strict_schema(t.input_schema, "gemini", keep_root_title=False)[0] if t.strict else t.input_schema
    # parametersJsonSchema takes plain JSON Schema (the older `parameters` field takes
    # an OpenAPI-style subset). The two are mutually exclusive.
    return {"name": t.name, "description": t.description, "parametersJsonSchema": schema}


def calls_from_parts(parts: list, start: int = 0) -> list[ToolCall]:
    calls = []
    for i, p in enumerate(parts):
        fc = p.get("functionCall")
        if fc:
            args = fc.get("args") or {}
            calls.append(ToolCall(id=fc.get("id") or f"{LOCAL_ID_PREFIX}{start + len(calls)}",
                                  name=fc.get("name", ""), arguments=args if isinstance(args, dict) else {},
                                  raw_arguments=json.dumps(args, ensure_ascii=False),
                                  signature=p.get("thoughtSignature")))
    return calls


class GeminiProvider:
    name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com"
    key_env = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

    def build(self, req: ChatRequest, model: str, api_key: str, stream: bool) -> HTTPCall:
        check_media(req, self.name)
        names = tool_names_by_id(req.messages)
        body: dict = {
            "contents": [
                # Gemini calls the assistant role "model". Function responses go in a user turn.
                {"role": "model" if m.role == "assistant" else "user", "parts": message_parts(m, names)}
                for m in req.messages
            ],
            "generationConfig": {"maxOutputTokens": req.max_tokens},
        }
        if req.tools:
            body["tools"] = [{"functionDeclarations": [function_declaration(t) for t in req.tools]}]
            cfg = tool_config(req.tool_choice, req.tools)
            if cfg:
                body["toolConfig"] = cfg
        if req.system:
            body["systemInstruction"] = {"parts": [{"text": content_text(req.system)}]}
        if req.effort:
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": req.effort}
        if req.response_schema is not None:
            body["generationConfig"]["responseMimeType"] = "application/json"
            body["generationConfig"]["responseJsonSchema"] = req.response_schema
        body.update(req.extra_body)
        # Key in a header, not in ?key=: URLs end up in proxy and server logs.
        headers = {"x-goog-api-key": api_key, "content-type": "application/json"}
        path = f"/v1beta/models/{model}:" + ("streamGenerateContent?alt=sse" if stream else "generateContent")
        return HTTPCall(path, headers, body)

    def parse(self, body: dict, headers: dict) -> Parsed:
        if "candidates" not in body:
            raise LLMError(f"unexpected response shape: {str(body)[:200]}", provider=self.name,
                           kind="malformed_response")
        text, finish = candidate_text(body)
        parts = ((body["candidates"] or [{}])[0].get("content") or {}).get("parts") or []
        calls = calls_from_parts(parts)
        # finishReason is "STOP" even when the model asks for functions.
        raw_stop = "FUNCTION_CALL" if calls and finish == "STOP" else finish
        return Parsed(text, raw_stop, usage_from(body.get("usageMetadata", {})), body.get("responseId"),
                      tool_calls=calls, raw_output=parts)

    def parse_stream(self, events: Iterator[SSEEvent], headers: dict) -> Iterator[StreamItem]:
        usage, finish, rid = Usage(), "", None
        all_parts: list[dict] = []
        calls: list[ToolCall] = []
        for ev in events:
            if not ev.data:
                continue
            data = load_json(ev.data, self.name)
            if "error" in data:
                err = data["error"]
                raise LLMError(err.get("message", "stream error"), provider=self.name,
                               status=err.get("code"), kind=err.get("status", ""))
            text, f = candidate_text(data)
            if text:
                yield TextDelta(text)
            parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            # Gemini streams a functionCall whole, in one chunk: no argument deltas.
            for call in calls_from_parts(parts, start=len(calls)):
                calls.append(call)
                yield ToolCallDone(call)
            for p in parts:  # merge consecutive text pieces so raw_output stays compact
                if "text" in p and all_parts and set(all_parts[-1]) == {"text"} and set(p) == {"text"}:
                    all_parts[-1] = {"text": all_parts[-1]["text"] + p["text"]}
                else:
                    all_parts.append(dict(p))
            if "usageMetadata" in data:
                usage = usage_from(data["usageMetadata"])  # cumulative: replace, never add
            rid = data.get("responseId", rid)
            finish = f or finish
        # No terminator event in Gemini's stream: a finishReason is the only proof it ended.
        if not finish:
            raise LLMError("stream ended without finishReason", provider=self.name,
                           kind="stream_truncated", request_id=rid)
        if calls and finish == "STOP":
            finish = "FUNCTION_CALL"
        yield StreamEnd(finish, usage, rid, tool_calls=calls, raw_output=all_parts)

    def error(self, status: int, text: str, headers: dict) -> LLMError:
        return generic_error(self.name, status, text, headers, "x-request-id")

    def map_stop(self, raw: str) -> StopReason:
        # "FUNCTION_CALL" is llmkit's marker for STOP + functionCall parts.
        # MALFORMED_FUNCTION_CALL / UNEXPECTED_TOOL_CALL / TOO_MANY_TOOL_CALLS map to "other".
        return {"STOP": "end", "MAX_TOKENS": "max_tokens", "SAFETY": "refusal", "FUNCTION_CALL": "tool_use",
                "RECITATION": "refusal"}.get(raw, "other")
