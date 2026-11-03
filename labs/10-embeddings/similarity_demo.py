"""Exercises 1-2: the geometry of embeddings, by hand and with a real model.

    python labs/10-embeddings/similarity_demo.py --part math          # no model needed
    python labs/10-embeddings/similarity_demo.py                      # e5-small (downloads once)
    python labs/10-embeddings/similarity_demo.py --model openai:text-embedding-3-small
    python labs/10-embeddings/similarity_demo.py --model fake         # offline, NOT semantic
    python labs/10-embeddings/similarity_demo.py --mine               # rank with YOUR cosine_top_k

Part "math": three 2-D vectors where dot product, cosine and L2 disagree, and then agree
after normalization. Part "model": eight sentences (English, their Hebrew translations, a
paraphrase with no shared words, a negation, unrelated text) as a cosine matrix, then one
question ranked against them with and without the e5 "query:"/"passage:" prefixes.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from common import DEFAULT_MODEL, MODEL_HELP, embedder  # noqa: E402
from ragkit.embed import SentenceTransformerEmbedder  # noqa: E402
from ragkit.embed.cache import CachedEmbedder  # noqa: E402
from ragkit.vectors import cosine_top_k, l2_normalize, similarity  # noqa: E402

SENTENCES = [
    ("EN", "Up to 5 unused vacation days may be carried over to the next calendar year."),
    ("HE", "עד 5 ימי חופשה שלא נוצלו אפשר להעביר לשנה הקלנדרית הבאה."),
    ("PARA", "Leftover days off can be moved into January instead of being lost."),
    ("NEG", "Unused vacation days may not be carried over to the next calendar year."),
    ("EN2", "The Tel Aviv parking garage closes at 22:00 every night."),
    ("HE2", "החניון של משרד תל אביב נסגר בכל לילה בשעה 22:00."),
    ("CODE", "Deploys are blocked during Quiet Hours; see #deploys."),
    ("ID", "Primary region il-central-1, failover to eu-central-1."),
]
QUESTION = "How many vacation days can I take into next year?"


def part_math() -> None:
    print("=== Part 1: dot, cosine and L2 on three 2-D vectors ===\n")
    q = np.array([1.0, 0.0])
    m = np.array([[0.9, 0.1],      # A: almost the same direction, length ~0.9
                  [3.0, 3.0],      # B: 45 degrees off, but long (length ~4.2)
                  [0.7, -0.7]])    # C: 45 degrees off the other way, length ~1
    names = ["A (same direction, short)", "B (45 deg off, long)", "C (45 deg off, unit-ish)"]
    for metric in ("dot", "cosine", "l2"):
        s = similarity(q, m, metric)
        order = " > ".join(names[i][0] for i in np.argsort(-s, kind="stable"))
        print(f"  {metric:6s} scores {np.round(s, 3)}   ranking {order}")
    print("\n  dot rewards length (B wins), cosine looks only at the angle (A wins),")
    print("  L2 (shown as -distance^2) punishes B for being far away.\n")
    mn, qn = l2_normalize(m), l2_normalize(q)[0]
    print("  after l2_normalize (every vector has length 1):")
    for metric in ("dot", "cosine", "l2"):
        s = similarity(qn, mn, metric)
        order = " > ".join(names[i][0] for i in np.argsort(-s, kind="stable"))
        print(f"  {metric:6s} scores {np.round(s, 3)}   ranking {order}")
    print("\n  Same ranking for all three: |a-b|^2 = 2 - 2*cos(a,b) on unit vectors.")
    print("  That is why we normalize once at write time and use the cheapest operation (dot).\n")


def part_model(spec: str, use_mine: bool) -> None:
    emb = embedder(spec)
    print(f"=== Part 2: real sentences with model {spec} ({emb.model_id}) ===\n")
    for i, (tag, s) in enumerate(SENTENCES):
        print(f"  [{i}] {tag:5s} {s}")
    v = emb.embed_documents([s for _, s in SENTENCES])
    print(f"\n  vectors: shape {v.shape}, norms {np.round(np.linalg.norm(v, axis=1)[:3], 4)}... "
          f"(normalized: dot == cosine)\n")
    sim = l2_normalize(v) @ l2_normalize(v).T
    print("  cosine matrix (rows/cols = sentence numbers):")
    print("       " + " ".join(f"{j:6d}" for j in range(len(SENTENCES))))
    for i in range(len(SENTENCES)):
        print(f"  [{i}] " + " ".join(f"{sim[i, j]:6.3f}" for j in range(len(SENTENCES))))
    print("\n  Read it like this:")
    print(f"  - EN vs its Hebrew translation [0,1]: {sim[0, 1]:.3f}   EN vs paraphrase [0,2]: {sim[0, 2]:.3f}")
    print(f"  - EN vs its NEGATION [0,3]: {sim[0, 3]:.3f}   (high = the model barely sees 'not')")
    print(f"  - EN vs unrelated parking [0,4]: {sim[0, 4]:.3f}   parking EN vs HE [4,5]: {sim[4, 5]:.3f}")
    print("  Absolute values depend on the model (e5 scores are squeezed into ~0.7-0.9); compare")
    print("  numbers WITHIN one model, never across models.\n")

    top = __import__("mine").cosine_top_k if use_mine else cosine_top_k
    print(f"  question: {QUESTION}" + ("   (ranked with mine.cosine_top_k)" if use_mine else ""))
    inner = emb.inner if isinstance(emb, CachedEmbedder) else emb
    q = emb.embed_queries([QUESTION])[0]
    idx, sc = top(q, v, len(SENTENCES))
    print("  ranked as query vs passages:")
    for i, s in zip(idx, sc):
        print(f"    {s:.3f}  [{i}] {SENTENCES[i][0]}")
    if isinstance(inner, SentenceTransformerEmbedder) and inner.query_prefix:
        raw = SentenceTransformerEmbedder(inner.name, dim=inner.dim, model=inner.model)   # same weights, no prefixes
        q2 = raw.embed_queries([QUESTION])[0]
        v2 = raw.embed_documents([s for _, s in SENTENCES])
        idx2, sc2 = top(q2, v2, len(SENTENCES))
        print("  the same, WITHOUT the 'query: ' / 'passage: ' prefixes:")
        for i, s in zip(idx2, sc2):
            print(f"    {s:.3f}  [{i}] {SENTENCES[i][0]}")
        print("  Compare the order and the gap between the top answer and the rest.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help=MODEL_HELP)
    ap.add_argument("--part", choices=["math", "model", "all"], default="all")
    ap.add_argument("--mine", action="store_true", help="rank with mine.cosine_top_k")
    args = ap.parse_args()
    if args.part in ("math", "all"):
        part_math()
    if args.part in ("model", "all"):
        try:
            part_model(args.model, args.mine)
        except ImportError as exc:
            sys.exit(f"\n{exc}")
        except NotImplementedError as exc:
            sys.exit(f"\n{exc}: implement exercise 2 in mine.py, or run without --mine")


if __name__ == "__main__":
    main()
