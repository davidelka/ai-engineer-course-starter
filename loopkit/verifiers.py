"""Verifiers: each turns a candidate into Evidence, using a real tool.

    RunsVerifier       the weakest oracle: "it imports and runs once without crashing"
    PytestVerifier     pytest + junit XML; either in the candidate's own workspace (the
                       candidate can edit those tests) or in a clean room with pristine
                       copies of the tests (the candidate controls only the module)
    RuffVerifier       ruff: syntax errors and undefined names
    MypyVerifier       mypy type check (optional)
    GuardVerifier      did the candidate tamper with the tests? (see guard.py)
    Flaky / Rerun      wrappers to inject flakiness and to mitigate it with reruns

Presets: weak, tests, strong (see make_verifiers).
"""

from __future__ import annotations

import importlib.util
import random
import time
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Callable

from .guard import find_tampering, is_test_path
from .types import Evidence, Task
from .workspace import python, room, run_cmd

HYPOTHESIS_CONFTEST = '''\
from hypothesis import settings

# Reproducible evidence: the same candidate always gets the same verdict.
settings.register_profile("oracle", derandomize=True, database=None, deadline=None, max_examples=60)
settings.load_profile("oracle")
'''

PYTEST_ARGS = ["-q", "--tb=short", "-rfE", "--no-header", "-p", "no:cacheprovider"]


class Verifier:
    name = "verifier"
    kind = "generic"
    required = True

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:  # pragma: no cover - interface
        raise NotImplementedError

    def _ev(self, passed: bool, score: float, summary: str, output: str = "", t0: float = 0.0, **kw) -> Evidence:
        return Evidence(verifier=self.name, passed=passed, score=score, required=self.required, summary=summary,
                        output=output, kind=self.kind, duration_s=round(time.perf_counter() - t0, 3), **kw)


class RunsVerifier(Verifier):
    """Weak oracle: import the module and evaluate the task's smoke expression once."""

    name, kind = "runs", "runs"

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        t0 = time.perf_counter()
        mod = PurePosixPath(task.module).stem
        code = f"{task.smoke_imports}\nfrom {mod} import *\nresult = {task.smoke or 'None'}\nprint(repr(result))"
        with room({task.module: files.get(task.module, "")}, pytest_ini=False) as d:
            r = run_cmd([python(), "-c", code], d, timeout=20)
        ok = r.code == 0
        return self._ev(ok, 1.0 if ok else 0.0, "ran" if ok else "crashed", r.out[-1500:], t0)


def parse_junit(xml_text: str) -> tuple[list[str], list[str], list[str]]:
    """(passed, failed_or_error, skipped) test ids as 'file.py::name'."""
    root = ET.fromstring(xml_text)
    passed, failed, skipped = [], [], []
    for tc in root.iter("testcase"):
        cls = tc.get("classname", "")
        parts = cls.split(".")
        # classname is 'tests.test_visible' or 'tests.test_visible.TestK'
        idx = next((i for i, p in enumerate(parts) if p.startswith("test_") or p.endswith("_test")), len(parts) - 1)
        file = "/".join(parts[: idx + 1]) + ".py"
        name = "::".join(parts[idx + 1:] + [tc.get("name", "")])
        tid = f"{file}::{name}"
        if tc.find("failure") is not None or tc.find("error") is not None:
            failed.append(tid)
        elif tc.find("skipped") is not None:
            skipped.append(tid)
        else:
            passed.append(tid)
    return passed, failed, skipped


