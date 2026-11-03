"""Turning evidence into feedback the generator can act on.

format_feedback is the reference version of exercise 5 in lesson 7: it turns raw
pytest output into a short list of failures with the exact assertion and values.
compose_feedback builds the whole message for the next iteration from all the
verifiers' evidence, in one of three modes (compact, raw, minimal), so you can
measure how feedback quality changes convergence and cost.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Callable, Optional

from .types import Evidence

SUMMARY_RE = re.compile(r"^=*\s*((?:\d+ \w+(?:, )?)+?)\s+in\s+[\d.]+s\b")
HEADER_RE = re.compile(r"^_{3,} (.+?) _{3,}$")
ABS_PATH_RE = re.compile(r'"(?:/[^"/]+)+/([^"/]+)"')
TRUNC = "\n...[truncated]"
HYPOTHESIS_NOTES = ("Failing test case:", "Falsifying example:")


def _display_id(node_id: str) -> str:
    path, sep, rest = node_id.partition("::")
    return PurePosixPath(path).name + (sep + rest if sep else "")


def _blocks(output: str) -> dict[str, list[str]]:
    """Traceback blocks keyed by their header ('test_x[1]', 'TestK.test_k', 'ERROR collecting tests/x.py')."""
    blocks: dict[str, list[str]] = {}
    current: Optional[str] = None
    for line in output.splitlines():
        m = HEADER_RE.match(line)
        if m:
            current = m.group(1)
            blocks[current] = []
        elif line.startswith("=") and current is not None:
            current = None  # a new ===== section ends the block
        elif current is not None:
            blocks[current].append(line)
    return blocks


def _details(block: list[str]) -> list[str]:
    e_idx = [i for i, line in enumerate(block) if line.startswith("E ")]
    if not e_idx:
        return []
    code = ""
    for line in reversed(block[:e_idx[0]]):
        s = line.strip()
        if line.startswith("    ") and s and set(s) - {"^", "~"}:
            code = s
            break
    e_lines = []
    for i in e_idx:
        text = ABS_PATH_RE.sub(r'"\1"', block[i][1:].strip())
        if text.startswith(HYPOTHESIS_NOTES):
            break  # Hypothesis' own repr of the example; our assertion messages already carry it
        if text:
            e_lines.append(text)
    if len(e_lines) > 4:
        e_lines = e_lines[:2] + e_lines[-2:]
    return ([code] if code else []) + e_lines


def format_feedback(pytest_output: str, max_failures: int = 5, max_chars: int = 1500) -> str:
    """Compact, actionable feedback from `pytest -q --tb=short -rfE --no-header` output.

    Line 1: the final counts without the timing ("2 failed, 6 passed"), "no tests ran",
            or "pytest output had no summary line".
    Then, for each FAILED / ERROR line of the short summary (in order, at most max_failures):
        - <file name>::<test name>             (for a collection error: "<file name> (collection error)")
            <the source line that failed>
            <E lines, without the leading "E" and spaces; absolute paths cut to the file name;
             stop at a line starting with "Failing test case:" or "Falsifying example:";
             if more than 4 remain, keep the first 2 and the last 2>
      Detail lines are indented 4 spaces. With no E lines, the message after " - " is used.
    Then "- ... and N more failing tests" if some were left out.
    The result is at most max_chars long: if longer, cut and end with "\\n...[truncated]".
    """
    lines = pytest_output.splitlines()
    header = "pytest output had no summary line"
    if any("no tests ran" in line for line in lines):
        header = "no tests ran"
    for line in reversed(lines):
        m = SUMMARY_RE.match(line.strip())
        if m:
            header = m.group(1).strip().rstrip(",")
            break
    summary = [line for line in lines if line.startswith(("FAILED ", "ERROR "))]
    out = [header]
    blocks = _blocks(pytest_output)
    for line in summary[:max_failures]:
        kind, _, rest = line.partition(" ")
        node_id, _, msg = rest.partition(" - ")
        node_id = node_id.strip()
        if kind == "ERROR" and "::" not in node_id:
            out.append(f"- {PurePosixPath(node_id).name} (collection error)")
            block = blocks.get(f"ERROR collecting {node_id}", [])
        else:
            out.append(f"- {_display_id(node_id)}")
            parts = node_id.split("::")[1:]
            block = blocks.get(".".join(parts), [])
        details = _details(block) or ([msg.strip()] if msg.strip() else [])
        out.extend("    " + d for d in details)
    if len(summary) > max_failures:
        out.append(f"- ... and {len(summary) - max_failures} more failing tests")
    text = "\n".join(out)
    if len(text) > max_chars:
        text = text[: max(0, max_chars - len(TRUNC))] + TRUNC
    return text


def minimal_feedback(evidence: Evidence) -> str:
    return f"{evidence.verifier}: failed."


def raw_feedback(evidence: Evidence, limit: int = 6000) -> str:
    out = evidence.output.strip()
    return out if len(out) <= limit else out[:limit] + TRUNC


LABELS = {
    "runs": "Smoke run (import the module and call it once)",
    "visible_tests": "Visible tests (tests/test_visible.py, which you can read)",
    "hidden_tests": "Hidden checks: property-based and edge-case tests (you cannot see this file)",
    "lint": "Linter (ruff: syntax errors and undefined names)",
    "types": "Type checker (mypy)",
    "guard": "Test-integrity guard",
}


def compose_feedback(
    evidence: list[Evidence],
    *,
    mode: str = "compact",
    formatter: Callable[[str], str] = format_feedback,
    regressions: Optional[list[str]] = None,
    reverted: bool = False,
) -> str:
    """The message the generator receives for its next attempt. '' when everything passed."""
    failed = [e for e in evidence if not e.passed and not e.skipped]
    if not failed and not regressions:
        return ""
    parts: list[str] = []
    if regressions:
        shown = ", ".join(_display_id(r) for r in regressions[:6])
        more = f" and {len(regressions) - 6} more" if len(regressions) > 6 else ""
        parts.append(f"REGRESSION: your last change broke checks that passed before: {shown}{more}."
                     + (" The code below is your best version so far; continue from it." if reverted else ""))
    for e in failed:
        title = LABELS.get(e.verifier, e.verifier)
        if mode == "minimal":
            parts.append(minimal_feedback(e))
            continue
        if e.kind == "guard":
            body = ("You changed the tests instead of the code. Test files are read-only: your changes "
                    "were discarded. Findings:\n" + "\n".join(f"- {f}" for f in e.findings)
                    + "\nFix solution.py so the ORIGINAL tests pass. If the spec and tests truly "
                      "contradict each other, say so (cannot_solve) instead of working around them.")
        elif mode == "raw":
            body = raw_feedback(e)
        elif e.kind == "pytest":
            body = formatter(e.output)
        else:
            body = e.output.strip()[:1200] or e.summary
        parts.append(f"## {title}\n{body}")
    return "\n\n".join(parts)
