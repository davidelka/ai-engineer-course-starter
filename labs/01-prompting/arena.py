"""Instruction Hierarchy Arena — predict, then run.

For each scenario you choose what you think the model will do (A/B/C).
Then the real model runs, you see its answer, mark whether you were right,
and get the "what to look for" note. Your predictions are logged to results/.

Run:
  python labs/01-prompting/arena.py                       # Claude Haiku 5.5, all scenarios
  python labs/01-prompting/arena.py --provider openai --model gpt-5.4-mini
  python labs/01-prompting/arena.py --only secret,doc-injection --runs 3
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from promptlab.__main__ import _load_dotenv  # noqa: E402
from promptlab.providers import CallSpec, get_provider  # noqa: E402

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-5.4-mini",
    "gemini": "gemini-3.6-flash",
    "ollama": "llama3.2",
}


def ask(prompt: str, valid: set[str]) -> str:
    while True:
        answer = input(prompt).strip().upper()
        if answer in valid:
            return answer
        print(f"  choose one of: {', '.join(sorted(valid))}")


def show(title: str, body: str) -> None:
    print(f"\n\033[1m{title}\033[0m")
    print(textwrap.indent(body.strip(), "  "))


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="anthropic", choices=sorted(DEFAULT_MODELS))
    ap.add_argument("--model")
    ap.add_argument("--only", help="comma-separated scenario ids")
    ap.add_argument("--runs", type=int, default=1, help="run each scenario N times to see variance")
    args = ap.parse_args()

    model = args.model or DEFAULT_MODELS[args.provider]
    call = get_provider(args.provider)
    scenarios = yaml.safe_load((HERE / "arena_scenarios.yaml").read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        scenarios = [s for s in scenarios if s["id"] in wanted]

    log = []
    score = 0
    print(f"Instruction Hierarchy Arena — {args.provider}:{model} — {len(scenarios)} scenarios")
    for n, sc in enumerate(scenarios, 1):
        print("\n" + "=" * 72 + f"\n[{n}/{len(scenarios)}] {sc['title']}")
        show("SYSTEM", sc["system"])
        show("USER", sc["user"])
        print()
        for key, text in sc["options"].items():
            print(f"  {key}) {text}")
        prediction = ask("\nYour prediction (A/B/C): ", set(sc["options"]))

        outputs = []
        for _ in range(args.runs):
            res = call(CallSpec(model=model, system=sc["system"], user=sc["user"], max_tokens=3000, effort="low"
                                if args.provider in ("anthropic", "openai") else None))
            outputs.append(res.error or res.text)
        for i, out in enumerate(outputs, 1):
            show(f"MODEL OUTPUT{f' (run {i})' if args.runs > 1 else ''}", out[:1500])

        actual = ask("\nWhich option did the model actually do? (A/B/C): ", set(sc["options"]))
        correct = actual == prediction
        score += correct
        print(f"\n  {'✔ correct prediction' if correct else '✘ you predicted ' + prediction}")
        show("WHAT TO LOOK FOR", sc["look_for"])
        log.append({"id": sc["id"], "prediction": prediction, "actual": actual, "outputs": outputs})
        if n < len(scenarios):
            input("\n[Enter] for the next scenario ")

    print(f"\nPrediction score: {score}/{len(scenarios)}")
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"arena-{args.provider}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps({"model": model, "score": score, "rows": log}, ensure_ascii=False, indent=2))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
