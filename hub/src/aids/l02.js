// Lesson 2 aids: streaming animation, request comparer, retry/backoff simulator, cost calculator.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";

/* ---------------- animation: streaming ---------------- */
function mountStreaming(host) {
  const PIECES = ["Two colors", " are", " **red**", " and", " **blue**", "."];
  const FORMATS = {
    anthropic: {
      name: "Anthropic",
      start: [["message_start", '{"message":{"usage":{"input_tokens":14}}}'], ["content_block_start", '{"index":0,"content_block":{"type":"text"}}'], ["ping", ""]],
      delta: (t) => ["content_block_delta", `{"delta":{"type":"text_delta","text":${JSON.stringify(t)}}}`],
      end: [["content_block_stop", '{"index":0}'], ["message_delta", '{"delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":16}}'], ["message_stop", ""]],
      err: ["error", '{"error":{"type":"overloaded_error","message":"Overloaded"}}'],
    },
    openai: {
      name: "OpenAI",
      start: [["response.created", '{"response":{"status":"in_progress"}}'], ["response.in_progress", ""], ["response.output_item.added", '{"item":{"type":"message"}}'], ["response.content_part.added", ""]],
      delta: (t) => ["response.output_text.delta", `{"delta":${JSON.stringify(t)}}`],
      end: [["response.output_text.done", '{"text":"…"}'], ["response.completed", '{"response":{"status":"completed","usage":{"input_tokens":14,"output_tokens":16}}}']],
      err: ["error", '{"code":"server_error","message":"The server had an error"}'],
    },
    gemini: {
      name: "Gemini",
      start: [],
      delta: (t, k, n) => [null, `{"candidates":[{"content":{"parts":[{"text":${JSON.stringify(t)}}]}${k === n - 1 ? ',"finishReason":"STOP"' : ""}}],"usageMetadata":{"candidatesTokenCount":${Math.round(16 * (k + 1) / n)}}}`],
      end: [],
      err: [null, '{"error":{"code":503,"status":"UNAVAILABLE","message":"The model is overloaded."}}'],
    },
  };
  host.innerHTML = `<div class="sim">
    <div class="seg" role="group" aria-label="ספק">${Object.entries(FORMATS).map(([k, f], i) => `<button data-f="${k}" aria-pressed="${i === 0}">${f.name}</button>`).join("")}</div>
    <label class="row" style="font-size:.9rem"><input type="checkbox" id="sa-err"> שגיאה באמצע הזרם</label>
    <div class="stream-grid">
      <div><div class="eyebrow">Wire: what arrives</div><div class="wire" id="sa-wire" aria-live="off"></div></div>
      <div><div class="eyebrow">Screen: what the user sees</div><div class="screen" id="sa-screen"></div>
        <div class="stats" id="sa-stats"></div></div>
    </div>
    <div class="cap"><b id="sa-t"></b><div id="sa-b" class="muted"></div></div>
    <div class="row"><button class="btn small primary" id="sa-play">השהה</button><button class="btn small" id="sa-step">צעד</button><button class="btn small" id="sa-restart">מההתחלה</button></div></div>`;
  const g = (id) => host.querySelector("#" + id);
  let fmt = "anthropic", events = [], i = 0, timer = null;
  let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;

  function build() {
    const f = FORMATS[fmt], withErr = g("sa-err").checked, out = [];
    out.push({ kind: "http", line: "HTTP/1.1 200 OK   content-type: text/event-stream", t: 0.32, cap: ["הזרם נפתח", "קוד 200 מגיע מיד, עוד לפני שהמודל כתב משהו. מכאן והלאה קוד ה-HTTP כבר לא ישתנה, גם אם תהיה תקלה."] });
    f.start.forEach(([e, d]) => out.push({ kind: "meta", ev: e, data: d, t: 0.05, cap: ["אירועי פתיחה", fmt === "anthropic" ? "message_start מביא כבר את מספר טוקני הקלט. ping הוא keep-alive, ומדלגים עליו." : "אירועי ניהול: אין בהם טקסט, וה-adapter מתעלם מהם."] }));
    const n = PIECES.length;
    for (let k = 0; k < n; k++) {
      if (withErr && k === 3) {
        out.push({ kind: "err", ev: f.err[0], data: f.err[1], t: 0.4, cap: ["שגיאה בתוך זרם תקין", "קוד ה-HTTP היה 200, ובכל זאת התשובה נקטעה. רק מי שקורא את האירועים יודע. אסור להציג את החצי הזה כאילו הוא תשובה שלמה."] });
        return out;
      }
      const [e, d] = f.delta(PIECES[k], k, n);
      out.push({ kind: "delta", ev: e, data: d, text: PIECES[k], t: k === 0 ? 0.25 : 0.12, cap: k === 0 ? ["הטוקן הראשון: TTFT", "מכאן המשתמש רואה טקסט. הזמן עד לרגע הזה נקרא Time To First Token, וזה מה שהמשתמש מרגיש."] : ["עוד חתיכת טקסט", fmt === "gemini" ? "ב-Gemini כל חתיכה היא JSON שלם, וה-usageMetadata בה מצטבר: לוקחים את האחרון, לא סוכמים." : "כל אירוע מוסיף עוד כמה טוקנים לטקסט שעל המסך."] });
    }
    f.end.forEach(([e, d]) => out.push({ kind: "meta", ev: e, data: d, t: 0.05, cap: ["סוף הזרם", fmt === "anthropic" ? "stop_reason ומספר טוקני הפלט מגיעים רק כאן, בסוף. message_stop הוא ההוכחה שהתשובה שלמה." : "response.completed מביא את הספירה הסופית, והוא ההוכחה שהתשובה שלמה."] }));
    if (fmt === "gemini") out[out.length - 1].cap = ["סוף הזרם", "ל-Gemini אין אירוע סיום נפרד. החיבור נסגר, וה-finishReason בחתיכה האחרונה הוא ההוכחה היחידה שהתשובה שלמה."];
    out.push({ kind: "close", line: "(connection closed)", t: 0.05, cap: ["החיבור נסגר", "התשובה המלאה הורכבה מכל החתיכות. ה-adapter מחזיר עכשיו תוצאה אחת עם טקסט, טוקנים, עלות ו-TTFT."] });
    return out;
  }
  function render() {
    const wire = g("sa-wire"), screen = g("sa-screen");
    wire.innerHTML = ""; let text = "", clock = 0, ttft = null, broken = false;
    events.slice(0, i).forEach((e, k) => {
      clock += e.t;
      const row = document.createElement("div");
      row.className = "wl " + e.kind + (k === i - 1 ? " new" : "");
      const ts = document.createElement("span"); ts.className = "ts"; ts.textContent = clock.toFixed(2);
      const body = document.createElement("span");
      body.textContent = e.line || ((e.ev ? `event: ${e.ev}` : "") + (e.ev && e.data ? "\n" : "") + (e.data ? `data: ${e.data}` : ""));
      row.append(ts, body); wire.append(row);
      if (e.kind === "delta") { text += e.text; if (ttft === null) ttft = clock; }
      if (e.kind === "err") broken = true;
    });
    wire.scrollTop = wire.scrollHeight;
    screen.textContent = text || "…";
    screen.classList.toggle("broken", broken);
    if (broken) { const w = document.createElement("div"); w.className = "partial"; w.textContent = "התשובה נקטעה. מה מציגים עכשיו?"; screen.append(w); }
    g("sa-stats").innerHTML = `<span>TTFT: <b>${ttft === null ? "-" : ttft.toFixed(2) + "s"}</b></span><span>זמן: <b>${clock.toFixed(2)}s</b></span><span>אירועים: <b>${i}/${events.length}</b></span>`;
    const cap = i ? events[i - 1].cap : ["לפני הבקשה", "הלקוח שולח POST עם stream: true ומחכה. בצד שמאל: מה מגיע ברשת. בצד ימין: מה המשתמש רואה."];
    g("sa-t").textContent = cap[0]; g("sa-b").textContent = cap[1];
  }
  const tick = () => { clearTimeout(timer); if (!playing) return; timer = setTimeout(() => { if (i < events.length) { i++; render(); tick(); } else { timer = setTimeout(() => { i = 0; render(); tick(); }, 3500); } }, i === 0 ? 1400 : 1500); };
  const setP = (p) => { playing = p; g("sa-play").textContent = p ? "השהה" : "נגן"; tick(); };
  const reset = () => { events = build(); i = 0; render(); tick(); };
  host.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { fmt = b.dataset.f; host.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); reset(); }));
  g("sa-err").addEventListener("change", reset);
  g("sa-play").addEventListener("click", () => setP(!playing));
  g("sa-step").addEventListener("click", () => { setP(false); if (i < events.length) i++; else i = 0; render(); });
  g("sa-restart").addEventListener("click", () => { i = 0; render(); tick(); });
  events = build(); render(); setP(playing);
  return () => clearTimeout(timer);
}

