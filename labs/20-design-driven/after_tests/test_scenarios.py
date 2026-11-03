"""The scenarios of legacy/tests/test_tangled.py, after the refactor: the same
questions, with fakes injected through the constructor. No server, no
monkeypatch, no files, no sleeping. Plus the cases the tangled version could
not test at all (marked NEW).

measure.py runs this file with BRAIN_IMPL=mine (your AnswerService) or ref.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(LAB), str(LAB.parents[1])]

from designkit.adapters import KeywordRetriever  # noqa: E402
from designkit.fakes import FakeChatModel, FixedClock, InMemoryAnswerStore, InMemoryRetriever  # noqa: E402
from designkit.types import AnswerRequest, ModelRejected  # noqa: E402

if os.environ.get("BRAIN_IMPL", "mine") == "ref":
    from designkit.service import AnswerService
else:
    from mine import AnswerService

REPLY = "Full-time employees get 14 paid vacation days in their first year [vacation_policy.md]."
PASSAGES = KeywordRetriever.from_files().passages  # the real Acme documents, loaded once


def svc(model=None, retriever=None, store=None):
    model = model or FakeChatModel(REPLY)
    retriever = retriever or InMemoryRetriever(PASSAGES)
    store = store if store is not None else InMemoryAnswerStore()
    return AnswerService(model, retriever, store, FixedClock()), model, store


def ask(s, q, email="dana@acme.example", rid="r1"):
    return s.answer(AnswerRequest(request_id=rid, user_email=email, question=q))


def test_answers_with_citations():
    s, model, _ = svc()
    a = ask(s, "How many vacation days do I get in my first year?")
    assert a.status == "answered" and a.citations == ["vacation_policy.md"]
    assert len(model.calls) == 1


def test_refuses_salary_questions_without_calling_the_model():
    s, model, _ = svc()
    assert ask(s, "What is Moshe's salary?").status == "refused"
    assert model.calls == []


def test_refuses_non_employees():
    s, _, _ = svc()
    assert ask(s, "How many vacation days?", email="someone@gmail.com").status == "refused"


def test_no_context():
    s, model, _ = svc()
    assert ask(s, "Who won the football match yesterday?").status == "no_context"
    assert model.calls == []


def test_same_request_id_is_answered_once():
    s, model, _ = svc()
    ask(s, "How many vacation days do I get in my first year?")
    assert ask(s, "How many vacation days do I get in my first year?").status == "answered"
    assert len(model.calls) == 1


def test_model_down_degrades():
    s, _, _ = svc(model=FakeChatModel(fail="unavailable"))
    a = ask(s, "Can I work remotely from abroad?")
    assert a.status == "degraded" and "remote_work_policy.md" in a.citations


# ---------------------------------------------------------------- NEW: impossible before
def test_new_created_at_comes_from_the_clock():
    s, _, _ = svc()
    assert ask(s, "How many vacation days do I get in my first year?").created_at == \
        datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


def test_new_bad_key_is_not_hidden_as_degraded():
    s, _, store = svc(model=FakeChatModel(fail="rejected"))
    with pytest.raises(ModelRejected):
        ask(s, "How many vacation days do I get in my first year?")
    assert store.get("r1") is None


def test_new_degraded_is_not_stored_so_a_retry_can_succeed():
    store = InMemoryAnswerStore()
    s1, _, _ = svc(model=FakeChatModel(fail="unavailable"), store=store)
    assert ask(s1, "Can I work remotely from abroad?").status == "degraded"
    s2, _, _ = svc(store=store)
    assert ask(s2, "Can I work remotely from abroad?").status == "answered"


def test_new_search_backend_down():
    s, model, _ = svc(retriever=InMemoryRetriever(PASSAGES, fail=True))
    assert ask(s, "How many vacation days?").status == "degraded" and model.calls == []


def test_new_invented_citation_is_dropped():
    s, _, _ = svc(model=FakeChatModel("14 days [vacation_policy.md] [secret_salaries.xlsx]"))
    assert ask(s, "How many vacation days do I get in my first year?").citations == ["vacation_policy.md"]


def test_new_two_workers_same_request_id():
    class RacyStore(InMemoryAnswerStore):
        """Another worker stores the same request_id between our get() and our put()."""

        def put(self, answer):
            if not self.data:
                self.data[answer.request_id] = answer.model_copy(update={"text": "the other worker's answer"})
            return super().put(answer)

    s, _, _ = svc(store=RacyStore())
    assert ask(s, "How many vacation days do I get in my first year?").text == "the other worker's answer"
