// Lesson 16 aids: workflow graph animation (token, checkpoints, approval gate), approval-gate simulator,
// crash-and-resume simulator, time-travel fork tree.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function addL16Style() {
  if (document.getElementById("l16-style")) return;
  const st = document.createElement("style");
  st.id = "l16-style";
  st.textContent = `
  .l16 { display: grid; gap: 12px; min-width: 0; }
  .l16 p { margin: 0; line-height: 1.7; }
  .l16 code { overflow-wrap: anywhere; word-break: break-word; white-space: normal; }
  .l16 label { min-width: 0; }
  .l16-svg { width: 100%; max-width: 460px; height: auto; display: block; margin: 0 auto; direction: ltr; }
  .l16-svg .nd rect { fill: var(--surface); stroke: var(--line); stroke-width: 1.4; transition: all .25s; }
  .l16-svg .nd text { font-family: var(--mono); font-size: 11px; fill: var(--ink); text-anchor: middle; dominant-baseline: middle; }
  .l16-svg .nd.gate rect.outer { fill: none; stroke: var(--line); stroke-width: 1; }
  .l16-svg .nd.on rect.box { stroke: var(--accent); fill: var(--accent-soft); stroke-width: 2.2; }
  .l16-svg .nd.done rect.box { stroke: var(--good); }
  .l16-svg .nd.wait rect.box { stroke: var(--signal); fill: var(--signal-soft); stroke-width: 2.2; }
  .l16-svg .ed { stroke: var(--muted); stroke-width: 1.3; fill: none; opacity: .55; }
  .l16-svg .ed.cond { stroke-dasharray: 4 3; }
  .l16-svg .ed.hot { stroke: var(--accent); opacity: 1; stroke-width: 2.2; }
  .l16-svg .tok { fill: var(--signal); stroke: var(--surface); stroke-width: 2; }
  .l16-svg .tok.pulse { animation: l16pulse 1s ease-in-out infinite; }
  .l16-svg .badge { font-size: 10px; }
  @keyframes l16pulse { 0%,100% { r: 7; opacity: 1; } 50% { r: 11; opacity: .55; } }
  @media (prefers-reduced-motion: reduce) { .l16-svg .tok.pulse { animation: none; } }
  .l16-cap { border-inline-start: 3px solid var(--signal); padding: 8px 12px; background: var(--surface); border-radius: 0 8px 8px 0; min-height: 92px; }
  .l16-delta { direction: ltr; text-align: left; font-family: var(--mono); font-size: .74rem; background: var(--code-bg); border: 1px solid var(--line);
    border-radius: 8px; padding: 6px 8px; margin-top: 6px; white-space: pre-wrap; overflow-wrap: anywhere; }
  .l16-cps { display: flex; flex-wrap: wrap; gap: 5px; direction: ltr; min-height: 28px; }
  .l16-cp { font-family: var(--mono); font-size: .72rem; border: 1px solid var(--good); background: var(--good-soft); border-radius: 999px; padding: 2px 8px; }
  .l16-cp.pend { border-style: dashed; background: transparent; color: var(--muted); }
  .l16-cp.lost { border-color: var(--bad); background: var(--bad-soft); text-decoration: line-through; }
  .l16-ctl { display: grid; gap: 8px; }
  .l16-ctl .lbl { font-size: .82rem; color: var(--muted); }
  .l16-path { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; align-items: center; }
  .l16-path span.n { font-family: var(--mono); font-size: .74rem; border: 1px solid var(--line); border-radius: 8px; padding: 2px 7px; background: var(--surface); }
  .l16-path span.n.stop { border-color: var(--signal); background: var(--signal-soft); }
  .l16-path span.n.ref { border-color: var(--bad); background: var(--bad-soft); }
  .l16-path span.n.fin { border-color: var(--good); background: var(--good-soft); }
  .l16-path span.ar { color: var(--muted); font-size: .8rem; }
  .l16-box { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 6px; min-width: 0; }
  .l16-box h5 { margin: 0; font-size: .85rem; }
  .l16-rows { display: grid; gap: 3px; direction: ltr; text-align: left; font-family: var(--mono); font-size: .72rem; overflow-wrap: anywhere; }
  .l16-rows .ref { color: var(--bad); }
  .l16-verdict { padding: 8px 12px; border-radius: 10px; border: 1px solid var(--line); line-height: 1.6; }
  .l16-verdict.ok { border-color: var(--good); background: var(--good-soft); }
  .l16-verdict.bad { border-color: var(--bad); background: var(--bad-soft); }
  .l16-verdict.wait { border-color: var(--signal); background: var(--signal-soft); }
  .l16-two { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
  @media (max-width: 560px) { .l16-two { grid-template-columns: minmax(0, 1fr); } }
  .l16-lane { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 5px; direction: ltr; }
  .l16-lane > div { border: 1px solid var(--line); border-radius: 9px; padding: 6px 3px; text-align: center; font-family: var(--mono); font-size: .68rem;
    background: var(--surface); min-width: 0; overflow-wrap: anywhere; position: relative; transition: all .2s; }
  .l16-lane > div.run { border-color: var(--accent); background: var(--accent-soft); }
  .l16-lane > div.ok { border-color: var(--good); }
  .l16-lane > div.crash { border-color: var(--bad); background: var(--bad-soft); }
  .l16-lane > div.rerun { border-color: var(--signal); background: var(--signal-soft); }
  .l16-lane > div .sv { display: block; font-size: .8rem; min-height: 1.2em; }
  .l16-res { display: grid; gap: 4px; }
  .l16-res div { line-height: 1.6; }
  .l16-tree { display: grid; gap: 6px; direction: ltr; overflow-x: auto; padding-bottom: 4px; }
  .l16-trow { display: grid; grid-template-columns: repeat(8, 36px); gap: 4px; align-items: center; min-width: 0; }
  .l16-trow .lab { grid-column: span 8; font-size: .7rem; color: var(--muted); font-family: var(--mono); }
  .l16-cpn { width: 32px; height: 32px; border-radius: 50%; border: 1.5px solid var(--line); background: var(--surface); display: grid; place-items: center;
    font-family: var(--mono); font-size: .66rem; cursor: pointer; padding: 0; color: var(--ink); line-height: 1.05; }
  .l16-cpn.upd { border-color: var(--accent); border-style: dashed; }
  .l16-cpn.wait { border-color: var(--signal); background: var(--signal-soft); }
  .l16-cpn.end { border-color: var(--good); background: var(--good-soft); }
  .l16-cpn.sel { outline: 3px solid var(--accent); outline-offset: 1px; }
  .l16-cpn[disabled] { cursor: default; opacity: .9; }
  .l16-in { width: 100%; max-width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); font: inherit; }
  `;
  document.head.appendChild(st);
})();

