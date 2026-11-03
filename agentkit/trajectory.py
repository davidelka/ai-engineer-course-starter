"""The trajectory log: one JSON object per line, appended while the agent runs.

Record types, in the order they appear in a run:
  run      header: run_id, task, model, mode, budget, tools offered
  plan     plan mode: the plan (and every replan, with the reason)
  confirm  a side-effect call was shown to a human: approved or not
  step     one model call: the model's text (its visible reasoning), the tool calls
           (name, arguments, fingerprint), the results (error flag, hash, text cut to
           600 chars), tokens, cost, timing, and the stop policy's decision
  trim     old tool results were cleared (memory)
  stop     the end: stop reason, totals, the final text

Several runs can share one file (an evaluation writes one run per task); split_runs()
groups them by run_id. to_spans() converts a run into obskit span dicts (lesson 22),
so `python -m obskit.viewer` can draw it as a waterfall.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, Optional, Union


class TrajectoryLog:
    """Keeps every record in memory and, if a path is given, appends it to a JSONL file."""

    def __init__(self, path: Optional[Union[str, Path]] = None, run_id: str = ""):
        self.path = Path(path) if path else None
        self.run_id = run_id
        self.records: list[dict] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> dict:
        record = {"run_id": self.run_id, "ts": round(time.time() * 1000, 1), **record}
        self.records.append(record)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record


def load_trajectory(path: Union[str, Path]) -> list[dict]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def split_runs(records: Iterable[dict]) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {}
    for r in records:
        runs.setdefault(r.get("run_id", ""), []).append(r)
    return runs


def _short(s, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def format_trajectory(records: list[dict], width: int = 110) -> str:
    """A readable transcript of ONE run, for the terminal."""
    lines: list[str] = []
    for r in records:
        t = r.get("type")
        if t == "run":
            b = r.get("budget", {})
            lines.append(f"RUN {r.get('task_id') or r.get('run_id')}  model={r.get('model')}  mode={r.get('mode')}  "
                         f"budget: steps<={b.get('max_steps')} cost<={b.get('max_cost_usd')} "
                         f"tokens<={b.get('max_tokens')} time<={b.get('max_seconds')}")
            lines.append(f"  TASK: {_short(r.get('task', ''), width)}")
        elif t == "plan":
            tag = f"REPLAN #{r.get('revision')} ({r.get('reason')})" if r.get("revision") else "PLAN"
            lines.append(f"  {tag}  tokens={r.get('tokens')} cost=${r.get('cost_usd', 0):.5f}")
            for s in (r.get("plan") or {}).get("steps", []):
                lines.append(f"    {s.get('id')}. {_short(s.get('action', ''), 80)}"
                             f"{' [' + s['tool'] + ']' if s.get('tool') else ''}")
        elif t == "confirm":
            c = r.get("call", {})
            mark = "APPROVED" if r.get("approved") else "DECLINED"
            taint = "  (untrusted text was read earlier in this run)" if r.get("tainted") else ""
            lines.append(f"  confirm {mark}: {c.get('name')}({_short(json.dumps(c.get('arguments', {})), 80)}){taint}")
        elif t == "step":
            lines.append(f"  step {r['n']}  tokens={r.get('tokens_in', 0)}+{r.get('tokens_out', 0)}  "
                         f"cost=${r.get('cost_usd', 0):.5f}  total=${r.get('cum_cost_usd', 0):.5f}  "
                         f"{r.get('elapsed_s', 0):.2f}s")
            if r.get("thought"):
                lines.append(f"    think: {_short(r['thought'], width)}")
            for c, res in zip(r.get("calls", []), r.get("results", [])):
                mark = "ERR" if res.get("is_error") else "ok "
                lines.append(f"    act:   {c['name']}({_short(json.dumps(c.get('arguments', {}), ensure_ascii=False), 70)})"
                             f"  #{c.get('fp')}")
                lines.append(f"    obs:   {mark} {_short(res.get('text', ''), width - 12)}")
            if r.get("final"):
                lines.append(f"    final: {_short(r.get('text', ''), width)}")
            d = r.get("decision", {})
            lines.append(f"    policy -> {d.get('reason')}{': ' + d['detail'] if d.get('detail') and d.get('reason') != 'continue' else ''}")
        elif t == "trim":
            lines.append(f"  memory: cleared {r.get('cleared')} old tool result(s), kept the last {r.get('keep')}")
        elif t == "stop":
            lines.append(f"STOP {r.get('reason')}  ({r.get('detail', '')})")
            lines.append(f"  steps={r.get('steps')} tool_calls={r.get('tool_calls')} errors={r.get('errors')} "
                         f"tokens={r.get('input_tokens')}+{r.get('output_tokens')} cost=${r.get('cost_usd', 0):.5f}"
                         f"{' (estimated)' if r.get('estimated_cost') else ''} time={r.get('elapsed_s', 0):.2f}s")
            lines.append(f"  ANSWER: {_short(r.get('text', ''), 400)}")
    return "\n".join(lines)


def to_spans(records: list[dict], service: str = "agentkit") -> list[dict]:
    """One run -> obskit span dicts: invoke_agent root, a chat span per step, an
    execute_tool span per call. Ids are derived from run_id, so they are stable."""
    run = next((r for r in records if r.get("type") == "run"), None)
    stop = next((r for r in records if r.get("type") == "stop"), None)
    if run is None:
        return []
    rid = (run.get("run_id") or "0").replace("-", "")
    trace_id = (rid * 4)[:32].ljust(32, "0")
    root_id = (rid + "0" * 16)[:16]
    t0 = run.get("ts", 0.0)
    t_end = stop.get("ts", t0) if stop else max((r.get("ts", t0) for r in records), default=t0)

    def sid(n: int, k: int) -> str:
        return format((n * 1000 + k + 1) & 0xFFFFFFFFFFFF, "016x")

    spans = [{
        "trace_id": trace_id, "span_id": root_id, "parent_id": None,
        "name": f"invoke_agent {run.get('agent', 'agent')}", "kind": "INTERNAL",
        "start_ms": t0, "end_ms": t_end, "duration_ms": round(t_end - t0, 3),
        "status": "OK" if (stop or {}).get("reason") in ("final_answer", "gave_up") else "ERROR",
        "status_message": (stop or {}).get("detail", ""),
        "attributes": {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": run.get("agent", "agent"),
                       "obskit.span.type": "agent", "agentkit.stop_reason": (stop or {}).get("reason", ""),
                       "agentkit.task_id": run.get("task_id", ""), "obskit.cost_usd": (stop or {}).get("cost_usd", 0.0)},
        "events": [], "links": [], "service": service,
    }]
    for r in records:
        if r.get("type") != "step":
            continue
        n = r["n"]
        s0, s1 = r.get("t_start", r.get("ts", t0)), r.get("t_model_end", r.get("ts", t0))
        spans.append({
            "trace_id": trace_id, "span_id": sid(n, 0), "parent_id": root_id, "name": f"chat {run.get('model')}",
            "kind": "CLIENT", "start_ms": s0, "end_ms": s1, "duration_ms": round(s1 - s0, 3), "status": "OK",
            "status_message": "",
            "attributes": {"gen_ai.operation.name": "chat", "obskit.span.type": "llm",
                           "gen_ai.request.model": run.get("model"), "gen_ai.usage.input_tokens": r.get("tokens_in", 0),
                           "gen_ai.usage.output_tokens": r.get("tokens_out", 0), "obskit.cost_usd": r.get("cost_usd", 0.0),
                           "agentkit.step": n},
            "events": [], "links": [], "service": service,
        })
        for k, (c, res) in enumerate(zip(r.get("calls", []), r.get("results", [])), start=1):
            a, b = res.get("t_start", s1), res.get("t_end", s1)
            spans.append({
                "trace_id": trace_id, "span_id": sid(n, k), "parent_id": root_id, "name": f"execute_tool {c['name']}",
                "kind": "INTERNAL", "start_ms": a, "end_ms": b, "duration_ms": round(b - a, 3),
                "status": "ERROR" if res.get("is_error") else "OK",
                "status_message": res.get("text", "")[:200] if res.get("is_error") else "",
                "attributes": {"gen_ai.operation.name": "execute_tool", "obskit.span.type": "tool",
                               "gen_ai.tool.name": c["name"], "gen_ai.tool.call.id": c.get("id", ""),
                               "agentkit.fingerprint": c.get("fp", ""), "agentkit.step": n},
                "events": [], "links": [], "service": service,
            })
    return spans
