"""Exercise 4: your contract suites, run against fakes, real adapters and broken adapters.

The Test* classes below inherit YOUR test_* methods from mine.py, so pytest
reports one result per (adapter, contract test). Then the meta-tests check
that your suites are strong enough: each broken adapter must fail at least one
of your tests.

Optional live run (costs well under a cent, needs ANTHROPIC_API_KEY in .env):
    BRAIN_LIVE_MODEL=anthropic:claude-haiku-5-5 python -m pytest -q labs/20-design-driven/tests/test_ex4_contract.py -k Live
"""

import os
import random
from datetime import datetime, timezone

import pytest

import mine
from designkit.adapters import JsonlAnswerStore, KeywordRetriever, LlmkitChatModel
from designkit.domain import rank
from designkit.types import Answer, Completion, ModelRejected, ModelUnavailable, Passage
from llmkit import LLM, LLMError, RetryPolicy, load_dotenv
from mockllm import MockConfig, start_in_thread

_SERVER = None


def mock_server():
    """One mockllm per test session, started on first use."""
    global _SERVER
    if _SERVER is None:
        _SERVER = start_in_thread(MockConfig())
    return _SERVER


def no_sleep_retry():
    return RetryPolicy(max_attempts=2, sleep=lambda s: None, rng=random.Random(0))


# ================================================================ your suites, real adapters
class TestFakeChatModel(mine.ChatModelContract):
    def make_model(self, mode):
        return mine.FakeChatModel(fail=None if mode == "ok" else mode)


class TestLlmkitChatModel(mine.ChatModelContract):
    """The real adapter over llmkit, talking HTTP to mockllm. 'unavailable' = 529 on
    every attempt; 'rejected' = 400."""

    def make_model(self, mode):
        server, url = mock_server()
        server.state.cfg = {"ok": MockConfig(ttft=0, tps=0, reply="Fourteen days [vacation_policy.md]."),
                            "unavailable": MockConfig(ttft=0, tps=0, fail_first=10_000, status=529),
                            "rejected": MockConfig(ttft=0, tps=0, fail_first=10_000, status=400)}[mode]
        server.state.reset()
        return LlmkitChatModel(LLM("anthropic:mock-model", api_key="t", base_url=url, retry=no_sleep_retry()))


@pytest.mark.skipif(not os.environ.get("BRAIN_LIVE_MODEL"), reason="set BRAIN_LIVE_MODEL to run against a real provider")
class TestLiveChatModel(mine.ChatModelContract):
    def make_model(self, mode):
        if mode != "ok":
            pytest.skip("failure modes are tested against mockllm, not by breaking a real provider")
        load_dotenv()
        return LlmkitChatModel(LLM(os.environ["BRAIN_LIVE_MODEL"]))


class TestInMemoryRetriever(mine.RetrieverContract):
    def make_retriever(self, passages):
        return mine.InMemoryRetriever(passages)


class TestKeywordRetriever(mine.RetrieverContract):
    def make_retriever(self, passages):
        return KeywordRetriever.from_passages(passages)


class TestInMemoryAnswerStore(mine.AnswerStoreContract):
    def make_store(self):
        return mine.InMemoryAnswerStore()


class TestJsonlAnswerStore(mine.AnswerStoreContract):
    def make_store(self):
        import tempfile
        from pathlib import Path
        return JsonlAnswerStore(Path(tempfile.mkdtemp()) / "answers.jsonl")


# ================================================================ broken adapters
class LeakyModel:
    """Lets the provider's exception escape instead of translating it."""
    name = "broken:leaky"

    def __init__(self, mode):
        self.mode = mode

    def complete(self, system, prompt, *, max_tokens=512):
        if self.mode == "unavailable":
            raise LLMError("overloaded", provider="anthropic", status=529, kind="overloaded_error")
        if self.mode == "rejected":
            raise LLMError("bad request", provider="anthropic", status=400, kind="invalid_request_error")
        return Completion(text="ok", model=self.name)


class SwappedErrorsModel(LeakyModel):
    """Translates, but gets transient and permanent the wrong way round."""
    name = "broken:swapped"

    def complete(self, system, prompt, *, max_tokens=512):
        if self.mode == "unavailable":
            raise ModelRejected("x")
        if self.mode == "rejected":
            raise ModelUnavailable("x")
        return Completion(text="ok", model=self.name)


class EmptyTextModel(LeakyModel):
    """Works, but returns empty text and a model name that does not match."""
    name = "broken:empty"

    def complete(self, system, prompt, *, max_tokens=512):
        if self.mode == "unavailable":
            raise ModelUnavailable("x")
        if self.mode == "rejected":
            raise ModelRejected("x")
        return Completion(text="   ", model="other-name")


