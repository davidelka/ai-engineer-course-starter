// Lesson 22 aids: trace waterfall (animation), forensic trace explorer, SLO burn-rate simulator, head vs tail sampling.
// Registered on window.AIDS; uses the hub helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l22-style";
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l22 { display: grid; gap: 12px; direction: rtl; min-width: 0; }
.l22 .l22-why { background: var(--accent-soft); border-radius: 10px; padding: 9px 12px; line-height: 1.7; font-size: .92rem; min-height: 4.2em; }
.l22 .l22-why b { color: var(--accent); }
.l22 .l22-wf { direction: ltr; display: grid; gap: 3px; min-width: 0; }
.l22 .l22-row { display: grid; grid-template-columns: minmax(0, 40%) minmax(0, 1fr); gap: 6px; align-items: center; padding: 2px 4px; border-radius: 6px; cursor: pointer; min-width: 0; }
.l22 .l22-row:hover, .l22 .l22-row.sel { background: var(--code-bg); }
.l22 .l22-row.new { animation: pop .45s ease; }
.l22 .l22-nm { font-family: var(--mono); font-size: .72rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: left; }
.l22 .l22-lane { position: relative; height: 18px; background: var(--code-bg); border-radius: 4px; overflow: hidden; }
.l22 .l22-bar { position: absolute; top: 3px; height: 12px; border-radius: 3px; min-width: 2px; transition: width .7s ease; }
.l22 .l22-bar.err { outline: 2px solid var(--bad); outline-offset: -1px; }
.l22 .l22-ev { position: absolute; top: 0; width: 3px; height: 18px; background: var(--bad); border-radius: 1px; }
.l22 .l22-dur { position: absolute; top: 2px; font-size: .62rem; font-family: var(--mono); color: var(--muted); white-space: nowrap; }
.l22 .t-llm { background: var(--accent); } .l22 .t-retrieval { background: var(--good); } .l22 .t-tool { background: var(--signal); }
.l22 .t-agent { background: color-mix(in srgb, var(--accent) 45%, var(--muted)); } .l22 .t-cache { background: color-mix(in srgb, var(--good) 50%, var(--accent)); }
.l22 .t-other { background: var(--muted); }
.l22 .l22-axis { direction: ltr; display: flex; justify-content: space-between; font-size: .64rem; color: var(--muted); font-family: var(--mono); padding-left: calc(40% + 10px); }
.l22 .l22-legend { direction: ltr; display: flex; flex-wrap: wrap; gap: 8px; font-size: .7rem; }
.l22 .l22-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
.l22 .l22-attrs { direction: ltr; text-align: left; font-family: var(--mono); font-size: .72rem; background: var(--code-bg); border-radius: 8px; padding: 8px 10px; display: grid; gap: 2px; min-height: 6em; overflow-wrap: anywhere; }
.l22 .l22-attrs .hd { font-family: var(--font); font-size: .78rem; font-weight: 600; margin-bottom: 2px; }
.l22 .l22-attrs .k { color: var(--muted); }
.l22 .l22-attrs .fresh { background: var(--signal-soft); border-radius: 4px; animation: pop .45s ease; }
.l22 .l22-attrs .ev { color: var(--bad); }
.l22 .l22-list { display: grid; gap: 4px; }
.l22 .l22-tr { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: center; border: 1px solid var(--line); border-radius: 9px; padding: 6px 9px; cursor: pointer; background: var(--surface); text-align: right; font: inherit; color: inherit; }
.l22 .l22-tr.sel { border-color: var(--accent); background: var(--accent-soft); }
.l22 .l22-tr .q { font-size: .82rem; direction: ltr; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.l22 .l22-tr .m { font-family: var(--mono); font-size: .7rem; color: var(--muted); direction: ltr; white-space: nowrap; }
.l22 .l22-tr .tm { font-family: var(--mono); font-size: .72rem; }
.l22 .l22-ans { direction: ltr; text-align: left; background: var(--surface); border: 1px dashed var(--line); border-radius: 8px; padding: 6px 9px; font-size: .82rem; }
.l22 .l22-fb { font-size: .84rem; border-radius: 8px; padding: 6px 9px; }
.l22 .l22-fb.neg { background: var(--bad-soft); } .l22 .l22-fb.pos { background: var(--good-soft); }
.l22 .l22-causes { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 210px), 1fr)); gap: 5px; }
.l22 .l22-causes button { text-align: right; font-size: .8rem; }
.l22 .l22-verdict { border-radius: 10px; padding: 9px 12px; line-height: 1.7; font-size: .9rem; }
.l22 .l22-verdict.ok { background: var(--good-soft); border-inline-start: 3px solid var(--good); }
.l22 .l22-verdict.no { background: var(--bad-soft); border-inline-start: 3px solid var(--bad); }
.l22 .l22-score { font-size: .85rem; }
.l22 .l22-grid2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
@media (max-width: 640px) { .l22 .l22-grid2 { grid-template-columns: minmax(0, 1fr); } .l22 .l22-row { grid-template-columns: minmax(0, 46%) minmax(0, 1fr); } .l22 .l22-axis { padding-left: calc(46% + 10px); } }
.l22 .l22-svg { width: 100%; height: auto; display: block; direction: ltr; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.l22 .l22-svg text { fill: var(--muted); font-family: var(--mono); font-size: 10px; }
.l22 .l22-alerts { display: grid; gap: 4px; font-size: .84rem; }
.l22 .l22-alerts div { border-radius: 8px; padding: 5px 9px; }
.l22 .l22-alerts .page { background: var(--bad-soft); } .l22 .l22-alerts .ticket { background: var(--signal-soft); } .l22 .l22-alerts .none { background: var(--good-soft); }
.l22 .l22-ctl { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: 8px; }
.l22 .l22-ctl label { display: grid; gap: 3px; font-size: .84rem; }
.l22 .l22-ctl input[type=range] { width: 100%; }
.l22 .l22-ctl output { font-family: var(--mono); font-size: .8rem; color: var(--accent); }
.l22 .l22-cmp { display: grid; gap: 6px; direction: ltr; min-width: 0; }
.l22 .l22-tg { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; direction: ltr; }
.l22 .l22-cmp .brow { grid-template-columns: minmax(0, 9rem) minmax(0, 1fr) 6.5rem; }
.l22 .l22-cmp h4 { margin: 4px 0 0; font-size: .95rem; }
.l22 .l22-check { display: flex; gap: 8px; align-items: flex-start; font-size: .84rem; line-height: 1.5; }
`;
    document.head.appendChild(s);
  }

  const TYPES = ["agent", "cache", "retrieval", "llm", "tool", "other"];
  const legend = () => `<div class="l22-legend">${TYPES.map((t) => `<span><i class="t-${t}"></i>${t}</span>`).join("")}<span><i style="background:var(--bad)"></i>event (retry / error)</span></div>`;
  const fmtV = (v) => (typeof v === "string" ? v : JSON.stringify(v));

  /* =====================================================================
     Animation: a trace is built while one request flows through the system
     ===================================================================== */
  const TOTAL = 3400;
  const SPANS = [
    { id: "root", d: 0, name: "invoke_workflow acme_answer", t: "agent", s: 0, e: 3400 },
    { id: "cache", d: 1, name: "cache.lookup", t: "cache", s: 3, e: 6 },
    { id: "ret", d: 1, name: "retrieval acme-kb", t: "retrieval", s: 8, e: 62 },
    { id: "c1", d: 1, name: "chat claude-haiku-5-5", t: "llm", s: 65, e: 1480, ev: [[420, "retry"]] },
    { id: "tool", d: 1, name: "execute_tool lookup_employee", t: "tool", s: 1484, e: 1530 },
    { id: "c2", d: 1, name: "chat claude-haiku-5-5", t: "llm", s: 1534, e: 3390 },
  ];
  // Each step: which span is touched, how far it is drawn (end ms), attributes added, and why.
  const STEPS = [
    { span: "root", to: 60, attrs: { "gen_ai.operation.name": "invoke_workflow", "gen_ai.workflow.name": "acme_answer", "gen_ai.conversation.id": "conv_41b2", "obskit.user.id": "u-3f19", "gen_ai.prompt.version": "v3" },
      why: "הבקשה מגיעה: \"Who owns the sick leave policy, and what is their email?\". נפתח ה-<b>root span</b>, שמייצג את הבקשה כולה. ה-attributes שלו ידועים כבר עכשיו: איזה workflow, איזו שיחה, איזה משתמש (מזהה, לא מייל) ואיזו גרסת פרומפט. הפס שלו ימשיך לגדול עד שהבקשה תסתיים." },
    { span: "cache", to: 6, attrs: { "obskit.span.type": "cache", "obskit.cache.name": "response", "obskit.cache.hit": false },
      why: "השלב הראשון: מטמון התשובות. זה span ידני, כי אין לו פעולה בתקן של GenAI, ולכן ה-type שלו מגיע מ-obskit. הוא לקח 3 מילישניות, והתוצאה היא <b>miss</b>, אז ממשיכים. בשאלה שחוזרת, ה-trace היה נגמר כאן, בלי שום קריאה למודל." },
    { span: "ret", to: 62, attrs: { "gen_ai.operation.name": "retrieval", "gen_ai.data_source.id": "acme-kb", "gen_ai.retrieval.top_k": 3, "obskit.retrieval.index_version": "2026-10-30", "obskit.retrieval.replica": "kb-1", "gen_ai.retrieval.documents": "[{id: hr-sick-leave#0, score: 7.33}, {id: hr-sick-leave#3, score: 7.07}, ...]" },
      why: "השליפה: 54 מילישניות. ה-attributes החשובים הם <b>אילו מסמכים חזרו ובאיזה ציון</b>, ומאיזה אינדקס. כשתשובה שגויה, כאן בודקים קודם: האם המסמך הנכון בכלל הגיע למודל? גרסת האינדקס וה-replica לא בתקן, ו-obskit מוסיף אותם, כי בלעדיהם אי אפשר לזהות replica ישן." },
    { span: "c1", to: 420, attrs: { "gen_ai.operation.name": "chat", "gen_ai.provider.name": "anthropic", "gen_ai.request.model": "claude-haiku-5-5", "gen_ai.request.max_tokens": 300, "gen_ai.request.stream": true, "gen_ai.prompt.name": "rag-answer" },
      why: "הקריאה הראשונה למודל, span מסוג <b>CLIENT</b> בשם <code>chat claude-haiku-5-5</code>, כמו שהתקן מגדיר: הפעולה ואחריה המודל. ה-attributes שידועים <b>לפני</b> שליחת הבקשה נרשמים מיד: ספק, מודל, max_tokens, סטרימינג, שם הפרומפט." },
    { span: "c1", to: 760, ev: true, attrs: { "event: retry": "attempt=1, error.type=overloaded_error, http.status=529, wait_s=0.31" },
      why: "הספק החזיר <b>529</b>. llmkit ממתין 0.31 שניות ומנסה שוב. זה לא span חדש: זה <b>event</b> על אותו span, כי התקן מגדיר את ה-span כקריאה לוגית אחת. הקו האדום על הפס מסמן את הרגע. שלושה קווים כאלה על span אחד הם סימן ההיכר של סערת rate limit." },
    { span: "c1", to: 1480, attrs: { "gen_ai.response.model": "claude-haiku-5-5", "gen_ai.response.id": "msg_01H...", "gen_ai.response.finish_reasons": ["tool_call"], "gen_ai.usage.input_tokens": 1240, "gen_ai.usage.cache_read.input_tokens": 713, "gen_ai.usage.output_tokens": 38, "gen_ai.response.time_to_first_chunk": 0.62, "obskit.cost_usd": 0.000077, "obskit.attempts": 2 },
      why: "הקריאה הסתיימה, ורק עכשיו ידועים הטוקנים, העלות וסיבת העצירה. <b>finish_reasons = tool_call</b>: המודל לא ענה, הוא ביקש להפעיל כלי. 713 מתוך 1,240 טוקני הקלט הגיעו מה-prompt cache, ולכן הם זולים פי עשרה. attempts=2 מסכם את ה-retry." },
    { span: "tool", to: 1530, attrs: { "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "lookup_employee", "gen_ai.tool.call.id": "call_dir_1", "gen_ai.tool.type": "function", "gen_ai.tool.call.arguments": "{\"name\": \"Orly Peretz\"}", "gen_ai.tool.call.result": "{\"name\": \"Orly Peretz\", \"title\": \"VP People\", \"email\": \"[EMAIL]\"}" },
      why: "הכלי רץ: חיפוש בספריית העובדים. ה-<b>call id</b> מחבר את ההפעלה לבקשה של המודל. הארגומנטים והתוצאה הם תוכן (Opt-In), ושים לב שהמייל בתוצאה כבר הוחלף ב-[EMAIL]: ה-redaction processor ניקה אותו לפני שה-span יצא מהתהליך." },
    { span: "c2", to: 3390, attrs: { "gen_ai.operation.name": "chat", "gen_ai.request.model": "claude-haiku-5-5", "gen_ai.response.finish_reasons": ["stop"], "gen_ai.usage.input_tokens": 1302, "gen_ai.usage.cache_read.input_tokens": 1240, "gen_ai.usage.output_tokens": 41, "gen_ai.response.time_to_first_chunk": 0.55, "obskit.cost_usd": 0.000035, "obskit.attempts": 1 },
      why: "הקריאה השנייה למודל, עם תוצאת הכלי, כותבת את התשובה: <b>finish_reasons = stop</b>. כמעט כל הקלט הגיע מה-cache, כי הקידומת זהה לקריאה הראשונה, ולכן היא זולה ביותר. היא גם השלב הארוך ביותר ב-trace: 1.9 שניות, רובן כתיבת טוקנים." },
    { span: "root", to: 3400, attrs: { "obskit.answer.kind": "llm", "obskit.grounded": true, "duration": "3.40 s", "trace cost (sum of spans)": "$0.000112" },
      why: "הבקשה הסתיימה. על ה-root נרשמים סוג התשובה ותוצאת <b>בדיקת העיגון</b> (התשובה מצטטת מקור שנשלף). עכשיו אפשר לקרוא את ה-trace כולו: רוב הזמן הלך לשתי הקריאות למודל, השליפה והכלי זניחים, וה-retry הוסיף כ-0.3 שניות. לחץ על כל שורה כדי לראות את ה-attributes שלה." },
  ];

  window.AIDS["l22wf"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l22">
      <div class="guide"><p>כל שורה היא <strong>span</strong>, וההזחה מראה מי קרא למי. הציר האופקי הוא זמן מתחילת הבקשה (0 עד 3.4 שניות): הפס מתחיל כשהשלב התחיל ונגמר כשהוא נגמר. קו אדום על פס הוא <strong>event</strong>. בתחתית: ה-attributes של ה-span הנוכחי, והחדשים מודגשים. האנימציה מתחילה מבקשה ריקה, ואפשר לעצור ולעבור צעד צעד עם החצים.</p></div>
      ${legend()}
      <div class="l22-axis"><span>0</span><span>1.7 s</span><span>3.4 s</span></div>
      <div class="l22-wf" id="w-rows"></div>
      <div class="l22-why" id="w-why"></div>
      <div class="l22-attrs" id="w-attrs"></div>
      <div class="row"><button class="btn small primary" id="w-play">השהה</button><button class="btn small" id="w-prev" aria-label="צעד קודם">→</button><button class="btn small" id="w-next" aria-label="צעד הבא">←</button><button class="btn small" id="w-reset">מההתחלה</button><span class="spacer"></span><span class="counter" id="w-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = -1, timer = null, sel = null;
    let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    function state(n) { // attributes and drawn ends after steps 0..n
      const attrs = {}, ends = {}, evs = {};
      for (let k = 0; k <= n; k++) {
        const st = STEPS[k];
        attrs[st.span] = Object.assign(attrs[st.span] || {}, st.attrs);
        ends[st.span] = st.to;
        if (st.ev) evs[st.span] = true;
      }
      return { attrs, ends, evs };
    }
    function render() {
      const { attrs, ends, evs } = state(i);
      const cur = i >= 0 ? STEPS[i] : null;
      const shown = SPANS.filter((s) => ends[s.id] !== undefined);
      g("w-rows").innerHTML = shown.map((s) => {
        const L = (s.s / TOTAL) * 100, W = Math.max(0.5, ((ends[s.id] - s.s) / TOTAL) * 100);
        const ev = evs[s.id] ? (s.ev || []).map(([t]) => `<i class="l22-ev" style="left:${(t / TOTAL) * 100}%"></i>`).join("") : "";
        const done = ends[s.id] >= s.e;
        const lab = L + W > 75 ? `right:${100 - L + 1}%` : `left:${L + W + 1}%`;
        return `<div class="l22-row${cur && cur.span === s.id ? " sel new" : ""}${sel === s.id ? " sel" : ""}" data-id="${s.id}"><div class="l22-nm" style="padding-left:${s.d * 12}px">${esc(s.name)}</div>
          <div class="l22-lane"><i class="l22-bar t-${s.t}" style="left:${L}%;width:${W}%"></i>${ev}<span class="l22-dur" style="${lab}">${done ? Math.round(s.e - s.s) + " ms" : "..."}</span></div></div>`;
      }).join("") || `<div class="muted" style="direction:rtl;text-align:right">(עדיין אין spans: הבקשה לא הגיעה)</div>`;
      g("w-why").innerHTML = cur ? cur.why : "לחץ על החץ (או המתן) כדי לשלוח את הבקשה למערכת.";
      const show = sel || (cur && cur.span);
      if (show && attrs[show]) {
        const sp = SPANS.find((s) => s.id === show);
        const fresh = cur && cur.span === show && !sel ? Object.keys(cur.attrs) : [];
        g("w-attrs").innerHTML = `<div class="hd">${esc(sp.name)}</div>` + Object.entries(attrs[show]).map(([k, v]) =>
          `<div class="${fresh.includes(k) ? "fresh" : ""}${k.startsWith("event") ? " ev" : ""}"><span class="k">${esc(k)}</span> = ${esc(fmtV(v))}</div>`).join("");
      } else g("w-attrs").innerHTML = `<div class="hd" style="direction:rtl;text-align:right">attributes יופיעו כאן</div>`;
      g("w-c").textContent = `${i + 1} / ${STEPS.length}`;
      g("w-play").textContent = playing ? "השהה" : "נגן";
      host.querySelectorAll(".l22-row").forEach((r) => (r.onclick = () => { sel = r.dataset.id; playing = false; sched(); render(); }));
    }
    function sched() {
      clearTimeout(timer);
      if (playing) timer = setTimeout(() => { if (i < STEPS.length - 1) { i++; sel = null; render(); sched(); } else { playing = false; render(); } }, i < 0 ? 1200 : 4200);
    }
    g("w-play").onclick = () => { playing = !playing; if (playing && i >= STEPS.length - 1) i = -1; sel = null; render(); sched(); };
    g("w-next").onclick = () => { playing = false; sel = null; if (i < STEPS.length - 1) i++; render(); sched(); };
    g("w-prev").onclick = () => { playing = false; sel = null; if (i > -1) i--; render(); sched(); };
    g("w-reset").onclick = () => { i = -1; sel = null; playing = true; render(); sched(); };
    render(); sched();
    return () => clearTimeout(timer);
  };

  /* =====================================================================
     Sim: forensic trace explorer (the lab's 12 recorded traces)
     ===================================================================== */
  const FORENSIC = [{"id":"fe4548d0f99b8971c604b00be2fb3ad1","t":"09:02","q":"How many days a week can employees work remotely?","a":"Employees may work remotely up to 2 days per week. [1] Berlin employees follow the same rule of up to 2 remote days per week. [2]","fb":null,"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,2706.3,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-1a07","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.1,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.3,0.8,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"How many days a week can employees work remotely?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":9.2672,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"hr-remote-work-2026 (2026-03-01) score 9.2672; hr-remote-work-2026 (2026-03-01) score 7.2227; hr-vacation-2026 (2026-01-01) score 6.8101"},[]],[1,"chat mock-model","llm",1.4,2704.1,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_b62826cd5d3245b6","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1682,"gen_ai.usage.output_tokens":32,"gen_ai.usage.cache_write.input_tokens":1223,"gen_ai.response.time_to_first_chunk":2.2743,"obskit.cost_usd":0.00021478,"obskit.attempts":1},[]]]},{"id":"6d176edc621e2f9682723ee7d856646d","t":"09:08","q":"How many sick days do employees in Israel accrue per year?","a":"Employees in Israel accrue 1.5 sick days per month of employment, up to 18 days per year, as required by law. [1] Employees may use up to 8 of their sick days per year to care for a sick child under 16. [2]","fb":null,"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,1226.1,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-3f19","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.1,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.5,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"How many sick days do employees in Israel accrue per year?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":15.7687,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"hr-sick-leave (2025-07-01) score 15.7687; hr-sick-leave (2025-07-01) score 10.8988; hr-sick-leave (2025-07-01) score 9.0927"},[]],[1,"chat mock-model","llm",0.9,1225.1,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_361c5e083e3c4a10","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1628,"gen_ai.usage.output_tokens":52,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.8595,"obskit.cost_usd":7.873e-05,"obskit.attempts":1},[]]]},{"id":"63249c840ca5ea8bbfe5cde01a4c1676","t":"09:13","q":"How many unused vacation days can I carry over to next year, and when do they expire?","a":"Up to 3 unused days may be carried over to the next calendar year. [1] Carried-over days expire on February 28 of the following year. [1]","fb":[-1,"That's wrong. Since January it's 5 days, and they expire at the end of March."],"cause":"stale_index","spans":[[0,"invoke_workflow acme_answer","agent",0.0,1150.3,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-77d0","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.1,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.2,0.3,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"How many unused vacation days can I carry over to next year, and when do they expire?","obskit.retrieval.replica":"kb-2","obskit.retrieval.count":3,"obskit.retrieval.top_score":16.3283,"obskit.retrieval.index_version":"2025-05-30","retrieval results":"hr-vacation-2024 (2024-01-01) score 16.3283; hr-vacation-2024 (2024-01-01) score 4.8916; hr-vacation-2024 (2024-01-01) score 3.9565"},[]],[1,"chat mock-model","llm",0.7,1149.4,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_fab557b9d6fa4d97","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1700,"gen_ai.usage.output_tokens":34,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.9335,"obskit.cost_usd":7.693e-05,"obskit.attempts":1},[]]]},{"id":"ba51a2d978e8757bbebadfd65fadda8d","t":"09:19","q":"Can I use SMS codes as my second factor?","a":"SMS codes and phone calls are no longer accepted as a second factor. [1] SMS as a second factor: no longer allowed. [3]","fb":[1,""],"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,1175.3,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-9b42","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.2,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"Can I use SMS codes as my second factor?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":12.3241,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"it-password-mfa-2026 (2026-01-15) score 12.3241; it-password-policy-2024 (2024-06-01) score 10.2184; it-password-mfa-2026 (2026-01-15) score 8.2989"},[]],[1,"chat mock-model","llm",0.6,1174.5,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_a6ff4038fcb84d41","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1741,"gen_ai.usage.output_tokens":30,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.9814,"obskit.cost_usd":7.903e-05,"obskit.attempts":1},[]]]},{"id":"b52af5a1c107c0d3a5eec558967dce77","t":"09:40","q":"How much is the home office allowance and how do I claim it?","a":"The one-time home office allowance of 1,500 NIS (see the Remote Work Policy) is claimed in Spendwise under the category \"Home office\", within 60 days of the purchase. [1] Acme provides a one-time home office allowance of 1,500 NIS, claimed through the expense system within 60 days of the purchase. [2]","fb":null,"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,2676.1,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-0c55","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.1,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.2,0.3,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"How much is the home office allowance and how do I claim it?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":9.1774,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"hr-expenses (2026-01-01) score 9.1774; hr-remote-work-2026 (2026-03-01) score 6.0578; hr-expenses (2026-01-01) score 5.3347"},[]],[1,"chat mock-model","llm",0.9,2675.1,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_6b7bf094f08749fe","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1751,"gen_ai.usage.output_tokens":76,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.9942,"obskit.cost_usd":0.00010303,"obskit.attempts":2},[["retry",255,"rate_limit_error"]]]]},{"id":"f86dcd999b2207982c84a917bbed2cbd","t":"09:41","q":"How many sick days can I use to care for a sick child?","a":"Single parents may use up to 16 days per year to care for a sick child. [1] Employees may use up to 8 of their sick days per year to care for a sick child under 16. [1]","fb":null,"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,3719.1,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-6e81","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.2,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"How many sick days can I use to care for a sick child?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":18.3524,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"hr-sick-leave (2025-07-01) score 18.3524; hr-sick-leave (2025-07-01) score 6.4867; hr-sick-leave (2025-07-01) score 5.6939"},[]],[1,"chat mock-model","llm",0.5,3718.4,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_7b5e711c007a41bc","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1663,"gen_ai.usage.output_tokens":42,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.8962,"obskit.cost_usd":7.723e-05,"obskit.attempts":3},[["retry",254,"rate_limit_error"],["retry",1507,"rate_limit_error"]]]]},{"id":"e54f6e4c98aa7a597456a0d9416b701b","t":"09:43","q":"Do I need a medical certificate if I am sick for two days?","a":"Yes. Acme requires a medical certificate for every sick day, starting from the first day.","fb":[-1,"Not true, the policy says 3 or more consecutive days. Where did this come from?"],"cause":"rate_limit_fallback","spans":[[0,"invoke_workflow acme_answer","agent",0.0,3086.7,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-1a07","gen_ai.prompt.version":"v3","obskit.fallback":"model","obskit.answer.kind":"fallback_model","obskit.grounded":false},[["fallback",2768,"rate_limit_error"]]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.3,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"Do I need a medical certificate if I am sick for two days?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":12.7608,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"hr-sick-leave (2025-07-01) score 12.7608; hr-sick-leave (2025-07-01) score 6.6698; hr-sick-leave (2025-07-01) score 5.1863"},[]],[1,"chat mock-model","llm",0.6,2767.3,"ERROR",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","obskit.attempts":3,"error.type":"rate_limit_error"},[["retry",258,"rate_limit_error"],["retry",1513,"rate_limit_error"],["exception",2768,""]]],[1,"chat mock-small","llm",2768.2,318.3,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-small","gen_ai.request.max_tokens":200,"gen_ai.prompt.name":"fallback","gen_ai.prompt.version":"v1","gen_ai.response.model":"mock-small","gen_ai.response.id":"req_mock_4924a5b3e18f4d62","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":56,"gen_ai.usage.output_tokens":22,"obskit.cost_usd":3.32e-06,"obskit.attempts":1},[]]]},{"id":"2ef682148e9357a6b1e813cdc84af384","t":"09:54","q":"Who owns the sick leave policy, and what is their email?","a":"The Sick Leave Policy is owned by Orly Peretz [1], VP People (orly.peretz@acme.example) [4].","fb":[1,""],"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,971.9,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-3f19","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.4,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"Who owns the sick leave policy, and what is their email?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":7.3256,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"hr-sick-leave (2025-07-01) score 7.3256; hr-sick-leave (2025-07-01) score 7.0732; hr-sick-leave (2025-07-01) score 6.5339"},[]],[1,"execute_tool lookup_employee","tool",0.5,0.1,"UNSET",{"gen_ai.operation.name":"execute_tool","gen_ai.tool.name":"lookup_employee","gen_ai.tool.type":"function","gen_ai.tool.call.id":"call_dir_1","obskit.tool.found":true,"gen_ai.tool.call.arguments":"{\"name\": \"Orly Peretz\"}","gen_ai.tool.call.result":"{\"id\": \"E007\", \"name\": \"Orly Peretz\", \"title\": \"VP People\", \"team\": \"exec\", \"email\": \"orly.peretz@acme.example\"}"},[]],[1,"chat mock-model","llm",0.9,970.8,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_2b5e5f3c96334183","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1632,"gen_ai.usage.output_tokens":23,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.8588,"obskit.cost_usd":6.463e-05,"obskit.attempts":1},[]]]},{"id":"7a914e3bbb3a761eb864f2cc58832de0","t":"10:05","q":"A customer bought an annual plan three months ago and wants a refund. Are they entitled to one?","a":"A customer may cancel an annual plan and receive a full refund within 14 days of the initial purchase. [1]","fb":[-1,"Right answer, but much slower than usual."],"cause":"prompt_cache_miss","spans":[[0,"invoke_workflow acme_answer","agent",0.0,2384.0,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-77d0","gen_ai.prompt.version":"v3.1","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.3,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"A customer bought an annual plan three months ago and wants a refund. Are they entitled to one?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":13.7941,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"sup-refund-policy (2026-01-01) score 13.7941; sup-refund-policy (2026-01-01) score 7.9236; sup-refund-policy (2026-01-01) score 7.7834"},[]],[1,"chat mock-model","llm",0.7,2383.2,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3.1","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_46c0ccdbcf864e4e","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1635,"gen_ai.usage.output_tokens":26,"gen_ai.usage.cache_write.input_tokens":1222,"gen_ai.response.time_to_first_chunk":2.2194,"obskit.cost_usd":0.00020705,"obskit.attempts":1},[]]]},{"id":"24cd8294195701007406f0b261efe9ef","t":"10:13","q":"What is the minimum password length, and do I have to change my password every 90 days?","a":"I could not find this in the Acme documents.","fb":[-1,"It's in the password policy! Why can't it find it?"],"cause":"llm_timeout","spans":[[0,"invoke_workflow acme_answer","agent",0.0,7528.1,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-9b42","gen_ai.prompt.version":"v3","obskit.fallback":"canned","obskit.answer.kind":"canned"},[["fallback",7528,"timeout"]]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.3,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"What is the minimum password length, and do I have to change my password every 90 days?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":13.9336,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"it-password-mfa-2026 (2026-01-15) score 13.9336; it-password-policy-2024 (2024-06-01) score 7.4091; it-password-mfa-2026 (2026-01-15) score 7.0936"},[]],[1,"chat mock-model","llm",0.7,7527.2,"ERROR",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","obskit.attempts":3,"error.type":"timeout"},[["retry",2503,"timeout"],["retry",5019,"timeout"],["exception",7528,""]]]]},{"id":"b65ea5e719186255db7bc1899a498195","t":"10:20","q":"How many days a week can employees work remotely?","a":"Employees may work remotely up to 2 days per week. [1] Berlin employees follow the same rule of up to 2 remote days per week. [2]","fb":[1,""],"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,0.1,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-0c55","gen_ai.prompt.version":"v3","obskit.answer.kind":"cache"},[]],[1,"cache.lookup","cache",0.1,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":true},[]]]},{"id":"27d6199466326586f0987a61646da617","t":"10:27","q":"How often are laptops replaced?","a":"Laptops are replaced every 3 years. [1]","fb":null,"cause":null,"spans":[[0,"invoke_workflow acme_answer","agent",0.0,935.4,"UNSET",{"gen_ai.operation.name":"invoke_workflow","gen_ai.workflow.name":"acme_answer","obskit.user.id":"u-51c2","gen_ai.prompt.version":"v3","obskit.answer.kind":"llm","obskit.grounded":true},[]],[1,"cache.lookup","cache",0.0,0.0,"UNSET",{"obskit.cache.name":"response","obskit.cache.hit":false},[]],[1,"retrieval acme-kb","retrieval",0.1,0.2,"UNSET",{"gen_ai.operation.name":"retrieval","gen_ai.data_source.id":"acme-kb","gen_ai.retrieval.top_k":3,"gen_ai.retrieval.query.text":"How often are laptops replaced?","obskit.retrieval.replica":"kb-1","obskit.retrieval.count":3,"obskit.retrieval.top_score":7.0639,"obskit.retrieval.index_version":"2026-10-30","retrieval results":"it-laptop-policy (2025-08-01) score 7.0639; it-laptop-policy (2025-08-01) score 2.8812; hr-expenses (2026-01-01) score 2.2073"},[]],[1,"chat mock-model","llm",0.6,934.6,"OK",{"gen_ai.operation.name":"chat","gen_ai.provider.name":"anthropic","gen_ai.request.model":"mock-model","gen_ai.request.max_tokens":300,"gen_ai.prompt.name":"rag-answer","gen_ai.prompt.version":"v3","gen_ai.response.model":"mock-model","gen_ai.response.id":"req_mock_ac27b2edf0eb427b","gen_ai.response.finish_reasons":["stop"],"gen_ai.usage.input_tokens":1655,"gen_ai.usage.output_tokens":10,"gen_ai.usage.cache_read.input_tokens":1223,"gen_ai.response.time_to_first_chunk":0.8826,"obskit.cost_usd":6.043e-05,"obskit.attempts":1},[]]]}];
  const CAUSES = [
    ["stale_index", "אינדקס ישן: חסרים בו מסמכים חדשים"],
    ["retrieval_miss", "השליפה לא דירגה את המסמך הנכון ב-top k"],
    ["llm_timeout", "timeout בקריאה למודל, ותשובה בלעדיו"],
    ["rate_limit_fallback", "rate limit, ה-retries נגמרו, ונתיב גיבוי ענה"],
    ["prompt_cache_miss", "החטאה של ה-prompt cache: איטי ויקר יותר"],
    ["model_hallucination", "המודל קיבל מקורות נכונים והמציא בכל זאת"],
    ["tool_error", "הכלי נכשל או החזיר מידע שגוי"],
    ["max_tokens", "התשובה נקטעה בתקרת הטוקנים"],
  ];
  const EXPLAIN = {
    stale_index: "ה-span <code>retrieval acme-kb</code> נענה מ-replica <b>kb-2</b>, עם <code>obskit.retrieval.index_version = 2025-05-30</code>, בזמן שכל שאר ה-traces רצו על kb-1 מ-2026-10-30. שלושת המסמכים שחזרו הם <code>hr-vacation-2024</code>, ומסמך 2026 פשוט לא קיים באינדקס הזה. המודל עשה בדיוק מה שביקשו: ענה מהמקורות וציטט אותם, ולכן גם בדיקת העיגון עברה. זו הסיבה שעיגון הוא לא נכונות. התיקון: לבנות מחדש את kb-2, ולהתריע כשגרסת אינדקס של replica מפגרת.",
    rate_limit_fallback: "ה-span <code>chat mock-model</code> הסתיים ב-ERROR עם <code>error.type = rate_limit_error</code>, עם שני events של retry ו-<code>obskit.attempts = 3</code>. על ה-root יש event בשם <code>fallback</code> אל <code>mock-small</code>, וה-span של מודל הגיבוי קיבל רק <b>56 טוקני קלט</b>, לעומת כ-1,150 בבקשה רגילה: המקורות לא היו בפרומפט (<code>fallback@v1</code>). מודל בלי מקורות ענה מהזיכרון, ו-<code>obskit.grounded = false</code>. ושים לב לשני ה-traces שלפניו (09:40, 09:41): גם בהם יש retries של 429. זו הייתה סערה, לא תקלה בודדת. התיקון: נתיב גיבוי שמעביר את המקורות, או תשובה כנה ש\"השירות עמוס\".",
    prompt_cache_miss: "התשובה <b>נכונה</b>, והמשוב הוא על מהירות. ההבדל מה-traces הרגילים: <code>gen_ai.prompt.version = v3.1</code> (כולם v3), <code>gen_ai.usage.cache_write.input_tokens = 1,222</code> ואין <code>cache_read</code>, ו-TTFT של 2.2 שניות במקום כ-0.9. שינוי של מילה אחת ב-system prompt שינה את הקידומת, וה-prompt cache התחיל מאפס, כמו ב-trace הראשון של הבוקר (cold start). זו לא בעיית איכות, ולכן לא היה נכון לחקור את השליפה או את המודל. מה לעשות: לצפות את זה בכל deploy של פרומפט, או לחמם את ה-cache מראש.",
    llm_timeout: "השליפה הייתה תקינה: <code>it-password-mfa-2026</code> חזר ראשון עם ציון 13.9. הבעיה בקריאה למודל: ERROR עם <code>error.type = timeout</code>, שלושה ניסיונות, כ-7.5 שניות. על ה-root יש event <code>fallback</code> אל <code>canned_answer</code>, והמשתמש קיבל \"I could not find this in the Acme documents\". זה החלק המסוכן: הודעת כשל של תשתית שנראית כמו תשובה עניינית ש\"אין מידע\". ה-replay בתרגיל 7 מראה שעם שרת תקין אותה בקשה כן עונה. התיקון: הודעת שגיאה כנה, ו-timeout שמתאים ל-latency הרגיל של הספק.",
  };
  const CAUSE_LABEL = Object.fromEntries(CAUSES);

  window.AIDS["l22forensic"] = function (host) {
    ensureStyle();
    const verdicts = {};
    let cur = FORENSIC.findIndex((t) => !t.fb) , sortBy = "time", selSpan = 0;
    host.innerHTML = `<div class="l22">
      <div class="guide"><p>ברשימה: 12 בקשות מבוקר 2026-10-29, לפי שעה (או לפי משך). 👎 מסמן משוב שלילי. לחיצה על בקשה מציגה את השאלה, התשובה שהמשתמש קיבל, וה-waterfall שלה. לחיצה על שורה ב-waterfall מציגה את ה-attributes וה-events של ה-span. בבקשות עם 👎 מופיעה רשימת סיבות: בחר אחת, וקבל הסבר עם הראיות. כדאי להתחיל מבקשה תקינה, כדי לדעת איך "נורמלי" נראה.</p></div>
      <div class="row"><span class="muted">מיון:</span><div class="seg" id="f-sort"><button aria-pressed="true" data-v="time">שעה</button><button aria-pressed="false" data-v="dur">משך</button></div><span class="spacer"></span><span class="l22-score" id="f-score"></span></div>
      <div class="l22-list" id="f-list"></div>
      <div id="f-detail" style="display:grid;gap:8px"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const dur = (t) => t.spans[0][4];
    const cost = (t) => t.spans.reduce((a, s) => a + (+(s[6]["obskit.cost_usd"] || 0)), 0);
    function list() {
      const order = FORENSIC.map((t, k) => k).sort((a, b) => sortBy === "dur" ? dur(FORENSIC[b]) - dur(FORENSIC[a]) : 0);
      g("f-list").innerHTML = order.map((k) => {
        const t = FORENSIC[k], err = t.spans.some((s) => s[5] === "ERROR");
        const mark = t.fb ? (t.fb[0] < 0 ? "👎" : "👍") : "·";
        const v = verdicts[k];
        return `<button class="l22-tr${k === cur ? " sel" : ""}" data-k="${k}"><span class="tm">${t.t}</span><span class="q">${esc(t.q)}</span><span class="m">${(dur(t) / 1000).toFixed(2)}s${err ? " ⚠" : ""} ${mark}${v ? (v === t.cause ? " ✓" : " ✗") : ""}</span></button>`;
      }).join("");
      host.querySelectorAll(".l22-tr").forEach((b) => (b.onclick = () => { cur = +b.dataset.k; selSpan = 0; draw(); }));
      const flagged = FORENSIC.filter((t) => t.cause).length;
      const right = Object.entries(verdicts).filter(([k, v]) => FORENSIC[k].cause === v).length;
      g("f-score").textContent = `סיבות נכונות: ${right} / ${flagged}`;
    }
    function draw() {
      list();
      const t = FORENSIC[cur], T = Math.max(1, ...t.spans.map((s) => s[3] + s[4]));
      const rows = t.spans.map((s, j) => {
        const [d, name, ty, off, du, st, , evs] = s;
        const L = (off / T) * 100, W = Math.max(0.5, (du / T) * 100);
        const lab = L + W > 75 ? `right:${100 - L + 1}%` : `left:${L + W + 1}%`;
        const ev = evs.map((e) => `<i class="l22-ev" style="left:${Math.min(99.4, (e[1] / T) * 100)}%"></i>`).join("");
        return `<div class="l22-row${j === selSpan ? " sel" : ""}" data-j="${j}"><div class="l22-nm" style="padding-left:${d * 12}px">${esc(name)}</div><div class="l22-lane"><i class="l22-bar t-${TYPES.includes(ty) ? ty : "other"}${st === "ERROR" ? " err" : ""}" style="left:${L}%;width:${W}%"></i>${ev}<span class="l22-dur" style="${lab}">${du < 1 ? du.toFixed(1) : Math.round(du)} ms</span></div></div>`;
      }).join("");
      const s = t.spans[selSpan];
      const attrs = Object.entries(s[6]).map(([k, v]) => `<div><span class="k">${esc(k)}</span> = ${esc(fmtV(v))}</div>`).join("");
      const evs = s[7].map((e) => `<div class="ev">+${e[1]} ms event: ${esc(e[0])}${e[2] ? " (" + esc(e[2]) + ")" : ""}</div>`).join("");
      let fbHtml = "";
      if (t.fb) fbHtml = `<div class="l22-fb ${t.fb[0] < 0 ? "neg" : "pos"}">משוב משתמש: ${t.fb[0] < 0 ? "👎" : "👍"} <span dir="ltr">${esc(t.fb[1] || "(no comment)")}</span></div>`;
      let causeHtml = "";
      if (t.cause) {
        const v = verdicts[cur];
        causeHtml = `<div><b>מה סיבת השורש?</b></div><div class="l22-causes">${CAUSES.map(([c, label]) => `<button class="btn small${v === c ? " primary" : ""}" data-c="${c}">${label}</button>`).join("")}</div>` +
          (v ? (v === t.cause ? `<div class="l22-verdict ok"><b>נכון: ${CAUSE_LABEL[v]}.</b> ${EXPLAIN[t.cause]}</div>`
            : `<div class="l22-verdict no"><b>לא זו.</b> השווה את ה-trace הזה ל-trace תקין: איזה span הסתיים אחרת, ואיזה attribute שונה? (בדוק status, error.type, events, גרסת אינדקס, גרסת פרומפט, טוקני קלט ו-cache.)</div>`) : "");
      }
      g("f-detail").innerHTML = `<div class="l22-ans"><b>Q</b> ${esc(t.q)}<br><b>A</b> ${esc(t.a || "")}</div>${fbHtml}
        <div class="muted" style="font-size:.8rem">${t.t} · trace ${t.id.slice(0, 8)} · ${(T / 1000).toFixed(2)} s · $${cost(t).toFixed(6)}</div>
        ${legend()}<div class="l22-wf">${rows}</div>
        <div class="l22-attrs"><div class="hd">${esc(s[1])} · status ${s[5]}</div>${attrs}${evs}</div>${causeHtml}`;
      host.querySelectorAll("#f-detail .l22-row").forEach((r) => (r.onclick = () => { selSpan = +r.dataset.j; draw(); }));
      host.querySelectorAll("#f-detail [data-c]").forEach((b) => (b.onclick = () => { verdicts[cur] = b.dataset.c; draw(); }));
    }
    host.querySelectorAll("#f-sort button").forEach((b) => (b.onclick = () => {
      sortBy = b.dataset.v; host.querySelectorAll("#f-sort button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); list();
    }));
    draw();
  };

  /* =====================================================================
     Sim: SLO and burn-rate simulator
     ===================================================================== */
  const RULES = [
    { sev: "page", L: 60, S: 5, burn: 14.4, color: "var(--bad)" },
    { sev: "page", L: 360, S: 30, burn: 6, color: "var(--signal)" },
    { sev: "ticket", L: 1440, S: 120, burn: 3, color: "var(--accent)" },
  ];
  const rate = (m) => { const h = m / 60; return h >= 6 && h < 16 ? 4.2 + 0.8 * Math.sin(((h - 6) / 10) * Math.PI) : (h >= 4 && h < 6) || (h >= 16 && h < 19) ? 1.6 : 0.35; };
  const hhmm = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(Math.round(m % 60)).padStart(2, "0")}`;

  window.AIDS["l22slo"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l22">
      <div class="guide"><p>יום אחד של תעבורה (כ-3,500 בקשות, עמוס בשעות העבודה ושקט בלילה), עם תקלה אחת שאתה מגדיר. בגרף: ה-<strong>burn rate</strong> בחלון הארוך של כל אחד משלושת כללי ההתראה (שעה, 6 שעות, 24 שעות), בסקאלה לוגריתמית, והקו המקווקו באותו צבע הוא הסף של הכלל. התראה נורית רק כשגם החלון הארוך וגם הקצר שלו מעל הסף. ברשימה שמתחת: מתי כל התראה נורתה ונכבתה, וכמה תקציב נשרף. החישוב דטרמיניסטי: בדיוק השיעורים שבחרת, בלי רעש.</p></div>
      <div class="l22-ctl">
        <label>יעד הזמינות<div class="seg" id="s-t"><button aria-pressed="false" data-v="0.99">99%</button><button aria-pressed="true" data-v="0.995">99.5%</button><button aria-pressed="false" data-v="0.999">99.9%</button></div></label>
        <label>תחילת התקלה <output id="o-start"></output><input type="range" id="s-start" min="0" max="1410" step="10" value="680"></label>
        <label>משך התקלה <output id="o-dur"></output><input type="range" id="s-dur" min="10" max="600" step="10" value="30"></label>
        <label>שגיאות בזמן התקלה <output id="o-err"></output><input type="range" id="s-err" min="1" max="60" step="1" value="25"></label>
        <label>שגיאות ברקע <output id="o-base"></output><input type="range" id="s-base" min="0" max="10" step="1" value="2"></label>
      </div>
      <svg class="l22-svg" id="s-svg" viewBox="0 0 640 230" role="img" aria-label="burn rate over the day"></svg>
      <div class="l22-legend" id="s-leg"></div>
      <div class="l22-alerts" id="s-al"></div>
      <div class="stats" id="s-st"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let target = 0.995;
    function compute() {
      const start = +g("s-start").value, len = +g("s-dur").value, err = +g("s-err").value / 100, base = +g("s-base").value / 1000;
      g("o-start").textContent = hhmm(start) + " UTC"; g("o-dur").textContent = len + " min"; g("o-err").textContent = (err * 100).toFixed(0) + "%"; g("o-base").textContent = (base * 100).toFixed(1) + "%";
      const N = 1440, req = new Float64Array(N + 1), bad = new Float64Array(N + 1);
      for (let m = 0; m < N; m++) { const r = rate(m); req[m + 1] = req[m] + r; bad[m + 1] = bad[m] + r * (m >= start && m < start + len ? err : base); }
      const budget = 1 - target;
      const burn = (m, w) => { const a = Math.max(0, m - w), r = req[m] - req[a]; return r > 0 ? (bad[m] - bad[a]) / r / budget : 0; };
      // chart
      const X = (m) => 40 + (m / N) * 590, ymin = 0.1, ymax = 200, Y = (v) => 15 + (1 - (Math.log10(Math.max(ymin, Math.min(ymax, v))) - Math.log10(ymin)) / (Math.log10(ymax) - Math.log10(ymin))) * 190;
      let svg = `<rect x="${X(start)}" y="15" width="${Math.max(1, X(Math.min(N, start + len)) - X(start))}" height="190" fill="var(--bad-soft)"/>`;
      [0.1, 1, 10, 100].forEach((v) => { svg += `<line x1="40" x2="630" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="4" y="${Y(v) + 3}">${v}x</text>`; });
      for (let hh = 0; hh <= 24; hh += 4) svg += `<text x="${X(hh * 60) - 12}" y="222">${String(hh).padStart(2, "0")}:00</text>`;
      RULES.forEach((r) => {
        let d = "";
        for (let m = 5; m <= N; m += 5) d += `${m === 5 ? "M" : "L"}${X(m).toFixed(1)},${Y(burn(m, r.L)).toFixed(1)}`;
        svg += `<path d="${d}" fill="none" stroke="${r.color}" stroke-width="2"/><line x1="40" x2="630" y1="${Y(r.burn)}" y2="${Y(r.burn)}" stroke="${r.color}" stroke-dasharray="5 4" stroke-width="1.2"/>`;
      });
      g("s-svg").innerHTML = svg;
      g("s-leg").innerHTML = RULES.map((r) => `<span><i style="background:${r.color}"></i>${r.sev} · ${r.L / 60}h window · threshold ${r.burn}x</span>`).join("");
      // alerts: evaluate every 5 minutes
      const lines = [];
      RULES.forEach((r) => {
        let on = null;
        for (let m = 5; m <= N; m += 5) {
          const f = burn(m, r.L) >= r.burn && burn(m, r.S) >= r.burn;
          if (f && on === null) on = m;
          if (!f && on !== null) { lines.push([r, on, m]); on = null; }
        }
        if (on !== null) lines.push([r, on, null]);
      });
      g("s-al").innerHTML = lines.length ? lines.map(([r, a, b]) => `<div class="${r.sev}"><b>${r.sev}</b> (${r.L / 60}h/${r.S}m ≥ ${r.burn}x): נורתה ב-${hhmm(a)}${a >= start ? `, ${a - start} דקות אחרי תחילת התקלה` : ""}; ${b ? `נכבתה ב-${hhmm(b)}${b >= start + len ? `, ${b - start - len} דקות אחרי סופה` : ""}` : "עדיין פעילה בסוף היום"}.</div>`).join("")
        : `<div class="none">אף התראה לא נורתה. התקלה שרפה תקציב, אבל לא מספיק מהר בשום חלון.</div>`;
      const totalReq = req[N], totalBad = bad[N], incBad = bad[Math.min(N, start + len)] - bad[start];
      const month = totalReq * 30 * budget;
      g("s-st").innerHTML = `<span>בקשות ביום: <b>${Math.round(totalReq).toLocaleString("en-US")}</b></span><span>נכשלו בתקלה: <b>${Math.round(incBad)}</b></span><span>מתקציב היום: <b>${((totalBad / (totalReq * budget)) * 100).toFixed(0)}%</b></span><span>מתקציב 30 יום: <b>${((incBad / month) * 100).toFixed(1)}%</b></span>`;
    }
    host.querySelectorAll("#s-t button").forEach((b) => (b.onclick = () => { target = +b.dataset.v; host.querySelectorAll("#s-t button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); compute(); }));
    ["s-start", "s-dur", "s-err", "s-base"].forEach((id) => (g(id).oninput = compute));
    compute();
  };

  /* =====================================================================
     Sim: head vs tail sampling
     ===================================================================== */
  window.AIDS["l22sampling"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l22">
      <div class="guide"><p>10,000 בקשות ביום, ו-trace ממוצע של כ-12KB (עם content capture). <strong>Head sampling</strong> מחליט כשהבקשה מתחילה, לפי trace id, ולכן שומר את אותו אחוז מכל סוג. <strong>Tail sampling</strong> מחליט אחרי שה-trace הסתיים, ב-Collector, לפי ה-policies שתסמן. הפסים מראים כמה מכל סוג נשאר לחקירה. "תשובות שגויות" הן בקשות שהצליחו טכנית ומהירות, אבל נכשלו בבדיקת העיגון.</p></div>
      <div class="l22-ctl">
        <label>שגיאות (status ERROR) <output id="p-eo"></output><input type="range" id="p-e" min="0" max="5" step="0.1" value="0.5"></label>
        <label>בקשות איטיות (מעל 5 שניות) <output id="p-so"></output><input type="range" id="p-s" min="0" max="20" step="0.5" value="4"></label>
        <label>תשובות שגויות (לא מעוגנות) <output id="p-wo"></output><input type="range" id="p-w" min="0" max="10" step="0.5" value="2"></label>
        <label>Head sampling <output id="p-ho"></output><input type="range" id="p-h" min="1" max="100" step="1" value="10"></label>
        <label>Tail: מהשאר, שמור <output id="p-ro"></output><input type="range" id="p-r" min="0" max="100" step="1" value="10"></label>
      </div>
      <div class="l22-tg" style="display:grid;gap:4px">
        <label class="l22-check"><input type="checkbox" id="p-ke" checked> tail policy: keep every trace with status ERROR</label>
        <label class="l22-check"><input type="checkbox" id="p-ks" checked> tail policy: keep every trace longer than 5 s</label>
        <label class="l22-check"><input type="checkbox" id="p-kw"> tail policy: keep every trace with obskit.grounded = false</label>
      </div>
      <div class="l22-grid2"><div class="l22-cmp" id="p-head"></div><div class="l22-cmp" id="p-tail"></div></div>
      <div class="cap muted" id="p-note" style="line-height:1.7"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const N = 10000, KB = 12;
    function bar(label, kept, total) {
      const pct = total ? (kept / total) * 100 : 0;
      return `<div class="brow"><span class="t">${label}</span><span class="tr"><i class="f" style="width:${pct}%"></i></span><span class="v">${Math.round(kept).toLocaleString("en-US")} / ${Math.round(total).toLocaleString("en-US")}</span></div>`;
    }
    function compute() {
      const e = +g("p-e").value / 100, s = +g("p-s").value / 100, w = +g("p-w").value / 100, hr = +g("p-h").value / 100, rr = +g("p-r").value / 100;
      g("p-eo").textContent = (e * 100).toFixed(1) + "%"; g("p-so").textContent = (s * 100).toFixed(1) + "%"; g("p-wo").textContent = (w * 100).toFixed(1) + "%";
      g("p-ho").textContent = (hr * 100).toFixed(0) + "%"; g("p-ro").textContent = (rr * 100).toFixed(0) + "%";
      const E = N * e, S = N * s, W = N * w, R = Math.max(0, N - E - S - W);
      const ke = g("p-ke").checked, ks = g("p-ks").checked, kw = g("p-kw").checked;
      const head = { E: E * hr, S: S * hr, W: W * hr, R: R * hr };
      const tail = { E: ke ? E : E * rr, S: ks ? S : S * rr, W: kw ? W : W * rr, R: R * rr };
      const tot = (o) => o.E + o.S + o.W + o.R;
      const card = (title, o) => `<h4>${title}</h4>${bar("errors", o.E, E)}${bar("slow (> 5 s)", o.S, S)}${bar("wrong answers", o.W, W)}${bar("everything else", o.R, R)}
        <div class="stats"><span>traces kept: <b>${Math.round(tot(o)).toLocaleString("en-US")}</b></span><span>storage/day: <b>${((tot(o) * KB) / 1024).toFixed(0)} MB</b></span></div>`;
      g("p-head").innerHTML = card(`Head sampling (${(hr * 100).toFixed(0)}%)`, head);
      g("p-tail").innerHTML = card("Tail sampling (Collector)", tail);
      const lostErr = Math.round(E - head.E);
      g("p-note").innerHTML = `עם head sampling, <b>${lostErr}</b> מתוך ${Math.round(E)} השגיאות של היום לא נשמרו, כי ההחלטה התקבלה לפני שהן קרו. ` +
        (kw ? "עם ה-policy של obskit.grounded, גם התשובות השגויות נשמרות: tail sampling יכול להחליט לפי כל attribute שה-root נושא, אז את בדיקת העיגון צריך לרשום על ה-root לפני שה-span נסגר." :
          "התשובות השגויות לא ERROR ולא איטיות, ולכן tail sampling לפי status ו-latency שומר מהן רק את האחוז של \"השאר\". סמן את ה-policy השלישית וראה מה משתנה.") +
        " המחיר של tail sampling: ה-Collector מחזיק כל trace בזיכרון עד ההחלטה, וכל ה-spans של trace חייבים להגיע לאותו Collector.";
    }
    ["p-e", "p-s", "p-w", "p-h", "p-r"].forEach((id) => (g(id).oninput = compute));
    ["p-ke", "p-ks", "p-kw"].forEach((id) => (g(id).onchange = compute));
    compute();
  };
})();
