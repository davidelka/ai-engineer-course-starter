// Lesson 21 aids: image -> tokens animation (3 providers), image cost calculator,
// voice latency budget timeline, Hebrew WER calculator.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function addL21Style() {
  if (document.getElementById("l21-style")) return;
  const st = document.createElement("style");
  st.id = "l21-style";
  st.textContent = `
  .l21 { display: grid; gap: 12px; min-width: 0; }
  .l21 p { margin: 0; line-height: 1.7; }
  .l21-stage { position: relative; width: 100%; background: var(--code-bg); border: 1px solid var(--line); border-radius: 10px;
    overflow: hidden; direction: ltr; }
  .l21-img { position: absolute; left: 0; top: 0; background: var(--surface); border: 1px solid var(--line); transition: all .6s ease; overflow: hidden; }
  .l21-img .bar { position: absolute; left: 0; right: 0; top: 0; height: 9%; background: var(--accent-soft); border-bottom: 1px solid var(--line); }
  .l21-img .blk { position: absolute; background: var(--line); border-radius: 2px; }
  .l21-img .err { position: absolute; background: var(--bad-soft); border: 1px solid var(--bad); border-radius: 3px; }
  .l21-frame { position: absolute; left: 0; top: 0; border: 2px dashed var(--signal); transition: all .6s ease; pointer-events: none; }
  .l21-grid { position: absolute; left: 0; top: 0; pointer-events: none; transition: opacity .5s; opacity: 0; }
  .l21-hot { position: absolute; background: var(--accent); opacity: .85; transition: opacity .3s; border-radius: 1px; }
  .l21-vec { position: absolute; right: 8px; bottom: 8px; font-family: var(--mono); font-size: .72rem; background: var(--surface);
    border: 1px solid var(--accent); border-radius: 8px; padding: 4px 8px; opacity: 0; transition: opacity .4s; max-width: 60%; }
  .l21-levels { position: absolute; inset: 0; display: grid; place-items: center; opacity: 0; transition: opacity .5s; }
  .l21-levels div { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; padding: 8px; }
  .l21-levels span { font-family: var(--mono); font-size: .76rem; padding: 4px 8px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); }
  .l21-levels span.on { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .l21-cap { border-inline-start: 3px solid var(--signal); padding: 6px 12px; background: var(--surface); border-radius: 0 8px 8px 0; min-height: 76px; }
  .l21-nums { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; direction: ltr; }
  .l21-nums div { border: 1px solid var(--line); border-radius: 8px; padding: 6px; text-align: center; background: var(--surface); min-width: 0; }
  .l21-nums small { display: block; color: var(--muted); font-size: .7rem; }
  .l21-nums b { font-family: var(--mono); font-size: .9rem; overflow-wrap: anywhere; }
  .l21-legrow { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 5px 10px;
    border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
  .l21-legrow.ok { border-color: var(--good); background: var(--good-soft); }
  .l21-legrow.bad { border-color: var(--bad); background: var(--bad-soft); }
  .l21-legrow b { font-family: var(--mono); }
  .l21-in { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .l21-in label { display: grid; gap: 2px; font-size: .84rem; color: var(--muted); }
  .l21-in input { font: inherit; font-family: var(--mono); font-size: .9rem; color: var(--ink); background: var(--surface);
    border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; width: 100%; direction: ltr; }
  .l21 input[type=range] { width: 100%; }
  .l21-tl { display: grid; gap: 6px; direction: ltr; }
  .l21-tlrow { display: grid; grid-template-columns: 5.6rem minmax(0, 1fr); gap: 8px; align-items: center; font-size: .78rem; }
  .l21-tlrow > span { font-family: var(--mono); color: var(--muted); text-align: left; }
  .l21-track { position: relative; height: 22px; background: var(--code-bg); border-radius: 5px; }
  .l21-seg { position: absolute; top: 3px; bottom: 3px; border-radius: 4px; transition: all .35s; }
  .l21-seg.s-stt { background: var(--accent); } .l21-seg.s-llm { background: var(--signal); } .l21-seg.s-tts { background: var(--good); }
  .l21-seg.s-play { background: repeating-linear-gradient(135deg, var(--good) 0 4px, transparent 4px 8px); border: 1px solid var(--good); }
  .l21-mark { position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--ink); }
  .l21-budget { position: absolute; top: 0; bottom: 0; width: 0; border-left: 2px dashed var(--bad); pointer-events: none; }
  .l21-axis { position: relative; height: 16px; font-family: var(--mono); font-size: .68rem; color: var(--muted); }
  .l21-axis span { position: absolute; transform: translateX(-50%); }
  .l21-big { display: flex; flex-wrap: wrap; gap: 6px 18px; align-items: baseline; }
  .l21-big b { font-family: var(--mono); font-size: 1.25rem; }
  .l21-big .ok { color: var(--good); } .l21-big .bad { color: var(--bad); }
  .l21 textarea { font: inherit; font-size: .95rem; color: var(--ink); background: var(--surface); border: 1px solid var(--line);
    border-radius: 8px; padding: 6px 8px; width: 100%; min-height: 3.2em; direction: rtl; resize: vertical; }
  .l21-words { display: flex; flex-wrap: wrap; gap: 6px; direction: rtl; }
  .l21-w { border: 1px solid var(--line); border-radius: 8px; padding: 3px 8px; background: var(--surface); font-size: .95rem; display: grid; text-align: center; }
  .l21-w small { font-size: .68rem; color: var(--muted); font-family: var(--mono); direction: ltr; }
  .l21-w.sub { border-color: var(--signal); background: var(--signal-soft); }
  .l21-w.del { border-color: var(--bad); background: var(--bad-soft); text-decoration: line-through; }
  .l21-w.ins { border-color: var(--accent); background: var(--accent-soft); }
  .l21-norm { font-size: .88rem; display: grid; gap: 2px; }
  .l21-norm code { direction: rtl; unicode-bidi: plaintext; }
  .l21-checks { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .86rem; }
  .l21-checks label { display: inline-flex; gap: 6px; align-items: center; }
  .l21 select { font: inherit; font-size: .88rem; color: var(--ink); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; width: 100%; max-width: 100%; }
  @media (max-width: 520px) { .l21-nums { grid-template-columns: repeat(2, minmax(0, 1fr)); } .l21-tlrow { grid-template-columns: 4.4rem minmax(0, 1fr); } }
  `;
  document.head.appendChild(st);
})();

