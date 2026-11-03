"""Exercise 8: Company Brain answers access questions with the six Acme tools.

    python labs/14-tool-use/ask.py "Who would approve a Figma editor seat for dana.levi@acme.example?"
    python labs/14-tool-use/ask.py --set                      # the 5 questions below, with a trace
    python labs/14-tool-use/ask.py --set --mine               # with YOUR execute_tool and run_tool_loop
    python labs/14-tool-use/ask.py --model mock --fault invalid_args --set     # free; watch recovery
    python labs/14-tool-use/ask.py --model mock --fault loop "..."            # watch max_rounds stop it
    python labs/14-tool-use/ask.py --parallel-off --set       # parallel_tool_calls=False: compare rounds

Default model: Claude Haiku 5.5. A full --set run is about 15 model calls (well under 1 cent).
"""

from __future__ import annotations

import argparse
import json

import _lab  # noqa: F401
from _lab import DEFAULT_MODEL, make_llm, requests_db
from llmkit.types import ChatRequest
from toolkit import Executor, acme_registry, run_tool_loop
from toolkit.loop import SYSTEM

SET = [
    "Who would approve a Figma editor seat for dana.levi@acme.example, and how long should it take?",
    "Does Lena Hoffmann already have Salesforce access? If not, what route would read access take?",
    "Compare github and aws-production: owner team, tier, and whether each is sensitive.",
    "Can Sapir Golan get admin on Miro? Who is her manager?",
    "What access does E016 have that expires in the next 90 days?",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--set", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--mine", action="store_true", help="use mine.execute_tool and mine.run_tool_loop")
    ap.add_argument("--fault", default="", help="mock only: invalid_args | unknown_tool | loop | bad_json")
    ap.add_argument("--max-rounds", type=int, default=5)
    ap.add_argument("--parallel-off", action="store_true")
    ap.add_argument("--no-strict", action="store_true")
    a = ap.parse_args()
    questions = SET if a.set else [a.question or SET[0]]
    llm = make_llm(a.model, {"tool_fault": a.fault, "tool_fault_first": 1 if a.fault != "loop" else 0,
                             "tool_fault_rate": 1.0 if a.fault == "loop" else 0.0} if a.fault else None)
    reg = acme_registry(requests_db=requests_db()).subset(
        ["lookup_employee", "get_system_info", "list_access_grants", "check_policy"])  # least privilege: no writes
    total = 0.0
    for q in questions:
        print(f"\n### {q}")
        if a.mine:
            import mine
            ex = Executor(reg, run=mine.execute_tool)
            res = mine.run_tool_loop(llm, q, reg, max_rounds=a.max_rounds, executor=ex)
        else:
            ex = Executor(reg)
            req = ChatRequest(messages=[], system=SYSTEM, tools=reg.tools(strict=not a.no_strict), max_tokens=1024,
                              parallel_tool_calls=False if a.parallel_off else None)
            res = run_tool_loop(llm, q, reg, max_rounds=a.max_rounds, executor=ex, request=req)
        for t in ex.trace:
            mark = "ERR" if t.is_error else "ok "
            print(f"  round {t.round} {mark} {t.name}({json.dumps(t.arguments, ensure_ascii=False)[:90]}) "
                  f"{t.ms:.0f}ms -> {t.result[:110]}")
        print(f"  stop={res.stop} rounds={res.rounds} model_calls={res.model_calls} calls={len(res.calls)} "
              f"errors={res.errors} tokens in/out={res.input_tokens}/{res.output_tokens} cost=${res.cost_usd:.5f}")
        print(f"  ANSWER: {res.text}")
        total += res.cost_usd
    print(f"\ntotal cost ${total:.5f}")


if __name__ == "__main__":
    main()
