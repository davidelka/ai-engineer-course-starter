"""multikit: multi-agent patterns on top of agentkit (lesson 18).

    from multikit import build, run_set, aggregate_runs
    res = build("supervisor", "fake").run("Which rotation covers flow-scheduler? ...", task_id="x01")
    res.text, res.runs, aggregate_runs(res.records)

domains.py      the three domains, a keyword classifier and splitter (baseline + fake models)
specialists.py  hr / it_access / oncall: system prompts, tool subsets, make_specialist, make_single
router.py       RouteDecision (structured output), decide_route (threshold -> clarify), Router
supervisor.py   Supervisor: delegate_to_<worker> tools, parallel delegation, verify none|llm|code
handoff.py      HandoffSummary, make_handoff_brief (the contract), HandoffRunner (triage -> chain)
fanout.py       FanOut: plan -> parallel research workers -> synthesis with citation check
critic.py       CriticLoop: writer + code checks + critic rubric, max_rounds
attribution.py  AgentRun / MultiResult, aggregate_runs (per-agent cost), merge_for_scoring
faults.py       corrupt a worker's answer (the failure exercise)
fake.py         deterministic offline "models" for every role
patterns.py     build / run_set / score_multi / attribute_failure
"""

from .attribution import AgentRun, MultiResult, aggregate_runs, format_attribution, merge_for_scoring
from .critic import DEFAULT_RUBRIC, CriticLoop, Review
from .domains import DOMAINS, domains_of, split_by_domain
from .fanout import FanOut, SlowLLM, citations, score_research
from .faults import CORRUPTIONS, corrupt_text
from .handoff import HandoffError, HandoffRunner, HandoffSummary, make_handoff_brief, render_unchecked
from .patterns import PATTERNS, attribute_failure, build, run_set, score_multi
from .router import RouteChoice, RouteDecision, Router, classify, decide_route
from .specialists import SPECIALISTS, full_registry, make_single, make_specialist
from .supervisor import Supervisor, evidence_conflicts

__all__ = ["AgentRun", "MultiResult", "aggregate_runs", "format_attribution", "merge_for_scoring", "DEFAULT_RUBRIC",
           "CriticLoop", "Review", "DOMAINS", "domains_of", "split_by_domain", "FanOut", "SlowLLM", "citations",
           "score_research", "CORRUPTIONS", "corrupt_text", "HandoffError", "HandoffRunner", "HandoffSummary",
           "make_handoff_brief", "render_unchecked", "PATTERNS", "attribute_failure", "build", "run_set",
           "score_multi", "RouteChoice", "RouteDecision", "Router", "classify", "decide_route", "SPECIALISTS",
           "full_registry", "make_single", "make_specialist", "Supervisor", "evidence_conflicts"]
