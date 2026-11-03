"""Reference versions of exercises 4 and 5: the decision logic of a PreToolUse hook and a
PostToolUse hook for Claude Code. Try not to read this before your own versions pass.

Claude Code runs a command hook with one JSON object on stdin, for example:

    {"session_id": "...", "transcript_path": "...", "cwd": "/home/me/proj",
     "permission_mode": "default", "hook_event_name": "PreToolUse",
     "tool_name": "Bash", "tool_input": {"command": "cat .env"}, "tool_use_id": "toolu_..."}

These functions take that object (already parsed) and return the JSON object the hook
should print, or None for "no opinion". repoguard.hookrunner does the stdin/stdout part.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable

from repoguard.bash_rules import check_bash
from repoguard.paths import protected_write_reason, secret_reason

WRITE_TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
READ_TOOLS = {"Read": "file_path", "Grep": "path", "Glob": "path"}
MAX_FEEDBACK = 1500

Runner = Callable[[list[str], str], tuple[int, str]]


def check_path(file_path: str, project_dir: str, write: bool) -> tuple[str, str] | None:
    """("deny", reason) or None for a file an agent wants to read (write=False) or change."""
    if not file_path:
        return None
    p = os.path.expanduser(file_path)
    if not os.path.isabs(p):
        p = os.path.join(project_dir, p)
    requested = os.path.normpath(p)
    resolved = os.path.realpath(p)
    project = os.path.realpath(project_dir)
    for candidate in (requested, resolved):
        r = secret_reason(candidate)
        if r:
            return "deny", r
    if not write:
        return None
    inside = resolved == project or resolved.startswith(project + os.sep)
    if not inside:
        return "deny", f"{file_path} is outside the project directory"
    rel = os.path.relpath(resolved, project).replace(os.sep, "/")
    r = protected_write_reason(rel)
    if r:
        return "deny", r
    return None


def _decision(decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"repoguard: {reason}",
        }
    }


def pre_tool_use(event: dict, project_dir: str) -> dict | None:
    """The PreToolUse hook's output for one event, or None to let the normal flow decide."""
    if event.get("hook_event_name") != "PreToolUse":
        return None
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}
    verdict = None
    if tool == "Bash":
        verdict = check_bash(ti.get("command", ""))
    elif tool in WRITE_TOOLS:
        verdict = check_path(ti.get(WRITE_TOOLS[tool], ""), project_dir, write=True)
    elif tool in READ_TOOLS:
        verdict = check_path(ti.get(READ_TOOLS[tool], "") or "", project_dir, write=False)
    if verdict is None:
        return None
    return _decision(*verdict)


def run_command(cmd: list[str], cwd: str) -> tuple[int, str]:
    """Run a command and return (exit code, combined stdout and stderr)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=100)
    except subprocess.TimeoutExpired:
        return 124, f"timed out: {' '.join(cmd)}"
    return p.returncode, (p.stdout + p.stderr).strip()


def _tail(text: str, n: int = MAX_FEEDBACK) -> str:
    return text if len(text) <= n else "..." + text[-n:]


def post_tool_use(event: dict, project_dir: str, run: Runner = run_command) -> dict | None:
    """After an edit to a .py file: run ruff, then the related tests. Block with feedback on failure."""
    if event.get("hook_event_name") != "PostToolUse":
        return None
    if event.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return None
    path = (event.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return None
    project = os.path.realpath(project_dir)
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(project, path))
    if not full.startswith(project + os.sep):
        return None
    rel = os.path.relpath(full, project).replace(os.sep, "/")

    code, out = run([sys.executable, "-m", "ruff", "check", "--quiet", "--output-format", "concise", rel], project)
    if code != 0:
        return {"decision": "block", "reason": f"ruff check failed for {rel}:\n{_tail(out)}"}

    name = rel.rsplit("/", 1)[-1]
    if rel.startswith("tests/") and name.startswith("test_"):
        target = rel
    elif rel.startswith("app/"):
        candidate = f"tests/test_{name[:-3]}.py"
        target = candidate if os.path.exists(os.path.join(project, candidate)) else "tests"
    else:
        return None
    code, out = run([sys.executable, "-m", "pytest", "-x", "-q", "--tb=short", target], project)
    if code not in (0, 5):  # 5 = no tests collected
        return {
            "decision": "block",
            "reason": f"tests failed after editing {rel} (python -m pytest -x -q --tb=short {target}):\n{_tail(out)}",
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"repoguard: ruff clean and tests passed for {rel} ({target})",
        }
    }