/* ---------------- request comparer ---------------- */
function mountCompare(host) {
  host.innerHTML = `<div class="sim">
    <div class="form2">
      <label>System<textarea id="rc-sys" rows="2" dir="ltr">You are Acme's HR assistant. Answer briefly.</textarea></label>
      <label>User<textarea id="rc-user" rows="2" dir="ltr">How many vacation days in year 3?</textarea></label>
      <div class="row">
        <label>max tokens <input id="rc-max" type="number" value="300" min="1" style="width:6rem" dir="ltr"></label>
        <label>effort <select id="rc-eff" dir="ltr"><option value="">(none)</option><option>low</option><option>medium</option><option>high</option></select></label>
      </div>
      <div class="row">
        <label><input type="checkbox" id="rc-stream"> סטרימינג</label>
        <label><input type="checkbox" id="rc-hist"> שיחה בהמשכים (הודעה קודמת של המודל)</label>
      </div>
    </div>
    <div class="seg" role="group" aria-label="ספק">${["Anthropic", "OpenAI", "Gemini", "הכל"].map((x, i) => `<button data-p="${i}" aria-pressed="${i === 3}">${x}</button>`).join("")}</div>
    <div id="rc-out" class="stack"></div></div>`;
  const g = (id) => host.querySelector("#" + id);
  let show = 3;
  const MODELS = ["claude-haiku-5-5", "gpt-5.4-mini", "gemini-3.6-flash"];
  function build() {
    const sys = g("rc-sys").value, user = g("rc-user").value, max = +g("rc-max").value || 1, eff = g("rc-eff").value;
    const stream = g("rc-stream").checked, hist = g("rc-hist").checked;
    const turns = hist ? [["user", "How many vacation days in year 1?"], ["assistant", "14 days."], ["user", user]] : [["user", user]];
    const a = { model: MODELS[0], max_tokens: max };
    if (sys) a.system = sys;
    a.messages = turns.map(([r, c]) => ({ role: r, content: c }));
    if (eff) a.output_config = { effort: eff };
    if (stream) a.stream = true;
    const o = { model: MODELS[1] };
    if (sys) o.instructions = sys;
    o.input = turns.length === 1 ? user : turns.map(([r, c]) => ({ role: r, content: c }));
    o.max_output_tokens = max;
    if (eff) o.reasoning = { effort: eff };
    if (stream) o.stream = true;
    const gm = { contents: turns.map(([r, c]) => ({ role: r === "assistant" ? "model" : "user", parts: [{ text: c }] })) };
    if (sys) gm.systemInstruction = { parts: [{ text: sys }] };
    gm.generationConfig = { maxOutputTokens: max };
    if (eff) gm.generationConfig.thinkingConfig = { thinkingLevel: eff };
    return [
      { name: "Anthropic: Messages API", url: "POST https://api.anthropic.com/v1/messages", headers: ["x-api-key: sk-ant-…", "anthropic-version: 2023-06-01", "content-type: application/json"], body: a,
        notes: ["system הוא פרמטר נפרד, לא הודעה.", "max_tokens חובה.", stream ? "סטרימינג: שדה stream ב-body, אותה כתובת." : "התשובה: content[] עם בלוקים, stop_reason, usage."] },
      { name: "OpenAI: Responses API", url: "POST https://api.openai.com/v1/responses", headers: ["Authorization: Bearer sk-proj-…", "content-type: application/json"], body: o,
        notes: ["system נקרא instructions.", turns.length === 1 ? "input יכול להיות מחרוזת פשוטה." : "שיחה: input הופך לרשימת הודעות.", stream ? "סטרימינג: שדה stream ב-body, אותה כתובת." : "התשובה: output[], והקיצור output_text ב-SDK."] },
      { name: "Gemini: generateContent", url: `POST https://generativelanguage.googleapis.com/v1beta/models/${MODELS[2]}:${stream ? "streamGenerateContent?alt=sse" : "generateContent"}`, headers: ["x-goog-api-key: AIza…", "content-type: application/json"], body: gm,
        notes: ["המודל בכתובת, לא ב-body.", "התפקיד של המודל נקרא model, וההודעות נקראות contents.", stream ? "סטרימינג: כתובת אחרת (streamGenerateContent?alt=sse), לא שדה ב-body." : "התשובה: candidates[0].content.parts, finishReason ו-usageMetadata."] },
    ];
  }
  function draw() {
    const out = g("rc-out"); out.innerHTML = "";
    build().forEach((p, k) => {
      if (show !== 3 && show !== k) return;
      const card = h(`<div class="req"><h4 dir="ltr">${esc(p.name)}</h4><pre></pre><ul class="clean" style="font-size:.88rem">${p.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>`);
      card.querySelector("pre").textContent = `${p.url}\n${p.headers.join("\n")}\n\n${JSON.stringify(p.body, null, 2)}`;
      out.append(card);
    });
  }
  host.querySelectorAll("input, textarea, select").forEach((e) => e.addEventListener("input", draw));
  host.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { show = +b.dataset.p; host.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); }));
  draw();
}

