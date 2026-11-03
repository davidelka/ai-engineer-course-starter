"""Tracer setup and generic span helpers for LLM systems.

    from obskit import setup_tracing, agent_span, retrieval_span, tool_span
    tr = setup_tracing("acme-answer", jsonl="results/traces.jsonl", console=True)
    with agent_span("acme_answer", workflow=True):
        with retrieval_span("acme-kb", query=q, top_k=5) as sp:
            hits = index.search(q, k=5)
            record_retrieval(sp, hits)
        ...
    tr.shutdown()

Span types (obskit.span.type) are what dashboards group by: llm, retrieval, tool, agent,
cache, guard, other. They follow gen_ai.operation.name where the spec has a value, and
obskit's own attribute where it does not (a response-cache lookup is not a GenAI
operation, but you still want it on the waterfall).
"""

from __future__ import annotations

import functools
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Optional, Union

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased, TraceIdRatioBased
from opentelemetry.trace import SpanKind, Status, StatusCode

from . import semconv as sc
from .exporters import JsonlSpanExporter, MemorySpanExporter
from .redact import RedactingSpanProcessor

CAPTURE_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT"
CAPTURE_VALUES = ("NO_CONTENT", "SPAN_ONLY", "EVENT_ONLY", "SPAN_AND_EVENT")
TRACER_NAME = "obskit"


def capture_mode(explicit: Optional[Union[bool, str]] = None) -> str:
    """The content-capture setting, as the GenAI conventions define it.

    explicit True/False wins; a string is one of CAPTURE_VALUES; otherwise the
    environment variable OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT (case-insensitive).
    Anything unrecognized means NO_CONTENT, the spec's default."""
    if explicit is True:
        return "SPAN_ONLY"
    if explicit is False:
        return "NO_CONTENT"
    value = (explicit or os.environ.get(CAPTURE_ENV, "")).strip().upper()
    return value if value in CAPTURE_VALUES else "NO_CONTENT"


def content_on_spans(explicit: Optional[Union[bool, str]] = None) -> bool:
    return capture_mode(explicit) in ("SPAN_ONLY", "SPAN_AND_EVENT")


@dataclass
class Tracing:
    provider: TracerProvider
    tracer: trace.Tracer
    capture_content: bool = False
    memory: Optional[MemorySpanExporter] = None
    jsonl: Optional[str] = None
    _processors: list = field(default_factory=list)

    def flush(self) -> None:
        self.provider.force_flush()

    def shutdown(self) -> None:
        global _ACTIVE
        self.provider.force_flush()
        self.provider.shutdown()
        if _ACTIVE is self:
            _ACTIVE = None


_ACTIVE: Optional[Tracing] = None


