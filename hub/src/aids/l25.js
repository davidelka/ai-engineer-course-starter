// Lesson 25 aids: request flow through a gateway (animation), team budget simulator, policy decision explorer.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function addL25Style() {
  if (document.getElementById("l25-style")) return;
  const st = document.createElement("style");
  st.id = "l25-style";
  st.textContent = `
.l25 { display: grid; gap: 12px; min-width: 0; }
.l25 .l25-guide { border-inline-start: 3px solid var(--accent); background: var(--accent-soft); border-radius: 0 10px 10px 0; padding: 10px 14px; line-height: 1.7; }
.l25 .l25-guide p { margin: 0 0 6px; } .l25 .l25-guide p:last-child { margin: 0; }
.l25 .l25-grid { display: grid; gap: 10px; grid-template-columns: 1fr; direction: ltr; text-align: left; }
.l25 .l25-list, .l25 .l25-meters { text-align: left; }
@media (min-width: 720px) { .l25 .l25-grid { grid-template-columns: 0.9fr 1.5fr 0.9fr; align-items: start; } }
.l25 .l25-col { display: grid; gap: 6px; min-width: 0; }
.l25 .l25-row { display: flex; flex-wrap: wrap; gap: 6px; }
@media (min-width: 720px) { .l25 .l25-row { display: grid; gap: 6px; } }
.l25 .l25-box { border: 1px solid var(--line); background: var(--surface); border-radius: 10px; padding: 6px 9px; font-size: .8rem; font-family: var(--mono); min-width: 0; flex: 1 1 100px; transition: border-color .2s, background .2s; }
.l25 .l25-box small { display: block; font-family: inherit; color: var(--muted); font-size: .72rem; white-space: normal; }
.l25 .l25-box.on { border-color: var(--accent); background: var(--accent-soft); }
.l25 .l25-box.ok { border-color: var(--good); }
.l25 .l25-box.down { border-color: var(--bad); background: var(--bad-soft); }
.l25 .l25-box.gray { opacity: .5; }
.l25 .l25-st { display: grid; grid-template-columns: 22px 1fr auto; gap: 6px; align-items: center; border: 1px solid var(--line); border-radius: 9px; padding: 5px 8px; background: var(--surface); font-size: .8rem; min-width: 0; transition: border-color .2s, background .2s; }
.l25 .l25-st .n { font-family: var(--mono); color: var(--muted); font-size: .72rem; }
.l25 .l25-st .nm { font-family: var(--mono); min-width: 0; overflow-wrap: anywhere; }
.l25 .l25-st .nm small { display: block; color: var(--muted); font-size: .72rem; font-family: var(--mono); }
.l25 .l25-st.on { border-color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 1px var(--accent); }
.l25 .pill { font-family: var(--mono); font-size: .7rem; padding: 1px 6px; border-radius: 999px; border: 1px solid var(--line); white-space: nowrap; }
.l25 .pill.ok { background: var(--good-soft); border-color: var(--good); color: var(--good); }
.l25 .pill.bad { background: var(--bad-soft); border-color: var(--bad); color: var(--bad); }
.l25 .pill.skip { background: var(--signal-soft); border-color: var(--signal); color: var(--signal); }
.l25 .pill.info { background: var(--code-bg); }
.l25 .l25-cap { min-height: 96px; line-height: 1.7; }
.l25 .l25-cap b { display: block; margin-bottom: 2px; }
.l25 .l25-meters { display: grid; gap: 8px; grid-template-columns: 1fr; direction: ltr; font-size: .8rem; }
@media (min-width: 560px) { .l25 .l25-meters { grid-template-columns: 1fr 1fr 1fr; } }
.l25 .l25-meter { border: 1px solid var(--line); border-radius: 9px; padding: 6px 9px; font-family: var(--mono); min-width: 0; }
.l25 .l25-meter .tr { height: 8px; background: var(--code-bg); border-radius: 4px; overflow: hidden; margin-top: 4px; }
.l25 .l25-meter .f { height: 100%; background: var(--accent); transition: width .3s; }
.l25 .l25-meter .f.hot { background: var(--bad); }
.l25 .l25-chart { position: relative; height: 170px; display: flex; align-items: flex-end; gap: 2px; border-bottom: 1px solid var(--line); direction: ltr; padding-top: 6px; }
.l25 .l25-chart .d { flex: 1 1 0; min-width: 0; background: var(--accent); border-radius: 2px 2px 0 0; position: relative; }
.l25 .l25-chart .d.warn { background: var(--signal); }
.l25 .l25-chart .d.stop { background: var(--bad); }
.l25 .l25-chart .ln { position: absolute; left: 0; right: 0; border-top: 2px dashed var(--bad); pointer-events: none; }
.l25 .l25-chart .ln.soft { border-top-color: var(--signal); }
.l25 .l25-chart .ln span { position: absolute; right: 2px; top: -16px; font-family: var(--mono); font-size: .7rem; background: var(--surface); padding: 0 3px; }
.l25 .l25-axis { display: flex; justify-content: space-between; font-family: var(--mono); font-size: .7rem; color: var(--muted); direction: ltr; }
.l25 .l25-knobs { display: grid; gap: 10px; grid-template-columns: 1fr; }
@media (min-width: 640px) { .l25 .l25-knobs { grid-template-columns: 1fr 1fr; } }
.l25 .l25-list { display: grid; gap: 6px; direction: ltr; }
.l25 .l25-dep { display: grid; grid-template-columns: auto 1fr; gap: 4px 8px; align-items: center; border: 1px solid var(--line); border-radius: 9px; padding: 6px 9px; font-family: var(--mono); font-size: .8rem; background: var(--surface); }
.l25 .l25-dep .why { grid-column: 1 / -1; color: var(--muted); font-size: .74rem; overflow-wrap: anywhere; }
.l25 .l25-res { border-radius: 10px; padding: 10px 12px; line-height: 1.7; border: 1px solid var(--line); }
.l25 .l25-res.ok { background: var(--good-soft); border-color: var(--good); }
.l25 .l25-res.bad { background: var(--bad-soft); border-color: var(--bad); }
.l25 label.l25-chk { display: flex; gap: 8px; align-items: flex-start; line-height: 1.6; font-size: .9rem; }
.l25 .eyebrow2 { font-family: var(--mono); font-size: .72rem; color: var(--muted); letter-spacing: .06em; text-transform: uppercase; direction: ltr; }
`;
  document.head.append(st);
})();

