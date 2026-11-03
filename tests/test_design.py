"""designkit (lesson 20): reference ports, fakes, adapters, service, registry, sequence checker.
Offline: real adapters talk to mockllm or to temp files."""

import random
import sys
from pathlib import Path

import pytest

from designkit.adapters import ACME_FILES, JsonlAnswerStore, KeywordRetriever, LlmkitChatModel, load_passages
from designkit.contract import AnswerStoreContract, ChatModelContract, RetrieverContract
from designkit.fakes import SAMPLE_PASSAGES, FakeChatModel, FixedClock, InMemoryAnswerStore, InMemoryRetriever
from designkit.ports import AnswerStore, ChatModel, Clock, Retriever
from designkit.registry import IncompatibleVersion, PromptRegistry, check_compatible
from designkit.review_key import FINE, FLAWS
from designkit.sequence import check, mermaid_live_url, parse
from designkit.service import AnswerService
from designkit.sqlite_store import SqliteAnswerStore
from designkit.types import AnswerRequest, ModelRejected, ModelUnavailable
from llmkit import LLM, RetryPolicy
from mockllm import MockConfig, start_in_thread

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "20-design-driven"
_SRV = {}


def server():
    if not _SRV:
        _SRV["s"] = start_in_thread(MockConfig())
    return _SRV["s"]


def llmkit_model(cfg: MockConfig) -> LlmkitChatModel:
    srv, url = server()
    srv.state.cfg = cfg
    srv.state.reset()
    return LlmkitChatModel(LLM("anthropic:mock-model", api_key="t", base_url=url,
                               retry=RetryPolicy(max_attempts=2, sleep=lambda s: None, rng=random.Random(0))))


# ---------------------------------------------------------------- reference contracts x adapters
class TestFakeModelContract(ChatModelContract):
    def make_model(self, mode):
        return FakeChatModel(fail=None if mode == "ok" else mode)


class TestLlmkitModelContract(ChatModelContract):
    def make_model(self, mode):
        return llmkit_model({"ok": MockConfig(ttft=0, tps=0, reply="Fourteen [vacation_policy.md]."),
                             "unavailable": MockConfig(ttft=0, tps=0, fail_first=10_000, status=529),
                             "rejected": MockConfig(ttft=0, tps=0, fail_first=10_000, status=401)}[mode])


class TestInMemoryRetrieverContract(RetrieverContract):
    def make_retriever(self, passages):
        return InMemoryRetriever(passages)


class TestKeywordRetrieverContract(RetrieverContract):
    def make_retriever(self, passages):
        return KeywordRetriever.from_passages(passages)


class TestInMemoryStoreContract(AnswerStoreContract):
    def make_store(self):
        return InMemoryAnswerStore()


class TestJsonlStoreContract(AnswerStoreContract):
    def make_store(self):
        import tempfile
        return JsonlAnswerStore(Path(tempfile.mkdtemp()) / "a.jsonl")


class TestSqliteStoreContract(AnswerStoreContract):
    def make_store(self):
        return SqliteAnswerStore(":memory:")


def test_adapters_satisfy_ports_structurally():
    assert isinstance(FakeChatModel(), ChatModel) and isinstance(llmkit_model(MockConfig()), ChatModel)
    assert isinstance(KeywordRetriever([]), Retriever) and isinstance(InMemoryRetriever([]), Retriever)
    assert isinstance(SqliteAnswerStore(), AnswerStore) and isinstance(InMemoryAnswerStore(), AnswerStore)
    assert isinstance(FixedClock(), Clock)


def test_llmkit_adapter_translates_refusal_and_keeps_the_cause():
    m = llmkit_model(MockConfig(ttft=0, tps=0, fail_first=10_000, status=529))
    with pytest.raises(ModelUnavailable) as e:
        m.complete("s", "p")
    assert e.value.__cause__ is not None and "529" in str(e.value)
    assert ModelUnavailable.retryable and not ModelRejected.retryable


def test_stores_persist(tmp_path):
    from designkit.contract import _answer
    for make in (lambda: JsonlAnswerStore(tmp_path / "a.jsonl"), lambda: SqliteAnswerStore(tmp_path / "a.db")):
        make().put(_answer("r1", "kept"))
        s = make()
        assert s.get("r1").text == "kept" and s.put(_answer("r1", "other")) is False


def test_load_passages_from_acme_files():
    ids = [p.doc_id for p in load_passages(ACME_FILES)]
    assert ids == ["vacation_policy.md", "remote_work_policy.md", "saas_access_policy.md#auto_approve",
                   "saas_access_policy.md#needs_manager", "saas_access_policy.md#needs_security"]


