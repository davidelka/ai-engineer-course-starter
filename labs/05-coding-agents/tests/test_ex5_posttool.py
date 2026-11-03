"""Exercise 5: post_tool_use with a fake command runner, then once for real against sample-service."""

import os
import sys

from lab05_helpers import event

from mine import post_tool_use


class FakeRun:
    """Records commands; answers from a list of (exit code, output) in order."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, cmd, cwd):
        self.calls.append((cmd, cwd))
        return self.answers.pop(0) if self.answers else (0, "")


RUFF = lambda rel: [sys.executable, "-m", "ruff", "check", "--quiet", "--output-format", "concise", rel]  # noqa: E731
PYTEST = lambda target: [sys.executable, "-m", "pytest", "-x", "-q", "--tb=short", target]  # noqa: E731


def edit(project, rel, tool="Edit"):
    return event("PostToolUse", tool, {"file_path": os.path.join(project, rel), "old_string": "a", "new_string": "b"}, cwd=project)


def test_all_good_app_file_with_matching_test(project):
    run = FakeRun((0, ""), (0, "8 passed"))
    out = post_tool_use(edit(project, "app/policy.py"), project, run)
    assert run.calls == [(RUFF("app/policy.py"), project), (PYTEST("tests/test_policy.py"), project)]
    assert out == {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                          "additionalContext": "repoguard: ruff clean and tests passed for app/policy.py (tests/test_policy.py)"}}


def test_app_file_without_matching_test_runs_suite(project):
    run = FakeRun((0, ""), (0, ""))
    post_tool_use(edit(project, "app/catalog.py"), project, run)
    assert run.calls[1][0] == PYTEST("tests")


def test_test_file_runs_itself(project):
    run = FakeRun((0, ""), (0, ""))
    post_tool_use(edit(project, "tests/test_api.py", tool="Write"), project, run)
    assert run.calls[1][0] == PYTEST("tests/test_api.py")


def test_ruff_failure_blocks_and_skips_tests(project):
    run = FakeRun((1, "app/policy.py:5:8: F401 `os` imported but unused"))
    out = post_tool_use(edit(project, "app/policy.py"), project, run)
    assert len(run.calls) == 1
    assert out == {"decision": "block", "reason": "ruff check failed for app/policy.py:\napp/policy.py:5:8: F401 `os` imported but unused"}


def test_test_failure_blocks_with_command(project):
    run = FakeRun((0, ""), (1, "FAILED tests/test_policy.py::test_route"))
    out = post_tool_use(edit(project, "app/policy.py"), project, run)
    assert out["decision"] == "block"
    assert out["reason"] == ("tests failed after editing app/policy.py (python -m pytest -x -q --tb=short tests/test_policy.py):\n"
                             "FAILED tests/test_policy.py::test_route")


def test_no_tests_collected_is_a_pass(project):
    out = post_tool_use(edit(project, "app/policy.py"), project, FakeRun((0, ""), (5, "no tests ran")))
    assert "additionalContext" in out["hookSpecificOutput"]


def test_long_output_is_cut(project):
    long = "x" * 1000 + "END" + "y" * 2000
    out = post_tool_use(edit(project, "app/policy.py"), project, FakeRun((1, long)))
    body = out["reason"].split(":\n", 1)[1]
    assert body == "..." + long[-1500:]


def test_ignored(project):
    run = FakeRun()
    assert post_tool_use(edit(project, "README.md"), project, run) is None  # not Python
    assert post_tool_use(edit(project, "docs/x.py"), project, run) is None  # linted, nothing to test
    run2 = FakeRun()
    assert post_tool_use(event("PostToolUse", "Read", {"file_path": os.path.join(project, "app/main.py")}), project, run2) is None
    assert post_tool_use(event("PreToolUse", "Edit", {"file_path": os.path.join(project, "app/main.py")}), project, run2) is None
    assert post_tool_use(event("PostToolUse", "Write", {"file_path": "/tmp/elsewhere.py"}), project, run2) is None
    assert run2.calls == []


def test_python_file_outside_app_and_tests(project):
    run = FakeRun((0, ""))
    out = post_tool_use(edit(project, "scripts/seed.py", tool="Write"), project, run)
    assert out is None
    assert run.calls == [(RUFF("scripts/seed.py"), project)]  # linted, but nothing to test


def test_real_run_against_sample_service(project):
    """No fake: ruff and pytest really run on the copy of sample-service."""
    out = post_tool_use(edit(project, "app/policy.py"), project)
    assert out is not None and "additionalContext" in out["hookSpecificOutput"], out
    path = os.path.join(project, "app", "catalog.py")
    with open(path) as f:
        text = f.read()
    with open(path, "w") as f:
        f.write(text.replace('    "jira",\n', ""))
    out = post_tool_use(edit(project, "app/catalog.py"), project)
    assert out["decision"] == "block" and "tests failed" in out["reason"]
