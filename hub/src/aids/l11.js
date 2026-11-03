// Lesson 11 aids: HNSW step-by-step animation (l11hnsw), HNSW playground with M/ef/tombstones
// (l11tune), filtering pitfall (l11filter), memory + AWS cost calculator (l11cost).
// A real (small) HNSW implementation in 2-D, shared by the first two. Uses only CSS variables.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const CSS = `
  .l11 { display: grid; gap: 12px; direction: rtl; }
  .l11 svg { direction: ltr; width: 100%; height: auto; display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; touch-action: manipulation; }
  .l11 .l11-bar { display: flex; flex-wrap: wrap; gap: 4px; }
  .l11 .l11-bar button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 3px 9px; font-size: .78rem; }
  .l11 .l11-bar button.on { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .l11 .l11-panels { display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 700px) { .l11 .l11-panels { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .l11 .l11-panel { display: grid; gap: 3px; }
  .l11 .l11-panel small { color: var(--muted); font-size: .76rem; }
  .l11 .l11-cap { font-size: .9rem; line-height: 1.75; min-height: 3.2em; }
  .l11 .l11-cap b.t { display: block; font-size: .98rem; margin-bottom: 2px; }
  .l11 .l11-ctl { display: grid; gap: 10px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 700px) { .l11 .l11-ctl { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .l11 input[type=range] { width: 100%; }
  .l11 .l11-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .l11 .l11-stats { display: grid; gap: 6px; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
  .l11 .l11-stats div { border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; background: var(--surface); }
  .l11 .l11-stats b { display: block; font-family: var(--mono); font-size: 1.05rem; direction: ltr; text-align: right; }
  .l11 .l11-stats small { color: var(--muted); font-size: .74rem; line-height: 1.4; display: block; }
  .l11 .l11-src { font-size: .76rem; color: var(--muted); line-height: 1.6; }
  .l11 .l11-meas { display: grid; gap: 4px; font-size: .78rem; direction: ltr; }
  .l11 .l11-meas .r { display: grid; grid-template-columns: 5.5rem minmax(0, 1fr) 3.4rem 3.6rem; gap: 6px; align-items: center; }
  .l11 .l11-meas .r span, .l11 .l11-meas .r i { font-family: var(--mono); font-style: normal; }
  .l11 .l11-meas .r i { text-align: right; color: var(--muted); }
  .l11 .l11-meas .bar { height: 9px; border-radius: 4px; background: var(--accent); }
  .l11 .l11-meas .r.ok .bar { background: var(--good); }
  .l11 .l11-opts { display: grid; gap: 6px; }
  .l11 .l11-opt { border: 1px solid var(--line); border-radius: 9px; padding: 7px 9px; background: var(--surface); display: grid; gap: 3px; }
  .l11 .l11-opt .top { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; flex-wrap: wrap; }
  .l11 .l11-opt .top b { font-family: var(--mono); direction: ltr; }
  .l11 .l11-opt .bar { height: 7px; border-radius: 4px; background: var(--accent); min-width: 2px; }
  .l11 .l11-opt.best { border-color: var(--good); background: var(--good-soft); }
  .l11 .l11-opt small { color: var(--muted); font-size: .74rem; line-height: 1.5; direction: ltr; text-align: left; overflow-wrap: anywhere; }
  .l11 .l11-stack { display: flex; height: 16px; border-radius: 6px; overflow: hidden; border: 1px solid var(--line); direction: ltr; }
  .l11 .l11-stack span { display: block; height: 100%; }
  .l11 .l11-legend { display: flex; flex-wrap: wrap; gap: 10px; font-size: .78rem; }
  .l11 .l11-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-inline-end: 4px; vertical-align: middle; }
  .l11 .l11-form { display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 700px) { .l11 .l11-form { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .l11 .l11-form label { display: grid; gap: 3px; font-size: .84rem; }
  .l11 .l11-form select, .l11 .l11-form input[type=number] { width: 100%; padding: 4px 6px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); font: inherit; direction: ltr; }
  .l11 text { font-family: var(--mono); }
  `;
  function style() {
    if (document.getElementById("l11-style")) return;
    const s = document.createElement("style");
    s.id = "l11-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  function rng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  function gauss(r) { let u = 0, v = 0; while (u === 0) u = r(); while (v === 0) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function clusteredPoints(n, k, W, H, seed, spread) {
    const R = rng(seed);
    const C = Array.from({ length: k }, () => [25 + R() * (W - 50), 20 + R() * (H - 40)]);
    const lab = [];
    const P = Array.from({ length: n }, (_, i) => {
      const c = i % k; lab.push(c);
      return [Math.max(4, Math.min(W - 4, C[c][0] + gauss(R) * spread)), Math.max(4, Math.min(H - 4, C[c][1] + gauss(R) * spread * 0.8))];
    });
    return { P, lab };
  }
  const d2 = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;
  const exactK = (P, q, k, ok) => P.map((_, j) => j).filter((j) => !ok || ok(j)).sort((a, b) => d2(q, P[a]) - d2(q, P[b])).slice(0, k);

  /* ------------------------------------------------------------ HNSW (2-D, real algorithm) */
  // Malkov & Yashunin: random level with mL = 1/ln(M), greedy descent, beam search with ef,
  // heuristic neighbor selection, bidirectional links, pruning to M (2M on layer 0).
  function HNSW(P, M, efC, seed, maxLevel) {
    const R = rng(seed);
    const mL = 1 / Math.log(Math.max(M, 2));
    const level = [], nb = [];
    let entry = -1, top = -1;
    const cap = (l) => (l === 0 ? 2 * M : M);
    function searchLayer(dq, eps, ef, l, trace) {
      const visited = new Set(eps);
      let C = eps.map((e) => [dq(e), e]);
      let Wl = C.slice().sort((a, b) => a[0] - b[0]);
      if (trace) eps.forEach((e) => trace.push(e));
      while (C.length) {
        C.sort((a, b) => a[0] - b[0]);
        const [dc, c] = C.shift();
        if (Wl.length >= ef && dc > Wl[Wl.length - 1][0]) break;
        for (const e of (nb[c] && nb[c][l]) || []) {
          if (visited.has(e)) continue;
          visited.add(e);
          const de = dq(e);
          if (trace) trace.push(e);
          if (Wl.length < ef || de < Wl[Wl.length - 1][0]) {
            C.push([de, e]); Wl.push([de, e]); Wl.sort((a, b) => a[0] - b[0]);
            if (Wl.length > ef) Wl.pop();
          }
        }
      }
      return { W: Wl, visited };
    }
    function select(base, cands, m) {   // heuristic: keep diverse directions
      const out = [];
      for (const [dc, c] of cands.slice().sort((a, b) => a[0] - b[0])) {
        if (out.length >= m) break;
        if (out.every((s) => d2(P[c], P[s]) > dc)) out.push(c);
      }
      return out;
    }
    function insert(i, rec) {
      let L = Math.floor(-Math.log(Math.max(R(), 1e-9)) * mL);
      if (maxLevel !== undefined) L = Math.min(L, maxLevel);
      level[i] = L; nb[i] = Array.from({ length: L + 1 }, () => []);
      if (entry < 0) { entry = i; top = L; return; }
      const dq = (j) => d2(P[i], P[j]);
      let ep = entry;
      if (rec) { rec.level = L; rec.path = []; rec.cands = {}; rec.links = {}; }
      for (let l = top; l > L; l--) {
        let moved = true;
        while (moved) { moved = false; for (const e of nb[ep][l] || []) if (dq(e) < dq(ep)) { if (rec) rec.path.push([l, ep, e]); ep = e; moved = true; } }
      }
      for (let l = Math.min(L, top); l >= 0; l--) {
        const { W: cand } = searchLayer(dq, [ep], efC, l);
        const chosen = select(i, cand, M);
        if (rec) { rec.cands[l] = cand.map((x) => x[1]); rec.links[l] = chosen.slice(); }
        nb[i][l] = chosen.slice();
        for (const n of chosen) {
          nb[n][l].push(i);
          if (nb[n][l].length > cap(l)) nb[n][l] = select(n, nb[n][l].map((x) => [d2(P[n], P[x]), x]), cap(l));
        }
        ep = cand[0][1];
      }
      if (L > top) { entry = i; top = L; }
    }
    // in-graph search: walk ignores `ok`, results keep only nodes with ok(j) (tombstones, filters)
    function search(q, k, ef, ok, trace) {
      let dist = 0;
      const dq = (j) => { dist++; return d2(q, P[j]); };
      let ep = entry; const path = [];
      for (let l = top; l > 0; l--) {
        let moved = true, best = dq(ep);
        while (moved) { moved = false; for (const e of nb[ep][l] || []) { const de = dq(e); if (de < best) { path.push([l, ep, e]); ep = e; best = de; moved = true; } } }
      }
      const visitOrder = [];
      const { W: res, visited } = searchLayer(dq, [ep], Math.max(ef, k), 0, visitOrder);
      // with a filter, only allowed nodes in the ef-sized result list come back: fewer than k
      // when the walk saw few of them (what FAISS IDSelector / naive in-graph filtering does)
      const found = (ok ? res.map((x) => x[1]).filter(ok) : res.map((x) => x[1])).slice(0, k);
      if (trace) { trace.path = path; trace.visit = visitOrder; trace.entry = entry; }
      return { found, dist, visited };
    }
    return { insert, search, level, nb, get entry() { return entry; }, get top() { return top; } };
  }
  const graphBytes = (m) => (m < 2 ? 0 : (2 * m * 4 + 4) + (m * 4 + 4) / (m - 1));

  /* ================================================================ l11hnsw (intro animation) */
  window.AIDS["l11hnsw"] = function (host) {
    style();
    const W = 200, H = 140, N = 120;
    host.innerHTML = `<div class="l11">
      <div class="guide"><p><b>מה רואים:</b> אותו גרף HNSW בשלושה לוחות, אחד לכל שכבה. השכבה העליונה (2) בלוח הראשון, והתחתונה (0) באחרון. בכל לוח מוצגות רק הנקודות שהגיעו לשכבה הזו. הריבוע הוא נקודת הכניסה. הצלב הכתום הוא השאילתה, הקו העבה הוא המסלול, הנקודות הכחולות הבהירות הן צמתים שחושב אליהם מרחק, והטבעות הירוקות הן התוצאות (אדומה: שכן אמיתי שפוספס).</p>
      <p><b>איך משתמשים:</b> עוברים על השלבים עם "הבא", או לוחצים על שם השלב. הפסים משנים את M ואת efSearch, ואחרי שינוי של M הגרף נבנה מחדש מאפס.</p></div>
      <div class="l11-bar" id="hs-steps"></div>
      <div class="l11-panels" id="hs-panels"></div>
      <div class="l11-cap" id="hs-cap" aria-live="polite"></div>
      <div class="l11-row"><button class="btn small" id="hs-prev">הקודם</button><button class="btn small primary" id="hs-next">הבא</button><button class="btn small" id="hs-q">שאילתה אחרת</button></div>
      <div class="l11-ctl">
        <div class="knob"><div class="knob-head"><span>M: שכנים לצומת</span><b id="hs-mv">4</b></div><input type="range" id="hs-m" min="2" max="10" value="4"><small>בשכבה 0 עד 2M. משנה את הגרף, ולכן הוא נבנה מחדש</small></div>
        <div class="knob"><div class="knob-head"><span>efSearch: רוחב החיפוש</span><b id="hs-ev">6</b></div><input type="range" id="hs-e" min="1" max="40" value="6"><small>גודל רשימת התוצאות בשכבה 0 (לפחות k)</small></div>
        <div class="knob"><div class="knob-head"><span>k: שכנים מבוקשים</span><b>5</b></div><small>efConstruction קבוע: 16</small></div>
      </div>
      <div class="stats" id="hs-stats"></div>
      <h4 style="margin:4px 0 0">ומה קורה בממדים גבוהים? נמדד ב-FAISS</h4>
      <div class="l11-src">50 אלף וקטורים סינתטיים מקובצים, 384 ממדים, ליבה אחת, recall@10 מול חיפוש מדויק, efConstruction=100 (<code>labs/11-managed-vectors/hnsw_sweep.py</code>). מדידה אחת על מכונה משותפת: אצלך הזמנים יהיו אחרים. ירוק פירושו recall של 0.95 ומעלה.</div>
      <div class="l11-meas" id="hs-meas"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const { P } = clusteredPoints(N, 6, W, H, 11, 16);
    const STEPS = ["הגרלת שכבות", "הכנסה של נקודה", "ירידה חמדנית", "חיפוש רחב בשכבה 0", "התוצאה מול האמת"];
    let step = 0, M = 4, ef = 6, k = 5, idx, rec, Q, trace, res, timers = [], qseed = 3;
    const PL = [2, 1, 0];
    g("hs-panels").innerHTML = PL.map((l) => `<div class="l11-panel"><small id="hs-t${l}">שכבה ${l}</small><svg viewBox="0 0 ${W} ${H}" id="hs-s${l}" role="img" aria-label="שכבה ${l} של הגרף"></svg></div>`).join("");
    g("hs-steps").innerHTML = STEPS.map((s, i) => `<button data-i="${i}">${i + 1}. ${s}</button>`).join("");
    g("hs-steps").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { step = +b.dataset.i; show(); } });
    function build() {
      idx = HNSW(P, M, 16, 7, 2);
      for (let i = 0; i < N - 1; i++) idx.insert(i);
      rec = {};
      idx.insert(N - 1, rec);           // the purple point, recorded
      newQuery(false);
    }
    function newQuery(adv) {
      const R = rng(qseed++);
      Q = [20 + R() * (W - 40), 15 + R() * (H - 30)];
      trace = {};
      res = idx.search(Q, k, ef, null, trace);
      if (adv !== false) show();
    }
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function base(l, opts) {
      const ids = P.map((_, j) => j).filter((j) => idx.level[j] >= l && (opts.showNew || j !== N - 1));
      let s = "";
      if (opts.edges) for (const j of ids) for (const e of idx.nb[j][l] || []) if (e > j && (opts.showNew || e !== N - 1)) s += `<line x1="${P[j][0]}" y1="${P[j][1]}" x2="${P[e][0]}" y2="${P[e][1]}" stroke="var(--line)" stroke-width="0.6"/>`;
      for (const j of ids) s += `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="${l ? 2.6 : 1.9}" fill="var(--muted)" data-j="${j}"/>`;
      const en = idx.entry;
      if (idx.level[en] >= l) s += `<rect x="${P[en][0] - 4}" y="${P[en][1] - 4}" width="8" height="8" fill="none" stroke="var(--ink)" stroke-width="1.2"/>`;
      return s;
    }
    const cross = (q) => `<path d="M${q[0] - 5} ${q[1]}h10M${q[0]} ${q[1] - 5}v10" stroke="var(--signal)" stroke-width="2"/>`;
    function draw(fn) { PL.forEach((l) => { g("hs-s" + l).innerHTML = fn(l); }); }
    function counts() {
      const c = [0, 1, 2].map((l) => idx.level.filter((x) => x >= l).length);
      PL.forEach((l) => { g("hs-t" + l).textContent = `שכבה ${l}: ${c[l]} נקודות (תחזית ${(N * Math.pow(M, -l)).toFixed(0)}, תקרה ${l ? M : 2 * M} שכנים)`; });
      return c;
    }
    function stats() {
      const truth = exactK(P, Q, k);
      const hit = truth.filter((t) => res.found.includes(t)).length;
      g("hs-stats").innerHTML = `<div><b>${hit}/${k}</b><small>recall@${k} מול חיפוש מדויק</small></div><div><b>${res.dist}</b><small>מרחקים שחושבו (חיפוש מדויק: ${N})</small></div><div><b>${M} / ${ef}</b><small>M / efSearch</small></div>`;
      return truth;
    }
    function show() {
      clear();
      [...g("hs-steps").children].forEach((b, i) => b.classList.toggle("on", i === step));
      const c = counts();
      stats();
      const capEl = g("hs-cap");
      if (step === 0) {
        draw((l) => base(l, { edges: false, showNew: true }));
        capEl.innerHTML = `<b class="t">1. הגרלת שכבות</b>כל נקודה קיבלה שכבה מקסימלית בהגרלה: מגיעים לשכבה l בהסתברות M<sup>−l</sup>. עם M=${M}, ב-${N} נקודות הגיעו ${c[1]} לשכבה 1 ו-${c[2]} לשכבה 2 (כאן השכבות נחתכו ב-2 בשביל התצוגה). בשכבות העליונות יש מעט צמתים, ולכן אפשר לחצות בהן את המפה בכמה קפיצות.`;
      } else if (step === 1) {
        const nw = N - 1;
        draw((l) => {
          let s = base(l, { edges: true, showNew: false });
          if (idx.level[nw] >= l) {
            for (const c2 of (rec.cands[l] || [])) s += `<circle cx="${P[c2][0]}" cy="${P[c2][1]}" r="3.6" fill="none" stroke="var(--accent)" stroke-width="0.8"/>`;
            s += `<g class="l11-new"></g><circle cx="${P[nw][0]}" cy="${P[nw][1]}" r="3.4" fill="#8b5cf6"/>`;
          }
          for (const [ll, a, b] of rec.path) if (ll === l) s += `<line x1="${P[a][0]}" y1="${P[a][1]}" x2="${P[b][0]}" y2="${P[b][1]}" stroke="#8b5cf6" stroke-width="1.6" stroke-dasharray="3 2"/>`;
          return s;
        });
        PL.forEach((l, li) => {
          if (idx.level[nw] < l) return;
          (rec.links[l] || []).forEach((n, i) => timers.push(setTimeout(() => {
            const svg = g("hs-s" + l);
            svg.insertAdjacentHTML("afterbegin", `<line x1="${P[nw][0]}" y1="${P[nw][1]}" x2="${P[n][0]}" y2="${P[n][1]}" stroke="#8b5cf6" stroke-width="1.6"/>`);
          }, 400 + li * 500 + i * 250)));
        });
        capEl.innerHTML = `<b class="t">2. הכנסה של נקודה (סגולה)</b>הנקודה החדשה הגרילה שכבה ${rec.level}. מעל השכבה שלה היא רק יורדת חמדנית (קו מקווקו). בכל שכבה מ-${rec.level} עד 0 היא מחפשת efConstruction=16 מועמדים (עיגולים כחולים), ומתחברת לעד M=${M} מהם (בשכבה 0 עד ${2 * M}), תוך העדפה של כיוונים שונים. קשת נוספת בשני הכיוונים, ואם לשכן יש יותר מדי, הרשימה שלו נגזמת.`;
      } else if (step === 2 || step === 3 || step === 4) {
        const path = trace.path, visit = trace.visit;
        const truth = exactK(P, Q, k);
        draw((l) => {
          let s = base(l, { edges: true, showNew: true }) + cross(Q);
          if (l === 0 && step >= 3) s += `<g id="hs-vis"></g>`;
          if (step >= 2) for (const [ll, a, b] of path) if (ll === l) s += `<line class="l11-p" x1="${P[a][0]}" y1="${P[a][1]}" x2="${P[b][0]}" y2="${P[b][1]}" stroke="var(--signal)" stroke-width="2"/>`;
          if (l === 0 && step === 4) {
            for (const j of visit) s += `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="2.6" fill="var(--accent)" opacity=".55"/>`;
            for (const t of truth) s += `<circle cx="${P[t][0]}" cy="${P[t][1]}" r="4.5" fill="none" stroke="${res.found.includes(t) ? "var(--good)" : "var(--bad)"}" stroke-width="1.6"/>`;
            for (const f of res.found) if (!truth.includes(f)) s += `<circle cx="${P[f][0]}" cy="${P[f][1]}" r="4.5" fill="none" stroke="var(--muted)" stroke-dasharray="2 2"/>`;
          }
          return s;
        });
        if (step === 3) {
          const vis = g("hs-vis");
          visit.forEach((j, i) => timers.push(setTimeout(() => { vis.insertAdjacentHTML("beforeend", `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="2.6" fill="var(--accent)" opacity=".6"/>`); }, 60 * i)));
        }
        if (step === 2) capEl.innerHTML = `<b class="t">3. ירידה חמדנית</b>החיפוש מתחיל בנקודת הכניסה (הריבוע) בשכבה העליונה, וקופץ כל פעם לשכן שקרוב יותר לשאילתה (הקו הכתום), עד שאין שיפור. אז הוא יורד שכבה, ומתחיל מאותו צומת. ${path.length} קפיצות בשכבות העליונות הביאו אותו לאזור הנכון.`;
        else if (step === 3) capEl.innerHTML = `<b class="t">4. חיפוש רחב בשכבה 0</b>בשכבה 0 החיפוש מחזיק רשימה של efSearch=${Math.max(ef, k)} תוצאות, וממשיך לבדוק שכנים של המועמד הקרוב ביותר כל עוד הוא יכול לשפר את הרשימה. הנקודות הכחולות מופיעות בסדר שבו חושב אליהן מרחק: ${visit.length} בשכבה 0. נסה efSearch=1 (חמדני טהור) מול 30.`;
        else { const hit = truth.filter((t) => res.found.includes(t)).length; capEl.innerHTML = `<b class="t">5. התוצאה מול האמת</b>מצאנו ${hit} מתוך ${k} השכנים האמיתיים (ירוק נמצא, אדום פוספס), עם ${res.dist} חישובי מרחק במקום ${N}. בגרף של מיליון וקטורים היחס הזה הוא אלפים בודדים מול מיליון: זה כל הטעם של HNSW. הורד את M ל-2 ותראה כמה הגרף נעשה שביר.`; }
      }
      g("hs-prev").disabled = step === 0;
      g("hs-next").textContent = step === STEPS.length - 1 ? "מההתחלה" : "הבא";
    }
    g("hs-next").addEventListener("click", () => { step = (step + 1) % STEPS.length; show(); });
    g("hs-prev").addEventListener("click", () => { step = Math.max(0, step - 1); show(); });
    g("hs-q").addEventListener("click", () => { newQuery(); if (step < 2) { step = 2; show(); } });
    g("hs-m").addEventListener("input", (e) => { M = +e.target.value; g("hs-mv").textContent = M; build(); show(); });
    g("hs-e").addEventListener("input", (e) => { ef = +e.target.value; g("hs-ev").textContent = ef; res = idx.search(Q, k, ef, null, trace = {}); show(); });
    const MEAS = [["M=8 ef=10", .413, .081], ["M=8 ef=40", .786, .201], ["M=8 ef=160", .978, .782], ["M=16 ef=10", .717, .123], ["M=16 ef=40", .986, .465], ["M=16 ef=80", .999, .774], ["M=32 ef=10", .904, .266], ["M=32 ef=20", .986, .357], ["M=32 ef=40", 1.0, .510]];
    g("hs-meas").innerHTML = `<div class="r" style="color:var(--muted)"><span>config</span><span>recall@10</span><i>R@10</i><i>ms/q</i></div>` + MEAS.map(([n, r, ms]) => `<div class="r ${r >= .95 ? "ok" : ""}"><span>${n}</span><div class="bar" style="width:${(r * 100).toFixed(0)}%"></div><i>${r.toFixed(3)}</i><i>${ms.toFixed(3)}</i></div>`).join("");
    build(); show();
    return () => clear();
  };

  /* ================================================================ l11tune (playground) */
  window.AIDS["l11tune"] = function (host) {
    style();
    const W = 360, H = 250, N = 300, K = 10;
    host.innerHTML = `<div class="l11">
      <div class="guide"><p><b>מה רואים:</b> שכבה 0 של גרף HNSW על 300 נקודות. הקווים הדקים הם הקשתות, הצלב הכתום הוא השאילתה (<b>לחץ על המפה כדי להזיז אותו</b>), והקו הכתום העבה הוא המסלול בשכבות העליונות, כשהוא מוקרן על המישור. נקודות כחולות בהירות חושב אליהן מרחק. טבעת ירוקה היא שכן אמיתי שנמצא, ואדומה שכן אמיתי שפוספס. נקודות אפורות חלולות "נמחקו" (tombstones).</p>
      <p><b>איך לקרוא את הגרף הקטן:</b> בכל בנייה מחדש מורצות 40 שאילתות אקראיות לכל efSearch מ-10 עד 64 (מתחת ל-k=10 החיפוש מתנהג כמו 10). הציר האופקי הוא מספר המרחקים הממוצע (העלות), והאנכי הוא recall@10, מ-0.5 עד 1.0. במישור HNSW קל מאוד, ולכן ההבדלים קטנים מאשר ב-384 ממדים: נסה M=2 ומחיקת 30%. הנקודה המודגשת היא efSearch הנוכחי.</p></div>
      <div class="l11-ctl">
        <div class="knob"><div class="knob-head"><span>M</span><b id="tu-mv">3</b></div><input type="range" id="tu-m" min="2" max="16" value="3"><small>בנייה מחדש. בשכבה 0 עד 2M</small></div>
        <div class="knob"><div class="knob-head"><span>efConstruction</span><b id="tu-cv">16</b></div><input type="range" id="tu-c" min="2" max="64" value="16"><small>בנייה מחדש. רוחב החיפוש בזמן הכנסה</small></div>
        <div class="knob"><div class="knob-head"><span>efSearch</span><b id="tu-ev">10</b></div><input type="range" id="tu-e" min="1" max="64" value="10"><small>רק בחיפוש, בלי לבנות מחדש (לפחות k=10)</small></div>
      </div>
      <div class="l11-row"><label><input type="checkbox" id="tu-del"> מחיקת 30% מהנקודות (tombstones: נשארות בגרף לניווט, לא חוזרות כתוצאה)</label></div>
      <svg viewBox="0 0 ${W} ${H}" id="tu-svg" role="img" aria-label="שכבה 0 של גרף HNSW"></svg>
      <div class="l11-stats" id="tu-stats"></div>
      <svg viewBox="0 0 360 130" id="tu-chart" role="img" aria-label="recall מול מספר מרחקים לפי efSearch"></svg>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const { P } = clusteredPoints(N, 9, W, H, 21, 22);
    const DEL = (() => { const R = rng(5); return P.map(() => R() < 0.3); })();
    let M = 3, efC = 16, ef = 10, del = false, Q = [180, 120], idx, curve = [];
    const ok = (j) => !del || !DEL[j];
    const EFS = [10, 12, 16, 24, 32, 64];   // efSearch below k=10 behaves like 10
    function build() {
      idx = HNSW(P, M, efC, 9);
      for (let i = 0; i < N; i++) idx.insert(i);
      measure();
    }
    function measure() {
      const R = rng(77), qs = Array.from({ length: 40 }, () => [10 + R() * (W - 20), 10 + R() * (H - 20)]);
      curve = EFS.map((e) => {
        let rec = 0, dist = 0;
        for (const q of qs) { const t = exactK(P, q, K, del ? ok : null); const r = idx.search(q, K, e, del ? ok : null); rec += t.filter((x) => r.found.includes(x)).length / K; dist += r.dist; }
        return [e, rec / qs.length, dist / qs.length];
      });
    }
    function run() {
      const tr = {};
      const r = idx.search(Q, K, ef, del ? ok : null, tr);
      const truth = exactK(P, Q, K, del ? ok : null);
      let s = "";
      for (let j = 0; j < N; j++) for (const e of idx.nb[j][0]) if (e > j) s += `<line x1="${P[j][0]}" y1="${P[j][1]}" x2="${P[e][0]}" y2="${P[e][1]}" stroke="var(--line)" stroke-width="0.5"/>`;
      for (const j of r.visited) s += `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="3.6" fill="var(--accent)" opacity=".35"/>`;
      for (let j = 0; j < N; j++) s += del && DEL[j] ? `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="2" fill="none" stroke="var(--muted)" stroke-width=".8"/>` : `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="2" fill="var(--muted)"/>`;
      for (const [, a, b] of tr.path) s += `<line x1="${P[a][0]}" y1="${P[a][1]}" x2="${P[b][0]}" y2="${P[b][1]}" stroke="var(--signal)" stroke-width="2.2"/>`;
      for (const t of truth) s += `<circle cx="${P[t][0]}" cy="${P[t][1]}" r="5" fill="none" stroke="${r.found.includes(t) ? "var(--good)" : "var(--bad)"}" stroke-width="1.8"/>`;
      s += `<path d="M${Q[0] - 6} ${Q[1]}h12M${Q[0]} ${Q[1] - 6}v12" stroke="var(--signal)" stroke-width="2.4"/>`;
      g("tu-svg").innerHTML = s;
      const hit = truth.filter((t) => r.found.includes(t)).length;
      const deg = P.reduce((a, _, j) => a + idx.nb[j][0].length, 0) / N;
      g("tu-stats").innerHTML = `<div><b>${hit}/${K}</b><small>recall@10 בשאילתה הזו</small></div>
        <div><b>${r.dist}</b><small>מרחקים שחושבו (מדויק: ${N})</small></div>
        <div><b>${deg.toFixed(1)}</b><small>שכנים ממוצע בשכבה 0 (תקרה ${2 * M})</small></div>
        <div><b>${graphBytes(M).toFixed(1)} B</b><small>גרף לצומת לפי הנוסחה; למיליון צמתים ${(graphBytes(M) / 1.048576).toFixed(0)} MB</small></div>`;
      chart();
    }
    function chart() {
      const maxD = Math.max(...curve.map((c) => c[2]), 1);
      const minD = Math.min(...curve.map((c) => c[2])), x = (d) => 36 + ((d - minD) / Math.max(1, maxD - minD)) * 300, y = (r) => 112 - Math.max(0, (r - 0.5) * 2) * 100;
      let s = `<line x1="36" y1="112" x2="350" y2="112" stroke="var(--line)"/><line x1="36" y1="12" x2="36" y2="112" stroke="var(--line)"/>`;
      s += `<text x="4" y="16" font-size="9" fill="var(--muted)">1.0</text><text x="4" y="114" font-size="9" fill="var(--muted)">0.5</text><text x="250" y="126" font-size="9" fill="var(--muted)">avg distances</text>`;
      s += `<polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${curve.map((c) => `${x(c[2])},${y(c[1])}`).join(" ")}"/>`;
      for (const c of curve) {
        const on = c[0] === EFS.reduce((a, b) => (Math.abs(b - ef) < Math.abs(a - ef) ? b : a));
        s += `<circle cx="${x(c[2])}" cy="${y(c[1])}" r="${on ? 5 : 3}" fill="${on ? "var(--signal)" : "var(--accent)"}"/><text x="${x(c[2]) - 6}" y="${y(c[1]) - 7}" font-size="8" fill="var(--muted)">${c[0]}</text>`;
      }
      g("tu-chart").innerHTML = s;
    }
    g("tu-svg").addEventListener("click", (e) => {
      const r = g("tu-svg").getBoundingClientRect();
      Q = [(e.clientX - r.left) / r.width * W, (e.clientY - r.top) / r.height * H]; run();
    });
    g("tu-m").addEventListener("input", (e) => { M = +e.target.value; g("tu-mv").textContent = M; build(); run(); });
    g("tu-c").addEventListener("input", (e) => { efC = +e.target.value; g("tu-cv").textContent = efC; build(); run(); });
    g("tu-e").addEventListener("input", (e) => { ef = +e.target.value; g("tu-ev").textContent = ef; run(); });
    g("tu-del").addEventListener("change", (e) => { del = e.target.checked; measure(); run(); });
    build(); run();
    return () => {};
  };

  /* ================================================================ l11filter */
  window.AIDS["l11filter"] = function (host) {
    style();
    const W = 360, H = 250, N = 400, K = 10;
    host.innerHTML = `<div class="l11">
      <div class="guide"><p><b>מה רואים:</b> 400 מסמכים, ונקודות כחולות הן המסמכים של הלקוח שמחפש. השאר אפורים. השאילתה (הצלב הכתום, <b>לחץ להזזה</b>) מבקשת את 10 המסמכים הקרובים <b>של הלקוח הזה בלבד</b>. ירוק: תוצאה נכונה שחזרה. אדום: תוצאה נכונה שפוספסה. איקס: תוצאה שחזרה אבל אינה בין 10 הנכונות.</p>
      <p><b>האסטרטגיות:</b> post-filter מביא 30 קרובים בלי מסנן מגרף HNSW, ומסנן. pre-filter מחשב מרחק לכל מסמך של הלקוח (מדויק). in-graph הולך בגרף עם efSearch=20 ומחזיר רק מסמכים של הלקוח. planner בוחר pre-filter כשללקוח עד 60 מסמכים, ו-in-graph אחרת.</p></div>
      <div class="l11-row"><span>גודל הלקוח:</span><div class="seg" id="fl-size"><button data-s="2" aria-pressed="true">2%</button><button data-s="10" aria-pressed="false">10%</button><button data-s="25" aria-pressed="false">25%</button><button data-s="50" aria-pressed="false">50% מפוזר</button></div></div>
      <div class="l11-row"><span>אסטרטגיה:</span><div class="seg" id="fl-st"><button data-t="post" aria-pressed="true">post-filter</button><button data-t="pre" aria-pressed="false">pre-filter</button><button data-t="graph" aria-pressed="false">in-graph</button><button data-t="plan" aria-pressed="false">planner</button></div></div>
      <svg viewBox="0 0 ${W} ${H}" id="fl-svg" role="img" aria-label="מסמכים לפי לקוח ושאילתה"></svg>
      <div class="l11-stats" id="fl-stats"></div>
      <div class="l11-cap" id="fl-cap"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const { P, lab } = clusteredPoints(N, 8, W, H, 31, 20);
    const R = rng(8);
    const half = P.map(() => R() < 0.5);
    const MASK = { 2: P.map((_, j) => lab[j] === 0 && j < 64), 10: P.map((_, j) => lab[j] === 1 && j < 320), 25: P.map((_, j) => lab[j] === 2 || lab[j] === 3), 50: half };
    const idx = HNSW(P, 6, 32, 4);
    for (let i = 0; i < N; i++) idx.insert(i);
    let size = 2, st = "post", Q = [300, 60];
    function seg(id, key, cb) { g(id).addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; [...g(id).children].forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false")); cb(b.dataset[key]); run(); }); }
    seg("fl-size", "s", (v) => { size = +v; });
    seg("fl-st", "t", (v) => { st = v; });
    function run() {
      const m = MASK[size], ok = (j) => m[j];
      const allowed = m.filter(Boolean).length;
      const truth = exactK(P, Q, K, ok);
      let found, dist, used = st;
      if (st === "plan") used = allowed <= 60 ? "pre" : "graph";
      if (used === "post") { const r = idx.search(Q, 30, 30); found = r.found.filter(ok).slice(0, K); dist = r.dist; }
      else if (used === "pre") { found = truth.slice(); dist = allowed; }
      else { const r = idx.search(Q, K, 20, ok); found = r.found; dist = r.dist; }
      let s = "";
      for (let j = 0; j < N; j++) s += `<circle cx="${P[j][0]}" cy="${P[j][1]}" r="${m[j] ? 2.6 : 1.8}" fill="${m[j] ? "var(--accent)" : "var(--line)"}"/>`;
      for (const t of truth) s += `<circle cx="${P[t][0]}" cy="${P[t][1]}" r="5" fill="none" stroke="${found.includes(t) ? "var(--good)" : "var(--bad)"}" stroke-width="1.8"/>`;
      for (const f of found) if (!truth.includes(f)) s += `<path d="M${P[f][0] - 4} ${P[f][1] - 4}l8 8M${P[f][0] + 4} ${P[f][1] - 4}l-8 8" stroke="var(--bad)" stroke-width="1.6"/>`;
      s += `<path d="M${Q[0] - 6} ${Q[1]}h12M${Q[0]} ${Q[1] - 6}v12" stroke="var(--signal)" stroke-width="2.4"/>`;
      g("fl-svg").innerHTML = s;
      const hit = truth.filter((t) => found.includes(t)).length;
      const rec = truth.length ? hit / truth.length : 1;
      g("fl-stats").innerHTML = `<div><b>${found.length}/${Math.min(K, allowed)}</b><small>תוצאות שחזרו / שצריכות לחזור</small></div><div><b>${rec.toFixed(2)}</b><small>filtered recall@10</small></div><div><b>${dist}</b><small>מרחקים שחושבו (מתוך ${N})</small></div><div><b>${allowed}</b><small>מסמכים של הלקוח${st === "plan" ? ` · planner בחר ${used === "pre" ? "pre-filter" : "in-graph"}` : ""}</small></div>`;
      const msg = {
        post: found.length < Math.min(K, allowed) ? "post-filter החזיר פחות מ-10: רוב 30 הקרובים שייכים ללקוחות אחרים. מודל השפה יקבל מעט מקורות ויענה \"לא מצאתי\"." : "post-filter עבד כאן, כי ללקוח יש הרבה מסמכים ליד השאילתה. הזז את השאילתה רחוק מהנקודות הכחולות ותראה מה קורה.",
        pre: `pre-filter תמיד נכון: חושב מרחק לכל ${allowed} המסמכים של הלקוח. זול כשהלקוח קטן, ויקר כשהוא חצי מהקורפוס (במיליוני מסמכים זה חיפוש מדויק על מיליונים).`,
        graph: rec < 1 ? "in-graph החזיר תוצאות של הלקוח, אבל לא את הקרובות ביותר: ההליכה בגרף לא הגיעה לאזור של הלקוח. זה הכישלון השקט, ונגדו בנויים filterable HNSW ו-ACORN ב-Qdrant." : "in-graph עבד: המסמכים של הלקוח קרובים למסלול של החיפוש. עכשיו בחר לקוח 2% ושים את השאילתה רחוק ממנו.",
        plan: `ה-planner ספר ${allowed} מסמכים ובחר ${used === "pre" ? "חיפוש מדויק על התת-קבוצה" : "הליכה בגרף"}. זה מה ש-full_scan_threshold של Qdrant וה-planner של PostgreSQL עושים, בהיקף אחר.`,
      };
      g("fl-cap").textContent = msg[st];
    }
    g("fl-svg").addEventListener("click", (e) => { const r = g("fl-svg").getBoundingClientRect(); Q = [(e.clientX - r.left) / r.width * W, (e.clientY - r.top) / r.height * H]; run(); });
    run();
    return () => {};
  };

  /* ================================================================ l11cost */
  window.AIDS["l11cost"] = function (host) {
    style();
    host.innerHTML = `<div class="l11">
      <div class="guide"><p><b>מה רואים:</b> למעלה, ה-RAM של אינדקס HNSW: וקטורים ב-float32 שנשארים בזיכרון, קודים דחוסים וגרף. מתחת, המקוריים שיושבים בדיסק כשיש quantization. למטה, עלות חודשית משוערת לכל אפשרות ב-AWS, מהזולה ליקרה, ומתחת לכל שורה ההנחות שלה. המחירים של us-east-1 מנובמבר 2026, והנוסחאות זהות ל-<code>ragkit/vectors/sizing.py</code>. אלה הערכות לסדרי גודל: לפני החלטה בודקים ב-AWS Pricing Calculator.</p></div>
      <div class="l11-form">
        <label>מספר וקטורים<select id="co-n"><option value="210">210 (Acme היום)</option><option value="100000">100 אלף</option><option value="1000000" selected>מיליון</option><option value="10000000">10 מיליון</option><option value="100000000">100 מיליון</option></select></label>
        <label>ממדים<select id="co-d"><option>384</option><option>768</option><option selected>1024</option><option>1536</option><option>3072</option></select></label>
        <label>quantization<select id="co-q"><option value="none">בלי (float32)</option><option value="float16">float16 / halfvec</option><option value="int8">int8 (scalar)</option><option value="binary">binary</option></select></label>
        <label>M<select id="co-m"><option>8</option><option selected>16</option><option>32</option></select></label>
        <label>שאילתות בחודש<input type="number" id="co-qs" value="100000" min="0" step="10000"></label>
        <label>שעות פעילות בחודש (scale to zero): <b id="co-hv">200</b><input type="range" id="co-h" min="20" max="730" value="200"></label>
      </div>
      <div class="l11-stack" id="co-stack"></div>
      <div class="l11-legend"><span><i style="background:var(--accent)"></i>float32 ב-RAM</span><span><i style="background:var(--good)"></i>קודים דחוסים</span><span><i style="background:var(--signal)"></i>גרף</span></div>
      <div class="l11-stats" id="co-ram"></div>
      <div class="l11-opts" id="co-opts"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const GIB = 1024 ** 3, HRS = 730;
    const PR = { s3: 0.06, put: 0.20, q1k: 0.0025, t1: 0.004, t2: 0.002, t3: 0.0004, ocu: 0.24, aossSt: 0.024, acu: 0.12, aurSt: 0.10, r7l: 0.1071, r7x: 0.2142, gp3: 0.08, pcMin: 50, pcSt: 0.33 };
    const fmt = (b) => (b < GIB ? (b / 1048576).toFixed(1) + " MB" : (b / GIB).toFixed(2) + " GB");
    const usd = (x) => "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    function ram(n, d, m, q) {
      const bpv = { none: 0, float16: 2 * d, int8: d, binary: Math.ceil(d / 8) }[q];
      const vec = q === "none" ? n * d * 4 : 0, codes = n * bpv, graph = n * graphBytes(m);
      return { vec, codes, graph, disk: q === "none" ? 0 : n * d * 4, total: vec + codes + graph };
    }
    function run() {
      const n = +g("co-n").value, d = +g("co-d").value, q = g("co-q").value, m = +g("co-m").value, qs = Math.max(0, +g("co-qs").value || 0), hrs = +g("co-h").value;
      g("co-hv").textContent = hrs;
      const r = ram(n, d, m, q);
      const tot = r.total || 1;
      g("co-stack").innerHTML = `<span style="width:${(r.vec / tot) * 100}%;background:var(--accent)"></span><span style="width:${(r.codes / tot) * 100}%;background:var(--good)"></span><span style="width:${(r.graph / tot) * 100}%;background:var(--signal)"></span>`;
      g("co-ram").innerHTML = `<div><b>${fmt(r.total)}</b><small>RAM של האינדקס</small></div><div><b>${fmt(r.graph)}</b><small>מתוכו גרף (${graphBytes(m).toFixed(1)} B לצומת)</small></div><div><b>${fmt(r.disk)}</b><small>מקוריים בדיסק (ל-rescoring)</small></div><div><b>${fmt(n * d * 4)}</b><small>float32 גולמי, להשוואה</small></div>`;
      // S3 Vectors
      const perVec = d * 4 + 200 + 1500, tb = (d * 4 + 200) / 1024 ** 4;
      const s3store = n * perVec / GIB * PR.s3, s3put = n * perVec / GIB * PR.put * 0.05;
      const perQ = PR.q1k / 1000 + Math.min(n, 1e5) * tb * PR.t1 + Math.max(0, Math.min(n, 1e7) - 1e5) * tb * PR.t2 + Math.max(0, n - 1e7) * tb * PR.t3;
      const opts = [];
      opts.push({ o: "S3 Vectors", t: s3store + s3put + qs * perQ, a: `storage ${usd(s3store)} + queries ${usd(qs * perQ)} (${usd(perQ * 1000)} per 1k); no idle cost; ~100 ms warm, <1 s cold; no hybrid` });
      const searchOcu = Math.max(1, Math.ceil(r.total / (3 * GIB))), ocu = searchOcu + 1;
      const aossSt = n * perVec / GIB * PR.aossSt;
      opts.push({ o: "OpenSearch Serverless (classic)", t: Math.max(ocu, 2) * HRS * PR.ocu + aossSt, a: `${Math.max(ocu, 2)} OCUs x 730 h (assumes ~3 GiB of index per 6 GiB OCU); min 2 OCUs` });
      opts.push({ o: "OpenSearch Serverless (NextGen)", t: ocu * hrs * PR.ocu + aossSt, a: `${ocu} OCUs x ${hrs} active h; scales to zero after 10 idle min; ~10 s cold start` });
      const aurRam = q === "float16" ? r.total : ram(n, d, m, "none").total;
      const acu = Math.max(0.5, Math.ceil(aurRam / (2 * GIB * 0.6) * 2) / 2);
      opts.push({ o: "Aurora Serverless + pgvector" + (q === "float16" ? " (halfvec)" : ""), t: acu * HRS * PR.acu + (n * perVec / GIB + aurRam / GIB) * PR.aurSt, a: `${acu} ACU always on (index in ~60% of 2 GiB/ACU); float32 unless you pick float16 (halfvec); I/O not included` });
      const need = r.total * 1.5;
      const nodes = need <= 12 * GIB ? 1 : Math.max(1, Math.ceil(need / (26 * GIB)));
      const inst = need <= 12 * GIB ? ["r7g.large", PR.r7l] : ["r7g.xlarge", PR.r7x];
      const disk = Math.max(20, 2 * n * perVec / GIB);
      opts.push({ o: `EC2 + Qdrant (${nodes} x ${inst[0]})`, t: nodes * inst[1] * HRS + disk * PR.gp3, a: `index x1.5 headroom in RAM; ${disk.toFixed(0)} GB gp3; no replica, backups or ops time` });
      opts.push({ o: "Pinecone Standard (not AWS)", t: Math.max(PR.pcMin, n * perVec / GIB * PR.pcSt), a: "$50 monthly minimum + storage; read/write units not modelled" });
      opts.sort((a, b) => a.t - b.t);
      const max = Math.max(...opts.map((x) => x.t));
      g("co-opts").innerHTML = opts.map((x, i) => `<div class="l11-opt ${i === 0 ? "best" : ""}"><div class="top"><span>${x.o}</span><b>${usd(x.t)} / חודש</b></div><div class="bar" style="width:${Math.max(0.5, Math.sqrt(x.t / max) * 100)}%"></div><small>${x.a}</small></div>`).join("") + `<div class="l11-src">אורך הפס הוא שורש העלות, כדי שגם האפשרויות הזולות ייראו. כל אפשרות חוץ מ-S3 Vectors גובה כסף גם בסרק: אחרי ניסוי, teardown.</div>`;
    }
    host.querySelectorAll("select, input").forEach((el) => el.addEventListener("input", run));
    run();
    return () => {};
  };
})();
