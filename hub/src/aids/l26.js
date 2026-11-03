// Lesson 26 aids: concurrency gate animation, load simulator (Little's law), stream cancellation, token bucket.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l26-style";
  function style() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l26 .lane { display: grid; gap: 4px; }
.l26 .lane-h { display: flex; justify-content: space-between; gap: 8px; font-size: .82rem; color: var(--muted); direction: rtl; }
.l26 .cells { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; min-height: 34px; align-items: center; }
.l26 .cell { position: relative; width: 38px; height: 30px; border-radius: 6px; border: 1px dashed var(--line); background: var(--code-bg); overflow: hidden; font-family: var(--mono); font-size: .68rem; display: grid; place-items: center; color: var(--muted); }
.l26 .cell > i { position: absolute; inset-block: 0; left: 0; opacity: .35; }
.l26 .cell > span { position: relative; }
.l26 .cell.run { border: 1px solid var(--good); color: var(--ink); }
.l26 .cell.run > i { background: var(--good); }
.l26 .cell.wait { border: 1px solid var(--signal); color: var(--ink); }
.l26 .cell.wait > i { background: var(--signal); }
.l26 .chip-r { font-family: var(--mono); font-size: .68rem; padding: 2px 6px; border-radius: 6px; background: var(--bad-soft); color: var(--bad); border: 1px solid var(--bad); }
.l26 .chip-r.to { border-style: dashed; }
.l26 .chip-ok { font-family: var(--mono); font-size: .68rem; padding: 2px 6px; border-radius: 6px; background: var(--good-soft); color: var(--good); }
.l26 .knobs { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.l26 .say { min-height: 3.2em; font-size: .9rem; border-inline-start: 3px solid var(--signal); padding: 4px 10px; }
.l26 svg { width: 100%; max-width: 560px; margin-inline: auto; height: auto; display: block; direction: ltr; }
.l26 svg text { fill: var(--muted); font-family: var(--mono); font-size: 10px; }
.l26 .three { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; direction: rtl; }
.l26 .actor { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 4px; min-width: 0; }
.l26 .actor h4 { margin: 0; font-size: .9rem; display: flex; justify-content: space-between; gap: 8px; }
.l26 .actor .flow { font-family: var(--mono); font-size: .74rem; direction: ltr; text-align: left; min-height: 2.6em; overflow-wrap: anywhere; color: var(--ink); }
.l26 .actor.dead { opacity: .55; }
.l26 .badge { font-size: .72rem; padding: 1px 8px; border-radius: 999px; background: var(--line); color: var(--muted); font-weight: 500; white-space: nowrap; }
.l26 .badge.on { background: var(--good-soft); color: var(--good); }
.l26 .badge.busy { background: var(--signal-soft); color: var(--signal); }
.l26 .badge.badx { background: var(--bad-soft); color: var(--bad); }
.l26 .bucket { display: grid; grid-template-columns: 70px minmax(0, 1fr); gap: 12px; align-items: end; }
.l26 .tank { height: 140px; border: 2px solid var(--line); border-top: 0; border-radius: 0 0 10px 10px; position: relative; overflow: hidden; background: var(--code-bg); }
.l26 .tank > i { position: absolute; inset-inline: 0; bottom: 0; background: var(--accent); opacity: .55; transition: height .1s linear; }
.l26 .tank > b { position: absolute; inset-inline: 0; top: 4px; text-align: center; font-family: var(--mono); font-size: .8rem; }
.l26 .strip { position: relative; height: 54px; background: var(--code-bg); border-radius: 8px; overflow: hidden; direction: ltr; }
.l26 .strip i { position: absolute; width: 4px; border-radius: 2px; }
.l26 .strip i.ok { background: var(--good); top: 6px; height: 18px; }
.l26 .strip i.no { background: var(--bad); bottom: 6px; height: 18px; }
@media (min-width: 640px) { .l26 .three { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
`;
    document.head.appendChild(s);
  }
  const pct = (arr, p) => { if (!arr.length) return 0; const a = [...arr].sort((x, y) => x - y); return a[Math.min(a.length - 1, Math.floor(p * a.length))]; };
  function rng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }
  const expo = (r, rate) => -Math.log(1 - r()) / rate;
  const svc = (r, S) => S * (0.6 + 0.8 * r()); // service time: uniform 0.6S .. 1.4S
  const knob = (id, label, min, max, step, val, help) =>
    `<div class="knob"><div class="knob-head"><label for="${id}">${label}</label><b id="${id}v"></b></div><input id="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${val}"><small>${help}</small></div>`;

  /* ================= animation: concurrency gate + queue ================= */
  window.AIDS["l26gate"] = function (host) {
    style();
    const PRESETS = {
      calm: { lam: 2, S: 2, c: 6, K: 6, T: 3, l: "רגוע" },
      busy: { lam: 4.5, S: 2, c: 6, K: 6, T: 3, l: "עומס" },
      noq: { lam: 4.5, S: 2, c: 6, K: 0, T: 3, l: "בלי תור" },
      huge: { lam: 4.5, S: 2, c: 6, K: 200, T: 600, l: "תור ענק" },
    };
    host.innerHTML = `<div class="sim l26">
      <p style="margin:0">בקשות מגיעות משמאל בקצב אקראי. <b>ירוק</b> = רצה עכשיו במקום בשער, <b>כתום</b> = מחכה בתור, <b>אדום</b> = נדחתה עם 429 (מקווקו: נדחתה אחרי שחיכתה עד ה-queue timeout).</p>
      <div class="seg" id="g-pre">${Object.entries(PRESETS).map(([k, p]) => `<button data-k="${k}" aria-pressed="${k === "calm"}">${p.l}</button>`).join("")}</div>
      <div class="stage" style="min-height:0">
        <div class="lane"><div class="lane-h"><span>תור (כיסאות)</span><span id="g-qh"></span></div><div class="cells" id="g-q"></div></div>
        <div class="lane"><div class="lane-h"><span>שער: מקומות (קריאות למודל שרצות)</span><span id="g-sh"></span></div><div class="cells" id="g-s"></div></div>
        <div class="lane"><div class="lane-h"><span>נדחו לאחרונה (429)</span><span></span></div><div class="cells" id="g-r"></div></div>
      </div>
      <div class="stats" id="g-st"></div>
      <div class="say" id="g-say">ההדמיה מתחילה ריקה. הבקשה הראשונה תגיע בעוד רגע.</div>
      <div class="row"><button class="btn small primary" id="g-play">השהה</button><button class="btn small" id="g-reset">התחל מחדש</button><span class="spacer"></span>
        <div class="seg" id="g-spd"><button data-v="0.5" aria-pressed="false">x0.5</button><button data-v="1" aria-pressed="true">x1</button><button data-v="2" aria-pressed="false">x2</button></div></div>
      <details><summary>מחוונים (שחק בעצמך)</summary><div class="knobs" style="margin-top:8px">
        ${knob("g-lam", "בקשות בשנייה", 0.5, 8, 0.5, 2, "קצב ההגעה הממוצע")}
        ${knob("g-S", "זמן קריאה (שניות)", 0.5, 5, 0.5, 2, "כמה זמן כל קריאה למודל תופסת מקום")}
        ${knob("g-c", "מקומות בשער", 1, 12, 1, 6, "קיבולת = מקומות / זמן קריאה")}
        ${knob("g-K", "כיסאות בתור", 0, 30, 1, 6, "0 = כל עודף נדחה מיד")}
        ${knob("g-T", "queue timeout (שניות)", 0.5, 10, 0.5, 3, "המתנה מקסימלית בתור")}
      </div></details></div>`;
    const g = (id) => host.querySelector("#" + id);
    let P = { ...PRESETS.calm }, st, timer = null, last = 0, speed = 1;
    let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    const r = rng(7);
    function reset() {
      st = { t: 0, next: 0.6, id: 0, slots: Array(P.c).fill(null), q: [], rej: [], served: 0, full: 0, to: 0, lat: [] };
      g("g-say").textContent = "ההדמיה מתחילה ריקה. הבקשה הראשונה תגיע בעוד רגע.";
      syncKnobs(); draw();
    }
    function syncKnobs() {
      for (const [k, id] of [["lam", "g-lam"], ["S", "g-S"], ["c", "g-c"], ["K", "g-K"], ["T", "g-T"]]) {
        const v = P[k] > +g(id).max ? +g(id).max : P[k];
        g(id).value = v; g(id + "v").textContent = P[k];
      }
    }
    function say(s) { g("g-say").innerHTML = s; }
    function step(dt) {
      st.t += dt;
      const t = st.t;
      st.slots.forEach((s, i) => {
        if (s && s.start + s.dur <= t) {
          st.served++; st.lat.push(t - s.arr); if (st.lat.length > 300) st.lat.shift();
          st.slots[i] = null;
          if (st.q.length) { const n = st.q.shift(); st.slots[i] = { ...n, start: t, dur: svc(r, P.S) }; say(`#${s.id} הסתיימה. #${n.id}, הראשונה בתור, נכנסה למקום שהתפנה אחרי ${(t - n.arr).toFixed(1)} שניות המתנה.`); }
        }
      });
      while (st.q.length && st.q[0].arr + P.T <= t) {
        const n = st.q.shift(); st.to++; st.rej.unshift({ id: n.id, to: true });
        say(`#${n.id} חיכתה ${P.T} שניות בתור ולא קיבלה מקום: <b>429 אחרי המתנה</b>. הלקוח בזבז ${P.T} שניות וקיבל לא.`);
      }
      while (st.next <= t) {
        const id = ++st.id, arr = st.next;
        st.next += expo(r, P.lam);
        const free = st.slots.indexOf(null);
        if (free >= 0 && !st.q.length) { st.slots[free] = { id, arr, start: t, dur: svc(r, P.S) }; say(`#${id} הגיעה, יש מקום פנוי ואף אחד לא מחכה: <b>נכנסה מיד</b>.`); }
        else if (st.q.length < P.K) { st.q.push({ id, arr }); say(`#${id} הגיעה, כל ${P.c} המקומות תפוסים: <b>מחכה בתור</b> (מקום ${st.q.length} מתוך ${P.K}).`); }
        else { st.full++; st.rej.unshift({ id, to: false }); say(`#${id} הגיעה, ${P.K ? "גם התור מלא" : "אין תור בכלל"}: <b>נדחתה מיד</b> עם 429 ו-Retry-After. הסירוב לקח מילישנייה ולא עלה כלום.`); }
      }
      st.rej = st.rej.slice(0, 14);
    }
    function draw() {
      const t = st.t;
      g("g-s").innerHTML = st.slots.map((s) => s
        ? `<div class="cell run" title="#${s.id}"><i style="width:${Math.min(100, ((t - s.start) / s.dur) * 100)}%"></i><span>#${s.id}</span></div>`
        : `<div class="cell"><span>·</span></div>`).join("");
      const shown = Math.min(P.K, 24);
      let qh = "";
      for (let i = 0; i < shown; i++) {
        const n = st.q[i];
        qh += n ? `<div class="cell wait"><i style="width:${Math.min(100, ((t - n.arr) / P.T) * 100)}%"></i><span>#${n.id}</span></div>` : `<div class="cell"><span>·</span></div>`;
      }
      if (P.K > 24) qh += `<span class="badge">${st.q.length > 24 ? "+" + (st.q.length - 24) + " מחכות" : "עוד " + (P.K - 24) + " כיסאות"}</span>`;
      if (!P.K) qh = `<span class="badge">אין תור</span>`;
      g("g-q").innerHTML = qh;
      g("g-r").innerHTML = st.rej.map((x) => `<span class="chip-r${x.to ? " to" : ""}">#${x.id}</span>`).join("") || `<span class="badge">אין עדיין</span>`;
      g("g-sh").textContent = `${st.slots.filter(Boolean).length}/${P.c}`;
      g("g-qh").textContent = P.K ? `${st.q.length}/${P.K}` : "";
      const cap = P.c / P.S;
      g("g-st").innerHTML = `<span>זמן <b>${t.toFixed(0)}s</b></span><span>רצות <b>${st.slots.filter(Boolean).length}</b></span><span>בתור <b>${st.q.length}</b></span>
        <span>הצליחו <b>${st.served}</b></span><span>נדחו מיד <b>${st.full}</b></span><span>נדחו אחרי המתנה <b>${st.to}</b></span>
        <span>p50 <b>${pct(st.lat, .5).toFixed(1)}s</b></span><span>p95 <b>${pct(st.lat, .95).toFixed(1)}s</b></span>
        <span>קיבולת (מקומות/זמן) <b>${cap.toFixed(1)}/s</b> מול הגעה <b>${P.lam}/s</b></span>`;
    }
    function frame(ts) {
      if (!playing) { timer = null; return; }
      const dt = Math.min(0.1, (ts - (last || ts)) / 1000) * speed;
      last = ts; step(dt); draw();
      timer = requestAnimationFrame(frame);
    }
    function play(on) { playing = on; g("g-play").textContent = on ? "השהה" : "המשך"; if (on && !timer) { last = 0; timer = requestAnimationFrame(frame); } }
    g("g-play").onclick = () => play(!playing);
    g("g-reset").onclick = () => { reset(); play(true); };
    g("g-pre").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      g("g-pre").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      P = { ...PRESETS[b.dataset.k] }; reset(); play(true);
    };
    g("g-spd").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; speed = +b.dataset.v; g("g-spd").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b)); };
    for (const [k, id] of [["lam", "g-lam"], ["S", "g-S"], ["c", "g-c"], ["K", "g-K"], ["T", "g-T"]]) {
      g(id).oninput = () => {
        P[k] = +g(id).value; g(id + "v").textContent = P[k];
        if (k === "c") { const s = st.slots.slice(0, P.c); while (s.length < P.c) s.push(null); st.slots = s; }
        if (k === "K") st.q = st.q.slice(0, P.K);
        g("g-pre").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", "false"));
        draw();
      };
    }
    reset();
    play(playing);
    return () => { playing = false; if (timer) cancelAnimationFrame(timer); };
  };

  /* ================= simulator: load, Little's law, knee ================= */
  function simulate({ lam, S, c, K, T }, n, seed) {
    const r = rng(seed), free = Array(c).fill(0), waitEnds = [];
    let a = 0, served = 0, full = 0, to = 0;
    const lat = [], intervals = [];
    for (let i = 0; i < n; i++) {
      a += expo(r, lam);
      let k = 0; for (let j = 1; j < c; j++) if (free[j] < free[k]) k = j;
      const f = free[k];
      if (f <= a) { const d = svc(r, S); free[k] = a + d; served++; lat.push(d); intervals.push([a, a + d]); continue; }
      let ql = 0; for (const e of waitEnds) if (e > a) ql++;
      if (waitEnds.length > 4 * (K + 10)) waitEnds.splice(0, waitEnds.length - 2 * (K + 10));
      if (ql >= K) { full++; continue; }
      if (f - a > T) { to++; waitEnds.push(a + T); intervals.push([a, a + T]); continue; }
      const d = svc(r, S); free[k] = f + d; served++; lat.push(f - a + d); waitEnds.push(f); intervals.push([a, f + d]);
    }
    const span = Math.max(...free, a) || 1;
    let area = 0; for (const [s, e] of intervals) area += e - s; // integral of "requests inside" over time
    const inside = intervals.length, W = inside ? area / inside : 0;
    return { thr: served / span, p50: pct(lat, .5), p95: pct(lat, .95), p99: pct(lat, .99), full: full / n, to: to / n,
      Lmeas: area / span, lamEff: inside / span, W, util: Math.min(1, lat.length ? (served * S) / (span * c) : 0) };
  }
  window.AIDS["l26load"] = function (host) {
    style();
    host.innerHTML = `<div class="sim l26">
      <div class="guide"><p><b>מה רואים:</b> סימולציה של השירות מול 20,000 בקשות שמגיעות בקצב אקראי (מודל <b>פתוח</b>: הבקשות מגיעות בלי קשר לכמה השרת עמוס, כמו משתמשים אמיתיים). כל קריאה למודל לוקחת בין 60% ל-140% מזמן הקריאה שבחרת. בשורת המספרים: התפוקה, זמני התגובה של הבקשות שהצליחו (כולל ההמתנה בתור), ואחוז הדחיות משני הסוגים.</p>
      <p><b>חוק Little במילים:</b> כמה בקשות נמצאות בפנים בממוצע = כמה נכנסות בשנייה × כמה זמן כל אחת נשארת. למשל 4 בשנייה × 2 שניות = 8 בפנים. השורה "בדיקת Little" סופרת בפועל כמה בקשות היו בפנים לאורך הזמן, ומשווה לחישוב. הם תמיד יוצאים שווים, וזה הכוח של החוק: הוא לא תלוי באיך השירות בנוי. ומכאן הכיוון ההפוך שחשוב לנו: אם בפנים יכולות להיות לכל היותר <i>מקומות</i> בקשות, התפוקה לא תעבור את <i>מקומות ÷ זמן קריאה</i>.</p>
      <p><b>הגרף:</b> אותו שירות בעשרה קצבי הגעה, מחמישית מהקיבולת ועד פי שניים ממנה. הקו הכחול הוא p95, הקו האדום הוא אחוז הבקשות שנדחו, והקו המקווקו האנכי הוא הקיבולת. הברך היא המקום שבו p95 מתחיל לטפס.</p></div>
      <div class="knobs">
        ${knob("ld-lam", "בקשות בשנייה (λ)", 0.5, 12, 0.5, 3, "קצב ההגעה")}
        ${knob("ld-S", "זמן קריאה ממוצע (שניות)", 0.5, 8, 0.5, 2, "למשל 0.3 TTFT + 300 טוקנים")}
        ${knob("ld-c", "מקומות בשער", 1, 32, 1, 8, "קריאות במקביל")}
        ${knob("ld-K", "גודל התור", 0, 200, 1, 16, "0 = בלי תור")}
        ${knob("ld-T", "queue timeout (שניות)", 0.5, 30, 0.5, 2, "המתנה מקסימלית")}
      </div>
      <div class="stats" id="ld-st"></div>
      <div class="say" id="ld-say"></div>
      <svg id="ld-svg" viewBox="0 0 360 190" role="img" aria-label="p95 ואחוז דחיות לפי קצב הגעה"></svg>
      <div class="legend"><span><i style="background:var(--accent)"></i>p95 (שניות, ציר שמאל)</span><span><i style="background:var(--bad)"></i>נדחו (%, ציר ימין)</span><span><i style="background:var(--muted)"></i>קיבולת</span><span><i style="background:var(--signal)"></i>הקצב שבחרת</span></div></div>`;
    const g = (id) => host.querySelector("#" + id);
    const ids = ["lam", "S", "c", "K", "T"];
    let pending = null;
    function params() { const p = {}; ids.forEach((k) => { p[k] = +g("ld-" + k).value; g("ld-" + k + "v").textContent = p[k]; }); return p; }
    function run() {
      const p = params(), cap = p.c / p.S, res = simulate(p, 20000, 11);
      g("ld-st").innerHTML = `<span>קיבולת <b>${cap.toFixed(2)}/s</b></span><span>תפוקה <b>${res.thr.toFixed(2)}/s</b></span><span>ניצולת <b>${(res.util * 100).toFixed(0)}%</b></span>
        <span>p50 <b>${res.p50.toFixed(2)}s</b></span><span>p95 <b>${res.p95.toFixed(2)}s</b></span><span>p99 <b>${res.p99.toFixed(2)}s</b></span>
        <span>נדחו מיד <b>${(res.full * 100).toFixed(1)}%</b></span><span>נדחו אחרי המתנה <b>${(res.to * 100).toFixed(1)}%</b></span>
        <span>בדיקת Little: בפנים בממוצע <b>${res.Lmeas.toFixed(2)}</b> = ${res.lamEff.toFixed(2)}/s × ${res.W.toFixed(2)}s = <b>${(res.lamEff * res.W).toFixed(2)}</b></span>`;
      const ratio = p.lam / cap;
      g("ld-say").innerHTML = ratio < 0.7 ? `הקצב הוא ${(ratio * 100).toFixed(0)}% מהקיבולת. כמעט כל בקשה נכנסת מיד, ו-p95 קרוב לזמן הקריאה עצמו.`
        : ratio < 1 ? `הקצב הוא ${(ratio * 100).toFixed(0)}% מהקיבולת: קרוב לברך. אין עדיין דחיות רבות, אבל בגלל האקראיות נוצרים תורים קצרים, ו-p95 מתחיל לעלות לפני שהתפוקה מגיעה לתקרה.`
        : `הקצב גבוה מהקיבולת (${(ratio * 100).toFixed(0)}%). התפוקה תקועה על ${res.thr.toFixed(2)} בשנייה, ולא משנה כמה עוד יגיעו. כל עודף הופך להמתנה (עד גבול התור וה-timeout) ואז לדחייה. ${p.K > 50 && p.T > 10 ? "עם תור כל כך גדול, המחיר הוא p95 ארוך מאוד: הלקוחות מחכים במקום לקבל תשובה מהירה שלילית." : ""}`;
      drawChart(p, cap);
    }
    function drawChart(p, cap) {
      const pts = [];
      for (let i = 0; i < 10; i++) { const lam = cap * (0.2 + (1.8 * i) / 9); const r = simulate({ ...p, lam }, 5000, 3 + i); pts.push({ lam, p95: r.p95, drop: r.full + r.to }); }
      const W = 360, H = 190, L = 34, R = 30, Tp = 10, B = 28;
      const xmax = cap * 2, ymax = Math.max(p.S * 1.6, ...pts.map((q) => q.p95)) * 1.05;
      const X = (v) => L + (v / xmax) * (W - L - R), Y = (v) => H - B - (v / ymax) * (H - Tp - B), Yd = (v) => H - B - v * (H - Tp - B);
      const line = (f, col, dash) => `<polyline fill="none" stroke="${col}" stroke-width="2" ${dash ? 'stroke-dasharray="4 3"' : ""} points="${pts.map((q) => X(q.lam).toFixed(1) + "," + f(q).toFixed(1)).join(" ")}"/>`;
      let s = `<line x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}" stroke="var(--line)"/><line x1="${L}" y1="${Tp}" x2="${L}" y2="${H - B}" stroke="var(--line)"/>`;
      for (let i = 0; i <= 4; i++) { const v = (ymax * i) / 4; s += `<text x="${L - 4}" y="${Y(v) + 3}" text-anchor="end">${v.toFixed(1)}</text>`; s += `<text x="${W - R + 4}" y="${Yd(i / 4) + 3}">${i * 25}%</text>`; }
      for (let i = 0; i <= 4; i++) { const v = (xmax * i) / 4; s += `<text x="${X(v)}" y="${H - B + 14}" text-anchor="middle">${v.toFixed(1)}</text>`; }
      s += `<text x="${(W) / 2}" y="${H - 2}" text-anchor="middle">arrivals / s</text>`;
      s += `<line x1="${X(cap)}" y1="${Tp}" x2="${X(cap)}" y2="${H - B}" stroke="var(--muted)" stroke-dasharray="3 3"/>`;
      if (p.lam <= xmax) s += `<line x1="${X(p.lam)}" y1="${Tp}" x2="${X(p.lam)}" y2="${H - B}" stroke="var(--signal)" stroke-width="2"/>`;
      s += line((q) => Y(q.p95), "var(--accent)") + line((q) => Yd(q.drop), "var(--bad)", true);
      g("ld-svg").innerHTML = s;
    }
    ids.forEach((k) => (g("ld-" + k).oninput = () => { params(); clearTimeout(pending); pending = setTimeout(run, 60); }));
    run();
    return () => clearTimeout(pending);
  };

  /* ================= stream cancellation ================= */
  window.AIDS["l26cancel"] = function (host) {
    style();
    const WORDS = "Full-time employees receive 14 paid vacation days in their first year and the allowance grows by one day per year of service up to 24 days. Requests of three days or more go through the HR portal at least two weeks in advance and need the direct manager's approval. Up to 5 unused days carry over to the next year and expire on March 31 [1].".split(" ");
    const TOTAL = WORDS.length;
    const MODES = {
      async: { l: "async (AsyncLLM)", d: "הביטול מגיע כ-CancelledError לתוך ה-generator, ה-async with של httpx סוגר את החיבור, והספק נכשל בכתיבה הבאה ועוצר. טוקן אחד שכבר היה בדרך עוד נוצר." },
      thread: { l: "thread (threaded_stream)", d: "ה-thread נמצא בתוך next() ואי אפשר לקטוע אותו. הסגירה מחכה שהוא יחזור עם הטוקן הבא, ורק אז gen.close() סוגר את החיבור. כך נוצר עוד טוקן, וה-thread תפוס עד אז." },
      leaky: { l: "leaky (משימת רקע)", d: "משימת הרקע שקוראת מהספק לא קשורה לבקשה. היא ממשיכה עד הסוף, וכל טוקן נערם בתור שאף אחד לא יקרא. השירות רואה closed_early וחושב שהכל בסדר." },
    };
    host.innerHTML = `<div class="sim l26">
      <div class="guide"><p><b>מה רואים:</b> שלוש תיבות, משמאל לימין: <b>הספק</b> מייצר טוקנים, <b>השירות</b> מעביר אותם הלאה, ו<b>הלקוח</b> מציג אותם. לחץ "התחל", ואחרי כמה טוקנים לחץ "הלקוח סגר את הלשונית". השורה התחתונה מסבירה מה קרה בכל שכבה, והמונים מראים כמה טוקנים <b>נוצרו</b> (ועליהם משלמים), כמה <b>הגיעו</b> ללקוח, ומה כל צד מדווח. נסה את שלושת המצבים: הם שלושת המימושים ב-servekit, ותריץ אותם באמת בתרגיל 4.</p></div>
      <div class="seg" id="c-mode">${Object.entries(MODES).map(([k, m]) => `<button data-k="${k}" aria-pressed="${k === "async"}">${m.l}</button>`).join("")}</div>
      <div class="three">
        <div class="actor" id="c-up"><h4><span>הספק (upstream)</span><span class="badge" id="c-upb">ממתין</span></h4><div class="flow" id="c-upf"></div></div>
        <div class="actor" id="c-sv"><h4><span>השירות</span><span class="badge" id="c-svb">ממתין</span></h4><div class="flow" id="c-svf"></div></div>
        <div class="actor" id="c-cl"><h4><span>הלקוח</span><span class="badge" id="c-clb">ממתין</span></h4><div class="flow" id="c-clf" style="direction:ltr"></div></div>
      </div>
      <div class="stats" id="c-st"></div>
      <div class="say" id="c-say">בחר מצב ולחץ "התחל".</div>
      <div class="row"><button class="btn small primary" id="c-go">התחל</button><button class="btn small" id="c-cut" disabled>הלקוח סגר את הלשונית</button></div></div>`;
    const g = (id) => host.querySelector("#" + id);
    let mode = "async", timer = null, s;
    function reset() { s = { gen: 0, got: 0, cut: false, cutAt: 0, upDone: false, upAborted: false, buf: 0, threadBusy: false, running: false }; draw(); }
    function badge(id, txt, cls) { const b = g(id); b.textContent = txt; b.className = "badge" + (cls ? " " + cls : ""); }
    function draw() {
      g("c-upf").textContent = WORDS.slice(Math.max(0, s.gen - 8), s.gen).join(" ");
      g("c-clf").textContent = WORDS.slice(0, s.got).join(" ");
      g("c-svf").textContent = mode === "leaky" && s.cut ? `queue: ${s.buf} tokens nobody will read` : s.cut ? "stream closed" : s.running ? "relaying tokens..." : "";
      g("c-cl").classList.toggle("dead", s.cut);
      badge("c-upb", s.upAborted ? "aborted" : s.upDone ? "completed" : s.running ? "מייצר" : "ממתין", s.upAborted ? "on" : s.upDone && s.cut ? "badx" : s.running ? "busy" : "");
      badge("c-svb", s.cut ? (mode === "thread" && s.threadBusy ? "thread תפוס" : "closed_early") : s.running ? "פעיל" : "ממתין", s.cut && mode === "thread" && s.threadBusy ? "busy" : s.cut ? "on" : "");
      badge("c-clb", s.cut ? "התנתק" : s.got >= TOTAL ? "קיבל הכל" : s.running ? "קורא" : "ממתין", s.cut ? "badx" : "");
      const wasted = s.gen - s.got;
      g("c-st").innerHTML = `<span>נוצרו אצל הספק <b>${s.gen}</b></span><span>הגיעו ללקוח <b>${s.got}</b></span><span>נוצרו לשווא <b>${wasted}</b></span>
        <span>השירות מדווח <b>${s.cut ? "closed_early" : s.upDone ? "finished" : "-"}</b></span><span>הספק מדווח <b>${s.upAborted ? "aborted" : s.upDone ? "completed" : "-"}</b></span>`;
    }
    function tick() {
      if (s.upDone || s.upAborted) { stop(); return; }
      s.gen++;
      if (!s.cut) s.got = s.gen;
      else if (mode === "leaky") s.buf++;
      if (s.cut && mode === "async" && s.gen >= s.cutAt + 1) { s.upAborted = true; g("c-say").innerHTML = `<b>async:</b> ${MODES.async.d} סך הכל ${s.gen - s.got} טוקן לשווא.`; }
      if (s.cut && mode === "thread" && s.gen >= s.cutAt + 2) { s.upAborted = true; s.threadBusy = false; g("c-say").innerHTML = `<b>thread:</b> ${MODES.thread.d} סך הכל ${s.gen - s.got} טוקנים לשווא.`; }
      if (s.gen >= TOTAL) { s.upDone = true; if (s.cut && mode === "leaky") g("c-say").innerHTML = `<b>leaky:</b> ${MODES.leaky.d} הספק סיים את כל ${TOTAL} הטוקנים, הלקוח ראה ${s.got}. בדשבורד של השירות הכל ירוק, ובחשבונית שילמת על ${s.gen - s.got} טוקנים שאף אחד לא ראה.`; else if (!s.cut) g("c-say").textContent = "הזרם הסתיים כרגיל: done. נסה שוב, והפעם נתק באמצע."; }
      draw();
    }
    function stop() { clearInterval(timer); timer = null; s.running = false; g("c-cut").disabled = true; g("c-go").disabled = false; g("c-go").textContent = "שוב"; draw(); }
    g("c-go").onclick = () => {
      reset(); s.running = true; g("c-go").disabled = true; g("c-cut").disabled = false;
      g("c-say").textContent = "הספק מייצר טוקנים, השירות מעביר כל אחד ללקוח מיד. עכשיו לחץ \"הלקוח סגר את הלשונית\".";
      timer = setInterval(tick, 260);
    };
    g("c-cut").onclick = () => {
      if (s.cut) return;
      s.cut = true; s.cutAt = s.gen; g("c-cut").disabled = true;
      if (mode === "thread") s.threadBusy = true;
      g("c-say").innerHTML = mode === "async" ? "uvicorn זיהה ניתוק, Starlette מבטל את משימת השליחה..." : mode === "thread" ? "Starlette ביטל את השליחה, אבל ה-thread עוד בתוך next() ומחכה לטוקן הבא..." : "Starlette ביטל את מי שקורא מהתור. משימת הרקע? אף אחד לא ביטל אותה...";
      draw();
    };
    g("c-mode").onclick = (e) => {
      const b = e.target.closest("button"); if (!b || s.running) return;
      mode = b.dataset.k; g("c-mode").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      reset(); g("c-go").textContent = "התחל"; g("c-say").textContent = MODES[mode].l + ": לחץ \"התחל\", ונתק אחרי כמה טוקנים.";
    };
    reset();
    return () => clearInterval(timer);
  };

  /* ================= token bucket ================= */
  window.AIDS["l26bucket"] = function (host) {
    style();
    host.innerHTML = `<div class="sim l26">
      <div class="guide"><p><b>מה רואים:</b> הדלי של לקוח אחד. הגובה הכחול הוא מספר האסימונים שיש לו עכשיו. הדלי מתמלא ברציפות בקצב <b>rate</b>, עד <b>burst</b>. כל בקשה לוקחת אסימון אחד. אם אין אסימון שלם, הבקשה נדחית עם 429, וזמן ההמתנה המדויק הוא (1 − אסימונים) ÷ rate. ה-Retry-After בכותרת הוא המספר הזה מעוגל למעלה לשניות שלמות.</p>
      <p><b>הרצועה מימין</b> מראה את 12 השניות האחרונות: פס ירוק למעלה = בקשה שעברה, פס אדום למטה = בקשה שנדחתה. שלח ביד, או הפעל תבנית תנועה.</p></div>
      <div class="knobs">${knob("b-rate", "rate (אסימונים לשנייה)", 0.5, 10, 0.5, 2, "הקצב היציב המותר")}${knob("b-burst", "burst (גודל הדלי)", 1, 20, 1, 5, "כמה בקשות ברצף מותר")}</div>
      <div class="bucket"><div class="tank"><i id="b-lvl"></i><b id="b-num"></b></div><div class="strip" id="b-strip"></div></div>
      <div class="row"><button class="btn small primary" id="b-one">שלח בקשה</button><button class="btn small" id="b-ten">10 בבת אחת</button><span class="spacer"></span>
        <div class="seg" id="b-pat"><button data-k="none" aria-pressed="true">בלי תנועה</button><button data-k="steady" aria-pressed="false">יציבה 3/s</button><button data-k="burst" aria-pressed="false">פרצים: 8 כל 4s</button></div></div>
      <div class="stats" id="b-st"></div>
      <div class="say" id="b-say">לחץ "שלח בקשה".</div></div>`;
    const g = (id) => host.querySelector("#" + id);
    let rate = 2, burst = 5, tokens = 5, now = 0, last = performance.now(), marks = [], ok = 0, no = 0, pat = "none", nextAuto = 0, timer = null;
    function advance() { const t = performance.now(); const dt = (t - last) / 1000; last = t; now += dt; tokens = Math.min(burst, tokens + dt * rate); }
    function send(n = 1) {
      advance();
      let txt = "";
      for (let i = 0; i < n; i++) {
        if (tokens >= 1) { tokens -= 1; ok++; marks.push([now, 1]); txt = `200: עברה. נשארו ${tokens.toFixed(2)} אסימונים.`; }
        else { const w = (1 - tokens) / rate; no++; marks.push([now, 0]); txt = `429: אין אסימון שלם (יש ${tokens.toFixed(2)}). עוד ${w.toFixed(2)} שניות יהיה, ולכן Retry-After: ${Math.max(1, Math.ceil(w))}.`; }
      }
      if (n > 1) { const recent = marks.slice(-n); const k = recent.filter((m) => m[1]).length; txt = `${n} בקשות ברצף: ${k} עברו (כמה שהיו אסימונים בדלי), ${n - k} נדחו. ${txt}`; }
      g("b-say").textContent = txt;
    }
    function draw() {
      advance();
      if (pat === "steady" && now >= nextAuto) { send(1); nextAuto = now + 1 / 3; }
      if (pat === "burst" && now >= nextAuto) { send(8); nextAuto = now + 4; }
      g("b-lvl").style.height = (tokens / burst) * 100 + "%";
      g("b-num").textContent = tokens.toFixed(1) + " / " + burst;
      marks = marks.filter((m) => now - m[0] < 12);
      const st = g("b-strip"), w = st.clientWidth || 300;
      st.innerHTML = marks.map((m) => `<i class="${m[1] ? "ok" : "no"}" style="left:${(w - 6) * (1 - (now - m[0]) / 12)}px"></i>`).join("");
      const tot = ok + no;
      g("b-st").innerHTML = `<span>עברו <b>${ok}</b></span><span>נדחו <b>${no}</b></span><span>אחוז דחיות <b>${tot ? ((no / tot) * 100).toFixed(0) : 0}%</b></span><span>הדלי מתמלא מאפס תוך <b>${(burst / rate).toFixed(1)}s</b></span>`;
    }
    g("b-one").onclick = () => send(1);
    g("b-ten").onclick = () => send(10);
    g("b-pat").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; pat = b.dataset.k; nextAuto = now; g("b-pat").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b)); ok = 0; no = 0; };
    const sync = () => { rate = +g("b-rate").value; burst = +g("b-burst").value; tokens = Math.min(tokens, burst); g("b-ratev").textContent = rate; g("b-burstv").textContent = burst; };
    g("b-rate").oninput = sync; g("b-burst").oninput = sync; sync();
    timer = setInterval(draw, 100);
    draw();
    return () => clearInterval(timer);
  };
})();
