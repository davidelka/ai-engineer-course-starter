"""A small offline trace viewer: JSONL spans -> one self-contained HTML file (waterfall).

    python -m obskit.viewer results/traces.jsonl -o results/traces.html [--feedback feedback.jsonl]

No server, no CDN, no build step: open the file in a browser. It is the offline fallback
for Phoenix or Langfuse, and it is small enough to read: about 150 lines of JS.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from .analyze import span_type
from .exporters import load_spans

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f2f4f7;--surface:#fff;--ink:#141a2e;--muted:#586079;--line:#d9dde7;--accent:#2446c4;--bad:#b3261e;--code:#eef1f6;
--t-llm:#2446c4;--t-retrieval:#1f7a4d;--t-tool:#c56a06;--t-agent:#6b4fbb;--t-cache:#0f7c8c;--t-guard:#8a5a00;--t-other:#7a8299}
@media (prefers-color-scheme:dark){:root{--bg:#0e1220;--surface:#161b2d;--ink:#e7e9f3;--muted:#9aa1bb;--line:#2a3150;--accent:#8ea3ff;--bad:#ff8f85;--code:#1d2338;
--t-llm:#8ea3ff;--t-retrieval:#5fd09a;--t-tool:#f2a43a;--t-agent:#b9a4ff;--t-cache:#5fd0dc;--t-guard:#e0b04a;--t-other:#9aa1bb}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,"Segoe UI",sans-serif}
header{padding:12px 16px;border-bottom:1px solid var(--line);background:var(--surface)}
header h1{margin:0;font-size:1.05rem}.guide{direction:rtl;text-align:right;color:var(--muted);font-size:.85rem;margin-top:4px}
main{display:grid;grid-template-columns:minmax(0,300px) minmax(0,1fr);gap:12px;padding:12px 16px}
@media (max-width:760px){main{grid-template-columns:minmax(0,1fr)}}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px;min-width:0}
.tr{display:grid;gap:2px;padding:7px 8px;border-radius:8px;cursor:pointer;border:1px solid transparent}
.tr:hover{background:var(--code)}.tr.sel{border-color:var(--accent);background:var(--code)}
.tr b{font-size:.85rem;overflow-wrap:anywhere}.tr small{color:var(--muted);font-family:ui-monospace,monospace;font-size:.72rem}
.err{color:var(--bad);font-weight:600}.fb{font-size:.75rem}
.wf{display:grid;gap:3px}.row{display:grid;grid-template-columns:minmax(0,38%) minmax(0,1fr);gap:8px;align-items:center;cursor:pointer;padding:2px 4px;border-radius:6px}
.row:hover,.row.sel{background:var(--code)}.nm{font-family:ui-monospace,monospace;font-size:.75rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lane{position:relative;height:18px;background:var(--code);border-radius:4px}
.bar{position:absolute;top:3px;height:12px;border-radius:3px;min-width:2px}.bar.e{outline:2px solid var(--bad)}
.ev{position:absolute;top:0;width:2px;height:18px;background:var(--bad);opacity:.8}
.dur{position:absolute;top:1px;font-size:.66rem;font-family:ui-monospace,monospace;color:var(--muted);white-space:nowrap}
.axis{display:flex;justify-content:space-between;font-size:.68rem;color:var(--muted);font-family:ui-monospace,monospace;margin:4px 0 6px 38%}
.legend{display:flex;flex-wrap:wrap;gap:8px;font-size:.72rem;margin:6px 0}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-inline-end:4px;vertical-align:-1px}
dl{display:grid;grid-template-columns:minmax(0,1fr);gap:2px;margin:6px 0}dt{font-family:ui-monospace,monospace;font-size:.72rem;color:var(--muted);margin-top:6px}
dd{margin:0;font-family:ui-monospace,monospace;font-size:.78rem;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--code);padding:3px 6px;border-radius:5px}
h2{font-size:.95rem;margin:4px 0 8px}h3{font-size:.85rem;margin:12px 0 2px}.muted{color:var(--muted)}
</style></head><body>
<header><h1>__TITLE__</h1>
<div class="guide">משמאל: רשימת ה-traces (שם, משך, עלות, שגיאה, משוב משתמש). לחיצה על trace מציגה את ה-waterfall: כל שורה היא span, ההזחה היא היררכיית האב והילד, והפס מראה מתי ה-span התחיל ונגמר ביחס לתחילת הבקשה. קו אדום על פס הוא event (למשל retry). לחיצה על שורה מציגה את כל ה-attributes שלה.</div></header>
<main><div class="panel" id="list"></div><div class="panel"><div id="wf"></div><div id="detail"></div></div></main>
<script>
const SPANS=__SPANS__, FEEDBACK=__FEEDBACK__;
const COLORS=["llm","retrieval","tool","agent","cache","guard","other"];
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const traces={};for(const s of SPANS){(traces[s.trace_id]=traces[s.trace_id]||[]).push(s)}
const ids=new Set(SPANS.map(s=>s.span_id));
function root(ss){const r=ss.filter(s=>!s.parent_id||!ids.has(s.parent_id));return r.sort((a,b)=>a.start_ms-b.start_ms)[0]}
function cost(ss){return ss.reduce((a,s)=>a+(+(s.attributes["obskit.cost_usd"]||0)),0)}
function fmtT(ms){const d=new Date(ms);return d.toISOString().slice(5,19).replace("T"," ")}
const order=Object.keys(traces).sort((a,b)=>root(traces[a]).start_ms-root(traces[b]).start_ms);
function list(){const el=document.getElementById("list");el.innerHTML=`<h2>${order.length} traces</h2>`+order.map(t=>{const ss=traces[t],r=root(ss),f=FEEDBACK[t];
const err=ss.some(s=>s.status==="ERROR");return `<div class="tr" data-t="${t}"><b>${esc(r.name)}</b><small>${fmtT(r.start_ms)} · ${r.duration_ms.toFixed(0)} ms · $${cost(ss).toFixed(6)} · ${t.slice(0,8)}</small>
${err?'<small class="err">ERROR</small>':""}${f?`<span class="fb">${f.rating>0?"👍":"👎"} ${esc(f.comment||"")}</span>`:""}</div>`}).join("");
el.querySelectorAll(".tr").forEach(d=>d.onclick=()=>show(d.dataset.t))}
function tree(ss){const kids={};for(const s of ss){const p=s.parent_id&&ss.some(x=>x.span_id===s.parent_id)?s.parent_id:"_";(kids[p]=kids[p]||[]).push(s)}
for(const k in kids)kids[k].sort((a,b)=>a.start_ms-b.start_ms);const out=[];(function walk(p,d){for(const s of kids[p]||[]){out.push([d,s]);walk(s.span_id,d+1)}})("_",0);return out}
function show(t){document.querySelectorAll(".tr").forEach(d=>d.classList.toggle("sel",d.dataset.t===t));
const ss=traces[t],r=root(ss),t0=Math.min(...ss.map(s=>s.start_ms)),t1=Math.max(...ss.map(s=>s.end_ms)),W=Math.max(1,t1-t0);
const rows=tree(ss).map(([d,s])=>{const L=(s.start_ms-t0)/W*100,Wd=Math.max(.4,s.duration_ms/W*100),ty=s.attributes["obskit.span.type"]||"other";
const evs=(s.events||[]).map(e=>`<i class="ev" style="left:${(e.time_ms-t0)/W*100}%" title="${esc(e.name)}"></i>`).join("");
const lab=L+Wd>78?`right:${100-L+1}%`:`left:${L+Wd+1}%`;
return `<div class="row" data-s="${s.span_id}"><div class="nm" style="padding-left:${d*12}px">${esc(s.name)}</div><div class="lane"><i class="bar${s.status==="ERROR"?" e":""}" style="left:${L}%;width:${Wd}%;background:var(--t-${COLORS.includes(ty)?ty:"other"})"></i>${evs}<span class="dur" style="${lab}">${s.duration_ms.toFixed(0)} ms</span></div></div>`}).join("");
const f=FEEDBACK[t];
document.getElementById("wf").innerHTML=`<h2>${esc(r.name)} <span class="muted">· ${W.toFixed(0)} ms · $${cost(ss).toFixed(6)}</span></h2>${f?`<div class="fb">user feedback: ${f.rating>0?"👍":"👎"} ${esc(f.comment||"")}</div>`:""}
<div class="legend">${COLORS.map(c=>`<span><i style="background:var(--t-${c})"></i>${c}</span>`).join("")}<span><i style="background:var(--bad)"></i>event / error</span></div>
<div class="axis"><span>0</span><span>${(W/2).toFixed(0)} ms</span><span>${W.toFixed(0)} ms</span></div><div class="wf">${rows}</div>`;
document.querySelectorAll(".row").forEach(d=>d.onclick=()=>detail(ss.find(s=>s.span_id===d.dataset.s)));detail(r)}
function pretty(v){if(typeof v==="string"&&/^[\[{]/.test(v)){try{return JSON.stringify(JSON.parse(v),null,1)}catch(e){}}return typeof v==="string"?v:JSON.stringify(v)}
function detail(s){document.querySelectorAll(".row").forEach(d=>d.classList.toggle("sel",d.dataset.s===s.span_id));
const a=Object.entries(s.attributes).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(pretty(v))}</dd>`).join("");
const ev=(s.events||[]).map(e=>`<dt>+${(e.time_ms-s.start_ms).toFixed(0)} ms · ${esc(e.name)}</dt><dd>${esc(JSON.stringify(e.attributes))}</dd>`).join("");
document.getElementById("detail").innerHTML=`<h3>${esc(s.name)}</h3><div class="muted" style="font-size:.75rem">kind ${s.kind} · status ${s.status}${s.status_message?": "+esc(s.status_message):""} · span ${s.span_id} · ${s.duration_ms.toFixed(1)} ms</div><dl>${a}</dl>${ev?`<h3>events</h3><dl>${ev}</dl>`:""}`}
list();if(order.length)show(order[0]);
</script></body></html>"""


