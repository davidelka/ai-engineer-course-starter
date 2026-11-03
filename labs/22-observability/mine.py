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
    """The p-th percentile (0..100) with linear interpolation (numpy's default):
        xs = sorted(values); rank = (len(xs) - 1) * p / 100
        result = xs[floor(rank)] + (xs[ceil(rank)] - xs[floor(rank)]) * (rank - floor(rank))
    percentile([1, 2, 3, 4], 50) == 2.5, percentile([10], 95) == 10.0
    Raise ValueError for an empty sequence or p outside 0..100.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement percentile")


def summarize(spans: Iterable[dict], top_n: int = 5) -> dict:
    """Aggregate spans into the numbers a dashboard shows. Return exactly this shape:

    {
      "spans": <number of spans>,
      "traces": <number of distinct trace_id>,
      "by_type": {                      # one entry per span type, keys sorted alphabetically
         "<type>": {"count": int, "errors": int, "p50_ms": float, "p95_ms": float, "max_ms": float},
      },
      "per_trace": {
         "<trace_id>": {"name": <root span name>, "duration_ms": <root duration_ms>,
                        "cost_usd": <sum of obskit.cost_usd over ALL spans of the trace, 0 if none>,
                        "llm_calls": <number of spans of type "llm">,
                        "error": <True if ANY span of the trace has status "ERROR">},
      },
      "cost": {"total_usd": <sum over traces>, "mean_per_trace_usd": <mean over traces>,
               "p95_per_trace_usd": <percentile 95 of per-trace cost>},
      "latency": {"p50_ms": ..., "p95_ms": ...},     # over ROOT durations, one per trace
      "slowest": [{"trace_id", "name", "duration_ms"}, ...],   # top_n traces by root duration,
                                                               # longest first, ties by trace_id
    }
    Span type: attributes["obskit.span.type"] if present, else
    sc.TYPE_BY_OPERATION.get(attributes["gen_ai.operation.name"]), else "other".
    "errors" counts spans whose status is "ERROR". Use your percentile().
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement summarize")


# ------------------------------------------------------------------ exercise 4
def israeli_id_valid(s: str) -> bool:
    """True when s is exactly 9 digits and the check digit is right:
    multiply the digits by 1,2,1,2,1,2,1,2,1 (left to right); when a product is above 9,
    subtract 9 (that is the sum of its two digits); the total must divide by 10.
    "123456782" -> True, "123456789" -> False, "12345678" -> False.
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement israeli_id_valid")


def redact_text(text: str) -> tuple[str, int]:
    """Replace personal data and return (new_text, number_of_replacements).

    In this order (an email can contain digits, a phone number can look like an ID):
      1. emails                      -> "[EMAIL]"     e.g. dana.levi@acme.example
      2. Israeli phone numbers       -> "[PHONE]"
           mobile 05X + 7 digits, landline 0[2-4,8,9] + 7 digits, 07X + 7 digits,
           with or without "-" or spaces after the prefix and after 3 more digits,
           or with +972 instead of the leading 0 (+972-52-123-4567, +972 52 1234567).
           Not inside a longer run of digits.
      3. Israeli ID numbers          -> "[IL_ID]"     a run of EXACTLY 9 digits (not part of
           a longer number) that passes israeli_id_valid(). Other 9-digit numbers stay.
    Empty text -> ("", 0).
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement redact_text")


def redact_attributes(attrs: Mapping[str, Any], skip: Iterable[str] = ()) -> tuple[dict, int]:
    """Return (a NEW dict, total replacements). Never modify `attrs`.
      - str values: redact_text
      - list/tuple values: redact each str item, keep the container type
      - anything else (int, float, bool, None): copied as is
      - keys listed in `skip`: copied as is
    JSON strings (like gen_ai.input.messages) are just strings: redact them as text.
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
      availability: good when not event["error"]
      latency:      None when event["error"] (failures belong to availability);
                    otherwise good when duration_ms <= slo.threshold
      grounded:     None when event["error"] or event["grounded"] is None;
                    otherwise good when grounded is True
      cost:         good when cost_usd <= slo.threshold
    Unknown kind: raise ValueError.
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement is_good")


def burn_rate(events: Sequence[dict], slo: SLO, start_ms: float, end_ms: float) -> float:
    """Over the events with start_ms <= t_ms < end_ms that are eligible (is_good not None):
        (bad / eligible) / slo.budget
    0.0 when no event is eligible. Example: target 0.995, 2 bad out of 100 -> 0.02/0.005 = 4.0
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement burn_rate")


def alerts_at(events: Sequence[dict], slo: SLO, now_ms: float,
              rules: Sequence[AlertRule] = ALERT_RULES) -> list[dict]:
    """Multiwindow, multi-burn-rate alerting, evaluated at now_ms.
    A rule fires when BOTH windows ending at now_ms burn at least rule.burn:
        long window  [now_ms - rule.long_min * MINUTE_MS,  now_ms)
        short window [now_ms - rule.short_min * MINUTE_MS, now_ms)
    Return one dict per firing rule, in the order of `rules`:
        {"severity": rule.severity, "long_min": rule.long_min, "short_min": rule.short_min,
         "threshold": rule.burn, "long_burn": <float>, "short_burn": <float>}
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement alerts_at")
