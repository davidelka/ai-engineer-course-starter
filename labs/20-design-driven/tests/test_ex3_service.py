"""Exercise 3: AnswerService against ports. Uses the REFERENCE fakes from
designkit.fakes, so a bug in your fakes (exercise 2) cannot hide here."""

from datetime import datetime, timezone

import pytest

import mine
from designkit.domain import ANSWER_PROMPT_V1, NO_CONTEXT_TEXT
from designkit.fakes import SAMPLE_PASSAGES, FakeChatModel, FixedClock, InMemoryAnswerStore, InMemoryRetriever
from designkit.types import Answer, AnswerRequest, ModelRejected, PromptVersion

REPLY = "First-year employees get 14 days [vacation_policy.md]. See also [made_up.md]."
Q = "How many vacation days do I get in my first year?"


def build(model=None, retriever=None, store=None, **kw):
    model = model or FakeChatModel(REPLY)
    retriever = retriever or InMemoryRetriever(SAMPLE_PASSAGES)
    store = store if store is not None else InMemoryAnswerStore()
    svc = mine.AnswerService(model, retriever, store, FixedClock(), **kw)
    return svc, model, retriever, store


def req(q=Q, rid="r1", email="dana@acme.example"):
    return AnswerRequest(request_id=rid, user_email=email, question=q)


def test_answers_with_only_real_citations():
    svc, model, _, store = build()
    a = svc.answer(req())
    assert a.status == "answered" and a.text == REPLY
    assert a.citations == ["vacation_policy.md"], "made_up.md was never retrieved: drop it"
    assert a.prompt_version == "answer@1.0.0" and a.model == "fake:chat"
    assert a.created_at == datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc), "use the injected clock"
    assert store.get("r1") == a


def test_sends_the_versioned_prompt_and_the_passages():
    p = PromptVersion(name="answer", version="1.3.0", template="SYSTEM v1.3")
    svc, model, _, _ = build(prompt=p, max_tokens=300)
    a = svc.answer(req())
    system, prompt, max_tokens = model.calls[0]
    assert system == "SYSTEM v1.3" and max_tokens == 300
    assert '<document id="vacation_policy.md"' in prompt and Q in prompt
    assert a.prompt_version == "answer@1.3.0"


def test_replay_returns_stored_answer_without_calling_anything():
    svc, model, retriever, store = build()
    first = svc.answer(req())
    again = svc.answer(req())
    assert again == first
    assert len(model.calls) == 1 and len(retriever.calls) == 1


@pytest.mark.parametrize("q,email", [("What is Moshe's salary?", "dana@acme.example"),
                                     ("Where do I find the AWS API key?", "dana@acme.example"),
                                     (Q, "someone@gmail.com")])
def test_policy_runs_before_search_and_model(q, email):
    svc, model, retriever, store = build()
    a = svc.answer(req(q=q, email=email))
    assert a.status == "refused" and a.text
    assert model.calls == [] and retriever.calls == []
    assert store.get("r1") == a


def test_no_context_skips_the_model():
    svc, model, _, store = build()
    a = svc.answer(req(q="Who won the football match yesterday?"))
    assert a.status == "no_context" and a.text == NO_CONTEXT_TEXT
    assert model.calls == [] and store.get("r1") == a


def test_min_score_filters_weak_passages():
    svc, model, _, _ = build(min_score=0.99)
    a = svc.answer(req(q="vacation remote zebra"))  # each passage matches only part of the query
    assert a.status == "no_context" and model.calls == []


def test_model_unavailable_degrades_and_is_not_stored():
    svc, _, _, store = build(model=FakeChatModel(fail="unavailable"))
    a = svc.answer(req())
    assert a.status == "degraded"
    assert "vacation_policy.md" in a.citations and "vacation_policy.md" in a.text
    assert store.get("r1") is None, "a retry must be able to succeed later"


def test_retry_after_degraded_succeeds():
    store = InMemoryAnswerStore()
    svc1, *_ = build(model=FakeChatModel(fail="unavailable"), store=store)
    assert svc1.answer(req()).status == "degraded"
    svc2, *_ = build(store=store)
    assert svc2.answer(req()).status == "answered"


def test_model_rejected_propagates():
    svc, _, _, store = build(model=FakeChatModel(fail="rejected"))
    with pytest.raises(ModelRejected):
        svc.answer(req())
    assert store.get("r1") is None


def test_retriever_unavailable_degrades():
    svc, model, _, store = build(retriever=InMemoryRetriever(SAMPLE_PASSAGES, fail=True))
    a = svc.answer(req())
    assert a.status == "degraded" and model.calls == [] and store.get("r1") is None


def test_race_returns_the_answer_that_was_stored_first():
    class RacyStore(InMemoryAnswerStore):
        """get() says 'not there yet', but another worker stores first, just before our put()."""

        def get(self, rid):
            return None if not getattr(self, "armed", False) else super().get(rid)

        def put(self, answer):
            if not self.data:
                self.data[answer.request_id] = answer.model_copy(update={"text": "theirs"})
            self.armed = True
            return super().put(answer)

    svc, *_ = build(store=RacyStore())
    assert svc.answer(req()).text == "theirs"


def test_k_is_passed_to_the_retriever():
    class Spy(InMemoryRetriever):
        def search(self, query, k=4):
            self.k_seen = k
            return super().search(query, k)

    spy = Spy(SAMPLE_PASSAGES)
    svc, *_ = build(retriever=spy, k=2)
    assert isinstance(svc.answer(req()), Answer)
    assert spy.k_seen == 2


def test_default_prompt_is_v1():
    svc, model, _, _ = build()
    svc.answer(req())
    assert model.calls[0][0] == ANSWER_PROMPT_V1.template
