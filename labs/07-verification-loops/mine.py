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

    history: one IterationRecord per iteration so far, oldest first, with PER-ITERATION
    values: iteration, score (0..1), solved, candidate_hash, tokens, cost_usd, elapsed_s,
    tampered. budget: max_iterations, max_tokens, max_cost_usd, max_seconds (None = no
    limit), patience, max_tamper.

    Returns StopDecision(stop, reason). When several reasons apply, the earlier one in
    this list wins:
      "continue" (stop=False)  empty history
      "solved"                 the last iteration is solved and not tampered
      "tampering"              at least max_tamper tampered iterations
      "budget_iterations"      at least max_iterations iterations
      "budget_tokens"          total tokens reached max_tokens
      "budget_cost"            total cost reached max_cost_usd, or one more iteration
                               costing as much as the last one would exceed it
      "budget_time"            total elapsed_s reached max_seconds
      "no_change"              the last candidate is identical to the previous one
      "oscillation"            the last candidate repeats an earlier one (not the previous)
      "no_progress"            (patience > 0) the last `patience` iterations did not beat
                               the best score before them
      "continue" (stop=False)  none of the above

    Stuck? HINTS.md -> should_stop
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
    A test file is test_*.py, *_test.py or conftest.py. A test is a top-level function
    test*, or a method test* in a class Test*, named "Class::method".

    Returns a SORTED list of UNIQUE strings:
      deleted_file:<path>            a pristine test file is missing
      new_conftest:<path>            a conftest.py that the original did not have
      unparsable_test:<path>         a candidate test file that does not parse (no other checks on it)
      removed_test:<path>::<name>    a pristine test is gone
      skip_marker:<path>::<name>     the test gained a skip/skipif/xfail marker or calls pytest.skip/xfail
      skip_marker:<path>::*          a module-level pytestmark skip was added
      trivial_assert:<path>::<name>  assert of a truthy constant, or assert X == X
      weakened_test:<path>::<name>   fewer real checks (non-trivial asserts, pytest.raises blocks)
      modified_test:<path>::<name>   the test's code differs from the pristine version
      special_case:<literal>         `source` compares against, or uses as a dict key, a string
                                     literal (3+ chars) taken from call arguments in the ORIGINAL
                                     tests, which is not in `spec`
    One test can get several findings (assert True in place of a real assert gives
    trivial_assert, weakened_test and modified_test).

    Stuck? HINTS.md -> find_tampering
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement find_tampering")


# ------------------------------------------------------------------ exercise 5
def format_feedback(pytest_output: str, max_failures: int = 5, max_chars: int = 1500) -> str:
    """Turn raw output of `pytest -q --tb=short -rfE --no-header` into compact feedback.

    Returns lines joined with newlines:
      line 1: pytest's final counts without the timing, e.g. "2 failed, 6 passed";
              "no tests ran" if the output says so; else "pytest output had no summary line".
      then, per FAILED/ERROR entry of the short summary, in order, at most max_failures:
          - <file name>::<rest of the node id>       e.g. "- test_visible.py::TestK::test_k"
          - <file name> (collection error)            for an ERROR without "::"
        followed by detail lines indented by 4 spaces, taken from that test's traceback:
          the source line that failed; then the "E " lines without the "E" prefix, with
          absolute paths in quotes cut to the file name, nothing from "Failing test case:" or
          "Falsifying example:" on, and only the first 2 and last 2 if more than 4 remain;
          with no "E " lines, the message after " - " in the summary line, if any.
      last, if there were more failures: "- ... and N more failing tests".
    If longer than max_chars: cut so that, with "\n...[truncated]" appended, the result is
    exactly max_chars long.

    Stuck? HINTS.md -> format_feedback
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement format_feedback")
