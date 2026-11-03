"""Exercises 1 and 2: RRF and weighted fusion, computed in the open on real Acme rankings.

    python labs/12-advanced-retrieval/fusion_demo.py                      # part rrf, q040, fake dense
    python labs/12-advanced-retrieval/fusion_demo.py --dense e5-small     # with the real model
    python labs/12-advanced-retrieval/fusion_demo.py --q q039 --mine      # YOUR rrf from mine.py
    python labs/12-advanced-retrieval/fusion_demo.py --part weighted --mine

Part rrf: the top chunks of BM25 and of the dense retriever for one golden question, every
RRF term written out (1/(k+rank)), the fused order, and how the top 5 changes with k.
Part weighted: the same lists with their RAW scores, min-max normalized, fused with several
weights; then three small synthetic cases that show the normalization traps.
Relevant documents (the question's source_ids) are marked with '*'.
"""

from __future__ import annotations

import argparse
import sys

from common import DENSE_HELP, acme_qa, bm25_index, chunks, dense_index
from ragkit import fusion as ref


def impl(use_mine: bool):
    if not use_mine:
        return ref.rrf, ref.minmax, ref.weighted_fusion
    import mine
    try:
        mine.rrf([["a"]])
    except NotImplementedError as exc:
        sys.exit(f"{exc}: implement exercise 1 in mine.py, or run without --mine")
    return mine.rrf, mine.minmax_normalize, mine.weighted_fusion


def star(cid: str, rel: set) -> str:
    return "*" if cid.split("#")[0] in rel else " "


def part_rrf(q, a, b, rrf, show: int, use_mine: bool):
    rel = set(q["source_ids"])
    ra = [h.chunk.id for h in a]
    rb = [h.chunk.id for h in b]
    print(f"\n{q['id']} [{q['type']}] {q['question']}\nrelevant documents: {', '.join(sorted(rel))}  (marked *)")
    print(f"\nBM25 top {show}:")
    for i, cid in enumerate(ra[:show], 1):
        print(f"  {i:2d}. {star(cid, rel)} {cid}")
    print(f"dense top {show}:")
    for i, cid in enumerate(rb[:show], 1):
        print(f"  {i:2d}. {star(cid, rel)} {cid}")
    k = 60
    fused = rrf([ra, rb], k=k)
    pa, pb = {c: i for i, c in enumerate(ra, 1)}, {c: i for i, c in enumerate(rb, 1)}
    print(f"\nRRF with k={k}: score = 1/(k + rank in BM25) + 1/(k + rank in dense); missing = no term")
    for i, (cid, s) in enumerate(fused[:show], 1):
        ta = f"1/({k}+{pa[cid]})={1 / (k + pa[cid]):.4f}" if cid in pa else "not in BM25 list"
        tb = f"1/({k}+{pb[cid]})={1 / (k + pb[cid]):.4f}" if cid in pb else "not in dense list"
        print(f"  {i:2d}. {star(cid, rel)} {cid:32s} {ta:22s} + {tb:22s} = {s:.4f}")
    print("\nhow k changes the fused top 5 DOCUMENTS (chunks of one document collapse to its best rank;")
    print("k small = 'first place anywhere wins', k large = 'agreement wins'):")
    for kk in (0, 1, 10, 60, 200):
        docs = list(dict.fromkeys(c.split("#")[0] for c, _ in rrf([ra, rb], k=kk)))[:5]
        r5 = len(rel & set(docs)) / len(rel)
        print(f"  k={kk:<4d} recall@5 {r5:.2f}  " + "  ".join(("*" if d in rel else "") + d for d in docs))
    print("  (try --q q050 or --q q015 to see k change the answer)")
    if use_mine:
        same = [c for c, _ in rrf([ra, rb])] == [c for c, _ in ref.rrf([ra, rb])]
        print(f"\nmine.rrf matches ragkit.fusion.rrf on this question: {same}")


def part_weighted(q, a, b, minmax, wf, show: int):
    rel = set(q["source_ids"])
    sa = {h.chunk.id: h.score for h in a}
    sb = {h.chunk.id: h.score for h in b}
    na, nb = minmax(sa), minmax(sb)
    print(f"\n{q['id']} {q['question']}")
    print("\nraw scores live on different scales (BM25 unbounded, cosine in a narrow band):")
    for name, s, n in (("BM25", sa, na), ("dense", sb, nb)):
        print(f"  {name}:")
        for cid in list(s)[:show]:
            print(f"    {star(cid, rel)} {cid:32s} raw {s[cid]:8.4f}  ->  min-max {n[cid]:.3f}")
    print("\nfused top 5 for several weights (BM25 weight, dense weight):")
    for w in ((1.0, 0.0), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.0, 1.0)):
        top = wf([sa, sb], list(w))[:5]
        print(f"  {w}: " + "  ".join(f"{star(c, rel)}{c}({s:.2f})" for c, s in top))

    print("\nthree traps of min-max normalization (synthetic numbers, so you can check them by hand):")
    print("  1. one outlier squashes the rest. BM25 {a: 40, b: 9, c: 8, d: 7} ->",
          {k: round(v, 3) for k, v in minmax({"a": 40, "b": 9, "c": 8, "d": 7}).items()})
    print("     b, c and d are now almost 0, as if BM25 barely found them.")
    print("  2. the best item always gets 1.0, even when it is bad in absolute terms.")
    print("     dense {x: 0.31, y: 0.30} (both unrelated) ->", minmax({"x": 0.31, "y": 0.30}))
    print("  3. the LAST item of a list gets 0.0, exactly like an item that list never returned:")
    out = wf([{"a": 10, "b": 5, "c": 0}, {"b": 0.9, "c": 0.8}], [0.5, 0.5])
    print("     BM25 {a: 10, b: 5, c: 0}, dense {b: 0.9, c: 0.8} ->", [(c, round(s, 3)) for c, s in out])
    print("     c was 2nd of 2 for dense and got 0 from it, the same as a, which dense did not return.")
    print("  RRF has none of these problems, because it never looks at the scores; it also throws")
    print("  away the information that one result was FAR ahead. That is the trade-off.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", choices=["rrf", "weighted", "both"], default="rrf")
    ap.add_argument("--q", default="q040", help="golden question id (q040 multi-hop, q039 cross-lingual...)")
    ap.add_argument("--dense", default="fake", help=DENSE_HELP)
    ap.add_argument("--show", type=int, default=8)
    ap.add_argument("--mine", action="store_true", help="use your functions from mine.py")
    args = ap.parse_args()
    qa = {q["id"]: q for q in acme_qa()}
    if args.q not in qa:
        sys.exit(f"unknown question {args.q}")
    q = qa[args.q]
    cs = chunks()
    bm25 = bm25_index(cs)
    try:
        dense = dense_index(args.dense, cs)
    except ImportError as exc:
        sys.exit(str(exc))
    a, b = bm25.search(q["question"], k=30), dense.search(q["question"], k=30)
    rrf, minmax, wf = impl(args.mine)
    if args.mine and args.part in ("weighted", "both"):
        try:
            minmax({"a": 1.0})
        except NotImplementedError as exc:
            sys.exit(f"{exc}: implement exercise 2 in mine.py, or run without --mine")
    if args.part in ("rrf", "both"):
        part_rrf(q, a, b, rrf, args.show, args.mine)
    if args.part in ("weighted", "both"):
        part_weighted(q, a, b, minmax, wf, args.show)


if __name__ == "__main__":
    main()
