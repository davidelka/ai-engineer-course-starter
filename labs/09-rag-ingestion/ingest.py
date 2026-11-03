"""Exercise 5: incremental ingestion with a manifest, using YOUR content_hash and plan_ingest.

    python labs/09-rag-ingestion/ingest.py --demo            # the full story, in a scratch copy
    python labs/09-rag-ingestion/ingest.py                   # ingest the real corpus into results/index
    python labs/09-rag-ingestion/ingest.py --chunker recursive:256:0    # change the recipe: watch what happens
    python labs/09-rag-ingestion/ingest.py --reference       # use ragkit's functions instead of mine.py

--demo copies the corpus to results/demo_corpus and runs five rounds:
  1. first run                       everything is "added"
  2. run again, nothing changed      everything "unchanged", nothing is parsed
  3. edit one policy, re-classify one document in its sidecar only, delete one, add one
  4. run again                       exactly those four show up
  5. change the chunker              everything is "changed" (the recipe changed, not the files)
After each round it prints the plan, the time, and a BM25 search to show the index is current.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB), str(LAB.parents[1])]

from ragkit.acme import DOCS_DIR  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.manifest import content_hash as ref_hash, plan_ingest as ref_plan  # noqa: E402
from ragkit.pipeline import IngestPipeline  # noqa: E402

RESULTS = LAB / "results"


def functions(reference: bool):
    if reference:
        return ref_hash, ref_plan, "reference (ragkit.manifest)"
    import mine
    try:
        mine.content_hash(b"x", {})
        mine.plan_ingest({}, {})
    except NotImplementedError:
        raise SystemExit("mine.content_hash / mine.plan_ingest are not implemented yet "
                         "(exercise 5), or run with --reference")
    return mine.content_hash, mine.plan_ingest, "mine.py"


def make(store: Path, chunker: str, tok: str, reference: bool) -> IngestPipeline:
    h, p, _ = functions(reference)
    return IngestPipeline(store, make_chunker(chunker, tok), planner=p, hasher=h)


def report(title: str, pipe: IngestPipeline, root: Path, query: str) -> None:
    r = pipe.run(root)
    print(f"\n== {title}\n   {r}")
    for label, ids in (("added", r.plan.added), ("changed", r.plan.changed), ("removed", r.plan.removed)):
        if ids and len(ids) <= 6:
            print(f"   {label}: {', '.join(ids)}")
    hits = pipe.index.search(query, k=2)
    print(f"   search {query!r}: " + "; ".join(f"{h.chunk.id} [{h.chunk.classification}]" for h in hits))


def demo(args) -> None:
    root = RESULTS / "demo_corpus"
    store = RESULTS / "demo_store"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(store, ignore_errors=True)
    shutil.copytree(DOCS_DIR, root)
    _, _, who = functions(args.reference)
    print(f"demo corpus: {root}  (using {who})")
    q = "relocation lump sum Berlin"
    report("1. first run", make(store, args.chunker, args.tokenizer, args.reference), root, q)
    report("2. same files, new process", make(store, args.chunker, args.tokenizer, args.reference), root, q)

    sick = root / "hr-sick-leave.md"
    sick.write_text(sick.read_text(encoding="utf-8") + "\nUpdate: sick notes can now be uploaded in Pulse.\n",
                    encoding="utf-8")
    side = root / "hr-relocation.meta.yaml"
    side.write_text(side.read_text(encoding="utf-8").replace("classification: confidential",
                                                             "classification: internal"), encoding="utf-8")
    (root / "it-laptop-faq.md").unlink()
    (root / "hr-gym-2026.md").write_text(
        "---\nid: hr-gym-2026\ntitle: Gym Subsidy (2026)\ndepartment: hr\ndoc_type: policy\nversion: \"1.0\"\n"
        "effective_date: 2026-11-01\nowner: Orly Peretz\nclassification: internal\nlanguage: en\n---\n\n"
        "# Gym Subsidy\n\nAcme subsidizes gym memberships up to 150 NIS per month.\n", encoding="utf-8")
    print("\n   changes: edited hr-sick-leave.md, hr-relocation.meta.yaml (classification only),"
          " deleted it-laptop-faq.md, added hr-gym-2026.md")
    report("3. after the changes", make(store, args.chunker, args.tokenizer, args.reference), root, q)
    report("4. and again (nothing to do)", make(store, args.chunker, args.tokenizer, args.reference), root, q)
    other = "recursive:256:0" if not args.chunker.startswith("recursive") else "heading:400:40"
    report(f"5. new chunker {other}", make(store, other, args.tokenizer, args.reference), root, q)
    print(f"\nmanifest: {store / 'manifest.json'}   chunks: {store / 'chunks.jsonl'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--chunker", default="heading:400:40:150")
    ap.add_argument("--tokenizer", default="approx")
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--root", default=str(DOCS_DIR))
    ap.add_argument("--store", default=str(RESULTS / "index"))
    args = ap.parse_args()
    if args.demo:
        return demo(args)
    pipe = make(Path(args.store), args.chunker, args.tokenizer, args.reference)
    r = pipe.run(args.root)
    print(r)
    print(f"{len(pipe.index)} chunks in {args.store}")


if __name__ == "__main__":
    main()
