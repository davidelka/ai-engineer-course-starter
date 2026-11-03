"""Exercise 5: compact, actionable feedback from real pytest output (fixtures/*.txt)."""

import pytest

from conftest import FIXTURES
from mine import format_feedback


def fx(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_header_is_counts_without_timing():
    assert format_feedback(fx("vacation_starter.txt")).splitlines()[0] == "5 failed, 3 passed"


def test_all_passed_is_just_the_header():
    assert format_feedback(fx("route_all_pass.txt")) == "10 passed"


def test_one_entry_per_failure_in_order():
    lines = format_feedback(fx("vacation_starter.txt")).splitlines()
    entries = [x for x in lines if x.startswith("- ")]
    assert entries == [
        "- test_visible.py::test_second_year_adds_one_day",
        "- test_visible.py::test_counts_completed_years_only",
        "- test_visible.py::test_capped_at_24",
        "- test_visible.py::test_part_time_rounds_to_half_days",
        "- test_visible.py::test_negative_years_rejected",
    ]


def test_details_show_code_and_values():
    text = format_feedback(fx("vacation_starter.txt"))
    block = text.split("- test_visible.py::test_second_year_adds_one_day\n")[1].split("\n- ")[0]
    assert block.splitlines() == [
        "    assert vacation_days(1.0) == 15",
        "    assert 14 == 15",
        "    +  where 14 = vacation_days(1.0)",
    ]


def test_marker_lines_are_not_the_source_line():
    text = format_feedback(fx("vacation_starter.txt"))
    block = text.split("- test_visible.py::test_negative_years_rejected\n")[1]
    assert block.splitlines()[:2] == ["    with pytest.raises(ValueError):", "    Failed: DID NOT RAISE ValueError"]


def test_class_and_parametrized_ids():
    text = format_feedback(fx("class_and_params.txt"))
    assert "- test_visible.py::test_param[6-12]\n    assert f(x) == want\n    assert 0 == 12" in text
    assert "- test_visible.py::TestK::test_k\n" in text
    assert "    AssertionError: f doubles" in text


def test_max_failures_and_the_rest_line():
    text = format_feedback(fx("duration_starter.txt"), max_failures=3)
    entries = [x for x in text.splitlines() if x.startswith("- ")]
    assert len(entries) == 4 and entries[-1] == "- ... and 5 more failing tests"


def test_collection_error_shows_the_syntax_error():
    text = format_feedback(fx("route_syntax_error.txt"))
    lines = text.splitlines()
    assert lines[0] == "1 error"
    assert lines[1] == "- test_visible.py (collection error)"
    assert "    SyntaxError: expected ':'" in lines
    assert '    File "solution.py", line 1' in lines  # absolute temp path cut to the file name
    assert not any("/tmp/" in x for x in lines)


def test_hypothesis_notes_are_dropped_but_the_counterexample_stays():
    text = format_feedback(fx("business_hidden.txt"))
    assert "Failing test case" not in text
    assert "= 262, expected 263" in text
    assert text.splitlines()[0] == "1 failed, 3 passed"


def test_long_e_blocks_keep_first_two_and_last_two():
    out = ("F\n" + "_" * 5 + " test_a " + "_" * 5 + "\nt.py:3: in test_a\n    check()\n"
           + "".join(f"E   line {i}\n" for i in range(1, 8))
           + "=== short test summary info ===\nFAILED tests/t.py::test_a - line 1\n1 failed in 0.01s\n")
    assert format_feedback(out).splitlines()[1:] == [
        "- t.py::test_a", "    check()", "    line 1", "    line 2", "    line 6", "    line 7"]


def test_fallback_to_summary_message():
    out = "F\n=== short test summary info ===\nFAILED tests/t.py::test_a - boom happened\n1 failed in 0.01s\n"
    assert format_feedback(out) == "1 failed\n- t.py::test_a\n    boom happened"


def test_no_summary_line_and_no_tests():
    assert format_feedback("garbage") == "pytest output had no summary line"
    assert format_feedback("\nno tests ran in 0.01s\n").splitlines()[0] in ("no tests ran",)


@pytest.mark.parametrize("limit", [120, 300])
def test_max_chars_is_exact(limit):
    text = format_feedback(fx("duration_starter.txt"), max_chars=limit)
    assert len(text) == limit and text.endswith("\n...[truncated]")


def test_much_shorter_than_raw():
    raw = fx("duration_starter.txt")
    assert len(format_feedback(raw)) < len(raw) / 2
