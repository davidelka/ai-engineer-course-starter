"""Reference ports (exercise 2). Each port is a typing.Protocol: structural typing,
so an adapter does not inherit from anything; it only has to have the methods.

Every port documents three things, because the signature alone is not the contract:
  1. what it returns (only domain types from designkit.types),
  2. which errors it may raise (only BrainError subclasses),
  3. the behavioral promises that a type checker cannot see (ordering, idempotency...).
Those promises are what the contract tests (exercise 4) check.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from .types import Answer, Completion, Passage


@runtime_checkable
class ChatModel(Protocol):
    """Port: something that turns (system, prompt) into text."""

    name: str  # "provider:model", recorded on every answer

    def complete(self, system: str, prompt: str, *, max_tokens: int = 512) -> Completion:
        """Return a Completion with non-empty text.

        Raises ModelUnavailable for transient failures (after the adapter's own
        retries) and ModelRejected for permanent ones. Never lets a provider or
        transport exception escape.
        """
        ...


@runtime_checkable
class Retriever(Protocol):
    """Port: search over company documents."""

    def search(self, query: str, k: int = 4) -> list[Passage]:
        """At most k passages, sorted by score, highest first, unique doc_ids.
        No match (or an empty query) returns [], it does not raise.
        Same query on the same data returns the same result.
        Raises RetrieverUnavailable when the backend is down."""
        ...


@runtime_checkable
class AnswerStore(Protocol):
    """Port: where answers are kept, keyed by request_id (the idempotency key)."""

    def get(self, request_id: str) -> Optional[Answer]:
        """The stored answer, or None."""
        ...

    def put(self, answer: Answer) -> bool:
        """Store if absent. Returns True if stored, False if an answer with this
        request_id already existed; the existing one is NOT overwritten
        (first write wins)."""
        ...


@runtime_checkable
class Clock(Protocol):
    """Port: time. Injected so tests can freeze it."""

    def now(self) -> datetime:
        """Timezone-aware current time."""
        ...
