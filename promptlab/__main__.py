"""Command line: python -m promptlab run <experiment.yaml> | report <results.jsonl>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .runner import format_summary, load_experiment, load_jsonl, render, run_experiment, summarize


def _load_dotenv() -> None:
    """Minimal .env loader so the lab needs no extra package. Existing env vars win."""
    import os

    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return


FREE_PROVIDERS = {"ollama", "mock", "fake"}


def plan_cost(exp, only=None) -> tuple[list[tuple[str, str, int, Optional[float]]], int, float, bool]:
    """Per variant: (name, model, calls, worst-case USD or None if unknown). Worst case = prompt
    tokens estimated as chars/4 of the rendered prompts, plus max_tokens of output for every call."""
    from llmkit.pricing import PRICES

    rows, total_calls, total_usd, unknown = [], 0, 0.0, False
    for v in exp.variants:
        if only and v.name not in only:
            continue
        calls = len(exp.cases) * exp.repeats
        provider, model = v.params.get("provider", ""), v.params.get("model", "")
        if provider in FREE_PROVIDERS:
            usd: Optional[float] = 0.0
        else:
            price = exp.prices.get(model) or PRICES.get(model)
            if not price:
                usd, unknown = None, True
            else:
                prompt_chars = sum(len(render(v.system, c)) + len(render(v.user_template, c)) for c in exp.cases)
                in_tok = prompt_chars / 4 * exp.repeats
                out_tok = int(v.params.get("max_tokens", 1024)) * calls
                usd = (in_tok * price["input"] + out_tok * price["output"]) / 1_000_000
        rows.append((v.name, f"{provider}:{model}", calls, usd))
        total_calls += calls
        total_usd += usd or 0.0
    return rows, total_calls, total_usd, unknown


def confirm_cost(exp, only=None, *, yes: bool = False, max_cost: float = 1.00) -> bool:
    rows, calls, usd, unknown = plan_cost(exp, only)
    paid = any(u is None or u > 0 for *_, u in rows)
    print(f"Plan: {calls} calls")
    for name, model, n, u in rows:
        cost = "free (local)" if u == 0 else ("price unknown" if u is None else f"<= ${u:.3f}")
        print(f"  {name:<28} {model:<32} {n:>4} calls  {cost}")
    if not paid:
        return True
    print(f"Worst-case estimate: <= ${usd:.3f}" + (" plus variants with an unknown price" if unknown else "")
          + "  (prompt tokens estimated as chars/4; every reply assumed to use all of max_tokens)")
    if usd > max_cost:
        print(f"Refusing: the estimate is above --max-cost {max_cost:.2f}. Use --limit / --repeats, or raise --max-cost.")
        return False
    if yes:
        return True
    try:
        answer = input("Run it? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        print("Not run. (--dry-run shows the prompts; --yes skips this question.)")
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="promptlab")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run an experiment")
    run_p.add_argument("experiment")
    run_p.add_argument("--variants", help="comma-separated subset of variant names")
    run_p.add_argument("--repeats", type=int, help="override repeats")
    run_p.add_argument("--limit", type=int, help="only the first N cases (cheap smoke test)")
    run_p.add_argument("--dry-run", action="store_true", help="print the rendered prompts, call nothing")
    run_p.add_argument("--yes", action="store_true", help="skip the cost confirmation (paid providers)")
    run_p.add_argument("--max-cost", type=float, default=1.00,
                       help="refuse to start if the worst-case estimate is above this many USD (default 1.00)")

    rep_p = sub.add_parser("report", help="summarize an existing results file")
    rep_p.add_argument("results")
    rep_p.add_argument("--experiment", help="experiment yaml, for prices")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        exp = load_experiment(args.experiment)
        if args.repeats:
            exp.repeats = args.repeats
        if args.limit:
            exp.cases = exp.cases[: args.limit]
        only = args.variants.split(",") if args.variants else None

        if args.dry_run:
            for v in exp.variants:
                if only and v.name not in only:
                    continue
                case = exp.cases[0]
                print(f"===== {v.name}  {v.params}")
                print("--- system ---\n" + render(v.system, case))
                print("--- user ---\n" + render(v.user_template, case) + "\n")
            n = len([v for v in exp.variants if not only or v.name in only])
            print(f"Would make {n * len(exp.cases) * exp.repeats} calls.")
            plan_cost_rows = plan_cost(exp, only)
            print(f"Worst-case estimate: <= ${plan_cost_rows[2]:.3f}" + (" plus unknown-price variants" if plan_cost_rows[3] else ""))
            return 0

        if not confirm_cost(exp, only, yes=args.yes, max_cost=args.max_cost):
            return 1
        out = run_experiment(exp, exp.results_dir, only)
        rows = load_jsonl(out)
        print("\n" + format_summary(summarize(rows, exp.prices)))
        print(f"\nRaw rows: {out}")
        return 0

    rows = load_jsonl(Path(args.results))
    prices = load_experiment(args.experiment).prices if args.experiment else {}
    print(format_summary(summarize(rows, prices)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
