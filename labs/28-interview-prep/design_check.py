"""Exercise 5: the timed LLM system-design exercise, and a checklist score for your answer.

    python labs/28-interview-prep/design_check.py prompt                      # show the task, start the clock
    python labs/28-interview-prep/design_check.py check results/my_design.md  # coverage per section (mine.py)
    python labs/28-interview-prep/design_check.py check my.md --reference     # interviewkit's scorer
    python labs/28-interview-prep/design_check.py check my.md --llm           # + Claude grades with quotes
    python labs/28-interview-prep/design_check.py check system_design/weak_answer.md --reference

The checklist (system_design/checklist.json) has 20 points in 9 sections. The keyword
check tells you what you did NOT mention; --llm asks the grader for a quote per point.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB.parents[1]), str(LAB)]
from bank_tool import impl  # noqa: E402

TASK = LAB / "system_design" / "ticket_triage.md"
CHECKLIST = LAB / "system_design" / "checklist.json"
START = LAB / "results" / "design_start.json"
SECTIONS = ["requirements", "metrics", "architecture", "data", "eval", "failures", "cost_latency",
            "security", "iteration"]


def load_checklist() -> dict:
    data = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    data["id"] = "design-ticket-triage"
    return data


def section_report(result: dict, checklist: dict) -> list[tuple[str, int, int, list[dict]]]:
    """[(section, covered_weight, total_weight, missing_points)] in framework order."""
    cov, tot, miss = defaultdict(int), defaultdict(int), defaultdict(list)
    covered = set(result["covered"])
    for p in checklist["rubric"]:
        w = p.get("weight", 1)
        tot[p["section"]] += w
        if p["id"] in covered:
            cov[p["section"]] += w
        else:
            miss[p["section"]].append(p)
    return [(s, cov[s], tot[s], miss[s]) for s in SECTIONS if tot[s]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompt")
    ck = sub.add_parser("check")
    ck.add_argument("file", type=Path)
    ck.add_argument("--reference", action="store_true")
    ck.add_argument("--llm", nargs="?", const="anthropic:claude-haiku-5-5", default=None,
                    help="also grade with an LLM (default model: anthropic:claude-haiku-5-5)")
    ck.add_argument("--offline", action="store_true", help="with --llm: use a local mockllm server")
    a = ap.parse_args()

    if a.cmd == "prompt":
        print(TASK.read_text(encoding="utf-8"))
        START.parent.mkdir(exist_ok=True)
        START.write_text(json.dumps({"start": time.time()}), encoding="utf-8")
        print("\n>>> Clock started: 45 minutes. Write your answer in a markdown file, then run `check`.")
        return

    text = a.file.read_text(encoding="utf-8")
    checklist = load_checklist()
    score = impl(a.reference)["score"]
    try:
        r = score(text, checklist, min_words=250, max_words=4000)
    except NotImplementedError as exc:
        sys.exit(f"{exc}\nImplement score_answer in mine.py (exercise 2), or run with --reference.")

    if START.exists():
        mins = (time.time() - json.loads(START.read_text())["start"]) / 60
        note = "within the 45 minutes" if mins <= 45 else "over the 45 minutes: practise cutting scope"
        print(f"Time since `prompt`: {mins:.0f} min ({note})")
    print(f"Checklist coverage: {r['coverage']:.0%} of the weight, keyword score {r['score']}/100, {r['words']} words")
    print("Structure: " + ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in r["checks"].items()))
    for sec, c, t, missing in section_report(r, checklist):
        bar = "#" * round(10 * c / t) + "." * (10 - round(10 * c / t))
        print(f"\n  {sec:13} [{bar}] {c}/{t}")
        for p in missing:
            print(f"      missing: {p['point']}")

    if a.llm:
        from interviewkit.interviewer import grade_answer
        from llmkit import LLM, load_dotenv
        server = None
        if a.offline:
            from mockllm import MockConfig, start_in_thread
            server, url = start_in_thread(MockConfig(ttft=0, tps=0))
            llm = LLM("anthropic:mock-model", base_url=url, api_key="mock-key")
        else:
            load_dotenv(str(LAB.parents[1] / ".env"))
            llm = LLM(a.llm)
        try:
            g = grade_answer(llm, checklist, f"<design_doc>\n{text}\n</design_doc>", max_tokens=3000)
        finally:
            if server:
                server.shutdown()
        print(f"\nLLM grade: {g.score}/100 ({g.calls} calls, ${g.cost_usd:.5f})")
        for v in g.grade.criteria:
            print(f"  {'✓' if v.covered else '✗'} {v.point_id}: {v.evidence or '-'}")
        if g.grade.red_flags:
            print("Red flags: " + "; ".join(g.grade.red_flags))
        print("Feedback: " + g.grade.feedback)
    print("\nNow read system_design/model_answer.md and compare section by section.")


if __name__ == "__main__":
    main()
