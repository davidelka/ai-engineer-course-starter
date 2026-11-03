"""A small HTML report per run: results/runs/<slot>.html (+ the obskit trace waterfall).

Hebrew, right-to-left, lists instead of tables. What to look at first: the counts line, the
cost, the safety findings, and why each job got its tier.
"""

from __future__ import annotations

import html
from pathlib import Path

from .match import CAT_HE

CSS = """body{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;line-height:1.5;
color:#1d1d1f;background:#fafafa}h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:28px;border-bottom:1px solid #ddd}
.k{display:inline-block;background:#fff;border:1px solid #ddd;border-radius:8px;padding:6px 10px;margin:3px}
.match{border-right:4px solid #2e7d32}.maybe{border-right:4px solid #f9a825}.skip{border-right:4px solid #bbb}
.dup{opacity:.6}li{margin:6px 0;padding:6px 10px;background:#fff;border-radius:6px}.r{color:#555;font-size:.9rem}
pre{background:#fff;border:1px solid #ddd;padding:12px;white-space:pre-wrap;direction:rtl;text-align:right}
.warn{color:#b71c1c}code{direction:ltr;unicode-bidi:embed}
@media (prefers-color-scheme: dark){body{background:#151515;color:#eee}li,.k,pre{background:#222;border-color:#333}
.r{color:#aaa}}"""


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def render_report(res) -> str:
    from obskit import summarize

    s = summarize(res.spans) if res.spans else {"by_type": {}, "latency": {}}
    reposts = sum(1 for o in res.posts if o.repost_of)
    flagged = sum(1 for o in res.posts if o.flagged)
    dups = sum(1 for j in res.all_jobs if j.duplicate_of)
    d = res.digest
    parts = [f"<!doctype html><html lang='he' dir='rtl'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>Job agent run {_e(res.run_id)}</title>"
             f"<style>{CSS}</style></head><body>",
             f"<h1>ריצה <code>{_e(res.run_id)}</code>{' (דולגה: ' + _e(res.reason) + ')' if res.skipped else ''}</h1>"]
    if res.error:
        parts.append(f"<p class='warn'>שגיאה: {_e(res.error)}</p>")
    kv = [("פוסטים חדשים", res.posts_new), ("פרסומים חוזרים", reposts), ("משרות חדשות", len(res.new_jobs)),
          ("כפילויות שסוננו", dups), ("התאמות בדיגסט", len(d.matches) if d else 0), ("פוסטים חשודים", flagged),
          ("קריאות למודל", res.llm_calls), ("עלות", f"${res.cost_usd:.4f}"),
          ("זמן ריצה (p50 של ספאנים)", f"{s.get('latency', {}).get('p50_ms', 0):.0f}ms"),
          ("טיוטות Gmail", sum(1 for r in res.drafts if r.ok))]
    parts.append("<div>" + "".join(f"<span class='k'>{_e(k)}: <b>{_e(v)}</b></span>" for k, v in kv) + "</div>")
    if d:
        parts.append(f"<h2>הדיגסט שנשלח</h2><pre>{_e(d.text)}</pre>")
    parts.append("<h2>משרות לפי דרגה</h2><ul>")
    for j in sorted(res.all_jobs, key=lambda j: (j.duplicate_of is not None, {"match": 0, "maybe": 1, "skip": 2}[j.tier],
                                                 -j.score)):
        p = j.posting
        cls = j.tier + (" dup" if j.duplicate_of else "")
        tag = " · כפילות" if j.duplicate_of else ""
        warn = " <span class='warn'>⚠ חשוד</span>" if j.suspicious else ""
        reasons = "<br>".join(_e(r) for r in j.reasons)
        findings = ", ".join(_e(f.code) for f in j.findings)
        parts.append(f"<li class='{cls}'><b>{_e(p.title)}</b> · {_e(p.company or '?')} · {_e(p.location or '?')} · "
                     f"{_e(CAT_HE.get(j.category or '', j.category or '-'))} · ציון {j.score} ({_e(j.tier)}){tag}{warn}"
                     f"<div class='r'>{reasons}</div>"
                     + (f"<div class='r warn'>ממצאים: {findings}</div>" if findings else "")
                     + f"<div class='r'><code>{_e(j.post_key)}</code></div></li>")
    parts.append("</ul><h2>ספאנים לפי סוג</h2><ul>")
    for t, v in s.get("by_type", {}).items():
        parts.append(f"<li>{_e(t)}: {v['count']} ספאנים, p50 {v['p50_ms']:.1f}ms, p95 {v['p95_ms']:.1f}ms, "
                     f"שגיאות {v['errors']}</li>")
    parts.append("</ul><p class='r'>את מפל הספאנים המלא (obskit viewer) פותחים בקובץ <code>.traces.html</code> שליד הקובץ הזה, עם אותו שם.</p></body></html>")
    return "".join(parts)


def write_report(res, results_dir) -> Path:
    from obskit.viewer import render_html

    out = Path(results_dir) / "runs"
    out.mkdir(parents=True, exist_ok=True)
    name = res.run_id.replace(":", "")
    path = out / f"{name}.html"
    path.write_text(render_report(res), encoding="utf-8")
    if res.spans:
        (out / f"{name}.traces.html").write_text(render_html(res.spans, title=f"job agent {res.run_id}"),
                                                encoding="utf-8")
    return path
