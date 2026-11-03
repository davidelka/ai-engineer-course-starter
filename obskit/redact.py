"""PII redaction for spans: emails, Israeli phone numbers and Israeli ID numbers.

Reference implementation for lesson 22, exercise 4 (labs/22-observability/mine.py has
the TODO versions). Two layers:

  redact_text(text)          -> (new_text, n_replacements)
  redact_attributes(attrs)   -> (new_attrs, n_replacements)   str values, lists of str,
                                                               and JSON strings alike
  RedactingSpanProcessor     an OpenTelemetry SpanProcessor that redacts every span
                             BEFORE it reaches the exporter behind it

Why in the process and not only in a Collector: the first hop already carries the data.
If spans leave the machine unredacted (to a SaaS backend, or a Collector on another
host), the redaction came too late. A Collector redaction processor is a good SECOND
line (see labs/22-observability/collector/otel-collector.yaml).

Israeli ID numbers (teudat zehut) are 9 digits with a check digit: multiply the digits by
1,2,1,2,... from the left, add the digits of each product, and the sum must divide by 10.
Checking it avoids redacting every 9-digit number (order ids, amounts). The trade-off is
real: an ID typed with a typo is not redacted. For the strictest setting, pass
validate_ids=False and every bare 9-digit number is treated as an ID.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable, Mapping, Optional

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# +972-52-123-4567, +972 52 1234567, 052-1234567, 0521234567, 03-1234567, 03 123 4567
PHONE_RE = re.compile(r"(?<![\d+])(?:\+972[-\s]?|0)(?:5\d|7\d|[23489])[-\s]?\d{3}[-\s]?\d{4}(?!\d)")
ID_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")

EMAIL_TOKEN, PHONE_TOKEN, ID_TOKEN = "[EMAIL]", "[PHONE]", "[IL_ID]"


def israeli_id_valid(s: str) -> bool:
    """True when s is 9 digits whose check digit is right ("123456782" is valid)."""
    if not (len(s) == 9 and s.isdigit()):
        return False
    total = 0
    for i, ch in enumerate(s):
        p = int(ch) * (1 if i % 2 == 0 else 2)
        total += p - 9 if p > 9 else p
    return total % 10 == 0


def redact_text(text: str, *, validate_ids: bool = True) -> tuple[str, int]:
    """Replace emails, phones and Israeli IDs. Order matters: emails first (an email can
    contain digits), then phones, then bare 9-digit IDs."""
    if not text:
        return text, 0
    n = 0

    def sub(rx, token, s, keep=None):
        nonlocal n

        def rep(m):
            nonlocal n
            if keep is not None and keep(m.group(0)):
                return m.group(0)
            n += 1
            return token
        return rx.sub(rep, s)

    out = sub(EMAIL_RE, EMAIL_TOKEN, text)
    out = sub(PHONE_RE, PHONE_TOKEN, out)
    out = sub(ID_RE, ID_TOKEN, out, keep=(lambda s: not israeli_id_valid(s)) if validate_ids else None)
    return out, n


def _redact_value(v: Any, redactor: Callable[[str], tuple[str, int]]) -> tuple[Any, int]:
    if isinstance(v, str):
        return redactor(v)
    if isinstance(v, (list, tuple)):
        total, out = 0, []
        for x in v:
            y, k = _redact_value(x, redactor)
            out.append(y)
            total += k
        return (tuple(out) if isinstance(v, tuple) else out), total
    return v, 0


def redact_attributes(attrs: Mapping[str, Any], *, skip: Iterable[str] = (),
                      redactor: Optional[Callable[[str], tuple[str, int]]] = None) -> tuple[dict, int]:
    """A NEW dict with every string value redacted (lists of strings too).

    JSON strings (gen_ai.input.messages and friends) are redacted as text: the tokens
    contain no quotes or backslashes, so the JSON stays valid. Keys in `skip` are copied
    unchanged (ids, hashes, anything you know is safe).
    """
    redactor = redactor or redact_text
    skip = set(skip)
    out, total = {}, 0
    for k, v in attrs.items():
        if k in skip:
            out[k] = v
            continue
        out[k], n = _redact_value(v, redactor)
        total += n
    return out, total


# ------------------------------------------------------------------ OpenTelemetry processor
try:
    from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
except ImportError:  # pragma: no cover
    SpanProcessor = object  # type: ignore


class RedactingSpanProcessor(SpanProcessor):
    """Wraps another processor (usually a BatchSpanProcessor with your exporter) and hands
    it a redacted COPY of every finished span. Span attributes are read-only once a span
    has ended, so we build a new ReadableSpan instead of mutating.

        provider.add_span_processor(RedactingSpanProcessor(BatchSpanProcessor(exporter)))

    `redactor(text) -> (text, n)` defaults to redact_text; the lab passes yours.
    """

    def __init__(self, inner: "SpanProcessor", *, redactor: Optional[Callable[[str], tuple[str, int]]] = None,
                 skip: Iterable[str] = ()):
        self.inner = inner
        self.redactor = redactor or redact_text
        self.skip = tuple(skip)

    def on_start(self, span, parent_context=None) -> None:
        self.inner.on_start(span, parent_context=parent_context)

    def on_end(self, span: "ReadableSpan") -> None:
        attrs, n = redact_attributes(span.attributes or {}, skip=self.skip, redactor=self.redactor)
        events = []
        for e in span.events:
            ea, k = redact_attributes(e.attributes or {}, skip=self.skip, redactor=self.redactor)
            n += k
            events.append(Event(e.name, ea, e.timestamp))
        desc = span.status.description if span.status else None
        status = span.status
        if desc:
            new_desc, k = self.redactor(desc)
            if k:
                n += k
                from opentelemetry.trace import Status
                status = Status(span.status.status_code, new_desc)
        if n:
            attrs["obskit.redacted"] = n
        copy = ReadableSpan(
            name=span.name, context=span.get_span_context(), parent=span.parent, resource=span.resource,
            attributes=attrs, events=events, links=span.links, kind=span.kind,
            instrumentation_scope=span.instrumentation_scope, status=status,
            start_time=span.start_time, end_time=span.end_time,
        )
        self.inner.on_end(copy)

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)


def redact_span_dict(span: dict, redactor: Optional[Callable[[str], tuple[str, int]]] = None) -> dict:
    """Same idea for an already exported span dict (to clean an existing JSONL file)."""
    redactor = redactor or redact_text
    s = json.loads(json.dumps(span))
    s["attributes"], n = redact_attributes(s.get("attributes", {}), redactor=redactor)
    for e in s.get("events", []):
        e["attributes"], k = redact_attributes(e.get("attributes", {}), redactor=redactor)
        n += k
    if s.get("status_message"):
        s["status_message"], k = redactor(s["status_message"])
        n += k
    if n:
        s["attributes"]["obskit.redacted"] = n
    return s
