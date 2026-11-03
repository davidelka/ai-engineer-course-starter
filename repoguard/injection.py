"""Reference version of exercise 7: find prompt-injection attempts planted in repository text.

A coding agent reads READMEs, docs, code comments, test fixtures, issue text and tool output.
Anything it reads can contain instructions written for it by someone else. This scanner is a
review aid, not a defense: it flags suspicious lines so a human looks at them, and it will
miss paraphrases. The defenses are the permissions, hooks and sandbox around the agent.

find_injections(text) returns hits as dicts {"line": int, "kind": str, "text": str},
one per (line, kind), sorted by line and then kind. Kinds:

  override         "ignore / disregard / forget (all) previous / prior / above instructions"
  agent_directive  text addressed to an AI that tells it what to do ("AI agents must ...",
                   "note to the assistant", "SYSTEM:" or <system> in the text)
  hidden_unicode   zero-width characters, bidi controls or Unicode tag characters
  exfiltration     a network command together with a secret (curl ... .env, API_KEY, token),
                   or a download piped into a shell
  hidden_comment   an HTML comment (<!-- ... -->) whose content matches override,
                   agent_directive or exfiltration; reported on the line where it starts
"""

from __future__ import annotations

import re

OVERRIDE = re.compile(
    r"\b(ignore|disregard|forget|override)\b[^.\n]{0,20}\b(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|preceding|system)\b[^.\n]{0,15}\b(instructions?|rules|prompts?|context|guidelines)\b",
    re.I,
)
AGENT_WORDS = r"(ai|llm|assistant|agent|coding agent|claude|copilot|codex|cursor|model)s?"
AGENT_DIRECTIVE = [
    re.compile(rf"\b{AGENT_WORDS}\b[^.\n]{{0,60}}\b(must|should|need to|have to|are required to|always|never)\b", re.I),
    re.compile(rf"\b(note|message|instructions?|attention)\s+(to|for)\s+(the\s+|all\s+|any\s+)?{AGENT_WORDS}\b", re.I),
    re.compile(r"^\s*(<\s*)?(system|assistant)\s*(>|:)", re.I),
    re.compile(r"\bSYSTEM\s*:|<\s*/?\s*system\s*>"),
]
HIDDEN = re.compile("[​‌‍⁠﻿‪-‮⁦-⁩\U000e0000-\U000e007f]")
NET = re.compile(r"\b(curl|wget|nc|netcat|scp|requests\.post|fetch\(|invoke-webrequest)\b", re.I)
SECRET = re.compile(r"(\.env\b(?!\.example|\.sample|\.template)|api[_-]?key|secret|token|password|id_rsa|credentials)", re.I)
PIPE_SHELL = re.compile(r"\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+)?(sh|bash|zsh|python3?)\b", re.I)


def _line_kinds(line: str) -> set[str]:
    kinds = set()
    if OVERRIDE.search(line):
        kinds.add("override")
    if any(p.search(line) for p in AGENT_DIRECTIVE):
        kinds.add("agent_directive")
    if HIDDEN.search(line):
        kinds.add("hidden_unicode")
    if (NET.search(line) and SECRET.search(line)) or PIPE_SHELL.search(line):
        kinds.add("exfiltration")
    return kinds


def find_injections(text: str) -> list[dict]:
    lines = text.splitlines()
    hits: dict[tuple[int, str], str] = {}
    for i, line in enumerate(lines, 1):
        for k in _line_kinds(line):
            hits[(i, k)] = line.strip()
    # HTML comments: hidden when the file is rendered, fully visible to an agent reading the source.
    for m in re.finditer(r"<!--(.*?)-->", text, re.S):
        body = m.group(1)
        if any(_line_kinds(b) & {"override", "agent_directive", "exfiltration"} for b in body.splitlines() or [body]):
            start = text.count("\n", 0, m.start()) + 1
            hits[(start, "hidden_comment")] = lines[start - 1].strip()
    return [{"line": ln, "kind": k, "text": t} for (ln, k), t in sorted(hits.items())]


INSTRUCTION_FILES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "SKILL.md"}


def scan_tree(root: str, exts=(".md", ".py", ".json", ".txt", ".toml", ".yaml", ".yml", ".cfg", ".ini", "")) -> list[dict]:
    """Run find_injections over every text file under root. Adds a "path" key to each hit.

    Instruction files (CLAUDE.md, AGENTS.md, SKILL.md, anything under .claude/) are skipped:
    they are the legitimate channel for talking to the agent, so "Claude must run make test"
    is expected there and suspicious anywhere else. Review them in code review instead.
    """
    import os

    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".ruff_cache", ".claude")]
        for fn in sorted(filenames):
            if fn in INSTRUCTION_FILES or os.path.splitext(fn)[1] not in exts:
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            for h in find_injections(text):
                out.append({"path": os.path.relpath(path, root), **h})
    return out
