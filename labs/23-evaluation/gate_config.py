"""The regression gate for the Acme RAG answer prompt: one list, used by gate_experiment.py and
by the pytest gate in ci/test_regression_gate.py. Change the rules here, nowhere else.

Why these four rules (lesson 23, slide "regression gates"):
  1. an overall floor, so nothing ships that is plainly worse than what we promised
  2. a floor on version_conflict, the slice that answers "which policy is in force", where a
     wrong answer sends an employee to an outdated rule
  3. no statistically significant drop overall vs the baseline (McNemar exact, because
     answer_ok is pass/fail)
  4. a PRACTICAL limit on the version_conflict slice: 11 questions can never reach
     significance for a moderate drop, so "more than 1 question in 10 got worse" fails directly
"""

from evalkit import NoSignificantDrop, Threshold

GATES = [
    Threshold("answer_ok", 0.45),
    Threshold("answer_ok", 0.50, slice="version_conflict"),
    NoSignificantDrop("answer_ok"),
    NoSignificantDrop("answer_ok", slice="version_conflict", max_drop=0.10),
]