class UnsortedRetriever:
    """Returns every passage that matches, in insertion order, ignoring k."""

    def __init__(self, passages):
        self.passages = passages

    def search(self, query, k=4):
        scored = rank(query, self.passages, 100)
        order = {p.doc_id: i for i, p in enumerate(self.passages)}
        return sorted(scored, key=lambda p: order[p.doc_id])


class RaisingRetriever:
    """Raises when nothing matches, and duplicates passages."""

    def __init__(self, passages):
        self.passages = passages

    def search(self, query, k=4):
        hits = [p for p in self.passages if any(w in p.text.lower() for w in query.lower().split())]
        if not hits:
            raise LookupError("no results")
        hits = sorted(hits, key=lambda p: -len(p.text))
        return [p.model_copy(update={"score": 1.0}) for p in hits[:k]]


class OverwritingStore:
    """Last write wins, and put always says True."""

    def __init__(self):
        self.d = {}

    def get(self, rid):
        return self.d.get(rid)

    def put(self, a):
        self.d[a.request_id] = a
        return True


class ForgetfulStore(OverwritingStore):
    """put() says True and stores nothing."""

    def put(self, a):
        return True


BROKEN = [  # (id, contract, hook name, factory)
    ("leaky-model", mine.ChatModelContract, "make_model", lambda self, mode: LeakyModel(mode)),
    ("swapped-errors", mine.ChatModelContract, "make_model", lambda self, mode: SwappedErrorsModel(mode)),
    ("empty-text", mine.ChatModelContract, "make_model", lambda self, mode: EmptyTextModel(mode)),
    ("unsorted-retriever", mine.RetrieverContract, "make_retriever", lambda self, ps: UnsortedRetriever(ps)),
    ("raising-retriever", mine.RetrieverContract, "make_retriever", lambda self, ps: RaisingRetriever(ps)),
    ("overwriting-store", mine.AnswerStoreContract, "make_store", lambda self: OverwritingStore()),
    ("forgetful-store", mine.AnswerStoreContract, "make_store", lambda self: ForgetfulStore()),
]
WHAT = {"leaky-model": LeakyModel.__doc__, "swapped-errors": SwappedErrorsModel.__doc__,
        "empty-text": EmptyTextModel.__doc__, "unsorted-retriever": UnsortedRetriever.__doc__,
        "raising-retriever": RaisingRetriever.__doc__, "overwriting-store": OverwritingStore.__doc__,
        "forgetful-store": ForgetfulStore.__doc__}


def run_suite(base, hook, factory):
    """Run every test_* method of a contract class against one adapter, without pytest.
    Returns (number of tests, list of failures)."""
    cls = type("Probe", (base,), {hook: factory})
    names = [n for n in dir(cls) if n.startswith("test_") and callable(getattr(cls, n))]
    failures = []
    for n in names:
        try:
            getattr(cls(), n)()
        except pytest.skip.Exception:
            pass
        except BaseException as exc:  # noqa: BLE001  (AssertionError, or the adapter blew up)
            failures.append(f"{n}: {type(exc).__name__}")
    return len(names), failures


# ================================================================ meta-tests
@pytest.mark.parametrize("base,minimum", [(mine.ChatModelContract, 4), (mine.RetrieverContract, 4),
                                          (mine.AnswerStoreContract, 3)])
def test_contract_has_enough_tests(base, minimum):
    n = len([x for x in dir(base) if x.startswith("test_")])
    assert n >= minimum, f"{base.__name__} has {n} test_* methods, needs at least {minimum}"


@pytest.mark.parametrize("name,base,hook,factory", BROKEN, ids=[b[0] for b in BROKEN])
def test_contract_catches_broken_adapter(name, base, hook, factory):
    n, failures = run_suite(base, hook, factory)
    assert n > 0, f"{base.__name__} has no test_* methods yet"
    assert failures, f"all {n} tests of {base.__name__} PASSED for a broken adapter. It is broken like this: {WHAT[name]}"


def test_contract_methods_take_only_self():
    import inspect
    for base in (mine.ChatModelContract, mine.RetrieverContract, mine.AnswerStoreContract):
        for n in dir(base):
            if n.startswith("test_"):
                assert list(inspect.signature(getattr(base, n)).parameters) == ["self"], \
                    f"{base.__name__}.{n} must take only self (no fixtures)"


def test_answer_helper_sanity():
    # Not about your code: makes sure the Answer model used by the store contract is what we think.
    a = Answer(request_id="x", status="answered", text="t", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert Answer.model_validate_json(a.model_dump_json()) == a
    assert Passage(doc_id="d", title="t", text="x").score == 0.0
