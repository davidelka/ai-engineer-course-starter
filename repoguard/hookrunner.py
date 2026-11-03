"""Turn the pure decision functions into a real Claude Code command hook.

Claude Code runs the hook command, writes one JSON event to its stdin and reads back:

  - exit 0 with a JSON object on stdout: a structured decision (hookSpecificOutput ...)
  - exit 0 with nothing on stdout: no opinion, the normal permission flow continues
  - exit 2: a blocking error; for PreToolUse the call is blocked and stderr goes to Claude
  - any other exit code: a non-blocking error; the call goes ahead (exit 1 is NOT a block)

handle() implements that contract and logs every decision to a JSONL file, so after a run
you can see what the agent tried and what the hook did. Policy on crashes:
PreToolUse fails closed (a crash blocks the call with exit 2), PostToolUse fails open.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from types import ModuleType


def load_impl(name: str, lab_dir: str | None = None) -> ModuleType:
    """'reference' -> repoguard.hooks; 'mine' -> the lab's mine.py (lab_dir goes on sys.path)."""
    if name == "reference":
        return importlib.import_module("repoguard.hooks")
    if lab_dir and lab_dir not in sys.path:
        sys.path.insert(0, lab_dir)
    return importlib.import_module("mine")


def _summary(event: dict) -> str:
    ti = event.get("tool_input") or {}
    for key in ("command", "file_path", "notebook_path", "path", "pattern"):
        if key in ti:
            return str(ti[key])[:300]
    return ""


def _log(log_path: str | None, event: dict, code: int, out: dict | None, err: str) -> None:
    if not log_path:
        return
    rec = {
        "ts": round(time.time(), 3),
        "event": event.get("hook_event_name"),
        "tool": event.get("tool_name"),
        "input": _summary(event),
        "exit": code,
    }
    if out:
        hso = out.get("hookSpecificOutput") or {}
        rec["decision"] = hso.get("permissionDecision") or out.get("decision") or ("context" if hso.get("additionalContext") else None)
        rec["reason"] = (hso.get("permissionDecisionReason") or out.get("reason") or hso.get("additionalContext") or "")[:300]
    if err:
        rec["stderr"] = err[:300]
    try:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def handle(raw: str, impl: ModuleType, project_dir: str | None = None, log_path: str | None = None) -> tuple[int, str, str]:
    """Process one hook invocation. Returns (exit code, stdout, stderr)."""
    try:
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError("not an object")
    except ValueError as e:
        return 1, "", f"repoguard: stdin is not a JSON object ({e})"
    project = project_dir or event.get("cwd") or os.getcwd()
    name = event.get("hook_event_name")
    out, code, err = None, 0, ""
    try:
        if name == "PreToolUse":
            out = impl.pre_tool_use(event, project)
        elif name == "PostToolUse":
            out = impl.post_tool_use(event, project)
    except NotImplementedError as e:
        code, err = 1, f"repoguard: {e} (not implemented yet, so the call is allowed)"
    except Exception as e:  # noqa: BLE001
        if name == "PreToolUse":
            code, err = 2, f"repoguard hook crashed ({type(e).__name__}: {e}); blocking the call to be safe"
        else:
            code, err = 1, f"repoguard hook crashed ({type(e).__name__}: {e})"
    _log(log_path, event, code, out, err)
    return code, (json.dumps(out) if out else ""), err


def main(impl_name: str = "reference", lab_dir: str | None = None, log_path: str | None = None) -> None:
    """Entry point for a hook script: read stdin, print the decision, exit with the right code."""
    impl = load_impl(impl_name, lab_dir)
    code, out, err = handle(sys.stdin.read(), impl, os.environ.get("CLAUDE_PROJECT_DIR"), log_path)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    sys.exit(code)
