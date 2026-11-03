"""Reference contract tests (exercise 4): one reusable suite per port.

How to use: subclass, give the class a name that starts with Test, and
implement the factory hook. pytest collects the subclass and runs every test_*
method against your adapter:

    class TestSqliteStore(AnswerStoreContract):
        def make_store(self):
            return SqliteAnswerStore(":memory:")

The base classes do not start with "Test", so pytest does not collect them on
their own. Test methods take only `self` (no fixtures), so the same suite can
also be called directly from code, which is how tests/test_ex4_contract.py
checks that a contract really catches broken adapters.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .fakes import SAMPLE_PASSAGES
from .types import Answer, BrainError, Completion, ModelRejected, ModelUnavailable, Passage

SYSTEM = "You are a test. Reply with one short sentence."
PROMPT = '<documents>\n<document id="vacation_policy.md" title="Vacation">14 days.</document>\n</documents>\n\n<question>How many vacation days?</question>'


class ChatModelContract:
    def make_model(self, mode: str):
        """mode: "ok" (works), "unavailable" (backend overloaded/down), "rejected" (bad request/key)."""
        raise NotImplementedError

    def test_returns_completion_with_text(self):
        c = self.make_model("ok").complete(SYSTEM, PROMPT, max_tokens=64)
        assert isinstance(c, Completion)
        assert c.text.strip()

    def test_reports_model_name(self):
        m = self.make_model("ok")
        c = m.complete(SYSTEM, PROMPT, max_tokens=64)
        assert isinstance(m.name, str) and ":" in m.name
        assert c.model == m.name

    def test_usage_is_not_negative(self):
        c = self.make_model("ok").complete(SYSTEM, PROMPT, max_tokens=64)
        assert c.input_tokens >= 0 and c.output_tokens >= 0 and c.cost_usd >= 0

    def test_transient_failure_is_model_unavailable(self):
        m = self.make_model("unavailable")
        try:
            m.complete(SYSTEM, PROMPT, max_tokens=64)
        except ModelUnavailable:
            return
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"expected ModelUnavailable, got {type(exc).__name__}: {exc}") from exc
        raise AssertionError("expected ModelUnavailable, nothing was raised")

    def test_permanent_failure_is_model_rejected(self):
        m = self.make_model("rejected")
        try:
            m.complete(SYSTEM, PROMPT, max_tokens=64)
        except ModelRejected:
            return
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"expected ModelRejected, got {type(exc).__name__}: {exc}") from exc
        raise AssertionError("expected ModelRejected, nothing was raised")

    def test_errors_are_brain_errors(self):
        for mode in ("unavailable", "rejected"):
            try:
                self.make_model(mode).complete(SYSTEM, PROMPT, max_tokens=64)
            except BrainError:
                continue
            except Exception as exc:  # noqa: BLE001
                raise AssertionError(f"{mode}: a {type(exc).__name__} escaped the port") from exc


class RetrieverContract:
    def make_retriever(self, passages: list[Passage]):
        """Return an adapter that searches exactly these passages."""
        raise NotImplementedError

    def test_finds_a_relevant_passage(self):
        r = self.make_retriever(SAMPLE_PASSAGES)
        hits = r.search("vacation days first year", k=3)
        assert hits and hits[0].doc_id == "vacation_policy.md"

    def test_at_most_k_sorted_by_score(self):
        r = self.make_retriever(SAMPLE_PASSAGES)
        hits = r.search("employees days policy office", k=2)
        assert len(hits) <= 2
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)

    def test_unique_doc_ids(self):
        r = self.make_retriever(SAMPLE_PASSAGES + SAMPLE_PASSAGES[:1])
        ids = [h.doc_id for h in r.search("vacation days employees", k=4)]
        assert len(ids) == len(set(ids))

    def test_no_match_and_empty_query_return_empty_list(self):
        r = self.make_retriever(SAMPLE_PASSAGES)
        assert r.search("zebra quantum xylophone", k=3) == []
        assert r.search("", k=3) == []

    def test_deterministic(self):
        r = self.make_retriever(SAMPLE_PASSAGES)
        assert r.search("remote work office days", k=3) == r.search("remote work office days", k=3)


def _answer(rid: str, text: str = "x") -> Answer:
    return Answer(request_id=rid, status="answered", text=text, citations=["vacation_policy.md"],
                  prompt_version="answer@1.0.0", model="fake:chat",
                  created_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc))


class AnswerStoreContract:
    def make_store(self):
        """Return a fresh, empty store."""
        raise NotImplementedError

    def test_unknown_id_returns_none(self):
        assert self.make_store().get("nope") is None

    def test_put_then_get_round_trips(self):
        s = self.make_store()
        a = _answer("r1")
        assert s.put(a) is True
        assert s.get("r1") == a

    def test_first_write_wins(self):
        s = self.make_store()
        s.put(_answer("r1", "first"))
        assert s.put(_answer("r1", "second")) is False
        assert s.get("r1").text == "first"

    def test_ids_are_independent(self):
        s = self.make_store()
        s.put(_answer("r1", "one"))
        s.put(_answer("r2", "two"))
        assert s.get("r1").text == "one" and s.get("r2").text == "two"
