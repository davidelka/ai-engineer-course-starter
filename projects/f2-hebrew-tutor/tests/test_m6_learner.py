"""M6: sm2_update and update_level (mine.py): the learner model."""

from datetime import date

import pytest

from hebtutor.hooks import load_mine
from hebtutor.learner import Card

mine = load_mine()
T = date(2026, 11, 2)


def test_new_card_good_answers():
    c = Card("v001", "רופא", "طبيب")
    c1 = mine.sm2_update(c, 4, T)
    assert (c1.reps, c1.interval, c1.due, c1.ef) == (1, 1, "2026-11-03", 2.5)
    c2 = mine.sm2_update(c1, 4, T)
    assert (c2.reps, c2.interval) == (2, 6)
    c3 = mine.sm2_update(c2, 4, T)
    assert (c3.reps, c3.interval, c3.due) == (3, 15, "2026-11-17")
    assert c.reps == 0 and c.due == ""  # the input is not modified


def test_ef_moves_with_quality_and_has_a_floor():
    c = Card("v1", "a", "b")
    assert mine.sm2_update(c, 5, T).ef == 2.6
    assert mine.sm2_update(c, 3, T).ef == 2.36
    low = c
    for _ in range(10):
        low = mine.sm2_update(low, 0, T)
    assert low.ef == 1.3


def test_failure_resets_and_counts_a_lapse():
    c = Card("v1", "a", "b", ef=2.5, reps=4, interval=40, due="2026-11-02")
    f = mine.sm2_update(c, 2, T)
    assert (f.reps, f.interval, f.lapses, f.due) == (0, 1, 1, "2026-11-03")
    assert f.ef == pytest.approx(2.18)


def test_quality_range():
    with pytest.raises(ValueError):
        mine.sm2_update(Card("v", "a", "b"), 6, T)


def test_level_unclear_changes_nothing():
    assert mine.update_level(1.7, "A1", "unclear") == (1.7, "A1")
    assert mine.update_level(1.7, "A1", None) == (1.7, "A1")


def test_level_moves_slowly_with_hysteresis():
    s, lv = mine.update_level(1.5, "A1", "B1")
    assert (s, lv) == (1.8, "A1")
    steps = 0
    while lv == "A1":
        s, lv = mine.update_level(s, lv, "B1")
        steps += 1
    assert lv == "A2" and s >= 2.15 and steps >= 2
    # just below the A2 band does not demote: the margin protects it
    assert mine.update_level(2.0, "A2", "A1")[1] == "A2"
    assert mine.update_level(1.9, "A2", "A1")[1] == "A1"


def test_clamped():
    s = 3.9
    for _ in range(50):
        s, lv = mine.update_level(s, "B1", "B1")
    assert s <= 3.99 and lv == "B1"
    s = 1.0
    for _ in range(5):
        s, lv = mine.update_level(s, "A1", "A1")
    assert 1.0 <= s <= 1.5
