import math
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from solution import parse_duration

UNIT_DAYS = {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30}


@given(st.integers(1, 400), st.sampled_from(sorted(UNIT_DAYS)))
def test_whole_numbers(n, unit):
    text = f"{n} {unit}"
    got, want = parse_duration(text), n * UNIT_DAYS[unit]
    assert got == want, f"parse_duration({text!r}) = {got!r}, expected {want}"


@given(st.integers(1, 200))
def test_decimal_weeks_round_up(k):
    text = f"{k // 10}.{k % 10} weeks"
    got, want = parse_duration(text), math.ceil(Fraction(k, 10) * 7)
    assert got == want, f"parse_duration({text!r}) = {got!r}, expected {want}"


@given(st.integers(1, 99), st.sampled_from(sorted(UNIT_DAYS)), st.text(" \t", max_size=3),
       st.text(" \t", max_size=3), st.text(" \t", min_size=1, max_size=3), st.booleans())
def test_case_and_whitespace_do_not_matter(n, unit, pre, post, mid, upper):
    text = f"{pre}{n}{mid}{unit}{post}"
    text = text.upper() if upper else text
    got, want = parse_duration(text), parse_duration(f"{n} {unit}")
    assert got == want, f"parse_duration({text!r}) = {got!r}, but parse_duration('{n} {unit}') = {want!r}"


@given(st.text(max_size=30))
def test_never_raises_and_returns_positive_int_or_none(s):
    got = parse_duration(s)
    assert got is None or (isinstance(got, int) and got > 0), f"parse_duration({s!r}) = {got!r}"


@pytest.mark.parametrize("text,days", [
    ("three days", 3), ("one month", 30), ("a week", 7), ("an day", 1), ("half a day", 1),
    ("יום", 1), ("יומיים", 2), ("שבוע", 7), ("חודש", 30), ("A Fortnight", 14), ("2.5 days", 3),
])
def test_words_and_phrases(text, days):
    got = parse_duration(text)
    assert got == days, f"parse_duration({text!r}) = {got!r}, expected {days}"


@pytest.mark.parametrize("text", ["0 days", "0.0 weeks", "days", "3", "3 years", "minus 3 days"])
def test_not_a_duration(text):
    got = parse_duration(text)
    assert got is None, f"parse_duration({text!r}) = {got!r}, expected None"
