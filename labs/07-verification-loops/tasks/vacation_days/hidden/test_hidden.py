import math
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from solution import vacation_days

years = st.floats(min_value=0, max_value=60, allow_nan=False, allow_infinity=False)
eighths = st.integers(min_value=1, max_value=8).map(lambda k: k / 8)  # exact in binary


def expected(y, scope):
    full = min(24, 14 + math.floor(y))
    exact = Fraction(full) * Fraction(scope)
    return float(math.floor(exact * 2 + Fraction(1, 2)) / 2)


@given(years)
def test_full_time_formula(y):
    got, want = vacation_days(y), min(24, 14 + math.floor(y))
    assert got == want, f"vacation_days({y!r}) = {got!r}, expected {want}"


@given(years, years)
def test_monotonic_in_years(a, b):
    lo, hi = sorted((a, b))
    assert vacation_days(lo) <= vacation_days(hi), f"vacation_days({lo!r}) > vacation_days({hi!r})"


@given(years, eighths)
def test_part_time_nearest_half_quarters_round_up(y, scope):
    got, want = vacation_days(y, scope), expected(y, scope)
    assert got == want, f"vacation_days({y!r}, scope={scope}) = {got!r}, expected {want}"


def test_quarter_rounds_up():
    got = vacation_days(1, scope=0.75)
    assert got == 11.5, f"vacation_days(1, scope=0.75) = {got!r}: 15 * 0.75 = 11.25 must round UP to 11.5"


@pytest.mark.parametrize("scope", [0, -0.5, 1.01, 2])
def test_bad_scope_rejected(scope):
    with pytest.raises(ValueError):
        vacation_days(3, scope=scope)
