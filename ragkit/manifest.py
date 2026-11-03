"""The ingestion manifest: what was ingested, from which bytes, with which chunker.

Incremental ingestion is a diff between two maps, doc_id -> content hash:
    previous (the manifest from the last run)  vs  current (hash of every file now)
  added      in current, not in previous            -> load, chunk, index
  changed    in both, hash differs                  -> remove old chunks, re-ingest
  unchanged  in both, same hash                     -> skip (no parsing at all)
  removed    in previous, not in current            -> remove its chunks from the index
And if the PIPELINE changed (another chunker, size or tokenizer), every document is
"changed", even with identical bytes: the old chunks were made by a different recipe.

The hash covers the raw file bytes AND the metadata sidecar: re-classifying a document from
internal to confidential, without touching its text, must reach the index.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


def content_hash(data: bytes, meta: Optional[dict] = None) -> str:
    """Stable hash of a source: raw bytes + metadata. The metadata is serialized canonically
    (sorted keys), so the same fields in another order give the same hash. 16 hex chars."""
    h = hashlib.sha256(data)
    h.update(b"\0")
    h.update(json.dumps(meta or {}, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    return h.hexdigest()[:16]


@dataclass
class IngestPlan:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def to_process(self) -> list[str]:
        return sorted(self.added + self.changed)

    def summary(self) -> str:
        return (f"added {len(self.added)}, changed {len(self.changed)}, "
                f"unchanged {len(self.unchanged)}, removed {len(self.removed)}")


def plan_ingest(previous: dict[str, str], current: dict[str, str], *,
                pipeline_changed: bool = False) -> IngestPlan:
    plan = IngestPlan()
    for doc_id in sorted(current):
        if doc_id not in previous:
            plan.added.append(doc_id)
        elif pipeline_changed or previous[doc_id] != current[doc_id]:
            plan.changed.append(doc_id)
        else:
            plan.unchanged.append(doc_id)
    plan.removed = sorted(set(previous) - set(current))
    return plan


@dataclass
class Manifest:
    pipeline: str = ""                                   # chunker signature (+ loader options)
    docs: dict[str, dict] = field(default_factory=dict)  # doc_id -> {hash, path, chunks, ingested_at}
    path: Optional[Path] = None

    def hashes(self) -> dict[str, str]:
        return {k: v["hash"] for k, v in self.docs.items()}

    def record(self, doc_id: str, content_hash: str, path: str, chunk_ids: list[str]) -> None:
        self.docs[doc_id] = {"hash": content_hash, "path": path, "chunks": chunk_ids,
                             "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def forget(self, doc_id: str) -> None:
        self.docs.pop(doc_id, None)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Manifest":
        p = Path(path)
        if not p.exists():
            return cls(path=p)
        d = json.loads(p.read_text(encoding="utf-8"))
        return cls(pipeline=d.get("pipeline", ""), docs=d.get("docs", {}), path=p)

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        p = Path(path or self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pipeline": self.pipeline, "docs": self.docs}, indent=1,
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)  # atomic: a crash mid-write never leaves half a manifest
