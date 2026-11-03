"""Run a system over a dataset, with an output cache keyed by (system version, input).

A "system" is anything with a `name`, a `version` string and `__call__(input: dict) -> dict`.
The version must change whenever anything that can change the output changes: the prompt,
the model, k, the chunker, temperature. A good habit is to build it from those parts (see
evalkit.rag.RagSystem.version), so you cannot forget to bump it.

Why cache: an eval is re-run far more often than the system changes. You add a metric, fix a
bug in a scorer, recompute a confidence interval: none of that needs new model calls. With
the cache, the second run of 79 questions costs $0 and takes a second. The cache key is
sha256(system.version + canonical JSON of the input), so a new prompt version can never be
served an old prompt's answer.

    run = run_system(system, dataset, cache=OutputCache("results/cache"))
    run.records[0].output["answer"]; run.cached_count; run.cost_usd
    run.save("results/run_v1.jsonl"); Run.load(...)

Scoring is a separate step (score_run) so a metric can change without re-running anything.
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Union

from .dataset import Dataset, Example, stable_hash


class System(Protocol):
    name: str
    version: str

    def __call__(self, input: dict) -> dict: ...


@dataclass
class FunctionSystem:
    """Wrap a plain function as a System: FunctionSystem("upper", "v1", lambda inp: {...})."""
    name: str
    version: str
    fn: Callable[[dict], dict]

    def __call__(self, input: dict) -> dict:
        return self.fn(input)


class OutputCache:
    """One JSON file per (system version, input) under `root`. Plain files: easy to inspect,
    to delete one entry, or to commit a small cache as a fixture."""

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(version: str, input: dict) -> str:
        return stable_hash({"system_version": version, "input": input})[:24]

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, version: str, input: dict) -> Optional[dict]:
        p = self._path(self.key(version, input))
        if p.exists():
            self.hits += 1
            return json.loads(p.read_text(encoding="utf-8"))
        self.misses += 1
        return None

    def put(self, version: str, input: dict, record: dict) -> None:
        p = self._path(self.key(version, input))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


@dataclass
class Record:
    example_id: str
    output: dict = field(default_factory=dict)
    error: Optional[str] = None
    latency_s: float = 0.0
    cost_usd: float = 0.0
    cached: bool = False
    scores: dict[str, Any] = field(default_factory=dict)   # filled by score_run


@dataclass
class Run:
    system_name: str
    system_version: str
    dataset_ref: str
    records: list[Record] = field(default_factory=list)
    started_at: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records if not r.cached)

    @property
    def cached_count(self) -> int:
        return sum(r.cached for r in self.records)

    @property
    def errors(self) -> list[Record]:
        return [r for r in self.records if r.error]

    def by_id(self) -> dict[str, Record]:
        return {r.example_id: r for r in self.records}

    def values(self, metric: str, ids: Optional[list[str]] = None) -> list[float]:
        """The per-example values of one metric (None values are skipped), in `ids` order."""
        recs = self.by_id()
        order = ids if ids is not None else [r.example_id for r in self.records]
        out = []
        for i in order:
            v = recs[i].scores.get(metric) if i in recs else None
            if v is not None:
                out.append(float(v))
        return out

    def mean(self, metric: str, ids: Optional[list[str]] = None) -> Optional[float]:
        v = self.values(metric, ids)
        return sum(v) / len(v) if v else None

    def save(self, path: Union[str, Path]) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            head = {k: v for k, v in asdict(self).items() if k != "records"}
            f.write(json.dumps({"_run": head}, ensure_ascii=False) + "\n")
            for r in self.records:
                f.write(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n")
        return p

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Run":
        run = None
        recs = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if "_run" in obj:
                run = cls(**obj["_run"])
            else:
                recs.append(Record(**obj))
        if run is None:
            raise ValueError(f"{path}: no _run header line")
        run.records = recs
        return run


def run_system(system: System, dataset: Dataset, *, cache: Optional[OutputCache] = None,
               on_progress: Optional[Callable[[int, int, Run], None]] = None,
               fail_fast: bool = False) -> Run:
    """Call the system once per example (or read the cache). Exceptions become Record.error:
    an eval must finish and report the failure, not crash on question 37."""
    run = Run(system.name, system.version, dataset.ref, started_at=time.time())
    for i, ex in enumerate(dataset.examples, 1):
        hit = cache.get(system.version, ex.input) if cache else None
        if hit is not None:
            rec = Record(ex.id, output=hit.get("output", {}), error=hit.get("error"),
                         latency_s=hit.get("latency_s", 0.0), cost_usd=hit.get("cost_usd", 0.0), cached=True)
        else:
            t0 = time.perf_counter()
            try:
                out = system(ex.input)
                err = None
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                if fail_fast:
                    raise
                out, err = {}, f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}"
            rec = Record(ex.id, output=out, error=err, latency_s=time.perf_counter() - t0,
                         cost_usd=float(out.get("cost_usd", 0.0) or 0.0))
            if cache and err is None:   # never cache failures: a retry should really retry
                cache.put(system.version, ex.input, {"output": rec.output, "latency_s": rec.latency_s,
                                                     "cost_usd": rec.cost_usd})
        run.records.append(rec)
        if on_progress:
            on_progress(i, len(dataset), run)
    return run


Scorer = Callable[[Example, dict], dict]


def score_run(run: Run, dataset: Dataset, scorers: list[Scorer]) -> Run:
    """Apply each scorer(example, output) -> {metric: value}. A value of None means "not
    applicable to this example" (e.g. retrieval recall on an unanswerable question) and is
    left out of means, so a metric's denominator is always the examples it applies to."""
    for rec in run.records:
        ex = dataset[rec.example_id]
        rec.scores = {}
        if rec.error:
            rec.scores["error"] = 1.0
            continue
        for s in scorers:
            rec.scores.update(s(ex, rec.output))
    return run


def aggregate(run: Run, dataset: Dataset, metrics: list[str], *, by: str = "type") -> dict[str, dict[str, Optional[float]]]:
    """{slice: {metric: mean}} with an "ALL" slice, plus "n" per slice."""
    out: dict[str, dict[str, Optional[float]]] = {}
    groups = dict(dataset.by(by))
    groups["ALL"] = dataset
    for name, ds in groups.items():
        ids = [e.id for e in ds if e.id in run.by_id()]
        row: dict[str, Optional[float]] = {"n": float(len(ids))}
        for m in metrics:
            row[m] = run.mean(m, ids)
        out[name] = row
    return out
