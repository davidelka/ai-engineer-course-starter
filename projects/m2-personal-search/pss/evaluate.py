"""Offline evaluation on the sample folder: does search find the right file (and page), do answers
stay grounded, and what does it cost in time and disk.

    python -m pss eval                                  # fake embedder + extractive answers: free
    python -m pss eval --embedder e5-small              # real local embeddings (your machine)
    python -m pss eval --llm ollama:qwen3.5:4b --record # answers from Ollama, recorded for the gate

The golden set (data/golden.jsonl, 52 queries) was written by hand against the sample files:
- kinds: keyword (the words are in the file), semantic (a paraphrase, few shared words),
  cross-lingual (Hebrew question, English file, or the opposite), filter (type/folder/date/lang
  inside the query), ocr and ocr-he (text that exists only inside an image), negative (the
  answer is not in the folder, or only in an EXCLUDED file).
- relevant: file ids; a downloaded-twice copy counts as relevant too. pages: the PDF page the
  answer is on. facts: short strings an answer must contain.

Retrieval is scored at FILE level (what the user clicks): recall@k = share of relevant files in
the first k distinct files, MRR@10, and page@1 = the best chunk of the first relevant file is on
the right page. ocr queries are skipped (and reported as skipped) when Tesseract or its language
is missing, so the numbers do not depend on what happens to be installed.

Answers: fact coverage (evalkit.metrics.fact_coverage), cited-relevant (at least one citation
points to a relevant file), invalid citations ([n] with no source n), grounded sentences (a
sentence with a citation whose numbers all appear in the cited source text) and abstention on
the negative questions.
"""

from __future__ import annotations

import json
import re
import statistics
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from evalkit.metrics import fact_coverage, numbers_in

from .config import PROJECT, SAMPLE, Settings
from .extract import tesseract_langs

GOLDEN = PROJECT / "data" / "golden.jsonl"
RECORDED = PROJECT / "data" / "recorded"
KINDS = ("keyword", "semantic", "cross-lingual", "filter", "ocr", "ocr-he")


def load_golden(path: Path = GOLDEN) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def available_kinds(settings: Settings) -> set[str]:
    kinds = set(KINDS) - {"ocr", "ocr-he"}
    if settings.ocr != "off":
        langs = set(tesseract_langs())
        if "eng" in langs:
            kinds.add("ocr")
        if "heb" in langs:
            kinds.add("ocr-he")
    return kinds


def eval_settings(base: Optional[Settings] = None, index_dir: Optional[str] = None, **over) -> Settings:
    s = replace(base) if base else Settings()
    s.roots = [str(SAMPLE)]
    s.index_dir = index_dir or tempfile.mkdtemp(prefix="pss-eval-")
    for k, v in over.items():
        if v is not None:
            setattr(s, k, v)
    return s


def build_index(settings: Settings, *, embedder=None):
    from .index import PersonalIndex

    idx = PersonalIndex(settings, embedder=embedder)
    t0 = time.perf_counter()
    rep = idx.sync()
    build_s = time.perf_counter() - t0
    return idx, {"build_s": round(build_s, 3), "files": len(idx.manifest.files), "chunks": len(idx.chunks),
                 "index_bytes": idx.stats()["index_bytes"], "warnings": rep.warnings}


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return xs[i]


def _summ(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["relevant"]]
    out = {"n": len(scored)}
    if not scored:
        return out
    for k in (1, 5, 10):
        out[f"recall@{k}"] = round(statistics.fmean(r[f"r{k}"] for r in scored), 3)
    out["mrr"] = round(statistics.fmean(r["rr"] for r in scored), 3)
    paged = [r for r in scored if r["page_ok"] is not None]
    if paged:
        out["page@1"] = round(statistics.fmean(1.0 if r["page_ok"] else 0.0 for r in paged), 3)
        out["n_paged"] = len(paged)
    return out


