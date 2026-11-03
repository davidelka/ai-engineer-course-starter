"""The loop: generate -> verify -> record evidence -> decide -> feed back.

    result = run_loop(task, ScriptedGenerator("honest"), make_verifiers("strong"),
                      budget=Budget(max_iterations=5), log=EvidenceLog(path))

Design choices worth knowing (lesson 7):
- Every iteration appends one JSON line to the evidence log, BEFORE the stop decision,
  so a crash or a budget stop never loses evidence.
- Regression guard: the next attempt starts from the best candidate so far, not the
  last one, and the feedback names the checks that the last change broke.
- With a guard in the verifier list, tests are read-only: whatever the candidate did to
  them, the next attempt starts from the pristine tests again.
- After the loop, an independent audit (pristine visible tests + hidden checks) re-checks
  the final candidate, whatever verifiers the loop itself used. That is how a weak
  oracle's false "solved" becomes visible.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable, Optional

from .feedback import compose_feedback, format_feedback
from .generators import GenContext, Generator
from .guard import is_test_path
from .log import EvidenceLog
from .policy import should_stop
from .types import Budget, IterationRecord, LoopResult, StopDecision, Task, candidate_hash
from .verifiers import Verifier, audit, gate, tampered
from .workspace import apply_files

Checkpoint = Callable[[dict, StopDecision], bool]


def _passing(evidence) -> set[str]:
    return {t for e in evidence if e.kind == "pytest" for t in e.passing}


def run_loop(
    task: Task,
    generator: Generator,
    verifiers: list[Verifier],
    *,
    budget: Optional[Budget] = None,
    policy: Callable[[list[IterationRecord], Budget], StopDecision] = should_stop,
    formatter: Callable[[str], str] = format_feedback,
    feedback_mode: str = "compact",
    log: Optional[EvidenceLog] = None,
    label: str = "",
    checkpoint: Optional[Checkpoint] = None,
    ask_every: int = 0,
    on_iteration: Optional[Callable[[dict], None]] = None,
) -> LoopResult:
    budget = budget or Budget()
    run_id = uuid.uuid4().hex[:8]
    read_only = any(v.kind == "guard" for v in verifiers)
    pristine = task.visible_tests
    base = task.starter_files()
    best_files, best_score, best_passing = dict(base), -1.0, set()
    history: list[IterationRecord] = []
    previous: list[str] = []
    feedback = ""
    totals = {"tokens": 0, "cost": 0.0}
    t_start = time.perf_counter()
    solved_at: Optional[int] = None
    decision = StopDecision(False, "continue")
    final_files = dict(base)
    if log:
        log.write({"type": "run", "run_id": run_id, "label": label, "task": task.id, "generator": generator.name,
                   "verifiers": [v.name for v in verifiers], "feedback_mode": feedback_mode,
                   "budget": budget.__dict__, "impossible": task.impossible, "ts": time.time()})
    it = 0
    while True:
        it += 1
        t0 = time.perf_counter()
        ctx = GenContext(iteration=it, max_iterations=budget.max_iterations, files=dict(base),
                         feedback=feedback, previous=list(previous))
        cand = generator.generate(task, ctx)
        files = apply_files(base, cand.files)
        evidence = [v.verify(task, files) for v in verifiers]
        solved, score = gate(evidence)
        was_tampered = tampered(evidence)
        passing = _passing(evidence)
        # regression guard: checks that passed in the best candidate and fail now (even if the score held)
        regressions = sorted(best_passing - passing) if best_score >= 0 else []
        worse = best_score >= 0 and score < best_score
        h = candidate_hash({p: c for p, c in files.items() if p == task.module or is_test_path(p)})
        rec = IterationRecord(iteration=it, score=round(score, 4), solved=solved, candidate_hash=h,
                              tokens=cand.input_tokens + cand.output_tokens, cost_usd=cand.cost_usd,
                              elapsed_s=round(time.perf_counter() - t0, 3), tampered=was_tampered)
        history.append(rec)
        totals["tokens"] += rec.tokens
        totals["cost"] += rec.cost_usd
        improved = score > best_score and not was_tampered
        if improved:
            best_files, best_score, best_passing = dict(files), score, passing
        if solved and not was_tampered and solved_at is None:
            solved_at = it
        # what the next attempt starts from
        nxt = best_files if (worse or was_tampered) else files
        if read_only:
            nxt = {p: c for p, c in nxt.items() if not is_test_path(p)} | pristine
        feedback = compose_feedback(evidence, mode=feedback_mode, formatter=formatter,
                                    regressions=regressions, reverted=worse or was_tampered)
        previous.append(f"attempt {it}: score {score:.2f}" + (" (tests tampered)" if was_tampered else "")
                        + (f"; your note: {cand.notes[:140]}" if cand.notes else ""))
        decision = policy(history, budget)
        if cand.gave_up and decision.reason != "solved":
            decision = StopDecision(True, "generator_gave_up")  # a human should read why
        record = {
            "type": "iteration", "run_id": run_id, "label": label, "task": task.id, "iteration": it,
            "candidate_hash": h, "candidate_label": cand.label, "notes": cand.notes[:500],
            "files_changed": sorted(cand.files), "score": rec.score, "best_score": round(max(best_score, 0), 4),
            "solved": solved, "tampered": was_tampered, "regressions": regressions,
            "verifiers": [e.to_log() for e in evidence],
            "tokens_in": cand.input_tokens, "tokens_out": cand.output_tokens, "cost_usd": round(cand.cost_usd, 6),
            "estimated_cost": cand.estimated, "elapsed_s": rec.elapsed_s,
            "feedback_chars": len(feedback), "feedback": feedback[:3000],
            "decision": {"stop": decision.stop, "reason": decision.reason},
        }
        if log:
            log.write(record)
        if on_iteration:
            on_iteration(record)
        if decision.stop:
            final_files = files if (decision.reason == "solved") else best_files
            break
        if checkpoint and ((ask_every and it % ask_every == 0) or was_tampered):
            if not checkpoint(record, decision):
                decision = StopDecision(True, "human_stop")
                final_files = best_files
                if log:
                    log.write({"type": "checkpoint", "run_id": run_id, "iteration": it, "approved": False})
                break
        base = nxt
    au = audit(task, final_files)
    result = LoopResult(
        task_id=task.id, solved=decision.reason == "solved", stop_reason=decision.reason, iterations=it,
        best_score=round(max(best_score, 0.0), 4), final_files=final_files, history=history,
        tokens=totals["tokens"], cost_usd=totals["cost"], elapsed_s=round(time.perf_counter() - t_start, 2),
        audit_passed=au.passed, audit_summary=au.summary,
        tamper_iterations=sum(1 for r in history if r.tampered), solved_at=solved_at,
    )
    if log:
        log.write({"type": "summary", "run_id": run_id, "label": label, "task": task.id,
                   "generator": generator.name, "solved": result.solved, "solved_at": solved_at,
                   "stop_reason": result.stop_reason, "iterations": it, "best_score": result.best_score,
                   "tokens": result.tokens, "cost_usd": round(result.cost_usd, 6),
                   "estimated_cost": cand.estimated,
                   "elapsed_s": result.elapsed_s, "audit_passed": au.passed, "audit": au.summary,
                   "audit_failing": au.failing[:10], "tamper_iterations": result.tamper_iterations,
                   "impossible": task.impossible})
    return result
