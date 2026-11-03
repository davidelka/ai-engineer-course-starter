// Lesson 28 aids: system-design whiteboard animation, SM-2 flashcards, red/green flag game, 5-minute pitch coach.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  if (document.getElementById("l28-style")) return;
  const st = document.createElement("style");
  st.id = "l28-style";
  st.textContent = `
.l28-phases { display: flex; flex-wrap: wrap; gap: 4px; }
.l28-phases span { font-size: .74rem; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); background: var(--surface); }
.l28-phases span.done { border-color: var(--good); color: var(--good); background: var(--good-soft); }
.l28-phases span.on { border-color: var(--accent); background: var(--accent-soft); color: var(--ink); font-weight: 700; }
.l28-phases span.miss { border-color: var(--bad); color: var(--bad); background: var(--bad-soft); text-decoration: line-through; }
.l28-clock { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: .86rem; }
.l28-clock b { font-family: var(--mono); font-size: 1.1rem; font-variant-numeric: tabular-nums; }
.l28-strip { position: relative; display: flex; height: 12px; border-radius: 6px; overflow: hidden; direction: ltr; border: 1px solid var(--line); }
.l28-strip i { display: block; height: 100%; border-inline-end: 1px solid var(--surface); background: var(--accent-soft); }
.l28-strip i.done { background: var(--good-soft); }
.l28-strip i.on { background: var(--accent); }
.l28-strip .mk { position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--signal); transition: left .4s; }
.l28-board { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 10px; min-height: 230px; display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 8px; align-content: start; }
.l28-note { border: 1px solid var(--line); border-inline-start: 4px solid var(--accent); border-radius: 8px; padding: 6px 8px; font-size: .8rem; line-height: 1.45; background: var(--bg, var(--surface)); min-width: 0; overflow-wrap: anywhere; }
.l28-note .ph { display: block; font-size: .68rem; color: var(--muted); margin-bottom: 2px; }
.l28-note.new { animation: l28pop .5s ease; box-shadow: 0 0 0 2px var(--signal); }
.l28-note.bad { border-inline-start-color: var(--bad); background: var(--bad-soft); }
.l28-note.gap { border-style: dashed; border-inline-start-color: var(--bad); color: var(--bad); background: transparent; }
.l28-note.c0, .l28-note.c3, .l28-note.c6 { border-inline-start-color: var(--accent); }
.l28-note.c1, .l28-note.c4, .l28-note.c7 { border-inline-start-color: var(--signal); }
.l28-note.c2, .l28-note.c5, .l28-note.c8 { border-inline-start-color: var(--good); }
@keyframes l28pop { from { transform: scale(.92); opacity: .3; } to { transform: none; opacity: 1; } }
.l28-say { border-inline-start: 3px solid var(--signal); background: var(--signal-soft); border-radius: 0 10px 10px 0; padding: 8px 12px; min-height: 92px; }
.l28-say q { display: block; font-style: italic; margin-bottom: 4px; }
.l28-card { border: 1px solid var(--line); border-radius: 12px; padding: 14px; background: var(--surface); display: grid; gap: 10px; min-height: 200px; }
.l28-card h4 { margin: 0; font-size: 1.02rem; line-height: 1.55; }
.l28-keys { margin: 0; padding-inline-start: 1.2em; display: grid; gap: 4px; font-size: .9rem; line-height: 1.6; }
.l28-grades { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 4px; }
.l28-grades button { border: 1px solid var(--line); background: var(--surface); border-radius: 8px; padding: 6px 2px; font-size: .78rem; line-height: 1.25; color: var(--ink); }
.l28-grades button b { display: block; font-family: var(--mono); font-size: 1rem; }
.l28-grades button.lo { border-color: var(--bad); }
.l28-grades button.hi { border-color: var(--good); }
@media (max-width: 480px) { .l28-grades { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.l28-flag { border: 1px solid var(--line); border-radius: 10px; padding: 10px; display: grid; gap: 8px; min-width: 0; }
.l28-flag .qq { font-size: .84rem; color: var(--muted); }
.l28-flag blockquote { margin: 0; padding: 6px 10px; border-inline-start: 3px solid var(--line); background: var(--code-bg); border-radius: 0 8px 8px 0; font-size: .9rem; line-height: 1.6; unicode-bidi: plaintext; }
.l28-flag.right { border-color: var(--good); }
.l28-flag.wrong { border-color: var(--bad); }
.l28-flag .seg button.red[aria-pressed="true"] { border-color: var(--bad); background: var(--bad-soft); }
.l28-flag .seg button.green[aria-pressed="true"] { border-color: var(--good); background: var(--good-soft); }
.l28-timer { font-family: var(--mono); font-size: 2.2rem; font-weight: 700; text-align: center; font-variant-numeric: tabular-nums; direction: ltr; }
.l28-timer.over { color: var(--bad); }
.l28-secs { display: grid; gap: 6px; }
.l28-sec { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 4px; }
.l28-sec.on { border-color: var(--accent); background: var(--accent-soft); }
.l28-sec.done { opacity: .75; }
.l28-sec .top { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.l28-sec .top b { flex: 1; min-width: 0; }
.l28-sec .top span { font-family: var(--mono); font-size: .8rem; color: var(--muted); }
.l28-sec .top span.over { color: var(--bad); font-weight: 700; }
.l28-bar { height: 6px; border-radius: 3px; background: var(--line); overflow: hidden; direction: ltr; }
.l28-bar i { display: block; height: 100%; background: var(--accent); transition: width .25s; }
.l28-bar i.over { background: var(--bad); }
.l28-sec .tip { font-size: .86rem; line-height: 1.6; }
.l28-sec .ex { font-size: .84rem; color: var(--muted); line-height: 1.6; }
`;
  document.head.appendChild(st);
})();

