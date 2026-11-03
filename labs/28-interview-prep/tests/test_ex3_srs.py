"""Exercise 3: SM-2 spaced repetition for the question bank."""

from datetime import date

import pytest

from mine import grade_from_score, pick_session, sm2_review

D = date(2026, 11, 1)


def test_new_card_good_answer():
    s = sm2_review(None, 4, D)
    assert s["reps"] == 1 and s["interval"] == 1 and s["lapses"] == 0
    assert s["ef"] == pytest.approx(2.5)  # grade 4 leaves EF unchanged
    assert s["due"] == "2026-11-02" and s["last"] == "2026-11-01"


def test_interval_sequence_1_6_then_times_ef():
    s = sm2_review(None, 5, D)                     # I=1, ef 2.6
    s = sm2_review(s, 5, date(2026, 11, 2))        # I=6, ef 2.7
    assert s["interval"] == 6 and s["ef"] == pytest.approx(2.7)
    s = sm2_review(s, 5, date(2026, 11, 8))        # I=round(6*2.7)=16, ef 2.8
    assert s["interval"] == 16 and s["reps"] == 3
    assert s["due"] == "2026-11-24"
    assert s["ef"] == pytest.approx(2.8)


def test_uses_old_ef_for_the_interval():
    s = {"ef": 2.5, "reps": 2, "interval": 6, "lapses": 0, "due": "2026-11-01", "last": "2026-10-26"}
    out = sm2_review(s, 3, D)  # interval = round(6 * 2.5) = 15, then ef drops to 2.36
    assert out["interval"] == 15
    assert out["ef"] == pytest.approx(2.36)


def test_failure_resets_and_counts_lapse():
    s = {"ef": 2.5, "reps": 4, "interval": 40, "lapses": 1, "due": "2026-11-01", "last": "2026-09-22"}
    out = sm2_review(s, 1, D)
    assert out["reps"] == 0 and out["interval"] == 1 and out["lapses"] == 2
    assert out["ef"] == pytest.approx(2.5 - 0.54)
    assert out["due"] == "2026-11-02"


def test_ef_floor():
    s = None
    for _ in range(10):
        s = sm2_review(s, 0, D)
    assert s["ef"] == pytest.approx(1.3)


def test_does_not_mutate_and_keeps_extra_keys():
    s = {"ef": 2.5, "reps": 0, "interval": 0, "lapses": 0, "due": "2026-11-01", "last": "", "note": "x"}
    before = dict(s)
    out = sm2_review(s, 5, D)
    assert s == before
    assert out["note"] == "x" and out is not s


@pytest.mark.parametrize("bad", [6, -1, 3.0, True, "4", None])
def test_bad_grade(bad):
    with pytest.raises(ValueError):
        sm2_review(None, bad, D)


@pytest.mark.parametrize("score,grade", [(100, 5), (90, 5), (89.9, 4), (75, 4), (60, 3), (59, 2),
                                         (40, 2), (20, 1), (19, 0), (0, 0)])
def test_grade_from_score(score, grade):
    assert grade_from_score(score) == grade


def test_pick_session_order():
    bank = ["a", "b", "c", "d", "e", "f", "g"]
    states = {
        "a": {"due": "2026-11-05", "ef": 2.5},   # not due yet
        "b": {"due": "2026-10-30", "ef": 2.5},
        "c": {"due": "2026-10-30", "ef": 1.7},   # same day as b but harder -> first
        "d": {"due": "2026-11-01", "ef": 2.0},   # due today
        "zz": {"due": "2026-01-01", "ef": 1.3},  # not in the bank -> ignored
    }
    assert pick_session(bank, states, D, new_per_day=2, limit=10) == ["c", "b", "d", "e", "f"]


def test_pick_session_limits():
    bank = [f"q{i}" for i in range(20)]
    states = {f"q{i}": {"due": "2026-10-01", "ef": 2.5} for i in range(5)}
    assert pick_session(bank, states, D, new_per_day=3, limit=6) == ["q0", "q1", "q2", "q3", "q4", "q5"]
    assert pick_session(bank, {}, D, new_per_day=0) == []
