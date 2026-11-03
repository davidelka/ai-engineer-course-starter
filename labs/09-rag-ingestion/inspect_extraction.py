"""Exercise 1: look at what extraction really produces, before and after boilerplate removal.

    python labs/09-rag-ingestion/inspect_extraction.py --doc it-helpdesk
    python labs/09-rag-ingestion/inspect_extraction.py --doc sales-sla-2026
    python labs/09-rag-ingestion/inspect_extraction.py --doc sales-sla-2026 --pdf-mode plain
    python labs/09-rag-ingestion/inspect_extraction.py --doc hr-relocation
    python labs/09-rag-ingestion/inspect_extraction.py --doc co-haifa-office-he --trafilatura
    python labs/09-rag-ingestion/inspect_extraction.py --all          # one line per binary/HTML doc

For one document it prints: the naive extraction ("before": every text node of the HTML, or
pypdf's default output with headers, or the DOCX with header and footer), the ragkit
extraction ("after"), what was removed, sizes in characters and tokens, and whether the
golden quotes of that document are still findable. Full texts go to
results/extract_<id>_before.txt and _after.txt so you can diff them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[1]))

from ragkit.acme import DOCS_DIR, acme_qa  # noqa: E402
from ragkit.clean import collapse_ws, normalize  # noqa: E402
from ragkit.loaders import iter_sources, load_document  # noqa: E402
from ragkit.tokens import get_tokenizer  # noqa: E402

RESULTS = LAB / "results"


def find_source(doc_id: str):
    for s in iter_sources(DOCS_DIR):
        if s.id == doc_id:
            return s
    raise SystemExit(f"no document {doc_id!r}; ids are file names without the extension")


def show(title: str, text: str, n: int) -> None:
    print(f"\n----- {title} (first {n} chars) " + "-" * 30)
    print(text[:n].rstrip() + ("\n[...]" if len(text) > n else ""))


def quotes_for(doc_id: str) -> list[tuple[str, str]]:
    return [(q["id"], sq["quote"]) for q in acme_qa() for sq in q["source_quotes"]
            if sq["source_id"] == doc_id]


def one(doc_id: str, args) -> None:
    tok = get_tokenizer(args.tokenizer)
    src = find_source(doc_id)
    opts = {}
    if src.path.suffix == ".pdf":
        opts["mode"] = args.pdf_mode
    if src.path.suffix == ".html" and args.trafilatura:
        opts["extractor"] = "trafilatura"
    doc = load_document(src, keep_raw=True, **opts)
    before = normalize(doc.extras["raw_text"])
    after = doc.text
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"extract_{doc_id}_before.txt").write_text(before, encoding="utf-8")
    (RESULTS / f"extract_{doc_id}_after.txt").write_text(after, encoding="utf-8")

    print(f"{doc_id}  format={doc.format}  language={doc.language}  options={opts or 'default'}")
    print(f"metadata: title={doc.title!r} version={doc.version} effective_date={doc.effective_date} "
          f"classification={doc.classification}")
    bt, at = tok.count(before), tok.count(after)
    print(f"before: {len(before):6d} chars {bt:5d} tokens | after: {len(after):6d} chars {at:5d} tokens "
          f"| removed {1 - at / max(1, bt):.0%} of the tokens ({tok.name})")
    show("BEFORE: naive extraction", before, args.chars)
    show("AFTER: ragkit extraction", after, args.chars)
    if doc.extras["removed"]:
        print("\n----- removed as boilerplate " + "-" * 30)
        for r in doc.extras["removed"]:
            print("  x", r[:110])
    qs = quotes_for(doc_id)
    if qs:
        print("\n----- golden quotes from this document " + "-" * 20)
        for qid, quote in qs:
            ok_after = collapse_ws(quote) in collapse_ws(after)
            ok_before = collapse_ws(quote) in collapse_ws(before)
            print(f"  {qid}: after={'found' if ok_after else 'MISSING'} before={'found' if ok_before else 'MISSING'}"
                  f"  \"{quote[:70]}\"")
    print(f"\nfull texts: results/extract_{doc_id}_before.txt  results/extract_{doc_id}_after.txt")


def all_docs(args) -> None:
    tok = get_tokenizer(args.tokenizer)
    print("doc                      format  before_tok  after_tok  removed  boilerplate items")
    for s in iter_sources(DOCS_DIR):
        if s.path.suffix == ".md":
            continue
        d = load_document(s, keep_raw=True)
        bt, at = tok.count(normalize(d.extras["raw_text"])), tok.count(d.text)
        print(f"{s.id:24s} {d.format:6s} {bt:10d} {at:10d} {1 - at / max(1, bt):7.0%}  {len(d.extras['removed'])}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", default="it-helpdesk")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pdf-mode", choices=["layout", "plain"], default="layout")
    ap.add_argument("--trafilatura", action="store_true", help="HTML: use trafilatura instead of the rules")
    ap.add_argument("--chars", type=int, default=900)
    ap.add_argument("--tokenizer", default="approx", help="approx (default, reproducible) or tiktoken")
    args = ap.parse_args()
    all_docs(args) if args.all else one(args.doc, args)


if __name__ == "__main__":
    main()
