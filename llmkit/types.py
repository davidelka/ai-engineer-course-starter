"""Provider-neutral request and result types.

Everything above the adapter layer speaks only these types, so swapping a
provider never touches application code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

Role = Literal["user", "assistant"]
# Prompt-cache lifetimes (lesson 4). Anthropic: "5m" (default) or "1h".
CacheTTL = Literal["5m", "1h"]
# Normalized stop reasons. Each adapter maps its provider's values onto these.
StopReason = Literal["end", "max_tokens", "stop_sequence", "tool_use", "refusal", "other"]


@dataclass
class Block:
    """One piece of text in a system prompt or a message (lesson 4).

    cache="5m" or "1h" puts a cache breakpoint at the END of this block: on
    Anthropic it becomes cache_control, so everything up to and including this
    block is the cached prefix. Other providers cache prefixes automatically and
    simply see the joined text.
    """

    text: str
    cache: Optional[CacheTTL] = None


# ---------------------------------------------------------------- tools (lesson 14)
@dataclass
class Tool:
    """A function the model may ask YOUR code to run.

    input_schema is a JSON Schema object (build it from a Pydantic model with
    llmkit.tools.tool_from_model). strict=True asks the provider to guarantee that
    arguments match the schema (Anthropic strict tool use, OpenAI strict functions,
    Gemini VALIDATED mode); the adapter then sends llmkit.schema.strict_schema(...).
    cache: Anthropic only, a cache breakpoint after this tool definition.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    strict: bool = False
    cache: Optional[CacheTTL] = None


@dataclass
class ToolCall:
    """One tool call the model asked for, normalized across providers.

    id: Anthropic tool_use.id / OpenAI call_id / Gemini functionCall.id (or a local
    id starting with LOCAL_ID_PREFIX when Gemini sent none).
    arguments: always a dict. If the provider sent arguments that are not valid
    JSON, arguments is {} and parse_error says why (your executor should answer
    with an is_error result, not crash).
    raw_arguments: the arguments string exactly as received (OpenAI sends a string;
    for the others it is json.dumps of the object).
    signature: Gemini thoughtSignature, which must be sent back with the call.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str = ""
    parse_error: Optional[str] = None
    signature: Optional[str] = None


LOCAL_ID_PREFIX = "llmkit-local-"


@dataclass
class ToolResult:
    """The output of running one ToolCall, sent back to the model.

    content: a string, or anything JSON-serializable (sent as JSON text).
    is_error: True when the tool failed. The model sees the error and can recover
    (retry with fixed arguments, try another tool, or explain), instead of your
    program crashing.
    name: the tool name. Gemini needs it in functionResponse; the adapter fills it
    from the matching ToolCall when you leave it empty.
    """

    call_id: str
    content: Any
    is_error: bool = False
    name: str = ""

    @property
    def text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        return json.dumps(self.content, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- media (lesson 21)
def _short(b: Optional[bytes]) -> str:
    return "None" if b is None else f"<{len(b):,} bytes>"


@dataclass(repr=False)
class Image:
    """An image in a user message. Exactly one source: data (bytes), url, or file_id.

    media_type is sniffed from the bytes when you leave it empty, so a .jpg file that is
    really a PNG is still sent with the right type (Anthropic returns 400 on a mismatch).
    detail: OpenAI "low" | "high" | "auto" | "original"; Gemini media resolution
    "low" | "medium" | "high" | "ultra_high". Anthropic has no such knob and ignores it.
    cache: Anthropic cache breakpoint after this block (lesson 4).
    See llmkit/MEDIA.md for the wire shapes and limits.
    """

    data: Optional[bytes] = None
    media_type: str = ""
    url: Optional[str] = None
    file_id: Optional[str] = None
    detail: Optional[str] = None
    cache: Optional[CacheTTL] = None

    def __post_init__(self):
        sources = [x for x in (self.data, self.url, self.file_id) if x]
        if len(sources) != 1:
            raise ValueError("Image needs exactly one of data, url or file_id")
        if self.data is not None and not self.media_type:
            from .media import image_info
            self.media_type = image_info(self.data).media_type

    @classmethod
    def from_path(cls, path, **kw) -> "Image":
        from pathlib import Path
        return cls(data=Path(path).read_bytes(), **kw)

    @classmethod
    def from_url(cls, url: str, **kw) -> "Image":
        return cls(url=url, **kw)

    @property
    def base64(self) -> str:
        import base64
        return base64.b64encode(self.data or b"").decode("ascii")

    @property
    def size(self) -> Optional[tuple[int, int]]:
        """(width, height) read from the header bytes, or None for url / file_id images."""
        if self.data is None:
            return None
        from .media import image_info
        info = image_info(self.data)
        return info.width, info.height

    def __repr__(self) -> str:  # never dump megabytes of bytes into a log line
        src = _short(self.data) if self.data is not None else (self.url or f"file_id={self.file_id}")
        return f"Image({self.media_type or '?'}, {src}, detail={self.detail})"


@dataclass(repr=False)
class Document:
    """A PDF (or, on Anthropic via the Files API, a text file) in a user message.

    The provider turns each page into an image AND extracts its text, so a page costs
    image tokens plus text tokens (lesson 21). Exactly one source: data, url, file_id.
    filename: OpenAI requires one with file_data. title: Anthropic document title.
    detail: OpenAI page-image detail ("low" | "high" | "auto"); Gemini media resolution.
    """

    data: Optional[bytes] = None
    media_type: str = "application/pdf"
    url: Optional[str] = None
    file_id: Optional[str] = None
    filename: str = "document.pdf"
    title: Optional[str] = None
    detail: Optional[str] = None
    cache: Optional[CacheTTL] = None

    def __post_init__(self):
        sources = [x for x in (self.data, self.url, self.file_id) if x]
        if len(sources) != 1:
            raise ValueError("Document needs exactly one of data, url or file_id")

    @classmethod
    def from_path(cls, path, **kw) -> "Document":
        from pathlib import Path
        p = Path(path)
        kw.setdefault("filename", p.name)
        return cls(data=p.read_bytes(), **kw)

    @property
    def base64(self) -> str:
        import base64
        return base64.b64encode(self.data or b"").decode("ascii")

    @property
    def pages(self) -> Optional[int]:
        if self.data is None:
            return None
        from .media import pdf_page_count
        return pdf_page_count(self.data)

    def __repr__(self) -> str:
        src = _short(self.data) if self.data is not None else (self.url or f"file_id={self.file_id}")
        return f"Document({self.media_type}, {self.filename}, {src})"


Media = Union[Image, Document]
Part = Union[Block, ToolCall, ToolResult, Image, Document]
Content = Union[str, list[Part]]


def media_parts(content: "Content") -> list[Media]:
    """The images and documents in a message's content (empty for a plain string)."""
    return [] if isinstance(content, str) else [p for p in content if isinstance(p, (Image, Document))]