/* ---------------- retry / backoff simulator ---------------- */
function mountRetry(host) {
  host.innerHTML = `<div class="sim">
    <div class="seg" role="group" aria-label="שיטה">
      <button data-s="fixed" aria-pressed="true">המתנה קבועה</button><button data-s="exp" aria-pressed="false">Exponential</button><button data-s="jitter" aria-pressed="false">Exponential + jitter</button></div>
    <div class="knob"><div class="knob-head"><label for="rt-n">לקוחות שנכשלים יחד</label><b id="rt-nv"></b></div><input id="rt-n" type="range" min="10" max="200" step="10" value="50"></div>
    <div class="knob"><div class="knob-head"><label for="rt-c">קיבולת השרת (בקשות לשנייה)</label><b id="rt-cv"></b></div><input id="rt-c" type="range" min="2" max="40" step="1" value="10"></div>
    <div class="knob"><div class="knob-head"><label for="rt-m">מקסימום ניסיונות</label><b id="rt-mv"></b></div><input id="rt-m" type="range" min="2" max="10" step="1" value="6"></div>
    <div class="knob"><div class="knob-head"><label for="rt-b">base (שניות)</label><b id="rt-bv"></b></div><input id="rt-b" type="range" min="0.25" max="2" step="0.25" value="1"><small>המתנה קבועה = base. Exponential = base × 2^ניסיון, עד תקרה של 16 שניות.</small></div>
    <div class="chart" id="rt-chart" role="img" aria-label="בקשות לאורך זמן"></div>
    <div class="legend"><span><i class="ok"></i>התקבלו</span><span><i class="no"></i>נדחו (429)</span><span class="muted">כל עמודה = חצי שנייה</span></div>
    <div class="stats" id="rt-stats"></div>
    <div class="row"><button class="btn small" id="rt-again">הרצה חוזרת (אקראיות אחרת)</button></div></div>`;
  const g = (id) => host.querySelector("#" + id);
  let strat = "fixed", seed = 7;
  const rng = (s) => () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  function simulate() {
    const N = +g("rt-n").value, C = +g("rt-c").value, M = +g("rt-m").value, base = +g("rt-b").value, cap = 16;
    const DT = 0.5, per = Math.max(1, Math.round(C * DT)), H = 120, R = rng(seed);
    const clients = Array.from({ length: N }, () => ({ next: 0, attempt: 0, done: false, gave: false }));
    const ok = new Array(H).fill(0), no = new Array(H).fill(0);
    let rejected = 0, finishAt = null;
    for (let b = 0; b < H; b++) {
      const t0 = b * DT;
      const arriving = clients.filter((c) => !c.done && !c.gave && c.next >= t0 && c.next < t0 + DT);
      for (let i = arriving.length - 1; i > 0; i--) { const j = Math.floor(R() * (i + 1)); [arriving[i], arriving[j]] = [arriving[j], arriving[i]]; }
      arriving.forEach((c, k) => {
        if (k < per) { c.done = true; ok[b]++; return; }
        no[b]++; rejected++; c.attempt++;
        if (c.attempt >= M) { c.gave = true; return; }
        const expo = Math.min(cap, base * 2 ** (c.attempt - 1));
        const d = strat === "fixed" ? base : strat === "exp" ? expo : R() * expo;
        c.next = t0 + DT + d;  // the reply arrives at the end of the bucket, then we wait
      });
      if (finishAt === null && clients.every((c) => c.done || c.gave)) finishAt = t0 + DT;
    }
    return { N, ok, no, rejected, gave: clients.filter((c) => c.gave).length, done: clients.filter((c) => c.done).length, finishAt, per };
  }
  function draw() {
    ["n", "c", "m"].forEach((k) => (g(`rt-${k}v`).textContent = g(`rt-${k}`).value));
    g("rt-bv").textContent = (+g("rt-b").value).toFixed(2) + "s";
    const r = simulate();
    const last = Math.max(8, ...r.ok.map((v, i) => (v || r.no[i] ? i + 1 : 0)));
    const max = Math.max(...r.ok.slice(0, last).map((v, i) => v + r.no[i]), r.per);
    const ch = g("rt-chart"); ch.innerHTML = "";
    ch.style.setProperty("--cols", last);
    for (let i = 0; i < last; i++) {
      const col = document.createElement("div"); col.className = "col";
      col.title = `${(i * 0.5).toFixed(1)}s: ${r.ok[i]} התקבלו, ${r.no[i]} נדחו`;
      const a = document.createElement("i"); a.className = "no"; a.style.height = (r.no[i] / max) * 100 + "%";
      const b = document.createElement("i"); b.className = "ok"; b.style.height = (r.ok[i] / max) * 100 + "%";
      col.append(a, b); ch.append(col);
    }
    const capLine = document.createElement("div"); capLine.className = "capline"; capLine.style.bottom = (r.per / max) * 100 + "%"; capLine.textContent = "קיבולת"; ch.append(capLine);
    g("rt-stats").innerHTML = `<span>הצליחו: <b>${r.done}/${r.N}</b></span><span>ויתרו: <b>${r.gave}</b></span><span>דחיות: <b>${r.rejected}</b></span><span>כולם סיימו אחרי: <b>${r.finishAt === null ? "לא בטווח" : r.finishAt.toFixed(1) + "s"}</b></span>`;
  }
  host.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { strat = b.dataset.s; host.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); }));
  ["rt-n", "rt-c", "rt-m", "rt-b"].forEach((id) => g(id).addEventListener("input", draw));
  g("rt-again").addEventListener("click", () => { seed = (seed * 31 + 11) % 100000; draw(); });
  draw();
}

