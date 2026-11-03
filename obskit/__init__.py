"""obskit: observability for LLM systems (lesson 22 onward).

OpenTelemetry spans that follow the GenAI semantic conventions, added from the OUTSIDE
of llmkit and ragkit (wrappers and context managers, no changes to those packages):

    from obskit import setup_tracing, InstrumentedLLM, InstrumentedRetriever, agent_span, tool_span
    tr = setup_tracing("acme-answer", jsonl="results/traces.jsonl", capture_content=True)
    llm = InstrumentedLLM(LLM("anthropic:claude-haiku-5-5"), prompt_name="rag-answer", prompt_version="v3")
    with agent_span("acme_answer", workflow=True):
        ...

Modules: semconv (attribute names) · tracing (setup, span helpers, InstrumentedRetriever)
· instrument (InstrumentedLLM) · exporters (JSONL exporter, readers) · redact (PII
redaction processor) · analyze (percentiles, cost per trace) · slo (SLIs, burn rates,
multiwindow alerts) · replay (rebuild and resend a recorded LLM call) · viewer (offline
HTML waterfall). The readers, analyze, slo and viewer work on plain span dicts.
"""

from . import semconv
from .analyze import percentile, span_type, summarize
from .exporters import JsonlSpanExporter, MemorySpanExporter, by_trace, load_spans, root_of, span_to_dict, tree, write_spans
from .instrument import InstrumentedLLM
from .redact import RedactingSpanProcessor, israeli_id_valid, redact_attributes, redact_text
from .slo import ALERT_RULES, SLO, alerts_at, burn_rate, request_events
from .tracing import (InstrumentedRetriever, Tracing, agent_span, capture_mode, get_tracer, record_retrieval,
                      record_tool_result, retrieval_span, setup_tracing, span, tool_span, traced)

__all__ = [
    "semconv", "setup_tracing", "Tracing", "get_tracer", "capture_mode", "span", "agent_span", "retrieval_span",
    "tool_span", "record_retrieval", "record_tool_result", "traced", "InstrumentedLLM", "InstrumentedRetriever",
    "JsonlSpanExporter", "MemorySpanExporter", "span_to_dict", "load_spans", "write_spans", "by_trace", "root_of",
    "tree", "RedactingSpanProcessor", "redact_text", "redact_attributes", "israeli_id_valid", "percentile",
    "span_type", "summarize", "SLO", "ALERT_RULES", "burn_rate", "alerts_at", "request_events",
]
