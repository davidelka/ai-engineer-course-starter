// Lesson 4 aids: context assembly + cache animation, cache cost simulator,
// lost-in-the-middle explorer (real data from Liu et al.), history/compaction lab.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l04-style";
  function style() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l04 { display: grid; gap: 12px; direction: rtl; min-width: 0; }
.l04 .ltr { direction: ltr; text-align: left; }
.l04-strip { position: relative; height: 34px; display: flex; direction: ltr; background: var(--code-bg); border-radius: 6px; overflow: visible; gap: 2px; }
.l04-strip i { display: block; height: 100%; border-radius: 3px; transition: width .45s, background .3s; min-width: 0; position: relative; }
.l04-strip i.new { animation: pop .45s ease; }
.l04-budget { position: absolute; top: -6px; bottom: -6px; border-inline-start: 2px dashed var(--ink); pointer-events: none; }
.l04-budget span { position: absolute; top: -18px; left: 4px; font-size: .66rem; color: var(--muted); white-space: nowrap; font-family: var(--mono); }
.l04-bp { position: absolute; top: -8px; bottom: -8px; width: 0; border-left: 3px solid var(--signal); }
.l04-bp span { position: absolute; bottom: -20px; left: -30px; font-size: .64rem; color: var(--signal); font-family: var(--mono); white-space: nowrap; }
.l04-c-tools { background: color-mix(in srgb, var(--accent) 35%, var(--surface)); }
.l04-c-sys { background: color-mix(in srgb, var(--accent) 60%, var(--surface)); }
.l04-c-docs { background: var(--accent); }
.l04-c-hist { background: color-mix(in srgb, var(--muted) 55%, var(--surface)); }
.l04-c-user { background: var(--ink); }
.l04-c-write { background: var(--signal); }
.l04-c-read { background: var(--good); }
.l04-c-raw { background: color-mix(in srgb, var(--muted) 45%, var(--surface)); }
.l04-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: .8rem; color: var(--muted); }
.l04-legend span { display: inline-flex; align-items: center; gap: 5px; }
.l04-legend i { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
.l04-layers { display: grid; gap: 3px; font-size: .84rem; }
.l04-layers div { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 8px; align-items: center; opacity: .35; transition: opacity .3s; }
.l04-layers div.on { opacity: 1; }
.l04-layers i { width: 12px; height: 12px; border-radius: 2px; }
.l04-layers b { font-family: var(--mono); font-weight: 600; direction: ltr; }
.l04-calls { display: grid; gap: 6px; }
.l04-call { display: grid; grid-template-columns: 4.2rem minmax(0, 1fr); gap: 8px; align-items: center; font-size: .8rem; }
.l04-call .bars2 { display: grid; gap: 3px; direction: ltr; }
.l04-call .b { height: 10px; border-radius: 3px; transition: width .4s; }
.l04-call .b.cost { background: var(--accent); }
.l04-call .b.ttft { background: var(--signal); }
.l04-call small { font-family: var(--mono); color: var(--muted); font-size: .7rem; }
.l04-badge { display: inline-block; font-size: .74rem; padding: 1px 8px; border-radius: 999px; background: var(--bad-soft); color: var(--bad); font-weight: 600; }
.l04-grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }
@media (max-width: 600px) { .l04-grid2 { grid-template-columns: minmax(0, 1fr); } }
.l04-tl { position: relative; height: 54px; direction: ltr; background: var(--code-bg); border-radius: 8px; overflow: hidden; }
.l04-tl .life { position: absolute; top: 30px; height: 8px; background: color-mix(in srgb, var(--good) 28%, transparent); }
.l04-tl .dot { position: absolute; top: 12px; width: 10px; height: 10px; margin-left: -5px; border-radius: 50%; box-shadow: 0 0 0 2px var(--code-bg); }
.l04-tl .dot.hit { background: var(--good); }
.l04-tl .dot.miss { background: var(--signal); }
.l04-tl .tick { position: absolute; bottom: 2px; font-size: .6rem; color: var(--muted); font-family: var(--mono); transform: translateX(-50%); }
.l04-big { font-size: 1.5rem; font-weight: 700; font-family: var(--mono); direction: ltr; display: inline-block; }
.l04-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.l04-tile { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 2px; }
.l04-tile small { color: var(--muted); font-size: .76rem; }
.l04-warn { font-size: .85rem; color: var(--bad); }
.l04 svg { width: 100%; height: auto; display: block; overflow: visible; direction: ltr; }
.l04 svg text { font-family: var(--mono); font-size: 11px; fill: var(--muted); }
.l04 .grid line { stroke: var(--line); stroke-width: 1; }
.l04-docs { display: flex; flex-wrap: wrap; gap: 3px; direction: ltr; }
.l04-docs i { width: 14px; height: 18px; border-radius: 2px; background: var(--code-bg); border: 1px solid var(--line); }
.l04-docs i.gold { background: var(--signal); border-color: var(--signal); }
.l04-tip { position: absolute; pointer-events: none; background: var(--ink); color: var(--bg); font-size: .76rem; padding: 4px 8px; border-radius: 6px; white-space: nowrap; transform: translate(-50%, -110%); direction: rtl; }
.l04-facts { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; }
.l04-facts span { font-size: .72rem; padding: 2px 7px; border-radius: 999px; border: 1px solid var(--line); font-family: var(--mono); }
.l04-facts span.ok { background: var(--good-soft); border-color: var(--good); color: var(--good); }
.l04-facts span.lost { color: var(--muted); text-decoration: line-through; }
`;
    document.head.append(s);
  }
  const fmtUsd = (x) => (x >= 1 ? "$" + x.toFixed(2) : x >= 0.01 ? "$" + x.toFixed(3) : "$" + x.toFixed(5));
  const fmtInt = (n) => Math.round(n).toLocaleString("en-US");
  function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

  /* ================================================================ l04ctx: animation */
  window.AIDS["l04ctx"] = function (host) {
    style();
    // Claude Haiku 5.5, prompts under 100K tokens. USD per 1M tokens.
    const P = { in: 0.10, out: 0.50, write: 0.125, read: 0.01 };
    const OUT = 300, BUDGET = 16000;
    const L = [
      { k: "tools", name: "tools: 2 tool definitions", t: 400, c: "l04-c-tools" },
      { k: "sys", name: "system: HR instructions", t: 200, c: "l04-c-sys" },
      { k: "docs", name: "documents: Acme handbook + HR policies", t: 13000, c: "l04-c-docs" },
      { k: "hist", name: "history: earlier turns", t: 600, c: "l04-c-hist" },
      { k: "user", name: "user turn: the question", t: 60, c: "l04-c-user" },
    ];
    const CAPS = [
      ["בקשה ריקה", "הרצועה היא הבקשה שתישלח, והקו המקווקו הוא תקציב של 16,000 טוקנים שהחלטנו עליו. כל שכבה שתיכנס תתפוס רוחב לפי מספר הטוקנים שלה."],
      ["1. כלים", "הגדרות של שני כלים: כ-400 טוקנים. הן נכנסות ראשונות, כי זה הסדר שבו ה-API קורא: tools, system, messages."],
      ["2. הוראות", "ה-system prompt של עוזר ה-HR: כ-200 טוקנים. השכבה הכי חשובה, וגם מהקטנות."],
      ["3. מסמכים", "מדריך העובד ומסמכי המדיניות: כ-13,000 טוקנים, כמעט כל הבקשה. בסוף שלהם יושבת נקודת השבירה (cache_control), הקו הכתום: כל מה שעד כאן הוא הקידומת שתישמר במטמון."],
      ["4. היסטוריה", "התורות הקודמות של השיחה: כ-600 טוקנים. הן אחרי נקודת השבירה, כי הן משתנות."],
      ["5. השאלה", "השאלה החדשה: 60 טוקנים, פחות מחצי אחוז מהבקשה. ועל כל השאר משלמים שוב בכל קריאה, אלא אם הם במטמון."],
      ["קריאה 1: כתיבה", "המטמון ריק. כל הקידומת (כלים, הוראות, מסמכים) נכתבת למטמון, בכתום, במחיר של פי 1.25 מקלט רגיל. ההיסטוריה והשאלה, באפור, מעובדות במחיר רגיל. הקריאה הזו קצת יקרה יותר מקריאה בלי caching."],
      ["קריאה 2: קריאה", "שאלה אחרת, אותה קידומת בדיוק. הקידומת נקראת מהמטמון, בירוק, בעשירית מהמחיר, והמודל לא מחשב אותה מחדש, אז גם ה-TTFT יורד. ההיסטוריה גדלה בתור הקודם, והיא עדיין באפור."],
      ["קריאה 3: עוד קריאה", "כל קריאה מהמטמון מרעננת את אורך החיים של 5 דקות, כך שתנועה רציפה שומרת את הקידומת חיה."],
      ["קריאה 4: הבאג", "מישהו הוסיף את השעה הנוכחית לשורה הראשונה של ה-system prompt. כמה טוקנים בלבד, אבל הם נמצאים לפני הכל, ולכן אף קידומת לא זהה למה שנשמר. כל 13,600 הטוקנים נכתבים מחדש, וכך יקרה בכל קריאה מעכשיו."],
    ];
    host.innerHTML = `<div class="l04">
      <div class="l04-legend" id="lg"></div>
      <div style="padding-top:20px"><div class="l04-strip" id="strip"></div></div>
      <div style="height:14px"></div>
      <div class="l04-layers" id="layers"></div>
      <div class="cap"><b id="ct"></b><div id="cb" class="muted"></div></div>
      <div class="stats" id="st"></div>
      <div id="callsWrap" hidden><div class="eyebrow">Per call: cost (blue) · time to first token (orange, illustrative)</div><div class="l04-calls" id="calls"></div></div>
      <div class="row"><button class="btn small primary" id="play">השהה</button><button class="btn small" id="prev" aria-label="צעד קודם">→</button><button class="btn small" id="next" aria-label="צעד הבא">←</button><span class="spacer"></span><span class="counter" id="cnt"></span></div>
      <label style="font-size:.88rem"><input type="checkbox" id="qf"> <b>השאלה לפני המסמכים</b>: מה קורה לקידומת אם ההודעה בנויה כמו בשיעור 1, עם השאלה למעלה והמסמכים אחריה?</label>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    const N = CAPS.length;

    function call(n, qf) {
      // returns segments [{t, cls}] and usage for call n (1..4)
      const hist = 600 + (n - 1) * 400;
      const pre = qf ? 600 : 13600; // with the question first, only tools+instructions are a stable prefix
      const rest = qf ? 13000 + hist + 60 : hist + 60;
      const broken = n === 4;
      const write = n === 1 || broken ? pre : 0, read = n === 1 || broken ? 0 : pre;
      const segs = [{ t: pre, c: write ? "l04-c-write" : "l04-c-read" }, { t: rest, c: "l04-c-raw" }];
      const cost = (write * P.write + read * P.read + rest * P.in + OUT * P.out) / 1e6;
      const nocache = ((pre + rest) * P.in + OUT * P.out) / 1e6;
      const ttft = 0.3 + (write + rest) / 25000 + read / 400000;
      return { segs, write, read, rest, cost, nocache, ttft, total: pre + rest };
    }
    function draw() {
      const qf = g("qf").checked, strip = g("strip");
      strip.innerHTML = "";
      const assembling = i <= 5;
      g("lg").innerHTML = assembling
        ? L.map((l) => `<span><i class="${l.c}"></i>${esc(l.k === "sys" ? "system" : l.k === "hist" ? "history" : l.k === "user" ? "user turn" : l.k)}</span>`).join("")
        : `<span><i class="l04-c-write"></i>נכתב למטמון (פי 1.25)</span><span><i class="l04-c-read"></i>נקרא מהמטמון (פי 0.1)</span><span><i class="l04-c-raw"></i>בלי מטמון (מחיר רגיל)</span>`;
      const scale = (t) => (100 * t) / BUDGET;
      let used = 0;
      if (assembling) {
        L.forEach((l, k) => {
          if (k >= i) return;
          const el = document.createElement("i");
          el.className = l.c + (k === i - 1 ? " new" : "");
          el.style.width = scale(l.t) + "%";
          el.title = `${l.name}: ${fmtInt(l.t)} tokens`;
          strip.append(el);
          used += l.t;
        });
        if (i >= 3) { const bp = document.createElement("div"); bp.className = "l04-bp"; bp.style.left = scale(13600) + "%"; bp.innerHTML = "<span>cache_control</span>"; strip.append(bp); }
      } else {
        const c = call(i - 5, qf);
        c.segs.forEach((sg) => { const el = document.createElement("i"); el.className = sg.c; el.style.width = scale(sg.t) + "%"; strip.append(el); });
        used = c.total;
      }
      const bud = document.createElement("div"); bud.className = "l04-budget"; bud.style.left = "100%"; bud.style.left = "calc(100% - 2px)";
      bud.innerHTML = `<span style="left:auto;right:4px">budget 16K</span>`; strip.append(bud);
      g("layers").innerHTML = L.map((l, k) => `<div class="${k < i || i > 5 ? "on" : ""}"><i class="${l.c}"></i><span class="ltr">${esc(l.name)}</span><b>${fmtInt(l.k === "hist" && i > 5 ? 600 + (i - 6) * 400 : l.t)}</b></div>`).join("");
      g("ct").textContent = CAPS[i][0];
      let body = CAPS[i][1];
      if (qf && i > 5) body = i === 6
        ? "השאלה למעלה, והמסמכים אחריה: הקידומת היציבה היא רק הכלים וההוראות (600 טוקנים). את 13,000 טוקני המסמכים אי אפשר לשמור, כי לפניהם יש שאלה שמשתנה בכל קריאה."
        : "גם כאן רק 600 טוקנים נקראים מהמטמון. המסמכים, באפור, משולמים במלואם בכל קריאה. זו הסיבה שבתרגיל 2 השאלה זזה לסוף.";
      g("cb").textContent = body;
      if (i <= 5) {
        const c = (used * P.in + (i === 5 ? OUT * P.out : 0)) / 1e6;
        g("st").innerHTML = `<span>טוקנים בבקשה: <b>${fmtInt(used)}</b></span>` + (i === 5 ? `<span>עלות קריאה בלי caching: <b>${fmtUsd(c)}</b></span>` : "");
        g("callsWrap").hidden = true;
      } else {
        const c = call(i - 5, qf);
        g("st").innerHTML = `<span>נכתב: <b>${fmtInt(c.write)}</b></span><span>נקרא: <b>${fmtInt(c.read)}</b></span><span>בלי מטמון: <b>${fmtInt(c.rest)}</b></span><span>עלות: <b>${fmtUsd(c.cost)}</b></span><span>בלי caching: <b>${fmtUsd(c.nocache)}</b></span>` + (i === 9 ? ` <span class="l04-badge">השעה בשורה הראשונה</span>` : "");
        g("callsWrap").hidden = false;
        const rows = [];
        const maxCost = 0.0025, maxT = 1.2;
        for (let n = 1; n <= i - 5; n++) {
          const k = call(n, qf);
          rows.push(`<div class="l04-call"><span>קריאה ${n}</span><div class="bars2"><div class="b cost" style="width:${Math.min(100, (100 * k.cost) / maxCost)}%"></div><small>${fmtUsd(k.cost)}</small><div class="b ttft" style="width:${Math.min(100, (100 * k.ttft) / maxT)}%"></div><small>~${k.ttft.toFixed(2)}s</small></div></div>`);
        }
        g("calls").innerHTML = rows.join("");
      }
      g("cnt").textContent = `${i + 1}/${N}`;
      g("play").textContent = playing ? "השהה" : "נגן";
    }
    function step(d) { i = (i + d + N) % N; draw(); }
    function loop() { clearTimeout(timer); if (playing) timer = setTimeout(() => { step(1); loop(); }, i === N - 1 ? 7000 : 5200); }
    g("play").addEventListener("click", () => { playing = !playing; draw(); loop(); });
    g("next").addEventListener("click", () => { playing = false; step(1); clearTimeout(timer); });
    g("prev").addEventListener("click", () => { playing = false; step(-1); clearTimeout(timer); });
    g("qf").addEventListener("change", draw);
    draw(); loop();
    return () => clearTimeout(timer);
  };

  /* ================================================================ l04cache: cost simulator */
  window.AIDS["l04cache"] = function (host) {
    style();
    const MODELS = {
      "claude-haiku-5-5": { label: "Haiku 5.5", in: 0.10, out: 0.50, w5: 0.125, w1h: 0.20, read: 0.01, min: 512, ttl: [300, 3600], ttlNames: ["5m", "1h"], tier: 100000 },
      "claude-sonnet-5-5": { label: "Sonnet 5.5", in: 2, out: 10, w5: 2.5, w1h: 4, read: 0.10, min: 512, ttl: [300, 3600], ttlNames: ["5m", "1h"] },
      "claude-opus-5-5": { label: "Opus 5.5", in: 4, out: 20, w5: 5, w1h: 8, read: 0.20, min: 512, ttl: [300, 3600], ttlNames: ["5m", "1h"] },
      "gpt-5.4-mini": { label: "gpt-5.4-mini", in: 0.75, out: 4.5, w5: 0.75, w1h: 0.75, read: 0.075, min: 1024, ttl: [450, 1800], ttlNames: ["in_memory (~5-10m)", "24h (~30m typical)"] },
    };
    const st = { model: "claude-haiku-5-5", ttl: 0, rate: 60, prefix: 13000, suffix: 400, out: 300, seed: 7 };
    const rateFromSlider = (v) => Math.round(Math.pow(10, v / 25)); // 0..75 -> 1..1000
    const sliderFromRate = (r) => Math.round(25 * Math.log10(r));
    host.innerHTML = `<div class="l04">
      <details class="guide" open><summary>איך לקרוא את הסימולטור</summary>
        <p>למעלה בוחרים מודל ו-TTL, ומזיזים ארבעה מחוונים: כמה קריאות בשעה חולקות את אותה קידומת, כמה טוקנים יש בקידומת היציבה (הוראות, כלים, מסמכים קבועים), כמה טוקנים יש בחלק שמשתנה (השאלה וסוף ההיסטוריה), וכמה טוקנים יש בתשובה.</p>
        <p>הסימולטור מניח שהקריאות מגיעות באקראי, ומחשב את <b>שיעור הפגיעות</b>: הסיכוי שהקריאה הקודמת הגיעה בתוך ה-TTL, כלומר <span dir="ltr" style="unicode-bidi:isolate">1 − e<sup>−rate × TTL</sup></span>, כש-rate הוא קריאות לשנייה. קריאה שפוגעת משלמת על הקידומת מחיר קריאה, וקריאה שמפספסת משלמת מחיר כתיבה. החלק המשתנה והתשובה עולים אותו דבר בשני המקרים.</p>
        <p><b>ציר הזמן</b> בתחתית מגריל שעה אחת של קריאות: נקודה ירוקה היא פגיעה, ונקודה כתומה היא כתיבה. הפס הירוק הבהיר הוא הזמן שבו הרשומה חיה במטמון. כל פגיעה מאריכה אותו.</p></details>
      <div class="l04-grid2">
        <div class="knob"><div class="knob-head"><span>מודל</span></div><div class="seg" id="mdl"></div></div>
        <div class="knob"><div class="knob-head"><span>TTL</span></div><div class="seg" id="ttl"></div></div>
        <div class="knob"><div class="knob-head"><span>קריאות בשעה עם אותה קידומת</span><b id="vRate"></b></div><input type="range" id="rate" min="0" max="75" step="1"></div>
        <div class="knob"><div class="knob-head"><span>טוקנים בקידומת היציבה</span><b id="vPre"></b></div><input type="range" id="pre" min="200" max="120000" step="100"></div>
        <div class="knob"><div class="knob-head"><span>טוקנים בחלק המשתנה</span><b id="vSuf"></b></div><input type="range" id="suf" min="20" max="5000" step="20"></div>
        <div class="knob"><div class="knob-head"><span>טוקנים בתשובה</span><b id="vOut"></b></div><input type="range" id="out" min="20" max="2000" step="20"></div>
      </div>
      <div class="l04-tiles" id="tiles"></div>
      <div id="warn" class="l04-warn"></div>
      <div><div class="row"><span class="eyebrow">One random hour of calls</span><span class="spacer"></span><button class="btn small" id="reroll">הגרל שעה אחרת</button></div>
        <div class="l04-tl" id="tl"></div><div class="stats" id="tlst" style="margin-top:6px"></div></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    g("mdl").innerHTML = Object.entries(MODELS).map(([k, m]) => `<button data-k="${k}">${esc(m.label)}</button>`).join("");
    function setSeg(el, val) { el.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === String(val)))); }
    g("mdl").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; st.model = b.dataset.k; draw(); });
    g("ttl").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; st.ttl = +b.dataset.k; draw(); });
    g("rate").value = sliderFromRate(st.rate); g("pre").value = st.prefix; g("suf").value = st.suffix; g("out").value = st.out;
    g("rate").addEventListener("input", (e) => { st.rate = Math.max(1, rateFromSlider(+e.target.value)); draw(); });
    g("pre").addEventListener("input", (e) => { st.prefix = +e.target.value; draw(); });
    g("suf").addEventListener("input", (e) => { st.suffix = +e.target.value; draw(); });
    g("out").addEventListener("input", (e) => { st.out = +e.target.value; draw(); });
    g("reroll").addEventListener("click", () => { st.seed++; draw(); });

    function draw() {
      const m = MODELS[st.model];
      g("ttl").innerHTML = m.ttlNames.map((n, k) => `<button data-k="${k}">${esc(n)}</button>`).join("");
      setSeg(g("mdl"), st.model); setSeg(g("ttl"), st.ttl);
      g("vRate").textContent = fmtInt(st.rate); g("vPre").textContent = fmtInt(st.prefix); g("vSuf").textContent = fmtInt(st.suffix); g("vOut").textContent = fmtInt(st.out);
      const ttl = m.ttl[st.ttl], write = st.ttl ? m.w1h : m.w5;
      const tooShort = st.prefix < m.min;
      const total = st.prefix + st.suffix;
      const mult = m.tier && total > m.tier ? 5 : 1;
      const p = tooShort ? 0 : 1 - Math.exp(-(st.rate / 3600) * ttl);
      const common = st.suffix * m.in + st.out * m.out;
      const none = (st.prefix * m.in + common) * mult / 1e6;
      const cached = tooShort ? none : ((p * st.prefix * m.read + (1 - p) * st.prefix * write) + common) * mult / 1e6;
      const be = write <= m.in ? 0 : (write - m.in) / (write - m.read);
      const saving = 1 - cached / none;
      g("tiles").innerHTML = `
        <div class="l04-tile"><small>שיעור פגיעות צפוי</small><span class="l04-big">${(100 * p).toFixed(0)}%</span><small>נקודת איזון: ${(100 * be).toFixed(1)}%</small></div>
        <div class="l04-tile"><small>עלות לשעה בלי caching</small><span class="l04-big">${fmtUsd(none * st.rate)}</span><small>${fmtUsd(none)} לקריאה</small></div>
        <div class="l04-tile"><small>עלות לשעה עם caching</small><span class="l04-big">${fmtUsd(cached * st.rate)}</span><small>${fmtUsd(cached)} לקריאה</small></div>
        <div class="l04-tile"><small>${saving >= 0 ? "חיסכון" : "הפסד"}</small><span class="l04-big" style="color:${saving >= 0 ? "var(--good)" : "var(--bad)"}">${(100 * Math.abs(saving)).toFixed(0)}%</span><small>${p > be ? "מעל נקודת האיזון" : "מתחת לנקודת האיזון"}</small></div>`;
      const warns = [];
      if (tooShort) warns.push(`הקידומת קצרה מהמינימום של ${fmtInt(m.min)} טוקנים במודל הזה: היא לא תישמר במטמון, ולא תהיה שום שגיאה.`);
      if (mult > 1) warns.push("מעל 100,000 טוקנים בפרומפט, כל המחירים של Haiku 5.5 גדלים פי 5, כולל כתיבה, קריאה ופלט.");
      if (st.model === "gpt-5.4-mini") warns.push("במודלים של OpenAI שלפני GPT-5.6 אין תוספת על כתיבה, ולכן caching אף פעם לא מייקר. ה-TTL שלהם לא מובטח, וכאן הוא מוצג כהערכה מהתיעוד.");
      g("warn").innerHTML = warns.map((w) => `<div>${esc(w)}</div>`).join("");
      // timeline
      const r = rng(st.seed * 97 + st.rate);
      const times = []; let t = 0;
      while (true) { t += -Math.log(1 - r()) * (3600 / st.rate); if (t > 3600) break; times.push(t); }
      const shown = times.slice(0, 160);
      const tl = g("tl"); let html = "";
      let exp = -1, hits = 0, lifeStart = null;
      const lives = [];
      times.forEach((x) => {
        const hit = !tooShort && x < exp;
        if (hit) hits++;
        if (!hit) { if (lifeStart !== null) lives.push([lifeStart, exp]); lifeStart = x; }
        exp = x + ttl;
      });
      if (lifeStart !== null && !tooShort) lives.push([lifeStart, Math.min(exp, 3600)]);
      lives.forEach(([a, b]) => { html += `<div class="life" style="left:${(100 * a) / 3600}%;width:${(100 * (Math.min(b, 3600) - a)) / 3600}%"></div>`; });
      exp = -1;
      shown.forEach((x) => { const hit = !tooShort && x < exp; exp = x + ttl; html += `<div class="dot ${hit ? "hit" : "miss"}" style="left:${(100 * x) / 3600}%" title="${(x / 60).toFixed(1)} min: ${hit ? "hit" : "write"}"></div>`; });
      [0, 15, 30, 45, 60].forEach((mm) => { html += `<div class="tick" style="left:${Math.min(97, Math.max(3, (100 * mm) / 60))}%">${mm}m</div>`; });
      tl.innerHTML = html;
      g("tlst").innerHTML = `<span>קריאות בשעה הזו: <b>${times.length}</b>${times.length > shown.length ? ` (מוצגות ${shown.length})` : ""}</span><span>פגיעות: <b>${hits}</b> (${times.length ? ((100 * hits) / times.length).toFixed(0) : 0}%)</span><span>כתיבות: <b>${times.length - hits}</b></span>`;
    }
    draw();
  };

  /* ================================================================ l04lost: lost in the middle */
  window.AIDS["l04lost"] = function (host) {
    style();
    // Liu et al., "Lost in the Middle", TACL 2024, Appendix tables 5-7 (multi-document QA accuracy, %).
    const DATA = {
      gpt: { label: "GPT-3.5-Turbo", closed: 56.1, sets: {
        10: { idx: [0, 4, 9], acc: [76.8, 61.2, 62.4] },
        20: { idx: [0, 4, 9, 14, 19], acc: [75.8, 57.2, 53.8, 55.4, 63.2] },
        30: { idx: [0, 4, 9, 14, 19, 24, 29], acc: [73.4, 55.1, 50.5, 50.9, 51.8, 54.9, 63.7], note: "GPT-3.5-Turbo (16K)" } } },
      claude: { label: "Claude-1.3", closed: null, sets: {
        10: { idx: [0, 4, 9], acc: [62.9, 58.3, 59.7] },
        20: { idx: [0, 4, 9, 14, 19], acc: [59.9, 55.9, 56.8, 57.2, 60.1] },
        30: { idx: [0, 4, 9, 14, 19, 24, 29], acc: [59.1, 55.1, 54.8, 55.7, 56.4, 56.2, 59.9] } } },
    };
    const st = { m: "gpt", n: 20, k: 0 };
    host.innerHTML = `<div class="l04">
      <details class="guide" open><summary>איך לקרוא את הגרף</summary>
        <p>בניסוי, המודל קיבל שאלה ו-10, 20 או 30 מסמכים מוויקיפדיה. רק באחד מהם הייתה התשובה, וכל השאר היו מסמכים דומים בלי התשובה. החוקרים הזיזו את מסמך התשובה ממקום למקום, ומדדו את הדיוק בכל מיקום.</p>
        <p><b>ציר X</b> הוא המיקום של מסמך התשובה (0 הוא הראשון), ו<b>ציר Y</b> הוא אחוז התשובות הנכונות. הנקודות הן המיקומים שנמדדו בפועל, והקו רק מחבר ביניהן. <b>הקו המקווקו</b> הוא הדיוק של GPT-3.5-Turbo <b>בלי מסמכים בכלל</b>, רק מהידע שלו. המחוון מזיז את מסמך התשובה, והשורה של המלבנים מראה איפה הוא נמצא בתוך ההקשר.</p></details>
      <div class="l04-grid2">
        <div class="knob"><div class="knob-head"><span>מודל</span></div><div class="seg" id="m"><button data-k="gpt">GPT-3.5-Turbo</button><button data-k="claude">Claude-1.3</button></div></div>
        <div class="knob"><div class="knob-head"><span>מספר מסמכים בהקשר</span></div><div class="seg" id="n"><button data-k="10">10</button><button data-k="20">20</button><button data-k="30">30</button></div></div>
      </div>
      <div style="position:relative" id="chartWrap"><svg id="svg" viewBox="0 0 600 260" role="img" aria-label="accuracy by position of the answer document"></svg></div>
      <div class="legend"><span><i style="background:var(--accent)"></i>דיוק לפי מיקום (נמדד)</span><span id="lgClosed"><i style="background:none;border-top:2px dashed var(--ink);height:0;width:14px;display:inline-block;vertical-align:middle"></i> בלי מסמכים (closed-book)</span></div>
      <div class="knob"><div class="knob-head"><span>מיקום מסמך התשובה</span><b id="vk"></b></div><input type="range" id="k" min="0" max="4" step="1"></div>
      <div class="l04-docs" id="docs" aria-hidden="true"></div>
      <div class="stats" id="st"></div>
      <div class="callout"><b>ומה היום?</b> המודלים במאמר הם מ-2023. מודלים חדשים מוצאים "מחט" אחת בהקשר ארוך כמעט תמיד, ולכן בדיקה פשוטה כבר לא מראה עקומת U חדה. אבל הדו"ח של Chroma מ-2025 מצא, ב-18 מודלים חדשים, שהביצועים עדיין יורדים כשההקשר מתארך, ובמיוחד כשיש מסיחים, וכשהתשובה לא מנוסחת במילים של השאלה. בתרגיל 5 תבדוק את זה בעצמך על Claude Haiku 5.5, עם מסיחים.</div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const setSeg = (el, v) => el.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === String(v))));
    g("m").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { st.m = b.dataset.k; draw(); } });
    g("n").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { st.n = +b.dataset.k; st.k = 0; draw(); } });
    g("k").addEventListener("input", (e) => { st.k = +e.target.value; draw(); });
    function draw() {
      setSeg(g("m"), st.m); setSeg(g("n"), st.n);
      const D = DATA[st.m], S = D.sets[st.n];
      const kk = Math.min(st.k, S.idx.length - 1);
      g("k").max = String(S.idx.length - 1); g("k").value = String(kk);
      const W = Math.max(320, Math.min(640, host.clientWidth || 600)), H = W < 450 ? 230 : 260, ml = 40, mr = 14, mt = 14, mb = 34, y0 = 45, y1 = 80;
      g("svg").setAttribute("viewBox", `0 0 ${W} ${H}`);
      const X = (i) => ml + ((W - ml - mr) * i) / (st.n - 1), Y = (v) => mt + ((H - mt - mb) * (y1 - v)) / (y1 - y0);
      let s = `<g class="grid">`;
      for (let v = 45; v <= 80; v += 5) s += `<line x1="${ml}" x2="${W - mr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${ml - 6}" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`;
      s += `</g>`;
      S.idx.forEach((i) => { s += `<text x="${X(i)}" y="${H - mb + 16}" text-anchor="middle">${i}</text>`; });
      s += `<text x="${(W + ml) / 2}" y="${H - 4}" text-anchor="middle">${W < 450 ? "answer position (0 = first)" : "position of the answer document (0 = first)"}</text>`;
      if (D.closed) s += `<line x1="${ml}" x2="${W - mr}" y1="${Y(D.closed)}" y2="${Y(D.closed)}" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="5 4"/><text x="${W - mr}" y="${Y(D.closed) - 5}" text-anchor="end">closed-book ${D.closed}%</text>`;
      s += `<polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${S.idx.map((i, j) => `${X(i)},${Y(S.acc[j])}`).join(" ")}"/>`;
      S.idx.forEach((i, j) => {
        const on = j === kk;
        s += `<circle cx="${X(i)}" cy="${Y(S.acc[j])}" r="${on ? 7 : 5}" fill="${on ? "var(--signal)" : "var(--accent)"}" stroke="var(--surface)" stroke-width="2" data-j="${j}" style="cursor:pointer"><title>position ${i}: ${S.acc[j]}%</title></circle>`;
        if (on) s += `<text x="${X(i)}" y="${Y(S.acc[j]) - 12}" text-anchor="middle" style="fill:var(--ink);font-weight:600">${S.acc[j]}%</text>`;
      });
      g("svg").innerHTML = s;
      g("svg").querySelectorAll("circle").forEach((c) => c.addEventListener("click", () => { st.k = +c.dataset.j; draw(); }));
      g("lgClosed").style.display = D.closed ? "" : "none";
      const pos = S.idx[kk], acc = S.acc[kk];
      g("vk").textContent = `${pos} / ${st.n - 1}`;
      g("docs").innerHTML = Array.from({ length: st.n }, (_, i) => `<i class="${i === pos ? "gold" : ""}"></i>`).join("");
      const best = Math.max(...S.acc), worst = Math.min(...S.acc);
      let txt = `<span>${esc(S.note || D.label)}, ${st.n} מסמכים</span><span>דיוק במיקום ${pos}: <b>${acc}%</b></span><span>טווח: <b>${worst}%–${best}%</b></span>`;
      if (D.closed) txt += `<span>${acc < D.closed ? "<b style='color:var(--bad)'>נמוך</b> מהדיוק בלי מסמכים" : "מעל הדיוק בלי מסמכים"}</span>`;
      else txt += `<span>למודל הזה המאמר לא מדווח closed-book בטבלאות האלה</span>`;
      g("st").innerHTML = txt;
    }
    draw();
    const onR = () => draw();
    window.addEventListener("resize", onR);
    return () => window.removeEventListener("resize", onR);
  };

  /* ================================================================ l04compact: history lab */
  window.AIDS["l04compact"] = function (host) {
    style();
    const TURNS = 60, FACTS = 6, PER_TURN = 260, SUMMARY = 450, SYS = 3000;
    const FACT_NAMES = ["employee ID", "start date", "manager", "city", "allergy", "due date"];
    const P = { in: 0.10, read: 0.01, write: 0.125, out: 0.50 }; // Haiku 5.5
    const st = { strat: "compact", budget: 4000, thr: 90, keep: 4, fid: 95, seed: 3 };
    host.innerHTML = `<div class="l04">
      <details class="guide" open><summary>איך לקרוא את המעבדה</summary>
        <p>שיחה של 60 תורות. כל תור (שאלה ותשובה) מוסיף כ-260 טוקנים להיסטוריה. ב-6 התורות הראשונות המשתמש מספר עובדה על עצמו: מספר עובד, תאריך התחלה, מנהל וכן הלאה. לפני ההיסטוריה יש system prompt של 3,000 טוקנים עם נקודת שבירה משלו, וגם להיסטוריה יש caching אוטומטי.</p>
        <p><b>הגרף</b> מראה את גודל ההיסטוריה שנשלחת בכל תור. הקו המקווקו הוא התקציב. ב-<b>full</b> ההיסטוריה פשוט גדלה. ב-<b>truncate</b> היא נעצרת בתקציב, כי התורות הישנות נזרקות. ב-<b>compact</b>, כשההיסטוריה עוברת את הסף, הישנות מסוכמות לכ-450 טוקנים, ו-K האחרונות נשארות. לכן הגרף הוא "שן מסור". הנקודות הכתומות הן תורות שבהן ה-compaction שבר את המטמון, ולכן היה צריך לכתוב את ההיסטוריה מחדש.</p>
        <p><b>נאמנות הסיכום</b> היא הסיכוי שעובדה תשרוד כל סיכום. המספר הזה מומצא לצורך ההמחשה: את הערך האמיתי מודדים, וזה תרגיל 6.</p></details>
      <div class="seg" id="sg"><button data-k="full">full</button><button data-k="truncate">truncate</button><button data-k="compact">compact</button></div>
      <div class="l04-grid2">
        <div class="knob"><div class="knob-head"><span>תקציב היסטוריה (טוקנים)</span><b id="vb"></b></div><input type="range" id="b" min="1500" max="12000" step="250"></div>
        <div class="knob" id="kThr"><div class="knob-head"><span>סף ל-compaction (% מהתקציב)</span><b id="vt"></b></div><input type="range" id="t" min="40" max="100" step="5"></div>
        <div class="knob" id="kKeep"><div class="knob-head"><span>תורות שנשארות מילה במילה (K)</span><b id="vk"></b></div><input type="range" id="k" min="1" max="10" step="1"></div>
        <div class="knob" id="kFid"><div class="knob-head"><span>נאמנות הסיכום (לכל עובדה, לכל סיכום)</span><b id="vf"></b></div><input type="range" id="f" min="50" max="100" step="1"></div>
      </div>
      <svg id="svg" viewBox="0 0 600 220" role="img" aria-label="history tokens per turn"></svg>
      <div class="l04-tiles" id="tiles"></div>
      <div><div class="eyebrow">Facts from turns 1-6, after turn 60</div><div class="l04-facts" id="facts"></div></div>
      <div class="row"><button class="btn small" id="rr">הגרל סיכומים מחדש</button></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    g("b").value = st.budget; g("t").value = st.thr; g("k").value = st.keep; g("f").value = st.fid;
    g("sg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { st.strat = b.dataset.k; draw(); } });
    [["b", "budget"], ["t", "thr"], ["k", "keep"], ["f", "fid"]].forEach(([id, key]) => g(id).addEventListener("input", (e) => { st[key] = +e.target.value; draw(); }));
    g("rr").addEventListener("click", () => { st.seed++; draw(); });

    function simulate() {
      const r = rng(st.seed);
      // turns kept verbatim: list of turn numbers; summary: null or {tokens, facts:Set}
      let verbatim = [], summary = null, compactions = 0, writes = 0;
      const sizes = [], breaks = [];
      let cost = 0, prevPrefix = 0;
      const alive = new Set();
      for (let t = 1; t <= TURNS; t++) {
        verbatim.push(t);
        let broke = false;
        const hist = () => verbatim.length * PER_TURN + (summary ? summary.tokens : 0);
        if (st.strat === "truncate") {
          while (verbatim.length > 1 && hist() > st.budget) { verbatim.shift(); broke = true; }
        } else if (st.strat === "compact" && hist() > (st.budget * st.thr) / 100) {
          const keep = Math.min(st.keep, verbatim.length);
          const old = verbatim.slice(0, verbatim.length - keep);
          const facts = new Set();
          if (summary) summary.facts.forEach((f) => { if (r() * 100 < st.fid) facts.add(f); });
          old.forEach((x) => { if (x <= FACTS && r() * 100 < st.fid) facts.add(x); });
          summary = { tokens: SUMMARY, facts };
          verbatim = verbatim.slice(verbatim.length - keep);
          compactions++; broke = true;
        }
        const h = hist();
        sizes.push(h);
        // cost of this turn: system always read after turn 1; history: the part equal to last turn's prefix is read, rest uncached/written
        const sysCost = t === 1 ? SYS * P.write : SYS * P.read;
        let histCost;
        if (broke || t === 1) { histCost = h * P.write; writes++; if (t > 1) breaks.push(t); }
        else { const reused = Math.min(prevPrefix, h); histCost = reused * P.read + (h - reused) * P.write; }
        prevPrefix = h;
        cost += (sysCost + histCost + 300 * P.out) / 1e6;
      }
      verbatim.forEach((x) => { if (x <= FACTS) alive.add(x); });
      if (summary) summary.facts.forEach((f) => alive.add(f));
      return { sizes, breaks, compactions, writes, cost, alive };
    }
    function draw() {
      g("sg").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === st.strat)));
      ["kThr", "kKeep", "kFid"].forEach((id) => { g(id).style.opacity = st.strat === "compact" ? "1" : ".4"; g(id).querySelector("input").disabled = st.strat !== "compact"; });
      g("vb").textContent = fmtInt(st.budget); g("vt").textContent = st.thr + "%"; g("vk").textContent = st.keep; g("vf").textContent = st.fid + "%";
      const R = simulate();
      const W = Math.max(320, Math.min(640, host.clientWidth || 600)), H = W < 450 ? 200 : 220, ml = 46, mr = 10, mt = 14, mb = 28;
      g("svg").setAttribute("viewBox", `0 0 ${W} ${H}`);
      const ymax = Math.max(st.budget * 1.2, Math.max(...R.sizes));
      const X = (t) => ml + ((W - ml - mr) * (t - 1)) / (TURNS - 1), Y = (v) => mt + ((H - mt - mb) * (1 - v / ymax));
      let s = `<g class="grid">`;
      const stepV = ymax > 12000 ? 4000 : 2000;
      for (let v = 0; v <= ymax; v += stepV) s += `<line x1="${ml}" x2="${W - mr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${ml - 6}" y="${Y(v) + 4}" text-anchor="end">${v / 1000}K</text>`;
      s += `</g>`;
      [1, 15, 30, 45, 60].forEach((t) => { s += `<text x="${X(t)}" y="${H - mb + 16}" text-anchor="middle">${t}</text>`; });
      s += `<text x="${W - mr}" y="${H - 2}" text-anchor="end">turn</text>`;
      s += `<line x1="${ml}" x2="${W - mr}" y1="${Y(st.budget)}" y2="${Y(st.budget)}" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="5 4"/><text x="${W - mr}" y="${Y(st.budget) - 5}" text-anchor="end">budget ${fmtInt(st.budget)}</text>`;
      s += `<polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${R.sizes.map((v, i) => `${X(i + 1)},${Y(v)}`).join(" ")}"/>`;
      R.breaks.forEach((t) => { s += `<circle cx="${X(t)}" cy="${Y(R.sizes[t - 1])}" r="4.5" fill="var(--signal)" stroke="var(--surface)" stroke-width="2"><title>turn ${t}: history rewritten to the cache</title></circle>`; });
      g("svg").innerHTML = s;
      const alive = R.alive.size;
      g("tiles").innerHTML = `
        <div class="l04-tile"><small>היסטוריה בתור 60</small><span class="l04-big">${fmtInt(R.sizes[TURNS - 1])}</span><small>טוקנים</small></div>
        <div class="l04-tile"><small>עלות מצטברת, 60 תורות</small><span class="l04-big">${fmtUsd(R.cost)}</span><small>Haiku 5.5, עם caching</small></div>
        <div class="l04-tile"><small>${st.strat === "compact" ? "compactions" : "תורות שבהן המטמון נשבר"}</small><span class="l04-big">${st.strat === "compact" ? R.compactions : R.breaks.length}</span><small>${R.breaks.length} כתיבות מחדש של ההיסטוריה</small></div>
        <div class="l04-tile"><small>עובדות ששרדו</small><span class="l04-big" style="color:${alive === FACTS ? "var(--good)" : alive === 0 ? "var(--bad)" : "var(--ink)"}">${alive}/${FACTS}</span><small>${st.strat === "truncate" ? "חיתוך לא שומר כלום מהעבר" : st.strat === "full" ? "הכל נשאר, ובמחיר מלא" : "תלוי בנאמנות הסיכום"}</small></div>`;
      g("facts").innerHTML = FACT_NAMES.map((n, i) => `<span class="${R.alive.has(i + 1) ? "ok" : "lost"}">${esc(n)}</span>`).join("");
    }
    draw();
    const onR = () => draw();
    window.addEventListener("resize", onR);
    return () => window.removeEventListener("resize", onR);
  };
})();