/* ---------------- token formulas (same rules as llmkit/media.py, Nov 2026) ---------------- */
const L21 = {
  aTier(model) { const m = /-(\d+)-(\d+)(?:-|$)/.exec(model); if (!m) return "high"; return (+m[1] > 4 || (+m[1] === 4 && +m[2] >= 7)) ? "high" : "standard"; },
  aTok(w, h) { return Math.ceil(w / 28) * Math.ceil(h / 28); },
  anthropic(w, h, model) {
    const tier = L21.aTier(model), [maxLong, maxTok] = tier === "high" ? [2576, 4784] : [1568, 1568];
    const long = Math.max(w, h), short = Math.min(w, h);
    let rw = w, rh = h;
    if (!(long <= maxLong && L21.aTok(w, h) <= maxTok)) {
      let nl = Math.floor(Math.min(long, maxLong) / 28) * 28, ns;
      for (;;) { ns = Math.max(1, Math.round(short * nl / long)); if (L21.aTok(nl, ns) <= maxTok || nl <= 28) break; nl -= 28; }
      [rw, rh] = w >= h ? [nl, ns] : [ns, nl];
    }
    return { tokens: L21.aTok(rw, rh), w: rw, h: rh, patch: 28, how: `${tier} tier: ceil(${rw}/28) × ceil(${rh}/28) = ${Math.ceil(rw / 28)} × ${Math.ceil(rh / 28)}` };
  },
  fit(w, h, m) { const s = Math.min(1, m / w, m / h); return s < 1 ? [Math.max(1, Math.floor(w * s)), Math.max(1, Math.floor(h * s))] : [w, h]; },
  openai(w, h, model, detail) {
    if (model === "gpt-4o") {
      if (detail === "low") { const [a, b] = L21.fit(w, h, 512); return { tokens: 85, w: a, h: b, patch: 512, how: "tiles: detail=low costs the base 85" }; }
      let [rw, rh] = L21.fit(w, h, 2048);
      if (Math.min(rw, rh) > 768) { const s = 768 / Math.min(rw, rh); rw = Math.floor(rw * s); rh = Math.floor(rh * s); }
      const t = Math.ceil(rw / 512) * Math.ceil(rh / 512);
      return { tokens: 85 + 170 * t, w: rw, h: rh, patch: 512, how: `tiles: 85 + ${t} × 170` };
    }
    const rules = { low: [2048, 6144], high: [2048, 2500], original: [6000, 10000] };
    const d = detail === "auto" || !detail ? "high" : detail;
    const [maxDim, budget] = rules[d];
    let [rw, rh] = L21.fit(w, h, maxDim);
    let p = Math.ceil(rw / 32) * Math.ceil(rh / 32);
    if (p > budget) {
      let s = Math.sqrt(budget * 1024 / (rw * rh)), nw, nh;
      for (;;) { nw = Math.max(1, Math.floor(rw * s)); nh = Math.max(1, Math.floor(rh * s)); if (Math.ceil(nw / 32) * Math.ceil(nh / 32) <= budget) break; s *= 0.99; }
      rw = nw; rh = nh; p = Math.ceil(rw / 32) * Math.ceil(rh / 32);
    }
    return { tokens: Math.ceil(p * 1.2), w: rw, h: rh, patch: 32, how: `patches: ceil(${rw}/32) × ceil(${rh}/32) = ${p} × 1.2 (detail=${d})` };
  },
  gemini(w, h, model, level) {
    if (model.startsWith("gemini-2")) {
      if (w <= 384 && h <= 384) return { tokens: 258, w, h, patch: null, how: "both sides ≤ 384 px: 258" };
      const crop = Math.max(256, Math.min(768, Math.floor(Math.min(w, h) / 1.5)));
      const t = Math.ceil(w / crop) * Math.ceil(h / crop);
      return { tokens: 258 * t, w, h, patch: null, how: `crop ${crop}: ${Math.ceil(w / crop)} × ${Math.ceil(h / crop)} tiles × 258` };
    }
    const L = { low: 280, medium: 560, high: 1120, ultra_high: 2240 };
    const tok = L[level] || 1120;
    return { tokens: tok, w, h, patch: null, how: `fixed budget per image: media_resolution=${level || "default"} → ${tok}` };
  },
  PRICE: { "claude-haiku-5-5": 0.10, "claude-haiku-4-5": 1.00, "gpt-5.4-mini": 0.75, "gemini-3.6-flash": 1.50 },
  money(tokens, model, per) { const p = L21.PRICE[model]; return p == null ? "—" : "$" + (tokens * p / 1e6 * per).toFixed(per >= 1000 ? 2 : 4); },
};

function l21Stepper(host, n, draw, ms) {
  let i = 0, timer = null;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let playing = !reduce;
  const btn = host.querySelector("[data-play]"), ctr = host.querySelector("[data-ctr]");
  function show() { draw(i); if (ctr) ctr.textContent = `${i + 1} / ${n}`; if (btn) btn.textContent = playing ? "השהה" : "נגן"; }
  function arm() { clearInterval(timer); if (playing) timer = setInterval(() => { i = (i + 1) % n; show(); }, ms); }
  host.querySelector("[data-next]").addEventListener("click", () => { playing = false; arm(); i = (i + 1) % n; show(); });
  host.querySelector("[data-prev]").addEventListener("click", () => { playing = false; arm(); i = (i - 1 + n) % n; show(); });
  btn.addEventListener("click", () => { playing = !playing; arm(); show(); });
  show(); arm();
  return { reset() { i = 0; show(); }, stop() { clearInterval(timer); }, redraw() { show(); } };
}

