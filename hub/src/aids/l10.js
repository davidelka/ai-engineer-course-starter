// Lesson 10 aids: text-to-points animation (l10space), cosine/dot/L2 playground (l10cos),
// recall@k / MRR calculator on real BM25 rankings (l10metrics), ANN explorer (l10ann).
// Self-contained; uses only CSS variables from index.html so dark mode works.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const CSS = `
  .l10 { display: grid; gap: 12px; direction: rtl; }
  .l10 svg { direction: ltr; width: 100%; height: auto; display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; touch-action: none; }
  .l10 .l10-bar { display: flex; flex-wrap: wrap; gap: 4px; }
  .l10 .l10-bar button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 3px 9px; font-size: .78rem; }
  .l10 .l10-bar button.on { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .l10 .l10-bar button.done { color: var(--muted); }
  .l10 .l10-cap { font-size: .9rem; line-height: 1.75; }
  .l10 .l10-cap b.t { display: block; font-size: .98rem; margin-bottom: 2px; }
  .l10 .l10-warn { font-size: .86rem; line-height: 1.7; color: var(--bad); border-inline-start: 3px solid var(--bad); padding-inline-start: 8px; }
  .l10 .l10-grid { display: grid; gap: 10px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .l10 .l10-grid.two { grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); } }
  .l10 .l10-legend { display: grid; gap: 3px; font-size: .78rem; line-height: 1.45; }
  .l10 .l10-legend div { display: grid; grid-template-columns: 2.6rem minmax(0, 1fr); gap: 6px; align-items: baseline; }
  .l10 .l10-legend b { font-family: var(--mono); font-size: .74rem; direction: ltr; text-align: left; }
  .l10 .l10-legend span { unicode-bidi: plaintext; text-align: start; overflow-wrap: anywhere; }
  .l10 .l10-vals { display: grid; gap: 4px; font-size: .8rem; direction: ltr; }
  .l10 .l10-vals .r { display: grid; grid-template-columns: 2.8rem minmax(0, 1fr) 3.4rem; gap: 6px; align-items: center; }
  .l10 .l10-vals .r b { font-family: var(--mono); }
  .l10 .l10-vals .r i { font-style: normal; font-family: var(--mono); text-align: right; }
  .l10 .l10-vals .bar { height: 8px; border-radius: 4px; background: var(--accent); }
  .l10 .l10-vals .r.top .bar { background: var(--good); }
  .l10 .l10-vals .r.neg .bar { background: var(--bad); }
  .l10 .l10-tbl { display: grid; gap: 4px; font-size: .8rem; direction: ltr; }
  .l10 .l10-tbl .h, .l10 .l10-tbl .r { display: grid; grid-template-columns: 2.2rem repeat(3, minmax(0, 1fr)); gap: 4px; align-items: center; }
  .l10 .l10-tbl .h { color: var(--muted); font-size: .74rem; }
  .l10 .l10-tbl .r span { font-family: var(--mono); background: var(--code-bg); border-radius: 5px; padding: 2px 5px; }
  .l10 .l10-tbl .r span.win { background: var(--good-soft); font-weight: 700; }
  .l10 .l10-list { display: grid; gap: 4px; }
  .l10 .l10-row { display: grid; grid-template-columns: 1.6rem minmax(0, 1fr) auto; gap: 6px; align-items: center; direction: ltr; font-size: .8rem; border: 1px solid var(--line); border-radius: 8px; padding: 4px 6px; background: var(--surface); }
  .l10 .l10-row.rel { background: var(--good-soft); border-color: var(--good); }
  .l10 .l10-row.dup { opacity: .55; }
  .l10 .l10-row.out { border-style: dashed; }
  .l10 .l10-row code { font-family: var(--mono); font-size: .76rem; overflow-wrap: anywhere; }
  .l10 .l10-row small { color: var(--muted); display: block; font-size: .7rem; }
  .l10 .l10-row .mv { display: flex; gap: 2px; }
  .l10 .l10-row .mv button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 6px; padding: 1px 7px; font-size: .78rem; line-height: 1.3; }
  .l10 .l10-cut { border-top: 2px dashed var(--signal); margin: 2px 0; position: relative; }
  .l10 .l10-cut span { position: absolute; top: -.75em; left: 8px; background: var(--surface); color: var(--signal); font-size: .7rem; padding: 0 4px; font-family: var(--mono); }
  .l10 .l10-m { display: grid; gap: 8px; }
  .l10 .l10-m .card2 { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 2px; }
  .l10 .l10-m .card2 b.v { font-family: var(--mono); font-size: 1.15rem; direction: ltr; text-align: right; }
  .l10 .l10-m .card2 small { color: var(--muted); line-height: 1.5; font-size: .78rem; }
  .l10 .l10-q { font-size: .88rem; line-height: 1.6; unicode-bidi: plaintext; text-align: start; }
  .l10 .l10-ctl { display: grid; gap: 10px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .l10 .l10-ctl { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .l10 input[type=range] { width: 100%; }
  .l10 .l10-meas { display: grid; gap: 5px; font-size: .78rem; direction: ltr; }
  .l10 .l10-meas .r { display: grid; grid-template-columns: minmax(0, 9.5rem) minmax(0, 1fr) 4.3rem 4.2rem; gap: 6px; align-items: center; }
  .l10 .l10-meas .r span { font-family: var(--mono); overflow-wrap: anywhere; }
  .l10 .l10-meas .r i { font-style: normal; font-family: var(--mono); text-align: right; color: var(--muted); }
  .l10 .l10-meas .bar { height: 9px; border-radius: 4px; background: var(--accent); }
  .l10 .l10-meas .r.ok .bar { background: var(--good); }
  .l10 .l10-meas .h { color: var(--muted); }
  .l10 .l10-src { font-size: .74rem; color: var(--muted); line-height: 1.55; }
  .l10 text { font-family: var(--mono); }
  @media (max-width: 480px) { .l10 .l10-meas .r { grid-template-columns: minmax(0, 7rem) minmax(0, 1fr) 3.6rem 3.6rem; } }
  `;
  function style() {
    if (document.getElementById("l10-style")) return;
    const s = document.createElement("style");
    s.id = "l10-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fx = (v, d = 3) => (Math.round(v * 10 ** d) / 10 ** d).toFixed(d);
  function rng(seed) { // mulberry32: deterministic layouts on every load
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function gauss(r) { let u = 0, v = 0; while (u === 0) u = r(); while (v === 0) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

  /* ================================================================ l10space */
  // Hand-placed 2-D positions: ILLUSTRATIVE, not model output (the guide says so).
  const PTS = [
    { k: "EN", a: 40, r: 110, dx: 8, dy: 12, s: "Up to 5 unused vacation days may be carried over to the next calendar year." },
    { k: "HE", a: 44, r: 85, dx: 8, dy: 14, s: "עד 5 ימי חופשה שלא נוצלו אפשר להעביר לשנה הקלנדרית הבאה." },
    { k: "PARA", a: 63, r: 120, dx: -8, dy: -4, s: "Leftover days off can be moved into January instead of being lost." },
    { k: "NEG", a: 34, r: 150, dx: 7, dy: 4, s: "Unused vacation days may not be carried over to the next calendar year." },
    { k: "EN2", a: 148, r: 120, dx: -8, dy: -4, s: "The Tel Aviv parking garage closes at 22:00 every night." },
    { k: "HE2", a: 156, r: 88, dx: -6, dy: 14, s: "החניון של משרד תל אביב נסגר בכל לילה בשעה 22:00." },
    { k: "CODE", a: 232, r: 112, dx: -8, dy: 4, s: "Deploys are blocked during Quiet Hours; see #deploys." },
    { k: "ID", a: 302, r: 120, dx: 8, dy: 4, s: "Primary region il-central-1, failover to eu-central-1." },
  ];
  const QY = { k: "Q", a: 47, r: 62, s: "How many vacation days can I carry over?" };
  const O = { x: 200, y: 150 };
  const rad = (d) => (d * Math.PI) / 180;
  const pos = (p, r) => ({ x: O.x + (r ?? p.r) * Math.cos(rad(p.a)), y: O.y - (r ?? p.r) * Math.sin(rad(p.a)) });
  const cos2 = (p, q) => Math.cos(rad(p.a - q.a));

  const SPACE = [
    { name: "טקסט לנקודה", title: "1. כל משפט הופך לנקודה במרחב",
      cap: "המודל קורא כל משפט ומחזיר וקטור. כאן הווקטור מצויר כחץ מהראשית. משפטים עם אותה משמעות נוחתים באותו אזור: ארבעת המשפטים על העברת ימי חופשה (באנגלית, בעברית, בפרפרזה ובשלילה) מצביעים כמעט לאותו כיוון, ושני המשפטים על החניון לכיוון אחר לגמרי.",
      warn: "המפה הזו מצוירת ביד בשני ממדים. מודל אמיתי משתמש ב-384 עד 3,072 ממדים, ואף ממד לבדו לא ניתן לפירוש." },
    { name: "שאלה", title: "2. השאלה מקבלת חץ משלה, וזווית קובעת דמיון",
      cap: "השאלה \"How many vacation days can I carry over?\" עוברת דרך אותו מודל. מימין מוצג ה-cos של הזווית בין חץ השאלה לכל משפט, מחושב מהזוויות שעל המסך. חץ באותו כיוון מקבל ערך קרוב ל-1, חץ מאונך מקבל 0, וחץ הפוך מקבל 1-.",
      warn: "האורך של החץ לא משנה את ה-cosine. EN ארוך מ-HE, ושניהם מקבלים כמעט אותו ציון." },
    { name: "בין שפות", title: "3. תרגומים נוחתים זה ליד זה",
      cap: "הקווים המקווקווים מחברים כל משפט לתרגום שלו. ל-BM25 אין אף מילה משותפת בין \"vacation days\" לבין \"ימי חופשה\", ולכן הציון שלו הוא אפס. מודל רב-לשוני אומן על זוגות של טקסט ותרגום, ושם אותם כמעט באותו כיוון. בזכות זה שאלה באנגלית מוצאת מסמך בעברית.",
      warn: "זה לא תרגום. המודל לא יודע מה התשובה. הוא רק יודע ששני הטקסטים מופיעים באותם הקשרים." },
    { name: "top-k", title: "4. שלושת השכנים הקרובים, וגם מלכודת",
      cap: "חיפוש וקטורי מחזיר את k החצים עם הזווית הקטנה ביותר לשאלה. כאן k=3. שים לב מי נכנס: גם השלילה, \"may not be carried over\", נמצאת ממש ליד המשפט המקורי. האימון כמעט אף פעם לא דרש מהמודל להפריד בין \"may\" ל-\"may not\".",
      warn: "embeddings לא מבחינים טוב בשלילה, במספרים ובמזהים. את זה משלימים BM25 ו-reranker (שיעור 12)." },
    { name: "נרמול", title: "5. נרמול: כל החצים באורך 1",
      cap: "כל וקטור מחולק באורכו, וכל הנקודות עוברות למעגל היחידה. הכיוונים לא זזו, ולכן הדירוג לפי cosine נשאר זהה. עכשיו dot product שווה בדיוק ל-cosine, ומרחק L2 בריבוע שווה ל-2 פחות פעמיים ה-cosine. לכן מנרמלים פעם אחת בזמן הכתיבה, ובזמן השאילתה מחשבים רק מכפלה.",
      warn: "בלי נרמול, ו-dot product, וקטור ארוך מנצח גם כשהכיוון שלו פחות מתאים." },
  ];

  window.AIDS["l10space"] = function (host) {
    style();
    host.innerHTML = `<div class="l10">
      <div class="guide"><p><b>מה רואים:</b> מפה דו-ממדית שמצוירת ביד (להמחשה, לא פלט של מודל). כל נקודה היא משפט מהעולם של Acme, וכל משפט הוא חץ מהראשית, הנקודה השחורה. <b>הכיוון קובע את הדמיון</b>, לא האורך. בכל שלב מופיעים מתחת למפה ההסבר, ובאדום המגבלה שצריך לזכור. ליד המפה מופיעים הערכים שמחושבים מהזוויות שעל המסך.</p></div>
      <div class="l10-bar" id="sp-bar"></div>
      <div class="l10-grid two">
        <svg viewBox="0 0 400 300" id="sp-svg" role="img" aria-label="מפת embeddings דו-ממדית להמחשה"></svg>
        <div style="display:grid;gap:10px;align-content:start">
          <div class="l10-vals" id="sp-vals"></div>
          <div class="l10-legend" id="sp-leg"></div>
        </div>
      </div>
      <div class="l10-cap" id="sp-cap"></div>
      <div class="l10-warn" id="sp-warn"></div>
      <div class="row"><button class="btn small primary" id="sp-play">השהה</button><button class="btn small" id="sp-prev" aria-label="שלב קודם">→</button><button class="btn small" id="sp-next" aria-label="שלב הבא">←</button><span class="spacer"></span><span class="counter" id="sp-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const svg = g("sp-svg");
    let i = 0, timer = null, anim = null, playing = !RM();
    g("sp-bar").innerHTML = SPACE.map((s, k) => `<button data-k="${k}">${k + 1}. ${s.name}</button>`).join("");
    g("sp-leg").innerHTML = [...PTS, QY].map((p) => `<div><b>${p.k}</b><span>${esc(p.s)}</span></div>`).join("");
    const ranked = PTS.map((p) => ({ p, c: cos2(p, QY) })).sort((a, b) => b.c - a.c);
    const top3 = new Set(ranked.slice(0, 3).map((x) => x.p.k));

    function frame(t) { // t in [0,1]: stage-1 fly-in progress; stage 5: normalization progress
      const st = i;
      const norm = st === 4 ? t : 0;
      const fly = st === 0 ? t : 1;
      let s = `<circle cx="${O.x}" cy="${O.y}" r="100" fill="none" stroke="var(--line)" stroke-dasharray="3 4"/>`;
      s += `<line x1="10" y1="${O.y}" x2="390" y2="${O.y}" stroke="var(--line)"/><line x1="${O.x}" y1="8" x2="${O.x}" y2="292" stroke="var(--line)"/>`;
      if (st === 4) s += `<text x="${O.x - 98}" y="${O.y - 84}" font-size="11" fill="var(--muted)">|v| = 1</text>`;
      const at = (p) => { const r = (p.r * (1 - norm) + 100 * norm) * fly; return pos(p, r); };
      if (st === 2) {
        for (const [a, b] of [["EN", "HE"], ["EN2", "HE2"]]) {
          const pa = at(PTS.find((p) => p.k === a)), pb = at(PTS.find((p) => p.k === b));
          s += `<line x1="${pa.x}" y1="${pa.y}" x2="${pb.x}" y2="${pb.y}" stroke="var(--good)" stroke-width="2" stroke-dasharray="4 3"/>`;
        }
      }
      if (st >= 1) {
        const qp = at(QY);
        s += `<line x1="${O.x}" y1="${O.y}" x2="${qp.x}" y2="${qp.y}" stroke="var(--signal)" stroke-width="2.5"/>`;
      }
      if (st === 3) {
        const far = ranked[2].p;
        const ang = Math.abs(far.a - QY.a) + 2;
        const r0 = 150;
        const a1 = rad(QY.a - ang), a2 = rad(QY.a + ang);
        s += `<path d="M${O.x},${O.y} L${O.x + r0 * Math.cos(a1)},${O.y - r0 * Math.sin(a1)} A${r0},${r0} 0 0 0 ${O.x + r0 * Math.cos(a2)},${O.y - r0 * Math.sin(a2)} Z" fill="var(--good-soft)" stroke="var(--good)" stroke-width="1" opacity=".75"/>`;
      }
      PTS.forEach((p, k) => {
        const tt = st === 0 ? Math.max(0, Math.min(1, t * 1.6 - k * 0.08)) : 1;
        const r = (p.r * (1 - norm) + 100 * norm) * tt;
        const q = pos(p, r);
        const hot = st === 3 && top3.has(p.k);
        const col = hot ? (p.k === "NEG" ? "var(--bad)" : "var(--good)") : "var(--accent)";
        s += `<line x1="${O.x}" y1="${O.y}" x2="${q.x}" y2="${q.y}" stroke="${col}" stroke-width="${hot ? 2 : 1}" opacity="${0.35 + 0.65 * tt}"/>`;
        s += `<circle cx="${q.x}" cy="${q.y}" r="${hot ? 6 : 4.5}" fill="${col}" opacity="${tt}"/>`;
        s += `<text x="${q.x + p.dx}" y="${q.y + p.dy}" font-size="12" font-weight="600" fill="${col}" text-anchor="${p.dx >= 0 ? "start" : "end"}" opacity="${tt}">${p.k}</text>`;
      });
      if (st >= 1) {
        const qp = at(QY);
        s += `<circle cx="${qp.x}" cy="${qp.y}" r="6" fill="var(--signal)"/><text x="${qp.x - 9}" y="${qp.y + 4}" font-size="12" font-weight="700" fill="var(--signal)" text-anchor="end">Q</text>`;
      }
      s += `<circle cx="${O.x}" cy="${O.y}" r="3.5" fill="var(--ink)"/>`;
      svg.innerHTML = s;
    }
    function values() {
      const st = i;
      if (st === 0) {
        g("sp-vals").innerHTML = `<div class="l10-src">אורך החץ (להמחשה) של כל משפט:</div>` + PTS.map((p) =>
          `<div class="r"><b>${p.k}</b><div class="bar" style="width:${(p.r / 150) * 100}%"></div><i>${fx(p.r / 100, 2)}</i></div>`).join("");
        return;
      }
      if (st === 2) {
        const pair = (a, b) => { const pa = PTS.find((p) => p.k === a), pb = PTS.find((p) => p.k === b); return fx(cos2(pa, pb)); };
        g("sp-vals").innerHTML = `<div class="l10-src">זוגות של משפט ותרגום:</div>
          <div class="r"><b>EN-HE</b><div class="bar top" style="width:100%"></div><i>${pair("EN", "HE")}</i></div>
          <div class="r"><b>EN2-HE2</b><div class="bar top" style="width:100%"></div><i>${pair("EN2", "HE2")}</i></div>
          <div class="l10-src" style="direction:rtl">מילים משותפות ל-BM25 בכל זוג: <b>0</b>, חוץ מהמספרים 5 ו-22:00.</div>`;
        return;
      }
      g("sp-vals").innerHTML = `<div class="l10-src">cos(Q, משפט) לפי הזוויות שעל המסך, מהגבוה לנמוך${st === 4 ? " (אחרי נרמול: זהה, וגם dot זהה)" : ""}:</div>` +
        ranked.map(({ p, c }, k) => {
          const cls = st >= 3 && k < 3 ? (p.k === "NEG" ? "r neg" : "r top") : "r";
          return `<div class="${cls}"><b>${p.k}</b><div class="bar" style="width:${Math.max(0, c) * 100}%"></div><i>${fx(c)}</i></div>`;
        }).join("");
    }
    function draw() {
      const s = SPACE[i];
      g("sp-cap").innerHTML = `<b class="t">${s.title}</b>${s.cap}`;
      g("sp-warn").innerHTML = "<b>לזכור: </b>" + s.warn;
      g("sp-c").textContent = `${i + 1}/${SPACE.length}`;
      host.querySelectorAll("#sp-bar button").forEach((b, k) => { b.classList.toggle("on", k === i); b.classList.toggle("done", k < i); });
      g("sp-play").textContent = playing ? "השהה" : "הפעל";
      values();
      cancelAnimationFrame(anim);
      if ((i === 0 || i === 4) && !RM()) {
        const t0 = performance.now(), dur = i === 0 ? 1800 : 1400;
        const step = (now) => { const t = Math.min(1, (now - t0) / dur); frame(t); if (t < 1) anim = requestAnimationFrame(step); };
        anim = requestAnimationFrame(step);
      } else frame(1);
    }
    function sched() { clearTimeout(timer); if (playing) timer = setTimeout(() => { i = (i + 1) % SPACE.length; draw(); sched(); }, 9000); }
    function go(d) { i = (i + d + SPACE.length) % SPACE.length; draw(); sched(); }
    g("sp-next").addEventListener("click", () => { playing = false; go(1); });
    g("sp-prev").addEventListener("click", () => { playing = false; go(-1); });
    g("sp-play").addEventListener("click", () => { playing = !playing; draw(); sched(); });
    g("sp-bar").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; playing = false; i = +b.dataset.k; draw(); sched(); });
    draw(); sched();
    return () => { clearTimeout(timer); cancelAnimationFrame(anim); };
  };

  /* ================================================================ l10cos */
  window.AIDS["l10cos"] = function (host) {
    style();
    host.innerHTML = `<div class="l10">
      <div class="guide"><p><b>מה רואים:</b> מישור עם שאלה <b>q</b> (כתום) ושלושה מועמדים <b>A</b>, <b>B</b> ו-<b>C</b> (כחול). גרור את קצה של כל חץ, או גע בו בטלפון. הטבלה שליד המישור מציגה לכל מועמד את שלוש המטריקות. הציון הירוק בכל עמודה הוא המנצח לפי אותה מטריקה. ב-L2 מוצג המרחק עצמו, ולכן שם הקטן מנצח.</p>
      <p><b>מה לנסות:</b> הפעל את <b>הנרמול</b>. כל החצים מתקצרים לאורך 1 (העיגול המקווקו), והמקוריים נשארים חיוורים ברקע. בדוק שאחרי הנרמול שלוש העמודות בוחרות את אותו מנצח, ושהזהות שבתחתית מתקיימת.</p></div>
      <div class="seg" id="cs-seg"><button data-n="0" aria-pressed="true">בלי נרמול</button><button data-n="1" aria-pressed="false">עם נרמול לאורך 1</button><button data-n="r">איפוס</button></div>
      <div class="l10-grid two">
        <svg viewBox="0 0 300 300" id="cs-svg" role="img" aria-label="מישור עם וקטורים שאפשר לגרור"></svg>
        <div style="display:grid;gap:10px;align-content:start">
          <div class="l10-tbl" id="cs-tbl"></div>
          <div class="l10-src" id="cs-id"></div>
          <div class="l10-src" id="cs-note"></div>
        </div>
      </div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const svg = g("cs-svg");
    const U = 38, C = 150;
    const init = () => ({ q: [1.4, 0.3], A: [1.0, 0.6], B: [2.6, 2.4], C: [0.9, -0.9] });
    let V = init(), normOn = false, drag = null;
    const len = (v) => Math.hypot(v[0], v[1]);
    const nrm = (v) => { const l = len(v); return l > 1e-9 ? [v[0] / l, v[1] / l] : [0, 0]; };
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1];
    const toPx = (v) => [C + v[0] * U, C - v[1] * U];
    function arrow(v, col, w, op, label) {
      const [x, y] = toPx(v);
      let s = `<line x1="${C}" y1="${C}" x2="${x}" y2="${y}" stroke="${col}" stroke-width="${w}" opacity="${op}"/>`;
      if (label) s += `<circle cx="${x}" cy="${y}" r="9" fill="${col}" opacity="${op * 0.25}" data-h="${label}" style="cursor:grab"/><circle cx="${x}" cy="${y}" r="4.5" fill="${col}" opacity="${op}" data-h="${label}" style="cursor:grab"/><text x="${x + 8}" y="${y - 7}" font-size="12" fill="${col}">${label}</text>`;
      return s;
    }
    function draw() {
      let s = "";
      for (let k = -3; k <= 3; k++) s += `<line x1="${C + k * U}" y1="10" x2="${C + k * U}" y2="290" stroke="var(--line)" opacity=".5"/><line x1="10" y1="${C + k * U}" x2="290" y2="${C + k * U}" stroke="var(--line)" opacity=".5"/>`;
      s += `<circle cx="${C}" cy="${C}" r="${U}" fill="none" stroke="var(--muted)" stroke-dasharray="3 4"/>`;
      const show = (v) => (normOn ? nrm(v) : v);
      if (normOn) for (const k of ["q", "A", "B", "C"]) s += arrow(V[k], k === "q" ? "var(--signal)" : "var(--accent)", 1, 0.25, null);
      for (const k of ["A", "B", "C"]) s += arrow(show(V[k]), "var(--accent)", 2, 1, normOn ? null : k);
      s += arrow(show(V.q), "var(--signal)", 2.5, 1, normOn ? null : "q");
      if (normOn) for (const k of ["q", "A", "B", "C"]) { const [x, y] = toPx(nrm(V[k])); s += `<text x="${x + 6}" y="${y - 6}" font-size="12" fill="${k === "q" ? "var(--signal)" : "var(--accent)"}">${k}</text>`; }
      s += `<circle cx="${C}" cy="${C}" r="3" fill="var(--ink)"/>`;
      svg.innerHTML = s;
      const q = show(V.q);
      const rows = ["A", "B", "C"].map((k) => { const v = show(V[k]); return { k, d: dot(q, v), c: len(q) && len(v) ? dot(q, v) / (len(q) * len(v)) : 0, l: Math.hypot(q[0] - v[0], q[1] - v[1]) }; });
      const best = (f, min) => rows.reduce((b, r) => ((min ? f(r) < f(b) : f(r) > f(b)) ? r : b)).k;
      const bd = best((r) => r.d), bc = best((r) => r.c), bl = best((r) => r.l, true);
      g("cs-tbl").innerHTML = `<div class="h"><span></span><span>dot</span><span>cosine</span><span>L2 distance</span></div>` +
        rows.map((r) => `<div class="r"><b>${r.k}</b><span class="${r.k === bd ? "win" : ""}">${fx(r.d, 2)}</span><span class="${r.k === bc ? "win" : ""}">${fx(r.c)}</span><span class="${r.k === bl ? "win" : ""}">${fx(r.l, 2)}</span></div>`).join("") +
        `<div class="l10-src">אורכים: <span dir="ltr">|q| = ${fx(len(q), 2)} · |A| = ${fx(len(show(V.A)), 2)} · |B| = ${fx(len(show(V.B)), 2)} · |C| = ${fx(len(show(V.C)), 2)}</span></div>`;
      const a = rows[0];
      g("cs-id").innerHTML = normOn
        ? `<b>הזהות על A:</b> <span dir="ltr">L2² = ${fx(a.l * a.l)}</span> וגם <span dir="ltr">2 − 2·cos = ${fx(2 - 2 * a.c)}</span>. הם שווים, ולכן שלוש העמודות מדרגות אותו דבר.`
        : `<b>בלי נרמול:</b> <span dir="ltr">L2² = ${fx(a.l * a.l)}</span> לעומת <span dir="ltr">2 − 2·cos = ${fx(2 - 2 * a.c)}</span>. הם לא שווים, כי האורכים אינם 1.`;
      const agree = bd === bc && bc === bl;
      g("cs-note").innerHTML = agree ? "שלוש המטריקות מסכימות כרגע על המנצח." : `<b style="color:var(--bad)">המטריקות לא מסכימות:</b> dot בוחר ${bd}, cosine בוחר ${bc}, ו-L2 בוחר ${bl}.`;
    }
    function svgPt(e) { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; const m = svg.getScreenCTM(); return m ? p.matrixTransform(m.inverse()) : { x: 0, y: 0 }; }
    svg.addEventListener("pointerdown", (e) => { const h = e.target.getAttribute && e.target.getAttribute("data-h"); if (!h) return; drag = h; svg.setPointerCapture(e.pointerId); e.preventDefault(); });
    svg.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const p = svgPt(e);
      const v = [Math.max(-3.6, Math.min(3.6, (p.x - C) / U)), Math.max(-3.6, Math.min(3.6, (C - p.y) / U))];
      if (Math.hypot(v[0], v[1]) < 0.15) return;
      V[drag] = v; draw();
    });
    const end = () => { drag = null; };
    svg.addEventListener("pointerup", end); svg.addEventListener("pointercancel", end);
    g("cs-seg").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.n === "r") { V = init(); normOn = false; }
      else normOn = b.dataset.n === "1";
      host.querySelectorAll("#cs-seg button[data-n='0'],#cs-seg button[data-n='1']").forEach((x) => x.setAttribute("aria-pressed", String((x.dataset.n === "1") === normOn)));
      draw();
    });
    draw();
    return () => {};
  };

  /* ================================================================ l10metrics */
  // Real BM25 top-10 (chunk level) from ragkit on the Acme corpus, chunker heading:400:40:150.
  const MQ = [
    { id: "q001", type: "version_conflict", q: "How many unused vacation days can I carry over to next year, and when do they expire?", rel: ["hr-vacation-2026"],
      ranked: ["hr-vacation-2026#1", "hr-vacation-2024#1", "hr-vacation-2026#2", "hr-sick-leave#0", "hr-vacation-2024#2", "co-allhands-2026-01#2", "hr-vacation-2026#0", "hr-vacation-2024#0", "it-saas-access-v2-2#3", "it-laptop-policy#3"] },
    { id: "q039", type: "single_hop · cross-lingual", q: "When is the deadline to finish the new-hire security training?", rel: ["hr-onboarding-he"],
      ranked: ["it-laptop-faq#0", "it-laptop-faq#1", "fin-procurement-2026#1", "it-saas-access-v2-2#3", "it-helpdesk#1", "fin-procurement-2025#1", "co-allhands-2026-07#1", "fin-travel-2026#2", "it-saas-access-v2-2#1", "hr-performance-reviews#3"] },
    { id: "q040", type: "multi_hop", q: "Which team owns the service whose configuration change caused the August 2026 flow-api outage, who leads that team, and when does its on-call rotation hand over?", rel: ["eng-pm-2026-08-api", "eng-service-catalog"],
      ranked: ["eng-pm-2026-08-api#0", "eng-pm-2026-08-api#3", "eng-pm-2026-08-api#2", "eng-pm-2026-08-api#4", "eng-deploy-process#2", "eng-pm-2026-08-api#1", "eng-architecture#10", "eng-deploy-process#4", "eng-service-catalog#4", "eng-leads-sync-2026-05#3"] },
    { id: "q047", type: "multi_hop · cross-lingual", q: "An engineer joined two months ago. Can they be the primary on-call?", rel: ["eng-service-catalog", "hr-onboarding-he"],
      ranked: ["hr-performance-reviews#3", "co-glossary#3", "eng-service-catalog#4", "eng-runbook-flow-api#0", "eng-pm-2026-03-scheduler#3", "sec-incident-response#2", "sup-escalation#0", "eng-runbook-billing#0", "hr-performance-reviews#2", "eng-runbook-flow-engine#0"] },
    { id: "q068", type: "hebrew · cross-lingual", q: "כמה ימי חופשה מקבל עובד במשרה מלאה בשנה הראשונה?", rel: ["hr-vacation-2026", "hr-vacation-2026-he"],
      ranked: ["hr-vacation-2026-he#0", "hr-reserve-duty-he#0", "hr-onboarding-he#2", "hr-health-insurance-he#1", "hr-vacation-2026-he#1", "co-haifa-office-he#1", "hr-health-insurance-he#0", "hr-onboarding-he#1", "hr-onboarding-he#0", "hr-health-insurance-he#2"] },
    { id: "q069", type: "hebrew · cross-lingual", q: "מי הבעלים של השירות flow-api ומתי מתחלפת הכוננות שלו?", rel: ["eng-service-catalog"],
      ranked: ["hr-reserve-duty-he#1", "eng-oncall-scheduler-he#0", "hr-reserve-duty-he#0", "eng-oncall-scheduler-he#3", "hr-onboarding-he#2", "eng-oncall-scheduler-he#2", "hr-reserve-duty-he#2", "sup-meeting-2026-09-he#1", "sup-meeting-2026-09-he#0", "eng-runbook-flow-api#0"] },
  ];
  const docOf = (cid) => cid.split("#")[0];
  const dedupe = (xs) => [...new Set(xs)];
  function recall(docs, rel, k) { const top = docs.slice(0, k); return rel.filter((r) => top.includes(r)).length / rel.length; }
  function rr(docs, rel, k) { const i = docs.slice(0, k).findIndex((d) => rel.includes(d)); return i < 0 ? 0 : 1 / (i + 1); }

  window.AIDS["l10metrics"] = function (host) {
    style();
    host.innerHTML = `<div class="l10">
      <div class="guide"><p><b>מה רואים:</b> שאלת זהב אמיתית של Acme, ו-10 ה-chunks ש-BM25 של ragkit באמת החזיר עבורה, לפי הסדר. שורה <b>ירוקה</b> שייכת למסמך רלוונטי (מתוך <code>source_ids</code> של השאלה). שורה <b>חיוורת</b> היא chunk של מסמך שכבר הופיע קודם: אחרי הסרת כפילויות הוא לא נספר. הקו הכתום מסמן את <b>k</b>.</p>
      <p><b>איך לקרוא את המדדים:</b> שלושת הכרטיסים מחושבים מרשימת <b>המסמכים</b>, אחרי הסרת כפילויות. אפשר להזיז שורות עם החצים ולשנות את k, ולראות איך כל מדד מגיב. ה-MRR בתחתית הוא ממוצע ה-RR של כל שש השאלות, כולל השינויים שעשית.</p></div>
      <div class="seg" id="mt-seg"></div>
      <div class="l10-q" id="mt-q"></div>
      <div class="knob"><div class="knob-head"><span>k (כמה מסמכים נכנסים לחשבון)</span><b id="mt-kv">5</b></div><input type="range" id="mt-k" min="1" max="10" value="5"></div>
      <div class="l10-grid two">
        <div class="l10-list" id="mt-list"></div>
        <div class="l10-m" id="mt-m"></div>
      </div>
      <div class="row"><button class="btn small" id="mt-reset">החזר את הדירוג המקורי של BM25</button></div>
      <div class="l10-src">מקור: <code>data/acme/corpus/golden/qa.jsonl</code>, ודירוג BM25 של ragkit עם ה-chunker <code>heading:400:40:150</code>, אותו chunker כמו במעבדה.</div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let qi = 2, k = 5;
    const order = MQ.map((m) => m.ranked.slice());
    g("mt-seg").innerHTML = MQ.map((m, j) => `<button data-j="${j}" aria-pressed="${j === qi}">${m.id}</button>`).join("");
    function draw() {
      const m = MQ[qi], list = order[qi];
      g("mt-q").innerHTML = `<b>${m.id}</b> <span style="color:var(--muted)">[${m.type}]</span> ${esc(m.q)}<br><span class="l10-src">מסמכים רלוונטיים: ${m.rel.map((r) => `<code>${r}</code>`).join(", ")}</span>`;
      const seen = new Map();
      let rows = "", docRank = 0;
      list.forEach((cid, j) => {
        const d = docOf(cid);
        const dup = seen.has(d);
        if (!dup) { docRank += 1; seen.set(d, docRank); }
        const rel = m.rel.includes(d);
        const outK = !dup && seen.get(d) > k;
        rows += `<div class="l10-row ${rel ? "rel" : ""} ${dup ? "dup" : ""} ${outK ? "out" : ""}"><b>${j + 1}</b><div><code>${cid}</code><small>${dup ? `duplicate of document #${seen.get(d)}: not counted` : `document #${seen.get(d)}${rel ? " · relevant" : ""}`}</small></div><span class="mv"><button data-u="${j}" aria-label="up">▲</button><button data-d="${j}" aria-label="down">▼</button></span></div>`;
        const nextNew = list.slice(j + 1).some((c) => !seen.has(docOf(c)));
        if (!dup && seen.get(d) === k && nextNew) rows += `<div class="l10-cut"><span>k = ${k}</span></div>`;
      });
      g("mt-list").innerHTML = rows;
      const docs = dedupe(list.map(docOf));
      const rec = recall(docs, m.rel, k), hit = rec > 0 ? 1 : 0, r = rr(docs, m.rel, 10);
      const found = m.rel.filter((x) => docs.slice(0, k).includes(x)).length;
      const first = docs.findIndex((d) => m.rel.includes(d));
      const mrr = MQ.reduce((s, mm, j) => s + rr(dedupe(order[j].map(docOf)), mm.rel, 10), 0) / MQ.length;
      g("mt-m").innerHTML = `
        <div class="card2"><span>recall@${k}</span><b class="v">${fx(rec)}</b><small>${found} מתוך ${m.rel.length} המסמכים הרלוונטיים נמצאים ב-${k} המסמכים הראשונים. ${m.rel.length > 1 ? "בשאלת multi-hop צריך את כולם." : ""}</small></div>
        <div class="card2"><span>hit@${k}</span><b class="v">${hit}</b><small>1 אם לפחות מסמך רלוונטי אחד נמצא ב-top-${k}.${m.rel.length > 1 && hit && rec < 1 ? " כאן hit מסתיר שחסר מקור." : ""}</small></div>
        <div class="card2"><span>RR (עד מקום 10)</span><b class="v">${fx(r)}</b><small>${first < 0 ? "אף מסמך רלוונטי לא נמצא בעשרת הראשונים, ולכן 0." : `המסמך הרלוונטי הראשון נמצא במקום ${first + 1} ברשימת המסמכים, ולכן 1/${first + 1}.`}</small></div>
        <div class="card2"><span>MRR על כל שש השאלות</span><b class="v">${fx(mrr)}</b><small>הממוצע של RR בכל השאלות. שאלה אחת עם 0 (q039) מורידה את הממוצע ב-1/6.</small></div>`;
    }
    g("mt-seg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; qi = +b.dataset.j; host.querySelectorAll("#mt-seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); });
    g("mt-k").addEventListener("input", (e) => { k = +e.target.value; g("mt-kv").textContent = k; draw(); });
    g("mt-list").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const L = order[qi];
      const j = b.dataset.u != null ? +b.dataset.u : +b.dataset.d;
      const t = b.dataset.u != null ? j - 1 : j + 1;
      if (t < 0 || t >= L.length) return;
      [L[j], L[t]] = [L[t], L[j]]; draw();
    });
    g("mt-reset").addEventListener("click", () => { order[qi] = MQ[qi].ranked.slice(); draw(); });
    draw();
    return () => {};
  };

  /* ================================================================ l10ann */
  // FAISS numbers measured in the course sandbox (faiss-cpu 1.15.1, 2 threads, 100k synthetic
  // clustered vectors, 384 dims, 500 queries, k=10). Shown as measured, not as a promise.
  const MEAS = [
    { n: "Flat (exact)", r: 1.000, ms: 2.81, mb: 154 },
    { n: "HNSW32 ef=16", r: 0.841, ms: 0.146, mb: 181 },
    { n: "HNSW32 ef=32", r: 0.952, ms: 0.252, mb: 181 },
    { n: "HNSW32 ef=64", r: 0.986, ms: 0.428, mb: 181 },
    { n: "HNSW32 ef=128", r: 0.994, ms: 0.948, mb: 181 },
    { n: "IVF1264 nprobe=1", r: 0.928, ms: 0.043, mb: 156 },
    { n: "IVF1264 nprobe=16", r: 0.954, ms: 0.161, mb: 156 },
    { n: "IVF1264 nprobe=64", r: 0.971, ms: 0.493, mb: 156 },
    { n: "IVF,PQ48 nprobe=64", r: 0.558, ms: 0.150, mb: 8 },
    { n: "IVF,PQ48 + re-rank", r: 0.964, ms: 0.191, mb: 162 },
  ];

  window.AIDS["l10ann"] = function (host) {
    style();
    host.innerHTML = `<div class="l10">
      <div class="guide"><p><b>מה רואים:</b> 300 נקודות במישור, שמייצגות וקטורים, והשאילתה היא הצלב הכתום. <b>לחץ על המפה</b> כדי להזיז את השאילתה. המטרה היא למצוא את 10 השכנים הקרובים. נקודה עם <b>טבעת ירוקה</b> היא שכן אמיתי שנמצא, ונקודה עם <b>טבעת אדומה</b> היא שכן אמיתי שהאינדקס פספס. מתחת למפה מוצג כמה מרחקים חושבו (חיפוש מדויק מחשב 300) ומה ה-recall.</p>
      <p><b>IVF:</b> הרקע הצבעוני הוא 12 תאים של k-means, והריבועים הם המרכזים. רק התאים הבהירים נבדקים (nprobe). <b>HNSW:</b> הקווים הדקים הם הגרף בשכבה התחתונה. הקו העבה הוא המסלול של החיפוש, מנקודת הכניסה ועד השכונה של השאילתה. הנקודות הכחולות הבהירות הן הצמתים שהחיפוש בדק.</p></div>
      <div class="seg" id="an-mode"><button data-m="ivf" aria-pressed="true">IVF (תאים)</button><button data-m="hnsw" aria-pressed="false">HNSW (גרף)</button></div>
      <div class="l10-ctl" id="an-ctl"></div>
      <svg viewBox="0 0 360 250" id="an-svg" role="img" aria-label="מפת נקודות לחיפוש שכנים קרובים"></svg>
      <div class="stats" id="an-stats"></div>
      <div class="l10-cap" id="an-cap"></div>
      <h4 style="margin:6px 0 0">מספרים שנמדדו ב-FAISS: 100 אלף וקטורים, 384 ממדים</h4>
      <div class="l10-src">נמדד בסביבת הפיתוח של הקורס (faiss-cpu 1.15.1, שתי ליבות, נתונים סינתטיים מקובצים, 500 שאילתות, k=10), עם <code>labs/10-embeddings/faiss_bench.py</code>. זו מדידה אחת על מכונה משותפת. על המחשב שלך הזמנים יהיו אחרים, ולכן תרגיל 7 מודד אותם אצלך. הפס הוא recall@10 מול חיפוש מדויק. ירוק פירושו 0.95 ומעלה.</div>
      <div class="l10-meas" id="an-meas"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const svg = g("an-svg");
    const R = rng(10);
    const W = 360, H = 250, K = 10;
    const centers = Array.from({ length: 9 }, () => [30 + R() * 300, 25 + R() * 200]);
    const P = Array.from({ length: 300 }, () => { const c = centers[Math.floor(R() * centers.length)]; return [Math.max(4, Math.min(W - 4, c[0] + gauss(R) * 26)), Math.max(4, Math.min(H - 4, c[1] + gauss(R) * 20))]; });
    const d2 = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;
    // --- IVF: k-means with 12 cells
    const NL = 12;
    let cent = P.filter((_, j) => j % 25 === 0).slice(0, NL).map((p) => p.slice());
    let assign = new Array(P.length).fill(0);
    for (let it = 0; it < 12; it++) {
      assign = P.map((p) => { let b = 0; for (let c = 1; c < NL; c++) if (d2(p, cent[c]) < d2(p, cent[b])) b = c; return b; });
      cent = cent.map((c, ci) => { const m = P.filter((_, j) => assign[j] === ci); return m.length ? [m.reduce((s, p) => s + p[0], 0) / m.length, m.reduce((s, p) => s + p[1], 0) / m.length] : c; });
    }
    const FILLS = ["var(--accent-soft)", "var(--signal-soft)", "var(--good-soft)", "var(--bad-soft)", "var(--code-bg)"];
    const cellOf = (x, y) => { let b = 0; for (let c = 1; c < NL; c++) if (d2([x, y], cent[c]) < d2([x, y], cent[b])) b = c; return b; };
    const GRID = []; const GS = 10;
    for (let y = 0; y < H; y += GS) for (let x = 0; x < W; x += GS) GRID.push([x, y, cellOf(x + GS / 2, y + GS / 2)]);
    // --- HNSW: 3 layers, M=4 on layer 0 plus the nearest neighbors at insertion time
    const lvl = P.map((_, j) => (j < 3 ? 2 : (R() < 0.1 ? 1 : 0)));
    function knn(set, j, m) { return set.filter((x) => x !== j).sort((a, b) => d2(P[j], P[a]) - d2(P[j], P[b])).slice(0, m); }
    const ids = P.map((_, j) => j);
    const L = [0, 1, 2].map((l) => { const set = ids.filter((j) => lvl[j] >= l); const adj = new Map(); set.forEach((j) => adj.set(j, new Set(knn(set, j, l === 0 ? 4 : 3)))); adj.forEach((nb, j) => nb.forEach((x) => adj.get(x).add(j))); return adj; });
    const ENTRY = 0;

    let mode = "ivf", nprobe = 1, ef = 10, kk = 10, Q = [200, 120], anim = null;
    function ctl() {
      g("an-ctl").innerHTML = mode === "ivf"
        ? `<div class="knob"><div class="knob-head"><span>nprobe: כמה תאים לבדוק</span><b id="an-v">${nprobe}</b></div><input type="range" id="an-r" min="1" max="${NL}" value="${nprobe}"><small>מתוך ${NL} תאים. ב-FAISS: <code>index.nprobe</code></small></div>`
        : `<div class="knob"><div class="knob-head"><span>efSearch: רוחב החיפוש</span><b id="an-v">${ef}</b></div><input type="range" id="an-r" min="1" max="40" value="${ef}"><small>כמו ב-FAISS, בפועל משתמשים ב-max(efSearch, k)</small></div>
           <div class="knob"><div class="knob-head"><span>k: כמה שכנים מחפשים</span><b id="an-kv">${kk}</b></div><input type="range" id="an-k" min="1" max="10" value="${kk}"><small>k=1 ו-efSearch=1 הם חיפוש חמדן טהור</small></div>`;
      g("an-r").addEventListener("input", (e) => { if (mode === "ivf") nprobe = +e.target.value; else ef = +e.target.value; g("an-v").textContent = e.target.value; run(); });
      const kEl = g("an-k"); if (kEl) kEl.addEventListener("input", (e) => { kk = +e.target.value; g("an-kv").textContent = kk; run(); });
    }
    function exact(k) { return ids.slice().sort((a, b) => d2(Q, P[a]) - d2(Q, P[b])).slice(0, k); }
    function searchIVF() {
      const order = cent.map((c, ci) => ci).sort((a, b) => d2(Q, cent[a]) - d2(Q, cent[b])).slice(0, nprobe);
      const pset = new Set(order);
      const cand = ids.filter((j) => pset.has(assign[j]));
      const found = cand.sort((a, b) => d2(Q, P[a]) - d2(Q, P[b])).slice(0, K);
      return { found, probed: pset, dists: NL + cand.length, k: K };
    }
    function searchHNSW() {
      let dists = 0; const dist = (j) => { dists++; return d2(Q, P[j]); };
      let cur = ENTRY, cd = dist(cur); const path = [cur];
      for (let l = 2; l >= 1; l--) {
        let moved = true;
        while (moved) { moved = false; for (const nb of L[l].get(cur) || []) { const dd = dist(nb); if (dd < cd) { cd = dd; cur = nb; moved = true; path.push(cur); } } }
      }
      const efE = Math.max(ef, kk);
      const visited = new Set([cur]);
      let cands = [[cd, cur]], best = [[cd, cur]];
      while (cands.length) {
        cands.sort((a, b) => a[0] - b[0]);
        const [dc, c] = cands.shift();
        best.sort((a, b) => a[0] - b[0]);
        if (dc > best[best.length - 1][0] && best.length >= efE) break;
        for (const nb of L[0].get(c)) {
          if (visited.has(nb)) continue; visited.add(nb);
          const dd = dist(nb);
          if (best.length < efE || dd < best[best.length - 1][0]) {
            cands.push([dd, nb]); best.push([dd, nb]); best.sort((a, b) => a[0] - b[0]); if (best.length > efE) best.pop();
          }
        }
        if (path[path.length - 1] !== c && best[0][1] === c) path.push(c);
      }
      best.sort((a, b) => a[0] - b[0]);
      const found = best.slice(0, kk).map((x) => x[1]);
      // greedy path on layer 0 toward the best result, for drawing
      let p0 = cur; const route = path.slice();
      for (let s = 0; s < 40; s++) { let nxt = p0, nd = d2(Q, P[p0]); for (const nb of L[0].get(p0)) if (visited.has(nb) && d2(Q, P[nb]) < nd) { nd = d2(Q, P[nb]); nxt = nb; } if (nxt === p0) break; p0 = nxt; route.push(p0); }
      return { found, visited, route, dists, k: kk };
    }
    function render(res, steps) {
      const truth = exact(res.k), fset = new Set(res.found), tset = new Set(truth);
      let s = "";
      if (mode === "ivf") {
        s += GRID.map(([x, y, c]) => `<rect x="${x}" y="${y}" width="${GS}" height="${GS}" fill="${FILLS[c % FILLS.length]}" opacity="${res.probed.has(c) ? 0.95 : 0.28}"/>`).join("");
        s += cent.map((c, ci) => `<rect x="${c[0] - 4}" y="${c[1] - 4}" width="8" height="8" fill="${res.probed.has(ci) ? "var(--ink)" : "var(--muted)"}" opacity=".85"/>`).join("");
        s += P.map((p, j) => `<circle cx="${p[0]}" cy="${p[1]}" r="2.2" fill="${res.probed.has(assign[j]) ? "var(--accent)" : "var(--muted)"}" opacity="${res.probed.has(assign[j]) ? 0.9 : 0.45}"/>`).join("");
      } else {
        const E = []; L[0].forEach((nb, j) => nb.forEach((x) => { if (x > j) E.push([j, x]); }));
        s += E.map(([a, b]) => `<line x1="${P[a][0]}" y1="${P[a][1]}" x2="${P[b][0]}" y2="${P[b][1]}" stroke="var(--line)" stroke-width=".7"/>`).join("");
        s += P.map((p, j) => `<circle cx="${p[0]}" cy="${p[1]}" r="${lvl[j] ? 3.4 : 2.2}" fill="${res.visited.has(j) ? "var(--accent)" : "var(--muted)"}" opacity="${res.visited.has(j) ? 0.95 : 0.4}"/>`).join("");
        const r = res.route.slice(0, steps == null ? res.route.length : steps);
        if (r.length > 1) s += `<polyline points="${r.map((j) => P[j].join(",")).join(" ")}" fill="none" stroke="var(--signal)" stroke-width="2.4" stroke-linejoin="round"/>`;
        s += `<circle cx="${P[ENTRY][0]}" cy="${P[ENTRY][1]}" r="5" fill="none" stroke="var(--ink)" stroke-width="1.6"/><text x="${P[ENTRY][0] + 7}" y="${P[ENTRY][1] - 6}" font-size="9" fill="var(--ink)">entry</text>`;
      }
      if (steps == null || mode === "ivf") {
        truth.forEach((j) => { s += `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="5" fill="none" stroke="${fset.has(j) ? "var(--good)" : "var(--bad)"}" stroke-width="2"/>`; });
      }
      s += `<path d="M${Q[0] - 7},${Q[1]} L${Q[0] + 7},${Q[1]} M${Q[0]},${Q[1] - 7} L${Q[0]},${Q[1] + 7}" stroke="var(--signal)" stroke-width="3"/>`;
      svg.innerHTML = s;
      const hit = res.found.filter((j) => tset.has(j)).length;
      g("an-stats").innerHTML = `<span>מרחקים שחושבו: <b>${res.dists}</b> (מדויק: 300)</span><span>recall@${res.k}: <b>${hit}/${res.k}</b></span>` + (mode === "ivf" ? `<span>נקודות בתאים שנבדקו: <b>${res.dists - NL}</b></span>` : `<span>צמתים שנבדקו: <b>${res.visited.size}</b></span>`);
      g("an-cap").innerHTML = mode === "ivf"
        ? (hit < res.k ? `<b>פספוס:</b> ${res.k - hit} מהשכנים האמיתיים (טבעת אדומה) נמצאים בתא שלא נבדק. זה קורה בעיקר כשהשאילתה ליד גבול בין תאים. הגדלת nprobe תמצא אותם, במחיר של יותר מרחקים.` : `כל השכנים האמיתיים נמצאו, וחושבו ${res.dists} מרחקים במקום 300. נסה להזיז את השאילתה לגבול בין שני תאים.`)
        : (hit < res.k ? `<b>פספוס:</b> החיפוש עצר כשאף שכן לא היה קרוב יותר מהמועמדים שכבר החזיק. עם efSearch קטן הוא מחזיק מעט מועמדים, ועלול להיתקע בשכונה הלא נכונה (מינימום מקומי).` : `המסלול (הקו הכתום) קופץ בשכבות העליונות, שבהן הנקודות הגדולות, ואז מתקדם בשכבה התחתונה. נבדקו ${res.visited.size} צמתים מתוך 300.`);
    }
    function run() {
      cancelAnimationFrame(anim);
      const res = mode === "ivf" ? searchIVF() : searchHNSW();
      if (mode === "hnsw" && !RM() && res.route.length > 1) {
        let st = 1; let last = 0;
        const step = (t) => { if (t - last > 90) { last = t; st++; render(res, st); } if (st < res.route.length) anim = requestAnimationFrame(step); else render(res, null); };
        render(res, 1); anim = requestAnimationFrame(step);
      } else render(res, null);
    }
    function svgPt(e) { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; const m = svg.getScreenCTM(); return m ? p.matrixTransform(m.inverse()) : { x: 0, y: 0 }; }
    svg.addEventListener("click", (e) => { const p = svgPt(e); Q = [Math.max(2, Math.min(W - 2, p.x)), Math.max(2, Math.min(H - 2, p.y))]; run(); });
    g("an-mode").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; mode = b.dataset.m; host.querySelectorAll("#an-mode button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); ctl(); run(); });
    const maxMs = Math.max(...MEAS.map((m) => m.ms));
    g("an-meas").innerHTML = `<div class="r h"><span>index</span><span>recall@10</span><i>ms/query</i><i>MB</i></div>` + MEAS.map((m) =>
      `<div class="r ${m.r >= 0.95 ? "ok" : ""}"><span>${m.n}</span><div><div class="bar" style="width:${m.r * 100}%"></div><small style="font-family:var(--mono)">${fx(m.r)}</small></div><i>${m.ms < 0.1 ? m.ms.toFixed(3) : m.ms.toFixed(2)}</i><i>${m.mb}</i></div>`).join("") +
      `<div class="l10-src" style="direction:rtl">שים לב: Flat איטי פי ${Math.round(maxMs / 0.428)} מ-HNSW עם ef=64, שמגיע ל-recall של 0.986. PQ לבד דוחס פי 19 ומאבד הרבה recall, ודירוג מחדש מדויק מחזיר אותו, אבל צריך שוב את הווקטורים המלאים.</div>`;
    ctl(); run();
    return () => cancelAnimationFrame(anim);
  };
})();