def eval_retrieval(index, golden: list[dict], modes=("bm25", "dense", "hybrid"), *, depth: int = 10,
                   kinds: Optional[set[str]] = None) -> dict:
    kinds = kinds if kinds is not None else available_kinds(index.s)
    report: dict[str, Any] = {"skipped": sorted({q["kind"] for q in golden if q["kind"] not in kinds | {"negative"}}),
                              "modes": {}}
    for mode in modes:
        rows, times = [], []
        for q in golden:
            if q["kind"] != "negative" and q["kind"] not in kinds:
                continue
            t0 = time.perf_counter()
            ranked = index.rank_files(q["q"], mode=mode, depth=depth)
            times.append((time.perf_counter() - t0) * 1000)
            ids = [f for f, _ in ranked]
            rel = set(q["relevant"])
            first = next((i for i, f in enumerate(ids) if f in rel), None)
            page_ok = None
            if q.get("pages"):
                pf = next(((f, p) for f, p in ranked if f in q["pages"]), None)
                page_ok = bool(pf and pf[1] in q["pages"][pf[0]])
            row = {"id": q["id"], "kind": q["kind"], "lang": q["lang"], "relevant": sorted(rel),
                   "ranked": ids, "rr": 1.0 / (first + 1) if first is not None else 0.0, "page_ok": page_ok,
                   "must_not_hit": sorted(set(q.get("must_not", [])) & set(ids))}
            for k in (1, 5, 10):
                row[f"r{k}"] = (len(rel & set(ids[:k])) / len(rel)) if rel else 0.0
            rows.append(row)
        by_kind = {k: _summ([r for r in rows if r["kind"] == k]) for k in KINDS if any(r["kind"] == k for r in rows)}
        by_lang = {lg: _summ([r for r in rows if r["lang"] == lg]) for lg in ("he", "en")}
        report["modes"][mode] = {"all": _summ(rows), "by_kind": by_kind, "by_lang": by_lang,
                                 "must_not_violations": sum(len(r["must_not_hit"]) for r in rows),
                                 "latency_ms": {"p50": round(pct(times, 0.5), 2), "p95": round(pct(times, 0.95), 2)},
                                 "rows": rows}
    return report


CITES = r"(?:\s*\[\d+(?:\s*[,;]\s*\d+)*\])+"


