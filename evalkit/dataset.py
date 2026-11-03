"""Golden sets as versioned, content-addressed datasets.

An eval result means nothing unless you can say WHICH data it was measured on. So a Dataset
carries a version that is computed from its content (a short sha256 of every example), not
typed by hand: change one reference answer and the version changes, and a cached run or a
baseline measured on the old version will not be silently compared with the new one.

    from evalkit.dataset import acme_golden
    ds = acme_golden()                          # 79 questions, version "acme-qa@3f2a91c0"
    vc = ds.filter(type="version_conflict")     # a new Dataset, with its own version
    dev, test = ds.split({"dev": 0.5, "test": 0.5}, stratify="type")
    ds.save("results/acme-qa.jsonl")            # one JSON object per line + a manifest line

Splits are deterministic: an example goes to a split by the hash of its id (and the seed),
so adding a new question never moves an old one from test to dev. Stratifying by type keeps
each split's mix of question types close to the full set's.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional, Union


def stable_hash(obj: Any) -> str:
    """sha256 of the canonical JSON form (sorted keys, no spaces). Same content, same hash."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class Example:
    """One golden example.

    input:     what the system receives (for RAG: {"question": ...})
    expected:  what a good output must satisfy (reference answer, facts, source ids, ...)
    tags:      free labels used for slicing ("type:numeric", "stale:hr-vacation-2024", ...)
    meta:      anything else (difficulty, notes); NOT part of the version hash
    """
    id: str
    input: dict[str, Any]
    expected: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return next((t.split(":", 1)[1] for t in self.tags if t.startswith("type:")), "")

    def content_hash(self) -> str:
        return stable_hash({"id": self.id, "input": self.input, "expected": self.expected, "tags": self.tags})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Dataset:
    name: str
    examples: list[Example]
    description: str = ""

    # -------------------------------------------------------------- identity
    @property
    def version(self) -> str:
        """Content address: 8 hex chars of the hash of every example's content hash, in id order."""
        h = stable_hash(sorted(e.content_hash() for e in self.examples))
        return h[:8]

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self) -> Iterator[Example]:
        return iter(self.examples)

    def __getitem__(self, ex_id: str) -> Example:
        for e in self.examples:
            if e.id == ex_id:
                return e
        raise KeyError(ex_id)

    def ids(self) -> list[str]:
        return [e.id for e in self.examples]

    # -------------------------------------------------------------- slicing
    def filter(self, pred: Optional[Callable[[Example], bool]] = None, *, type: Optional[str] = None,
               tag: Optional[str] = None, ids: Optional[Iterable[str]] = None, name: Optional[str] = None) -> "Dataset":
        """A new Dataset with the matching examples. `type` may be a comma-separated list."""
        keep = self.examples
        if type:
            types = set(type.split(","))
            keep = [e for e in keep if e.type in types]
        if tag:
            keep = [e for e in keep if any(t == tag or t.startswith(tag + ":") for t in e.tags)]
        if ids is not None:
            wanted = set(ids)
            keep = [e for e in keep if e.id in wanted]
        if pred:
            keep = [e for e in keep if pred(e)]
        suffix = type or tag or ("custom" if pred or ids is not None else "")
        return Dataset(name or (f"{self.name}[{suffix}]" if suffix else self.name), list(keep), self.description)

    def by(self, key: str = "type") -> dict[str, "Dataset"]:
        """Group by type, or by any tag prefix (e.g. key="difficulty" reads tag "difficulty:hard")."""
        groups: dict[str, list[Example]] = defaultdict(list)
        for e in self.examples:
            value = e.type if key == "type" else next(
                (t.split(":", 1)[1] for t in e.tags if t.startswith(key + ":")), "")
            groups[value].append(e)
        return {k: Dataset(f"{self.name}[{key}={k}]", v) for k, v in sorted(groups.items())}

    def counts(self, key: str = "type") -> dict[str, int]:
        return {k: len(v) for k, v in self.by(key).items()}

    def split(self, fractions: dict[str, float], *, seed: int = 0,
              stratify: Optional[str] = "type") -> dict[str, "Dataset"]:
        """Deterministic split by hash(seed, id). Within each stratum examples are ordered by
        that hash and cut by the fractions, so each split gets close to its share of every type."""
        total = sum(fractions.values())
        names = list(fractions)
        strata = self.by(stratify) if stratify else {"": self}
        out: dict[str, list[Example]] = {n: [] for n in names}
        for group in strata.values():
            ordered = sorted(group.examples, key=lambda e: stable_hash([seed, e.id]))
            n, start, acc = len(ordered), 0, 0.0
            for i, split_name in enumerate(names):
                acc += fractions[split_name] / total
                end = n if i == len(names) - 1 else round(acc * n)
                out[split_name].extend(ordered[start:end])
                start = end
        order = {e.id: i for i, e in enumerate(self.examples)}
        return {n: Dataset(f"{self.name}:{n}", sorted(v, key=lambda e: order[e.id])) for n, v in out.items()}

    # -------------------------------------------------------------- io
    def save(self, path: Union[str, Path]) -> Path:
        """JSONL: a manifest line ({"_manifest": ...}) then one example per line."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"_manifest": {"name": self.name, "version": self.version, "n": len(self),
                                              "description": self.description, "counts": self.counts()}},
                               ensure_ascii=False) + "\n")
            for e in self.examples:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
        return p

    @classmethod
    def load(cls, path: Union[str, Path], *, check_version: bool = True) -> "Dataset":
        name, desc, want = Path(path).stem, "", None
        examples = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if "_manifest" in obj:
                m = obj["_manifest"]
                name, desc, want = m.get("name", name), m.get("description", ""), m.get("version")
                continue
            examples.append(Example(**obj))
        ds = cls(name, examples, desc)
        if check_version and want and want != ds.version:
            raise ValueError(f"{path}: manifest says version {want} but the content hashes to {ds.version}; "
                             "the file was edited by hand. Re-save it to accept the change.")
        return ds

    def summary(self) -> str:
        parts = ", ".join(f"{k} {v}" for k, v in self.counts().items())
        return f"{self.ref}: {len(self)} examples ({parts})"


# ------------------------------------------------------------------ the Acme golden set
def example_from_qa(q: dict) -> Example:
    """A line of data/acme/corpus/golden/qa.jsonl -> Example."""
    tags = [f"type:{q['type']}", f"difficulty:{q.get('difficulty', '')}"] + list(q.get("tags") or [])
    stale = [t.split(":", 1)[1] for t in q.get("tags") or [] if t.startswith("stale:")]
    return Example(
        id=q["id"],
        input={"question": q["question"]},
        expected={"answer": q["answer"], "answer_facts": q.get("answer_facts", []),
                  "source_ids": q.get("source_ids", []), "source_quotes": q.get("source_quotes", []),
                  "stale_ids": stale, "answerable": bool(q.get("source_ids"))},
        tags=tags,
    )


def acme_golden(path: Optional[Union[str, Path]] = None) -> Dataset:
    from ragkit.acme import QA_PATH, acme_qa   # read-only use of ragkit
    qa = acme_qa(Path(path) if path else None)
    return Dataset("acme-qa", [example_from_qa(q) for q in qa],
                   f"Acme golden QA from {Path(path or QA_PATH).name}")


def type_counts(examples: Iterable[Example]) -> Counter:
    return Counter(e.type for e in examples)
