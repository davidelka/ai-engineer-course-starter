"""Exercises 4 and 5: feed recorded hook events to your hook, exactly the way Claude Code does.

    python labs/05-coding-agents/hook_replay.py                     # all events, your mine.py
    python labs/05-coding-agents/hook_replay.py --impl reference    # the reference hooks
    python labs/05-coding-agents/hook_replay.py 04 09 15 --show     # some events, with full I/O

For every file in fixtures/hook_events/ it:
  1. makes a fresh copy of sample-service in a temp dir (with a fake .env), applies the
     event's _setup (to simulate the edit that just happened, for PostToolUse events),
  2. starts the hook as a separate process, writes the event JSON to its stdin, with
     CLAUDE_PROJECT_DIR set, just like Claude Code,
  3. reads exit code, stdout and stderr and says what Claude Code would do with them,
  4. compares with the expected outcome stored in the event (_expect).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

LAB = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(LAB))
SAMPLE = os.path.join(LAB, "sample-service")
EVENTS = os.path.join(LAB, "fixtures", "hook_events")


def _project(tmp: str, setup: dict | None) -> str:
    proj = os.path.join(tmp, "project")
    shutil.copytree(SAMPLE, proj, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"))
    with open(os.path.join(proj, ".env"), "w") as f:
        f.write("ACME_ADMIN_TOKEN=lab-fake-token-7f3a9c\n")
    os.makedirs(os.path.join(proj, ".claude"), exist_ok=True)
    with open(os.path.join(proj, ".claude", "settings.json"), "w") as f:
        f.write('{"permissions": {"deny": []}}\n')
    for rel, op in (setup or {}).items():
        path = os.path.join(proj, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if op.startswith("PREPEND:"):
            text = op[len("PREPEND:"):] + text
        elif op.startswith("REPLACE:"):
            old, new = op[len("REPLACE:"):].split("=>", 1)
            text = text.replace(old, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return proj


def _sub(obj, proj: str):
    if isinstance(obj, dict):
        return {k: _sub(v, proj) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sub(v, proj) for v in obj]
    if isinstance(obj, str):
        return obj.replace("__PROJECT__", proj)
    return obj


def outcome(event_name: str, code: int, stdout: str) -> str:
    """Name what Claude Code does with the hook's answer: deny / ask / allow / block / context / none / error."""
    if code == 2:
        return "deny" if event_name == "PreToolUse" else "block"
    if code != 0:
        return "error"
    if not stdout.strip():
        return "none"
    try:
        out = json.loads(stdout)
    except ValueError:
        return "context" if event_name != "PreToolUse" else "none"
    hso = out.get("hookSpecificOutput") or {}
    if hso.get("permissionDecision"):
        return hso["permissionDecision"]
    if out.get("decision") == "block":
        return "block"
    if hso.get("additionalContext"):
        return "context"
    return "none"


MEANING = {
    "deny": "the tool call is blocked; Claude sees the reason and must try something else",
    "ask": "the user is asked to approve (in a -p run with nobody to ask, the call is denied)",
    "allow": "the hook approves; permission deny/ask rules can still stop it",
    "none": "no opinion: the normal permission rules and mode decide",
    "block": "the tool already ran; the reason is shown to Claude next to the tool result",
    "context": "the tool already ran; the extra text is added to Claude's context",
    "error": "non-blocking error: Claude Code shows a hook error and the call goes ahead",
}


def replay(path: str, impl: str, show: bool) -> bool:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    expect, note, setup = raw.pop("_expect", None), raw.pop("_note", ""), raw.pop("_setup", None)
    with tempfile.TemporaryDirectory() as tmp:
        proj = _project(tmp, setup)
        event = _sub(raw, proj)
        code_str = (
            f"import sys; sys.path.insert(0, {REPO!r}); from repoguard.hookrunner import main; "
            f"main({impl!r}, lab_dir={LAB!r})"
        )
        env = {**os.environ, "CLAUDE_PROJECT_DIR": proj}
        p = subprocess.run([sys.executable, "-c", code_str], input=json.dumps(event), capture_output=True,
                           text=True, cwd=proj, env=env, timeout=180)
    got = outcome(event["hook_event_name"], p.returncode, p.stdout)
    ok = got == expect
    ti = event.get("tool_input", {})
    what = ti.get("command") or ti.get("file_path", "").replace(proj, "<project>")
    print(f"{'OK      ' if ok else 'MISMATCH'} {os.path.basename(path)[:-5]:26} {event['hook_event_name']:11} {event['tool_name']:5} {what[:60]}")
    print(f"         expected {expect}, got {got}: {MEANING.get(got, '')}")
    if note and (show or not ok):
        print(f"         why: {note}")
    if show or not ok:
        print(f"         exit code: {p.returncode}")
        if p.stdout.strip():
            print("         stdout: " + p.stdout.strip().replace(proj, "<project>")[:700])
        if p.stderr.strip():
            print("         stderr: " + p.stderr.strip().replace(proj, "<project>")[:400])
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="*", help="event number prefixes, e.g. 04 15")
    ap.add_argument("--impl", choices=["mine", "reference"], default="mine")
    ap.add_argument("--show", action="store_true", help="print stdin/stdout details for every event")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(EVENTS, "*.json")))
    if a.only:
        files = [f for f in files if any(os.path.basename(f).startswith(o) for o in a.only)]
    good = sum(replay(f, a.impl, a.show) for f in files)
    print(f"\n{good}/{len(files)} events behave as expected (impl: {a.impl})")
    sys.exit(0 if good == len(files) else 1)


if __name__ == "__main__":
    main()
