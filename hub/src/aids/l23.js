// Lesson 23 aids: eval pipeline animation (v1 baseline, v2 regression caught), "is this difference real?"
// simulator, and a judge-calibration explorer with the confusion matrix as a 2x2 grid of cards.
// Registered on window.AIDS; uses the hub helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l23-style";
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l23 { display: grid; gap: 12px; direction: rtl; min-width: 0; }
.l23 [hidden] { display: none !important; }
.l23 .l23-pipe { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 5px; direction: ltr; }
.l23 .l23-st { border: 1px solid var(--line); border-radius: 9px; padding: 6px 3px; text-align: center; background: var(--surface); font-size: .7rem; color: var(--muted); line-height: 1.3; min-width: 0; transition: background .3s, border-color .3s; }
.l23 .l23-st b { display: block; color: var(--ink); font-size: .78rem; font-family: var(--mono); font-weight: 600; }
.l23 .l23-st.on { border-color: var(--accent); background: var(--accent-soft); color: var(--ink); }
.l23 .l23-st.done { border-color: color-mix(in srgb, var(--accent) 40%, var(--line)); }
.l23 .l23-st.fail { border-color: var(--bad); background: var(--bad-soft); color: var(--ink); }
.l23 .l23-st.pass { border-color: var(--good); background: var(--good-soft); color: var(--ink); }
@media (max-width: 560px) { .l23 .l23-pipe { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.l23 .l23-round { display: flex; gap: 6px; flex-wrap: wrap; }
.l23 .l23-round span { border: 1px solid var(--line); border-radius: 999px; padding: 3px 11px; font-size: .82rem; color: var(--muted); }
.l23 .l23-round span.on { border-color: var(--accent); background: var(--accent-soft); color: var(--ink); font-weight: 700; }
.l23 .l23-panel { font-family: var(--mono); font-size: .76rem; direction: ltr; text-align: left; background: var(--code-bg); border-radius: 8px; padding: 8px 10px; white-space: pre-wrap; overflow-wrap: anywhere; min-height: 7.5em; line-height: 1.5; }
.l23 .l23-panel .del { color: var(--bad); text-decoration: line-through; }
.l23 .l23-panel .ok { color: var(--good); font-weight: 600; }
.l23 .l23-panel .no { color: var(--bad); font-weight: 600; }
.l23 .l23-dots { direction: ltr; display: grid; gap: 4px; }
.l23 .l23-drow { display: grid; grid-template-columns: 7.6rem minmax(0, 1fr) 3.4rem; gap: 6px; align-items: center; min-width: 0; }
.l23 .l23-drow .nm { font-family: var(--mono); font-size: .7rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.l23 .l23-drow .sc { font-family: var(--mono); font-size: .7rem; text-align: right; }
.l23 .l23-drow.hl .nm, .l23 .l23-drow.hl .sc { color: var(--bad); font-weight: 700; }
.l23 .l23-dd { display: flex; flex-wrap: wrap; gap: 3px; }
.l23 .l23-dd i { width: 11px; height: 11px; border-radius: 50%; background: var(--line); display: inline-block; transition: background .35s; box-sizing: border-box; }
.l23 .l23-dd i.p { background: var(--good); }
.l23 .l23-dd i.f { background: var(--bad); opacity: .75; }
.l23 .l23-dd i.ch { box-shadow: 0 0 0 2px var(--signal); }
@media (max-width: 560px) { .l23 .l23-drow { grid-template-columns: 6.2rem minmax(0, 1fr) 3rem; } .l23 .l23-dd i { width: 9px; height: 9px; } }
.l23 .l23-why { background: var(--accent-soft); border-radius: 10px; padding: 9px 12px; line-height: 1.7; font-size: .92rem; min-height: 5.6em; }
.l23 .l23-why b { color: var(--accent); }
.l23 .l23-legend { direction: rtl; display: flex; flex-wrap: wrap; gap: 10px; font-size: .78rem; color: var(--muted); }
.l23 .l23-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-inline-end: 4px; vertical-align: -1px; }
.l23 .l23-ctl { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 210px), 1fr)); gap: 10px; }
.l23 .l23-ctl label { display: grid; gap: 3px; font-size: .86rem; }
.l23 .l23-ctl output { font-family: var(--mono); font-size: .82rem; color: var(--accent); direction: ltr; }
.l23 .l23-ctl small { color: var(--muted); font-size: .76rem; line-height: 1.4; }
.l23 .l23-res { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 150px), 1fr)); gap: 8px; }
.l23 .l23-kpi { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); min-width: 0; }
.l23 .l23-kpi b { display: block; font-size: .74rem; color: var(--muted); font-weight: 500; }
.l23 .l23-kpi span { font-family: var(--mono); font-size: 1.15rem; font-weight: 700; direction: ltr; display: block; text-align: right; }
.l23 .l23-kpi.good { border-color: var(--good); background: var(--good-soft); }
.l23 .l23-kpi.bad { border-color: var(--bad); background: var(--bad-soft); }
.l23 .l23-svg { width: 100%; height: auto; display: block; direction: ltr; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.l23 .l23-svg text { fill: var(--muted); font-family: var(--mono); font-size: 10px; }
.l23 .l23-svg .b-ok { fill: var(--good); } .l23 .l23-svg .b-no { fill: var(--muted); opacity: .55; } .l23 .l23-svg .b-wrong { fill: var(--bad); }
.l23 .l23-svg .ax { stroke: var(--line); } .l23 .l23-svg .zero { stroke: var(--ink); stroke-dasharray: 3 3; } .l23 .l23-svg .tru { stroke: var(--accent); stroke-width: 2; }
.l23 .l23-svg .ci { stroke: var(--signal); stroke-width: 3; } .l23 .l23-svg .pt { fill: var(--signal); }
.l23 .l23-grid { display: grid; grid-template-columns: auto minmax(0, 1fr) minmax(0, 1fr); gap: 6px; align-items: stretch; }
.l23 .l23-grid .hd { font-size: .74rem; color: var(--muted); align-self: end; text-align: center; padding-bottom: 2px; }
.l23 .l23-grid .rh { font-size: .74rem; color: var(--muted); writing-mode: vertical-rl; transform: rotate(180deg); text-align: center; align-self: center; }
@media (max-width: 420px) { .l23 .l23-grid .rh { writing-mode: horizontal-tb; transform: none; font-size: .66rem; max-width: 3.2rem; } }
.l23 .l23-cell { border: 1px solid var(--line); border-radius: 12px; padding: 10px; background: var(--surface); text-align: right; font: inherit; color: inherit; display: grid; gap: 2px; cursor: pointer; min-width: 0; }
.l23 .l23-cell .n { font-family: var(--mono); font-size: 1.6rem; font-weight: 700; line-height: 1.1; }
.l23 .l23-cell .t { font-size: .8rem; font-weight: 600; }
.l23 .l23-cell .d { font-size: .74rem; color: var(--muted); line-height: 1.4; }
.l23 .l23-cell.agree { border-color: var(--good); background: var(--good-soft); }
.l23 .l23-cell.fpass { border-color: var(--bad); background: var(--bad-soft); }
.l23 .l23-cell.ffail { border-color: var(--signal); background: var(--signal-soft); }
.l23 .l23-cell.sel { box-shadow: 0 0 0 3px var(--accent); }
.l23 .l23-cases { display: grid; gap: 6px; }
.l23 .l23-case { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 4px; font-size: .84rem; }
.l23 .l23-case .a { direction: ltr; text-align: left; font-size: .8rem; background: var(--code-bg); border-radius: 6px; padding: 4px 8px; unicode-bidi: plaintext; }
.l23 .l23-case .m { font-family: var(--mono); font-size: .72rem; color: var(--muted); direction: ltr; text-align: right; }
.l23 .l23-case .w { color: var(--muted); line-height: 1.6; }
`;
    document.head.appendChild(s);
  }
  const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* =====================================================================
     Animation: the eval pipeline, two rounds (v1 baseline, v2 candidate)
     ===================================================================== */
  // Real per-question answer_ok of the lab's offline run (rule follower, k=5): "id v1 v2"
  const RAW = {
    version_conflict: "00111 00200 00300 00400 00511 00610 00711 00810 00900 01010 01111",
    numeric: "01200 01311 01400 01511 01611 01700 01810 01900 02011",
    single_hop: "02111 02211 02311 02411 02511 02600 02710 02800 02900 03011 03111 03211 03300 03411 03511 03611 03711 03800 03900",
    multi_hop: "04000 04100 04200 04311 04400 04500 04611 04700 04800 04911 05000",
    acronym: "05111 05211 05311 05400 05511 05611 05711 05811",
    hebrew: "05911 06011 06111 06200 06311 06411 06500 06600 06700 06800 06900",
    unanswerable: "07011 07100 07200 07300 07411 07500 07600 07700 07811 07900",
  };
  const GROUPS = Object.entries(RAW).map(([t, s]) => ({ t, q: s.split(" ").map((x) => ({ id: "q" + x.slice(0, 3), a: +x[3], b: +x[4] })) }));

  const STEPS = [
    { r: 0, st: 0, dots: "none", t: "Dataset", panel: "acme-qa@f315e0c0\n79 questions: single_hop 19, multi_hop 11, numeric 9,\nversion_conflict 11, acronym 8, hebrew 11, unanswerable 10\neach: answer_facts, source_ids, tags (stale:<id>)",
      b: "<b>הסבב הראשון מתחיל ב-dataset.</b> 79 שאלות הזהב של Acme, עם עובדות, מקורות ותגיות. הגרסה <b>f315e0c0</b> מחושבת מהתוכן: שינוי של תשובת ייחוס אחת היה משנה אותה. הנקודות למטה הן השאלות, מקובצות לפי סוג. הן אפורות כי עוד לא רצנו." },
    { r: 0, st: 1, dots: "none", t: "System v1", panel: "rag|v1:388eff|k=5|fake-rule-follower|8dadecf3\n\nsystem prompt v1 includes:\n- If sources disagree, prefer the one with the latest\n  effective_date, and say that an older version said otherwise.",
      b: "<b>המערכת:</b> ה-RAG של שיעור 9, עם הפרומפט v1. הגרסה שלה בנויה מכל מה שיכול לשנות תשובה: hash של הפרומפט, k, המודל וטביעת האצבע של האינדקס. ב-v1 יש כלל שאומר להעדיף את המסמך עם תאריך התוקף האחרון." },
    { r: 0, st: 2, dots: "none", t: "Outputs", panel: "run_system(system, dataset, cache)\n79 answers, 0 from cache (first run)\neach output: answer, cited_docs, retrieved_docs, contexts\ncache key = sha256(system version + input)",
      b: "<b>79 תשובות</b> נאספות ונשמרות במטמון לפי גרסת המערכת והקלט. הרצה חוזרת של אותה גרסה תעלה אפס, וגרסה אחרת אף פעם לא תקבל את התשובות האלה." },
    { r: 0, st: 3, dots: "a", t: "Metrics + judge", panel: "per question: answer_ok, fact_coverage, cite_precision,\ncite_recall, stale_cited, recall@5, mrr (+ judge verdicts)\nanswer_ok = answered (or abstained when unanswerable)\n          and >= half the facts and no stale citation",
      b: "<b>ניקוד.</b> כל שאלה מקבלת answer_ok: <span style='color:var(--good)'>ירוק</span> אם עברה, <span style='color:var(--bad)'>אדום</span> אם נכשלה. לצד זה נמדדים כיסוי עובדות, ציטוטים, ציטוט של גרסה מיושנת ואחזור. הניקוד הוא שלב נפרד מההרצה, ולכן אפשר לשנות מדד בלי לקרוא שוב למודל." },
    { r: 0, st: 4, dots: "a", t: "Report", panel: "answer_ok        0.544 [0.430, 0.646]  n=79\nversion_conflict 0.636 [0.364, 0.909]  n=11\nstale_cited      0.025\nreport_rule_v1_k5.md / .html",
      b: "<b>הדוח</b> מראה כל ממוצע עם רווח סמך של 95%, ופירוט לפי סוג שאלה. על 79 שאלות הרווח הוא בערך ±10 נקודות. על 11 שאלות version_conflict, הוא בערך ±27 נקודות." },
    { r: 0, st: 5, dots: "a", t: "Baseline saved", panel: "v1 is the baseline (the main branch).\nIts outputs stay in the cache, so comparing\nany candidate against it costs nothing extra.",
      b: "<b>v1 נשמר כ-baseline.</b> כל גרסה מועמדת בעתיד תושווה אליו, שאלה מול שאלה. אין עדיין gate לבדוק, כי אין עם מה להשוות." },
    { r: 1, st: 1, dots: "a", t: "System v2", panel: "rag|v2:203cd2|k=5|fake-rule-follower|8dadecf3\n\n<span class='del'>- If sources disagree, prefer the one with the latest\n  effective_date, and say that an older version said otherwise.</span>\n- Answer ... <span class='del'>in at most 4 sentences</span> briefly and helpfully.",
      b: "<b>הסבב השני: pull request עם \"ניקוי\" של הפרומפט.</b> v2 מוחק את כלל הגרסאות ומרכך את מגבלת האורך. ב-code review זה נראה תמים. ה-hash של הפרומפט השתנה, ולכן גם הגרסה, והמטמון לא יחזיר תשובות של v1." },
    { r: 1, st: 2, dots: "a", t: "Outputs", panel: "baseline v1: 79 from cache ($0)\ncandidate v2: 79 new answers\nsame 79 questions, same order -> paired comparison",
      b: "<b>רק v2 רץ באמת.</b> התשובות של v1 מגיעות מהמטמון. שתי הקבוצות על אותן 79 שאלות ובאותו סדר, וזה מה שמאפשר השוואה מזווגת." },
    { r: 1, st: 3, dots: "b", t: "Metrics", panel: "v2 vs v1, per question:\nworse on 5: q006 q008 q010 (version_conflict), q018, q027\nbetter on 0\nv2 cites the superseded version more: stale 0.025 -> 0.089",
      b: "<b>הניקוד של v2.</b> חמש שאלות עברו ב-v1 ונכשלו ב-v2, והן מסומנות ב<span style='color:var(--signal)'>מסגרת כתומה</span>. שלוש מהן הן שאלות version_conflict: המחירון, סף האישור ברכש וחופשת הלידה. בכל אחת מהן v2 ציטט את הגרסה הישנה." },
    { r: 1, st: 4, dots: "b", t: "Report", panel: "answer_ok          0.544 -> 0.481   diff -0.063\nversion_conflict   0.636 -> 0.364   diff -0.273\npaired: +0 -5 =74   McNemar p = 0.062",
      b: "<b>הדוח המזווג.</b> הממוצע הכללי ירד ב-6 נקודות, ו-version_conflict ירד ב-27 נקודות. המבחן הכללי לא מובהק: חמש שאלות שזזו לאותו כיוון נותנות p של 0.062, מעל 0.05." },
    { r: 1, st: 5, dots: "b", gate: true, t: "Gate", panel: "<span class='ok'>[PASS]</span> answer_ok >= 0.45                observed 0.481\n<span class='no'>[FAIL]</span> answer_ok[version_conflict] >= 0.50  observed 0.364\n<span class='ok'>[PASS]</span> no significant drop (all)      McNemar p=0.062\n<span class='no'>[FAIL]</span> version_conflict max drop 0.10  drop 0.273\n\nverdict: FAIL, v2 must not ship",
      b: "<b>ה-gate נכשל, ובזכות החוקים הנכונים.</b> שני החוקים הכלליים <b>עוברים</b>: הרצפה, ו\"אין ירידה מובהקת\". בלי חוקים לפי slice, v2 היה עולה. מה שעוצר אותו הוא הרצפה של version_conflict והגבול המעשי max_drop. 11 שאלות אף פעם לא יגיעו למובהקות, אבל ירידה משבע שאלות נכונות לארבע היא בדיוק מה שאסור לפספס." },
  ];
  const STATIONS = [["dataset", "golden set"], ["system", "version"], ["outputs", "cached"], ["metrics", "+ judge"], ["report", "CI per type"], ["gate", "rules"]];

  window.AIDS["l23pipe"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l23">
      <p style="margin:0">אותו צינור רץ פעמיים: פעם עם הפרומפט <b>v1</b>, שנשמר כ-baseline, ופעם עם <b>v2</b>, שמחק שורה אחת. עקוב אחרי התחנה המסומנת למעלה, אחרי הנקודות (שאלה אחת לכל נקודה) ואחרי ההסבר בתחתית.</p>
      <div class="l23-round" id="l23p-round"><span data-r="0">סבב 1: v1 (baseline)</span><span data-r="1">סבב 2: v2 (מועמד)</span></div>
      <div class="l23-pipe" id="l23p-pipe">${STATIONS.map(([a, b], i) => `<div class="l23-st" data-i="${i}"><b>${a}</b>${b}</div>`).join("")}</div>
      <div class="l23-panel" id="l23p-panel"></div>
      <div class="l23-dots" id="l23p-dots"></div>
      <div class="l23-legend"><span><i style="background:var(--good)"></i>עברה</span><span><i style="background:var(--bad);opacity:.75"></i>נכשלה</span><span><i style="background:var(--line);box-shadow:0 0 0 2px var(--signal)"></i>עברה ב-v1, נכשלה ב-v2</span><span><i style="background:var(--line)"></i>עוד לא נוקדה</span></div>
      <div class="l23-why" id="l23p-why"></div>
      <div class="row"><button class="btn small primary" id="l23p-play">השהה</button><button class="btn small" id="l23p-prev">→</button><button class="btn small" id="l23p-next">←</button><span class="spacer"></span><span class="counter" id="l23p-c" dir="ltr"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, timer = null, playing = !reduce();
    function dotsHtml(mode) {
      return GROUPS.map(({ t, q }) => {
        const val = (x) => (mode === "a" ? x.a : x.b);
        const passed = mode === "none" ? null : q.reduce((s, x) => s + val(x), 0);
        const changed = mode === "b" && q.some((x) => x.a && !x.b);
        const dd = q.map((x) => {
          let c = mode === "none" ? "" : val(x) ? "p" : "f";
          if (mode === "b" && x.a && !x.b) c += " ch";
          return `<i class="${c}" title="${x.id}"></i>`;
        }).join("");
        return `<div class="l23-drow${changed && t === "version_conflict" ? " hl" : ""}"><span class="nm">${t}</span><span class="l23-dd">${dd}</span><span class="sc">${passed === null ? "" : passed + "/" + q.length}</span></div>`;
      }).join("");
    }
    function draw() {
      const s = STEPS[i];
      host.querySelectorAll("#l23p-round span").forEach((x) => x.classList.toggle("on", +x.dataset.r === s.r));
      host.querySelectorAll(".l23-st").forEach((x) => {
        const k = +x.dataset.i;
        x.className = "l23-st" + (k === s.st ? (s.gate ? " fail" : " on") : k < s.st ? " done" : "");
      });
      g("l23p-panel").innerHTML = s.panel;
      g("l23p-dots").innerHTML = dotsHtml(s.dots);
      g("l23p-why").innerHTML = s.b;
      g("l23p-c").textContent = `${i + 1} / ${STEPS.length} · ${s.t}`;
    }
    function tick() { i = (i + 1) % STEPS.length; draw(); }
    function setPlay(p) {
      playing = p;
      g("l23p-play").textContent = p ? "השהה" : "הפעל";
      clearInterval(timer);
      if (p) timer = setInterval(tick, 5200);
    }
    g("l23p-play").onclick = () => setPlay(!playing);
    g("l23p-next").onclick = () => { setPlay(false); tick(); };
    g("l23p-prev").onclick = () => { setPlay(false); i = (i - 1 + STEPS.length) % STEPS.length; draw(); };
    draw();
    setPlay(playing);
    return () => clearInterval(timer);
  };

  /* =====================================================================
     Simulator: is this difference real?
     ===================================================================== */
  function lgamma(x) { // Lanczos approximation
    const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
    let y = x, tmp = x + 5.5; tmp -= (x + 0.5) * Math.log(tmp);
    let ser = 1.000000000190015;
    for (const k of c) ser += k / ++y;
    return -tmp + Math.log(2.5066282746310005 * ser / x);
  }
  function mcnemar(n01, n10) {
    const n = n01 + n10;
    if (!n) return 1;
    const k = Math.min(n01, n10);
    let tail = 0;
    for (let j = 0; j <= k; j++) tail += Math.exp(lgamma(n + 1) - lgamma(j + 1) - lgamma(n - j + 1) - n * Math.LN2);
    return Math.min(1, 2 * tail);
  }
  function mulberry(seed) { return () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  window.AIDS["l23diff"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l23">
      <div class="guide"><p><b>מה רואים:</b> סימולציה של ניסוי שבו שתי גרסאות, A ו-B, רצות על אותן n שאלות. אתה קובע את ה<b>אמת</b>: בכמה נקודות B באמת טובה מ-A, וכמה שאלות "זזות" בין הגרסאות סתם, בלי קשר לאיכות. זה הרעש שנובע ממודל לא דטרמיניסטי או משינוי שנוגע בהרבה תשובות. כל ניסוי מגריל את התוצאה של כל שאלה, מודד את ההפרש, ומחליט עם מבחן McNemar (p&lt;0.05) אם יש הבדל.</p>
      <p><b>איך לקרוא:</b> הכרטיסים מראים את הניסוי האחרון: ההפרש שנמדד, רווח הסמך המזווג וההחלטה. הגרף מראה את ההפרש שנמדד בכל הניסויים: <span style="color:var(--good)">ירוק</span> כשההחלטה נכונה (זוהה הבדל אמיתי, או שלא הוכרז הבדל שלא קיים), <span style="color:var(--bad)">אדום</span> כשהוכרז הבדל שגוי, ו<span style="color:var(--muted)">אפור</span> כשהבדל אמיתי לא זוהה. הקו הכחול הוא האמת, והקו המקווקו הוא אפס. "עוצמה" היא אחוז הניסויים שבהם ההחלטה נכונה.</p></div>
      <div class="l23-ctl">
        <label>מספר שאלות (n) <output id="l23d-no"></output><input type="range" id="l23d-n" min="20" max="1000" step="10" value="80"><small>ה-golden set של Acme: 79</small></label>
        <label>הבדל אמיתי (B פחות A) <output id="l23d-do"></output><input type="range" id="l23d-d" min="-10" max="20" step="1" value="5"><small>בנקודות אחוז של answer_ok</small></label>
        <label>רעש: שאלות שזזות סתם <output id="l23d-ro"></output><input type="range" id="l23d-r" min="0" max="40" step="1" value="10"><small>אחוז השאלות שמחליפות תוצאה בין הגרסאות</small></label>
      </div>
      <div class="row"><button class="btn small primary" id="l23d-one">ניסוי אחד</button><button class="btn small" id="l23d-many">200 ניסויים</button><button class="btn small" id="l23d-clear">נקה</button></div>
      <div class="l23-res" id="l23d-res"></div>
      <svg class="l23-svg" id="l23d-svg" viewBox="0 0 600 190" role="img" aria-label="histogram of measured differences"></svg>
      <div class="l23-why" id="l23d-why"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const rng = mulberry(23);
    let results = [], last = null;
    const P = () => {
      const n = +g("l23d-n").value, d = +g("l23d-d").value / 100, noise = Math.max(+g("l23d-r").value / 100, Math.abs(d) + 0.002);
      return { n, d, noise, p10: (noise + d) / 2, p01: (noise - d) / 2 };
    };
    function experiment() {
      const { n, d, p10, p01 } = P();
      let n10 = 0, n01 = 0;
      for (let k = 0; k < n; k++) { const u = rng(); if (u < p10) n10++; else if (u < p10 + p01) n01++; }
      const diff = (n10 - n01) / n;
      const se = Math.sqrt(Math.max(0, (n10 + n01) / n - diff * diff) / n);
      const p = mcnemar(n01, n10);
      const sig = p < 0.05;
      const decision = !sig ? "none" : diff > 0 ? "better" : "worse";
      const truth = Math.abs(d) < 1e-9 ? "none" : d > 0 ? "better" : "worse";
      const kind = decision === truth ? "ok" : decision === "none" ? "miss" : "wrong";
      return { diff, lo: diff - 1.96 * se, hi: diff + 1.96 * se, p, n10, n01, decision, kind };
    }
    function mdd() {
      const { n, noise } = P();
      return 2.8 * Math.sqrt(noise / n);
    }
    function draw() {
      const { n, d, noise } = P();
      g("l23d-no").textContent = n;
      g("l23d-do").textContent = (d >= 0 ? "+" : "") + Math.round(d * 100) + " pts";
      g("l23d-ro").textContent = Math.round(noise * 100) + "%";
      const ok = results.filter((r) => r.kind === "ok").length;
      const wrong = results.filter((r) => r.kind === "wrong").length;
      const dec = { none: "אין הבדל מובהק", better: "B טובה יותר", worse: "B גרועה יותר" };
      g("l23d-res").innerHTML = (last ? `
        <div class="l23-kpi"><b>ההפרש שנמדד</b><span>${(last.diff >= 0 ? "+" : "") + (last.diff * 100).toFixed(1)} pts</span></div>
        <div class="l23-kpi"><b>רווח סמך 95% (מזווג)</b><span>${(last.lo * 100).toFixed(1)} .. ${(last.hi * 100).toFixed(1)}</span></div>
        <div class="l23-kpi"><b>שאלות שזזו (B+ / A+)</b><span>${last.n10} / ${last.n01}</span></div>
        <div class="l23-kpi ${last.kind === "ok" ? "good" : "bad"}"><b>החלטה (McNemar p=${last.p < 0.001 ? "<0.001" : last.p.toFixed(3)})</b><span style="font-family:inherit;font-size:.95rem">${dec[last.decision]}</span></div>` : "")
        + `<div class="l23-kpi"><b>ניסויים</b><span>${results.length}</span></div>
        <div class="l23-kpi ${results.length ? (ok / results.length >= 0.8 ? "good" : "bad") : ""}"><b>${Math.abs(d) < 1e-9 ? "החלטה נכונה (אין הבדל)" : "עוצמה: זוהה נכון"}</b><span>${results.length ? Math.round((100 * ok) / results.length) + "%" : "-"}</span></div>
        <div class="l23-kpi"><b>הכרזה שגויה</b><span>${results.length ? Math.round((100 * wrong) / results.length) + "%" : "-"}</span></div>
        <div class="l23-kpi"><b>הפרש מינימלי לזיהוי (80%)</b><span>${(mdd() * 100).toFixed(1)} pts</span></div>`;
      // histogram
      const W = 600, H = 190, L = 30, R = 10, T = 12, B = 30, lo = -0.3, hi = 0.3, bins = 60;
      const x = (v) => L + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * (W - L - R);
      const counts = Array.from({ length: bins }, () => ({ ok: 0, miss: 0, wrong: 0 }));
      for (const r of results) { const b = Math.min(bins - 1, Math.max(0, Math.floor(((r.diff - lo) / (hi - lo)) * bins))); counts[b][r.kind]++; }
      const mx = Math.max(4, ...counts.map((c) => c.ok + c.miss + c.wrong));
      const bw = (W - L - R) / bins;
      let svg = `<line class="ax" x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}"/>`;
      counts.forEach((c, k) => {
        let y = H - B;
        for (const [key, cls] of [["ok", "b-ok"], ["miss", "b-no"], ["wrong", "b-wrong"]]) {
          const hgt = (c[key] / mx) * (H - B - T - 30);
          if (hgt > 0) { y -= hgt; svg += `<rect class="${cls}" x="${(L + k * bw + 0.5).toFixed(1)}" y="${y.toFixed(1)}" width="${(bw - 1).toFixed(1)}" height="${hgt.toFixed(1)}"/>`; }
        }
      });
      for (const v of [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3]) svg += `<text x="${x(v)}" y="${H - 12}" text-anchor="middle">${(v * 100).toFixed(0)}</text>`;
      svg += `<line class="zero" x1="${x(0)}" y1="${T}" x2="${x(0)}" y2="${H - B}"/><line class="tru" x1="${x(d)}" y1="${T}" x2="${x(d)}" y2="${H - B}"/>`;
      if (last) svg += `<line class="ci" x1="${x(last.lo)}" y1="${T + 8}" x2="${x(last.hi)}" y2="${T + 8}"/><circle class="pt" cx="${x(last.diff)}" cy="${T + 8}" r="4"/>`;
      svg += `<text x="${W - R}" y="${T + 4}" text-anchor="end">measured diff (pts)</text>`;
      g("l23d-svg").innerHTML = svg;
      const m = mdd() * 100;
      g("l23d-why").innerHTML = Math.abs(d) < 1e-9
        ? `<b>אין הבדל אמיתי.</b> כל הכרזה על הבדל היא טעות מסוג ראשון. עם רמת מובהקות של 5%, בערך אחד מכל עשרים ניסויים יכריז על הבדל שלא קיים. המבחן המדויק שמרני מעט, ולכן לרוב תראה פחות מ-5%. אם תריץ 20 גרסאות של פרומפט ותבחר את ה"טובה", כנראה מצאת רעש.`
        : `<b>עם n=${n} ורעש של ${Math.round(noise * 100)}%</b>, הפרש אמיתי של כ-${m.toFixed(1)} נקודות יזוהה ב-80% מהניסויים. ההבדל שקבעת הוא ${Math.abs(d * 100).toFixed(0)} נקודות, ולכן ${Math.abs(d * 100) >= m ? "הניסוי <b>מסוגל</b> לזהות אותו ברוב המקרים." : "הניסוי <b>חלש מדי</b>: ברוב המקרים יוצא \"אין הבדל מובהק\", למרות שיש הבדל. כדי לזהות אותו צריך יותר שאלות, או פחות רעש (temperature 0, מטמון ותשובות קבועות ל-baseline)."}`;
    }
    g("l23d-one").onclick = () => { last = experiment(); results.push(last); draw(); };
    g("l23d-many").onclick = () => { for (let k = 0; k < 200; k++) results.push(experiment()); last = results[results.length - 1]; draw(); };
    g("l23d-clear").onclick = () => { results = []; last = null; draw(); };
    ["l23d-n", "l23d-d", "l23d-r"].forEach((id) => g(id).addEventListener("input", () => { results = []; last = null; draw(); }));
    draw();
    return () => {};
  };

  /* =====================================================================
     Explorer: judge calibration against the 30 human labels of the lab
     ===================================================================== */
  // [id, human g|n, heuristic judge g|n, trap, hardness for an LLM judge (0-1), answer, labeler's why]
  const CASES = [["h01", "g", "g", "plain", 0.05, "Up to 5 unused days carry over, and they expire on March 31 [1].", "התשובה חוזרת כמעט מילה במילה על המקור. מקרה קל, כדי לוודא שהשופט לא מחמיר בלי סיבה."], ["h02", "g", "g", "stale_but_grounded", 0.6, "You can carry over up to 3 days, which expire on February 28 [1].", "מלכודת: התשובה שגויה (זו המדיניות הישנה של 2024), אבל כל טענה בה כתובה בהקשר. לכן היא grounded. ביסוס הוא לא נכונות, ואת הטעות הזו צריך לתפוס שופט correctness או מדד stale_cited."], ["h03", "n", "g", "number_swap", 0.45, "The per diem in high-cost cities is $85 per day [1].", "מלכודת: גם 85 וגם 'high-cost cities' מופיעים בהקשר, אבל לא יחד. 85 הוא הסכום לערים רגילות, וב-high-cost הסכום הוא 110. שופט לקסיקלי יעביר את זה."], ["h04", "g", "n", "plain", 0.05, "In standard cities it is now $85 a day; it used to be $75 [1].", "שתי טענות, ושתיהן במקור, כולל ההשוואה לסכום הקודם."], ["h05", "g", "g", "plain", 0.05, "No. There is no forced periodic rotation [1].", "תשובה שלילית שתואמת את המקור."], ["h06", "n", "g", "negation_flip", 0.3, "Yes, SMS codes and phone calls are accepted as a second factor [1].", "מלכודת: כל המילים של התשובה מופיעות במקור, אבל המקור אומר no longer accepted. היפוך שלילה הוא העיוורון הקלאסי של בדיקה לקסיקלית."], ["h07", "n", "n", "overgeneralization", 0.2, "Every Acme employee must use a FIDO2 key.", "המקור מחייב רק בעלי הרשאות admin, גישה לייצור וצוות הכספים. הכללה לכל העובדים היא טענה שלא כתובה."], ["h08", "g", "g", "paraphrase", 0.15, "Admins in any system, people with production access, and the Finance team must use a YubiKey (FIDO2) [1].", "ניסוח מחדש של אותה רשימה. נכון ומבוסס."], ["h09", "g", "g", "injection_followed_but_grounded", 0.8, "Yes, every annual subscription can be refunded in full at any time [2].", "מלכודת קשה: התשובה צייתה להזרקה ממייל השותף, והטענה אכן כתובה בהקשר (בתוך ההזרקה). לפי הרובריקה היא grounded. זה מראה למה groundedness לבד לא מספיק: צריך גם correctness מול עובדות הזהב, ובדיקת אבטחה (שיעור 24)."], ["h10", "g", "g", "plain", 0.05, "No. A full refund is only possible within 14 days of the initial purchase; after that annual plans are not refundable [1].", "התשובה הנכונה, שהתעלמה מההזרקה."], ["h11", "n", "n", "outside_knowledge", 0.6, "Report it to IT and Security within 1 hour of noticing [1]. IT will then lock and wipe it remotely.", "המשפט השני נכון במציאות של Acme (הוא מופיע בתשובת הזהב), אבל הוא לא כתוב בהקשר שנשלח. טענה שלא בהקשר היא לא מבוססת, גם אם היא נכונה."], ["h12", "g", "g", "paraphrase", 0.15, "Tell IT (it@acme.example) and Security (security@acme.example) within an hour of noticing [1].", "within an hour במקום within 1 hour. שקול לחלוטין, ו-1 נעלם מהתשובה, כך שבדיקת מספרים לא נפגעת."], ["h13", "n", "n", "outside_knowledge", 0.6, "Within 72 hours of becoming aware of it, as GDPR Article 33 requires [1].", "Article 33 הוא ידע כללי נכון, אבל ההקשר לא מזכיר אותו. לפי הרובריקה זו טענה לא מבוססת. מקרה שבו אנשים סבירים יכולים להתווכח: הוא נכלל בכוונה, כי גם ב-golden set של שופטים יש מקרים גבוליים."], ["h14", "g", "g", "plain", 0.05, "It indexes Public, Internal and Confidential documents; Restricted information is never indexed [1].", "חזרה מדויקת."], ["h15", "n", "g", "partial_invented", 0.35, "Restricted information is never indexed, and Confidential documents are never indexed either [1].", "הטענה השנייה הפוכה למקור, אבל כל המילים שלה (confidential, documents, never, indexed) מופיעות בו. שופט לקסיקלי יעביר."], ["h16", "g", "n", "number_in_words", 0.25, "The Security team completes it within two business days [1].", "two במקום 2. אותה עובדה. בדיקה שמחפשת מילים תיכשל על two."], ["h17", "g", "g", "plain", 0.05, "15 paid days, which is three working weeks, to be taken within 6 months of the birth or adoption [1].", "חזרה על המקור."], ["h18", "n", "n", "number_swap", 0.45, "The non-birth parent gets 15 paid days, to be taken within the first 3 months [1].", "3 חודשים זה הערך מהמדיניות הישנה, והוא לא בהקשר. מספר שגוי בתוך משפט שכולו נשמע נכון."], ["h19", "g", "g", "plain", 0.05, "About 47 minutes, from 14:06 to 14:53 Israel time [1].", "מספרים ושעות מדויקים."], ["h20", "n", "n", "extra_number", 0.3, "47 minutes, and 312 customers were affected [1].", "312 הוא מספר הלקוחות מתקלת החיוב של יוני, לא מהתקלה הזו, והוא לא בהקשר."], ["h21", "g", "n", "plain", 0.05, "€48,900 in total across 312 euro-billed customers, roughly €157 each [1].", "שלוש עובדות מספריות, כולן במקור."], ["h22", "g", "n", "cross_lingual", 0.3, "עובד במשרה מלאה מקבל 14 ימי חופשה בתשלום בשנה הראשונה [1].", "התשובה בעברית וההקשר באנגלית. זו אותה עובדה בתרגום, ולכן grounded. בדיקה לקסיקלית לא רואה שום מילה משותפת חוץ מ-14."], ["h23", "n", "n", "number_swap", 0.45, "יש 18 מקומות חניה, בקומה מינוס 1 [1].", "הקומה היא מינוס 2. שוב מספר אחד שגוי בתוך משפט שנראה מבוסס."], ["h24", "g", "g", "plain", 0.05, "500 ש\"ח על כל 10 ימי מילואים בשנה, עד 3,000 ש\"ח בשנה [1].", "עברית מול עברית, עם מספרים מדויקים."], ["h25", "g", "g", "plain", 0.05, "From Thursday 15:00 to Sunday 09:00 Israel time, and on holiday eves from 15:00 until 09:00 on the next working day [1].", "סיכום נאמן של הגדרה ארוכה."], ["h26", "n", "n", "number_swap", 0.45, "auth-service is owned by the Identity team, led by Gil Avraham; the on-call handover is on Sunday at 10:00 [1].", "ההחלפה ביום חמישי, לא ראשון. 10:00 נכון, ולכן בדיקת מספרים בלבד לא תתפוס את זה."], ["h27", "g", "g", "wrong_refusal", 0.65, "not in the documents", "מלכודת: התשובה במקור, והמערכת סירבה. אין בסירוב שום טענה, ולכן לפי הרובריקה הוא grounded. את הכשל הזה תופס שופט refusal או המדד abstain_ok, לא שופט ביסוס."], ["h28", "g", "g", "plain", 0.05, "When the canary error rate is more than 0.5 percentage points higher than stable, or p99 latency is more than 20% higher [1].", "חזרה על המקור."], ["h29", "n", "n", "extra_number", 0.3, "ההסעה יוצאת בשעות 08:15, 08:45, 09:15 ו-09:45 [1].", "09:45 לא קיים בהקשר. טענה אחת מומצאת מתוך ארבע: לפי הרובריקה זה partially_grounded, ובשתי קטגוריות זה not_grounded."], ["h30", "n", "n", "irrelevant_claim", 0.4, "One of the 25 highest-ARR accounts, on Shira Levin's list [1]; their tickets go straight to L2 [2]. Home office allowance is 1,500 NIS.", "המשפט האחרון לא קשור לשאלה ולא מופיע בהקשר (הוא נכון במסמך אחר שלא נשלח). טענה לא מבוססת, גם אם היא נכונה במקום אחר."]];

  window.AIDS["l23calib"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l23">
      <div class="guide"><p><b>מה רואים:</b> 30 התשובות מ-<code>labs/23-evaluation/data/human_labels.jsonl</code>. לכל אחת יש תווית של בן אדם, grounded או not_grounded, והשאלה היא כמה פעמים השופט מסכים איתה. ארבעת הכרטיסים הם מטריצת הבלבול: השורה היא מה שהאדם אמר, והעמודה היא מה שהשופט אמר. הכרטיסים הירוקים הם הסכמה. הכרטיס האדום הוא <b>false pass</b>, תשובה פסולה שהשופט העביר, שב-gate היא רגרסיה שעוברת. הכרטיס הכתום הוא <b>false fail</b>, התראת שווא.</p>
      <p><b>מה לנסות:</b> בחר שופט למעלה. לחץ על כרטיס כדי לראות את המקרים שבו, עם המלכודת והנימוק של המתייג. ב"שופט LLM מדומה" אתה קובע <b>מיומנות</b> (כמה מלכודות קשות הוא מזהה) ו<b>מקלות</b> (כמה פעמים הוא אומר grounded כשהוא לא בטוח). זו סימולציה להבנת המדדים. את השופט האמיתי מריצים בתרגיל 5.</p></div>
      <div class="seg" id="l23c-mode"><button data-m="lex" aria-pressed="true">שופט לקסיקלי (מהמעבדה)</button><button data-m="llm" aria-pressed="false">שופט LLM מדומה</button><button data-m="all" aria-pressed="false">תמיד grounded</button></div>
      <div class="l23-ctl" id="l23c-knobs" hidden>
        <label>מיומנות <output id="l23c-so"></output><input type="range" id="l23c-s" min="0" max="100" value="70"><small>גבוהה: מזהה גם הזרקה ועובדה מחוץ להקשר</small></label>
        <label>מקלות <output id="l23c-lo"></output><input type="range" id="l23c-l" min="0" max="100" value="15"><small>הסיכוי לומר grounded על תשובה פסולה שהוא זיהה</small></label>
      </div>
      <div class="l23-res" id="l23c-res"></div>
      <div class="l23-grid" id="l23c-grid"></div>
      <div class="l23-cases" id="l23c-cases"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let mode = "lex", sel = "fp";
    const u = (k) => ((Math.sin(k * 12.9898 + 4.1) * 43758.5453) % 1 + 1) % 1; // fixed pseudo-random per case
    function judgeLabels() {
      if (mode === "all") return CASES.map(() => "g");
      if (mode === "lex") return CASES.map((c) => c[2]);
      const skill = +g("l23c-s").value / 100, len = +g("l23c-l").value / 100;
      return CASES.map((c, k) => {
        const right = skill >= c[4] ? c[1] : c[1] === "g" ? "n" : "g";
        if (right === "n" && c[1] === "n" && u(k) < len) return "g";
        return right;
      });
    }
    function kappa(h, j) {
      const n = h.length, po = h.filter((x, k) => x === j[k]).length / n;
      const pe = ["g", "n"].reduce((s, l) => s + (h.filter((x) => x === l).length / n) * (j.filter((x) => x === l).length / n), 0);
      return pe >= 1 ? (po === 1 ? 1 : 0) : (po - pe) / (1 - pe);
    }
    function draw() {
      g("l23c-knobs").hidden = mode !== "llm";
      g("l23c-so").textContent = g("l23c-s").value + "%";
      g("l23c-lo").textContent = g("l23c-l").value + "%";
      host.querySelectorAll("#l23c-mode button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.m === mode)));
      const H = CASES.map((c) => c[1]), J = judgeLabels();
      const cell = (h, j) => CASES.map((c, k) => k).filter((k) => H[k] === h && J[k] === j);
      const cells = { tp: cell("g", "g"), ff: cell("g", "n"), fp: cell("n", "g"), tn: cell("n", "n") };
      const agree = (cells.tp.length + cells.tn.length) / CASES.length, k = kappa(H, J);
      const band = k < 0 ? "גרוע ממקרי" : k <= 0.2 ? "קלוש" : k <= 0.4 ? "חלש" : k <= 0.6 ? "בינוני" : k <= 0.8 ? "משמעותי" : "כמעט מלא";
      g("l23c-res").innerHTML = `
        <div class="l23-kpi"><b>agreement</b><span>${(agree * 100).toFixed(1)}%</span></div>
        <div class="l23-kpi ${k >= 0.6 ? "good" : k < 0.4 ? "bad" : ""}"><b>Cohen's kappa (${band})</b><span>${k.toFixed(2)}</span></div>
        <div class="l23-kpi ${cells.fp.length ? "bad" : "good"}"><b>false pass</b><span>${cells.fp.length}</span></div>
        <div class="l23-kpi"><b>false fail</b><span>${cells.ff.length}</span></div>`;
      const card = (key, cls, title, desc) => `<button class="l23-cell ${cls}${sel === key ? " sel" : ""}" data-k="${key}"><span class="n">${cells[key].length}</span><span class="t">${title}</span><span class="d">${desc}</span></button>`;
      g("l23c-grid").innerHTML = `<span></span><span class="hd">השופט: grounded</span><span class="hd">השופט: not_grounded</span>
        <span class="rh">אדם: grounded (18)</span>${card("tp", "agree", "הסכמה", "שניהם אמרו grounded")}${card("ff", "ffail", "false fail", "תשובה תקינה שנפסלה: התראת שווא")}
        <span class="rh">אדם: not_grounded (12)</span>${card("fp", "fpass", "false pass", "תשובה פסולה שעברה: רגרסיה שחומקת")}${card("tn", "agree", "הסכמה", "שניהם אמרו not_grounded")}`;
      host.querySelectorAll(".l23-cell").forEach((b) => (b.onclick = () => { sel = b.dataset.k; draw(); }));
      const names = { tp: "הסכמה על grounded", ff: "false fail", fp: "false pass", tn: "הסכמה על not_grounded" };
      const list = cells[sel];
      g("l23c-cases").innerHTML = `<b style="font-size:.9rem">${names[sel]}: ${list.length} מקרים</b>` + (list.length ? list.map((i) => {
        const c = CASES[i];
        return `<div class="l23-case"><span class="m">${c[0]} · trap: ${esc(c[3])} · human ${c[1] === "g" ? "grounded" : "not_grounded"} · judge ${J[i] === "g" ? "grounded" : "not_grounded"}</span><span class="a">${esc(c[5])}</span><span class="w">${esc(c[6])}</span></div>`;
      }).join("") : `<span class="muted" style="font-size:.85rem">אין מקרים בכרטיס הזה.</span>`)
        + (mode === "all" ? `<div class="l23-why"><b>שופט שתמיד אומר grounded</b> מסכים עם האדם ב-60% מהמקרים (18 מתוך 30), כי זה החלק של התשובות התקינות בסט. ה-kappa שלו הוא 0: הוא לא יודע כלום. ב-gate הוא יעביר כל רגרסיה. זו הסיבה שמדווחים kappa ואת שני תאי הטעות, ולא רק agreement.</div>` : "");
    }
    host.querySelectorAll("#l23c-mode button").forEach((b) => (b.onclick = () => { mode = b.dataset.m; draw(); }));
    ["l23c-s", "l23c-l"].forEach((id) => g(id).addEventListener("input", draw));
    draw();
    return () => {};
  };
})();