def content_text(content: Content) -> str:
    """The plain text of a str or a list of parts (text blocks joined with blank lines).
    Tool calls and tool results are not text and are skipped."""
    if isinstance(content, str):
        return content
    return "\n\n".join(b.text for b in content if isinstance(b, Block))


@dataclass
class Message:
    """One turn. content is a plain string (the common case, unchanged since lesson 2),
    or a list of parts: Block (text, optional cache breakpoint), ToolCall (in an
    assistant turn), ToolResult (in a user turn), and Image / Document (in a user
    turn, lesson 21).

    raw / raw_provider: the provider's own output for an assistant turn, exactly as
    received (Anthropic content blocks, OpenAI output items, Gemini parts). When the
    message is sent back to the SAME provider, the adapter replays raw verbatim, which
    keeps thinking blocks, reasoning items and Gemini thought signatures intact. Sent
    to another provider, the normalized content is used instead.
    """

    role: Role
    content: Content
    raw: Optional[Any] = None
    raw_provider: Optional[str] = None

    @property
    def text(self) -> str:
        return content_text(self.content)

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [] if isinstance(self.content, str) else [p for p in self.content if isinstance(p, ToolCall)]

    @property
    def tool_results(self) -> list[ToolResult]:
        return [] if isinstance(self.content, str) else [p for p in self.content if isinstance(p, ToolResult)]

    @property
    def media(self) -> list[Media]:
        return media_parts(self.content)

    @classmethod
    def user_with(cls, *parts: Union[str, Block, Image, Document]) -> "Message":
        """A user turn mixing text and media, in the order given (lesson 21):
        Message.user_with(Image.from_path("receipt.png"), "What is the total?").
        Strings become Blocks. Put images before the question: Anthropic documents that
        image-then-text works best."""
        return cls("user", [Block(p) if isinstance(p, str) else p for p in parts])

    @classmethod
    def with_tool_results(cls, results: list[ToolResult], text: str = "") -> "Message":
        """The user turn that answers a tool-calling assistant turn: ALL results of
        that turn in ONE message (parallel calls included), optional text after them."""
        parts: list[Part] = list(results)
        if text:
            parts.append(Block(text))
        return cls("user", parts)


