"""llmkit: one adapter for Anthropic, OpenAI and Gemini (lesson 2).

Raw HTTP (httpx) on purpose: no SDK hides the request, the API version or the
retries. Every result carries normalized stop reason, usage, cost, latency,
TTFT (when streaming) and the provider's request id.
"""

from .client import LLM, parse_spec
from .errors import LLMError, RetryDecision, classify_error
from .pricing import PRICES, cost_usd
from .retry import RetryPolicy, backoff_delay
from .types import (Block, ChatRequest, ChatResult, Document, Image, Message, StreamEvent, Tool, ToolCall, ToolResult,
                    Usage, content_text)


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, existing environment wins. Never prints values."""
    import os
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


__all__ = [
    "LLM", "parse_spec", "LLMError", "RetryDecision", "classify_error", "PRICES", "cost_usd",
    "RetryPolicy", "backoff_delay", "ChatRequest", "ChatResult", "Message", "StreamEvent",
    "Usage", "load_dotenv", "Block", "content_text", "Tool", "ToolCall", "ToolResult", "Image", "Document",
]