def sentences(text: str) -> list[str]:
    """Split into sentences, keeping a citation written AFTER the period ("... 8 kg. [1]") with
    its sentence, and not splitting inside numbers ("349.00", "1.5")."""
    text = re.sub(r"([.!?])(" + CITES + ")", r"\2\1", text)
    parts = re.split(r"(?<=[.!?])(?!\d)\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def grounded_rate(text: str, cited_texts: dict[int, str]) -> Optional[float]:
    """Share of sentences that carry a citation whose source contains every number of the sentence."""
    sents = sentences(text)
    if not sents:
        return None
    ok = 0
    for s in sents:
        nums_cited = [int(n) for n in re.findall(r"\[(\d+)\]", s)]
        body = re.sub(r"\[\d+(?:\s*[,;]\s*\d+)*\]", "", s)
        srcs = " ".join(cited_texts.get(n, "") for n in nums_cited)
        if nums_cited and srcs and numbers_in(body) <= numbers_in(srcs):
            ok += 1
    return ok / len(sents)


def score_answer(q: dict, text: str, abstained: bool, cited_files: list[str], cited_texts: dict[int, str],
                 invalid: list[int]) -> dict:
    rel = set(q["relevant"])
    row = {"id": q["id"], "kind": q["kind"], "answer": text[:300], "abstained": abstained,
           "invalid_citations": len(invalid)}
    if q.get("abstain") or not rel:
        row["abstain_ok"] = abstained
        return row
    row["fact_coverage"] = fact_coverage(text, q.get("facts", [])) if q.get("facts") else None
    row["cited_relevant"] = bool(rel & set(cited_files))
    row["grounded"] = None if abstained else grounded_rate(text, cited_texts)
    return row


def summarize_answers(rows: list[dict], times: list[float]) -> dict:
    def mean(key):
        xs = [r[key] for r in rows if r.get(key) is not None]
        return round(statistics.fmean(float(x) for x in xs), 3) if xs else None
    neg = [r for r in rows if "abstain_ok" in r]
    return {"n": len(rows), "fact_coverage": mean("fact_coverage"), "cited_relevant": mean("cited_relevant"),
            "grounded": mean("grounded"),
            "abstain_accuracy": round(statistics.fmean(1.0 if r["abstain_ok"] else 0.0 for r in neg), 3) if neg else None,
            "answered_but_should_abstain": sum(1 for r in neg if not r["abstain_ok"]),
            "invalid_citations": sum(r["invalid_citations"] for r in rows),
            "latency_s": {"p50": round(pct(times, 0.5), 2), "p95": round(pct(times, 0.95), 2)}}


def answer_questions(golden: list[dict]) -> list[dict]:
    return [q for q in golden if q.get("facts") or q.get("abstain")]


def eval_answers(index, golden: list[dict], llm: Any, *, mode: str = "hybrid", record: Optional[Path] = None,
                 kinds: Optional[set[str]] = None) -> dict:
    from .answer import ask

    kinds = kinds if kinds is not None else available_kinds(index.s)
    rows, times, recs = [], [], []
    for q in answer_questions(golden):
        if q["kind"] != "negative" and q["kind"] not in kinds:
            continue
        t0 = time.perf_counter()
        a = ask(index, q["q"], llm=llm, mode=mode)
        times.append(time.perf_counter() - t0)
        cited_texts = {c.n: c.text for c in a.citations}
        rows.append(score_answer(q, a.text, a.abstained, a.cited_files, cited_texts, a.invalid_citations))
        recs.append({"id": q["id"], "q": q["q"], "model": a.model, "answer": a.text,
                     "citations": [c.to_dict() | {"text": c.text} for c in a.citations],
                     "invalid_citations": a.invalid_citations, "latency_s": round(times[-1], 3)})
    if record:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    return {"summary": summarize_answers(rows, times), "rows": rows}


def eval_recorded(golden: list[dict], path: Path) -> dict:
    """Score a recording (data/recorded/<model>.jsonl) without calling anything."""
    from ragkit.rag import NOT_FOUND

    by_id = {q["id"]: q for q in golden}
    rows, times, missing = [], [], []
    recs = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    for r in recs:
        q = by_id.get(r["id"])
        if q is None or q["q"] != r.get("q"):
            missing.append(r["id"])
            continue
        seen.add(r["id"])
        cited_texts = {c["n"]: c.get("text", "") for c in r["citations"]}
        cited_files = list(dict.fromkeys(c["file"] for c in r["citations"]))
        rows.append(score_answer(q, r["answer"], NOT_FOUND in r["answer"].lower(), cited_files, cited_texts,
                                 r.get("invalid_citations", [])))
        times.append(r.get("latency_s", 0.0))
    return {"summary": summarize_answers(rows, times), "rows": rows, "stale": missing,
            "model": recs[0]["model"] if recs else None}


def format_report(rep: dict) -> str:
    """Plain-text report: lists, not tables."""
    lines = []
    b = rep.get("build")
    if b:
        lines.append(f"index: {b['files']} files, {b['chunks']} chunks, {b['index_bytes'] / 1024:.0f} KB on disk, "
                     f"built in {b['build_s']:.2f}s (embedder: {rep.get('embedder')})")
    r = rep.get("retrieval")
    if r:
        if r["skipped"]:
            lines.append(f"skipped kinds (not available here): {', '.join(r['skipped'])}")
        for mode, m in r["modes"].items():
            a = m["all"]
            lines.append(f"\n[{mode}]  recall@1 {a['recall@1']:.2f}  recall@5 {a['recall@5']:.2f}  "
                         f"recall@10 {a['recall@10']:.2f}  MRR {a['mrr']:.2f}  page@1 {a.get('page@1', 0):.2f}  "
                         f"(n={a['n']}, latency p50 {m['latency_ms']['p50']:.1f} ms, p95 {m['latency_ms']['p95']:.1f} ms)")
            for k, s in m["by_kind"].items():
                lines.append(f"  - {k:<13} recall@5 {s['recall@5']:.2f}  MRR {s['mrr']:.2f}  (n={s['n']})")
            for lg, s in m["by_lang"].items():
                if s.get("n"):
                    lines.append(f"  - lang {lg:<8} recall@5 {s['recall@5']:.2f}  MRR {s['mrr']:.2f}  (n={s['n']})")
            if m["must_not_violations"]:
                lines.append(f"  !! {m['must_not_violations']} results from files that must never be indexed")
    a = rep.get("answers")
    if a:
        s = a["summary"]
        lines.append(f"\n[answers: {rep.get('llm')}]  fact coverage {s['fact_coverage']}  cited relevant {s['cited_relevant']}  "
                     f"grounded {s['grounded']}  abstain accuracy {s['abstain_accuracy']}  invalid citations "
                     f"{s['invalid_citations']}  (n={s['n']}, p50 {s['latency_s']['p50']}s, p95 {s['latency_s']['p95']}s)")
    return "\n".join(lines)
