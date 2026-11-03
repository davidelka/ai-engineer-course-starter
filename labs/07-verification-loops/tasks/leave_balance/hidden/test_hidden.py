from hypothesis import given
from hypothesis import strategies as st

from solution import remaining_days

num = st.integers(0, 40)


@given(num, num, num)
def test_formula(a, c, t):
    got, want = remaining_days(a, c, t), a + min(c, 5) - t
    assert got == want, f"remaining_days({a}, {c}, {t}) = {got}, expected {want}"


def test_typical_year_by_the_spec():
    assert remaining_days(15, 3, 6) == 12, "15 + 3 - 6 = 12 according to the spec"
