"""toolkit: Acme tools for Company Brain (lesson 14 onward).

    from toolkit import acme_registry, Executor, run_tool_loop
    reg = acme_registry()
    result = run_tool_loop(LLM("anthropic:claude-haiku-5-5"), "Who approves Figma editor for Dana Levi?", reg)

registry.py   ToolSpec / Registry / ToolError: name, description, Pydantic input model, function, safety flags
acme.py       the six Acme tools over data/acme/corpus/structured/acme.db (+ a local requests store)
executor.py   execute_tool (validate, authorize, timeout, errors as data) and Executor (parallel, trace)
loop.py       run_tool_loop: the round trip for one question, with max_rounds
confirm.py    ConfirmationGate: single-use tokens bound to the exact call, for side-effect tools
guards.py     spotlight / scan / output_violations / Taint: layers against prompt injection via tool results
"""

from .acme import acme_registry, route_for
from .confirm import ConfirmationGate, call_fingerprint
from .executor import Executor, execute_tool, to_text
from .guards import Taint, output_violations, scan, spotlight
from .loop import LoopResult, run_tool_loop
from .registry import Registry, ToolError, ToolSpec

__all__ = ["acme_registry", "route_for", "ConfirmationGate", "call_fingerprint", "Executor", "execute_tool",
           "to_text", "Taint", "output_violations", "scan", "spotlight", "LoopResult", "run_tool_loop",
           "Registry", "ToolError", "ToolSpec"]
