from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from solution import business_days

WORK = {6, 0, 1, 2, 3}
days = st.dates(min_value=date(2024, 1, 1), max_value=date(2028, 12, 31))


def brute(a, b, hol):
    off = set(hol)
    span = (a + timedelta(i) for i in range((b - a).days + 1))
    return sum(1 for d in span if d.weekday() in WORK and d not in off)


@given(days, days, st.lists(days, max_size=8))
def test_matches_day_by_day_count(a, b, hol):
    a, b = min(a, b), max(a, b)
    got, want = business_days(a, b, hol), brute(a, b, hol)
    assert got == want, f"business_days({a}, {b}, holidays={sorted(hol)}) = {got}, expected {want}"


@given(days, st.integers(0, 400), st.integers(0, 400))
def test_split_ranges_add_up(a, n, m):
    b = a + timedelta(n)
    c = b + timedelta(1 + m)
    whole = business_days(a, c)
    parts = business_days(a, b) + business_days(b + timedelta(1), c)
    assert whole == parts, f"[{a}..{c}] gives {whole}, but [{a}..{b}] + [{b + timedelta(1)}..{c}] gives {parts}"


@given(days)
def test_any_seven_days_have_five_workdays(a):
    got = business_days(a, a + timedelta(6))
    assert got == 5, f"business_days({a}, {a + timedelta(6)}) = {got}, expected 5"


@given(days, st.integers(1, 30))
def test_reversed_range_is_zero(a, n):
    got = business_days(a + timedelta(n), a)
    assert got == 0, f"business_days({a + timedelta(n)}, {a}) = {got}, expected 0 (end before start)"
