"""Your code for lesson 5. Each part is checked by tests in ./tests.

Reference versions live in repoguard/ (bash_rules.py, hooks.py, injection.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/05-coding-agents/tests

Your hook functions run for real: make_workspace.py --hooks mine generates a
.claude/hooks/guard.py that imports this file, so Claude Code calls pre_tool_use and
post_tool_use below on every tool call in the configured workspace.
"""

from __future__ import annotations

import os  # noqa: F401  (you will likely need it)
import re  # noqa: F401
import sys  # noqa: F401
from typing import Callable

from repoguard.hooks import run_command
from repoguard.paths import protected_write_reason, secret_reason  # noqa: F401  (helpers you may use)
from repoguard.shell import parse, program  # noqa: F401

Verdict = tuple[str, str]  # ("deny" | "ask", reason)


# ------------------------------------------------------------------ exercise 3
def check_bash(command: str) -> Verdict | None:
    """Decide whether a Bash command an agent wants to run is dangerous.

    Returns ("deny", reason), ("ask", reason) or None; reason is a short, non-empty
    sentence for Claude. Every part of the command counts: chained commands (&& || ; &),
    every stage of a pipe, $(...), backticks, bash -c '...', eval, and wrappers such as
    timeout or env VAR=1. repoguard.shell.parse/program (imported above) understand this.

    DENY: sudo/doas/su; recursive rm of a dangerous target (/, /*, ~, ~/..., ., ./, ..,
      ../, *, ./*, $HOME, $HOME/..., a one-component absolute path like /etc, .git or
      inside it), while `rm -rf build` is fine; force push (--force*, -f, a +refspec);
      git reset --hard; git clean with force; curl/wget piped into an interpreter;
      curl/wget uploading a local file; any argument that is a secret path (secret_reason,
      including the value of --name=value) or /proc/<x>/environ; dumping the environment
      (bare printenv, or env with no command); DROP TABLE/DATABASE/SCHEMA or TRUNCATE TABLE
      (any case); mkfs*, dd of=/dev/..., shred.
    ASK (only when nothing is denied): git push; installing a dependency (pip install,
      uv add, poetry add, npm/pnpm/yarn add or install <pkg>; a bare `npm install` is
      fine); any other curl or wget.
    Everything else: None.

    Stuck? HINTS.md -> check_bash
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement check_bash")


# ------------------------------------------------------------------ exercise 4
def check_path(file_path: str, project_dir: str, write: bool) -> Verdict | None:
    """Decide whether the agent may read (write=False) or change (write=True) a file.

    Returns ("deny", reason) or None. The path is judged as the OS will see it: ~ expanded,
    relative paths taken from project_dir, symlinks and .. followed.
      - Secret files (secret_reason) are denied for reading and for writing, whether the
        requested path or the real path is the secret.
      - Writes are denied outside project_dir, and inside it on protected paths
        (protected_write_reason on the project-relative path: .git/..., .claude/settings.json,
        .claude/hooks/..., lock files).
      - Reads outside the project are not this hook's business: None.
      - An empty file_path: None.

    Stuck? HINTS.md -> check_path
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement check_path")


def pre_tool_use(event: dict, project_dir: str) -> dict | None:
    """The PreToolUse hook: map one Claude Code event to the JSON the hook prints, or None.

    `event` is the parsed stdin object, e.g.
        {"hook_event_name": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "cat .env"}, "cwd": "...", "session_id": "...", ...}

    Bash commands go through check_bash. Edit, Write, MultiEdit (file_path) and NotebookEdit
    (notebook_path) go through check_path as writes; Read (file_path), Grep and Glob (path,
    may be missing) as reads. Other events, other tools, or no verdict: None.
    With a verdict (decision, reason) return exactly:
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                "permissionDecision": decision,
                                "permissionDecisionReason": "repoguard: " + reason}}

    Stuck? HINTS.md -> pre_tool_use
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement pre_tool_use")


# ------------------------------------------------------------------ exercise 5
Runner = Callable[[list[str], str], tuple[int, str]]


def post_tool_use(event: dict, project_dir: str, run: Runner = run_command) -> dict | None:
    """The PostToolUse hook: after the agent edits a Python file, lint it and run its tests.

    `run(cmd, cwd)` runs a command and returns (exit code, combined output); always call it
    with cwd=project_dir. The tests check the exact commands:
        [sys.executable, "-m", "ruff", "check", "--quiet", "--output-format", "concise", rel]
        [sys.executable, "-m", "pytest", "-x", "-q", "--tb=short", target]
    rel is the file relative to project_dir with forward slashes ("app/policy.py").
    Acts only on PostToolUse of Edit/Write/MultiEdit for a .py file inside project_dir;
    otherwise None. Target: a tests/test_*.py file tests itself; app/<module>.py is tested by
    tests/test_<module>.py if it exists, else by "tests"; any other file: None after lint.
    pytest exit 0 or 5 (no tests collected) is a pass. Outputs over 1500 characters become
    "..." + their last 1500 characters. Returns exactly one of:
        {"decision": "block", "reason": f"ruff check failed for {rel}:\n{output}"}
        {"decision": "block", "reason": f"tests failed after editing {rel} (python -m pytest -x -q --tb=short {target}):\n{output}"}
        {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                "additionalContext": f"repoguard: ruff clean and tests passed for {rel} ({target})"}}

    Stuck? HINTS.md -> post_tool_use
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement post_tool_use")


# ------------------------------------------------------------------ exercise 7
def find_injections(text: str) -> list[dict]:
    """Find lines in repository text that try to instruct an AI agent.

    Returns a list of {"line": n, "kind": k, "text": the stripped line}, 1-based line numbers,
    at most one entry per (line, kind), sorted by line and then kind.
    Kinds:
      override         "ignore/disregard/forget/override (all|any|the) previous/prior/above/
                       earlier/system instructions/rules/prompts/context/guidelines"
      agent_directive  a line telling an AI (AI, LLM, assistant, agent, Claude, Copilot, Codex,
                       Cursor, model...) what it must/should/always/never do; "note/message/
                       instruction(s)/attention to/for the <AI word>"; a line starting with
                       "system:", "assistant:" or "<system>"; "SYSTEM:" or a <system> tag anywhere
      hidden_unicode   zero-width, bidi-control or Unicode tag characters in the line
      exfiltration     a network command on the same line as a secret word (.env but not
                       .env.example/.sample/.template, api key, secret, token, password, id_rsa,
                       credentials); or curl/wget piped into a shell or python
      hidden_comment   an HTML comment <!-- ... --> (may span lines) containing an override,
                       agent_directive or exfiltration line; reported on the "<!--" line
    Matching is case-insensitive except "SYSTEM:". It must NOT flag ordinary prose such as
    "Ignore the build/ directory", "The agent field is optional",
    "Run `curl http://localhost:8000/health`", ".env.example lists the variables",
    "Our assistant manager approves requests".

    Stuck? HINTS.md -> find_injections
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement find_injections")