class PytestVerifier(Verifier):
    """Run pytest and read the result from junit XML (counts) and stdout (feedback).

    clean_room=False: run in the candidate's workspace, with whatever tests it has now.
        Exit code 0 counts as a pass, exactly like a naive CI job: skipped tests do not fail it.
    clean_room=True: copy ONLY the module into a fresh folder, plus pristine copies of the
        selected test sets. The candidate's edits to tests cannot reach this verifier.
    """

    kind = "pytest"

    def __init__(self, name: str, *, sets: tuple[str, ...] = ("tests",), clean_room: bool = False,
                 skips_fail: bool = False, required: bool = True, timeout: float = 90.0):
        self.name, self.sets, self.clean_room = name, sets, clean_room
        self.skips_fail, self.required, self.timeout = skips_fail, required, timeout

    def files_for(self, task: Task, files: dict[str, str]) -> dict[str, str]:
        if not self.clean_room:
            return dict(files)
        out = {task.module: files.get(task.module, "")}
        for s in self.sets:
            out.update(task.visible_tests if s == "tests" else task.hidden_tests if s == "hidden" else {})
        if "hidden" in self.sets:
            out["conftest.py"] = HYPOTHESIS_CONFTEST
        return out

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        t0 = time.perf_counter()
        room_files = self.files_for(task, files)
        targets = [s for s in self.sets if any(p.startswith(s + "/") for p in room_files)]
        if not targets:
            return self._ev(False, 0.0, "no test files", "no tests ran", t0)
        with room(room_files) as d:
            r = run_cmd([python(), "-m", "pytest", *PYTEST_ARGS, "--junitxml=_junit.xml", *targets], d, self.timeout)
            xml = (d / "_junit.xml").read_text(encoding="utf-8") if (d / "_junit.xml").exists() else ""
        passed, failed, skipped = parse_junit(xml) if xml else ([], [], [])
        counted = len(passed) + len(failed) + (len(skipped) if self.skips_fail else 0)
        score = len(passed) / counted if counted else 0.0
        ok = r.code == 0 and not (self.skips_fail and skipped) and counted > 0
        if r.timed_out:
            ok, score = False, 0.0
        summary = f"{len(passed)} passed, {len(failed)} failed" + (f", {len(skipped)} skipped" if skipped else "")
        if r.code not in (0, 1) and not failed:
            summary = f"pytest exit code {r.code}" + (" (timeout)" if r.timed_out else "")
        return self._ev(ok, score, summary, r.out, t0, passing=passed, failing=failed)


class RuffVerifier(Verifier):
    """ruff check, limited to rules that mean "this code is broken": syntax errors, undefined names."""

    name, kind = "lint", "lint"
    RULES = "E9,F63,F7,F82"

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        t0 = time.perf_counter()
        if importlib.util.find_spec("ruff") is None:
            return self._ev(True, 1.0, "ruff not installed: skipped", t0=t0, skipped=True)
        with room({task.module: files.get(task.module, "")}, pytest_ini=False) as d:
            r = run_cmd([python(), "-m", "ruff", "check", "--no-cache", "--select", self.RULES,
                         "--output-format", "concise", task.module], d, 30)
        ok = r.code == 0
        return self._ev(ok, 1.0 if ok else 0.0, "clean" if ok else "lint errors", r.out.strip(), t0)


class MypyVerifier(Verifier):
    name, kind = "types", "types"

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        t0 = time.perf_counter()
        if importlib.util.find_spec("mypy") is None:
            return self._ev(True, 1.0, "mypy not installed: skipped", t0=t0, skipped=True)
        with room({task.module: files.get(task.module, "")}, pytest_ini=False) as d:
            r = run_cmd([python(), "-m", "mypy", "--ignore-missing-imports", "--no-error-summary",
                         "--cache-dir=/dev/null", task.module], d, 60)
        ok = r.code == 0
        return self._ev(ok, 1.0 if ok else 0.0, "typed" if ok else "type errors", r.out.strip(), t0)


class GuardVerifier(Verifier):
    """Fails when the candidate tampered with the tests or special-cased test inputs."""

    name, kind = "guard", "guard"

    def __init__(self, guard: Callable[..., list[str]] = find_tampering):
        self.guard = guard

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        t0 = time.perf_counter()
        cand_tests = {p: c for p, c in files.items() if is_test_path(p)}
        findings = list(self.guard(task.visible_tests, cand_tests, files.get(task.module), task.spec))
        ok = not findings
        return self._ev(ok, 1.0 if ok else 0.0, "tests intact" if ok else f"{len(findings)} finding(s)",
                        "\n".join(findings), t0, findings=findings)


