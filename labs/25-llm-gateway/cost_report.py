"""Exercise 6, part 2: a cost and anomaly report from the audit log.

    python labs/25-llm-gateway/cost_report.py                              # state/audit_traffic.jsonl
    python labs/25-llm-gateway/cost_report.py --audit labs/25-llm-gateway/state/audit.jsonl
    python labs/25-llm-gateway/cost_report.py --json > report.json

Everything comes from gatewaykit.audit.cost_report(), which only reads the JSONL
lines the gateway wrote. No provider console, no invoice: the gateway saw every
request, so it can attribute every cent to a team and a key. All times are UTC.
"""

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from lablib import STATE

from gatewaykit.audit import cost_report, read_audit


def bar(value, top, width=28):
    return "#" * max(1 if value else 0, round(width * value / top)) if top else ""


def section(title):
    print(f"\n=== {title}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audit", default=str(STATE / "audit_traffic.jsonl"))
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    records = list(read_audit(a.audit))
    if not records:
        raise SystemExit(f"no records in {a.audit}. Run traffic.py first.")
    rep = cost_report(records)
    if a.json:
        print(json.dumps(rep, indent=2))
        return

    t = rep["total"]
    section("Total")
    print(f"  requests {t['requests']}   allowed {t['allowed']}   denied {t['denied']}   "
          f"with fallback {t['fallbacks']}   cache hits {t['cache_hits']}   cost ${t['cost_usd']:.4f}")

    for name in ("team", "key_id", "model", "deployment"):
        rows = rep[f"by_{name}"]
        section(f"By {name}")
        top = max((r["cost_usd"] for r in rows.values()), default=0)
        for k, r in rows.items():
            share = 100 * r["cost_usd"] / t["cost_usd"] if t["cost_usd"] else 0
            print(f"  {k:22} ${r['cost_usd']:8.4f} {share:5.1f}%  {r['requests']:5} req  "
                  f"in {r['input_tokens']:>8,} out {r['output_tokens']:>7,}  {bar(r['cost_usd'], top)}")

    section("By day (UTC)")
    days = rep["by_day"]
    top = max((r["cost_usd"] for r in days.values()), default=0)
    for day in sorted(days):
        r = days[day]
        name = datetime.strptime(day, "%Y-%m-%d").strftime("%a")
        print(f"  {day} {name}  ${r['cost_usd']:7.4f}  {r['requests']:4} req  {bar(r['cost_usd'], top)}")

    section("Denied, by reason")
    for reason, n in rep["denied_by_reason"].items():
        print(f"  {reason:24} {n}")
    section("Denied, by key (unknown keys are not attributed)")
    for key, n in sorted(rep["denied_by_key"].items(), key=lambda kv: -kv[1]):
        print(f"  {key:24} {n}")

    section("Requests by hour of day (UTC), per key")
    for key, hours in sorted(rep["hours_by_key"].items()):
        row = "".join(" .:-=+*#%@"[min(9, round(9 * hours.get(h, 0) / max(hours.values())))] for h in range(24))
        night = sum(n for h, n in hours.items() if int(h) < 5)
        print(f"  {key:18} |{row}|  00-05h: {night}")
    print(f"  {'':18}  0         1         2   ")
    print(f"  {'':18}  0123456789012345678901234")

    section("Daily spend per key vs that key's median day")
    per = defaultdict(lambda: defaultdict(float))
    for r in records:
        if r.get("status") == 200 and r.get("key_id"):
            per[r["key_id"]][datetime.fromtimestamp(r["ts"], tz=timezone.utc).strftime("%Y-%m-%d")] += r.get("cost_usd") or 0
    for key, days_ in sorted(per.items()):
        med = statistics.median(days_.values())
        worst_day, worst = max(days_.items(), key=lambda kv: kv[1])
        flag = "   <-- look at this" if med and worst > 4 * med else ""
        print(f"  {key:18} median ${med:.4f}/day   max ${worst:.4f} on {worst_day}{flag}")

    print("\nQuestions: which team pays most, and is that expected? Which key and which hours look wrong,")
    print("and which THREE independent signals in this report support that? What happened on Tuesday?")


if __name__ == "__main__":
    main()
