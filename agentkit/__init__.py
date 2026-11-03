"""agentkit: agent loops for Company Brain (lesson 15 onward).

    from agentkit import Agent, Budget
    agent = Agent(LLM("anthropic:claude-haiku-5-5"), acme_registry(), budget=Budget(max_steps=8, max_cost_usd=0.01),
                  confirm=lambda call: input(f"run {call.name}? [y/N] ") == "y", log_path="results/run.jsonl")
    res = agent.run("Dana asks for admin on aws-production for 3 days. Who is her manager? Open the request.")

types.py       Budget, StepRecord, StopDecision, Plan, AgentResult
agent.py       Agent: the step loop (react or plan), confirmations, give_up, notes, trimming, trajectory, spans
policy.py      should_stop: final answer, give-up, steps, tokens, cost, time, repetition, tool errors, no progress
planner.py     make_plan / replan with llmkit.structured
memory.py      clear_old_tool_results and the note tool (Scratchpad)
trajectory.py  JSONL log, pretty printer, conversion to obskit spans
evaluate.py    score_trajectory / summarize_scores / run_tasks
fake.py        FakeLLM + ScriptPolicy + AcmeHeuristic: deterministic offline "models"
faults.py      tool-side faults: transient errors, crashes, slowness, misleading/stale documents
workflow.py    the same access-request job as a fixed workflow (preview of lesson 16)
"""

from .agent import GIVE_UP, SYSTEM, Agent
from .evaluate import format_summary, load_tasks, run_tasks, score_trajectory, summarize_scores
from .fake import AcmeHeuristic, FakeLLM, ScriptPolicy, parse_task
from .faults import parse_faults, with_faults
from .memory import Scratchpad, clear_old_tool_results
from .planner import make_plan, replan
from .policy import STOP_REASONS, fingerprint, result_hash, should_stop
from .trajectory import TrajectoryLog, format_trajectory, load_trajectory, split_runs, to_spans
from .types import AgentResult, Budget, Plan, PlanStep, StepRecord, StopDecision
from .workflow import run_workflow

__all__ = [
    "Agent", "GIVE_UP", "SYSTEM", "format_summary", "load_tasks", "run_tasks", "score_trajectory", "summarize_scores",
    "AcmeHeuristic", "FakeLLM", "ScriptPolicy", "parse_task", "parse_faults", "with_faults", "Scratchpad",
    "clear_old_tool_results", "make_plan", "replan", "STOP_REASONS", "fingerprint", "result_hash", "should_stop",
    "TrajectoryLog", "format_trajectory", "load_trajectory", "split_runs", "to_spans", "AgentResult", "Budget",
    "Plan", "PlanStep", "StepRecord", "StopDecision", "run_workflow",
]
