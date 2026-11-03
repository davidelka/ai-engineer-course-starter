"""Exercise 3: latency per span type, cost per trace, the slowest traces, with YOUR summarize().

    python labs/22-observability/trace_stats.py labs/22-observability/fixtures/forensic.jsonl
    python labs/22-observability/trace_stats.py results/traces.jsonl --top 3
    python labs/22-observability/trace_stats.py ... --reference      # the obskit version
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _lab import RESULTS, pick
from obskit import load_spans
from obskit.analyze import format_summary, tokens, ttft_stats


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args(argv)
    src = Path(a.jsonl)
    if not src.exists() and (RESULTS.parent / a.jsonl).exists():
        src = RESULTS.parent / a.jsonl
    spans = load_spans(src)
    summarize, origin = pick("summarize", a.reference)
    s = summarize(spans, top_n=a.top)
    print(f"summarize() from {origin}\n")
    print(format_summary(s, top_n=a.top))
    t = ttft_stats(spans)
    if t["count"]:
        print(f"\ntime to first chunk (streamed LLM calls): n={t['count']}  p50 {t['p50_s']:.3f}s  p95 {t['p95_s']:.3f}s")
    tk = tokens(spans)
    print(f"tokens: input {tk['input']:,}  output {tk['output']:,}  cache read {tk['cache_read']:,} "
          f"({tk['cache_read_share']:.0%} of input)  cache write {tk['cache_write']:,}")


if __name__ == "__main__":
    main()
