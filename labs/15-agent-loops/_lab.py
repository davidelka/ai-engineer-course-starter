"""Shared bits for the lesson 15 scripts: paths, model choice, registries, confirmation hooks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]

from llmkit import LLM, load_dotenv  # noqa: E402

LIVE_MODEL = "anthropic:claude-haiku-5-5"
RESULTS = LAB / "results"
TASKS = LAB / "data" / "tasks.jsonl"
MOCK_SCRIPT = LAB / "data" / "mock_script.json"


def make_llm(spec: str, *, mock_cfg: Optional[dict] = None, heuristic: Optional[dict] = None):
    """'fake'  = agentkit.FakeLLM(AcmeHeuristic): deterministic, free, tokens estimated.
    'mock' / 'mock-openai' / 'mock-gemini' = in-process mockllm with data/mock_script.json
             (real wire shapes; it only knows the scripted tasks, and is dumb on purpose).
    anything else = a live model through llmkit, e.g. anthropic:claude-haiku-5-5 (costs money)."""
    load_dotenv(str(ROOT / ".env"))
    if spec == "fake":
        from agentkit import AcmeHeuristic, FakeLLM
        return FakeLLM(AcmeHeuristic(**(heuristic or {})))
    if spec.startswith("mock"):
        from mockllm import MockConfig, start_in_thread
        cfg = MockConfig(ttft=0, tps=0, seed=1, tool_script=str(MOCK_SCRIPT), **(mock_cfg or {}))
        server, url = start_in_thread(cfg)
        provider = spec.split("-", 1)[1] if "-" in spec else "anthropic"
        llm = LLM(f"{provider}:mock-model", api_key="mock", base_url=url)
        llm._mock_server = server  # keep a reference; the daemon thread dies with the process
        return llm
    return LLM(spec)


def registry(requests_db: Optional[Path] = None, faults: Optional[dict] = None):
    from agentkit import with_faults
    from toolkit import acme_registry
    reg = acme_registry(requests_db=requests_db or Path(os.environ.get("ACME_REQUESTS_DB") or RESULTS / "requests.db"))
    return with_faults(reg, faults) if faults else reg


def confirm_hook(mode: str):
    """yes = approve every side effect (and print it), no = decline, ask = ask on the terminal."""
    def hook(call) -> bool:
        args = json.dumps(call.arguments, ensure_ascii=False)
        if mode == "ask":
            ans = input(f"\n>>> The agent wants to run {call.name}({args})\n>>> Approve? [y/N] ")
            return ans.strip().lower() in ("y", "yes")
        print(f"  [human {'APPROVED' if mode == 'yes' else 'DECLINED'}] {call.name}({args[:120]})")
        return mode == "yes"
    return hook


def task_by_id(task_or_id: str) -> tuple[str, str, Optional[dict]]:
    """'t01' -> (id, text, gold) from data/tasks.jsonl; any other string is used as the task text."""
    from agentkit import load_tasks
    for t in load_tasks(TASKS):
        if t["id"] == task_or_id:
            return t["id"], t["task"], t["gold"]
    return "", task_or_id, None


def is_live(spec: str) -> bool:
    return not (spec == "fake" or spec.startswith("mock"))
