"""One multi-agent run = many agent runs. This module keeps them together and adds them up.

Every agent (router, supervisor, worker, synthesizer, critic ...) leaves a normal agentkit
trajectory: run, step(s), stop records. A multi-agent run is a TREE of such trajectories,
linked by two extra fields that multikit adds to each "run" header record:

    role            "coordinator" (router, supervisor, triage, planner, synthesizer, critic)
                    or "worker" (the specialists that do the domain work)
    parent_run_id   the run_id of the agent that started this one (None for the root)

LLM calls that are not agent loops (a router classification, a synthesis call) are logged
as a tiny trajectory too (llm_call_records), so EVERY token has an owner.

    aggregate_runs(records)    per-agent tokens, cost, calls, time; coordination share;
                               wall time vs the sum of agent time (= parallelism).
                               Reference for lesson 18, exercise 6 (mine.py).
    merge_for_scoring(...)     one flat trajectory for agentkit.score_trajectory, so a
                               multi-agent run is scored against the SAME gold as a single agent.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

COORDINATION_ROLES = ("coordinator",)
LOCAL_TOOLS = ("note",)
ROUTING_TOOL_PREFIXES = ("delegate_to_", "transfer_to_")


@dataclass
class AgentRun:
    agent: str
    role: str  # "coordinator" | "worker"
    records: list[dict]
    parent_run_id: Optional[str] = None
    text: str = ""
    stop_reason: str = ""

    @property
    def run_id(self) -> str:
        return self.records[0].get("run_id", "") if self.records else ""

    def stop(self) -> dict:
        return next((r for r in reversed(self.records) if r.get("type") == "stop"), {})

    @property
    def cost_usd(self) -> float:
        return float(self.stop().get("cost_usd", 0.0) or 0.0)

    @property
    def tokens(self) -> int:
        s = self.stop()
        return int(s.get("input_tokens", 0) or 0) + int(s.get("output_tokens", 0) or 0)


@dataclass
class MultiResult:
    """What every pattern returns. text = the answer the user sees."""

    pattern: str
    text: str
    stop_reason: str
    runs: list[AgentRun] = field(default_factory=list)
    elapsed_s: float = 0.0
    task_id: str = ""
    info: dict[str, Any] = field(default_factory=dict)  # pattern-specific: route decision, handoffs, rounds ...

    @property
    def records(self) -> list[dict]:
        out: list[dict] = []
        for r in self.runs:
            out += r.records
        return out

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.runs)

    @property
    def tokens(self) -> int:
        return sum(r.tokens for r in self.runs)

    @property
    def estimated(self) -> bool:
        return any(r.stop().get("estimated_cost") for r in self.runs)

    def save(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for rec in self.records:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def annotate(records: list[dict], *, role: str, parent_run_id: Optional[str], agent: Optional[str] = None,
             task_id: str = "") -> list[dict]:
    """Add role / parent_run_id (and the multi-agent task id) to the run header, in place."""
    for r in records:
        if r.get("type") == "run":
            r["role"] = role
            r["parent_run_id"] = parent_run_id
            if agent:
                r["agent"] = agent
            if task_id:
                r["multi_task_id"] = task_id
            break
    return records


def agent_run(name: str, role: str, result, parent_run_id: Optional[str] = None, task_id: str = "") -> AgentRun:
    """agentkit AgentResult -> AgentRun (annotates its records)."""
    annotate(result.records, role=role, parent_run_id=parent_run_id, agent=name, task_id=task_id)
    return AgentRun(name, role, result.records, parent_run_id, result.text, result.stop_reason)


def llm_call_records(agent: str, role: str, *, input_tokens: int, output_tokens: int, cost_usd: float,
                     elapsed_s: float, text: str, model: str = "?", parent_run_id: Optional[str] = None,
                     estimated: bool = False, task_id: str = "", t0_ms: Optional[float] = None,
                     calls: int = 1) -> list[dict]:
    """A plain LLM call (no tools, no loop) as a 3-record trajectory, so it is counted like an agent."""
    rid = uuid.uuid4().hex[:16]
    t1 = time.time() * 1000
    t0 = t0_ms if t0_ms is not None else t1 - elapsed_s * 1000
    head = {"run_id": rid, "ts": round(t0, 1), "type": "run", "agent": agent, "role": role,
            "parent_run_id": parent_run_id, "model": model, "mode": "llm_call", "task": "", "tools": []}
    if task_id:
        head["multi_task_id"] = task_id
    step = {"run_id": rid, "ts": round(t1, 1), "type": "step", "n": 1, "t_start": round(t0, 1),
            "t_model_end": round(t1, 1), "tokens_in": input_tokens, "tokens_out": output_tokens, "cost_usd": cost_usd,
            "calls": [], "results": [], "final": True, "text": text, "model_calls": calls}
    stop = {"run_id": rid, "ts": round(t1, 1), "type": "stop", "reason": "final_answer", "detail": "", "steps": 1,
            "tool_calls": 0, "errors": 0, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": cost_usd, "estimated_cost": estimated, "elapsed_s": round(elapsed_s, 3), "text": text}
    return [head, step, stop]


# ---------------------------------------------------------------- exercise 6 reference
def aggregate_runs(records: list[dict]) -> dict:
    """See labs/18-multi-agent/mine.py for the exact contract (this is the reference)."""
    runs: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        runs[r.get("run_id", "")].append(r)
    per: dict[str, dict] = {}
    roles: dict[str, str] = {}
    coord_cost = 0.0
    t_min, t_max = None, None
    for rid, recs in runs.items():
        head = next((x for x in recs if x.get("type") == "run"), {})
        stop = next((x for x in reversed(recs) if x.get("type") == "stop"), {})
        name = head.get("agent", "?")
        role = head.get("role", "worker")
        roles.setdefault(name, role)
        a = per.setdefault(name, {"role": role, "runs": 0, "steps": 0, "tool_calls": 0, "input_tokens": 0,
                                  "output_tokens": 0, "cost_usd": 0.0, "elapsed_s": 0.0})
        a["runs"] += 1
        steps = [x for x in recs if x.get("type") == "step"]
        a["steps"] += len(steps)
        a["tool_calls"] += sum(1 for s in steps for c in s.get("calls", []) if c.get("name") not in LOCAL_TOOLS)
        a["input_tokens"] += int(stop.get("input_tokens", 0) or 0)
        a["output_tokens"] += int(stop.get("output_tokens", 0) or 0)
        cost = float(stop.get("cost_usd", 0.0) or 0.0)
        a["cost_usd"] += cost
        a["elapsed_s"] += float(stop.get("elapsed_s", 0.0) or 0.0)
        if role in COORDINATION_ROLES:
            coord_cost += cost
        for x in recs:
            ts = x.get("ts")
            if ts is None:
                continue
            t_min = ts if t_min is None else min(t_min, ts)
            t_max = ts if t_max is None else max(t_max, ts)
    total_cost = sum(a["cost_usd"] for a in per.values())
    total_tokens = sum(a["input_tokens"] + a["output_tokens"] for a in per.values())
    for a in per.values():
        a["tokens"] = a["input_tokens"] + a["output_tokens"]
        a["cost_share"] = a["cost_usd"] / total_cost if total_cost else 0.0
    wall = (t_max - t_min) / 1000 if t_min is not None else 0.0
    agent_s = sum(a["elapsed_s"] for a in per.values())
    return {
        "agents": per,
        "runs": len(runs),
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "coordination_cost_usd": coord_cost,
        "coordination_share": coord_cost / total_cost if total_cost else 0.0,
        "wall_s": wall,
        "agent_s": agent_s,
        "parallelism": agent_s / wall if wall > 0 else 1.0,
    }


def format_attribution(agg: dict, estimated: bool = False) -> str:
    est = "  (estimated tokens)" if estimated else ""
    lines = [f"  agents: {len(agg['agents'])}  runs: {agg['runs']}  tokens: {agg['total_tokens']:,}  "
             f"cost: ${agg['total_cost_usd']:.5f}{est}",
             f"  coordination share of cost: {agg['coordination_share']:.0%}   wall {agg['wall_s']:.2f}s vs "
             f"agent time {agg['agent_s']:.2f}s (parallelism x{agg['parallelism']:.2f})"]
    for name, a in sorted(agg["agents"].items(), key=lambda kv: -kv[1]["cost_usd"]):
        lines.append(f"    {name:<14} {a['role']:<11} runs={a['runs']:<3} steps={a['steps']:<3} calls={a['tool_calls']:<3} "
                     f"tokens={a['tokens']:>7,}  ${a['cost_usd']:.5f}  {a['cost_share']:>4.0%}")
    return "\n".join(lines)


# ---------------------------------------------------------------- scoring a tree with the lesson 15 scorer
def merge_for_scoring(result: MultiResult) -> list[dict]:
    """All step records of all agents (routing tools removed) + one stop record with the user-facing
    text and the TOTAL tokens and cost. agentkit.score_trajectory can then score it unchanged:
    required/forbidden tools, the filed request, facts in the answer, evidence conflicts."""
    steps: list[dict] = []
    n = 0
    for run in result.runs:
        for r in run.records:
            if r.get("type") != "step":
                continue
            pairs = [(c, x) for c, x in zip(r.get("calls", []), r.get("results", []))
                     if not c.get("name", "").startswith(ROUTING_TOOL_PREFIXES)]
            n += 1
            steps.append({**r, "n": n, "agent": run.agent, "calls": [c for c, _ in pairs],
                          "results": [x for _, x in pairs]})
    tin = sum(int(r.stop().get("input_tokens", 0) or 0) for r in result.runs)
    tout = sum(int(r.stop().get("output_tokens", 0) or 0) for r in result.runs)
    head = {"type": "run", "run_id": f"multi-{result.task_id}", "agent": result.pattern, "task_id": result.task_id}
    stop = {"type": "stop", "run_id": head["run_id"], "task_id": result.task_id, "reason": result.stop_reason,
            "text": result.text, "input_tokens": tin, "output_tokens": tout, "cost_usd": result.cost_usd,
            "estimated_cost": result.estimated}
    return [head] + steps + [stop]
