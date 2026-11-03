"""Your code for final project F2 (the spoken-Hebrew tutor). Four milestones are coding TODOs:

    M4  validate_assessment          code checks the model's structured output
    M5  sm2_update, update_level     the learner model: spaced repetition and a CEFR estimate
    M6  redact_for_log               PII redaction for minors, before the model and the store
    M7  word_feedback                speaking feedback: intelligibility via ASR, word by word

Each is checked by tests in ./tests (python -m pytest -q projects/f2-hebrew-tutor/tests).
Every command of the project (`python -m hebtutor ...`) and the API use YOUR function once it
stops raising NotImplementedError, and the reference until then (it says so once per run).
`--reference` forces the references. They live in hebtutor/ (validate.py, learner.py,
safety.py, speaking.py): try not to read them before your tests pass.

The data you work with (hebtutor/models.py, hebtutor/learner.py, hebtutor/speaking.py):
    Assessment   reply_he, correction (Correction | None), help_ar, new_vocabulary [VocabItem],
                 level_signal ("A1"|"A2"|"B1"|"unclear"), safety_flag
    Correction   original, corrected, explanation_ar, error_type
    VocabItem    he, ar, transliteration
    Finding      code, detail, severity ("info" | "warn" | "block")
    Card         vocab_id, he, ar, ef=2.5, reps=0, interval=0, due="", lapses=0
    WordResult   word, status, heard, cer, hint      SpeakingFeedback(words, extra)
"""

from __future__ import annotations

import math  # noqa: F401
import re  # noqa: F401
from dataclasses import replace  # noqa: F401
from datetime import date, timedelta  # noqa: F401
from typing import Optional  # noqa: F401

from guardkit.redact import is_valid_israeli_id  # noqa: F401
from voicekit.text import align, cer, normalize_hebrew  # noqa: F401

from hebtutor.content import ARB, HEB, arabic_share, render, share  # noqa: F401
from hebtutor.learner import ALPHA, BAND_MID, MARGIN, Card, level_of  # noqa: F401
from hebtutor.models import LEVELS, Assessment, Finding  # noqa: F401
from hebtutor.prompts import LEVEL_LIMITS  # noqa: F401
from hebtutor.rules import EXPLAIN_AR  # noqa: F401
from hebtutor.speaking import SpeakingFeedback, WordResult, homophone_key, sound_hint  # noqa: F401
from hebtutor.validate import FALLBACK_REPLY, MAX_EXPLANATION, MAX_HELP, SEVERITY, cut, sentences  # noqa: F401


# ------------------------------------------------------------------ M4: output validation
def validate_assessment(a: Assessment, student_text: str, *, level: str = "A1", mode: str = "text",
                        input_flag: str = "none") -> tuple[Assessment, list[Finding]]:
    """Return (a CLEANED deep copy of a, findings). Never modify `a` itself (a.model_copy(deep=True)).
    Compare Hebrew with normalize_hebrew() on both sides (niqqud, punctuation, final letters).

    Correction checks, in this order (the first that applies decides; the rest are skipped):
      correction_not_grounded (block)  normalized original is empty or not a substring of the
                                       normalized student_text            -> correction = None
      correction_noop         (warn)   normalized original == normalized corrected -> None
      spelling_in_voice       (info)   mode == "voice" and error_type == "spelling" -> None
                                       (the recognizer spelled it, not the student)
    If the correction survived:
      explanation_not_arabic  (warn)   arabic_share(explanation_ar) < 0.5 (Hebrew letters ignored) -> replace it with
                                       EXPLAIN_AR[error_type] (or EXPLAIN_AR["other"]).format(fix=corrected)
      explanation_too_long    (warn)   len > MAX_EXPLANATION (160) -> cut(text, MAX_EXPLANATION)
    Reply:
      reply_not_hebrew        (block)  share(HEB, reply_he) < 0.6 -> reply_he =
                                       render(FALLBACK_REPLY[level], "m")
      reply_too_long          (warn)   otherwise, if sentences(reply_he) has more than
                                       LEVEL_LIMITS[level]["sentences"] + 1 sentences -> keep that
                                       many, joined with " "
    Help (only when help_ar is not None):
      help_not_arabic         (warn)   arabic_share(help_ar) < 0.5 -> help_ar = None
      help_too_long           (warn)   else len > MAX_HELP (220) -> cut(help_ar, MAX_HELP)
    Vocabulary: keep at most 3 items, in order; drop (finding vocab_dropped, info, one per item)
      any item with share(HEB, he) < 0.8, share(ARB, ar) < 0.5, a normalized `he` already kept,
      or when 3 are already kept.
    Safety:
      safety_downgrade        (block)  input_flag != "none" and the model's flag is LESS severe
                                       (SEVERITY.index(a.safety_flag) > SEVERITY.index(input_flag))
                                       -> safety_flag = input_flag. The model may raise a flag,
                                       never lower the input screen's.
    `detail` is free text; tests check `code` and `severity`.
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement validate_assessment")


# ------------------------------------------------------------------ M5: learner model
def sm2_update(card: Card, quality: int, today: date) -> Card:
    """SM-2 (SuperMemo 2). Return a NEW Card (dataclasses.replace), never modify `card`.
    quality 0..5, else ValueError.
      ef' = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))   rounded to 4 decimals
      q < 3 (failed):  reps = 0, interval = 1, lapses + 1
      q >= 3:          reps + 1; interval = 1 if the new reps == 1, 6 if == 2,
                       else math.ceil(old interval * ef') (rounded UP, as in
                       the original SM-2; compute math.ceil(round(interval * ef, 6)) to avoid float noise)
      due = (today + interval days).isoformat()
    Example: a new card answered 4, 4, 4 -> intervals 1, 6, 15; ef stays 2.5.
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement sm2_update")


