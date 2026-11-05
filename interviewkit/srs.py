"""Spaced repetition, SM-2 style (lesson 28, reference for exercise 3).

The algorithm as described on Wikipedia's SuperMemo page (SM-2, Wozniak 1987):
grade q in 0..5, easiness factor EF starting at 2.5, intervals 1, 6, then I*EF.
One deliberate reading: EF is updated after every review, including failed ones
(the Wikipedia pseudo-code does this), and never drops below 1.3.
"""

from __future__ import annotations

import math

from datetime import date, timedelta
from typing import Iterable, Optional

START_EF = 2.5
MIN_EF = 1.3


def sm2_review(state: Optional[dict], grade: int, today: date) -> dict:
    if isinstance(grade, bool) or not isinstance(grade, int) or not 0 <= grade <= 5:
        raise ValueError(f"grade must be an int 0..5, got {grade!r}")
    state = dict(state or {})
    ef = float(state.get("ef", START_EF))
    reps = int(state.get("reps", 0))
    interval = int(state.get("interval", 0))
    lapses = int(state.get("lapses", 0))
    if grade >= 3:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            # the original SM-2 description rounds a fractional interval UP (as F2's learner.py does);
            # the inner round() absorbs float noise such as 6 * 2.5000000001
            interval = math.ceil(round(interval * ef, 6))
        reps += 1
    else:
        reps, interval, lapses = 0, 1, lapses + 1
    ef = max(MIN_EF, ef + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
    state.update(ef=round(ef, 4), reps=reps, interval=interval, lapses=lapses,
                 due=(today + timedelta(days=interval)).isoformat(), last=today.isoformat())
    return state


def grade_from_score(score: float) -> int:
    for cut, g in ((90, 5), (75, 4), (60, 3), (40, 2), (20, 1)):
        if score >= cut:
            return g
    return 0


def pick_session(bank_ids: Iterable[str], states: dict[str, dict], today: date,
                 new_per_day: int = 5, limit: int = 15) -> list[str]:
    ids = list(bank_ids)
    due = [i for i in ids if i in states and date.fromisoformat(states[i]["due"]) <= today]
    due.sort(key=lambda i: (states[i]["due"], states[i].get("ef", START_EF), i))
    new = [i for i in ids if i not in states][:max(0, new_per_day)]
    return (due + new)[:max(0, limit)]
