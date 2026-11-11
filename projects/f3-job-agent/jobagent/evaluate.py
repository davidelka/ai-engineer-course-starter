"""Evaluation on the labeled set (data/posts.jsonl): three questions, measured separately.

1. Extraction: did we read the post right?  per-field accuracy over gold jobs (a gold job
   with no predicted counterpart counts as wrong on every field), job-count accuracy,
   is_job_post accuracy, injection detection.
2. Relevance: did the matcher put the right jobs in front of the owner?  precision and recall of
   the "match" tier and of "shown" (match or maybe), measured twice:
     - on GOLD facts (matcher only: are the rules right?)
     - on PREDICTED facts (end to end: rules + extraction errors)
3. Digest: did each run send exactly the new jobs?  the whole pipeline replays the day slot by
   slot on a fresh store; per slot the delivered dedup groups must equal the expected ones,
   and no group may be delivered twice.

Metrics use evalkit (per_field_accuracy, wilson_ci) where it fits. The regression gate is in
tests/ and in tests/test_f3_job_agent.py: thresholds on the heuristic baseline (always), and
on a recorded LLM run when data/recorded/*.jsonl exists.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from evalkit import per_field_accuracy, wilson_ci

from .dedup import jaccard, normalize_company, normalize_title
from .extract import Extractor
from .match import score_job
from .models import CategoryScore, JobPosting, PostExtraction, RawPost
from .prefs import Preferences, load_prefs
from .safety import screen_post, validate_extraction

DATA = Path(__file__).resolve().parent.parent / "data"
FIELDS = ["title", "company", "location", "work_mode", "seniority", "years_required", "primary_category",
          "hardware_oriented", "language", "apply"]


def load_posts(path: Union[str, Path, None] = None) -> list[dict]:
    p = Path(path or DATA / "posts.jsonl")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def raw_post(p: dict) -> RawPost:
    return RawPost(source=p["source"], source_id=p["id"], channel=p["channel"], ts=datetime.fromisoformat(p["ts"]),
                   text=p["text"])


def gold_posting(j: dict) -> JobPosting:
    company = j["company"][0] if isinstance(j["company"], list) else j["company"]
    return JobPosting(title=j["title"], company=company, location=j["location"], work_mode=j["work_mode"],
                      seniority=j["seniority"], years_required=j["years_required"],
                      categories=[CategoryScore(category=c, confidence=round(0.9 - 0.25 * i, 2))
                                  for i, c in enumerate(j["categories"])],
                      tech_stack=j.get("tech_stack", []), hardware_oriented=j["hardware_oriented"],
                      language=j["language"], apply=j["apply"])


def title_match(pred: Optional[str], gold: str) -> bool:
    a, b = set(normalize_title(pred).split()), set(normalize_title(gold).split())
    return jaccard(a, b) >= 0.5


def company_match(pred: Optional[str], gold) -> bool:
    golds = gold if isinstance(gold, list) else [gold]
    return any((g is None and pred is None) or (g is not None and pred is not None
                                                and normalize_company(g) == normalize_company(pred)) for g in golds)


def field_scores(pred: Optional[JobPosting], gold: dict) -> dict[str, bool]:
    if pred is None:
        return {f: False for f in FIELDS}
    pd = pred.model_dump()
    pd["primary_category"] = pred.primary_category
    pd["apply"] = (pred.apply or "").strip().rstrip("/.").lower() or None
    gd = {k: gold[k] for k in ("location", "work_mode", "seniority", "years_required", "primary_category",
                               "hardware_oriented", "language")}
    gd["apply"] = (gold["apply"] or "").strip().rstrip("/.").lower() or None
    out = per_field_accuracy(pd, gd)
    out["title"] = title_match(pred.title, gold["title"])
    out["company"] = company_match(pred.company, gold["company"])
    return {f: out[f] for f in FIELDS}


def align(*args, **kwargs):
    """Milestone 9: runs your mine.align (see jobagent/hooks.py)."""
    from .hooks import call
    return call("align", *args, **kwargs)


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"precision": p, "recall": r, "f1": (2 * p * r / (p + r)) if p + r else 0.0, "tp": tp, "fp": fp, "fn": fn}


def relevance(*args, **kwargs):
    """Milestone 9: runs your mine.relevance (see jobagent/hooks.py)."""
    from .hooks import call
    return call("relevance", *args, **kwargs)


@dataclass
class EvalReport:
    extractor: str
    n_posts: int
    n_gold_jobs: int
    field_accuracy: dict[str, float]
    field_ci: dict[str, tuple[float, float]]
    job_count_accuracy: float
    is_job_post_accuracy: float
    injection: dict
    relevance_gold_facts: dict
    relevance_predicted: dict
    cost_usd: float
    errors: list[str] = field(default_factory=list)
    misses: list[dict] = field(default_factory=list)
    digest: Optional[dict] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def evaluate_extractor(extractor: Extractor, posts: Optional[list[dict]] = None,
                       prefs: Optional[Preferences] = None, scorer=score_job) -> EvalReport:
    posts = posts or load_posts()
    prefs = prefs or load_prefs()
    per_field: dict[str, list[bool]] = defaultdict(list)
    count_ok, jobpost_ok, cost, errors, misses = [], [], 0.0, [], []
    inj_tp = inj_fp = inj_fn = 0
    gold_tiers, pred_tiers, gold_fact_tiers = [], [], []
    for p in posts:
        g = p["gold"]
        r = extractor.extract(raw_post(p))
        cost += r.cost_usd
        if r.error:
            errors.append(f"{p['id']}: {r.error}")
        verdict = screen_post(p["text"])
        flagged = verdict.flagged or r.extraction.injection_suspected
        inj_tp += flagged and g["injection"]
        inj_fp += flagged and not g["injection"]
        inj_fn += (not flagged) and g["injection"]
        ex, findings = validate_extraction(r.extraction, p["text"])
        jobpost_ok.append(ex.is_job_post == g["is_job_post"])
        if g["jobs"]:
            count_ok.append(len(ex.jobs) == len(g["jobs"]))
        aligned = align(ex.jobs, g["jobs"])
        for gj, pj in zip(g["jobs"], aligned):
            fs = field_scores(pj, gj)
            for f, ok in fs.items():
                per_field[f].append(ok)
            bad = [f for f, ok in fs.items() if not ok]
            if bad:
                misses.append({"post": p["id"], "gold_title": gj["title"], "wrong": bad,
                               "pred": pj.model_dump(include={"title", "company", "location", "work_mode", "seniority",
                                                              "years_required", "hardware_oriented", "apply"})
                               if pj else None})
            susp = flagged or (pj is not None and any(f.severity == "block" for f in
                                                      findings[ex.jobs.index(pj)]))
            pred_tiers.append(scorer(pj, prefs, suspicious=susp)["tier"] if pj else "skip")
            gold_tiers.append(gj["tier"])
            gold_fact_tiers.append(scorer(gold_posting(gj), prefs, suspicious=g["injection"])["tier"])
    acc = {f: sum(v) / len(v) for f, v in per_field.items()}
    ci = {}
    for f, v in per_field.items():
        c = wilson_ci(sum(v), len(v))
        ci[f] = (round(c.low, 3), round(c.high, 3))
    return EvalReport(
        extractor=extractor.name, n_posts=len(posts), n_gold_jobs=len(gold_tiers), field_accuracy=acc, field_ci=ci,
        job_count_accuracy=sum(count_ok) / max(1, len(count_ok)),
        is_job_post_accuracy=sum(jobpost_ok) / len(jobpost_ok),
        injection=prf(inj_tp, inj_fp, inj_fn),
        relevance_gold_facts=relevance(gold_fact_tiers, gold_tiers),
        relevance_predicted=relevance(pred_tiers, gold_tiers),
        cost_usd=cost, errors=errors, misses=misses)


# ---------------------------------------------------------------- digest correctness
SLOTS_OF_DAY = ["2026-11-01T08:30", "2026-11-01T15:00", "2026-11-01T21:00"]


def expected_digests(posts: list[dict]) -> dict[str, dict[str, set]]:
    """Per slot: the dedup groups that must be delivered, by gold tier, given the slot windows."""
    seen, out = set(), {}
    prev = None
    for slot in SLOTS_OF_DAY:
        end = datetime.fromisoformat(slot + ":00+02:00")
        exp = {"match": set(), "maybe": set(), "skip": set()}
        for p in sorted(posts, key=lambda x: x["ts"]):
            ts = datetime.fromisoformat(p["ts"])
            in_window = ts <= end and (prev is None or ts > prev or
                                       (p["source"] == "airtable" and slot.endswith("08:30")))
            if not in_window:
                continue
            for j in p["gold"]["jobs"]:
                if j["group"] in seen:
                    continue
                seen.add(j["group"])
                exp[j["tier"]].add(j["group"])
        out[slot] = exp
        prev = end
    return out


def evaluate_digests(make_extractor, posts: Optional[list[dict]] = None, prefs: Optional[Preferences] = None,
                     hooks=None) -> dict:
    """Replay the day through the real Pipeline (fresh in-memory store, FileDelivery to a temp dir)."""
    import tempfile

    from .delivery import FileDelivery
    from .pipeline import Pipeline
    from .sources import FixtureSource
    from .store import Store

    posts = posts or load_posts()
    prefs = prefs or load_prefs()
    by_key = {f"{p['source']}:{p['id']}": p for p in posts}
    wa = FixtureSource([raw_post(p) for p in posts if p["source"] == "whatsapp"], name="whatsapp")
    at = FixtureSource([raw_post(p) for p in posts if p["source"] == "airtable"], name="airtable")
    store = Store(":memory:")
    expected = expected_digests(posts)
    slots, delivered_all, repeats = {}, Counter(), 0
    with tempfile.TemporaryDirectory() as tmp:
        pipe = Pipeline(sources=[wa, at], extractor=make_extractor(), prefs=prefs, store=store,
                        delivery=FileDelivery(tmp), hooks=hooks, trace=False,
                        first_run_lookback=__import__("datetime").timedelta(hours=12))
        for slot in SLOTS_OF_DAY:
            res = pipe.run(slot)
            got = {"match": set(), "maybe": set(), "skip": set()}
            d = res.digest
            for tier, jobs in (("match", d.matches), ("maybe", d.maybes), ("skip", d.others)) if d else ():
                for j in jobs:
                    gp = by_key.get(j.post_key)
                    group = None
                    if gp and gp["gold"]["jobs"]:
                        al = align([j.posting], gp["gold"]["jobs"])
                        idx = next((i for i, a in enumerate(al) if a is not None), None)
                        group = gp["gold"]["jobs"][idx]["group"] if idx is not None else None
                    group = group or f"spurious:{j.post_key}#{j.job_index}"
                    got[tier].add(group)
                    delivered_all[group] += 1
            exp = expected[slot]
            slots[slot] = {
                "match_exact": got["match"] == exp["match"],
                "missing_match": sorted(exp["match"] - got["match"]),
                "extra_match": sorted(got["match"] - exp["match"]),
                "shown_recall": len((got["match"] | got["maybe"]) & (exp["match"] | exp["maybe"]))
                / max(1, len(exp["match"] | exp["maybe"])),
                "delivered": sum(len(v) for v in got.values()),
                "error": res.error,
            }
        repeats = sum(1 for g, n in delivered_all.items() if n > 1)
        rerun = pipe.run(SLOTS_OF_DAY[-1])  # idempotency: the same slot again must be skipped
    return {"slots": slots, "groups_delivered_twice": repeats, "rerun_skipped": rerun.skipped,
            "slot_exact_rate": sum(s["match_exact"] for s in slots.values()) / len(slots)}


def format_report(r: EvalReport) -> str:
    lines = [f"Extractor: {r.extractor} | posts {r.n_posts} | gold jobs {r.n_gold_jobs} | cost ${r.cost_usd:.4f}",
             "", "Extraction, per-field accuracy (95% Wilson CI):"]
    for f in FIELDS:
        lo, hi = r.field_ci[f]
        lines.append(f"  - {f:18s} {r.field_accuracy[f]:.3f}  [{lo:.2f}-{hi:.2f}]")
    lines += [f"  - job count exact   {r.job_count_accuracy:.3f}", f"  - is_job_post       {r.is_job_post_accuracy:.3f}",
              f"Injection detection: precision {r.injection['precision']:.2f} recall {r.injection['recall']:.2f} "
              f"(tp {r.injection['tp']}, fp {r.injection['fp']}, fn {r.injection['fn']})", "",
              "Relevance (match tier / shown = match+maybe):"]
    for name, rel in (("gold facts (matcher only)", r.relevance_gold_facts),
                      ("predicted facts (end to end)", r.relevance_predicted)):
        m, s = rel["match"], rel["shown"]
        lines.append(f"  - {name}: match P {m['precision']:.2f} R {m['recall']:.2f} | shown P {s['precision']:.2f} "
                     f"R {s['recall']:.2f} | tier accuracy {rel['tier_accuracy']:.2f}")
    if r.digest:
        lines += ["", f"Digest: slots exactly right (match tier) {r.digest['slot_exact_rate']:.2f}, "
                      f"groups delivered twice {r.digest['groups_delivered_twice']}, "
                      f"re-run skipped {r.digest['rerun_skipped']}"]
        for slot, s in r.digest["slots"].items():
            lines.append(f"  - {slot}: delivered {s['delivered']}, missing {s['missing_match']}, extra {s['extra_match']}")
    if r.errors:
        lines += ["", "Errors: " + "; ".join(r.errors[:10])]
    return "\n".join(lines)
