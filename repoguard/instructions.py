"""A linter for agent instruction files (CLAUDE.md, AGENTS.md, .cursor rules, SKILL.md bodies).

The rubric follows the advice in the Claude Code memory docs (code.claude.com/docs/en/memory):
target under 200 lines, write instructions concrete enough to verify ("Run `npm test` before
committing", not "Test your changes"), group them under headers and bullets, and keep
contradictions and secrets out. HTML comments are ignored, as Claude Code strips them. It is a heuristic: a high score means the file has the
shape of a useful instruction file, not that every rule in it is right.

lint(text) -> {"score": int, "passed": bool, "findings": [...], "stats": {...}}
Each finding: {"severity": "error" | "warn" | "info", "rule": str, "line": int, "message": str}.
Score: 100 minus 25 per error, 8 per warning, 2 per info (floor 0). Passed: no errors and score >= 70.
"""

from __future__ import annotations

import re

TEST_CMD = re.compile(r"\b(pytest|make test|npm (run )?test|pnpm test|yarn test|go test|cargo test|tox|nox)\b")
LINT_CMD = re.compile(r"\b(ruff|flake8|pylint|eslint|make lint|make fmt|npm run lint|black|mypy|pyright|prettier)\b")
VAGUE = [
    "clean code", "best practices", "be careful", "properly", "as needed", "when appropriate",
    "good code", "high quality", "high-quality", "make sure everything works", "keep it simple",
    "follow conventions", "write good tests", "be consistent", "use common sense", "industry standard",
]
SECRET = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}"
    r"|\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*(?![<$\"']?(example|changeme|xxx|\.\.\.|<))\S{6,})",
    re.I,
)
SHOUT = re.compile(r"\b(IMPORTANT|MUST|NEVER|ALWAYS|CRITICAL)\b")
HEADING = re.compile(r"^#{1,4}\s+\S")
BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
PATHLIKE = re.compile(r"(\b[\w.-]+/[\w.*/-]*|\b[\w-]+\.(py|ts|js|md|json|toml|yaml|yml|txt|sh|cfg|ini|lock)\b)")
CONCRETE = re.compile(r"(`[^`]+`|\d|" + PATHLIKE.pattern + r")")

WEIGHTS = {"error": 25, "warn": 8, "info": 2}


def _code_mask(lines: list[str]) -> list[bool]:
    """True for lines inside fenced code blocks (the fences included)."""
    mask, inside = [], False
    for ln in lines:
        if ln.strip().startswith("```"):
            mask.append(True)
            inside = not inside
            continue
        mask.append(inside)
    return mask


def strip_comments(text: str) -> str:
    """Remove HTML block comments (Claude Code strips them before loading CLAUDE.md), keeping line numbers."""
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def lint(text: str) -> dict:
    lines = strip_comments(text).splitlines()
    code = _code_mask(lines)
    findings: list[dict] = []

    def add(sev, rule, line, msg):
        findings.append({"severity": sev, "rule": rule, "line": line, "message": msg})

    n = len(lines)
    nonempty = [ln for ln in lines if ln.strip()]
    if n > 200:
        add("error", "too_long", 201, f"{n} lines. The Claude Code docs target under 200: long files cost context and lower adherence. Move part-specific rules to .claude/rules/ or a skill.")
    elif n > 120:
        add("warn", "long", 121, f"{n} lines. Keep only what matters in every session.")
    if len(nonempty) < 8:
        add("warn", "too_short", 1, "Fewer than 8 non-empty lines: probably missing commands, layout or conventions.")

    headings = sum(1 for i, ln in enumerate(lines) if HEADING.match(ln) and not code[i])
    if headings < 2:
        add("warn", "no_structure", 1, "Fewer than 2 headings. Group instructions under headers (Commands, Layout, Conventions...).")

    test_lines = [i for i, ln in enumerate(lines) if TEST_CMD.search(ln)]
    if not test_lines:
        add("error", "no_test_command", 1, "No test command (pytest, make test, npm test...). The agent needs one exact command to check its work.")
    elif not any(code[i] or re.search(r"`[^`]*" + TEST_CMD.pattern + r"[^`]*`", lines[i]) for i in test_lines):
        add("info", "commands_not_code", test_lines[0] + 1, "Put commands in backticks or a code block so they can be copied exactly.")
    if not any(LINT_CMD.search(ln) for ln in lines):
        add("warn", "no_lint_command", 1, "No lint/format command (ruff, eslint, make lint...).")

    if not any(PATHLIKE.search(ln) for i, ln in enumerate(lines) if not code[i]):
        add("info", "no_layout", 1, "No paths mentioned. Say where things live (app/, tests/...).")

    vague_count = 0
    for i, ln in enumerate(lines):
        if code[i]:
            continue
        low = ln.lower()
        for phrase in VAGUE:
            if phrase in low and vague_count < 5:
                vague_count += 1
                add("warn", "vague", i + 1, f"\"{phrase}\" cannot be verified. Say exactly what to do or check.")
        if "TODO" in ln:
            add("warn", "todo", i + 1, "Unfinished TODO left in the file.")
        m = SECRET.search(ln)
        if m:
            add("error", "secret", i + 1, "Looks like a secret value. Instruction files are committed and read by tools: never put keys here.")
        if len(ln) > 300 and not BULLET.match(ln) and not HEADING.match(ln):
            add("warn", "dense_paragraph", i + 1, f"Paragraph of {len(ln)} characters. Split into bullets.")

    shouts = sum(len(SHOUT.findall(ln)) for i, ln in enumerate(lines) if not code[i])
    if shouts > 5:
        add("info", "shouting", 1, f"{shouts} words in capitals (MUST, NEVER...). When everything is critical nothing is; current models follow plain instructions.")

    bullets = [ln for i, ln in enumerate(lines) if BULLET.match(ln) and not code[i]]
    concrete = [b for b in bullets if CONCRETE.search(b)]
    ratio = (len(concrete) / len(bullets)) if bullets else 0.0
    if len(bullets) >= 5 and ratio < 0.5:
        add("warn", "unverifiable", 1, f"Only {len(concrete)}/{len(bullets)} bullets name a command, path, number or code token.")

    score = max(0, 100 - sum(WEIGHTS[f["severity"]] for f in findings))
    errors = sum(1 for f in findings if f["severity"] == "error")
    findings.sort(key=lambda f: (["error", "warn", "info"].index(f["severity"]), f["line"]))
    return {
        "score": score,
        "passed": errors == 0 and score >= 70,
        "findings": findings,
        "stats": {
            "lines": n,
            "headings": headings,
            "has_test_command": bool(test_lines),
            "has_lint_command": any(LINT_CMD.search(ln) for ln in lines),
            "bullets": len(bullets),
            "concrete_bullets": len(concrete),
            "vague_phrases": vague_count,
        },
    }
