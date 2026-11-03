import pytest

from solution import vacation_days


def test_first_year_is_14():
    assert vacation_days(0.5) == 14


def test_second_year_adds_one_day():
    assert vacation_days(1.0) == 15


def test_counts_completed_years_only():
    assert vacation_days(3.9) == 17


def test_capped_at_24():
    assert vacation_days(10) == 24
    assert vacation_days(30) == 24


def test_part_time_half_scope():
    assert vacation_days(0, scope=0.5) == 7


def test_part_time_rounds_to_half_days():
    assert vacation_days(0, scope=0.75) == 10.5


def test_part_time_rounds_down_when_closer():
    assert vacation_days(3, scope=0.6) == 10  # 17 * 0.6 = 10.2


def test_negative_years_rejected():
    with pytest.raises(ValueError):
        vacation_days(-1)
