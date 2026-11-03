"""Exercises 3-4: prompt caching, measured. N calls of the HR assistant with a ~13K-token
stable prefix (instructions + HR policies + Acme handbook), one row per call.

    python labs/04-context-engineering/cache_experiment.py --mode all                 # live, Claude Haiku 5.5
    python labs/04-context-engineering/cache_experiment.py --mode explicit --layout mine
    python labs/04-context-engineering/cache_experiment.py --mode explicit --parallel 3
    python labs/04-context-engineering/cache_experiment.py --mode explicit --short    # prefix below the minimum
    python labs/04-context-engineering/cache_experiment.py --mode explicit --ttl 1h
    python labs/04-context-engineering/cache_experiment.py --model mock:mock-model --mode all   # free

Modes (all send the same questions; only the cache setup differs):
  none      the layered request, with no cache breakpoint
  explicit  build_hr_request(): a breakpoint at the end of the documents (exercise 2)
  auto      no block breakpoint, but a top-level cache_control (automatic caching)
  broken    explicit, but the first system line has the current time in it: a classic bug

The free path: start the mock with a simulated prompt-processing speed, so cache hits are
visibly faster (the speed is invented; only the live run tells you the real numbers):
    python -m mockllm --prefill-tps 5000      # terminal 2

Live cost: one mode is about $0.002-0.01 on Claude Haiku 5.5; --mode all about $0.03.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from llmkit import LLM, Block, LLMError, load_dotenv  # noqa: E402

QUESTIONS = [
    "How many vacation days do I get in my first year?",
    "Can I carry unused vacation days into next year?",
    "Which days are office days?",
    "How do I claim the home office allowance?",
    "What is the per-diem lodging cap in Germany?",
    "Who approves working from abroad, and for how many days?",
    "What is the on-call allowance in the Payments team?",
    "How long are Ledger's records retained?",
]
EMPLOYEES = ["Dana Cohen", "Karim Haddad", "Noa Levi", "Omer Peretz"]


def documents(short: bool) -> str:
    policies = (ROOT / "data" / "acme" / "hr_policies.md").read_text(encoding="utf-8")
    if short:
        return policies  # ~300 tokens: together with the instructions, near or under the 512 minimum
    return policies + "\n\n" + (LAB / "data" / "acme_handbook.md").read_text(encoding="utf-8")


def make_request(mode: str, layout: str, docs: str, i: int, ttl: str):
    if layout == "mine":
        from mine import build_hr_request
    else:
        from ctxkit.layout import build_hr_request
    req = build_hr_request(docs, QUESTIONS[i % len(QUESTIONS)], employee=EMPLOYEES[i % len(EMPLOYEES)],
                           today="2026-11-01", ttl=ttl)
    if mode in ("none", "auto"):
        req.system = [replace(b, cache=None) for b in req.system]
    if mode == "auto":
        req.cache = ttl
    if mode == "broken":
        first = req.system[0]
        req.system = [Block(f"Request time: {time.time():.3f}\n{first.text}", first.cache)] + req.system[1:]
    return req


def one(llm, req, i):
    t0 = time.perf_counter()
    try:
        r = llm.complete(req, stream=True)
        return {"i": i, "ok": True, "ttft": r.ttft_s, "latency": r.latency_s, "input": r.usage.input_tokens,
                "write": r.usage.cache_creation_tokens, "read": r.usage.cached_input_tokens,
                "uncached": r.usage.uncached_input_tokens, "output": r.usage.output_tokens,
                "cost": r.cost_usd or 0.0, "answer": r.text[:120].replace("\n", " ")}
    except LLMError as e:
        return {"i": i, "ok": False, "error": str(e)[:200], "latency": time.perf_counter() - t0, "cost": 0.0}


def run_mode(llm, mode, a, docs):
    print(f"\n=== mode: {mode}  ({a.model}, {a.calls} calls, ttl {a.ttl}"
          + (f", first {a.parallel} in parallel" if a.parallel > 1 else "") + ") ===")
    print(f"  {'#':>2} {'ttft s':>7} {'total s':>8} {'prompt':>8} {'write':>7} {'read':>7} {'uncached':>8} {'cost $':>9}")
    rows = []
    if a.parallel > 1:
        with ThreadPoolExecutor(a.parallel) as pool:
            rows += list(pool.map(lambda i: one(llm, make_request(mode, a.layout, docs, i, a.ttl), i), range(a.parallel)))
    for i in range(len(rows), a.calls):
        if rows and a.gap:
            time.sleep(a.gap)
        rows.append(one(llm, make_request(mode, a.layout, docs, i, a.ttl), i))
    for r in rows:
        if not r["ok"]:
            print(f"  {r['i'] + 1:>2} ERROR {r['error']}")
            continue
        print(f"  {r['i'] + 1:>2} {r['ttft'] or 0:>7.2f} {r['latency']:>8.2f} {r['input']:>8,} {r['write']:>7,} "
              f"{r['read']:>7,} {r['uncached']:>8,} {r['cost']:>9.5f}")
    ok = [r for r in rows if r["ok"]]
    if ok:
        later = ok[1:] or ok
        print(f"  total cost ${sum(r['cost'] for r in ok):.5f} | calls with a cache read: "
              f"{sum(1 for r in ok if r['read'])}/{len(ok)} | median TTFT first {ok[0]['ttft'] or 0:.2f}s, "
              f"later {statistics.median([r['ttft'] or 0 for r in later]):.2f}s")
        if a.verbose:
            for r in ok:
                print(f"     {r['i'] + 1}: {r['answer']}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--mode", default="explicit", choices=["none", "explicit", "auto", "broken", "all"])
    ap.add_argument("--layout", default="ref", choices=["ref", "mine"], help="whose build_hr_request to use")
    ap.add_argument("--calls", type=int, default=6)
    ap.add_argument("--gap", type=float, default=1.0, help="seconds between sequential calls")
    ap.add_argument("--parallel", type=int, default=1, help="send the first K calls at the same time")
    ap.add_argument("--ttl", default="5m", choices=["5m", "1h"])
    ap.add_argument("--short", action="store_true", help="only the HR policies: a prefix near the minimum size")
    ap.add_argument("--verbose", action="store_true", help="print the start of every answer")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    llm = LLM(a.model)
    docs = documents(a.short)
    modes = ["none", "explicit", "auto", "broken"] if a.mode == "all" else [a.mode]
    results = {}
    for m in modes:
        results[m] = run_mode(llm, m, a, docs)
        if a.mode == "all" and m != modes[-1]:
            time.sleep(a.gap)
    out = LAB / "results" / f"cache_{a.model.replace(':', '_')}_{a.mode}_{int(time.time())}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"args": vars(a), "results": results}, indent=1), encoding="utf-8")
    print(f"\nsaved {out.relative_to(ROOT)}")
    if a.mode == "all":
        print("note: 'auto' and 'explicit' share a prefix, so the auto run may READ what explicit wrote.")


if __name__ == "__main__":
    main()
