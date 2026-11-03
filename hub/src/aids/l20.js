// Lesson 20 aids: untangle animation (tangled function -> ports and adapters), swap-the-adapter diagram,
// error-path simulator, design-review spot-the-flaw. Uses the hub helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  if (document.getElementById("l20-style")) return;
  const st = document.createElement("style");
  st.id = "l20-style";
  st.textContent = `
.l20 { display: grid; gap: 12px; direction: rtl; }
.l20 .two { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 12px; align-items: start; }
@media (max-width: 680px) { .l20 .two { grid-template-columns: minmax(0, 1fr); } }
.l20-code { font-family: var(--mono); font-size: .72rem; line-height: 1.5; direction: ltr; text-align: left; background: var(--code-bg); border-radius: 10px; padding: 8px; display: grid; gap: 2px; min-width: 0; }
.l20-code .ln { padding: 1px 6px; border-radius: 4px; white-space: pre-wrap; overflow-wrap: anywhere; border-inline-start: 3px solid transparent; color: var(--muted); transition: background .3s, color .3s, opacity .3s; }
.l20-code .ln.on { color: var(--ink); font-weight: 600; }
.l20-code .ln.done { opacity: .45; }
.l20-code .hd { font-weight: 600; color: var(--ink); padding: 2px 6px; }
.l20 .r-model { --c: var(--accent); } .l20 .r-retr { --c: var(--good); } .l20 .r-store { --c: var(--signal); }
.l20 .r-clock { --c: var(--muted); } .l20 .r-log { --c: var(--bad); } .l20 .r-core { --c: var(--ink); }
.l20-code .ln.on, .l20-code .ln.done { border-inline-start-color: var(--c); background: color-mix(in srgb, var(--c) 12%, transparent); }
.l20-ports { display: grid; gap: 8px; align-content: start; min-width: 0; }
.l20-port { border: 1px solid var(--line); border-inline-start: 4px solid var(--c); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 4px; animation: pop .45s ease; min-width: 0; }
.l20-port .nm { font-weight: 700; font-size: .9rem; }
.l20-port .sig { font-family: var(--mono); font-size: .72rem; direction: ltr; text-align: left; overflow-wrap: anywhere; color: var(--ink); }
.l20-port .ad { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; }
.l20-port .ad span { font-family: var(--mono); font-size: .7rem; padding: 1px 6px; border-radius: 6px; background: var(--code-bg); border: 1px solid var(--line); }
.l20-port.ghost { opacity: .55; border-style: dashed; animation: none; }
.l20-hex { display: grid; gap: 8px; }
.l20-core { border: 2px solid var(--ink); border-radius: 14px; padding: 10px; display: grid; gap: 6px; background: var(--surface); }
.l20-core .t { font-weight: 700; font-family: var(--mono); direction: ltr; text-align: center; }
.l20-core ol { margin: 0; padding-inline-start: 1.3em; font-size: .82rem; display: grid; gap: 2px; }
.l20-root { border: 1px dashed var(--accent); border-radius: 10px; padding: 8px 10px; background: var(--accent-soft); font-size: .84rem; display: grid; gap: 4px; }
.l20-root pre { font-size: .7rem; white-space: pre-wrap; overflow-wrap: anywhere; }
.l20-steps { display: flex; flex-wrap: wrap; gap: 4px; }
.l20-steps i { width: 22px; height: 6px; border-radius: 3px; background: var(--line); display: block; }
.l20-steps i.on { background: var(--accent); }
.l20-box { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; background: var(--surface); display: grid; gap: 6px; min-width: 0; }
.l20-box h4 { margin: 0; font-size: .92rem; }
.l20-box ul { margin: 0; padding-inline-start: 1.2em; display: grid; gap: 4px; font-size: .88rem; line-height: 1.6; }
.l20-box.warn { border-color: var(--signal); background: var(--signal-soft); }
.l20-box.badb { border-color: var(--bad); background: var(--bad-soft); }
.l20-box.goodb { border-color: var(--good); background: var(--good-soft); }
.l20 code.f { font-size: .78rem; }
.l20-pick { display: grid; gap: 4px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.l20-pick .lbl { font-size: .84rem; font-weight: 700; }
.l20-pick .lbl span { display: block; font-family: var(--mono); font-weight: 400; color: var(--muted); font-size: .72rem; direction: ltr; text-align: left; overflow-wrap: anywhere; }
.l20-pick.changed { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.l20-flow { display: grid; gap: 6px; }
.l20-stage { display: grid; grid-template-columns: 6.6rem minmax(0, 1fr); gap: 8px; align-items: start; border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); }
.l20-stage .who { font-weight: 700; font-size: .84rem; }
.l20-stage .who small { display: block; font-weight: 400; color: var(--muted); font-family: var(--mono); font-size: .68rem; direction: ltr; text-align: right; }
.l20-stage .what { font-size: .86rem; line-height: 1.6; min-width: 0; }
.l20-stage .what code { overflow-wrap: anywhere; }
.l20-stage.hot { border-color: var(--accent); background: var(--accent-soft); }
.l20-stage.err { border-color: var(--bad); background: var(--bad-soft); }
.l20-stage.ok { border-color: var(--good); background: var(--good-soft); }
.l20-att { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; margin-top: 4px; }
.l20-att span { font-family: var(--mono); font-size: .7rem; padding: 2px 6px; border-radius: 6px; border: 1px solid var(--line); background: var(--surface); }
.l20-att span.x { border-color: var(--bad); color: var(--bad); }
.l20-att span.v { border-color: var(--good); color: var(--good); }
.l20-att span.w { border-style: dashed; color: var(--muted); }
.l20-doc { display: grid; gap: 8px; }
.l20-para { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; background: var(--surface); display: grid; gap: 6px; }
.l20-para .id { font-family: var(--mono); font-weight: 700; color: var(--accent); }
.l20-para p { margin: 0; font-size: .9rem; line-height: 1.7; }
.l20-para pre { font-size: .72rem; white-space: pre-wrap; overflow-wrap: anywhere; }
.l20-para select { font: inherit; font-size: .84rem; color: var(--ink); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 5px 8px; max-width: 100%; }
.l20-para.right { border-color: var(--good); }
.l20-para.wrong { border-color: var(--bad); }
.l20-verdict { font-size: .86rem; line-height: 1.65; border-inline-start: 3px solid var(--accent); padding: 4px 10px; }
.l20-check { font-size: .84rem; }
.l20-check li { line-height: 1.55; }
`;
  document.head.appendChild(st);
})();

