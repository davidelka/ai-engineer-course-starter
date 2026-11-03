from solution import remaining_days


def test_simple():
    assert remaining_days(14, 0, 3) == 11


def test_carryover_is_added():
    assert remaining_days(14, 2, 3) == 13


def test_carryover_capped_at_five():
    assert remaining_days(14, 8, 0) == 19


def test_overdraft_allowed():
    assert remaining_days(14, 0, 20) == -6


def test_typical_year():
    assert remaining_days(15, 3, 6) == 13
