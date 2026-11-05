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
    """Return (a CLEANED deep copy of a, findings). Never modify `a` itself.
    Hebrew is compared after normalize_hebrew() on both sides. Each problem gives a Finding with
    this `code` and `severity` (tests check those two; `detail` is free text) and this fix:
      correction_not_grounded (block)  original empty or not inside student_text -> correction None
      correction_noop         (warn)   original == corrected                     -> correction None
      spelling_in_voice       (info)   mode "voice" and error_type "spelling"    -> correction None
          (only the first of these three that applies is reported)
      explanation_not_arabic  (warn)   surviving correction, explanation mostly not Arabic
                                       (arabic_share < 0.5) -> EXPLAIN_AR text for its error_type
      explanation_too_long    (warn)   explanation over MAX_EXPLANATION -> cut()
      reply_not_hebrew        (block)  share(HEB, reply_he) < 0.6 -> render(FALLBACK_REPLY[level], "m")
      reply_too_long          (warn)   more than LEVEL_LIMITS[level]["sentences"] + 1 sentences -> trimmed
      help_not_arabic         (warn)   help_ar set and arabic_share < 0.5 -> None
      help_too_long           (warn)   help_ar over MAX_HELP -> cut()
      vocab_dropped           (info)   one per dropped item: at most 3 kept, in order; drop items with
                                       share(HEB, he) < 0.8, share(ARB, ar) < 0.5, or a repeated `he`
      safety_downgrade        (block)  the model's safety_flag is less severe (SEVERITY) than a
                                       non-"none" input_flag -> safety_flag = input_flag

    Stuck? HINTS.md -> validate_assessment
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement validate_assessment")


# ------------------------------------------------------------------ M5: learner model
def sm2_update(card: Card, quality: int, today: date) -> Card:
    """SM-2 (SuperMemo 2) after one review. Return a NEW Card, never modify `card`.

    quality: 0..5, anything else -> ValueError.
    - ef follows the standard SM-2 easiness update, never below 1.3, rounded to 4 decimals.
    - quality < 3 (failed): reps 0, interval 1, lapses + 1.
    - quality >= 3: reps + 1; interval 1 for the first success, 6 for the second, then the old
      interval times the new ef, rounded UP (guard against float noise: 2.5 * 6 must give 15).
    - due = (today + interval days).isoformat().
    Example: a new card answered 4, 4, 4 -> intervals 1, 6, 15; ef stays 2.5.

    Stuck? HINTS.md -> sm2_update
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement sm2_update")


def update_level(score: float, level: str, signal: Optional[str]) -> tuple[float, str]:
    """Update the CEFR estimate after one level signal. Return (new score, displayed level).

    score is in [1.0, 3.99]: A1 = [1, 2), A2 = [2, 3), B1 = [3, 4).
    - signal not in BAND_MID ("unclear", None): (score, level) unchanged.
    - otherwise the score moves a fraction ALPHA of the way toward BAND_MID[signal]; clamped to
      [1.0, 3.99], rounded to 4 decimals.
    - hysteresis: the displayed level changes only when the new score leaves the level's band by
      more than MARGIN (up or down); then it becomes level_of(score). Otherwise it stays.
    Example: (1.5, "A1", "B1") -> (1.8, "A1"); many B1 signals later the score passes 2.15 -> "A2".

    Stuck? HINTS.md -> update_level
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement update_level")


# ------------------------------------------------------------------ M6: redaction
def redact_for_log(text: str) -> tuple[str, list[str]]:
    """Return (redacted text, sorted list of the kinds found). Applied in THIS order:
      url        https?://... or www....                                   -> "[קישור]"
      email      name@domain.tld, ASCII (a Hebrew prefix like "ל-" before it stays) -> "[מייל]"
      phone      Israeli numbers: 050-1234567, 0501234567, 08-6234567, +972-50-1234567 -> "[טלפון]"
      id_number  exactly 9 digits that pass is_valid_israeli_id (other 9-digit numbers stay) -> "[ת״ז]"
      address    רחוב / ברחוב / רח' / שדרות / شارع + one or two words + a number -> "[כתובת]"
      full_name  after קוראים לי / שמי / השם שלי / اسمي / انا اسمي: a first name AND a family name
                 (which may start with "אבו " / "أبو " / "بو "). The intro stays, the two names become
                 one "[שם]": "קוראים לי מרים אבו סעיד" -> "קוראים לי [שם]". A single word is a first
                 name or nickname and stays: "קוראים לי סאלם ואני..." is unchanged (ואני, אני, בן,
                 בת, גר, גרה, وانا, عمري are never a family name).
    Example: "הטלפון שלי 050-7654321" -> ("הטלפון שלי [טלפון]", ["phone"])

    Stuck? HINTS.md -> redact_for_log
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement redact_for_log")


# ------------------------------------------------------------------ M7: speaking feedback
def word_feedback(expected: str, heard: str) -> SpeakingFeedback:
    """Compare the phrase the student was asked to say with what the recognizer heard.

    Words are compared after normalize_hebrew(text, finals=False) (final letters are kept: the
    words are shown to the student). Return SpeakingFeedback(words, extra), one WordResult per
    expected word, in order (score and missed are computed for you):
      said right    WordResult(r, "ok", h, 0.0)
      said wrong    WordResult(r, status, h, c, hint), c = round(cer(r, h).rate, 3);
                    status "homophone" when homophone_key says the difference is only spelling
                    (ט/ת, כ/ח, א/ע, ס/ש, ב/ו), else "close" if c <= 0.34, else "wrong";
                    hint = sound_hint(r, h)
      not said      WordResult(r, "missing", "", 1.0)
      heard words that match no expected word go to `extra`.
    Example: expected "כמה פעמים ביום", heard "כמה בעמים ביום" -> ok, close (hint p_b), ok.

    Stuck? HINTS.md -> word_feedback
    """
    # TODO(M7)
    raise NotImplementedError("M7: implement word_feedback")
