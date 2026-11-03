"""Plain data types shared by every part of loopkit.

A loop is: a Task, a Generator that proposes Candidates, a list of Verifiers that
turn a candidate into Evidence, and a stop policy that reads the history of
IterationRecords and returns a StopDecision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Task:
    """One small coding task: a spec, a starting file, visible tests, hidden checks."""

    id: str
    title: str
    spec: str
    root: Path
    module: str = "solution.py"
    smoke: str = ""  # a Python expression the weak "it runs" verifier evaluates
    smoke_imports: str = ""
    impossible: bool = False  # spec and visible tests contradict on purpose (lesson 7, exercise 7)

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def _files_under(self, sub: str) -> dict[str, str]:
        base = self.root / sub
        if not base.exists():
            return {}
        return {f"{sub}/{p.relative_to(base).as_posix()}": p.read_text(encoding="utf-8")
                for p in sorted(base.rglob("*.py"))}

    @property
    def visible_tests(self) -> dict[str, str]:
        """Pristine visible tests, keyed by workspace path (e.g. tests/test_visible.py)."""
        return self._files_under("tests")

    @property
    def hidden_tests(self) -> dict[str, str]:
        """Checks the generator never sees (property-based tests and edge cases)."""
        return self._files_under("hidden")

    def starter_files(self) -> dict[str, str]:
        """What the generator starts from: the buggy module plus the visible tests."""
        files = {self.module: self.read(f"starter/{self.module}")}
        files.update(self.visible_tests)
        return files

    def reference_source(self) -> str:
        return self.read(f"reference/{self.module}")


@dataclass
class Candidate:
    """What a generator proposes: new file contents (None = delete the file)."""

    files: dict[str, Optional[str]]
    notes: str = ""
    gave_up: bool = False  # the generator says the task cannot be solved as specified
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    estimated: bool = False  # tokens/cost are estimates (scripted generator), not billed usage
    label: str = ""  # scripted generators name the step ("honest", "cheat: skip marker", ...)


@dataclass
class Evidence:
    """One verifier's verdict on one candidate."""

    verifier: str
    passed: bool
    score: float  # 0..1, used to measure progress between iterations
    required: bool = True  # only required verifiers decide "solved"
    summary: str = ""  # one line for logs and dashboards
    output: str = ""  # raw tool output (pytest stdout, ruff output, ...)
    kind: str = "generic"  # pytest | runs | lint | guard | generic
    passing: list[str] = field(default_factory=list)  # test ids that passed (for regression checks)
    failing: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)  # guard findings
    duration_s: float = 0.0
    flaky: bool = False  # passed only on a rerun
    skipped: bool = False  # the tool is not installed, so nothing was checked

    def to_log(self, max_output: int = 2000) -> dict[str, Any]:
        d = asdict(self)
        if len(d["output"]) > max_output:
            d["output"] = d["output"][:max_output] + "\n...[cut]"
        return d


@dataclass
class Budget:
    """Every limit is optional except iterations. patience and max_tamper feed the policy."""

    max_iterations: int = 6
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_seconds: Optional[float] = None
    patience: int = 2  # iterations without a new best score before "no_progress"
    max_tamper: int = 2  # tampering iterations before the loop stops and asks a human


@dataclass
class IterationRecord:
    """What the stop policy sees about one iteration. Per-iteration values, not totals."""

    iteration: int
    score: float
    solved: bool
    candidate_hash: str
    tokens: int = 0
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    tampered: bool = False


@dataclass
class StopDecision:
    stop: bool
    reason: str  # "continue" when stop is False


@dataclass
class LoopResult:
    task_id: str
    solved: bool  # according to the loop's own verifiers
    stop_reason: str
    iterations: int
    best_score: float
    final_files: dict[str, str]
    history: list[IterationRecord]
    tokens: int
    cost_usd: float
    elapsed_s: float
    audit_passed: Optional[bool] = None  # the independent audit (pristine + hidden tests)
    audit_summary: str = ""
    tamper_iterations: int = 0
    solved_at: Optional[int] = None  # first iteration where the loop declared success


def candidate_hash(files: dict[str, Optional[str]]) -> str:
    """Stable short hash of a set of files; whitespace at line ends is ignored."""
    norm = {k: ("\n".join(line.rstrip() for line in v.strip().splitlines()) if v is not None else None)
            for k, v in sorted(files.items())}
    return hashlib.sha256(json.dumps(norm, sort_keys=True).encode()).hexdigest()[:12]
