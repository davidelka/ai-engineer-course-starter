"""A minimal Server-Sent Events parser.

An event is a group of lines ending with a blank line:
    event: <name>     (optional)
    data: <payload>   (may repeat; joined with newlines)
Lines starting with ':' are comments (keep-alives).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Optional


@dataclass
class SSEEvent:
    event: Optional[str]
    data: str


def iter_sse(lines: Iterable[str]) -> Iterator[SSEEvent]:
    event: Optional[str] = None
    data: list[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if line == "":
            if event is not None or data:
                yield SSEEvent(event, "\n".join(data))
            event, data = None, []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)
    if event is not None or data:  # stream ended without a final blank line
        yield SSEEvent(event, "\n".join(data))
