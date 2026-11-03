"""Exercise 6: latency and cost benchmark across models.

    python labs/02-llm-apis/bench.py --models anthropic:claude-haiku-5-5@low,anthropic:claude-haiku-5-5@high --runs 10
    python labs/02-llm-apis/bench.py --models mock:mock-model,mock-openai:mock-model --runs 20   # free

Every call streams, so TTFT is measured. '@effort' is optional.
Reports TTFT p50/p95, total p50/p95, output tokens/s, output tokens, $ per 1,000 tasks.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from llmkit import LLM, ChatRequest, LLMError, load_dotenv  # noqa: E402

TASK_SYSTEM = "You are Acme's HR assistant. Answer in at most 60 words."
TASK = ("An employee in their third year asks how many vacation days they get, "
        "and whether unused days carry over. The policy: 14 days in year 1, +1 per year "
        "up to 20; up to 5 unused days carry over until March 31.")


def pct(xs: list[float], q: float):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def fmt(v, nd=2):
    return "-" if v is None else f"{v:.{nd}f}"


def bench(spec: str, runs: int, workers: int, max_tokens: int) -> dict:
    model_spec, _, effort = spec.partition("@")
    llm = LLM(model_spec)
    req = ChatRequest.from_prompt(TASK, system=TASK_SYSTEM, max_tokens=max_tokens, effort=effort or None)

    def one(_):
        try:
            return llm.complete(req, stream=True)
        except LLMError as e:
            return e

    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        out = list(pool.map(one, range(runs)))
    wall = time.perf_counter() - t0
    ok = [r for r in out if not isinstance(r, LLMError)]
    errs = [r for r in out if isinstance(r, LLMError)]
    ttft = [r.ttft_s for r in ok if r.ttft_s is not None]
    total = [r.latency_s for r in ok]
    tps = [r.tokens_per_second for r in ok if r.tokens_per_second]
    costs = [r.cost_usd for r in ok if r.cost_usd is not None]
    return {
        "spec": spec, "ok": len(ok), "errors": len(errs), "wall": wall,
        "first_error": str(errs[0]) if errs else "",
        "ttft50": pct(ttft, .5), "ttft95": pct(ttft, .95),
        "tot50": pct(total, .5), "tot95": pct(total, .95),
        "tps": statistics.median(tps) if tps else None,
        "out_tok": statistics.mean(r.usage.output_tokens for r in ok) if ok else None,
        "think_tok": statistics.mean(r.usage.thinking_tokens for r in ok) if ok else None,
        "per1k": statistics.mean(costs) * 1000 if costs else None,
        "retries": sum(r.attempts - 1 for r in ok),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--models", required=True, help="comma list of provider:model[@effort]")
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--workers", type=int, default=2, help="parallel calls (stay under rate limits)")
    p.add_argument("--max-tokens", type=int, default=1500)
    a = p.parse_args()
    load_dotenv(str(ROOT / ".env"))

    rows = []
    for spec in a.models.split(","):
        print(f"running {spec} x{a.runs} ...", flush=True)
        try:
            rows.append(bench(spec.strip(), a.runs, a.workers, a.max_tokens))
        except (LLMError, ValueError) as e:
            print(f"  skipped: {e}")

    head = f"{'model':<36}{'ok':>4}{'ttft p50':>10}{'p95':>7}{'total p50':>11}{'p95':>7}{'tok/s':>7}{'out':>6}{'think':>7}{'$/1k':>8}{'retry':>7}"
    print("\n" + head + "\n" + "-" * len(head))
    for r in rows:
        print(f"{r['spec'][:35]:<36}{r['ok']:>4}{fmt(r['ttft50']):>10}{fmt(r['ttft95']):>7}"
              f"{fmt(r['tot50']):>11}{fmt(r['tot95']):>7}{fmt(r['tps'], 0):>7}{fmt(r['out_tok'], 0):>6}"
              f"{fmt(r['think_tok'], 0):>7}{fmt(r['per1k'], 3):>8}{r['retries']:>7}")
    for r in rows:
        if r["first_error"]:
            print(f"\n[{r['spec']}] {r['errors']} errors, first: {r['first_error'][:200]}")
    print("\nTimes in seconds. With few runs, p95 is close to the max: treat it as a rough signal.")


if __name__ == "__main__":
    main()