def update_level(score: float, level: str, signal: Optional[str]) -> tuple[float, str]:
    """The CEFR estimate. score is in [1.0, 3.99]: A1 = [1, 2), A2 = [2, 3), B1 = [3, 4).
    - signal not in BAND_MID ("unclear", None): return (score, level) unchanged.
    - s = score + ALPHA * (BAND_MID[signal] - score), clamped to [1.0, 3.99], rounded to 4 decimals.
    - hysteresis: the displayed level i (index in LEVELS) has the band [i+1, i+2). Change it only
      when s >= i+2 + MARGIN (go up) or s < i+1 - MARGIN (go down); the new level is level_of(s).
      Otherwise keep `level`.
    Example: (1.5, "A1", "B1") -> (1.8, "A1"); many B1 signals later the score passes 2.15 -> "A2".
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement update_level")


# ------------------------------------------------------------------ M6: redaction
def redact_for_log(text: str) -> tuple[str, list[str]]:
    """Return (redacted text, sorted list of the kinds found). Applied, in THIS order:
      url        https?://... or www....                         -> "[קישור]"
      email      name@domain.tld, ASCII letters/digits (a Hebrew prefix like "ל-" before it stays)
                                                                  -> "[מייל]"
      phone      Israeli numbers: 050-1234567, 0501234567, 08-6234567, +972-50-1234567
                 (0 or +972, then 5X/7X or one of 2,3,4,8,9, then 3+4 digits, optional - or space)
                                                                  -> "[טלפון]"
      id_number  exactly 9 digits that pass is_valid_israeli_id   -> "[ת״ז]" (other 9-digit numbers stay)
      address    רחוב / ברחוב / רח' / שדרות / شارع + one or two words + a number
                                                                  -> "[כתובת]"
      full_name  after קוראים לי / שמי / השם שלי / اسمي / انا اسمي: TWO words (a first name and a
                 family name, which may start with "אבו " / "أبو " / "بو "). Keep the intro
                 phrase, replace both words with "[שם]": "קוראים לי מרים אבו סעיד" -> "קוראים לי [שם]".
                 One word is a first name or nickname and stays: "קוראים לי סאלם ואני..." is
                 unchanged (the second word "ואני" is not a name: words like ואני, אני, בן, בת,
                 גר, גרה, وانا, عمري are never a family name).
    Example: "הטלפון שלי 050-7654321" -> ("הטלפון שלי [טלפון]", ["phone"])
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement redact_for_log")


# ------------------------------------------------------------------ M7: speaking feedback
def word_feedback(expected: str, heard: str) -> SpeakingFeedback:
    """Compare the phrase the student was asked to say with what the recognizer heard.
    Normalize both with normalize_hebrew(text, finals=False) (keep final letters: the words are
    shown to the student), split into words, and walk align(ref, hyp)
    (voicekit: a list of (op, ref_word, hyp_word), op in ok | sub | del | ins):
      ok   -> WordResult(r, "ok", h, 0.0)
      sub  -> c = round(cer(r, h).rate, 3);
              status "homophone" if homophone_key(r) == homophone_key(h) (ט/ת, כ/ח, א/ע, ס/ש, ב/ו:
              the recognizer's spelling, not the student's), else "close" if c <= 0.34, else "wrong";
              hint = sound_hint(r, h) ("p_b" for פ heard as ב, "v_f" for ו/ב heard as פ, else None)
      del  -> WordResult(r, "missing", "", 1.0)
      ins  -> the heard word goes to SpeakingFeedback.extra (not to words)
    SpeakingFeedback.score and .missed are computed from the words for you.
    Example: expected "כמה פעמים ביום", heard "כמה בעמים ביום" -> ok, close (hint p_b), ok.
    """
    # TODO(M7)
    raise NotImplementedError("M7: implement word_feedback")
