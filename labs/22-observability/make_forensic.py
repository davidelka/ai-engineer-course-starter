"""Regenerate the forensic trace set (fixtures/forensic.jsonl + fixtures/feedback.jsonl).

You do NOT need to run this: the fixtures are committed, and the exercise is to read them.
It is here so you can see exactly how the faults were produced (no hand-edited spans).

Every request goes through the real stack: AnswerService -> obskit spans -> llmkit ->
HTTP -> an in-process mockllm. The faults are mock settings and pipeline settings,
changed between requests:
  - a stale index replica          (the retrieval replica "kb-2", built 2025-05-30)
  - a rate-limit storm             (mockllm answers 429 for the first N requests)
  - a timeout                      (mockllm waits longer than the client's read timeout)
  - a prompt-cache miss            (a one-word system prompt edit, v3 -> v3.1)
The only thing changed afterwards is the clock: traces ran back to back in ~20 seconds,
so each trace is shifted to a time on the morning of 2026-10-29 (durations unchanged).

    python labs/22-observability/make_forensic.py            # rewrites fixtures/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys

import httpx

from _lab import FIXTURES, MockBacked, start_mock
from acme_app import CURRENT_VERSION, STALE_VERSION, AnswerService, build_index
from llmkit import LLM, RetryPolicy
from obskit import InstrumentedLLM, by_trace, root_of, setup_tracing, write_spans

BASE_MS = 1761721320000.0  # 2026-10-29 07:02:00 UTC (09:02 in Tel Aviv)
PRICES = {"mock-model": {"input": 0.10, "output": 0.50, "cached_input": 0.01, "cache_write": 0.125},
          "mock-small": {"input": 0.02, "output": 0.10}}

# (minute offset, question, settings, feedback)
SCENARIOS = [
    (0, "How many days a week can employees work remotely?", {}, None),
    (6, "How many sick days do employees in Israel accrue per year?", {}, None),
    (11, "How many unused vacation days can I carry over to next year, and when do they expire?",
     {"replica": "kb-2"}, (-1, "That's wrong. Since January it's 5 days, and they expire at the end of March.")),
    (17, "Can I use SMS codes as my second factor?", {}, (1, "")),
    (38, "How much is the home office allowance and how do I claim it?", {"fail_first": 1}, None),
    (39, "How many sick days can I use to care for a sick child?", {"fail_first": 2}, None),
    (41, "Do I need a medical certificate if I am sick for two days?",
     {"fail_first": 3, "fallback_reply": "Yes. Acme requires a medical certificate for every sick day, starting from the first day."},
     (-1, "Not true, the policy says 3 or more consecutive days. Where did this come from?")),
    (52, "Who owns the sick leave policy, and what is their email?",
     {"reply": "The Sick Leave Policy is owned by Orly Peretz [1], VP People ({email}) [4]."}, (1, "")),
    (63, "A customer bought an annual plan three months ago and wants a refund. Are they entitled to one?",
     {"prompt_version": "v3.1"}, (-1, "Right answer, but much slower than usual.")),
    (71, "What is the minimum password length, and do I have to change my password every 90 days?",
     {"latency": 3.0}, (-1, "It's in the password policy! Why can't it find it?")),
    (78, "How many days a week can employees work remotely?", {}, (1, "")),
    (85, "How often are laptops replaced?", {"user": "u-51c2"}, None),
]

# The answer key, stored as hashes so the check script can verify you without spoiling.
CAUSES = {2: "stale_index", 6: "rate_limit_fallback", 8: "prompt_cache_miss", 9: "llm_timeout"}


def answer_hash(trace_id: str, cause: str) -> str:
    return hashlib.sha256(f"{trace_id}:{cause}".encode()).hexdigest()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(FIXTURES))
    ap.add_argument("--hub-json", default=None, help="also write a compact copy for the hub aid")
    a = ap.parse_args(argv)

    base_cfg = dict(ttft=0.15, tps=120, latency=0.25, prefill_tps=900, cache_min_tokens=512, seed=7)
    server, url = start_mock(**base_cfg)
    tr = setup_tracing("acme-answer", memory=True, capture_content=True,
                       resource_attributes={"deployment.environment": "prod", "service.version": "2.4.1"})
    timeout = httpx.Timeout(connect=2.0, read=2.5, write=5.0, pool=2.0)
    retry = RetryPolicy(max_attempts=3, base=0.2, cap=2.0, rng=random.Random(3))
    primary = MockBacked(LLM("anthropic:mock-model", api_key="mock", base_url=url, retry=retry,
                             timeout=timeout, prices=PRICES), server)
    small = MockBacked(LLM("anthropic:mock-small", api_key="mock", base_url=url, retry=RetryPolicy.none(),
                           timeout=timeout, prices=PRICES), server)
    svc = AnswerService(
        llm=InstrumentedLLM(primary, prompt_name="rag-answer", prompt_version="v3", capture_content=True),
        fallback_llm=InstrumentedLLM(small, prompt_name="fallback", prompt_version="v1", capture_content=True),
        replicas={"kb-1": (build_index(), CURRENT_VERSION), "kb-2": (build_index(STALE_VERSION), STALE_VERSION)},
    )
    users = ["u-1a07", "u-3f19", "u-77d0", "u-9b42", "u-0c55", "u-6e81"]
    order, feedback = [], []
    for i, (minute, q, s, fb) in enumerate(SCENARIOS):
        cfg = dict(base_cfg)
        cfg.update({k: s[k] for k in ("fail_first", "latency") if k in s})
        if "fail_first" in s:
            cfg["status"] = 429
        server.state.cfg = type(server.state.cfg)(**cfg)
        server.state.requests = 0  # fail_first counts from here; the prompt cache is kept
        if "reply" in s:
            from acme_app import lookup_employee
            primary.script = [s["reply"].format(email=(lookup_employee("Orly Peretz") or {}).get("email", "?"))]
        if "fallback_reply" in s:
            small.script = [s["fallback_reply"]]
        pv = s.get("prompt_version", "v3")
        svc.prompt_version = pv
        svc.llm.prompt_version = pv
        out = svc.answer(q, replica=s.get("replica", "kb-1"), user=s.get("user", users[i % len(users)]))
        order.append((out["trace_id"], minute))
        print(f"{i:2d} {out['trace_id'][:8]} {out['kind']:<15} grounded={out.get('grounded')}  {out['answer'][:90]}")
        if fb:
            feedback.append({"trace_id": out["trace_id"], "rating": fb[0], "comment": fb[1],
                             "time_ms": None, "_i": i})
    tr.flush()
    spans = tr.memory.spans
    traces = by_trace(spans)
    shift = {}
    for tid, minute in order:
        root = root_of(traces[tid])
        shift[tid] = BASE_MS + minute * 60_000 + 7_000 - root["start_ms"]
    for s in spans:
        d = shift[s["trace_id"]]
        s["start_ms"] = round(s["start_ms"] + d, 3)
        s["end_ms"] = round(s["end_ms"] + d, 3)
        for e in s.get("events", []):
            e["time_ms"] = round(e["time_ms"] + d, 3)
    spans.sort(key=lambda s: (s["start_ms"], s["span_id"]))
    for f in feedback:
        root = root_of([s for s in spans if s["trace_id"] == f["trace_id"]])
        f["time_ms"] = round(root["end_ms"] + 25_000, 3)
    write_spans(spans, f"{a.out}/forensic.jsonl")
    key = {answer_hash(order[i][0], c): True for i, c in CAUSES.items()}
    with open(f"{a.out}/feedback.jsonl", "w", encoding="utf-8") as fh:
        for f in feedback:
            fh.write(json.dumps({k: v for k, v in f.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")
    with open(f"{a.out}/forensic_key.json", "w", encoding="utf-8") as fh:
        json.dump({"hashes": sorted(key), "flagged": [order[i][0] for i in sorted(CAUSES)]}, fh, indent=1)
    print(f"wrote {len(spans)} spans in {len(order)} traces to {a.out}/forensic.jsonl")
    if a.hub_json:
        with open(a.hub_json, "w", encoding="utf-8") as fh:
            json.dump({"spans": spans, "feedback": feedback, "causes": {order[i][0]: c for i, c in CAUSES.items()}},
                      fh, ensure_ascii=False)
    server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
