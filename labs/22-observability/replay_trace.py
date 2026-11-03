"""Exercise 7: replay the LLM call of a recorded trace, with exactly the same inputs.

    python labs/22-observability/replay_trace.py <trace_id prefix>
    python labs/22-observability/replay_trace.py <prefix> --fresh-retrieval   # same question, today's index kb-1
    python labs/22-observability/replay_trace.py <prefix> --live              # the same request to Claude Haiku 5.5

Reads labs/22-observability/fixtures/forensic.jsonl by default (--file to change).
The request is rebuilt from the span's gen_ai.system_instructions, gen_ai.input.messages
and gen_ai.request.max_tokens, then sent through llmkit to a HEALTHY mockllm (no faults),
whose replies come from the same deterministic answerer that produced the recording.
The replay is itself traced (results/replays.jsonl), with a span link to the original.
"""

from __future__ import annotations

import argparse
import random
import re

from _lab import FIXTURES, RESULTS, MockBacked, start_mock
from llmkit import LLM, RetryPolicy, load_dotenv
from obskit import InstrumentedLLM, by_trace, load_spans, setup_tracing
from obskit.replay import llm_spans, recorded_output, replay, request_from_span

SRC_RE = re.compile(r'<source id="(\d+)"[^>]*doc="([^"]+)"[^>]*?(?:effective_date="([^"]*)")?[^>]*>')


def describe(req) -> None:
    user = req.messages[-1].text
    q = re.search(r"<question>(.*?)</question>", user, re.S)
    print(f"  question : {q.group(1) if q else user[:80]}")
    print(f"  system   : {len(req.system_text)} chars, max_tokens={req.max_tokens}")
    srcs = SRC_RE.findall(user)
    if srcs:
        print("  sources  : " + ", ".join(f"[{n}] {d}" + (f" ({e})" if e else "") for n, d, e in srcs))
    else:
        print("  sources  : none (the prompt carried no <source> blocks)")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--file", default=str(FIXTURES / "forensic.jsonl"))
    ap.add_argument("--span", type=int, default=0, help="which LLM span of the trace (0 = first)")
    ap.add_argument("--fresh-retrieval", action="store_true", help="rebuild the sources with today's index (kb-1)")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    a = ap.parse_args(argv)

    traces = by_trace(load_spans(a.file))
    hits = [t for t in traces if t.startswith(a.trace)]
    if len(hits) != 1:
        raise SystemExit(f"{a.trace!r} matches {len(hits)} traces")
    calls = llm_spans(traces[hits[0]])
    if not calls:
        raise SystemExit("this trace has no LLM span (a response-cache hit?): nothing to replay")
    span = calls[min(a.span, len(calls) - 1)]
    at = span["attributes"]
    print(f"original span: {span['name']}  status={span['status']}  attempts={at.get('obskit.attempts')}  "
          f"prompt={at.get('gen_ai.prompt.name')}@{at.get('gen_ai.prompt.version')}")
    req = request_from_span(span)
    describe(req)
    if a.fresh_retrieval:
        from acme_app import CURRENT_VERSION, AnswerService, build_index
        q = re.search(r"<question>(.*?)</question>", req.messages[-1].text, re.S).group(1)
        svc = AnswerService(llm=None, replicas={"kb-1": (build_index(), CURRENT_VERSION)})
        fresh = svc.build_request(q, build_index().search(q, k=svc.k))
        req.messages = fresh.messages
        print("  -> sources replaced with a fresh retrieval from kb-1:")
        describe(req)
        # replay() rebuilds from the span, so give it a span whose input is the new request
        import json
        span = {**span, "attributes": {**at, "gen_ai.input.messages": json.dumps(
            [{"role": m.role, "parts": [{"type": "text", "content": m.text}]} for m in req.messages])}}

    tr = setup_tracing("acme-replay", jsonl=str(RESULTS / "replays.jsonl"), capture_content=True)
    server = None
    if a.live:
        load_dotenv()
        base = LLM(a.model)
    else:
        server, url = start_mock(ttft=0.05, tps=0, seed=1)
        base = MockBacked(LLM("anthropic:mock-model", api_key="mock", base_url=url,
                              retry=RetryPolicy(max_attempts=2, rng=random.Random(0))), server)
    out = replay(span, InstrumentedLLM(base, prompt_name="replay", capture_content=True))
    tr.shutdown()
    if server:
        server.shutdown()
    recorded = recorded_output(calls[min(a.span, len(calls) - 1)])
    print(f"\nrecorded answer : {recorded or '(none: the original call failed)'}")
    print(f"replayed answer : {out['replayed']}")
    print(f"identical       : {out['same']}   (replay trace {out['replay_trace_id'][:12]} in results/replays.jsonl)")


if __name__ == "__main__":
    main()