/* =============================================================== animation: untangle */
window.AIDS["l20untangle"] = function (host) {
  const LINES = [
    ["core", "def answer_question(question, email, rid):"],
    ["log", '    log.write(f"{now()} {email} asked: {question}")'],
    ["store", "    cache = json.load(open(CACHE_PATH))"],
    ["store", "    if rid in cache: return cache[rid]"],
    ["core", '    if not email.endswith("@acme.example"): return refuse()'],
    ["core", '    if re.search("salary|password", question): return refuse()'],
    ["retr", "    passages = [split(open(DATA / f).read()) for f in FILES]"],
    ["retr", "    scored = keyword_score(question, passages)[:4]"],
    ["core", "    if not scored: return NO_CONTEXT"],
    ["core", "    prompt = build_prompt(question, scored)"],
    ["model", '    llm = LLM(os.environ["BRAIN_MODEL"])'],
    ["model", "    try: r = llm.complete(prompt, system=SYSTEM)"],
    ["model", "    except LLMError: return degraded(scored)"],
    ["core", "    cites = parse_citations(r.text, ids_of(scored))"],
    ["clock", '    result = {"text": r.text, "created_at": datetime.now()}'],
    ["store", "    cache[rid] = result; json.dump(cache, open(CACHE_PATH, 'w'))"],
  ];
  const PORTS = {
    model: { nm: "ChatModel", sig: "complete(system, prompt, *, max_tokens) -> Completion\nraises ModelUnavailable | ModelRejected", ad: ["LlmkitChatModel", "FakeChatModel"] },
    retr: { nm: "Retriever", sig: "search(query, k=4) -> list[Passage]\nraises RetrieverUnavailable", ad: ["KeywordRetriever", "InMemoryRetriever", "pgvector (Q1)"] },
    store: { nm: "AnswerStore", sig: "get(request_id) -> Answer | None\nput(answer) -> bool   # first write wins", ad: ["JsonlAnswerStore", "SqliteAnswerStore", "InMemoryAnswerStore"] },
    clock: { nm: "Clock", sig: "now() -> datetime (aware)", ad: ["SystemClock", "FixedClock"] },
    log: { nm: "logging (not a port)", sig: 'log.info("answered request_id=%s status=%s cost=%.6f")', ad: ["after the policy check", "no question text, no email"] },
    core: { nm: "stays in the core: domain.py", sig: "policy_check(question, email) -> PolicyDecision\nbuild_prompt(...)  parse_citations(...)", ad: ["pure functions", "tested directly"] },
  };
  const STEPS = [
    { r: null, t: "נקודת ההתחלה: הכל באותה פונקציה",
      b: "שש-עשרה שורות שמייצגות את answer_question מהמעבדה. בקוד עצמו אין שום סימן שמפריד בין קריאה למודל, קריאת קבצים, cache ולוגיקה עסקית: הכל שורות רצופות. בצעדים הבאים נזהה אחריות אחת בכל פעם ונוציא אותה." },
    { r: "model", t: "1. המודל הופך ל-port: ChatModel",
      b: "השורות הכחולות יוצרות את ה-LLM בתוך הפונקציה (אז אי אפשר להחליף אותו בבדיקה), קוראות לו, ותופסות כל LLMError באותו אופן. ה-port מגדיר מה הליבה צריכה: טקסט מתוך system ו-prompt, ושתי שגיאות בלבד, זמנית וקבועה. llmkit נשאר בדיוק כמו שהוא, ועכשיו הוא יושב בתוך adapter שמתרגם את השגיאות שלו." },
    { r: "retr", t: "2. החיפוש הופך ל-port: Retriever",
      b: "השורות הירוקות קוראות את כל הקבצים מהדיסק בכל שאלה ומדרגות אותם. ה-port אומר רק: שאלה פנימה, עד k קטעים ממוינים החוצה. ה-adapter של מילות מפתח טוען את המסמכים פעם אחת, ברבעון הבא יבוא adapter וקטורי, והליבה לא תדע על זה." },
    { r: "store", t: "3. ה-cache הופך ל-port: AnswerStore",
      b: "שלוש השורות הכתומות הן בעצם idempotency: קריאה לפני העבודה, וכתיבה בסוף. ה-port נותן לזה שם ומבטיח 'first write wins', כך ששני ניסיונות של אותה בקשה לא ייצרו שתי תשובות. ה-fake הוא dict, ובפרודקשן אפשר SQLite או Postgres." },
    { r: "clock", t: "4. השעון הופך ל-port: Clock",
      b: "datetime.now() בתוך הפונקציה אומר שאי אפשר לבדוק את created_at, ואי אפשר לבדוק תפוגה. port קטן עם מתודה אחת פותר את זה: SystemClock בפרודקשן, FixedClock בבדיקות." },
    { r: "log", t: "5. הלוג: לא port, אבל במקום אחר ובתוכן אחר",
      b: "השורה האדומה כותבת את השאלה ואת המייל לקובץ, לפני בדיקת המדיניות. כאן לא צריך port, כי logging הסטנדרטי כבר ניתן להחלפה. מה שמשתנה הוא הסדר והתוכן: רק request_id, סטטוס ועלות, ורק אחרי שהמדיניות אישרה. זה ממצא של תכנון, לא של refactoring." },
    { r: "core", t: "6. המדיניות נשארת בליבה",
      b: "בדיקת העובדים, השכר והסיסמאות היא לא תלות חיצונית, היא העסק עצמו: מהירה, דטרמיניסטית ושלנו. היא הופכת לפונקציה טהורה policy_check בקובץ domain.py, יחד עם build_prompt ו-parse_citations, ונבדקת ישירות. לא כל דבר צריך להיות port." },
    { r: "final", t: "7. התמונה המלאה: ליבה, ports, adapters ו-composition root",
      b: "AnswerService מכיר רק את ארבעת ה-ports ואת domain.py, ומקבל את כל התלויות בבנאי. ה-adapters חיים מסביב. ובקובץ אחד בקצה, ה-composition root, מישהו בוחר אילו adapters אמיתיים לחבר. בבדיקות מחברים fakes במקומם, בלי שרת, בלי monkeypatch ובלי לחכות." },
  ];
  host.innerHTML = `<div class="l20">
    <div class="l20-steps" id="u-dots"></div>
    <div class="two">
      <div><div class="eyebrow">legacy/tangled.py (short)</div><div class="l20-code" id="u-code"></div></div>
      <div><div class="eyebrow" id="u-rh">What comes out</div><div class="l20-ports" id="u-ports"></div></div>
    </div>
    <div class="cap"><b id="u-t"></b><div id="u-b" class="muted"></div></div>
    <div class="row"><button class="btn small primary" id="u-play">השהה</button><button class="btn small" id="u-prev" aria-label="צעד קודם">→</button><button class="btn small" id="u-next" aria-label="צעד הבא">←</button><span class="spacer"></span><span class="counter" id="u-c"></span></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  let i = 0, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const order = ["model", "retr", "store", "clock", "log", "core"];

  function portCard(r, ghost) {
    const p = PORTS[r];
    return `<div class="l20-port r-${r}${ghost ? " ghost" : ""}"><div class="nm">${esc(p.nm)}</div><pre class="sig" style="background:none;padding:0">${esc(p.sig)}</pre><div class="ad">${p.ad.map((a) => `<span>${esc(a)}</span>`).join("")}</div></div>`;
  }
  function finalView() {
    return `<div class="l20-hex">
      <div class="l20-core"><div class="t">AnswerService.answer(req)</div>
        <ol dir="ltr" style="text-align:left">
          <li>store.get(request_id) → replay</li><li>policy_check() → refused</li><li>retriever.search() → no_context</li>
          <li>model.complete() → degraded on ModelUnavailable</li><li>parse_citations()</li><li>store.put() → first write wins</li>
        </ol></div>
      ${["model", "retr", "store", "clock"].map((r) => portCard(r, false)).join("")}
      <div class="l20-root"><b>composition root (answer_demo.py)</b><pre dir="ltr">svc = AnswerService(
    LlmkitChatModel(LLM("anthropic:claude-haiku-5-5")),
    KeywordRetriever.from_files(),
    JsonlAnswerStore("results/answers.jsonl"),
    SystemClock())</pre></div></div>`;
  }
  function draw() {
    const s = STEPS[i], done = order.slice(0, Math.max(0, order.indexOf(s.r)));
    if (s.r === "final") done.push(...order);
    g("u-dots").innerHTML = STEPS.map((_, k) => `<i class="${k <= i ? "on" : ""}"></i>`).join("");
    g("u-code").innerHTML = (s.r === "final"
      ? [["core", "class AnswerService:"], ["core", "    def __init__(self, model, retriever, store, clock, *, prompt): ..."], ["core", "    def answer(self, req) -> Answer:"], ["core", "        # same behavior, ports only"], ["core", "        # no LLM(), no open(), no now()"]]
      : LINES).map(([r, txt]) => {
      const on = s.r === r && s.r !== "final", dn = done.includes(r) || s.r === "final";
      return `<div class="ln r-${r}${on ? " on" : dn ? " done" : ""}">${esc(txt)}</div>`;
    }).join("");
    g("u-rh").textContent = s.r === "final" ? "Core, ports and adapters" : s.r ? "What comes out" : "Nothing extracted yet";
    if (s.r === "final") g("u-ports").innerHTML = finalView();
    else g("u-ports").innerHTML = done.map((r) => portCard(r, true)).join("") + (s.r ? portCard(s.r, false) : `<div class="l20-box"><ul><li>לוג, cache, מדיניות, קבצים, חיפוש, מודל, שעון: הכל באותה פונקציה.</li><li>כדי לבדוק אותה צריך שרת HTTP מדומה וארבעה monkeypatch.</li></ul></div>`);
    g("u-t").textContent = s.t;
    g("u-b").textContent = s.b;
    g("u-c").textContent = `${i + 1}/${STEPS.length}`;
    g("u-prev").disabled = i === 0;
    g("u-next").disabled = i === STEPS.length - 1;
  }
  function tick() { if (i < STEPS.length - 1) { i++; draw(); } else { stop(); } }
  function start() { playing = true; g("u-play").textContent = "השהה"; clearInterval(timer); timer = setInterval(tick, 6500); }
  function stop() { playing = false; g("u-play").textContent = i === STEPS.length - 1 ? "מההתחלה" : "המשך"; clearInterval(timer); timer = null; }
  g("u-play").addEventListener("click", () => {
    if (playing) stop();
    else { if (i === STEPS.length - 1) { i = 0; draw(); } start(); }
  });
  g("u-prev").addEventListener("click", () => { i = Math.max(0, i - 1); stop(); draw(); });
  g("u-next").addEventListener("click", () => { i = Math.min(STEPS.length - 1, i + 1); stop(); draw(); });
  draw();
  if (playing) start(); else stop();
  return () => clearInterval(timer);
};

/* =============================================================== sim: swap the adapter */
window.AIDS["l20swap"] = function (host) {
  const PORTS = [
    { id: "model", nm: "ChatModel", sig: "complete(system, prompt) -> Completion", leak: "complete(system, prompt) -> anthropic.types.Message",
      opts: [
        { k: "claude", l: "Claude Haiku (llmkit)", base: true },
        { k: "gpt", l: "GPT-5.4 mini (llmkit)", files: [], cfg: "מחרוזת אחרת ל-LLM: openai:gpt-5.4-mini",
          hidden: ["הפרומפט כויל על Claude. ההוראה לצטט [doc_id] עלולה להתנהג אחרת: גרסה חדשה של הפרומפט, והרצת eval לפני ואחרי.", "מחיר אחר לטוקן: בדוק את pricing.py ואת התקציב."] },
        { k: "gateway", l: "LLM gateway", files: [], cfg: "base_url של ה-gateway במקום הספק",
          hidden: ["אם גם ה-gateway עושה retries, יש עכשיו retries בשתי שכבות: כבה אחד מהם.", "השגיאות של ה-gateway צריכות להיות ממופות לאותו חוזה: 429 שלו הוא ModelUnavailable."] },
        { k: "local", l: "מודל מקומי (Ollama)", files: ["designkit/adapters_ollama.py (adapter חדש)"],
          hidden: ["איכות ו-latency אחרים לגמרי: ה-eval קובע אם זה מספיק.", "חלון הקשר קטן יותר: k=4 קטעים עלול לא להיכנס."] },
        { k: "fake", l: "FakeChatModel", files: [], tests: true, hidden: ["רק לבדיקות ולפיתוח. אף פעם לא ב-composition root של פרודקשן."] },
      ] },
    { id: "retr", nm: "Retriever", sig: "search(query, k) -> list[Passage]", leak: "search(embedding, top_k, ef_search) -> list[dict]",
      opts: [
        { k: "keyword", l: "KeywordRetriever", base: true },
        { k: "pgvector", l: "pgvector", files: ["designkit/adapters_pgvector.py (adapter חדש)", "jobs/index_documents.py (בניית אינדקס)"],
          hidden: ["סקאלת הציונים משתנה: min_score=0.2 כויל על חיפוש מילות מפתח. לנרמל בתוך ה-adapter, או להעביר את ההחלטה אליו.", "צריך embedding model ותהליך אינדוקס, ולהריץ אותו מחדש כשמסמכים משתנים."] },
        { k: "managed", l: "vector DB מנוהל", files: ["designkit/adapters_managed.py (adapter חדש)"],
          hidden: ["קריאת רשת: timeouts ו-RetrieverUnavailable הופכים למקרה אמיתי, לא תיאורטי.", "מפתח API נוסף, ונתוני החברה יוצאים לספק נוסף: שאלה לנושא 24."] },
        { k: "hybrid", l: "hybrid (מילות מפתח + וקטורי)", files: ["designkit/adapters_hybrid.py (adapter שמרכיב שני adapters)"],
          hidden: ["אותו port: ה-adapter מחזיק שני retrievers ומאחד עם RRF (נושא 12). הליבה לא יודעת שיש שניים."] },
        { k: "fake", l: "InMemoryRetriever", files: [], tests: true, hidden: ["רק לבדיקות. עובר את אותו RetrieverContract."] },
      ] },
    { id: "store", nm: "AnswerStore", sig: "get(id) / put(answer) -> bool", leak: "conn: sqlite3.Connection  (service writes SQL)",
      opts: [
        { k: "jsonl", l: "JsonlAnswerStore", base: true },
        { k: "sqlite", l: "SqliteAnswerStore", files: ["labs/20-design-driven/sqlite_store.py (סוכן כתב בתרגיל 5)"],
          hidden: ["first write wins דרך PRIMARY KEY ו-INSERT OR IGNORE, לא בדיקה ב-Python."] },
        { k: "postgres", l: "Postgres", files: ["designkit/adapters_postgres.py (adapter חדש)", "migrations/001_answers.sql"],
          hidden: ["מיגרציה של התשובות הקיימות מה-JSONL.", "first write wins אטומי: INSERT ... ON CONFLICT DO NOTHING, ובדיקת rowcount."] },
        { k: "memory", l: "InMemoryAnswerStore", files: [], tests: true, hidden: ["נמחק באתחול, ולא משותף בין כמה workers: idempotency נשבר בפרודקשן. רק לבדיקות."] },
      ] },
    { id: "clock", nm: "Clock", sig: "now() -> datetime", leak: "now() -> datetime",
      opts: [
        { k: "system", l: "SystemClock", base: true },
        { k: "fixed", l: "FixedClock", files: [], tests: true, hidden: ["רק לבדיקות: created_at צפוי, ואפשר advance() כדי לבדוק תפוגה."] },
      ] },
  ];
  const sel = Object.fromEntries(PORTS.map((p) => [p.id, p.opts[0].k]));
  host.innerHTML = `<div class="l20">
    <div class="guide"><p><b>מה רואים:</b> לכל אחד מארבעת ה-ports של שירות התשובות יש שורת כפתורים, ובכל שורה ה-adapter הנוכחי מסומן. ברירת המחדל היא מה שרץ במעבדה: Claude דרך llmkit, חיפוש מילות מפתח, קובץ JSONL ושעון מערכת.</p>
    <p><b>איך לקרוא:</b> כשבוחרים adapter אחר, ארבע התיבות למטה מתעדכנות: אילו קבצים משתנים, אילו קבצים לא נוגעים בהם, אילו בדיקות להריץ, ומה הממשק <b>לא</b> מסתיר (הדברים שעדיין צריך לחשוב עליהם). המתג "ports דולפים" מחליף את חתימות ה-ports לגרסה שמעוצבת לפי ספק, כמו במסמך של תרגיל 8, ומראה מה זה עושה לאותן החלפות.</p></div>
    <label class="row" style="font-size:.9rem"><input type="checkbox" id="sw-leak"> <b>ports דולפים</b> (החתימות מכילות טיפוסים ופרמטרים של ספק)</label>
    <div id="sw-picks" style="display:grid;gap:8px"></div>
    <div class="two">
      <div class="l20-box" id="sw-changed"></div>
      <div class="l20-box goodb" id="sw-same"></div>
    </div>
    <div class="two">
      <div class="l20-box" id="sw-tests"></div>
      <div class="l20-box warn" id="sw-hidden"></div>
    </div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  function draw() {
    const leak = g("sw-leak").checked;
    g("sw-picks").innerHTML = PORTS.map((p) => {
      const changed = sel[p.id] !== p.opts[0].k;
      return `<div class="l20-pick${changed ? " changed" : ""}"><div class="lbl">${esc(p.nm)} <span>${esc(leak ? p.leak : p.sig)}</span></div>
        <div class="seg" role="group" aria-label="${esc(p.nm)}">${p.opts.map((o) => `<button data-p="${p.id}" data-k="${o.k}" aria-pressed="${sel[p.id] === o.k}">${esc(o.l)}</button>`).join("")}</div></div>`;
    }).join("");
    host.querySelectorAll("#sw-picks button").forEach((b) => b.addEventListener("click", () => { sel[b.dataset.p] = b.dataset.k; draw(); }));
    const picked = PORTS.map((p) => [p, p.opts.find((o) => o.k === sel[p.id])]).filter(([p, o]) => !o.base);
    const changed = new Set(), hidden = [], tests = new Set(), notes = [];
    let leakHit = false;
    for (const [p, o] of picked) {
      (o.files || []).forEach((f) => changed.add(f));
      if (o.cfg) notes.push(`${p.nm}: ${o.cfg}`);
      (o.hidden || []).forEach((x) => hidden.push(`<b>${esc(p.nm)}:</b> ${esc(x)}`));
      tests.add(`${p.nm}Contract על ה-adapter החדש`);
      if (leak && p.id !== "clock") {
        leakHit = true;
        changed.add(`designkit/service.py (${p.id === "model" ? "קורא message.content[0].text" : p.id === "retr" ? "מחשב embedding ומעביר ef_search" : "כותב SQL ישירות"})`);
        changed.add("designkit/fakes.py (ה-fake צריך לחקות את הספק החדש)");
        changed.add("tests/test_ex3_service.py (הבדיקות בונות אובייקטים של הספק)");
      }
    }
    if (picked.some(([, o]) => !o.tests)) changed.add("answer_demo.py (composition root: שורה אחת לכל port שהוחלף)");
    if (picked.length && picked.every(([, o]) => o.tests)) notes.push("כל ה-adapters שנבחרו הם fakes: זה הרכב של בדיקה, לא של פרודקשן. ה-composition root של הבדיקות הוא הבנאי בתוך הבדיקה.");
    const same = ["designkit/domain.py (מדיניות, דירוג, פרומפט, ציטוטים)"];
    if (!leakHit) same.unshift("designkit/service.py (AnswerService)", "designkit/fakes.py", "tests/test_ex3_service.py ו-after_tests/ (בדיקות השירות)");
    same.push("designkit/types.py (טיפוסי הדומיין וחוזה השגיאות)");
    if (picked.length) tests.add("tests/test_ex3_service.py: לא אמור להשתנות כלום. אם משהו נשבר, ה-port דולף");
    if (picked.some(([p]) => p.id === "model")) tests.add("eval על ה-golden set (נושא 23): לפני ואחרי ההחלפה");
    g("sw-changed").className = "l20-box" + (leakHit ? " badb" : "");
    g("sw-changed").innerHTML = `<h4>קבצים שמשתנים (${changed.size})</h4>${changed.size ? `<ul>${[...changed].map((f) => `<li><code class="f">${esc(f.split(" (")[0])}</code>${f.includes(" (") ? " " + esc("(" + f.split(" (").slice(1).join(" (")) : ""}</li>`).join("")}${notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : `<p class="muted" style="margin:0;font-size:.88rem">שום דבר עדיין. בחר adapter אחר באחד ה-ports.</p>`}`;
    g("sw-same").innerHTML = `<h4>לא נוגעים בהם</h4><ul>${same.map((f) => `<li><code class="f">${esc(f.split(" (")[0])}</code>${f.includes(" (") ? " " + esc("(" + f.split(" (").slice(1).join(" (")) : ""}</li>`).join("")}</ul>`;
    g("sw-tests").innerHTML = `<h4>מה להריץ</h4>${tests.size ? `<ul>${[...tests].map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<p class="muted" style="margin:0;font-size:.88rem">אין שינוי, אין מה להריץ מעבר לרגיל.</p>`}`;
    g("sw-hidden").innerHTML = `<h4>מה הממשק לא מסתיר</h4>${hidden.length ? `<ul>${hidden.map((x) => `<li>${x}</li>`).join("")}</ul>` : `<p class="muted" style="margin:0;font-size:.88rem">כאן יופיעו הצימודים שהחתימה של ה-port לא תופסת: פרומפט שכויל על מודל אחד, סקאלת ציונים, מיגרציות.</p>`}${leakHit ? `<p style="margin:0;font-size:.88rem"><b>במצב דולף</b> כל החלפה נוגעת גם בליבה ובבדיקות שלה. זה בדיוק מה שהפגמים D2 ו-D3 בתרגיל 8 מתארים.</p>` : ""}`;
  }
  g("sw-leak").addEventListener("change", draw);
  draw();
};

/* =============================================================== sim: error path */
window.AIDS["l20errors"] = function (host) {
  const ERRS = [
    { k: "429", l: "429 rate limit", transient: true, http: "429", kind: "rate_limit_error" },
    { k: "529", l: "529 overloaded", transient: true, http: "529", kind: "overloaded_error" },
    { k: "timeout", l: "timeout", transient: true, http: "—", kind: "timeout" },
    { k: "401", l: "401 מפתח שגוי", transient: false, http: "401", kind: "authentication_error" },
    { k: "400", l: "400 בקשה שגויה", transient: false, http: "400", kind: "invalid_request_error" },
    { k: "refusal", l: "סירוב (200)", transient: false, http: "200", kind: "stop_reason=refusal" },
  ];
  let cur = "529";
  host.innerHTML = `<div class="l20">
    <div class="guide"><p><b>מה רואים:</b> שאלה של עובד יוצאת לספק המודל, ומשהו משתבש. בוחרים מה בדיוק קרה, והמסלול למטה מראה איך התקלה עוברת בין השכבות: <b>הספק</b>, <b>llmkit</b> (שאחראי על retries), <b>ה-adapter</b> (שמתרגם לחוזה השגיאות), <b>השירות</b> (שמחליט מה לעשות), ו<b>המשתמש</b>. השלב שבו ההחלטה נופלת צבוע.</p>
    <p><b>שורת הניסיונות</b> בשלב של llmkit מראה כל קריאה לספק: אדום הוא כישלון, ירוק הצלחה, ומקווקו הוא ההמתנה (backoff) לפני הניסיון הבא. בתחתית יש את מה שהקוד הסבוך היה עושה באותו מצב, לשם השוואה. שני המתגים משנים את התרחיש: תקלה שחולפת אחרי הניסיון השני, ו-retries כפולים גם בשירות.</p></div>
    <div class="seg" role="group" aria-label="סוג התקלה" id="er-seg">${ERRS.map((e) => `<button data-k="${e.k}" aria-pressed="${e.k === cur}">${esc(e.l)}</button>`).join("")}</div>
    <label class="row" style="font-size:.88rem"><input type="checkbox" id="er-clear"> התקלה חולפת אחרי הניסיון השני</label>
    <label class="row" style="font-size:.88rem"><input type="checkbox" id="er-double"> retries גם בשירות (3 ניסיונות חוזרים סביב כל קריאה)</label>
    <div class="l20-flow" id="er-flow"></div>
    <div class="stats" id="er-stats"></div>
    <div class="l20-box badb" id="er-tangled"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  function attempts(e, clear) {
    if (!e.transient) return [["x", `1: ${e.http}`]];
    const out = [], waits = ["~0.25s", "~0.5s", "~1s"];
    for (let a = 1; a <= 4; a++) {
      if (clear && a === 3) { out.push(["v", `${a}: 200`]); return out; }
      out.push(["x", `${a}: ${e.http}`]);
      if (a < 4) out.push(["w", `wait ${waits[a - 1]}`]);
    }
    return out;
  }
  function draw() {
    host.querySelectorAll("#er-seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === cur)));
    const e = ERRS.find((x) => x.k === cur), clear = g("er-clear").checked, dbl = g("er-double").checked;
    const att = attempts(e, clear), calls = att.filter((a) => a[0] !== "w").length, ok = att.some((a) => a[0] === "v");
    const totalCalls = e.transient && !ok && dbl ? calls * 4 : calls;
    const perm = !e.transient;
    const st = (cls, who, sub, what) => `<div class="l20-stage ${cls}"><div class="who">${who}<small>${sub}</small></div><div class="what">${what}</div></div>`;
    const attHtml = `<div class="l20-att">${att.map(([c, t]) => `<span class="${c}">${esc(t)}</span>`).join("")}</div>`;
    let rows = [];
    rows.push(st("", "ספק המודל", "provider", e.k === "refusal" ? "מחזיר HTTP 200, אבל stop_reason הוא refusal: המודל סירב לענות." : e.k === "timeout" ? "לא עונה בזמן: החיבור נסגר אחרי ה-read timeout של llmkit (60 שניות בין בתים)." : `מחזיר HTTP ${e.http} (<code>${esc(e.kind)}</code>).`));
    rows.push(st(e.transient ? "hot" : "", "llmkit", "RetryPolicy, classify_error", (e.transient ? (ok ? "classify_error אומר: זמני, כדאי לנסות שוב. הניסיון השלישי מצליח." : "classify_error אומר: זמני. ארבעה ניסיונות עם backoff, וכולם נכשלים. llmkit זורק LLMError.") : e.k === "refusal" ? "אין כאן שגיאת HTTP, אז אין retry. llmkit מחזיר ChatResult עם stop_reason=refusal." : "classify_error אומר: קבוע. אותה בקשה תיכשל שוב, אז אין retry. llmkit זורק LLMError מיד.") + attHtml));
    if (ok) {
      rows.push(st("", "adapter", "LlmkitChatModel", "קיבל תשובה רגילה, מחזיר Completion. ה-adapter לא יודע ולא צריך לדעת שהיו שני כישלונות."));
      rows.push(st("ok", "שירות", "AnswerService", "status=answered, נשמר ב-store. התשובה הגיעה קצת יותר לאט, וזה הכל."));
      rows.push(st("ok", "משתמש", "user", "מקבל תשובה עם ציטוטים."));
    } else if (!perm) {
      rows.push(st("hot", "adapter", "LlmkitChatModel", "<code>raise ModelUnavailable(str(exc)) from exc</code>. השגיאה המקורית נשמרת ב-__cause__ ללוג."));
      rows.push(st("hot", "שירות", "AnswerService", (dbl ? "השירות תופס ומנסה שוב, עוד שלוש פעמים, וכל ניסיון כזה מפעיל שוב את ארבעת הניסיונות של llmkit. אחר כך: " : "") + "status=degraded עם רשימת המסמכים הרלוונטיים, <b>ולא נשמר</b>, כדי שניסיון חוזר עם אותו request_id יוכל להצליח."));
      rows.push(st("", "משתמש", "user", "\"השירות לא זמין כרגע. המסמכים האלה נראים רלוונטיים: Remote Work Policy...\". אפשר לנסות שוב בעוד דקה."));
    } else {
      rows.push(st("err", "adapter", "LlmkitChatModel", e.k === "refusal" ? "<code>if r.stop_reason == \"refusal\": raise ModelRejected(...)</code>" : "<code>raise ModelRejected(str(exc)) from exc</code>"));
      rows.push(st("err", "שירות", "AnswerService", "לא תופס את ModelRejected: זה באג, בעיית קונפיגורציה או תוכן שהמודל לא יענה עליו. השגיאה עולה לשכבת ה-API, ללוג ולהתראה. שום דבר לא נשמר." + (e.k === "refusal" ? " <i>החלטת תכנון:</i> אפשר גם לתכנן סירוב כ-status נפרד שמוצג למשתמש. מה שחשוב הוא שזה מוגדר בחוזה, ולא מתערבב עם \"לא זמין\"." : "")));
      rows.push(st("err", "משתמש", "user", e.k === "401" ? "HTTP 500 עם הודעה כללית. אצל הצוות: התראה בדקה הראשונה, \"ModelRejected: authentication_error\". מחליפים מפתח." : e.k === "400" ? "HTTP 500. אצל הצוות: הלוג מראה בדיוק מה בבקשה לא תקין, למשל פרומפט ארוך מדי." : "הודעה שהשאלה לא נענתה. אצל הצוות: הסירוב מתועד, ואפשר לבדוק אם השאלה או הפרומפט גרמו לו."));
    }
    g("er-flow").innerHTML = rows.join("");
    g("er-stats").innerHTML = `<span>קריאות לספק: <b>${totalCalls}</b></span><span>מי מנסה שוב: <b>${dbl ? "llmkit וגם השירות" : "llmkit בלבד"}</b></span><span>מה נשמר: <b>${ok ? "התשובה" : "כלום"}</b></span>` + (dbl && e.transient && !ok ? `<span style="color:var(--bad)">4 ניסיונות כפול 4 = ${totalCalls} קריאות, דווקא כשהספק עמוס</span>` : "");
    g("er-tangled").innerHTML = `<h4>אותו מצב בקוד הסבוך</h4><ul><li>${e.k === "refusal" ? "אין שם בדיקה של stop_reason. טקסט הסירוב חוזר כתשובה רגילה עם status=answered, <b>ונשמר ב-cache</b>, כך שגם הניסיון הבא יקבל אותו." : ok ? "אותה תוצאה: llmkit מנסה שוב בפנים, והתשובה מגיעה." : "<code>except LLMError</code> תופס הכל: status=degraded, \"השירות לא זמין זמנית\"."}</li>${perm && e.k !== "refusal" ? `<li><b>${e.k === "401" ? "מפתח שגוי" : "בקשה שגויה"} נראה בדיוק כמו עומס זמני.</b> אין התראה, ואין הבדל בלוג חוץ משורת print. באג קונפיגורציה יכול לחיות שם ימים.</li>` : ""}${e.transient && !ok ? `<li>בבדיקה: llmkit באמת ממתין בין ארבעת הניסיונות, ואין דרך להזריק לו מדיניות אחרת. זו הבדיקה האיטית ב-measure.py --before.</li>` : ""}</ul>`;
  }
  host.querySelectorAll("#er-seg button").forEach((b) => b.addEventListener("click", () => { cur = b.dataset.k; draw(); }));
  g("er-clear").addEventListener("change", draw);
  g("er-double").addEventListener("change", draw);
  draw();
};

/* =============================================================== sim: design review */
window.AIDS["l20review"] = function (host) {
  const CHECK = [
    ["C1", "Ports מדברים בשפת הדומיין", "אין טיפוסים של ספק או SDK בפרמטרים או בערכי ההחזרה."],
    ["C2", "חוזה שגיאות", "אילו שגיאות, מה זמני ומה קבוע, ושכבה אחת שאחראית על retries. שגיאה לא נבלעת בשקט."],
    ["C3", "ממשק לפי הדומיין, לא לפי מימוש", "אין פרמטרים שהגיוניים רק לטכנולוגיה של היום."],
    ["C4", "Idempotency", "ניסיון חוזר לא מבצע פעולה פעמיים: מפתח מהלקוח, first write wins."],
    ["C5", "גרסאות לפרומפטים ולסכמות", "גרסאות שלא משתנות, pin אצל הצרכן, הגרסה נרשמת על כל פלט."],
    ["C6", "שומרים לפני שהנתונים יוצאים", "בדיקות מדיניות רצות לפני מודל, לפני כלים ולפני לוג עם תוכן."],
    ["C7", "בדיקות בלי רשת", "תלויות מוזרקות, fake לכל port, וחבילת חוזה שכל adapter עובר."],
    ["C8", "תאימות של סכמות ציבוריות", "שינוי שם או הסרה של שדה שלקוחות קוראים: גרסה חדשה, או תקופת מעבר."],
    ["C9", "Observability", "request id בכל קריאה ובכל שורת לוג, בלי תוכן אישי."],
  ];
  const DOC = [
    { id: "P1", text: "<b>הקשר.</b> בתהליך אישור הגישה של Company Brain, אחרי שהוחלט על מסלול, השירות צריך לתת את הגישה בפועל דרך ספק הזהויות (Okta). המסמך מתכנן את ה-port של הכלי הזה ואת ה-adapter שלו. כ-300 בקשות ביום.", key: "ok",
      why: "הקשר קצר עם מספר. אין כאן החלטה שאפשר לטעות בה, וזה בדיוק מה שסעיף הקשר צריך להיות." },
    { id: "P2", text: "<b>ה-port.</b>", code: "class IdentityProvider(Protocol):\n    def grant(self, user: str, app: str, level: str) -> okta.models.User: ...", text2: "השירות קורא את <code>user.profile.login</code> מהתוצאה כדי לאשר שהגישה ניתנה.", key: "C1",
      why: "הטיפוס של Okta עובר בגבול, והשירות קורא שדות שלו. מעבר ל-Azure AD, או fake בבדיקות, מחייב לחקות את ה-SDK של Okta. התיקון: להחזיר טיפוס דומיין, למשל Grant(user, app, level, granted_at, external_id)." },
    { id: "P3", text: "<b>הזרימה.</b> כדי לקצר את זמן ההמתנה, ברגע שהמסווג (ה-LLM) מחזיר מסלול auto_approve, השירות קורא ל-<code>grant</code> מיד. מנוע המדיניות רץ אחר כך, במקביל, ואם הוא לא מסכים, הגישה מבוטלת.", key: "C6",
      why: "המודל מציע והכללים מחליטים, לא להפך. כאן גישה ניתנת על סמך פלט של LLM, לפני הכללים, ו-prompt injection בהודעה של העובד יכול לקבל admin לכמה שניות או דקות. התיקון: מנוע המדיניות לפני כל grant, תמיד." },
    { id: "P4", text: "<b>Timeouts.</b> אם הקריאה ל-Okta לא חוזרת תוך 3 שניות, השירות קורא ל-<code>grant</code> שוב, עד שלוש פעמים. ל-Okta אין זיהוי כפילויות בצד שלה, ואנחנו לא מעבירים שום מזהה של הבקשה.", key: "C4",
      why: "timeout לא אומר שהפעולה לא התבצעה. ניסיון חוזר בלי מפתח idempotency יכול לתת את הגישה פעמיים, לפתוח שני מושבים בתשלום, או ליצור שני רישומי audit. התיקון: להעביר request_id, ולבדוק ב-store אם כבר ניתן grant לפני שמנסים שוב." },
    { id: "P5", text: "<b>שגיאות.</b> כל חריגה מה-adapter נרשמת ללוג, הבקשה מסומנת approved, והעובד מקבל הודעה שהגישה תופיע בקרוב. כך המשתמש לא נתקע בגלל תקלות זמניות.", key: "C2",
      why: "החריגה נבלעת, והמערכת מדווחת על הצלחה שלא קרתה. אין הבחנה בין זמני (לנסות שוב) לקבוע (הרשאה חסרה, משתמש לא קיים). התיקון: חוזה שגיאות, למשל ToolUnavailable מול ToolRejected, וסטטוס pending עם ניסיון חוזר מתוזמן במקום approved." },
    { id: "P6", text: "<b>הפרומפט של המסווג.</b> הוא נמצא בקובץ <code>prompts/classifier.txt</code>, שנקרא בכל בקשה. כשמשפרים אותו, עורכים את הקובץ על השרת, והשינוי נכנס מיד בלי deploy.", key: "C5",
      why: "אין גרסה, אין rollback, ואין דרך לדעת איזה פרומפט סיווג בקשה מסוימת. כשסיווג שגוי מגיע מביקורת, אי אפשר לשחזר אותו. התיקון: גרסאות שלא משתנות, pin בשירות, והגרסה נרשמת על כל החלטה." },
    { id: "P7", text: "<b>בדיקות.</b> יש FakeIdentityProvider בזיכרון. חבילת חוזה אחת רצה על ה-fake בכל commit, ועל sandbox של Okta פעם בלילה. השירות נבדק עם ה-fake.", key: "ok",
      why: "זה התכנון הנכון: fake לבדיקות מהירות, וחבילת חוזה שמוודאת שה-fake וה-adapter האמיתי מתנהגים אותו דבר. הריצה הלילית מול sandbox תופסת שינויים אצל הספק." },
    { id: "P8", text: "<b>לוגים.</b> כל קריאה ל-grant נרשמת עם request_id, המסלול, האפליקציה וה-latency. שם העובד ותוכן ההודעה שלו לא נרשמים.", key: "ok",
      why: "request id שמחבר את כל השלבים, ומטא-דאטה בלי תוכן אישי. זה C9 כמו שצריך." },
    { id: "P9", text: "<b>סכמת התגובה.</b> שדה <code>route</code> בתגובה של ה-API יחזיר מעכשיו <code>manager</code> ו-<code>security</code> במקום <code>needs_manager</code> ו-<code>needs_security</code>, כי זה קצר יותר. בוט ה-Slack יתעדכן בספרינט הבא.", key: "C8",
      why: "שינוי ערכים של שדה ציבורי שובר את בוט ה-Slack ביום ה-deploy, וכל לקוח אחר שקורא את השדה. מבחינת הקורא, ערכי enum חדשים הם שינוי שובר. התיקון: להשאיר את הערכים, או לפרסם גרסה חדשה של ה-API ולתת תקופת מעבר." },
  ];
  const ans = {};
  host.innerHTML = `<div class="l20">
    <div class="guide"><p><b>מה יש כאן:</b> מסמך תכנון קצר, תשעה סעיפים (P1 עד P9), של ה-adapter שנותן גישה בפועל בתהליך אישור הגישה. מעליו יש את הצ'קליסט, אותו צ'קליסט כמו בתרגיל 8 במעבדה, בתשעה פריטים (C1 עד C9).</p>
    <p><b>מה עושים:</b> לכל סעיף בוחרים ברשימה אם הוא <b>תקין</b>, או <b>איזה פריט בצ'קליסט</b> הוא מפר. ההסבר מופיע מיד אחרי הבחירה, ואפשר לשנות בחירה. חלק מהסעיפים תקינים, וחלק מהפגמים נראים כמו החלטה סבירה במבט ראשון. הציון בתחתית סופר פגמים שנמצאו, וסעיפים תקינים שסומנו בטעות.</p></div>
    <details class="cd-what" open><summary>הצ'קליסט (C1 עד C9)</summary><ul class="l20-check">${CHECK.map(([c, t, d]) => `<li><b>${c}. ${esc(t)}.</b> ${esc(d)}</li>`).join("")}</ul></details>
    <div class="l20-doc" id="rv-doc"></div>
    <div class="stats" id="rv-score"></div>
    <div class="row"><button class="btn small" id="rv-reset">לנקות ולהתחיל מחדש</button></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  const optHtml = `<option value="">בחר...</option><option value="ok">תקין</option>${CHECK.map(([c, t]) => `<option value="${c}">${c}: ${esc(t)}</option>`).join("")}`;
  g("rv-doc").innerHTML = DOC.map((d) => `<div class="l20-para" data-id="${d.id}"><div class="row"><span class="id">${d.id}</span></div><p>${d.text}</p>${d.code ? `<pre dir="ltr">${esc(d.code)}</pre>` : ""}${d.text2 ? `<p>${d.text2}</p>` : ""}
    <label style="font-size:.84rem;display:grid;gap:4px">הערכה שלך<select aria-label="הערכה ל-${d.id}">${optHtml}</select></label><div class="l20-verdict" hidden></div></div>`).join("");
  function score() {
    const flaws = DOC.filter((d) => d.key !== "ok");
    const found = flaws.filter((d) => ans[d.id] && ans[d.id] !== "ok").length;
    const exact = flaws.filter((d) => ans[d.id] === d.key).length;
    const fp = DOC.filter((d) => d.key === "ok" && ans[d.id] && ans[d.id] !== "ok").length;
    const answered = Object.keys(ans).length;
    g("rv-score").innerHTML = `<span>נענו: <b>${answered}/${DOC.length}</b></span><span>פגמים שנמצאו: <b>${found}/${flaws.length}</b></span><span>עם הפריט הנכון: <b>${exact}</b></span><span>סעיפים תקינים שסומנו כפגם: <b>${fp}</b></span>`;
  }
  host.querySelectorAll(".l20-para").forEach((el) => {
    const d = DOC.find((x) => x.id === el.dataset.id), s = el.querySelector("select"), v = el.querySelector(".l20-verdict");
    s.addEventListener("change", () => {
      if (!s.value) { delete ans[d.id]; v.hidden = true; el.classList.remove("right", "wrong"); score(); return; }
      ans[d.id] = s.value;
      const right = s.value === d.key, half = d.key !== "ok" && s.value !== "ok" && !right;
      el.classList.toggle("right", right);
      el.classList.toggle("wrong", !right && !half);
      const head = right ? (d.key === "ok" ? "נכון, הסעיף תקין." : `נכון: ${d.key}.`) : half ? `יש כאן פגם, אבל הפריט העיקרי הוא ${d.key}.` : d.key === "ok" ? "הסעיף הזה בעצם תקין." : `יש כאן פגם: ${d.key}.`;
      v.innerHTML = `<b>${esc(head)}</b> ${esc(d.why)}`;
      v.hidden = false;
      score();
    });
  });
  g("rv-reset").addEventListener("click", () => {
    for (const k of Object.keys(ans)) delete ans[k];
    host.querySelectorAll(".l20-para").forEach((el) => { el.querySelector("select").value = ""; el.querySelector(".l20-verdict").hidden = true; el.classList.remove("right", "wrong"); });
    score();
  });
  score();
};