function l16Seg(host, sel, onPick) {
  host.querySelectorAll(sel + " button").forEach((b) => b.addEventListener("click", () => {
    host.querySelectorAll(sel + " button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    onPick(b.dataset.v);
  }));
}
function l16Pick(host, sel) {
  const b = host.querySelector(sel + ' button[aria-pressed="true"]');
  return b ? b.dataset.v : null;
}
function l16PathHtml(items) {
  return items.map((it, k) => (k ? '<span class="ar">→</span>' : "") + `<span class="n ${it.c || ""}">${esc(it.n)}</span>`).join("");
}

/* ---------------- animation: the workflow graph with a moving request ---------------- */
window.AIDS["l16flow"] = function (host) {
  const N = {
    intake: [130, 28, "intake ✦"], enrich: [130, 80, "enrich"], policy: [130, 132, "policy"],
    file_request: [130, 184, "file_request"], manager_approval: [70, 250, "manager_approval"],
    risk_summary: [226, 250, "risk_summary ✦"], escalate: [70, 312, "escalate"],
    security_approval: [226, 312, "security_approval"], apply_decision: [130, 378, "apply_decision"],
    notify: [130, 432, "notify"], END: [130, 482, "END"],
  };
  const W = { manager_approval: 116, security_approval: 120, risk_summary: 108, file_request: 100, apply_decision: 106 };
  const gates = new Set(["manager_approval", "security_approval"]);
  const RX = 318;
  const E = [
    ["intake", "enrich", 1], ["enrich", "policy", 1], ["policy", "file_request", 0],
    ["file_request", "manager_approval", 1], ["file_request", "risk_summary", 1],
    ["manager_approval", "escalate", 1], ["escalate", "risk_summary", 0], ["risk_summary", "security_approval", 0],
    ["manager_approval", "apply_decision", 1], ["security_approval", "apply_decision", 1],
    ["apply_decision", "notify", 0], ["notify", "END", 0],
  ];
  const SHORT = { intake: 1, enrich: 1, file_request: 1 };  // dashed shortcuts to notify along the right margin
  const w = (k) => W[k] || 96;
  function pts(a, b) {
    const [ax, ay] = N[a], [bx, by] = N[b];
    if (b === "notify" && SHORT[a]) return [[ax + w(a) / 2, ay], [RX, ay], [RX, by], [bx + 48, by]];
    if (a === b) return [[ax, ay]];
    if (a === "escalate" && b === "risk_summary") return [[ax + w(a) / 2, ay], [bx - w(b) / 2, by + 6]];
    if (a === "manager_approval" && b === "apply_decision") return [[ax - w(a) / 2, ay], [6, ay], [6, by], [bx - w(b) / 2, by]];
    return [[ax, ay + 13], [bx, by - 13]];
  }
  const edgeSvg = E.map(([a, b, c]) => {
    const p = pts(a, b);
    return `<polyline class="ed${c ? " cond" : ""}" data-e="${a}>${b}" points="${p.map((q) => q.join(",")).join(" ")}"/>`;
  }).join("") + Object.keys(SHORT).map((a) => {
    const p = pts(a, "notify");
    return `<polyline class="ed cond" data-e="${a}>notify" points="${p.map((q) => q.join(",")).join(" ")}"/>`;
  }).join("");
  const nodeSvg = Object.entries(N).map(([k, [x, y, label]]) => {
    const ww = k === "END" ? 52 : w(k);
    const outer = gates.has(k) ? `<rect class="outer" x="${x - ww / 2 - 3}" y="${y - 16}" width="${ww + 6}" height="32" rx="9"/>` : "";
    return `<g class="nd${gates.has(k) ? " gate" : ""}" data-n="${k}">${outer}<rect class="box" x="${x - ww / 2}" y="${y - 13}" width="${ww}" height="26" rx="${k === "END" ? 13 : 7}"/>
      <text x="${x}" y="${y + 1}">${label}</text><text class="badge" data-b="${k}" x="${x + ww / 2 + 2}" y="${y - 12}"></text></g>`;
  }).join("");

  const S = {
    r1: { label: "r1: Jira read", steps: [
      { n: "intake", cp: "extracted", cap: "צעד ה-LLM היחיד בבקשה הזו: הטקסט החופשי של Avital הופך ל-IntakeRequest (llmkit.structured). המסלול <b>לא</b> מחולץ, רק עובדות.", d: '{"request": {"system": "jira", "access_level": "read", "employee": "avital.tal@acme.example"}, "status": "extracted"}' },
      { n: "enrich", cp: "enriched", cap: "שלושה כלים בסדר קבוע, בלי מודל: lookup_employee, get_system_info, list_access_grants. אין לה הרשאה קיימת על jira.", d: '{"employee": {"id": "E017", "manager": {"id": "E016"}}, "system_info": {"approved_tool": true, "sensitive": false}, "grants": []}' },
      { n: "policy", cp: "routed", cap: "check_policy (קוד, מדיניות v2.2) מחליט: כלי מאושר, רמה בסיסית, בלי מידע רגיש. auto_approve.", d: '{"route": "auto_approve", "reasons": ["approved tool, basic level, no customer or financial data"]}' },
      { n: "file_request", cp: "approved", cap: "תופעת הלוואי: create_access_request עם מפתח idempotency. הרשומה נוצרת ישר כ-approved. פונקציית הניתוב שולחת ל-notify, בקשת הקו המקווקו מימין.", d: '{"record": {"id": "AR-00001", "status": "approved"}, "audit": [{"from_status": null, "to_status": "approved", "actor": "system"}]}' },
      { n: "notify", cp: "approved", cap: "הודעה אחת לעובדת, ל-outbox עם מזהה קבוע (r1:notify:approved). הרצה שנייה לא שולחת פעמיים.", d: '{"notifications": [{"to": "avital.tal@acme.example", "body": "... is approved (AR-00001)."}]}' },
      { n: "END", cp: null, cap: "סיום: קריאת LLM אחת, חמישה checkpoints של צמתים, ורשומת audit אחת במסד. next ריק.", d: "snap.next == ()" },
    ] },
    r2: { label: "r2: Figma editor", steps: [
      { n: "intake", cp: "extracted", cap: "דנה כתבה \"I need a Figma editor seat...\". ה-LLM מחלץ: figma, editor, בשביל השולחת עצמה.", d: '{"request": {"system": "figma", "access_level": "editor"}, "status": "extracted"}' },
      { n: "enrich", cp: "enriched", cap: "הכלים מגלים מי היא, מי המנהלת שלה (E005, מיכל) ושאין לה כבר editor.", d: '{"employee": {"id": "E016", "manager": {"id": "E005", "name": "Michal Ben-David"}}}' },
      { n: "policy", cp: "routed", cap: "מושב בתשלום בכלי מאושר: needs_manager.", d: '{"route": "needs_manager", "review_target": "direct manager approval within 2 business days"}' },
      { n: "file_request", cp: "pending_manager", cap: "הרשומה נפתחת כ-pending_manager, <b>לפני</b> השער, בצומת נפרד. בגלל זה אין לשער תופעות לוואי לפני interrupt.", d: '{"record": {"id": "AR-00002", "status": "pending_manager", "approver": "E005"}}' },
      { n: "manager_approval", cp: "pending_manager", wait: true, cap: "<b>interrupt().</b> הגרף עוצר, ה-state נשמר, וה-payload (מי, מה, למה, מי רשאי להחליט) חוזר לקורא. התהליך יכול לצאת. מכאן אולי עוברים יומיים. ההמתנה היא checkpoint, לא תהליך חי.", d: '__interrupt__: {"gate": "manager", "request_id": "AR-00002", "allowed_approvers": ["E005 Michal Ben-David (manager)", "security team"]}' },
      { n: "manager_approval", cp: "pending_manager", resume: true, cap: "מיכל מאשרת, מתהליך אחר: <b>Command(resume=...)</b>. הצומת רץ <b>שוב מההתחלה</b>, הפעם interrupt מחזיר את התשובה, והצומת בודק סמכות מול acme.db (E005 היא המנהלת הישירה).", d: 'Command(resume={"decision": "approve", "actor": "E005", "comment": "ok for Q4"})\n-> {"decision": {"actor_id": "E005", "decision": "approve"}, "gate_error": null}' },
      { n: "apply_decision", cp: "approved", cap: "עדכון מותנה: WHERE status='pending_manager'. רשומת audit: pending_manager ל-approved, על ידי E005.", d: '{"status": "approved", "audit": [{"from_status": "pending_manager", "to_status": "approved", "actor": "E005"}]}' },
      { n: "notify", cp: "approved", cap: "דנה מקבלת הודעה. אחר כך END.", d: '{"notifications": [{"to": "dana.levi@acme.example", "subject": "Access request: approved"}]}' },
      { n: "END", cp: null, cap: "סיום. בהיסטוריה יש checkpoint לכל צעד, כולל ההמתנה, וב-audit שתי שורות: new ל-pending_manager, ו-pending_manager ל-approved.", d: "snap.next == ()" },
    ] },
    r4: { label: "r4: AWS admin", steps: [
      { n: "intake", cp: "extracted", cap: "\"admin on aws-production for 7 days\": admin, aws-production, duration_days=7.", d: '{"request": {"system": "aws-production", "access_level": "admin", "duration_days": 7}}' },
      { n: "enrich", cp: "enriched", cap: "aws-production היא tier 1, restricted, sensitive.", d: '{"system_info": {"tier": 1, "data_classification": "restricted", "sensitive": true}}' },
      { n: "policy", cp: "routed", cap: "שני כללים מתאימים (admin וגם פרודקשן), והמחמיר מנצח: needs_security.", d: '{"route": "needs_security", "reasons": ["admin rights on any system need security review", "the system is production infrastructure ..."]}' },
      { n: "file_request", cp: "pending_security", cap: "הרשומה נפתחת כ-pending_security. הניתוב שולח ל-risk_summary, כי הסוקר מקבל סיכום לפני ההחלטה.", d: '{"record": {"id": "AR-00003", "status": "pending_security", "approver": "security-team"}}' },
      { n: "risk_summary", cp: "pending_security", cap: "צעד ה-LLM השני: 3-4 משפטים לסוקר האבטחה, בלי המלצה. ה-justification עטוף בתגית כטקסט לא אמין. אם ה-LLM נופל, הסוקר מקבל את העובדות הגולמיות.", d: '{"risk_summary": "Tomer Shani asks for admin access to aws-production (restricted, tier 1) ..."}' },
      { n: "security_approval", cp: "pending_security", wait: true, cap: "<b>interrupt()</b> בשער של צוות האבטחה. רק חבר בצוות security רשאי להחליט. המנהל של Tomer, Itai Barak, יקבל סירוב.", d: '__interrupt__: {"gate": "security", "risk_summary": "...", "allowed_approvers": ["security team"]}' },
      { n: "security_approval", cp: "pending_security", resume: true, cap: "Neta (E064, צוות האבטחה) דוחה, עם הערה, כי דחייה בלי הערה נחסמת. הצומת רץ שוב, ו-interrupt מחזיר את התשובה.", d: 'Command(resume={"decision": "reject", "actor": "neta.yosef@acme.example", "comment": "use the scoped migration role"})' },
      { n: "apply_decision", cp: "rejected", cap: "pending_security ל-rejected, על ידי E064.", d: '{"status": "rejected"}' },
      { n: "notify", cp: "rejected", cap: "Tomer מקבל את הדחייה ואת הסיבה.", d: '{"body": "... was rejected by Neta Yosef: use the scoped migration role"}' },
      { n: "END", cp: null, cap: "שתי קריאות LLM, intake ו-risk_summary, ושום אישור בלי אדם מוסמך.", d: "snap.next == ()" },
    ] },
    r6: { label: "r6: עובד לא קיים", steps: [
      { n: "intake", cp: "extracted", cap: "\"Please add Yossi Cohen to GitHub with read access\": ה-employee הוא Yossi Cohen, ולא השולח.", d: '{"request": {"employee": "Yossi Cohen", "system": "github", "access_level": "read"}}' },
      { n: "enrich", cp: "needs_info", cap: "lookup_employee מחזיר ToolError: No employee matches 'Yossi Cohen'. Did you mean: Yossi Dahan, Noa Cohen, Ariel Cohen? הצומת לא קורס: הוא כותב status=needs_info.", d: '{"status": "needs_info", "error": "No employee matches \'Yossi Cohen\'. Did you mean: ..."}' },
      { n: "notify", cp: "needs_info", cap: "הניתוב אחרי enrich שולח ישר ל-notify, בקו המקווקו. לא נפתחה שום רשומה, והשולח מתבקש להשלים את הפרטים.", d: '{"body": "We could not process your request: ... Please reply with the person\'s work email ..."}' },
      { n: "END", cp: null, cap: "סיום מהיר: קריאת LLM אחת, אפס תופעות לוואי בבקשות. זה בדיוק מה ש-agent חופשי נוטה לפספס.", d: "snap.next == ()" },
    ] },
  };

  host.innerHTML = `<div class="l16">
    <p>העיגול הכתום הוא <b>הבקשה</b>. מלבן מודגש הוא הצומת שרץ עכשיו. ✦ מסמן צומת שקורא ל-LLM, וגבול כפול מסמן שער אישור. קו מקווקו הוא קשת מותנית. מתחת לגרף: מה הצומת עשה, מה הוא כתב ל-state, ופס ה-checkpoints שנשמרו עד עכשיו.</p>
    <div class="seg" id="fl-sc">${Object.entries(S).map(([k, v], i) => `<button data-v="${k}" aria-pressed="${i === 1}">${esc(v.label)}</button>`).join("")}</div>
    <svg class="l16-svg" viewBox="0 0 340 500" role="img" aria-label="workflow graph">${edgeSvg}${nodeSvg}<circle class="tok" r="7" cx="74" cy="28"/></svg>
    <div class="l16-cap" id="fl-cap"></div>
    <div><div class="lbl" style="font-size:.82rem;color:var(--muted)">checkpoints שנשמרו (thread_id = הבקשה):</div><div class="l16-cps" id="fl-cps"></div></div>
    <div class="row"><button class="btn small primary" data-play>השהה</button><button class="btn small" data-prev>→</button><button class="btn small" data-next>←</button><span class="spacer"></span><span class="counter" data-ctr></span></div>
  </div>`;
  const svg = host.querySelector("svg");
  const tok = svg.querySelector(".tok");
  let sc = "r2", i = 0, timer = null, raf = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const reduce = !playing;
  let tokPos = [74, 28];

  function moveTo(target, path) {
    cancelAnimationFrame(raf);
    const seq = path && path.length > 1 ? path : [tokPos, target];
    if (reduce) { tokPos = target; tok.setAttribute("cx", target[0]); tok.setAttribute("cy", target[1]); return; }
    const segs = [];
    let total = 0;
    for (let k = 1; k < seq.length; k++) {
      const len = Math.hypot(seq[k][0] - seq[k - 1][0], seq[k][1] - seq[k - 1][1]);
      segs.push([seq[k - 1], seq[k], len]); total += len;
    }
    const t0 = performance.now(), dur = 650;
    function step(now) {
      let d = Math.min(1, (now - t0) / dur) * total;
      let p = seq[seq.length - 1];
      for (const [a, b, len] of segs) {
        if (d <= len) { const f = len ? d / len : 1; p = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]; break; }
        d -= len;
      }
      tok.setAttribute("cx", p[0]); tok.setAttribute("cy", p[1]);
      if (now - t0 < dur) raf = requestAnimationFrame(step); else tokPos = target;
    }
    raf = requestAnimationFrame(step);
  }

  function draw(k, animate) {
    const steps = S[sc].steps;
    const s = steps[k];
    const prev = k > 0 ? steps[k - 1].n : null;
    svg.querySelectorAll(".nd").forEach((g) => { g.classList.remove("on", "done", "wait"); });
    svg.querySelectorAll(".badge").forEach((b) => (b.textContent = ""));
    svg.querySelectorAll(".ed").forEach((e) => e.classList.remove("hot"));
    for (let j = 0; j < k; j++) {
      const g = svg.querySelector(`.nd[data-n="${steps[j].n}"]`);
      if (g) g.classList.add("done");
      if (steps[j].cp) { const b = svg.querySelector(`[data-b="${steps[j].n}"]`); if (b) b.textContent = "💾"; }
      if (j > 0) { const e = svg.querySelector(`[data-e="${steps[j - 1].n}>${steps[j].n}"]`); if (e) e.classList.add("hot"); }
    }
    const g = svg.querySelector(`.nd[data-n="${s.n}"]`);
    g.classList.add(s.wait ? "wait" : "on");
    if (prev && prev !== s.n) { const e = svg.querySelector(`[data-e="${prev}>${s.n}"]`); if (e) e.classList.add("hot"); }
    tok.classList.toggle("pulse", !!s.wait);
    const tx = (k2) => N[k2][0] - (k2 === "END" ? 26 : w(k2) / 2) - 8;  // sit just left of the box, not over its text
    const target = [tx(s.n), N[s.n][1]];
    if (animate && prev && prev !== s.n) moveTo(target, pts(prev, s.n).length > 2 ? [[tx(prev), N[prev][1]], ...pts(prev, s.n), target] : null);
    else moveTo(target, [target, target]);
    const tag = s.wait ? "⏸ ממתין" : s.resume ? "▶ resume" : "";
    host.querySelector("#fl-cap").innerHTML = `<b>צעד ${k + 1}: ${esc(s.n)}</b> ${tag ? `<b>(${tag})</b>` : ""}<br>${s.cap}<div class="l16-delta">${esc(s.d)}</div>`;
    const cps = [];
    for (let j = 0; j <= k; j++) if (steps[j].cp && !steps[j].resume) cps.push(`<span class="l16-cp">💾 step ${cps.length} · ${esc(steps[j].n)} · ${esc(steps[j].cp)}</span>`);
    host.querySelector("#fl-cps").innerHTML = cps.join("") || '<span class="l16-cp pend">(עוד אין: נשמר אחרי שהצומת הראשון מסיים)</span>';
    host.querySelector("[data-ctr]").textContent = `${k + 1} / ${steps.length}`;
    host.querySelector("[data-play]").textContent = playing ? "השהה" : "נגן";
  }
  function arm() {
    clearInterval(timer);
    if (playing) timer = setInterval(() => {
      const steps = S[sc].steps;
      const dwell = steps[i].wait ? 2 : 1;
      if (!arm.hold) arm.hold = dwell;
      if (--arm.hold > 0) return;
      i = (i + 1) % steps.length; draw(i, i > 0);
    }, 3600);
  }
  host.querySelector("[data-next]").addEventListener("click", () => { playing = false; arm(); i = (i + 1) % S[sc].steps.length; draw(i, i > 0); });
  host.querySelector("[data-prev]").addEventListener("click", () => { playing = false; arm(); i = (i - 1 + S[sc].steps.length) % S[sc].steps.length; draw(i, false); });
  host.querySelector("[data-play]").addEventListener("click", () => { playing = !playing; arm(); draw(i, false); });
  l16Seg(host, "#fl-sc", (v) => { sc = v; i = 0; tokPos = [74, 28]; draw(0, false); arm(); });
  draw(0, false); arm();
  return () => { clearInterval(timer); cancelAnimationFrame(raf); };
};

