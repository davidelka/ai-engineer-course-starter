"""Domain types and the error contract of the Company Brain answer service (lesson 20).

These are the *given* part of the design: every port speaks only these types,
so no adapter-specific object (an httpx response, an anthropic Message, a
sqlite Row) ever crosses a port. Application code, fakes and real adapters all
import from here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- data that crosses ports
class Passage(BaseModel):
    """One retrieved piece of a document. `doc_id` is what the answer cites."""

    model_config = ConfigDict(frozen=True)
    doc_id: str
    title: str
    text: str
    score: float = 0.0


class Completion(BaseModel):
    """What a ChatModel returns. Provider-neutral on purpose."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class AnswerRequest(BaseModel):
    """One question. `request_id` is the idempotency key: the caller generates it
    once and sends the same value on every retry of the same question."""

    request_id: str = Field(min_length=1)
    user_email: str
    question: str


Status = Literal["answered", "refused", "no_context", "degraded"]


class Answer(BaseModel):
    request_id: str
    status: Status
    text: str
    citations: list[str] = Field(default_factory=list)
    prompt_version: Optional[str] = None  # e.g. "answer@1.0.0": which prompt produced this answer
    model: Optional[str] = None
    cost_usd: float = 0.0
    created_at: datetime


class PolicyDecision(BaseModel):
    allowed: bool
    rule: str = ""  # which rule decided, for the audit log
    reason: str = ""  # shown to the user when not allowed


class PromptVersion(BaseModel):
    """A versioned prompt plus the output schema the calling code expects.

    `version` is semantic: MAJOR.MINOR.PATCH. A change that can break the code
    that reads the output (a removed field, a new enum value...) needs a new MAJOR.
    """

    model_config = ConfigDict(frozen=True)
    name: str
    version: str
    template: str
    output_schema: Optional[dict[str, Any]] = None

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def fingerprint(self) -> str:
        """Content hash: two versions with the same number must have the same fingerprint."""
        blob = json.dumps({"t": self.template, "s": self.output_schema}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- the error contract
class BrainError(Exception):
    """Base of every error a port may raise. Adapters translate their own
    exceptions (LLMError, httpx errors, sqlite3 errors...) into one of these,
    so the service never imports an adapter's exception types."""

    retryable: ClassVar[bool] = False


class ModelUnavailable(BrainError):
    """Transient: timeout, 429, 5xx, overload, a broken stream, after the
    adapter's own retries were used up. Trying again later may work."""

    retryable = True


class ModelRejected(BrainError):
    """Permanent: bad request, bad key, refusal, content too long. Sending the
    same request again will fail again. This is a bug or a config problem."""

    retryable = False


class RetrieverUnavailable(BrainError):
    """Transient failure of the search backend (vector DB down, timeout)."""

    retryable = True
