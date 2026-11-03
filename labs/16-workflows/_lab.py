"""Shared bits for the lesson 16 scripts: paths, .env, model choice, building the app."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]

from llmkit import LLM, load_dotenv  # noqa: E402

DEFAULT_MODEL = "anthropic:claude-haiku-5-5"
RESULTS = LAB / "results"
REQUESTS_DB = Path(os.environ.get("FLOW_REQUESTS_DB") or RESULTS / "requests.db")
CHECKPOINTS_DB = Path(os.environ.get("FLOW_CHECKPOINTS_DB") or RESULTS / "checkpoints.db")
SAMPLES = [json.loads(line) for line in (LAB / "data" / "requests.jsonl").read_text().splitlines() if line.strip()]

# The parts of mine.py, grouped by exercise, so a script can use only what you finished.
MINE_PARTS = {"ex2": ("merge_audit", "add_usage", "route_after_file", "route_after_gate"),
              "ex3": ("intake_node", "policy_node", "file_request_node"),
              "ex5": ("approval_gate",)}


def make_llm(spec: str):
    """'fake' = flowkit.FakeLLM (offline, free). 'mock' = the course's mockllm in-process
    (used by compare.py for the free agent). Anything else = a real llmkit model."""
    load_dotenv(str(ROOT / ".env"))
    if spec == "fake":
        from flowkit import FakeLLM
        return FakeLLM()
    if spec.startswith("mock"):
        from mockllm import MockConfig, start_in_thread
        server, url = start_in_thread(MockConfig(ttft=0, tps=0, seed=1))
        provider = spec.split("-", 1)[1] if "-" in spec else "anthropic"
        llm = LLM(f"{provider}:mock-model", api_key="mock", base_url=url)
        llm._mock_server = server
        return llm
    return LLM(spec)


def mine_impl(parts: Optional[list[str]] = None):
    """A namespace with the functions from mine.py for the given exercises (default: all).
    Parts that still raise NotImplementedError would crash the run, so pick what you finished."""
    import mine
    names = [n for p in (parts or MINE_PARTS) for n in MINE_PARTS[p]]
    return SimpleNamespace(**{n: getattr(mine, n) for n in names})


def make_app(model: str = "fake", *, mine_parts: Optional[list[str]] = None, crash_in: Optional[str] = None,
             slow_s: float = 0.0, fault: str = "", tool_timeout_s: float = 5.0):
    """(app, saver, deps) on results/requests.db and results/checkpoints.db."""
    from flowkit import Deps, build_graph, open_checkpointer
    from flowkit.faults import parse_fault, with_faults
    from toolkit import acme_registry

    reg = acme_registry(requests_db=REQUESTS_DB)
    if fault:
        reg = with_faults(reg, parse_fault(fault), delay_s=0.6, timeout_s=0.2)
    deps = Deps(llm=make_llm(model), registry=reg, requests_db=REQUESTS_DB, crash_in=crash_in, slow_s=slow_s,
                tool_timeout_s=tool_timeout_s)
    saver = open_checkpointer(CHECKPOINTS_DB)
    impl = mine_impl(mine_parts) if mine_parts is not None else None
    return build_graph(deps, impl=impl, checkpointer=saver), saver, deps


def add_common_args(ap) -> None:
    ap.add_argument("--model", default=os.environ.get("FLOW_MODEL", "fake"),
                    help="fake (offline, default) or e.g. anthropic:claude-haiku-5-5")
    ap.add_argument("--mine", nargs="*", choices=list(MINE_PARTS), default=None,
                    help="use your mine.py parts (no value = all of ex2, ex3, ex5)")


def mine_parts_arg(args) -> Optional[list[str]]:
    if args.mine is None:
        return None
    return args.mine or list(MINE_PARTS)
