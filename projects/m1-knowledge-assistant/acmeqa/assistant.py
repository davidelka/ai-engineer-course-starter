"""One question, end to end, as a stream of events (the service sends them as SSE).

    a = Assistant(Settings.from_env())
    for ev in a.events("How many vacation days carry over?", role="employee"):
        print(ev["event"], ev["data"])
    res = a.ask("כמה קריאות P1 פתוחות יש?", role="support")      # the same, collected

Events, in order:
    route    {"kind": "docs"|"data", "reason", "matched", "final": "docs"|"data", "fallback": bool}
    data     the datakit result: sql, columns, rows, provenance chips, warnings   (data path only)
    sources  the packed context: [{n, doc_id, chunk_id, title, section, effective_date}]  (docs path)
    token    {"text"}  many, as the model streams
    answer   {"text", "refused", "citations": [Citation...], "invalid_citations": [n...]}
    done     {"usage", "cost_usd", "latency_ms", "ttft_ms", "timings_ms", "trace_id", "model"}
    error    {"detail"}  if something failed after the stream started

Tracing (obskit, lesson 22, used here as infrastructure): one trace per question. The root span
is "invoke_workflow acme_assistant" with the role and the route; children: route, data_query,
retrieval (ids and scores of the candidates), pack_context, and the LLM call as a GenAI span
with tokens, cache reads and cost. Span attributes go through obskit's PII redaction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from ragkit.types import Hit

from .answer import PROMPT_VERSION, build_request, is_refusal, usage_dict
from .config import Settings
from .hooks import pick_hooks
from .ingest import IngestJob
from .retrieval import ROLES, acl_filter, build_retriever
from .router import DataAnswerer


@dataclass
class AskResult:
    question: str
    role: str
    route: dict = field(default_factory=dict)
    kind: str = "docs"                       # the path that produced the answer
    text: str = ""
    refused: bool = False
    citations: list = field(default_factory=list)
    invalid_citations: list = field(default_factory=list)
    candidates: list[Hit] = field(default_factory=list)     # deep retrieval (docs path)
    context: list[Hit] = field(default_factory=list)        # what the model read
    data: Optional[dict] = None
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    ttft_ms: Optional[float] = None
    timings_ms: dict = field(default_factory=dict)
    trace_id: str = ""
    error: Optional[str] = None

    @property
    def cited_doc_ids(self) -> list[str]:
        return list(dict.fromkeys(c["doc_id"] for c in self.citations if c.get("valid")))


def _ctx_row(h: Hit) -> dict:
    c = h.chunk
    return {"n": h.rank, "doc_id": c.doc_id, "chunk_id": c.id, "title": c.title, "section": c.section,
            "effective_date": c.effective_date, "classification": c.classification, "language": c.language,
            "start": c.start, "end": c.end}


class Assistant:
    def __init__(self, settings: Optional[Settings] = None, job: Optional[IngestJob] = None, *,
                 llm: Any = None, data_llm: Any = None, tracing: bool = True):
        self.s = settings or Settings.from_env()
        self.job = job or IngestJob(self.s)
        self.job.ensure()
        self.retriever = build_retriever(self.job, self.s)
        self.hooks = pick_hooks(self.s.reference)
        raw_llm = llm if llm is not None else self.s.make_llm()
        self.data = DataAnswerer(data_llm if data_llm is not None else self.s.make_data_llm())
        self.tracing = None
        if tracing:
            from obskit import InstrumentedLLM, setup_tracing
            self.tracing = setup_tracing("acme-knowledge-assistant", memory=True, redact=True,
                                         jsonl=str(self.s.trace_file) if self.s.trace_file else None)
            raw_llm = InstrumentedLLM(raw_llm, tracer=self.tracing.tracer, prompt_name="m1-answer",
                                      prompt_version=PROMPT_VERSION)
        self.llm = raw_llm

    # ------------------------------------------------------------ helpers
    def _span(self, name: str, **attrs):
        from contextlib import nullcontext
        if not self.tracing:
            return nullcontext(None)
        from obskit import span
        return span(name, attributes=attrs, tracer=self.tracing.tracer)

    def retrieve(self, question: str, role: str) -> tuple[list[Hit], list[Hit], dict]:
        """(candidates, packed context, timings) for the docs path."""
        t0 = time.perf_counter()
        cands = self.retriever.search(question, k=self.s.fetch_k, where=acl_filter(role))
        t1 = time.perf_counter()
        ctx = self.hooks.pack_context(cands, max_chunks=self.s.k, max_tokens=self.s.context_tokens,
                                      max_per_doc=self.s.max_per_doc)
        t2 = time.perf_counter()
        timing = {f"retrieve.{k}": round(v, 2) for k, v in (getattr(self.retriever, "last_timing", {}) or {}).items()
                  if isinstance(v, (int, float))}
        timing.update({"retrieve": round((t1 - t0) * 1000, 2), "pack": round((t2 - t1) * 1000, 2)})
        return cands, ctx, timing

    # ------------------------------------------------------------ the stream
    def events(self, question: str, role: str = "employee", _sink: Optional[dict] = None) -> Iterator[dict]:
        """_sink (optional dict) receives the candidate and context Hits, for ask() and the evaluation."""
        question = (question or "").strip()
        if role not in ROLES:
            yield {"event": "error", "data": {"detail": f"unknown role {role!r}"}}
            return
        t_start = time.perf_counter()
        timings: dict[str, float] = {}
        cost = 0.0
        usage: dict = {}
        ttft = None
        trace_id = ""
        root_cm = None
        if self.tracing:
            from obskit import agent_span
            root_cm = agent_span("acme_assistant", workflow=True, tracer=self.tracing.tracer,
                                 attributes={"acme.role": role, "acme.question_chars": len(question)})
        root = root_cm.__enter__() if root_cm else None
        try:
            if root is not None:
                trace_id = format(root.get_span_context().trace_id, "032x")
            # 1. route
            t = time.perf_counter()
            with self._span("route") as sp:
                r = self.hooks.route_question(question)
                route = r.to_dict() if hasattr(r, "to_dict") else dict(r)
                if sp is not None:
                    sp.set_attribute("acme.route", route["kind"])
            timings["route"] = round((time.perf_counter() - t) * 1000, 2)
            final, fallback = route["kind"], False
            data_res = None
            if route["kind"] == "data":
                t = time.perf_counter()
                with self._span("data_query", **{"acme.role": role}) as sp:
                    data_res = self.data.answer(question, role)
                    if sp is not None:
                        sp.set_attribute("acme.data.status", data_res.status)
                        sp.set_attribute("acme.data.sql", data_res.sql[:500])
                timings["data"] = round((time.perf_counter() - t) * 1000, 2)
                cost += data_res.cost_usd
                if data_res.fallback:
                    final, fallback = "docs", True
            if root is not None:
                root.set_attribute("acme.route", final)
            yield {"event": "route", "data": {**route, "final": final, "fallback": fallback}}

            if final == "data":
                d = data_res.to_dict()
                yield {"event": "data", "data": d}
                yield {"event": "token", "data": {"text": data_res.answer}}
                usage = {"input_tokens": data_res.input_tokens, "output_tokens": data_res.output_tokens}
                yield {"event": "answer", "data": {"text": data_res.answer, "refused": data_res.status != "ok",
                                                   "citations": [], "invalid_citations": [], "kind": "data"}}
            else:
                # 2. retrieve + pack
                from obskit import record_retrieval, retrieval_span
                if self.tracing:
                    with retrieval_span("acme-hybrid", query=question, top_k=self.s.fetch_k,
                                        tracer=self.tracing.tracer) as sp:
                        cands, ctx, tm = self.retrieve(question, role)
                        record_retrieval(sp, cands[:10])
                        sp.set_attribute("acme.context_docs", ",".join(h.chunk.doc_id for h in ctx))
                else:
                    cands, ctx, tm = self.retrieve(question, role)
                timings.update(tm)
                if _sink is not None:
                    _sink["candidates"], _sink["context"] = cands, ctx
                yield {"event": "sources", "data": {"context": [_ctx_row(h) for h in ctx], "candidates": len(cands)}}
                # 3. generate (streaming)
                req = build_request(question, ctx)
                t = time.perf_counter()
                parts: list[str] = []
                result = None
                for ev in self.llm.stream(req):
                    if ev.type == "text":
                        if ttft is None:
                            ttft = round((time.perf_counter() - t) * 1000, 1)
                        parts.append(ev.text)
                        yield {"event": "token", "data": {"text": ev.text}}
                    elif ev.type == "done":
                        result = ev.result
                timings["generate"] = round((time.perf_counter() - t) * 1000, 2)
                text = (result.text if result is not None else "".join(parts)).strip()
                usage = usage_dict(result)
                cost += float(getattr(result, "cost_usd", 0.0) or 0.0)
                refused = is_refusal(text)
                cits = [] if refused else [c.to_dict() if hasattr(c, "to_dict") else dict(c)
                                           for c in self.hooks.resolve_citations(text, ctx)]
                yield {"event": "answer", "data": {
                    "text": text, "refused": refused, "kind": "docs",
                    "citations": [c for c in cits if c.get("valid")],
                    "invalid_citations": [c["n"] for c in cits if not c.get("valid")]}}
            if root is not None:
                root.set_attribute("acme.cost_usd", round(cost, 6))
            yield {"event": "done", "data": {
                "usage": usage, "cost_usd": round(cost, 6), "ttft_ms": ttft, "timings_ms": timings,
                "latency_ms": round((time.perf_counter() - t_start) * 1000, 1), "trace_id": trace_id,
                "model": getattr(self.llm, "model", "?"), "embedder": self.s.embedder}}
        except Exception as exc:  # noqa: BLE001  (an error after the stream started is an event)
            if root is not None:
                from obskit.tracing import mark_error
                mark_error(root, exc)
            yield {"event": "error", "data": {"detail": f"{type(exc).__name__}: {exc}"}}
        finally:
            if root_cm is not None:
                root_cm.__exit__(None, None, None)
            mem = self.tracing.memory if self.tracing else None
            if mem is not None and len(mem.spans) > 5000:   # a long-running service keeps the last spans only
                with mem._lock:
                    del mem.spans[:-2000]

    # ------------------------------------------------------------ collected
    def ask(self, question: str, role: str = "employee") -> AskResult:
        res = AskResult(question=question, role=role)
        sink: dict = {}
        for ev in self.events(question, role, _sink=sink):
            e, d = ev["event"], ev["data"]
            if e == "route":
                res.route, res.kind = d, d["final"]
            elif e == "data":
                res.data = d
            elif e == "answer":
                res.text, res.refused = d["text"], d["refused"]
                res.citations, res.invalid_citations = d["citations"], d["invalid_citations"]
            elif e == "done":
                res.usage, res.cost_usd, res.latency_ms = d["usage"], d["cost_usd"], d["latency_ms"]
                res.ttft_ms, res.timings_ms, res.trace_id = d["ttft_ms"], d["timings_ms"], d["trace_id"]
            elif e == "error":
                res.error = d["detail"]
        res.candidates, res.context = sink.get("candidates", []), sink.get("context", [])
        return res

    def spans(self) -> list[dict]:
        if not self.tracing or not self.tracing.memory:
            return []
        self.tracing.flush()
        return list(self.tracing.memory.spans)

    def close(self) -> None:
        if self.tracing:
            self.tracing.shutdown()
            self.tracing = None
