"""Helpers for the load-test sweep: read locust's CSV, find the knee, draw the chart.

The knee: as concurrency grows, throughput rises until the server's real
capacity is reached; after that, extra users only add queueing delay (and then
429s). We locate it with "power" = throughput / p95 latency, a classic measure
(Kleinrock): it rises while added load buys throughput, and falls once added
load buys only latency. The level with the highest power is the knee.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Level:
    users: int
    rps: float  # successful streams per second
    p50_ms: float
    p95_ms: float
    ttft_p50_ms: float
    ttft_p95_ms: float
    requests: int
    failures: int  # includes 429 shed

    @property
    def power(self) -> float:
        return self.rps / self.p95_ms if self.p95_ms > 0 else 0.0

    def as_dict(self) -> dict:
        return {**asdict(self), "power": round(self.power * 1000, 3)}


def _num(row: dict, *names: str) -> float:
    for n in names:
        v = row.get(n)
        if v not in (None, "", "N/A"):
            try:
                return float(v)
            except ValueError:
                pass
    return 0.0


def read_locust_stats(path: str | Path) -> dict[str, dict]:
    """<prefix>_stats.csv -> {name: {"requests","failures","p50","p95","p99","rps"}}."""
    out: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("Name", "")
            out[name] = {"requests": int(_num(row, "Request Count")), "failures": int(_num(row, "Failure Count")),
                         "p50": _num(row, "50%", "Median Response Time"), "p95": _num(row, "95%"),
                         "p99": _num(row, "99%"), "rps": _num(row, "Requests/s"),
                         "fail_rps": _num(row, "Failures/s")}
    return out


def level_from_stats(users: int, stats: dict[str, dict], total: str = "stream total",
                     ttft: str = "TTFT", shed_name: str = "429 shed") -> Level:
    t = stats.get(total, {})
    f = stats.get(ttft, {})
    shed = stats.get(shed_name, {})
    ok_rps = max(0.0, t.get("rps", 0.0) - t.get("fail_rps", 0.0))
    return Level(users, round(ok_rps, 2), t.get("p50", 0.0), t.get("p95", 0.0), f.get("p50", 0.0),
                 f.get("p95", 0.0), t.get("requests", 0) + shed.get("requests", 0),
                 t.get("failures", 0) + shed.get("failures", 0))


def find_knee(levels: list[Level]) -> Optional[Level]:
    good = [lv for lv in levels if lv.p95_ms > 0 and lv.rps > 0]
    return max(good, key=lambda lv: lv.power) if good else None


def write_csv(levels: list[Level], path: str | Path) -> None:
    rows = [lv.as_dict() for lv in levels]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def plot(levels: list[Level], path: str | Path, title: str = "") -> bool:
    """Latency percentiles and TTFT (left axis) and throughput (right axis) vs users.
    Returns False when matplotlib is not installed (the CSV is still written)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    u = [lv.users for lv in levels]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(u, [lv.p50_ms for lv in levels], marker="o", label="total p50")
    ax.plot(u, [lv.p95_ms for lv in levels], marker="o", label="total p95")
    ax.plot(u, [lv.ttft_p50_ms for lv in levels], marker="s", linestyle="--", label="TTFT p50")
    ax.plot(u, [lv.ttft_p95_ms for lv in levels], marker="s", linestyle="--", label="TTFT p95")
    ax.set_xscale("log", base=2)
    ax.set_xticks(u, [str(x) for x in u])
    ax.set_xlabel("concurrent users")
    ax.set_ylabel("milliseconds")
    ax2 = ax.twinx()
    ax2.bar(u, [lv.rps for lv in levels], width=[x * 0.25 for x in u], alpha=0.2, color="gray",
            label="successful streams/s")
    ax2.set_ylabel("streams per second")
    knee = find_knee(levels)
    if knee:
        ax.axvline(knee.users, color="red", linestyle=":", label=f"knee ({knee.users} users)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    ax.set_title(title or "Company Brain API under load")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True
