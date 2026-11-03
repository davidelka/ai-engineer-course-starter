"""The question bank from the command line: stats, show, validate, and a daily drill.

    python labs/28-interview-prep/bank_tool.py stats
    python labs/28-interview-prep/bank_tool.py show --category rag --n 3 --answers
    python labs/28-interview-prep/bank_tool.py validate
    python labs/28-interview-prep/bank_tool.py due
    python labs/28-interview-prep/bank_tool.py drill --new 5 --limit 10      # uses YOUR mine.py
    python labs/28-interview-prep/bank_tool.py drill --reference             # interviewkit's versions

The drill state (SM-2 per question) lives in labs/28-interview-prep/results/srs_state.json.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import textwrap
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]
from interviewkit import rubric as ref_rubric, srs as ref_srs  # noqa: E402
from interviewkit.bank import CATEGORIES, load_bank, validate_question  # noqa: E402

STATE = LAB / "results" / "srs_state.json"


def impl(reference: bool) -> dict[str, Callable]:
    """Your functions from mine.py, or the reference ones with --reference."""
    if reference:
        return {"score": ref_rubric.score_answer, "review": ref_srs.sm2_review,
                "grade": ref_srs.grade_from_score, "pick": ref_srs.pick_session}
    import mine
    return {"score": mine.score_answer, "review": mine.sm2_review, "grade": mine.grade_from_score,
            "pick": mine.pick_session}


def load_state(path: Path = STATE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(states: dict, path: Path = STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(states, ensure_ascii=False, indent=1), encoding="utf-8")


def wrap(text: str, indent: str = "  ") -> str:
    return textwrap.fill(text, width=100, initial_indent=indent, subsequent_indent=indent)


def print_question(q: dict, answers: bool = False) -> None:
    print(f"\n[{q['id']}] {CATEGORIES[q['category']]} · {q['level']}")
    print(wrap(q["q"]))
    if answers:
        print("\n  Reference answer:")
        print(wrap(q["answer"], "    "))
        print("\n  Rubric (what an interviewer listens for):")
        for p in q["rubric"]:
            terms = " | ".join("/".join(g) if isinstance(g, list) else g for g in p["concepts"])
            print(f"    {p['id']} (w{p.get('weight', 1)}) {p['point']}")
            print(f"         concepts: {terms}")
        for f in q.get("follow_ups", []):
            print(f"  follow-up: {f}")
        for f in q.get("red_flags", []):
            print(f"  red flag:  {f}")


def read_answer(prompt: str = "Your answer (finish with an empty line; empty = just show me):") -> str:
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def run_drill(bank: list[dict], states: dict, today: date, answer_fn: Callable[[dict], str],
              self_grade: Callable[[dict, dict | None, int], int], fns: dict, new_per_day: int = 5,
              limit: int = 10, category: str | None = None) -> list[tuple[str, int]]:
    """One session. Mutates and returns `states` entries for the questions practised."""
    pool = [q for q in bank if not category or q["category"] == category]
    by = {q["id"]: q for q in pool}
    done = []
    for qid in fns["pick"]([q["id"] for q in pool], states, today, new_per_day=new_per_day, limit=limit):
        q = by[qid]
        answer = answer_fn(q)
        result = fns["score"](answer, q) if answer.strip() else None
        suggested = fns["grade"](result["score"]) if result else 0
        g = self_grade(q, result, suggested)
        states[qid] = fns["review"](states.get(qid), g, today)
        done.append((qid, g))
    return done


def cmd_drill(a, bank) -> None:
    fns = impl(a.reference)
    states = load_state()
    today = date.today()

    def answer_fn(q):
        print_question(q)
        return read_answer()

    def self_grade(q, result, suggested):
        if result:
            print(f"\n  local rubric score: {result['score']}/100  coverage {result['coverage']:.0%}  "
                  f"missing: {', '.join(result['missing']) or '-'}")
            print("  checks: " + ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in result["checks"].items()))
        print_question(q, answers=True)
        raw = input(f"\n  Grade yourself 0-5 (Enter = {suggested}): ").strip()
        return int(raw) if raw.isdigit() and 0 <= int(raw) <= 5 else suggested

    try:
        done = run_drill(bank, states, today, answer_fn, self_grade, fns, a.new, a.limit, a.category)
    except NotImplementedError as exc:
        sys.exit(f"{exc}\nImplement it in mine.py (exercises 2-3), or run with --reference.")
    save_state(states)
    print(f"\nPractised {len(done)}: " + ", ".join(f"{i}={g}" for i, g in done))
    print(f"State saved to {STATE.relative_to(LAB.parents[1])}")


def cmd_due(bank) -> None:
    states = load_state()
    today = date.today()
    ids = {q["id"] for q in bank}
    days = Counter()
    for qid, s in states.items():
        if qid in ids:
            d = (date.fromisoformat(s["due"]) - today).days
            days["today (overdue included)" if d <= 0 else f"in {d} days" if d <= 7 else "later"] += 1
    print(f"{len(states)} of {len(bank)} questions practised at least once; {len(bank) - len(states)} new.")
    for k in sorted(days, key=lambda k: (k != "today (overdue included)", k)):
        print(f"  {k}: {days[k]}")
    hard = sorted((s.get("ef", 2.5), qid) for qid, s in states.items() if qid in ids)[:5]
    if hard:
        print("Hardest for you (lowest easiness): " + ", ".join(f"{q} ({e:.2f})" for e, q in hard))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    sub.add_parser("validate")
    sub.add_parser("due")
    sh = sub.add_parser("show")
    sh.add_argument("--category", choices=list(CATEGORIES))
    sh.add_argument("--id")
    sh.add_argument("--n", type=int, default=3)
    sh.add_argument("--answers", action="store_true", help="also print reference answer and rubric")
    sh.add_argument("--seed", type=int)
    dr = sub.add_parser("drill")
    dr.add_argument("--category", choices=list(CATEGORIES))
    dr.add_argument("--new", type=int, default=5, help="new questions per session")
    dr.add_argument("--limit", type=int, default=10)
    dr.add_argument("--reference", action="store_true")
    a = ap.parse_args()
    bank = load_bank()

    if a.cmd == "stats":
        cats = Counter(q["category"] for q in bank)
        levels = Counter(q["level"] for q in bank)
        print(f"{len(bank)} questions, {sum(len(q['rubric']) for q in bank)} rubric points")
        for c, name in CATEGORIES.items():
            print(f"  {c:14} {cats[c]:3}  {name}")
        print("levels: " + ", ".join(f"{k}={v}" for k, v in levels.items()))
    elif a.cmd == "validate":
        bad = {q.get("id", "?"): p for q in bank if (p := validate_question(q))}
        dup = [i for i, n in Counter(q["id"] for q in bank).items() if n > 1]
        for i, p in bad.items():
            print(f"{i}: {'; '.join(p)}")
        if dup:
            print("duplicate ids: " + ", ".join(dup))
        print("OK" if not bad and not dup else "PROBLEMS FOUND")
        sys.exit(1 if bad or dup else 0)
    elif a.cmd == "show":
        qs = [q for q in bank if (not a.category or q["category"] == a.category) and (not a.id or q["id"] == a.id)]
        random.Random(a.seed).shuffle(qs)
        for q in qs[: a.n]:
            print_question(q, a.answers)
    elif a.cmd == "due":
        cmd_due(bank)
    elif a.cmd == "drill":
        cmd_drill(a, bank)


if __name__ == "__main__":
    main()
