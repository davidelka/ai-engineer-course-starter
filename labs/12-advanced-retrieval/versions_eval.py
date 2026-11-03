"""Exercise 5: version-aware retrieval. Does the superseded policy still reach the top 5?

    python labs/12-advanced-retrieval/versions_eval.py                 # e5-small hybrid as the base
    python labs/12-advanced-retrieval/versions_eval.py --dense fake    # offline
    python labs/12-advanced-retrieval/versions_eval.py --mine          # YOUR drop_superseded

The data (data/acme/corpus): 9 pairs of policy versions. Only the NEWER document carries
`supersedes: <old id>` in its metadata, e.g. hr-vacation-2026 -> hr-vacation-2024,
fin-travel-2026 -> fin-travel-2025, it-saas-access-v2-2 -> it-saas-access-v2-1.
The 11 version_conflict golden questions are tagged `stale:<doc id>` with the document that
would give the WRONG (old) answer. Three conflicts have NO supersedes link: q004 (an all-hands
note corrected later), q005 (a meeting decision that was reversed), q011 (a proposal).

Policies compared on top of the hybrid retriever (BM25 + dense, RRF, top 50 candidates):
  none                no filter
  retrieved           drop a document when a newer version of it is ALSO in the candidates
  corpus              drop every document that has a newer version anywhere (pre-filter)
  recent w=0.1/0.3    boost by effective_date (no links needed)
For each: recall@5 and MRR on version_conflict and on ALL, and "stale in top 5": in how many of
the 11 questions a stale document is still among the first 5 documents. Then a per-question
list, and one question that ASKS about the old version, to show what "corpus" costs.
"""

from __future__ import annotations

import argparse
import sys

from common import DEFAULT_DENSE, DENSE_HELP, acme_qa, bm25_index, chunks, dense_index
from ragkit import metrics as M
from ragkit.hybrid import HybridRetriever
from ragkit.versions import VersionAwareRetriever, stale_at_k, stale_docs, supersedes_map


class MineFilter:
    def __init__(self, base):
        import mine
        self.base, self.fn, self.name = base, mine.drop_superseded, "mine"

    def search(self, query, k=5, where=None):
        return self.fn(self.base.search(query, k=max(k, 50), where=where))[:k]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dense", default=DEFAULT_DENSE, help=DENSE_HELP)
    ap.add_argument("--mine", action="store_true", help="add the policy from mine.drop_superseded")
    args = ap.parse_args()

    qa = acme_qa()
    cs = chunks()
    try:
        hybrid = HybridRetriever({"bm25": bm25_index(cs), "dense": dense_index(args.dense, cs)})
    except ImportError as exc:
        sys.exit(str(exc))
    smap = supersedes_map(cs)
    print("supersedes links found in chunk metadata (old -> new):")
    for old, new in sorted(smap.items()):
        print(f"  - {old} -> {', '.join(sorted(new))}")

    rs = {"none": hybrid,
          "retrieved": VersionAwareRetriever(hybrid, mode="retrieved"),
          "corpus": VersionAwareRetriever(hybrid, mode="corpus", superseded_by=smap),
          "recent w=0.1": VersionAwareRetriever(hybrid, mode="recent", recency_weight=0.1),
          "recent w=0.3": VersionAwareRetriever(hybrid, mode="recent", recency_weight=0.3)}
    if args.mine:
        rs["mine"] = MineFilter(hybrid)
        try:
            rs["mine"].search("vacation carry over", 3)
        except NotImplementedError as exc:
            sys.exit(f"{exc}: implement exercise 5 in mine.py, or run without --mine")

    vc = [q for q in qa if q["type"] == "version_conflict"]
    res = {n: M.run_queries(r, qa, depth=10) for n, r in rs.items()}
    print(f"\nbase: hybrid BM25 + {args.dense} (RRF k=60)")
    for n, rr in res.items():
        t = M.summarize(rr)
        by = {x.qid: x for x in rr}
        stale = sum(stale_at_k(by[q["id"]].ranked_docs, q, 5) for q in vc)
        print(f"- {n}: version_conflict recall@5 {t['version_conflict']['recall@5']:.3f}, MRR "
              f"{t['version_conflict']['mrr']:.3f}; stale in top 5: {stale:.0f}/11; "
              f"ALL recall@5 {t['ALL']['recall@5']:.3f}, MRR {t['ALL']['mrr']:.3f}")

    print("\nper question: rank of the first correct document / stale document in the top 5? (none -> retrieved)")
    a, b = {x.qid: x for x in res["none"]}, {x.qid: x for x in res["retrieved"]}
    for q in vc:
        def rank(r):
            return next((str(i) for i, d in enumerate(r.ranked_docs, 1) if d in r.relevant), "-")
        sa, sb = stale_at_k(a[q["id"]].ranked_docs, q, 5), stale_at_k(b[q["id"]].ranked_docs, q, 5)
        st = stale_docs(q)
        linked = [s for s in st if s in smap]
        link = ("NO supersedes link" if not linked else "has supersedes link" if len(linked) == len(st)
                else f"link only for {', '.join(linked)}")
        print(f"  {q['id']} rank {rank(a[q['id']])} -> {rank(b[q['id']])}, stale {'yes' if sa else 'no'} -> "
              f"{'yes' if sb else 'no'}  [{link}: {', '.join(sorted(stale_docs(q))) or 'proposal'}]  {q['question'][:60]}")

    q_old = "What was the vacation carry-over rule in the 2024 vacation policy?"
    print(f"\na question ABOUT the old version: {q_old!r}")
    for n in ("none", "retrieved", "corpus"):
        docs = M.dedupe(h.chunk.doc_id for h in rs[n].search(q_old, k=15))[:5]
        print(f"  - {n}: {', '.join(docs)}")
    print("  'corpus' can never return hr-vacation-2024. 'retrieved' drops it here too, because the 2026")
    print("  version is retrieved as well: the question's intent (the OLD rule) needs the generation step,")
    print("  or a filter that the user can turn off (e.g. where={'effective_date': ...}).")


if __name__ == "__main__":
    main()
