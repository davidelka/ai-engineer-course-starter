// Lesson 19 aids: architecture builder (animation), pattern chooser, cost/latency budget explorer, live rule checker.
// Registered on window.AIDS; uses the hub helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l19-style";
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l19 { display: grid; gap: 12px; direction: rtl; min-width: 0; }
.l19 .l19-req { background: var(--signal-soft); border-inline-start: 3px solid var(--signal); border-radius: 0 10px 10px 0; padding: 8px 12px; }
.l19 .l19-req b { display: block; font-size: .78rem; color: var(--signal); }
.l19 .l19-bands { display: grid; gap: 6px; }
.l19 .l19-band { border: 1px dashed var(--line); border-radius: 10px; padding: 6px 8px 8px; display: grid; gap: 6px; min-width: 0; }
.l19 .l19-band.u { background: color-mix(in srgb, var(--bad-soft) 45%, var(--surface)); }
.l19 .l19-band.t { background: color-mix(in srgb, var(--good-soft) 45%, var(--surface)); }
.l19 .l19-band.x { background: color-mix(in srgb, var(--accent-soft) 45%, var(--surface)); }
.l19 .l19-band > span { font-size: .72rem; color: var(--muted); font-family: var(--mono); direction: ltr; text-align: left; }
.l19 .l19-chips { display: flex; flex-wrap: wrap; gap: 5px; direction: ltr; min-height: 30px; }
.l19 .l19-chip { font-size: .76rem; line-height: 1.25; padding: 3px 8px; border-radius: 7px; border: 1px solid var(--line); background: var(--surface); display: inline-grid; max-width: 100%; }
.l19 .l19-chip small { font-family: var(--mono); font-size: .62rem; color: var(--muted); }
.l19 .l19-chip.new { border: 2px solid var(--signal); animation: pop .45s ease; }
.l19 .k-llm { border-color: var(--accent); background: var(--accent-soft); }
.l19 .k-guard { border-color: var(--good); background: var(--good-soft); }
.l19 .k-data { background: var(--code-bg); }
.l19 .k-act { border-color: var(--signal); background: var(--signal-soft); }
.l19 .k-ops { border-style: dashed; }
.l19 .l19-legend { display: flex; flex-wrap: wrap; gap: 6px; font-size: .74rem; direction: ltr; }
.l19 .l19-legend span { padding: 1px 7px; border-radius: 6px; border: 1px solid var(--line); }
.l19 .l19-flows { font-family: var(--mono); font-size: .74rem; direction: ltr; text-align: left; background: var(--code-bg); border-radius: 8px; padding: 6px 10px; display: grid; gap: 2px; min-height: 2.6em; }
.l19 .l19-flows .pii { color: var(--bad); font-weight: 600; }
.l19 .l19-flows .fb { color: var(--muted); }
.l19 .l19-q { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 6px; }
.l19 .l19-q > b { font-size: .92rem; }
.l19 .l19-q .seg button { font-size: .8rem; text-align: right; }
.l19 .l19-out { border: 2px solid var(--accent); border-radius: 12px; padding: 12px; display: grid; gap: 8px; }
.l19 .l19-out h4 { margin: 0; font-size: 1.05rem; color: var(--accent); }
.l19 .l19-out ul { margin: 0; padding-inline-start: 1.2em; display: grid; gap: 4px; }
.l19 .l19-grid2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
@media (max-width: 600px) { .l19 .l19-grid2 { grid-template-columns: minmax(0, 1fr); } }
.l19 .l19-big { font-family: var(--mono); font-size: 1.25rem; font-weight: 600; direction: ltr; text-align: right; }
.l19 .l19-big.bad { color: var(--bad); } .l19 .l19-big.ok { color: var(--good); }
.l19 .l19-lat { display: grid; gap: 4px; direction: ltr; }
.l19 .l19-lat .brow { grid-template-columns: minmax(0, 7rem) minmax(0, 1fr) 4.2rem; }
.l19 .l19-lat .brow.over .f { background: var(--bad); }
.l19 .l19-budget { position: relative; height: 22px; background: var(--code-bg); border-radius: 6px; overflow: hidden; direction: ltr; }
.l19 .l19-budget i { position: absolute; inset-block: 0; left: 0; display: block; transition: width .3s; }
.l19 .l19-budget .sum { background: color-mix(in srgb, var(--signal) 55%, var(--surface)); }
.l19 .l19-budget .sim { background: var(--accent); height: 50%; top: 25%; }
.l19 .l19-budget .line { width: 2px; background: var(--ink); }
.l19 .l19-find { display: grid; gap: 5px; }
.l19 .l19-find div { font-size: .8rem; border-radius: 8px; padding: 6px 9px; direction: ltr; text-align: left; font-family: var(--mono); overflow-wrap: anywhere; }
.l19 .l19-find .error { background: var(--bad-soft); border-inline-start: 3px solid var(--bad); }
.l19 .l19-find .warning { background: var(--signal-soft); border-inline-start: 3px solid var(--signal); }
.l19 .l19-find .clean { background: var(--good-soft); border-inline-start: 3px solid var(--good); font-family: var(--font); direction: rtl; text-align: right; }
.l19 .l19-tg { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 6px; font-size: .88rem; }
.l19 .l19-tg label { display: flex; gap: 8px; align-items: flex-start; line-height: 1.5; }
.l19 .l19-tg input { margin-top: 4px; }
`;
    document.head.appendChild(s);
  }

  const KIND_CLASS = { llm: "k-llm", guardrail: "k-guard", classifier: "k-guard", datastore: "k-data", cache: "k-data", retriever: "k-data",
    tool: "k-act", human_approval: "k-act", observability: "k-ops", eval: "k-ops" };
  const LEGEND = `<div class="l19-legend"><span class="k-llm">llm</span><span class="k-guard">guardrail / classifier</span><span class="k-data">data / retrieval / cache</span><span class="k-act">tool / human approval</span><span class="k-ops">observability / eval</span><span>client / service / external</span></div>`;
  const usd = (x) => (x >= 100 ? "$" + Math.round(x).toLocaleString("en-US") : x >= 1 ? "$" + x.toFixed(2) : "$" + x.toFixed(4));
  const ms = (x) => Math.round(x).toLocaleString("en-US") + " ms";

  /* =====================================================================
     Animation: build Company Brain, requirement by requirement
     ===================================================================== */
  const C = {
    slack: ["Slack app", "client", 0], api: ["API (FastAPI)", "service", 1], answer: ["Answer model · Sonnet 5.5", "llm", 2],
    retriever: ["Hybrid retriever", "retriever", 1], vdb: ["Vector store · pgvector", "datastore", 1], ingest: ["Nightly ingestion", "batch_job", 1],
    confluence: ["Confluence", "external_api", 2], iguard: ["Input guard", "guardrail", 1], redactor: ["PII redactor", "classifier", 1],
    oguard: ["Output guard · citations", "guardrail", 1], router: ["Intent router · Haiku 5.5", "llm", 2], rcache: ["Response cache", "cache", 1],
    small: ["Answer model · Haiku 5.5", "llm", 2], backup: ["Backup · GPT-5.4-mini", "llm", 2], kw: ["Keyword router", "service", 1],
    wf: ["Access workflow · LangGraph", "service", 1], policy: ["Policy step · Haiku 5.5", "llm", 2], approval: ["Approval (Slack buttons)", "human_approval", 1],
    grant: ["Grant tool (write)", "tool", 1], okta: ["Okta", "external_api", 2], audit: ["Audit log", "datastore", 1],
    tracing: ["Tracing · Langfuse", "observability", 2], evalr: ["Eval runner · golden set", "eval", 1],
  };
  const STEPS = [
    { add: ["slack", "api", "answer"], cost: 252, p95: 5500,
      req: "עובדים שואלים שאלות ב-Slack ומקבלים תשובה.",
      flows: [["slack", "api", "question", 1], ["api", "answer", "question"], ["answer", "api", "answer"], ["api", "slack", "answer"]],
      why: "הדבר הפשוט ביותר שעובד: קריאה אחת למודל. העלות נמוכה כי ההקשר קצר (כ-800 טוקנים). אבל המודל עונה מהזיכרון שלו, והוא לא יודע כלום על המדיניות של Acme. הוא ימציא תשובה שנשמעת אמינה." },
    { add: ["retriever", "vdb", "ingest", "confluence"], cost: 832, p95: 6250,
      req: "התשובות חייבות לבוא מהמסמכים של Acme, עם ציטוט.",
      flows: [["confluence", "ingest", "pages"], ["ingest", "vdb", "chunks + embeddings"], ["api", "retriever", "question"], ["retriever", "vdb", "query"], ["retriever", "answer", "question + top-k chunks"]],
      why: "RAG: שליפה של קטעים מהמסמכים והזנה שלהם למודל. ה-ingestion רץ כל לילה (batch). המחיר: כ-7,000 טוקני קלט בכל שאלה במקום 800, ולכן העלות קפצה פי 3, ושליפה שמוסיפה זמן. שים לב: Confluence יושב אצל צד שלישי." },
    { add: ["iguard"], cost: 832, p95: 6370,
      req: "מה שעובד כותב לא אמין: הוא יכול לנסות injection.",
      flows: [["api", "iguard", "question", 1]],
      why: "כל מסלול מרכיב לא אמין אל מודל או כלי צריך לעבור guardrail. לא רק \"יש guardrail במערכת\", אלא שאין שום מסלול שעוקף אותו. זה הכלל הראשון של הבודק במעבדה." },
    { add: ["redactor"], cost: 832, p95: 6450,
      req: "מידע אישי לא יוצא לספק בלי סינון.",
      flows: [["iguard", "redactor", "question", 1], ["redactor", "retriever", "redacted question"]],
      why: "השאלה של העובד יכולה להכיל שמות, מספרי עובד או פרטים רפואיים. היא עומדת לצאת לספק המודל, ברצועה התחתונה. רכיב סיווג (classifier) מזהה ומסיר מידע אישי לפני שהוא חוצה את גבול האמון. החצים האדומים מסמנים זרימה של pii." },
    { add: ["oguard"], cost: 832, p95: 6650,
      req: "תשובה לא יוצאת בלי ציטוט ממסמך שנשלף באמת.",
      flows: [["answer", "oguard", "draft answer"], ["oguard", "api", "answer + citations"]],
      why: "Guardrail ביציאה: בודק שכל ציטוט מצביע על קטע שנשלף, ושהתשובה לא חושפת מסמך שהמשתמש לא מורשה לראות. תשובה שנכשלה בבדיקה הופכת ל\"לא מצאתי תשובה במסמכים\", שזה עדיף על תשובה בטוחה ושגויה." },
    { add: ["router", "small", "rcache"], cost: 225, p95: 7550,
      req: "התקציב: 800$ לחודש לכל המערכת, כולל 250$ תשתית.",
      flows: [["redactor", "router", "redacted question"], ["router", "retriever", "route + tier"], ["retriever", "small", "simple questions (70%)"], ["small", "oguard", "draft answer"], ["oguard", "rcache", "answer"]],
      why: "שלושה כלים יחד: מודל קטן מסווג כל שאלה, ו-70% מהשאלות, הפשוטות, הולכות ל-Haiku שזול פי 20. מטמון תשובות עונה על שאלות זהות בלי קריאה בכלל, ו-prompt cache מוזיל את הקידומת הקבועה. העלות יורדת מ-832$ ל-225$. המחיר: הנתב מוסיף כ-900 ms ל-p95. זו פשרה מודעת, והיא נכנסת ל-ADR." },
    { add: ["backup", "kw"], cost: 226, p95: 7550,
      req: "תקלה אצל ספק המודל לא עוצרת את המערכת.",
      flows: [["answer", "backup", "fallback", 0, 1], ["router", "kw", "fallback", 0, 1]],
      why: "לכל מודל: timeout, retry ו-fallback. הגיבוי של מודל התשובה הוא אצל <b>ספק אחר</b>, כי גיבוי אצל אותו ספק לא עוזר כשהספק נפל. הגיבוי של הנתב הוא <b>קוד</b>: כללי מילות מפתח. העלות כמעט לא משתנה, כי הגיבוי רץ רק בתקלות." },
    { add: ["wf", "policy", "approval", "grant", "okta", "audit"], cost: 227, p95: 7550,
      req: "בקשות גישה מטופלות לפי המדיניות, עם אישור של אדם כשצריך.",
      flows: [["router", "wf", "access request"], ["wf", "policy", "request + policy"], ["wf", "approval", "needs_manager / security"], ["approval", "grant", "approved"], ["wf", "grant", "auto_approve (policy v2.1)"], ["grant", "okta", "grant"], ["grant", "audit", "who, what, by whom"]],
      why: "Workflow קבוע: חילוץ שדות במודל, ניתוב בקוד, ואז הסתעפות. כל מסלול לכלי הכתיבה עובר דרך אדם, חוץ מ-auto_approve, שהמדיניות של Acme מתירה, והנימוק כתוב על החץ. ה-state נשמר ב-checkpoints, כי אישור יכול להגיע אחרי שעות. 120 בקשות ביום על Haiku: כ-1.4$ לחודש." },
    { add: ["tracing", "evalr"], cost: 227, p95: 7550,
      req: "צריך לדעת מה קורה בכל בקשה, ואם שינוי הרע את המצב.",
      flows: [["redactor", "tracing", "redacted request logs"], ["wf", "tracing", "workflow traces"], ["evalr", "api", "golden questions"]],
      why: "Tracing ו-eval הם רכיבים עם זרימות, לא הערה בשוליים. ה-tracing כאן הוא שירות ענן (צד שלישי), ולכן הוא מקבל לוגים <b>אחרי</b> ה-redactor, ולא את הבקשות הגולמיות. ה-eval מריץ golden set על המערכת כל לילה ובכל שינוי פרומפט. זו הארכיטקטורה המלאה שתבדוק במעבדה." },
  ];

  window.AIDS["l19build"] = function (host) {
    ensureStyle();
    host.innerHTML = `<div class="l19">
      <div class="l19-req" id="b-req"></div>
      <div class="l19-bands">
        <div class="l19-band u"><span>untrusted · employee devices</span><div class="l19-chips" data-band="0"></div></div>
        <div class="l19-band t"><span>trusted · Acme VPC</span><div class="l19-chips" data-band="1"></div></div>
        <div class="l19-band x"><span>third party · model providers, SaaS</span><div class="l19-chips" data-band="2"></div></div>
      </div>
      ${LEGEND}
      <div><div class="eyebrow">New flows in this step</div><div class="l19-flows" id="b-flows"></div></div>
      <div class="stats"><span>רכיבים: <b id="b-n"></b></span><span>מודלים לחודש (הערכה): <b id="b-cost"></b></span><span>p95 של שאלה: <b id="b-p95"></b></span></div>
      <div class="cap muted" id="b-why" style="line-height:1.75"></div>
      <div class="row"><button class="btn small primary" id="b-play">השהה</button><button class="btn small" id="b-prev" aria-label="צעד קודם">→</button><button class="btn small" id="b-next" aria-label="צעד הבא">←</button><span class="spacer"></span><span class="counter" id="b-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    function draw() {
      const s = STEPS[i];
      const have = new Set(STEPS.slice(0, i + 1).flatMap((x) => x.add));
      const fresh = new Set(s.add);
      host.querySelectorAll(".l19-chips").forEach((box) => {
        const band = +box.dataset.band;
        box.innerHTML = Object.entries(C).filter(([id, c]) => c[2] === band && have.has(id))
          .map(([id, c]) => `<span class="l19-chip ${KIND_CLASS[c[1]] || ""}${fresh.has(id) ? " new" : ""}">${esc(c[0])}<small>${esc(c[1])}</small></span>`).join("");
      });
      g("b-req").innerHTML = `<b>דרישה ${i + 1} מתוך ${STEPS.length}</b>${esc(s.req)}`;
      g("b-flows").innerHTML = s.flows.map(([a, b, d, pii, fb]) => {
        const arrow = fb ? "-.->" : pii ? "==>" : "-->";
        return `<div class="${pii ? "pii" : fb ? "fb" : ""}">${esc(C[a][0].split(" · ")[0])} ${arrow} ${esc(C[b][0].split(" · ")[0])} : ${esc(d)}${pii ? " (pii)" : ""}</div>`;
      }).join("");
      g("b-n").textContent = have.size;
      g("b-cost").textContent = "$" + s.cost;
      g("b-p95").textContent = (s.p95 / 1000).toFixed(2) + " s";
      g("b-why").innerHTML = s.why;
      g("b-c").textContent = `צעד ${i + 1}/${STEPS.length}`;
    }
    const tick = () => { clearTimeout(timer); if (playing) timer = setTimeout(() => { i = (i + 1) % STEPS.length; draw(); tick(); }, 9000); };
    const setP = (p) => { playing = p; g("b-play").textContent = p ? "השהה" : "נגן"; tick(); };
    g("b-play").addEventListener("click", () => setP(!playing));
    g("b-next").addEventListener("click", () => { setP(false); i = Math.min(STEPS.length - 1, i + 1); draw(); });
    g("b-prev").addEventListener("click", () => { setP(false); i = Math.max(0, i - 1); draw(); });
    draw(); setP(playing);
    return () => clearTimeout(timer);
  };

  /* =====================================================================
     Sim: pattern chooser
     ===================================================================== */
  const QS = [
    { k: "steps", q: "1. האם הצעדים ידועים מראש?", o: [["one", "צעד אחד"], ["known", "כמה צעדים, ידועים"], ["mostly", "ידועים ברובם, עם חריגים"], ["open", "לא, משתנים מאוד"]] },
    { k: "docs", q: "2. האם צריך ידע של החברה שהמודל לא ראה?", o: [["no", "לא"], ["yes", "כן: מסמכים, מדיניות, מאמרים"]] },
    { k: "act", q: "3. האם המערכת משנה משהו בעולם?", o: [["none", "לא, רק עונה"], ["rev", "כן, הפיך (שדה, טיוטה)"], ["risky", "כן, מסוכן (גישה, כסף, שליחה)"]] },
    { k: "wait", q: "4. מי מחכה לתשובה?", o: [["sec", "משתמש, שניות"], ["min", "דקות זה בסדר"], ["later", "אף אחד, בהמשך היום"]] },
    { k: "dom", q: "5. כמה תחומים נפרדים, עם כלים והרשאות שונים?", o: [["one", "אחד"], ["few", "2-3, אותן הרשאות"], ["many", "הרבה, כל אחד עם כלים משלו"]] },
    { k: "err", q: "6. מה עולה טעות?", o: [["low", "מעט"], ["med", "בינוני"], ["high", "הרבה (אבטחה, לקוח, כסף)"]] },
  ];
  const PRESETS = {
    "Company Brain: שאלה": { steps: "one", docs: "yes", act: "none", wait: "sec", dom: "one", err: "med" },
    "Company Brain: בקשת גישה": { steps: "known", docs: "yes", act: "risky", wait: "min", dom: "one", err: "high" },
    "מיון פניות": { steps: "known", docs: "yes", act: "rev", wait: "min", dom: "one", err: "high" },
    "סוכן המשרות": { steps: "known", docs: "no", act: "rev", wait: "later", dom: "one", err: "low" },
    "מורה לעברית": { steps: "one", docs: "yes", act: "none", wait: "sec", dom: "few", err: "med" },
  };
  function recommend(a) {
    let pattern, why = [], comps = [], trade = [];
    if (a.steps === "one") {
      pattern = a.docs === "yes" ? "קריאה אחת עם retrieval (RAG)" : "קריאה אחת";
      why.push(a.docs === "yes" ? "צעד אחד, אבל התשובה תלויה בידע שהמודל לא ראה, ולכן שליפה לפני הקריאה." : "צעד אחד, בלי ידע חיצוני: פרומפט טוב, ואם קוד קורא את התשובה, structured output.");
    } else if (a.steps === "known") {
      pattern = "Workflow: צעדים קבועים בקוד, עם צעדי LLM";
      why.push("הצעדים ידועים, ולכן הקוד קובע את המסלול. זה זול יותר, מהיר יותר, וכל צעד נבדק ומתועד בנפרד.");
    } else if (a.steps === "mostly") {
      pattern = "Workflow לרוב הבקשות, ופתח מילוט לחריגים";
      why.push("רוב הבקשות מתאימות לצעדים קבועים. את החריגים מעבירים לאדם, או לסוכן מוגבל בלי כלי כתיבה, במקום להפוך את כל המערכת לסוכן.");
    } else {
      pattern = a.dom === "many" ? "ריבוי סוכנים: supervisor ומומחים" : "סוכן עם כלים";
      why.push(a.dom === "many" ? "הצעדים לא ידועים, ויש תחומים נפרדים עם כלים והרשאות שונים: מומחה לכל תחום, ומתאם ביניהם." : "אי אפשר לכתוב את הצעדים מראש, ולכן המודל מחליט על הכלים ועל הסדר, בתוך תקציב צעדים ותנאי עצירה.");
    }
    if (a.dom === "few" && a.steps !== "open") { why.push("כמה תחומים עם אותן הרשאות: מספיק נתב (routing) לפרומפטים מתמחים. ריבוי סוכנים לא מוצדק כאן."); comps.push("נתב: מודל קטן שבוחר פרומפט או מסלול"); }
    if (a.docs === "yes") comps.push("retriever + אינדקס + ingestion לילי (batch)");
    comps.push("input guardrail על כל מסלול מהמשתמש");
    if (a.act === "risky") {
      comps.push("שער אישור אנושי לפני כל כלי כתיבה, או חריגה עם מדיניות כתובה", "checkpoints: האישור יכול להגיע אחרי שעות", "audit log וכלים אידמפוטנטיים");
      why.push("יש פעולה מסוכנת: אף מודל לא מפעיל אותה לבד. " + (a.steps === "open" ? "לסוכן יש רק כלים לקריאה, והוא מציע פעולה שאדם מאשר." : "ההסתעפות לאישור היא node קבוע ב-workflow."));
    } else if (a.act === "rev") comps.push("audit log של כל החלטה (גרסת מודל ופרומפט)");
    if (a.wait === "sec") { comps.push("streaming, ותקציב לזמן עד הטוקן הראשון"); why.push("משתמש מחכה: כל קריאה נוספת במסלול מאריכה את ההמתנה. זה נימוק חזק נגד לולאת סוכן במסלול הזה."); }
    if (a.wait === "min") { comps.push("תור + worker + DLQ: סופג שיאים ומאפשר retry"); why.push("דקות זה בסדר: תור סופג שיאים, ושום בקשה לא הולכת לאיבוד."); }
    if (a.wait === "later") { comps.push("ריצה מתוזמנת, ו-Batch API (חצי מחיר)"); why.push("אף אחד לא מחכה: batch. לפי התיעוד של Anthropic, Batch API מחויב ב-50% מהמחיר הרגיל."); }
    if (a.err === "high") { comps.push("כללים דטרמיניסטיים להחלטות הקריטיות, לפני המודל", "fallback שעושה fail closed", "eval עם סף שחוסם שינוי (נושא 23)"); why.push("טעות יקרה: מה שאפשר לכתוב ככלל נכתב בקוד, וכשהמודל לא זמין, המערכת עוצרת או מעבירה לאדם."); }
    else comps.push("eval על golden set");
    comps.push("timeout, retry ו-fallback לכל קריאה למודל", "tracing");
    if (a.steps === "open") trade.push("סוכן: יותר קריאות לבקשה, ולכן יותר זמן וכסף, ופחות צפוי. צריך תקציב צעדים, ו-eval על מסלולים ולא רק על תשובות.");
    if (a.steps === "known" || a.steps === "mostly") trade.push("Workflow: כל מקרה חדש דורש קוד חדש. אם החריגים הופכים לרוב, ההחלטה נפתחת מחדש.");
    if (a.docs === "yes") trade.push("RAG: האיכות תלויה בשליפה. מודדים retrieval בנפרד מהתשובה (נושא 13).");
    if (a.wait === "min") trade.push("תור: ההמתנה בו בזמן שיא יכולה להיות רוב ה-p95. בקשות דחופות צריכות תור עדיפות.");
    if (a.wait === "later") trade.push("Batch: עד 24 שעות לתוצאה. לא מתאים למשהו שמישהו מחכה לו.");
    return { pattern, why, comps, trade };
  }
  window.AIDS["l19pattern"] = function (host) {
    ensureStyle();
    const a = { ...PRESETS["Company Brain: שאלה"] };
    host.innerHTML = `<div class="l19">
      <details class="guide" open><summary>איך זה עובד</summary>
      <p>לכל שאלה בוחרים תשובה אחת, וההמלצה בתחתית מתעדכנת מיד. ההמלצה כוללת ארבעה חלקים: ה-<b>pattern</b> (איפה בסולם, מקריאה אחת ועד ריבוי סוכנים), <b>למה</b>, אילו <b>רכיבים</b> הוא מחייב, ומה ה<b>פשרות</b> שלו. הכללים כאן הם אותם כללים שבשקופיות, לא קסם: כדאי לשנות תשובה אחת בכל פעם ולראות מה זז.</p>
      <p>הכפתורים למעלה ממלאים את התשובות של כל אחד מהמקרים בשיעור. Company Brain מופיע פעמיים, כי לשאלה ולבקשת גישה יש תשובות שונות.</p></details>
      <div class="seg" id="p-pre">${Object.keys(PRESETS).map((k) => `<button data-k="${esc(k)}">${esc(k)}</button>`).join("")}</div>
      <div class="stack" id="p-qs" style="gap:8px">${QS.map((q) => `<div class="l19-q"><b>${esc(q.q)}</b><div class="seg" data-k="${q.k}">${q.o.map(([v, t]) => `<button data-v="${v}">${esc(t)}</button>`).join("")}</div></div>`).join("")}</div>
      <div class="l19-out" id="p-out"></div></div>`;
    function draw(preset) {
      host.querySelectorAll("#p-qs .seg").forEach((seg) => seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(a[seg.dataset.k] === b.dataset.v))));
      host.querySelectorAll("#p-pre button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === preset)));
      const r = recommend(a);
      host.querySelector("#p-out").innerHTML = `<div class="eyebrow">Recommendation</div><h4>${esc(r.pattern)}</h4>
        <div><b>למה</b><ul>${r.why.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
        <div><b>רכיבים שזה מחייב</b><ul>${r.comps.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
        <div><b>פשרות</b><ul>${r.trade.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    }
    host.querySelectorAll("#p-qs .seg").forEach((seg) => seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { a[seg.dataset.k] = b.dataset.v; draw(null); })));
    host.querySelectorAll("#p-pre button").forEach((b) => b.addEventListener("click", () => { Object.assign(a, PRESETS[b.dataset.k]); draw(b.dataset.k); }));
    draw("Company Brain: שאלה");
  };

  /* =====================================================================
     Sim: cost & latency budget explorer
     ===================================================================== */
  // USD per 1M tokens, from llmkit/pricing.py (Anthropic checked November 2026): i input, o output,
  // c cache read, w cache write (5-minute TTL; gpt-5.4-mini has no write charge). ttft/tps are illustrative assumptions.
  const PR = {
    "claude-haiku-5-5": { i: 0.10, o: 0.50, c: 0.01, w: 0.125, ttft: 600, tps: 160 },
    "gpt-5.4-mini": { i: 0.75, o: 4.50, c: 0.075, w: 0.75, ttft: 800, tps: 120 },
    "claude-sonnet-5-5": { i: 2.00, o: 10.0, c: 0.10, w: 2.50, ttft: 1200, tps: 90 },
  };
  function callCost(m, I, K, O, h) {
    const p = PR[m];
    const hit = ((I - K) * p.i + K * p.c + O * p.o) / 1e6;
    const miss = h > 0 ? ((I - K) * p.i + K * p.w + O * p.o) / 1e6 : (I * p.i + O * p.o) / 1e6;
    return h * hit + (1 - h) * miss;
  }
  function rng(seed) { let t = seed >>> 0; return () => { t += 0x6D2B79F5; let r = Math.imul(t ^ (t >>> 15), 1 | t); r ^= r + Math.imul(r ^ (r >>> 7), 61 | r); return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }
  function simulate(stages, n = 4000) {
    const R = rng(7), Z = 1.6448536;
    const gauss = () => { let u = 0; while (u === 0) u = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * R()); };
    const tot = [];
    for (let k = 0; k < n; k++) {
      const grp = {}; const order = [];
      for (const s of stages) {
        let x;
        if (s.mix) { const pick = R() < s.mix[0].w ? s.mix[0] : s.mix[1]; x = Math.exp(Math.log(pick.p50) + gauss() * Math.log(pick.p95 / pick.p50) / Z); }
        else x = Math.exp(Math.log(s.p50) + gauss() * Math.log(s.p95 / s.p50) / Z);
        const key = s.group || s.name;
        if (!(key in grp)) { order.push(key); grp[key] = x; } else grp[key] = Math.max(grp[key], x);
      }
      tot.push(order.reduce((acc, kk) => acc + grp[kk], 0));
    }
    tot.sort((x, y) => x - y);
    return { p50: tot[Math.floor(0.5 * (n - 1))], p95: tot[Math.floor(0.95 * (n - 1))], p99: tot[Math.floor(0.99 * (n - 1))] };
  }
  window.AIDS["l19budget"] = function (host) {
    ensureStyle();
    const st = { kase: "cb", rpd: 1500, k: 8, out: 450, tier: "claude-sonnet-5-5", cheap: 0, pc: 80, rc: 10, queue: 20, stream: false };
    host.innerHTML = `<div class="l19">
      <details class="guide" open><summary>מה רואים, ואיך לקרוא</summary>
      <p>זה מודל העלות וה-latency של המעבדה (<code>cost_model.py</code>), בדפדפן. בוחרים מקרה, ומשנים את הכפתורים. <b>למעלה</b>: עלות לבקשה, עלות המודלים לחודש, והסכום הכולל מול המגבלה (ירוק בתוך התקציב, אדום מעליו). הפס הצבעוני מפרק את העלות לבקשה: קריאת הנתב, קלט רגיל, קלט מהמטמון, ופלט.</p>
      <p><b>למטה</b>: תקציב ה-latency. כל שורה היא שלב, והאורך הוא ה-p95 שלו. שלבים במקביל (שני סוגי החיפוש) מופיעים כשורה אחת. הפס התחתון משווה שלושה מספרים מול היעד (הקו השחור): <b>סכום ה-p95</b> (כתום, התכנון הזהיר), ו-<b>p95 מסימולציה</b> (כחול, 4,000 בקשות מוגרלות).</p>
      <p class="muted">המחירים מ-llmkit/pricing.py. זמני המודלים (TTFT וקצב) הם הנחות לצורך ההמחשה: את האמיתיים מודדים עם bench.py משיעור 2.</p></details>
      <div class="seg" id="g-case"><button data-c="cb">Company Brain: שאלה</button><button data-c="tt">מיון פניות</button></div>
      <div class="l19-grid2">
        <div class="stack" style="gap:8px">
          <div class="knob"><div class="knob-head"><label for="g-rpd">בקשות ביום</label><b id="g-rpdv"></b></div><input id="g-rpd" type="range" min="250" max="6000" step="250"></div>
          <div class="knob"><div class="knob-head"><label for="g-k">top-k: קטעים בהקשר (כ-625 טוקנים כל אחד)</label><b id="g-kv"></b></div><input id="g-k" type="range" min="0" max="12" step="1"></div>
          <div class="knob"><div class="knob-head"><label for="g-out">טוקני פלט בתשובה</label><b id="g-outv"></b></div><input id="g-out" type="range" min="50" max="1200" step="50"></div>
          <div><div class="muted" style="font-size:.84rem">המודל הראשי</div><div class="seg" id="g-tier">${Object.keys(PR).map((m) => `<button data-m="${m}">${m}</button>`).join("")}</div></div>
        </div>
        <div class="stack" style="gap:8px">
          <div class="knob" id="g-cheapk"><div class="knob-head"><label for="g-cheap">ניתוב למודל הזול (Haiku 5.5)</label><b id="g-cheapv"></b></div><input id="g-cheap" type="range" min="0" max="100" step="5"><small>אחוז השאלות שהנתב שולח ל-Haiku במקום למודל הראשי.</small></div>
          <div class="knob"><div class="knob-head"><label for="g-pc">פגיעה ב-prompt cache</label><b id="g-pcv"></b></div><input id="g-pc" type="range" min="0" max="100" step="5"></div>
          <div class="knob" id="g-rck"><div class="knob-head"><label for="g-rc">פגיעה ב-response cache</label><b id="g-rcv"></b></div><input id="g-rc" type="range" min="0" max="50" step="5"></div>
          <div class="knob" id="g-qk"><div class="knob-head"><label for="g-q">p95 של ההמתנה בתור (שניות)</label><b id="g-qv"></b></div><input id="g-q" type="range" min="1" max="60" step="1"></div>
          <label class="row" id="g-streamk" style="font-size:.86rem"><input type="checkbox" id="g-stream"> להציג זמן עד הטוקן הראשון (streaming)</label>
        </div>
      </div>
      <div class="l19-grid2">
        <div><div class="muted" style="font-size:.82rem">לבקשה</div><div class="l19-big" id="g-req"></div></div>
        <div><div class="muted" style="font-size:.82rem">סה"כ לחודש (מודלים + קבוע) מול מגבלה</div><div class="l19-big" id="g-tot"></div></div>
      </div>
      <div class="stats" id="g-stats"></div>
      <div class="stackbar" id="g-bar"></div>
      <div class="legend"><span><i style="background:var(--muted)"></i>נתב / מיון</span><span><i style="background:var(--accent)"></i>קלט</span><span><i style="background:color-mix(in srgb,var(--accent) 35%,var(--surface))"></i>קלט מהמטמון</span><span><i style="background:var(--signal)"></i>פלט</span></div>
      <div><div class="eyebrow">p95 per stage</div><div class="l19-lat" id="g-lat"></div></div>
      <div class="l19-budget" id="g-bud"></div>
      <div class="stats" id="g-latstats"></div>
      <div class="callout" id="g-note"></div></div>`;
    const g = (id) => host.querySelector("#" + id);
    function setCase(c) {
      st.kase = c;
      if (c === "cb") Object.assign(st, { rpd: 1500, k: 8, out: 450, tier: "claude-sonnet-5-5", cheap: 0, pc: 80, rc: 10 });
      else Object.assign(st, { rpd: 2500, k: 4, out: 350, tier: "claude-haiku-5-5", cheap: 0, pc: 90, rc: 0, queue: 20 });
      sync(); draw();
    }
    function sync() {
      g("g-rpd").value = st.rpd; g("g-k").value = st.k; g("g-out").value = st.out; g("g-cheap").value = st.cheap;
      g("g-pc").value = st.pc; g("g-rc").value = st.rc; g("g-q").value = st.queue; g("g-stream").checked = st.stream;
      host.querySelectorAll("#g-case button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.c === st.kase)));
      host.querySelectorAll("#g-tier button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.m === st.tier)));
      const cb = st.kase === "cb";
      const show = (id, on) => { g(id).style.display = on ? "" : "none"; };
      show("g-cheapk", cb); show("g-rck", cb); show("g-qk", !cb); show("g-streamk", cb);
    }
    function draw() {
      const cb = st.kase === "cb";
      const days = cb ? 30 : 22, fixed = cb ? 250 : 180, limit = cb ? 800 : 700, other = cb ? 1.37 : 0;
      const h = st.pc / 100, rc = cb ? st.rc / 100 : 0, cheap = cb ? st.cheap / 100 : 0;
      const I = (cb ? 2000 : 2000) + st.k * 625, K = cb ? 1500 : 900, O = st.out;
      const pre = cb ? callCost("claude-haiku-5-5", 700, 550, 30, h) : callCost("claude-haiku-5-5", 1500, 700, 60, h);
      const mainShare = 1 - cheap;
      const main = mainShare * callCost(st.tier, I, K, O, h) + cheap * callCost("claude-haiku-5-5", I, K, O, h);
      const perReq = pre + main;
      const monthLLM = perReq * st.rpd * days * (1 - rc);
      const total = monthLLM + fixed + other;
      // breakdown of the main call(s): uncached input / cached input / output (expected values)
      const part = (m, w) => { const p = PR[m]; return { inp: w * ((I - h * K) * p.i) / 1e6, cac: w * (h * K * p.c) / 1e6, out: w * O * p.o / 1e6 }; };
      const a1 = part(st.tier, mainShare), a2 = part("claude-haiku-5-5", cheap);
      const seg = [["var(--muted)", pre], ["var(--accent)", a1.inp + a2.inp], ["color-mix(in srgb,var(--accent) 35%,var(--surface))", a1.cac + a2.cac], ["var(--signal)", a1.out + a2.out]];
      const sum = seg.reduce((x, s) => x + s[1], 0) || 1;
      g("g-bar").innerHTML = seg.map(([c, v]) => `<i style="width:${(100 * v / sum).toFixed(1)}%;background:${c}"></i>`).join("");
      g("g-rpdv").textContent = st.rpd.toLocaleString("en-US"); g("g-kv").textContent = `${st.k} (${I.toLocaleString("en-US")} tokens in)`;
      g("g-outv").textContent = st.out; g("g-cheapv").textContent = st.cheap + "%"; g("g-pcv").textContent = st.pc + "%"; g("g-rcv").textContent = st.rc + "%"; g("g-qv").textContent = st.queue + " s";
      g("g-req").textContent = "$" + perReq.toFixed(5);
      const tot = g("g-tot"); tot.textContent = `${usd(total)} / ${usd(limit)}`; tot.className = "l19-big " + (total <= limit ? "ok" : "bad");
      g("g-stats").innerHTML = `<span>מודלים, מסלול זה: <b>${usd(monthLLM)}</b></span><span>קבוע: <b>${usd(fixed)}</b></span>${cb ? `<span>בקשות גישה: <b>$1.37</b></span>` : ""}<span>${cb ? "" : "22 ימי עבודה, "}בקשות לחודש עם מודל: <b>${Math.round(st.rpd * days * (1 - rc)).toLocaleString("en-US")}</b></span>`;
      // latency
      const t = PR[st.tier], hk = PR["claude-haiku-5-5"];
      const llm = (p) => ({ p95: p.ttft + 1000 * O / p.tps, p50: 0.55 * p.ttft + 1000 * O / (p.tps * 1.25) });
      let stages;
      if (cb) {
        const big = llm(t), small = llm(hk);
        const ans = cheap <= 0 ? { name: "answer_llm", ...big } : cheap >= 1 ? { name: "answer_llm", ...small }
          : { name: "answer_llm", p95: mainShare > 0.05 ? big.p95 : small.p95, p50: (mainShare * big.p50 + cheap * small.p50), mix: [{ w: cheap, ...small }, { w: mainShare, ...big }] };
        stages = [{ name: "input_guard", p95: 120, p50: 60 }, { name: "pii_redaction", p95: 80, p50: 40 }, { name: "intent_router", p95: 900, p50: 450 },
          { name: "vector_search", p95: 250, p50: 90, group: "retrieval" }, { name: "bm25_search", p95: 150, p50: 50, group: "retrieval" },
          ans, { name: "output_guard", p95: 200, p50: 80 }];
        if (st.k === 0) stages = stages.filter((s) => s.group !== "retrieval");
        if (st.stream) {
          const tt = (p) => ({ p95: p.ttft, p50: 0.55 * p.ttft });
          stages = stages.filter((s) => s.name !== "output_guard").map((s) => s.name === "answer_llm" ? { name: "first_token", ...(cheap >= 1 ? tt(hk) : tt(t)) } : s);
        }
      } else {
        const tri = { p95: 2500, p50: 1200 };
        stages = [{ name: "intake_guard", p95: 300, p50: 120 }, { name: "queue_wait", p95: st.queue * 1000, p50: st.queue * 100 },
          { name: "keyword_rules", p95: 30, p50: 10 }, { name: "triage_llm", ...tri },
          { name: "zendesk_update", p95: 1500, p50: 400, group: "notify" }, { name: "pagerduty", p95: 1200, p50: 300, group: "notify" }];
      }
      const budget = cb ? (st.stream ? 3000 : 8000) : 60000;
      const blocks = []; const idx = {};
      stages.forEach((s) => { const k = s.group || s.name; if (!(k in idx)) { idx[k] = blocks.length; blocks.push([k, s.p95]); } else blocks[idx[k]][1] = Math.max(blocks[idx[k]][1], s.p95); });
      const total95 = blocks.reduce((x, b) => x + b[1], 0);
      const mx = Math.max(budget, total95);
      g("g-lat").innerHTML = blocks.map(([n, v]) => `<div class="brow${v > budget * 0.5 ? " over" : ""}"><span class="t">${esc(n)}</span><span class="tr"><span class="f" style="width:${(100 * v / mx).toFixed(1)}%"></span></span><span class="v">${ms(v)}</span></div>`).join("");
      const sim = simulate(stages);
      g("g-bud").innerHTML = `<i class="sum" style="width:${(100 * total95 / mx).toFixed(1)}%"></i><i class="sim" style="width:${(100 * sim.p95 / mx).toFixed(1)}%"></i><i class="line" style="left:calc(${(100 * budget / mx).toFixed(1)}% - 1px)"></i>`;
      const label = st.stream && cb ? "יעד לטוקן הראשון" : "יעד";
      g("g-latstats").innerHTML = `<span>${label}: <b>${ms(budget)}</b></span><span>סכום p95: <b style="color:${total95 <= budget ? "var(--good)" : "var(--bad)"}">${ms(total95)}</b></span><span>סימולציה p50: <b>${ms(sim.p50)}</b></span><span>p95: <b>${ms(sim.p95)}</b></span><span>p99: <b>${ms(sim.p99)}</b></span>`;
      let note;
      if (cb) note = total > limit ? `מעל המגבלה ב-${usd(total - limit)}. המנוף הכי חזק הוא הרמה של המודל: נסה ניתוב למודל הזול, או top-k קטן יותר (הקלט הוא רוב העלות ב-RAG).`
        : `בתוך המגבלה, עם מרווח של ${usd(limit - total)}. עכשיו בדוק נפח כפול: הזז את "בקשות ביום" ל-${(st.rpd * 2).toLocaleString("en-US")}.`;
      else note = sim.p99 > budget ? `ה-p99 (${ms(sim.p99)}) מעבר ליעד של 60 שניות. כמעט כל הזנב הוא ההמתנה בתור: מודל מהיר יותר לא יעזור כאן. הפתרון הוא תור עדיפות ל-P1, או עוד workers בשיא.`
        : `בתוך היעד. שים לב איזה חלק מה-p95 הוא ההמתנה בתור לעומת המודל, ונסה להגדיל את ההמתנה כאילו יש שיא אחרי תקלה.`;
      if (cb && st.stream) note = "עם streaming המשתמש רואה את המילה הראשונה אחרי השלבים שלפני המודל ועוד TTFT. היעד כאן הוא 3 שניות לטוקן הראשון. התשובה המלאה עדיין לוקחת את כל הזמן, אבל ההמתנה המורגשת קצרה בהרבה.";
      g("g-note").textContent = note;
    }
    const bind = (id, key, num = true) => g(id).addEventListener("input", (e) => { st[key] = num ? +e.target.value : e.target.value; draw(); });
    bind("g-rpd", "rpd"); bind("g-k", "k"); bind("g-out", "out"); bind("g-cheap", "cheap"); bind("g-pc", "pc"); bind("g-rc", "rc"); bind("g-q", "queue");
    g("g-stream").addEventListener("change", (e) => { st.stream = e.target.checked; draw(); });
    host.querySelectorAll("#g-tier button").forEach((b) => b.addEventListener("click", () => { st.tier = b.dataset.m; sync(); draw(); }));
    host.querySelectorAll("#g-case button").forEach((b) => b.addEventListener("click", () => setCase(b.dataset.c)));
    setCase("cb");
  };

  /* =====================================================================
     Sim: live rule checker on Company Brain (a port of archkit.rules)
     ===================================================================== */
  const MODES = ["static_message", "cached_response", "queue_for_human"];
  function baseSpec(o) {
    const B = { employees: "untrusted", acme_vpc: "trusted", anthropic: "third_party", openai: "third_party", acme_saas: "third_party",
      tracing_saas: o.tracing === "self" ? "trusted" : "third_party" };
    const L = (id, bd, x) => ({ id, kind: "llm", boundary: bd, ...x });
    const S = (id, kind, bd, x) => ({ id, kind, boundary: bd, ...(x || {}) });
    const comps = [
      S("slack_app", "client", "employees"), S("web_ui", "client", "employees"), S("api_gateway", "service", "acme_vpc"),
      S("input_guard", "guardrail", "acme_vpc"), S("pii_redactor", "classifier", "acme_vpc"), S("keyword_router", "service", "acme_vpc"),
      L("intent_router", "anthropic", { timeout_s: o.timeout ? 10 : null, retry: 3, fallback: "keyword_router", traced: true }),
      S("retriever", "retriever", "acme_vpc"), S("vector_db", "datastore", "acme_vpc"),
      L("answer_llm", "anthropic", { timeout_s: 30, retry: 2, fallback: "answer_llm_backup", traced: true }),
      L("answer_llm_backup", "openai", { timeout_s: 30, retry: 2, fallback: "static_message", traced: true }),
      S("output_guard", "guardrail", "acme_vpc"), S("response_cache", "cache", "acme_vpc"), S("access_workflow", "service", "acme_vpc"),
      L("policy_llm", "anthropic", { timeout_s: 20, retry: 3, fallback: o.fallback === "none" ? null : o.fallback, traced: o.traced }),
      S("default_approve", "service", "acme_vpc"),
      S("approval_ui", "human_approval", "acme_vpc"), S("grant_tool", "tool", "acme_vpc", { side_effects: "write" }), S("okta", "external_api", "acme_saas"),
      S("audit_log", "datastore", "acme_vpc"), S("confluence", "external_api", "acme_saas"), S("ingest_job", "batch_job", "acme_vpc"),
      S("tracing", "observability", "tracing_saas", { pii_allowed: o.tracing === "dpa" }), S("eval_runner", "eval", "acme_vpc"),
    ];
    const F = (src, dst, data, cls, ex) => ({ src, dst, data, cls: cls || "internal", exempt: ex || null });
    const flows = [
      F("slack_app", "api_gateway", "question", "pii"), F("web_ui", "api_gateway", "question", "pii"), F("api_gateway", "input_guard", "question", "pii"),
      F("input_guard", "pii_redactor", "question", "pii"), F("pii_redactor", "intent_router", "redacted question"), F("intent_router", "retriever", "question"),
      F("retriever", "vector_db", "query"), F("retriever", "answer_llm", "question + chunks"), F("answer_llm", "output_guard", "draft"),
      F("output_guard", "response_cache", "answer"), F("output_guard", "api_gateway", "answer"), F("api_gateway", "slack_app", "answer"),
      F("intent_router", "access_workflow", "access request"),
      ...(o.shortcut ? [] : [F("slack_app", "access_workflow", "/access shortcut", "pii")]),
      F("access_workflow", "policy_llm", "request + policy"), F("policy_llm", "access_workflow", "route"),
      F("access_workflow", "approval_ui", "needs approval"), F("approval_ui", "grant_tool", "approved"),
      F("access_workflow", "grant_tool", "auto_approve", "internal", "policy v2.1"), F("grant_tool", "okta", "grant"), F("grant_tool", "audit_log", "decision"),
      F("confluence", "ingest_job", "pages"), F("ingest_job", "vector_db", "chunks"),
      o.tracing === "redacted" ? F("pii_redactor", "tracing", "redacted logs") : F("api_gateway", "tracing", "raw request logs", "pii"),
      F("access_workflow", "tracing", "workflow traces"), F("eval_runner", "api_gateway", "golden questions"),
    ];
    const by = Object.fromEntries(comps.map((c) => [c.id, c]));
    return { comps, flows, by, trust: (id) => B[by[id].boundary], out: (id) => flows.filter((f) => f.src === id), inc: (id) => flows.filter((f) => f.dst === id) };
  }
  function runRules(s) {
    const out = [], push = (sev, rule, where, msg) => out.push({ sev, rule, where, msg });
    // 1 external_input_guarded
    s.comps.filter((c) => s.trust(c.id) === "untrusted").forEach((src) => {
      const seen = new Set([src.id]), stack = [[src.id, [src.id]]], rep = new Set();
      while (stack.length) {
        const [node, path] = stack.pop();
        for (const f of s.out(node)) {
          const n = s.by[f.dst];
          if (n.kind === "guardrail" || s.trust(n.id) === "untrusted") continue;
          if (n.kind === "llm" || n.kind === "tool") { if (!rep.has(n.id)) { rep.add(n.id); push("error", "external_input_guarded", n.id, `${src.id} reaches ${n.id} without a guardrail: ${[...path, n.id].join(" -> ")}`); } continue; }
          if (!seen.has(n.id)) { seen.add(n.id); stack.push([n.id, [...path, n.id]]); }
        }
      }
    });
    // 2 llm_resilience
    s.comps.filter((c) => c.kind === "llm").forEach((c) => {
      if (!c.timeout_s) push("error", "llm_resilience", c.id, `${c.id} has no timeout_s`);
      if (!c.retry || c.retry < 2) push("error", "llm_resilience", c.id, `${c.id} has no retry`);
      if (!c.fallback) { push("error", "llm_resilience", c.id, `${c.id} has no fallback`); return; }
      if (MODES.includes(c.fallback)) return;
      if (!s.by[c.fallback]) push("error", "llm_resilience", c.id, `fallback ${c.fallback} is not a component or a mode`);
      else if (s.by[c.fallback].kind === "llm" && s.by[c.fallback].boundary === c.boundary) push("warning", "llm_resilience", c.id, `fallback in the same boundary`);
    });
    // 3 pii_classified
    s.flows.forEach((f) => {
      const d = s.by[f.dst];
      if (s.trust(d.id) !== "third_party" || d.pii_allowed) return;
      if (f.cls === "pii") { push("error", "pii_classified", `${f.src}->${f.dst}`, `pii (${f.data}) sent to third-party ${d.id}`); return; }
      const seen = new Set([f.src]), stack = [f.src]; let hit = null;
      while (stack.length && !hit) {
        const node = stack.pop();
        if (s.by[node].kind === "classifier") continue;
        for (const g of s.inc(node)) { if (g.cls === "pii") { hit = g; break; } if (!seen.has(g.src)) { seen.add(g.src); stack.push(g.src); } }
      }
      if (hit) push("error", "pii_classified", `${f.src}->${f.dst}`, `pii from ${hit.src} can reach third-party ${d.id} through ${f.src}`);
    });
    // 4 write_tools_approved
    const rep4 = new Set();
    s.comps.filter((c) => c.kind === "llm").forEach((m) => {
      const seen = new Set([m.id]), stack = [m.id];
      while (stack.length) {
        const node = stack.pop();
        for (const f of s.out(node)) {
          const n = s.by[f.dst];
          if (n.kind === "human_approval") continue;
          if (n.kind === "tool" && n.side_effects === "write") { const k = `${f.src}->${f.dst}`; if (!f.exempt && !rep4.has(k)) { rep4.add(k); push("error", "write_tools_approved", k, `${m.id} can trigger ${n.id} with no approval`); } continue; }
          if (!seen.has(n.id)) { seen.add(n.id); stack.push(n.id); }
        }
      }
    });
    // 5 observability
    s.comps.filter((c) => c.kind === "llm" && !c.traced).forEach((c) => push("warning", "observability", c.id, `${c.id} is not traced`));
    return out;
  }
  window.AIDS["l19trust"] = function (host) {
    ensureStyle();
    const o = { shortcut: false, timeout: false, fallback: "none", tracing: "raw", traced: false };
    host.innerHTML = `<div class="l19">
      <details class="guide" open><summary>מה רואים, ואיך לקרוא</summary>
      <p>זה הקובץ <code>specs/company_brain.arch.yaml</code> מהמעבדה, וחמשת הכללים של <code>arch_check.py</code>, בגרסת JavaScript שרצה בדפדפן. במצב ההתחלה יש בו ארבע בעיות שהוכנסו בכוונה, והן מייצרות 8 שגיאות ואזהרה אחת.</p>
      <p>כל מתג הוא <b>החלטת עיצוב אחת</b>: להסיר קיצור דרך, להוסיף timeout, לבחור fallback, להחליט איך הלוגים מגיעים ל-tracing. הממצאים מתעדכנים מיד. כל ממצא כתוב כמו בפלט של הבודק: <code>[חומרה] כלל @ מיקום: הסבר</code>, כשהמיקום הוא רכיב, או זרימה בצורה <code>from-&gt;to</code>.</p>
      <p>כדאי לשים לב שמספר הממצאים לא שווה למספר הבעיות: בעיה אחת יכולה לשבור כמה כללים, וזו הסיבה שבתרגיל 4 מחפשים <b>סיבות שורש</b> ולא מתקנים שורה אחרי שורה.</p></details>
      <div class="l19-tg">
        <label><input type="checkbox" id="t-short"> <span>להסיר את הקיצור <code>slack_app -&gt; access_workflow</code> (פקודת /access ישנה שעוקפת את ה-API)</span></label>
        <label><input type="checkbox" id="t-to"> <span>להוסיף ל-<code>intent_router</code> את <code>timeout_s: 10</code></span></label>
        <label><input type="checkbox" id="t-tr"> <span>לסמן <code>traced: true</code> ל-<code>policy_llm</code></span></label>
        <div><div style="font-size:.86rem">ה-fallback של <code>policy_llm</code>:</div><div class="seg" id="t-fb"><button data-v="none">אין</button><button data-v="queue_for_human">queue_for_human</button><button data-v="default_approve">default_approve (שירות שמאשר הכול)</button></div></div>
        <div><div style="font-size:.86rem">הלוגים ל-tracing (Langfuse Cloud):</div><div class="seg" id="t-trc"><button data-v="raw">גולמיים מה-API</button><button data-v="redacted">אחרי ה-redactor</button><button data-v="self">tracing אצלנו (self-hosted)</button><button data-v="dpa">ספק עם DPA (pii_allowed)</button></div></div>
      </div>
      <div class="stats" id="t-sum"></div>
      <div class="l19-find" id="t-out"></div>
      <div class="callout" id="t-note" hidden></div></div>`;
    const g = (id) => host.querySelector("#" + id);
    function draw() {
      host.querySelectorAll("#t-fb button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === o.fallback)));
      host.querySelectorAll("#t-trc button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === o.tracing)));
      const f = runRules(baseSpec(o)).sort((a, b) => (a.sev === b.sev ? a.rule.localeCompare(b.rule) : a.sev === "error" ? -1 : 1));
      const e = f.filter((x) => x.sev === "error").length;
      g("t-sum").innerHTML = `<span>שגיאות: <b style="color:${e ? "var(--bad)" : "var(--good)"}">${e}</b></span><span>אזהרות: <b>${f.length - e}</b></span>`;
      g("t-out").innerHTML = f.length ? f.map((x) => `<div class="${x.sev}">[${x.sev}] ${esc(x.rule)} @ ${esc(x.where)}: ${esc(x.msg)}</div>`).join("")
        : `<div class="clean"><b>נקי.</b> כל חמשת הכללים עוברים. עכשיו שאלה אחרת: האם כל ההחלטות שקיבלת נכונות, או רק חוקיות?</div>`;
      const n = g("t-note");
      if (o.fallback === "default_approve") { n.hidden = false; n.innerHTML = "<b>הבודק שקט, וההחלטה גרועה.</b> fallback לשירות שמאשר הכול הוא fail open: כשהמודל לא זמין, כל בקשה, כולל admin ופרודקשן, מאושרת. אף אחד מחמשת הכללים לא בודק את זה. כלל שהיה תופס: \"החלטה של רכיב ברמת אבטחה גבוהה חייבת fallback שעוצר או מעביר לאדם\". כללים אוטומטיים תופסים את מה שהגדרת, ולכן הם לא מחליפים ביקורת."; }
      else if (o.tracing === "dpa") { n.hidden = false; n.innerHTML = "חוקי לפי הכלל, אבל זו החלטה עסקית ומשפטית: מישהו צריך לחתום על DPA ולבדוק מדיניות שמירה. זה שייך ל-ADR, עם שם של מי שאישר."; }
      else n.hidden = true;
    }
    g("t-short").addEventListener("change", (e) => { o.shortcut = e.target.checked; draw(); });
    g("t-to").addEventListener("change", (e) => { o.timeout = e.target.checked; draw(); });
    g("t-tr").addEventListener("change", (e) => { o.traced = e.target.checked; draw(); });
    host.querySelectorAll("#t-fb button").forEach((b) => b.addEventListener("click", () => { o.fallback = b.dataset.v; draw(); }));
    host.querySelectorAll("#t-trc button").forEach((b) => b.addEventListener("click", () => { o.tracing = b.dataset.v; draw(); }));
    draw();
  };
})();
