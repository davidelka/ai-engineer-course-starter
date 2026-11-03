"""Exercises 1, 2 and 4: run the Acme answer service with tracing on, and look at the spans.

    python labs/22-observability/trace_demo.py                       # offline (mockllm), JSONL
    python labs/22-observability/trace_demo.py --console             # also print every span
    python labs/22-observability/trace_demo.py --no-content          # content capture OFF
    python labs/22-observability/trace_demo.py --pii                 # questions with PII, redacted by YOUR redact_text
    python labs/22-observability/trace_demo.py --otlp http://localhost:6006/v1/traces    # + Phoenix
    python labs/22-observability/trace_demo.py --live                # Claude Haiku 5.5 (a few cents at most)

Writes results/traces.jsonl (overwritten each run). Then:
    python labs/22-observability/trace_view.py results/traces.jsonl
"""

from __future__ import annotations

import argparse
import random

from _lab import RESULTS, MockBacked, pick, start_mock
from acme_app import CURRENT_VERSION, AnswerService, build_index
from llmkit import LLM, RetryPolicy, load_dotenv
from obskit import InstrumentedLLM, load_spans, setup_tracing, summarize

QUESTIONS = [
    "How many days a week can employees work remotely?",
    "Can I use SMS codes as my second factor?",
    "Who owns the sick leave policy, and what is their email?",
    "How many days a week can employees work remotely?",   # asked again: response cache
]
PII_QUESTIONS = [
    "I'm Dana (ID 123456782, phone 052-1234567, dana.levi@gmail.com). How many sick days do I accrue per year?",
    "Please call me back on +972 54 765 4321 about the home office allowance.",
]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use anthropic:claude-haiku-5-5 (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--console", action="store_true")
    ap.add_argument("--otlp", default=None, help="OTLP/HTTP traces URL (Phoenix: http://localhost:6006/v1/traces)")
    ap.add_argument("--otlp-header", action="append", default=[], help="KEY=VALUE, e.g. for Langfuse Authorization=Basic ...")
    ap.add_argument("--no-content", action="store_true", help="do not record prompts/completions")
    ap.add_argument("--pii", action="store_true", help="ask questions that contain personal data, and redact")
    ap.add_argument("--reference", action="store_true", help="use the reference redact_text")
    ap.add_argument("--sample", type=float, default=1.0, help="head sampling ratio (try 0.5)")
    a = ap.parse_args(argv)

    redact = False
    if a.pii:
        redact, src = pick("redact_text", a.reference)
        print(f"redaction: redact_text from {src}")
    headers = dict(h.split("=", 1) for h in a.otlp_header)
    out = RESULTS / "traces.jsonl"
    tr = setup_tracing("acme-answer", jsonl=str(out), truncate=True, console=a.console, otlp_endpoint=a.otlp,
                       otlp_headers=headers, capture_content=not a.no_content, redact=redact,
                       sample_ratio=a.sample, resource_attributes={"deployment.environment": "lab"})
    server = None
    if a.live:
        load_dotenv()
        base = LLM(a.model, retry=RetryPolicy(max_attempts=3))
    else:
        server, url = start_mock(ttft=0.1, tps=150, latency=0.1, prefill_tps=2000, seed=1)
        base = MockBacked(LLM("anthropic:mock-model", api_key="mock", base_url=url,
                              retry=RetryPolicy(max_attempts=3, rng=random.Random(1))), server)
    llm = InstrumentedLLM(base, prompt_name="rag-answer", prompt_version="v3", capture_content=not a.no_content)
    svc = AnswerService(llm=llm, replicas={"kb-1": (build_index(), CURRENT_VERSION)})
    for q in (PII_QUESTIONS if a.pii else QUESTIONS):
        res = svc.answer(q, user="u-demo")
        print(f"\n[{res['trace_id'][:12]}] {res['kind']:<6} {q}\n  -> {res['answer']}")
    tr.shutdown()
    if server:
        server.shutdown()
    spans = load_spans(out)
    s = summarize(spans)
    print(f"\n{s['traces']} traces, {s['spans']} spans -> {out}")
    print(f"cost: ${s['cost']['total_usd']:.6f}" + ("  (mock-model is priced like Haiku 5.5)" if not a.live else ""))
    print(f"next: python labs/22-observability/trace_view.py {out.relative_to(RESULTS.parents[2])}")


if __name__ == "__main__":
    main()
