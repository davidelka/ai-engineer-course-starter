"""Your code for final project F2 (the spoken-Hebrew tutor): eleven functions.

You build the parts of the tutor that the course taught: the safety screens for minors (before
anything else), retrieval of phrases, the prompt and the streamed reply, the validation of the
model's structured output, the learner model, speaking feedback, and the correction metrics of the
evaluation. The course gives you the rest ready: the API and the demo page, the SQLite store,
speech-to-text and text-to-speech adapters, the offline stand-in model, and the deployment files.

    M2  screen_text, screen_output, redact_for_log   safety for minors: input, output, logs
    M3  retrieve_phrases                              phrases of the scenario, at or below the level
    M4  build_request, partial_json_field             the prompt, and the reply decoded while it streams
    M5  validate_assessment                           code checks the model's structured output
    M6  sm2_update, update_level                      the learner model: spaced repetition and a CEFR estimate
    M8  word_feedback                                 speaking feedback: intelligibility via ASR, word by word
    M9  correction_metrics                            precision and recall of the corrections

After milestone 6 a full tutor turn runs on your code; milestone 7 is the tutor talking.
Each is checked by tests in ./tests (python -m pytest -q projects/f2-hebrew-tutor/tests). Every
command of the project (`python -m hebtutor ...`) and the API use YOUR functions; a command that
needs one you have not written yet stops and names the milestone. The reference implementations
are on the repo's `solutions` branch, for comparing AFTER your tests pass. Stuck? HINTS.md has
three graded hints per function.

The data you work with (hebtutor/models.py, hebtutor/learner.py, hebtutor/speaking.py):
    Assessment   reply_he, correction (Correction | None), help_ar, new_vocabulary [VocabItem],
                 level_signal ("A1"|"A2"|"B1"|"unclear"), safety_flag
    Correction   original, corrected, explanation_ar, error_type
    VocabItem    he, ar, transliteration
    Finding      code, detail, severity ("info" | "warn" | "block")
    Card         vocab_id, he, ar, ef=2.5, reps=0, interval=0, due="", lapses=0
    WordResult   word, status, heard, cer, hint      SpeakingFeedback(words, extra)
    Screen       flag, reasons, score, borderline     (hebtutor/safety.py)
"""

from __future__ import annotations

import math  # noqa: F401
import re  # noqa: F401
from dataclasses import replace  # noqa: F401
from datetime import date, timedelta  # noqa: F401
from typing import Optional  # noqa: F401

from guardkit.redact import is_valid_israeli_id  # noqa: F401
from voicekit.text import align, cer, normalize_hebrew  # noqa: F401

from hebtutor.content import ARB, HEB, Content, arabic_share, levels_up_to, render, share  # noqa: F401
from hebtutor.learner import ALPHA, BAND_MID, MARGIN, Card, level_of  # noqa: F401
from hebtutor.models import LEVELS, Assessment, Finding, SessionState  # noqa: F401
from hebtutor.prompts import LEVEL_LIMITS, STATIC_RULES, session_block, user_turn  # noqa: F401
from hebtutor.rules import EXPLAIN_AR  # noqa: F401
from hebtutor.safety import (DISTRESS, FLAG_ORDER, INJECTION, OFF_TOPIC, OUT_BLOCK, PII, UNSAFE,  # noqa: F401
                             Screen)
from llmkit.types import Block, ChatRequest, Message  # noqa: F401
from hebtutor.speaking import SpeakingFeedback, WordResult, homophone_key, sound_hint  # noqa: F401
from hebtutor.validate import FALLBACK_REPLY, MAX_EXPLANATION, MAX_HELP, SEVERITY, cut, sentences  # noqa: F401


# ------------------------------------------------------------------ M2: the input screen
def screen_text(text: str, *, threshold: float = 2.0) -> Screen:
    """The cheap input screen for a student's message. Returns Screen(flag, reasons, score, borderline).

    The signal lists are in hebtutor/safety.py: DISTRESS, UNSAFE and PII are lists of
    (weight, name, compiled regex). For each of the three categories, the score is the sum of the
    weights of the signals whose regex matches, and reasons are their names, in list order. One
    exception: the "id_number" signal of PII counts only when one of the 9-digit numbers in the text
    passes is_valid_israeli_id (a random 9-digit number is not an ID).
    Two more categories: "injection" = INJECTION.detect(text, kind="user message") (its .score and
    .reasons), and "off_topic" = (2.0, ["off_topic_topic"]) when OFF_TOPIC matches.
    The flag is the FIRST category in FLAG_ORDER (most severe first: distress, unsafe, personal_info,
    injection, off_topic) whose score reaches its threshold: 3.0 for injection, `threshold` for the
    others. Then Screen(category, its reasons, its score). When none does: Screen("none", reasons and
    score of the category with the highest score, borderline=True when that score is above 0) - the
    tutor then asks the LLM classifier for a second opinion. None or "" is a clean "none" screen.

    Stuck? HINTS.md -> screen_text
    """
    # TODO(M2)
    raise NotImplementedError("M2: implement screen_text")


