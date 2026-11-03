"""Exercise 2: Hebrew text, invisible characters, and what normalization buys you.

    python labs/09-rag-ingestion/normalize_demo.py
    python labs/09-rag-ingestion/normalize_demo.py --tokenizer tiktoken     # real o200k counts
    python labs/09-rag-ingestion/normalize_demo.py --claude                 # + Claude's own count (free endpoint, needs the key)

Part 1 builds a sentence the way it arrives when copied from Word or a browser: RLM marks,
a zero-width space, a non-breaking space, gershayim (U+05F4) instead of a quote, niqqud.
It shows every odd code point, then searches it with BM25 before and after normalize().

Part 2 counts tokens for the SAME vacation policy in English and in Hebrew
(hr-vacation-2026 and hr-vacation-2026-he), and the cost of putting each in a prompt.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[1]))

from llmkit.pricing import PRICES  # noqa: E402
from ragkit.acme import acme_documents  # noqa: E402
from ragkit.clean import invisible_report, normalize  # noqa: E402
from ragkit.retrieval import BM25Index, analyze  # noqa: E402
from ragkit.tokens import get_tokenizer  # noqa: E402
from ragkit.types import Chunk  # noqa: E402

DIRTY = ("‏מנהל‏/ת הצוות או סמנכ״ל משאבי אנוש מאשרים "
         "חופשה​ של יותר מ-10 ימים. בְּהַצְלָחָה!")


def codepoints(s: str) -> None:
    for ch in s:
        if not ("א" <= ch <= "ת" or ch.isascii() and ch.isprintable()):
            print(f"    U+{ord(ch):04X}  {unicodedata.name(ch, '?')}")


def part1() -> None:
    print("PART 1: invisible characters")
    print(f"  dirty text   : {DIRTY}")
    print(f"  looks like   : {len(DIRTY)} characters; the odd ones:")
    codepoints(DIRTY)
    clean = normalize(DIRTY)
    print(f"  normalized   : {clean}  ({len(clean)} characters)")
    print(f"  report       : {dict(invisible_report(DIRTY))}")
    print(f"  terms before : {analyze(DIRTY, hebrew_prefixes=False)}")
    print(f"  terms after  : {analyze(clean, hebrew_prefixes=False)}")
    for label, text in (("not normalized", DIRTY), ("normalized", clean)):
        idx = BM25Index(with_context=False, analyzer=lambda t: analyze(t, hebrew_prefixes=False))
        idx.add([Chunk(id="x#0", doc_id="x", text=text, start=0, end=len(text))])
        for q in ("חופשה", 'סמנכ"ל', "בהצלחה"):
            hits = idx.search(q)
            print(f"  search {q!r:12} in {label:15}: {'FOUND' if hits else 'not found'}")
    for phrase in ("חופשה של", "מנהל/ת", 'סמנכ"ל משאבי אנוש'):
        print(f"  exact phrase {phrase!r:22}: dirty={'FOUND' if phrase in DIRTY else 'not found':9} "
              f"normalized={'FOUND' if phrase in clean else 'not found'}")
    print("  Read it like this: BM25 with a \\w+ tokenizer happens to survive RLM and zero-width\n"
          "  spaces (they are not word characters, so they split words where they already split),\n"
          "  but niqqud shatters words into letters. Exact matching (quotes, citations, dedup\n"
          "  hashes) breaks on every invisible character. Normalize once, at ingestion, and apply\n"
          "  the same normalize() to queries and quotes.")


def claude_counts(docs) -> None:
    from ctxkit.tokens import claude_count_tokens
    from llmkit import load_dotenv

    load_dotenv()
    print("\n  Claude Haiku 5.5 (count_tokens endpoint, free):")
    for d in docs:
        n = claude_count_tokens({"model": "claude-haiku-5-5",
                                 "messages": [{"role": "user", "content": d.text}]})
        words = len(d.text.split())
        print(f"  {d.id:22s} {n:6d} tokens ({n / max(1, words):.2f} tokens/word, includes ~8 tokens of message overhead)")


def part2(tok_name: str, claude: bool = False) -> None:
    tok = get_tokenizer(tok_name)
    docs = {d.id: d for d in acme_documents()}
    en, he = docs["hr-vacation-2026"], docs["hr-vacation-2026-he"]
    print(f"\nPART 2: the same policy in two languages ({tok.name})")
    price = PRICES["claude-haiku-5-5"]["input"]
    for d in (en, he):
        n = tok.count(d.text)
        words = len(d.text.split())
        print(f"  {d.id:22s} {len(d.text):6d} chars {words:5d} words {n:6d} tokens "
              f"({n / max(1, words):.2f} tokens/word)  ${n * price / 1e6:.6f} per prompt on Haiku 5.5")
    print("  The Hebrew version is shorter than the English one (it is a summary translation), so\n"
          "  compare tokens PER WORD, not totals.")
    print("  Note: 'approx' splits words into <=5-letter pieces, so it understates Hebrew. Run with\n"
          "  --tokenizer tiktoken, and remember Claude's tokenizer is different again: the exact\n"
          "  number for Claude comes from the count_tokens endpoint (lesson 4).")
    if claude:
        claude_counts((en, he))
    print("\n  Hebrew prefixes: the analyzer also indexes words without ו/ה/ב/ל/מ/ש/כ prefixes:")
    for w in ("בחניון", "והחופשה", "שהעובד", "משרד"):
        print(f"    {w:10} -> {analyze(w)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", default="approx")
    ap.add_argument("--claude", action="store_true", help="also count with Claude's count_tokens (free)")
    args = ap.parse_args()
    part1()
    part2(args.tokenizer, args.claude)


if __name__ == "__main__":
    main()