def render_html(spans: Iterable[dict], *, title: str = "obskit traces", feedback: Optional[dict] = None) -> str:
    spans = list(spans)
    for s in spans:  # make sure every span has a type the colors understand
        s.setdefault("attributes", {}).setdefault("obskit.span.type", span_type(s))
    data = json.dumps(spans, ensure_ascii=False).replace("</", "<\\/")
    fb = json.dumps(feedback or {}, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__TITLE__", title).replace("__SPANS__", data).replace("__FEEDBACK__", fb)


def load_feedback(path) -> dict:
    """feedback.jsonl lines {"trace_id", "rating": 1|-1, "comment"} -> {trace_id: {...}}."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["trace_id"]] = d
    return out


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m obskit.viewer", description="JSONL spans -> HTML waterfall")
    p.add_argument("jsonl")
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--feedback", default=None)
    p.add_argument("--title", default=None)
    a = p.parse_args(argv)
    spans = load_spans(a.jsonl)
    out = Path(a.out or Path(a.jsonl).with_suffix(".html"))
    fb = load_feedback(a.feedback) if a.feedback else None
    out.write_text(render_html(spans, title=a.title or Path(a.jsonl).name, feedback=fb), encoding="utf-8")
    print(f"wrote {out}  ({len(spans)} spans). Open it in a browser.")


if __name__ == "__main__":
    main()
