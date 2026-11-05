"""Your code for lesson 20. Each part is checked by tests in ./tests.

    python -m pytest -q labs/20-design-driven/tests

The given parts of the design are imported from designkit:
  designkit/types.py   the domain types (Passage, Completion, Answer, ...) and the
                       error contract (ModelUnavailable, ModelRejected, RetrieverUnavailable)
  designkit/domain.py  pure business rules you call from the service (policy_check,
                       rank, build_prompt, parse_citations, degraded_text, NO_CONTEXT_TEXT)
Reference solutions live in designkit/ports.py, fakes.py, service.py, contract.py and
registry.py. Try not to peek before your tests pass.
"""

from __future__ import annotations

from datetime import datetime, timezone  # noqa: F401
from typing import Any, Callable, Optional, Protocol, Union, runtime_checkable  # noqa: F401

from designkit.domain import (ANSWER_PROMPT_V1, NO_CONTEXT_TEXT, build_prompt, degraded_text,  # noqa: F401
                              parse_citations, policy_check, rank)
from designkit.types import (Answer, AnswerRequest, BrainError, Completion, ModelRejected,  # noqa: F401
                             ModelUnavailable, Passage, PromptVersion, RetrieverUnavailable)


# ================================================================== exercise 2: ports
# Declare each port as a typing.Protocol, decorated with @runtime_checkable.
# Write the method signature exactly as given, with `...` as the body, and put the
# behavioral promises in the docstring: they are part of the contract.

@runtime_checkable
class ChatModel(Protocol):
    """Port: (system, prompt) -> text.

    Members:
        name: str                      e.g. "anthropic:claude-haiku-5-5"
        complete(self, system: str, prompt: str, *, max_tokens: int = 512) -> Completion
    Promises: non-empty text; raises ModelUnavailable (transient) or ModelRejected
    (permanent), never a provider or transport exception.

    Stuck? HINTS.md -> ChatModel
    """
    # TODO(ex2): declare `name: str` and the `complete` method


@runtime_checkable
class Retriever(Protocol):
    """Port: search over company documents.

    Members:
        search(self, query: str, k: int = 4) -> list[Passage]
    Promises: at most k, highest score first, unique doc_ids, [] when nothing
    matches (never raises for that), deterministic; RetrieverUnavailable when down.

    Stuck? HINTS.md -> Retriever
    """
    # TODO(ex2)


@runtime_checkable
class AnswerStore(Protocol):
    """Port: answers keyed by request_id.

    Members:
        get(self, request_id: str) -> Optional[Answer]
        put(self, answer: Answer) -> bool
    Promises: put stores only if absent and returns True; if the id exists it returns
    False and does NOT overwrite (first write wins).

    Stuck? HINTS.md -> AnswerStore
    """
    # TODO(ex2)


@runtime_checkable
class Clock(Protocol):
    """Port: time.

    Members:
        now(self) -> datetime          timezone-aware

    Stuck? HINTS.md -> Clock
    """
    # TODO(ex2)


# ================================================================== exercise 2: fakes
class FakeChatModel:
    """A fake model with real, predictable behavior. Satisfies the ChatModel port.

    __init__(self, reply=None, *, fail=None, name="fake:chat")
      reply: None, a str (always that), a list[str] (one per call in order; after the end keep
             returning the last one), or a callable (system, prompt) -> str.
             None: if the prompt contains <document id="X" ...>, the reply cites the FIRST such
             id as [X]; otherwise the reply is exactly "I don't know."
      fail:  None, "unavailable" (complete raises ModelUnavailable) or "rejected" (raises
             ModelRejected). Any other value: ValueError in __init__.
    self.calls: list of (system, prompt, max_tokens), one per complete() call, recorded even
    when the call fails.
    complete returns Completion(text, model=self.name, input_tokens=len(prompt)//4,
    output_tokens=max(1, len(text)//4)).

    Stuck? HINTS.md -> FakeChatModel
    """

    def __init__(self, reply: Union[None, str, list[str], Callable[[str, str], str]] = None,
                 *, fail: Optional[str] = None, name: str = "fake:chat"):
        # TODO(ex2)
        raise NotImplementedError("exercise 2: FakeChatModel")

    def complete(self, system: str, prompt: str, *, max_tokens: int = 512) -> Completion:
        raise NotImplementedError("exercise 2: FakeChatModel.complete")


