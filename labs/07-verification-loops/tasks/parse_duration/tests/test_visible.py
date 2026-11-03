import pytest

from solution import parse_duration


@pytest.mark.parametrize("text,days", [
    ("3 days", 3), ("1 day", 1), ("2 weeks", 14), ("1 month", 30), ("two weeks", 14),
])
def test_number_and_unit(text, days):
    assert parse_duration(text) == days


def test_decimal_rounds_up():
    assert parse_duration("1.5 weeks") == 11


def test_fortnight():
    assert parse_duration("a fortnight") == 14


def test_case_and_spaces():
    assert parse_duration("  3 Days ") == 3


def test_hebrew():
    assert parse_duration("שבועיים") == 14


@pytest.mark.parametrize("text", ["soon", "", "until the project ends"])
def test_unknown_is_none(text):
    assert parse_duration(text) is None
