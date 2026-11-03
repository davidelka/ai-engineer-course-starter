"""What every loader returns, and the small helpers they share."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoadResult:
    text: str                                   # markdown-ish: '#' headings, '- ' list items, 'a | b' rows
    meta: dict[str, Any] = field(default_factory=dict)   # what the file itself says (title, lang...)
    raw_text: str = ""                          # the naive extraction, for before/after inspection
    removed: list[str] = field(default_factory=list)     # boilerplate lines/blocks that were dropped


def parse_yaml(src: str) -> dict:
    """YAML front matter / sidecar: PyYAML when installed, else flat 'key: value' lines.
    Dates and versions come back as strings (a version of 2.0 must stay "2.0")."""
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(src) or {}
    except ImportError:
        data = {}
        for line in src.splitlines():
            if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    return {k: (v.isoformat() if hasattr(v, "isoformat") else
                (str(v) if isinstance(v, float) else v)) for k, v in data.items()}


def table_rows_to_text(rows: list[list[str]]) -> str:
    """Rows of cells -> 'cell | cell | cell' lines. A header row stays a row: it is what lets a
    reader (and a model) know that '10%' is a credit and not an uptime."""
    out = []
    for r in rows:
        cells = [" ".join(c.split()) for c in r]
        if any(cells):
            out.append(" | ".join(cells))
    return "\n".join(out)