/* ---------------- sim: approval gate ---------------- */
window.AIDS["l16gate"] = function (host) {
  const P = {
    E016: { name: "Dana Levi", team: "engine", note: "מבקשת r2" },
    E005: { name: "Michal Ben-David", team: "exec", note: "המנהלת של דנה" },
    E009: { name: "Itai Barak", team: "core-api", note: "המנהל של Tomer" },
    E015: { name: "Tomer Shani", team: "core-api", note: "מבקש r4" },
    E064: { name: "Neta Yosef", team: "security", note: "צוות האבטחה" },
  };
  const R = {
    r2: { emp: "E016", mgr: "E005", sys: "figma", lvl: "editor", gate: "manager", id: "AR-00002" },
    r4: { emp: "E015", mgr: "E009", sys: "aws-production", lvl: "admin", gate: "security", id: "AR-00003" },
  };
  host.innerHTML = `<div class="l16">
    <p><b>איך לקרוא:</b> למעלה בוחרים בקשה שעומדת בשער. ה-thread כבר עצר ב-interrupt, והבקשה במסד במצב pending. אחר כך בוחרים מי עונה ומה הוא עונה, ולוחצים <b>שלח resume</b>. זה בדיוק <code>approve.py decide</code>. מתחת מופיעים המסלול שהגרף עבר בתגובה (כתום: עצר שוב, אדום: תשובה שנדחתה, ירוק: סיום), ההודעה, השורה במסד ושתי רשימות audit: זו שב-state, שכוללת גם סירובים, וזו שבמסד, שכוללת רק שינויי סטטוס.</p>
    <div class="l16-ctl">
      <div><div class="lbl">בקשה (thread)</div><div class="seg" id="gt-r"><button data-v="r2" aria-pressed="true">r2: Dana, Figma editor (needs_manager)</button><button data-v="r4" aria-pressed="false">r4: Tomer, AWS admin (needs_security)</button></div></div>
      <div><div class="lbl">מי עונה (actor)</div><div class="seg" id="gt-a">${Object.entries(P).map(([k, p], j) => `<button data-v="${k}" aria-pressed="${j === 1}">${esc(p.name)} <small><bdi>${k}</bdi> · ${esc(p.note)}</small></button>`).join("")}</div></div>
      <div><div class="lbl">החלטה</div><div class="seg" id="gt-d"><button data-v="approve" aria-pressed="true">approve</button><button data-v="reject" aria-pressed="false">reject</button><button data-v="timeout" aria-pressed="false">timeout (מתזמן ה-SLA)</button></div></div>
      <div><div class="lbl">הערה (comment)</div><input class="l16-in" id="gt-c" dir="ltr" value="ok for Q4" aria-label="comment"></div>
      <div class="row"><button class="btn small primary" id="gt-go">שלח resume</button><button class="btn small" id="gt-reset">איפוס הבקשה</button></div>
    </div>
    <div class="l16-verdict wait" id="gt-v"></div>
    <div class="l16-path" id="gt-p"></div>
    <div class="l16-two">
      <div class="l16-box"><h5>requests.db: access_requests</h5><div class="l16-rows" id="gt-db"></div></div>
      <div class="l16-box"><h5>audit במסד (REQ-11)</h5><div class="l16-rows" id="gt-adb"></div></div>
    </div>
    <div class="l16-box"><h5>audit ב-state של ה-thread (כולל תשובות שנדחו)</h5><div class="l16-rows" id="gt-ast"></div></div>
  </div>`;
  let T;
  function reset() {
    const r = R[l16Pick(host, "#gt-r")];
    T = { r, gate: r.gate, status: r.gate === "manager" ? "pending_manager" : "pending_security", done: false, approver: r.gate === "manager" ? r.mgr : "security-team",
      adb: [`new -> ${r.gate === "manager" ? "pending_manager" : "pending_security"}  by system`], ast: [], refused: 0 };
    render(`<b>${esc(r.id)} ממתינה בשער ${r.gate === "manager" ? "של המנהל" : "של צוות האבטחה"}.</b> רשאים להחליט: ${r.gate === "manager" ? `${esc(P[r.mgr].name)} (${r.mgr}, המנהל הישיר) או צוות האבטחה` : "רק צוות האבטחה"}.`, "wait",
      [{ n: `${T.gate}_approval ⏸`, c: "stop" }]);
  }
  function render(msg, cls, path) {
    const v = host.querySelector("#gt-v");
    v.className = "l16-verdict " + cls; v.innerHTML = msg;
    host.querySelector("#gt-p").innerHTML = l16PathHtml(path);
    host.querySelector("#gt-db").innerHTML = `<div>${esc(T.r.id)}  ${esc(T.r.sys)}  ${esc(T.r.lvl)}</div><div>status=${esc(T.status)}</div><div>approver=${esc(T.approver)}</div>`;
    host.querySelector("#gt-adb").innerHTML = T.adb.map((a) => `<div>${esc(a)}</div>`).join("");
    host.querySelector("#gt-ast").innerHTML = T.ast.length ? T.ast.map((a) => `<div class="${a.ref ? "ref" : ""}">${esc(a.t)}</div>`).join("") : "<div>(עוד אין אירועים מהשער)</div>";
  }
  function go() {
    const actor = l16Pick(host, "#gt-a"), dec = l16Pick(host, "#gt-d"), comment = host.querySelector("#gt-c").value.trim();
    const r = T.r, g = T.gate;
    if (T.done) {
      render(`<b>ה-thread הסתיים (status=${esc(T.status)}).</b> אין interrupt ממתין, ולכן Command(resume) לא מריץ כלום, וגם העדכון במסד מותנה ב-status=pending. בקשה סגורה נשארת סגורה (REQ-10).`, "bad", [{ n: "(nothing to resume)", c: "ref" }]);
      return;
    }
    const refuse = (why, rule) => {
      T.refused += 1;
      T.ast.push({ t: `${r.id}:${g}:refused:${T.refused}  ${actor}  ${why}`, ref: true });
      render(`<b>נדחה (${rule}):</b> ${esc(why)}<br>הצומת החזיר gate_error, הניתוב שלח בחזרה ל-${g}_approval, והשער עצר שוב, הפעם עם הסיבה ב-payload. המסד לא השתנה.`, "bad",
        [{ n: `${g}_approval` }, { n: "gate_error", c: "ref" }, { n: `${g}_approval ⏸`, c: "stop" }]);
    };
    if (dec === "timeout") {
      if (g === "manager") {
        T.gate = "security"; T.status = "pending_security"; T.approver = "security-team";
        T.adb.push("pending_manager -> pending_security  by system:sla-timer");
        T.ast.push({ t: `${r.id}: decision timeout (manager gate)` });
        render("<b>הסלמה.</b> המנהל לא החליט בזמן (v2.2: שני ימי עבודה). escalate העביר את הבקשה לצוות האבטחה, risk_summary כתב סיכום, והגרף עצר בשער החדש. מעכשיו רק צוות האבטחה רשאי להחליט, גם לא המנהל.", "wait",
          [{ n: "manager_approval" }, { n: "escalate" }, { n: "risk_summary ✦" }, { n: "security_approval ⏸", c: "stop" }]);
      } else {
        T.status = "expired"; T.done = true; T.approver = "system:sla-timer";
        T.adb.push("pending_security -> expired  by system:sla-timer");
        render("<b>פג תוקף.</b> גם צוות האבטחה לא החליט בזמן. הבקשה expired, והעובד מקבל הודעה שאפשר להגיש שוב.", "bad",
          [{ n: "security_approval" }, { n: "apply_decision" }, { n: "notify" }, { n: "END", c: "fin" }]);
      }
      return;
    }
    const p = P[actor];
    if (actor === r.emp) return refuse(`${actor} cannot decide their own request`, "REQ-9");
    const sec = p.team === "security", mgr = actor === r.mgr;
    if (g === "security" && !sec) return refuse(`only the security team decides needs_security (${actor} is in ${p.team})`, "REQ-8");
    if (g === "manager" && !(mgr || sec)) return refuse(`${actor} is not ${r.emp}'s manager or in security`, "REQ-8");
    if (dec === "reject" && !comment) return refuse("a rejection needs a comment that explains why", "הערה חובה");
    const to = dec === "approve" ? "approved" : "rejected";
    const from = T.status;
    T.status = to; T.done = true; T.approver = actor;
    T.adb.push(`${from} -> ${to}  by ${actor}  "${comment}"`);
    T.ast.push({ t: `${r.id}: decision ${dec} by ${actor}` });
    render(`<b>${to === "approved" ? "אושר" : "נדחה"} על ידי ${esc(p.name)}.</b> ${mgr ? "היא המנהלת הישירה לפי acme.db." : sec ? "חבר בצוות האבטחה, ולכן רשאי." : ""} apply_decision עדכן את המסד בעדכון מותנה, ו-notify שלח לעובד: <i dir="ltr">${to === "approved" ? `Your request for ${r.lvl} access to ${r.sys} is approved (${r.id}).` : `... was rejected by ${p.name}: ${comment}`}</i>`, to === "approved" ? "ok" : "bad",
      [{ n: `${g}_approval` }, { n: "apply_decision" }, { n: "notify" }, { n: "END", c: "fin" }]);
  }
  l16Seg(host, "#gt-r", reset);
  l16Seg(host, "#gt-a", () => {});
  l16Seg(host, "#gt-d", () => {});
  host.querySelector("#gt-go").addEventListener("click", go);
  host.querySelector("#gt-reset").addEventListener("click", reset);
  reset();
};

