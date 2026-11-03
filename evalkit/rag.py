"""The lesson-9 RAG baseline as an evalkit System, plus its scorer.

    from evalkit.rag import RagSystem, rag_scorer, PROMPTS
    sys_v1 = RagSystem(index, llm, prompt="v1")      # version: "rag|v1:<hash>|k=5|<model>|<index>"
    run = run_system(sys_v1, acme_golden(), cache=OutputCache("results/cache"))
    score_run(run, ds, [rag_scorer()])

PROMPTS holds two system-prompt versions used by the regression-gate experiment:
  v1  ragkit's prompt, which includes the rule "If sources disagree, prefer the one with the
      latest effective_date".
  v2  a "cleanup" that shortens the prompt and, in doing so, drops that rule. It looks
      harmless in review. Exercise 6 shows what it does to version-conflict questions.

Offline, ragkit's ExtractiveAnswerer ignores the system prompt entirely, so it cannot show a
prompt regression. RuleFollowingAnswerer is a SIMULATION of a model that obeys the version
rule when (and only when) the prompt contains it: before extracting, it drops sources that
belong to the same policy family as a source with a later effective_date. It is honest
about being a simulation; the live run with Haiku measures whether a real model reacts to
the prompt change the same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any, Callable, Optional

from llmkit import ChatRequest, Message
from ragkit.fake import ExtractiveAnswerer
from ragkit.rag import SYSTEM as RAGKIT_SYSTEM
from ragkit.rag import answer as rag_answer

from .dataset import Example, stable_hash
from .metrics import abstained, citation_scores, fact_coverage, mrr, recall_at_k

VERSION_RULE = "- If sources disagree, prefer the one with the latest effective_date, and say that an older version said otherwise.\n"

PROMPTS: dict[str, str] = {
    "v1": RAGKIT_SYSTEM,
    # v2: "shorter, friendlier prompt" -- the version rule was merged away.
    "v2": RAGKIT_SYSTEM.replace(VERSION_RULE, "").replace(
        "Answer in the language of the question, in at most 4 sentences.",
        "Answer in the language of the question, briefly and helpfully."),
}
assert VERSION_RULE.strip() in PROMPTS["v1"] and VERSION_RULE.strip() not in PROMPTS["v2"]


# ------------------------------------------------------------------ simulated rule follower
_SOURCE_BLOCK = re.compile(r"<source id=\"(\d+)\"([^>]*)>\n(.*?)\n</source>\n?", re.S)
_ATTR = re.compile(r"(\w+)=\"([^\"]*)\"")
_FAMILY = re.compile(r"\s*\((?:v?[\d.]+)\)\s*$")


def policy_family(title: str) -> str:
    """"Vacation Policy (2024)" -> "vacation policy"; "SaaS Access Policy (v2.1)" -> "saas access policy"."""
    return _FAMILY.sub("", unescape(title or "")).strip().lower()


@dataclass
class RuleFollowingAnswerer:
    """ExtractiveAnswerer that obeys the version rule if the system prompt contains it."""
    inner: ExtractiveAnswerer = field(default_factory=ExtractiveAnswerer)
    model: str = "fake-rule-follower"

    def complete(self, req: ChatRequest, **kw: Any):
        if "latest effective_date" in req.system_text:
            prompt = req.messages[-1].text
            blocks = [(m.group(0), dict(_ATTR.findall(m.group(2)))) for m in _SOURCE_BLOCK.finditer(prompt)]
            latest: dict[str, str] = {}
            for _, a in blocks:
                fam = policy_family(a.get("title", ""))
                if fam and a.get("effective_date", "") > latest.get(fam, ""):
                    latest[fam] = a.get("effective_date", "")
            for raw, a in blocks:
                fam = policy_family(a.get("title", ""))
                if fam and a.get("effective_date", "") < latest.get(fam, ""):
                    prompt = prompt.replace(raw, "")
            req = ChatRequest(messages=[Message("user", prompt)], system=req.system, max_tokens=req.max_tokens)
        res = self.inner.complete(req, **kw)
        res.model = self.model
        return res


# ------------------------------------------------------------------ the system
def index_fingerprint(index: Any) -> str:
    """A short hash of what is in the index (chunk ids and texts), for the system version."""
    chunks = getattr(index, "chunks", None) or getattr(index, "_chunks", None)
    if isinstance(chunks, dict):
        chunks = list(chunks.values())
    if not chunks:
        return "idx?"
    return stable_hash([(c.id, c.text) for c in chunks])[:8]


@dataclass
class RagSystem:
    retriever: Any
    llm: Any
    prompt: str = "v1"
    k: int = 5
    name: str = "acme-rag"
    index_tag: Optional[str] = None
    max_tokens: int = 400

    @property
    def model(self) -> str:
        prov = getattr(getattr(self.llm, "provider", None), "name", None)
        m = getattr(self.llm, "model", type(self.llm).__name__)
        return f"{prov}:{m}" if prov else str(m)

    @property
    def version(self) -> str:
        """Everything that can change an answer is in here, so the cache cannot mix versions."""
        tag = self.index_tag or index_fingerprint(self.retriever)
        return f"rag|{self.prompt}:{stable_hash(PROMPTS[self.prompt])[:6]}|k={self.k}|{self.model}|{tag}"

    def __call__(self, input: dict) -> dict:
        q = input["question"]
        hits = self.retriever.search(q, k=self.k)
        from ragkit.rag import build_request
        req = build_request(q, hits, max_tokens=self.max_tokens, system=PROMPTS[self.prompt])
        res = self.llm.complete(req)
        from ragkit.rag import RagAnswer, parse_citations
        ans = RagAnswer(question=q, text=res.text.strip(), hits=hits, citations=parse_citations(res.text),
                        result=res, request=req)
        return {
            "answer": ans.text,
            "cited_docs": ans.cited_doc_ids,
            "invalid_citations": ans.invalid_citations,
            "retrieved_docs": list(dict.fromkeys(h.chunk.doc_id for h in hits)),
            "contexts": [{"n": i + 1, "doc": h.chunk.doc_id, "title": h.chunk.title,
                          "effective_date": h.chunk.effective_date, "text": h.chunk.text}
                         for i, h in enumerate(hits)],
            "abstained": ans.abstained,
            "cost_usd": ans.cost_usd,
            "input_tokens": res.usage.input_tokens if res.usage else 0,
            "output_tokens": res.usage.output_tokens if res.usage else 0,
        }


# ------------------------------------------------------------------ scoring
FactFn = Callable[[str, list], Optional[float]]
CiteFn = Callable[[list, list, list], dict]


def rag_scorer(fact_fn: FactFn = fact_coverage, cite_fn: CiteFn = citation_scores, *, k: int = 5,
               min_facts: float = 0.5) -> Callable[[Example, dict], dict]:
    """Per-example metrics for a RAG output. `fact_fn` and `cite_fn` are pluggable so the lab
    can score with your mine.py versions.

    abstain_ok      answered an answerable question / abstained on an unanswerable one
    fact_coverage   share of answer_facts stated (answerable only)
    cite_precision, cite_recall, stale_cited
    recall@k, mrr   retrieval, by document (answerable only)
    answer_ok       the headline pass/fail: abstain_ok, and for answerable questions
                    fact_coverage >= min_facts and no stale citation
    """
    def score(ex: Example, out: dict) -> dict:
        e = ex.expected
        answerable = bool(e.get("source_ids"))
        ans = out.get("answer", "")
        did_abstain = out.get("abstained", abstained(ans))
        abstain_ok = (not did_abstain) if answerable else did_abstain
        cites = cite_fn(out.get("cited_docs", []), e.get("source_ids", []), e.get("stale_ids", []))
        fc = fact_fn(ans, e.get("answer_facts", [])) if answerable else None
        ok = abstain_ok and (not answerable or ((fc or 0.0) >= min_facts and not cites["stale"]))
        return {
            "abstain_ok": float(abstain_ok),
            "fact_coverage": fc,
            "cite_precision": cites["precision"],
            "cite_recall": cites["recall"],
            "stale_cited": float(cites["stale"]),
            f"recall@{k}": recall_at_k(out.get("retrieved_docs", []), e.get("source_ids", []), k),
            "mrr": mrr(out.get("retrieved_docs", []), e.get("source_ids", [])),
            "answer_ok": float(ok),
        }
    return score


RAG_METRICS = ["answer_ok", "abstain_ok", "fact_coverage", "cite_precision", "cite_recall", "stale_cited",
               "recall@5", "mrr"]


def judge_scorer(judge: Any, kinds: tuple[str, ...] = ("groundedness",)) -> Callable[[Example, dict], dict]:
    """Adds judge verdicts as metrics: groundedness -> grounded (1/0) and a label;
    correctness -> judge_correct (1 / 0.5 / 0); refusal -> refusal_ok."""
    def score(ex: Example, out: dict) -> dict:
        q, ans, ctx = ex.input["question"], out.get("answer", ""), out.get("contexts", [])
        s: dict[str, Any] = {}
        cost = 0.0
        if "groundedness" in kinds:
            r = judge.groundedness(q, ans, ctx)
            cost += r.cost_usd
            s["grounded"] = None if r.label is None else float(r.label == "grounded")
            s["groundedness_label"] = r.label
        if "correctness" in kinds:
            r = judge.correctness(q, ans, ex.expected.get("answer_facts", []))
            cost += r.cost_usd
            s["judge_correct"] = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}.get(r.label or "", None)
        if "refusal" in kinds:
            r = judge.refusal(q, ans, ctx)
            cost += r.cost_usd
            s["refusal_ok"] = None if r.label is None else float(r.label == "appropriate")
        s["judge_cost_usd"] = cost
        return s
    return score


def run_one(question: str, retriever: Any, llm: Any, k: int = 5):
    """Convenience for notebooks: ragkit's own answer loop."""
    return rag_answer(question, retriever, llm, k=k)
