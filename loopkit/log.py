"""The evidence log: one JSON object per line, appended as the loop runs.

Record types: "run" (header), "iteration" (everything the verifiers said), "checkpoint"
(a human decision), "summary" (stop reason, totals and the independent audit).
summarize() turns summaries into the numbers lesson 7 asks for: solved within k
iterations, false passes (claimed solved, failed the audit) and cost per solved task.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional


class EvidenceLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_records(paths: Iterable[Path]) -> list[dict]:
    out: list[dict] = []
    for p in paths:
        p = Path(p)
        files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
        for f in files:
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(json.loads(line))
    return out


def summarize(records: list[dict], max_k: Optional[int] = None) -> dict[str, dict]:
    """Per label: tasks, claimed solved, truly solved (claimed AND passed the audit), false passes,
    solved@k (truly solved within k iterations, as a fraction of tasks), cost per truly solved task."""
    groups: dict[str, list[dict]] = {}
    for r in records:
        if r.get("type") == "summary":
            groups.setdefault(r.get("label") or r.get("generator", "?"), []).append(r)
    out: dict[str, dict] = {}
    for label, runs in groups.items():
        n = len(runs)
        kmax = max_k or max((r["iterations"] for r in runs), default=1)
        true_runs = [r for r in runs if r["solved"] and r.get("audit_passed")]
        claimed = [r for r in runs if r["solved"]]
        cost = sum(r.get("cost_usd", 0.0) for r in runs)
        out[label] = {
            "tasks": n,
            "claimed": len(claimed),
            "truly_solved": len(true_runs),
            "false_passes": len(claimed) - len(true_runs),
            "solved_at": {k: sum(1 for r in true_runs if (r.get("solved_at") or 99) <= k) / n for k in range(1, kmax + 1)},
            "claimed_at": {k: sum(1 for r in claimed if (r.get("solved_at") or 99) <= k) / n for k in range(1, kmax + 1)},
            "mean_iterations": sum(r["iterations"] for r in runs) / n,
            "tokens": sum(r.get("tokens", 0) for r in runs),
            "cost_usd": cost,
            "cost_per_solved": cost / len(true_runs) if true_runs else None,
            "estimated_cost": any(r.get("estimated_cost") for r in runs),
            "stop_reasons": dict(Counter(r["stop_reason"] for r in runs)),
            "tamper_runs": sum(1 for r in runs if r.get("tamper_iterations")),
            "per_task": {r["task"]: (r["stop_reason"], r["iterations"], r.get("audit_passed")) for r in runs},
        }
    return out


def format_summary(summary: dict[str, dict]) -> str:
    lines: list[str] = []
    for label, s in summary.items():
        est = " (estimated: scripted generator, priced like Haiku 5.5)" if s["estimated_cost"] else ""
        cps = f"${s['cost_per_solved']:.5f}" if s["cost_per_solved"] is not None else "n/a (nothing truly solved)"
        lines += [
            f"== {label}",
            f"  tasks: {s['tasks']}   claimed solved: {s['claimed']}   truly solved (audit): {s['truly_solved']}"
            f"   FALSE PASSES: {s['false_passes']}",
            "  solved@k (true):    " + "  ".join(f"k={k}: {v:.0%}" for k, v in s["solved_at"].items()),
            "  solved@k (claimed): " + "  ".join(f"k={k}: {v:.0%}" for k, v in s["claimed_at"].items()),
            f"  mean iterations: {s['mean_iterations']:.2f}   tokens: {s['tokens']:,}   cost: ${s['cost_usd']:.5f}{est}",
            f"  cost per truly solved task: {cps}",
            "  stop reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(s["stop_reasons"].items())),
            f"  runs with tampering detected: {s['tamper_runs']}",
        ]
        for task, (reason, iters, ok) in sorted(s["per_task"].items()):
            mark = "audit OK" if ok else "audit FAIL"
            lines.append(f"    - {task}: {reason} after {iters} iteration(s), {mark}")
    return "\n".join(lines)
