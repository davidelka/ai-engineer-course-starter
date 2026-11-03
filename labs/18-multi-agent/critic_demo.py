"""Exercise 8: generator + critic with a rubric and a round limit.

    python labs/18-multi-agent/critic_demo.py                     # strict fake critic
    python labs/18-multi-agent/critic_demo.py --critic lenient    # a rubber stamp
    python labs/18-multi-agent/critic_demo.py --critic nitpick --max-rounds 4
    python labs/18-multi-agent/critic_demo.py --model anthropic:claude-haiku-5-5
"""

from __future__ import annotations

import argparse
import json

import _lab  # noqa: F401
from _lab import CRITIC_CASE, is_live, money
from agentkit import FakeLLM
from multikit import DEFAULT_RUBRIC, CriticLoop
from multikit.fake import CriticHeuristic, WriterHeuristic


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake")
    ap.add_argument("--critic", default="strict", choices=["strict", "lenient", "nitpick"])
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--no-code-checks", action="store_true", help="give every criterion to the critic model")
    a = ap.parse_args()
    case = json.loads(CRITIC_CASE.read_text(encoding="utf-8"))
    rubric = [dict(c, check="llm") for c in DEFAULT_RUBRIC] if a.no_code_checks else DEFAULT_RUBRIC
    if is_live(a.model):
        from llmkit import LLM
        w = c = LLM(a.model)
    else:
        w, c = FakeLLM(WriterHeuristic()), FakeLLM(CriticHeuristic(a.critic))
    print("RUBRIC:")
    for r in rubric:
        print(f"  - {r['id']} [{r['check']}]: {r['text']}")
    res = CriticLoop(w, c, rubric=rubric, max_rounds=a.max_rounds).run(case["task"], case["facts"])
    for rd in res.info["rounds"]:
        print(f"\n--- round {rd['round']}  ({money(rd['cost_usd'])})\nDRAFT: {rd['draft']}")
        for x in rd["results"]:
            print(f"  {'PASS' if x['passed'] else 'FAIL'} {x['id']}: {x['note']}")
    print(f"\nSTOP: {res.stop_reason} after {len(res.info['rounds'])} round(s); total {res.tokens:,} tokens, "
          f"{money(res.cost_usd)}{' (estimated)' if res.estimated else ''}")
    print(f"FINAL: {res.text}")


if __name__ == "__main__":
    main()
