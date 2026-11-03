"""Exercises 6-7: extract Acme access requests and score every field against the golden set.

    python labs/03-structured-outputs/extract_eval.py --model anthropic:claude-haiku-5-5
    python labs/03-structured-outputs/extract_eval.py --model anthropic:claude-haiku-5-5 --mode prompt
    python labs/03-structured-outputs/extract_eval.py --model openai:gpt-5.4-mini --set hard --show
    python labs/03-structured-outputs/extract_eval.py --model mock:mock-model                # free, pipeline only
    python labs/03-structured-outputs/extract_eval.py --schema mine --set hard               # your validators

Reports: how many replies became valid objects (and after how many repairs),
accuracy per field, route accuracy, hallucinations (a value where the golden
answer is null), cost per 1,000 requests and latency.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
from acme_schema import SYSTEM_PROMPT, AccessRequest  # noqa: E402
from llmkit import LLM, LLMError, load_dotenv  # noqa: E402
from llmkit.structured import StructuredError, complete_structured  # noqa: E402

DATA = ROOT / "data" / "acme"
SETS = {"normal": ["access_requests.jsonl"], "hard": ["access_requests_hard.jsonl"],
        "all": ["access_requests.jsonl", "access_requests_hard.jsonl"]}
FIELDS = ["requester_name", "requester_email", "tool", "access_level", "production", "customer_data",
          "financial_data", "external_sharing", "duration_days", "route"]
NULLISH = (None, "", "unknown", "n/a", "none")


def norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def match(field: str, pred, exp) -> bool:
    if isinstance(exp, list):
        return any(match(field, pred, e) for e in exp)
    if exp is None:
        return pred is None
    if field == "requester_email":  # exact on purpose: normalization is exercise 5's job
        return pred == exp
    if isinstance(exp, str):
        return isinstance(pred, str) and norm(pred) == norm(exp)
    return pred == exp and type(pred) is type(exp)


def hallucinated(pred, exp) -> bool:
    exp_null = exp is None or (isinstance(exp, list) and None in exp)
    return exp_null and norm(pred) not in NULLISH


def run_case(llm, case, model, mode, effort, max_repairs, system):
    t0 = time.perf_counter()
    row = {"id": case["id"], "message": case["message"], "expected": case["expected"]}
    try:
        res = complete_structured(llm, case["message"], model, system=system, mode=mode,
                                  effort=effort, max_repairs=max_repairs, max_tokens=2000)
        row.update(ok=True, attempts=res.attempts, pred=res.value.model_dump(), cost=res.cost_usd,
                   errors=res.errors)
    except StructuredError as e:
        r = e.result
        row.update(ok=False, stage=e.stage, attempts=r.attempts if r else 0, pred=None,
                   cost=r.cost_usd if r else 0.0, errors=e.errors, last_text=e.last_text[:500])
    except LLMError as e:
        row.update(ok=False, stage="api", attempts=0, pred=None, cost=0.0, errors=[str(e)])
    row["latency_s"] = time.perf_counter() - t0
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic:claude-haiku-5-5")
    ap.add_argument("--mode", default="native", choices=["native", "prompt"])
    ap.add_argument("--set", default="normal", choices=list(SETS))
    ap.add_argument("--schema", default="reference", choices=["reference", "mine"])
    ap.add_argument("--effort", default="low")
    ap.add_argument("--max-repairs", type=int, default=2)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--show", action="store_true", help="print every wrong field")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))

    model = AccessRequest
    if a.schema == "mine":
        from mine import MyAccessRequest as model  # noqa: N813
    cases = [json.loads(x) for f in SETS[a.set] for x in (DATA / f).read_text(encoding="utf-8").splitlines() if x.strip()]
    cases = cases[: a.limit] if a.limit else cases
    system = SYSTEM_PROMPT.format(policy=(DATA / "saas_access_policy.md").read_text(encoding="utf-8"))
    llm = LLM(a.model)

    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(lambda c: run_case(llm, c, model, a.mode, a.effort or None, a.max_repairs, system), cases))

    per_field = {f: [0, 0] for f in FIELDS}
    halluc, route_ok, route_n = [], 0, 0
    for row in rows:
        exp, pred = row["expected"], row["pred"]
        marks = []
        for f in FIELDS:
            if f not in exp:
                continue
            got = pred.get(f) if pred else None
            ok = bool(pred) and match(f, got, exp[f])
            per_field[f][0] += ok
            per_field[f][1] += 1
            if pred and hallucinated(got, exp[f]):
                halluc.append(f"{row['id']}.{f}={got!r}")
            if not ok:
                marks.append(f"{f}: got {got!r}, expected {exp[f]!r}")
        if "route" in exp:
            route_n += 1
            route_ok += bool(pred) and pred.get("route") == exp["route"]
        status = "OK " if row["ok"] and not marks else ("ERR" if not row["ok"] else "MIS")
        extra = f" [{row.get('stage')}]" if not row["ok"] else ""
        print(f"{row['id']}  {status}{extra}  attempts={row['attempts']}  {row['latency_s']:5.2f}s  "
              f"{len(marks)} wrong field(s)")
        if a.show:
            for m in marks:
                print(f"      {m}")
            for err in row["errors"]:
                print("      repair: " + err.replace("\n", "\n              "))

    valid = [r for r in rows if r["ok"]]
    print(f"\n{a.model}  mode={a.mode}  set={a.set}  schema={a.schema}  effort={a.effort}")
    print(f"valid objects: {len(valid)}/{len(rows)}   first try: {sum(r['attempts'] == 1 for r in valid)}   "
          f"after repair: {sum(r['attempts'] > 1 for r in valid)}   failed: {len(rows) - len(valid)}")
    for stage in sorted({r.get('stage') for r in rows if not r['ok']}):
        print(f"  failed at {stage}: {sum(r.get('stage') == stage for r in rows)}")
    print("field accuracy:")
    for f, (ok, n) in per_field.items():
        if n:
            print(f"  {f:<18}{ok:>3}/{n:<3} {ok / n:6.0%}")
    if route_n:
        print(f"route accuracy: {route_ok}/{route_n}")
    print(f"hallucinations (value where the answer is null): {len(halluc)}" + (f"  {', '.join(halluc)}" if halluc else ""))
    costs = [r["cost"] for r in rows]
    print(f"cost: ${statistics.mean(costs) * 1000:.3f} per 1,000 requests   "
          f"latency p50: {statistics.median(r['latency_s'] for r in rows):.2f}s")

    out = LAB / "results" / f"{a.model.replace(':', '_')}-{a.mode}-{a.set}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"rows saved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
