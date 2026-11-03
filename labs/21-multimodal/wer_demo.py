"""Exercise 5 (after your tests pass): WER on Hebrew examples, with and without normalization.

    python labs/21-multimodal/wer_demo.py           # reference implementation (voicekit.text)
    python labs/21-multimodal/wer_demo.py --mine    # your mine.normalize_hebrew and mine.wer

Each pair is (what the student was asked to say, what a recognizer wrote). Read the
alignment: which "errors" are real, and which disappear after normalization?
"""

from __future__ import annotations

import argparse

import _lab  # noqa: F401

PAIRS = [
    ("niqqud and punctuation only", "שָׁלוֹם, מָה שְׁלוֹמְךָ?", "שלום מה שלומך"),
    ("final letter written wrong", "אני גר בירושלים", "אני גר בירושלימ"),
    ("gershayim in an acronym", 'הוא שירת בצה"ל', "הוא שירת בצהל"),
    ("homophone spelling (כ/ק)", "התלמיד קנה כרטיס", "התלמיד קנה קרטיס"),
    ("prefix split from the word", "ובבית הספר יש ספרייה", "ו בבית הספר יש ספרייה"),
    ("a real substitution: p heard as b", "פתח את הספר בפרק שלוש", "פתח את הספר בברק שלוש"),
    ("a skipped word", "אני רוצה לקנות כרטיס לאוטובוס", "אני רוצה כרטיס לאוטובוס"),
    ("number written as digits", "יש לי שלושה אחים", "יש לי 3 אחים"),
    ("hallucinated extra words", "תודה רבה", "תודה רבה לכם על הצפייה"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", action="store_true")
    a = ap.parse_args()
    if a.mine:
        from mine import normalize_hebrew, wer
    else:
        from voicekit.text import normalize_hebrew, wer
    from voicekit.text import cer
    for title, ref, hyp in PAIRS:
        raw = wer(ref, hyp, normalize=None)
        norm = wer(ref, hyp)
        print(f"\n{title}\n   ref: {ref}\n   hyp: {hyp}")
        print(f"   normalized ref: {normalize_hebrew(ref)}\n   normalized hyp: {normalize_hebrew(hyp)}")
        print(f"   WER raw {raw.rate:.2f} -> normalized {norm.rate:.2f} "
              f"(S={norm.substitutions} D={norm.deletions} I={norm.insertions}), CER {cer(ref, hyp).rate:.2f}")
        for op, r, h in norm.ops:
            if op != "ok":
                print(f"      {op:3}  {r or '-'}  ->  {h or '-'}")


if __name__ == "__main__":
    main()
