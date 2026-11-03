"""Exercise 2: the four ports as Protocols, and a fake for each."""

import inspect
from datetime import datetime, timedelta, timezone

import pytest

import mine
from designkit.adapters import JsonlAnswerStore, KeywordRetriever, LlmkitChatModel, SystemClock
from designkit.types import Answer, Completion, ModelRejected, ModelUnavailable, Passage, RetrieverUnavailable
from llmkit import LLM

PROMPT = '<documents>\n<document id="vacation_policy.md" title="V">14 days</document>\n</documents>\n<question>q</question>'


# ---------------------------------------------------------------- ports
def params(proto, method):
    assert hasattr(proto, method), f"{proto.__name__} must declare {method}()"
    return list(inspect.signature(getattr(proto, method)).parameters)


def test_ports_declare_their_methods():
    assert params(mine.ChatModel, "complete")[:3] == ["self", "system", "prompt"]
    assert "max_tokens" in params(mine.ChatModel, "complete")
    assert params(mine.Retriever, "search") == ["self", "query", "k"]
    assert params(mine.AnswerStore, "get") == ["self", "request_id"]
    assert params(mine.AnswerStore, "put") == ["self", "answer"]
    assert params(mine.Clock, "now") == ["self"]
    assert "name" in getattr(mine.ChatModel, "__annotations__", {}), "ChatModel must declare `name: str`"


def test_k_and_max_tokens_have_defaults():
    assert inspect.signature(mine.Retriever.search).parameters["k"].default == 4
    assert inspect.signature(mine.ChatModel.complete).parameters["max_tokens"].default == 512


def test_real_adapters_satisfy_your_ports_without_inheriting():
    # Structural typing: none of these classes knows that mine.py exists.
    llm = LLM("anthropic:mock-model", api_key="t", base_url="http://127.0.0.1:9")
    assert isinstance(LlmkitChatModel(llm), mine.ChatModel)
    assert isinstance(KeywordRetriever([]), mine.Retriever)
    assert isinstance(JsonlAnswerStore("/nonexistent/never-written.jsonl"), mine.AnswerStore)
    assert isinstance(SystemClock(), mine.Clock)


def test_ports_reject_things_that_do_not_fit():
    assert not isinstance(object(), mine.ChatModel)
    assert not isinstance(SystemClock(), mine.Retriever)
    assert not isinstance(KeywordRetriever([]), mine.AnswerStore)


# ---------------------------------------------------------------- fakes
def test_fakes_satisfy_the_ports():
    assert isinstance(mine.FakeChatModel(), mine.ChatModel)
    assert isinstance(mine.InMemoryRetriever([]), mine.Retriever)
    assert isinstance(mine.InMemoryAnswerStore(), mine.AnswerStore)
    assert isinstance(mine.FixedClock(), mine.Clock)


def test_fake_model_replies():
    m = mine.FakeChatModel("hello")
    c = m.complete("sys", "prompt text", max_tokens=99)
    assert isinstance(c, Completion) and c.text == "hello" and c.model == "fake:chat"
    assert m.calls == [("sys", "prompt text", 99)]
    seq = mine.FakeChatModel(["one", "two"])
    assert [seq.complete("s", "p").text for _ in range(3)] == ["one", "two", "two"]
    fn = mine.FakeChatModel(lambda s, p: p.upper())
    assert fn.complete("s", "abc").text == "ABC"


def test_fake_model_default_reply_cites_the_first_document():
    c = mine.FakeChatModel().complete("s", PROMPT)
    assert "[vacation_policy.md]" in c.text
    assert mine.FakeChatModel().complete("s", "no documents here").text == "I don't know."


def test_fake_model_failures_follow_the_error_contract():
    m = mine.FakeChatModel(fail="unavailable")
    with pytest.raises(ModelUnavailable):
        m.complete("s", "p")
    assert len(m.calls) == 1, "record the call before failing"
    with pytest.raises(ModelRejected):
        mine.FakeChatModel(fail="rejected").complete("s", "p")
    with pytest.raises(ValueError):
        mine.FakeChatModel(fail="sometimes")


def test_in_memory_retriever():
    ps = [Passage(doc_id="a", title="Vacation", text="vacation days"), Passage(doc_id="b", title="Remote", text="remote work")]
    r = mine.InMemoryRetriever(ps)
    hits = r.search("vacation days", k=1)
    assert [h.doc_id for h in hits] == ["a"] and hits[0].score > 0
    assert r.search("zebra") == []
    assert r.calls == ["vacation days", "zebra"]
    with pytest.raises(RetrieverUnavailable):
        mine.InMemoryRetriever(ps, fail=True).search("x")


def test_in_memory_store_first_write_wins():
    s = mine.InMemoryAnswerStore()
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a1 = Answer(request_id="r", status="answered", text="first", created_at=t)
    a2 = Answer(request_id="r", status="answered", text="second", created_at=t)
    assert s.get("r") is None
    assert s.put(a1) is True and s.put(a2) is False
    assert s.get("r").text == "first"


def test_fixed_clock():
    c = mine.FixedClock()
    assert c.now() == datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    c.advance(90)
    assert c.now() == datetime(2026, 11, 1, 9, 1, 30, tzinfo=timezone.utc)
    t = datetime(2030, 5, 5, tzinfo=timezone.utc)
    assert mine.FixedClock(t).now() == t and mine.FixedClock(t).now().tzinfo is not None
    assert c.now() - mine.FixedClock().now() == timedelta(seconds=90)
