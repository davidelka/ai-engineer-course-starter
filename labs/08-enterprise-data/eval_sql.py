"""Exercise 5: execution accuracy on the golden business questions.

    python labs/08-enterprise-data/eval_sql.py                       # offline replay, YOUR results_match
    python labs/08-enterprise-data/eval_sql.py --lenient             # allow extra columns
    python labs/08-enterprise-data/eval_sql.py --live                # Claude Haiku 5.5, ~27-35 calls, about $0.01
    python labs/08-enterprise-data/eval_sql.py --live --model openai:gpt-5.4-mini
    python labs/08-enterprise-data/eval_sql.py --only q09,q12 --show

The golden set (golden/business_questions.jsonl) has 27 questions: lookup, aggregate, metric,
join, time, incident, role, and 3 that must be REFUSED (PII for the role, an answer that lives in
a document, data that does not exist). A question with expect=rows is correct when the result
of the predicted SQL matches the golden result; expect=refuse is correct when the pipeline
ends as not_answerable (or rejected by the guard after its repair turn).
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

import _lab
from _lab import DEFAULT_MODEL, GOLDEN, RESULTS, make_llm, pick
from datakit.evaluate import mismatch_hint, summarize
from datakit.guard import guard_sql as ref_guard
from datakit.semantic import load_layer, policy_from_layer
from datakit.text2sql import Settings, answer_question


def load_golden(only: str = "") -> list[dict]:
    rows = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    if only:
        keep = {x.strip() for x in only.split(",")}
        rows = [r for r in rows if r["id"] in keep]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--reference", action="store_true", help="use the reference results_match")
    ap.add_argument("--lenient", action="store_true", help="allow extra predicted columns")
    ap.add_argument("--only", default="", help="comma-separated ids")
    ap.add_argument("--show", action="store_true", help="print SQL and results for every question")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    match, src = pick("results_match", a.reference)
    layer = load_layer()
    policy = policy_from_layer(layer)
    llm, label = make_llm(a.live, a.model)
    golden = load_golden(a.only)
    print(f"model: {label}   results_match: {src}   mode: {'lenient' if a.lenient else 'strict'}\n")

    # The guard must accept every golden query, or it caps accuracy no matter how good the model is.
    gold_ok = [g for g in golden if g["expect"] == "rows" and ref_guard(g["gold_sql"], policy, g["role"]).ok]
    n_rows = sum(g["expect"] == "rows" for g in golden)

    def run(g):
        s = Settings(role=g["role"], user=g["user"], layer=layer, narrate=False)
        t0 = time.perf_counter()
        ans = answer_question(llm, g["question"], s)
        row = {"id": g["id"], "category": g["category"], "role": g["role"], "expect": g["expect"],
               "status": ans.status, "attempts": ans.attempts, "errors": ans.errors, "sql": ans.sql_executed,
               "cost": ans.cost_usd, "latency_s": round(time.perf_counter() - t0, 2),
               "assumptions": (ans.plan or {}).get("assumptions", [])}
        if g["expect"] == "refuse":
            row["correct"] = ans.status in ("not_answerable", "rejected")
            row["hint"] = "" if row["correct"] else f"answered ({ans.status}) instead of refusing"
        else:
            ok = ans.status == "ok" and match(ans.rows, [tuple(r) for r in g["rows"]], ordered=g["ordered"],
                                              allow_extra_columns=a.lenient)
            row["correct"] = bool(ok)
            row["hint"] = "" if ok else (mismatch_hint(ans.rows, g["rows"]) if ans.status == "ok" else ans.status)
            row["pred_rows"] = [list(r) for r in ans.rows[:20]]
            row["gold_rows"] = g["rows"][:20]
        return row

    with ThreadPoolExecutor(max_workers=a.workers if a.live else 1) as ex:
        rows = list(ex.map(run, golden))

    for r, g in zip(rows, golden):
        mark = "PASS" if r["correct"] else "FAIL"
        extra = f"  repairs: {r['attempts'] - 1}" if r["attempts"] > 1 else ""
        print(f"{mark} {r['id']} [{r['category']:9}] {g['question'][:62]:62} {r['hint']}{extra}")
        if a.show or not r["correct"]:
            if r["sql"]:
                print(f"       sql : {r['sql']}")
            if r.get("pred_rows") is not None and not r["correct"]:
                print(f"       got : {r['pred_rows'][:4]}")
                print(f"       gold: {r['gold_rows'][:4]}   ({g['note'] or 'no note'})")
            for e in r["errors"]:
                print(f"       ! {e}")
    total = sum(r["correct"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    print(f"\nexecution accuracy: {total}/{len(rows)} = {total / max(1, len(rows)):.0%}")
    for cat, (c, n) in summarize(rows).items():
        print(f"  {cat:10} {c}/{n}")
    print(f"guard accepts {len(gold_ok)}/{n_rows} golden queries (anything less caps the score)")
    print(f"repair turns: {sum(r['attempts'] - 1 for r in rows if r['attempts'] > 1)}   "
          f"guard rejections: {sum(1 for r in rows for e in r['errors'] if e.startswith('guard'))}")
    print(f"cost: ${cost:.4f}{' (estimated: replay)' if not a.live else ''}")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"eval_{'live' if a.live else 'replay'}.json"
    out.write_text(json.dumps({"model": label, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"details: {out.relative_to(_lab.ROOT)}")


if __name__ == "__main__":
    main()
