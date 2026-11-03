"""A rule-based "tutor brain": the offline, free baseline (like F3's heuristic extractor).

It detects a fixed list of typical Arabic-speaker errors with patterns and a small lexicon,
estimates the level from surface features, and writes a reply from the scenario's tutor lines.
It is deliberately simple and it was written by the same person who wrote the eval set, so its
eval numbers are optimistic by construction: treat them as a floor for the plumbing and a
baseline a real model must beat, never as evidence about learners. Real Hebrew needs a model
(or a morphological analyzer) for everything outside these patterns.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from .content import ARB, HEB, Content, render, share
from .models import Correction

H = r"[א-ת]"
NB = r"(?<![א-ת])"  # not preceded by a Hebrew letter
NA = r"(?![א-ת])"   # not followed by one

EXPLAIN_AR = {
    "definiteness": "في الإضافة تدخل «ה» على الكلمة الثانية، وفي الصفة على الاسم والصفة معًا: {fix}.",
    "negation": "للنفي مع «יש» نستخدم «אין»، وليس «לא יש»: {fix}.",
    "gender_agreement": "الصفة أو الفعل يوافق الاسم في الجنس (مذكر أو مؤنث): {fix}.",
    "number_gender": "العدد يتغيّر حسب جنس الاسم، مثل «שלושה ימים» و«שלוש שעות»: {fix}.",
    "verb_agreement": "الفعل يوافق الفاعل في العدد والجنس: {fix}.",
    "preposition": "هذا الفعل يأتي في العبرية مع حرف جر مختلف عن العربية: {fix}.",
    "word_order": "في العبرية تأتي «שלי» بعد الاسم: {fix}.",
    "spelling": "انتبه للحرف: الكتابة الصحيحة {fix}.",
    "pronunciation": "في العبرية صوت P (פּ) غير موجود في العربية، فانتبه أن تقول: {fix}.",
    "vocabulary": "الكلمة المناسبة هنا: {fix}.",
    "other": "الصيغة الصحيحة: {fix}.",
}

ADJ = {"טוב": "טובה", "גדול": "גדולה", "קטן": "קטנה", "חדש": "חדשה", "ישן": "ישנה", "זול": "זולה", "יקר": "יקרה",
       "טעים": "טעימה", "חם": "חמה", "קר": "קרה", "חריף": "חריפה", "קרוב": "קרובה", "רחוק": "רחוקה",
       "מרכזי": "מרכזית", "מעניין": "מעניינת", "אחראי": "אחראית", "מתאים": "מתאימה", "אבוד": "אבודה",
       "ראשון": "ראשונה", "ארוך": "ארוכה", "עייף": "עייפה", "שמח": "שמחה", "עצוב": "עצובה", "נקי": "נקייה"}
ADJ_F = {f: m for m, f in ADJ.items()}
SELF_VERBS = {"הולך": "הולכת", "מרגיש": "מרגישה", "צריך": "צריכה", "יכול": "יכולה", "גר": "גרה", "לומד": "לומדת",
              "עובד": "עובדת", "מחפש": "מחפשת", "אוהב": "אוהבת", "יודע": "יודעת", "מבין": "מבינה", "נוסע": "נוסעת",
              "מדבר": "מדברת", "עוזר": "עוזרת", "שואל": "שואלת", "חושב": "חושבת", "בא": "באה", "מתעניין": "מתעניינת"}
SELF_F = {f: m for m, f in SELF_VERBS.items()}
# ms, fs, mpl, fpl
VERBS = [("רוצה", "רוצה", "רוצים", "רוצות"), ("הולך", "הולכת", "הולכים", "הולכות"), ("יודע", "יודעת", "יודעים", "יודעות"),
         ("עובד", "עובדת", "עובדים", "עובדות"), ("צריך", "צריכה", "צריכים", "צריכות"), ("יכול", "יכולה", "יכולים", "יכולות"),
         ("אוהב", "אוהבת", "אוהבים", "אוהבות"), ("לומד", "לומדת", "לומדים", "לומדות"), ("גר", "גרה", "גרים", "גרות"),
         ("מחפש", "מחפשת", "מחפשים", "מחפשות"), ("נוסע", "נוסעת", "נוסעים", "נוסעות"), ("מדבר", "מדברת", "מדברים", "מדברות"),
         ("משחק", "משחקת", "משחקים", "משחקות"), ("מבין", "מבינה", "מבינים", "מבינות"), ("מרגיש", "מרגישה", "מרגישים", "מרגישות"),
         ("מחכה", "מחכה", "מחכים", "מחכות"), ("בא", "באה", "באים", "באות"), ("עוזר", "עוזרת", "עוזרים", "עוזרות")]
VERB_FORM = {f: (row, i) for row in VERBS for i, f in enumerate(row)}
PRONOUNS = {"הוא": 0, "היא": 1, "אנחנו": 2, "הם": 2, "הן": 3}
NUM_M2F = {"שני": "שתי", "שלושה": "שלוש", "ארבעה": "ארבע", "חמישה": "חמש", "שישה": "שש", "שבעה": "שבע"}
NUM_F2M = {f: m for m, f in NUM_M2F.items()}
PLURAL_GENDER = {"ימים": "m", "שעות": "f", "דקות": "f", "לחמים": "m", "שקלים": "m", "ילדים": "m", "כרטיסים": "m",
                 "שנים": "f", "ספרים": "m", "תרופות": "f", "חבילות": "f", "ביצים": "f", "אחים": "m", "פעמים": "f",
                 "מכתבים": "m", "עגבניות": "f", "שבועות": "m", "חודשים": "m", "כדורים": "m", "קווים": "m"}
COMPOUNDS = [("בית", "ספר"), ("כרטיס", "אוטובוס"), ("קופת", "חולים"), ("בית", "מרקחת"), ("תחנת", "אוטובוס"),
             ("חדר", "מורים"), ("מספר", "טלפון"), ("בדיקת", "דם"), ("אישור", "מחלה"), ("מערכת", "שעות")]
ACC_TO_DAT = {"אותי": "לי", "אותך": "לך", "אותו": "לו", "אותה": "לה", "אותנו": "לנו", "אותם": "להם", "אותן": "להן"}
DAT_TO_ACC = {v: k for k, v in ACC_TO_DAT.items()}
NOT_NOUN_AFTER_WAIT = {"הרבה", "היום", "הנה", "הזה", "הזאת", "המון"}
SWAPS_TEXT = [("ח", "ה"), ("ה", "ח"), ("ע", "א"), ("א", "ע"), ("ט", "ת"), ("ת", "ט"), ("כ", "ח"), ("ח", "כ"),
              ("ק", "כ"), ("כ", "ק"), ("ך", "ק"), ("ב", "פ"), ("פ", "ב"), ("ס", "ש"), ("ש", "ס")]
SWAPS_VOICE = [("ב", "פ")]  # /p/ said as /b/: the only spelling-level change we trust from a recognizer
PREFIXES = "הבלמשוכ"
STUCK = re.compile(r"לא מבינ|לא הבנתי|ما فهمت|مش فاهم|لا أفهم|ما بعرف|^\s*\?+\s*$|^\s*מה\?\s*$")


def _fix(original: str, corrected: str, etype: str) -> Correction:
    return Correction(original=original, corrected=corrected, error_type=etype,
                      explanation_ar=EXPLAIN_AR[etype].format(fix=corrected))


def _strip_def(w: str) -> tuple[str, str]:
    return ("ה", w[1:]) if w.startswith("ה") and len(w) > 2 else ("", w)


class RuleDetector:
    def __init__(self, content: Content):
        self.lex = content.lexicon() | set(PLURAL_GENDER) | set(ADJ) | set(ADJ_F) | {f for r in VERBS for f in r}
        g = content.noun_genders()
        g.update({"עיר": "f", "חברה": "f", "תחנה": "f", "חבילה": "f", "מנה": "f", "בטן": "f", "לחם": "m"})
        self.genders = g

    # -------------------------------------------------------------- lexicon helpers
    def known(self, w: str) -> bool:
        w = w.strip("'\".,?!")
        if w in self.lex:
            return True
        if len(w) > 2 and w[0] in PREFIXES and w[1:] in self.lex:
            return True
        return len(w) > 3 and w[0] in PREFIXES and w[1] in PREFIXES and w[2:] in self.lex

    def gender_of(self, w: str) -> Optional[str]:
        _, base = _strip_def(w)
        return self.genders.get(base) or self.genders.get(w)

    # -------------------------------------------------------------- the rules, in priority order
    def detect(self, text: str, *, addressing: str = "m", mode: str = "text") -> Optional[Correction]:
        for rule in (self._negation, self._definiteness, self._prepositions, self._word_order, self._numbers,
                     self._verb_agreement, self._gender, self._spelling):
            c = rule(text, addressing=addressing, mode=mode)
            if c:
                return c
        return None

    def _negation(self, text, **_):
        for pat, fix in ((r"לא יש לי", "אין לי"), (r"יש לי לא", "אין לי"), (r"לא יש", "אין")):
            m = re.search(NB + pat + NA, text)
            if m:
                return _fix(m.group(0), fix, "negation")
        return None

    def _definiteness(self, text, **_):
        for a, b in COMPOUNDS:
            m = re.search(NB + "ה" + a + r"\s+" + b + NA, text)
            if m:
                return _fix(m.group(0), f"{a} ה{b}", "definiteness")
        words = re.findall(H + r"+", text)
        for w1, w2, w3 in zip(words, words[1:], words[2:]):
            art, base = _strip_def(w1)
            if art and base in self.genders and (w2 in ADJ or w2 in ADJ_F) and (w3 in ADJ or w3 in ADJ_F or w3 in VERB_FORM):
                return _fix(f"{w1} {w2}", f"{w1} ה{w2}", "definiteness")
        return None

    def _prepositions(self, text, **_):
        m = re.search(NB + r"(לעזור|עוזר|עוזרת|עוזרים|תעזור|תעזרי|יעזור|עזרתי)\s+(" + "|".join(ACC_TO_DAT) + ")" + NA, text)
        if m:
            return _fix(m.group(0), f"{m.group(1)} {ACC_TO_DAT[m.group(2)]}", "preposition")
        m = re.search(NB + r"(מחכה|מחכים|מחכות|לחכות|חיכיתי|נחכה|אחכה)\s+(?:את\s+)?ה(" + H + r"+)", text)
        if m and "ה" + m.group(2) not in NOT_NOUN_AFTER_WAIT:
            return _fix(m.group(0), f"{m.group(1)} ל{m.group(2)}", "preposition")
        m = re.search(NB + r"(מתעניין|מתעניינת|מתעניינים|להתעניין|תלוי|תלויה|תלויים)\s+על\s+(ה)?(" + H + r"+)", text)
        if m:
            return _fix(m.group(0), f"{m.group(1)} ב{m.group(3)}", "preposition")
        m = re.search(NB + r"(אשאל|שואל|שואלת|לשאול|שאלתי|תשאל|תשאלי)\s+ל(" + H + r"*)", text)
        if m:
            rest = m.group(2)
            if "ל" + rest in DAT_TO_ACC:
                return _fix(m.group(0), f"{m.group(1)} {DAT_TO_ACC['ל' + rest]}", "preposition")
            if rest:
                return _fix(m.group(0), f"{m.group(1)} את ה{rest}", "preposition")
        m = re.search(NB + r"(נוסע|נוסעת|נוסעים|לנסוע|נסעתי)\s+על\s+ה(" + H + r"+)", text)
        if m:
            return _fix(m.group(0), f"{m.group(1)} ב{m.group(2)}", "preposition")
        return None

    def _word_order(self, text, **_):
        m = re.search(r"(?:^|[.!?,]\s*)((שלי|שלך|שלו|שלה|שלנו)\s+(ה" + H + r"+))", text)
        if m:
            return _fix(m.group(1), f"{m.group(3)} {m.group(2)}", "word_order")
        return None

    def _numbers(self, text, **_):
        words = re.findall(H + r"+", text)
        for num, noun in zip(words, words[1:]):
            g = PLURAL_GENDER.get(noun)
            if not g:
                continue
            if g == "m" and num in NUM_F2M:
                return _fix(f"{num} {noun}", f"{NUM_F2M[num]} {noun}", "number_gender")
            if g == "f" and num in NUM_M2F:
                return _fix(f"{num} {noun}", f"{NUM_M2F[num]} {noun}", "number_gender")
        return None

    def _verb_agreement(self, text, **_):
        words = re.findall(H + r"+", text)
        for i, w in enumerate(words[:-1]):
            nxt = words[i + 1]
            if w in PRONOUNS and nxt in VERB_FORM:
                row, idx = VERB_FORM[nxt]
                want = PRONOUNS[w]
                if row[idx] != row[want] and idx != want:
                    return _fix(f"{w} {nxt}", f"{w} {row[want]}", "verb_agreement")
            if w.startswith("ה") and len(w) > 4 and (w.endswith("ים") or w.endswith("ות")) and w not in VERB_FORM:
                j = i + 1 + (1 if nxt in ("שלי", "שלך", "שלו", "שלה", "שלנו", "שלהם") else 0)
                if j < len(words) and words[j] in VERB_FORM:
                    row, idx = VERB_FORM[words[j]]
                    want = 2 if w.endswith("ים") else 3
                    if idx in (0, 1) and row[idx] != row[want]:
                        return _fix(words[j], row[want], "verb_agreement")
        return None

    def _gender(self, text, *, addressing="m", **_):
        words = re.findall(H + r"+", text)
        for i, w in enumerate(words[:-1]):
            if w == "אני":
                for nxt in words[i + 1:i + 3]:
                    if addressing == "m" and nxt in SELF_F:
                        return _fix(nxt, SELF_F[nxt], "gender_agreement")
                    if addressing == "f" and nxt in SELF_VERBS:
                        return _fix(nxt, SELF_VERBS[nxt], "gender_agreement")
            g = self.gender_of(w)
            if not g:
                continue
            j = i + 1
            if j < len(words) and words[j] in ("הזה", "הזאת", "הזו"):
                j += 1
            if j >= len(words):
                continue
            art, adj = _strip_def(words[j])
            if adj not in ADJ and adj not in ADJ_F:
                art, adj = "", words[j]
            if g == "f" and adj in ADJ and ADJ[adj] != adj:
                fixed = art + ADJ[adj]
                return _fix(f"{w} {words[j]}" if j == i + 1 else words[j], f"{w} {fixed}" if j == i + 1 else fixed,
                            "gender_agreement")
            if g == "m" and adj in ADJ_F:
                fixed = art + ADJ_F[adj]
                return _fix(f"{w} {words[j]}" if j == i + 1 else words[j], f"{w} {fixed}" if j == i + 1 else fixed,
                            "gender_agreement")
        return None

    def _spelling(self, text, *, mode="text", **_):
        swaps = SWAPS_VOICE if mode == "voice" else SWAPS_TEXT
        for w in re.findall(H + r"+", text):
            if len(w) < 3 or self.known(w):
                continue
            for i, ch in enumerate(w):
                for a, b in swaps:
                    if ch == a:
                        cand = w[:i] + b + w[i + 1:]
                        if self.known(cand):
                            return _fix(w, cand, "pronunciation" if mode == "voice" else "spelling")
        return None


# ---------------------------------------------------------------- level and stuck
B1_CONNECTORS = re.compile(NB + r"(כי|אבל|אם|כש\S+|ש(?:אני|הוא|היא|אנחנו)|למרות|בגלל|לכן)" + NA)
PAST_FUTURE = re.compile(NB + r"(אתמול|מחר|הייתי|היה|הלכתי|עבדתי|שיחקנו|אני אהיה|אני אלך|נלך|ב?שבוע הבא)" + NA)


def level_signal(text: str) -> str:
    if share(HEB, text) < 0.5:
        return "unclear"
    n = len(re.findall(H + r"+", text))
    if n < 2:
        return "unclear"
    if n >= 7 and B1_CONNECTORS.search(text):
        return "B1"
    if n >= 5 or PAST_FUTURE.search(text):
        return "A2"
    return "A1"


def is_stuck(text: str) -> bool:
    return bool(STUCK.search(text)) or (share(ARB, text) > 0.5)


@lru_cache(maxsize=4)
def detector_for(content_id: int, content: Content) -> RuleDetector:
    return RuleDetector(content)


def praise(turn: int) -> str:
    return ["מצוין!", "יפה מאוד!", "כל הכבוד!"][turn % 3]


def rule_reply(content: Content, scenario_id: str, level: str, addressing: str, turn: int,
               correction: Optional[Correction], stuck: bool, flag: str, example: Optional[str]) -> str:
    sc = content.scenarios[scenario_id]
    lines = sc.tutor_lines.get(level) or next(iter(sc.tutor_lines.values()))
    q = render(lines[turn % len(lines)], addressing)
    if flag == "injection":
        return f"אני כאן כדי לתרגל איתך עברית. {q}"
    if flag == "off_topic":
        return render("זה נשמע מעניין, אבל בוא{|י} נחזור לתרגול. ", addressing) + q
    if stuck:
        return f"אין בעיה. אפשר להגיד: «{example.rstrip('.!?')}». {q}" if example else f"אין בעיה, ננסה שוב. {q}"
    if correction:
        return f"כמעט! אומרים: «{correction.corrected}». {q}"
    return f"{praise(turn)} {q}"
