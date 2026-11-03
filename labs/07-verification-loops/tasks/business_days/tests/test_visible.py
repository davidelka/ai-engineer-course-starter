from datetime import date

from solution import business_days

SUN = date(2026, 11, 1)  # a Sunday
THU = date(2026, 11, 5)
FRI = date(2026, 11, 6)
SAT = date(2026, 11, 7)


def test_single_sunday_counts():
    assert business_days(SUN, SUN) == 1


def test_friday_is_weekend():
    assert business_days(FRI, FRI) == 0


def test_sunday_to_thursday_is_five():
    assert business_days(SUN, THU) == 5


def test_full_week_is_five():
    assert business_days(SUN, SAT) == 5


def test_two_weeks():
    assert business_days(SUN, date(2026, 11, 14)) == 10


def test_holiday_on_a_workday_is_removed():
    assert business_days(SUN, SAT, [date(2026, 11, 3)]) == 4


def test_holiday_on_saturday_changes_nothing():
    assert business_days(SUN, SAT, [SAT]) == 5


def test_duplicate_holidays_count_once():
    h = date(2026, 11, 3)
    assert business_days(SUN, SAT, [h, h]) == 4


def test_end_before_start_is_zero():
    assert business_days(THU, SUN) == 0