def setup_tracing(
    service: str = "acme-answer",
    *,
    jsonl: Optional[str] = None,
    truncate: bool = False,
    console: bool = False,
    otlp_endpoint: Optional[str] = None,
    otlp_headers: Optional[dict] = None,
    memory: bool = False,
    sample_ratio: float = 1.0,
    redact: Union[bool, Callable[[str], tuple[str, int]]] = False,
    capture_content: Optional[Union[bool, str]] = None,
    resource_attributes: Optional[dict] = None,
    set_global: bool = False,
    processors: Iterable[Any] = (),
) -> Tracing:
    """Build a TracerProvider with the exporters you ask for.

    jsonl          path of a local JSONL file (obskit.exporters format)
    console        print every span as JSON to stdout (ConsoleSpanExporter)
    otlp_endpoint  OTLP/HTTP traces URL, e.g. http://localhost:6006/v1/traces (Phoenix)
                   or http://localhost:3000/api/public/otel/v1/traces (Langfuse)
    memory         keep span dicts in tr.memory.spans (tests)
    sample_ratio   head sampling: ParentBased(TraceIdRatioBased(ratio)). The decision is
                   made when the ROOT span starts, before anyone knows if it will fail.
    redact         True = obskit.redact.redact_text on every span before export, or pass
                   your own redactor(text) -> (text, n)
    capture_content  record prompts/completions on spans (Opt-In in the spec). None reads
                   OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT.
    set_global     also make it the global OTel provider (allowed once per process)
    """
    global _ACTIVE
    attrs = {"service.name": service, **(resource_attributes or {})}
    sampler = ALWAYS_ON if sample_ratio >= 1.0 else ParentBased(TraceIdRatioBased(sample_ratio))
    provider = TracerProvider(resource=Resource.create(attrs), sampler=sampler)
    redactor = None if redact is False else (None if redact is True else redact)

    def add(proc):
        if redact is not False:
            proc = RedactingSpanProcessor(proc, redactor=redactor)
        provider.add_span_processor(proc)

    mem = None
    if memory:
        mem = MemorySpanExporter()
        add(SimpleSpanProcessor(mem))
    if jsonl:
        add(SimpleSpanProcessor(JsonlSpanExporter(jsonl, truncate=truncate)))
    if console:
        add(SimpleSpanProcessor(ConsoleSpanExporter()))
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        add(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, headers=otlp_headers or {})))
    for p in processors:
        add(p)
    if set_global:
        trace.set_tracer_provider(provider)
    tr = Tracing(provider=provider, tracer=provider.get_tracer(TRACER_NAME),
                 capture_content=content_on_spans(capture_content), memory=mem, jsonl=jsonl)
    _ACTIVE = tr
    return tr


def get_tracer() -> trace.Tracer:
    """The tracer of the last setup_tracing() call, else the global OTel tracer."""
    return _ACTIVE.tracer if _ACTIVE else trace.get_tracer(TRACER_NAME)


def capturing(explicit: Optional[bool] = None) -> bool:
    if explicit is not None:
        return explicit
    if _ACTIVE is not None:
        return _ACTIVE.capture_content
    return content_on_spans(None)


def to_json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def mark_error(span: trace.Span, exc: BaseException) -> None:
    """Recording Errors convention: status ERROR, error.type, and an exception event."""
    kind = getattr(exc, "kind", "") or type(exc).__name__
    span.set_attribute(sc.ERROR_TYPE, str(kind))
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)[:300]))


@contextmanager
def span(name: str, *, type: str = "other", kind: SpanKind = SpanKind.INTERNAL,
         attributes: Optional[dict] = None, tracer: Optional[trace.Tracer] = None,
         links: Iterable[trace.Link] = ()) -> Iterator[trace.Span]:
    """A current span with obskit.span.type set; exceptions mark it as an error and re-raise."""
    t = tracer or get_tracer()
    attrs = {sc.SPAN_TYPE: type, **(attributes or {})}
    with t.start_as_current_span(name, kind=kind, attributes=attrs, links=list(links),
                                 record_exception=False, set_status_on_exception=False) as sp:
        try:
            yield sp
        except BaseException as exc:
            mark_error(sp, exc)
            raise


def agent_span(name: str, *, workflow: bool = False, conversation_id: Optional[str] = None,
               attributes: Optional[dict] = None, tracer=None):
    """invoke_agent {name} (or invoke_workflow {name}): the root of one request."""
    op = sc.OP_WORKFLOW if workflow else sc.OP_AGENT
    attrs = {sc.OPERATION: op, (sc.WORKFLOW_NAME if workflow else sc.AGENT_NAME): name}
    if conversation_id:
        attrs[sc.CONVERSATION_ID] = conversation_id
    attrs.update(attributes or {})
    return span(f"{op} {name}", type="agent", attributes=attrs, tracer=tracer)


def retrieval_span(data_source: str, *, query: Optional[str] = None, top_k: Optional[int] = None,
                   attributes: Optional[dict] = None, capture: Optional[bool] = None, tracer=None):
    attrs = {sc.OPERATION: sc.OP_RETRIEVAL, sc.DATA_SOURCE_ID: data_source}
    if top_k is not None:
        attrs[sc.RETRIEVAL_TOP_K] = int(top_k)
    if query is not None and capturing(capture):
        attrs[sc.RETRIEVAL_QUERY] = query
    attrs.update(attributes or {})
    return span(f"{sc.OP_RETRIEVAL} {data_source}", type="retrieval", attributes=attrs, tracer=tracer)


