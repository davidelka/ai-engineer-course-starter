"""What every provider adapter must implement.

An adapter is pure translation: it never opens connections or sleeps.
The client (llmkit/client.py) does I/O, timing, retries and cost.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Protocol, Union

from ..errors import LLMError, parse_retry_after
from ..sse import SSEEvent
from ..types import ChatRequest, Document, Image, Message, StopReason, ToolCall, Usage


@dataclass
class HTTPCall:
    path: str  # appended to the base URL
    headers: dict
    body: dict


@dataclass
class Parsed:
    text: str
    raw_stop: str
    usage: Usage
    request_id: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)  # lesson 14
    raw_output: Optional[Any] = None  # provider-native assistant output, for replay


@dataclass
class TextDelta:
    text: str


@dataclass
class StreamEnd:
    raw_stop: str
    usage: Usage
    request_id: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)  # lesson 14
    raw_output: Optional[Any] = None


@dataclass
class ToolCallDelta:
    """A fragment of a tool call's arguments JSON (lesson 14)."""

    id: str
    name: str
    partial_json: str


@dataclass
class ToolCallDone:
    """A tool call whose arguments are complete (lesson 14)."""

    call: ToolCall


StreamItem = Union[TextDelta, StreamEnd, ToolCallDelta, ToolCallDone]


def parse_arguments(raw: str) -> tuple[dict, Optional[str]]:
    """Arguments JSON text -> (dict, None), or ({}, error message) when it is not a
    JSON object. Never raises: a bad tool call is the model's mistake, and the
    executor reports it back to the model as an is_error result."""
    if raw is None or raw.strip() == "":
        return {}, None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, f"arguments are not valid JSON: {exc.msg} at position {exc.pos}"
    if not isinstance(value, dict):
        return {}, f"arguments must be a JSON object, got {type(value).__name__}"
    return value, None


def tool_names_by_id(messages: list[Message]) -> dict[str, str]:
    """call id -> tool name, from every assistant ToolCall in the conversation.
    Gemini's functionResponse needs the name; ToolResult may leave it empty."""
    return {c.id: c.name for m in messages for c in m.tool_calls}


def sort_results_first(parts: list) -> list:
    """Tool results must come before any text in the user turn (Anthropic returns 400
    otherwise). Stable: keeps the order inside each group."""
    from ..types import ToolResult
    return [p for p in parts if isinstance(p, ToolResult)] + [p for p in parts if not isinstance(p, ToolResult)]


def media_source(m) -> tuple[str, str]:
    """('base64' | 'url' | 'file', value) for an Image or Document."""
    if m.data is not None:
        return "base64", m.base64
    if m.url:
        return "url", m.url
    return "file", m.file_id or ""


def check_media(req: ChatRequest, provider: str) -> None:
    """Fail locally, with a clear message, on media the provider documents as rejected
    (lesson 21). Raises ValueError. Only checks what can be known from the bytes."""
    from ..media import LIMITS, image_info
    lim = LIMITS[provider]
    images = [p for m in req.messages for p in m.media if isinstance(p, Image)]
    docs = [p for m in req.messages for p in m.media if isinstance(p, Document)]
    if not images and not docs:
        return
    if len(images) > lim.get("max_images", 10**9):
        raise ValueError(f"{len(images)} images in one request; {provider} accepts at most {lim['max_images']}")
    many = provider == "anthropic" and len(images) + len(docs) > lim["many_images"]
    inline = 0
    for im in images:
        if im.data is None:
            continue
        inline += len(im.base64)
        info = image_info(im.data)
        if provider == "anthropic":
            if len(im.base64) > lim["image_bytes_b64"]:
                raise ValueError(f"image is {len(im.base64):,} bytes as base64; Anthropic's limit is 10 MB per image")
            side = lim["many_images_max_side"] if many else lim["max_side"]
            if max(info.width, info.height) > side:
                why = " (more than 20 images/documents in the request)" if many else ""
                raise ValueError(f"image is {info.width}x{info.height}; Anthropic's limit is {side} px per side{why}")
    pages = 0
    for d in docs:
        if d.data is None:
            continue
        inline += len(d.base64)
        pages += d.pages or 0
        if provider == "gemini" and len(d.data) > lim["pdf_bytes"]:
            raise ValueError("PDF is larger than 50 MB, Gemini's documented limit")
        if provider == "openai" and len(d.data) > lim["file_bytes"]:
            raise ValueError("file is larger than 50 MB, OpenAI's documented per-request file limit")
    if lim.get("pdf_pages") and pages > lim["pdf_pages"]:
        raise ValueError(f"{pages} PDF pages in one request; {provider} accepts at most {lim['pdf_pages']}")
    if inline > lim["request_bytes"]:
        raise ValueError(f"{inline:,} bytes of inline media; {provider}'s request limit is {lim['request_bytes']:,}"
                         " (use the provider's Files API for large files)")


class Provider(Protocol):
    name: str
    default_base_url: str
    key_env: tuple[str, ...]

    def build(self, req: ChatRequest, model: str, api_key: str, stream: bool) -> HTTPCall: ...
    def parse(self, body: dict, headers: dict) -> Parsed: ...
    def parse_stream(self, events: Iterator[SSEEvent], headers: dict) -> Iterator[StreamItem]: ...
    def error(self, status: int, text: str, headers: dict) -> LLMError: ...
    def map_stop(self, raw: str) -> StopReason: ...


def load_json(data: str, provider: str) -> dict:
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise LLMError(f"malformed JSON from provider: {exc}: {data[:120]!r}",
                       provider=provider, kind="malformed_response") from None


def header(headers: dict, name: str) -> Optional[str]:
    # httpx headers are case-insensitive; plain dicts in tests may not be.
    for k, v in headers.items():
        if k.lower() == name:
            return v
    return None


def generic_error(provider: str, status: int, text: str, headers: dict,
                  request_id_header: str) -> LLMError:
    kind, message = "", text[:300]
    try:
        body = json.loads(text)
        err = body.get("error", body)
        if isinstance(err, dict):
            kind = err.get("type") or err.get("status") or err.get("code") or ""
            message = err.get("message", message)
        rid = body.get("request_id")
    except (json.JSONDecodeError, AttributeError):
        rid = None
    return LLMError(
        message,
        provider=provider,
        status=status,
        kind=str(kind),
        retry_after=parse_retry_after(header(headers, "retry-after")),
        request_id=header(headers, request_id_header) or rid,
    )
