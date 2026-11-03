"""Experiment runner: variants x cases x repeats -> logged rows -> summary.

Methodology from lesson 1, section "controlled experiment":
one variable per variant, a fixed case set, several repeats per case,
metrics chosen in advance, and everything logged so a run can be reproduced.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from .providers import CallSpec, Result, get_provider

PARAM_KEYS = ("provider", "model", "max_tokens", "temperature", "top_p", "top_k", "effort")


# ----------------------------------------------------------------- loading
def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def render(template: str, values: dict) -> str:
    """Replace {key} placeholders without choking on other braces (JSON, code)."""
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def format_examples(examples: list[dict], input_key: str, label_key: str) -> str:
    blocks = [
        f"<example>\n<request>{ex[input_key]}</request>\n<label>{ex[label_key]}</label>\n</example>"
        for ex in examples
    ]
    return "\n".join(blocks)


@dataclass
class Variant:
    name: str
    system: str
    user_template: str
    params: dict


@dataclass
class Experiment:
    name: str
    base_dir: Path
    cases: list[dict]
    variants: list[Variant]
    repeats: int = 5
    max_workers: int = 4
    scorer: str = "none"
    labels: list[str] = field(default_factory=list)
    expected_field: str = "label"
    prices: dict = field(default_factory=dict)
    results_dir: Path = Path("results")
    # Optional regex whose last match is used as the "answer" for the consistency
    # metrics, so different wording around the same final answer is not counted
    # as inconsistency. Example: "ANSWER:\s*(.+)"
    normalize_regex: Optional[str] = None


def _read_text_or_file(cfg: dict, key: str, base: Path, default: str = "") -> str:
    if key + "_file" in cfg:
        return (base / cfg[key + "_file"]).read_text(encoding="utf-8")
    return cfg.get(key, default)


def load_experiment(path: str | Path) -> Experiment:
    path = Path(path)
    base = path.parent
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = cfg.get("defaults", {})
    cases = load_jsonl(base / cfg["cases"])
    if cfg.get("limit_cases"):
        cases = cases[: cfg["limit_cases"]]

    variants: list[Variant] = []
    for vcfg in cfg["variants"]:
        merged = {**cfg, **defaults, **vcfg}  # variant overrides defaults overrides top level
        system = _read_text_or_file(vcfg, "system", base) or _read_text_or_file(cfg, "system", base)
        user_t = vcfg.get("user_template", cfg.get("user_template", "{input}"))

        examples_text = ""
        ex_cfg = vcfg.get("examples")
        if ex_cfg:
            examples = load_jsonl(base / ex_cfg["file"])[: ex_cfg.get("n")]
            examples_text = format_examples(
                examples, ex_cfg.get("input_key", "request"), ex_cfg.get("label_key", "label")
            )
        system = system.replace("{examples}", examples_text)

        for key, value in vcfg.get("context", {}).items():  # e.g. documents pasted into the prompt
            system = system.replace("{" + key + "}", (base / value).read_text(encoding="utf-8"))
            user_t = user_t.replace("{" + key + "}", (base / value).read_text(encoding="utf-8"))

        params = {k: merged[k] for k in PARAM_KEYS if merged.get(k) is not None}
        params.setdefault("max_tokens", 1024)
        variants.append(Variant(vcfg["name"], system, user_t, params))

    return Experiment(
        name=cfg["name"],
        base_dir=base,
        cases=cases,
        variants=variants,
        repeats=cfg.get("repeats", 5),
        max_workers=cfg.get("max_workers", 4),
        scorer=cfg.get("scorer", "none"),
        labels=cfg.get("labels", []),
        expected_field=cfg.get("expected_field", "label"),
        prices=cfg.get("prices") or {},
        results_dir=(base / cfg.get("results_dir", "../results")).resolve(),
        normalize_regex=cfg.get("normalize_regex"),
    )


# ----------------------------------------------------------------- scoring
def predict_label(text: str, labels: list[str]) -> Optional[str]:
    """First allowed label appearing in the output (by position), else None."""
    low = text.lower()
    hits = [(low.find(lab.lower()), lab) for lab in labels if lab.lower() in low]
    return min(hits)[1] if hits else None


def normalize(exp: Experiment, text: str) -> str:
    if exp.normalize_regex:
        hits = re.findall(exp.normalize_regex, text)
        if hits:
            return str(hits[-1]).strip().lower()
    return text.strip().lower()


def score(exp: Experiment, case: dict, text: str) -> tuple[Optional[bool], Optional[str]]:
    """Return (passed, normalized_output). normalized_output feeds the consistency metric."""
    passed, _ = _score(exp, case, text)
    return passed, (_ if exp.scorer == "label" else normalize(exp, text))


def _score(exp: Experiment, case: dict, text: str) -> tuple[Optional[bool], Optional[str]]:
    if exp.scorer == "label":
        pred = predict_label(text, exp.labels)
        return pred == case[exp.expected_field], pred
    if exp.scorer == "contains_any":
        low = text.lower()
        return any(s.lower() in low for s in case["expect_any"]), text.strip().lower()
    if exp.scorer == "expect_and_forbid":  # right fact present AND no forbidden phrase
        low = text.lower()
        ok = any(s.lower() in low for s in case["expect_any"]) and not any(
            s.lower() in low for s in case["forbid_any"]
        )
        return ok, text.strip().lower()
    if exp.scorer == "not_contains_any":  # e.g. an injected phrase must NOT leak into the answer
        low = text.lower()
        return not any(s.lower() in low for s in case["forbid_any"]), text.strip().lower()
    if exp.scorer == "exact":
        return text.strip().lower() == str(case[exp.expected_field]).strip().lower(), text.strip().lower()
    return None, text.strip().lower()


# ----------------------------------------------------------------- running
def run_experiment(
    exp: Experiment,
    out_dir: Path,
    only: Optional[list[str]] = None,
    call: Optional[Callable[[str, CallSpec], Result]] = None,
    progress: bool = True,
) -> Path:
    """Run all (variant, case, repeat) combinations; write one JSON line per call."""
    call = call or (lambda provider, spec: get_provider(provider)(spec))
    variants = [v for v in exp.variants if not only or v.name in only]
    jobs = [(v, i, c, r) for v in variants for i, c in enumerate(exp.cases) for r in range(exp.repeats)]

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{exp.name}-{stamp}.jsonl"

    def one(job):
        v, idx, case, rep = job
        spec = CallSpec(
            model=v.params["model"],
            system=render(v.system, case),
            user=render(v.user_template, case),
            max_tokens=v.params["max_tokens"],
            temperature=v.params.get("temperature"),
            top_p=v.params.get("top_p"),
            top_k=v.params.get("top_k"),
            effort=v.params.get("effort"),
        )
        res = call(v.params["provider"], spec)
        passed, norm = (None, None) if res.error else score(exp, case, res.text)
        return {
            "experiment": exp.name,
            "variant": v.name,
            "prompt_hash": hashlib.sha256((v.system + v.user_template).encode()).hexdigest()[:10],
            "params": v.params,
            "case_index": idx,
            "case_id": case.get("id", idx),
            "repeat": rep,
            "output": res.text,
            "normalized": norm,
            "passed": passed,
            "in_tokens": res.in_tokens,
            "out_tokens": res.out_tokens,
            "stop_reason": res.stop_reason,
            "latency_s": round(res.latency_s, 3),
            "error": res.error,
        }

    done = 0
    with out_path.open("w", encoding="utf-8") as fh, ThreadPoolExecutor(exp.max_workers) as pool:
        for row in pool.map(one, jobs):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            done += 1
            if progress and (done % 10 == 0 or done == len(jobs)):
                print(f"  {done}/{len(jobs)} calls", flush=True)
    return out_path


# ----------------------------------------------------------------- summary
def summarize(rows: list[dict], prices: Optional[dict] = None) -> list[dict]:
    prices = prices or {}
    by_variant: dict[str, list[dict]] = {}
    for row in rows:
        by_variant.setdefault(row["variant"], []).append(row)

    summary = []
    for name, vrows in by_variant.items():
        ok = [r for r in vrows if not r["error"]]
        scored = [r for r in ok if r["passed"] is not None]

        per_case: dict[Any, list] = {}
        for r in ok:
            per_case.setdefault(r["case_index"], []).append(r["normalized"])
        consistent = [len(set(outs)) == 1 for outs in per_case.values() if len(outs) > 1]
        distinct = [len(set(outs)) for outs in per_case.values()]

        lat = sorted(r["latency_s"] for r in ok)
        in_t = [r["in_tokens"] for r in ok]
        out_t = [r["out_tokens"] for r in ok]
        model = vrows[0]["params"].get("model", "")
        price = prices.get(model)
        cost_per_call = None
        if price and ok:
            cost_per_call = (
                statistics.mean(in_t) * price["input"] + statistics.mean(out_t) * price["output"]
            ) / 1_000_000

        pred_dist: dict[str, int] = {}
        for r in ok:
            key = str(r["normalized"]) if r["normalized"] is not None else "-"
            if len(key) <= 40:
                pred_dist[key] = pred_dist.get(key, 0) + 1

        summary.append(
            {
                "variant": name,
                "model": model,
                "calls": len(vrows),
                "errors": len(vrows) - len(ok),
                "first_error": next((r["error"] for r in vrows if r["error"]), None),
                "pass_rate": (sum(r["passed"] for r in scored) / len(scored)) if scored else None,
                "consistency": (sum(consistent) / len(consistent)) if consistent else None,
                "distinct_per_case": statistics.mean(distinct) if distinct else None,
                "in_tokens_mean": statistics.mean(in_t) if in_t else None,
                "out_tokens_mean": statistics.mean(out_t) if out_t else None,
                "latency_p50": lat[len(lat) // 2] if lat else None,
                "latency_p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
                "cost_per_1k_calls": cost_per_call * 1000 if cost_per_call is not None else None,
                "pred_dist": pred_dist,
            }
        )
    return summary


def format_summary(summary: list[dict]) -> str:
    def f(v, pct=False, nd=1):
        if v is None:
            return "-"
        return f"{v * 100:.0f}%" if pct else f"{v:.{nd}f}"

    head = f"{'variant':<22}{'pass':>7}{'consist':>9}{'distinct':>9}{'in_tok':>8}{'out_tok':>8}{'p50 s':>7}{'$/1k':>8}{'err':>5}"
    lines = [head, "-" * len(head)]
    for s in summary:
        lines.append(
            f"{s['variant'][:21]:<22}{f(s['pass_rate'], True):>7}{f(s['consistency'], True):>9}"
            f"{f(s['distinct_per_case']):>9}{f(s['in_tokens_mean'], nd=0):>8}{f(s['out_tokens_mean'], nd=0):>8}"
            f"{f(s['latency_p50'], nd=2):>7}{f(s['cost_per_1k_calls'], nd=2):>8}{s['errors']:>5}"
        )
    for s in summary:
        if s["first_error"]:
            lines.append(f"\n[{s['variant']}] first error: {s['first_error'][:300]}")
        if s["pred_dist"] and len(s["pred_dist"]) <= 6:
            dist = ", ".join(f"{k}: {v}" for k, v in sorted(s["pred_dist"].items()))
            lines.append(f"[{s['variant']}] outputs: {dist}")
    return "\n".join(lines)