@dataclass
class ChatRequest:
    messages: list[Message]
    system: Content = ""  # a string, or Blocks with cache breakpoints (lesson 4)
    max_tokens: int = 1024
    effort: Optional[str] = None  # low | medium | high, mapped per provider
    # Provider-specific escape hatch: merged into the request body as-is.
    # This is how the adapter avoids the "lowest common denominator" trap.
    extra_body: dict[str, Any] = field(default_factory=dict)
    # Native structured output (lesson 3): a provider-ready JSON Schema, or None.
    # Build it with llmkit.structured.provider_schema(Model, provider).
    response_schema: Optional[dict[str, Any]] = None
    schema_name: str = "output"
    # Prompt caching (lesson 4).
    # cache: automatic caching. Anthropic gets a top-level cache_control, which puts
    #   the breakpoint on the last cacheable block and moves it as the chat grows.
    #   OpenAI and Gemini cache prefixes automatically; this field is ignored there.
    # cache_key: OpenAI's prompt_cache_key (routes requests that share a prefix to
    #   the same cache). Ignored by the other providers.
    # Explicit breakpoints: Block(text, cache="5m"|"1h") in system or message content.
    cache: Optional[CacheTTL] = None
    cache_key: Optional[str] = None
    # Tool use (lesson 14). See llmkit/TOOLS.md.
    tools: list[Tool] = field(default_factory=list)
    # None (provider default, which is "auto" when tools are given) | "auto" | "any"
    # (must call some tool) | "none" (must not call tools) | any other string = the
    # name of the ONE tool the model must call.
    tool_choice: Optional[str] = None
    # False = at most one tool call per turn. None = provider default (parallel allowed).
    # Gemini has no switch for this; the adapter ignores it there.
    parallel_tool_calls: Optional[bool] = None

    @property
    def system_text(self) -> str:
        return content_text(self.system)

    @classmethod
    def from_prompt(cls, prompt: str, **kw) -> "ChatRequest":
        return cls(messages=[Message("user", prompt)], **kw)


@dataclass
class Usage:
    # input_tokens is the TOTAL prompt size on every provider: uncached + cache reads
    # + cache writes. (Anthropic reports these three separately; the adapter adds them.)
    input_tokens: int = 0
    output_tokens: int = 0  # includes thinking tokens: they are billed as output
    cached_input_tokens: int = 0  # cache READS: billed at the cheap cached rate
    cache_creation_tokens: int = 0  # cache WRITES (Anthropic, OpenAI GPT-5.6+): billed above input
    cache_creation_1h_tokens: int = 0  # the part of cache_creation_tokens written with a 1h TTL
    thinking_tokens: int = 0  # informational subset of output_tokens, when reported

    @property
    def uncached_input_tokens(self) -> int:
        """Prompt tokens processed at the normal input price."""
        return max(0, self.input_tokens - self.cached_input_tokens - self.cache_creation_tokens)


@dataclass
class ChatResult:
    text: str
    stop_reason: StopReason
    usage: Usage
    provider: str
    model: str
    cost_usd: Optional[float] = None
    latency_s: float = 0.0
    ttft_s: Optional[float] = None  # only measured when streaming
    request_id: Optional[str] = None
    attempts: int = 1
    raw_stop_reason: str = ""
    partial: bool = False  # True when a stream broke after text had arrived
    # Lesson 14: tool calls the model asked for (empty when it just answered), and the
    # provider's raw output, kept so the turn can be replayed verbatim.
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_output: Optional[Any] = None

    @property
    def message(self) -> "Message":
        """This reply as an assistant Message, ready to append to the conversation.
        Holds the text, the tool calls, and the raw provider output for replay."""
        if not self.tool_calls:  # a plain answer stays a plain string, as before lesson 14
            return Message("assistant", self.text)
        parts: list[Part] = [Block(self.text)] if self.text else []
        parts += self.tool_calls
        return Message("assistant", parts, raw=self.raw_output, raw_provider=self.provider)

    @property
    def tokens_per_second(self) -> Optional[float]:
        """Visible output tokens per second after the first token.

        Thinking tokens are excluded: they are generated BEFORE the first visible
        token (inside ttft_s), so counting them here would inflate the rate.
        """
        visible = self.usage.output_tokens - self.usage.thinking_tokens
        if self.ttft_s is None or self.latency_s <= self.ttft_s or visible <= 0:
            return None
        return visible / (self.latency_s - self.ttft_s)


@dataclass
class StreamEvent:
    """One normalized streaming event.

    type == "text": a piece of output text in `text`.
    type == "tool_call_delta": a fragment of a tool call's arguments JSON in `text`
        (concatenate; parse only when the "tool_call" event arrives). `tool_call`
        holds the id and name known so far.
    type == "tool_call": one tool call is complete; `tool_call` holds it.
    type == "done": the stream finished; `result` holds the full ChatResult.
    Errors are raised as exceptions, never yielded.
    """

    type: Literal["text", "tool_call_delta", "tool_call", "done"]
    text: str = ""
    result: Optional[ChatResult] = None
    tool_call: Optional[ToolCall] = None
