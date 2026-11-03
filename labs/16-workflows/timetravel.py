"""Time travel: list a thread's checkpoints, inspect one, replay from it, or fork it with changed state.

    python labs/16-workflows/timetravel.py history r2
    python labs/16-workflows/timetravel.py show r2 --step 2
    python labs/16-workflows/timetravel.py fork r2 --before policy --set access_level=viewer
    python labs/16-workflows/timetravel.py replay r4 --before risk_summary    # re-runs the LLM step

history  every checkpoint, oldest first: step, source (input = the start, loop = a node ran,
         update = update_state wrote it), next node, status
fork     update_state() on a past checkpoint creates a NEW checkpoint (a branch) with your change,
         then the graph continues from there. The old checkpoints are kept: nothing is erased.
replay   invoke(None, <past checkpoint config>) re-runs every node after that checkpoint, including
         LLM calls (new answers) and side effects (guarded only by their idempotency).
"""

from __future__ import annotations

import argparse
import json
import sys

import _lab  # noqa: F401
from _lab import REQUESTS_DB, add_common_args, make_app, mine_parts_arg

from flowkit import runner, store


def pick(rows: list[dict], args) -> dict:
    if getattr(args, "step", None) is not None:
        matches = [r for r in rows if r["step"] == args.step]
    else:
        matches = [r for r in rows if r["next"] == [args.before]]
    if not matches:
        raise SystemExit(f"no checkpoint matches (see: timetravel.py history {args.thread})")
    return matches[-1]  # the latest such checkpoint (after earlier forks there can be several)


def parse_set(pairs: list[str]) -> dict:
    out = {}
    for p in pairs:
        k, _, v = p.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_common_args(common)  # --model / --mine, accepted after the sub-command
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("history", parents=[common])
    p.add_argument("thread")
    for name in ("show", "fork", "replay"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("thread")
        p.add_argument("--before", help="the checkpoint whose NEXT node is this one")
        p.add_argument("--step", type=int)
        if name == "fork":
            p.add_argument("--set", action="append", default=[], help="request field=value, e.g. access_level=viewer")
    args = ap.parse_args()

    app, _, _ = make_app(args.model, mine_parts=mine_parts_arg(args))
    rows = runner.history(app, args.thread)
    if not rows:
        print(f"no thread {args.thread!r}")
        return 1
    if args.cmd == "history":
        print(f"{'step':>4}  {'source':<7} {'status':<17} {'next':<20} checkpoint_id (parent)")
        for r in rows:
            print(f"{r['step']:>4}  {r['source']:<7} {r['status'] or '-':<17} {','.join(r['next']) or '(end)':<20} "
                  f"{r['checkpoint_id'][-12:]} ({(r['parent'] or '-')[-12:]})")
        print(f"\n{len(rows)} checkpoints. The current state is the newest one: "
              f"{runner.summary(app, args.thread)['status']}")
        return 0
    row = pick(rows, args)
    snap = row["snapshot"]
    if args.cmd == "show":
        v = {k: snap.values.get(k) for k in ("status", "route", "request", "record", "decision", "gate_error")}
        print(runner.dumps({"step": row["step"], "next": row["next"], "values": v}))
        return 0
    if args.cmd == "replay":
        print(f"replaying {args.thread} from step {row['step']} (next: {row['next']}). Nodes after it run AGAIN.")
        runner.print_events(app.stream(None, snap.config, stream_mode=["updates", "custom"]))
        print(f"  = {runner.summary(app, args.thread)['status']}")
        return 0
    changes = parse_set(args.set)
    if not changes:
        raise SystemExit("fork needs at least one --set field=value")
    req = dict(snap.values.get("request") or {}, **changes)
    print(f"forking {args.thread} at step {row['step']} (next: {row['next']}) with request changes {changes}")
    fork_cfg = app.update_state(snap.config, {"request": req})
    print(f"  new checkpoint {fork_cfg['configurable']['checkpoint_id'][-12:]} (parent "
          f"{row['checkpoint_id'][-12:]}): the old branch is still in the history")
    runner.print_events(app.stream(None, fork_cfg, stream_mode=["updates", "custom"]))
    s = runner.summary(app, args.thread)
    print(f"  = status {s['status']}, request {s['request_id']}")
    recs = [r for r in store.dump(REQUESTS_DB)["access_requests"] if r["idempotency_key"].startswith(args.thread + ":")]
    print(f"\nrequests.db now has {len(recs)} record(s) filed by thread {args.thread}:")
    for r in recs:
        print(f"  {r['id']}  {r['system']}  {r['access_level']:<7} {r['status']:<17} key={r['idempotency_key']}")
    if len(recs) > 1:
        print("  -> time travel re-ran file_request. Checkpoints can be rewound; the outside world cannot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
