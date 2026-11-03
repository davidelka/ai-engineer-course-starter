// Lesson 6 aids: the spec chain animation with traceability lines, the "make it testable" linter,
// and the traceability matrix explorer. Registered on window.AIDS; uses $, h, esc at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l06-style";
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l06-stage { position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 10px; display: grid; gap: 6px; }
.l06-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.l06-svg path { fill: none; stroke: var(--accent); stroke-width: 1.4; opacity: .28; }
.l06-svg path.hot { opacity: .95; stroke-width: 2; }
.l06-svg path.new { opacity: .9; stroke-width: 1.8; }
.l06-svg path.broken { stroke: var(--bad); stroke-dasharray: 5 4; opacity: .95; }
.l06-row { display: grid; grid-template-columns: 6.6rem minmax(0, 1fr); gap: 8px; align-items: start; padding: 6px 4px; border-radius: 8px; transition: opacity .3s, background .3s; }
.l06-row.off { opacity: .12; }
.l06-row.now { background: var(--accent-soft); }
.l06-row .lbl { font-size: .78rem; line-height: 1.3; }
.l06-row .lbl b { display: block; font-size: .86rem; }
.l06-row .lbl span { color: var(--muted); font-size: .7rem; }
.l06-items { display: flex; flex-wrap: wrap; gap: 6px; direction: ltr; justify-content: flex-start; position: relative; z-index: 1; }
.l06-it { font-family: var(--mono); font-size: .72rem; line-height: 1.3; padding: 4px 7px; border-radius: 7px; border: 1px solid var(--line); background: var(--surface); text-align: left; max-width: 100%; white-space: normal; overflow-wrap: anywhere; transition: opacity .2s, border-color .2s, background .2s; }
.l06-it small { display: block; color: var(--muted); font-size: .64rem; }
.l06-it.hl { border-color: var(--accent); background: var(--accent-soft); }
.l06-it.dim { opacity: .3; }
.l06-it.bad { border-color: var(--bad); background: var(--bad-soft); }
.l06-it.warn { border-color: var(--signal); background: var(--signal-soft); }
.l06-it.ghost { border-style: dashed; border-color: var(--bad); color: var(--bad); background: transparent; }
.l06-what { display: grid; gap: 6px; }
.l06-what label { display: flex; gap: 8px; align-items: flex-start; font-size: .88rem; line-height: 1.5; }
.l06-ta { width: 100%; min-height: 64px; font-family: var(--mono); font-size: .8rem; color: var(--ink); background: var(--code-bg); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; direction: ltr; text-align: left; resize: vertical; }
.l06-find { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; font-size: .84rem; }
.l06-find li { padding: 3px 8px; border-radius: 6px; background: var(--bad-soft); }
.l06-find li.w { background: var(--signal-soft); }
.l06-find li.ok { background: var(--good-soft); color: var(--good); font-weight: 500; }
.l06-orig { font-family: var(--mono); font-size: .78rem; direction: ltr; text-align: left; color: var(--muted); background: var(--code-bg); border-radius: 8px; padding: 6px 10px; overflow-wrap: anywhere; }
.l06-mrow { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 6px; background: var(--surface); }
.l06-mrow > button { all: unset; cursor: pointer; display: grid; grid-template-columns: 4.2rem 5.6rem minmax(0, 1fr) auto; gap: 8px; align-items: center; font-size: .86rem; }
.l06-mrow > button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }
.l06-mrow .id { font-family: var(--mono); font-weight: 600; direction: ltr; text-align: left; }
.l06-st { font-family: var(--mono); font-size: .7rem; padding: 2px 6px; border-radius: 999px; text-align: center; }
.l06-st.PASSING { background: var(--good-soft); color: var(--good); }
.l06-st.FAILING { background: var(--bad-soft); color: var(--bad); }
.l06-st.UNTESTED { background: var(--signal-soft); color: var(--signal); }
.l06-mrow .n { font-family: var(--mono); font-size: .74rem; color: var(--muted); }
.l06-detail { display: grid; gap: 6px; font-size: .84rem; border-top: 1px dashed var(--line); padding-top: 6px; }
.l06-detail .en { direction: ltr; text-align: left; font-family: var(--mono); font-size: .76rem; overflow-wrap: anywhere; }
.l06-detail ul { margin: 0; padding-inline-start: 1.1em; display: grid; gap: 3px; }
.l06-nets { display: grid; gap: 6px; }
.l06-net { display: grid; grid-template-columns: 1.4rem minmax(0, 1fr); gap: 6px; font-size: .86rem; align-items: start; }
.l06-net i { font-style: normal; font-weight: 700; text-align: center; border-radius: 6px; }
.l06-net i.y { background: var(--good-soft); color: var(--good); }
.l06-net i.n { background: var(--bad-soft); color: var(--bad); }
@media (max-width: 480px) {
  .l06-row { grid-template-columns: minmax(0, 1fr); gap: 4px; }
  .l06-mrow > button { grid-template-columns: 3.9rem 5.2rem minmax(0, 1fr); }
  .l06-mrow .n { display: none; }
}`;
    document.head.append(s);
  }

  /* ======================================================================
     Animation: intent -> requirements -> criteria -> contract -> plan -> tasks -> tests -> code
     ====================================================================== */
  const ROWS = [
    { k: "intent", he: "כוונה", who: "ארכיטקט" },
    { k: "req", he: "דרישות", who: "אדם (EARS)" },
    { k: "ac", he: "קריטריוני קבלה", who: "אדם (GIVEN/WHEN/THEN)" },
    { k: "contract", he: "חוזה", who: "אדם (OpenAPI)" },
    { k: "plan", he: "תוכנית", who: "סוכן מנסח, אדם מאשר" },
    { k: "tasks", he: "משימות", who: "סוכן מנסח, אדם מאשר" },
    { k: "tests", he: "בדיקות", who: "לא הסוכן המממש" },
    { k: "code", he: "קוד", who: "הסוכן" },
  ];
  const ITEMS = [
    { id: "I1", row: "intent", t: "No request that needs a human is approved without one", p: [] },
    { id: "I2", row: "intent", t: "Every status change can be audited", p: [] },
    { id: "REQ-4", row: "req", t: "REQ-4 Route by policy", p: ["I1"] },
    { id: "REQ-8", row: "req", t: "REQ-8 Approve with authority", p: ["I1"] },
    { id: "REQ-9", row: "req", t: "REQ-9 Refuse without authority", p: ["I1"] },
    { id: "REQ-10", row: "req", t: "REQ-10 Refuse closed requests", p: ["I1"] },
    { id: "REQ-11", row: "req", t: "REQ-11 Audit every change", p: ["I2"] },
    { id: "AC-4.2", row: "ac", t: "AC-4.2 Slack admin → needs_security", p: ["REQ-4"] },
    { id: "AC-4.7", row: "ac", t: "AC-4.7 \"  aws \" read → needs_security", p: ["REQ-4"] },
    { id: "AC-8.1", row: "ac", t: "AC-8.1 manager approves → 200", p: ["REQ-8"] },
    { id: "AC-9.1", row: "ac", t: "AC-9.1 manager on security → 403, still pending", p: ["REQ-9"] },
    { id: "AC-10.1", row: "ac", t: "AC-10.1 approved again → 409", p: ["REQ-10"] },
    { id: "AC-11.2", row: "ac", t: "AC-11.2 approval → one audit record", p: ["REQ-11"] },
    { id: "C1", row: "contract", t: "POST /access-requests", sub: "route: enum of 3", p: ["REQ-4"] },
    { id: "C2", row: "contract", t: "POST /…/approve", sub: "200 · 403 · 404 · 409", p: ["REQ-8", "REQ-9", "REQ-10"] },
    { id: "C3", row: "contract", t: "Error.code", sub: "forbidden · conflict", p: ["REQ-9", "REQ-10"] },
    { id: "P1", row: "plan", t: "routing.py: route_for() pure", p: ["C1"] },
    { id: "P2", row: "plan", t: "approve(): 404 → 409 → 403", p: ["C2", "C3"] },
    { id: "P3", row: "plan", t: "logger access_api.audit", p: ["REQ-11"] },
    { id: "T2", row: "tasks", t: "T2 route_for + table test", sub: "(REQ-4)", p: ["P1"] },
    { id: "T5", row: "tasks", t: "T5 create + audit", sub: "(REQ-11)", p: ["P3"] },
    { id: "T6", row: "tasks", t: "T6 approve endpoint", sub: "(REQ-8, 9, 10, 11)", p: ["P2", "P3"] },
    { id: "t1", row: "tests", t: "test_route[AC-4.2]", sub: "@req(\"REQ-4\")", p: ["AC-4.2", "T2"] },
    { id: "t2", row: "tests", t: "test_route[AC-4.7]", sub: "@req(\"REQ-4\")", p: ["AC-4.7", "T2"] },
    { id: "t3", row: "tests", t: "test_manager_approves…", sub: "@req(\"REQ-8\")", p: ["AC-8.1", "T6"] },
    { id: "t4", row: "tests", t: "test_manager_cannot_approve…", sub: "@req(\"REQ-9\")", p: ["AC-9.1", "T6"] },
    { id: "t5", row: "tests", t: "test_already_approved_is_409", sub: "@req(\"REQ-10\")", p: ["AC-10.1", "T6"] },
    { id: "t6", row: "tests", t: "test_approval_writes_audit…", sub: "@req(\"REQ-11\")", p: ["AC-11.2", "T6"] },
    { id: "k1", row: "code", t: "routing.py route_for()", p: ["T2", "t1", "t2"] },
    { id: "k2", row: "code", t: "app.py approve()", p: ["T6", "t3", "t4", "t5"] },
    { id: "k3", row: "code", t: "app.py log_change()", p: ["T5", "T6", "t6"] },
  ];
  const STEPS = [
    ["כוונה", "הכול מתחיל בשתי שורות של הארכיטקט: מה חייב להיות נכון כשהפיצ'ר עובד. אין כאן עדיין שום פרט טכני, וזה בכוונה: זה מה שכל שאר השרשרת צריכה לשרת, ומה שסוקר בודק כשהוא שואל \"זה בכלל מה שצריך?\"."],
    ["דרישות", "כל כוונה מתפרקת לדרישות ממוספרות, כל אחת התנהגות אחת שאפשר לראות מבחוץ, במשפט EARS עם SHALL. הקווים מראים מאיזו כוונה כל דרישה נגזרת: ארבע דרישות משרתות את \"אף בקשה לא מאושרת בלי אדם\"."],
    ["קריטריוני קבלה", "לכל דרישה יש דוגמאות קונקרטיות בצורת GIVEN/WHEN/THEN. כל קריטריון יהפוך לבדיקה אחת. שים לב ש-REQ-4 מונה חמישה כלים רגישים, ויש קריטריון רק ל-AWS: זה יחזור בניסוי השלישי."],
    ["חוזה", "החוזה ב-OpenAPI מקבע את הממשק: נתיבים, שדות וקודי סטטוס. הוא נגזר מהדרישות (403 קיים בגלל REQ-9, 409 בגלל REQ-10), אבל הוא לא אומר מתי כל קוד מוחזר. את זה רק הדרישה אומרת."],
    ["תוכנית", "עכשיו נכנסות ההחלטות הטכניות: אילו קבצים, ואיך הם מתחברים. סוקר יכול לקרוא את שלוש השורות האלה בדקה ולתפוס עיצוב שגוי לפני שיש קוד. את התוכנית אפשר לתת לסוכן לנסח, ולך לאשר."],
    ["משימות", "התוכנית מתפרקת למשימות קטנות, כל אחת עם הפניה לדרישות שהיא מממשת. בסוף כל משימה יש משהו שרץ ועובר."],
    ["בדיקות", "כל קריטריון הופך לבדיקה אחת, שמסומנת במזהה הדרישה (@pytest.mark.req). זה הקו שמטריצת ה-traceability עוקבת אחריו. כדאי שמי שכותב אותן לא יהיה הסוכן שמממש."],
    ["קוד", "רק עכשיו הסוכן כותב קוד, והבדיקות הן מה שמכריע אם הוא הצליח. השרשרת מלאה: לחץ על כל פריט כדי לראות את כל מה שמחובר אליו, לשני הכיוונים, ואחר כך נסה את שלושת הניסויים."],
  ];

  window.AIDS.l06chain = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="sim">
      <p style="margin:0">שמונה שורות, מלמעלה למטה: מה הארכיטקט רוצה, ועד הקוד שהסוכן כותב. בכל צעד נוספת שורה, והקווים מראים <b>מאיזה פריט כל פריט נגזר</b>. בסוף, לחץ על פריט כדי לסמן את כל השרשרת שלו.</p>
      <div class="l06-stage" id="l6c-stage"><svg class="l06-svg" id="l6c-svg" aria-hidden="true"></svg></div>
      <div class="cap"><b id="l6c-t"></b><div id="l6c-b" class="muted"></div></div>
      <div class="row"><button class="btn small primary" id="l6c-play">השהה</button><button class="btn small" id="l6c-prev" aria-label="צעד קודם">→</button><button class="btn small" id="l6c-next" aria-label="צעד הבא">←</button><button class="btn small" id="l6c-clear">נקה סימון</button><span class="spacer"></span><span class="counter" id="l6c-c"></span></div>
      <details class="cd-what l06-what" id="l6c-what"><summary>מה קורה אם... (שלושה ניסויים)</summary>
        <label><input type="checkbox" id="l6c-e1"> <span><b>REQ-10 בלי בדיקה.</b> כמו במעבדה לפני תרגיל 3: יש דרישה וקריטריון, ואף בדיקה לא מצביעה עליהם.</span></label>
        <label><input type="checkbox" id="l6c-e2"> <span><b>נתיב reject בלי מפרט.</b> מישהו הוסיף לקוד <code>reject()</code> ובדיקה מסומנת REQ-12, ולא עדכן את המפרט ואת החוזה.</span></label>
        <label><input type="checkbox" id="l6c-e3"> <span><b>Kubernetes נמחק מ-routing.py.</b> שינוי קטן בקוד, שאף בדיקה לא אמורה להרגיש בו. האם משהו נשבר?</span></label>
      </details></div>`;
    const g = (id) => host.querySelector("#" + id);
    const stage = g("l6c-stage"), svg = g("l6c-svg");
    ROWS.forEach((r, i) => {
      const row = document.createElement("div");
      row.className = "l06-row";
      row.dataset.i = i;
      row.innerHTML = `<div class="lbl"><b>${esc(r.he)}</b><span>${esc(r.who)}</span></div><div class="l06-items" data-row="${r.k}"></div>`;
      stage.append(row);
    });
    let step = 0, sel = null, timer = null;
    let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ex = () => ({ e1: g("l6c-e1").checked, e2: g("l6c-e2").checked, e3: g("l6c-e3").checked });

    function items() {
      const e = ex();
      let list = ITEMS.map((x) => ({ ...x }));
      if (e.e1) list = list.filter((x) => x.id !== "t5");
      if (e.e2) {
        list.push({ id: "t7", row: "tests", t: "test_manager_rejects", sub: "@req(\"REQ-12\")", p: ["REQ-12?"], cls: "bad" });
        list.push({ id: "k4", row: "code", t: "app.py reject()", sub: "no task, no requirement", p: ["t7"], cls: "bad" });
        list.push({ id: "REQ-12?", row: "req", t: "REQ-12 (not in spec)", ghost: true, p: [] });
        list.push({ id: "C4?", row: "contract", t: "POST /…/reject (not in contract)", ghost: true, p: [] });
      }
      if (e.e3) {
        list.find((x) => x.id === "k1").cls = "warn";
        list.find((x) => x.id === "k1").sub = "Kubernetes removed";
        list.push({ id: "AC-4.8?", row: "ac", t: "AC-4.8 Kubernetes → needs_security (missing)", ghost: true, p: ["REQ-4"] });
      }
      if (e.e1) {
        list.find((x) => x.id === "REQ-10").cls = "bad";
        list.find((x) => x.id === "AC-10.1").cls = "bad";
      }
      return list;
    }
    function related(list, id) {
      const byId = Object.fromEntries(list.map((x) => [x.id, x]));
      const kids = {};
      list.forEach((x) => x.p.forEach((p) => (kids[p] = kids[p] || []).push(x.id)));
      const out = new Set([id]);
      const up = [id], down = [id];
      while (up.length) { const c = byId[up.pop()]; if (c) c.p.forEach((p) => { if (!out.has(p)) { out.add(p); up.push(p); } }); }
      while (down.length) { const c = down.pop(); (kids[c] || []).forEach((k) => { if (!out.has(k)) { out.add(k); down.push(k); } }); }
      return out;
    }
    function draw() {
      const list = items();
      const visible = new Set(ROWS.slice(0, step + 1).map((r) => r.k));
      host.querySelectorAll(".l06-row").forEach((row) => {
        const i = +row.dataset.i;
        row.classList.toggle("off", i > step);
        row.classList.toggle("now", i === step && step < ROWS.length - 1);
      });
      const rel = sel && list.some((x) => x.id === sel) ? related(list, sel) : null;
      host.querySelectorAll(".l06-items").forEach((box) => {
        box.innerHTML = "";
        list.filter((x) => x.row === box.dataset.row).forEach((x) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "l06-it" + (x.ghost ? " ghost" : "") + (x.cls ? " " + x.cls : "") +
            (rel ? (rel.has(x.id) ? " hl" : " dim") : "");
          b.dataset.id = x.id;
          b.innerHTML = esc(x.t) + (x.sub ? `<small>${esc(x.sub)}</small>` : "");
          b.disabled = !visible.has(x.row);
          b.addEventListener("click", () => { setP(false); step = ROWS.length - 1; sel = sel === x.id ? null : x.id; draw(); explain(); });
          box.append(b);
        });
      });
      lines(list, rel);
      explain();
    }
    function lines(list, rel) {
      const box = stage.getBoundingClientRect();
      svg.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
      svg.innerHTML = "";
      const rowIdx = Object.fromEntries(ROWS.map((r, i) => [r.k, i]));
      const el = (id) => stage.querySelector(`.l06-it[data-id="${CSS.escape(id)}"]`);
      list.forEach((x) => {
        if (rowIdx[x.row] > step) return;
        x.p.forEach((pid) => {
          const par = list.find((y) => y.id === pid);
          if (!par || rowIdx[par.row] > step) return;
          const a = el(pid), b = el(x.id);
          if (!a || !b) return;
          const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
          const x1 = ra.left + ra.width / 2 - box.left, y1 = ra.bottom - box.top;
          const x2 = rb.left + rb.width / 2 - box.left, y2 = rb.top - box.top;
          const my = (y1 + y2) / 2;
          const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
          path.setAttribute("d", `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`);
          const broken = par.ghost || x.ghost;
          let cls = broken ? "broken" : "";
          if (rel && rel.has(pid) && rel.has(x.id)) cls += " hot";
          else if (!rel && rowIdx[x.row] === step && step < ROWS.length - 1) cls += " new";
          path.setAttribute("class", cls.trim());
          svg.append(path);
        });
      });
    }
    function explain() {
      const e = ex();
      let t, b;
      if (sel && step === ROWS.length - 1) {
        const it = items().find((x) => x.id === sel);
        t = `השרשרת של ${it ? it.t : sel}`;
        b = "מסומן כל מה שהפריט נגזר ממנו (למעלה) וכל מה שנגזר ממנו (למטה). זו השאלה שמטריצת traceability עונה עליה: מאיפה זה בא, ומה ייפגע אם זה ישתנה. לחיצה נוספת על אותו פריט מבטלת את הסימון.";
      } else {
        [t, b] = STEPS[step];
      }
      const notes = [];
      if (step === ROWS.length - 1) {
        if (e.e1) notes.push("ניסוי 1: ל-REQ-10 ול-AC-10.1 אין אף קו שיורד לבדיקה. המטריצה תסמן את REQ-10 כ-UNTESTED. אם מישהו ישבור את ה-409, שום דבר לא ייכשל.");
        if (e.e2) notes.push("ניסוי 2: הבדיקה החדשה מצביעה על REQ-12, שלא קיים במפרט (מסגרת מקווקוות), והנתיב לא קיים בחוזה. המטריצה תדווח על orphan, והשוואת החוזים על פעולה לא מתועדת. בדיקות הקבלה ובדיקת החוזה לא ירגישו: הן בודקות רק מה שמתועד.");
        if (e.e3) notes.push("ניסוי 3: routing.py השתנה (כתום), אבל הבדיקות של REQ-4 בודקות רק Slack admin ו-AWS, ולכן הכול ירוק. הקריטריון שהיה תופס את זה, AC-4.8, לא קיים (מקווקו). כיסוי של דרישה הוא לא כיסוי של כל סעיף בה.");
      }
      g("l6c-t").textContent = t;
      g("l6c-b").textContent = [b, ...notes].join(" ");
      g("l6c-c").textContent = `צעד ${step + 1}/${ROWS.length}`;
    }
    const tick = () => { clearTimeout(timer); if (playing && step < ROWS.length - 1) timer = setTimeout(() => { step++; draw(); tick(); }, 3600); else if (step >= ROWS.length - 1) setP(false, true); };
    function setP(p, quiet) { playing = p; g("l6c-play").textContent = p ? "השהה" : (step >= ROWS.length - 1 ? "מההתחלה" : "נגן"); if (!quiet) tick(); }
    g("l6c-play").addEventListener("click", () => { if (!playing && step >= ROWS.length - 1) { step = 0; sel = null; draw(); } setP(!playing); });
    g("l6c-next").addEventListener("click", () => { setP(false); step = Math.min(ROWS.length - 1, step + 1); draw(); });
    g("l6c-prev").addEventListener("click", () => { setP(false); step = Math.max(0, step - 1); sel = null; draw(); });
    g("l6c-clear").addEventListener("click", () => { sel = null; draw(); });
    ["l6c-e1", "l6c-e2", "l6c-e3"].forEach((id) => g(id).addEventListener("change", () => { setP(false); step = ROWS.length - 1; draw(); }));
    const ro = new ResizeObserver(() => lines(items(), sel ? related(items(), sel) : null));
    ro.observe(stage);
    draw();
    setP(playing);
    return () => { clearTimeout(timer); ro.disconnect(); };
  };

  /* ======================================================================
     Sim: make it testable (a JS port of spectools/lint.py)
     ====================================================================== */
  const VAGUE = ["fast", "quickly", "slow", "simple", "easy", "easily", "user-friendly", "intuitive", "appropriate",
    "appropriately", "relevant", "reasonable", "robust", "scalable", "efficient", "flexible", "gracefully", "properly",
    "seamless", "seamlessly", "as needed", "if possible", "etc", "and so on", "some", "several", "many", "normal",
    "usually", "generally", "tbd", "best", "optimal", "adequate", "sufficient"];
  const WEAK = ["should", "may", "might", "could"];
  const words = (text, list) => list.filter((w) => new RegExp("(?<![\\w-])" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\w-])", "i").test(text));
  function gwt(text) {
    let pos = 0;
    for (const kw of ["given", "when", "then"]) {
      const m = new RegExp("\\b" + kw + "\\b", "i").exec(text.slice(pos));
      if (!m) return false;
      pos += m.index + kw.length;
    }
    return true;
  }
  function lintOne(stmt, ac, nfr) {
    const out = [];
    const st = stmt.trim();
    if (!st) out.push(["e", "missing-statement: אין משפט דרישה"]);
    else {
      if (!/\bshall\b/i.test(st) || !/^(the|when|while|if|where)\s/i.test(st)) out.push(["e", "not-ears: המשפט צריך להתחיל ב-THE / WHEN / WHILE / IF / WHERE ולכלול SHALL"]);
      words(st, WEAK).forEach((w) => out.push(["w", `weak-modal: המילה "${w}" במשפט. כתוב SHALL, או WHERE אם זה באמת אופציונלי`]));
      words(st, VAGUE).forEach((w) => out.push(["e", `vague-word: המילה "${w}" במשפט`]));
      if (nfr && !/\d/.test(st)) out.push(["e", "nfr-not-measurable: דרישה לא-פונקציונלית בלי מספר"]);
    }
    const a = ac.trim();
    if (!a) out.push(["e", "no-criteria: אין קריטריון קבלה"]);
    else {
      if (!gwt(a)) out.push(["e", "criterion-not-gwt: הקריטריון צריך GIVEN, אחריו WHEN, אחריו THEN"]);
      words(a, VAGUE).forEach((w) => out.push(["e", `vague-word: המילה "${w}" בקריטריון`]));
    }
    return out;
  }
  const CASES = [
    { id: "REQ-1", nfr: false, stmt: "WHEN an employee submits a request, THE SYSTEM SHALL store it quickly and return it.",
      ac: "GIVEN a request WHEN it is posted THEN it works properly.",
      good: ["WHEN an authenticated caller sends a valid NewAccessRequest to POST /access-requests, THE SYSTEM SHALL store it, assign an id matching ^ar_[0-9a-z]+$, set requester to the X-Actor header, and respond 201 with the stored AccessRequest.",
        "GIVEN a valid body for Jira read access WHEN dana@acme.example posts it THEN the response is 201 AND requester is dana@acme.example."],
      tip: "\"quickly\" עובר ל-NFR עם מספר. \"return it\" הופך לקוד סטטוס ולשדות. \"works properly\" הופך לתוצאה שאפשר לבדוק." },
    { id: "REQ-4", nfr: false, stmt: "THE SYSTEM SHALL route requests to the appropriate track according to the policy, etc.",
      ac: "Requests for admin access go to security.",
      good: ["WHEN a request is created, THE SYSTEM SHALL set route by the first matching rule: needs_security if access_level is admin, any sensitive flag is true, or the tool is one of AWS, GCP, Kubernetes, NetSuite, Payroll; needs_manager if the tool is not on the approved list or access_level is write; auto_approve otherwise.",
        "GIVEN Slack with admin WHEN created THEN route is needs_security."],
      tip: "\"appropriate\" ו-\"etc\" מוחלפים בכללים מפורשים בסדר קבוע. הקריטריון הופך לדוגמה עם קלט מדויק ותוצאה מדויקת." },
    { id: "REQ-2", nfr: false, stmt: "The system should handle invalid input gracefully.", ac: "",
      good: ["IF the body, a query parameter or a path parameter does not match spec/openapi.yaml, THEN THE SYSTEM SHALL respond 422 with error code validation_error and SHALL NOT store anything.",
        "GIVEN a body without justification WHEN it is posted THEN the response is 422 AND error.code is validation_error AND total did not change."],
      tip: "מקרי שגיאה נכתבים בתבנית IF ... THEN. \"gracefully\" הופך לקוד סטטוס, צורת שגיאה, ומה שלא קורה (לא נשמר)." },
    { id: "NFR-1", nfr: true, stmt: "THE SYSTEM SHALL be fast and scalable.",
      ac: "GIVEN normal load WHEN requests are sent THEN responses are fast.",
      good: ["WHILE 1,000 requests are stored, THE SYSTEM SHALL answer POST and GET /access-requests with a p95 latency of at most 50 ms each, measured in-process over 200 calls.",
        "GIVEN 1,000 stored requests WHEN 200 creates and 200 lists are timed THEN the p95 of each is at most 50 ms."],
      tip: "ארבעה חלקים: מצב (1,000 רשומות), מדד (p95), סף ויחידה (50 ms), ואיך מודדים (in-process, 200 קריאות). \"scalable\" בלי מספר נמחק או הופך ל-NFR נפרדת." },
    { id: "REQ-6", nfr: false, stmt: "WHEN a user lists requests, THE SYSTEM SHALL return the relevant requests and may filter them by status.",
      ac: "GIVEN some requests WHEN they are listed THEN they are shown as needed.",
      good: ["WHEN a caller sends GET /access-requests, THE SYSTEM SHALL return the requests that match the optional status filter, ordered by created_at descending with ties broken by id descending, at most limit items (default 20, allowed 1 to 100).",
        "GIVEN requests A, B, C created in that order WHEN the caller lists THEN the ids come back as C, B, A."],
      tip: "\"may filter\" אומר שהסינון אופציונלי למימוש. הכוונה היא שהפרמטר אופציונלי לקורא, וזה כתוב כ-\"the optional status filter\". \"relevant\" ו-\"as needed\" הופכים לסדר מפורש ולמגבלה מספרית." },
  ];

  window.AIDS.l06testable = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="sim">
      <div class="guide"><p><b>מה רואים:</b> חמש דרישות מטיוטה חפוזה. לכל אחת יש שתי תיבות: <b>משפט הדרישה</b> ו<b>קריטריון קבלה</b> אחד. מתחת לתיבות מופיעים הממצאים של ה-linter, אותם כללים כמו ב-spec_lint.py של המעבדה, והם מתעדכנים בזמן שאתה מקליד. אדום הוא שגיאה, כתום הוא אזהרה, וירוק אומר שה-linter לא מוצא כלום.</p><p><b>מה לעשות:</b> שכתב עד שיופיע ירוק, ורק אז לחץ על "הצג שכתוב לדוגמה" (מתוך SPEC-006) והשווה. זכור שירוק אומר רק שהצורה תקינה, לא שהדרישה נכונה.</p></div>
      <div id="l6t-list" class="stack"></div></div>`;
    const list = host.querySelector("#l6t-list");
    CASES.forEach((c, k) => {
      const el = h(`<div class="req">
        <div class="row"><b>${k + 1}.</b><span class="pill">${esc(c.id)}</span>${c.nfr ? '<span class="pill">non-functional</span>' : ""}</div>
        <div class="l06-orig"></div>
        <label class="muted" style="font-size:.8rem">משפט הדרישה (Statement)</label>
        <textarea class="l06-ta" data-f="stmt" rows="3" spellcheck="false"></textarea>
        <label class="muted" style="font-size:.8rem">קריטריון קבלה (Acceptance criterion)</label>
        <textarea class="l06-ta" data-f="ac" rows="2" spellcheck="false"></textarea>
        <ul class="l06-find"></ul>
        <div class="row"><button class="btn small" data-a="show">הצג שכתוב לדוגמה</button><button class="btn small" data-a="reset">חזרה למקור</button></div>
        <div class="l06-model" hidden></div></div>`);
      el.querySelector(".l06-orig").textContent = "Original: " + c.stmt + (c.ac ? "  |  " + c.ac : "  |  (no criterion)");
      const ts = el.querySelector('[data-f="stmt"]'), ta = el.querySelector('[data-f="ac"]');
      ts.value = c.stmt; ta.value = c.ac;
      const upd = () => {
        const f = lintOne(ts.value, ta.value, c.nfr);
        el.querySelector(".l06-find").innerHTML = f.length
          ? f.map(([s, m]) => {
            const i = m.indexOf(": ");
            const rule = i > 0 && /^[a-z-]+$/.test(m.slice(0, i)) ? m.slice(0, i) : "";
            const text = rule ? m.slice(i + 2) : m;
            return `<li class="${s === "w" ? "w" : ""}">${rule ? `<code>${esc(rule)}</code> ` : ""}${esc(text)}</li>`;
          }).join("")
          : '<li class="ok">נקי: ה-linter לא מוצא כלום. עכשיו שאל את עצמך אם שני מממשים היו בונים מזה אותו דבר.</li>';
      };
      ts.addEventListener("input", upd); ta.addEventListener("input", upd);
      el.querySelector('[data-a="reset"]').addEventListener("click", () => { ts.value = c.stmt; ta.value = c.ac; upd(); });
      el.querySelector('[data-a="show"]').addEventListener("click", (ev) => {
        const m = el.querySelector(".l06-model");
        m.hidden = !m.hidden;
        ev.target.textContent = m.hidden ? "הצג שכתוב לדוגמה" : "הסתר שכתוב לדוגמה";
        m.innerHTML = `<div class="l06-orig" style="color:var(--ink)"></div><div class="l06-orig" style="color:var(--ink);margin-top:4px"></div><p class="muted" style="margin:6px 0 0;font-size:.86rem"></p>`;
        const [a, b] = m.querySelectorAll(".l06-orig");
        a.textContent = c.good[0]; b.textContent = c.good[1];
        m.querySelector("p").textContent = c.tip;
      });
      upd();
      list.append(el);
    });
  };

  /* ======================================================================
     Sim: traceability matrix explorer (data from the real lab runs)
     ====================================================================== */
  const REQS = [
    ["REQ-1", "Create an access request", "WHEN an authenticated caller sends a valid NewAccessRequest, THE SYSTEM SHALL store it, assign an id, set requester from X-Actor, and respond 201.", ["AC-1.1 201 with id and requester", "AC-1.2 requester in body → 422", "AC-1.3 stored equals the 201 body"],
      ["test_acc_create.py::test_create_returns_201_with_id_and_requester", "test_acc_create.py::test_requester_cannot_come_from_the_body", "test_acc_create.py::test_stored_request_equals_the_201_body"]],
    ["REQ-2", "Reject invalid input", "IF the body, a query or a path parameter does not match the contract, THEN THE SYSTEM SHALL respond 422 validation_error and SHALL NOT store anything.", ["AC-2.1 no justification → 422", "AC-2.2 superuser → 422", "AC-2.3 9-char justification → 422", "AC-2.4 total unchanged"],
      ["test_acc_create.py::test_invalid_body_is_422_and_nothing_is_stored", "test_acc_create.py::test_requester_cannot_come_from_the_body", "test_acc_list_get.py::test_limit_out_of_range_is_422"]],
    ["REQ-3", "Identify the caller", "IF X-Actor is missing, has no @, or is not 3-254 characters, or X-Role is not employee/manager/security, THEN THE SYSTEM SHALL respond 401 unauthenticated.", ["AC-3.1 no X-Actor → 401", "AC-3.2 X-Role admin → 401"],
      ["test_acc_create.py::test_missing_actor_is_401", "test_acc_create.py::test_bad_identity_is_401_on_list"]],
    ["REQ-4", "Route by policy", "WHEN a request is created, THE SYSTEM SHALL set route by the first matching rule (security: admin, flags, AWS/GCP/Kubernetes/NetSuite/Payroll; manager: unlisted tool, write, Figma/GitHub standard; else auto).", ["AC-4.1 Jira read → auto", "AC-4.2 Slack admin → security", "AC-4.3 customer_data → security", "AC-4.4 Notion → manager", "AC-4.5 GitHub write → manager", "AC-4.6 Figma standard → manager", "AC-4.7 \"  aws \" → security"],
      ["test_acc_routing.py::test_route"]],
    ["REQ-5", "Set the initial status", "WHEN created with auto_approve, THE SYSTEM SHALL set approved by system; otherwise pending with nulls.", ["AC-5.1 auto → approved by system", "AC-5.2 manager track → pending"],
      ["test_acc_create.py::test_auto_approve_is_approved_by_system_at_creation", "test_acc_create.py::test_other_routes_start_pending"]],
    ["REQ-6", "List requests", "WHEN a caller lists, THE SYSTEM SHALL return matches newest first (ties by id), at most limit (default 20, 1-100), with total.", ["AC-6.1 C, B, A", "AC-6.2 25 stored → 20 items, total 25", "AC-6.3 status filter", "AC-6.4 limit 101 → 422"],
      ["test_acc_list_get.py::test_newest_first", "test_acc_list_get.py::test_default_limit_is_20_and_total_counts_all", "test_acc_list_get.py::test_status_filter", "test_acc_list_get.py::test_limit_out_of_range_is_422"]],
    ["REQ-7", "Get one request", "WHEN a caller gets an existing id, THE SYSTEM SHALL respond 200; IF it does not exist, THEN 404 not_found (also on approve).", ["AC-7.1 unknown id → 404", "AC-7.2 approve unknown → 404"],
      ["test_acc_create.py::test_stored_request_equals_the_201_body", "test_acc_list_get.py::test_unknown_id_is_404", "test_acc_list_get.py::test_approving_unknown_id_is_404"]],
    ["REQ-8", "Approve with the right authority", "WHEN an allowed role approves a pending request, THE SYSTEM SHALL set approved, decided_by and decided_at. Manager track: manager or security; security track: security.", ["AC-8.1 manager approves manager track", "AC-8.2 security approves security track", "AC-8.3 security approves manager track"],
      ["test_acc_approve.py::TestAuthority::test_manager_approves_manager_track", "test_acc_approve.py::TestAuthority::test_security_approves_security_track", "test_acc_approve.py::TestAuthority::test_security_may_approve_manager_track"]],
    ["REQ-9", "Refuse approvals without authority", "IF the role is not allowed for the route, OR the caller is the requester, THEN THE SYSTEM SHALL respond 403 forbidden and SHALL NOT change the request.", ["AC-9.1 manager on security → 403, still pending", "AC-9.2 employee → 403", "AC-9.3 own request → 403"],
      ["test_acc_approve.py::TestForbidden::test_manager_cannot_approve_security_track", "test_acc_approve.py::TestForbidden::test_employee_cannot_approve", "test_acc_approve.py::TestForbidden::test_nobody_approves_their_own_request"]],
    ["REQ-10", "Refuse decisions on closed requests", "IF a caller approves a request whose status is not pending, THEN THE SYSTEM SHALL respond 409 conflict and SHALL NOT change it. Checked after 404, before 403.", ["AC-10.1 auto-approved, security approves → 409", "AC-10.2 second manager → 409, decided_by kept"],
      []],
    ["REQ-11", "Audit every status change", "WHEN a status is set or changed, THE SYSTEM SHALL write one JSON record to access_api.audit with request_id, actor, from_status, to_status.", ["AC-11.1 creation → one record, actor system", "AC-11.2 approval → one record, actor manager"],
      ["test_acc_create.py::test_creation_writes_one_audit_record", "test_acc_approve.py::test_approval_writes_one_audit_record"]],
    ["NFR-1", "Latency", "WHILE 1,000 requests are stored, THE SYSTEM SHALL answer POST and GET with p95 ≤ 50 ms, in-process, over 200 calls.", ["AC-N1.1 p95 of each ≤ 50 ms"],
      ["test_acc_nfr.py::test_p95_latency_with_1000_stored"]],
    ["NFR-2", "Contract conformance", "THE SYSTEM SHALL return documented status codes and schema-valid bodies for every request the contract describes, and never 5xx.", ["AC-N2.1 Schemathesis finds no failure"],
      ["test_acc_nfr.py::test_contract"]],
  ];
  const EX3 = ["test_acc_approve.py::TestConflict::test_already_approved_is_409", "test_acc_approve.py::TestConflict::test_second_approval_is_409_and_keeps_first"];
  // Failing tests per scenario, from `drift_demo.py --all --reference` (November 2026 run).
  const SCEN = {
    base: { he: "מצב התחלתי", story: "המימוש לדוגמה עם בדיקות הקבלה כמו שהן מגיעות במעבדה.", fail: [], nets: null },
    ex3: { he: "אחרי תרגיל 3", story: "הוספת שתי בדיקות ל-REQ-10, לפי AC-10.1 ו-AC-10.2.", fail: [], add: true, nets: null },
    reject_route: { he: "drift: reject_route", story: "מישהו הוסיף נתיב reject וסטטוס rejected, עם בדיקה מסומנת REQ-12, בלי לעדכן מפרט וחוזה.", fail: [], orphan: { "REQ-12": ["test_change.py::test_manager_rejects_request"] },
      nets: { traceability: [true, "מזהה יתום: REQ-12 לא קיים במפרט."], diff: [true, "פעולה לא מתועדת POST /access-requests/{}/reject, ו-enum של status עם rejected."], contract: [false, "Schemathesis בודק רק פעולות שבחוזה, והנתיב החדש לא שם."], acceptance: [false, "כל הבדיקות עוברות: אף אחת לא נוגעת ב-reject."] } },
    renamed_status: { he: "drift: renamed_status", story: "approved שונה ל-granted בקוד, כי כך קוראים לזה ב-UI.",
      fail: ["test_acc_create.py::test_create_returns_201_with_id_and_requester", "test_acc_create.py::test_stored_request_equals_the_201_body", "test_acc_create.py::test_auto_approve_is_approved_by_system_at_creation", "test_acc_create.py::test_creation_writes_one_audit_record", "test_acc_list_get.py::test_newest_first", "test_acc_list_get.py::test_default_limit_is_20_and_total_counts_all", "test_acc_list_get.py::test_status_filter", "test_acc_routing.py::test_route", "test_acc_approve.py::TestAuthority::test_manager_approves_manager_track", "test_acc_approve.py::TestAuthority::test_security_approves_security_track", "test_acc_approve.py::TestAuthority::test_security_may_approve_manager_track", "test_acc_approve.py::test_approval_writes_one_audit_record"],
      nets: { traceability: [false, "המזהים בבדיקות ובמפרט לא השתנו."], diff: [true, "enum-mismatch על status בכל תשובה: approved מול granted."], contract: [false, "הבקשות של Schemathesis עם כלים אקראיים כמעט אף פעם לא מגיעות ל-auto_approve, אז approved לא מופיע."], acceptance: [true, "openapi-core מאמת כל תשובה, ו-granted לא ב-enum של החוזה."] } },
    default_limit: { he: "drift: default_limit", story: "ברירת המחדל של limit עלתה מ-20 ל-50.", fail: ["test_acc_list_get.py::test_default_limit_is_20_and_total_counts_all"],
      nets: { traceability: [false, "שום מזהה לא השתנה."], diff: [false, "השוואת החוזים במעבדה לא משווה ערכי default של פרמטרים."], contract: [false, "כל תשובה עדיין תואמת לסכמה."], acceptance: [true, "AC-6.2: עם 25 בקשות חוזרות 25 במקום 20."] } },
    dropped_rule: { he: "drift: dropped_rule", story: "Kubernetes נמחק מרשימת הכלים הרגישים ב-routing.py.", fail: [],
      nets: { traceability: [false, "שום מזהה לא השתנה."], diff: [false, "הממשק לא השתנה."], contract: [false, "המבנה לא השתנה."], acceptance: [false, "אין קריטריון קבלה עם Kubernetes. כל הבדיקות ירוקות, וקובץ הקוד שגוי."] } },
  };
  const NETS = [["traceability", "Traceability"], ["diff", "השוואת חוזים (find_drift)"], ["contract", "בדיקת חוזה (Schemathesis)"], ["acceptance", "בדיקות קבלה (עם openapi-core)"]];

  window.AIDS.l06matrix = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="sim">
      <div class="guide"><p><b>מה רואים:</b> כל שורה היא דרישה אחת מ-SPEC-006: המזהה, הסטטוס שלה במטריצה, הכותרת, ומספר הבדיקות שמצביעות עליה. <b>PASSING</b> אומר שיש בדיקות עם ה-marker שלה וכולן עוברות, <b>FAILING</b> שלפחות אחת נכשלת, ו-<b>UNTESTED</b> שאף בדיקה לא מצביעה עליה. לחיצה על שורה פותחת את משפט הדרישה, את קריטריוני הקבלה ואת הבדיקות עם התוצאה של כל אחת.</p><p><b>התרחישים</b> למעלה הם בדיוק אלה של המעבדה, והתוצאות לקוחות מהרצה אמיתית של <code>drift_demo.py</code>. בתרחישי drift מופיעה מתחת גם רשימה של ארבע הרשתות: מי תפסה את השינוי ומי לא, ולמה.</p></div>
      <div class="seg" role="group" aria-label="תרחיש" id="l6m-seg">${Object.entries(SCEN).map(([k, s], i) => `<button data-k="${k}" aria-pressed="${i === 0}">${esc(s.he)}</button>`).join("")}</div>
      <p class="muted" id="l6m-story" style="margin:0"></p>
      <div class="stats" id="l6m-stats"></div>
      <div id="l6m-rows" style="display:grid;gap:6px"></div>
      <div id="l6m-orph"></div>
      <div id="l6m-nets"></div></div>`;
    let cur = "base";
    const open = new Set();
    function render() {
      const s = SCEN[cur];
      host.querySelector("#l6m-story").textContent = s.story;
      const failing = new Set(s.fail);
      const rows = REQS.map(([id, title, stmt, acs, tests]) => {
        const ts = id === "REQ-10" && s.add ? EX3 : tests;
        const res = ts.map((t) => [t, failing.has(t) ? "failed" : "passed"]);
        const status = !ts.length ? "UNTESTED" : res.some((r) => r[1] === "failed") ? "FAILING" : "PASSING";
        return { id, title, stmt, acs, res, status };
      });
      const count = (st) => rows.filter((r) => r.status === st).length;
      host.querySelector("#l6m-stats").innerHTML = `<span>PASSING <b>${count("PASSING")}</b></span><span>FAILING <b>${count("FAILING")}</b></span><span>UNTESTED <b>${count("UNTESTED")}</b></span><span>orphans <b>${s.orphan ? Object.keys(s.orphan).length : 0}</b></span>`;
      const box = host.querySelector("#l6m-rows");
      box.innerHTML = "";
      rows.forEach((r) => {
        const el = h(`<div class="l06-mrow"><button type="button" aria-expanded="${open.has(r.id)}"><span class="id">${esc(r.id)}</span><span class="l06-st ${r.status}">${r.status}</span><span>${esc(r.title)}</span><span class="n">${r.res.length} tests</span></button></div>`);
        if (open.has(r.id)) {
          const d = h(`<div class="l06-detail"><div class="en"></div><div><b>קריטריוני קבלה</b><ul class="en"></ul></div><div><b>בדיקות</b><ul class="en"></ul></div></div>`);
          d.querySelector(".en").textContent = r.stmt;
          const [acs, tl] = d.querySelectorAll("ul");
          r.acs.forEach((a) => { const li = document.createElement("li"); li.textContent = a; acs.append(li); });
          if (!r.res.length) { const li = document.createElement("li"); li.textContent = "(none: no test carries this marker)"; li.style.color = "var(--signal)"; tl.append(li); }
          r.res.forEach(([t, v]) => { const li = document.createElement("li"); li.textContent = `[${v}] ${t}`; if (v === "failed") li.style.color = "var(--bad)"; tl.append(li); });
          if (r.id === "REQ-4" && cur === "dropped_rule") {
            const n = h(`<p class="callout" style="margin:0">הדרישה מונה חמישה כלים רגישים. הבדיקה מכסה את AWS בלבד. PASSING כאן הוא כיסוי של הדרישה, לא של כל סעיף בה.</p>`);
            d.append(n);
          }
          el.append(d);
        }
        el.querySelector("button").addEventListener("click", () => { open.has(r.id) ? open.delete(r.id) : open.add(r.id); render(); });
        box.append(el);
      });
      const orph = host.querySelector("#l6m-orph");
      orph.innerHTML = s.orphan ? `<div class="callout"><b>Orphan markers:</b> ${Object.entries(s.orphan).map(([k, v]) => `<code>${esc(k)}</code> ← <code>${esc(v.join(", "))}</code>`).join(" ")}. בדיקה מצביעה על דרישה שלא קיימת במפרט.</div>` : "";
      const nets = host.querySelector("#l6m-nets");
      if (!s.nets) { nets.innerHTML = ""; return; }
      nets.innerHTML = `<div class="card" style="padding:12px"><b>ארבע הרשתות בתרחיש הזה</b><div class="l06-nets">${NETS.map(([k, he]) => {
        const [y, why] = s.nets[k];
        return `<div class="l06-net"><i class="${y ? "y" : "n"}">${y ? "✓" : "✗"}</i><div><b>${esc(he)}</b>: ${y ? "תפסה" : "לא תפסה"}. <span class="muted">${esc(why)}</span></div></div>`;
      }).join("")}</div></div>`;
    }
    host.querySelectorAll("#l6m-seg button").forEach((b) => b.addEventListener("click", () => {
      cur = b.dataset.k;
      host.querySelectorAll("#l6m-seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      render();
    }));
    render();
  };
})();