/* ---------------- animation: the 45-minute whiteboard ---------------- */
window.AIDS["l28board"] = function (host) {
  const PH = ["דרישות", "מדדים", "ארכיטקטורה", "נתונים", "Eval", "כשלים", "עלות ו-latency", "אבטחה", "איטרציה"];
  const BUDGET = [6, 3, 12, 4, 5, 5, 4, 3, 3]; // minutes, sums to 45
  const STRONG = [
    { p: 0, t: 3, note: "מי קורא את הפלט? נציג מאשר. v1 לא סוגר פניות לבד.",
      say: "Before I design anything: who reads the output, the employee or an agent?",
      why: "המועמד לא מצייר כלום עדיין. התשובה לשאלה הזו קובעת את רמת הסיכון של כל המערכת: טיוטה שנציג מאשר היא מערכת אחרת לגמרי מבוט שעונה ישר לעובד." },
    { p: 0, t: 6, note: "600 פניות ביום, שיא 120 בשעה. עברית ואנגלית. אסינכרוני, אבל P1 של security מגיע לאדם תוך 15 דקות.",
      say: "So this is async, a minute is fine, except P1 security. I'll optimize for recall there.",
      why: "מספרים ראשונים על הלוח. כבר עכשיו ברור שלא צריך סטרימינג, שעברית תשפיע על הטוקנים ועל BM25, ושהטעות היקרה היא פניית אבטחה בתור הלא נכון." },
    { p: 1, t: 9, note: "דיוק ניתוב לכל תור. recall של 98% לפחות ל-security. זמן עד ניתוב: מ-4 שעות לפחות מ-5 דקות.",
      say: "Success is time-to-route under 5 minutes, without missing security tickets.",
      why: "מדד עסקי אחד, מדדים טכניים שמסבירים אותו, ומדד שמגן על המקום הרגיש. מעכשיו, כל החלטה בארכיטקטורה נמדדת מול השורה הזו." },
    { p: 2, t: 15, note: "קליטה ל-queue. סיווג במודל קטן עם structured output: תור, דחיפות, ביטחון, ונימוק קצר לפני ההחלטה.",
      say: "A workflow, not an agent: the order is known, and I want to test every step.",
      why: "רק עכשיו, אחרי רבע שעה, מתחיל הציור. ההחלטה הראשונה מוסברת עם ה-trade-off שלה: צפיות ויכולת בדיקה, על חשבון גמישות שלא צריך כאן." },
    { p: 2, t: 21, note: "hybrid retrieval על בסיס הידע ועל פניות שנפתרו, rerank, טיוטה עם ציטוטים שנבדקים בקוד. הסלמה לפי כללים בקוד. ממשק לנציג.",
      say: "Escalation is a rule in code on the extracted fields, never the model's decision.",
      why: "הגבול בין מודל, קוד ואדם מסומן במפורש. זה הדבר הראשון שמראיין בודק בציור, כי הוא מראה שהמועמד מבין מה מודל לא אמור להחליט." },
    { p: 3, t: 25, note: "golden set: 600 פניות היסטוריות, התור הסופי מהיסטוריית ההעברות. בסיס הידע: chunking לפי כותרות, סימון מאמרים ישנים.",
      say: "The historical labels are noisy, so I take the final queue from the transfer history.",
      why: "המועמד משתמש בנתון שהמראיין נתן (תוויות לא מדויקות) ומראה שהוא יודע מה לעשות איתו. golden set לא נופל מהשמיים." },
    { p: 4, t: 30, note: "offline: דיוק לכל תור, recall@5, faithfulness עם שופט מכויל. online: כל תיקון של נציג הוא תווית.",
      say: "Every agent correction is a free label, and it goes back into the golden set weekly.",
      why: "eval לכל שכבה בנפרד, ושופט שלא סומכים עליו לפני כיול. וההבנה ש-online הוא לא רק ניטור, אלא מקור לנתונים." },
    { p: 5, t: 35, note: "אין מקור: אין טיוטה. injection בפנייה: הכללים בקוד. הספק נופל: fallback, ואז תור ידני. אף פנייה לא נתקעת.",
      say: "No ticket ever gets stuck: worst case, it goes to manual triage like today.",
      why: "לכל כשל, מה המערכת עושה, לא רק שהוא קיים. \"אף פנייה לא נתקעת\" הוא משפט שמראיינים זוכרים." },
    { p: 6, t: 39, note: "18,000 בחודש × כ-0.0008$ = כ-15$ מתוך תקציב של 500$. התראה ל-P1 מיד אחרי הסיווג.",
      say: "Back of the envelope: about fifteen dollars a month on Haiku, so there's room for a bigger model on drafts.",
      why: "חישוב של דקה, בקול, שמוביל להחלטה: יש מרווח, ולכן אם הטיוטות חלשות אפשר לשלם על מודל חזק יותר רק בשלב הזה." },
    { p: 7, t: 42, note: "מיסוך PII בפניות שכר. retrieval מסונן לפי תור. המערכת רק קוראת ומציעה. audit log.",
      say: "The system can read and suggest; it cannot close tickets or change permissions.",
      why: "אבטחה בכותרות, אבל קונקרטיות: least privilege ומיסוך, לא \"נשמור על אבטחה\"." },
    { p: 8, t: 45, note: "shadow mode לשבועיים, assist לפי תור (מתחילים מהזולים), ניתוב אוטומטי רק איפה שהדיוק מעל 95% לאורך חודש.",
      say: "v1 is shadow mode: we measure on real traffic with zero risk.",
      why: "הלוח מלא, וכל תשעת השלבים מכוסים בזמן. שים לב ששום פתק לא מתאר טכנולוגיה בלי סיבה." },
  ];
  const WEAK = [
    { p: 2, t: 1, bad: 1, note: "LangChain agent + Pinecone + GPT",
      say: "OK, so I'd use a LangChain agent with Pinecone and GPT.",
      why: "קפיצה לרכיבים בדקה הראשונה. המועמד לא יודע מי המשתמש, מה הנפח, או מה מחיר הטעות, ולכן אין לו דרך להצדיק אף אחד מהשמות האלה." },
    { p: 2, t: 10, bad: 1, note: "הסוכן מחליט על התור ועונה לעובד",
      say: "The agent reads the ticket, decides the queue, and answers the employee.",
      why: "בלי לשאול, המועמד בנה בדיוק את מה שההנהלה לא מוכנה לו: מערכת שסוגרת פניות לבד. וגם ההסלמה היא החלטה של המודל." },
    { p: 2, t: 20, bad: 1, note: "chunks של 512 טוקנים, embeddings",
      say: "We chunk everything into 512 tokens and embed it.",
      why: "ברירת מחדל בלי נימוק. מראיין ישאל \"למה 512?\" ו\"מה עם קודי שגיאה ומספרי סעיפים?\", ואין תשובה." },
    { p: 2, t: 35, bad: 1, note: "בפרומפט: \"היה זהיר עם פניות security\"",
      say: "And in the prompt we tell it to be careful with security tickets.",
      why: "מדיניות בפרומפט. פנייה עם injection, או סתם פנייה שנוסחה אחרת, תעבור. כבר 35 דקות על ארכיטקטורה בלבד." },
    { p: 4, t: 43, bad: 1, note: "\"ננסה על כמה פניות לפני שעולים\"",
      say: "We'll try it on a few tickets before launch.",
      why: "מדידה בעיניים. אין golden set, אין מדד, ואין דרך לדעת אם שינוי פרומפט שיפר או קלקל." },
    { p: 6, t: 45, bad: 1, note: "המראיין: \"כמה זה יעלה? ומה אם הספק נופל?\" אין תשובה.",
      say: "Hmm... I guess we'd need to check the pricing.",
      why: "הזמן נגמר. על הלוח יש רק ארכיטקטורה, ושבעה שלבים חסרים לגמרי. הפתקים המקווקווים מראים מה מראיין היה מצפה לראות." },
  ];
  host.innerHTML = `<div class="sim">
    <div class="guide"><p><b>מה רואים:</b> הלוח של מועמד בסבב system design, שמתמלא לפי הזמן. הפס הצבעוני הוא תשעת שלבי המסגרת, השעון מראה דקות מתוך 45, וכל פתק מסומן בשלב שממנו הגיע. בתיבה הכתומה: מה המועמד אומר בקול, ולמה זה חשוב למראיין.</p></div>
    <div class="row"><div class="seg" role="group" aria-label="מועמד"><button data-m="strong" aria-pressed="true">מועמד חזק</button><button data-m="weak" aria-pressed="false">מועמד חלש</button></div></div>
    <div class="l28-phases" id="b-ph"></div>
    <div class="l28-clock"><span>דקה</span><b id="b-min">0</b><span>מתוך 45</span><span class="spacer"></span><span class="muted" id="b-phn"></span></div>
    <div class="l28-strip" id="b-strip"></div>
    <div class="l28-board" id="b-board" aria-live="polite"></div>
    <div class="l28-say"><q id="b-say" dir="ltr"></q><div id="b-why"></div></div>
    <div class="row"><button class="btn small primary" id="b-play">השהה</button><button class="btn small" id="b-prev" aria-label="צעד קודם">→</button><button class="btn small" id="b-next" aria-label="צעד הבא">←</button><span class="spacer"></span><span class="counter" id="b-c"></span></div></div>`;
  const g = (id) => host.querySelector("#" + id);
  let mode = "strong", i = 0, timer = null;
  let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const steps = () => (mode === "strong" ? STRONG : WEAK);
  const total = BUDGET.reduce((a, b) => a + b, 0);
  g("b-strip").innerHTML = BUDGET.map((b, k) => `<i data-k="${k}" style="width:${(100 * b) / total}%" title="${esc(PH[k])}: ${b}"></i>`).join("") + `<span class="mk" id="b-mk"></span>`;
  function draw() {
    const S = steps(), s = S[i], last = i === S.length - 1;
    const seen = new Set(S.slice(0, i + 1).map((x) => x.p));
    g("b-ph").innerHTML = PH.map((n, k) => {
      let c = "";
      if (k === s.p) c = "on";
      else if (seen.has(k) && (mode === "strong" ? k < s.p : true)) c = "done";
      else if (mode === "weak" && last && !seen.has(k)) c = "miss";
      return `<span class="${c}">${k + 1}. ${esc(n)}</span>`;
    }).join("");
    g("b-min").textContent = s.t;
    g("b-phn").textContent = `שלב: ${PH[s.p]}`;
    host.querySelectorAll("#b-strip i").forEach((el) => {
      const k = +el.dataset.k;
      el.className = mode === "strong" ? (k < s.p ? "done" : k === s.p ? "on" : "") : (k === 2 ? "on" : "");
    });
    g("b-mk").style.left = `calc(${(100 * s.t) / 45}% - 1px)`;
    const board = g("b-board");
    board.innerHTML = "";
    S.slice(0, i + 1).forEach((x, k) => {
      const n = h(`<div class="l28-note c${x.p}${x.bad ? " bad" : ""}${k === i ? " new" : ""}"><span class="ph">${x.p + 1}. ${esc(PH[x.p])} · דקה ${x.t}</span></div>`);
      n.append(document.createTextNode(x.note));
      board.append(n);
    });
    if (mode === "weak" && last) {
      PH.forEach((n, k) => {
        if (!seen.has(k)) board.append(h(`<div class="l28-note gap"><span class="ph">${k + 1}. ${esc(n)}</span>חסר על הלוח</div>`));
      });
    }
    g("b-say").textContent = s.say;
    g("b-why").textContent = s.why;
    g("b-c").textContent = `צעד ${i + 1}/${S.length}`;
  }
  const step = (d) => { const S = steps(); i = (i + d + S.length) % S.length; draw(); };
  const tick = () => { clearTimeout(timer); if (playing) timer = setTimeout(() => { step(1); tick(); }, i === steps().length - 1 ? 7000 : 5200); };
  const setP = (p) => { playing = p; g("b-play").textContent = p ? "השהה" : "נגן"; tick(); };
  host.querySelectorAll("[data-m]").forEach((b) => b.addEventListener("click", () => {
    mode = b.dataset.m; i = 0;
    host.querySelectorAll("[data-m]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    draw(); tick();
  }));
  g("b-play").addEventListener("click", () => setP(!playing));
  g("b-next").addEventListener("click", () => { setP(false); step(1); });
  g("b-prev").addEventListener("click", () => { setP(false); step(-1); });
  draw(); setP(playing);
  return () => clearTimeout(timer);
};

/* ---------------- flashcards with SM-2 ---------------- */
window.AIDS["l28cards"] = function (host) {
  const CATS = { fundamentals: "יסודות", structured: "Structured outputs", rag: "RAG", embeddings: "Embeddings", agents: "סוכנים", evals: "Evals", observability: "Observability", security: "אבטחה", cost_latency: "עלות ו-latency", adaptation: "Fine-tuning מול RAG", system_design: "System design", behavioral: "התנהגותי" };
  const CARDS = [
    ["fund-01", "fundamentals", "מה זה טוקן, ולמה זה חשוב למהנדס שבונה מוצר?", ["יחידה של ה-<b>tokenizer</b>, לרוב חלק ממילה", "<b>עלות</b>: משלמים לפי טוקנים, ה-output יקר בערך פי 5", "<b>חלון ההקשר</b> ו-max_tokens נמדדים בטוקנים", "<b>latency</b> גדל עם טוקני הפלט", "<b>עברית</b>: בערך פי 2 עד 3 טוקנים לאותו תוכן"]],
    ["fund-02", "fundamentals", "מה עושה temperature, ומתי משנים אותו?", ["מחלק את ה-<b>logits</b> לפני ה-softmax: נמוך מחדד, גבוה משטיח", "נמוך ל<b>חילוץ, סיווג וקוד</b>", "<b>temperature 0 לא מבטיח דטרמיניזם</b> (batching, floating point)", "עקביות נבדקת ב-eval עם כמה הרצות"]],
    ["struct-01", "structured", "איך מבטיחים JSON שהקוד יכול לסמוך עליו?", ["ארבע רמות: פרומפט, <b>JSON mode</b>, <b>structured outputs</b>, ולידציה בקוד", "<b>constrained decoding</b> חוסם טוקנים שהיו שוברים את הסכמה", "<b>Pydantic</b> תמיד, כי לא כל מילת מפתח נאכפת", "<b>repair</b> מוגבל עם שגיאות מדויקות; לא מתקנים סירוב ו-max_tokens", "<b>תקינות היא לא דיוק</b>"]],
    ["struct-03", "structured", "שדה חובה tool, וההודעה לא מזכירה כלי. מה קורה במצב native?", ["המודל <b>ימציא</b> ערך, כי המסכה מחייבת מחרוזת", "שדות שעלולים לחסור: <b>nullable</b>, והוראה להחזיר null", "<b>נימוק לפני החלטה</b> בסדר השדות", "<b>enum</b> לכל ערך שקוד בודק", "למדוד <b>הזיות</b> בשדות שהתשובה בהם null"]],
    ["rag-02", "rag", "איך בוחרים אסטרטגיית chunking?", ["<b>trade-off</b>: קטן מדויק ומאבד הקשר, גדול שומר הקשר ומדלל", "<b>structure-aware</b>: לפי כותרות וסעיפים, עם הכותרות כהקשר", "<b>overlap</b> או parent-child", "מחליטים לפי <b>recall@5 על golden set</b>, לא לפי מאמר"]],
    ["rag-05", "rag", "ה-RAG עונה לא נכון. איך מאבחנים?", ["לפרק לשכבות: <b>כיסוי, retrieval, הקשר, generation</b>", "לאסוף 30 עד 50 מקרים אמיתיים מה-<b>traces</b>", "<b>error analysis</b>: לסווג, לספור, לתקן את הגדול ראשון", "<b>recall@k</b> ל-retrieval, <b>faithfulness</b> לתשובה", "להוסיף את המקרים ל-<b>golden set</b>"]],
    ["emb-03", "embeddings", "מה זה HNSW, ולמה לא brute force?", ["brute force הוא <b>O(n)</b> לשאילתה", "<b>ANN</b>: גרף בשכבות, חיפוש קרוב ללוגריתמי", "<b>trade-off</b>: recall מעט נמוך מ-100%, וזיכרון", "<b>ef_search</b> מכוונן מול recall שנמדד מול brute force"]],
    ["emb-04", "embeddings", "איך מטפלים בהרשאות בחיפוש וקטורי?", ["לאכוף <b>לפני</b> שהטקסט מגיע למודל", "<b>metadata filtering</b> בתוך השאילתה (pre-filter)", "post-filter משאיר מעט תוצאות", "הזהות מגיעה מה-<b>שרת המאומת</b>, לא מהמודל", "<b>eval של דליפות</b>"]],
    ["agent-01", "agents", "workflow או agent: מתי כל אחד?", ["<b>workflow</b>: הקוד קובע סדר; <b>agent</b>: המודל מחליט בלולאה", "workflow <b>צפוי, זול וקל לבדיקה</b>: ברירת המחדל", "agent כשהצעדים <b>באמת לא ידועים</b>", "להוסיף אוטונומיה רק כשהיא <b>משפרת תוצאה מדידה</b>"]],
    ["agent-02", "agents", "לולאת הסוכן ותנאי העצירה שלה", ["<b>tool_use</b>, הרצה, <b>tool_result</b>, וחוזר", "<b>מספר צעדים מקסימלי</b> ו<b>תקציב</b>", "<b>timeout</b> ו<b>זיהוי לולאה</b>", "שגיאת כלי חוזרת למודל עם <b>is_error</b>", "כל צעד ב-<b>trace</b>"]],
    ["eval-01", "evals", "איך בונים eval לפיצ'ר חדש מאפס?", ["מתחילים מ-<b>error analysis</b> על 50 עד 100 פלטים אמיתיים", "<b>open coding</b> ואז קיבוץ וספירה", "מה שאפשר, <b>בקוד</b>; שיפוט עם <b>LLM-as-judge בינארי</b>", "<b>golden set</b> שרץ בכל שינוי, כמו רגרסיה"]],
    ["eval-02", "evals", "איך יודעים שאפשר לסמוך על LLM-as-judge?", ["הטיות: <b>אורך</b>, <b>מיקום</b>, self-preference", "<b>כיול מול תיוג אנושי</b> על כמה עשרות דוגמאות", "<b>TPR ו-TNR</b>, לא רק accuracy", "שאלה <b>בינארית</b>, <b>ציטוט</b> כראיה, החלפת סדר", "<b>סט נפרד</b> ודגימה בפרודקשן"]],
    ["obs-01", "observability", "מה רושמים בכל קריאה למודל?", ["<b>trace id</b> ו-<b>spans</b> לכל צעד", "<b>גרסת מודל ופרומפט</b>", "<b>טוקנים</b> (כולל cached), <b>עלות</b>, <b>latency ו-TTFT</b>, stop_reason", "תוכן, עם <b>PII</b> ו-<b>retention</b>", "<b>dashboards ו-alerts</b>"]],
    ["obs-02", "observability", "ה-latency קפץ מ-2 ל-8 שניות. איך חוקרים?", ["במספרים: <b>p50 או p95</b>, פילוח, ממתי", "לפרק ל-<b>spans</b>", "חשודים: <b>TTFT</b>, יותר <b>טוקני פלט</b>, <b>retries</b> (429), יותר צעדים", "<b>cache hit rate</b> שירד, deploy אחרון", "<b>alert</b> על p95 אחרי התיקון"]],
    ["sec-01", "security", "prompt injection: direct מול indirect", ["<b>direct</b>: המשתמש כותב את ההוראה", "<b>indirect</b>: מגיעה ממסמך, מייל או תוצאת כלי", "<b>אין הפרדה</b> בין הוראות לנתונים, אז אין פתרון בפרומפט", "הגנה ארכיטקטונית: <b>least privilege</b>, <b>אכיפה בקוד</b>, אישור אנושי"]],
    ["sec-02", "security", "סוכן קורא מיילים וגם שולח. מה הסיכון?", ["השילוב: <b>נתונים פרטיים</b>, <b>תוכן לא אמין</b>, <b>יציאה החוצה</b>", "מייל זדוני יכול להורות לשלוח מידע", "לשבור רכיב: <b>אישור אנושי</b>, <b>allowlist</b>, או הפרדה", "<b>red team eval</b>"]],
    ["cost-01", "cost_latency", "איך מעריכים עלות חודשית לפני שבונים?", ["<b>בקשות ביום × טוקנים לבקשה</b>", "מחיר נפרד ל-<b>input</b> ול-<b>output</b>", "קריאות נוספות: <b>repair, שופט, embeddings, צעדי סוכן</b>", "לאמת ב-<b>usage</b> אמיתי", "מנופים: <b>caching</b>, מודל קטן, <b>batch</b>"]],
    ["cost-02", "cost_latency", "prompt caching: איך מתכננים פרומפט בשבילו?", ["נשמר ה-<b>prefix</b>; טוקנים זולים ו-TTFT נמוך", "<b>קבוע ראשון, משתנה אחרון</b>", "טעות: <b>timestamp</b> בתחילת ה-system", "למדוד <b>cache hit rate</b>"]],
    ["adapt-01", "adaptation", "prompting, RAG או fine-tuning?", ["חסרות הוראות: <b>prompting</b>", "חסר ידע (משתנה, פרטי): <b>RAG או tools</b>", "<b>fine-tuning לא מלמד עובדות</b> בצורה אמינה", "fine-tuning: <b>התנהגות, סגנון</b>, מודל קטן למשימה צרה", "מהזול ליקר, <b>לפי eval</b>"]],
    ["adapt-02", "adaptation", "\"נעשה fine-tuning כדי שהמודל יכיר את המוצרים\"", ["לשאול <b>מה הבעיה</b>, לא הפתרון", "fine-tuning: <b>הזיות</b>, אין <b>ציטוט</b>, אימון מחדש לכל שינוי", "<b>RAG או tool</b> מהקטלוג", "ניסוי עם <b>golden set</b> ו-<b>baseline</b>"]],
    ["sd-07", "system_design", "45 דקות לתכנן מערכת LLM: איך מחלקים?", ["<b>דרישות והנחות</b> (5 עד 7), <b>מדדים</b> (3)", "<b>ארכיטקטורה</b> (10 עד 12): מודל, קוד, אדם", "<b>נתונים, eval, כשלים</b> (5 כל אחד)", "<b>עלות ו-latency</b> במספרים, <b>אבטחה, איטרציה</b>", "לבדוק עם המראיין לאן להעמיק"]],
    ["sd-06", "system_design", "איך שורדים נפילה של ספק ה-LLM?", ["להגדיר <b>משמעות עסקית</b>", "<b>retries</b> עם backoff ו-<b>timeout</b>", "<b>fallback</b> לספק שני שנבדק מראש ב-<b>eval</b>", "<b>circuit breaker</b>", "<b>degradation</b> חינני, queue, ובדיקת chaos"]],
    ["beh-01", "behavioral", "ספר על מערכת AI שהתנהגה בצורה לא צפויה", ["מבנה <b>STAR</b>, בגוף ראשון", "<b>כשל ספציפי</b> (למשל 400 על pattern בסכמה)", "<b>בידוד ומדידה</b> במקום ניחוש", "<b>תוצאה עם מספר</b>", "<b>למה זה קרה</b> ומה למדת"]],
    ["beh-03", "behavioral", "להסביר למנהל מוצר למה הפיצ'ר \"לפעמים טועה\"", ["להתחיל מ<b>סיכון ומשתמש</b>, לא ממנגנון", "\"המערכת <b>מנבאת</b>, יש לה <b>שיעור טעות</b>\"", "<b>מספרים מה-eval</b> ואיפה הטעויות", "מה עשינו: <b>אישור אנושי</b>, הסלמה", "<b>החלטה עם trade-off</b> בשבילו"]],
  ].map(([id, cat, q, keys]) => ({ id, cat, q, keys }));
  const KEY = "l28cards-v1";
  const today = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  let states = {};
  try { states = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { states = {}; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(states)); } catch (e) { /* storage blocked: progress lives only in this page view */ } };
  function sm2(s, q) {
    s = Object.assign({ ef: 2.5, reps: 0, interval: 0, lapses: 0 }, s || {});
    if (q >= 3) { s.interval = s.reps === 0 ? 1 : s.reps === 1 ? 6 : Math.round(s.interval * s.ef); s.reps += 1; }
    else { s.reps = 0; s.interval = 1; s.lapses += 1; }
    s.ef = Math.max(1.3, +(s.ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))).toFixed(4));
    const d = today(); d.setDate(d.getDate() + s.interval);
    s.due = iso(d);
    return s;
  }
  host.innerHTML = `<div class="sim">
    <div class="guide"><p><b>מה זה:</b> כרטיסיות לחזרה מרווחת, באותו אלגוריתם שתממש בתרגיל 3 (SM-2). <b>איך עובדים:</b> קרא את השאלה, ענה <b>בקול</b> כאילו אתה בראיון, ורק אז לחץ "הפוך". מאחורי הכרטיס יש נקודות המפתח שתשובה טובה חייבת לכסות (לא תשובה לשינון). דרג את עצמך: <b>0 עד 2</b> אם פספסת את רוב הנקודות, <b>3</b> אם ענית נכון במאמץ, <b>4</b> אם ענית טוב, <b>5</b> אם כיסית הכל בקלות. הדירוג קובע מתי הכרטיס יחזור.</p><p><b>המספרים:</b> "בתור להיום" הם כרטיסים שהגיע זמנם. ease הוא מקדם הקלות (מתחיל ב-2.5): ככל שהוא נמוך, הכרטיס קשה לך והמרווחים גדלים לאט. ההתקדמות נשמרת רק בדפדפן הזה.</p></div>
    <div class="form2"><label>קטגוריה<select id="c-cat" style="font-family:inherit"><option value="">כל הקטגוריות</option>${Object.entries(CATS).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></label></div>
    <div class="stats" id="c-stats"></div>
    <div class="l28-card" id="c-card"></div>
    <div class="row"><button class="btn small" id="c-free">תרגול חופשי (כרטיס אקראי)</button><span class="spacer"></span><button class="btn small" id="c-reset">איפוס ההתקדמות</button></div>
    <details class="cd-what"><summary>איך זה מחושב</summary><div id="c-how" style="margin-top:8px;line-height:1.7;font-size:.9rem"></div></details></div>`;
  const g = (id) => host.querySelector("#" + id);
  let cur = null, flipped = false, free = false, msg = "";
  const pool = () => CARDS.filter((c) => !g("c-cat").value || c.cat === g("c-cat").value);
  function queue() {
    const t = iso(today());
    const due = pool().filter((c) => states[c.id] && states[c.id].due <= t)
      .sort((a, b) => (states[a.id].due < states[b.id].due ? -1 : states[a.id].due > states[b.id].due ? 1 : states[a.id].ef - states[b.id].ef));
    const fresh = pool().filter((c) => !states[c.id]);
    return { due, fresh };
  }
  function pick() {
    const { due, fresh } = queue();
    flipped = false;
    if (free) { const p = pool(); cur = p[Math.floor(Math.random() * p.length)]; return; }
    cur = due[0] || fresh[0] || null;
  }
  function draw() {
    const { due, fresh } = queue();
    const learned = pool().filter((c) => states[c.id]).length;
    g("c-stats").innerHTML = `<span>בתור להיום: <b>${due.length}</b></span><span>חדשים: <b>${fresh.length}</b></span><span>נלמדו: <b>${learned}/${pool().length}</b></span>`;
    const box = g("c-card");
    if (!cur) {
      box.innerHTML = `<div class="eyebrow">Done</div><h4>אין כרטיסים לתרגול היום בקטגוריה הזו.</h4><p class="muted" style="margin:0">${msg ? esc(msg) + " " : ""}חזור מחר, או לחץ "תרגול חופשי" כדי לחזור על כרטיס אקראי.</p>`;
      g("c-how").innerHTML = howText(null);
      return;
    }
    const s = states[cur.id];
    box.innerHTML = `<div class="row"><span class="eyebrow">${esc(CATS[cur.cat])} · ${esc(cur.id)}</span><span class="spacer"></span><span class="counter">${s ? `ease ${s.ef.toFixed(2)} · מרווח ${s.interval} ימים` : "כרטיס חדש"}</span></div>
      <h4></h4>
      ${msg ? `<div class="muted" style="font-size:.86rem">${esc(msg)}</div>` : ""}
      ${flipped ? `<ul class="l28-keys">${cur.keys.map((k) => `<li>${k}</li>`).join("")}</ul>
        <div class="l28-grades">${[["0", "לא זכרתי", "lo"], ["1", "כמעט כלום", "lo"], ["2", "חלקי", "lo"], ["3", "נכון, במאמץ", ""], ["4", "טוב", "hi"], ["5", "מושלם", "hi"]].map(([v, l, c]) => `<button data-g="${v}" class="${c}"><b>${v}</b>${l}</button>`).join("")}</div>`
        : `<div><button class="btn primary" id="c-flip">ענית בקול? הפוך</button></div>`}`;
    box.querySelector("h4").textContent = cur.q;
    const f = box.querySelector("#c-flip");
    if (f) f.addEventListener("click", () => { flipped = true; msg = ""; draw(); });
    box.querySelectorAll("[data-g]").forEach((b) => b.addEventListener("click", () => {
      const q = +b.dataset.g, before = states[cur.id];
      const after = sm2(before, q);
      states[cur.id] = after; save();
      msg = `${cur.id}: ציון ${q} → יחזור בעוד ${after.interval} ${after.interval === 1 ? "יום" : "ימים"} (${after.due}), ease ${after.ef.toFixed(2)}${q < 3 ? ", ונחשב כשכחה" : ""}.`;
      g("c-how").innerHTML = howText(before, q, after);
      pick(); draw();
    }));
    if (!msg) g("c-how").innerHTML = howText(s);
  }
  function howText(before, q, after) {
    const base = `<p style="margin:0 0 6px">כל כרטיס שומר <b>ease</b> (מתחיל ב-2.5), <b>reps</b> (כמה הצלחות ברצף) ו<b>מרווח</b> בימים. בציון 3 ומעלה: המרווח הוא 1 יום בהצלחה הראשונה, 6 בשנייה, ומאז <b>המרווח הקודם × ease</b>. בציון מתחת ל-3: חוזרים להתחלה, מרווח של יום. אחרי כל דירוג: ease += 0.1 − (5 − ציון) × (0.08 + (5 − ציון) × 0.02), ולא פחות מ-1.3. כלומר 5 מוסיף 0.1, 4 לא משנה, 3 מוריד 0.14, ו-0 מוריד 0.8.</p>`;
    if (before === undefined || q === undefined) return base;
    const b = Object.assign({ ef: 2.5, reps: 0, interval: 0 }, before || {});
    const iv = q < 3 ? "ציון מתחת ל-3, אז המרווח חוזר ל-1" : b.reps === 0 ? "הצלחה ראשונה, מרווח 1" : b.reps === 1 ? "הצלחה שנייה, מרווח 6" : `round(${b.interval} × ${b.ef.toFixed(2)}) = ${after.interval}`;
    return base + `<p style="margin:0" dir="rtl"><b>הדירוג האחרון:</b> לפני: ease ${b.ef.toFixed(2)}, reps ${b.reps}, מרווח ${b.interval}. ציון ${q}: ${iv}. ease חדש: ${after.ef.toFixed(2)}.</p>`;
  }
  g("c-cat").addEventListener("change", () => { free = false; msg = ""; pick(); draw(); });
  g("c-free").addEventListener("click", () => { free = true; msg = ""; pick(); draw(); });
  g("c-reset").addEventListener("click", () => { states = {}; save(); free = false; msg = "ההתקדמות אופסה."; pick(); draw(); });
  pick(); draw();
};

