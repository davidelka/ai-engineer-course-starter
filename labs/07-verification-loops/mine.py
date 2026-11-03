"""Your code for lesson 7. Each part is checked by tests in ./tests.

loopkit/policy.py, loopkit/guard.py and loopkit/feedback.py hold reference versions.
Try not to peek before your tests pass.

    python -m pytest -q labs/07-verification-loops/tests

Plug your versions into the real loop with:  run_loop.py --mine
"""

from __future__ import annotations

import ast  # noqa: F401  (exercise 4: you will need it)
import re  # noqa: F401  (exercise 5)
from typing import Optional

from loopkit.types import Budget, IterationRecord, StopDecision  # noqa: F401


# ------------------------------------------------------------------ exercise 3
def should_stop(history: list[IterationRecord], budget: Budget) -> StopDecision:
    """Decide after every iteration: run another one, or stop, and why.

    history: one IterationRecord per iteration so far, oldest first. Its fields hold
    PER-ITERATION values: iteration, score (0..1), solved, candidate_hash, tokens,
    cost_usd, elapsed_s, tampered. Totals are sums over the history.
    budget: max_iterations, max_tokens, max_cost_usd, max_seconds (None = no limit),
    patience, max_tamper.

    Apply these rules IN THIS ORDER; the first one that applies decides:
      1. empty history                                   -> StopDecision(False, "continue")
      2. last iteration solved and not tampered          -> stop, "solved"
      3. number of tampered iterations >= max_tamper     -> stop, "tampering"
      4. len(history) >= max_iterations                  -> stop, "budget_iterations"
      5. total tokens >= max_tokens                      -> stop, "budget_tokens"
      6. total cost >= max_cost_usd, OR total cost + the last iteration's cost
         > max_cost_usd (one more iteration like the last would overspend)
                                                         -> stop, "budget_cost"
      7. total elapsed_s >= max_seconds                  -> stop, "budget_time"
      8. last candidate_hash == the previous one         -> stop, "no_change"
      9. last candidate_hash equals any EARLIER one (not the previous) -> stop, "oscillation"
     10. len(history) > patience (and patience > 0), and the best score among the last
         `patience` iterations is NOT higher than the best score before them
                                                         -> stop, "no_progress"
     11. otherwise                                       -> StopDecision(False, "continue")
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement should_stop")


# ------------------------------------------------------------------ exercise 4
def find_tampering(original: dict[str, str], candidate: dict[str, str], source: Optional[str] = None,
                   spec: str = "") -> list[str]:
    """Find what the candidate did to the tests, instead of to the code.

    original:  pristine test files, {path: text}, e.g. {"tests/test_visible.py": "..."}
    candidate: the candidate's test files (same shape). A path missing here was deleted.
    source:    the candidate's solution module (for special-casing), or None.
    spec:      the task spec; literals that appear in it (case-insensitive) are allowed.

    A "test file" is a .py file named test_*.py, *_test.py or conftest.py.
    A "test" is a top-level function named test*, or a method test* inside a class Test*,
    named "Class::method".

    Return a SORTED list of UNIQUE strings:
      deleted_file:<path>            a pristine test file is missing from candidate
      new_conftest:<path>            a conftest.py exists in candidate but not in original
      unparsable_test:<path>         a candidate test file does not parse (skip its other checks)
      removed_test:<path>::<name>    a pristine test is gone from its file
      skip_marker:<path>::<name>     the test gained @pytest.mark.skip / skipif / xfail, or
                                     calls pytest.skip(...) / pytest.xfail(...) in its body
      skip_marker:<path>::*          a module-level `pytestmark = pytest.mark.skip...` was added
      trivial_assert:<path>::<name>  the test contains `assert <truthy constant>` (assert True,
                                     assert 1) or `assert X == X` with the same expression twice
      weakened_test:<path>::<name>   fewer real checks than the pristine version; a real check is
                                     a non-trivial assert or a `with pytest.raises(...)` block
      modified_test:<path>::<name>   the test's code differs from the pristine version
                                     (compare ast.dump of the two function nodes)
      special_case:<literal>         `source` compares (==, !=, in, not in, or inside a tuple/list/set
                                     being compared) a string literal, or uses it as a dict key,
                                     where the literal (3+ chars after strip) appears inside the
                                     arguments of a call in the ORIGINAL tests (parametrize lists
                                     included), and does not appear in `spec`
    One test can get several findings (assert True in place of a real assert gives
    trivial_assert, weakened_test and modified_test).
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement find_tampering")


# ------------------------------------------------------------------ exercise 5
def format_feedback(pytest_output: str, max_failures: int = 5, max_chars: int = 1500) -> str:
    """Turn raw output of `pytest -q --tb=short -rfE --no-header` into compact feedback.

    Line 1: the counts from pytest's final line without the timing: "2 failed, 6 passed"
            (from "2 failed, 6 passed in 0.12s"); "no tests ran" if the output says so;
            otherwise "pytest output had no summary line".
    Then, for each line of the short summary that starts with "FAILED " or "ERROR ",
    in order, at most max_failures of them:
        - <file name>::<rest of the node id>      e.g. "- test_visible.py::TestK::test_k"
          (for "ERROR <path>" with no "::", a collection error: "- <file name> (collection error)")
        then detail lines, each indented by 4 spaces:
          * the source line that failed: in that test's traceback block, the last line before
            the first "E " line that starts with 4 spaces and is not just ^ or ~ markers (stripped)
          * the block's "E " lines, without the leading "E" and spaces; absolute paths in quotes
            cut to the file name ("/tmp/x/solution.py" -> "solution.py"); stop at a line
            starting with "Failing test case:" or "Falsifying example:"; if more than 4 remain,
            keep the first 2 and the last 2
          * if the block has no "E " lines: the message after " - " in the summary line, if any
    A test's block starts at its header line "____ <name> ____", where <name> is the node id
    after the file, with "::" replaced by "." ("TestK.test_k"), or "ERROR collecting <path>".
    It ends at the next header or at a line starting with "=".
    If more than max_failures: a last line "- ... and N more failing tests".
    Join with newlines. If the result is longer than max_chars, cut it so that, with
    "\\n...[truncated]" appended, it is exactly max_chars long.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement format_feedback")