def tool_span(name: str, *, call_id: Optional[str] = None, arguments: Any = None,
              tool_type: str = "function", attributes: Optional[dict] = None,
              capture: Optional[bool] = None, tracer=None):
    attrs = {sc.OPERATION: sc.OP_TOOL, sc.TOOL_NAME: name, sc.TOOL_TYPE: tool_type}
    if call_id:
        attrs[sc.TOOL_CALL_ID] = call_id
    if arguments is not None and capturing(capture):
        attrs[sc.TOOL_ARGUMENTS] = arguments if isinstance(arguments, str) else to_json(arguments)
    attrs.update(attributes or {})
    return span(f"{sc.OP_TOOL} {name}", type="tool", attributes=attrs, tracer=tracer)


def record_tool_result(sp: trace.Span, result: Any, capture: Optional[bool] = None) -> None:
    if capturing(capture):
        sp.set_attribute(sc.TOOL_RESULT, result if isinstance(result, str) else to_json(result))


def _hit_fields(h: Any) -> dict:
    """A ragkit Hit (h.chunk, h.score) or a plain dict -> {id, doc_id, score, ...}."""
    if isinstance(h, dict):
        return dict(h)
    c = getattr(h, "chunk", None)
    out = {"id": getattr(c, "id", None) or getattr(h, "id", None), "score": round(float(getattr(h, "score", 0.0)), 4)}
    for k in ("doc_id", "title", "effective_date", "version"):
        v = getattr(c, k, None) if c is not None else None
        if v:
            out[k] = v
    return out


def record_retrieval(sp: trace.Span, hits: Iterable[Any], *, index_version: Optional[str] = None,
                     capture: Optional[bool] = None) -> list[dict]:
    """Record what came back. The ids and scores are the forensic gold: they tell you
    whether a bad answer started at retrieval or at the model."""
    rows = [_hit_fields(h) for h in hits]
    sp.set_attribute("obskit.retrieval.count", len(rows))
    if rows:
        sp.set_attribute("obskit.retrieval.top_score", max(float(r.get("score", 0)) for r in rows))
    if index_version:
        sp.set_attribute(sc.INDEX_VERSION, index_version)
    if capturing(capture):
        sp.set_attribute(sc.RETRIEVAL_DOCUMENTS, to_json([{"id": r.get("id"), "score": r.get("score")} for r in rows]))
        sp.set_attribute(sc.RETRIEVAL_RESULTS, to_json(rows))
    return rows


class InstrumentedRetriever:
    """Wraps anything with search(query, k=, where=) (ragkit's Retriever protocol)."""

    def __init__(self, retriever: Any, data_source: str, *, index_version: Optional[str] = None,
                 capture: Optional[bool] = None, attributes: Optional[dict] = None, tracer=None):
        self.inner = retriever
        self.attributes = dict(attributes or {})
        self.data_source = data_source
        self.index_version = index_version
        self.capture = capture
        self.tracer = tracer

    def search(self, query: str, k: int = 5, where: Any = None):
        with retrieval_span(self.data_source, query=query, top_k=k, capture=self.capture,
                            attributes=self.attributes, tracer=self.tracer) as sp:
            if where:
                sp.set_attribute("obskit.retrieval.filter", to_json(where))
            hits = self.inner.search(query, k=k, where=where)
            record_retrieval(sp, hits, index_version=self.index_version, capture=self.capture)
            return hits

    def __getattr__(self, name):
        return getattr(self.inner, name)


def traced(type: str = "other", name: Optional[str] = None, **attributes):
    """Decorator: run the function inside a span of this type.

        @traced("guard", name="output_guard")
        def check(answer): ...
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            with span(name or fn.__qualname__, type=type, attributes=attributes):
                return fn(*a, **kw)
        return wrapper
    return deco
