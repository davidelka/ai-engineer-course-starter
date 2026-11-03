"""obskit (lesson 22): OpenTelemetry spans around llmkit/ragkit, exporters, redaction,
aggregation, SLOs, replay and the offline viewer. Offline and free (mockllm)."""

import hashlib
import json
import random
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk", reason="pip install -r labs/22-observability/requirements.txt")

from llmkit import LLM, ChatRequest, LLMError, Message, RetryPolicy  # noqa: E402
from mockllm import MockConfig, start_in_thread  # noqa: E402
from obskit import (InstrumentedLLM, InstrumentedRetriever, agent_span, by_trace, capture_mode,  # noqa: E402
                    load_spans, redact_text, root_of, setup_tracing, summarize, tool_span, tree)
from obskit import semconv as sc  # noqa: E402
from obskit.replay import replay, request_from_span  # noqa: E402
from obskit.slo import SLO, burn_rate, request_events  # noqa: E402
from obskit.viewer import render_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "22-observability"


@pytest.fixture(scope="module")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.reset()
    return server, url


def llm_for(url, model="mock-model", **kw):
    return LLM(f"anthropic:{model}", api_key="test", base_url=url,
               retry=RetryPolicy(sleep=lambda s: None, rng=random.Random(0), **kw))


def test_chat_span_follows_genai_conventions(mock):
    _, url = mock
    tr = setup_tracing("t", memory=True, capture_content=False)
    llm = InstrumentedLLM(llm_for(url), prompt_name="p", prompt_version="v9")
    with agent_span("acme_answer", workflow=True):
        res = llm.complete("Name two colors.", system="Be brief.")
    tr.shutdown()
    chat, root = sorted(tr.memory.spans, key=lambda s: s["parent_id"] is None)
    a = chat["attributes"]
    assert chat["name"] == "chat mock-model" and chat["kind"] == "CLIENT" and chat["parent_id"] == root["span_id"]
    assert a[sc.OPERATION] == "chat" and a[sc.PROVIDER] == "anthropic" and a[sc.REQUEST_MODEL] == "mock-model"
    assert a[sc.USAGE_INPUT] == res.usage.input_tokens and a[sc.USAGE_OUTPUT] == res.usage.output_tokens
    assert a[sc.FINISH_REASONS] == ["stop"] and a[sc.PROMPT_VERSION] == "v9"
    assert a[sc.COST_USD] == pytest.approx(res.cost_usd) and a[sc.ATTEMPTS] == 1
    assert sc.INPUT_MESSAGES not in a and sc.SYSTEM_INSTRUCTIONS not in a     # content is opt-in
    assert root["name"] == "invoke_workflow acme_answer" and root["attributes"][sc.SPAN_TYPE] == "agent"


def test_content_capture_and_env_var(mock, monkeypatch):
    _, url = mock
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT", "span_only")
    assert capture_mode() == "SPAN_ONLY"
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT", "bogus")
    assert capture_mode() == "NO_CONTENT"
    tr = setup_tracing("t", memory=True, capture_content=True)
    InstrumentedLLM(llm_for(url)).complete("hello", system="sys")
    tr.shutdown()
    a = tr.memory.spans[0]["attributes"]
    assert json.loads(a[sc.INPUT_MESSAGES]) == [{"role": "user", "parts": [{"type": "text", "content": "hello"}]}]
    assert json.loads(a[sc.SYSTEM_INSTRUCTIONS])[0]["content"] == "sys"
    assert json.loads(a[sc.OUTPUT_MESSAGES])[0]["finish_reason"] == "stop"


def test_retries_become_events_and_failures_errors(mock):
    server, url = mock
    tr = setup_tracing("t", memory=True)
    llm = InstrumentedLLM(llm_for(url))
    server.state.cfg = MockConfig(ttft=0, tps=0, fail_first=2, status=529)
    llm.complete("x")
    server.state.reset()
    server.state.cfg = MockConfig(ttft=0, tps=0, fail_first=10, status=429)
    with pytest.raises(LLMError):
        llm.complete("y")
    tr.shutdown()
    ok, bad = tr.memory.spans
    assert [e["name"] for e in ok["events"]] == ["retry", "retry"] and ok["attributes"][sc.ATTEMPTS] == 3
    assert ok["events"][0]["attributes"][sc.ERROR_TYPE] == "overloaded_error"
    assert bad["status"] == "ERROR" and bad["attributes"][sc.ERROR_TYPE] == "rate_limit_error"
    assert bad["attributes"][sc.ATTEMPTS] == 4 and bad["events"][-1]["name"] == "exception"
    assert llm.inner.on_retry is None, "the retry hook must be restored"


def test_stream_records_ttft_and_cache_usage(mock):
    server, url = mock
    server.state.cfg = MockConfig(ttft=0.01, tps=0, cache_min_tokens=10)
    from llmkit import Block
    tr = setup_tracing("t", memory=True)
    llm = InstrumentedLLM(llm_for(url))
    req = ChatRequest(messages=[Message("user", "hi")], system=[Block("rules " * 200, cache="5m")])
    list(llm.stream(req))
    llm.complete(req, stream=True)
    tr.shutdown()
    first, second = tr.memory.spans
    assert first["attributes"][sc.REQUEST_STREAM] is True and sc.TIME_TO_FIRST_CHUNK in first["attributes"]
    assert first["attributes"].get(sc.USAGE_CACHE_WRITE, 0) > 0
    assert second["attributes"].get(sc.USAGE_CACHE_READ, 0) > 0


