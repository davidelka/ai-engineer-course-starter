"""Exercise 6: SLOs, error budgets and burn-rate alerts over a day of traces, with YOUR
is_good / burn_rate / alerts_at.

    python labs/22-observability/make_day.py
    python labs/22-observability/slo_report.py results/day.jsonl
    python labs/22-observability/slo_report.py results/day.jsonl --hourly        # burn rate per hour
    python labs/22-observability/slo_report.py results/day.jsonl --reference

SLOs (obskit.slo.DEFAULT_SLOS):
  availability   99.5% of requests do not fail
  latency-8s     95% of successful requests finish within 8 s
  groundedness   97% of checked answers are grounded
Alert rules (obskit.slo.ALERT_RULES): page 1h/5m >= 14.4x, page 6h/30m >= 6x, ticket 24h/2h >= 3x
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from _lab import RESULTS, pick
import obskit.slo as slo_mod
from obskit import load_spans
from obskit.slo import DEFAULT_SLOS, MINUTE_MS, request_events


def hhmm(ms: float) -> str:
    return time.strftime("%H:%M", time.gmtime(ms / 1000))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="?", default=str(RESULTS / "day.jsonl"))
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--hourly", action="store_true")
    a = ap.parse_args(argv)
    src = Path(a.jsonl)
    if not src.exists() and (RESULTS.parent / a.jsonl).exists():
        src = RESULTS.parent / a.jsonl
    if not src.exists():
        raise SystemExit(f"{src} not found: run python labs/22-observability/make_day.py first")
    is_good, s1 = pick("is_good", a.reference)
    burn_rate, s2 = pick("burn_rate", a.reference)
    alerts_at, s3 = pick("alerts_at", a.reference)
    print(f"is_good from {s1}, burn_rate from {s2}, alerts_at from {s3}")
    # The reference budget/scan helpers call obskit.slo.is_good / burn_rate: point them at yours.
    slo_mod.is_good, slo_mod.burn_rate = is_good, burn_rate
    events = request_events(load_spans(src))
    start, end = events[0]["t_ms"], events[-1]["t_ms"]
    day0 = start - start % (24 * 60 * MINUTE_MS)
    print(f"{len(events)} requests, {hhmm(start)} to {hhmm(end)} UTC\n")
    for slo in DEFAULT_SLOS:
        r = slo_mod.budget_report(events, slo)
        print(f"== {slo.name}  target {slo.target:.1%}" + (f"  threshold {slo.threshold:g}" if slo.threshold else ""))
        print(f"   eligible {r['eligible']}, bad {r['bad']}, SLI {r['sli']:.3%}; the day's budget allowed "
              f"{r['budget_bad_allowed']:.1f} bad -> used {r['budget_used']:.0%}")
        if a.hourly:
            row = []
            for hour in range(24):
                b = burn_rate(events, slo, day0 + hour * 60 * MINUTE_MS, day0 + (hour + 1) * 60 * MINUTE_MS)
                row.append(f"{hour:02d}:{b:4.1f}")
            for i in range(0, 24, 8):
                print("   burn/h  " + "  ".join(row[i:i + 8]))
        for tr in slo_mod.scan(events, slo, day0, day0 + 24 * 60 * MINUTE_MS, step_min=5, alerts_fn=alerts_at):
            for f in tr["fired"]:
                print(f"   {hhmm(tr['t_ms'])}  FIRING   {f}")
            for c in tr["cleared"]:
                print(f"   {hhmm(tr['t_ms'])}  resolved {c}")
        print()


if __name__ == "__main__":
    main()
