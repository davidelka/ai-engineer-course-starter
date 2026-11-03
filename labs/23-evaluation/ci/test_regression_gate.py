"""The regression gate as a pytest test: what a CI job runs on every pull request that touches
the answer prompt, the retriever or the model.

    python -m pytest -q labs/23-evaluation/ci                         # candidate v1: passes
    EVAL_CANDIDATE=v2 python -m pytest -q labs/23-evaluation/ci       # candidate v2: fails, with reasons
    EVAL_MODEL=anthropic:claude-haiku-5-5 EVAL_CANDIDATE=v2 python -m pytest -q labs/23-evaluation/ci   # live

In a real repository the baseline is the run of the main branch, stored as a CI artifact (or
in the output cache, which makes it free to recompute). Here it is recomputed from the cache.
The CI job also uploads results/ci_gate.md so a reviewer sees WHY the gate failed.
"""

import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

from _lab import CACHE, RESULTS, OutputCache, acme_golden, build_index, is_paid, system_for  # noqa: E402
from gate_config import GATES  # noqa: E402

from evalkit import assert_gates, build_report, check_gates, run_system, score_run, to_markdown  # noqa: E402
from evalkit.rag import RAG_METRICS, rag_scorer  # noqa: E402

MODEL = os.environ.get("EVAL_MODEL", "rule")
CANDIDATE = os.environ.get("EVAL_CANDIDATE", "v1")
BASELINE = os.environ.get("EVAL_BASELINE", "v1")


def test_answer_prompt_regression_gate():
    if is_paid(MODEL) and not os.environ.get("EVAL_ALLOW_PAID"):
        import pytest
        pytest.skip("paid model: set EVAL_ALLOW_PAID=1 to run the live gate")
    ds = acme_golden()
    idx = build_index()
    runs = {}
    for p in {BASELINE, CANDIDATE}:
        r = run_system(system_for(MODEL, p, 5, index=idx), ds, cache=OutputCache(CACHE))
        runs[p] = score_run(r, ds, [rag_scorer()])
    results = check_gates(runs[CANDIDATE], ds, GATES, baseline=runs[BASELINE])
    RESULTS.mkdir(exist_ok=True)
    rep = build_report(runs[CANDIDATE], ds, RAG_METRICS, baseline=runs[BASELINE], gate_results=results,
                       title=f"CI gate: {CANDIDATE} vs {BASELINE} ({MODEL})")
    (RESULTS / "ci_gate.md").write_text(to_markdown(rep), encoding="utf-8")
    assert_gates(results)
