"""evalkit: evaluation and regression testing for LLM systems (lesson 23).

    dataset      versioned golden sets (content-hashed), filters, tags, deterministic splits
    runner       run a System over a Dataset with an output cache keyed by (system version, input)
    metrics      exact/contains/regex, per-field accuracy, recall@k, MRR, fact coverage, citations
    judge        LLM-as-judge with rubrics and structured verdicts (llmkit.structured); pairwise
                 with position swap; HeuristicJudgeLLM as a free offline stand-in
    calibration  judge vs human labels: agreement, Cohen's kappa, confusion
    stats        bootstrap CI, paired comparison, McNemar, minimum detectable difference, sample size
    gates        Threshold and NoSignificantDrop rules, assert_gates for pytest/CI
    report       Markdown and HTML reports (lists, no tables)
    rag          the lesson-9 RAG baseline as a System, prompt versions v1/v2, rag_scorer

Uses ragkit and llmkit read-only. Pure Python; pydantic for the judge verdicts.
"""

from .calibration import CalibrationReport, agreement, calibrate, cohen_kappa, confusion, kappa_band
from .dataset import Dataset, Example, acme_golden, stable_hash
from .gates import GateResult, NoSignificantDrop, Threshold, assert_gates, check_gates
from .judge import HeuristicJudgeLLM, Judge, JudgeResult, binary_groundedness
from .metrics import (citation_scores, contains, exact_match, fact_coverage, fact_covered, hit_at_k, mrr,
                      per_field_accuracy, recall_at_k, regex_match)
from .report import build_report, to_html, to_markdown
from .runner import FunctionSystem, OutputCache, Record, Run, aggregate, run_system, score_run
from .stats import (CI, PairedResult, bootstrap_ci, mcnemar_exact, min_detectable_diff, paired_compare, sample_size,
                    wilson_ci)

__all__ = [
    "Dataset", "Example", "acme_golden", "stable_hash",
    "FunctionSystem", "OutputCache", "Record", "Run", "run_system", "score_run", "aggregate",
    "exact_match", "contains", "regex_match", "per_field_accuracy", "hit_at_k", "recall_at_k", "mrr",
    "fact_coverage", "fact_covered", "citation_scores",
    "Judge", "JudgeResult", "HeuristicJudgeLLM", "binary_groundedness",
    "agreement", "cohen_kappa", "confusion", "calibrate", "CalibrationReport", "kappa_band",
    "CI", "PairedResult", "bootstrap_ci", "paired_compare", "mcnemar_exact", "min_detectable_diff",
    "sample_size", "wilson_ci",
    "Threshold", "NoSignificantDrop", "GateResult", "check_gates", "assert_gates",
    "build_report", "to_markdown", "to_html",
]
