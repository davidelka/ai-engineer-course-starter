"""Exercise 5: does the model find one sentence in a long context, and does position matter?

    python labs/04-context-engineering/position_test.py --dry-run                 # sizes, positions, estimated cost
    python labs/04-context-engineering/position_test.py                           # live: Claude Haiku 5.5
    python labs/04-context-engineering/position_test.py --distractors 3
    python labs/04-context-engineering/position_test.py --question-first          # question BEFORE the documents
    python labs/04-context-engineering/position_test.py --sizes 2000,8000,32000,120000   # above 100K: x5 price tier
    python labs/04-context-engineering/position_test.py --model fake               # free, pipeline only

The haystack is the Acme handbook (labs/04-context-engineering/data/acme_handbook.md, about 13K
Claude tokens), split into its '## ' sections and repeated in order until the target size.
The needle is one sentence inserted into the section at the chosen position (0 = first
document, 1 = last). The needles and distractors are listed in ctxkit/haystack.py, e.g.:
  question: What is the door code for the server room on floor 7 of the Haifa office?
  needle:   The door code for the server room on floor 7 of the Haifa office is 4-8-1-5-2, ...
  distractor: The door code for the storage room on floor 3 of the Haifa office is 7-7-2-0-9.
A reply is correct if it contains the answer (digits compared without dashes).

--model fake uses ctxkit.fake.ExtractiveLLM: a string search, not a model. It always finds
the needle, so offline runs check the pipeline and the cost estimate, never position effects.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from ctxkit.fake import ExtractiveLLM  # noqa: E402
from ctxkit.haystack import NEEDLES, build_haystack, is_correct, split_sections  # noqa: E402
from llmkit import LLM, PRICES, ChatRequest, LLMError, load_dotenv  # noqa: E402

SYSTEM = ("You answer questions about Acme Ltd. using only the documents provided. "
          "Reply with the answer in one short sentence. If the documents do not contain it, reply NOT FOUND.")


def filler(kind: str) -> list[str]:
    if kind == "corpus":
        docs = sorted((ROOT / "data" / "acme" / "corpus" / "docs").glob("*.md"))
        if docs:
            return [f"## {p.name}\n" + p.read_text(encoding="utf-8") for p in docs]
        print("(no corpus docs found, using the handbook)")
    return split_sections((LAB / "data" / "acme_handbook.md").read_text(encoding="utf-8"))


def prompt(haystack: str, question: str, question_first: bool) -> str:
    q = f"<question>\n{question}\n</question>"
    return f"{q}\n\n{haystack}" if question_first else f"{haystack}\n\n{q}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5", help="or 'fake' for the offline string search")
    ap.add_argument("--sizes", default="2000,8000,32000", help="haystack sizes in (o200k) tokens")
    ap.add_argument("--positions", default="0,0.25,0.5,0.75,1")
    ap.add_argument("--needle", default="0", help="index into ctxkit.haystack.NEEDLES, or 'all'")
    ap.add_argument("--distractors", type=int, default=0)
    ap.add_argument("--question-first", action="store_true")
    ap.add_argument("--filler", default="handbook", choices=["handbook", "corpus"])
    ap.add_argument("--effort", default="low")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))

    sizes = [int(s) for s in a.sizes.split(",")]
    positions = [float(p) for p in a.positions.split(",")]
    needles = NEEDLES if a.needle == "all" else [NEEDLES[int(a.needle)]]
    sections = filler(a.filler)
    cases = []
    for n in needles:
        for size in sizes:
            for pos in positions:
                hay, tok = build_haystack(sections, size, n, pos, a.distractors)
                cases.append({"needle": n, "size": size, "pos": pos, "tokens": tok,
                              "prompt": prompt(hay, n.question, a.question_first)})
    total_tok = sum(c["tokens"] for c in cases)
    model_name = a.model.partition(":")[2] or a.model
    p = PRICES.get(model_name)
    est = None
    if p:
        est = sum(c["tokens"] * 1.3 * p["input"] * (p.get("long_multiplier", 1) if p.get("long_threshold") and c["tokens"] * 1.3 > p["long_threshold"] else 1)
                  for c in cases) / 1e6
    print(f"{len(cases)} calls, {total_tok:,} o200k tokens in total (about {int(total_tok * 1.3):,} Claude tokens)"
          + (f", estimated input cost ${est:.3f}" if est is not None else ""))
    if a.dry_run:
        return

    if a.model == "fake":
        llm = ExtractiveLLM({n.question: n.sentence for n in NEEDLES})
    else:
        llm = LLM(a.model)

    def run(c):
        req = ChatRequest.from_prompt(c["prompt"], system=SYSTEM, max_tokens=200,
                                      effort=None if a.model == "fake" else (a.effort or None))
        try:
            r = llm.complete(req)
            return {**c, "reply": r.text.strip(), "ok": is_correct(r.text, c["needle"].answer),
                    "cost": r.cost_usd or 0.0, "latency": r.latency_s}
        except LLMError as e:
            return {**c, "reply": f"ERROR {e}", "ok": False, "cost": 0.0, "latency": 0.0}

    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(run, cases))

    print(f"\nposition ->  " + "  ".join(f"{p:>5}" for p in positions))
    for n in needles:
        if len(needles) > 1:
            print(f"needle: {n.question[:60]}")
        for size in sizes:
            cells = []
            for pos in positions:
                r = next(x for x in rows if x["needle"] is n and x["size"] == size and x["pos"] == pos)
                cells.append("  ok " if r["ok"] else " MISS")
            print(f"{size:>8} tok  " + "  ".join(cells))
    acc = sum(r["ok"] for r in rows) / len(rows)
    print(f"\naccuracy {acc:.0%} | cost ${sum(r['cost'] for r in rows):.4f} | "
          f"mean latency {sum(r['latency'] for r in rows) / len(rows):.1f}s")
    for r in rows:
        if not r["ok"]:
            print(f"  MISS size={r['size']} pos={r['pos']}: {r['reply'][:140]!r}")
    out = LAB / "results" / f"position_{a.model.replace(':', '_')}_{int(time.time())}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"args": vars(a), "rows": [
        {k: v for k, v in r.items() if k not in ("prompt", "needle")} | {"needle": r["needle"].question}
        for r in rows]}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    print("one run per cell is ONE sample: run it 2-3 times before concluding anything.")


if __name__ == "__main__":
    main()