class InMemoryRetriever:
    """Satisfies the Retriever port over a fixed list of passages.

    __init__(self, passages, *, fail=False). self.calls: the list of queries searched, in order.
    search raises RetrieverUnavailable when fail is set, otherwise keeps every Retriever promise
    (designkit.domain.rank already does the ranking).

    Stuck? HINTS.md -> InMemoryRetriever
    """

    def __init__(self, passages: list[Passage], *, fail: bool = False):
        raise NotImplementedError("exercise 2: InMemoryRetriever")

    def search(self, query: str, k: int = 4) -> list[Passage]:
        raise NotImplementedError("exercise 2: InMemoryRetriever.search")


class InMemoryAnswerStore:
    """A dict behind the AnswerStore port. First write wins.

    Stuck? HINTS.md -> InMemoryAnswerStore
    """

    def __init__(self):
        raise NotImplementedError("exercise 2: InMemoryAnswerStore")

    def get(self, request_id: str) -> Optional[Answer]:
        raise NotImplementedError

    def put(self, answer: Answer) -> bool:
        raise NotImplementedError


class FixedClock:
    """Satisfies the Clock port. now() returns a fixed aware datetime (default 2026-11-01 09:00
    UTC, or `at` when given); advance(seconds) moves it forward.

    Stuck? HINTS.md -> FixedClock
    """

    def __init__(self, at: Optional[datetime] = None):
        raise NotImplementedError("exercise 2: FixedClock")

    def now(self) -> datetime:
        raise NotImplementedError

    def advance(self, seconds: float) -> None:
        raise NotImplementedError


# ================================================================== exercise 3: the service
class AnswerService:
    """The behavior of legacy/tangled.py, written against the ports only.

    __init__ keeps every argument it receives and constructs NOTHING inside.
    answer(req) -> Answer, with request_id = req.request_id and created_at = clock.now().
    Outcomes (status, text, what is stored):
      - an answer already stored for req.request_id: returned as is, no other port is called;
      - policy_check refuses: "refused", text = the decision's reason; stored; no search, no model;
      - retriever down (RetrieverUnavailable): "degraded", text = degraded_text([]); NOT stored;
      - no passage with score >= min_score: "no_context", text = NO_CONTEXT_TEXT; stored; no model;
      - model down (ModelUnavailable): "degraded", text = degraded_text(passages), citations =
        the doc_ids of those passages; NOT stored (a retry may succeed);
      - ModelRejected: propagates (a bug or a config problem), nothing stored;
      - otherwise "answered": text = the completion text, citations = only ids of passages that
        were sent (parse_citations), prompt_version = prompt.ref, model and cost_usd from the
        Completion; stored.
    The model is called with the prompt version's template as system, build_prompt(...) as the
    prompt, and self.max_tokens; the retriever with self.k. If another call stored the same
    request_id first, return the stored answer instead of yours.

    Stuck? HINTS.md -> AnswerService
    """

    def __init__(self, model: ChatModel, retriever: Retriever, store: AnswerStore, clock: Clock,
                 *, prompt: PromptVersion = ANSWER_PROMPT_V1, k: int = 4, min_score: float = 0.2,
                 max_tokens: int = 512):
        # TODO(ex3)
        raise NotImplementedError("exercise 3: AnswerService.__init__")

    def answer(self, req: AnswerRequest) -> Answer:
        raise NotImplementedError("exercise 3: AnswerService.answer")


# ================================================================== exercise 4: contract tests
# One reusable test suite per port. A subclass named Test... implements the factory
# hook, and pytest runs all your test_* methods against that adapter
# (tests/test_ex4_contract.py does this for fakes AND for real adapters).
# Rules: test methods take ONLY self (no pytest fixtures), and use plain assert.
# Use the constants below. The tests also run YOUR suite against deliberately broken
# adapters: each broken one must fail at least one of your tests.

SYSTEM = "You are a test. Reply with one short sentence."
PROMPT = ('<documents>\n<document id="vacation_policy.md" title="Vacation">14 days.</document>\n</documents>'
          '\n\n<question>How many vacation days?</question>')
