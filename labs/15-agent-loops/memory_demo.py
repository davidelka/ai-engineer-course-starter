"""Exercise 7: memory within a run. Clearing old tool results saves tokens, and can make the agent forget.

    python labs/15-agent-loops/memory_demo.py                  # 4 settings x 2 tasks, fake model
    python labs/15-agent-loops/memory_demo.py --mine           # with YOUR clear_old_tool_results
    python labs/15-agent-loops/memory_demo.py --show 1         # print the trajectory for keep=1 (no notes)
    python labs/15-agent-loops/memory_demo.py --model anthropic:claude-haiku-5-5   # does Claude re-fetch? (~$0.01)

Settings: keep everything; keep the last 2 tool-result turns; keep 1; keep 1 plus the note tool.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import RESULTS, is_live, make_llm, registry
from agentkit import Agent, Budget, format_trajectory

TASKS = {
    "dana": ("Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her "
             "manager, what does the policy say, and open the request (it goes to whatever track the policy requires)."),
    "compare6": ("Compare github, aws-production, salesforce, figma, netsuite and zendesk: owner team, tier, and "
                 "whether each one is sensitive. Look them up one at a time."),
}
SETTINGS = [("keep all", None, False), ("keep 2", 2, False), ("keep 1", 1, False), ("keep 1 + notes", 1, True)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--show", type=int, default=None, help="print the trajectory for this keep value (no notes)")
    a = ap.parse_args()
    trim = {}
    if a.mine:
        import mine
        trim = {"trim": mine.clear_old_tool_results}
    if is_live(a.model):
        print(f"LIVE model {a.model}: 8 runs, roughly $0.01 in total.")
    llm = make_llm(a.model)
    for tname, task in TASKS.items():
        print(f"\n######## task: {tname}")
        for label, keep, notes in SETTINGS:
            with tempfile.TemporaryDirectory() as tmp:
                agent = Agent(llm, registry(Path(tmp) / "r.db"), confirm=lambda c: True, keep_tool_results=keep,
                              scratchpad=notes, budget=Budget(max_steps=12, max_cost_usd=0.02),
                              log_path=str(RESULTS / "memory.jsonl"), **trim)
                res = agent.run(task, task_id=f"memory-{tname}-{label}")
            cleared = sum(r.get("cleared", 0) for r in res.records if r.get("type") == "trim")
            last_in = max((r.get("tokens_in", 0) for r in res.records if r.get("type") == "step"), default=0)
            print(f"  {label:<15} stop={res.stop_reason:<12} steps={res.steps:<2} tool_calls={len(res.calls):<2} "
                  f"input_tokens total={res.input_tokens:<6} largest prompt={last_in:<5} cleared={cleared:<2} "
                  f"answer: {res.text[:70]}")
            if a.show is not None and keep == a.show and not notes:
                print(format_trajectory(res.records))


if __name__ == "__main__":
    main()
