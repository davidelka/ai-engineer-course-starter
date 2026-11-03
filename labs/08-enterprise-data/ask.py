"""Exercise 4: the whole loop. Question -> SQLPlan (structured output) -> guard -> row policy ->
read-only execution -> answer with provenance.

    python labs/08-enterprise-data/ask.py "How many open P1 tickets do we have right now?"     # offline replay
    python labs/08-enterprise-data/ask.py --list                                               # questions that have recordings
    python labs/08-enterprise-data/ask.py --live "How many open P1 tickets do we have right now?"
    python labs/08-enterprise-data/ask.py --live --role manager --team core-api "List the people on my team with their email addresses."
    python labs/08-enterprise-data/ask.py --live --show-prompt "..."                           # see the system prompt
    python labs/08-enterprise-data/ask.py --live --record "..."                                # save the reply as a new fixture
    python labs/08-enterprise-data/ask.py --mine "..."                                         # use YOUR guard and row policy

Offline mode replays fixtures/replay.jsonl: synthetic replies, hand-written to behave like a
model (including some typical mistakes). Only recorded questions work offline.
Live mode calls Claude Haiku 5.5: about $0.0003-0.0006 per question.
"""

from __future__ import annotations

import argparse
import json

import _lab
from _lab import DEFAULT_MODEL, FIXTURES, make_llm, pick
from datakit.semantic import load_layer
from datakit.text2sql import Settings, answer_question, build_system, format_answer, load_fixtures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--live", action="store_true", help="call the real model (default: offline replay)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--role", default="analyst")
    ap.add_argument("--team", default=None, help="row-policy parameter for --role manager")
    ap.add_argument("--now", default=None, help="'now' for freshness, ISO (default 2026-11-01T09:00:00Z)")
    ap.add_argument("--mine", action="store_true", help="use guard_sql and apply_row_policy from mine.py")
    ap.add_argument("--no-narrate", action="store_true", help="skip the second (answer-writing) model call")
    ap.add_argument("--show-prompt", action="store_true")
    ap.add_argument("--record", action="store_true", help="append the live replies to fixtures/replay.jsonl")
    ap.add_argument("--list", action="store_true", help="list the questions recorded for offline mode")
    a = ap.parse_args()

    if a.list:
        for q in load_fixtures(FIXTURES):
            print("-", q)
        return
    if not a.question:
        ap.error("give a question (or --list)")
    layer = load_layer()
    if a.role == "manager" and not a.team:
        ap.error("--role manager needs --team (e.g. core-api)")
    s = Settings(role=a.role, user={"team": a.team} if a.team else {}, layer=layer, now=a.now,
                 narrate=not a.no_narrate)
    if a.mine:
        s.guard, gsrc = pick("guard_sql", False)
        s.row_policy, rsrc = pick("apply_row_policy", False)
        print(f"guard: {gsrc}; row policy: {rsrc}")
    if a.show_prompt:
        print("----- system prompt -----\n" + build_system(layer, a.role) + "-------------------------\n")
    llm, label = make_llm(a.live, a.model)
    print(f"model: {label}\n")
    ans = answer_question(llm, a.question, s)
    print(format_answer(ans))
    if a.record:
        if not a.live:
            print("\n--record only makes sense with --live")
            return
        n = len(ans.raw_replies) - (1 if s.narrate and ans.status == "ok" else 0)
        rec = {"id": "rec", "question": a.question, "plans": ans.raw_replies[:n],
               "answer": ans.answer if ans.status == "ok" else "", "note": f"recorded live from {a.model}"}
        with open(FIXTURES, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\nrecorded to {FIXTURES.name}")


if __name__ == "__main__":
    main()
