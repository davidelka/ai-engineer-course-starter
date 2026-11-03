"""Exercise 5: results_match in mine.py (execution accuracy)."""

from mine import results_match


def test_same_rows_any_order():
    assert results_match([("a", 1), ("b", 2)], [("b", 2), ("a", 1)])


def test_order_matters_when_asked():
    assert not results_match([("a", 1), ("b", 2)], [("b", 2), ("a", 1)], ordered=True)
    assert results_match([("b", 2), ("a", 1)], [("b", 2), ("a", 1)], ordered=True)


def test_duplicates_count():
    assert not results_match([(1,), (1,)], [(1,), (2,)])
    assert not results_match([(1,)], [(1,), (1,)])


def test_numbers_are_normalized():
    assert results_match([(3.0,)], [(3,)])
    assert results_match([(0.155172,)], [(0.1552,)])
    assert not results_match([(0.135,)], [(0.1552,)])
    assert results_match([(True,)], [(1,)])


def test_strings_are_trimmed_but_case_sensitive():
    assert results_match([(" Haifa ",)], [("Haifa",)])
    assert not results_match([("haifa",)], [("Haifa",)])


def test_none_matches_none():
    assert results_match([(None, 1)], [(None, 1)])
    assert not results_match([(None,)], [(0,)])


def test_column_order_does_not_matter():
    assert results_match([(79, "Tel Aviv"), (28, "Haifa")], [("Tel Aviv", 79), ("Haifa", 28)])


def test_extra_columns_strict_and_lenient():
    pred = [("billing", "Billing", 1), ("engine", "Engine", 2)]
    gold = [("Billing", 1), ("Engine", 2)]
    assert not results_match(pred, gold)
    assert results_match(pred, gold, allow_extra_columns=True)


def test_fewer_columns_never_match():
    assert not results_match([(1,)], [("Billing", 1)], allow_extra_columns=True)


def test_empty_results():
    assert results_match([], [])
    assert not results_match([], [(0,)])
    assert not results_match([(0,)], [])


def test_lists_and_tuples_are_the_same():
    assert results_match([["a", 1]], [("a", 1)])
