"""Exercise 8: error analysis. Group the failures by WHERE in the pipeline they happen, then fix
the biggest group first.

    python labs/23-evaluation/error_analysis.py                                 # extractive baseline
    python labs/23-evaluation/error_analysis.py --model anthropic:claude-haiku-5-5   # the live run (cached from ex1)
    python labs/23-evaluation/error_analysis.py --examples 5 --mode retrieval_miss

Each failing question (answer_ok = 0) gets exactly ONE failure mode, the first that applies in
pipeline order. The order matters: if retrieval never brought the source document, it is
pointless to blame the generator for not stating the fact.

  error                  the system raised an exception
  retrieval_miss         answerable, and no source document is in the top-k (recall@5 = 0)
  retrieval_partial      a multi-source question where only some sources were retrieved
  answered_unanswerable  the answer is not in the documents, and the system answered anyway
  wrong_abstain          the source WAS retrieved, and the system said "not in the documents"
  stale_version          it cited the superseded version of a policy
  incomplete_answer      the source was retrieved, it answered, but stated < half of the facts
Writes results/error_analysis_<model>.md. Lesson 13 (RAG diagnostics) goes deeper on each mode.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab import CACHE, RESULTS, OutputCache, acme_golden, confirm, progress, system_for  # noqa: E402

from evalkit import run_system, score_run  # noqa: E402
from evalkit.rag import rag_scorer  # noqa: E402

MODES = ["error", "retrieval_miss", "retrieval_partial", "answered_unanswerable", "wrong_abstain",
         "stale_version", "incomplete_answer"]

FIX_HINTS = {
    "retrieval_miss": "The generator never saw the source. Look at the question wording vs the document wording "
                      "(acronyms, Hebrew vs English, numbers in tables). Candidates: query rewriting, embeddings "
                      "(lesson 10), hybrid search and reranking (lesson 12), contextual chunk headers.",
    "retrieval_partial": "Multi-hop: one source found, the second not. Candidates: larger k with reranking, "
                         "query decomposition into sub-questions, or an agentic retrieve-again loop (lessons 12-13).",
    "answered_unanswerable": "Near-miss documents look like answers. Candidates: a stricter abstain rule in the "
                             "prompt, a relevance threshold on retrieval scores, a refusal judge in the eval.",
    "wrong_abstain": "The evidence was in the prompt and the generator refused: often a table row or a PDF line "
                     "it could not read, or a Hebrew/English mismatch. Inspect the chunk text (lesson 9 ex1).",
    "stale_version": "Both versions retrieved, the old one won. Candidates: the effective_date rule in the prompt "
                     "(exercise 6), metadata filtering on `supersedes`, or dropping superseded docs at ingestion.",
    "incomplete_answer": "Retrieved and answered, but facts are missing. Check first whether the METRIC is wrong "
                         "(paraphrase, Hebrew answer, number in words) with the correctness judge, then the prompt "
                         "(answer length limit) and the chunk boundaries.",
    "error": "Read the traceback in the run file; fix the code before reading any metric.",
}


def failure_mode(ex, rec) -> str:
    s, e = rec.scores, ex.expected
    answerable = bool(e.get("source_ids"))
    if rec.error:
        return "error"
    if answerable and (s.get("recall@5") or 0.0) == 0.0:
        return "retrieval_miss"
    if answerable and len(e["source_ids"]) > 1 and (s.get("recall@5") or 0.0) < 1.0 and (s.get("fact_coverage") or 0.0) < 0.5:
        return "retrieval_partial"
    if not answerable:
        return "answered_unanswerable"
    if rec.output.get("abstained"):
        return "wrong_abstain"
    if s.get("stale_cited"):
        return "stale_version"
    return "incomplete_answer"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="extractive")
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--examples", type=int, default=2, help="examples to print per mode")
    ap.add_argument("--mode", default="", help="print only this mode")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    ds = acme_golden()
    if not confirm(args.model, len(ds), 2500, 200, args.yes):
        return
    run = run_system(system_for(args.model, args.prompt, 5), ds, cache=OutputCache(CACHE), on_progress=progress)
    score_run(run, ds, [rag_scorer()])
    groups: dict[str, list] = defaultdict(list)
    for rec in run.records:
        if rec.scores.get("answer_ok", 0.0) < 1.0 or rec.error:
            ex = ds[rec.example_id]
            groups[failure_mode(ex, rec)].append((ex, rec))
    n_fail = sum(len(v) for v in groups.values())
    lines = [f"# Error analysis: {run.system_version}", "", f"{n_fail} of {len(run.records)} questions fail answer_ok.", ""]
    print(f"\n{n_fail} of {len(run.records)} questions fail. By failure mode (pipeline order):\n")
    for mode in MODES:
        items = groups.get(mode, [])
        if not items:
            continue
        types = Counter(ex.type for ex, _ in items)
        head = f"{mode}: {len(items)}  (" + ", ".join(f"{t} {c}" for t, c in types.most_common()) + ")"
        print("  " + head)
        lines += [f"## {head}", "", f"Fix candidates: {FIX_HINTS[mode]}", ""]
        for ex, rec in items:
            lines.append(f"- **{ex.id}** [{ex.type}] {ex.input['question']}")
            lines.append(f"  - answer: {rec.output.get('answer', rec.error or '')[:200]}")
            lines.append(f"  - should use: {ex.expected.get('source_ids')}, retrieved: {rec.output.get('retrieved_docs')}")
        lines.append("")
    for mode in MODES:
        if args.mode and mode != args.mode:
            continue
        items = groups.get(mode, [])[: args.examples]
        if not items:
            continue
        print(f"\n=== {mode} ===\nfix candidates: {FIX_HINTS[mode]}")
        for ex, rec in items:
            print(f"- {ex.id} [{ex.type}] {ex.input['question'][:100]}\n    answer: {rec.output.get('answer', '')[:160]}\n"
                  f"    reference: {ex.expected.get('answer', '')[:160]}\n"
                  f"    should use {ex.expected.get('source_ids')}  retrieved {rec.output.get('retrieved_docs')}")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"error_analysis_{args.model.replace(':', '_')}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nfull list: {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")


if __name__ == "__main__":
    main()
