"""Exercises 1-3: run the agent on one task and read its trajectory.

    python labs/15-agent-loops/run_agent.py                         # task t01 (Dana), fake model, free
    python labs/15-agent-loops/run_agent.py t02 --approve no        # the human declines the side effect
    python labs/15-agent-loops/run_agent.py --model mock            # mockllm: real wire shapes, scripted
    python labs/15-agent-loops/run_agent.py --model anthropic:claude-haiku-5-5 --approve ask
    python labs/15-agent-loops/run_agent.py --mode plan             # plan-then-act
    python labs/15-agent-loops/run_agent.py --loop paraphrase --mine   # YOUR stop policy vs a sneaky loop
    python labs/15-agent-loops/run_agent.py --max-cost 0.0005 --summarize
    python labs/15-agent-loops/run_agent.py --spans results/spans.jsonl   # then: python -m obskit.viewer ...

Every run appends to results/trajectory.jsonl (one JSON object per line) unless --log says otherwise.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import RESULTS, confirm_hook, is_live, make_llm, registry, task_by_id
from agentkit import Agent, Budget, format_trajectory, parse_faults, score_trajectory, to_spans


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?", default="t01", help="a task id from data/tasks.jsonl, or any task text")
    ap.add_argument("--model", default="fake", help="fake | mock | mock-openai | mock-gemini | anthropic:claude-haiku-5-5")
    ap.add_argument("--mode", default="react", choices=["react", "plan"])
    ap.add_argument("--approve", default="yes", choices=["yes", "no", "ask", "none"],
                    help="what the human says to side-effect calls (none = no confirmation hook at all)")
    ap.add_argument("--max-steps", type=int, default=8)
    ap.add_argument("--max-cost", type=float, default=0.02)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--max-seconds", type=float, default=60.0)
    ap.add_argument("--repeat-limit", type=int, default=3)
    ap.add_argument("--fault", action="append", default=[], help="tool fault, e.g. lookup_employee=error:1 (repeatable)")
    ap.add_argument("--mock-fault", default="", help="mockllm model fault: loop | invalid_args | unknown_tool | bad_json")
    ap.add_argument("--loop", default="", choices=["", "repeat", "paraphrase"], help="fake model: loop on purpose")
    ap.add_argument("--stubborn", action="store_true", help="fake model: keep retrying a failing tool")
    ap.add_argument("--naive-docs", action="store_true", help="fake model: believe documents over check_policy")
    ap.add_argument("--keep", type=int, default=None, help="keep only the last N tool-result turns (memory trimming)")
    ap.add_argument("--notes", action="store_true", help="offer the note tool (scratchpad)")
    ap.add_argument("--summarize", action="store_true", help="on a limit stop, one more call for a best-effort answer")
    ap.add_argument("--effort", default=None, help="low | medium | high (thinking depth on models that support it)")
    ap.add_argument("--mine", action="store_true", help="use mine.should_stop and mine.clear_old_tool_results")
    ap.add_argument("--log", default=str(RESULTS / "trajectory.jsonl"))
    ap.add_argument("--spans", default="", help="also write obskit span JSONL for python -m obskit.viewer")
    ap.add_argument("--quiet", action="store_true")
    return ap


def build_agent(a, reg) -> Agent:
    heur = {"loop": a.loop, "stubborn": a.stubborn, "naive_docs": a.naive_docs}
    mock_cfg = {"tool_fault": a.mock_fault, "tool_fault_rate": 1.0 if a.mock_fault == "loop" else 0.0,
                "tool_fault_first": 0 if a.mock_fault == "loop" else 1} if a.mock_fault else None
    llm = make_llm(a.model, mock_cfg=mock_cfg, heuristic=heur)
    kw = {}
    if a.mine:
        import mine
        kw = {"policy": mine.should_stop, "trim": mine.clear_old_tool_results}
    return Agent(llm, reg, mode=a.mode, confirm=None if a.approve == "none" else confirm_hook(a.approve),
                 budget=Budget(max_steps=a.max_steps, max_cost_usd=a.max_cost, max_tokens=a.max_tokens,
                               max_seconds=a.max_seconds, repeat_limit=a.repeat_limit),
                 keep_tool_results=a.keep, scratchpad=a.notes, summarize_on_stop=a.summarize, effort=a.effort,
                 log_path=a.log or None, **kw)


def main() -> None:
    a = build_parser().parse_args()
    tid, text, gold = task_by_id(a.task)
    if is_live(a.model):
        print(f"LIVE model {a.model}: this costs money (budget per run: ${a.max_cost}).")
    with tempfile.TemporaryDirectory() as tmp:
        reg = registry(Path(tmp) / "requests.db", parse_faults(a.fault))  # a fresh requests store per run
        res = build_agent(a, reg).run(text, task_id=tid)
    if not a.quiet:
        print(format_trajectory(res.records))
    if gold:
        s = score_trajectory(res.records, gold, tid)
        print(f"\nGOLD CHECK ({tid}): {'SUCCESS' if s['success'] else 'FAIL'}  steps={s['steps']} "
              f"tool_calls={s['tool_calls']} redundant={s['redundant_calls']} efficiency={s['efficiency']}")
        for r in s["reasons"]:
            print(f"  - {r}")
    if a.spans:
        from obskit import write_spans
        write_spans(to_spans(res.records), a.spans)
        print(f"\nspans -> {a.spans}   view: python -m obskit.viewer {a.spans} -o {a.spans[:-6]}.html")


if __name__ == "__main__":
    main()
