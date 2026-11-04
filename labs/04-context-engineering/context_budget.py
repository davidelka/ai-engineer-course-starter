"""Exercises 1, 2 and 7: where do the tokens of a request go, and what does each layer cost?

    python labs/04-context-engineering/context_budget.py                      # the three built-in requests
    python labs/04-context-engineering/context_budget.py --scenario agent --show
    python labs/04-context-engineering/context_budget.py --file labs/04-context-engineering/requests/company_brain_mine.json
    python labs/04-context-engineering/context_budget.py --calibrate          # exact total from Claude (free, needs key)
    python labs/04-context-engineering/context_budget.py --ref                # use ctxkit's reference instead of mine.py

Scenarios (built from real lab data, so you can open them):
  hr-naive    the lesson-1 HR assistant: ctxkit/layout.py naive_hr_request(), with the HR policies
              (data/acme/hr_policies.md) and the Acme handbook (labs/04-context-engineering/data/acme_handbook.md)
  hr-layered  the same request from YOUR build_hr_request() in mine.py (exercise 2)
  agent       requests/agent_turn.json: a Company Brain turn with 4 tools, a cached system prompt,
              5 earlier turns and 2 retrieved documents

Tokens are counted offline with tiktoken o200k_base, an approximation of Claude's tokenizer.
If tiktoken cannot load o200k_base, counts fall back to len/4: the header says which one you got.
--calibrate asks Claude's count_tokens endpoint for the exact total and scales every layer.
Cost assumes the steady state: the cached prefix is READ on a hit and WRITTEN on a miss.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from ctxkit.layout import naive_hr_request  # noqa: E402
from ctxkit.tokens import claude_count_tokens, count_tokens, tokenizer_name  # noqa: E402
from llmkit import PRICES, load_dotenv  # noqa: E402
from llmkit.providers.anthropic import AnthropicProvider  # noqa: E402

QUESTION = "I'm in my fourth year. How many vacation days do I get, and can I carry 5 of them over?"


def hr_documents() -> str:
    return ((ROOT / "data" / "acme" / "hr_policies.md").read_text(encoding="utf-8") + "\n\n"
            + (LAB / "data" / "acme_handbook.md").read_text(encoding="utf-8"))


def body_of(req, model: str) -> dict:
    return AnthropicProvider().build(req, model, "unused", stream=False).body


def scenarios(model: str, use_ref: bool) -> dict[str, dict]:
    docs = hr_documents()
    out = {"hr-naive": body_of(naive_hr_request(docs, QUESTION, employee="Dana Cohen", today="2026-11-01"), model)}
    try:
        if use_ref:
            from ctxkit.layout import build_hr_request
        else:
            from mine import build_hr_request
        out["hr-layered"] = body_of(build_hr_request(docs, QUESTION, employee="Dana Cohen", today="2026-11-01"), model)
    except NotImplementedError:
        print("(hr-layered skipped: build_hr_request in mine.py is not implemented yet, exercise 2)\n")
    out["agent"] = json.loads((LAB / "requests" / "agent_turn.json").read_text(encoding="utf-8"))
    return out


def money(x: float) -> str:
    return f"${x:,.4f}" if x < 1 else f"${x:,.2f}"


def analyze(name: str, body: dict, layer_report, model: str, out_tokens: int, hit_rate: float,
            calls: int, calibrate: bool, show: bool) -> None:
    layers = layer_report(body, count_tokens)
    total = sum(x.tokens for x in layers)
    scale = 1.0
    if calibrate:
        exact = claude_count_tokens({**body, "model": model})
        scale = exact / total if total else 1.0
        print(f"[{name}] Claude count_tokens: {exact:,} tokens; {tokenizer_name()} said {total:,} (ratio {scale:.2f})")
    p = PRICES.get(model) or PRICES["claude-haiku-5-5"]
    print(f"\n=== {name}  ({model}; tokens counted with {tokenizer_name()}) ===")
    cached_total = 0
    for x in layers:
        t, c = x.tokens * scale, x.cached_tokens * scale
        cached_total += c
        share = 100 * t / (total * scale) if total else 0
        bar = "#" * round(share / 4)
        print(f"  {x.name:<10} {t:>9,.0f} tok  {share:5.1f}%  cached {c:>8,.0f}  {bar}")
    t_all = total * scale
    print(f"  {'TOTAL':<10} {t_all:>9,.0f} tok           cached {cached_total:>8,.0f}  "
          f"({100 * cached_total / t_all if t_all else 0:.0f}% of the prompt is a cacheable prefix)")
    m = 1e-6
    mult = p.get("long_multiplier", 1.0) if p.get("long_threshold") and t_all > p["long_threshold"] else 1.0
    out_cost = out_tokens * p["output"] * m
    no_cache = (t_all * p["input"]) * m + out_cost
    uncached = (t_all - cached_total) * p["input"] * m
    hit = uncached + cached_total * p.get("cached_input", p["input"]) * m + out_cost
    miss = uncached + cached_total * p.get("cache_write", p["input"]) * m + out_cost
    blended = hit_rate * hit + (1 - hit_rate) * miss
    print(f"  per call ({out_tokens} output tokens): no cache {money(no_cache * mult)} | "
          f"cache miss (write) {money(miss * mult)} | cache hit (read) {money(hit * mult)}")
    print(f"  {calls:,} calls at {hit_rate:.0%} hit rate: {money(blended * calls * mult)} "
          f"vs {money(no_cache * calls * mult)} without caching"
          + (f"  (x{mult:g}: above {p['long_threshold']:,} prompt tokens)" if mult != 1 else ""))
    if show:
        print("  --- body (truncated strings) ---")
        print("  " + json.dumps(body, ensure_ascii=False, default=str)[:1500] + " ...")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["hr-naive", "hr-layered", "agent", "all"], default="all")
    ap.add_argument("--file", help="analyze this Anthropic request body (JSON) instead")
    ap.add_argument("--model", default="claude-haiku-5-5", help="price table entry in llmkit/pricing.py")
    ap.add_argument("--out", type=int, default=300, help="assumed output tokens per call")
    ap.add_argument("--hit-rate", type=float, default=0.9)
    ap.add_argument("--calls", type=int, default=1000)
    ap.add_argument("--calibrate", action="store_true", help="exact totals via Claude count_tokens (free, needs key)")
    ap.add_argument("--ref", action="store_true", help="use ctxkit's reference layer_report/build_hr_request")
    ap.add_argument("--show", action="store_true", help="print the request body too")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    if a.ref:
        from ctxkit.layers import layer_report
    else:
        from mine import layer_report
    if a.file:
        bodies = {Path(a.file).name: json.loads(Path(a.file).read_text(encoding="utf-8"))}
    else:
        bodies = scenarios(a.model, a.ref)
        if a.scenario != "all":
            bodies = {k: v for k, v in bodies.items() if k == a.scenario}
    try:
        for name, body in bodies.items():
            analyze(name, body, layer_report, a.model, a.out, a.hit_rate, a.calls, a.calibrate, a.show)
    except NotImplementedError as e:
        sys.exit(f"{e}\nRun with --ref to see the reference output first, or implement it in mine.py.")


if __name__ == "__main__":
    main()
