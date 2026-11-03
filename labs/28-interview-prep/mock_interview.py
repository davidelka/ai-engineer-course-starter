"""A mock AI-engineering interview: Claude asks, follows up, and grades against the rubric.

    python labs/28-interview-prep/mock_interview.py --offline                 # free: local mock server
    python labs/28-interview-prep/mock_interview.py --category rag            # live, claude-haiku-5-5
    python labs/28-interview-prep/mock_interview.py --id sd-01 --followups 3
    python labs/28-interview-prep/mock_interview.py --lang en                 # interview in English
    python labs/28-interview-prep/mock_interview.py --project present/company_brain.md --title "Company Brain"
    python labs/28-interview-prep/mock_interview.py --id rag-02 --answers my_answers.txt   # scripted

Answers are typed in the terminal (finish each with an empty line), or read from a file
where answers are separated by lines containing only ---.
The local rubric score comes from YOUR score_answer in mine.py (or --reference).
After a bank question, the SM-2 state is updated from the LLM grade (skip with --no-srs).
A full live interview with Haiku 5.5 is 3-4 calls and costs well under one cent.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]
from bank_tool import impl, load_state, save_state, wrap  # noqa: E402
from interviewkit.bank import CATEGORIES, load_bank  # noqa: E402
from interviewkit.interviewer import project_question, run_interview  # noqa: E402
from llmkit import LLM, load_dotenv  # noqa: E402

RESULTS = LAB / "results"


def scripted(path: Path):
    parts = [p.strip() for p in path.read_text(encoding="utf-8").split("\n---\n")]
    it = iter(parts)
    return lambda _msg: next(it, "(no more scripted answers)")


def typed(_msg: str) -> str:
    print("\nYou (finish with an empty line):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines) or "(no answer)"


def choose(bank, a, fns):
    if a.id:
        return next(q for q in bank if q["id"] == a.id)
    pool = [q for q in bank if not a.category or q["category"] == a.category]
    try:
        due = fns["pick"]([q["id"] for q in pool], load_state(), date.today(), new_per_day=0, limit=1)
    except NotImplementedError:
        due = []
    if due:
        return next(q for q in pool if q["id"] == due[0])
    return random.Random(a.seed).choice(pool)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--offline", action="store_true", help="run against a local mockllm server (free)")
    ap.add_argument("--id")
    ap.add_argument("--category", choices=list(CATEGORIES))
    ap.add_argument("--lang", default="he", choices=["he", "en"])
    ap.add_argument("--followups", type=int, default=2)
    ap.add_argument("--answers", type=Path, help="file with answers separated by --- lines")
    ap.add_argument("--project", type=Path, help="interview about YOUR project write-up instead of a bank question")
    ap.add_argument("--title", default="הפרויקט שלך")
    ap.add_argument("--reference", action="store_true", help="use interviewkit's scorer/SM-2, not mine.py")
    ap.add_argument("--no-srs", action="store_true")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()

    fns = impl(a.reference)
    if a.project:
        question = project_question(a.project.read_text(encoding="utf-8"), a.title)
    else:
        question = choose(load_bank(), a, fns)

    server = None
    if a.offline:
        from mockllm import MockConfig, start_in_thread
        server, url = start_in_thread(MockConfig(ttft=0, tps=0, seed=1))
        llm = LLM("anthropic:mock-model", base_url=url, api_key="mock-key")
        print(f"(offline: mockllm at {url}; the interviewer's lines will be placeholders)")
    else:
        load_dotenv(str(LAB.parents[1] / ".env"))
        llm = LLM(a.model)

    def show(role: str, text: str) -> None:
        if role == "interviewer":
            print(f"\nINTERVIEWER: {text}")
        elif a.answers or a.offline:
            print(f"\nYOU: {text}")

    answer_fn = scripted(a.answers) if a.answers else (lambda m: "(offline run)") if a.offline else typed

    def local_scorer(text, q):
        try:
            return fns["score"](text, q)
        except NotImplementedError:
            return {"note": "score_answer not implemented yet (exercise 2); run with --reference"}

    try:
        res = run_interview(llm, question, answer_fn, lang=a.lang, max_followups=a.followups,
                            on_message=show, scorer=local_scorer)
    finally:
        if server:
            server.shutdown()

    print("\n" + "=" * 70)
    print(f"Question {res.question_id}: LLM grade {res.score}/100 (weighted rubric points marked covered)")
    for v in res.grade.criteria:
        mark = "✓" if v.covered else "✗"
        print(f"  {mark} {v.point_id}: {v.evidence or '-'}")
    for p in question["rubric"]:
        if p["id"] not in {v.point_id for v in res.grade.criteria}:
            print(f"  ? {p['id']}: the grader returned no verdict (counted as not covered)")
    if res.grade.red_flags:
        print("Red flags: " + "; ".join(res.grade.red_flags))
    print("Structure: " + res.grade.structure_note)
    print("Feedback:")
    print(wrap(res.grade.feedback))
    if "score" in res.local:
        print(f"Local keyword score: {res.local['score']}/100, missing {res.local['missing']}. "
              "A big gap between the two scores is worth reading: buzzwords without substance, or the opposite.")
    else:
        print(res.local.get("note", ""))
    print(f"{res.calls} calls, ${res.cost_usd:.5f}, {res.latency_s:.1f}s")

    if not a.project and not a.no_srs:
        try:
            states = load_state()
            g = fns["grade"](res.score)
            states[res.question_id] = fns["review"](states.get(res.question_id), g, date.today())
            save_state(states)
            print(f"SM-2: grade {g}, next review {states[res.question_id]['due']}")
        except NotImplementedError:
            print("SM-2 not updated: implement sm2_review/grade_from_score (exercise 3) or use --reference.")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"interview-{time.strftime('%Y%m%d-%H%M%S')}-{res.question_id}.json"
    out.write_text(json.dumps({**res.to_dict(), "model": "offline" if a.offline else a.model, "lang": a.lang},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Transcript saved to {out.relative_to(LAB.parents[1])}")


if __name__ == "__main__":
    main()
