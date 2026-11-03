"""Reading-aloud feedback from a transcript (the F2 starting point), with its limits stated.

What this CAN do: the student reads a known sentence; we align the reference words with
what the recognizer heard and report, per word: ok, heard as something else, missing, or
"unsure" (the recognizer's word confidence was low). That catches skipped words, wrong
words, and the clearest mispronunciations (פרק heard as ברק).

What it CANNOT do, and why:
- A recognizer is trained to output the most likely WORDS, with a strong language model
  behind it. A slightly wrong vowel or a /p/ that is almost a /b/ is usually "corrected" to
  the intended word, so the transcript looks perfect. Good ASR hides pronunciation errors.
- Word confidence measures the recognizer's certainty, which also drops with noise, a
  rare word, or a name. Low confidence is a hint to listen, not a grade.
- Real pronunciation assessment compares PHONEMES: expected phonemes from a G2P (for
  Hebrew: Phonikud, or Piper's Nakdimon-based phonemizer) against phonemes recognized from
  the audio (a phoneme recognizer, e.g. a multilingual wav2vec2 phoneme model), aligned and
  scored per phoneme (goodness of pronunciation). That is a research-grade build.
- Azure AI Speech has a dedicated Pronunciation Assessment service (accuracy, fluency,
  completeness, prosody, per word and phoneme). Its docs list 33 supported locales; in the
  versions we could read (November 2026) Hebrew was not among them, and phoneme-level
  output is documented only for en-US (and zh-CN with SAPI). Verify on the language-support
  page before planning around it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .text import align, normalize_hebrew
from .types import Transcript


@dataclass
class WordFeedback:
    word: str  # the reference word (normalized)
    status: str  # "ok" | "heard_as" | "missing" | "unsure"
    heard: str = ""
    confidence: Optional[float] = None


@dataclass
class ReadingFeedback:
    words: list[WordFeedback] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)  # words heard that are not in the reference

    @property
    def score(self) -> float:
        """Share of reference words read as expected (ok or unsure)."""
        if not self.words:
            return 0.0
        return sum(w.status in ("ok", "unsure") for w in self.words) / len(self.words)

    def lines(self) -> list[str]:
        out = []
        for w in self.words:
            conf = f" (confidence {w.confidence:.2f})" if w.confidence is not None else ""
            if w.status == "ok":
                out.append(f"ok       {w.word}{conf}")
            elif w.status == "unsure":
                out.append(f"unsure   {w.word}{conf}: listen again")
            elif w.status == "heard_as":
                out.append(f"heard    {w.word} -> {w.heard}{conf}")
            else:
                out.append(f"missing  {w.word}")
        out += [f"extra    {x}" for x in self.extra]
        return out


def reading_feedback(reference: str, transcript: Transcript, *, unsure_below: float = 0.6) -> ReadingFeedback:
    ref = normalize_hebrew(reference).split()
    hyp_words = [w for w in transcript.words if normalize_hebrew(w.text)]
    hyp = [normalize_hebrew(w.text) for w in hyp_words] if hyp_words else normalize_hebrew(transcript.text).split()
    confs = [w.confidence for w in hyp_words] if hyp_words else [None] * len(hyp)
    fb = ReadingFeedback()
    j = 0  # index into hyp, to fetch the confidence of the matched word
    for op, r, h in align(ref, hyp):
        conf = confs[j] if op != "del" and j < len(confs) else None
        if op == "ok":
            status = "unsure" if conf is not None and conf < unsure_below else "ok"
            fb.words.append(WordFeedback(r, status, h, conf))
        elif op == "sub":
            fb.words.append(WordFeedback(r, "heard_as", h, conf))
        elif op == "del":
            fb.words.append(WordFeedback(r, "missing"))
        else:
            fb.extra.append(h)
        if op != "del":
            j += 1
    return fb
