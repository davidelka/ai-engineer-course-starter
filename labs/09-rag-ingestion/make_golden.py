"""Regenerate tests/golden_sections.json from the reference HeadingChunker (you do not need to
run this; it is here so you can see how the golden expectations were made).

For every golden source quote: the section paths of the reference chunks that contain it
(heading chunker, max_tokens=400, overlap=40, approx tokenizer). Your heading_chunks must put
each quote in a chunk whose section_path is one of these.

    python labs/09-rag-ingestion/make_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[1]))

from ragkit.acme import acme_documents, acme_qa  # noqa: E402
from ragkit.chunking import HeadingChunker  # noqa: E402
from ragkit.evaluate import norm  # noqa: E402
from ragkit.tokens import ApproxTokenizer  # noqa: E402


def main() -> None:
    docs = {d.id: d for d in acme_documents()}
    ch = HeadingChunker(400, 40, tokenizer=ApproxTokenizer())
    chunks = {i: ch.split(d) for i, d in docs.items()}
    rows = []
    for q in acme_qa():
        for sq in q["source_quotes"]:
            quote = norm(sq["quote"])
            paths = sorted({tuple(c.section_path) for c in chunks[sq["source_id"]] if quote in norm(c.text)})
            rows.append({"qid": q["id"], "source_id": sq["source_id"], "quote": sq["quote"],
                         "paths": [list(p) for p in paths]})
    out = LAB / "tests" / "golden_sections.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} quote expectations to {out}")


if __name__ == "__main__":
    main()
