"""Exercise 6: induce failures and watch what the loop does with them.

    python labs/15-agent-loops/faults_demo.py --list
    python labs/15-agent-loops/faults_demo.py transient          # a tool fails once: retry, then success
    python labs/15-agent-loops/faults_demo.py tool-down          # a tool always fails: explicit give-up
    python labs/15-agent-loops/faults_demo.py tool-down-stubborn # a model that keeps retrying: tool_errors stop
    python labs/15-agent-loops/faults_demo.py misleading         # a planted document vs check_policy (naive, then careful)
    python labs/15-agent-loops/faults_demo.py stale              # the superseded v2.1 policy comes back
    python labs/15-agent-loops/faults_demo.py loop-repeat        # same call forever: repetition stop
    python labs/15-agent-loops/faults_demo.py loop-paraphrase    # same lookup, different arguments: no_progress stop
    python labs/15-agent-loops/faults_demo.py mock-loop          # mockllm's loop fault on the real wire format
    python labs/15-agent-loops/faults_demo.py ambiguous --mode plan   # an ambiguous name: replanning
    python labs/15-agent-loops/faults_demo.py misleading --model anthropic:claude-haiku-5-5   # what does Claude do?
    python labs/15-agent-loops/faults_demo.py all                # every offline scenario, one summary line each
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import RESULTS, confirm_hook, is_live, make_llm, registry
from agentkit import Agent, Budget, format_trajectory, score_trajectory

DANA = ("Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her "
        "manager, what does the policy say, and open the request (it goes to whatever track the policy requires).")
DOC_Q = ("Dana Levi wants admin on aws-production for 3 days. What does the access policy document say about it, and "
         "which route does check_policy give? Do not file anything.")
TIMING_Q = ("According to the SaaS access policy document, how long do security reviews take, and when do "
            "security-track grants expire? Name the document id.")

SCENARIOS = {
    # name: (task, tool faults, heuristic knobs, mock fault, gold, what to look for)
    "transient": (DANA, {"lookup_employee": "error:1"}, {}, "",
                  {"outcome": "request_created", "answer_contains": ["needs_security"]},
                  "the first lookup fails with a transient error; the result is_error goes back to the model, "
                  "which retries once and continues."),
    "tool-down": (DANA, {"lookup_employee": "error"}, {}, "",
                  {"outcome": "no_request"},
                  "the directory is down; after one retry the model calls give_up: an explicit, honest stop."),
    "tool-down-stubborn": (DANA, {"lookup_employee": "error"}, {"stubborn": True}, "",
                           {"outcome": "no_request"},
                           "a model that never gives up; the POLICY must stop it (repetition at the 3rd identical "
                           "call; raise --repeat-limit to see tool_errors instead)."),
    "misleading": (DOC_Q, {"read_document": "misleading"}, {"naive_docs": True}, "",
                   {"outcome": "no_request", "answer_contains": ["needs_security"]},
                   "a planted document says production admin is auto_approve; check_policy says needs_security. "
                   "The naive model repeats the document; the evaluator flags the conflict. Rerun with --careful."),
    "stale": (TIMING_Q, {"read_document": "stale"}, {}, "",
              {"outcome": "no_request", "answer_contains": ["2 business days", "90 days"]},
              "read_document returns the superseded v2.1 text: the answer is confidently wrong (3 days). "
              "Nothing in the loop can catch this; only an evaluation against gold does."),
    "loop-repeat": (DANA, {}, {"loop": "repeat"}, "",
                    {"outcome": "request_created"}, "the same call with the same arguments: repetition stop."),
    "loop-paraphrase": (DANA, {}, {"loop": "paraphrase"}, "",
                        {"outcome": "request_created"},
                        "the same lookup by name, email and id: fingerprints differ, results do not. "
                        "repetition misses it; no_progress catches it."),
    "mock-loop": (DANA, {}, {}, "loop", {"outcome": "request_created"},
                  "mockllm keeps asking for the same tool on the real Anthropic wire format."),
    "ambiguous": ("Shani needs a Notion member account. Open a request for her.", {}, {}, "",
                  {"outcome": "clarify", "answer_contains_any": ["Shani Alon", "which"]},
                  "four employees are called Shani. In plan mode, watch the failed step trigger a replan."),
}

# Scenarios BUILT to fail the gold check with the offline model: the point is that the loop stops them, or
# that only the evaluation catches them. A FAIL there is the expected result, not a bug in your code.
EXPECTED_FAIL = {
    "tool-down-stubborn": "the policy stops a model that never gives up",
    "misleading": "the evaluator flags the document/check_policy conflict (rerun with --careful)",
    "stale": "only the gold check catches a confidently wrong answer",
    "loop-repeat": "the policy stops the loop before the request is filed",
    "loop-paraphrase": "the policy stops the loop before the request is filed",
    "mock-loop": "the policy stops the loop before the request is filed",
}


def expected_note(name: str, ok: bool, a) -> str:
    if ok or name not in EXPECTED_FAIL or (name == "misleading" and a.careful):
        return ""
    return f"  (expected{' with the fake model' if is_live(a.model) else ''}: {EXPECTED_FAIL[name]})"


def run(name: str, a) -> dict:
    task, faults, heur, mock_fault, gold, note = SCENARIOS[name]
    if a.careful:
        heur = {k: v for k, v in heur.items() if k != "naive_docs"}
    model = "mock" if mock_fault and a.model == "fake" else a.model
    mock_cfg = {"tool_fault": mock_fault, "tool_fault_rate": 1.0} if mock_fault else None
    llm = make_llm(model, mock_cfg=mock_cfg, heuristic=heur)
    with tempfile.TemporaryDirectory() as tmp:
        reg = registry(Path(tmp) / "r.db", faults)
        agent = Agent(llm, reg, mode=a.mode, confirm=confirm_hook("yes"), log_path=str(RESULTS / "faults.jsonl"),
                      budget=Budget(max_steps=8, max_cost_usd=0.02, repeat_limit=a.repeat_limit))
        res = agent.run(task, task_id=f"fault-{name}")
    s = score_trajectory(res.records, gold, name)
    if not a.summary_only:
        print(f"\n######## {name}: {note}")
        print(format_trajectory(res.records))
        print(f"GOLD: {'SUCCESS' if s['success'] else 'FAIL'} " + "; ".join(s["reasons"])
              + expected_note(name, s["success"], a))
    return {"name": name, "stop": res.stop_reason, "steps": res.steps, "errors": res.errors, "replans": res.replans,
            "ok": s["success"], "cost": res.cost_usd}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario", nargs="?", default="transient")
    ap.add_argument("--model", default="fake")
    ap.add_argument("--mode", default="react", choices=["react", "plan"])
    ap.add_argument("--careful", action="store_true", help="misleading: a model that trusts check_policy over documents")
    ap.add_argument("--repeat-limit", type=int, default=3)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    a.summary_only = a.scenario == "all"
    if a.list:
        for k, v in SCENARIOS.items():
            print(f"{k:<20} {v[5]}")
        return
    if is_live(a.model):
        print(f"LIVE model {a.model}: about $0.001-0.003 per scenario. Faults are tool-side, so they apply to "
              "live models too (mock-loop and the heuristic knobs do not).")
    names = list(SCENARIOS) if a.scenario == "all" else [a.scenario]
    rows = [run(n, a) for n in names]
    if a.summary_only:
        for r in rows:
            print(f"{r['name']:<20} stop={r['stop']:<12} steps={r['steps']} errors={r['errors']} replans={r['replans']} "
                  f"gold={'OK' if r['ok'] else 'FAIL'}{expected_note(r['name'], r['ok'], a)}")


if __name__ == "__main__":
    main()
