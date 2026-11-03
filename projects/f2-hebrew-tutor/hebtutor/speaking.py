"""Speaking feedback: intelligibility via ASR, not pronunciation scoring.

The student is asked to say a known phrase. We compare it with what the recognizer heard,
word by word. Reference version of milestone 7 (mine.word_feedback).

What the result means, and what it does not:
- "ok"/"homophone": the recognizer heard the intended word (a homophone spelling such as ט/ת
  is the RECOGNIZER's spelling; it says nothing about the student).
- "close": one or two letters differ (character error rate <= 0.34). Often a real sound
  problem (/p/ said as /b/: פעם heard as בעם), sometimes the recognizer.
- "wrong"/"missing": the recognizer heard another word, or nothing.
A strong recognizer "corrects" small accent errors to the intended word (lesson 21), so a
perfect score does not mean perfect pronunciation. Real phoneme-level assessment needs a
phoneme recognizer and a Hebrew G2P; Azure's Pronunciation Assessment did not list Hebrew
when we checked (November 2026). The API says this in every response ("method").
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from voicekit.text import align, cer, normalize_hebrew

HOMOPHONE_CLASS = {"ט": "ת", "ת": "ת", "כ": "ח", "ח": "ח", "ק": "ק", "א": "א", "ע": "א", "ס": "ס", "ש": "ס",
                   "ב": "ב", "ו": "ב"}
METHOD = ("intelligibility via speech recognition: which expected words the recognizer heard. "
          "It is not a phonetic pronunciation score.")


@dataclass
class WordResult:
    word: str
    status: str  # ok | homophone | close | wrong | missing
    heard: str = ""
    cer: float = 0.0
    hint: Optional[str] = None  # "p_b" (/p/ said as /b/) | "v_f" (/v/ said as /f/) | None


@dataclass
class SpeakingFeedback:
    words: list[WordResult] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    method: str = METHOD

    @property
    def score(self) -> float:
        if not self.words:
            return 0.0
        pts = {"ok": 1.0, "homophone": 1.0, "close": 0.5}
        return round(sum(pts.get(w.status, 0.0) for w in self.words) / len(self.words), 3)

    @property
    def missed(self) -> list[str]:
        return [w.word for w in self.words if w.status in ("wrong", "missing")]

    def to_dict(self) -> dict:
        return {"words": [asdict(w) for w in self.words], "extra": self.extra, "score": self.score,
                "missed": self.missed, "method": self.method}


def homophone_key(w: str) -> str:
    return "".join(HOMOPHONE_CLASS.get(c, c) for c in w)


def sound_hint(ref: str, hyp: str) -> Optional[str]:
    if len(ref) != len(hyp):
        return None
    diffs = [(a, b) for a, b in zip(ref, hyp) if a != b]
    if len(diffs) != 1:
        return None
    a, b = diffs[0]
    if a == "פ" and b == "ב":
        return "p_b"
    if a in "וב" and b == "פ":
        return "v_f"
    return None


def word_feedback(expected: str, heard: str) -> SpeakingFeedback:
    ref, hyp = normalize_hebrew(expected, finals=False).split(), normalize_hebrew(heard, finals=False).split()
    fb = SpeakingFeedback()
    for op, r, h in align(ref, hyp):
        if op == "ok":
            fb.words.append(WordResult(r, "ok", h, 0.0))
        elif op == "sub":
            c = round(cer(r, h).rate, 3)
            if homophone_key(r) == homophone_key(h):
                status = "homophone"
            elif c <= 0.34:
                status = "close"
            else:
                status = "wrong"
            fb.words.append(WordResult(r, status, h, c, sound_hint(r, h)))
        elif op == "del":
            fb.words.append(WordResult(r, "missing", "", 1.0))
        else:
            fb.extra.append(h)
    return fb