/* ---------------- red flag or green flag ---------------- */
window.AIDS["l28flags"] = function (host) {
  const ITEMS = [
    { q: "איך היית יודע שמערכת ה-RAG שלך עובדת?", a: "בדקתי אותה על הרבה שאלות, והתשובות נראו טובות מאוד. גם המשתמשים מרוצים.", red: true,
      why: "מדידה \"בעיניים\". אין golden set, אין מדד, ואין דרך לדעת אם שינוי שיפר או קלקל. גרסה ירוקה: \"40 שאלות עם המקור הנכון מסומן, recall@5 של 0.81 ו-faithfulness של 92% לפי שופט שכיילתי\"." },
    { q: "איך היית יודע שמערכת ה-RAG שלך עובדת?", a: "מדדתי בנפרד את ה-retrieval ואת התשובה: recall@5 על 40 שאלות עם המקור המסומן, ו-faithfulness עם שופט שכיילתי מול 30 תיוגים שלי. ה-recall היה 0.62, ואחרי hybrid search עלה ל-0.81.", red: false,
      why: "מדידה לכל שכבה, גודל הסט, כיול של השופט, ומספר לפני ואחרי. כל משפט כאן מזמין שאלת המשך שהמועמד יודע לענות עליה." },
    { q: "איך היית מונע מהסוכן לאשר בקשת גישה של admin?", a: "הייתי כותב ב-system prompt בצורה מאוד ברורה, עם דוגמאות, שאסור לאשר admin, ומשתמש במודל החזק ביותר כדי שיבין את זה.", red: true,
      why: "מדיניות בפרומפט. נשמע זהיר ומקצועי, אבל injection או ניסוח אחר יעקפו את זה. מדיניות נאכפת בקוד דטרמיניסטי על השדות שחולצו, והמודל רק מציע." },
    { q: "למה בחרת ב-workflow ולא ב-agent?", a: "הסדר של השלבים היה ידוע מראש, והסיכון גבוה, אז רציתי לבדוק כל שלב בנפרד ולהבטיח שער אישור. שילמתי בגמישות: בקשה חריגה עוברת לאדם. אם היו הרבה בקשות שלא מתאימות לזרימה, הייתי שוקל צעד של סוכן בתוכה.", red: false,
      why: "חלופות, קריטריון, בחירה, מחיר, ותנאי לשינוי: כל חמשת החלקים של הסבר trade-off." },
    { q: "ה-latency של הפיצ'ר קפץ. מה תעשה?", a: "כנראה הספק איטי היום. הייתי עובר למודל מהיר יותר, למשל ה-mini.", red: true,
      why: "פתרון לפני אבחון. גרסה ירוקה: להגדיר במספרים (p50 או p95, ממתי), לפרק ל-spans ב-traces, ולבדוק TTFT, טוקני פלט, retries ו-cache hit rate." },
    { q: "איזה vector DB היית בוחר?", a: "pgvector, כי כבר יש לנו Postgres, הנפח הוא כמה מאות אלפי chunks, ואני רוצה לסנן הרשאות ב-JOIN. אם נגיע לעשרות מיליונים או לעומס גבוה, אשקול שירות מנוהל.", red: false,
      why: "בחירה עם נימוק שקשור לדרישות, ותנאי מפורש לשינוי. לא \"Pinecone כי כולם משתמשים\"." },
    { q: "אפשר לסמוך על LLM-as-judge?", a: "כן, המודלים היום מאוד חכמים, ו-GPT או Claude שופטים טוב יותר מבני אדם. אני נותן ציון 1 עד 10 ולוקח ממוצע.", red: true,
      why: "שופט בלי כיול, וסולם לא מוגדר. לשופטים יש הטיות ידועות (אורך, מיקום). כיול מול תיוג אנושי ושאלה בינארית לכל קריטריון." },
    { q: "ספר על כשל של מערכת שבנית.", a: "המודל פשוט החליט לעשות משהו אחר ממה שביקשנו. אחרי כמה ניסיונות של שינוי הפרומפט זה הסתדר.", red: true,
      why: "\"המודל החליט\", בלי trace, בלי סיבה ובלי בדיקה שהתיקון מחזיק. מראיין שומע: אין תצפית ואין eval." },
    { q: "הלקוח רוצה fine-tuning על מסמכי החברה. מה תגיד?", a: "הייתי שואל מה הבעיה בפועל. אם צריך תשובות נכונות על פרטים שמשתנים, fine-tuning לא מלמד עובדות בצורה אמינה ואין ממנו ציטוט, אז הייתי מציע RAG, ומריץ golden set של 50 שאלות על שתי הגישות לפני שמחליטים.", red: false,
      why: "שואל על הבעיה לפני הפתרון, מסביר את המגבלה של fine-tuning, ומציע ניסוי מדיד." },
    { q: "כמה המערכת שתכננת תעלה?", a: "זה תלוי בהרבה דברים: בנפח, במודל, באורך הפרומפטים. קשה להגיד בלי לבנות.", red: true,
      why: "\"זה תלוי\" בלי המשך. נשמע זהיר, אבל זו הימנעות. גרסה ירוקה: חישוב גס בקול עם ההנחות (נפח × טוקנים × מחיר), ואז \"ואם הנפח פי 10, הייתי שוקל caching ו-batch\"." },
    { q: "תאר את צינור ה-RAG שלך.", a: "ingestion עם chunking לפי סעיפים ו-metadata של הרשאות, hybrid search עם RRF, reranker על top-50, ותשובה עם ציטוטים שנבדקים בקוד. לכל שלב יש לי מדד: recall@k ל-retrieval ו-faithfulness לתשובה.", red: false,
      why: "תיאור קצר, עם החלטות (לפי סעיפים, RRF, top-50), הרשאות, בדיקה בקוד, ומדד לכל שכבה." },
    { q: "כמה שיפרת את המערכת?", a: "שיפרתי את הדיוק ב-40%, וה-latency ירד פי שלושה.", red: true,
      why: "מספרים שנשמעים מרשימים, בלי בסיס: 40% ממה? על כמה דוגמאות? איך נמדד? השאלה הבאה של המראיין תהיה \"איך מדדת?\", ובלי תשובה המספרים פוגעים יותר מאשר עוזרים." },
  ];
  host.innerHTML = `<div class="sim">
    <div class="guide"><p><b>איך משחקים:</b> לכל כרטיס יש שאלה של מראיין (באפור) ותשובה של מועמד (בתיבה). החלט אם מראיין מנוסה היה רושם את התשובה כ<b>סימן אדום</b> (חוסר ניסיון אמיתי) או כ<b>סימן ירוק</b> (מישהו שבנה ומדד), ואז קרא את ההסבר. חלק מהשאלות מופיעות פעמיים, עם תשובה חלשה ותשובה חזקה, כדי שתוכל להשוות.</p></div>
    <div class="stats" id="f-score"></div>
    <div class="stack" id="f-list" style="display:grid;gap:10px"></div></div>`;
  const list = host.querySelector("#f-list");
  const ans = {};
  ITEMS.forEach((it, k) => {
    const el = h(`<div class="l28-flag"><div class="qq"></div><blockquote></blockquote>
      <div class="seg" role="group" aria-label="סימן"><button class="red" data-v="1">סימן אדום</button><button class="green" data-v="0">סימן ירוק</button></div>
      <div class="why" hidden></div></div>`);
    el.querySelector(".qq").textContent = `${k + 1}. המראיין: ${it.q}`;
    el.querySelector("blockquote").textContent = it.a;
    el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      const v = b.dataset.v === "1";
      ans[k] = v === it.red;
      el.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      el.classList.toggle("right", ans[k]); el.classList.toggle("wrong", !ans[k]);
      const w = el.querySelector(".why"); w.hidden = false;
      w.innerHTML = `<b>${ans[k] ? "נכון." : "לא בדיוק."} ${it.red ? "סימן אדום." : "סימן ירוק."}</b> `;
      w.append(document.createTextNode(it.why));
      score();
    }));
    list.append(el);
  });
  function score() {
    const n = Object.keys(ans).length, ok = Object.values(ans).filter(Boolean).length;
    host.querySelector("#f-score").innerHTML = `<span>נענו: <b>${n}/${ITEMS.length}</b></span><span>נכונים: <b>${ok}</b></span>${n === ITEMS.length ? `<span>${ok >= 11 ? "מצוין: אתה שומע את מה שמראיין שומע." : "כדאי לחזור לשקופית על הסימנים האדומים."}</span>` : ""}`;
  }
  score();
};

