"""Exercise 7: a worker returns WRONG information. Does the supervisor catch it?

The worker's tools are right; only its final answer is corrupted (multikit.faults.CORRUPTIONS):
  route     it_access says auto_approve where check_policy said needs_security / needs_manager
  lead      oncall names the wrong team lead
  rotation  oncall names the wrong rotation
  number    hr changes a number (5 carry-over days -> 10)

    python labs/18-multi-agent/failure_demo.py                     # all faults x verify none|llm|code, fake
    python labs/18-multi-agent/failure_demo.py --fault route --times 1   # the worker is wrong only once
    python labs/18-multi-agent/failure_demo.py --fault route --model anthropic:claude-haiku-5-5 --verify none,llm,code
"""

from __future__ import annotations

import argparse
import json

import _lab  # noqa: F401
from _lab import is_live, money, tasks
from multikit import CORRUPTIONS, run_set
from multikit.faults import WORKER_OF

TASKS_FOR = {"route": "x01,x04,x06", "lead": "x03,x06", "rotation": "x01,x08", "number": "x02,x05,x08"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake")
    ap.add_argument("--fault", default="route,lead,rotation,number")
    ap.add_argument("--verify", default="none,llm,code")
    ap.add_argument("--times", type=int, default=0, help="corrupt only the first N runs of the worker (0 = always)")
    ap.add_argument("--total-budget", type=float, default=0.15)
    a = ap.parse_args()
    spent = [0.0]
    for f in a.fault.split(","):
        worker = WORKER_OF[f]
        ts = tasks(TASKS_FOR[f])
        print(f"\n######## fault={f}: the {worker} worker's answer is corrupted {CORRUPTIONS[f][:2]} ...")
        for v in a.verify.split(","):
            rs = run_set("supervisor", ts, a.model, verify=v, worker_faults={worker: CORRUPTIONS[f]},
                         fault_times=a.times or None, budget_usd=a.total_budget if is_live(a.model) else None,
                         spent=spent)
            for t, res, s in rs:
                redo = res.info["delegations"].get(worker, 0) > 1
                flagged = "conflict" in res.text.lower() or "warning" in res.text.lower()
                ids = [json.loads(x["text"]).get("id") for r in res.records if r.get("type") == "step"
                       for c, x in zip(r["calls"], r["results"])
                       if c["name"] == "create_access_request" and not x.get("is_error")]
                req = f" filed={len(ids)} call(s)/{len(set(ids))} id(s)" if ids else ""
                verdict = "OK (caught or fixed)" if s["success"] else ("FLAGGED but wrong" if flagged else "WRONG, not caught")
                print(f"  verify={v:<5} {t['id']}  re-delegated={'yes' if redo else 'no ':<3} {verdict:<20} "
                      f"tokens={res.tokens:,}{req}" + (f"   <- {'; '.join(s['reasons'][:2])}" if not s["success"] else ""))
    print(f"\ntotal cost {money(spent[0])}{' (estimated)' if not is_live(a.model) else ''}")
    print("Note: re-delegating it_access re-runs its side effect. The idempotency key (lesson 14) returns the SAME "
          "request id, so nothing is duplicated in the store, but the human was asked twice and the lesson 15 scorer "
          "counts two create calls ('expected 1 request, got 2').")
    print("Note: the 'number' fault has no structured evidence to compare with (the HR worker read a document), so "
          "code verification cannot see it. Only an evaluation against gold catches it.")


if __name__ == "__main__":
    main()