SAMPLE = [
    Passage(doc_id="vacation_policy.md", title="Vacation Policy",
            text="Full-time employees receive 14 paid vacation days in their first year of employment."),
    Passage(doc_id="remote_work_policy.md", title="Remote Work Policy",
            text="Employees may work remotely up to 2 days per week. Tuesday and Wednesday are office days."),
    Passage(doc_id="saas_access_policy.md#needs_security", title="SaaS Access Policy: needs_security",
            text="The security team reviews admin rights, production infrastructure and customer data."),
]


class ChatModelContract:
    """Hook: make_model(self, mode) with mode "ok", "unavailable" or "rejected".

    Write at least 4 test_* methods covering:
      - "ok" returns a Completion whose text is not empty
      - the model's name has the form "provider:model" and Completion.model equals it
      - token counts and cost are not negative
      - "unavailable" raises ModelUnavailable, and nothing else
      - "rejected" raises ModelRejected, and nothing else

    Stuck? HINTS.md -> ChatModelContract
    """

    def make_model(self, mode: str):
        raise NotImplementedError("subclass provides the adapter")

    # TODO(ex4): test_* methods


class RetrieverContract:
    """Hook: make_retriever(self, passages) -> an adapter that searches exactly these.

    Write at least 4 test_* methods covering (use SAMPLE):
      - a relevant query ("vacation days first year") finds vacation_policy.md first
      - at most k results, sorted by score, highest first
      - unique doc_ids, even if the same passage was given twice
      - no match and an empty query both return [] (not an exception)
      - the same query twice returns the same result

    Stuck? HINTS.md -> RetrieverContract
    """

    def make_retriever(self, passages: list[Passage]):
        raise NotImplementedError("subclass provides the adapter")

    # TODO(ex4)


class AnswerStoreContract:
    """Hook: make_store(self) -> a fresh, empty store.

    Write at least 3 test_* methods covering:
      - get() of an unknown id returns None
      - put() then get() returns an equal Answer, and put() returned True
      - a second put() with the same request_id returns False and does not overwrite

    Stuck? HINTS.md -> AnswerStoreContract
    """

    def make_store(self):
        raise NotImplementedError("subclass provides the adapter")

    # TODO(ex4)


# ================================================================== exercise 6: prompt/schema registry
class IncompatibleVersion(ValueError):
    """A breaking schema change registered without a new MAJOR version."""


def check_compatible(old: Optional[dict], new: Optional[dict]) -> list[str]:
    """Breaking changes for CODE THAT READS the output, between two JSON Schemas
    (from Model.model_json_schema()). Only top-level "properties" and "required" matter.

    Returns a list of messages, [] when nothing breaks. Each message starts with "breaking:",
    names the field in single quotes, and names what is new (the new type, e.g. null, or the
    new enum values), e.g. "breaking: removed field 'citations'".

    Breaking: the schema removed (old given, new None); a REQUIRED field removed; a required
    field no longer required; a field that can now hold a type it could not before ("type" as
    str or list, or "anyOf" members); an enum ("enum"/"const", also inside "anyOf") that gained
    values; a field that had an enum and now has none.
    NOT breaking: new fields, removing an optional field, fewer types, fewer enum values.
    old is None -> [].

    Stuck? HINTS.md -> check_compatible
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: check_compatible")


class PromptRegistry:
    """Versioned prompts. Versions are "MAJOR.MINOR.PATCH" strings, compared as numbers
    (so 1.10.0 > 1.9.0).

    register(pv: PromptVersion) -> None
      - bad version string -> ValueError
      - same name+version again: same pv.fingerprint is a no-op; a different fingerprint ->
        ValueError (versions are immutable)
      - a new version must be compatible (check_compatible on output_schema) with the previous
        version of the same name and SAME MAJOR, i.e. the highest one lower than pv; otherwise
        raise IncompatibleVersion, whose message lists the problems, and do not register it.
    get(name, pin="latest") -> PromptVersion
      - pin "latest": highest version; "1": highest 1.x.y; "1.2": highest 1.2.x;
        "1.2.3": exactly that. Unknown name or nothing matches -> KeyError.
    versions(name) -> list[str], sorted from lowest to highest.

    Stuck? HINTS.md -> PromptRegistry
    """

    def __init__(self):
        # TODO(ex6)
        raise NotImplementedError("exercise 6: PromptRegistry")

    def register(self, pv: PromptVersion) -> None:
        raise NotImplementedError

    def get(self, name: str, pin: str = "latest") -> PromptVersion:
        raise NotImplementedError

    def versions(self, name: str) -> list[str]:
        raise NotImplementedError
