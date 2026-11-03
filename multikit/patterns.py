"""Build any pattern with fake or live models, run a task set, score it, attribute failures.

    run = build("supervisor", "fake", requests_db=tmp/"r.db", confirm=lambda c: True)
    res = run.run(task_text, task_id="x01")                 # -> MultiResult
    score = score_multi(res, gold)                          # agentkit.score_trajectory on the merged tree
    blame = attribute_failure(res, score, gold)             # which agent caused the failure

Patterns: single | router | router2 (multi-route) | supervisor | handoff.
model: "fake" (deterministic heuristics, free) or a live llmkit spec such as
"anthropic:claude-haiku-5-5" (every agent uses the same model).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Iterable, Optional

from agentkit import FakeLLM, score_trajectory

from .attribution import MultiResult, agent_run, merge_for_scoring
from .domains import DOMAINS
from .fake import ComboHeuristic, HandoffHeuristic, RouterHeuristic, SpecialistHeuristic, SupervisorHeuristic
from .handoff import HandoffRunner, make_handoff_brief
from .router import Router, decide_route
from .specialists import SPECIALISTS, make_single, make_specialist
from .supervisor import Supervisor

PATTERNS = ("single", "router", "router2", "supervisor", "handoff")


class _Single:
    def __init__(self, agent):
        self.agent = agent

    def run(self, task: str, *, task_id: str = "") -> MultiResult:
        res = self.agent.run(task, task_id=task_id)
        return MultiResult("single", res.text, res.stop_reason, [agent_run("single", "worker", res, None, task_id)],
                           res.elapsed_s, task_id, {})


def _live(spec: str):
    from llmkit import LLM, load_dotenv
    load_dotenv(str(Path(__file__).resolve().parents[1] / ".env"))
    return LLM(spec)


def build(pattern: str, model: str = "fake", *, requests_db: Optional[Path] = None, confirm=None,
          faults: Optional[dict] = None, decide: Callable = decide_route, brief: Callable = make_handoff_brief,
          verify: str = "none", parallel: bool = True, worker_faults: Optional[dict] = None,
          fault_times: Optional[int] = None, threshold: float = 0.6, lossy: bool = False, naive_docs: bool = False):
    live = None if model == "fake" else _live(model)

    def llm(policy):
        return live if live is not None else FakeLLM(policy)

    def worker(d: str):
        return make_specialist(d, llm(SpecialistHeuristic(d, naive_docs=naive_docs)), requests_db=requests_db,
                               confirm=confirm, faults=faults)

    if pattern == "single":
        return _Single(make_single(llm(ComboHeuristic(naive_docs=naive_docs)), requests_db=requests_db,
                                   confirm=confirm, faults=faults))
    if pattern in ("router", "router2"):
        return Router(llm(RouterHeuristic()), worker, threshold=threshold, max_targets=1 if pattern == "router" else 2,
                      decide=decide)
    if pattern == "supervisor":
        return Supervisor(llm(SupervisorHeuristic(parallel=parallel, verify=verify != "none")), worker, verify=verify,
                          worker_faults=worker_faults or {}, fault_times=fault_times)
    if pattern == "handoff":
        return HandoffRunner(lambda role: llm(HandoffHeuristic(role, lossy=lossy, naive_docs=naive_docs)),
                             requests_db=requests_db, confirm=confirm, faults=faults, brief=brief)
    raise ValueError(f"unknown pattern {pattern!r}; choose from {PATTERNS}")


def score_multi(result: MultiResult, gold: dict, score: Callable = score_trajectory) -> dict:
    s = score(merge_for_scoring(result), gold, result.task_id)
    s["agents"] = len({r.agent for r in result.runs})
    s["agent_runs"] = len(result.runs)
    s["elapsed_s"] = result.elapsed_s
    return s


TOOL_OWNER = {t: d for d, sp in SPECIALISTS.items() for t in sp.tools if t != "read_document"}


def attribute_failure(result: MultiResult, score: dict, gold: dict) -> list[str]:
    """Best-effort blame for a failed task: which agent (or which coordination step) caused each reason."""
    if score.get("success"):
        return []
    ran = {r.agent for r in result.runs}
    workers = [r for r in result.runs if r.role == "worker"]
    out = []
    want = gold.get("domains") or []
    choice = result.info.get("choice")
    if choice is not None:
        if choice.get("action") == "clarify" and gold.get("outcome") != "clarify":
            out.append("router: asked a clarifying question instead of routing")
        missing = [d for d in want if d not in (choice.get("targets") or [])]
        if choice.get("action") == "route" and missing:
            out.append(f"router: did not route to {', '.join(missing)}")
            # everything downstream of a missed route is the router's fault: report the request outcome only
            return out + [f"router: {r}" for r in score.get("reasons", []) if r.startswith(("expected", "a request was"))]
    for reason in score.get("reasons", []):
        if reason.startswith("missing tool: "):
            t = reason.split(": ", 1)[1]
            d = TOOL_OWNER.get(t)
            if result.pattern != "single" and d and d not in ran:
                out.append(f"coordination: {d} never ran ({reason})")
            else:
                out.append(f"{d if result.pattern != 'single' else 'single'}: {reason}")
        elif reason.startswith("answer lacks"):
            fact = reason.split("lacks ", 1)[1]
            needle = fact.strip("'\"[]").split("', '")[0].lower()
            found_in = [w.agent for w in workers if needle and needle in (w.text or "").lower()]
            if found_in and result.pattern in ("supervisor", "router", "router2", "handoff"):
                out.append(f"coordination: {found_in[0]} found it but the final answer dropped it ({reason})")
            else:
                out.append(f"{workers[-1].agent if workers else 'coordinator'}: {reason}")
        elif "request" in reason or "forbidden" in reason:
            filers = [r.agent for r in result.runs for rec in r.records if rec.get("type") == "step"
                      for c, x in zip(rec.get("calls", []), rec.get("results", []))
                      if c.get("name") == "create_access_request" and not x.get("is_error")]
            out.append(f"{filers[0] if filers else 'it_access'}: {reason}")
        else:
            out.append(f"{result.pattern}: {reason}")
    return list(dict.fromkeys(out))


def run_set(pattern: str, tasks: Iterable[dict], model: str = "fake", *, score: Callable = score_trajectory,
            log_path: Optional[Path] = None, budget_usd: Optional[float] = None, spent: Optional[list] = None,
            **kw) -> list[tuple[dict, MultiResult, dict]]:
    """Every task with fresh agents and a fresh requests store; side effects auto-approved (the eval plays the human)."""
    out = []
    spent = spent if spent is not None else [0.0]
    with tempfile.TemporaryDirectory() as tmp:
        for t in tasks:
            if budget_usd is not None and spent[0] >= budget_usd:
                break
            runner = build(pattern, model, requests_db=Path(tmp) / f"{pattern}-{t['id']}.db",
                           confirm=lambda c: True, **kw)
            res = runner.run(t["task"], task_id=t["id"])
            spent[0] += res.cost_usd
            if log_path:
                res.save(log_path)
            s = score_multi(res, t["gold"], score)
            s["blame"] = attribute_failure(res, s, t["gold"])
            out.append((t, res, s))
    return out
