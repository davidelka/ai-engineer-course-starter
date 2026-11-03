"""Parse a Markdown spec written with spec/TEMPLATE.md (lesson 6) into requirements.

The format is deliberately small:

    ## 3. Requirements                     any "##" section whose name contains "requirement"
    ### REQ-4: Route by policy             one requirement; "### Some title" without an id is kept, id=None
    **Statement:** WHEN ..., THE SYSTEM SHALL ...      (may continue over several lines)
    **Acceptance criteria:**
    - AC-4.1: GIVEN ... WHEN ... THEN ...  (a bullet may continue on indented lines)

NFR-<n> ids, or any requirement inside a section whose name contains "non-functional",
are non-functional.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

ID_RE = re.compile(r"\b(?:REQ|NFR)-\d+\b")
HEADING_RE = re.compile(r"^###\s+(?:((?:REQ|NFR)-\d+)\s*[:.\-–]\s*)?(.*?)\s*$")
CRIT_RE = re.compile(r"^(AC-[\w.\-]+)\s*:\s*(.*)$")


@dataclass
class Criterion:
    id: Optional[str]
    text: str
    line: int


@dataclass
class Requirement:
    id: Optional[str]
    title: str
    kind: str  # "functional" | "non-functional"
    statement: str = ""
    criteria: list[Criterion] = field(default_factory=list)
    line: int = 0


@dataclass
class Spec:
    title: str
    requirements: list[Requirement]
    sections: dict[str, str]  # "## 5. Constraints" -> {"constraints": "<text>"}

    def ids(self) -> list[str]:
        """Requirement ids in spec order, first occurrence only."""
        seen: list[str] = []
        for r in self.requirements:
            if r.id and r.id not in seen:
                seen.append(r.id)
        return seen

    def get(self, req_id: str) -> Optional[Requirement]:
        return next((r for r in self.requirements if r.id == req_id), None)


def _section_key(heading: str) -> str:
    name = re.sub(r"^\d+[.)]?\s*", "", heading.strip())
    return name.lower()


def parse_spec(source: Union[str, Path]) -> Spec:
    """Accepts the Markdown text, or a Path to the file."""
    text = Path(source).read_text(encoding="utf-8") if isinstance(source, Path) else source
    title, section, reqs, sections = "", "", [], {}
    cur: Optional[Requirement] = None
    mode = ""  # "", "statement", "criteria"
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            section = _section_key(line[3:])
            sections[section] = ""
            cur, mode = None, ""
            continue
        if section:
            sections[section] += raw + "\n"
        if line.startswith("### ") and "requirement" in section:
            m = HEADING_RE.match(line)
            rid, rtitle = (m.group(1), m.group(2)) if m else (None, line[4:].strip())
            kind = "non-functional" if (rid or "").startswith("NFR") or "non-functional" in section else "functional"
            cur = Requirement(id=rid, title=rtitle, kind=kind, line=n)
            reqs.append(cur)
            mode = ""
            continue
        if line.startswith("### "):
            cur, mode = None, ""
            continue
        if cur is None:
            continue
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("**statement:**"):
            cur.statement = stripped[len("**statement:**"):].strip()
            mode = "statement"
        elif low.startswith("**acceptance criteria:**"):
            mode = "criteria"
        elif mode == "statement" and stripped:
            cur.statement = (cur.statement + " " + stripped).strip()
        elif mode == "criteria" and stripped.startswith(("- ", "* ")):
            body = stripped[2:].strip()
            m = CRIT_RE.match(body)
            cur.criteria.append(Criterion(m.group(1) if m else None, m.group(2) if m else body, n))
        elif mode == "criteria" and stripped and raw[:1].isspace() and cur.criteria:
            cur.criteria[-1].text += " " + stripped  # continuation of the previous bullet
    return Spec(title=title, requirements=reqs, sections=sections)
