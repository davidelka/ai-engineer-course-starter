"""Exercise 1 — the price of a language.

Counts tokens for the same paragraph in English, Hebrew and Arabic with:
  - Anthropic's count_tokens endpoint (free, needs ANTHROPIC_API_KEY)
  - tiktoken's o200k_base encoding (OpenAI's recent tokenizer, fully offline)
  - Gemini's count_tokens (needs GEMINI_API_KEY)
Providers without a key are skipped.

Run:  python labs/01-prompting/count_tokens.py [--claude-model claude-haiku-5-5]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from promptlab.__main__ import _load_dotenv  # noqa: E402

LANGS = {"en": "English", "he": "Hebrew", "ar": "Arabic"}


def count_claude(text: str, model: str) -> int:
    import anthropic

    resp = anthropic.Anthropic().messages.count_tokens(
        model=model, messages=[{"role": "user", "content": text}]
    )
    return resp.input_tokens  # includes a few tokens of message framing


def count_tiktoken(text: str) -> int:
    import tiktoken

    return len(tiktoken.get_encoding("o200k_base").encode(text))


def count_gemini(text: str, model: str) -> int:
    from google import genai

    return genai.Client().models.count_tokens(model=model, contents=text).total_tokens


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude-model", default="claude-haiku-5-5")
    ap.add_argument("--gemini-model", default="gemini-3.6-flash")
    args = ap.parse_args()

    texts = {k: (ROOT / "data" / "texts" / f"{k}.txt").read_text(encoding="utf-8").strip() for k in LANGS}

    counters = {"o200k (OpenAI)": count_tiktoken}
    if os.environ.get("ANTHROPIC_API_KEY"):
        counters["Claude"] = lambda t: count_claude(t, args.claude_model)
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        counters["Gemini"] = lambda t: count_gemini(t, args.gemini_model)

    results: dict[str, dict[str, int]] = {}
    for name, fn in counters.items():
        try:
            results[name] = {k: fn(t) for k, t in texts.items()}
        except Exception as exc:
            print(f"[skip] {name}: {type(exc).__name__}: {exc}")

    print(f"\n{'tokenizer':<16}" + "".join(f"{LANGS[k]:>16}" for k in LANGS))
    for name, counts in results.items():
        base = counts["en"]
        cells = [f"{c} ({c / base:.2f}x)" for c in (counts[k] for k in LANGS)]
        print(f"{name:<16}" + "".join(f"{c:>16}" for c in cells))

    words = {k: len(t.split()) for k, t in texts.items()}
    print("\nwords:      " + ", ".join(f"{LANGS[k]} {w}" for k, w in words.items()))
    print("characters: " + ", ".join(f"{LANGS[k]} {len(t)}" for k, t in texts.items()))
    print("\nQuestion for your notes: what would the same chatbot cost per month in each language?")


if __name__ == "__main__":
    main()
