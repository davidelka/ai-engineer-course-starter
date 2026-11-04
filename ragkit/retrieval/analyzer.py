"""Text analysis for lexical retrieval: text -> terms.

Lowercase, split into Unicode words (Hebrew letters are \\w), drop stopwords, and for
Hebrew optionally add the word without its attached prefix letters.

Hebrew writes several function words as one-letter prefixes glued to the next word:
ו (and), ה (the), ב (in), ל (to), מ (from), ש (that), כ (as). "בחניון" (in the parking lot)
and "החניון" (the parking lot) share no token with "חניון" unless something strips the
prefix. Real systems use a morphological analyzer (e.g. HebMorph for Elasticsearch, or
the analyzers inside a multilingual embedding model, lesson 10). This analyzer does the
crude thing: for a Hebrew word of 4+ letters starting with a prefix letter, it ALSO emits
the word without its first letter, and (only for 5+ letters whose second letter is also a
prefix letter) without its first two. All forms are indexed, so exact matches still win,
and recall goes up at some cost in precision ("שלום" -> "לום", "הלוואה" -> "לוואה", "וואה").
Two side effects: the variants count in BM25's document length (Hebrew chunks look longer,
about x1.6 terms on Acme's Hebrew Markdown docs), and the same analyzer runs on the query,
so a query word with two prefixes can match three terms and weigh up to 3x.
"""

from __future__ import annotations

import re

WORD_RE = re.compile(r"\w+", re.U)
HEB_PREFIX = set("והבלמשכ")
HEB_WORD_RE = re.compile(r"^[א-ת]+$")

EN_STOP = frozenset("""a an and are as at be but by can do does for from has have how i if in is it
its my of on or our so than that the their them then there these they this to was we were what
when where which who whom why will with you your""".split())
HE_STOP = frozenset("""של את על עם זה זו זאת הוא היא הם הן אני אנחנו אתה את גם או אם כי לא כן יש אין
מה מי איך כמה למה מתי איפה כל עד אל בין אחרי לפני רק עוד היה היו יהיה""".split())


def hebrew_variants(w: str) -> list[str]:
    out = []
    if HEB_WORD_RE.match(w) and len(w) >= 4 and w[0] in HEB_PREFIX:
        out.append(w[1:])
        if len(w) >= 5 and w[1] in HEB_PREFIX:
            out.append(w[2:])
    return out


def analyze(text: str, *, hebrew_prefixes: bool = True, stopwords: bool = True) -> list[str]:
    terms: list[str] = []
    for w in WORD_RE.findall(text.lower()):
        if stopwords and (w in EN_STOP or w in HE_STOP):
            continue
        terms.append(w)
        if hebrew_prefixes:
            terms.extend(hebrew_variants(w))
    return terms
