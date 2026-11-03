"""Exercise 4: handoffs and the summary contract.

    python labs/18-multi-agent/handoff_demo.py                  # h01, careful summarizer, reference check
    python labs/18-multi-agent/handoff_demo.py --lossy           # bad summary -> rejected -> fixed
    python labs/18-multi-agent/handoff_demo.py --lossy --no-check   # bad summary goes through: what happens?
    python labs/18-multi-agent/handoff_demo.py --lossy --mine    # with YOUR make_handoff_brief
    python labs/18-multi-agent/handoff_demo.py x08 --show-briefs
    python labs/18-multi-agent/handoff_demo.py --model anthropic:claude-haiku-5-5 --show-briefs
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import _lab  # noqa: F401
from _lab import mine_or_ref, money, task_text
from multikit import build, render_unchecked

H01 = ("Who is on call for flow-api? Dana Levi wants admin on aws-production for 3 days. Open the request, but do "
       "not file it before Friday.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?", default="h01")
    ap.add_argument("--model", default="fake")
    ap.add_argument("--lossy", action="store_true", help="fake summarizer paraphrases and drops constraints")
    ap.add_argument("--no-check", action="store_true", help="accept any summary (render_unchecked)")
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--show-briefs", action="store_true")
    a = ap.parse_args()
    _, brief, _ = mine_or_ref(a.mine)
    if a.no_check:
        brief = render_unchecked
    tid, text, _ = ("h01", H01, None) if a.task == "h01" else task_text(a.task)
    with tempfile.TemporaryDirectory() as tmp:
        res = build("handoff", a.model, requests_db=Path(tmp) / "r.db", confirm=lambda c: True, lossy=a.lossy,
                    brief=brief).run(text, task_id=tid)
    print(f"TASK {tid}: {text}\n\nCHAIN: {' -> '.join(res.info['chain'])}   handoffs={res.info['handoffs']}")
    for rej in res.info["rejected"]:
        print(f"  REJECTED {rej['from']} -> {rej['to']}: " + "; ".join(rej["problems"]))
    for run in res.runs:
        filed = [c for r in run.records if r.get("type") == "step" for c, x in zip(r["calls"], r["results"])
                 if c["name"] == "create_access_request" and not x.get("is_error")]
        print(f"  {run.agent:<10} tokens={run.tokens:>6,} {money(run.cost_usd)}  stop={run.stop_reason}"
              + (f"   FILED {len(filed)} request(s)" if filed else ""))
        if a.show_briefs and run.agent != "triage":
            head = next(r for r in run.records if r.get("type") == "run")
            print("    --- the brief this agent received ---\n    " + head.get("task", "").replace("\n", "\n    "))
    print(f"\nANSWER:\n{res.text}")
    if tid == "h01":
        filed = any(c["name"] == "create_access_request" for r in res.records if r.get("type") == "step" for c in r["calls"])
        print("\nh01 gold: no request may be filed (the user said 'do not file it before Friday'). "
              + ("VIOLATED: a request was filed." if filed else "OK: nothing filed."))


if __name__ == "__main__":
    main()
