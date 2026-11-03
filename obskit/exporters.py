"""A local JSONL span exporter, and helpers to read spans back.

One JSON object per finished span, one span per line. The format is deliberately flat
and close to what the OTLP/JSON export carries, minus the nesting:

    {"trace_id": "4bf9...", "span_id": "00f0...", "parent_id": null | "...",
     "name": "chat claude-haiku-5-5", "kind": "CLIENT",
     "start_ms": 1761727200123.4, "end_ms": 1761727201011.9, "duration_ms": 888.5,
     "status": "OK" | "ERROR" | "UNSET", "status_message": "",
     "attributes": {...}, "events": [{"name", "time_ms", "attributes"}],
     "links": [{"trace_id", "span_id"}], "service": "acme-answer"}

Times are epoch milliseconds (floats), so a human can read them and `jq` can sort them.
Everything downstream (obskit.analyze, obskit.viewer, obskit.replay, the lab exercises)
works on these dicts, not on SDK objects, so it runs without the OpenTelemetry SDK.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

try:  # the exporter class needs the SDK; the readers below do not
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
except ImportError:  # pragma: no cover
    ReadableSpan = object  # type: ignore
    SpanExporter = object  # type: ignore
    SpanExportResult = None  # type: ignore


def _hex(n: int, width: int) -> str:
    return format(n, f"0{width}x")


def _plain(v):
    """OTel attribute values (tuples, BoundedAttributes...) -> JSON-friendly values."""
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if hasattr(v, "items"):
        return {str(k): _plain(x) for k, x in v.items()}
    return v


def span_to_dict(span: "ReadableSpan") -> dict:
    ctx = span.get_span_context()
    parent = span.parent
    start = (span.start_time or 0) / 1e6
    end = (span.end_time or span.start_time or 0) / 1e6
    status = span.status
    return {
        "trace_id": _hex(ctx.trace_id, 32),
        "span_id": _hex(ctx.span_id, 16),
        "parent_id": _hex(parent.span_id, 16) if parent else None,
        "name": span.name,
        "kind": span.kind.name if span.kind is not None else "INTERNAL",
        "start_ms": round(start, 3),
        "end_ms": round(end, 3),
        "duration_ms": round(end - start, 3),
        "status": status.status_code.name if status else "UNSET",
        "status_message": (status.description or "") if status else "",
        "attributes": {k: _plain(v) for k, v in (span.attributes or {}).items()},
        "events": [{"name": e.name, "time_ms": round(e.timestamp / 1e6, 3),
                    "attributes": {k: _plain(v) for k, v in (e.attributes or {}).items()}}
                   for e in span.events],
        "links": [{"trace_id": _hex(link.context.trace_id, 32), "span_id": _hex(link.context.span_id, 16)}
                  for link in span.links],
        "service": (span.resource.attributes.get("service.name") if span.resource else None),
    }


class JsonlSpanExporter(SpanExporter):
    """Append finished spans to a JSONL file. Thread safe; flushes after every batch."""

    def __init__(self, path: Union[str, Path], *, truncate: bool = False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if truncate:
            self.path.write_text("", encoding="utf-8")
        self._lock = threading.Lock()
        self._closed = False

    def export(self, spans: Sequence["ReadableSpan"]):
        if self._closed:
            return SpanExportResult.FAILURE
        lines = [json.dumps(span_to_dict(s), ensure_ascii=False, sort_keys=False) for s in spans]
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self._closed = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class MemorySpanExporter(SpanExporter):
    """Keeps span dicts in a list. For tests and for building fixtures in-process."""

    def __init__(self):
        self.spans: list[dict] = []
        self._lock = threading.Lock()

    def export(self, spans):
        with self._lock:
            self.spans.extend(span_to_dict(s) for s in spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def clear(self) -> None:
        with self._lock:
            self.spans.clear()


# ------------------------------------------------------------------ reading
def load_spans(path: Union[str, Path]) -> list[dict]:
    """All spans in a JSONL file (blank lines and lines starting with // are skipped)."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            out.append(json.loads(line))
    return out


def write_spans(spans: Iterable[dict], path: Union[str, Path]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for s in spans:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def by_trace(spans: Iterable[dict]) -> dict[str, list[dict]]:
    """trace_id -> spans of that trace, sorted by start time."""
    out: dict[str, list[dict]] = defaultdict(list)
    for s in spans:
        out[s["trace_id"]].append(s)
    for v in out.values():
        v.sort(key=lambda s: (s["start_ms"], s["name"]))
    return dict(out)


def root_of(trace_spans: Sequence[dict]) -> Optional[dict]:
    """The span with no parent inside this trace (the earliest one if there are several)."""
    ids = {s["span_id"] for s in trace_spans}
    roots = [s for s in trace_spans if not s.get("parent_id") or s["parent_id"] not in ids]
    return min(roots, key=lambda s: s["start_ms"]) if roots else None


def tree(trace_spans: Sequence[dict]) -> list[tuple[int, dict]]:
    """Depth-first (depth, span) list: the order a waterfall view draws rows in."""
    kids: dict[Optional[str], list[dict]] = defaultdict(list)
    ids = {s["span_id"] for s in trace_spans}
    for s in trace_spans:
        p = s.get("parent_id")
        kids[p if p in ids else None].append(s)
    for v in kids.values():
        v.sort(key=lambda s: s["start_ms"])
    out: list[tuple[int, dict]] = []

    def walk(parent: Optional[str], depth: int):
        for s in kids.get(parent, []):
            out.append((depth, s))
            walk(s["span_id"], depth + 1)
    walk(None, 0)
    return out
