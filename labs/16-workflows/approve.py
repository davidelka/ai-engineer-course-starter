"""The approver's CLI: list paused threads, show one, approve / reject with a comment, or time out.

Each command is a NEW process: the graph is rebuilt and the thread is loaded from
results/checkpoints.db by its thread id. That is the point: the workflow waited on disk.

    python labs/16-workflows/approve.py pending
    python labs/16-workflows/approve.py show r2
    python labs/16-workflows/approve.py decide r2 --as michal.ben-david@acme.example --approve --comment "ok for Q4"
    python labs/16-workflows/approve.py decide r4 --as E063 --reject --comment "use the scoped migration role"
    python labs/16-workflows/approve.py timeout r5            # what the SLA scheduler would send after 2 business days
    python labs/16-workflows/approve.py audit r2              # the audit trail (DB) and the checkpoint trail
"""

from __future__ import annotations

import argparse
import sys

import _lab  # noqa: F401  (paths)
from _lab import REQUESTS_DB, add_common_args, make_app, mine_parts_arg

from flowkit import runner, store


def show_gate(s: dict) -> None:
    g = s["gate"]
    print(f"thread {s['thread_id']}  request {g['request_id']}  gate: {g['gate']}")
    print(f"  employee   {g['employee']}")
    print(f"  wants      {g['access_level']} on {g['system']}" + (f" for {g['duration_days']} days" if g["duration_days"] else ""))
    print(f"  why        {g['justification']!r}  (written by the employee: untrusted)")
    print(f"  policy     {'; '.join(g['reasons'])}  [{g['review_target']}]")
    if g.get("risk_summary"):
        print(f"  risk       {g['risk_summary']}")
    print(f"  may decide {' or '.join(g['allowed_approvers'])}")
    if g.get("previous_error"):
        print(f"  !! previous answer refused: {g['previous_error']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_common_args(common)  # --model / --mine, accepted after the sub-command
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending", parents=[common])
    p = sub.add_parser("show", parents=[common])
    p.add_argument("thread")
    p = sub.add_parser("decide", parents=[common])
    p.add_argument("thread")
    p.add_argument("--as", dest="actor", required=True, help="approver email or employee id")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", action="store_true")
    p.add_argument("--comment", default="")
    p = sub.add_parser("timeout", parents=[common])
    p.add_argument("thread")
    p = sub.add_parser("audit", parents=[common])
    p.add_argument("thread")
    args = ap.parse_args()

    app, saver, _ = make_app(args.model, mine_parts=mine_parts_arg(args))
    if args.cmd == "pending":
        rows = runner.pending(app, saver)
        if not rows:
            print("nothing is waiting for approval")
        for s in rows:
            gt = s["gate"]
            print(f"{s['thread_id']:<10} {gt['request_id']:<9} {gt['gate']:<9} {gt['access_level']:<7} "
                  f"{gt['system']:<17} {gt['employee']}")
        return 0
    s = runner.summary(app, args.thread)
    if s["status"] is None:
        print(f"no thread {args.thread!r} in the checkpoints DB")
        return 1
    if args.cmd == "show":
        if not s["paused_at_gate"]:
            print(f"{args.thread} is not waiting for approval (status={s['status']}, next={s['next']})")
            return 1
        show_gate(s)
        return 0
    if args.cmd == "audit":
        print("audit rows in requests.db (SPEC-006 REQ-11):")
        for a in store.dump(REQUESTS_DB, args.thread)["audit"]:
            print(f"  {a['at']}  {a['request_id']}  {a['from_status'] or 'new':>16} -> {a['to_status']:<17} "
                  f"by {a['actor']:<16} {a['note'] or ''}")
        print("\naudit events in the checkpointed state (includes refused answers):")
        for e in app.get_state(runner.config(args.thread)).values.get("audit", []):
            print(f"  {e['id']:<45} {e['actor']:<16} {e['note'] or ''}")
        return 0
    if not s["paused_at_gate"]:
        print(f"{args.thread} is not waiting for approval (status={s['status']}). A closed request stays closed.")
        return 1
    if args.cmd == "timeout":
        answer = {"decision": "timeout", "actor": "system:sla-timer", "comment": "no decision within 2 business days"}
    else:
        answer = {"decision": "approve" if args.approve else "reject", "actor": args.actor, "comment": args.comment}
    print(f"resuming {args.thread} with Command(resume={answer})")
    runner.print_events(runner.resume(app, args.thread, answer))
    s = runner.summary(app, args.thread)
    note = ""
    if s["paused_at_gate"]:
        note = (f"  (answer refused, still waiting at the {s['gate']['gate']} gate)" if s["gate"].get("previous_error")
                else f"  (now waiting at the {s['gate']['gate']} gate)")
    print(f"  = status {s['status']}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
