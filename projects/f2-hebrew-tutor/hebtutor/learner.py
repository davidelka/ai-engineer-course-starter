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

from dataclasses import asdict, dataclass

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


def sm2_update(*args, **kwargs):
    """Milestone 6: runs your mine.sm2_update (see hebtutor/hooks.py)."""
    from .hooks import call
    return call("sm2_update", *args, **kwargs)


def level_of(score: float) -> str:
    return LEVELS[min(2, max(0, int(score) - 1))]


def update_level(*args, **kwargs):
    """Milestone 6: runs your mine.update_level (see hebtutor/hooks.py)."""
    from .hooks import call
    return call("update_level", *args, **kwargs)


def turn_points(has_correction: bool, n_new_words: int) -> int:
    return (POINTS["turn_corrected"] if has_correction else POINTS["turn_clean"]) + POINTS["new_word"] * n_new_words


def scenario_done(turns: int, clean_turns: int) -> bool:
    """A scenario counts as done after 6 turns with at least 4 without a correction."""
    return turns >= 6 and clean_turns >= 4
