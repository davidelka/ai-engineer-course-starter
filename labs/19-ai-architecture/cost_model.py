"""Exercises 1-2: cost and latency of every request path in a spec.

    python labs/19-ai-architecture/cost_model.py labs/19-ai-architecture/specs/company_brain.arch.yaml
    python labs/19-ai-architecture/cost_model.py <spec> --scale 2        # what if traffic doubles?
    python labs/19-ai-architecture/cost_model.py <spec> --reference      # archkit's versions

Prints, per path: cost per request and per month, what the same path costs on each
model tier and without caches, and the p95 latency budget (conservative sum of p95s)
next to a Monte Carlo estimate of the real p95.
"""

from __future__ import annotations

import argparse

from _lab import load, pick

from archkit.cost import profiles_from_spec, with_model  # noqa: E402
from archkit.latency import simulate, stages_from_spec  # noqa: E402
from llmkit.pricing import PRICES  # noqa: E402


def usd(x: float) -> str:
    if x == 0:
        return "$0"
    return f"${x:,.2f}" if x >= 0.995 else f"${x:.5f}"


def bar(frac: float, width: int = 28) -> str:
    n = max(0, min(width, round(frac * width)))
    return "#" * n + "." * (width - n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply requests_per_day")
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args()
    spec = load(a.spec)
    monthly_cost, src = pick("monthly_cost", a.reference)
    latency_budget, _ = pick("latency_budget", a.reference)
    if not spec.budget or not spec.budget.paths:
        print("this spec has no budget section yet (see the commented example in the starter)")
        return
    b = spec.budget
    print(f"# {spec.system}  (functions: {src}, traffic x{a.scale:g})\n")
    total_llm = 0.0
    for p in b.paths:
        calls = profiles_from_spec(p)
        rpd = p.requests_per_day * a.scale
        kw = dict(days=p.days, prompt_cache_hit_rate=p.prompt_cache_hit_rate,
                  response_cache_hit_rate=p.response_cache_hit_rate)
        m = monthly_cost(calls, rpd, **kw)
        total_llm += m["llm_monthly_usd"]
        print(f"## path: {p.name}   {rpd:,.0f} requests/day x {p.days} days")
        print(f"   prompt cache hit {p.prompt_cache_hit_rate:.0%}, response cache hit {p.response_cache_hit_rate:.0%}")
        for c in calls:
            print(f"   - {c.name:<16} {c.model:<18} in {c.input_tokens:>6} (cacheable {c.cacheable_tokens:>5})"
                  f"  out {c.output_tokens:>5}  x{c.calls_per_request:g}")
        print(f"   per request: {usd(m['per_request_usd'])}    per month: {usd(m['llm_monthly_usd'])}")
        print("   what if ALL calls ran on one tier:")
        for model in [k for k in PRICES if k != "mock-model"]:
            mm = monthly_cost(with_model(calls, model), rpd, **kw)
            print(f"     {model:<18} {usd(mm['llm_monthly_usd']):>12}/month")
        nc = monthly_cost(calls, rpd, days=p.days)
        print(f"   without any cache: {usd(nc['llm_monthly_usd'])}/month")
        if p.stages and p.latency_budget_ms:
            st = stages_from_spec(p)
            lb = latency_budget(st, p.latency_budget_ms)
            sim = simulate(st)
            print(f"   latency budget {p.latency_budget_ms:,.0f} ms (p95):")
            for name, ms in lb["blocks"]:
                print(f"     {name:<16} {bar(lb['shares'][name])} {ms:>8,.0f} ms")
            state = "within budget" if lb["within_budget"] else "OVER BUDGET"
            print(f"     sum of p95s = {lb['total_p95_ms']:,.0f} ms, slack {lb['slack_ms']:,.0f} ms: {state}")
            print(f"     simulated end-to-end: p50 {sim['p50_ms']:,.0f} ms, p95 {sim['p95_ms']:,.0f} ms,"
                  f" p99 {sim['p99_ms']:,.0f} ms  (log-normal stages, 20k samples)")
        print()
    total = total_llm + b.fixed_monthly_usd
    print(f"## total: models {usd(total_llm)} + fixed {usd(b.fixed_monthly_usd)} = {usd(total)}/month")
    if b.monthly_limit_usd:
        verdict = "within" if total <= b.monthly_limit_usd else "OVER"
        print(f"   limit {usd(b.monthly_limit_usd)}: {verdict} budget")


if __name__ == "__main__":
    main()
