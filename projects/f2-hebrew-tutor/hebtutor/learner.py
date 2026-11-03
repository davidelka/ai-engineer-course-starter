"""The learner model: points, a CEFR estimate, spaced repetition, progress per scenario.

Reference versions of milestone 5 (mine.sm2_update and mine.update_level).

CEFR estimate: a number in [1.0, 4.0), A1 = [1, 2), A2 = [2, 3), B1 = [3, 4). Each turn's
level_signal pulls it toward the middle of that band with an exponential moving average, so
one lucky sentence does not promote a student and one bad day does not demote them. The
displayed level changes only when the number crosses a band edge by a margin (hysteresis):
without it a student near 2.0 would flip between A1 and A2 every turn, and the tutor's
language with them.

Spaced repetition: SM-2 (Wozniak, SuperMemo 2, 1987), the algorithm under Anki's classic
scheduler. A missed word comes back tomorrow, then after 6 days, then after interval x EF
(rounded up, as in the original description). The original text updates EF after every
repetition (step 5) and, for a failed one, restarts the intervals "without changing the
E-Factor" (step 6); like most implementations we read that as "do not reset EF", so a failure
both lowers EF and restarts the intervals.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from typing import Optional

from .models import LEVELS

BAND_MID = {"A1": 1.5, "A2": 2.5, "B1": 3.5}
ALPHA = 0.15
MARGIN = 0.15
POINTS = {"turn_clean": 10, "turn_corrected": 5, "new_word": 2, "review_ok": 3, "review_fail": 1,
          "scenario_done": 50}


@dataclass
class Card:
    vocab_id: str
    he: str
    ar: str
    ef: float = 2.5          # easiness factor, never below 1.3
    reps: int = 0            # successful reviews in a row
    interval: int = 0        # days
    due: str = ""            # ISO date of the next review
    lapses: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def sm2_update(card: Card, quality: int, today: date) -> Card:
    """Reference. quality 0..5 (5 perfect, 3 correct with effort, below 3 failed)."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be 0..5")
    q = quality
    ef = max(1.3, card.ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if q < 3:
        reps, interval, lapses = 0, 1, card.lapses + 1
    else:
        reps = card.reps + 1
        interval = 1 if reps == 1 else 6 if reps == 2 else math.ceil(round(card.interval * ef, 6))
        lapses = card.lapses
    return replace(card, ef=round(ef, 4), reps=reps, interval=interval, lapses=lapses,
                   due=(today + timedelta(days=interval)).isoformat())


def level_of(score: float) -> str:
    return LEVELS[min(2, max(0, int(score) - 1))]


def update_level(score: float, level: str, signal: Optional[str]) -> tuple[float, str]:
    """Reference. Returns (new score, displayed level)."""
    if signal not in BAND_MID:
        return score, level
    s = min(3.99, max(1.0, score + ALPHA * (BAND_MID[signal] - score)))
    s = round(s, 4)
    i = LEVELS.index(level)
    lo, hi = float(i + 1), float(i + 2)  # band of the displayed level
    if s >= hi + MARGIN and i < 2:
        level = level_of(s)
    elif s < lo - MARGIN and i > 0:
        level = level_of(s)
    return s, level


def turn_points(has_correction: bool, n_new_words: int) -> int:
    return (POINTS["turn_corrected"] if has_correction else POINTS["turn_clean"]) + POINTS["new_word"] * n_new_words


def scenario_done(turns: int, clean_turns: int) -> bool:
    """A scenario counts as done after 6 turns with at least 4 without a correction."""
    return turns >= 6 and clean_turns >= 4