/* ---------------- cost calculator ---------------- */
function mountCost(host) {
  // USD per 1M tokens, October 2026. heb = tokens for Hebrew text relative to English
  // (Claude and OpenAI measured in lesson 1, exercise 1; Gemini is an estimate).
  const M = [
    { id: "claude-haiku-5-5", i: 0.10, o: 0.50, heb: 1.89 },
    { id: "gpt-5.4-mini", i: 0.75, o: 4.50, heb: 1.46 },
    { id: "gemini-3.6-flash", i: 1.50, o: 7.50, heb: 1.5, est: true },
    { id: "claude-haiku-4-5", i: 1.00, o: 5.00, heb: 1.89 },
    { id: "claude-sonnet-5-5", i: 2.00, o: 10.00, heb: 1.89 },
  ];
  host.innerHTML = `<div class="sim">
    <div class="form2">
      <div class="row">
        <label>בקשות בחודש <input id="cc-n" type="number" value="10000" min="0" step="1000" dir="ltr" style="width:8rem"></label>
        <label>טוקני קלט לבקשה <input id="cc-in" type="number" value="570" min="0" dir="ltr" style="width:6rem"></label>
        <label>טוקני פלט לבקשה <input id="cc-out" type="number" value="120" min="0" dir="ltr" style="width:6rem"></label>
      </div>
      <div class="row"><label><input type="checkbox" id="cc-heb"> הטקסט בעברית (מכפיל את הטוקנים לפי הטוקנייזר של כל ספק)</label></div>
      <small class="muted">מספרי הטוקנים הם באנגלית. המחירים בדולר למיליון טוקנים, ואפשר לערוך אותם.</small>
    </div>
    <div class="stack" id="cc-rows"></div>
    <div class="callout" id="cc-note"></div></div>`;
  const g = (id) => host.querySelector("#" + id);
  const rows = g("cc-rows");
  M.forEach((m, k) => {
    const r = h(`<div class="cost-row">
      <div class="row"><b dir="ltr">${m.id}</b><span class="spacer"></span>
        <label class="pr">in $<input type="number" step="0.05" min="0" value="${m.i}" data-k="${k}" data-f="i" dir="ltr"></label>
        <label class="pr">out $<input type="number" step="0.05" min="0" value="${m.o}" data-k="${k}" data-f="o" dir="ltr"></label></div>
      <div class="cbar"><i class="ci"></i><i class="co"></i></div>
      <div class="stats"><span>בחודש: <b class="m"></b></span><span>ל-1,000 בקשות: <b class="k"></b></span><span>חלק הפלט: <b class="sh"></b></span><span class="hebnote"></span></div></div>`);
    rows.append(r);
  });
  const money = (v) => (v >= 100 ? "$" + v.toFixed(0) : v >= 1 ? "$" + v.toFixed(2) : "$" + v.toFixed(3));
  function draw() {
    const n = +g("cc-n").value || 0, tin = +g("cc-in").value || 0, tout = +g("cc-out").value || 0, heb = g("cc-heb").checked;
    const res = M.map((m) => {
      const f = heb ? m.heb : 1, ci = (n * tin * f * m.i) / 1e6, co = (n * tout * f * m.o) / 1e6;
      return { m, f, ci, co, tot: ci + co };
    });
    const max = Math.max(...res.map((r) => r.tot), 1e-9);
    [...rows.children].forEach((row, k) => {
      const r = res[k];
      row.querySelector(".ci").style.width = (r.ci / max) * 100 + "%";
      row.querySelector(".co").style.width = (r.co / max) * 100 + "%";
      row.querySelector(".m").textContent = money(r.tot);
      row.querySelector(".k").textContent = money(n ? (r.tot / n) * 1000 : 0);
      row.querySelector(".sh").textContent = r.tot ? Math.round((r.co / r.tot) * 100) + "%" : "-";
      row.querySelector(".hebnote").textContent = heb ? `×${r.f} טוקנים${r.m.est ? " (הערכה)" : ""}` : "";
    });
    const cheap = res.reduce((a, b) => (b.tot < a.tot ? b : a));
    const dear = res.reduce((a, b) => (b.tot > a.tot ? b : a));
    g("cc-note").innerHTML = `הזול ביותר כאן: <b dir="ltr">${cheap.m.id}</b>. היקר ביותר עולה פי <b>${(dear.tot / Math.max(cheap.tot, 1e-12)).toFixed(1)}</b>. בכחול: עלות הקלט, בכתום: עלות הפלט. שים לב כמה מהר הכתום גדל כשמאריכים את הפלט, כי טוקן פלט עולה פי 5 עד 6 מטוקן קלט.`;
  }
  host.querySelectorAll("input").forEach((e) => e.addEventListener("input", () => {
    if (e.dataset.k) M[+e.dataset.k][e.dataset.f] = +e.value || 0;
    draw();
  }));
  draw();
}
