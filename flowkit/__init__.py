"""flowkit: the Acme access-request approval workflow on LangGraph (lesson 16).

state.py   FlowState (TypedDict with reducers), IntakeRequest schema, merge_audit / add_usage
fake.py    FakeLLM: an offline stand-in for llmkit.LLM (rule-based intake, template risk summary)
nodes.py   Deps, the node functions, the approval gate (interrupt), routing functions
graph.py   build_graph(deps, impl=None, checkpointer=None, retry=...), open_checkpointer(path)
runner.py  start / resume / summary / pending / history: what the lab CLI scripts are made of
store.py   flow_audit, flow_outbox and conditional status updates in the requests DB
faults.py  with_faults(registry, ...): tool timeouts and errors on purpose

state.py and fake.py need only pydantic and llmkit; the rest needs `langgraph` and
`langgraph-checkpoint-sqlite` (labs/16-workflows/requirements.txt).
"""

from .fake import FakeLLM, heuristic_extract
from .state import TERMINAL, FlowState, IntakeRequest, add_usage, make_state, merge_audit

try:  # LangGraph parts: optional at import time so state/fake work without it
    from .graph import DEFAULT_RETRY, build_graph, open_checkpointer
    from .nodes import Deps, ToolUnavailable
except ImportError:  # pragma: no cover - langgraph not installed
    pass

__all__ = ["FakeLLM", "heuristic_extract", "TERMINAL", "FlowState", "IntakeRequest", "add_usage", "make_state",
           "merge_audit", "DEFAULT_RETRY", "build_graph", "open_checkpointer", "Deps", "ToolUnavailable"]
