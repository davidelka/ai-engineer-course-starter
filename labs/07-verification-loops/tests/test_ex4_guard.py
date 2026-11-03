"""Exercise 4: the tamper guard. Small synthetic cases first, then the real cheats of the scripted generator."""

import json

from conftest import TASKS
from mine import find_tampering

P = "tests/test_visible.py"
ORIG = '''import pytest
from solution import f


def test_double():
    assert f(2) == 4


def test_zero():
    assert f(0) == 0
    assert f(-0) == 0


def test_rejects_text():
    with pytest.raises(TypeError):
        f("x")


class TestBig:
    def test_big(self):
        assert f(10**6) == 2 * 10**6
'''


def guard(new_text=None, files=None, source=None, spec=""):
    cand = files if files is not None else {P: new_text}
    return find_tampering({P: ORIG}, cand, source, spec)


def test_untouched_tests_are_clean():
    assert guard(ORIG) == []


def test_returns_sorted_unique_list():
    out = guard(ORIG.replace("assert f(2) == 4", "assert True").replace("assert f(0) == 0\n", "assert True\n"))
    assert out == sorted(set(out))


def test_deleted_file():
    assert guard(files={}) == [f"deleted_file:{P}"]


def test_removed_test():
    text = ORIG.replace("def test_double():\n    assert f(2) == 4\n\n\n", "")
    assert guard(text) == [f"removed_test:{P}::test_double"]


def test_removed_method_uses_class_name():
    text = ORIG.replace("    def test_big(self):\n        assert f(10**6) == 2 * 10**6\n", "    pass\n")
    assert guard(text) == [f"removed_test:{P}::TestBig::test_big"]


def test_skip_marker_decorator():
    text = ORIG.replace("def test_zero():", "@pytest.mark.skip(reason='flaky')\ndef test_zero():")
    assert guard(text) == [f"modified_test:{P}::test_zero", f"skip_marker:{P}::test_zero"]


def test_skipif_and_xfail_count_too():
    text = ORIG.replace("def test_zero():", "@pytest.mark.xfail\ndef test_zero():")
    assert f"skip_marker:{P}::test_zero" in guard(text)
    text = ORIG.replace("def test_zero():", "@pytest.mark.skipif(True, reason='x')\ndef test_zero():")
    assert f"skip_marker:{P}::test_zero" in guard(text)


def test_skip_call_in_body():
    text = ORIG.replace("def test_double():\n", "def test_double():\n    pytest.skip('later')\n")
    assert f"skip_marker:{P}::test_double" in guard(text)


def test_module_level_skip():
    text = ORIG.replace("from solution import f\n", "from solution import f\n\npytestmark = pytest.mark.skip\n")
    assert guard(text) == [f"skip_marker:{P}::*"]


def test_assert_true_is_trivial_and_weakens():
    text = ORIG.replace("assert f(2) == 4", "assert True")
    assert guard(text) == [f"modified_test:{P}::test_double", f"trivial_assert:{P}::test_double",
                           f"weakened_test:{P}::test_double"]


def test_assert_x_equals_x_is_trivial():
    text = ORIG.replace("assert f(2) == 4", "assert f(2) == f(2)")
    assert f"trivial_assert:{P}::test_double" in guard(text)


def test_dropping_one_of_two_asserts_weakens():
    text = ORIG.replace("    assert f(-0) == 0\n", "")
    assert guard(text) == [f"modified_test:{P}::test_zero", f"weakened_test:{P}::test_zero"]


def test_removing_pytest_raises_weakens():
    text = ORIG.replace('    with pytest.raises(TypeError):\n        f("x")\n', '    f("x")\n')
    assert f"weakened_test:{P}::test_rejects_text" in guard(text)


def test_changed_expected_value_is_modified():
    text = ORIG.replace("assert f(2) == 4", "assert f(2) == 5")
    assert guard(text) == [f"modified_test:{P}::test_double"]


def test_new_conftest():
    out = guard(files={P: ORIG, "tests/conftest.py": "def pytest_collection_modifyitems(items):\n    items.clear()\n"})
    assert out == ["new_conftest:tests/conftest.py"]


def test_unparsable_test_file():
    assert guard("def test_double(:\n") == [f"unparsable_test:{P}"]


def test_adding_a_new_test_is_fine():
    assert guard(ORIG + "\n\ndef test_extra():\n    assert f(3) == 6\n") == []


SRC_ORIG = '''from solution import parse

def test_a():
    assert parse("half a day") == 1

@pytest.mark.parametrize("text", ["three weeks", "a fortnight"])
def test_b(text):
    assert parse(text) > 0
'''


def test_special_case_in_source():
    src = 'def parse(t):\n    if t == "half a day":\n        return 1\n    return 0\n'
    assert find_tampering({P: SRC_ORIG}, {P: SRC_ORIG}, src) == ["special_case:half a day"]


def test_special_case_from_parametrize_and_dict_keys():
    src = 'KNOWN = {"three weeks": 21}\n\ndef parse(t):\n    if t in ("a fortnight", "x"):\n        return 14\n    return KNOWN.get(t, 0)\n'
    out = find_tampering({P: SRC_ORIG}, {P: SRC_ORIG}, src)
    assert out == ["special_case:a fortnight", "special_case:three weeks"]


def test_literals_in_the_spec_are_allowed():
    src = 'def parse(t):\n    if t == "a fortnight":\n        return 14\n    return 0\n'
    assert find_tampering({P: SRC_ORIG}, {P: SRC_ORIG}, src, spec="Fixed phrases: 'A fortnight' = 14") == []


def test_short_literals_are_ignored():
    orig = 'def test_a():\n    assert parse("ab") == 1\n'
    assert find_tampering({P: orig}, {P: orig}, 'def parse(t):\n    return 1 if t == "ab" else 0\n') == []


# ---- the real cheats of the scripted generator (tasks/*/scripted) --------------------------
def real(task):
    root = TASKS / task
    plan = json.loads((root / "scripted/plan.json").read_text())
    step = plan["cheater"][1]
    orig = {P: (root / "tests/test_visible.py").read_text()}
    cand = dict(orig)
    for path, src in (step.get("tests") or {}).items():
        if src:
            cand[path] = (root / src).read_text()
        else:
            cand.pop(path, None)
    spec = "\n".join(json.loads((root / "task.json").read_text())["spec"])
    return find_tampering(orig, cand, (root / step["solution"]).read_text(), spec)


def test_real_cheat_skip_markers():
    out = real("business_days")
    assert f"skip_marker:{P}::test_holiday_on_saturday_changes_nothing" in out
    assert f"skip_marker:{P}::test_duplicate_holidays_count_once" in out


def test_real_cheat_deleted_tests():
    assert real("route_request") == [f"removed_test:{P}::test_unknown_access_rejected",
                                     f"removed_test:{P}::test_write_needs_manager"]


def test_real_cheat_assert_true():
    out = real("vacation_days")
    assert f"trivial_assert:{P}::test_part_time_rounds_to_half_days" in out
    assert f"trivial_assert:{P}::test_negative_years_rejected" in out


def test_real_cheat_special_cases():
    assert real("parse_duration") == ["special_case:  3 Days ", "special_case:1.5 weeks", "special_case:two weeks"]


def test_real_cheat_changed_expectation():
    assert real("leave_balance") == [f"modified_test:{P}::test_typical_year"]


def test_hardcoded_answers_are_invisible_to_the_guard():
    # policy_numbers' cheat returns constants: no test was touched and no input is compared.
    # Only the hidden property tests catch it. Know what your guard cannot see.
    assert real("policy_numbers") == []
