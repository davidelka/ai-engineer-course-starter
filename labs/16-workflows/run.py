"""Run the access-request workflow: start threads, stream progress, crash on purpose, resume.

    python labs/16-workflows/run.py --show-graph               # the graph as Mermaid + ASCII list of edges
    python labs/16-workflows/run.py --list                     # the sample requests
    python labs/16-workflows/run.py --sample r2                # one sample, offline (FakeLLM)
    python labs/16-workflows/run.py --all                      # all eight samples
    python labs/16-workflows/run.py --text "I need Miro" --requester dana.levi@acme.example
    python labs/16-workflows/run.py --sample r2 --crash-in file_request   # dies after filing, before the checkpoint
    python labs/16-workflows/run.py --resume r2                # continue a stopped thread (same thread id)
    python labs/16-workflows/run.py --sample r1 --slow 3       # 3 s per node: kill -9 it by hand, then --resume
    python labs/16-workflows/run.py --sample r1 --fault timeout:get_system_info:2   # node-level retries
    python labs/16-workflows/run.py --status r2                # where a thread is, plus its DB rows
    python labs/16-workflows/run.py --reset                    # delete results/*.db
    add --model anthropic:claude-haiku-5-5 for the real LLM steps, --mine to use your mine.py
"""

from __future__ import annotations

import argparse
import sys
import time

import _lab
from _lab import CHECKPOINTS_DB, REQUESTS_DB, SAMPLES, add_common_args, make_app, mine_parts_arg

from flowkit import runner, store
from flowkit.nodes import utc_now


def show_graph(app) -> None:
    g = app.get_graph()
    print(g.draw_mermaid())
    print("Paste the Mermaid text into https://mermaid.live to see it drawn.\n")
    print("Edges (dotted = conditional):")
    for e in g.edges:
        print(f"  {e.source:>18} {'-.->' if e.conditional else '--->'} {e.target}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    ap.add_argument("--show-graph", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sample", action="append", default=[], help="sample id (r1..r8); repeatable")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--text")
    ap.add_argument("--requester", default="dana.levi@acme.example")
    ap.add_argument("--thread", help="thread id (default: the sample id, or a timestamp for --text)")
    ap.add_argument("--resume", metavar="THREAD")
    ap.add_argument("--status", metavar="THREAD")
    ap.add_argument("--crash-in", choices=["intake", "enrich", "policy", "file_request", "risk_summary"])
    ap.add_argument("--slow", type=float, default=0.0)
    ap.add_argument("--fault", default="", help="e.g. timeout:get_system_info:2 or error:check_policy:1")
    ap.add_argument("--durability", choices=["sync", "async", "exit"], default="sync")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset:
        for p in (REQUESTS_DB, CHECKPOINTS_DB):
            for suffix in ("", "-wal", "-shm"):
                p.with_name(p.name + suffix).unlink(missing_ok=True)
        print(f"deleted {REQUESTS_DB.name} and {CHECKPOINTS_DB.name} in {REQUESTS_DB.parent}")
        return 0
    if args.list:
        for s in SAMPLES:
            print(f"{s['id']}  {s['requester']:<28} expect {s['expect_status']:<17} {s['text']}")
        return 0

    app, saver, deps = make_app(args.model, mine_parts=mine_parts_arg(args), crash_in=args.crash_in,
                                slow_s=args.slow, fault=args.fault)
    if args.show_graph:
        show_graph(app)
        return 0
    if args.status:
        print(runner.dumps({k: v for k, v in runner.summary(app, args.status).items()}))
        print(store.pretty(store.dump(REQUESTS_DB, args.status)))
        return 0
    if args.resume:
        s = runner.summary(app, args.resume)
        if s["status"] is None:
            print(f"no checkpoint for thread {args.resume!r}. If it crashed with --durability exit, nothing was "
                  "saved before the crash: the run must start over (and only idempotency protects side effects).")
            return 1
        if s["paused_at_gate"]:
            print(f"{args.resume} is waiting at an approval gate: use approve.py decide {args.resume} ...")
            return 1
        if not s["next"]:
            print(f"{args.resume} has nothing left to run (status={s['status']}).")
            return 0
        print(f"resuming {args.resume}: next = {s['next']} (loaded from {CHECKPOINTS_DB.name})")
        runner.print_events(runner.resume(app, args.resume, durability=args.durability))
        print(f"  = {runner.summary(app, args.resume)['status']}")
        return 0

    jobs = []
    if args.text:
        jobs.append((args.thread or f"req-{int(time.time())}", args.requester, args.text))
    for s in SAMPLES if args.all else [x for x in SAMPLES if x["id"] in args.sample]:
        jobs.append((args.thread or s["id"], s["requester"], s["text"]))
    if not jobs:
        ap.print_help()
        return 1
    total = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    for tid, requester, text in jobs:
        if app.get_state(runner.config(tid)).values:
            print(f"thread {tid} already exists: use --resume {tid}, another --thread, or --reset")
            continue
        print(f"\n=== {tid}  {requester}: {text}")
        t0 = time.perf_counter()
        runner.print_events(runner.start(app, tid, requester, text, utc_now(), durability=args.durability))
        s = runner.summary(app, tid)
        usage = app.get_state(runner.config(tid)).values.get("usage") or {}
        for k in total:
            total[k] += usage.get(k, 0) or 0
        print(f"  = status {s['status']}, route {s['route']}, request {s['request_id']}, "
              f"{usage.get('calls', 0)} LLM calls, ${usage.get('cost_usd', 0):.5f}, {time.perf_counter() - t0:.2f}s")
    print(f"\nLLM total: {total['calls']} calls, {total['input_tokens']} in / {total['output_tokens']} out tokens, "
          f"${total['cost_usd']:.5f} ({args.model})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
