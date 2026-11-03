"""One error type for every provider, plus the retry decision.

The rule from the lesson: an error caused by the request will not go away
if you send the same request again; an error caused by a temporary state at
the provider might.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# HTTP statuses worth retrying. 408 = request timeout, 409 = conflict
# (OpenAI uses it for transient conflicts), 529 = Anthropic "overloaded".
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
# Error types that arrive inside a stream (after HTTP 200) and are transient.
RETRYABLE_KINDS = {"overloaded_error", "rate_limit_error", "api_error", "server_error", "timeout", "network"}


class LLMError(Exception):
    """A failed call, normalized across providers."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status: Optional[int] = None,
        kind: str = "",
        retry_after: Optional[float] = None,
        request_id: Optional[str] = None,
        partial_text: str = "",
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status = status
        self.kind = kind  # e.g. invalid_request_error, overloaded_error, timeout, network, stream_truncated
        self.retry_after = retry_after
        self.request_id = request_id
        self.partial_text = partial_text  # text that arrived before a stream broke

    def __str__(self) -> str:
        bits = [self.provider or "llm"]
        if self.status:
            bits.append(str(self.status))
        if self.kind:
            bits.append(self.kind)
        if self.request_id:
            bits.append(f"request_id={self.request_id}")
        return f"[{' '.join(bits)}] {self.message}"


@dataclass
class RetryDecision:
    retry: bool
    retry_after: Optional[float] = None  # server-requested minimum wait, seconds


def classify_error(err: LLMError) -> RetryDecision:
    """Reference implementation. Exercise 3 asks you to write your own in mine.py."""
    if err.status is not None and err.status in RETRYABLE_STATUS:
        return RetryDecision(True, err.retry_after)
    if err.status is None and err.kind in RETRYABLE_KINDS | {"stream_truncated", "malformed_response"}:
        return RetryDecision(True, err.retry_after)
    return RetryDecision(False)


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """retry-after is seconds ("12") in practice; HTTP also allows a date, which we ignore."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
