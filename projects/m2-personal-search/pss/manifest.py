"""The manifest: what is in the index, file by file, and how to update it cheaply.

A watcher fires many events (an editor saves a file three times, a sync client touches 500
files). Re-indexing must therefore be incremental and cheap:

1. compare size and mtime with the manifest (a stat call, no read): equal -> unchanged;
2. only for files whose size or mtime moved, read and hash the bytes: equal hash -> the file
   was only touched (update size/mtime, keep its chunks and vectors); different -> changed;
3. files in the manifest that are gone -> removed (their chunks and vectors are deleted).

If the index signature changes (another embedder, chunker or OCR setting), everything is
stale and the index is rebuilt; the embedding cache still saves the embedding work for every
chunk whose text did not change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:20]


@dataclass
class SyncPlan:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    touched: list[str] = field(default_factory=list)     # stat moved, bytes identical
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)  # every hash computed during planning

    @property
    def to_index(self) -> list[str]:
        return sorted(self.added + self.changed)

    def summary(self) -> str:
        return (f"added {len(self.added)}, changed {len(self.changed)}, touched {len(self.touched)}, "
                f"unchanged {len(self.unchanged)}, removed {len(self.removed)}, hashed {len(self.hashes)}")


def plan_sync(manifest: dict[str, dict], current: dict[str, dict],
              hash_fn: Callable[[str], str]) -> SyncPlan:
    """Reference implementation (see mine.plan_sync for the contract)."""
    plan = SyncPlan()
    for fid in sorted(current):
        st = current[fid]
        old = manifest.get(fid)
        if old is None:
            plan.hashes[fid] = hash_fn(fid)
            plan.added.append(fid)
            continue
        if old.get("size") == st.get("size") and old.get("mtime") == st.get("mtime"):
            plan.unchanged.append(fid)
            continue
        h = hash_fn(fid)
        plan.hashes[fid] = h
        (plan.touched if h == old.get("hash") else plan.changed).append(fid)
    plan.removed = sorted(fid for fid in manifest if fid not in current)
    return plan


@dataclass
class Manifest:
    signature: str = ""
    files: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls()
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(signature=d.get("signature", ""), files=d.get("files", {}))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"signature": self.signature, "files": self.files},
                                  ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
