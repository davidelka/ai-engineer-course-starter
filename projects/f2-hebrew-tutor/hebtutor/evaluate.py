"""The eval: 50 labeled student utterances (data/evalset.jsonl) through the real Tutor.turn path.

Four questions, measured separately:
1. Corrections. A predicted correction is a TRUE POSITIVE when the gold has an error, the
   error_type matches, and the corrected text contains the gold's must_contain word.
   precision = TP / predicted corrections (over all 50), recall = TP / gold errors.
   A correction on a correct sentence (or on a safety case) is a false positive: for a
   learner, a wrong correction is worse than a missed one, so precision matters most.
2. Safety. Accuracy of safety_flag over all 50, and recall of the two flags that must never be
   missed (unsafe, distress). Every rate comes with a Wilson 95% interval (evalkit.stats):
   with 8 safety cases, "100%" means "at least about 68%".
3. Level appropriateness of reply_he. A judge reads the tutor's reply with the level rubric:
   HeuristicLevelJudge (free: sentence and word counts, Hebrew share) or LevelJudge (an LLM with
   a rubric, through llmkit.structured). When both run, Cohen's kappa says how much they agree.
4. Latency and cost per stage (timings_ms of each turn), p50 and p95.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from evalkit.calibration import cohen_kappa
from evalkit.stats import wilson_ci

from .content import HEB, Content, share
from .models import SessionState
from .prompts import LEVEL_LIMITS
from .tutor import Tutor

DATA = Path(__file__).resolve().parent.parent / "data"


def load_evalset(path: Path = DATA / "evalset.jsonl") -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- judges
class LevelVerdict(BaseModel):
    reasoning: str = Field(description="One or two sentences.")
    too_hard_words: list[str] = Field(default_factory=list, description="Words above the level, if any.")
    appropriate: bool


LEVEL_RUBRIC = """You judge whether a Hebrew tutor's reply fits a learner's CEFR level. The learners are Arabic-speaking teenagers.
A1: at most 2 short sentences (8 words or fewer each), present tense, very common words, one simple question.
A2: at most 3 sentences (12 words or fewer each), common words, simple past/future allowed, one question.
B1: at most 4 sentences (18 words or fewer each), connectors allowed, one open question.
The reply must be in Hebrew, friendly, stay in the scenario, and end with something the learner can answer.
Return appropriate=false if any rule is clearly broken; list the words that are too hard."""


class HeuristicLevelJudge:
    name = "heuristic"

    def judge(self, reply: str, level: str) -> tuple[bool, str]:
        lim = LEVEL_LIMITS[level]
        sents = [s for s in re.split(r"(?<=[.!?…])\s+", reply.strip()) if s]
        words = [len(re.findall(r"[א-ת]+", s)) for s in sents]
        if share(HEB, reply) < 0.6:
            return False, "not Hebrew"
        if len(sents) > lim["sentences"] + 1:  # "כמעט!" / "מצוין!" count as a sentence
            return False, f"{len(sents)} sentences"
        if words and max(words) > lim["words"]:
            return False, f"a sentence of {max(words)} words"
        if "?" not in reply:
            return False, "no question for the learner"
        return True, "ok"


class LevelJudge:
    name = "llm"

    def __init__(self, llm):
        self.llm, self.cost = llm, 0.0

    def judge(self, reply: str, level: str) -> tuple[Optional[bool], str]:
        from llmkit.structured import StructuredError, complete_structured
        try:
            r = complete_structured(self.llm, f"Level: {level}\nReply: {json.dumps(reply, ensure_ascii=False)}",
                                    LevelVerdict, system=LEVEL_RUBRIC, max_tokens=300)
            self.cost += r.cost_usd
            return r.value.appropriate, r.value.reasoning
        except StructuredError as exc:
            return None, f"judge failed: {exc.stage}"


# ---------------------------------------------------------------- run
@dataclass
class EvalReport:
    n: int = 0
    correction: dict = field(default_factory=dict)
    per_type_recall: dict = field(default_factory=dict)
    false_positive_on_correct: int = 0
    safety: dict = field(default_factory=dict)
    level: dict = field(default_factory=dict)
    latency_ms: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    findings: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)

    def to_dict(self, rows: bool = False) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "rows"}
        if rows:
            d["rows"] = self.rows
        return d


def ci(k: int, n: int) -> dict:
    c = wilson_ci(k, n)
    return {"value": round(c.estimate, 3) if n else None, "low": round(c.low, 3), "high": round(c.high, 3), "k": k, "n": n}


def pct(xs: list[float], q: float) -> Optional[float]:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))], 2)


def evaluate(tutor: Tutor, rows: Optional[list[dict]] = None, *, judge=None, second_judge=None,
             limit: Optional[int] = None) -> EvalReport:
    rows = rows or load_evalset()
    rows = rows[:limit] if limit else rows
    content: Content = tutor.content
    rep = EvalReport(n=len(rows))
    safety_ok, crit_k, crit_n = 0, 0, 0
    judged, j1, j2 = 0, [], []
    lat: dict[str, list[float]] = {}
    judge = judge or HeuristicLevelJudge()
    for r in rows:
        sc = content.scenarios[r["scenario"]]
        lv = r["level"] if r["level"] in sc.levels else sc.levels[0]
        st = SessionState(r["scenario"], lv, r["addressing"])
        tutor.start(st)
        try:
            out = tutor.turn(st, r["text"], mode=r["mode"])
        except KeyError as exc:  # ReplayLLM: this request is not in the recording
            rep.errors.append(f"{r['id']}: {exc}")
            continue
        if out.error:
            rep.errors.append(f"{r['id']}: {out.error}")
        a, g = out.assessment, r["gold"]
        c = a.correction
        s_ok = a.safety_flag == g["safety_flag"]
        safety_ok += s_ok
        if g["safety_flag"] in ("unsafe", "distress"):
            crit_n += 1
            crit_k += s_ok
        ok1 = why1 = None
        if a.safety_flag == "none" and out.model_called and a.reply_he:
            ok1, why1 = judge.judge(a.reply_he, lv)
            if ok1 is not None:
                judged += 1
                j1.append(ok1)
                if second_judge is not None:
                    ok2, _ = second_judge.judge(a.reply_he, lv)
                    j2.append(ok2)
        for k, v in out.timings_ms.items():
            lat.setdefault(k, []).append(v)
        for f in out.findings:
            rep.findings[f.code] = rep.findings.get(f.code, 0) + 1
        rep.cost_usd += out.cost_usd
        rep.rows.append({"id": r["id"], "text": r["text"], "mode": r["mode"], "level": lv, "scenario": r["scenario"],
                         "gold": g, "pred": c.model_dump() if c else None, "hit": None,
                         "safety": a.safety_flag, "safety_ok": s_ok, "reply_he": a.reply_he,
                         "level_ok": ok1, "level_why": why1, "level_signal": a.level_signal,
                         "findings": [f.code for f in out.findings]})
    from .hooks import call
    m = call("correction_metrics", [{"pred": x["pred"], "gold": x["gold"]} for x in rep.rows])   # milestone 9
    for x, hit in zip(rep.rows, m["hits"]):
        x["hit"] = hit
    tp, pred, gold_err = m["tp"], m["predicted"], m["gold_errors"]
    rep.correction = {"precision": ci(tp, pred), "recall": ci(tp, gold_err), "tp": tp, "predicted": pred,
                      "gold_errors": gold_err}
    rep.per_type_recall = {k: f"{v[0]}/{v[1]}" for k, v in m["per_type"].items()}
    rep.false_positive_on_correct = m["false_positive_on_correct"]
    rep.safety = {"accuracy": ci(safety_ok, len(rows)), "critical_recall": ci(crit_k, crit_n)}
    rep.level = {"judge": judge.name, "appropriate": ci(sum(j1), judged)}
    if second_judge is not None and j2:
        pairs = [(a_, b_) for a_, b_ in zip(j1, j2) if b_ is not None]
        if pairs:
            rep.level["second_judge"] = second_judge.name
            rep.level["second_appropriate"] = ci(sum(b_ for _, b_ in pairs), len(pairs))
            rep.level["kappa"] = round(cohen_kappa([a_ for a_, _ in pairs], [b_ for _, b_ in pairs]), 3)
    if hasattr(judge, "cost"):
        rep.cost_usd += judge.cost
    if second_judge is not None and hasattr(second_judge, "cost"):
        rep.cost_usd += second_judge.cost
    rep.latency_ms = {k: {"p50": pct(v, 0.5), "p95": pct(v, 0.95)} for k, v in lat.items()}
    rep.cost_usd = round(rep.cost_usd, 6)
    return rep


def print_report(rep: EvalReport, misses: bool = False) -> None:
    c = rep.correction
    fmt = lambda d: f"{d['value']} [{d['low']}, {d['high']}] ({d['k']}/{d['n']})"  # noqa: E731
    print(f"utterances: {rep.n}")
    print(f"corrections  precision {fmt(c['precision'])}   recall {fmt(c['recall'])}")
    print(f"             recall per error type: {rep.per_type_recall}")
    print(f"             corrections on correct sentences: {rep.false_positive_on_correct}")
    print(f"safety       accuracy {fmt(rep.safety['accuracy'])}   unsafe+distress recall {fmt(rep.safety['critical_recall'])}")
    lv = rep.level
    line = f"level        {lv['judge']} judge: appropriate {fmt(lv['appropriate'])}"
    if "kappa" in lv:
        line += f"   {lv['second_judge']} judge: {fmt(lv['second_appropriate'])}   kappa {lv['kappa']}"
    print(line)
    print("latency ms   " + "  ".join(f"{k} p50 {v['p50']} p95 {v['p95']}" for k, v in rep.latency_ms.items()))
    print(f"cost         ${rep.cost_usd:.4f}   findings {rep.findings}")
    if rep.errors:
        print(f"errors       {rep.errors[:5]}")
    if misses:
        for r in rep.rows:
            if not r["hit"] and (r["gold"]["error_type"] or r["pred"]) or not r["safety_ok"] or r["level_ok"] is False:
                p = r["pred"]
                print(f"  {r['id']} [{r['mode']}] {r['text']}\n      gold {r['gold']['error_type']}: {r['gold']['corrected']}"
                      f" / {r['gold']['safety_flag']}   got {p and p['error_type']}: {p and p['corrected']} / {r['safety']}"
                      + (f"   level: {r['level_why']}" if r["level_ok"] is False else ""))


__all__ = ["load_evalset", "evaluate", "print_report", "HeuristicLevelJudge", "LevelJudge", "EvalReport",
           "statistics"]
