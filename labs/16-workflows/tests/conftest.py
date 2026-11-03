import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))  # so tests can `import mine`
sys.path.insert(0, str(LAB.parents[1]))

pytest.importorskip("langgraph", reason="pip install -r labs/16-workflows/requirements.txt")
pytest.importorskip("langgraph.checkpoint.sqlite", reason="pip install -r labs/16-workflows/requirements.txt")

from langgraph.types import RetryPolicy  # noqa: E402

from flowkit import FakeLLM, runner  # noqa: E402
from flowkit.graph import build_graph, open_checkpointer  # noqa: E402
from flowkit.nodes import Deps, ToolUnavailable  # noqa: E402
from toolkit import acme_registry  # noqa: E402

T0 = "2026-11-02T08:00:00+00:00"
SAMPLES = {s["id"]: s for s in map(json.loads, (LAB / "data" / "requests.jsonl").read_text().splitlines())}
PARTS = {"ex2": ("merge_audit", "add_usage", "route_after_file", "route_after_gate"),
         "ex3": ("intake_node", "policy_node", "file_request_node"),
         "ex5": ("approval_gate",)}
FAST_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.01, jitter=False, retry_on=ToolUnavailable)


def impl_for(*parts):
    import mine
    return SimpleNamespace(**{n: getattr(mine, n) for p in parts for n in PARTS[p]})


@pytest.fixture
def lab(tmp_path):
    """lab.app(*parts, llm=None, registry=None) -> a compiled graph that uses your mine.py
    functions for the given exercises and the reference for everything else."""
    db, cp = tmp_path / "requests.db", tmp_path / "checkpoints.db"

    def deps(llm=None, registry=None):
        return Deps(llm=llm or FakeLLM(), registry=registry or acme_registry(requests_db=db), requests_db=db,
                    clock=lambda: T0)

    def app(*parts, llm=None, registry=None):
        return build_graph(deps(llm, registry), impl=impl_for(*parts), checkpointer=open_checkpointer(cp),
                           retry=FAST_RETRY)

    def run(app_, tid, sample_id):
        s = SAMPLES[sample_id]
        list(runner.start(app_, tid, s["requester"], s["text"], T0))
        return runner.summary(app_, tid)

    def decide(app_, tid, decision, actor, comment=""):
        list(runner.resume(app_, tid, {"decision": decision, "actor": actor, "comment": comment}))
        return runner.summary(app_, tid)

    return SimpleNamespace(db=db, cp=cp, deps=deps, app=app, run=run, decide=decide, samples=SAMPLES)
