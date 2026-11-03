"""Evaluation of the whole assistant on the golden set (79 questions) and the data questions (16).

    rep = evaluate(Assistant(settings))          # everything below, as one dict
    print(format_report(rep))

Five measurements, each answering a different question:

1. answers (docs path, role "security" so every golden source is visible): for each golden
   question, run the REAL assistant (router, retrieval with ACL, packing, the answer model,
   citations) and score it, per question type:
     context_recall@k   share of the golden source docs that reached the prompt
     answer_ok          ragkit.diagnose.outcome: not refused (or refused, if unanswerable), facts
                        covered, grounded, a golden source cited, no stale or invented citation
     fact_coverage      share of the golden answer_facts the answer states (evalkit, lexical)
     citation P / R     cited docs vs golden source docs (evalkit.citation_scores)
     stale_cited        cites a superseded version (golden tag stale:<id>)
     grounded           claim-level groundedness judge (ragkit.diagnose.check_claims; offline a
                        lexical stand-in, live Haiku)
     abstain_ok         unanswerable -> refused; answerable -> answered
2. diagnosis: every failed question gets ONE root-cause stage (ragkit.diagnose.classify, lesson
   13): missing_from_corpus ... not_retrieved, ranked_low, stale_version, false_refusal,
   ignored_context, hallucination, wrong_citation, failed_to_refuse. The fix depends on the stage.
3. router: golden questions must go to the documents, data questions to the database; the data
   answers are compared to the gold rows (execution accuracy, datakit.results_match), and a
   role that may not see a table must not get rows.
4. acl: for every role, run retrieval for every golden question and check every candidate chunk
   against the ACL matrix (guardkit.acl.acl_allows, an independent implementation). Leaks must be 0.
5. ablation: recall@5 / MRR / stale@5 of each retrieval stage (ragkit.ablation), same chunks.

Cost: offline 0. Live (Haiku 5.5, 79 answers + judge + 16 SQL plans): see the README; the run
prints its own total.
"""

from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Optional

from ragkit.acme import acme_qa

from .assistant import Assistant
from .retrieval import ROLES, acl_filter, build_retriever, visible_docs
from .router import DATA_ROLE, data_questions

TYPES = ("single_hop", "multi_hop", "numeric", "version_conflict", "acronym", "hebrew", "unanswerable")


