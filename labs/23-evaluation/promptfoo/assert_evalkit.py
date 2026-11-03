"""promptfoo Python assertion: score the output with evalkit's rag_scorer, the same code as run_eval.py.

Test vars (written by make_config.py): qid, qtype, question, expected (JSON), doc_map (JSON: "n" -> doc id
of the n-th source in the frozen prompt). Returns pass = answer_ok, score = fact coverage, and the
other metrics as named scores, which promptfoo shows as columns.
Docs: https://www.promptfoo.dev/docs/configuration/expected-outputs/python/
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evalkit.dataset import Example  # noqa: E402
from evalkit.metrics import abstained  # noqa: E402
from evalkit.rag import rag_scorer  # noqa: E402
from ragkit.rag import parse_citations  # noqa: E402

SCORE = rag_scorer()


def get_assert(output, context):
    v = context["vars"]
    expected = json.loads(v["expected"])
    doc_map = json.loads(v["doc_map"])
    cited = list(dict.fromkeys(doc_map[str(n)] for n in parse_citations(output) if str(n) in doc_map))
    ex = Example(v["qid"], {"question": v["question"]}, expected, [f"type:{v['qtype']}"])
    s = SCORE(ex, {"answer": output, "cited_docs": cited, "abstained": abstained(output),
                   "retrieved_docs": list(dict.fromkeys(doc_map.values()))})
    reason = (f"answer_ok={s['answer_ok']:.0f} facts={s['fact_coverage'] if s['fact_coverage'] is not None else '-'} "
              f"stale={s['stale_cited']:.0f} abstain_ok={s['abstain_ok']:.0f} cited={cited}")
    named = {k: float(s[k]) for k in ("fact_coverage", "stale_cited", "abstain_ok", "cite_precision") if s[k] is not None}
    return {"pass": bool(s["answer_ok"]), "score": float(s["fact_coverage"] if s["fact_coverage"] is not None else s["abstain_ok"]),
            "reason": reason, "named_scores": named}