/* ---------------- sim: crash and resume ---------------- */
window.AIDS["l16crash"] = function (host) {
  const NODES = [["intake", "✦ LLM"], ["enrich", "tools"], ["policy", "code"], ["file_request", "writes DB"], ["manager_approval", "interrupt"]];
  host.innerHTML = `<div class="l16">
    <p><b>איך לקרוא:</b> חמשת הצמתים של בקשה r2 בשורה. בזמן ההרצה הצומת שרץ צבוע בכחול, ומתחתיו מופיע 💾 כשה-checkpoint שלו נכתב לדיסק (מקווקו: עוד לא נכתב). ⚡ הוא הרגע שבו התהליך מת. אחרי הקריסה לוחצים <b>תהליך חדש: resume</b>. צמתים כתומים רצים שוב, ובתחתית מופיע מה זה עלה.</p>
    <div class="l16-ctl">
      <div><div class="lbl">איפה התהליך מת</div><div class="seg" id="cr-at"><button data-v="enrich" aria-pressed="false">באמצע enrich</button><button data-v="file" aria-pressed="true">ב-file_request, אחרי הכתיבה</button><button data-v="gate" aria-pressed="false">בזמן ההמתנה בשער</button></div></div>
      <div><div class="lbl">durability</div><div class="seg" id="cr-du"><button data-v="sync" aria-pressed="true">sync</button><button data-v="async" aria-pressed="false">async (ברירת מחדל)</button><button data-v="exit" aria-pressed="false">exit</button></div></div>
      <label style="display:flex;gap:8px;align-items:flex-start"><input type="checkbox" id="cr-key" checked><span>ל-file_request יש מפתח idempotency: <code dir="ltr">thread:employee:system:level</code></span></label>
      <div class="row"><button class="btn small primary" id="cr-run">הרץ</button><button class="btn small" id="cr-res" disabled>תהליך חדש: resume</button></div>
    </div>
    <div class="l16-lane" id="cr-lane">${NODES.map(([n, k]) => `<div data-n="${n}">${n}<br><small>${k}</small><span class="sv"></span></div>`).join("")}</div>
    <div class="l16-verdict wait" id="cr-v">בחר נקודת קריסה ומצב durability, ולחץ "הרץ".</div>
    <div class="l16-box"><h5>מה זה עלה</h5><div class="l16-res" id="cr-r"><div>(עוד לא רץ)</div></div></div>
  </div>`;
  const lane = [...host.querySelectorAll("#cr-lane > div")];
  let timers = [], sim = null;
  const clear = () => { timers.forEach(clearTimeout); timers = []; };
  const later = (ms, fn) => timers.push(setTimeout(fn, ms));
  function paint(idx, cls, sv) { lane[idx].className = cls || ""; if (sv !== undefined) lane[idx].querySelector(".sv").textContent = sv; }
  function run() {
    clear();
    const at = l16Pick(host, "#cr-at"), du = l16Pick(host, "#cr-du"), key = host.querySelector("#cr-key").checked;
    lane.forEach((_, k) => paint(k, "", ""));
    host.querySelector("#cr-res").disabled = true;
    host.querySelector("#cr-r").innerHTML = "<div>(רץ...)</div>";
    const completed = at === "enrich" ? 1 : at === "file" ? 3 : 4;  // nodes fully finished before the crash
    const crashIdx = at === "enrich" ? 1 : at === "file" ? 3 : 4;
    sim = { at, du, key, completed, crashIdx, wrote: at !== "enrich" };
    const v = host.querySelector("#cr-v");
    v.className = "l16-verdict wait"; v.textContent = "התהליך רץ...";
    const fast = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1;
    let t = 0;
    for (let k = 0; k < completed; k++) {
      later(t, () => paint(k, "run", ""));
      t += 650 * fast;
      later(t, () => {
        const saved = du === "sync" ? "💾" : du === "async" ? "💾?" : "";
        paint(k, "ok", saved);
        if (du === "async" && k > 0) lane[k - 1].querySelector(".sv").textContent = "💾";
      });
      t += 150 * fast;
    }
    if (at === "gate") {
      later(t, () => {
        paint(4, "run", "⏸");
        for (let k = 0; k < 4; k++) lane[k].querySelector(".sv").textContent = "💾";
      });
      t += 900 * fast;
      later(t, () => { paint(4, "crash", "⏸ ⚡"); finishCrash(); });
    } else {
      later(t, () => paint(crashIdx, "run", at === "file" ? "✎ DB" : ""));
      t += 700 * fast;
      later(t, () => {
        paint(crashIdx, "crash", at === "file" ? "✎ ⚡" : "⚡");
        if (du === "async" && completed > 0) { lane[completed - 1].querySelector(".sv").textContent = "✗"; }
        finishCrash();
      });
    }
  }
  function lastSaved() {
    // index of the last node whose checkpoint is on disk at crash time (-1 = only the input / nothing)
    const s = sim;
    if (s.at === "gate") return 3;  // interrupt ends the run: saved in every mode
    if (s.du === "sync") return s.completed - 1;
    if (s.du === "async") return s.completed - 2;  // worst case: the last write was still in flight
    return null;  // exit: nothing at all
  }
  function finishCrash() {
    const v = host.querySelector("#cr-v");
    const ls = lastSaved();
    const txt = sim.at === "gate"
      ? "התהליך מת בזמן שה-thread חיכה בשער. אבל interrupt כבר סיים את הריצה ושמר הכל, ולכן שום דבר לא אבד."
      : ls === null ? "התהליך מת. עם durability=exit שום checkpoint לא נכתב לפני הקריסה: ה-thread ריק על הדיסק."
        : `התהליך מת. ה-checkpoint האחרון שבטוח על הדיסק: אחרי ${ls >= 0 ? NODES[ls][0] : "הקלט (לפני intake)"}.` + (sim.du === "async" ? " (async, המקרה הגרוע: הכתיבה האחרונה עוד הייתה ברקע.)" : "");
    v.className = "l16-verdict bad"; v.innerHTML = "⚡ " + txt + (sim.wrote && sim.at !== "gate" ? " <b>הרשומה ב-requests.db כבר נכתבה.</b>" : "");
    host.querySelector("#cr-res").disabled = false;
  }
  function resume() {
    clear();
    const s = sim, ls = lastSaved();
    host.querySelector("#cr-res").disabled = true;
    let start, note;
    if (s.at === "gate") { start = 4; note = "invoke(None) לא נדרש בכלל: ה-thread מחכה בשער, ו-Command(resume) מכל תהליך ימשיך אותו."; }
    else if (ls === null) { start = 0; note = "אין checkpoint: invoke(None, cfg) זורק EmptyInputError. מריצים את הבקשה מחדש, עם <b>אותו thread_id</b>."; }
    else { start = ls + 1; note = `invoke(None, cfg) טוען את ה-checkpoint שאחרי ${ls >= 0 ? NODES[ls][0] : "הקלט"}, ו-next הוא ${NODES[start][0]}.`; }
    const rerun = [];
    for (let k = start; k < 4; k++) rerun.push(k);
    rerun.forEach((k, j) => later(j * 500, () => paint(k, "rerun", "↻")));
    later(rerun.length * 500, () => {
      paint(4, "ok", "⏸");
      const llmTwice = rerun.includes(0) ? 1 : 0;
      const fileRerun = rerun.includes(3);
      const records = s.wrote && fileRerun ? (s.key ? 1 : 2) : 1;
      const v = host.querySelector("#cr-v");
      v.className = "l16-verdict " + (records === 1 ? "ok" : "bad");
      v.innerHTML = records === 1 ? "ה-thread שוב ממתין בשער, עם רשומה אחת בדיוק." : "ה-thread ממתין בשער, אבל <b>יש שתי רשומות</b> לאותה בקשה, ומיכל תתבקש לאשר פעמיים.";
      host.querySelector("#cr-r").innerHTML = [
        `<div><b>מאיפה ממשיכים:</b> ${note}</div>`,
        `<div><b>צמתים שרצו שוב:</b> <span dir="ltr">${rerun.length ? rerun.map((k) => NODES[k][0]).join(", ") : "אף אחד"}</span></div>`,
        `<div><b>קריאות LLM ששולמו פעמיים:</b> ${llmTwice}${llmTwice ? " (intake רץ שוב. עם מודל אמיתי החילוץ יכול גם לצאת שונה)" : ""}</div>`,
        `<div><b>רשומות ב-requests.db:</b> ${records} ${records === 1 ? "✓" : "✗"}${s.wrote && fileRerun ? (s.key ? " (file_request רץ שוב, וה-toolkit החזיר את הקיימת עם deduplicated)" : " (בלי מפתח, הקריאה השנייה יצרה רשומה חדשה. LangGraph לא יודע מה הכלי עשה בתוך צומת שלא הסתיים)") : ""}</div>`,
        s.du === "exit" && s.at !== "gate" && s.key ? `<div><b>שים לב:</b> המפתח מגן רק אם מריצים מחדש עם אותו thread_id, כי הוא חלק מהמפתח. thread חדש הוא בקשה חדשה.</div>` : "",
      ].join("");
    });
  }
  host.querySelector("#cr-run").addEventListener("click", run);
  host.querySelector("#cr-res").addEventListener("click", resume);
  ["#cr-at", "#cr-du"].forEach((s) => l16Seg(host, s, () => {}));
  return () => clear();
};

