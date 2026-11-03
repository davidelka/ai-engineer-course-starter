"""SLOs over traces: good/bad events, error budgets, burn rates and multiwindow alerts.

Reference for lesson 22, exercise 6 (labs/22-observability/mine.py).

An SLI here is a ratio of good requests to eligible requests. One request = one trace;
its "event" is computed from the root span and the spans under it (request_events).

Burn rate (Google SRE workbook, "Alerting on SLOs"): how fast the error budget is being
spent relative to the SLO. With target 99.5% the budget is 0.5% bad requests; a window
where 2% of requests are bad burns at 2 / 0.5 = 4x: at that pace a 30-day budget lasts
7.5 days.

Multiwindow, multi-burn-rate alerts: an alert fires only when BOTH a long window and a
short window (1/12 of the long one) burn above the threshold. The long window gives
significance, the short one makes the alert stop soon after the problem stops. The page
rules below are the workbook's table for a 30-day SLO (14.4x over 1h, 6x over 6h); the
ticket rule is the 24h/2h at 3x from the workbook's example configuration, because a
one-day lab dataset cannot have a 3-day window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from . import semconv as sc
from .analyze import span_cost
from .exporters import by_trace, root_of

MINUTE_MS = 60_000.0


@dataclass(frozen=True)
class SLO:
    name: str
    kind: str            # availability | latency | grounded | cost
    target: float        # e.g. 0.995
    threshold: float = 0.0   # ms for latency, USD for cost

    @property
    def budget(self) -> float:
        return 1.0 - self.target


@dataclass(frozen=True)
class AlertRule:
    severity: str        # page | ticket
    long_min: float
    short_min: float
    burn: float


ALERT_RULES = (AlertRule("page", 60, 5, 14.4), AlertRule("page", 360, 30, 6.0), AlertRule("ticket", 1440, 120, 3.0))

DEFAULT_SLOS = (
    SLO("availability", "availability", 0.995),
    SLO("latency-8s", "latency", 0.95, 8000.0),
    SLO("groundedness", "grounded", 0.97),
)


def request_events(spans: Iterable[dict]) -> list[dict]:
    """One event per trace: {trace_id, t_ms, duration_ms, error, grounded, cost_usd}.

    error    the request failed for the user (see request_error: the ROOT span is ERROR)
    grounded the root's obskit.grounded attribute (True/False), or None if not checked
    cost_usd the sum of obskit.cost_usd over every span in the trace
    """
    out = []
    for tid, ss in by_trace(spans).items():
        root = root_of(ss)
        a = root.get("attributes", {})
        g = a.get(sc.GROUNDED)
        out.append({"trace_id": tid, "t_ms": root["start_ms"], "duration_ms": root["duration_ms"],
                    "error": request_error(root), "grounded": (bool(g) if g is not None else None),
                    "cost_usd": sum(span_cost(s) for s in ss)})
    out.sort(key=lambda e: e["t_ms"])
    return out


def request_error(root: dict) -> bool:
    """A request failed for the USER when its root span is ERROR. A retried child span
    that later succeeded is not a failed request; a fallback answer is not an error here
    (that is what the groundedness SLO is for)."""
    return root.get("status") == "ERROR"


def is_good(event: dict, slo: SLO) -> Optional[bool]:
    """True good, False bad, None not eligible (does not count either way)."""
    if slo.kind == "availability":
        return not event["error"]
    if slo.kind == "latency":
        if event["error"]:
            return None            # failures belong to the availability SLO
        return event["duration_ms"] <= slo.threshold
    if slo.kind == "grounded":
        if event["error"] or event.get("grounded") is None:
            return None
        return bool(event["grounded"])
    if slo.kind == "cost":
        return event["cost_usd"] <= slo.threshold
    raise ValueError(f"unknown SLO kind {slo.kind!r}")


def window_counts(events: Sequence[dict], slo: SLO, start_ms: float, end_ms: float) -> tuple[int, int]:
    """(bad, eligible) among events with start_ms <= t_ms < end_ms."""
    bad = eligible = 0
    for e in events:
        if start_ms <= e["t_ms"] < end_ms:
            g = is_good(e, slo)
            if g is None:
                continue
            eligible += 1
            bad += (g is False)
    return bad, eligible


def burn_rate(events: Sequence[dict], slo: SLO, start_ms: float, end_ms: float) -> float:
    """(bad / eligible) / (1 - target) over [start_ms, end_ms). 0.0 when nothing is eligible."""
    bad, eligible = window_counts(events, slo, start_ms, end_ms)
    if eligible == 0:
        return 0.0
    return (bad / eligible) / slo.budget


def alerts_at(events: Sequence[dict], slo: SLO, now_ms: float,
              rules: Sequence[AlertRule] = ALERT_RULES) -> list[dict]:
    """The rules that fire at now_ms: both windows ending at now_ms burn >= rule.burn."""
    out = []
    for r in rules:
        long_b = burn_rate(events, slo, now_ms - r.long_min * MINUTE_MS, now_ms)
        short_b = burn_rate(events, slo, now_ms - r.short_min * MINUTE_MS, now_ms)
        if long_b >= r.burn and short_b >= r.burn:
            out.append({"severity": r.severity, "long_min": r.long_min, "short_min": r.short_min,
                        "threshold": r.burn, "long_burn": long_b, "short_burn": short_b})
    return out


def budget_report(events: Sequence[dict], slo: SLO) -> dict:
    bad, eligible = window_counts(events, slo, float("-inf"), float("inf"))
    sli = 1.0 - bad / eligible if eligible else 1.0
    allowed = slo.budget * eligible
    return {"slo": slo.name, "target": slo.target, "eligible": eligible, "bad": bad, "sli": sli,
            "budget_bad_allowed": allowed, "budget_used": (bad / allowed) if allowed else 0.0}


def scan(events: Sequence[dict], slo: SLO, start_ms: float, end_ms: float, *, step_min: float = 5,
         rules: Sequence[AlertRule] = ALERT_RULES, alerts_fn=None) -> list[dict]:
    """Evaluate the alert rules every step_min minutes, like a Prometheus rule would, and
    return the transitions: [{"t_ms", "fired": [...labels], "cleared": [...labels]}]."""
    fn = alerts_fn or alerts_at
    t, active, out = start_ms, set(), []
    while t <= end_ms:
        now = {f"{a['severity']} {int(a['long_min'])}m/{int(a['short_min'])}m >= {a['threshold']}x"
               for a in fn(events, slo, t, rules)}
        fired, cleared = sorted(now - active), sorted(active - now)
        if fired or cleared:
            out.append({"t_ms": t, "fired": fired, "cleared": cleared})
        active = now
        t += step_min * MINUTE_MS
    return out
