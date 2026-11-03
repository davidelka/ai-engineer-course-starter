"""Reference version of exercise 3: decide whether a Bash command an agent wants to run is
dangerous. Try not to read this before your own check_bash passes the tests.

check_bash(command) returns ("deny", reason), ("ask", reason) or None (no objection).
The rules are listed in labs/05-coding-agents/mine.py next to the exercise.
"""

from __future__ import annotations

import posixpath
import re

from repoguard.paths import secret_reason
from repoguard.shell import parse, program

INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh", "python", "python3", "perl", "ruby", "node"}
NET = {"curl", "wget"}
SQL_DESTROY = re.compile(r"\b(drop\s+(table|database|schema)|truncate\s+table)\b", re.I)
HOME_PREFIXES = ("~/", "$HOME/", "${HOME}/")
DANGEROUS_RM_TARGETS = {"/", "/*", "~", "~/", ".", "./", "..", "../", "*", "./*", "$HOME", "${HOME}"}


def _short_flags(args: list[str]) -> str:
    """All single-letter flags in args, e.g. ['-rf', '-v', '--force'] -> 'rfv'."""
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def _rm_reason(argv: list[str]) -> str | None:
    args = argv[1:]
    recursive = "--recursive" in args or any(c in _short_flags(args) for c in "rR")
    if not recursive:
        return None
    for t in (a for a in args if not a.startswith("-")):
        norm = posixpath.normpath(t) if t not in ("~", "$HOME", "${HOME}") else t
        top = [x for x in norm.split("/") if x]
        if (
            t in DANGEROUS_RM_TARGETS
            or norm in (".", "..")
            or t.startswith(HOME_PREFIXES)
            or (t.startswith("/") and len(top) <= 1)
            or (top and top[0] == ".git")
        ):
            return f"recursive delete of {t!r} could wipe the project, the home directory or the system"
    return None


def _git_reason(argv: list[str]) -> tuple[str, str] | None:
    args = argv[1:]
    if "push" in args:
        if any(a in ("--force", "-f", "--force-with-lease") or a.startswith("--force") or a.startswith("+") for a in args):
            return "deny", "force-push rewrites shared history"
        return "ask", "git push publishes changes; a human should confirm"
    if "reset" in args and "--hard" in args:
        return "deny", "git reset --hard throws away uncommitted work"
    if "clean" in args and ("--force" in args or "f" in _short_flags(args[args.index("clean") + 1 :])):
        return "deny", "git clean -f deletes untracked files permanently"
    return None


def _curl_upload(argv: list[str]) -> bool:
    p = program(argv)
    args = argv[1:]
    if p == "curl":
        if "-T" in args or "--upload-file" in args or any(a.startswith("--upload-file=") for a in args):
            return True
        return any(a.startswith("@") or "=@" in a or (a.startswith("-d@")) for a in args)
    if p == "wget":
        return any(a.startswith(("--post-file", "--body-file")) for a in args)
    return False


def _installs(argv: list[str]) -> bool:
    p, args = program(argv), argv[1:]
    if p in ("pip", "pip3") and "install" in args:
        return True
    if p in ("python", "python3") and "-m" in args and "pip" in args and "install" in args:
        return True
    if p == "uv" and (args[:1] == ["add"] or args[:2] == ["pip", "install"]):
        return True
    if p == "poetry" and args[:1] == ["add"]:
        return True
    if p in ("npm", "pnpm", "yarn"):
        if args[:1] == ["add"]:
            return True
        if args[:1] in (["install"], ["i"]) and any(not a.startswith("-") for a in args[1:]):
            return True
    return False


def _secret_in_args(argv: list[str]) -> str | None:
    for a in argv[1:]:
        value = a.split("=", 1)[1] if a.startswith("-") and "=" in a else (None if a.startswith("-") else a)
        if value:
            r = secret_reason(value)
            if r:
                return r
            if value.startswith("/proc/") and value.endswith("/environ"):
                return "the process environment may contain API keys"
    return None


def check_bash(command: str) -> tuple[str, str] | None:
    """("deny", reason), ("ask", reason) or None for a Bash command. See the module docstring."""
    if SQL_DESTROY.search(command):
        return "deny", "destructive SQL (DROP / TRUNCATE)"
    if ":(){" in command.replace(" ", ""):
        return "deny", "fork bomb"
    pipelines = parse(command)
    asks: list[str] = []
    for pipe in pipelines:
        progs = [program(st) for st in pipe]
        for i, p in enumerate(progs):
            if p in NET and any(q in INTERPRETERS for q in progs[i + 1 :]):
                return "deny", "piping a download into an interpreter runs code nobody reviewed"
        for st in pipe:
            p = program(st)
            if p in ("sudo", "doas", "su"):
                return "deny", f"{p} runs commands as another user (root)"
            if p == "rm":
                r = _rm_reason(st)
                if r:
                    return "deny", r
            if p == "git":
                g = _git_reason(st)
                if g and g[0] == "deny":
                    return g
                if g:
                    asks.append(g[1])
            if _curl_upload(st):
                return "deny", "uploading a local file over the network"
            r = _secret_in_args(st)
            if r:
                return "deny", r
            if (p == "printenv" and len(st) == 1) or (p == "env" and all(a.startswith("-") or "=" in a for a in st[1:])):
                return "deny", "dumping environment variables can leak API keys"
            if p.startswith("mkfs") or (p == "dd" and any(a.startswith("of=/dev/") for a in st[1:])) or p == "shred":
                return "deny", "low-level disk write"
            if _installs(st):
                asks.append("installing a new dependency changes the project; a human should confirm")
            elif p in NET:
                asks.append(f"{p} reaches the network")
    if asks:
        return "ask", asks[0]
    return None