/* ---------------- sim: time-travel fork tree ---------------- */
window.AIDS["l16fork"] = function (host) {
  const MAIN = [
    { step: -1, next: "start", st: "-" }, { step: 0, next: "intake", st: "received" }, { step: 1, next: "enrich", st: "extracted" },
    { step: 2, next: "policy", st: "enriched" }, { step: 3, next: "file_request", st: "routed" }, { step: 4, next: "manager_approval", st: "pending_manager", wait: true },
  ];
  const ROUTE = { viewer: "auto_approve", read: "auto_approve", editor: "needs_manager", admin: "needs_security" };
  const RANK = { auto_approve: 1, needs_manager: 2, needs_security: 3 };
  const STATUS = { auto_approve: "approved", needs_manager: "pending_manager", needs_security: "pending_security" };
  host.innerHTML = `<div class="l16">
    <p><b>איך לקרוא:</b> כל שורה היא ענף של אותו thread (r2, דנה, Figma editor). כל עיגול הוא checkpoint, והמספר שבו הוא ה-step. מתחת למספר מופיע הצומת הבא. עיגול כתום ממתין בשער, ירוק הוא סוף. עיגול מקווקו נוצר ב-<code>update_state</code> (source=update), וממנו הענף ממשיך. בחר נקודה (לפני איזה צומת), בחר רמה, ולחץ fork. מימין לתחתית מופיעות הרשומות ב-requests.db.</p>
    <div class="l16-ctl">
      <div><div class="lbl">fork מה-checkpoint שלפני</div><div class="seg" id="fk-at"><button data-v="3" aria-pressed="true">policy</button><button data-v="4" aria-pressed="false">file_request</button><button data-v="5" aria-pressed="false">manager_approval</button></div></div>
      <div><div class="lbl">access_level ב-update_state</div><div class="seg" id="fk-lv"><button data-v="viewer" aria-pressed="true">viewer</button><button data-v="editor" aria-pressed="false">editor</button><button data-v="admin" aria-pressed="false">admin</button></div></div>
      <div class="row"><button class="btn small primary" id="fk-go">fork + invoke(None)</button><button class="btn small" id="fk-reset">איפוס</button></div>
    </div>
    <div class="l16-tree" id="fk-tree"></div>
    <div class="l16-verdict wait" id="fk-v">ה-thread עומד בשער המנהלת (step 4). שום checkpoint לא נמחק לעולם: fork מוסיף ענף.</div>
    <div class="l16-box"><h5>requests.db</h5><div class="l16-rows" id="fk-db"></div></div>
  </div>`;
  let branches, records, nextId;
  function reset() {
    branches = [{ label: "main", offset: 0, cps: MAIN.map((c) => ({ ...c })) }];
    records = [{ id: "AR-00002", lvl: "editor", status: "pending_manager", key: "r2:E016:figma:editor" }];
    nextId = 5;
    draw();
    host.querySelector("#fk-v").className = "l16-verdict wait";
    host.querySelector("#fk-v").innerHTML = "ה-thread עומד בשער המנהלת (step 4). שום checkpoint לא נמחק לעולם: fork מוסיף ענף.";
  }
  function draw() {
    host.querySelector("#fk-tree").innerHTML = branches.map((b) => {
      const cells = [];
      for (let k = 0; k < b.offset; k++) cells.push("<span></span>");
      b.cps.forEach((c) => cells.push(`<button class="l16-cpn ${c.upd ? "upd" : ""} ${c.wait ? "wait" : ""} ${c.end ? "end" : ""}" disabled title="${esc(c.st)}">${c.step}<br>${esc((c.next || "").slice(0, 5))}</button>`));
      return `<div class="lab">${esc(b.label)}</div><div class="l16-trow">${cells.join("")}</div>`;
    }).join("");
    host.querySelector("#fk-db").innerHTML = records.map((r) => `<div>${r.id}  figma  ${r.lvl.padEnd(6)} ${r.status.padEnd(16)} key=${r.key}</div>`).join("");
  }
  function fork() {
    if (branches.length >= 4) { host.querySelector("#fk-v").innerHTML = "מספיק ענפים לתרגיל: לחץ איפוס."; return; }
    const at = +l16Pick(host, "#fk-at"), lvl = l16Pick(host, "#fk-lv");
    const parent = MAIN[at];
    const cps = [{ step: parent.step + 1, next: parent.next, st: "update", upd: true }];
    let step = parent.step + 1, msg = "", route = "needs_manager", status;
    const key = `r2:E016:figma:${lvl}`;
    const fileReq = (stateRoute) => {
      const toolRoute = ROUTE[lvl];
      const fin = RANK[stateRoute] >= RANK[toolRoute] ? stateRoute : toolRoute;
      const existing = records.find((r) => r.key === key);
      if (existing) return { st: existing.status, dedup: true, route: fin };
      const rec = { id: `AR-0000${nextId++}`, lvl, status: STATUS[fin], key };
      records.push(rec);
      return { st: rec.status, dedup: false, route: fin, rec };
    };
    const tail = (st, route2) => {
      if (st === "approved") { cps.push({ step: ++step, next: "notify", st }); cps.push({ step: ++step, next: "END", st, end: true }); }
      else if (route2 === "needs_security") { cps.push({ step: ++step, next: "risk_sum", st }); cps.push({ step: ++step, next: "security", st, wait: true }); }
      else cps.push({ step: ++step, next: "manager", st, wait: true });
    };
    if (at === 3) {
      route = ROUTE[lvl];
      cps.push({ step: ++step, next: "file_request", st: "routed" });
      const f = fileReq(route);
      tail(f.st, f.route);
      msg = f.dedup ? `policy החליט ${route}, ו-file_request רץ שוב עם <b>אותו מפתח</b> (אותה רמה), ולכן לא נוצרה רשומה חדשה (deduplicated). הענף עומד שוב בשער.`
        : `policy רץ מחדש עם ${lvl} והחליט <b>${route}</b>. file_request רץ שוב עם מפתח חדש (<span dir="ltr">${key}</span>), ולכן נוצרה רשומה <b>חדשה</b> (${f.rec.id}, ${f.st}). הרשומה המקורית לא נעלמה, כי חזרה בזמן מחזירה state, לא את העולם.`;
    } else if (at === 4) {
      const f = fileReq("needs_manager");
      tail(f.st, f.route);
      msg = f.dedup ? "file_request רץ שוב עם אותו מפתח: deduplicated, הענף חוזר לשער."
        : `ה-checkpoint הזה כבר מכיל route=needs_manager, שחושב בשביל <b>editor</b>. policy לא רץ שוב. file_request פתח רשומה חדשה ל-${lvl} (${f.rec.id}) עם המסלול המחמיר מבין route שב-state לבין מה שה-toolkit חישב: <b>${f.st}</b>. ה-state עכשיו לא עקבי: route של בקשה אחת על רמה של בקשה אחרת. fork אחרי שהחלטה כבר נגזרה מהשדה שאתה משנה הוא מתכון לבאגים.`;
    } else if (lvl === "editor") {
      cps.push({ step: ++step, next: "manager", st: "pending_manager", wait: true });
      msg = "update_state עם אותו ערך: ענף חדש בהיסטוריה, השער רץ שוב ועוצר עם אותו payload. שום דבר בעולם לא השתנה.";
    } else {
      cps.push({ step: ++step, next: "manager", st: "pending_manager", wait: true });
      msg = `שום צומת עם תופעת לוואי לא רץ, ולכן אין רשומה חדשה. השער רץ שוב ועוצר עם payload חדש, שמציג למיכל <b>${lvl}</b>, בזמן שהרשומה במסד היא editor (AR-00002). המאשרת תראה דבר אחד ותאשר דבר אחר. update_state לפני שער צריך להתאים גם לעולם, או לעבור דרך הצמתים שמעדכנים אותו.`;
    }
    branches.push({ label: `fork ${branches.length}: update_state(before ${parent.next}, access_level=${lvl}) -> parent = step ${parent.step}`, offset: at + 1, cps });
    draw();
    const v = host.querySelector("#fk-v");
    v.className = "l16-verdict " + (at === 3 && ROUTE[lvl] !== "needs_manager" ? "bad" : at === 3 ? "ok" : "bad");
    v.innerHTML = msg;
  }
  ["#fk-at", "#fk-lv"].forEach((s) => l16Seg(host, s, () => {}));
  host.querySelector("#fk-go").addEventListener("click", fork);
  host.querySelector("#fk-reset").addEventListener("click", reset);
  reset();
};
