"""Plain data types for agentkit (lesson 15).

An agent run is a sequence of STEPS. One step = one model call plus the tool calls it
asked for and their results. After every step the stop policy reads the whole history
(a list of StepRecord) and the Budget, and answers: continue, or stop and why.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field

from llmkit.types import Message, ToolCall, ToolResult


@dataclass
class Budget:
    """Limits for ONE run. None = not checked. Steps are always checked.

    max_steps               model calls in the act loop (the planner call is not a step)
    max_tokens              input + output tokens of every model call, planner included
    max_cost_usd            dollars, planner included
    max_seconds             wall time since the run started
    repeat_limit            the same tool call (name + identical arguments) this many
                            times in one run -> "repetition"
    no_progress_steps       this many steps in a row that produced no NEW successful
                            result -> "no_progress" (0 = off)
    max_consecutive_errors  this many steps in a row where every tool call failed ->
                            "tool_errors" (0 = off)
    """

    max_steps: int = 8
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_seconds: Optional[float] = None
    repeat_limit: int = 3
    no_progress_steps: int = 3
    max_consecutive_errors: int = 3

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StepRecord:
    """What the stop policy sees about one step. Per-step values, not running totals.

    calls / fingerprints / result_hashes are aligned: one entry per tool call.
    result_hashes[i] is None when that call FAILED (is_error), else a short hash of
    the result text, so "did this step learn anything new?" is a set lookup.
    """

    n: int
    calls: list[str] = field(default_factory=list)  # tool names, in order
    fingerprints: list[str] = field(default_factory=list)  # name + canonical arguments, hashed
    result_hashes: list[Optional[str]] = field(default_factory=list)
    errors: int = 0  # results with is_error
    final: bool = False  # the model answered in text and asked for no tools
    gave_up: bool = False  # the model called the give_up tool
    tokens: int = 0  # input + output tokens of this step's model call(s)
    cost_usd: float = 0.0
    elapsed_s: float = 0.0  # wall time of this step


@dataclass
class StopDecision:
    stop: bool
    reason: str  # "continue" when stop is False
    detail: str = ""  # one human-readable line: which limit, which call, which numbers


# ---------------------------------------------------------------- planning (structured output)
class PlanStep(BaseModel):
    id: int = Field(description="1, 2, 3, ... in execution order")
    action: str = Field(description="What to do in this step, in one short sentence")
    tool: Optional[str] = Field(description="The tool this step uses, or null for a step that only reasons or answers")
    depends_on: list[int] = Field(description="Ids of steps whose results this step needs; [] if it can run first "
                                              "(steps with no dependencies between them can run in parallel)")


class Plan(BaseModel):
    goal: str = Field(description="The user's goal in one sentence")
    steps: list[PlanStep] = Field(description="The shortest sequence of steps that reaches the goal")
    done_when: str = Field(description="How to tell that the task is complete")

    def render(self) -> str:
        lines = [f"Goal: {self.goal}"]
        for s in self.steps:
            dep = f" (after {', '.join(map(str, s.depends_on))})" if s.depends_on else ""
            tool = f" [{s.tool}]" if s.tool else ""
            lines.append(f"{s.id}. {s.action}{tool}{dep}")
        lines.append(f"Done when: {self.done_when}")
        return "\n".join(lines)


# ---------------------------------------------------------------- the result of a run
@dataclass
class AgentResult:
    text: str  # the final answer, or a note explaining why the run stopped
    stop_reason: str  # see agentkit.policy.STOP_REASONS
    detail: str = ""
    steps: int = 0  # model calls in the act loop
    history: list[StepRecord] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)  # the trajectory (same dicts as the JSONL file)
    messages: list[Message] = field(default_factory=list)
    plan: Optional[dict] = None  # the last plan (plan mode)
    replans: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    estimated_cost: bool = False  # the fake model estimates tokens; nothing was billed

    @property
    def tool_names(self) -> list[str]:
        return [c.name for c in self.calls]

    @property
    def errors(self) -> int:
        return sum(r.is_error for r in self.results)

    @property
    def success_answer(self) -> bool:
        """The run ended because the model answered (or explicitly gave up), not because a limit hit."""
        return self.stop_reason in ("final_answer", "gave_up")

    def side_effects(self) -> list[dict[str, Any]]:
        """Successful results of side-effect tools, as recorded in the trajectory."""
        out = []
        for rec in self.records:
            if rec.get("type") == "step":
                for r in rec.get("results", []):
                    if r.get("side_effect") and not r.get("is_error"):
                        out.append(r)
        return out
