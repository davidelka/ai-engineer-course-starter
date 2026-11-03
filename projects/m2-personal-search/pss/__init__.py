"""pss: Personal Smart Search. A local-first search and "ask my documents" tool over a folder
of personal files on your own Linux machine (project M2 of the AI Engineer course).

Everything runs on the machine by default: parsing (ragkit loaders + pypdf per page + optional
Tesseract OCR), local embeddings (multilingual-e5 through ragkit.embed, cached in SQLite), an
exact vector store on disk (ragkit NumpyVectorStore, FAISS optional), BM25, hybrid fusion (RRF),
and answers from a local model through Ollama. A cloud model (Claude Haiku) is an explicit
opt-in: sources from protected folders are withheld, the rest is redacted (pss.privacy), and
every byte that leaves the machine is written to an egress log first.

    python -m pss demo                      # the whole flow on data/sample, offline and free
    python -m pss index data/sample         # build or update the index
    python -m pss search "type:pdf ערבות"   # BM25 + dense + RRF, with filters in the query
    python -m pss ask "כמה עולה הטיול השנתי?"
    python -m pss serve                     # local web UI on http://127.0.0.1:8765
"""

__version__ = "1.0.0"