def _mean(xs) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _p(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def stale_of(q: dict) -> list[str]:
    return [t.split(":", 1)[1] for t in (q.get("tags") or []) if t.startswith("stale:")]


# ------------------------------------------------------------------ 1+2: answers and diagnosis
def evaluate_answers(a: Assistant, qa: list[dict], *, role: str = "security", judge: bool = True,
                     progress: Optional[Callable[[int, int], None]] = None) -> list[dict]:
    from evalkit.metrics import citation_scores, fact_coverage
    from ragkit.diagnose import Case, classify, quote_locations, quote_status_map
    from ragkit.evaluate import norm
    from ragkit.tokens import get_tokenizer

    coverage = quote_status_map(a.job.documents(), a.job.all_chunks(), qa)
    judge_llm = a.s.make_judge_llm() if judge else None
    tok = get_tokenizer("approx")
    rows = []
    for i, q in enumerate(qa, 1):
        res = a.ask(q["question"], role)
        srcs = list(q.get("source_ids") or [])
        ctx_texts = [h.chunk.text for h in res.context]
        ctx_docs = [h.chunk.doc_id for h in res.context]
        cited = res.cited_doc_ids
        quotes = [sq["quote"] for sq in q.get("source_quotes", [])]
        locs = quote_locations(quotes, ctx_texts) if quotes else []
        grounded, gscore, gcost = None, None, 0.0
        if judge_llm is not None and res.kind == "docs" and not res.refused and res.text:
            from ragkit.diagnose import check_claims
            g = check_claims(res.text, ctx_texts, judge_llm)
            grounded, gscore, gcost = g.grounded, g.score, g.cost_usd
        fc = fact_coverage(res.text, q.get("answer_facts") or []) if srcs else None
        cs = citation_scores(cited, srcs, stale_of(q))
        case = Case(qid=q["id"], qtype=q.get("type", ""), question=q["question"], source_ids=srcs,
                    quote_status=list(coverage.get(q["id"], ["covered"] * len(quotes))), stale_ids=stale_of(q),
                    candidates=[h.chunk.doc_id for h in res.candidates], context=ctx_docs,
                    evidence_positions=sorted({p for s in locs for p in s}),
                    context_tokens=sum(tok.count(norm(t)) for t in ctx_texts), answer=res.text,
                    abstained=res.refused, cited=cited, invalid_citations=len(res.invalid_citations),
                    fact_coverage=fc, grounded=grounded)
        d = classify(case)
        rows.append({
            "id": q["id"], "type": q.get("type", ""), "question": q["question"], "route": res.route.get("kind"),
            "final_route": res.kind, "fallback": bool(res.route.get("fallback")),
            "answer": res.text, "refused": res.refused, "source_ids": srcs, "context_docs": ctx_docs,
            "candidate_docs": list(dict.fromkeys(h.chunk.doc_id for h in res.candidates)),
            "cited": cited, "invalid_citations": res.invalid_citations,
            "context_recall": (len(set(srcs) & set(ctx_docs)) / len(srcs)) if srcs else None,
            "fact_coverage": fc, "citation_precision": cs["precision"] if srcs else None,
            "citation_recall": cs["recall"] if srcs else None, "stale_cited": cs["stale"],
            "grounded": grounded, "groundedness": gscore,
            "abstain_ok": res.refused if not srcs else not res.refused,
            "answer_ok": d.ok, "stage": d.stage, "flags": d.flags, "path": d.path,
            "cost_usd": res.cost_usd + gcost, "answer_cost_usd": res.cost_usd, "latency_ms": res.latency_ms,
            "ttft_ms": res.ttft_ms, "usage": res.usage, "error": res.error,
        })
        if progress:
            progress(i, len(qa))
    return rows


def summarize_answers(rows: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups["ALL"].append(r)
        groups[r["type"]].append(r)
    out = {}
    for g in ["ALL", *TYPES]:
        rs = groups.get(g, [])
        if not rs:
            continue
        out[g] = {
            "n": len(rs),
            "answer_ok": _mean([float(r["answer_ok"]) for r in rs]),
            "context_recall": _mean([r["context_recall"] for r in rs]),
            "fact_coverage": _mean([r["fact_coverage"] for r in rs]),
            "citation_precision": _mean([r["citation_precision"] for r in rs]),
            "citation_recall": _mean([r["citation_recall"] for r in rs]),
            "grounded": _mean([None if r["grounded"] is None else float(r["grounded"]) for r in rs]),
            "abstain_ok": _mean([float(r["abstain_ok"]) for r in rs]),
            "stale_cited": sum(1 for r in rs if r["stale_cited"]),
            "invalid_citations": sum(len(r["invalid_citations"]) for r in rs),
        }
    lat = [r["latency_ms"] for r in rows]
    out["_cost"] = {"answers_usd": round(sum(r["answer_cost_usd"] for r in rows), 5),
                    "total_usd": round(sum(r["cost_usd"] for r in rows), 5),
                    "p50_ms": round(statistics.median(lat), 1) if lat else 0.0, "p95_ms": round(_p(lat, 0.95), 1),
                    "cached_input_tokens": sum((r["usage"] or {}).get("cached_input_tokens", 0) for r in rows),
                    "input_tokens": sum((r["usage"] or {}).get("input_tokens", 0) for r in rows)}
    return out


def diagnosis_summary(rows: list[dict]) -> dict:
    from ragkit.diagnose import FIXES, STAGE_GROUP
    by_type: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_type["ALL"][r["stage"]] += 1
        by_type[r["type"]][r["stage"]] += 1
    groups = Counter(STAGE_GROUP.get(r["stage"], "ok") for r in rows)
    fixes = {s: {"lesson": FIXES[s].lesson, "action": FIXES[s].action} for s in by_type["ALL"] if s in FIXES}
    return {"by_type": {k: dict(v) for k, v in by_type.items()}, "by_group": dict(groups), "fixes": fixes}


# ------------------------------------------------------------------ 3: router + data path
def evaluate_router(a: Assistant, qa: list[dict]) -> dict:
    from datakit.evaluate import results_match
    doc_wrong = [q["id"] for q in qa if a.hooks.route_question(q["question"]).kind != "docs"]
    dq = list(data_questions())
    rows = []
    for d in dq:
        first = a.hooks.route_question(d["question"]).kind
        role = d["roles"][0]
        res = a.data.answer(d["question"], role) if first == "data" else None
        correct = bool(res and res.status == "ok" and results_match(res.rows, d["rows"]))
        denied = [r for r in ROLES if r not in d["roles"]]
        leak = None
        if denied and first == "data":
            other = a.data.answer(d["question"], denied[0])
            leak = {"role": denied[0], "status": other.status, "rows": len(other.rows)}
        rows.append({"id": d["id"], "lang": d["lang"], "question": d["question"], "routed": first, "role": role,
                     "status": res.status if res else None, "correct": correct, "denied_check": leak,
                     "cost_usd": res.cost_usd if res else 0.0})
    return {
        "golden_to_docs": len(qa) - len(doc_wrong), "golden_n": len(qa), "golden_misrouted": doc_wrong,
        "data_to_data": sum(r["routed"] == "data" for r in rows), "data_n": len(rows),
        "execution_accuracy": _mean([float(r["correct"]) for r in rows]),
        "denied_leaks": sum(1 for r in rows if r["denied_check"] and r["denied_check"]["rows"] > 0),
        "rows": rows,
    }


# ------------------------------------------------------------------ 4: ACL
def acl_reference(role: str, meta: dict) -> bool:
    """The ACL matrix checked by a SECOND implementation, not by the filter under test.
    guardkit.acl (lesson 24) knows 6 roles; ragkit's acl_where (lesson 11) adds "finance". For a
    role guardkit does not know, the matrix is restated here: public -> everyone; internal -> not
    contractors; confidential -> security, or the role's own department."""
    from guardkit.acl import acl_allows
    from guardkit.types import ROLES as GUARD_ROLES
    if role in GUARD_ROLES:
        return acl_allows(role, meta)
    from ragkit.vectors.filters import ROLE_DEPARTMENT
    cls = str(meta.get("classification") or "").lower()
    if cls == "public":
        return True
    if cls == "internal":
        return role != "contractor"
    if cls == "confidential":
        return role == "security" or (ROLE_DEPARTMENT.get(role) is not None and ROLE_DEPARTMENT.get(role) == meta.get("department"))
    return False


def evaluate_acl(a: Assistant, qa: list[dict]) -> dict:
    from guardkit.types import ROLES as GUARD_ROLES
    out = {}
    for role in ROLES:
        vis = set(visible_docs(role, a.job.docs))
        leaks, answerable = 0, 0
        for q in qa:
            hits = a.retriever.search(q["question"], k=a.s.fetch_k, where=acl_filter(role))
            leaks += sum(1 for h in hits if not acl_reference(role, h.chunk.meta))
            if q.get("source_ids") and set(q["source_ids"]) <= vis:
                answerable += 1
        out[role] = {"visible_docs": len(vis), "leaks": leaks, "golden_answerable": answerable,
                     "checked_by": "guardkit.acl" if role in GUARD_ROLES else "restated matrix (guardkit has no such role)",
                     "hidden": sorted(set(a.job.docs) - vis)}
    return out


# ------------------------------------------------------------------ 5: ablation
def evaluate_ablation(a: Assistant, qa: list[dict]) -> list[dict]:
    from ragkit.ablation import evaluate_stage
    from ragkit.rerank import RerankingRetriever, make_reranker
    stages = [("bm25", build_retriever(a.job, upto="bm25")), ("dense", build_retriever(a.job, upto="dense")),
              ("hybrid (RRF)", build_retriever(a.job, upto="hybrid")),
              ("+ versions", build_retriever(a.job, upto="versions"))]
    stages.append(("+ rerank (fake)", RerankingRetriever(stages[-1][1], make_reranker("fake"), fetch_k=30)))
    out = []
    for name, r in stages:
        rep = evaluate_stage(name, r, qa)
        out.append({"stage": name, "table": {g: {k: round(v, 4) for k, v in row.items()} for g, row in rep.table.items()},
                    "stale5": round(rep.stale5, 4), "p50_ms": round(rep.p50, 2), "p95_ms": round(rep.p95, 2)})
    return out


# ------------------------------------------------------------------ all of it
def evaluate(a: Assistant, qa: Optional[list[dict]] = None, *, judge: bool = True, parts: tuple = ("answers", "router", "acl", "ablation"),
             progress: Optional[Callable[[int, int], None]] = None) -> dict:
    qa = qa if qa is not None else acme_qa()
    t0 = time.perf_counter()
    rep: dict[str, Any] = {"settings": a.s.describe(), "mode": a.s.mode, "embedder": a.s.embedder, "model": a.s.answer_model_name,
                           "hooks": dict(a.hooks.using), "n_questions": len(qa)}
    if "answers" in parts:
        rows = evaluate_answers(a, qa, judge=judge, progress=progress)
        rep["rows"] = rows
        rep["answers"] = summarize_answers(rows)
        rep["diagnosis"] = diagnosis_summary(rows)
    if "router" in parts:
        rep["router"] = evaluate_router(a, qa)
    if "acl" in parts:
        rep["acl"] = evaluate_acl(a, qa)
    if "ablation" in parts:
        rep["ablation"] = evaluate_ablation(a, qa)
    rep["seconds"] = round(time.perf_counter() - t0, 1)
    return rep


def _f(v) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def format_report(rep: dict, misses: bool = False) -> str:
    L = [f"settings: {rep['settings']}", f"your code: {rep.get('hooks')}"]
    if "answers" in rep:
        L.append("\nanswers (role=security, the real assistant end to end):")
        for g, m in rep["answers"].items():
            if g.startswith("_"):
                continue
            L.append(f"- {g} (n={m['n']}): answer_ok {_f(m['answer_ok'])}, context_recall {_f(m['context_recall'])}, "
                     f"facts {_f(m['fact_coverage'])}, cite P {_f(m['citation_precision'])} R {_f(m['citation_recall'])}, "
                     f"grounded {_f(m['grounded'])}, abstain_ok {_f(m['abstain_ok'])}, stale cited {m['stale_cited']}, "
                     f"invalid [n] {m['invalid_citations']}")
        c = rep["answers"]["_cost"]
        if rep.get("mode") != "live":
            L.append("  (offline: the answers come from an extractive stand-in, not a model, and 'grounded' from a lexical "
                     "judge. Costs below are ESTIMATES of replayed calls priced as Haiku.)")
        L.append(f"- cost: answers ${c['answers_usd']:.4f}, with judge ${c['total_usd']:.4f}; latency p50 {c['p50_ms']} ms, "
                 f"p95 {c['p95_ms']} ms; cached input tokens {c['cached_input_tokens']} of {c['input_tokens']}")
        L.append("\ndiagnosis (root-cause stage of every question; ok = passed):")
        for g, cnt in rep["diagnosis"]["by_type"].items():
            L.append(f"- {g}: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
        for s, fx in rep["diagnosis"]["fixes"].items():
            L.append(f"  fix for {s} (lesson {fx['lesson']}): {fx['action']}")
        if misses:
            L.append("\nfailed questions:")
            for r in rep["rows"]:
                if not r["answer_ok"]:
                    L.append(f"- {r['id']} [{r['type']}] {r['stage']}: {r['question']}\n    answer: {r['answer'][:160]}"
                             f"\n    sources {r['source_ids']} | prompt {r['context_docs']} | cited {r['cited']}")
    if "router" in rep:
        r = rep["router"]
        L.append(f"\nrouter: golden -> docs {r['golden_to_docs']}/{r['golden_n']} (misrouted, fall back to docs if the "
                 f"planner says not answerable: {r['golden_misrouted']}); data -> data {r['data_to_data']}/{r['data_n']}; "
                 f"execution accuracy {_f(r['execution_accuracy'])}; rows leaked to a denied role: {r['denied_leaks']}")
    if "acl" in rep:
        L.append("\nacl (retrieval for every golden question, every candidate checked by guardkit.acl):")
        for role, m in rep["acl"].items():
            L.append(f"- {role}: sees {m['visible_docs']} docs, leaks {m['leaks']} (checked by {m['checked_by']}), "
                     f"golden questions with all sources visible {m['golden_answerable']}")
    if "ablation" in rep:
        L.append("\nablation (retrieval only, document level, role=security):")
        for st in rep["ablation"]:
            t = st["table"]
            L.append(f"- {st['stage']}: recall@5 ALL {t['ALL']['recall@5']:.3f}, multi_hop {t['multi_hop']['recall@5']:.3f}, "
                     f"version_conflict {t['version_conflict']['recall@5']:.3f}, cross-lingual "
                     f"{t.get('cross-lingual', {}).get('recall@5', float('nan')):.3f}; MRR {t['ALL']['mrr']:.3f}; "
                     f"stale@5 {st['stale5']:.2f}; p50 {st['p50_ms']} ms")
    L.append(f"\n{rep.get('seconds', 0)} s")
    return "\n".join(L)
