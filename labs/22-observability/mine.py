"""Your code for lesson 22. Each part is checked by tests in ./tests.

The reference versions live in obskit/ (analyze.py, redact.py, slo.py). Try not to read
them before your tests pass.

    python -m pytest -q labs/22-observability/tests

What you work with
------------------
A span is a plain dict, one line of a JSONL file (obskit.exporters format):

    {"trace_id": "63249c84...", "span_id": "a1b2...", "parent_id": None | "<span_id>",
     "name": "chat mock-model", "kind": "CLIENT", "start_ms": 1761721327000.0,
     "end_ms": 1761721328148.0, "duration_ms": 1148.0, "status": "OK" | "ERROR" | "UNSET",
     "status_message": "", "attributes": {...}, "events": [...], "links": [...], "service": "acme-answer"}

Attributes you need (strings from obskit.semconv):
    "obskit.span.type"        llm | retrieval | tool | agent | cache | other   (may be missing)
    "gen_ai.operation.name"   chat | retrieval | execute_tool | invoke_agent | invoke_workflow ...
    "obskit.cost_usd"         cost of one LLM call, USD (only on LLM spans)

Helpers you may use: obskit.exporters.by_trace(spans) -> {trace_id: [spans sorted by start]},
obskit.exporters.root_of(trace_spans) -> the root span, obskit.semconv.TYPE_BY_OPERATION.
"""

from __future__ import annotations

import json  # noqa: F401
import math  # noqa: F401
import re  # noqa: F401
from typing import Any, Iterable, Mapping, Optional, Sequence

from obskit import semconv as sc  # noqa: F401
from obskit.exporters import by_trace, root_of  # noqa: F401
from obskit.slo import ALERT_RULES, MINUTE_MS, SLO, AlertRule  # noqa: F401


# ------------------------------------------------------------------ exercise 3
def percentile(values: Sequence[float], p: float) -> float:
    """The p-th percentile (p in 0..100) of the values, as a float.

    Same result as numpy's default method (linear interpolation between the closest ranks);
    the values do not have to be sorted.
    percentile([1, 2, 3, 4], 50) == 2.5, percentile([10], 95) == 10.0,
    percentile(range(1, 101), 95) == 95.05.
    Raises ValueError for an empty sequence or p outside 0..100.

    Stuck? HINTS.md -> percentile
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement percentile")


def summarize(spans: Iterable[dict], top_n: int = 5) -> dict:
    """Aggregate spans into the numbers a dashboard shows. Return exactly this shape:

    {
      "spans": int, "traces": int (distinct trace_id),
      "by_type": {"<type>": {"count", "errors", "p50_ms", "p95_ms", "max_ms"}},  # keys sorted
      "per_trace": {"<trace_id>": {"name": <root span name>, "duration_ms": <root duration>,
                                   "cost_usd": <obskit.cost_usd over ALL its spans, 0 if none>,
                                   "llm_calls": <spans of type "llm">,
                                   "error": <True if ANY of its spans has status "ERROR">}},
      "cost": {"total_usd", "mean_per_trace_usd", "p95_per_trace_usd"},   # over per-trace costs
      "latency": {"p50_ms", "p95_ms"},                  # over ROOT durations, one per trace
      "slowest": [{"trace_id", "name", "duration_ms"}, ...],  # top_n by root duration,
                                                              # longest first, ties by trace_id
    }
    Span type: attributes["obskit.span.type"] if present, else the type that
    sc.TYPE_BY_OPERATION gives for attributes["gen_ai.operation.name"], else "other".
    "errors" counts spans with status "ERROR". Percentiles come from your percentile().

    Stuck? HINTS.md -> summarize
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement summarize")


# ------------------------------------------------------------------ exercise 4
def israeli_id_valid(s: str) -> bool:
    """True when s is exactly 9 digits with a correct Israeli ID check digit, else False.

    "123456782" -> True, "123456789" -> False (bad check digit), "12345678" -> False (length).

    Stuck? HINTS.md -> israeli_id_valid
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement israeli_id_valid")


def redact_text(text: str) -> tuple[str, int]:
    """Replace personal data and return (new_text, number_of_replacements).

      emails                    -> "[EMAIL]"   e.g. dana.levi@acme.example
      Israeli phone numbers     -> "[PHONE]"   mobile 05X, landline 02/03/04/08/09, or 07X, plus
                                               7 digits; optional "-" or space after the prefix
                                               and after 3 more digits; +972 may replace the
                                               leading 0 (+972-52-123-4567, +972 52 1234567)
      Israeli ID numbers        -> "[IL_ID]"   exactly 9 digits that pass israeli_id_valid();
                                               other 9-digit numbers stay
    A phone or ID inside a longer run of digits is not replaced. The digits of an email are
    never treated as a phone or ID, and a phone number is never counted as an ID.
    Empty text -> ("", 0).

    Stuck? HINTS.md -> redact_text
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement redact_text")


def redact_attributes(attrs: Mapping[str, Any], skip: Iterable[str] = ()) -> tuple[dict, int]:
    """Return (a NEW dict, total replacements). Never modify `attrs`.

      - str values are redacted with redact_text (JSON strings such as gen_ai.input.messages
        are just strings: redact them as text);
      - list/tuple values: each str item is redacted, the container type is kept;
      - anything else (int, float, bool, None) and keys listed in `skip`: copied as is.

    Stuck? HINTS.md -> redact_attributes
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement redact_attributes")


# ------------------------------------------------------------------ exercise 6
# An event is one request (one trace), built by obskit.slo.request_events():
#   {"trace_id", "t_ms": <root start>, "duration_ms", "error": bool,
#    "grounded": True | False | None, "cost_usd": float}
# An SLO: SLO(name, kind, target, threshold), kind in availability | latency | grounded | cost,
# slo.budget == 1 - slo.target.

def is_good(event: dict, slo: SLO) -> Optional[bool]:
    """True = good, False = bad, None = not eligible (counts neither way).

      availability: bad when the request failed (event["error"])
      latency:      not eligible when the request failed (failures belong to availability);
                    good when duration_ms <= slo.threshold
      grounded:     not eligible when the request failed or "grounded" is None;
                    good when grounded is True
      cost:         good when cost_usd <= slo.threshold
    Unknown kind: raise ValueError.

    Stuck? HINTS.md -> is_good
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement is_good")


def burn_rate(events: Sequence[dict], slo: SLO, start_ms: float, end_ms: float) -> float:
    """The burn rate of `slo` over the window start_ms <= t_ms < end_ms (start included, end
    excluded), counting only eligible events (is_good not None). Returns a float: 1.0 means the
    error budget is spent exactly at the allowed pace. 0.0 when no event is eligible.
    Example: target 0.995, 2 bad out of 100 eligible -> 4.0

    Stuck? HINTS.md -> burn_rate
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement burn_rate")


def alerts_at(events: Sequence[dict], slo: SLO, now_ms: float,
              rules: Sequence[AlertRule] = ALERT_RULES) -> list[dict]:
    """Multiwindow, multi-burn-rate alerting, evaluated at now_ms.

    A rule fires when BOTH of its windows ending at now_ms (rule.long_min and rule.short_min
    minutes long, now_ms excluded) burn at least rule.burn.
    Returns one dict per firing rule, in the order of `rules`, with exactly these keys:
        {"severity": rule.severity, "long_min": rule.long_min, "short_min": rule.short_min,
         "threshold": rule.burn, "long_burn": float, "short_burn": float}

    Stuck? HINTS.md -> alerts_at
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement alerts_at")
