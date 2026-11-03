"""loopkit: verification-driven improvement loops (lesson 7).

A loop = a task + a candidate generator (LLM or scripted) + verifiers that produce
evidence + a stop policy with budgets, with every iteration written to a JSONL
evidence log and an independent audit at the end.
"""

from .feedback import compose_feedback, format_feedback
from .generators import GenContext, LLMGenerator, ScriptedGenerator, build_prompt
from .guard import find_tampering
from .log import EvidenceLog, format_summary, read_records, summarize
from .policy import should_stop
from .runner import run_loop
from .tasks import load_task, load_tasks
from .types import Budget, Candidate, Evidence, IterationRecord, LoopResult, StopDecision, Task
from .verifiers import TIERS, audit, make_verifiers

__all__ = [
    "compose_feedback", "format_feedback", "GenContext", "LLMGenerator", "ScriptedGenerator", "build_prompt",
    "find_tampering", "EvidenceLog", "format_summary", "read_records", "summarize", "should_stop", "run_loop",
    "load_task", "load_tasks", "Budget", "Candidate", "Evidence", "IterationRecord", "LoopResult",
    "StopDecision", "Task", "TIERS", "audit", "make_verifiers",
]
