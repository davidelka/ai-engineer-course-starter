// Lesson 12 aids: RRF merge animation (l12rrf), RRF vs weighted fusion playground (l12fuse),
// ablation explorer with the lab's OFFLINE numbers (l12ablate).
// Self-contained; uses only CSS variables from index.html so dark mode works.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const CSS = `
  .l12 { display: grid; gap: 12px; direction: rtl; }
  .l12 .l12-bar { display: flex; flex-wrap: wrap; gap: 4px; }
  .l12 .l12-bar button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 3px 9px; font-size: .78rem; }
  .l12 .l12-bar button.on { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .l12 .l12-bar button.done { color: var(--muted); }
  .l12 .l12-cap { font-size: .9rem; line-height: 1.75; }
  .l12 .l12-cap b.t { display: block; font-size: .98rem; margin-bottom: 2px; }
  .l12 .l12-warn { font-size: .86rem; line-height: 1.7; color: var(--bad); border-inline-start: 3px solid var(--bad); padding-inline-start: 8px; }
  .l12 .l12-q { font-size: .86rem; line-height: 1.6; direction: ltr; text-align: left; background: var(--code-bg); border-radius: 8px; padding: 6px 9px; overflow-wrap: anywhere; }
  .l12 .l12-cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
  .l12 .l12-col h5 { margin: 0 0 4px; font-size: .82rem; color: var(--muted); font-weight: 600; }
  .l12 .l12-list { display: grid; gap: 4px; }
  .l12 .l12-it { display: grid; grid-template-columns: 1.4rem minmax(0, 1fr); gap: 2px 6px; align-items: center; direction: ltr; text-align: left; font-size: .76rem; border: 1px solid var(--line); border-radius: 8px; padding: 4px 6px; background: var(--surface); transition: background .3s, border-color .3s, opacity .3s; }
  .l12 .l12-it b.r { font-family: var(--mono); color: var(--muted); font-weight: 600; }
  .l12 .l12-it code { font-family: var(--mono); font-size: .74rem; overflow-wrap: anywhere; }
  .l12 .l12-it .tm { grid-column: 2; font-family: var(--mono); font-size: .7rem; color: var(--muted); }
  .l12 .l12-it.rel { border-color: var(--good); }
  .l12 .l12-it.rel code::after { content: " ✓"; color: var(--good); font-weight: 700; }
  .l12 .l12-it.both { background: var(--accent-soft); border-color: var(--accent); }
  .l12 .l12-it.dim { opacity: .45; }
  .l12 .l12-fused { display: grid; gap: 4px; }
  .l12 .l12-frow { text-align: left; display: grid; grid-template-columns: 1.4rem minmax(0, 1fr) 4.2rem; gap: 6px; align-items: center; direction: ltr; font-size: .76rem; }
  .l12 .l12-frow code { font-family: var(--mono); font-size: .74rem; overflow-wrap: anywhere; }
  .l12 .l12-frow .bar { height: 7px; border-radius: 4px; background: var(--accent); margin-top: 2px; }
  .l12 .l12-frow.rel .bar { background: var(--good); }
  .l12 .l12-frow.rel code { color: var(--good); font-weight: 700; }
  .l12 .l12-frow i { font-style: normal; font-family: var(--mono); text-align: right; font-size: .72rem; }
  .l12 .l12-frow small { display: block; color: var(--muted); font-size: .68rem; font-family: var(--mono); overflow-wrap: anywhere; }
  .l12 .l12-cut { border-top: 2px dashed var(--signal); margin: 2px 0; position: relative; height: 0; }
  .l12 .l12-cut span { position: absolute; top: -.8em; left: 6px; background: var(--surface); color: var(--signal); font-size: .68rem; padding: 0 4px; font-family: var(--mono); }
  .l12 .l12-two { display: grid; gap: 10px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .l12 .l12-two { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }
  .l12 .l12-box { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 6px; min-width: 0; }
  .l12 .l12-box h5 { margin: 0; font-size: .86rem; }
  .l12 .l12-edit { display: grid; gap: 4px; }
  .l12 .l12-er { text-align: left; display: grid; grid-template-columns: 1.3rem minmax(0, 1fr) 4.4rem 2.2rem; gap: 5px; align-items: center; direction: ltr; font-size: .76rem; }
  .l12 .l12-er code { font-family: var(--mono); font-size: .72rem; overflow-wrap: anywhere; }
  .l12 .l12-er.rel code { color: var(--good); font-weight: 700; }
  .l12 .l12-er.off { opacity: .45; }
  .l12 .l12-er input[type=number] { width: 100%; font-family: var(--mono); font-size: .76rem; padding: 2px 4px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); }
  .l12 .l12-er button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 6px; padding: 1px 0; font-size: .7rem; }
  .l12 .l12-ctl { display: grid; gap: 10px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .l12 .l12-ctl { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .l12 input[type=range] { width: 100%; }
  .l12 .l12-note { font-size: .78rem; color: var(--muted); line-height: 1.6; }
  .l12 .l12-diff { font-size: .84rem; line-height: 1.7; }
  .l12 .l12-ab { display: grid; gap: 5px; }
  .l12 .l12-abr { display: grid; grid-template-columns: minmax(0, 11rem) minmax(0, 1fr) 3.6rem 3.8rem; gap: 6px; align-items: center; font-size: .78rem; }
  .l12 .l12-abr .nm { line-height: 1.35; overflow-wrap: anywhere; }
  .l12 .l12-abr .nm small { display: block; color: var(--muted); font-size: .68rem; }
  .l12 .l12-abr .bar { height: 10px; border-radius: 4px; background: var(--accent); direction: ltr; }
  .l12 .l12-abr.fake .bar { background: repeating-linear-gradient(135deg, var(--accent) 0 6px, var(--accent-soft) 6px 10px); }
  .l12 .l12-abr.ref { opacity: .6; }
  .l12 .l12-abr b { font-family: var(--mono); text-align: left; direction: ltr; font-size: .78rem; }
  .l12 .l12-abr i { font-style: normal; font-family: var(--mono); text-align: left; direction: ltr; font-size: .72rem; }
  .l12 .l12-abr i.up { color: var(--good); }
  .l12 .l12-abr i.down { color: var(--bad); }
  .l12 .l12-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .74rem; color: var(--muted); align-items: center; }
  .l12 .l12-legend span::before { content: ""; display: inline-block; width: 14px; height: 9px; border-radius: 3px; margin-inline-end: 4px; vertical-align: middle; background: var(--accent); }
  .l12 .l12-legend span.f::before { background: repeating-linear-gradient(135deg, var(--accent) 0 5px, var(--accent-soft) 5px 8px); }
  @media (max-width: 480px) { .l12 .l12-abr { grid-template-columns: minmax(0, 7.6rem) minmax(0, 1fr) 3.2rem 3.4rem; } }
  `;
  function style() {
    if (document.getElementById("l12-style")) return;
    const s = document.createElement("style");
    s.id = "l12-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fx = (v, d = 4) => (Math.round(v * 10 ** d) / 10 ** d).toFixed(d);

  // RRF with the same tie rules as ragkit.fusion.rrf: score desc, best rank asc, id asc.
  function rrf(lists, k, weights) {
    const terms = {}, best = {};
    lists.forEach((L, li) => {
      const w = weights ? weights[li] : 1;
      const seen = new Set();
      L.forEach((d, i) => {
        if (seen.has(d)) return;
        seen.add(d);
        (terms[d] = terms[d] || []).push({ li, r: i + 1, v: w / (k + i + 1) });
        best[d] = Math.min(best[d] ?? Infinity, i + 1);
      });
    });
    return Object.keys(terms).map((d) => ({ d, s: terms[d].reduce((a, t) => a + t.v, 0), terms: terms[d], best: best[d] }))
      .sort((a, b) => (Math.abs(b.s - a.s) > 1e-12 ? b.s - a.s : a.best - b.best || (a.d < b.d ? -1 : 1)));
  }

  /* ================================================================ l12rrf (animation) */
  // ILLUSTRATIVE rankings for a q040-like multi-hop question (the guide says so).
  const QTXT = "Which team owns the service whose configuration change caused the August 2026 flow-api outage?";
  const REL = new Set(["eng-pm-2026-08-api", "eng-service-catalog"]);
  const A = ["eng-pm-2026-08-api", "eng-deploy-process", "eng-architecture", "eng-runbook-flow-api", "eng-leads-sync-2026-05", "eng-service-catalog"];
  const B = ["eng-pm-2026-08-api", "co-org-chart", "eng-runbook-flow-api", "eng-service-catalog", "sup-escalation", "eng-oncall-scheduler-he"];
  const STEPS = [
    { name: "שתי רשימות", title: "1. שני retrievers, שתי רשימות",
      cap: "מימין BM25 ומשמאל dense, לאותה שאלה. כל אחד מצא את ה-postmortem (מסומן ב-✓). את קטלוג השירותים, המסמך השני שהשאלה צריכה, BM25 דירג במקום 6 ו-dense במקום 4. הציונים הגולמיים לא מוצגים: BM25 נותן מספרים כמו 27.7, dense נותן 0.48, ו-RRF לא משתמש באף אחד מהם.",
      warn: "הדירוגים כאן להמחשה. את הדירוגים האמיתיים של q040 תראה ב-fusion_demo.py במעבדה." },
    { name: "תרומות", title: "2. כל מקום הופך לתרומה: 1/(60+rank)",
      cap: "מתחת לכל מסמך מופיעה התרומה שלו מהרשימה הזו. שים לב כמה הן קרובות: מקום 1 שווה 0.0164 ומקום 6 שווה 0.0152. עם k=60 ההבדל בין ראשון לשישי קטן מאוד, ולכן מה שיכריע הוא <b>כמה רשימות</b> מצאו את המסמך.",
      warn: "מסמך שחסר ברשימה לא מקבל ממנה כלום. זה לא עונש, פשוט אין איבר." },
    { name: "בשתיהן", title: "3. מי נמצא בשתי הרשימות",
      cap: "המסמכים המודגשים מופיעים בשתי הרשימות, ולכן הם יקבלו שתי תרומות: ה-postmortem, ה-runbook של flow-api וקטלוג השירותים. כל השאר מופיעים רק ברשימה אחת.",
      warn: "גם מסמך לא רלוונטי יכול להופיע בשתי הרשימות, כמו ה-runbook כאן. RRF מתגמל הסכמה, לא נכונות." },
    { name: "איחוד (k=60)", title: "4. הרשימה המאוחדת עם k=60",
      cap: "כל מסמך מקבל את סכום התרומות שלו, והרשימה ממוינת לפיו. קטלוג השירותים, שהיה שישי ב-BM25 ורביעי ב-dense, עולה למקום 3 ונכנס ל-top 5. הוא עקף את co-org-chart, שהיה שני ב-dense אבל לא נמצא ב-BM25. ה-recall@5 של השאלה הוא 1.0: שני המסמכים בפנים.",
      warn: "בשוויון מדויק, ragkit מעדיף את המסמך עם המקום הטוב ביותר ברשימה כלשהי, ואחר כך לפי המזהה." },
    { name: "k=0", title: "5. אותן רשימות, עם k=0",
      cap: "עכשיו מקום 1 שווה 1.0, מקום 2 שווה 0.5 ומקום 6 שווה 0.167. מי שהיה שני ברשימה אחת (co-org-chart, eng-deploy-process) מקבל 0.5 ועוקף את קטלוג השירותים (1/6 + 1/4 = 0.417), שנדחק אל מתחת לקו של top 4. העקומה התלולה מתגמלת מקום גבוה ברשימה אחת, ולא הסכמה.",
      warn: "k קטן מגביר את ההשפעה של retriever אחד שטעה בביטחון. לכן k=60 הוא ברירת המחדל." },
    { name: "מסקנה", title: "6. מה לקחת מכאן",
      cap: "RRF צריך רק את המקומות, ולכן אין צורך לנרמל ציונים שחיים בסקאלות שונות. k קובע את הצורה: 60 היא \"הסכמה מנצחת\", ו-0 היא \"מקום ראשון מנצח\". כדי שמסמך כמו הקטלוג יגיע לאיחוד בכלל, כל retriever צריך להחזיר מספיק מועמדים (fetch_k, ב-ragkit 50), ולא רק 5.",
      warn: "RRF לא יודע כמה \"ראשון\" היה הראשון. אם זה חשוב, weighted fusion שומר את המידע הזה, במחיר של נרמול. נסה במגרש המשחקים שמתחת." },
  ];

  window.AIDS["l12rrf"] = function (host) {
    style();
    host.innerHTML = `<div class="l12">
      <div class="guide"><p><b>מה רואים:</b> שאלת multi-hop מ-Acme, ושתי רשימות מסמכים שחזרו עליה: מימין <b>BM25</b>, משמאל <b>dense</b>. המסמכים הרלוונטיים מסומנים ב-✓ ובמסגרת ירוקה. בתחתית נבנית <b>הרשימה המאוחדת</b>, עם הסכום של כל מסמך והחישוב שלו. הקו המקווקו הכתום מסמן את גבול ה-top. הדירוגים להמחשה.</p></div>
      <div class="l12-bar" id="r-bar"></div>
      <div class="l12-q">${esc(QTXT)}</div>
      <div class="l12-cols">
        <div class="l12-col"><h5>BM25 (מילים)</h5><div class="l12-list" id="r-a"></div></div>
        <div class="l12-col"><h5>dense (embeddings)</h5><div class="l12-list" id="r-b"></div></div>
      </div>
      <div class="l12-box" id="r-fbox" style="display:none"><h5 id="r-ftitle"></h5><div class="l12-fused" id="r-f"></div></div>
      <div class="l12-cap" id="r-cap"></div>
      <div class="l12-warn" id="r-warn"></div>
      <div class="row"><button class="btn small primary" id="r-play">השהה</button><button class="btn small" id="r-prev" aria-label="שלב קודם">→</button><button class="btn small" id="r-next" aria-label="שלב הבא">←</button><span class="spacer"></span><span class="counter" id="r-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, timer = null, playing = !RM();
    g("r-bar").innerHTML = STEPS.map((s, k) => `<button data-k="${k}">${k + 1}. ${s.name}</button>`).join("");
    const inBoth = new Set(A.filter((d) => B.includes(d)));

    function list(L, el, kk) {
      el.innerHTML = L.map((d, n) => {
        const cls = ["l12-it", REL.has(d) ? "rel" : "", i >= 2 && inBoth.has(d) ? "both" : "", i === 2 && !inBoth.has(d) ? "dim" : ""].join(" ");
        const tm = i >= 1 ? `<span class="tm">1/(${kk}+${n + 1}) = ${fx(1 / (kk + n + 1))}</span>` : "";
        return `<div class="${cls}"><b class="r">${n + 1}</b><code>${esc(d)}</code>${tm}</div>`;
      }).join("");
    }
    function fused(kk, cut) {
      const out = rrf([A, B], kk);
      const max = out[0].s;
      let h = "";
      out.forEach((x, n) => {
        if (n === cut) h += `<div class="l12-cut"><span>top ${cut}</span></div>`;
        const parts = [0, 1].map((li) => { const t = x.terms.find((y) => y.li === li); return t ? `1/(${kk}+${t.r})` : "—"; });
        h += `<div class="l12-frow ${REL.has(x.d) ? "rel" : ""}"><b>${n + 1}</b><div><code>${esc(x.d)}</code><small>${parts[0]} + ${parts[1]}</small><div class="bar" style="width:${(x.s / max) * 100}%"></div></div><i>${fx(x.s, kk === 0 ? 3 : 4)}</i></div>`;
      });
      return h;
    }
    function draw() {
      const s = STEPS[i];
      const kk = i === 4 ? 0 : 60;
      list(A, g("r-a"), kk);
      list(B, g("r-b"), kk);
      const showF = i >= 3;
      g("r-fbox").style.display = showF ? "" : "none";
      if (showF) {
        g("r-ftitle").textContent = i === 4 ? "הרשימה המאוחדת עם k=0" : "הרשימה המאוחדת עם k=60";
        g("r-f").innerHTML = fused(kk, i === 4 ? 4 : 5);
      }
      g("r-cap").innerHTML = `<b class="t">${s.title}</b>${s.cap}`;
      g("r-warn").innerHTML = "<b>לזכור: </b>" + s.warn;
      g("r-c").textContent = `${i + 1}/${STEPS.length}`;
      host.querySelectorAll("#r-bar button").forEach((b, k) => { b.classList.toggle("on", k === i); b.classList.toggle("done", k < i); });
      g("r-play").textContent = playing ? "השהה" : "הפעל";
      clearTimeout(timer);
      if (playing) timer = setTimeout(() => { i = (i + 1) % STEPS.length; draw(); }, i === 0 ? 7000 : 9500);
    }
    g("r-play").addEventListener("click", () => { playing = !playing; draw(); });
    g("r-prev").addEventListener("click", () => { playing = false; i = (i + STEPS.length - 1) % STEPS.length; draw(); });
    g("r-next").addEventListener("click", () => { playing = false; i = (i + 1) % STEPS.length; draw(); });
    host.querySelectorAll("#r-bar button").forEach((b) => b.addEventListener("click", () => { playing = false; i = +b.dataset.k; draw(); }));
    draw();
    return () => clearTimeout(timer);
  };

  /* ================================================================ l12fuse (playground) */
  const DOCS = ["fin-travel-2026", "fin-travel-2025", "hr-expenses", "co-offices", "sales-sla-2026", "it-helpdesk"];
  const FREL = new Set(["fin-travel-2026"]);
  const PRESETS = {
    agree: { name: "הסכמה", note: "המסמך הנכון (fin-travel-2026) שלישי בשתי הרשימות. בכל רשימה מישהו אחר ראשון.",
      a: [[16, 1], [21, 1], [18, 1], [4, 1], [4.5, 1], [5, 1]], b: [[0.80, 1], [0.60, 1], [0.65, 1], [0.86, 1], [0.83, 1], [0.66, 1]] },
    outlier: { name: "outlier", note: "ל-BM25 יש התאמה אחת חזקה מאוד (35) על מזהה, וכל השאר בין 6 ל-9. ב-min-max כל השאר נמחצים לאפס.",
      a: [[9, 1], [8, 1], [35, 1], [7, 1], [6.5, 1], [6, 1]], b: [[0.86, 1], [0.84, 1], [0.79, 1], [0.78, 1], [0.70, 1], [0.69, 1]] },
    missing: { name: "חסר", note: "dense החזיר רק שלושה מסמכים. fin-travel-2026 אחרון אצלו, ו-hr-expenses לא הוחזר בכלל. ב-min-max שניהם מקבלים 0 מ-dense.",
      a: [[15, 1], [17, 1], [16, 1], [8, 1], [6, 1], [4, 1]], b: [[0.71, 1], [0.83, 1], [0, 0], [0.80, 1], [0, 0], [0, 0]] },
  };

  window.AIDS["l12fuse"] = function (host) {
    style();
    host.innerHTML = `<div class="l12">
      <div class="guide"><p><b>מה רואים:</b> אותם שישה מסמכים מ-Acme בשתי רשימות. בכל רשימה, לכל מסמך יש <b>ציון גולמי</b> שאפשר לשנות (BM25 בעשרות, cosine בין 0 ל-1), וכפתור שמוציא אותו מהרשימה, כאילו ה-retriever לא החזיר אותו. <b>המקום</b> (rank) נגזר מהציון. מתחת מופיעות שתי רשימות מאוחדות: <b>RRF</b>, שמשתמש רק במקומות, ו-<b>weighted</b>, שמנרמל את הציונים ומחבר אותם עם משקל. המסמך הנכון לשאלה "What is the daily per diem in a standard city?" הוא <code>fin-travel-2026</code>, והוא מסומן בירוק.</p>
      <p><b>מה לנסות:</b> בחר תרחיש, שנה את k, את המשקל ואת הנרמול, ושים לב לשורת ההבדלים בתחתית.</p></div>
      <div class="seg" id="f-pre"></div>
      <div class="l12-note" id="f-note"></div>
      <div class="l12-two">
        <div class="l12-box"><h5>BM25: ציון גולמי</h5><div class="l12-edit" id="f-a"></div></div>
        <div class="l12-box"><h5>dense: cosine</h5><div class="l12-edit" id="f-b"></div></div>
      </div>
      <div class="l12-ctl">
        <div class="knob"><div class="knob-head"><span>k של RRF</span><b id="f-kv"></b></div><input type="range" id="f-k" min="0" max="200" step="1" value="60"><small>0 = מקום ראשון מנצח, 60 = ברירת המחדל</small></div>
        <div class="knob"><div class="knob-head"><span>משקל BM25 ב-weighted</span><b id="f-wv"></b></div><input type="range" id="f-w" min="0" max="1" step="0.05" value="0.5"><small>dense מקבל 1 פחות המשקל</small></div>
        <div class="knob"><div class="knob-head"><span>נרמול</span><b id="f-nv"></b></div><div class="seg" id="f-norm"><button data-n="minmax" aria-pressed="true">min-max</button><button data-n="zscore" aria-pressed="false">z-score</button><button data-n="none" aria-pressed="false">בלי</button></div></div>
      </div>
      <div class="l12-two">
        <div class="l12-box"><h5>RRF</h5><div class="l12-fused" id="f-rrf"></div></div>
        <div class="l12-box"><h5>weighted fusion</h5><div class="l12-fused" id="f-wf"></div></div>
      </div>
      <div class="l12-diff" id="f-diff"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let st = null, k = 60, w = 0.5, norm = "minmax", pre = "agree";
    g("f-pre").innerHTML = Object.entries(PRESETS).map(([key, p]) => `<button data-p="${key}" aria-pressed="${key === pre}">${p.name}</button>`).join("");
    function load(key) {
      pre = key;
      const p = PRESETS[key];
      st = { a: DOCS.map((d, n) => ({ d, s: p.a[n][0], on: !!p.a[n][1] })), b: DOCS.map((d, n) => ({ d, s: p.b[n][0], on: !!p.b[n][1] })) };
      g("f-note").textContent = p.note;
      host.querySelectorAll("#f-pre button").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.p === key)));
      editors();
      calc();
    }
    const ranked = (L) => L.filter((x) => x.on).slice().sort((x, y) => y.s - x.s || (x.d < y.d ? -1 : 1));
    function editors() {
      for (const side of ["a", "b"]) {
        const L = st[side], order = ranked(L).map((x) => x.d);
        g("f-" + side).innerHTML = L.map((x, n) => {
          const r = order.indexOf(x.d);
          return `<div class="l12-er ${FREL.has(x.d) ? "rel" : ""} ${x.on ? "" : "off"}"><b>${r >= 0 ? r + 1 : "–"}</b><code>${esc(x.d)}</code><input type="number" step="${side === "a" ? 0.5 : 0.01}" value="${x.s}" data-s="${side}" data-n="${n}" aria-label="ציון של ${esc(x.d)}" ${x.on ? "" : "disabled"}><button data-t="${side}" data-n="${n}" aria-label="${x.on ? "הוצא" : "החזר"}">${x.on ? "הוצא" : "החזר"}</button></div>`;
        }).join("");
      }
      host.querySelectorAll(".l12-er input").forEach((inp) => inp.addEventListener("input", () => {
        const v = parseFloat(inp.value);
        if (!Number.isFinite(v)) return;
        st[inp.dataset.s][+inp.dataset.n].s = v;
        refreshRanks();
        calc();
      }));
      host.querySelectorAll(".l12-er button").forEach((b) => b.addEventListener("click", () => {
        const x = st[b.dataset.t][+b.dataset.n];
        x.on = !x.on;
        editors();
        calc();
      }));
    }
    function refreshRanks() {
      for (const side of ["a", "b"]) {
        const order = ranked(st[side]).map((x) => x.d);
        host.querySelectorAll(`#f-${side} .l12-er`).forEach((row, n) => {
          const r = order.indexOf(st[side][n].d);
          row.querySelector("b").textContent = r >= 0 ? r + 1 : "–";
        });
      }
    }
    function normalize(L) {
      const vals = L.map((x) => x.s);
      if (!vals.length) return {};
      const out = {};
      if (norm === "none") { L.forEach((x) => { out[x.d] = x.s; }); return out; }
      if (norm === "minmax") {
        const lo = Math.min(...vals), hi = Math.max(...vals);
        L.forEach((x) => { out[x.d] = hi - lo <= 1e-12 ? 1 : (x.s - lo) / (hi - lo); });
        return out;
      }
      const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
      const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length);
      L.forEach((x) => { out[x.d] = sd <= 1e-12 ? 0 : (x.s - mu) / sd; });
      return out;
    }
    function row(n, d, s, max, sub, digits) {
      const width = max > 0 ? Math.max(0, (s / max) * 100) : 0;
      return `<div class="l12-frow ${FREL.has(d) ? "rel" : ""}"><b>${n}</b><div><code>${esc(d)}</code><small>${sub}</small><div class="bar" style="width:${width}%"></div></div><i>${fx(s, digits)}</i></div>`;
    }
    function calc() {
      g("f-kv").textContent = k;
      g("f-wv").textContent = `${w.toFixed(2)} / ${(1 - w).toFixed(2)}`;
      g("f-nv").textContent = norm;
      const ra = ranked(st.a), rb = ranked(st.b);
      const R = rrf([ra.map((x) => x.d), rb.map((x) => x.d)], k);
      const rmax = R.length ? R[0].s : 1;
      g("f-rrf").innerHTML = R.map((x, n) => {
        const parts = [0, 1].map((li) => { const t = x.terms.find((y) => y.li === li); return t ? `1/(${k}+${t.r})` : "—"; });
        return row(n + 1, x.d, x.s, rmax, `${parts[0]} + ${parts[1]}`, k < 5 ? 3 : 4);
      }).join("") || `<div class="l12-note">אין מסמכים.</div>`;
      const na = normalize(ra), nb = normalize(rb);
      const best = {};
      ra.forEach((x, n) => { best[x.d] = Math.min(best[x.d] ?? 99, n + 1); });
      rb.forEach((x, n) => { best[x.d] = Math.min(best[x.d] ?? 99, n + 1); });
      const ids = Object.keys(best);
      const W = ids.map((d) => ({ d, a: na[d], b: nb[d], s: w * (na[d] ?? 0) + (1 - w) * (nb[d] ?? 0) }))
        .sort((x, y) => (Math.abs(y.s - x.s) > 1e-12 ? y.s - x.s : best[x.d] - best[y.d] || (x.d < y.d ? -1 : 1)));
      const wmax = W.length ? Math.max(...W.map((x) => x.s)) : 1;
      g("f-wf").innerHTML = W.map((x, n) => row(n + 1, x.d, x.s, wmax,
        `${w.toFixed(2)}×${x.a === undefined ? "0 (missing)" : fx(x.a, 2)} + ${(1 - w).toFixed(2)}×${x.b === undefined ? "0 (missing)" : fx(x.b, 2)}`, 3)).join("")
        || `<div class="l12-note">אין מסמכים.</div>`;
      const pr = R.findIndex((x) => FREL.has(x.d)) + 1, pw = W.findIndex((x) => FREL.has(x.d)) + 1;
      const top3r = R.slice(0, 3).map((x) => x.d).join(", "), top3w = W.slice(0, 3).map((x) => x.d).join(", ");
      g("f-diff").innerHTML = `<b>המסמך הנכון:</b> מקום ${pr || "–"} ב-RRF, מקום ${pw || "–"} ב-weighted. `
        + (top3r === top3w ? "שלושת הראשונים זהים בשתי השיטות." : `<b>שלושת הראשונים שונים:</b> RRF: <code>${esc(top3r)}</code>; weighted: <code>${esc(top3w)}</code>.`)
        + (norm === "none" ? " <span style=\"color:var(--bad)\">בלי נרמול, BM25 (בעשרות) קובע כמעט הכול, בלי קשר למשקל.</span>" : "");
    }
    host.querySelectorAll("#f-pre button").forEach((b) => b.addEventListener("click", () => load(b.dataset.p)));
    g("f-k").addEventListener("input", (e) => { k = +e.target.value; calc(); });
    g("f-w").addEventListener("input", (e) => { w = +e.target.value; calc(); });
    host.querySelectorAll("#f-norm button").forEach((b) => b.addEventListener("click", () => {
      norm = b.dataset.n;
      host.querySelectorAll("#f-norm button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      calc();
    }));
    load(pre);
  };

  /* ================================================================ l12ablate */
  // OFFLINE numbers from the lab (python labs/12-advanced-retrieval/ablation.py --dense fake
  // --llm replay --reranker fake, plus rewrite.py, versions_eval.py, rerank_eval.py), Nov 2026.
  // g: {group: [recall@5, MRR]}; stale: version_conflict questions (of 11) with a stale doc in the
  // top 5; p50: ms per question in the course sandbox (LLM calls replayed: NOT real latency);
  // cost: estimated USD per question at Claude Haiku 5.5 prices (replay).
  const D = {"ablation":[["1. BM25",{"g":{"ALL":[0.906,0.879],"multi_hop":[0.727,0.754],"version_conflict":[0.909,0.75],"hebrew":[0.864,0.919],"cross-lingual":[0.333,0.574]},"stale":9,"p50":0.4,"cost":0.0}],["2. dense alone (fake), for reference",{"g":{"ALL":[0.867,0.777],"multi_hop":[0.667,0.745],"version_conflict":[0.909,0.667],"hebrew":[0.955,0.894],"cross-lingual":[0.417,0.583]},"stale":9,"p50":0.3,"cost":0.0}],["3. BM25 + dense, interleaved (naive union)",{"g":{"ALL":[0.906,0.879],"multi_hop":[0.636,0.753],"version_conflict":[0.909,0.745],"hebrew":[0.955,0.939],"cross-lingual":[0.5,0.639]},"stale":9,"p50":1.0,"cost":0.0}],["4. BM25 + dense, RRF k=60",{"g":{"ALL":[0.903,0.831],"multi_hop":[0.758,0.798],"version_conflict":[0.909,0.682],"hebrew":[0.955,0.927],"cross-lingual":[0.5,0.575]},"stale":9,"p50":1.4,"cost":0.0}],["5. + query rewrite (multi, decompose, translate; LLM replay)",{"g":{"ALL":[0.896,0.82],"multi_hop":[0.758,0.786],"version_conflict":[0.909,0.773],"hebrew":[0.955,0.75],"cross-lingual":[0.417,0.482]},"stale":10,"p50":6.2,"cost":0.000153}],["6. + version filter (drop superseded when the newer is retrieved)",{"g":{"ALL":[0.896,0.863],"multi_hop":[0.758,0.786],"version_conflict":[0.909,0.955],"hebrew":[0.955,0.795],"cross-lingual":[0.417,0.482]},"stale":2,"p50":7.5,"cost":0.000153}],["7. + rerank (fake, top 30)",{"g":{"ALL":[0.915,0.857],"multi_hop":[0.742,0.716],"version_conflict":[0.955,0.78],"hebrew":[0.864,0.924],"cross-lingual":[0.25,0.549]},"stale":1,"p50":11.8,"cost":0.000153}]],"rewrite_bm25":[["none",{"g":{"ALL":[0.906,0.879],"multi_hop":[0.727,0.754],"version_conflict":[0.909,0.75],"hebrew":[0.864,0.919],"cross-lingual":[0.333,0.574]},"stale":9,"p50":0.4,"cost":0.0}],["multi",{"g":{"ALL":[0.918,0.881],"multi_hop":[0.803,0.758],"version_conflict":[0.909,0.773],"hebrew":[0.864,0.92],"cross-lingual":[0.25,0.465]},"stale":9,"p50":2.7,"cost":0.000153}],["decompose",{"g":{"ALL":[0.925,0.902],"multi_hop":[0.758,0.879],"version_conflict":[0.909,0.75],"hebrew":[0.955,0.939],"cross-lingual":[0.5,0.611]},"stale":9,"p50":1.9,"cost":0.000153}],["translate",{"g":{"ALL":[0.884,0.609],"multi_hop":[0.636,0.662],"version_conflict":[0.955,0.586],"hebrew":[0.727,0.413],"cross-lingual":[1.0,0.708]},"stale":9,"p50":2.2,"cost":0.000153}],["stepback",{"g":{"ALL":[0.915,0.875],"multi_hop":[0.652,0.74],"version_conflict":[0.955,0.795],"hebrew":[0.955,0.955],"cross-lingual":[0.417,0.583]},"stale":10,"p50":2.2,"cost":0.000153}],["hyde",{"g":{"ALL":[0.913,0.885],"multi_hop":[0.773,0.814],"version_conflict":[0.909,0.682],"hebrew":[0.864,0.92],"cross-lingual":[0.333,0.688]},"stale":9,"p50":2.2,"cost":0.000153}],["multi+decompose+translate",{"g":{"ALL":[0.94,0.857],"multi_hop":[0.803,0.821],"version_conflict":[0.955,0.758],"hebrew":[0.955,0.859],"cross-lingual":[0.583,0.492]},"stale":9,"p50":2.9,"cost":0.000153}]],"versions":[["none",{"g":{"ALL":[0.903,0.831],"multi_hop":[0.758,0.798],"version_conflict":[0.909,0.682],"hebrew":[0.955,0.927],"cross-lingual":[0.5,0.575]},"stale":9,"p50":1.0,"cost":0.0}],["retrieved",{"g":{"ALL":[0.903,0.892],"multi_hop":[0.758,0.806],"version_conflict":[0.909,0.955],"hebrew":[0.955,0.927],"cross-lingual":[0.5,0.589]},"stale":1,"p50":1.9,"cost":0.0}],["corpus",{"g":{"ALL":[0.903,0.892],"multi_hop":[0.758,0.806],"version_conflict":[0.909,0.955],"hebrew":[0.955,0.927],"cross-lingual":[0.5,0.589]},"stale":1,"p50":1.5,"cost":0.0}],["recent 0.1",{"g":{"ALL":[0.911,0.868],"multi_hop":[0.758,0.826],"version_conflict":[0.909,0.955],"hebrew":[0.955,0.932],"cross-lingual":[0.5,0.583]},"stale":9,"p50":1.5,"cost":0.0}],["recent 0.3",{"g":{"ALL":[0.889,0.643],"multi_hop":[0.712,0.682],"version_conflict":[0.955,0.655],"hebrew":[0.955,0.803],"cross-lingual":[0.417,0.45]},"stale":8,"p50":1.3,"cost":0.0}]],"rerank":[["none",{"g":{"ALL":[0.903,0.892],"multi_hop":[0.758,0.806],"version_conflict":[0.909,0.955],"hebrew":[0.955,0.927],"cross-lingual":[0.5,0.589]},"stale":1,"p50":1.4,"cost":0.0}],["fake@30",{"g":{"ALL":[0.915,0.867],"multi_hop":[0.742,0.72],"version_conflict":[0.955,0.78],"hebrew":[0.864,0.922],"cross-lingual":[0.25,0.552]},"stale":1,"p50":3.7,"cost":0.0}],["llm:replay@30",{"g":{"ALL":[0.853,0.851],"multi_hop":[0.667,0.708],"version_conflict":[0.955,0.811],"hebrew":[0.864,0.924],"cross-lingual":[0.333,0.472]},"stale":1,"p50":6.6,"cost":0.000826}]]};
  const TABS = {
    ablation: { name: "השרשרת (7 שלבים)", chain: true,
      label: ["BM25", "dense לבד (להשוואה)", "איחוד נאיבי לסירוגין", "RRF, k=60", "+ שכתוב", "+ סינון גרסאות", "+ rerank"],
      sub: ["אמיתי", "embedder מזויף", "BM25 + embedder מזויף", "BM25 + embedder מזויף", "שכתובים שנכתבו ביד", "אמיתי (מזהי מסמכים)", "reranker מזויף, 30 מועמדים"],
      fake: [false, true, true, true, true, false, true], ref: [false, true, false, false, false, false, false],
      lead: "כל שלב מוסיף דבר אחד לקודם. השינוי בסוגריים הוא לעומת השלב הקודם בשרשרת (dense לבד הוא להשוואה בלבד, ולא חלק מהשרשרת)." },
    rewrite_bm25: { name: "מצבי שכתוב", chain: false,
      label: ["בלי שכתוב", "multi-query", "decomposition", "תרגום", "step-back", "HyDE", "multi + decompose + translate"],
      sub: Array(7).fill("BM25 + שכתובים שנכתבו ביד"), fake: [false, true, true, true, true, true, true], ref: Array(7).fill(false),
      lead: "כל מצב לחוד מעל BM25, עם השאלה המקורית בתוספת השכתובים, מאוחדים ב-RRF. השינוי בסוגריים הוא לעומת \"בלי שכתוב\"." },
    versions: { name: "מדיניות גרסאות", chain: false,
      label: ["בלי סינון", "retrieved", "corpus", "recent, משקל 0.1", "recent, משקל 0.3"],
      sub: Array(5).fill("מעל RRF (BM25 + מזויף)"), fake: Array(5).fill(false), ref: Array(5).fill(false),
      lead: "חמש מדיניויות מעל אותו hybrid. הסינון עובד על מזהי מסמכים ועל המטא-דאטה, ולכן השינוי שהוא גורם לא תלוי ב-embedder המזויף. השינוי בסוגריים הוא לעומת \"בלי סינון\"." },
    rerank: { name: "rerankers", chain: false,
      label: ["בלי reranker", "fake (חפיפה לקסיקלית)", "LLM reranker במצב replay"],
      sub: ["hybrid + סינון גרסאות", "לא מודל", "שופט לקסיקלי, לא Claude"], fake: [false, true, true], ref: Array(3).fill(false),
      lead: "אין כאן cross-encoder: בסביבת הקורס אין גישה ל-Hugging Face. bge-reranker-v2-m3 ימדד אצלך. השינוי בסוגריים הוא לעומת \"בלי reranker\"." },
  };
  const GROUPS = [["ALL", "כל השאלות (69)"], ["multi_hop", "multi_hop (11)"], ["version_conflict", "version_conflict (11)"], ["hebrew", "hebrew (11)"], ["cross-lingual", "cross-lingual (6)"]];
  const METRICS = [["r5", "recall@5"], ["mrr", "MRR"], ["stale", "מיושנים ב-top 5"], ["p50", "זמן p50"], ["cost", "עלות לשאלה"]];

  window.AIDS["l12ablate"] = function (host) {
    style();
    host.innerHTML = `<div class="l12">
      <div class="guide"><p><b>מה רואים:</b> המספרים שנמדדו במעבדה, ב<b>מסלול הלא מקוון</b>, על 69 שאלות הזהב של Acme. כל שורה היא תצורה, והפס מראה את הערך של המדד שבחרת. מימין לפס מופיע המספר, ובצבע השינוי: בשרשרת לעומת השלב הקודם, ובשאר הלשוניות לעומת השורה הראשונה. <b>פס מפוספס</b> מסמן ששורה תלויה ברכיב מזויף, ולכן היא בודקת את הצנרת ולא את האיכות. הסינון לפי גרסה ו-BM25 אמיתיים לגמרי.</p>
      <p><b>על זמן ועלות:</b> זמן p50 נמדד בסביבת הקורס. קריאות ה-LLM שם נענו מקובץ, ולכן הזמן של שלב השכתוב <b>לא כולל</b> קריאה אמיתית ל-Claude. העלות היא הערכה לפי המחירים של Haiku 5.5. בגלל שהשאלות מעטות, בקבוצה של 6 שאלות כל שאלה שווה 0.17, ובקבוצה של 11 כל שאלה שווה 0.09.</p></div>
      <div class="seg" id="a-tab"></div>
      <div class="seg" id="a-grp"></div>
      <div class="seg" id="a-met"></div>
      <div class="l12-note" id="a-lead"></div>
      <div class="l12-ab" id="a-rows"></div>
      <div class="l12-legend"><span>רכיבים אמיתיים</span><span class="f">תלוי ברכיב מזויף</span></div>
      <div class="l12-diff" id="a-take"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let tab = "ablation", grp = "ALL", met = "r5";
    const seg = (el, items, cur, key) => { el.innerHTML = items.map(([v, l]) => `<button data-${key}="${v}" aria-pressed="${v === cur}">${l}</button>`).join(""); };
    seg(g("a-tab"), Object.entries(TABS).map(([k, t]) => [k, t.name]), tab, "t");
    seg(g("a-grp"), GROUPS, grp, "g");
    seg(g("a-met"), METRICS, met, "m");
    const val = (r) => met === "r5" ? r.g[grp][0] : met === "mrr" ? r.g[grp][1] : met === "stale" ? r.stale : met === "p50" ? r.p50 : r.cost;
    const fmt = (v) => met === "stale" ? `${v}/11` : met === "p50" ? `${v.toFixed(1)}ms` : met === "cost" ? `$${v.toFixed(5)}` : v.toFixed(3);
    const better = (d) => (met === "r5" || met === "mrr") ? d > 0 : d < 0;
    function take() {
      const T = {
        ablation: "<b>לקרוא בכנות:</b> המספרים של RRF מול האיחוד הנאיבי, ושל סינון הגרסאות, הם התרומות שאפשר לסמוך עליהן כבר עכשיו. שלב השכתוב ושלב ה-rerank נמדדו עם תחליפים, ולכן הם אומרים רק שהצנרת עובדת. בהרצה החיה, עם e5, Haiku ו-bge-reranker-v2-m3, תקבל את המספרים האמיתיים.",
        rewrite_bm25: "<b>מה רואים כאן:</b> התרגום לבד מעלה את cross-lingual ל-1.000, ומוריד את ה-MRR הכללי ל-0.609. כל שכתוב עוזר לקבוצה אחת ומוסיף רעש לאחרות. זו הסיבה למדוד לפי סוג שאלה.",
        versions: "<b>מה רואים כאן:</b> recent במשקל 0.1 מגיע לאותו MRR של version_conflict, אבל המסמכים המיושנים נשארים ב-top 5 (מדד \"מיושנים\"), ורק יורדים כמה מקומות. במשקל 0.3 המחיר על שאר השאלות כבר גבוה.",
        rerank: "<b>מה רואים כאן:</b> ה-reranker המזויף לקסיקלי, ולכן הוא מוריד את cross-lingual. LLM במצב replay משתמש באותה צנרת (פרומפט, סכמה ועלות), אבל השופט שלו לא Claude. שתי השורות בודקות את הקוד, לא את הרעיון.",
      };
      g("a-take").innerHTML = T[tab];
    }
    function draw() {
      const t = TABS[tab], rows = D[tab];
      g("a-lead").textContent = t.lead + (met === "stale" ? " במדד הזה, פחות זה טוב יותר. הוא לא תלוי בקבוצה שבחרת." : met === "p50" || met === "cost" ? " במדד הזה, פחות זה טוב יותר. הוא לא תלוי בקבוצה שבחרת." : "");
      const vals = rows.map(([, r]) => val(r));
      const max = Math.max(...vals, met === "r5" || met === "mrr" ? 1 : 1e-9);
      let prevIdx = 0;
      g("a-rows").innerHTML = rows.map(([, r], n) => {
        const v = vals[n];
        let base = null;
        if (t.chain) { if (n > 0 && !t.ref[n]) base = vals[prevIdx]; if (!t.ref[n]) prevIdx = n; }
        else if (n > 0) base = vals[0];
        let delta = "";
        if (base !== null) {
          const d = v - base;
          const eq = Math.abs(d) < (met === "cost" ? 1e-7 : met === "p50" ? 0.05 : 0.0005);
          delta = eq ? `<i>=</i>` : `<i class="${better(d) ? "up" : "down"}">${d > 0 ? "+" : "−"}${met === "stale" ? Math.abs(d) : met === "p50" ? Math.abs(d).toFixed(1) : met === "cost" ? Math.abs(d).toFixed(5) : Math.abs(d).toFixed(3)}</i>`;
        } else delta = "<i></i>";
        const cls = ["l12-abr", t.fake[n] ? "fake" : "", t.ref[n] ? "ref" : ""].join(" ");
        return `<div class="${cls}"><div class="nm">${esc(t.label[n])}<small>${esc(t.sub[n])}</small></div><div><div class="bar" style="width:${max > 0 ? (v / max) * 100 : 0}%"></div></div><b>${fmt(v)}</b>${delta}</div>`;
      }).join("");
      take();
    }
    host.querySelectorAll("#a-tab button").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.t; host.querySelectorAll("#a-tab button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); }));
    host.querySelectorAll("#a-grp button").forEach((b) => b.addEventListener("click", () => { grp = b.dataset.g; host.querySelectorAll("#a-grp button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); }));
    host.querySelectorAll("#a-met button").forEach((b) => b.addEventListener("click", () => { met = b.dataset.m; host.querySelectorAll("#a-met button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); }));
    draw();
  };
})();
