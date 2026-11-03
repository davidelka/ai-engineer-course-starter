"""Eval reports: Markdown (for a PR comment or a commit) and a self-contained HTML page.

No tables on purpose: per-slice results are lists of "metric value [CI]" lines, which read
well on a phone, in a PR comment and in right-to-left text alike.

    rep = build_report(run, dataset, RAG_METRICS, baseline=base, gate_results=results)
    Path("results/report.md").write_text(to_markdown(rep)); Path("results/report.html").write_text(to_html(rep))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Optional

from .dataset import Dataset
from .gates import GateResult
from .runner import Run
from .stats import bootstrap_ci, paired_compare


@dataclass
class Report:
    title: str
    run: Run
    dataset: Dataset
    overall: dict[str, Any] = field(default_factory=dict)        # metric -> CI or None
    slices: dict[str, dict[str, Any]] = field(default_factory=dict)  # slice -> metric -> (mean, n)
    comparison: dict[str, Any] = field(default_factory=dict)     # metric -> PairedResult
    gates: list[GateResult] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    baseline: Optional[Run] = None


def build_report(run: Run, dataset: Dataset, metrics: list[str], *, baseline: Optional[Run] = None,
                 gate_results: Optional[list[GateResult]] = None, fail_metric: str = "answer_ok",
                 title: str = "Eval report", max_failures: int = 40) -> Report:
    rep = Report(title, run, dataset, baseline=baseline, gates=gate_results or [])
    for m in metrics:
        vals = run.values(m)
        rep.overall[m] = bootstrap_ci(vals) if vals else None
    for name, ds in dataset.by("type").items():
        ids = ds.ids()
        rep.slices[name] = {m: (run.mean(m, ids), len(run.values(m, ids))) for m in metrics}
    if baseline is not None:
        common = [i for i in dataset.ids() if i in run.by_id() and i in baseline.by_id()]
        for m in metrics:
            ids = [i for i in common if run.by_id()[i].scores.get(m) is not None
                   and baseline.by_id()[i].scores.get(m) is not None]
            if ids:
                rep.comparison[m] = paired_compare(baseline.values(m, ids), run.values(m, ids))
    for rec in run.records:
        if rec.error or rec.scores.get(fail_metric, 1.0) < 1.0:
            ex = dataset[rec.example_id]
            rep.failures.append({"id": rec.example_id, "type": ex.type, "question": ex.input.get("question", ""),
                                 "answer": rec.output.get("answer", rec.error or ""),
                                 "reference": ex.expected.get("answer", ""),
                                 "scores": {k: v for k, v in rec.scores.items() if not isinstance(v, (list, dict))}})
    rep.failures = rep.failures[:max_failures]
    return rep


def _fmt(v: Any) -> str:
    return "-" if v is None else f"{v:.3f}"


def to_markdown(rep: Report) -> str:
    r = rep.run
    out = [f"# {rep.title}", "",
           f"- system: `{r.system_name}` version `{r.system_version}`",
           f"- dataset: `{rep.dataset.ref}` ({len(rep.dataset)} examples)",
           f"- records: {len(r.records)}, from cache: {r.cached_count}, errors: {len(r.errors)}, "
           f"new spend: ${r.cost_usd:.4f}"]
    if rep.baseline is not None:
        out.append(f"- baseline: `{rep.baseline.system_version}`")
    if rep.gates:
        ok = all(g.passed for g in rep.gates)
        out += ["", f"## Gates: {'PASS' if ok else 'FAIL'}", ""]
        out += [f"- {'PASS' if g.passed else '**FAIL**'} {g.rule}: {g.detail}" for g in rep.gates]
    out += ["", "## Overall (95% bootstrap CI)", ""]
    for m, ci in rep.overall.items():
        out.append(f"- **{m}**: " + ("-" if ci is None else f"{ci.estimate:.3f} [{ci.low:.3f}, {ci.high:.3f}] n={ci.n}"))
    if rep.comparison:
        out += ["", "## Candidate vs baseline (paired)", ""]
        for m, pr in rep.comparison.items():
            out.append(f"- **{m}**: {pr}")
    out += ["", "## By question type", ""]
    for name, row in rep.slices.items():
        bits = ", ".join(f"{m} {_fmt(v)} (n={n})" for m, (v, n) in row.items() if n)
        out.append(f"- **{name}**: {bits}")
    if rep.failures:
        out += ["", f"## Failures ({len(rep.failures)} shown)", ""]
        for f in rep.failures:
            out.append(f"- **{f['id']}** [{f['type']}] {f['question']}")
            out.append(f"  - answer: {f['answer'][:240]}")
            out.append(f"  - reference: {f['reference'][:240]}")
    return "\n".join(out) + "\n"


CSS = """
:root{--ink:#1d2330;--muted:#5d6678;--line:#dde2ea;--surface:#fff;--bg:#f5f7fa;--good:#1f7a4d;--bad:#b3261e;--accent:#2f5bd3}
@media (prefers-color-scheme: dark){:root{--ink:#e8ecf3;--muted:#a3adbf;--line:#334;--surface:#1b2030;--bg:#11151f;--good:#5fd39a;--bad:#ff8a80;--accent:#8fb0ff}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:1.5rem;margin:0 0 6px} h2{font-size:1.1rem;margin:28px 0 10px}
.meta{color:var(--muted);font-size:.9rem} code{font-size:.85em;word-break:break-all}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card b{display:block;font-size:.8rem;color:var(--muted);font-weight:600}
.card .v{font-size:1.35rem;font-weight:700} .card .ci{font-size:.8rem;color:var(--muted)}
.bar{height:6px;border-radius:3px;background:var(--line);margin-top:6px;position:relative;overflow:hidden}
.bar i{position:absolute;inset:0 auto 0 0;background:var(--accent)}
ul{padding-inline-start:20px} li{margin:4px 0}
.pass{color:var(--good);font-weight:700} .fail{color:var(--bad);font-weight:700}
details{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:6px 0}
summary{cursor:pointer} .small{font-size:.85rem;color:var(--muted)}
"""


def to_html(rep: Report) -> str:
    r = rep.run
    e = escape
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
             f"content='width=device-width,initial-scale=1'><title>{e(rep.title)}</title><style>{CSS}</style></head>"
             f"<body><main><h1>{e(rep.title)}</h1>",
             f"<p class='meta'>system <code>{e(r.system_version)}</code><br>dataset <code>{e(rep.dataset.ref)}</code>"
             f" · {len(r.records)} records · {r.cached_count} from cache · {len(r.errors)} errors · new spend ${r.cost_usd:.4f}</p>"]
    if rep.gates:
        ok = all(g.passed for g in rep.gates)
        parts.append(f"<h2>Gates: <span class='{'pass' if ok else 'fail'}'>{'PASS' if ok else 'FAIL'}</span></h2><ul>")
        for g in rep.gates:
            parts.append(f"<li><span class='{'pass' if g.passed else 'fail'}'>{'PASS' if g.passed else 'FAIL'}</span> "
                         f"<b>{e(g.rule)}</b><br><span class='small'>{e(g.detail)}</span></li>")
        parts.append("</ul>")
    parts.append("<h2>Overall, with 95% bootstrap confidence intervals</h2><div class='cards'>")
    for m, ci in rep.overall.items():
        if ci is None:
            continue
        w = max(0.0, min(1.0, ci.estimate)) * 100
        parts.append(f"<div class='card'><b>{e(m)}</b><span class='v'>{ci.estimate:.3f}</span>"
                     f"<div class='ci'>{ci.low:.3f} – {ci.high:.3f} · n={ci.n}</div><div class='bar'><i style='width:{w:.0f}%'></i></div></div>")
    parts.append("</div>")
    if rep.comparison:
        parts.append("<h2>Candidate vs baseline (paired bootstrap)</h2><ul>")
        for m, pr in rep.comparison.items():
            cls = "fail" if pr.significant and pr.diff < 0 else ("pass" if pr.significant else "")
            parts.append(f"<li><b>{e(m)}</b>: <span class='{cls}'>{pr.diff:+.3f}</span> "
                         f"<span class='small'>(CI {pr.low:+.3f}..{pr.high:+.3f}, p={pr.p_value:.3f}, "
                         f"+{pr.wins} / -{pr.losses}, n={pr.n}) {e(pr.verdict())}</span></li>")
        parts.append("</ul>")
    parts.append("<h2>By question type</h2>")
    for name, row in rep.slices.items():
        items = "".join(f"<li>{e(m)}: <b>{_fmt(v)}</b> <span class='small'>n={n}</span></li>" for m, (v, n) in row.items() if n)
        parts.append(f"<details><summary><b>{e(name)}</b></summary><ul>{items}</ul></details>")
    if rep.failures:
        parts.append(f"<h2>Failures ({len(rep.failures)} shown)</h2>")
        for f in rep.failures:
            sc = ", ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in f["scores"].items() if v is not None)
            parts.append(f"<details><summary><b>{e(f['id'])}</b> [{e(f['type'])}] {e(f['question'][:110])}</summary>"
                         f"<p><b>answer</b><br>{e(f['answer'])}</p><p><b>reference</b><br>{e(f['reference'])}</p>"
                         f"<p class='small'>{e(sc)}</p></details>")
    parts.append("</main></body></html>")
    return "".join(parts)
