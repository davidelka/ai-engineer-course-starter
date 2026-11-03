"""The audit log: one JSON line per request, allowed or denied.

What goes in: who (key id, team), what (model asked, deployment used, classification,
policy rule), how it went (status, attempts, latency), how much (tokens, cost), and
what was redacted (counts and fingerprints). What does NOT go in by default: the
prompt and the answer. log_content: redacted keeps the REDACTED prompt, which is
still sensitive (internal data) and needs the same retention as the log.

The log is also the source of truth for spend: at startup the gateway rebuilds every
key's budget window from it (rebuild_spend), so a restart does not reset budgets.
LiteLLM solves the same problem with Postgres; that is why its virtual keys and
budgets need a database.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union


class AuditLog:
    def __init__(self, path: Optional[Union[str, Path]] = None):
        self.path = Path(path) if path else None
        self.memory: list[dict] = []  # always kept too: tests and /admin read it
        self._lock = threading.Lock()

    def write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.memory.append(record)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")


def read_audit(path: Union[str, Path]) -> Iterator[dict]:
    p = Path(path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def prune(path: Union[str, Path], retention_days: float, now: Optional[float] = None) -> int:
    """Delete records older than the retention period. Returns how many were removed.

    Retention is a governance decision with two sides: keep audit records long enough
    for investigations and cost disputes (Acme: 1 year), and not a day longer, because
    every stored record is something that can leak."""
    now = time.time() if now is None else now
    cutoff = now - retention_days * 86400
    records = list(read_audit(path))
    keep = [r for r in records if r.get("ts", now) >= cutoff]
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in keep),
                          encoding="utf-8")
    return len(records) - len(keep)


def rebuild_spend(records: Iterable[dict], windows: dict[str, Optional[float]], now: float) -> dict[str, float]:
    """Spend per key inside its current budget window.

    windows: {key_id: period_seconds or None}. With a period, only records newer than
    (now - period) count. This is a sliding approximation of the fixed window the ledger
    uses, good enough after a restart and never lower than the truth."""
    spent: dict[str, float] = defaultdict(float)
    for r in records:
        key = r.get("key_id")
        if not key or not r.get("cost_usd"):
            continue
        period = windows.get(key)
        if period and r.get("ts", 0) < now - period:
            continue
        spent[key] += float(r["cost_usd"])
    return dict(spent)


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def cost_report(records: Iterable[dict]) -> dict:
    """Aggregate the audit log for a cost report: by team, key, model, deployment and day,
    plus denials by reason and the share of requests served from cache."""
    by = {name: defaultdict(lambda: {"requests": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0})
          for name in ("team", "key_id", "model", "deployment", "day")}
    denied: dict[str, int] = defaultdict(int)
    denied_by_key: dict[str, int] = defaultdict(int)
    hours_by_key: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    total = {"requests": 0, "allowed": 0, "denied": 0, "cache_hits": 0, "fallbacks": 0, "cost_usd": 0.0}
    for r in records:
        if r.get("admin"):
            continue  # key created / revoked: not a model request
        total["requests"] += 1
        if r.get("status", 200) != 200:
            total["denied"] += 1
            denied[r.get("reason") or str(r.get("status"))] += 1
            if r.get("key_id"):
                denied_by_key[r["key_id"]] += 1
            continue
        total["allowed"] += 1
        total["cache_hits"] += bool(r.get("cache_hit"))
        total["fallbacks"] += len([a for a in r.get("attempts", []) if a.get("outcome") != "ok"]) > 0
        cost = float(r.get("cost_usd") or 0.0)
        total["cost_usd"] += cost
        usage = r.get("usage") or {}
        keys = {"team": r.get("team"), "key_id": r.get("key_id"), "model": r.get("model"),
                "deployment": r.get("deployment"), "day": _day(r.get("ts", 0))}
        for name, value in keys.items():
            row = by[name][value or "-"]
            row["requests"] += 1
            row["cost_usd"] += cost
            row["input_tokens"] += int(usage.get("input_tokens", 0))
            row["output_tokens"] += int(usage.get("output_tokens", 0))
        hours_by_key[r.get("key_id") or "-"][datetime.fromtimestamp(r.get("ts", 0), tz=timezone.utc).hour] += 1
    return {"total": total,
            **{f"by_{name}": dict(sorted(rows.items(), key=lambda kv: -kv[1]["cost_usd"])) for name, rows in by.items()},
            "denied_by_reason": dict(sorted(denied.items(), key=lambda kv: -kv[1])),
            "denied_by_key": dict(denied_by_key),
            "hours_by_key": {k: dict(v) for k, v in hours_by_key.items()}}