/* ---------------- animation: image -> tokens, per provider ---------------- */
window.AIDS["l21tiles"] = function (host) {
  const W0 = 1920, H0 = 1080;
  const P = {
    anthropic: { label: "Claude Haiku 5.5", model: "claude-haiku-5-5", est: () => L21.anthropic(W0, H0, "claude-haiku-5-5") },
    anthropic4: { label: "Claude Haiku 4.5", model: "claude-haiku-4-5", est: () => L21.anthropic(W0, H0, "claude-haiku-4-5") },
    openai: { label: "gpt-5.4-mini (high)", model: "gpt-5.4-mini", est: () => L21.openai(W0, H0, "gpt-5.4-mini", "high") },
    gemini: { label: "Gemini 3.6 Flash", model: "gemini-3.6-flash", est: () => L21.gemini(W0, H0, "gemini-3.6-flash", null) },
  };
  let prov = "anthropic";
  host.innerHTML = `<div class="l21">
    <div class="seg" role="group" aria-label="ספק">${Object.entries(P).map(([k, v]) => `<button aria-pressed="${k === prov}" data-p="${k}">${esc(v.label)}</button>`).join("")}</div>
    <div class="l21-stage" id="tl-stage">
      <div class="l21-img" id="tl-img"><div class="bar"></div>
        <div class="blk" style="left:6%;top:16%;width:22%;height:70%"></div>
        <div class="blk" style="left:32%;top:16%;width:62%;height:6%"></div>
        <div class="blk" style="left:32%;top:26%;width:50%;height:3%"></div>
        <div class="blk" style="left:32%;top:31%;width:55%;height:3%"></div>
        <div class="err" style="left:40%;top:44%;width:36%;height:30%"></div>
        <div class="blk" style="left:44%;top:52%;width:26%;height:2.4%"></div>
        <div class="blk" style="left:44%;top:57%;width:18%;height:1.6%"></div>
      </div>
      <div class="l21-grid" id="tl-grid"></div>
      <div class="l21-frame" id="tl-frame"></div>
      <div id="tl-hot"></div>
      <div class="l21-levels" id="tl-lv"><div>${["low 280", "medium 560", "high 1120 (default)", "ultra_high 2240"].map((x, i) => `<span data-lv="${i}">${x}</span>`).join("")}</div></div>
      <div class="l21-vec" id="tl-vec"></div>
    </div>
    <div class="row"><button class="btn small" data-prev>→ הקודם</button><button class="btn small primary" data-play>השהה</button><button class="btn small" data-next>הבא ←</button><span class="muted" data-ctr></span></div>
    <div class="l21-nums" id="tl-nums"></div>
    <div class="l21-cap" id="tl-cap"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  const stage = g("tl-stage");
  function geom() {
    const sw = stage.clientWidth || 320;
    const disp = sw - 16, scale = disp / W0;
    stage.style.height = Math.round(H0 * scale + 16) + "px";
    return { scale, ox: 8, oy: 8 };
  }
  const CAP = {
    anthropic: [
      "<b>1. המקור:</b> צילום מסך של 1920 על 1080 פיקסלים, כמו שנשמר בקובץ. Claude לא מעביר את כל הפיקסלים כמו שהם: קודם הוא בודק אם התמונה בתוך הגבולות.",
      "<b>2. הקטנה:</b> ב-Haiku 5.5 (רמה גבוהה, Claude 4.7 ואילך) הגבול הוא צלע של 2576 פיקסלים ו-4784 טוקנים. 1920x1080 נכנס בגבולות, ולכן <b>אין הקטנה</b>: המסגרת המקווקוות זהה לתמונה. נסה את Haiku 4.5 כדי לראות הקטנה.",
      "<b>3. חיתוך לריבועים:</b> רשת של ריבועים של 28 על 28 פיקסלים. 1920/28 הם 68.6, ולכן 69 עמודות, ו-1080/28 הם 38.6, ולכן 39 שורות. ריבוע חלקי בקצה נספר כשלם.",
      "<b>4. כל ריבוע הוא טוקן:</b> כל ריבוע עובר דרך ה-vision encoder והופך לווקטור, כמו מילה. המונה סופר: 69 כפול 39.",
      "<b>5. החשבון:</b> הטוקנים מחויבים כטוקני קלט. ב-Haiku 5.5, במחיר של 0.10 דולר למיליון, אלף צילומי מסך כאלה עולים בערך 27 סנט.",
    ],
    anthropic4: [
      "<b>1. המקור:</b> אותו צילום מסך של 1920 על 1080 פיקסלים.",
      "<b>2. הקטנה:</b> ב-Haiku 4.5 (רמה רגילה) הגבול הוא צלע של 1568 פיקסלים ו-1568 טוקנים. התמונה מוקטנת עד שגם הצלע וגם מספר הטוקנים בתוך הגבול: <b>1456x819</b>. טקסט של 12 פיקסלים במקור הופך לפחות מ-9.",
      "<b>3. חיתוך לריבועים:</b> ריבועים של 28 פיקסלים על התמונה <b>המוקטנת</b>: 52 עמודות ו-30 שורות.",
      "<b>4. כל ריבוע הוא טוקן:</b> 52 כפול 30, כלומר 1,560 טוקנים, קצת מתחת לגבול של 1568.",
      "<b>5. החשבון:</b> פחות טוקנים מ-Haiku 5.5, אבל המחיר לטוקן גבוה פי עשרה (1.00 דולר למיליון), ולכן אלף צילומים עולים כ-1.56 דולר. וגם רואים פחות פרטים.",
    ],
    openai: [
      "<b>1. המקור:</b> אותו צילום מסך של 1920 על 1080.",
      "<b>2. הקטנה:</b> ב-gpt-5.4-mini ברמת high, קודם מכניסים לגבול של 2048 פיקסלים (נכנס), ואז סופרים ריבועים של 32: 60 כפול 34, כלומר 2,040, בתוך התקציב של 2,500. לכן <b>אין הקטנה</b>.",
      "<b>3. חיתוך לריבועים:</b> הריבועים כאן גדולים יותר, 32 על 32. 60 עמודות ו-34 שורות.",
      "<b>4. ריבוע כפול מקדם:</b> 2,040 ריבועים כפול המקדם של המודל (1.2 במשפחת gpt-5.x), כלומר 2,448 טוקנים.",
      "<b>5. החשבון:</b> במחיר של 0.75 דולר למיליון, אלף צילומים עולים כ-1.84 דולר. תמונה גדולה יותר הייתה מוקטנת לתקציב של 2,500 ריבועים.",
    ],
    gemini: [
      "<b>1. המקור:</b> אותו צילום מסך של 1920 על 1080.",
      "<b>2. אין חשבון לפי גודל:</b> ב-Gemini 3 ואילך יש לכל תמונה תקציב קבוע לפי media_resolution. Google לא מתעדת לאיזה גודל התמונה מוקטנת בפנים, ולכן אין כאן מסגרת.",
      "<b>3. רמות במקום רשת:</b> low 280, medium 560, high 1120 (ברירת המחדל), ו-ultra_high 2240 (רק לכל תמונה בנפרד). את הרמה קובעים ב-mediaResolution של ה-part.",
      "<b>4. הטוקנים:</b> 1,120 טוקנים, בלי קשר לגודל. תמונה של 320x240 עולה אותו דבר כמו צילום 4K.",
      "<b>5. החשבון:</b> במחיר של 1.50 דולר למיליון, אלף תמונות עולות כ-1.68 דולר. לתמונות גדולות מאוד זה זול, לתמונות קטנות זה יקר. ברמת low זה רבע.",
    ],
  };
  let hotTimer = null;
  function draw(i) {
    const { scale, ox, oy } = geom();
    const est = P[prov].est();
    const img = g("tl-img"), frame = g("tl-frame"), grid = g("tl-grid"), vec = g("tl-vec"), lv = g("tl-lv"), hot = g("tl-hot");
    Object.assign(img.style, { left: ox + "px", top: oy + "px", width: W0 * scale + "px", height: H0 * scale + "px" });
    const isG = prov === "gemini";
    const fw = (i >= 1 ? est.w : W0) * scale, fh = (i >= 1 ? est.h : H0) * scale;
    Object.assign(frame.style, { left: ox + "px", top: oy + "px", width: fw + "px", height: fh + "px", opacity: isG ? 0 : 1 });
    // the image visibly shrinks to the resized frame from step 2 on
    if (i >= 1 && !isG) Object.assign(img.style, { width: fw + "px", height: fh + "px" });
    const cell = est.patch ? est.patch * scale : 0;
    Object.assign(grid.style, { left: ox + "px", top: oy + "px", width: fw + "px", height: fh + "px",
      opacity: !isG && i >= 2 ? 1 : 0,
      backgroundImage: cell ? `linear-gradient(to right, var(--accent) 1px, transparent 1px), linear-gradient(to bottom, var(--accent) 1px, transparent 1px)` : "none",
      backgroundSize: cell ? `${cell}px ${cell}px` : "auto" });
    lv.style.opacity = isG && i >= 2 ? 1 : 0;
    lv.querySelectorAll("span").forEach((s) => s.classList.toggle("on", s.dataset.lv === "2"));
    clearInterval(hotTimer);
    hot.innerHTML = "";
    vec.style.opacity = 0;
    let shown = i >= 4 ? est.tokens : 0;
    if (i === 3 && !isG && cell) {
      const cols = Math.ceil(est.w / est.patch), rows = Math.ceil(est.h / est.patch), total = cols * rows;
      let k = 0;
      vec.style.opacity = 1;
      const step = Math.max(1, Math.round(total / 40));
      hotTimer = setInterval(() => {
        k = Math.min(total, k + step);
        const c = (k - 1) % cols, r = Math.floor((k - 1) / cols);
        hot.innerHTML = `<div class="l21-hot" style="left:${ox + c * cell}px;top:${oy + r * cell}px;width:${Math.max(2, cell)}px;height:${Math.max(2, cell)}px"></div>`;
        const t = prov === "openai" ? Math.ceil(k * 1.2) : k;
        vec.textContent = `patch ${k} → [${(Math.sin(k) * .9).toFixed(2)}, ${(Math.cos(k * 1.7) * .9).toFixed(2)}, …]  tokens: ${t}`;
        nums(t);
        if (k >= total) clearInterval(hotTimer);
      }, 90);
      shown = 0;
    } else if (i === 3 && isG) { shown = est.tokens; }
    function nums(t) {
      g("tl-nums").innerHTML = `<div><small>original</small><b>${W0}×${H0}</b></div>
        <div><small>seen as</small><b>${isG ? "?" : (i >= 1 ? `${est.w}×${est.h}` : "—")}</b></div>
        <div><small>tokens</small><b>${t ? t.toLocaleString("en-US") : "—"}</b></div>
        <div><small>per 1,000 images</small><b>${i >= 4 ? L21.money(est.tokens, P[prov].model, 1000) : "—"}</b></div>`;
    }
    nums(shown);
    g("tl-cap").innerHTML = CAP[prov][i] + (i >= 3 ? `<br><span class="muted" dir="ltr" style="font-family:var(--mono);font-size:.78rem">${esc(est.how)}</span>` : "");
  }
  const ctl = l21Stepper(host, 5, draw, 5600);
  host.querySelectorAll("[data-p]").forEach((b) => b.addEventListener("click", () => {
    prov = b.dataset.p;
    host.querySelectorAll("[data-p]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    ctl.reset();
  }));
  const onResize = () => ctl.redraw();
  window.addEventListener("resize", onResize);
  return () => { ctl.stop(); clearInterval(hotTimer); window.removeEventListener("resize", onResize); };
};

/* ---------------- sim: image cost calculator ---------------- */
window.AIDS["l21cost"] = function (host) {
  const PRE = [["צילום טלפון", 4032, 3024], ["צילום מסך 1080p", 1920, 1080], ["צילום מסך 4K", 3840, 2160], ["סריקת A4 ב-150dpi", 1240, 1754],
    ["הקבלה של המעבדה", 900, 1800], ["הלוח של המעבדה", 2400, 1600], ["דיאלוג השגיאה", 1280, 800], ["תמונה ממוזערת", 320, 240]];
  const TGT = [
    ["Claude Haiku 5.5", "anthropic", "claude-haiku-5-5", []], ["Claude Haiku 4.5", "anthropic", "claude-haiku-4-5", []],
    ["gpt-5.4-mini", "openai", "gpt-5.4-mini", ["low", "high", "original"]], ["gpt-4o", "openai", "gpt-4o", ["low", "high"]],
    ["Gemini 3.6 Flash", "gemini", "gemini-3.6-flash", ["low", "medium", "high", "ultra_high"]], ["Gemini 2.5 Flash", "gemini", "gemini-2.5-flash", []],
  ];
  let w = 900, h = 1800, pre = 100, ti = 0, detail = { "gpt-5.4-mini": "high", "gpt-4o": "high", "gemini-3.6-flash": "high" };
  host.innerHTML = `<div class="l21">
    <div class="guide"><p><b>מה רואים:</b> תמונה בגודל שבחרת, ומה ספק אחד עושה איתה. <b>"הקטנה מראש"</b> היא מה שאתה עושה לפני השליחה (כמו prepare_image במעבדה). <b>"נראה כ-"</b> הוא הגודל אחרי ההקטנה של הספק, כלומר מה שהמודל באמת רואה. הטוקנים מחושבים בדיוק כמו ב-llmkit/media.py, והעלות לפי המחירים ב-llmkit/pricing.py (למודלים שאין להם מחיר שם, מוצגים רק טוקנים).</p>
    <p><b>שורות הקריאות:</b> לכל גודל אות במקור (בפיקסלים), גובה האות אחרי שתי ההקטנות. מתחת ל-9 פיקסלים בערך טקסט הופך לא אמין, ושורה הופכת לאדומה. ב-Gemini 3 הגודל הפנימי לא מתועד, ולכן אין שם שורות קריאות.</p></div>
    <label class="knob"><span>תמונה לדוגמה</span><select id="cc-pre">${PRE.map((p, i) => `<option value="${i}" ${i === 4 ? "selected" : ""}>${esc(p[0])} (${p[1]}×${p[2]})</option>`).join("")}</select></label>
    <div class="l21-in"><label>רוחב (px)<input type="number" id="cc-w" min="1" max="20000" value="${w}"></label><label>גובה (px)<input type="number" id="cc-h" min="1" max="20000" value="${h}"></label></div>
    <label class="knob"><div class="knob-head"><span>הקטנה מראש (הצלע הארוכה)</span><b id="cc-prev"></b></div><input type="range" id="cc-pr" min="10" max="100" step="1" value="100"></label>
    <div class="seg" id="cc-t" role="group" aria-label="מודל">${TGT.map((t, i) => `<button aria-pressed="${i === ti}" data-t="${i}">${esc(t[0])}</button>`).join("")}</div>
    <div class="seg" id="cc-d" role="group" aria-label="detail"></div>
    <div class="l21-nums" id="cc-n"></div>
    <div class="muted" id="cc-how" dir="ltr" style="font-family:var(--mono);font-size:.78rem;text-align:left"></div>
    <div class="stack" id="cc-leg" style="gap:6px"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  function draw() {
    const t = TGT[ti];
    const s = pre / 100, long0 = Math.max(w, h);
    const pw = Math.max(1, Math.round(w * s)), ph = Math.max(1, Math.round(h * s));
    g("cc-prev").textContent = `${Math.max(pw, ph)} px (${pre}%)`;
    const d = detail[t[2]];
    g("cc-d").innerHTML = t[3].length ? t[3].map((x) => `<button aria-pressed="${x === d}" data-d="${x}">${t[1] === "gemini" ? "media_resolution: " : "detail: "}${x}</button>`).join("") : "";
    let est;
    if (t[1] === "anthropic") est = L21.anthropic(pw, ph, t[2]);
    else if (t[1] === "openai") est = L21.openai(pw, ph, t[2], d);
    else est = L21.gemini(pw, ph, t[2], t[2].startsWith("gemini-2") ? null : d);
    const fixed = t[2] === "gemini-3.6-flash";
    g("cc-n").innerHTML = `<div><small>sent</small><b>${pw}×${ph}</b></div><div><small>seen as</small><b>${fixed ? "?" : `${est.w}×${est.h}`}</b></div>
      <div><small>tokens</small><b>${est.tokens.toLocaleString("en-US")}</b></div><div><small>per 1,000</small><b>${L21.money(est.tokens, t[2], 1000)}</b></div>`;
    g("cc-how").textContent = est.how;
    const seenLong = Math.max(est.w, est.h);
    g("cc-leg").innerHTML = fixed ? `<div class="l21-legrow"><span>Gemini 3: תקציב קבוע. Google לא מתעדת לאיזה גודל התמונה מוקטנת בפנים, ולכן אי אפשר לחשב כאן קריאות. מדוד על התמונות שלך.</span></div>`
      : [13, 17, 20, 24, 30].map((f) => {
        const eff = f * seenLong / long0;
        const ok = eff >= 9;
        return `<div class="l21-legrow ${ok ? "ok" : "bad"}"><span>אות של ${f} פיקסלים במקור → <b>${eff.toFixed(1)} px</b> אחרי ההקטנות</span><span>${ok ? "קריא" : "בסיכון"}</span></div>`;
      }).join("");
    g("cc-d").querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => { detail[t[2]] = b.dataset.d; draw(); }));
  }
  g("cc-pre").addEventListener("change", (e) => { const p = PRE[+e.target.value]; w = p[1]; h = p[2]; g("cc-w").value = w; g("cc-h").value = h; pre = 100; g("cc-pr").value = 100; draw(); });
  g("cc-w").addEventListener("input", (e) => { w = Math.max(1, Math.min(20000, +e.target.value || 1)); draw(); });
  g("cc-h").addEventListener("input", (e) => { h = Math.max(1, Math.min(20000, +e.target.value || 1)); draw(); });
  g("cc-pr").addEventListener("input", (e) => { pre = +e.target.value; draw(); });
  g("cc-t").querySelectorAll("[data-t]").forEach((b) => b.addEventListener("click", () => {
    ti = +b.dataset.t; g("cc-t").querySelectorAll("[data-t]").forEach((x) => x.setAttribute("aria-pressed", x === b)); draw();
  }));
  draw();
};

