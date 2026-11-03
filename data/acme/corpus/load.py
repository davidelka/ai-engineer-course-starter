"""Tiny, dependency-light loader for the Acme corpus.

    from data.acme.corpus.load import iter_docs, load_qa, db_path      # from the repo root
    # or: sys.path.insert(0, "data/acme/corpus"); import load

- iter_docs(): yields one Doc per document. For Markdown, `text` is the body without the
  front matter. For PDF/HTML/DOCX, `text` is None: extraction is the job of the ingestion
  lesson; `path` points to the file and `meta` comes from the sidecar <id>.meta.yaml.
- load_qa(): the golden question set as a list of dicts.
- db_path() / csv_path(table): the structured data.

Only the standard library is required. PyYAML is used when installed (it is in the repo
requirements); otherwise a minimal "key: value" parser reads the flat front matter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
GOLDEN_DIR = ROOT / "golden"
STRUCTURED_DIR = ROOT / "structured"

REQUIRED_META = ("id", "title", "department", "doc_type", "version", "effective_date",
                 "owner", "classification", "language")
BINARY_FORMATS = {".pdf": "pdf", ".html": "html", ".docx": "docx"}


@dataclass
class Doc:
    id: str
    meta: dict
    path: Path
    format: str                      # "md" | "pdf" | "html" | "docx"
    text: Optional[str] = None       # body text for md; None for binary/HTML formats
    extra: dict = field(default_factory=dict)


def _parse_yaml(src: str) -> dict:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(src) or {}
    except ImportError:
        data = {}
        for line in src.splitlines():
            if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    # normalise: dates and versions as strings
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in data.items()}


def split_front_matter(raw: str) -> tuple[dict, str]:
    """Return (metadata, body) for a Markdown file with a leading '---' YAML block."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta = _parse_yaml(raw[3:end])
    body = raw[end + 4:].lstrip("\n")
    return meta, body


def iter_docs(formats: Optional[set[str]] = None) -> Iterator[Doc]:
    """Yield every document, sorted by id. `formats` filters, e.g. {"md"}."""
    for p in sorted(DOCS_DIR.iterdir()):
        if p.suffix == ".md":
            fmt = "md"
            meta, body = split_front_matter(p.read_text(encoding="utf-8"))
            doc = Doc(id=meta.get("id", p.stem), meta=meta, path=p, format=fmt, text=body)
        elif p.suffix in BINARY_FORMATS:
            fmt = BINARY_FORMATS[p.suffix]
            side = p.with_name(p.stem + ".meta.yaml")
            meta = _parse_yaml(side.read_text(encoding="utf-8")) if side.exists() else {}
            doc = Doc(id=meta.get("id", p.stem), meta=meta, path=p, format=fmt, text=None)
        else:
            continue
        if formats is None or fmt in formats:
            yield doc


def get_doc(doc_id: str) -> Doc:
    for d in iter_docs():
        if d.id == doc_id:
            return d
    raise KeyError(doc_id)


def load_qa(path: Optional[Path] = None) -> list[dict]:
    path = path or GOLDEN_DIR / "qa.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def db_path() -> Path:
    return STRUCTURED_DIR / "acme.db"


def csv_path(table: str) -> Path:
    return STRUCTURED_DIR / f"{table}.csv"


if __name__ == "__main__":
    from collections import Counter
    docs = list(iter_docs())
    print(f"{len(docs)} docs")
    print("by format:", dict(Counter(d.format for d in docs)))
    print("by department:", dict(Counter(d.meta.get("department") for d in docs)))
    print("by language:", dict(Counter(d.meta.get("language") for d in docs)))
    print(f"{len(load_qa())} golden questions; db at {db_path()}")
