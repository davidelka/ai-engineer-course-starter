"""An approximate evaluator of Claude Code permission rules, for checking a settings.json offline.

It implements the documented core (code.claude.com/docs/en/permissions):

  - rules are `Tool` or `Tool(specifier)`; evaluated deny first, then ask, then allow;
    the first match in that order wins, and specificity does not change the order
  - Bash rules match the whole command text, `*` matches any text; compound commands are
    split (&&, ||, ;, |, ...): a deny/ask rule applies when ANY subcommand matches, an
    allow rule only when EVERY subcommand matches; wrappers like `timeout` are stripped
  - Read/Edit rules use gitignore-style paths: `./x` and `x` relative to the project,
    `/x` relative to the settings file's project, `//x` absolute, `~/x` home; a bare file
    name matches at any depth; `!pattern` in the same list carves an exception
  - Edit rules cover Edit, Write, MultiEdit and NotebookEdit; Read rules cover Read, Grep
    and Glob; a Read deny also blocks Edit and Write on the same path

It is NOT Claude Code's matcher. It ignores modes, sandboxing, working-directory checks,
read-only commands and many edge cases. Use it to catch mistakes, then test in a real session.
"""

from __future__ import annotations

import os
import posixpath
import re

from repoguard.shell import parse

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}
RULE = re.compile(r"^([A-Za-z0-9_*-]+)(?:\((.*)\))?$", re.S)


def parse_rule(rule: str) -> tuple[str, str | None]:
    m = RULE.match(rule.strip())
    if not m:
        return rule.strip(), None
    return m.group(1), m.group(2)


def _bash_match(spec: str, sub: str) -> bool:
    if spec in ("*", ""):
        return True
    if "*" not in spec:
        return sub == spec
    rx = "^" + ".*".join(re.escape(part) for part in spec.split("*")) + "$"
    if re.match(rx, sub, re.S):
        return True
    # "git push *" also matches a bare "git push"
    return spec.endswith(" *") and sub == spec[:-2]


def _subcommands(command: str) -> list[str]:
    subs = [" ".join(st) for pipe in parse(command) for st in pipe]
    return subs or [command.strip()]


def _glob_rx(pattern: str) -> str:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)


def _path_match(spec: str, path: str, project_dir: str) -> bool:
    """Does a Read/Edit specifier match an absolute, normalized path?"""
    home = os.path.expanduser("~")
    if spec.startswith("//"):
        base, pat = "/", spec[2:]
    elif spec.startswith("~/"):
        base, pat = home, spec[2:]
    elif spec.startswith("/"):
        base, pat = project_dir, spec[1:]
    elif spec.startswith("./"):
        base, pat = project_dir, spec[2:]
    else:
        base, pat = project_dir, spec
    base = os.path.realpath(base)
    if not (path == base or path.startswith(base.rstrip("/") + "/")):
        return False
    rel = posixpath.relpath(path, base) if path != base else "."
    pat = pat.rstrip("/")
    if "/" not in pat and not spec.startswith(("./", "/", "~/")):
        # bare name: gitignore matches it at any depth
        return re.fullmatch(_glob_rx(pat), posixpath.basename(rel)) is not None or re.fullmatch("(?:.*/)?" + _glob_rx(pat) + "(?:/.*)?", rel) is not None
    return re.fullmatch(_glob_rx(pat) + "(?:/.*)?", rel) is not None


def _matches_list(rules: list[str], tool: str, value: str, project_dir: str, mode: str) -> str | None:
    """Return the first rule in the list that matches, honoring `!` carve-outs for paths."""
    hit = None
    for rule in rules:
        name, spec = parse_rule(rule)
        if tool == "Bash" and name == "Bash":
            if spec is None:
                return rule
            subs = _subcommands(value)
            ok = all(_bash_match(spec, s) for s in subs) if mode == "allow" else any(_bash_match(spec, s) for s in subs)
            if ok:
                return rule
        elif name in ("Read", "Edit") and value:
            applies = (name == "Edit" and tool in EDIT_TOOLS) or (name == "Read" and tool in READ_TOOLS) or (
                name == "Read" and mode == "deny" and tool in EDIT_TOOLS
            )
            if not applies:
                continue
            if spec is None:
                return rule
            if spec.startswith("!"):
                if hit and _path_match(spec[1:], value, project_dir):
                    hit = None
                continue
            if hit is None and _path_match(spec, value, project_dir):
                hit = rule
        elif name == tool and spec is None:
            return rule
        elif name.endswith("*") and spec is None and mode != "allow" and tool.startswith(name[:-1]):
            return rule
        elif name == "WebFetch" == tool and spec and spec.startswith("domain:"):
            dom = spec.split(":", 1)[1]
            host = re.sub(r"^https?://", "", value).split("/")[0]
            if host == dom or host.endswith("." + dom):
                return rule
    return hit


def evaluate(settings: dict, tool: str, value: str = "", project_dir: str = ".") -> tuple[str, str | None]:
    """('deny' | 'ask' | 'allow' | 'prompt', the matching rule or None).

    `value` is the command for Bash, the file path for Read/Edit/Write (relative paths are
    taken relative to project_dir), the URL for WebFetch. 'prompt' means no rule matched,
    so the permission mode decides (Manual mode asks; a -p run denies).
    """
    perms = settings.get("permissions") or {}
    project = os.path.realpath(project_dir)
    if tool != "Bash" and tool != "WebFetch" and value:
        value = os.path.normpath(value if os.path.isabs(value) else os.path.join(project, value))
    for mode in ("deny", "ask", "allow"):
        rule = _matches_list(perms.get(mode) or [], tool, value, project, mode)
        if rule:
            return mode, rule
    return "prompt", None