/* ---------------- sim: voice latency budget ---------------- */
window.AIDS["l21voice"] = function (host) {
  const K = [
    ["stt", "STT (תמלול המשפט)", 0.05, 1.5, 0.05, 0.45, "s"],
    ["ttft", "LLM: זמן עד הטוקן הראשון", 0.1, 2.0, 0.05, 0.5, "s"],
    ["tps", "LLM: מהירות כתיבה", 20, 150, 5, 60, "tok/s"],
    ["first", "אורך המשפט הראשון", 4, 40, 1, 12, "tokens"],
    ["total", "אורך התשובה כולה", 20, 150, 5, 60, "tokens"],
    ["ttfb", "TTS: זמן עד הבייט הראשון", 0.05, 1.0, 0.05, 0.25, "s"],
    ["net", "רשת והשמעה", 0, 0.4, 0.02, 0.1, "s"],
  ];
  const v = Object.fromEntries(K.map((k) => [k[0], k[5]]));
  let mode = "streaming";
  const BUDGET = 1.0;
  host.innerHTML = `<div class="l21">
    <div class="guide"><p><b>מה רואים:</b> ציר זמן של תור אחד, מהרגע שהתלמיד הפסיק לדבר (0 שניות). כל שורה היא שלב: <b>STT</b> בכחול, <b>LLM</b> בכתום (הקו השחור הראשון הוא הטוקן הראשון, השני הוא סוף המשפט הראשון), <b>TTS</b> בירוק (עד הבייט הראשון של כל קטע), ו<b>השמעה</b> בפסים. הקו האדום המקווקו הוא תקציב של שנייה אחת לאודיו הראשון.</p>
    <p><b>שני המצבים:</b> ב<b>רציף</b> ה-TTS מתחיל רק אחרי שה-LLM סיים את כל התשובה. ב-<b>streaming</b> המשפט הראשון נשלח ל-TTS ברגע שהוא נגמר, וה-LLM ממשיך לכתוב במקביל. ההשמעה מניחה דיבור של כ-3.5 טוקנים לשנייה, ולכן היא נמשכת הרבה אחרי סוף הציר: הציר מציג רק את החלק שקובע את ההשהיה, ופסי ההשמעה נחתכים בקצה. זה מודל פשוט, אבל אותם שלבים נמדדים בתרגיל 7 עם קוד אמיתי.</p></div>
    <div class="seg" role="group" aria-label="מצב"><button aria-pressed="false" data-m="sequential">רציף</button><button aria-pressed="true" data-m="streaming">streaming</button></div>
    <div class="l21-big" id="lv-big"></div>
    <div class="l21-tl" id="lv-tl"></div>
    <div class="stack" style="gap:8px">${K.map((k) => `<label class="knob"><div class="knob-head"><span>${k[1]}</span><b id="lv-v-${k[0]}"></b></div><input type="range" data-k="${k[0]}" min="${k[2]}" max="${k[3]}" step="${k[4]}" value="${k[5]}"></label>`).join("")}</div>
    <div class="callout" id="lv-tip"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  function compute() {
    const sttEnd = v.stt;
    const firstTok = sttEnd + v.ttft;
    const firstSent = firstTok + Math.min(v.first, v.total) / v.tps;
    const llmEnd = firstTok + v.total / v.tps;
    const speak = (tok) => tok / 3.5;
    let ttsStart, firstAudio, end, play;
    if (mode === "sequential") {
      ttsStart = llmEnd; firstAudio = llmEnd + v.ttfb + v.net;
      end = firstAudio + speak(v.total); play = [[firstAudio, end]];
    } else {
      ttsStart = firstSent; firstAudio = firstSent + v.ttfb + v.net;
      const p1 = firstAudio + speak(Math.min(v.first, v.total));
      const restReady = llmEnd + v.ttfb + v.net; // the rest is synthesized after the LLM finishes
      const p2s = Math.max(p1, restReady), p2e = p2s + speak(Math.max(0, v.total - v.first));
      end = p2e; play = [[firstAudio, p1], [p2s, p2e]];
    }
    return { sttEnd, firstTok, firstSent, llmEnd, ttsStart, firstAudio, end, play };
  }
  function draw() {
    K.forEach((k) => { g("lv-v-" + k[0]).textContent = `${v[k[0]]} ${k[6]}`; });
    const r = compute();
    // window: the part of the turn that matters for the budget, not the whole spoken answer
    const synthDone = r.llmEnd + v.ttfb;
    const max = Math.max(r.firstAudio + 1.0, synthDone + 0.3, BUDGET * 1.3);
    const pct = (t) => (100 * t / max).toFixed(2) + "%";
    const seg = (cls, a, b) => { b = Math.min(b, max); if (a >= max) return ""; return `<div class="l21-seg ${cls}" style="left:${pct(a)};width:${pct(Math.max(b - a, max * 0.004))}"></div>`; };
    const budget = `<div class="l21-budget" style="left:${pct(BUDGET)}"></div>`;
    const ticks = [];
    const stepT = max > 8 ? 2 : max > 4 ? 1 : 0.5;
    for (let t = 0; t <= max + 1e-9; t += stepT) ticks.push(`<span style="left:${pct(t)}">${t.toFixed(1)}s</span>`);
    const ttsSegs = mode === "sequential" ? seg("s-tts", r.llmEnd, r.llmEnd + v.ttfb)
      : seg("s-tts", r.firstSent, r.firstSent + v.ttfb) + seg("s-tts", r.llmEnd, r.llmEnd + v.ttfb);
    g("lv-tl").innerHTML = `
      <div class="l21-tlrow"><span>STT</span><div class="l21-track">${seg("s-stt", 0, r.sttEnd)}${budget}</div></div>
      <div class="l21-tlrow"><span>LLM</span><div class="l21-track">${seg("s-llm", r.sttEnd, r.llmEnd)}<div class="l21-mark" style="left:${pct(r.firstTok)}"></div><div class="l21-mark" style="left:${pct(r.firstSent)}"></div>${budget}</div></div>
      <div class="l21-tlrow"><span>TTS</span><div class="l21-track">${ttsSegs}${budget}</div></div>
      <div class="l21-tlrow"><span>playback</span><div class="l21-track">${r.play.map((p) => seg("s-play", p[0], p[1])).join("")}${budget}</div></div>
      <div class="l21-tlrow"><span></span><div class="l21-axis">${ticks.join("")}</div></div>`;
    const ok = r.firstAudio <= BUDGET;
    g("lv-big").innerHTML = `<span>אודיו ראשון <b class="${ok ? "ok" : "bad"}">${r.firstAudio.toFixed(2)}s</b></span><span>סוף הסינתזה <b>${synthDone.toFixed(2)}s</b></span><span>סוף ההשמעה <b>${r.end.toFixed(1)}s</b></span><span class="muted">${ok ? "בתוך התקציב" : `מעל התקציב ב-${(r.firstAudio - BUDGET).toFixed(2)}s`}</span>`;
    const parts = mode === "sequential"
      ? [["STT", v.stt], ["LLM, כל התשובה", v.ttft + v.total / v.tps], ["TTS עד הבייט הראשון", v.ttfb], ["רשת", v.net]]
      : [["STT", v.stt], ["LLM עד הטוקן הראשון", v.ttft], ["LLM עד סוף המשפט הראשון", Math.min(v.first, v.total) / v.tps], ["TTS עד הבייט הראשון", v.ttfb], ["רשת", v.net]];
    parts.sort((a, b) => b[1] - a[1]);
    g("lv-tip").innerHTML = `<b>החלק הגדול ביותר באודיו הראשון:</b> ${parts[0][0]} (${parts[0][1].toFixed(2)}s), ואחריו ${parts[1][0]} (${parts[1][1].toFixed(2)}s). ${mode === "sequential" ? "במצב רציף, כל התשובה של ה-LLM נמצאת על המסלול הקריטי. נסה streaming." : "קיצור של המשפט הראשון עוזר רק עד גבול: מתחת לכמה מילים, ההקראה נשמעת קטועה."}`;
  }
  host.querySelectorAll("[data-k]").forEach((inp) => inp.addEventListener("input", () => { v[inp.dataset.k] = +inp.value; draw(); }));
  host.querySelectorAll("[data-m]").forEach((b) => b.addEventListener("click", () => {
    mode = b.dataset.m; host.querySelectorAll("[data-m]").forEach((x) => x.setAttribute("aria-pressed", x === b)); draw();
  }));
  draw();
};

/* ---------------- sim: Hebrew WER calculator ---------------- */
window.AIDS["l21wer"] = function (host) {
  const EX = [
    ["ניקוד ופיסוק", "שָׁלוֹם, מָה שְׁלוֹמְךָ?", "שלום מה שלומך"],
    ["אות סופית שגויה", "אני גר בירושלים", "אני גר בירושלימ"],
    ["גרשיים בראשי תיבות", "הוא שירת בצה\"ל", "הוא שירת בצהל"],
    ["כתיב שנשמע אותו דבר (כ/ק)", "התלמיד קנה כרטיס", "התלמיד קנה קרטיס"],
    ["תחילית מנותקת", "ובבית הספר יש ספרייה", "ו בבית הספר יש ספרייה"],
    ["פ נשמעה כ-ב", "פתח את הספר בפרק שלוש", "פתח את הספר בברק שלוש"],
    ["מילה שדולגה", "אני רוצה לקנות כרטיס לאוטובוס", "אני רוצה כרטיס לאוטובוס"],
    ["מספר בספרות", "יש לי שלושה אחים", "יש לי 3 אחים"],
    ["הזיה בסוף הקטע", "תודה רבה", "תודה רבה לכם על הצפייה"],
  ];
  const OPT = [["niqqud", "הסרת ניקוד"], ["punct", "פיסוק לרווח"], ["finals", "אותיות סופיות"], ["geresh", "גרש וגרשיים בתוך מילה"], ["maqaf", "מקף לרווח"]];
  const on = { niqqud: true, punct: true, finals: true, geresh: true, maqaf: true };
  let ref = EX[0][1], hyp = EX[0][2];
  host.innerHTML = `<div class="l21">
    <div class="guide"><p><b>מה רואים:</b> למעלה המשפט שהתלמיד היה אמור להגיד (ייחוס), ומתחתיו מה שמערכת התמלול כתבה. אחרי הנרמול, המחשבון מיישר את המילים במרחק עריכה ומציג את הייחוס מילה אחרי מילה: <b>מסגרת רגילה</b> למילה תקינה, <b>כתומה</b> להחלפה (מתחת: מה נשמע), <b>אדומה עם קו</b> למילה שחסרה, ו<b>כחולה</b> למילה שנוספה.</p>
    <p><b>המספרים:</b> WER הוא (החלפות + השמטות + הוספות) חלקי מספר המילים בייחוס. CER הוא אותו חישוב על תווים, בלי רווחים. המתגים קובעים מה הנרמול מוחק, וזה בדיוק מה ש-normalize_hebrew בתרגיל 5 עושה כשכולם דלוקים.</p></div>
    <label class="knob"><span>דוגמה</span><select id="wr-ex">${EX.map((e, i) => `<option value="${i}">${esc(e[0])}</option>`).join("")}</select></label>
    <label class="knob"><span>ייחוס (מה שהיה צריך להיאמר)</span><textarea id="wr-ref"></textarea></label>
    <label class="knob"><span>תמלול (מה שנכתב)</span><textarea id="wr-hyp"></textarea></label>
    <div class="l21-checks">${OPT.map((o) => `<label><input type="checkbox" data-o="${o[0]}" checked> ${esc(o[1])}</label>`).join("")}</div>
    <div class="l21-big" id="wr-big"></div>
    <div class="l21-words" id="wr-w"></div>
    <div class="l21-norm" id="wr-n"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  const FIN = { "ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ" };
  function norm(t) {
    t = t.normalize("NFC").replace(/[‎‏‪-‮⁦-⁩]/g, "");
    if (on.niqqud) t = t.replace(/[֑-ׇֽֿׁׂׅׄ]/g, "");
    if (on.maqaf) t = t.replace(/[־-]/g, " ");
    if (on.geresh) t = t.replace(/(?<=[\p{L}\p{N}])[׳״'"](?=[\p{L}\p{N}])/gu, "");
    if (on.punct) t = t.replace(/\p{P}/gu, " ");
    if (on.finals) t = t.replace(/[ךםןףץ]/g, (c) => FIN[c]);
    return t.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
  }
  function align(a, b) {
    const n = a.length, m = b.length, d = Array.from({ length: n + 1 }, (_, i) => Array.from({ length: m + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)));
    for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) d[i][j] = Math.min(d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1), d[i - 1][j] + 1, d[i][j - 1] + 1);
    const ops = []; let i = n, j = m;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && d[i][j] === d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)) { ops.push([a[i - 1] === b[j - 1] ? "ok" : "sub", a[i - 1], b[j - 1]]); i--; j--; }
      else if (i > 0 && d[i][j] === d[i - 1][j] + 1) { ops.push(["del", a[i - 1], ""]); i--; }
      else { ops.push(["ins", "", b[j - 1]]); j--; }
    }
    return ops.reverse();
  }
  function rate(ops, n, m) { const e = ops.filter((o) => o[0] !== "ok").length; return n ? e / n : (m ? 1 : 0); }
  function draw() {
    const r = norm(ref), hh = norm(hyp);
    const rw = r ? r.split(" ") : [], hw = hh ? hh.split(" ") : [];
    const ops = align(rw, hw);
    const S = ops.filter((o) => o[0] === "sub").length, D = ops.filter((o) => o[0] === "del").length, I = ops.filter((o) => o[0] === "ins").length;
    const rc = [...r.replace(/ /g, "")], hc = [...hh.replace(/ /g, "")];
    const cops = align(rc, hc);
    const wer = rate(ops, rw.length, hw.length), cer = rate(cops, rc.length, hc.length);
    g("wr-big").innerHTML = `<span>WER <b>${wer.toFixed(2)}</b></span><span>CER <b>${cer.toFixed(2)}</b></span><span class="muted" dir="ltr">S=${S} D=${D} I=${I}, N=${rw.length}</span>`;
    g("wr-w").innerHTML = ops.map((o) => o[0] === "ok" ? `<span class="l21-w">${esc(o[1])}</span>`
      : o[0] === "sub" ? `<span class="l21-w sub">${esc(o[1])}<small>heard: ${esc(o[2])}</small></span>`
      : o[0] === "del" ? `<span class="l21-w del">${esc(o[1])}<small>missing</small></span>`
      : `<span class="l21-w ins">${esc(o[2])}<small>inserted</small></span>`).join("") || `<span class="muted">אין מילים</span>`;
    g("wr-n").innerHTML = `<span>ייחוס אחרי נרמול: <code>${esc(r) || "—"}</code></span><span>תמלול אחרי נרמול: <code>${esc(hh) || "—"}</code></span>`;
  }
  function load(i) { ref = EX[i][1]; hyp = EX[i][2]; g("wr-ref").value = ref; g("wr-hyp").value = hyp; draw(); }
  g("wr-ex").addEventListener("change", (e) => load(+e.target.value));
  g("wr-ref").addEventListener("input", (e) => { ref = e.target.value; draw(); });
  g("wr-hyp").addEventListener("input", (e) => { hyp = e.target.value; draw(); });
  host.querySelectorAll("[data-o]").forEach((c) => c.addEventListener("change", () => { on[c.dataset.o] = c.checked; draw(); }));
  load(0);
};