# ---------------------------------------------------------------- service
def test_service_end_to_end_with_real_retriever_and_llmkit_over_mock():
    m = llmkit_model(MockConfig(ttft=0, tps=0, reply="14 days [vacation_policy.md] [nope.md]"))
    svc = AnswerService(m, KeywordRetriever.from_files(), InMemoryAnswerStore(), FixedClock())
    a = svc.answer(AnswerRequest(request_id="x", user_email="dana@acme.example",
                                 question="How many vacation days do I get in my first year?"))
    assert a.status == "answered" and a.citations == ["vacation_policy.md"] and a.model == "anthropic:mock-model"
    assert a.cost_usd > 0


def test_service_paths():
    def run(model=None, q="How many vacation days do I get in my first year?", email="dana@acme.example", store=None):
        svc = AnswerService(model or FakeChatModel(), InMemoryRetriever(SAMPLE_PASSAGES),
                            store if store is not None else InMemoryAnswerStore(), FixedClock())
        return svc.answer(AnswerRequest(request_id="r", user_email=email, question=q))
    assert run().status == "answered"
    assert run(q="What is my manager's salary?").status == "refused"
    assert run(email="x@gmail.com").status == "refused"
    assert run(q="football results").status == "no_context"
    store = InMemoryAnswerStore()
    assert run(FakeChatModel(fail="unavailable"), store=store).status == "degraded" and store.get("r") is None
    with pytest.raises(ModelRejected):
        run(FakeChatModel(fail="rejected"))


# ---------------------------------------------------------------- registry
def test_registry_with_the_lab_catalog():
    sys.path.insert(0, str(LAB))
    import prompts_catalog as pc
    r = PromptRegistry()
    accepted = []
    for p in pc.HISTORY:
        try:
            r.register(p)
            accepted.append(p.version)
        except IncompatibleVersion:
            pass
    assert accepted == ["1.0.0", "1.0.1", "1.1.0", "2.0.0"]
    assert r.get("answer", "1").version == "1.1.0" and r.get("answer").version == "2.0.0"
    assert check_compatible(pc.OutV1.model_json_schema(), pc.OutNullableText.model_json_schema())


# ---------------------------------------------------------------- sequence checker
def test_reference_sequence_passes_every_rule():
    text = (ROOT / "designkit" / "reference" / "access_request_sequence.mmd").read_text()
    assert all(ok for _, ok, _ in check(text)), [r for r in check(text) if not r[1]]
    assert mermaid_live_url(text).startswith("https://mermaid.live/edit#pako:")


def test_starter_sequence_parses_but_fails_the_design_rules():
    text = (LAB / "designs" / "access_request_sequence.mmd").read_text()
    res = dict((r, ok) for r, ok, _ in check(text))
    assert res["parses"] and not res["three routes in an alt"]
    assert len(parse(text).participants) == 8


def test_checker_catches_a_grant_without_approval():
    text = (ROOT / "designkit" / "reference" / "access_request_sequence.mmd").read_text()
    bad = text.replace("    API-->>Emp: 202 status + link", "    Svc->>IdP: grant anyway\n    API-->>Emp: 202")
    bad = bad.replace("Appr-->>Svc: approve / reject", "Svc->>Svc: wait")
    res = dict((r, ok) for r, ok, _ in check(bad))
    assert not res["no grant without a decision"]


# ---------------------------------------------------------------- design review key
def test_review_key_matches_the_doc():
    doc = (LAB / "designs" / "answer_service_v2.md").read_text()
    sections = {f"D{i}" for i in range(1, 13)}
    assert all(f"**[{s}]" in doc for s in sections)
    assert set(FLAWS) | set(FINE) == sections and not set(FLAWS) & set(FINE)
    checklist = (LAB / "designs" / "review_checklist.md").read_text()
    assert all(f"**{c}." in checklist for f in FLAWS.values() for c in f["checklist"])


# ---------------------------------------------------------------- legacy smoke test (fast path only)
def test_tangled_answers_against_mock(monkeypatch, tmp_path):
    import llmkit.client
    sys.path.insert(0, str(LAB / "legacy"))
    import tangled
    srv, url = server()
    srv.state.cfg = MockConfig(ttft=0, tps=0, reply="14 days [vacation_policy.md].")
    monkeypatch.setenv("BRAIN_MODEL", "mock:mock-model")
    monkeypatch.setattr(llmkit.client, "MOCK_URL", url)
    monkeypatch.setattr(tangled, "CACHE_PATH", tmp_path / "c.json")
    monkeypatch.setattr(tangled, "LOG_PATH", tmp_path / "b.log")
    r = tangled.answer_question("How many vacation days do I get in my first year?", "dana@acme.example", "t1")
    assert r["status"] == "answered" and r["citations"] == ["vacation_policy.md"]
