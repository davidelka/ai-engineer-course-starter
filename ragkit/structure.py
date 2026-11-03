"""Document structure: headings and section paths.

Every loader emits markdown-style headings ('#', '##', ...) whatever the source format
(HTML <h2>, DOCX "Heading 2", a numbered PDF heading), so one structure parser serves all
formats and every chunker can attach a section path to its chunks.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
FENCE_RE = re.compile(r"^(```|~~~)", re.M)


@dataclass(frozen=True)
class Heading:
    start: int        # offset of the '#' in the text
    line_end: int     # offset just after the heading line
    level: int
    title: str
    path: tuple[str, ...]  # titles of all enclosing headings, this one last


def _fenced_ranges(text: str) -> list[tuple[int, int]]:
    marks = [m.start() for m in FENCE_RE.finditer(text)]
    return [(marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2)]


def headings(text: str) -> list[Heading]:
    fences = _fenced_ranges(text)
    out: list[Heading] = []
    stack: list[tuple[int, str]] = []
    for m in HEADING_RE.finditer(text):
        if any(a <= m.start() < b for a, b in fences):
            continue  # '# comment' inside a code block is not a heading
        level, title = len(m.group(1)), m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        out.append(Heading(m.start(), m.end(), level, title, tuple(t for _, t in stack)))
    return out


class SectionIndex:
    """section_path(offset): the path of the heading that governs that offset."""

    def __init__(self, text: str):
        self.heads = headings(text)
        self._starts = [h.start for h in self.heads]

    def section_path(self, offset: int) -> tuple[str, ...]:
        i = bisect_right(self._starts, offset) - 1
        return self.heads[i].path if i >= 0 else ()

    def sections(self, text_len: int) -> list[tuple[int, int, tuple[str, ...]]]:
        """(start, end, path) for the preamble (if any) and every heading's section.
        A section runs from its heading to the next heading of ANY level."""
        out = []
        bounds = self._starts + [text_len]
        if not self.heads or self.heads[0].start > 0:
            out.append((0, bounds[0] if self.heads else text_len, ()))
        for i, h in enumerate(self.heads):
            out.append((h.start, bounds[i + 1], h.path))
        return [s for s in out if s[1] > s[0]]
