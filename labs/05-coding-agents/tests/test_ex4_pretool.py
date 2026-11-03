"""Exercise 4: check_path and pre_tool_use, including the exact JSON shape Claude Code expects."""

import json
import os

import pytest
from lab05_helpers import event

from mine import check_path, pre_tool_use


# ---------------------------------------------------------------- check_path
@pytest.mark.parametrize("path", [".env", "app/../.env", ".env.local", "secrets/prod.json", "deploy/server.pem"])
def test_secrets_denied_for_read_and_write(project, path):
    for write in (False, True):
        v = check_path(path, project, write)
        assert v is not None and v[0] == "deny", (path, write, v)


def test_absolute_secret_path(project):
    assert check_path(os.path.join(project, ".env"), project, False)[0] == "deny"


def test_template_is_fine(project):
    assert check_path(".env.example", project, False) is None
    assert check_path(".env.example", project, True) is None


def test_ordinary_files(project):
    assert check_path("app/policy.py", project, True) is None
    assert check_path(os.path.join(project, "tests", "test_new.py"), project, True) is None
    assert check_path("README.md", project, False) is None


@pytest.mark.parametrize("path", [".claude/settings.json", ".claude/hooks/guard.py", ".git/config", "app/../.git/hooks/pre-commit", "uv.lock"])
def test_protected_for_writing_only(project, path):
    assert check_path(path, project, True)[0] == "deny"
    assert check_path(path, project, False) is None


def test_write_outside_project(project):
    assert check_path("/etc/cron.d/x", project, True)[0] == "deny"
    assert check_path("../outside.txt", project, True)[0] == "deny"
    assert check_path("/etc/hostname", project, False) is None  # reads outside: not our business


def test_symlink_into_secret(project):
    os.symlink(os.path.join(project, ".env"), os.path.join(project, "config.txt"))
    assert check_path("config.txt", project, False)[0] == "deny"


def test_symlink_pointing_outside(project, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    os.symlink(outside, os.path.join(project, "link"))
    assert check_path("link/file.py", project, True)[0] == "deny"


def test_empty_path(project):
    assert check_path("", project, True) is None


# ---------------------------------------------------------------- pre_tool_use
def _decision(out):
    assert out is not None
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecisionReason"].startswith("repoguard: ")
    json.dumps(out)  # must be serializable
    return hso["permissionDecision"]


def test_exact_shape(project):
    out = pre_tool_use(event("PreToolUse", "Bash", {"command": "cat .env"}), project)
    assert set(out) == {"hookSpecificOutput"}
    assert set(out["hookSpecificOutput"]) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}
    assert _decision(out) == "deny"


@pytest.mark.parametrize("tool,ti,expected", [
    ("Bash", {"command": "rm -rf ~", "description": "clean"}, "deny"),
    ("Bash", {"command": "git push origin main"}, "ask"),
    ("Bash", {"command": "make test"}, None),
    ("Edit", {"file_path": "{p}/.claude/settings.json", "old_string": "a", "new_string": "b"}, "deny"),
    ("Edit", {"file_path": "{p}/app/policy.py", "old_string": "a", "new_string": "b"}, None),
    ("Write", {"file_path": "/etc/cron.d/x", "content": "x"}, "deny"),
    ("Write", {"file_path": "{p}/tests/test_x.py", "content": "def test_x(): pass\n"}, None),
    ("MultiEdit", {"file_path": "{p}/.git/config", "edits": []}, "deny"),
    ("NotebookEdit", {"notebook_path": "{p}/secrets/n.ipynb", "new_source": ""}, "deny"),
    ("Read", {"file_path": "{p}/.env"}, "deny"),
    ("Read", {"file_path": "{p}/.env.example"}, None),
    ("Grep", {"pattern": "KEY", "path": "{p}/secrets"}, "deny"),
    ("Grep", {"pattern": "auto_approve"}, None),
    ("Glob", {"pattern": "**/*.py"}, None),
    ("WebFetch", {"url": "https://example.com", "prompt": "x"}, None),
])
def test_tools(project, tool, ti, expected):
    ti = {k: (v.replace("{p}", project) if isinstance(v, str) else v) for k, v in ti.items()}
    out = pre_tool_use(event("PreToolUse", tool, ti, cwd=project), project)
    if expected is None:
        assert out is None
    else:
        assert _decision(out) == expected


def test_other_events_ignored(project):
    assert pre_tool_use(event("PostToolUse", "Bash", {"command": "cat .env"}), project) is None
    assert pre_tool_use(event("UserPromptSubmit", "", {}), project) is None
