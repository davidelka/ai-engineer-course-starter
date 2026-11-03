"""A checker for Claude Code skills (.claude/skills/<name>/SKILL.md).

What it checks comes from code.claude.com/docs/en/skills:

  - YAML frontmatter between --- lines. All fields are optional, but `description` is what
    Claude reads at session start to decide when to load the skill, so it must say what the
    skill does AND when to use it. Only descriptions are loaded up front; the body loads
    when the skill is invoked (progressive disclosure).
  - `name`, if given, becomes the /command; it should match the directory name.
  - the body should stay under 500 lines; long reference material goes to supporting files.
  - for this lab's "add an endpoint" skill: numbered steps, the files to touch, and the exact
    commands that prove the work is done.

check_skill(text, dirname) -> {"score", "passed", "findings", "frontmatter"} like instructions.lint.
"""

from __future__ import annotations

import re

import yaml

KNOWN_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "allowed-tools", "disallowed-tools", "model", "effort", "context", "agent",
    "background", "hooks", "paths", "shell", "license", "compatibility", "metadata",
}
WEIGHTS = {"error": 25, "warn": 8, "info": 2}


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """(frontmatter dict or None, body, error message or None)."""
    if not text.startswith("---"):
        return None, text, None
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return None, text, "frontmatter starts with --- but never closes"
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        return None, text[m.end():], f"frontmatter is not valid YAML: {e}"
    if not isinstance(data, dict):
        return None, text[m.end():], "frontmatter must be a mapping of fields"
    return data, text[m.end():], None


def check_skill(text: str, dirname: str = "add-endpoint") -> dict:
    findings: list[dict] = []

    def add(sev, rule, msg):
        findings.append({"severity": sev, "rule": rule, "message": msg})

    fm, body, err = split_frontmatter(text)
    if err:
        add("error", "frontmatter", err)
    if fm is None and not err:
        add("error", "frontmatter", "No YAML frontmatter. Start the file with --- / description: ... / ---.")
    fm = fm or {}
    desc = str(fm.get("description") or "")
    if not desc:
        add("error", "description", "No description. Claude decides when to load a skill from its description alone.")
    else:
        if len(desc) < 40:
            add("warn", "description", "Description is very short. Say what the skill does and when to use it.")
        if not re.search(r"\b(use|when|whenever|if)\b", desc, re.I):
            add("warn", "description", "Description does not say WHEN to use the skill (e.g. 'Use when asked to add an API endpoint').")
        if len(desc) > 1536:
            add("warn", "description", "Description over 1,536 characters is truncated in the skill listing.")
    name = fm.get("name")
    if name is not None and str(name) != dirname:
        add("warn", "name", f"name {name!r} differs from the directory {dirname!r}; the /command will not match the folder.")
    unknown = sorted(set(fm) - KNOWN_FIELDS)
    if unknown:
        add("warn", "unknown_field", f"Unknown frontmatter fields are ignored silently: {', '.join(unknown)}")

    lines = body.splitlines()
    if len(lines) > 500:
        add("warn", "long_body", f"Body has {len(lines)} lines; the docs suggest under 500 and supporting files for the rest.")
    if not re.search(r"^\s*\d+[.)]\s+", body, re.M):
        add("warn", "steps", "No numbered steps. A procedure skill should list the steps in order.")
    if not re.search(r"\b(pytest|make test)\b", body):
        add("error", "test_command", "The body never says how to run the tests (make test / python -m pytest).")
    if not re.search(r"\b(ruff|make lint)\b", body):
        add("warn", "lint_command", "The body never says how to lint (make lint / ruff check).")
    for path in ("app/main.py", "app/models.py", "tests/"):
        if path not in body:
            add("warn", "files", f"The body does not mention {path}; say which files the procedure touches.")
    if re.search(r"\b(404|409|422|403)\b", body) is None:
        add("info", "errors", "No error status codes mentioned. Endpoints in this service test their error cases.")
    if "$ARGUMENTS" not in body and "$0" not in body:
        add("info", "arguments", "No $ARGUMENTS placeholder: /add-endpoint <description> will append the text at the end instead.")

    score = max(0, 100 - sum(WEIGHTS[f["severity"]] for f in findings))
    errors = sum(1 for f in findings if f["severity"] == "error")
    return {"score": score, "passed": errors == 0 and score >= 70, "findings": findings, "frontmatter": fm}