class Flaky(Verifier):
    """Fault injection: with probability p, a passing run is reported as a spurious failure."""

    def __init__(self, inner: Verifier, p: float, rng: random.Random):
        self.inner, self.p, self.rng = inner, p, rng
        self.name, self.kind, self.required = inner.name, inner.kind, inner.required

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        ev = self.inner.verify(task, files)
        if ev.passed and self.rng.random() < self.p:
            victim = ev.passing[-1] if ev.passing else "tests/test_visible.py::test_unknown"
            fake = (f"F\n{'_' * 10} {victim.split('::')[-1]} {'_' * 10}\n    conn = fixture_db()\n"
                    f"E   TimeoutError: fixture database did not answer in 2.0s\n"
                    f"FAILED {victim} - TimeoutError: fixture database did not answer in 2.0s\n"
                    f"1 failed, {max(0, len(ev.passing) - 1)} passed in 2.10s\n")
            n = max(1, len(ev.passing))
            return replace(ev, passed=False, score=(n - 1) / n,
                           summary=f"{n - 1} passed, 1 failed (injected flaky failure)",
                           output=fake, passing=ev.passing[:-1], failing=[victim])
        return ev


class Rerun(Verifier):
    """Mitigation: rerun a failing verifier up to n times. A later pass counts, marked flaky."""

    def __init__(self, inner: Verifier, reruns: int):
        self.inner, self.reruns = inner, reruns
        self.name, self.kind, self.required = inner.name, inner.kind, inner.required

    def verify(self, task: Task, files: dict[str, str]) -> Evidence:
        ev = self.inner.verify(task, files)
        for _ in range(self.reruns):
            if ev.passed:
                break
            again = self.inner.verify(task, files)
            if again.passed:
                return replace(again, flaky=True, summary=again.summary + " (passed on rerun: flaky)")
            ev = again
        return ev


TIERS = ("weak", "tests", "strong")


def make_verifiers(tier: str, *, guard: Callable[..., list[str]] = find_tampering, flaky: float = 0.0,
                   reruns: int = 0, seed: int = 7, extra: tuple[str, ...] = ()) -> list[Verifier]:
    """weak:   it runs.
    tests:  visible tests, run in the candidate's workspace (the candidate can edit them).
    strong: tamper guard + lint + pristine visible tests + hidden property tests, in clean rooms.
    flaky/reruns wrap the pytest verifiers; extra may add "types" (mypy)."""
    if tier == "weak":
        vs: list[Verifier] = [RunsVerifier()]
    elif tier == "tests":
        vs = [PytestVerifier("visible_tests", sets=("tests",), clean_room=False)]
    elif tier == "strong":
        vs = [GuardVerifier(guard), RuffVerifier(),
              PytestVerifier("visible_tests", sets=("tests",), clean_room=True, skips_fail=True),
              PytestVerifier("hidden_tests", sets=("hidden",), clean_room=True, skips_fail=True)]
    else:
        raise ValueError(f"tier must be one of {TIERS}")
    if "types" in extra:
        vs.append(MypyVerifier())
    rng = random.Random(seed)
    out: list[Verifier] = []
    for v in vs:
        if v.kind == "pytest" and flaky > 0:
            v = Flaky(v, flaky, rng)
        if v.kind == "pytest" and reruns > 0:
            v = Rerun(v, reruns)
        out.append(v)
    return out


def audit(task: Task, files: dict[str, str]) -> Evidence:
    """The independent check after the loop: pristine visible tests + hidden checks, clean room."""
    v = PytestVerifier("audit", sets=("tests", "hidden"), clean_room=True, skips_fail=True)
    return v.verify(task, files)


def gate(evidence: list[Evidence]) -> tuple[bool, float]:
    """(solved, score): solved when every required, non-skipped verifier passed; score = mean of their scores."""
    req = [e for e in evidence if e.required and not e.skipped]
    if not req:
        return False, 0.0
    return all(e.passed for e in req), sum(e.score for e in req) / len(req)


def tampered(evidence: list[Evidence]) -> bool:
    return any(e.kind == "guard" and not e.passed for e in evidence)