# ------------------------------------------------------------------ M2: the output screen
def screen_output(sentence: str) -> Optional[str]:
    """Check one sentence of the tutor's reply before it is shown or spoken. None = it may be shown.

    In this order, the first that applies wins:
    - OUT_BLOCK matches (a link, an email, asking for an address, a phone number, a family name or a
      photo)                                            -> "asks_for_personal_info_or_link";
    - screen_text(sentence).flag is "unsafe" or "distress" -> "output_unsafe" / "output_distress";
    - the sentence is not empty and neither Hebrew nor Arabic: share(HEB, s) < 0.6 and
      share(ARB, s) < 0.6                               -> "not_hebrew";
    - otherwise None.

    Stuck? HINTS.md -> screen_output
    """
    # TODO(M2)
    raise NotImplementedError("M2: implement screen_output")


# ------------------------------------------------------------------ M2: redaction for logs
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
    # TODO(M2)
    raise NotImplementedError("M2: implement redact_for_log")


# ------------------------------------------------------------------ M3: retrieval
def retrieve_phrases(content: Content, scenario_id: str, level: str, query: str, k: int = 6) -> list[dict]:
    """Phrases and words of this scenario, at or below the student's level, relevant to what they said.

    `content.index` is a ragkit BM25 index of every phrase and approved word; each chunk's meta has
    "scenario", "level", "kind" ("phrase" | "vocab") and "ar". Search it with
    where={"scenario": scenario_id, "level": levels_up_to(level)} (A2 sees A1 and A2) and k; an empty
    or whitespace query searches nothing. Each hit becomes
        {"id": chunk.id, "he": chunk.text, "ar": meta["ar"], "kind": meta["kind"],
         "level": meta["level"], "score": round(hit.score, 3)}.
    When fewer than 3 came back (a short "כן" matches nothing), add the scenario's own phrases,
    content.scenarios[scenario_id].phrases_for(level), in order, skipping a "he" already in the list,
    until there are 3: {"id": None, "he", "ar", "kind": "phrase", "level", "score": 0.0}.

    Stuck? HINTS.md -> retrieve_phrases
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement retrieve_phrases")


# ------------------------------------------------------------------ M4: the prompt
def build_request(content: Content, st: SessionState, text: str, retrieved: list[dict], *, mode: str = "text",
                  max_tokens: int = 700, cache: bool = True, images=None) -> ChatRequest:
    """Build the ChatRequest for one student turn.

    - system: two Blocks, in this order: Block(STATIC_RULES, cache="5m" if cache else None), then
      Block(session_block(scenario, st, mode)), where scenario = content.scenarios[st.scenario_id].
      The static rules are identical for every student and turn, so they are the cached prefix; the
      session block changes per scenario, level and turn, so it comes after the cache breakpoint.
    - messages: the last 8 entries of st.history, each (role, text) with role "student" -> a "user"
      Message and anything else -> an "assistant" Message; then the new turn: user_turn(text, retrieved)
      as a "user" Message, or Message.user_with(*images, body) when images are given.
    - max_tokens as given.

    Stuck? HINTS.md -> build_request
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement build_request")


# ------------------------------------------------------------------ M4: the reply while it streams
def partial_json_field(buffer: str, field_name: str = "reply_he") -> tuple[str, bool]:
    r"""Decode the value of one JSON string field out of a JSON object that is still arriving.

    The model streams its structured answer as JSON text; the student should hear the reply before the
    whole object has arrived. `buffer` is everything received so far. Returns (value so far, complete):
    - the field starts after '"<field_name>"', then a ':', then an opening '"'. Until all three have
      arrived: ("", False);
    - then read characters until the closing '"': complete=True when it has arrived;
    - escapes: \n -> newline, \t -> tab, \r, \b and \f -> nothing, \uXXXX -> that character, and a
      backslash before any other character -> that character (\" -> ", \\ -> \);
    - an escape cut off at the end of the buffer (a lone backslash, or \u with fewer than 4 hex digits)
      is not decoded yet: stop before it, it will be complete in the next call.
    Example: '{"reply_he": "שלום\nעו' -> ("שלום\nעו", False).

    Stuck? HINTS.md -> partial_json_field
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement partial_json_field")


# ------------------------------------------------------------------ M5: output validation
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
    # TODO(M5)
    raise NotImplementedError("M5: implement validate_assessment")


# ------------------------------------------------------------------ M6: learner model
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
    # TODO(M6)
    raise NotImplementedError("M6: implement sm2_update")


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
    # TODO(M6)
    raise NotImplementedError("M6: implement update_level")


# ------------------------------------------------------------------ M8: speaking feedback
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
    # TODO(M8)
    raise NotImplementedError("M8: implement word_feedback")


# ------------------------------------------------------------------ M9: correction metrics
def correction_metrics(rows: list[dict]) -> dict:
    """Count the corrections of the evaluation: did the tutor find the error the label says is there?

    A row: {"pred": None or {"error_type", "corrected", ...}, "gold": {"error_type": None or a type,
    "must_contain": None or a text}}. A row is a hit when the prediction is not None, the gold
    error_type is not None, the two error types are equal, and gold must_contain (or "") is inside the
    predicted "corrected" text (or ""). Returns:
        {"tp": hits, "predicted": rows with a prediction, "gold_errors": rows whose gold has an error,
         "false_positive_on_correct": rows with a prediction but no gold error,
         "per_type": {gold error_type: [hits, total]} sorted by type,
         "hits": [True/False per row, in order]}
    Precision is tp / predicted and recall tp / gold_errors; the evaluation adds confidence intervals.

    Stuck? HINTS.md -> correction_metrics
    """
    # TODO(M9)
    raise NotImplementedError("M9: implement correction_metrics")
