"""Environment tests for midterm project M1 (projects/m1-knowledge-assistant): the reference
package `acmeqa`, offline. No network, no keys, no paid calls (mockllm runs in a thread)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "m1-knowledge-assistant"
sys.path[:0] = [str(ROOT), str(PROJECT)]

from acmeqa.answer import (NOT_FOUND, SYSTEM, OfflineAnswerer, Recorder, ReplayAnswerer, build_request,  # noqa: E402
                           is_refusal, prompt_key, system_tokens)
from acmeqa.assistant import Assistant  # noqa: E402
from acmeqa.citations import resolve_citations  # noqa: E402
from acmeqa.config import DOCS_DIR, Settings  # noqa: E402
from acmeqa.context import pack_context  # noqa: E402
from acmeqa.hooks import pick_hooks  # noqa: E402
from acmeqa.ingest import IngestJob  # noqa: E402
from acmeqa.retrieval import acl_filter, doc_visible, visible_docs  # noqa: E402
from acmeqa.router import DATA_ROLE, data_questions, route_question  # noqa: E402

CONFIDENTIAL_PM = "eng-pm-2026-08-api"


@pytest.fixture(scope="module")
def assistant(tmp_path_factory):
    a = Assistant(Settings(index_dir=tmp_path_factory.mktemp("m1index")))
    yield a
    a.close()


# ------------------------------------------------------------------ ingestion
def test_incremental_ingestion_and_docs_store(tmp_path):
    docs = tmp_path / "docs"
    shutil.copytree(DOCS_DIR, docs)
    s = Settings(index_dir=tmp_path / "idx", docs_dir=docs)
    job = IngestJob(s)
    r1 = job.run()
    assert len(r1.plan.added) == 55 and not r1.errors
    r2 = IngestJob(s).run()
    assert len(r2.plan.unchanged) == 55 and r2.chunks_added == 0
    # re-classify one document WITHOUT touching its text: the sidecar hash must reach the index
    md = docs / "co-glossary.md"
    md.write_text(md.read_text(encoding="utf-8").replace("classification: internal", "classification: confidential", 1),
                  encoding="utf-8")
    (docs / "hr-vacation-2024.md").unlink()
    job3 = IngestJob(s)
    r3 = job3.run()
    assert r3.plan.changed == ["co-glossary"] and r3.plan.removed == ["hr-vacation-2024"]
    assert job3.docs["co-glossary"].meta["classification"] == "confidential"
    assert "hr-vacation-2024" not in job3.docs
    assert all(c.doc_id != "hr-vacation-2024" for c in job3.all_chunks())
    # the offsets contract on the stored text: citations can be opened at the exact span
    for c in job3.all_chunks()[:200]:
        assert job3.docs[c.doc_id].text[c.start:c.end] == c.text


def test_restart_rebuilds_from_disk(assistant):
    job = IngestJob(assistant.s)
    assert job.ensure() is None                   # nothing to ingest: state on disk
    assert len(job.all_chunks()) == len(assistant.job.all_chunks()) > 300
    assert len(job.docs) == 55


# ------------------------------------------------------------------ ACL
def test_acl_filter_before_ranking(assistant):
    q = "How long was flow-api fully unavailable on August 19, 2026?"
    emp = assistant.retriever.search(q, k=30, where=acl_filter("employee"))
    eng = assistant.retriever.search(q, k=30, where=acl_filter("engineering"))
    assert CONFIDENTIAL_PM not in {h.chunk.doc_id for h in emp}
    assert eng[0].chunk.doc_id == CONFIDENTIAL_PM
    assert len(emp) == 30                          # filtered before the top-k: still a full list


def test_visible_docs_per_role(assistant):
    docs = assistant.job.docs
    assert len(visible_docs("security", docs)) == 55
    assert len(visible_docs("contractor", docs)) == 4
    assert not doc_visible("support", docs["hr-relocation"].meta)
    assert doc_visible("hr", docs["hr-relocation"].meta)
    assert len(visible_docs("nobody", docs)) == 0   # unknown role: fail closed


# ------------------------------------------------------------------ answers
def test_version_filter_and_citations(assistant):
    res = assistant.ask("How many unused vacation days can I carry over to next year, and when do they expire?", "employee")
    ctx = [h.chunk.doc_id for h in res.context]
    assert "hr-vacation-2026" in ctx and "hr-vacation-2024" not in ctx
    assert res.citations and res.citations[0]["doc_id"] == "hr-vacation-2026"
    c = res.citations[0]
    from ragkit.clean import collapse_ws
    assert collapse_ws(assistant.job.docs[c["doc_id"]].text[c["start"]:c["end"]]).startswith(c["snippet"][:40])
    assert not res.invalid_citations


def test_refusal(assistant):
    res = assistant.ask("Does Acme subsidize gym memberships?", "employee")
    assert res.refused and res.text == NOT_FOUND and res.citations == []
    assert is_refusal("Not in the documents.") and not is_refusal("Up to 5 days [1].")


def test_confidential_answer_depends_on_role(assistant):
    q = "How long was flow-api fully unavailable on August 19, 2026?"
    emp, eng = assistant.ask(q, "employee"), assistant.ask(q, "engineering")
    assert CONFIDENTIAL_PM not in emp.cited_doc_ids
    assert CONFIDENTIAL_PM in eng.cited_doc_ids


def test_pack_and_resolve_reference():
    from ragkit.types import Chunk, Hit
    hs = [Hit(Chunk(f"d{i}#0", f"d{i % 2}", f"text {i}", 0, 6), 1.0, i + 1) for i in range(6)]
    out = pack_context(hs, max_per_doc=2)
    assert [h.rank for h in out] == [1, 2, 3, 4] and {h.chunk.doc_id for h in out} == {"d0", "d1"}
    cs = resolve_citations("a [2] b [1, 9]", out)
    assert [(c.n, c.valid) for c in cs] == [(2, True), (1, True), (9, False)]


# ------------------------------------------------------------------ router and data path
def test_router_rules_and_sets():
    assert route_question("How many open P1 tickets do we have right now?").kind == "data"
    assert route_question("How many sick days do employees in Israel accrue per year?").kind == "docs"
    assert all(route_question(d["question"]).kind == "data" for d in data_questions())
    assert set(DATA_ROLE) == {"employee", "engineering", "security", "support", "finance", "hr", "contractor"}


def test_data_path_with_provenance(assistant):
    res = assistant.ask("How many open P1 tickets do we have right now?", "support")
    assert res.kind == "data" and res.data["status"] == "ok"
    assert res.data["rows"] == [[5]] and "tickets" in res.data["sql"]
    assert any("Zendesk" in p for p in res.data["provenance"])
    denied = assistant.ask("How many open P1 tickets do we have right now?", "contractor")
    assert denied.kind == "data" and denied.data["status"] == "forbidden" and denied.data["rows"] == []


def test_data_role_cannot_read_financial_column(assistant):
    d = assistant.data.answer("What is the total ARR of the Red Folder customers?", "employee")
    assert d.status != "ok" and d.rows == []           # analyst: no financial columns (guard)
    ok = assistant.data.answer("What is the total ARR of the Red Folder customers?", "finance")
    assert ok.status == "ok" and ok.rows[0][0] > 1_000_000


def test_fallback_to_documents(assistant):
    res = assistant.ask("How many duplicate runs did the March 2026 flow-scheduler incident cause, "
                        "and for how many customers?", "security")
    assert res.route["kind"] == "data" and res.route["fallback"] and res.kind == "docs"
    assert "eng-pm-2026-03-scheduler" in [h.chunk.doc_id for h in res.context]


# ------------------------------------------------------------------ streaming, prompt caching
def test_event_order(assistant):
    evs = [e["event"] for e in assistant.events("What is Blue Room?", "employee")]
    assert evs[0] == "route" and evs[1] == "sources" and "token" in evs and evs[-2:] == ["answer", "done"]


def test_system_prompt_is_cacheable():
    assert system_tokens() >= 700                       # above Haiku 5.5's 512-token minimum, with margin
    from ragkit.types import Chunk, Hit
    req = build_request("q", [Hit(Chunk("a#0", "a", "text", 0, 4, meta={"title": "A"}), 1.0, 1)])
    assert req.system[0].cache == "5m" and req.system[0].text == SYSTEM


def test_prompt_cache_hit_against_mockllm(assistant):
    from llmkit import LLM
    from mockllm import MockConfig, start_in_thread
    server, url = start_in_thread(MockConfig(ttft=0, tps=0, seed=1))
    try:
        llm = LLM("anthropic:claude-haiku-5-5", api_key="test", base_url=url)
        a = Assistant(assistant.s, job=assistant.job, llm=llm, tracing=False)
        first = a.ask("What is Blue Room?", "employee")
        second = a.ask("When is billing-service frozen for deploys?", "employee")
        assert first.usage["cache_creation_tokens"] >= 512 and first.usage["cached_input_tokens"] == 0
        assert second.usage["cached_input_tokens"] >= 512
        assert second.cost_usd < first.cost_usd
    finally:
        server.shutdown()


def test_record_and_replay(tmp_path, assistant):
    from ragkit.types import Chunk, Hit
    ctx = [Hit(Chunk("hr-sick-leave#0", "hr-sick-leave", "Employees in Israel accrue 1.5 sick days per month.", 0, 50,
                     meta={"title": "Sick Leave"}), 1.0, 1)]
    req = build_request("How many sick days per month in Israel?", ctx)
    rec = Recorder(OfflineAnswerer(), tmp_path / "rec.jsonl")
    live = rec.complete(req)
    rp = ReplayAnswerer(tmp_path / "rec.jsonl")
    assert rp.complete(req).text == live.text and rp.misses == 0
    other = build_request("Something else?", ctx)
    assert prompt_key(other) != prompt_key(req)
    assert rp.complete(other).text.startswith("[not recorded]") and rp.misses == 1


# ------------------------------------------------------------------ service
def test_service(assistant):
    from fastapi.testclient import TestClient

    from acmeqa.service import create_app
    c = TestClient(create_app(assistant))
    assert c.get("/healthz").json() == {"status": "ok"}
    assert c.get("/readyz").json()["documents"] == 55
    r = c.post("/ask", json={"question": "What is Blue Room?", "role": "employee"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = [b.split("\n")[0].removeprefix("event: ") for b in r.text.strip().split("\n\n")]
    assert events[0] == "route" and events[-1] == "done" and "answer" in events
    j = c.post("/ask", json={"question": "How many open P1 tickets do we have right now?", "role": "support",
                             "stream": False}).json()
    assert j["kind"] == "data" and j["data"]["rows"] == [[5]]
    assert c.get(f"/docs/{CONFIDENTIAL_PM}?role=employee").status_code == 404     # hidden = not found
    assert c.get(f"/docs/{CONFIDENTIAL_PM}?role=engineering").status_code == 200
    d = c.get("/docs/hr-vacation-2024?role=employee&start=0&end=20").json()
    assert d["highlight"] == {"start": 0, "end": 20} and "hr-vacation-2026" in d["superseded_by"]
    assert c.post("/ask", json={"question": "x", "role": "ceo"}).status_code == 422
    assert "Acme Knowledge Assistant" in c.get("/").text


# ------------------------------------------------------------------ tracing, hooks
def test_tracing_and_redaction(assistant):
    assistant.tracing.memory.spans.clear()
    assistant.ask("My email is dana.levi@acme.example: what is Blue Room?", "employee")
    spans = assistant.spans()
    names = {s["name"] for s in spans}
    assert "invoke_workflow acme_assistant" in names and "retrieval acme-hybrid" in names
    assert any(n.startswith("chat ") for n in names)
    assert "dana.levi@acme.example" not in json.dumps(spans, ensure_ascii=False)


def test_hooks_fall_back_to_reference():
    h = pick_hooks(reference=False)
    assert h.route_question("How many tickets are still open?").kind == "data"   # mine.py TODO -> reference
    assert pick_hooks(reference=True).using["pack_context"] == "reference"
