"""Exercise 8: run Claude Code headless on a task, with or without project configuration, and score it.

    python labs/05-coding-agents/run_agent.py --task bugfix --variant bare
    python labs/05-coding-agents/run_agent.py --task bugfix --variant configured --config mine --hooks mine
    python labs/05-coding-agents/run_agent.py --task feature --variant configured --repeat 3
    python labs/05-coding-agents/run_agent.py --task bugfix --variant bare --dry-run   # show the command only

Each run: a fresh workspace (make_workspace.py), one `claude -p` call with the task prompt,
the full stream-json transcript saved in results/, then score_run.py on the workspace and
one line appended to results/runs.jsonl. `python labs/05-coding-agents/report.py` compares.

Both variants get the SAME command-line flags, so the only difference is what lives in the
repo: CLAUDE.md, .claude/settings.json (permissions + hooks) and the skill.

  --permission-mode acceptEdits   file edits in the workspace need no approval
  --allowedTools ...              the test / lint / git-read commands, for both variants
  --setting-sources project,local your ~/.claude settings and CLAUDE.md stay out of the run
  --max-budget-usd                hard cap per run (default 1.00)
  --no-session-persistence        lab runs do not clutter your session history

Cost: with Haiku a run typically costs cents, not dollars; the cap protects you anyway.
If you are logged in with a Claude subscription, total_cost_usd is Claude Code's estimate.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time

LAB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LAB)

from make_workspace import build  # noqa: E402
from score_run import print_report, record, score  # noqa: E402
from tasks import TASKS  # noqa: E402

ALLOWED = [
    "Bash(make test)", "Bash(make lint)", "Bash(make fmt)",
    "Bash(python -m pytest *)", "Bash(python3 -m pytest *)", "Bash(pytest *)",
    "Bash(python -m ruff *)", "Bash(python3 -m ruff *)", "Bash(ruff *)",
    "Bash(git diff *)", "Bash(git status *)", "Bash(git log *)",
]


def command(task: str, model: str, budget: float, sources: str) -> list[str]:
    cmd = [
        "claude", "-p", TASKS[task]["prompt"],
        "--output-format", "stream-json", "--verbose",
        "--model", model,
        "--permission-mode", "acceptEdits",
        "--max-budget-usd", f"{budget:.2f}",
        "--no-session-persistence",
        "--allowedTools", *ALLOWED,
    ]
    if sources:
        cmd += ["--setting-sources", sources]
    return cmd


def run_once(a: argparse.Namespace, i: int) -> dict | None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{a.task}-{a.variant}-{stamp}-{i}"
    ws = build(a.variant, a.config, a.hooks, name=name)
    cmd = command(a.task, a.model, a.budget, a.sources)
    print(f"\n=== run {i + 1}/{a.repeat}: {name}\nworkspace: {ws}")
    print("command:   " + " ".join(shlex.quote(c) if c != TASKS[a.task]["prompt"] else "<task prompt>" for c in cmd))
    if a.dry_run:
        return None
    os.makedirs(os.path.join(LAB, "results"), exist_ok=True)
    transcript = os.path.join(LAB, "results", f"{name}.jsonl")
    env = {**os.environ, "PATH": os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")}
    t0 = time.time()
    with open(transcript, "w", encoding="utf-8") as out:
        p = subprocess.run(cmd, cwd=ws, stdout=out, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, env=env)
    print(f"claude exited {p.returncode} after {time.time() - t0:.0f}s; transcript: {transcript}")
    if p.stderr.strip():
        print("stderr: " + p.stderr.strip()[-500:])
    rec = score(a.task, ws, transcript)
    rec.update({"variant": a.variant, "config": a.config if a.variant == "configured" else None,
                "hooks": a.hooks if a.variant == "configured" else None, "model_flag": a.model,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "exit_code": p.returncode})
    print_report(rec)
    record(rec)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", choices=sorted(TASKS), required=True)
    ap.add_argument("--variant", choices=["bare", "configured"], required=True)
    ap.add_argument("--config", choices=["mine", "reference"], default="mine")
    ap.add_argument("--hooks", choices=["mine", "reference"], default="mine")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--budget", type=float, default=1.0, help="max USD per run (claude --max-budget-usd)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--sources", default="project,local", help="--setting-sources value; '' to load your user settings too")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and shutil.which("claude") is None:
        sys.exit("claude is not on PATH. Install Claude Code first: https://code.claude.com/docs/en/setup")
    for i in range(a.repeat):
        run_once(a, i)


if __name__ == "__main__":
    main()
