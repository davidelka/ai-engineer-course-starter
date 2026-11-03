"""Command line: python -m promptlab run <experiment.yaml> | report <results.jsonl>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
            return 0

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
