"""Tests for the tangled version, written the only way it allows: a real HTTP
mock server, monkeypatched module internals and the real filesystem.

Count the monkeypatches, notice what cannot be asserted (created_at, "the model
was not called" without counting HTTP requests), and notice which test is slow
and why. Exercise 1 measures this file; exercise 3 measures the same scenarios
after the refactor.
"""

import sys
from pathlib import Path

import pytest

LEGACY = Path(__file__).resolve().parents[1]
ROOT = LEGACY.parents[2]
sys.path[:0] = [str(ROOT), str(LEGACY)]

import llmkit.client  # noqa: E402
import tangled  # noqa: E402
from mockllm import MockConfig, start_in_thread  # noqa: E402

REPLY = "Full-time employees get 14 paid vacation days in their first year [vacation_policy.md]."


@pytest.fixture(scope="module")
def server():
    srv, url = start_in_thread(MockConfig())
    yield srv, url
    srv.shutdown()


@pytest.fixture
def env(server, monkeypatch, tmp_path):
    srv, url = server
    srv.state.cfg = MockConfig(ttft=0, tps=0, reply=REPLY)
    srv.state.reset()
    monkeypatch.setenv("BRAIN_MODEL", "mock:mock-model")          # 1: which model
    monkeypatch.setattr(llmkit.client, "MOCK_URL", url)            # 2: where the mock lives (an llmkit internal!)
    monkeypatch.setattr(tangled, "CACHE_PATH", tmp_path / "c.json")  # 3: do not touch ~/.cache
    monkeypatch.setattr(tangled, "LOG_PATH", tmp_path / "brain.log")  # 4: do not write brain.log in the cwd
    return srv


def calls(srv):
    return srv.state.stats()["requests"]


def test_answers_with_citations(env):
    r = tangled.answer_question("How many vacation days do I get in my first year?", "dana@acme.example", "r1")
    assert r["status"] == "answered"
    assert r["citations"] == ["vacation_policy.md"]
    assert calls(env) == 1


def test_refuses_salary_questions_without_calling_the_model(env):
    r = tangled.answer_question("What is Moshe's salary?", "dana@acme.example", "r2")
    assert r["status"] == "refused"
    assert calls(env) == 0


def test_refuses_non_employees(env):
    r = tangled.answer_question("How many vacation days?", "someone@gmail.com", "r3")
    assert r["status"] == "refused"


def test_no_context(env):
    r = tangled.answer_question("Who won the football match yesterday?", "dana@acme.example", "r4")
    assert r["status"] == "no_context"
    assert calls(env) == 0


def test_same_request_id_is_answered_once(env):
    tangled.answer_question("How many vacation days do I get in my first year?", "dana@acme.example", "r5")
    r = tangled.answer_question("How many vacation days do I get in my first year?", "dana@acme.example", "r5")
    assert r["status"] == "answered"
    assert calls(env) == 1


def test_model_down_degrades(env):
    # 529 on every call. llmkit's default RetryPolicy really sleeps between its 4 attempts,
    # and nothing in tangled.py lets a test pass a different policy. This test is slow.
    env.state.cfg = MockConfig(ttft=0, tps=0, fail_first=100, status=529)
    r = tangled.answer_question("Can I work remotely from abroad?", "dana@acme.example", "r6")
    assert r["status"] == "degraded"
    assert "remote_work_policy.md" in r["citations"]