def test_retrieval_and_tool_spans_with_ragkit():
    from ragkit import BM25Index, Chunk
    idx = BM25Index()
    idx.add([Chunk(id="d1#0", doc_id="d1", text="vacation days carry over", start=0, end=24,
                   meta={"effective_date": "2026-01-01"}),
             Chunk(id="d2#0", doc_id="d2", text="laptops are replaced", start=0, end=20)])
    tr = setup_tracing("t", memory=True, capture_content=True)
    with agent_span("a"):
        hits = InstrumentedRetriever(idx, "kb", index_version="v1").search("vacation carry", k=2)
        with tool_span("lookup", call_id="c1", arguments={"name": "Dana"}):
            pass
    tr.shutdown()
    spans = {s["name"]: s for s in tr.memory.spans}
    r = spans["retrieval kb"]["attributes"]
    assert r[sc.OPERATION] == "retrieval" and r[sc.RETRIEVAL_TOP_K] == 2 and r[sc.INDEX_VERSION] == "v1"
    docs = json.loads(r[sc.RETRIEVAL_DOCUMENTS])
    assert docs[0]["id"] == hits[0].chunk.id and "score" in docs[0]
    assert json.loads(r[sc.RETRIEVAL_RESULTS])[0]["effective_date"] == "2026-01-01"
    t = spans["execute_tool lookup"]["attributes"]
    assert t[sc.TOOL_NAME] == "lookup" and t[sc.TOOL_CALL_ID] == "c1" and json.loads(t[sc.TOOL_ARGUMENTS]) == {"name": "Dana"}


def test_jsonl_export_redaction_and_sampling(tmp_path, mock):
    _, url = mock
    path = tmp_path / "t.jsonl"
    tr = setup_tracing("t", jsonl=str(path), capture_content=True, redact=True)
    InstrumentedLLM(llm_for(url)).complete("my phone is 052-1234567, mail a@b.co")
    tr.shutdown()
    s = load_spans(path)[0]
    assert "052-1234567" not in json.dumps(s) and "[PHONE]" in s["attributes"][sc.INPUT_MESSAGES]
    assert s["attributes"]["obskit.redacted"] >= 2 and s["service"] == "t"
    tr = setup_tracing("t", memory=True, sample_ratio=0.0)
    with agent_span("x"):
        pass
    tr.shutdown()
    assert tr.memory.spans == []
    assert redact_text("ID 123456782")[0] == "ID [IL_ID]"


def test_replay_roundtrip(mock):
    server, url = mock
    server.state.cfg = MockConfig(ttft=0, tps=0, reply="fixed answer")
    tr = setup_tracing("t", memory=True, capture_content=True)
    llm = InstrumentedLLM(llm_for(url))
    llm.complete(ChatRequest(messages=[Message("user", "q?")], system="sys", max_tokens=77))
    tr.flush()
    orig = tr.memory.spans[0]
    req = request_from_span(orig)
    assert req.system == "sys" and req.max_tokens == 77 and req.messages[0].text == "q?"
    out = replay(orig, llm)
    tr.shutdown()
    assert out["same"] and out["replayed"] == "fixed answer"
    rep = [s for s in tr.memory.spans if s["name"] == "replay"][0]
    assert rep["links"][0]["trace_id"] == orig["trace_id"] and rep["attributes"][sc.REPLAY_OF] == orig["trace_id"]
    with pytest.raises(ValueError):
        request_from_span({"span_id": "x", "attributes": {}})


def test_forensic_fixture_is_consistent():
    spans = load_spans(LAB / "fixtures" / "forensic.jsonl")
    traces = by_trace(spans)
    assert len(traces) == 12 and all(root_of(ss)["name"] == "invoke_workflow acme_answer" for ss in traces.values())
    key = json.loads((LAB / "fixtures" / "forensic_key.json").read_text())
    fb = [json.loads(x) for x in (LAB / "fixtures" / "feedback.jsonl").read_text().splitlines() if x.strip()]
    negative = {f["trace_id"] for f in fb if f["rating"] < 0}
    assert negative == set(key["flagged"]) and len(key["hashes"]) == 4
    causes = ["stale_index", "rate_limit_fallback", "prompt_cache_miss", "llm_timeout", "retrieval_miss",
              "model_hallucination", "tool_error", "max_tokens"]
    for tid in key["flagged"]:   # exactly one cause matches each flagged trace
        assert sum(hashlib.sha256(f"{tid}:{c}".encode()).hexdigest() in key["hashes"] for c in causes) == 1
    s = summarize(spans)
    assert s["by_type"]["llm"]["errors"] == 2 and s["by_type"]["tool"]["count"] == 1
    assert all(d >= 0 for d, _ in tree(traces[key["flagged"][0]]))


def test_slo_and_viewer_smoke():
    spans = load_spans(LAB / "fixtures" / "forensic.jsonl")
    events = request_events(spans)
    assert len(events) == 12
    assert burn_rate(events, SLO("g", "grounded", 0.9), 0, float("inf")) > 0
    html = render_html(spans, title="x", feedback={})
    assert html.startswith("<!doctype html>") and "</script>" in html and "<table" not in html