function l25seg(name, items, current) {
  return `<div class="seg" role="group" aria-label="${name}">${items.map(([v, label]) =>
    `<button type="button" data-v="${v}" aria-pressed="${v === current}">${label}</button>`).join("")}</div>`;
}
function l25bindSeg(host, sel, onPick) {
  host.querySelectorAll(sel + " button").forEach((b) => b.addEventListener("click", () => {
    host.querySelectorAll(sel + " button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    onPick(b.dataset.v);
  }));
}

/* ======================================================================
   l25flow: one request at a time through the eight stations of a gateway
   ====================================================================== */
window.AIDS["l25flow"] = function (host) {
  const STATIONS = [
    ["virtual key", "מי שולח"], ["policy", "סיווג ומדיניות"], ["budget check", "תקציב לפני"],
    ["redaction", "השחרת PII"], ["routing", "ניתוב ו-breaker"], ["provider", "הספק עונה"],
    ["cost + budget", "עלות ועדכון"], ["audit", "רשומה אחת"],
  ];
  // Each step: s = station, r = result pill (ok|bad|skip|info), x = pill text,
  // t/b = caption, app/prov = highlights, brk = primary breaker text, spent = budget meter
  const SC = [
    { name: "בקשה רגילה", app: 0, max: 2, steps: [
      { s: 0, r: "ok", x: "support-bot", t: "1. בדיקת מפתח", b: "הבקשה מגיעה עם Authorization: Bearer sk-gw-... ה-gateway מחשב SHA-256 של המפתח ומחפש אותו ברשימה. נמצא support-bot מצוות support, והוא לא מבוטל. מכאן והלאה כל החלטה ורישום משויכים למפתח הזה.", spent: 1.21 },
      { s: 1, r: "ok", x: "internal", t: "2. סיווג ומדיניות", b: "הבקשה לא נושאת תווית סיווג, ולכן היא internal, כמו כל מידע בלי תווית במדיניות של Acme. זו גם הרצפה של המפתח. המדיניות של internal מרשה anthropic ו-openai, ולכן שני ה-deployments של haiku מותרים." },
      { s: 2, r: "ok", x: "$1.21 + $0.0004", t: "3. בדיקת תקציב לפני הקריאה", b: "המפתח הוציא עד עכשיו $1.21 מתוך $2.00. העלות הגרועה ביותר של הבקשה (הפרומפט ועוד max_tokens, במחיר המלא) היא $0.0004. הסכום מתחת לתקרה, ולכן הבקשה ממשיכה." },
      { s: 3, r: "info", x: "phone_il: 1", t: "4. השחרה", b: "בטקסט יש מספר טלפון: 054-1234567. ברמת internal המדיניות משחירה טלפונים ותעודות זהות, ומשאירה מיילים של עובדים. הספק יקבל [PHONE_IL_1], וה-gateway זוכר בזיכרון, רק לבקשה הזו, למה ה-placeholder מתייחס." },
      { s: 4, r: "ok", x: "anthropic-us", t: "5. ניתוב", b: "השרשרת אחרי סינון המדיניות היא anthropic-us ואחריו openai-global. ה-breaker של anthropic-us סגור (0 כישלונות), ולכן מנסים אותו ראשון.", brk: "closed 0/3" },
      { s: 5, r: "ok", x: "200", prov: [1, 0], t: "6. הספק עונה", b: "Claude עונה: 412 טוקני קלט ו-96 טוקני פלט. מבחינת הספק, הלקוח הוא ה-gateway. הוא לא יודע שיש support-bot, וגם לא ראה את מספר הטלפון." },
      { s: 6, r: "info", x: "+$0.00009", t: "7. עלות מתוך ה-usage ועדכון התקציב", b: "העלות מחושבת מה-usage שהספק החזיר, לפי המחיר של המודל האמיתי: 412 × $0.10 + 96 × $0.50 למיליון, כלומר $0.00009. ההוצאה של המפתח עולה ל-$1.21009. בתשובה לאפליקציה יוצאות הכותרות x-gateway-cost-usd ו-x-gateway-budget-remaining-usd.", spent: 1.21009 },
      { s: 7, r: "ok", x: "status 200", t: "8. רשומת audit, ותשובה לאפליקציה", b: "נכתבת שורה אחת: key_id, team, model, classification, ההחלטה לכל deployment, redactions={phone_il: 1} עם fingerprint, ה-deployment שענה, usage, עלות וזמן. הטקסט עצמו לא נכתב. האפליקציה מקבלת 200, והמספר האמיתי מוחזר לתשובה במקום ה-placeholder." },
    ] },
    { name: "תקלה אצל הספק", app: 0, max: 2, steps: [
      { s: 0, r: "ok", x: "support-bot", t: "1. מפתח", b: "עוד בקשה מבוט התמיכה. המפתח תקין.", spent: 1.4, brk: "closed 0/3" },
      { s: 1, r: "ok", x: "internal", t: "2. מדיניות", b: "internal: שני ה-deployments מותרים, אותה שרשרת כמו קודם." },
      { s: 2, r: "ok", x: "under limit", t: "3. תקציב", b: "$1.40 ועוד ההערכה, מתחת לתקרה של $2." },
      { s: 3, r: "info", x: "nothing", t: "4. השחרה", b: "אין בבקשה הזו טלפון או תעודת זהות, ולכן אין מה להשחיר." },
      { s: 4, r: "ok", x: "try anthropic-us", t: "5. ניתוב: מנסים את הראשי", b: "ה-breaker של anthropic-us סגור, ולכן הבקשה נשלחת אליו." },
      { s: 5, r: "bad", x: "529", prov: [2, 0], t: "6. הספק הראשי לא עונה", b: "Anthropic מחזיר 529 overloaded. llmkit מנסה שוב פעם אחת עם backoff (retries_per_deployment: 1), ומקבל שוב 529. זו שגיאה זמנית של הספק, ולכן ה-router עובר הלאה, וה-breaker של anthropic-us סופר כישלון ראשון.", brk: "closed 1/3" },
      { s: 4, r: "skip", x: "fallback", t: "5. ניתוב: fallback", b: "הבא בשרשרת הוא openai-global, והמדיניות של internal מרשה אותו. הוא מקבל את אותה בקשה, כבר מושחרת." },
      { s: 5, r: "ok", x: "200 (backup)", prov: [2, 1], t: "6. ספק הגיבוי עונה", b: "OpenAI עונה. שים לב: זה מודל אחר, שעונה בסגנון אחר. ה-audit ירשום מי ענה בפועל." },
      { s: 6, r: "info", x: "+$0.0002", t: "7. עלות", b: "העלות מחושבת לפי המחיר של מודל הגיבוי, ולא של המודל הראשי. התקציב מתעדכן.", spent: 1.4002 },
      { s: 7, r: "ok", x: "attempts: 2", t: "8. audit", b: "attempts: anthropic-us:error/529, openai-global:ok. בדוח העלויות של סוף השבוע זה יופיע כ-fallback, ויראו בדיוק מתי התקלה התחילה." },
      { s: 4, r: "skip", x: "skipped_open", prov: [2, 1], t: "שתי בקשות אחר כך: ה-breaker נפתח", b: "שתי הבקשות הבאות נכשלו גם הן אצל anthropic-us. שלושה כישלונות רצופים, וה-breaker עובר ל-open. מעכשיו, במשך 20 שניות, ה-router מדלג על anthropic-us בלי לנסות אותו (skipped_open), והבקשות הולכות ישר לגיבוי, בלי להמתין ל-timeout.", brk: "OPEN (cooldown 20 s)" },
    ] },
    { name: "confidential בזמן התקלה", app: 1, max: 5, steps: [
      { s: 0, r: "ok", x: "hr-assistant", t: "1. מפתח", b: "עוזר משאבי האנוש שולח סיכום של תלונה. המפתח שלו תקין, והרצפה שלו היא confidential.", spent: 2.1, brk: "OPEN (cooldown 20 s)" },
      { s: 1, r: "skip", x: "1 of 2 allowed", prov: [2, 3], t: "2. מדיניות: הגיבוי אסור", b: "הבקשה מטופלת כ-confidential, כי זו הרצפה של המפתח. anthropic-us מותר (confidential.allow). openai-global נדחה לפי הכלל confidential.providers: מידע confidential מותר רק ל-Claude. לכן לרשימה שה-router יקבל נשאר רק anthropic-us." },
      { s: 2, r: "ok", x: "under limit", t: "3. תקציב", b: "$2.10 מתוך $5. בסדר." },
      { s: 3, r: "info", x: "il_id: 1", t: "4. השחרה", b: "מספר הזהות 039337423 עובר את בדיקת ספרת הביקורת, ומוחלף ב-[IL_ID_1]." },
      { s: 4, r: "bad", x: "all skipped", prov: [2, 3], t: "5. ניתוב: אין לאן ללכת", b: "ה-deployment המותר היחיד, anthropic-us, נמצא במצב open, ולכן מדלגים עליו. ספק הגיבוי תקין לגמרי, אבל הוא לא ברשימה, כי המדיניות הוציאה אותו לפני הניתוב. אין ניסיון לשלוח אליו." },
      { s: 5, r: "skip", x: "not called", prov: [2, 3], t: "6. אף ספק לא נקרא", b: "אף ספק לא קיבל את הבקשה. זו ההתנהגות הנכונה: עדיף 503 מאשר שמידע של עובד יגיע לספק שלא אושר, בדיוק ברגע של תקלה, כשאף אחד לא מסתכל." },
      { s: 6, r: "info", x: "$0", t: "7. אין עלות", b: "לא נשלחה קריאה, ולכן גם לא נרשמה הוצאה." },
      { s: 7, r: "bad", x: "503", t: "8. audit ותשובה: 503", b: "האפליקציה מקבלת 503 upstream_unavailable עם retry-after, וה-audit רושם reason=all_deployments_failed, ואת ההחלטה לכל deployment. את בעיית הזמינות פותרים בהוספת deployment מאושר נוסף, למשל anthropic-eu, ולא בעקיפת המדיניות." },
    ] },
    { name: "תקציב נגמר", app: 2, max: 20, steps: [
      { s: 0, r: "ok", x: "eng-copilot", t: "1. מפתח", b: "ה-copilot של ההנדסה שולח בקשה ל-sonnet עם max_tokens=4000.", spent: 19.9982, brk: "closed 0/3" },
      { s: 1, r: "ok", x: "internal", t: "2. מדיניות", b: "internal: מותר." },
      { s: 2, r: "bad", x: "402", t: "3. בדיקת תקציב: עצור", b: "ההוצאה היא $19.9982 מתוך $20. ההוצאה לבדה עוד מתחת לתקרה, אבל העלות הגרועה ביותר של הבקשה היא 4000 × $10 למיליון, כלומר $0.04, וביחד הם חוצים את התקרה. הבקשה נעצרת כאן, לפני שהיא עולה כסף." },
      { s: 7, r: "bad", x: "402", t: "8. audit ותשובה: 402", b: "האפליקציה מקבלת 402 budget_exceeded, ולא 429. llmkit לא מנסה שוב 402, ולכן לא נוצרת סערת ניסיונות. הצוות קיבל אזהרת soft_limit כבר כשעבר את $15. ה-audit רושם את הדחייה, וכך גם בדוח החודשי רואים שהצוות נתקע בתקרה." },
    ] },
  ];
  const APPS = [["support-bot", "צוות support"], ["hr-assistant", "צוות hr"], ["eng-copilot", "צוות engineering"]];
  host.innerHTML = `<div class="l25">
    <div class="l25-guide"><p><b>מה רואים:</b> משמאל שלוש אפליקציות, באמצע שמונה התחנות של ה-gateway, ומימין שני ספקים. בכל צעד תחנה אחת מודגשת, ובתיבה שמתחת מוסבר מה נבדק בה ומה הוחלט. ליד כל תחנה שכבר עברנו מופיעה התוצאה שלה.</p><p><b>איך לעבוד:</b> בחר תרחיש, או תן לארבעתם לרוץ ברצף. השהה, ועבור צעד אחרי צעד עם החצים. בתחתית יש מונה תקציב ומצב ה-breaker של הספק הראשי.</p></div>
    <div id="f-sc"></div>
    <div class="l25-grid">
      <div class="l25-col"><div class="eyebrow2">apps (virtual keys)</div><div class="l25-row" id="f-apps"></div></div>
      <div class="l25-col"><div class="eyebrow2">gateway</div><div class="l25-col" id="f-st"></div></div>
      <div class="l25-col"><div class="eyebrow2">providers</div><div class="l25-row" id="f-prov"></div></div>
    </div>
    <div class="l25-cap" aria-live="polite"><b id="f-t"></b><span id="f-b" class="muted"></span></div>
    <div class="l25-meters">
      <div class="l25-meter"><span id="f-bl"></span><div class="tr"><div class="f" id="f-bf"></div></div></div>
      <div class="l25-meter" id="f-brk"></div>
      <div class="l25-meter" id="f-code"></div>
    </div>
    <div class="row"><button class="btn small primary" id="f-play">השהה</button><button class="btn small" id="f-prev" aria-label="צעד קודם">→</button><button class="btn small" id="f-next" aria-label="צעד הבא">←</button><span class="spacer"></span><span class="counter" id="f-c"></span></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  let sc = 0, k = 0, auto = true, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  g("f-sc").innerHTML = l25seg("תרחיש", SC.map((x, i) => [String(i), `${i + 1}. ${x.name}`]), "0");
  l25bindSeg(host, "#f-sc", (v) => { sc = +v; k = 0; auto = false; draw(); });

  function draw() {
    const S = SC[sc], steps = S.steps.slice(0, k + 1), cur = S.steps[k];
    host.querySelectorAll("#f-sc button").forEach((b) => b.setAttribute("aria-pressed", String(+b.dataset.v === sc)));
    const last = {};
    let spent = 0, brk = "closed 0/3", prov = [0, 0];
    const firstSpent = S.steps.find((st) => st.spent != null);
    if (firstSpent) spent = firstSpent.spent;
    steps.forEach((st) => { last[st.s] = st; if (st.spent != null) spent = st.spent; if (st.brk) brk = st.brk; if (st.prov) prov = st.prov; });
    if (!steps.some((st) => st.brk)) { const first = S.steps.find((st) => st.brk); if (first) brk = first.brk; }
    g("f-apps").innerHTML = APPS.map(([n, d], i) => `<div class="l25-box ${i === S.app ? "on" : "gray"}">${esc(n)}<small dir="rtl" style="text-align:left">${esc(d)}</small></div>`).join("");
    g("f-st").innerHTML = STATIONS.map(([en, he], i) => {
      const r = last[i];
      const pill = r ? `<span class="pill ${r.r}">${esc(r.x)}</span>` : `<span class="pill">-</span>`;
      return `<div class="l25-st ${cur.s === i ? "on" : ""}"><span class="n">${i + 1}</span><span class="nm">${esc(en)}<small dir="rtl">${esc(he)}</small></span>${pill}</div>`;
    }).join("");
    const pstate = (v) => ["", "ok", "down", "gray"][v] || "";
    const plabel = (v, healthy) => v === 2 ? "529, down" : v === 3 ? "healthy, but forbidden here" : v === 1 ? "answered 200" : healthy;
    g("f-prov").innerHTML = `<div class="l25-box ${pstate(prov[0])}">anthropic-us<small>primary · ${plabel(prov[0], sc === 2 ? "down" : "healthy")}</small></div>
      <div class="l25-box ${pstate(prov[1])}">openai-global<small>backup · ${plabel(prov[1], "healthy")}</small></div>`;
    g("f-t").textContent = cur.t;
    g("f-b").textContent = cur.b;
    const pct = Math.min(100, (spent / S.max) * 100);
    g("f-bl").textContent = `${APPS[S.app][0]}: $${spent.toFixed(spent < 10 ? 5 : 4)} / $${S.max}`;
    g("f-bf").style.width = pct.toFixed(1) + "%";
    g("f-bf").classList.toggle("hot", pct > 90);
    g("f-brk").innerHTML = `breaker anthropic-us<br><b>${esc(brk)}</b>`;
    const finalStep = S.steps[S.steps.length - 1];
    const done = k === S.steps.length - 1 || (cur.s === 7);
    g("f-code").innerHTML = `response to app<br><b>${done ? esc(finalStep.x.replace("status ", "")) : "..."}</b>`;
    g("f-c").textContent = `${S.name} · ${k + 1}/${S.steps.length}`;
    g("f-play").textContent = playing ? "השהה" : "נגן";
  }
  function step(d) {
    const n = SC[sc].steps.length;
    k += d;
    if (k >= n) { if (auto) { sc = (sc + 1) % SC.length; } k = auto ? 0 : n - 1; }
    if (k < 0) k = 0;
    draw();
  }
  function tick() { if (playing) step(1); }
  timer = setInterval(tick, 3600);
  g("f-play").addEventListener("click", () => { playing = !playing; draw(); });
  g("f-next").addEventListener("click", () => { playing = false; step(1); });
  g("f-prev").addEventListener("click", () => { playing = false; step(-1); });
  draw();
  return () => clearInterval(timer);
};

/* ======================================================================
   l25budget: a month of traffic against one key's budget
   ====================================================================== */
window.AIDS["l25budget"] = function (host) {
  // price per 1M tokens; typical request shape; requests per workday
  const KEYS = {
    "support-bot": { model: "haiku", pin: 0.10, pout: 0.50, perDay: 400, inTok: 600, outTok: 150, hard: 2, desc: "400 בקשות ביום, Haiku ($0.10 / $0.50), בערך 600 טוקני קלט ו-150 טוקני פלט" },
    "hr-assistant": { model: "sonnet", pin: 2, pout: 10, perDay: 60, inTok: 3000, outTok: 400, hard: 5, desc: "60 בקשות ביום, Sonnet ($2 / $10), בערך 3,000 טוקני קלט ו-400 טוקני פלט" },
    "eng-copilot": { model: "sonnet", pin: 2, pout: 10, perDay: 120, inTok: 2500, outTok: 600, hard: 20, desc: "120 בקשות ביום, Sonnet, בערך 2,500 טוקני קלט ו-600 טוקני פלט" },
  };
  host.innerHTML = `<div class="l25">
    <div class="l25-guide"><p><b>מה רואים:</b> חודש של 30 יום של מפתח אחד. כל עמודה היא יום, והגובה שלה הוא ההוצאה המצטברת עד סוף אותו יום. הקו האדום המקווקו הוא התקציב הקשיח, והכתום הוא הרך. עמודה כתומה היא יום שבו הצוות כבר קיבל אזהרה, ועמודה אדומה היא יום שבו בקשות נדחו.</p><p><b>איך זה מחושב:</b> בכל יום עבודה (ראשון עד חמישי) נשלחות בקשות. רובן באורך פלט רגיל, אבל אחת מכל עשרים כותבת עד max_tokens. הבקשות נשלחות בקבוצות של "בקשות במקביל": כל הבקשות בקבוצה נבדקות מול אותה הוצאה, לפני שמישהי מהן נרשמה. בדיוק כך זה קורה ב-gateway אמיתי.</p></div>
    <div id="b-key"></div>
    <div class="muted" id="b-desc" style="font-size:.88rem"></div>
    <div class="l25-knobs">
      <div class="knob"><div class="knob-head"><label for="b-hard">תקציב קשיח לחודש</label><b id="b-hardv"></b></div><input id="b-hard" type="range" min="0.5" max="40" step="0.5"><small>מעבר לתקרה, הבקשה נדחית.</small></div>
      <div class="knob"><div class="knob-head"><label for="b-soft">תקציב רך, באחוזים מהקשיח</label><b id="b-softv"></b></div><input id="b-soft" type="range" min="10" max="100" step="5" value="75"><small>רק אזהרה והתראה, בלי חסימה.</small></div>
      <div class="knob"><div class="knob-head"><label for="b-mt">max_tokens</label><b id="b-mtv"></b></div><input id="b-mt" type="range" min="200" max="8000" step="100" value="1000"><small>התקרה של הפלט, וגם הבסיס להערכה מראש.</small></div>
      <div class="knob"><div class="knob-head"><label for="b-par">בקשות במקביל</label><b id="b-parv"></b></div><input id="b-par" type="range" min="1" max="30" step="1" value="1"><small>כמה בקשות נבדקות לפני שמישהי מהן נרשמת.</small></div>
    </div>
    <label class="l25-chk"><input type="checkbox" id="b-est" checked> <span><b>הערכה מראש</b> של העלות הגרועה ביותר (ההוצאה ועוד ההערכה חייבים להיות מתחת לתקרה)</span></label>
    <div>קוד הדחייה: <span id="b-code"></span></div>
    <div><div class="l25-chart" id="b-chart"></div><div class="l25-axis"><span>day 1</span><span>day 15</span><span>day 30</span></div></div>
    <div class="stats" id="b-stats"></div>
    <div class="l25-res" id="b-res"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  let key = "eng-copilot", code = "402";
  g("b-key").innerHTML = l25seg("מפתח", Object.keys(KEYS).map((k) => [k, k]), key);
  g("b-code").innerHTML = l25seg("קוד", [["402", "402 Payment Required"], ["429", "429 Too Many Requests"]], code);
  l25bindSeg(host, "#b-key", (v) => { key = v; g("b-hard").value = KEYS[v].hard; draw(); });
  l25bindSeg(host, "#b-code", (v) => { code = v; draw(); });
  g("b-hard").value = KEYS[key].hard;

  function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

  function simulate() {
    const K = KEYS[key];
    const hard = +g("b-hard").value, soft = hard * (+g("b-soft").value) / 100;
    const mt = +g("b-mt").value, par = +g("b-par").value, est = g("b-est").checked;
    const r = rng(25);
    const estimate = (K.inTok * K.pin + mt * K.pout) / 1e6;
    let spent = 0, denied = 0, retries = 0, stopDay = null, warnDay = null, served = 0;
    const days = [];
    for (let d = 0; d < 30; d++) {
      const workday = d % 7 < 5;
      const n = workday ? K.perDay : Math.round(K.perDay * 0.1);
      let dayDenied = 0;
      for (let i = 0; i < n; i += par) {
        const batch = Math.min(par, n - i);
        const base = spent;
        let add = 0;
        for (let j = 0; j < batch; j++) {
          const long = r() < 0.05;
          const out = Math.min(mt, long ? mt : Math.round(K.outTok * (0.5 + r())));
          const cost = (K.inTok * K.pin + out * K.pout) / 1e6;
          const blocked = base >= hard || (est && base + estimate > hard);
          if (blocked) {
            denied++; dayDenied++;
            if (code === "429") retries += 3; // llmkit-style client: 3 more attempts with backoff
          } else { add += cost; served++; }
        }
        spent += add;
        if (warnDay === null && spent >= soft) warnDay = d + 1;
      }
      if (dayDenied && stopDay === null) stopDay = d + 1;
      days.push({ spent, warn: warnDay !== null && warnDay <= d + 1, stop: dayDenied > 0 });
    }
    return { days, spent, denied, retries, stopDay, warnDay, hard, soft, served, estimate, mt, par, est };
  }

  function draw() {
    const K = KEYS[key];
    g("b-desc").textContent = K.desc + ".";
    g("b-hardv").textContent = "$" + (+g("b-hard").value).toFixed(2);
    g("b-softv").textContent = g("b-soft").value + "%";
    g("b-mtv").textContent = g("b-mt").value;
    g("b-parv").textContent = g("b-par").value;
    const R = simulate();
    const top = Math.max(R.hard * 1.15, R.spent * 1.05, 0.01);
    const ch = g("b-chart");
    ch.innerHTML = R.days.map((d, i) => `<div class="d ${d.stop ? "stop" : d.warn ? "warn" : ""}" style="height:${(100 * d.spent / top).toFixed(1)}%" title="day ${i + 1}: $${d.spent.toFixed(4)}"></div>`).join("")
      + `<div class="ln" style="bottom:${(100 * R.hard / top).toFixed(1)}%"><span>hard $${R.hard.toFixed(2)}</span></div>`
      + `<div class="ln soft" style="bottom:${(100 * R.soft / top).toFixed(1)}%"><span style="right:auto;left:2px">soft $${R.soft.toFixed(2)}</span></div>`;
    const over = Math.max(0, R.spent - R.hard);
    g("b-stats").innerHTML = `<span>spent <b>$${R.spent.toFixed(4)}</b></span><span>over the limit <b>$${over.toFixed(4)}</b></span>
      <span>served <b>${R.served}</b></span><span>denied <b>${R.denied}</b></span>
      <span>extra retry requests <b>${R.retries}</b></span><span>worst-case estimate <b>$${R.estimate.toFixed(4)}</b></span>`;
    let msg;
    if (R.stopDay === null) {
      msg = `<b>התקציב מספיק לכל החודש.</b> ההוצאה הגיעה ל-$${R.spent.toFixed(2)} מתוך $${R.hard.toFixed(2)}.` + (R.warnDay ? ` אזהרה רכה נשלחה ביום ${R.warnDay}.` : "");
    } else {
      msg = `<b>המפתח נעצר ביום ${R.stopDay}.</b> ` + (R.warnDay && R.warnDay < R.stopDay ? `האזהרה הרכה הגיעה ביום ${R.warnDay}, כלומר לצוות היו ${R.stopDay - R.warnDay} ימים להגיב. ` : R.warnDay ? `האזהרה הרכה הגיעה רק ביום שבו המפתח כבר נעצר, ולכן לא היה זמן להגיב. ` : "")
        + (over > 0 ? `ההוצאה <b>חרגה מהתקרה ב-$${over.toFixed(4)}</b>: ${R.est ? "גם עם הערכה מראש, בקשות שנבדקו במקביל עברו כולן מול אותה הוצאה." : "בלי הערכה מראש, הבקשה האחרונה (או הקבוצה האחרונה) אושרה כשההוצאה עוד הייתה מתחת לתקרה, ונרשמה רק אחרי שהיא נגמרה."} ` : "לא הייתה חריגה מהתקרה. ")
        + (code === "429" ? `עם 429, כל בקשה שנדחתה גרמה ל-3 ניסיונות חוזרים, כלומר <b>${R.retries} בקשות מיותרות</b> הגיעו ל-gateway, בלי שום סיכוי להצליח.` : "עם 402, הלקוח לא מנסה שוב, והבקשה הנדחית מגיעה פעם אחת בלבד.");
    }
    const res = g("b-res");
    res.className = "l25-res " + (R.stopDay === null ? "ok" : "bad");
    res.innerHTML = msg;
  }
  ["b-hard", "b-soft", "b-mt", "b-par", "b-est"].forEach((id) => g(id).addEventListener("input", draw));
  draw();
};

/* ======================================================================
   l25policy: classification + model + outage -> allow/deny per deployment
   ====================================================================== */
window.AIDS["l25policy"] = function (host) {
  const ORDER = ["public", "internal", "confidential", "restricted"];
  const RULES = {
    public: { providers: ["anthropic", "openai"], redact: ["email", "phone_il", "il_id"] },
    internal: { providers: ["anthropic", "openai"], redact: ["phone_il", "il_id"] },
    confidential: { providers: ["anthropic"], regions: ["us", "eu"], redact: ["phone_il", "il_id"] },
    restricted: { deny: true, reason: "Restricted data may not be sent to any AI tool (it-ai-usage-he)." },
  };
  const DEPS = {
    haiku: [["anthropic-us", "anthropic", "mock-model", "us"], ["openai-global", "openai", "mock-model", "global"]],
    sonnet: [["anthropic-sonnet-us", "anthropic", "mock-sonnet", "us"], ["anthropic-sonnet-eu", "anthropic", "mock-sonnet", "eu"]],
    gpt: [["openai-gpt", "openai", "mock-gpt", "global"]],
  };
  const KEYS = {
    "support-bot": { models: ["haiku"], floor: "internal" },
    "hr-assistant": { models: ["haiku", "sonnet"], floor: "confidential" },
    "eng-copilot": { models: ["haiku", "sonnet", "gpt"], floor: null },
    "finance-reports": { models: ["sonnet"], floor: "confidential" },
  };
  let key = "eng-copilot", label = "", model = "haiku";
  host.innerHTML = `<div class="l25">
    <div class="l25-guide"><p><b>מה רואים:</b> המדיניות של המעבדה (policy.yaml) מופעלת על בקשה אחת. בוחרים מפתח, תווית סיווג ומודל. התוצאה מראה מה ה-gateway מחליט לכל deployment ובאיזה כלל, איזו שרשרת fallback נשארת, ומה הבקשה תקבל בסוף.</p><p><b>המדיניות בקיצור:</b> public ו-internal מותרים ל-anthropic ול-openai. confidential מותר רק ל-anthropic, ב-us או ב-eu. restricted אסור לכולם. בקשה בלי תווית נחשבת internal. הרצפה של המפתח גוברת על תווית נמוכה ממנה.</p></div>
    <div><div class="eyebrow2">key</div><div id="p-key"></div></div>
    <div><div class="eyebrow2">x-data-classification</div><div id="p-label"></div></div>
    <div><div class="eyebrow2">model</div><div id="p-model"></div></div>
    <label class="l25-chk"><input type="checkbox" id="p-down"> <span><b>הספק הראשי של המודל נפל</b> (ה-breaker שלו פתוח)</span></label>
    <label class="l25-chk"><input type="checkbox" id="p-eu"> <span><b>הוספת anthropic-eu</b> לשרשרת של haiku (תרגיל 5)</span></label>
    <div class="l25-res" id="p-cls"></div>
    <div class="l25-list" id="p-deps"></div>
    <div class="l25-res" id="p-res"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  g("p-key").innerHTML = l25seg("מפתח", Object.keys(KEYS).map((k) => [k, k]), key);
  g("p-label").innerHTML = l25seg("תווית", [["", "(none)"], ...ORDER.map((c) => [c, c])], label);
  g("p-model").innerHTML = l25seg("מודל", Object.keys(DEPS).map((m) => [m, m]), model);
  l25bindSeg(host, "#p-key", (v) => { key = v; draw(); });
  l25bindSeg(host, "#p-label", (v) => { label = v; draw(); });
  l25bindSeg(host, "#p-model", (v) => { model = v; draw(); });
  g("p-down").addEventListener("input", draw);
  g("p-eu").addEventListener("input", draw);

  function decide(c, d) {
    const rule = RULES[c];
    if (rule.deny) return [false, `${c}.deny`, rule.reason];
    if (rule.providers && !rule.providers.includes(d[1])) return [false, `${c}.providers`, `provider ${d[1]} not in [${rule.providers.join(", ")}]`];
    if (rule.regions && !rule.regions.includes(d[3])) return [false, `${c}.regions`, `region ${d[3]} not in [${rule.regions.join(", ")}]`];
    return [true, `${c}.allow`, ""];
  }
  function draw() {
    const K = KEYS[key];
    const requested = label || "internal";
    let eff = requested, why = label ? `התווית שהבקשה ביקשה היא <b>${label}</b>.` : "לבקשה אין תווית, ולכן היא נחשבת <b>internal</b> (המסמך sec-data-classification).";
    if (K.floor && ORDER.indexOf(K.floor) > ORDER.indexOf(requested)) { eff = K.floor; why += ` הרצפה של ${key} היא <b>${K.floor}</b>, והיא גבוהה יותר, ולכן היא קובעת.`; }
    else if (K.floor) why += ` הרצפה של ${key} היא ${K.floor}, והיא לא גבוהה מהתווית.`;
    else why += ` ל-${key} אין רצפה.`;
    const red = RULES[eff].redact ? RULES[eff].redact.join(", ") : "-";
    g("p-cls").className = "l25-res";
    g("p-cls").innerHTML = `<b>הבקשה מטופלת כ-${eff}.</b> ${why} השחרה ברמה הזו: <code>${red}</code>.`;

    const res = g("p-res");
    if (!K.models.includes(model)) {
      g("p-deps").innerHTML = "";
      res.className = "l25-res bad";
      res.innerHTML = `<b>403 permission_error.</b> המפתח ${key} מורשה רק ל-${K.models.join(", ")}. הבקשה נעצרת בשלב רשימת המודלים, לפני שהמדיניות בכלל נבדקת.`;
      return;
    }
    const deps = DEPS[model].slice();
    if (model === "haiku" && g("p-eu").checked) deps.splice(1, 0, ["anthropic-eu", "anthropic", "mock-model", "eu"]);
    const down = g("p-down").checked;
    const rows = deps.map((d, i) => ({ d, i, dec: decide(eff, d) }));
    const chain = rows.filter((r) => r.dec[0]);
    g("p-deps").innerHTML = rows.map(({ d, i, dec }) => {
      const isDown = down && i === 0;
      const pill = dec[0] ? `<span class="pill ok">ALLOW</span>` : `<span class="pill bad">deny</span>`;
      return `<div class="l25-dep">${pill}<span>${esc(d[0])} · ${esc(d[1])} · ${esc(d[3])}${isDown ? ' <span class="pill skip">breaker open</span>' : ""}</span><span class="why">rule: ${esc(dec[1])}${dec[2] ? " · " + esc(dec[2]) : ""}</span></div>`;
    }).join("");
    const usable = chain.filter((r) => !(down && r.i === 0));
    const chainTxt = chain.map((r) => r.d[0]).join(" -> ") || "(none)";
    if (!chain.length) {
      res.className = "l25-res bad";
      res.innerHTML = `<b>403 policy_denied.</b> אף deployment של ${model} לא רשאי לקבל מידע ${eff}. ` + (eff === "restricted" ? "מידע Restricted אסור בכל כלי AI, כולל הכלים המאושרים." : `למשל, gpt רץ רק אצל openai, ו-${eff} מותר רק ל-anthropic.`);
    } else if (!usable.length) {
      const healthyForbidden = rows.some((r) => !r.dec[0] && r.i !== 0);
      res.className = "l25-res bad";
      res.innerHTML = `<b>503 upstream_unavailable.</b> השרשרת אחרי המדיניות היא <code>${esc(chainTxt)}</code>, והיחיד שבה נפל. ` + (healthyForbidden ? "יש ספק תקין בשרשרת המקורית, אבל המדיניות הוציאה אותו לפני הניתוב, ולכן ה-router לא מנסה אותו. " : "") + (model === "haiku" ? "הפתרון הוא להוסיף deployment מותר, למשל anthropic-eu. נסה את תיבת הסימון." : "");
    } else {
      const who = usable[0].d[0];
      res.className = "l25-res ok";
      res.innerHTML = `<b>200, דרך ${esc(who)}.</b> השרשרת אחרי המדיניות היא <code>${esc(chainTxt)}</code>.` + (down && chain[0].i === 0 ? ` הראשי מדולג, כי ה-breaker שלו פתוח, ו-${esc(who)} עונה במקומו.` : "") + (chain.length === 1 ? " שים לב: יש ברשימה deployment אחד בלבד, כך שתקלה אחת אצלו תיתן 503." : "");
    }
  }
  draw();
};