/* ---------------- 5-minute pitch coach ---------------- */
window.AIDS["l28pitch"] = function (host) {
  const SECS = [
    { n: "הבעיה והמשתמש", s: 45, tip: "מי המשתמש, מה הכאב, ואיך נראית הצלחה. משפט לכל אחד." },
    { n: "ארכיטקטורה", s: 60, tip: "הזרימה מקצה לקצה, חמישה עד שבעה רכיבים. ציור, לא רשימת ספריות." },
    { n: "החלטה עם trade-off", s: 60, tip: "חלופות, קריטריון, בחירה, מחיר, ומתי היית משנה." },
    { n: "מדידה", s: 60, tip: "golden set (כמה ומאיפה), מדדים, ושלושה מספרים: איכות, latency, עלות." },
    { n: "כשל אמיתי", s: 45, tip: "מה נשבר, איך גילית, מה הייתה הסיבה, מה שינית." },
    { n: "מה הייתי עושה אחרת", s: 30, tip: "משפט או שניים. הצעד הבא, או מה שהיית משנה בדיעבד." },
  ];
  const PROJ = {
    brain: { name: "Company Brain", ex: [
      "עובדי Acme מבזבזים זמן על שאלות שהתשובה עליהן כתובה במסמכים, ובקשות גישה מחכות שעות לניתוב ידני.",
      "ingestion לפי סעיפים, hybrid search עם reranker, תשובה עם ציטוטים; חילוץ בקשות גישה עם structured output, ניתוב בכללים, ושער אישור עם checkpoint.",
      "workflow ולא סוכן חופשי לבקשות גישה: צפיות ושער אישור מובטח, על חשבון גמישות.",
      "golden set של [N] שאלות: recall@5 [X], faithfulness [X]%, p95 [X] שניות, [X] דולר לשאלה.",
      "pattern בסכמה החזיר 400 למרות התיעוד; בודדתי, והעברתי אילוצים לא נתמכים ל-Pydantic.",
      "[למשל: הייתי מתחיל את ה-golden set כבר ביום הראשון.]",
    ] },
    tutor: { name: "המורה לעברית", ex: [
      "תלמידי תיכון מהחברה הבדואית כמעט לא מתרגלים שיחה יומיומית בעברית, ואין מספיק מורים לזמן דיבור אישי.",
      "PWA בממשק בערבית, שיחה קולית (STT, LLM, TTS עם סטרימינג, או speech-to-speech), משוב מובנה לפי רמת CEFR.",
      "[pipeline מול speech-to-speech: שליטה ותמלול לבדיקה, על חשבון latency.]",
      "p95 מסוף דיבור עד תשובה [X] שניות, WER בעברית של דוברי ערבית [X]%, הסכמה עם מורה [X]%.",
      "[התמלול סימן טעות שלא קרתה בגלל מבטא, והמשוב היה שגוי.]",
      "[פרטיות של קטינים כבר מהתכנון הראשון.]",
    ] },
    jobs: { name: "סוכן המשרות", ex: [
      "משרות מתפרסמות בכמה קבוצות WhatsApp ובלוח משרות, עשרות ביום, רובן לא רלוונטיות, ואותה משרה בכמה מקומות.",
      "גשר ל-WhatsApp, dedup, סיווג עם structured output במודל קטן, כללי סינון בקוד, סיכום שלוש פעמים ביום, וטיוטות ב-Gmail.",
      "טיוטות ולא שליחה אוטומטית: מייל שגוי למגייס עולה יותר מדקה של עבודה ידנית.",
      "golden set של [N] הודעות מתויגות: precision [X]%, recall [X]%, כפילויות מ-[X]% ל-[X]%, [X] דולר בחודש.",
      "[הגשר נפל בלילה ואף סיכום לא נשלח; הוספתי healthcheck והתראה.]",
      "[משפט על הצעד הבא.]",
    ] },
  };
  host.innerHTML = `<div class="sim">
    <div class="guide"><p><b>איך משתמשים:</b> בחר פרויקט ולחץ "התחל", ואז הצג אותו <b>בקול</b>, כאילו מראיין יושב מולך. החלק המודגש הוא החלק שאתה אמור להיות בו, עם ההנחיה ודוגמה מהפרויקט (בסוגריים מרובעים: מקום למספר שתמדוד). לחץ "החלק הבא" כשסיימת חלק; הפס מאדים כשאתה חורג מהזמן שלו. בסוף תראה כמה זמן הלך לכל חלק לעומת התקציב. סך הכול: חמש דקות.</p></div>
    <div class="seg" role="group" aria-label="פרויקט">${Object.entries(PROJ).map(([k, p], j) => `<button data-p="${k}" aria-pressed="${j === 0}">${esc(p.name)}</button>`).join("")}</div>
    <div class="l28-timer" id="p-t">0:00 / 5:00</div>
    <div class="row" style="justify-content:center"><button class="btn primary" id="p-go">התחל</button><button class="btn" id="p-next">החלק הבא</button><button class="btn small" id="p-reset">איפוס</button></div>
    <div class="l28-secs" id="p-secs"></div>
    <div class="callout" id="p-sum" hidden></div></div>`;
  const g = (id) => host.querySelector("#" + id);
  let proj = "brain", running = false, cur = 0, used = SECS.map(() => 0), last = 0, iv = null, finished = false;
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  function draw() {
    const total = used.reduce((a, b) => a + b, 0);
    g("p-t").textContent = `${fmt(total)} / 5:00`;
    g("p-t").classList.toggle("over", total > 300);
    g("p-go").textContent = running ? "השהה" : finished ? "שוב" : total ? "המשך" : "התחל";
    g("p-next").disabled = finished;
    const box = g("p-secs");
    box.innerHTML = "";
    SECS.forEach((s, k) => {
      const over = used[k] > s.s;
      const el = h(`<div class="l28-sec${k === cur && !finished ? " on" : ""}${k < cur || finished ? " done" : ""}">
        <div class="top"><b>${k + 1}. ${esc(s.n)}</b><span dir="ltr" class="${over ? "over" : ""}">${fmt(used[k])} / ${fmt(s.s)}</span></div>
        <div class="l28-bar"><i class="${over ? "over" : ""}" style="width:${Math.min(100, (100 * used[k]) / s.s)}%"></i></div></div>`);
      if (k === cur && !finished) {
        const tip = h(`<div class="tip"></div>`); tip.textContent = s.tip; el.append(tip);
        const ex = h(`<div class="ex"></div>`); ex.textContent = "דוגמה: " + PROJ[proj].ex[k]; el.append(ex);
      }
      box.append(el);
    });
    const sum = g("p-sum");
    if (finished) {
      const overs = SECS.map((s, k) => [s, used[k]]).filter(([s, u]) => u > s.s * 1.2).map(([s, u]) => `${s.n} (${fmt(u)} במקום ${fmt(s.s)})`);
      const shorts = SECS.map((s, k) => [s, used[k]]).filter(([s, u]) => u < s.s * 0.5).map(([s]) => s.n);
      sum.hidden = false;
      sum.innerHTML = `<b>סיימת ב-${fmt(total)}.</b> `;
      sum.append(document.createTextNode(
        (overs.length ? `חרגת ב: ${overs.join(", ")}. ` : "לא חרגת משמעותית באף חלק. ") +
        (shorts.length ? `קצר מדי: ${shorts.join(", ")}. אם זה ההחלטה או המדידה, שם המראיין יחפור, אז כדאי להרחיב.` : "") +
        (total > 330 ? " אם צריך לקצץ, קצץ בארכיטקטורה, לא בהחלטה ובמדידה." : "")));
    } else sum.hidden = true;
  }
  function tick() {
    const now = performance.now();
    used[cur] += (now - last) / 1000; last = now;
    draw();
  }
  function setRun(r) {
    running = r;
    clearInterval(iv);
    if (r) { last = performance.now(); iv = setInterval(tick, 250); }
    draw();
  }
  function reset() { setRun(false); cur = 0; used = SECS.map(() => 0); finished = false; draw(); }
  g("p-go").addEventListener("click", () => { if (finished) { reset(); setRun(true); } else setRun(!running); });
  g("p-next").addEventListener("click", () => {
    if (running) tick();
    if (cur < SECS.length - 1) { cur += 1; if (!running) setRun(true); else draw(); }
    else { finished = true; setRun(false); }
  });
  g("p-reset").addEventListener("click", reset);
  host.querySelectorAll("[data-p]").forEach((b) => b.addEventListener("click", () => {
    proj = b.dataset.p;
    host.querySelectorAll("[data-p]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    draw();
  }));
  draw();
  return () => clearInterval(iv);
};
