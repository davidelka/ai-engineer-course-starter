"""acmeqa: the Acme Knowledge Assistant (midterm project M1, Company Brain phase 1).

    question ──route──► docs:  hybrid retrieval (BM25 + dense, RRF) with ACL by role
                               ─► version filter ─► (rerank) ─► pack context
                               ─► answer with [n] citations, or "not in the documents"
                        data:  datakit text-to-SQL (guard, row policy, provenance)

Modules: config (settings from the environment) · ingest (incremental ingestion job, docs
store) · retrieval (the retriever stack, ACL) · context (pack_context) · citations
(resolve_citations) · answer (prompt with a cached system block, streaming, offline
answerer) · router (route_question, the data path) · assistant (one question end to end,
traced with obskit) · service (FastAPI: /ask with SSE, /docs/{id}, /healthz, the UI) ·
evaluate (golden set, per-type metrics, groundedness, diagnosis, ACL, router) · hooks
(your mine.py functions where implemented).
"""

import sys
from pathlib import Path

# The course packages (ragkit, datakit, llmkit, obskit, evalkit, guardkit) live at the repo root.
_ROOT = Path(__file__).resolve().parents[3]
if (_ROOT / "ragkit").is_dir() and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "1.0"
