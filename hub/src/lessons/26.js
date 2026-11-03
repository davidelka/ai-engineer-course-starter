// Lesson 26 — LLM Serving and API Design: FastAPI, streaming, async and backpressure.
window.LESSONS = window.LESSONS || {};
window.LESSONS["26"] = {
  n: 26,
  title: "LLM Serving and API Design",
  he: "FastAPI, סטרימינג, async ו-backpressure",
  hours: "כשעתיים וחצי שיעור, כחמש שעות מעבדה",

  goals: [
    "להבין <b>מה משתנה</b> כשפיצ'ר LLM הופך ל-API: בקשות שנמשכות שניות במקום מילישניות, עלות לכל בקשה, ספק עם מגבלות משלו, והרבה משתמשים במקביל. ולתרגם את זה להחלטות: סדר הבדיקות, מגבלות, timeouts וחוזה שגיאות.",
    "לבנות שירות ב-<b>FastAPI</b> עם סכמות <b>Pydantic</b> לבקשה ולתשובה, ולהבין מה FastAPI עושה איתן: ולידציה, תיעוד OpenAPI, ושגיאת 422 מפורטת.",
    "להבין את <b>ה-event loop</b>: למה קריאה סינכרונית בתוך <code>async def</code> מקפיאה את כל השרת, ומה ההבדל בין שלוש הדרכים לקרוא ל-llmkit: endpoint רגיל, threadpool, ולקוח async אמיתי.",
    "להזרים תשובות ב-<b>Server-Sent Events</b>: פורמט החוט, הכותרות, keep-alive, שגיאה שמגיעה אחרי שה-200 כבר נשלח, ומתי <b>WebSocket</b> מתאים יותר.",
    "להבטיח ש<b>ניתוק של הלקוח עוצר את הזרם למעלה</b>, ספק המודל, ולמדוד את זה. להכיר את הבאג הנפוץ שבו השירות נראה תקין בזמן שהספק ממשיך לייצר ולחייב.",
    "לבנות <b>backpressure</b>: שער מקביליות עם תור חסום, queue timeout, ו-429 עם <code>Retry-After</code>. ולהבין למה תור לא חסום הוא הדרך הכי מהירה להפיל שירות.",
    "להשתמש ב<b>חוק Little</b> כדי לחשב קיבולת לפני בדיקת עומס, ולמצוא בבדיקת עומס עם <b>locust</b> את נקודת הברך: p50, p95 ו-TTFT שנמדדים מצד הלקוח.",
    "להוסיף את מה שהופך שירות למוכן לפרודקשן: <b>rate limit לפי מפתח</b> (token bucket), <b>Idempotency-Key</b>, שגיאות <b>problem+json</b>, request id ולוגים מובנים, <b>health/readiness</b>, וגרסאות של ה-API.",
  ],
  connects: "בשיעור 2 בנית את llmkit, שמדבר עם כל ספק, כולל סטרימינג ו-retries. בשיעור 20 תכננת את חוזה השגיאות ואת ה-idempotency של שירות התשובות. עכשיו השירות הזה עולה לאוויר, כ-<b>Company Brain API v0</b>: אותו llmkit, מאחורי FastAPI, עם כל מה ששירות אמיתי צריך כדי לשרוד משתמשים אמיתיים. הלאה: ב<b>נושא 22</b> ה-request id והלוגים של היום הופכים ל-traces, ב<b>נושא 25</b> ה-rate limit עובר ל-gateway משותף לכמה שירותים, ובנושא <b>27</b> השירות נארז ב-container, ו-<code>/healthz</code> ו-<code>/readyz</code> של היום הם בדיוק מה שהפלטפורמה בענן תבדוק.",

  intro: {
    animation: "l26gate",
    animationTitle: "שער מקביליות ותור: איך שירות אומר \"לא\" בזמן",
    animationGuide: `<p><b>מה רואים כאן:</b> השירות שלנו מבפנים, כשבקשות מגיעות אליו. משמאל נכנסות בקשות, כל אחת היא ריבוע קטן עם מספר. באמצע יש <b>שער</b> עם מספר קבוע של <b>מקומות</b> (slots). כל מקום הוא קריאה אחת למודל שרצה עכשיו, והפס שמתמלא בו מראה כמה מהתשובה כבר נוצר. לפני השער יש <b>תור</b> עם מספר מוגבל של כיסאות. בקשה שיושבת בתור מחכה שמקום יתפנה, והפס שלה מראה כמה מזמן ההמתנה המותר כבר עבר.</p>
<p><b>מה קורה לבקשה חדשה:</b></p>
<ol>
<li>אם יש מקום פנוי בשער ואף אחד לא מחכה, היא <b>נכנסת מיד</b> (ירוק).</li>
<li>אם אין מקום אבל יש כיסא פנוי בתור, היא <b>מחכה</b> (כתום). כשמקום מתפנה, הראשונה בתור נכנסת.</li>
<li>אם התור מלא, היא <b>נדחית מיד</b> עם 429 ו-<code>Retry-After</code> (אדום). זה load shedding: הסירוב לוקח מילישנייה ולא עולה כלום.</li>
<li>אם היא חיכתה בתור יותר מה-queue timeout, היא <b>נדחית אחרי המתנה</b> (אדום מקווקו). זה הסירוב היקר: הלקוח כבר חיכה, ובסוף קיבל לא.</li>
</ol>
<p><b>איך לקרוא את המספרים למטה:</b> "רצות" ו"בתור" הם המצב ברגע זה. "הצליחו", "נדחו מיד" ו"נדחו אחרי המתנה" נספרים מתחילת ההרצה. p50 ו-p95 הם זמני התגובה של הבקשות שהצליחו, כולל ההמתנה בתור. השורה התחתונה מסבירה במילים מה קרה בבקשה האחרונה.</p>
<p><b>איך לעבוד איתה:</b> היא מתחילה ריקה, בתרחיש "רגוע", שבו כמעט כל בקשה נכנסת מיד. עבור לתרחיש "עומס", וראה איך התור מתמלא ואיך הדחיות מתחילות. אחר כך נסה "תור ענק": אין כמעט דחיות, אבל p95 עולה בלי הפסקה. זה בדיוק הרגע שבו לקוחות אמיתיים מתחילים לנטוש ולנסות שוב. בסוף שחק בעצמך עם המחוונים.</p>`,
    videos: [
      {
        title: "Server-Sent Events (SSE)",
        who: "FastAPI docs",
        part: "כל העמוד: EventSourceResponse, ServerSentEvent, Last-Event-ID, ו-SSE עם POST",
        minutes: 15,
        url: "https://fastapi.tiangolo.com/tutorial/server-sent-events/",
        required: true,
        kind: "תיעוד",
        why: "התמיכה המובנית ב-SSE נוספה ל-FastAPI בגרסה 0.135. העמוד קצר ומראה את הצורה הפשוטה של endpoint שמזרים. בשקף 6 נסביר למה בשירות שלנו בחרנו בצורה המפורשת יותר, ומה העמוד הזה לא מכסה: ניתוק של הלקוח.",
      },
      {
        title: "Concurrency and async / await",
        who: "FastAPI docs",
        part: "החלקים In a hurry ו-Path operation functions",
        minutes: 20,
        url: "https://fastapi.tiangolo.com/async/",
        required: true,
        kind: "תיעוד",
        why: "ההסבר הרשמי למתי כותבים def ומתי async def, ולמה endpoint רגיל רץ ב-threadpool. זה הבסיס לשקף 4, ולשאלה איך קוראים ל-llmkit, שהוא סינכרוני, מתוך שרת async.",
      },
      {
        title: "Using load shedding to avoid overload",
        who: "David Yanacek, Amazon Builders' Library",
        part: "כל המאמר. החשוב ביותר: goodput, ולמה לדחות מוקדם",
        minutes: 25,
        url: "https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload",
        required: true,
        kind: "מאמר",
        why: "המאמר הכי טוב שיש על backpressure בשירות אמיתי. הוא מסביר למה שירות שמקבל כל בקשה מתמוטט תחת עומס, ומה זה goodput: התפוקה שמגיעה ללקוח בזמן ששווה משהו. מתאים בדיוק לשער ולתור של השיעור.",
      },
      {
        title: "How NOT to Measure Latency",
        who: "Gil Tene, Strange Loop",
        part: "כל ההרצאה. אם אין זמן: החלק על percentiles ועל coordinated omission",
        minutes: 42,
        url: "https://www.youtube.com/watch?v=lJ8ydIuPFeU",
        required: false,
        kind: "וידאו",
        why: "למה ממוצע של latency מטעה, למה מסתכלים על p95 ו-p99, ואיך כלי בדיקת עומס יכולים להסתיר בדיוק את העיכובים שמעניינים אותך. ההרצאה לא חדשה, אבל הטעויות שהיא מתארת עדיין נפוצות.",
      },
      {
        title: "Locust documentation",
        who: "Locust 2.47",
        part: "Quickstart, Writing a locustfile, ו-Event hooks",
        minutes: 30,
        url: "https://docs.locust.io/en/stable/",
        required: false,
        kind: "תיעוד",
        why: "הכלי של תרגיל 5. כדאי לקרוא איך מגדירים משתמש, ואיך שולחים מדד משלך דרך events.request. ככה ה-locustfile של המעבדה מודד TTFT.",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "מסקריפט לשירות: מה משתנה",
      html: `<p class="big">עד עכשיו קראת למודל מסקריפט: בקשה אחת, אתה מחכה, מקבל תשובה. ברגע שהפיצ'ר הופך ל-API שאנשים אחרים קוראים לו, אותה קריאה צריכה לשרוד <b>הרבה משתמשים במקביל</b>, ספק עם מגבלות משלו, ולקוחות שמתנתקים, מנסים שוב ומחכים לתשובה בזמן.</p>
<p>שירות LLM שונה מ-API רגיל בארבעה דברים, וכל השיעור נגזר מהם. הדבר הראשון הוא <b>משך הבקשה</b>. בקשה טיפוסית לשירות web לוקחת 20 עד 100 מילישניות, ובקשה למודל לוקחת שתיים עד עשרים שניות. לכן כל בקשה תופסת משאבים (חיבור, זיכרון, מקום מול הספק) פי מאה יותר זמן, ושרת שמחזיק 100 בקשות במקביל נשמע כמו הרבה, אבל הוא מתמלא מהר. הדבר השני הוא <b>העלות</b>. כל בקשה עולה כסף, גם אם הלקוח כבר הלך. השלישי הוא <b>הספק</b>. יש לו rate limits ותקלות משלו (429, 529), והוא צוואר הבקבוק האמיתי שלך. הרביעי הוא <b>החוויה</b>. המשתמש לא מחכה לתשובה המלאה, הוא מחכה למילה הראשונה. לכן מזרימים, ולכן <b>TTFT</b> (time to first token) הוא המדד החשוב.</p>
<p>מכאן נגזרות ההחלטות של השיעור. מזרימים, ומוודאים שניתוק עוצר את הזרם. מגבילים מקביליות ודוחים מוקדם במקום לצבור תור. מגבילים כל לקוח בנפרד. נותנים לכל בקשה deadline. ומגדירים חוזה שגיאות שלקוח יכול לתכנת מולו. במעבדה כל זה נבנה סביב <b>Company Brain API v0</b>, שעונה על שאלות על Acme עם מקורות.</p>
<div class="callout"><b>מספר לזכור:</b> 8 קריאות במקביל, כשכל אחת לוקחת 2 שניות, הן לכל היותר 4 תשובות בשנייה. שום כמות של workers או שרתים לא משנה את זה, אם 8 הוא מה שהספק או התקציב מאפשרים. בשקף 13 נראה שזה חוק Little, ובתרגיל 5 תמדוד את זה.</div>`,
    },
    {
      kicker: "ארכיטקטורה",
      title: "Company Brain API v0: החוזה וסדר הבדיקות",
      html: `<p>לשירות יש שני endpoints עסקיים ושלושה תפעוליים. <code>POST /v1/answer</code> מקבל JSON ומחזיר JSON. <code>POST /v1/answer/stream</code> מקבל את אותו JSON ומחזיר זרם של אירועי SSE. <code>/healthz</code> ו-<code>/readyz</code> הם בשביל הפלטפורמה שמריצה את השירות, ו-<code>/admin/stats</code> מראה את המונים הפנימיים: השער, הלקוחות, ומה קרה לזרמים מול הספק.</p>
<p>הכי חשוב בשקף הזה הוא <b>סדר הבדיקות</b>. כל בקשה עוברת אותן בסדר קבוע, מהזולה ליקרה:</p>
<ol class="ladder">
<li><b>אימות</b><span>האם המפתח מוכר? בדיקה בזיכרון, מיקרו-שניות. בלי מפתח: 401.</span></li>
<li><b>Rate limit לפי מפתח</b><span>האם הלקוח הזה חרג מהקצב שלו? עוד בדיקה בזיכרון. אם כן: 429 rate-limited.</span></li>
<li><b>Idempotency</b><span>האם כבר ענינו על הבקשה הזו בדיוק? אם כן, מחזירים את התשובה השמורה ולא קוראים למודל בכלל.</span></li>
<li><b>שער מקביליות</b><span>האם יש מקום? אם לא, ממתינים בתור החסום, או מקבלים מיד 429 overloaded.</span></li>
<li class="danger"><b>הקריאה למודל, עם deadline</b><span>רק כאן מתחילים לשלם. וכל מה שלמעלה קרה <b>לפני</b> שנשלח 200, כך שכל סירוב הוא תשובת HTTP נקייה.</span></li>
</ol>
<p>למה הסדר הזה? כי שירות תחת עומס צריך לסרב <b>בזול</b>. אם בודקים rate limit אחרי שכבר חיכית בתור, לקוח אחד ששולח אלף בקשות ממלא את התור לכולם. ואם בודקים idempotency אחרי השער, בקשה חוזרת תופסת מקום יקר רק כדי לגלות שהתשובה כבר מוכנה. כלל אצבע: כל בדיקה שיכולה לסרב, ממוקמת לפני כל דבר שעולה יותר ממנה.</p>
<div class="example"><b>אירועי הזרם של /v1/answer/stream</b><pre dir="ltr">event: meta    {"id": "ans_...", "model": "claude-haiku-5-5", "citations": [...]}
event: token   {"text": "Full-time"}            (many of these)
event: done    {"usage": {...}, "cost_usd": 0.0002, "latency_ms": 1840, "ttft_ms": 410}
event: error   {problem+json}                   (only if something broke mid-stream)</pre></div>`,
    },
    {
      kicker: "FastAPI",
      title: "סכמות Pydantic: החוזה שהקוד אוכף",
      html: `<p>FastAPI (בדקנו: גרסה 0.162, אוקטובר 2026) בנוי סביב רעיון אחד: הטיפוסים של הפונקציה <b>הם</b> החוזה. מצהירים על מודל Pydantic לגוף הבקשה ולתשובה, ומקבלים שלושה דברים בחינם: ולידציה של כל בקשה, המרה ל-JSON של כל תשובה, ותיעוד OpenAPI ב-<code>/docs</code>, שנשאר מעודכן כי הוא נוצר מאותו קוד.</p>
<div class="example"><b>מתוך servekit/app.py</b><pre dir="ltr">class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    max_tokens: int = Field(400, ge=16, le=4096)

class AnswerResponse(BaseModel):
    id: str
    answer: str
    citations: list[Citation]
    model: str
    stop_reason: str
    usage: UsageOut
    cost_usd: Optional[float]
    latency_ms: int

@router.post("/answer", response_model=AnswerResponse, responses=PROBLEM_RESPONSES)
async def answer(body: AnswerRequest, request: Request,
                 client: str = Depends(rate_limited)): ...</pre></div>
<p>כמה החלטות שכדאי לשים לב אליהן. <b><code>extra="forbid"</code></b> אומר ששדה לא מוכר, למשל <code>temperature</code> שהלקוח חשב שאפשר לשלוח, יחזיר 422 ולא ייבלע בשקט. לקוח שחושב שהוא שולט בפרמטר שאנחנו מתעלמים ממנו יגלה את זה רק בפרודקשן. <b><code>max_length</code> על השאלה</b> הוא הגנה על התקציב: בלעדיו, לקוח יכול לשלוח שאלה של מאה אלף תווים, וזה מחיר שאתה משלם. <b><code>max_tokens</code> עם <code>le</code></b> מגביל את הפלט, ובקוד יש גם תקרה של השרת (<code>max_tokens_cap</code>), כי הגבול של ה-API והגבול התפעולי לא תמיד אותו דבר.</p>
<p><b><code>Depends(rate_limited)</code></b> הוא dependency injection של FastAPI. הפונקציה <code>rate_limited</code> תלויה ב-<code>authenticate</code>, ו-FastAPI מריץ את שתיהן לפני ה-handler. אם אחת מהן זורקת שגיאה, ה-handler לא רץ בכלל. כך סדר הבדיקות מהשקף הקודם נאכף על ידי המבנה של הקוד ולא על ידי משמעת.</p>
<div class="callout">התשובה מוגדרת כמודל גם כשמחזירים <code>JSONResponse</code> ידני (כמו אצלנו, כדי להוסיף כותרות). ה-<code>response_model</code> עדיין מתעד את החוזה ב-OpenAPI. ה-<code>responses=PROBLEM_RESPONSES</code> מתעד גם את השגיאות, כך שמי שמייצר client מהסכמה יודע שיכול לחזור 429.</div>`,
    },
    {
      kicker: "async",
      title: "ה-event loop, ולמה llmkit סינכרוני הוא בעיה",
      html: `<p>שרת async כמו uvicorn מריץ את כל הבקשות של worker אחד על <b>thread אחד</b>, עם event loop. כל פעם ש-handler מגיע ל-<code>await</code> (מחכה לרשת, לדיסק, לטיימר), הוא מוותר על ה-thread, והלולאה מריצה בקשה אחרת. כך worker אחד מחזיק אלפי חיבורים פתוחים. התנאי הוא שאף אחד לא <b>חוסם</b>: מי שמחכה בלי <code>await</code>, מחזיק את ה-thread, וכל השאר עומדים.</p>
<p>llmkit משיעור 2 משתמש ב-<code>httpx.Client</code> הסינכרוני. אם קוראים לו מתוך <code>async def</code>, הבקשה שמחכה שתי שניות למודל מקפיאה את כל ה-worker לשתי שניות. גם בקשות ל-<code>/healthz</code> לא נענות, והפלטפורמה עלולה להחליט שהשירות מת. זו הטעות הנפוצה ביותר בשרתי async, והיא לא נראית בבדיקה עם משתמש אחד.</p>
<h4>שלוש דרכים נכונות</h4>
<ul>
<li><b>endpoint רגיל (<code>def</code> ולא <code>async def</code>).</b> FastAPI מריץ אותו ב-threadpool, ולכן הוא לא חוסם את הלולאה. פשוט, אבל כל בקשה תופסת thread לכל משך הקריאה, וה-pool של anyio מוגבל כברירת מחדל ל-<b>40</b> threads. בדקנו בארגז החול: <code>total_tokens == 40</code>. המשמעות היא שהבקשה ה-41 מחכה, גם אם השער שלך מרשה 100.</li>
<li><b>threadpool ידני.</b> <code>await anyio.to_thread.run_sync(llm.complete, req)</code>, או לסטרימינג <code>threaded_stream</code> מ-servekit, שמריץ <code>next()</code> אחד ב-thread לכל אירוע. עובד עם כל ספרייה סינכרונית, עם אותה מגבלת threads, ועם עוד מחיר בביטול (שקף 9).</li>
<li><b>לקוח async אמיתי.</b> <code>AsyncLLM</code> ב-servekit משתמש ב-<code>httpx.AsyncClient</code>, ומשתמש מחדש ב-adapters של llmkit כדי לבנות בקשות ולפרסר תשובות, כך שפורמט החוט זהה. המתנה לא תופסת thread, וביטול סוגר את החיבור מיד. זו ברירת המחדל של השירות.</li>
</ul>
<div class="example"><b>הבאג, והתיקון</b><pre dir="ltr"># BAD: blocks the event loop for the whole LLM call
@app.post("/answer")
async def answer(body: AnswerRequest):
    return llm.complete(body.question)          # sync httpx inside async def

# OK: runs in the threadpool (max 40 at once by default)
@app.post("/answer")
def answer(body: AnswerRequest):
    return llm.complete(body.question)

# BEST for a server: a real async client
@app.post("/answer")
async def answer(body: AnswerRequest):
    return await allm.complete(build_request(body))</pre></div>`,
    },
    {
      kicker: "async",
      title: "AsyncLLM: לקוח async מעל אותם adapters",
      html: `<p>לא כתבנו לקוח חדש מאפס. ב-llmkit, ה-adapter של כל ספק הוא <b>תרגום טהור</b>: <code>build()</code> בונה את בקשת ה-HTTP, ו-<code>parse()</code> מפרסר את התשובה, בלי לפתוח חיבורים. רק <code>LLM</code> עושה I/O. לכן לקוח async צריך להחליף רק את שכבת ה-I/O: <code>httpx.AsyncClient</code> במקום <code>httpx.Client</code>, ו-<code>aiter_sse</code>, תאום אסינכרוני של מפרסר ה-SSE של llmkit. זה התגמול על ההפרדה שתכננו בשיעור 2.</p>
<div class="example"><b>servekit/async_llm.py, הליבה של stream()</b><pre dir="ltr">call = self.provider.build(req, self.model, self.api_key, stream=True)
async with self.http.stream("POST", self.base_url + call.path,
                            headers=call.headers, json=call.body) as resp:
    if resp.status_code >= 400:
        await resp.aread()
        raise self.provider.error(resp.status_code, resp.text, resp.headers)
    async for ev in aiter_sse(resp.aiter_lines()):
        ...  # content_block_delta -> yield StreamEvent("text", ...)</pre></div>
<p>הגבלה שכדאי להכיר: ה-<code>parse_stream</code> של llmkit הוא generator סינכרוני שצורך iterator של אירועים, ואי אפשר להזין אותו מבחוץ אירוע אחרי אירוע מתוך קוד async. לכן הסטרימינג האסינכרוני ב-servekit מומש לפורמט של Anthropic (שהוא גם הפורמט של <code>mock:</code>), ושאר הספקים עוברים דרך <code>threaded_stream</code>. זו החלטה מכוונת: הקורס עובד עם Claude, ולא היה טעם לשכפל שלושה מפרסרים.</p>
<h4>שתי החלטות נוספות</h4>
<ul>
<li><b>אין retries בתוך השרת.</b> llmkit עושה retries עם backoff, וזה נכון לסקריפט. בשרת תחת עומס, retry פנימי מכפיל את העומס בדיוק כשהספק כבר עמוס (retry storm), ומעכב תשובה ללקוח שיש לו deadline משלו. השרת מחזיר 503 עם <code>Retry-After</code>, והלקוח, שיודע כמה זמן נשאר לו, מחליט אם לנסות שוב.</li>
<li><b>connection pool.</b> <code>httpx.Limits(max_connections=200)</code>. ה-pool משותף לכל הבקשות, וחיבורי keep-alive חוסכים TLS handshake (עשרות מילישניות) בכל קריאה. אבל הוא לא תחליף לשער: הוא מגביל חיבורים, לא עלות.</li>
</ul>`,
    },
    {
      kicker: "סטרימינג",
      title: "Server-Sent Events: הפורמט, הכותרות, וה-endpoint",
      html: `<p>SSE הוא הפורמט הפשוט ביותר לזרם מהשרת ללקוח: תשובת HTTP רגילה עם <code>Content-Type: text/event-stream</code>, שהגוף שלה לא נגמר. כל אירוע הוא כמה שורות <code>field: value</code>, ושורה ריקה מסיימת אותו. שורה שמתחילה בנקודתיים היא הערה, ומשמשת כ-keep-alive. זה אותו פורמט שהספקים משתמשים בו מולך, ולכן llmkit כבר יודע לפרסר אותו.</p>
<div class="example"><b>מה עובר בחוט (curl -N מראה בדיוק את זה)</b><pre dir="ltr">event: token
data: {"text": " vacation"}

: ping

event: done
data: {"stop_reason": "end", "ttft_ms": 412, ...}</pre></div>
<h4>שלוש כותרות ושני פרטים שמכשילים</h4>
<ul>
<li><b><code>Cache-Control: no-cache</code></b> ו-<b><code>X-Accel-Buffering: no</code></b>. בלי השנייה, nginx (וחלק מה-load balancers) אוגר את כל התשובה ושולח אותה בסוף, והסטרימינג "עובד" רק במחשב שלך.</li>
<li><b>keep-alive.</b> proxy שלא רואה בייטים 60 שניות סוגר את החיבור. מודל עם thinking יכול לשתוק יותר מזה לפני הטוקן הראשון. FastAPI שולח <code>: ping</code> כל 15 שניות כשה-generator שותק.</li>
<li><b>SSE עם POST.</b> ה-<code>EventSource</code> של הדפדפן יודע רק GET. ל-LLM צריך גוף בקשה, ולכן לקוחות דפדפן קוראים את הזרם עם <code>fetch</code> ו-<code>response.body.getReader()</code>. בצד השרת זה לא משנה כלום.</li>
</ul>
<h4>שתי דרכים לכתוב את ה-endpoint</h4>
<div class="example"><b>הדרך המובנית של FastAPI (מ-0.135)</b><pre dir="ltr">from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.post("/chat/stream", response_class=EventSourceResponse)
async def chat(body: AnswerRequest):
    async for ev in allm.stream(build_request(body)):
        yield ServerSentEvent(data={"text": ev.text}, event="token")</pre></div>
<p>זו הדרך הנכונה לרוב המקרים, וגם <b>sse-starlette</b> (גרסה 3.6) עושה דבר דומה. בשירות שלנו בחרנו בדרך המפורשת: <code>StreamingResponse</code> משלנו, <code>GatedSSE</code>, שמקבל generator של בייטים שנבנו עם <code>format_sse_event</code> של FastAPI. הסיבה היא שהקוד שלפני ה-<code>yield</code> הראשון ב-endpoint עם yield רץ <b>אחרי</b> שה-200 נשלח. אנחנו צריכים לתפוס מקום בשער, ולדחות עם 429 אם אין, <b>לפני</b> הכותרות. וצריך להחזיק את המקום עד שהזרם נגמר, ולשחרר אותו בדיוק פעם אחת, גם אם הלקוח התנתק עוד לפני שהגוף התחיל.</p>`,
    },
    {
      kicker: "סטרימינג",
      title: "WebSocket בקצרה: מתי כן, ולמה לא כברירת מחדל",
      html: `<p>WebSocket הוא חיבור דו-כיווני ומתמשך: אחרי handshake של HTTP, שני הצדדים שולחים הודעות מתי שהם רוצים. זה נשמע כמו התאמה טבעית לצ'אט, אבל לרוב ה-APIs של LLM, SSE עדיף.</p>
<h4>מתי WebSocket מוצדק</h4>
<ul>
<li><b>קול ואודיו בזמן אמת.</b> הלקוח שולח אודיו ברציפות, והשרת עונה תוך כדי. זה המקרה של הפרויקט השני בסוף הקורס, המורה לעברית מדוברת, וזה מה שה-Realtime APIs של הספקים משתמשים בו.</li>
<li><b>הפרעה באמצע.</b> המשתמש אומר "עצור, התכוונתי למשהו אחר" בזמן שהמודל עונה, וצריך להעביר את זה על אותו חיבור.</li>
<li><b>הרבה הודעות קטנות לשני הכיוונים</b>, כמו עורך שיתופי או סוכן שמבקש אישורים תוך כדי עבודה.</li>
</ul>
<h4>מה מאבדים</h4>
<ul>
<li><b>סמנטיקה של HTTP.</b> אין status code לכל הודעה, אין <code>Retry-After</code>, אין caching, ואין idempotency. את כל אלה בונים בעצמך בפרוטוקול ההודעות.</li>
<li><b>תשתית.</b> load balancers, proxies ו-WAF צריכים תמיכה מפורשת. חיבור ארוך מקשה על פריסה מתגלגלת, כי צריך לנתק לקוחות כדי להחליף גרסה.</li>
<li><b>backpressure ידני.</b> ב-SSE, ה-TCP של תשובת HTTP אחת עושה את העבודה. ב-WebSocket צריך לחשוב מה קורה כשהלקוח איטי והשרת ממשיך לשלוח.</li>
</ul>
<div class="example"><b>WebSocket ב-FastAPI, לשם השוואה</b><pre dir="ltr">@app.websocket("/v1/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    while True:
        msg = await socket.receive_json()          # raises WebSocketDisconnect on close
        async for ev in allm.stream(build_request(msg["question"])):
            await socket.send_json({"type": "token", "text": ev.text})
        await socket.send_json({"type": "done"})</pre></div>
<p>כלל אצבע: אם הלקוח שולח בקשה אחת ומקבל תשובה אחת שמגיעה בחלקים, זה SSE. אם הלקוח צריך לדבר תוך כדי שהשרת מדבר, זה WebSocket.</p>`,
    },
    {
      kicker: "סטרימינג",
      title: "שגיאה אחרי ה-200",
      html: `<p>בתשובה רגילה, השרת מחליט על ה-status אחרי שהוא יודע מה קרה. בזרם זה הפוך: ה-200 והכותרות נשלחים <b>לפני</b> הטוקן הראשון, ואחרי זה אין דרך חזרה. אם הספק נופל אחרי עשרים טוקנים, אי אפשר "להפוך" את התשובה ל-503. זה אותו מצב שראית בשיעור 2 מהצד של הלקוח: אצל Anthropic מגיע אירוע <code>error</code> בתוך זרם של 200.</p>
<p>לכן החוזה שלנו מגדיר שלושה סיומים אפשריים לזרם, והלקוח חייב לטפל בכולם:</p>
<ul>
<li><b><code>event: done</code></b>: הצלחה. רק אחרי האירוע הזה התשובה שלמה. הוא מביא usage, עלות, latency ו-TTFT כפי שהשרת מדד אותם מול הספק.</li>
<li><b><code>event: error</code></b>: כישלון אחרי שהתחלנו. הגוף הוא אותו problem+json שהיה חוזר כ-status, עם אותו <code>type</code>. הלקוח מציג את הטקסט החלקי שהגיע, מסמן אותו כלא שלם, ומחליט אם לנסות שוב.</li>
<li><b>החיבור נסגר בלי אף אחד מהם</b>: רשת, proxy, או קריסה של השרת. הלקוח צריך להתייחס לזה כמו ל-error. לקוח שמחכה ל-<code>done</code> בלי timeout יתקע.</li>
</ul>
<div class="example"><b>מה errors_tour.py מדפיס בתרגיל 7 (הספק נופל אחרי 3 טוקנים)</b><pre dir="ltr">HTTP 200 (already sent, cannot change now)
event: error
data: {"type": "https://acme.example/problems/upstream-unavailable",
       "title": "The language model provider is overloaded", "status": 503,
       "detail": "The provider is overloaded (overloaded_error). Retry later.",
       "request_id": "f33b9e96...", "retry_after": 5}</pre></div>
<p>שתי החלטות נוספות. ראשית, <b>retry אחרי שהטקסט התחיל</b> הוא החלטה של המוצר: להתחיל מחדש (המשתמש יראה את הטקסט נעלם ומופיע שוב), או להשאיר את החלקי ולהציע כפתור. llmkit משיעור 2 עושה retry רק לפני הטוקן הראשון, מאותה סיבה. שנית, <b>ה-meta הולך ראשון</b>. המקורות נשלחים לפני הטוקנים, כך שה-UI יכול להציג אותם מיד, וגם אם הזרם נשבר, המשתמש יודע על מה התשובה הייתה מבוססת.</p>`,
    },
    {
      kicker: "ביטול",
      title: "ניתוק של הלקוח חייב לעצור את הזרם למעלה",
      html: `<p>משתמש שאל שאלה, ראה שהתשובה הולכת לכיוון לא נכון, וסגר את הלשונית. מה קורה בשרת? במימוש נכון, תוך מילישניות החיבור לספק נסגר, הספק מפסיק לייצר, ואתה מפסיק לשלם. במימוש שגוי, הספק ממשיך לייצר את כל 2,000 הטוקנים, השרת קורא אותם לתוך זיכרון שאף אחד לא יקרא, והמקום בשער תפוס עד הסוף.</p>
<h4>איך הביטול עובר, שכבה אחרי שכבה</h4>
<ol>
<li><b>uvicorn</b> מגלה שהחיבור נסגר. בדקנו בקוד: הוא מכריז על ASGI spec 2.3, ולכן <b>Starlette</b> מריץ, במקביל לשליחת הזרם, משימה שמאזינה ל-<code>http.disconnect</code>, ומבטלת את משימת השליחה ברגע שההודעה מגיעה.</li>
<li>הביטול מגיע כ-<code>CancelledError</code> לתוך ה-generator שלנו, בנקודה שבה הוא מחכה לאירוע הבא מהספק.</li>
<li>ה-<code>async with self.http.stream(...)</code> של <code>AsyncLLM</code> יוצא, ו-httpx סוגר את חיבור ה-TCP לספק.</li>
<li>הספק מנסה לכתוב את האירוע הבא, נכשל, ומפסיק. אצל ספק אמיתי, הוא גם מפסיק לחייב על טוקנים שלא נוצרו.</li>
</ol>
<p>ב-<code>GatedSSE</code> יש עוד רשת ביטחון: ב-<code>finally</code> של <code>__call__</code> הוא קורא ל-<code>aclose()</code> על ה-generator, בתוך scope מוגן מביטול, ורק אחר כך משחרר את המקום בשער. כך הסגירה דטרמיניסטית גם כשהביטול הגיע ברגע שה-generator לא רץ.</p>
<h4>מה מדדנו בארגז החול (cancel_demo.py, תשובה של 100 טוקנים, ניתוק אחרי 10)</h4>
<ul>
<li><b>async:</b> הספק שלח 11 טוקנים וסומן <code>aborted</code>. טוקן אחד "עף" בזמן שהניתוק התגלגל.</li>
<li><b>thread:</b> הספק שלח 12 וסומן <code>aborted</code>. ה-thread לא יכול להיקטע באמצע <code>next()</code>, ולכן הסגירה מחכה שהוא יחזור, כלומר טוקן אחד מאוחר יותר.</li>
<li class="bad"><b>leaky:</b> השירות דיווח <code>closed_early: 1</code>, וכל המדדים שלו נראו תקינים. אבל הספק סומן <code>completed</code> עם כל 100 הטוקנים. מבחינת החשבונית, המשתמש שסגר את הלשונית קיבל תשובה מלאה.</li>
</ul>`,
    },
    {
      kicker: "ביטול",
      title: "הבאג הדולף, והמקרה של JSON",
      html: `<p>איך נראה הקוד שדולף? כמעט תמיד כך: מישהו רצה "לפרק" את הקריאה לספק מהשליחה ללקוח, ולכן פתח משימת רקע שקוראת מהספק לתוך תור, וה-response קורא מהתור. זה נראה נקי, וזה עובד מצוין בבדיקות.</p>
<div class="example"><b>servekit/async_llm.py: leaky_stream (בכוונה)</b><pre dir="ltr">q = asyncio.Queue()                       # unbounded: no backpressure either

async def produce():
    async for ev in llm.stream(req):
        await q.put(ev)
    await q.put(_DONE)

task = loop.create_task(produce())         # fire and forget: THE BUG
while True:
    item = await q.get()
    if item is _DONE:
        return
    yield item</pre></div>
<p>כשהלקוח מתנתק, Starlette מבטל את מי שקורא מהתור. אבל המשימה <code>produce</code> לא קשורה אליו בשום צורה: היא ממשיכה לקרוא מהספק עד הסוף, ושמה הכל בתור שאף אחד לא יקרא. יש כאן שני באגים. הראשון הוא שאין ביטול: התיקון הוא <code>try/finally: task.cancel()</code>, או מבנה עם task group, שבו משימות ילדים מתבטלות עם ההורה. השני הוא שהתור לא חסום: גם בלי ניתוק, לקוח איטי גורם לשרת לצבור את כל התשובה בזיכרון. <code>asyncio.Queue(maxsize=8)</code> היה גורם ל-<code>produce</code> לחכות, וזה backpressure בקטן.</p>
<h4>ומה עם POST /v1/answer?</h4>
<p>כאן יש הפתעה: Starlette <b>לא</b> מבטל handler רגיל כשהלקוח מתנתק. הבדיקה של <code>http.disconnect</code> שראינו קיימת רק ב-<code>StreamingResponse</code>. אם לקוח שלח שאלה ונטש אחרי שנייה, השרת ימשיך לחכות לתשובה המלאה מהספק, וישלם עליה. לכן ב-servekit יש <code>run_until_disconnect</code>: הוא מריץ את הקריאה למודל כמשימה, ובמקביל משימה שבודקת כל 200 מילישניות את <code>request.is_disconnected()</code>. מה שמסתיים ראשון מנצח. אם הלקוח הלך, הקריאה מבוטלת, והלוג מסמן <code>outcome: client_disconnected</code>. אותה פונקציה אוכפת גם את ה-deadline של הבקשה כולה.</p>
<div class="callout"><b>הלקח של תרגיל 4:</b> מדדים שהשירות אוסף על עצמו מראים מה <b>הוא</b> חושב שקרה. במצב leaky הוא חשב שהכל בסדר. האמת נמדדת בצד השני: אצל ה-upstream, ובסוף בחשבונית של הספק.</div>`,
    },
    {
      kicker: "timeouts",
      title: "Timeouts: תקציב זמן בכמה שכבות",
      html: `<p>כל בקשה צריכה גבול זמן, אחרת בקשה אחת תקועה מחזיקה מקום בשער לנצח, ושירות שיש לו כמה כאלה מפסיק לענות. אבל timeout אחד לא מספיק, כי יש כמה דברים שונים שיכולים להיתקע. ב-Company Brain יש ארבע שכבות:</p>
<ul>
<li><b>connect ו-read של httpx</b> (מ-llmkit: 5 שניות להתחברות, 60 שניות בין בייטים). מגינים מפני ספק שלא עונה בכלל, או חיבור שמת באמצע.</li>
<li><b>first-token timeout</b> (15 שניות). בזרם, כמה זמן מחכים לטוקן הראשון. הוא נפרד, כי זמן החשיבה של המודל לפני הטוקן הראשון יכול להיות ארוך, ואחר כך הטוקנים זורמים מהר.</li>
<li><b>idle timeout</b> (15 שניות). כמה זמן מותר בין טוקן לטוקן. זרם שהתחיל ואז נתקע הוא תקלה, גם אם ה-read timeout של httpx עוד לא הגיע.</li>
<li><b>request deadline</b> (30 שניות, ב-endpoint של JSON). הזמן הכולל של הבקשה. מעבר לו, הלקוח כבר כנראה ויתר.</li>
</ul>
<p>שלושה כללים שעוזרים לבחור מספרים:</p>
<ol class="ladder">
<li><b>timeout של שכבה פנימית קטן מזה של החיצונית</b><span>אם ה-load balancer סוגר אחרי 60 שניות, ה-deadline של השרת צריך להיות קצר מזה. אחרת הלקוח מקבל 504 גנרי מה-proxy, במקום problem+json מסודר מהשרת, והשרת ממשיך לעבוד על תשובה שכבר אין לה למי ללכת.</span></li>
<li><b>timeout הוא סירוב, לא retry</b><span>בתוך השרת לא מנסים שוב אחרי timeout. מחזירים 504 upstream-timeout, ומשחררים את המקום. אם הספק איטי, retry רק מחמיר.</span></li>
<li><b>מודדים לפני שקובעים</b><span>p99 של TTFT מול Haiku הוא נקודת ההתחלה, לא הניחוש. בתרגיל 8 תראה את המספר האמיתי, ובשיעור 22 תעקוב אחריו לאורך זמן.</span></li>
</ol>
<div class="example"><b>first-token ו-idle timeout בקוד</b><pre dir="ltr">ev = await asyncio.wait_for(
    it.__anext__(), s.first_token_timeout if n == 0 else s.idle_timeout)
# TimeoutError -> event: error (upstream-timeout), finally: it.aclose()</pre></div>`,
    },
    {
      kicker: "backpressure",
      title: "שער מקביליות, תור חסום ו-429",
      html: `<p>Backpressure פירושו לדחוף את העומס חזרה למי ששולח אותו, במקום לספוג אותו. השירות יודע כמה הוא יכול לעשות בבת אחת: כמה קריאות במקביל הספק מרשה, כמה התקציב מרשה, וכמה הזיכרון מרשה. השער הוא המקום שבו המספר הזה נאכף.</p>
<div class="example"><b>servekit/gate.py, בקיצור (תרגיל 3)</b><pre dir="ltr">async def acquire(self):
    if self.waiting == 0 and not self._sem.locked():     # free slot, nobody ahead
        await self._sem.acquire(); ...; return
    if self.waiting >= self.max_queue:                    # shed: instant, costs nothing
        raise GateRejected("queue_full", self.retry_after())
    self.waiting += 1
    try:
        await asyncio.wait_for(self._sem.acquire(), self.queue_timeout)
    except asyncio.TimeoutError:                          # shed after waiting: expensive
        raise GateRejected("queue_timeout", self.retry_after())
    finally:
        self.waiting -= 1</pre></div>
<h4>למה כל חלק קיים</h4>
<ul>
<li><b>Semaphore</b> מגביל את מספר הקריאות שרצות. בלעדיו, 500 בקשות פותחות 500 קריאות לספק, הספק מחזיר 429 לחצי מהן, וכולן איטיות.</li>
<li><b>תור חסום</b> סופג גלים קצרים. בקשה שמגיעה ברגע של שיא מחכה חצי שנייה במקום להידחות. אבל הוא חסום, כי תור בלי גבול רק דוחה את הכישלון: כל בקשה מחכה יותר, הלקוחות מגיעים ל-timeout ושולחים שוב, והשרת עונה על בקשות שכבר אף אחד לא מחכה להן. ב-AWS קוראים לזה goodput שצונח לאפס בזמן שה-throughput נראה מצוין.</li>
<li><b>queue timeout</b> מגביל כמה זמן בקשה יכולה לחכות. בבדיקת העומס שלנו, דחיות מסוג queue_timeout לקחו 2 שניות כל אחת, ודחיות queue_full לקחו 4 מילישניות. שתיהן 429, אבל הראשונה בזבזה ללקוח שתי שניות.</li>
<li><b>Retry-After</b> אומר ללקוח מתי לחזור. אצלנו זה ההערכה של זמן ההתרוקנות של התור: <code>ceil(avg_service × (waiting + 1) / limit)</code>. בלי הכותרת, לקוחות חוזרים מיד, כולם ביחד.</li>
</ul>
<div class="callout"><b>429 או 503?</b> אצלנו, עומס על השירות מחזיר <b>429 overloaded</b>, ועומס על הספק מחזיר <b>503 upstream-unavailable</b>, שניהם עם <code>Retry-After</code>. יש מי שמחזירים 503 על עומס של השירות עצמו, וגם טיוטת ה-RateLimit של IETF ממליצה על 503 ל-"temporary reduced capacity". מה שחשוב הוא שזה עקבי ומתועד, שה-<code>type</code> ב-problem+json מבחין בין המקרים, ושהלקוח מכבד את <code>Retry-After</code>.</div>`,
    },
    {
      kicker: "קיבולת",
      title: "חוק Little ונקודת הברך",
      html: `<p class="big">חוק Little אומר: <b>מספר הבקשות שנמצאות בתוך המערכת שווה לקצב שבו הן מגיעות, כפול הזמן שכל אחת נשארת.</b> בסימון: L = λ × W.</p>
<p>במילים פשוטות: אם נכנסות 4 בקשות בשנייה, וכל אחת נשארת 2 שניות, אז בכל רגע נתון יש בפנים בממוצע 8 בקשות. זה נכון לכל מערכת יציבה, לא משנה איך היא בנויה: קופה בסופר, שרת, או ספק LLM. והשימוש החשוב הוא בכיוון ההפוך. אם השער מרשה לכל היותר 8 בקשות בפנים (L = 8), וכל קריאה למודל לוקחת 2 שניות (W = 2), אז התפוקה המקסימלית היא λ = L / W = 4 תשובות בשנייה. זה המספר שבשקף הפתיחה.</p>
<h4>מה זה אומר כשהעומס עולה</h4>
<ul>
<li><b>מתחת לקיבולת</b> (פחות מ-4 בשנייה), כל בקשה נכנסת מיד, W נשאר 2 שניות, והתפוקה שווה לקצב ההגעה.</li>
<li><b>בקיבולת</b>, השער מלא כל הזמן. התפוקה נתקעת על 4 בשנייה, ומכאן כל בקשה נוספת רק מחכה. W גדל, כי עכשיו הוא כולל המתנה בתור.</li>
<li><b>מעל הקיבולת</b>, התור מתמלא, ואז מתחילות דחיות. בלי תור חסום, W היה ממשיך לגדול עד שהלקוחות נוטשים.</li>
</ul>
<h4>מה מדדנו בתרגיל 5, בארגז החול</h4>
<p>השרת המדומה ענה תוך כ-1.8 שניות (0.3 עד הטוקן הראשון, ועוד 60 טוקנים בקצב של 40 לשנייה), והשער הרשה 8 בקשות במקביל. חוק Little צפה תקרה של 8 / 1.9, כלומר כ-4.2 בשנייה. בפועל:</p>
<ul>
<li><b>1 עד 8 משתמשים:</b> התפוקה עלתה ליניארית, מ-0.47 ל-3.5 בשנייה, ה-p95 נשאר כ-2 שניות, וה-TTFT נשאר כ-0.33 שניות.</li>
<li><b>16 משתמשים:</b> התפוקה נעצרה על 4.0, ה-p50 קפץ ל-3.3 שניות, וה-TTFT קפץ ל-1.8 שניות. זה זמן ההמתנה בתור.</li>
<li><b>32 ו-64 משתמשים:</b> התפוקה עדיין 4.0, ונוספו 257 ו-1,325 דחיות 429. השרת הגן על הבקשות שקיבל.</li>
</ul>
<p><b>נקודת הברך</b> היא הרמה שבה עוד עומס מפסיק לקנות תפוקה ומתחיל לקנות רק המתנה. כאן, 8 משתמשים. sweep.py מוצא אותה עם המדד "power", כלומר תפוקה חלקי p95, שהוא מקסימלי בברך. עם ספק אמיתי, התקרה לא באה מהשער שלך אלא מה-rate limit של הספק, בטוקנים לדקה. לכן מכוונים את השער לפי המספר הזה, ולא לפי כמה ה-CPU מחזיק.</p>`,
    },
    {
      kicker: "Rate limiting",
      title: "Rate limit לפי מפתח: token bucket",
      html: `<p>השער מגן על השירות מכלל העומס. Rate limit מגן על <b>הלקוחות אחד מהשני</b>: בלעדיו, סקריפט אחד שנתקע בלולאה ממלא את השער, וכל השאר מקבלים 429. לכן מגבילים כל מפתח API בנפרד, ובודקים את זה לפני השער.</p>
<h4>למה token bucket</h4>
<p>לכל מפתח יש דלי שמחזיק עד <b>burst</b> אסימונים, ומתמלא בקצב של <b>rate</b> אסימונים לשנייה. כל בקשה לוקחת אסימון. כשהדלי ריק, הבקשה נדחית, והתשובה אומרת בדיוק מתי יהיה אסימון: <code>(cost − tokens) / rate</code>. החלופה הנאיבית, "N בקשות לכל דקה עגולה", מאפשרת 2N בקשות בתוך שנייה, N ב-00:59 ועוד N ב-01:00. הדלי מאפשר פרץ קצר עד burst, ואחריו קצב יציב של rate, וזה בדיוק מה שרוצים מלקוח אנושי שלוחץ כמה פעמים ברצף.</p>
<div class="example"><b>מה burst.py מראה בתרגיל 2 (rate=2, burst=5)</b><pre dir="ltr">#0  t=0.08s  HTTP 200                  "per-key";r=4;t=1
...
#4  t=0.14s  HTTP 200                  "per-key";r=0;t=3
#5  t=0.14s  HTTP 429  rate-limited   Retry-After: 1   "per-key";r=0;t=3</pre></div>
<h4>כותרות שמספרות ללקוח איפה הוא עומד</h4>
<p>טיוטת IETF בשם RateLimit header fields (גרסה 11, מאי 2026) מגדירה שתי כותרות. <code>RateLimit-Policy: "per-key";q=5;w=3</code> מתארת את המדיניות: מכסה של 5 בחלון של 3 שניות. <code>RateLimit: "per-key";r=0;t=3</code> מתארת את המצב עכשיו: נשארו 0, ותוך 3 שניות המכסה מתמלאת. הטיוטה קובעת גם שכאשר יש <code>Retry-After</code>, הלקוח מציית לו. זו עדיין טיוטה, ולכן השמות עלולים להשתנות. הרבה APIs עדיין משתמשים בכותרות הישנות בסגנון <code>X-RateLimit-Remaining</code>.</p>
<h4>שתי הרחבות שחשובות ב-LLM</h4>
<ul>
<li><b>לספור טוקנים ולא בקשות.</b> שאלה של 10 מילים ושאלה עם מסמך של 50 עמודים הן לא אותה בקשה. ל-<code>try_acquire</code> יש פרמטר <code>cost</code>. אפשר לגבות לפי <code>max_tokens</code> מראש, ולתקן לפי ה-usage בסוף. כך עובדים ה-rate limits של הספקים עצמם.</li>
<li><b>כמה replicas.</b> דלי בזיכרון נכון רק לתהליך אחד. עם שלושה replicas, כל לקוח מקבל פי שלושה. הפתרון הוא Redis, עם סקריפט Lua אחד שעושה refill ו-take באופן אטומי, או gateway משותף. זה נושא 25.</li>
</ul>`,
    },
    {
      kicker: "Idempotency",
      title: "Idempotency-Key: לא לשלם פעמיים על אותה שאלה",
      html: `<p>לקוח שלח שאלה, ואחרי 30 שניות קיבל timeout מה-proxy. האם השרת קיבל את הבקשה? אולי היא עוד רצה, ואולי היא הסתיימה והתשובה הלכה לאיבוד בדרך. אם הלקוח שולח שוב, הוא עלול לשלם פעמיים, ולקבל תשובה אחרת. ב-POST אין הבטחה שבקשה חוזרת בטוחה. הכותרת <code>Idempotency-Key</code> נותנת אותה.</p>
<p>הלקוח מייצר מפתח ייחודי לכל פעולה לוגית (UUID), ושולח אותו בכל ניסיון של אותה פעולה. השרת זוכר, לפי (לקוח, מפתח), את טביעת האצבע של הגוף ואת התשובה. ההתנהגות מוגדרת בטיוטת IETF, <code>draft-ietf-httpapi-idempotency-key-header-08</code> מאוקטובר 2026:</p>
<ul>
<li><b>מפתח חדש:</b> מריצים כרגיל, ושומרים את התשובה.</li>
<li><b>אותו מפתח ואותו גוף, הבקשה הראשונה הסתיימה:</b> מחזירים את התשובה השמורה, אצלנו עם <code>Idempotent-Replayed: true</code>. המודל לא נקרא שוב, והתשובה זהה בייט אחרי בייט.</li>
<li><b>אותו מפתח ואותו גוף, הראשונה עוד רצה:</b> 409 Conflict. הלקוח מחכה ומנסה שוב.</li>
<li><b>אותו מפתח עם גוף אחר:</b> 422. זה באג אצל הלקוח, שהשתמש באותו מפתח לשתי פעולות.</li>
</ul>
<h4>ההחלטות שבקוד</h4>
<ul>
<li><b>טביעת אצבע קנונית:</b> sha256 של JSON עם מפתחות ממוינים ובלי רווחים. כך <code>{"a":1,"b":2}</code> ו-<code>{"b": 2, "a": 1}</code> הם אותה בקשה.</li>
<li><b>scope לפי לקוח:</b> שני לקוחות יכולים לבחור במקרה את אותו מחרוזת. בלי scope, אחד מקבל את התשובה של השני. זו דליפת מידע.</li>
<li><b>לא שומרים כישלונות.</b> אם הספק החזיר 502, השירות <b>שוכח</b> את המפתח, כדי שה-retry של הלקוח ירוץ באמת. אחרת הלקוח יקבל שוב ושוב את אותה שגיאה שמורה ל-24 שעות.</li>
<li><b>תפוגה מתועדת:</b> 24 שעות. הטיוטה דורשת לפרסם את מדיניות התפוגה.</li>
</ul>
<div class="callout">בזרם, idempotency מסובך יותר: אם החיבור נשבר באמצע, ה-retry צריך להמשיך מהמקום שבו נעצר, לא להתחיל מחדש. ל-SSE יש לזה מנגנון, <code>Last-Event-ID</code>, אבל זה מחייב לשמור את האירועים בצד השרת. ב-v0 בחרנו לתמוך ב-idempotency רק ב-endpoint של JSON, וזה כתוב בחוזה.</div>`,
    },
    {
      kicker: "שגיאות",
      title: "חוזה שגיאות: problem+json",
      html: `<p>לקוח שמקבל שגיאה צריך לדעת שלושה דברים: <b>מה קרה</b> (כדי להחליט מה לעשות), <b>האם לנסות שוב ומתי</b>, ו<b>איך לדווח</b>. RFC 9457 (Problem Details for HTTP APIs, 2023) מגדיר לזה פורמט סטנדרטי: <code>application/problem+json</code>, עם חמישה שדות.</p>
<div class="example"><b>429 מהשירות</b><pre dir="ltr">HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 1
RateLimit: "per-key";r=0;t=3

{"type": "https://acme.example/problems/rate-limited",
 "title": "Too many requests",
 "status": 429,
 "detail": "Client 'bob' exceeded 2 requests/second (burst 5).",
 "instance": "/v1/answer",
 "request_id": "f347158d8be24c21924d9532dfcc7c80",
 "retry_after": 1}</pre></div>
<ul>
<li><b><code>type</code></b> הוא המזהה היציב, ועליו הלקוח עושה <code>switch</code>. לעולם לא על <code>detail</code>, שמשתנה בכל מקרה.</li>
<li><b><code>title</code></b> קבוע לכל type, ו-<b><code>detail</code></b> הוא ההסבר למקרה הספציפי, לבני אדם.</li>
<li><b>שדות הרחבה</b> מותרים לפי ה-RFC. אצלנו: <code>request_id</code>, <code>retry_after</code>, <code>reason</code>, ו-<code>errors</code> בשגיאות ולידציה.</li>
</ul>
<h4>הקטלוג הוא החוזה</h4>
<p>ב-<code>servekit/problems.py</code> יש רשימה סגורה של 13 סוגים, כל אחד עם status ו-title. כל מקום בקוד זורק <code>Problem("rate-limited", ...)</code>, ו-exception handler אחד הופך אותו לתשובה. גם שגיאות של FastAPI עצמו (422 על גוף לא תקין, 404, 405) עוברות דרך handlers שממירים אותן לאותו פורמט. אחרת הלקוח היה מקבל שני פורמטים של שגיאות, והיה צריך לפרסר את שניהם.</p>
<h4>מה לא שמים בשגיאה</h4>
<ul>
<li><b>הודעות של הספק.</b> ההודעה המקורית של Anthropic הולכת ללוג, יחד עם ה-request id של הספק, ולא ללקוח. היא יכולה לחשוף פרטים פנימיים.</li>
<li><b>stack traces וטקסט של exceptions.</b> ב-500, ה-detail אומר רק "Quote the request_id", והפרטים בלוג.</li>
<li><b>הקלט של הלקוח.</b> שגיאות הוולידציה של Pydantic כוללות כברירת מחדל את הערך שנכשל. ה-handler שלנו מוריד אותו, כי שאלה של משתמש יכולה להכיל מידע רגיש, ושגיאות נוטות להגיע ללוגים.</li>
</ul>`,
    },
    {
      kicker: "תפעול",
      title: "Request ID, לוגים מובנים, health ו-readiness",
      html: `<p>כשמשתמש מתלונן ש"התשובה נתקעה באמצע", צריך למצוא את הבקשה שלו בין מיליון אחרות. לכן לכל בקשה יש <b>request id</b>. אם הלקוח שלח <code>X-Request-ID</code> תקין, משתמשים בו, וכך אפשר לעקוב אחרי בקשה דרך כמה שירותים. אחרת מייצרים אחד. הוא חוזר בכותרת התשובה ובכל problem+json, ונכנס לכל שורת לוג.</p>
<div class="example"><b>שורת הלוג של בקשה אחת (מהשירות בארגז החול)</b><pre dir="ltr">{"ts": 1793568860.43, "level": "info", "msg": "request",
 "request_id": "5f402cc6c6ac41dcba7708243231c9cf", "method": "POST",
 "path": "/v1/answer/stream", "status": 200, "duration_ms": 1212.7,
 "client": "alice", "outcome": "client_disconnected", "stream_mode": "thread",
 "ttft_ms": 206.9, "tokens_sent": 20}</pre></div>
<p>שימו לב למה שיש ולמה שאין. יש <b>client</b> (המזהה של הלקוח), אבל לא המפתח. יש <b>outcome</b>, ובו רואים ש-status 200 לא אומר שהמשתמש קיבל תשובה: הוא התנתק. יש TTFT ומספר טוקנים. אין את תוכן השאלה ואין את התשובה. אלה מידע של משתמשים, ומקומם, אם בכלל, ב-traces עם הרשאות ותקופת שמירה (נושא 22).</p>
<p>הלוג נכתב ב-<b>middleware של ASGI טהור</b>, ולא ב-<code>BaseHTTPMiddleware</code> של Starlette. התיעוד של Starlette מציין שבו שינויים ב-contextvars לא עוברים הלאה, וממליץ על ASGI טהור. ויש גם סיבה שקשורה לשיעור: <code>BaseHTTPMiddleware</code> עוטף את גוף התשובה בזרם משלו, ו-middleware טהור רק צופה בהודעות שעוברות. כך SSE וזיהוי ניתוקים מתנהגים בדיוק כמו בלעדיו.</p>
<h4>Liveness מול readiness</h4>
<ul>
<li><b><code>/healthz</code> (liveness):</b> "התהליך חי". לא בודק כלום מלבד זה שהוא עונה. אם הוא נכשל, הפלטפורמה מפעילה מחדש את ה-container.</li>
<li><b><code>/readyz</code> (readiness):</b> "שלחו לי תנועה". נכשל בזמן עלייה ובזמן <b>draining</b>: כשהשירות מתבקש לרדת, ה-lifespan מסמן not ready, ה-load balancer מפסיק לשלוח בקשות חדשות, והזרמים שכבר רצים מסתיימים.</li>
<li><b>לעולם לא לקרוא למודל מ-probe.</b> probe רץ כל כמה שניות, מכל replica. probe שקורא ל-Haiku הוא חשבונית קבועה, ו-probe שנכשל כשהספק איטי יוציא מהסבב את כל ה-replicas ביחד, בדיוק כשהם הכי נחוצים.</li>
</ul>`,
    },
    {
      kicker: "גרסאות ובדיקת עומס",
      title: "גרסאות של ה-API, ובדיקת עומס שמודדת את מה שחשוב",
      html: `<h4>גרסאות</h4>
<p>ה-API מתחיל ב-<code>/v1</code>. הכלל הוא ששינוי <b>שמוסיף</b> לא שובר: שדה חדש בתשובה, endpoint חדש, או סוג אירוע חדש בזרם (ולכן הלקוח צריך להתעלם מאירועים שהוא לא מכיר, וזה כתוב בחוזה). שינוי ששובר הולך ל-<code>/v2</code>: שינוי שם של שדה, שדה חובה חדש בבקשה, או שינוי במשמעות של <code>done</code>. את <code>/v1</code> מריצים במקביל לתקופה, ומודיעים על הסוף שלו בכותרות: <code>Deprecation</code> (RFC 9745, מרץ 2025) עם התאריך שבו הוא הוצא משימוש, ו-<code>Sunset</code> (RFC 8594) עם התאריך שבו הוא יפסיק לענות. ב-LLM יש עוד ממד: גם החלפת מודל או פרומפט משנה את <b>התוכן</b> של התשובות. השירות מחזיר <code>model</code> בכל תשובה, וה-eval של נושא 23 הוא מה שמחליט אם החלפה כזו מותרת בתוך אותה גרסה.</p>
<h4>בדיקת עומס</h4>
<p><b>locust</b> (גרסה 2.47, אוקטובר 2026) כותבים ב-Python: כל "משתמש" הוא לולאה ששולחת בקשה, קוראת את התשובה, וחושבת רגע. <b>k6</b> של Grafana הוא החלופה הנפוצה, עם תסריטים ב-JavaScript, וחזק במיוחד בהרצות גדולות. בחרנו ב-locust כי כל הקורס ב-Python, וכי קל להוסיף לו מדד משלך.</p>
<ul>
<li><b>TTFT נמדד אצל הלקוח.</b> ה-locustfile רושם מדד בשם TTFT, מרגע השליחה ועד אירוע ה-<code>token</code> הראשון. הוא כולל את כל מה שהמשתמש מרגיש: רשת, אימות, המתנה בתור, וזמן החשיבה של המודל. ה-TTFT שהשירות מדד מול הספק כולל רק את החלק האחרון.</li>
<li><b>מלכודת שנפלנו בה:</b> בהרצה הראשונה, "stream total" יצא 25 מילישניות ב-p50, כשכל תשובה לקחה 1.8 שניות. עם <code>stream=True</code>, הטיימר של locust עוצר כשמגיעות <b>הכותרות</b>. התיקון היה למדוד ביד ולשלוח דרך <code>events.request.fire</code>. מבדיקת עומס שנראית טוב מדי, כדאי לחשוד.</li>
<li><b>percentiles, לא ממוצע.</b> ממוצע של 2 שניות יכול להסתיר 5% של בקשות שלוקחות 20 שניות. p95 ו-p99 הם מה שמשתמשים זוכרים.</li>
<li><b>מודל סגור מול פתוח.</b> משתמש ב-locust שולח את הבקשה הבאה רק אחרי שהקודמת הסתיימה. לכן, כשהשרת מאט, גם קצב השליחה יורד, והבדיקה מסתירה חלק מהבעיה. זה ה-coordinated omission שגיל טנה מדבר עליו. משתמשים אמיתיים מגיעים בקצב שלהם. בסימולטור של השיעור יש מודל פתוח, כדי שתראה את ההבדל.</li>
</ul>`,
    },
  ],

  sims: [
    {
      id: "l26load",
      title: "סימולטור עומס: קצב, זמן שירות, שער ותור",
      lead: "מגדירים כמה בקשות מגיעות בשנייה, כמה זמן כל קריאה למודל לוקחת, וכמה מקומות ותור יש לשער. הסימולטור מריץ 20,000 בקשות ומראה תפוקה, p50/p95/p99, כמה נדחו ולמה, ובדיקה של חוק Little על התוצאה. הגרף למטה מריץ את אותו שירות בעשרה קצבים, כדי שתראה את הברך.",
      tasks: [
        "השאר את ברירות המחדל (8 מקומות, 2 שניות) וחשב לפני שאתה מזיז משהו: מה התפוקה המקסימלית לפי <b>חוק Little</b>? הזז את קצב ההגעה מ-2 ל-6 לשנייה, ובדוק איפה התפוקה נעצרת ומה קורה ל-p95.",
        "קבע קצב של 5 לשנייה (מעל הקיבולת), ושנה את <b>גודל התור</b> מ-0 ל-200. מה קורה לדחיות, ומה קורה ל-p95? איזו הגדרה היית בוחר לשירות שהלקוחות שלו מוותרים אחרי 10 שניות?",
        "קצר את <b>זמן השירות</b> ל-1 שנייה, כאילו עברת למודל מהיר יותר או קיצרת את max_tokens. כמה תפוקה הרווחת, ובכמה זה שקול להכפלת מספר המקומות?",
      ],
    },
    {
      id: "l26cancel",
      title: "ביטול זרם: הלקוח מתנתק, מה קורה למעלה?",
      lead: "שלושה שחקנים: הלקוח, השירות והספק. טוקנים זורמים מהספק לשירות וממנו ללקוח. באמצע לוחצים \"הלקוח סגר את הלשונית\", ורואים מה כל אחד משלושת המימושים של servekit עושה: async, thread ו-leaky. המונים מראים כמה טוקנים נוצרו, כמה הגיעו ללקוח, ועל כמה שילמת לשווא.",
      tasks: [
        "הרץ במצב <b>async</b> ונתק אחרי בערך 10 טוקנים. כמה טוקנים נוצרו אחרי הניתוק?",
        "עבור ל-<b>thread</b>. למה נוצר עוד טוקן אחד אחרי הניתוק, ולמה ה-thread מסומן תפוס עד אז?",
        "עבור ל-<b>leaky</b> ונתק. מה המונה של השירות אומר, ומה המונה של הספק אומר? איזה מהם היית רואה בדשבורד, ואיזה בחשבונית?",
      ],
    },
    {
      id: "l26bucket",
      title: "Token bucket: rate ו-burst",
      lead: "דלי אחד של לקוח אחד. שולחים בקשות ביד, או מפעילים תבנית תנועה, ורואים את מפלס האסימונים, אילו בקשות עברו ואילו נדחו, ואת ה-Retry-After שהלקוח היה מקבל. זה בדיוק מה שתממש בתרגיל 2.",
      tasks: [
        "עם rate=2 ו-burst=5, לחץ \"10 בבת אחת\". כמה עברו? כמה זמן לוקח עד שהדלי מתמלא שוב?",
        "הפעל תנועה <b>יציבה</b> של 3 בקשות בשנייה. מה אחוז הדחיות, ולמה הוא לא משתנה כשמגדילים את burst?",
        "הפעל תנועה <b>בפרצים</b> (8 בקשות כל 4 שניות). איזה ערך של burst מאפשר את כל הפרצים, בלי לשנות את rate? איך זה מתיישב עם קצב ממוצע של 2 בשנייה?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/26-llm-serving",
    intro: "המעבדה בתיקייה labs/26-llm-serving, והשירות עצמו הוא חבילה חדשה, <b>servekit</b>: Company Brain API v0, עם <code>POST /v1/answer</code> ו-<code>POST /v1/answer/stream</code>, שער מקביליות, rate limit לפי מפתח, idempotency, שגיאות problem+json, ולוגים מובנים. כמעט הכל רץ מול <b>servekit.mock</b>, שזה mockllm עם מונה שמראה אם כל זרם הגיע לסוף או נקטע כי הלקוח התנתק. רק תרגיל 8 קורא ל-Haiku 5.5, בבקשה אחת. ברוב התרגילים צריך שני טרמינלים: אחד לשרת המדומה ואחד לשירות.",
    setup: [
      'cd ~/ai-engineer-course-starter && source .venv/bin/activate',
      "uv pip install -r labs/26-llm-serving/requirements.txt   # fastapi, uvicorn, locust, matplotlib",
      "python -m pytest -q tests/test_servekit.py                # environment tests",
      "python -m pytest -q labs/26-llm-serving/tests             # your exercises: all fail at first",
    ],
    tools: [
      "<b>python -m servekit.mock:</b> השרת המדומה עם ספירת זרמים. הדגלים: <code>--ttft</code> (שניות עד הטוקן הראשון), <code>--tps</code> (טוקנים לשנייה), <code>--words</code> (אורך התשובה). ב-<code>GET :8765/__admin/stats</code> יש <code>streams_detail</code> עם <code>completed</code>, <code>aborted</code> ו-<code>text_events_sent</code>.",
      "<b>python -m servekit:</b> השירות על פורט 8000. הדגלים העיקריים: <code>--model</code> (ברירת המחדל היא <code>mock:mock-model</code>), <code>--stream-mode async|thread|leaky</code>, <code>--max-concurrency</code>, <code>--max-queue</code>, <code>--queue-timeout</code>, <code>--rate</code>, <code>--burst</code>, ו-<code>--load-test-keys N</code>. מפתחות הפיתוח: <code>dev-key-alice</code> ו-<code>dev-key-bob</code>.",
      "<b>serve.py --mine limiter,gate,idem:</b> אותו שירות, על הקוד שלך מ-mine.py.",
      "<b>client.py, burst.py, cancel_demo.py, errors_tour.py:</b> לקוח שמודד TTFT, פרץ של בקשות, הוכחת ביטול, וסיור בכל סוגי השגיאות.",
      "<b>locustfile.py ו-sweep.py:</b> בדיקת עומס ב-7 רמות של מקביליות, עם CSV וגרף של p50, p95 ו-TTFT בכל רמה, ומציאת הברך.",
      "<b>mine.py:</b> שלושה חלקים שלך: <code>TokenBucket</code>, <code>ConcurrencyGate.acquire</code> עם <code>retry_after</code>, ו-<code>fingerprint</code> עם <code>IdempotencyStore</code>.",
    ],
    exercises: [
      { id: "ex1", title: "להריץ ולהזרים", text: "הרם את השרת המדומה ואת השירות, ושלח שאלה עם curl -N ועם client.py. בלי -N, curl אוגר את התשובה ומדפיס הכל בסוף. פתח את /docs וראה את הסכמות ואת תגובות השגיאה. ענה: מה ההפרש בין ה-TTFT שהלקוח מדד ל-TTFT שהשירות מדד מול השרת המדומה (שדה ttft_ms באירוע done), ומה יושב בהפרש?", cmd: "python -m servekit.mock                      # terminal 1\npython -m servekit                           # terminal 2\ncurl -N -X POST http://127.0.0.1:8000/v1/answer/stream -H 'Authorization: Bearer dev-key-alice' -H 'Content-Type: application/json' -d '{\"question\": \"How many vacation days do I get in my first year?\"}'\npython labs/26-llm-serving/client.py \"How many vacation days do I get in my first year?\"\npython labs/26-llm-serving/client.py --json \"Who approves admin access to GitHub?\"" },
      { id: "ex2", title: "Token bucket לפי מפתח", text: "ממש את TokenBucket ב-mine.py. הדלי מתחיל מלא (burst אסימונים), מתמלא בקצב rate לשנייה עד burst, ובקשה שנדחית מחזירה (False, (cost − tokens) / rate) בלי לקחת כלום. עלות גדולה מ-burst מחזירה math.inf. כשהבדיקות עוברות, הרץ את השירות על הדלי שלך ושלח 12 בקשות ממפתח אחד (ברירת המחדל: rate=2, burst=5). אחר כך שוב עם --sleep 0.5. למה עכשיו כמעט הכל עובר?", cmd: "python -m pytest -q labs/26-llm-serving/tests/test_ex2_bucket.py\npython labs/26-llm-serving/serve.py --mine limiter        # terminal 2\npython labs/26-llm-serving/burst.py --n 12\npython labs/26-llm-serving/burst.py --n 12 --sleep 0.5" },
      { id: "ex3", title: "שער מקביליות עם תור חסום", text: "ממש את acquire ואת retry_after ב-ConcurrencyGate: עד limit רצות, עד max_queue מחכות לכל היותר queue_timeout שניות, וכל השאר נדחות מיד עם GateRejected(\"queue_full\"). דחייה אחרי המתנה היא GateRejected(\"queue_timeout\"). אסור לעקוף את התור: אם מישהו מחכה, גם בקשה חדשה מחכה. retry_after הוא ceil(avg_service × (waiting + 1) / limit), ולפחות 1. כשהבדיקות עוברות, הרץ עם 4 מקומות ותור של 4, ושלח 20 זרמים במקביל. בהרצה שלנו: 8 הצליחו ו-12 נדחו מיד.", cmd: "python -m pytest -q labs/26-llm-serving/tests/test_ex3_gate.py\npython labs/26-llm-serving/serve.py --mine gate --max-concurrency 4 --max-queue 4 --rate 100 --burst 100 --load-test-keys 64\npython labs/26-llm-serving/burst.py --n 20 --parallel --load-keys" },
      { id: "ex4", title: "להוכיח שניתוק עוצר את הספק", text: "הרץ את השרת המדומה עם תשובה של 5 שניות (100 מילים, 20 טוקנים לשנייה), ואת השירות שלוש פעמים: --stream-mode async, אחר כך thread, ואחר כך leaky. cancel_demo קורא 10 טוקנים, מתנתק, ומשווה את המונים של השירות למונים של השרת המדומה. בהרצה שלנו: async ו-thread סומנו aborted אחרי 11 ו-12 טוקנים, ו-leaky סומן completed עם כל 100, בזמן שהשירות דיווח closed_early. מצא ב-servekit/async_llm.py את השורה שגורמת לדליפה, ותאר את התיקון המינימלי.", cmd: "python -m servekit.mock --ttft 0.2 --tps 20 --words 100     # terminal 1\npython -m servekit --stream-mode async                       # terminal 2, then thread, then leaky\npython labs/26-llm-serving/cancel_demo.py --after 10" },
      { id: "ex5", title: "בדיקת עומס ונקודת הברך", text: "כל תשובה של השרת המדומה לוקחת כ-1.8 שניות (0.3 עד הטוקן הראשון, ועוד 60 טוקנים ב-40 לשנייה), והשער מרשה 8 במקביל. לפני ההרצה, חשב עם חוק Little את התפוקה המקסימלית ואת הרמה שבה תופיע הברך. sweep.py מריץ locust ב-1 עד 64 משתמשים, 20 שניות לכל רמה, וכותב את results/sweep.csv ואת results/sweep.png. השווה לחישוב שלך: איפה התפוקה נעצרה? מה קרה ל-TTFT ב-16 משתמשים, ולמה? (אצלנו: הברך ב-8, תקרה של כ-4 בשנייה, ו-TTFT שקפץ מ-0.33 ל-1.8 שניות.)", cmd: "python -m servekit.mock --ttft 0.3 --tps 40 --words 60                                     # terminal 1\npython -m servekit --max-concurrency 8 --max-queue 16 --rate 100 --burst 100 --load-test-keys 128   # terminal 2\npython labs/26-llm-serving/sweep.py" },
      { id: "ex6", title: "Idempotency-Key", text: "ממש את fingerprint (sha256 של JSON קנוני: sort_keys, separators=(',', ':'), ensure_ascii=False) ואת IdempotencyStore: חדש מחזיר new, גוף אחר מחזיר mismatch (422), בקשה שעוד רצה מחזירה in_progress (409), ובקשה שהסתיימה מחזירה replay עם התשובה השמורה. רשומות פגות אחרי ttl, ו-abandon שוכח מפתח. הרץ את השירות על הקוד שלך ושלח את אותה בקשה פעמיים: בשנייה צריך להופיע Idempotent-Replayed: true, והמונה requests של השרת המדומה לא עולה. ענה: למה השירות לא שומר תשובת 502?", cmd: "python -m pytest -q labs/26-llm-serving/tests/test_ex6_idempotency.py\npython labs/26-llm-serving/serve.py --mine idem\ncurl -i -X POST http://127.0.0.1:8000/v1/answer -H 'Authorization: Bearer dev-key-alice' -H 'Content-Type: application/json' -H 'Idempotency-Key: order-42' -d '{\"question\": \"Where is the Haifa office?\"}'" },
      { id: "ex7", title: "חוזה השגיאות", text: "הרץ את הסיור. הוא מפעיל שמונה שגיאות ומדפיס כל אחת כמו שהלקוח רואה אותה: בלי מפתח, גוף לא תקין, נתיב לא קיים, שיטה לא נכונה, Idempotency-Key עם גוף אחר, ספק עמוס (529), ספק שדוחה (400), ושגיאה באמצע זרם. הוא מדליק את התקלות בשרת המדומה דרך /__admin/config ומכבה אותן בסוף. ענה: על איזה שדה הלקוח עושה switch? אילו מהשגיאות שווה לנסות שוב, ואחרי כמה זמן? ולמה האחרונה מגיעה כאירוע error ולא כ-status?", cmd: "python labs/26-llm-serving/errors_tour.py" },
      { id: "ex8", title: "בקשה חיה מול Haiku", text: "הרץ את השירות מול Claude Haiku 5.5, ושלח בקשה אחת בסטרימינג. השווה את ה-TTFT של הלקוח ל-TTFT שהשירות מדד מול Anthropic, ואת שניהם ל-0.3 שניות של השרת המדומה. אחר כך קרא את שורת הלוג של הבקשה בטרמינל של השירות: האם יש בה כל מה שצריך כדי לחקור תלונה, בלי המפתח ובלי תוכן השאלה? עלות: כ-1,000 טוקני קלט ו-200 טוקני פלט, בערך $0.0002.", cmd: "python -m servekit --model anthropic:claude-haiku-5-5        # terminal 2, reads ANTHROPIC_API_KEY from .env\npython labs/26-llm-serving/client.py \"How many vacation days do I get in my first year?\"" },
    ],
  },

  quiz: [
    { q: "endpoint מוגדר כ-async def, ובתוכו קוראים ל-llm.complete() של llmkit (httpx סינכרוני). הקריאה לוקחת 3 שניות. מה קורה לבקשות אחרות שמגיעות לאותו worker באותו זמן?", options: ["הן רצות במקביל, כי זה async", "הן מחכות: הקריאה הסינכרונית חוסמת את ה-event loop, ואפילו /healthz לא עונה", "FastAPI מעביר את הקריאה ל-threadpool אוטומטית", "הן מקבלות 429"], correct: 1, explain: "בתוך <b>async def</b> אין threadpool אוטומטי. קריאה בלי await מחזיקה את ה-thread היחיד של הלולאה. הפתרונות: endpoint רגיל עם def, <b>to_thread</b>, או לקוח <b>async</b> אמיתי." },
    { q: "השער מרשה 10 קריאות במקביל, וכל קריאה למודל לוקחת 2.5 שניות. מה התפוקה המקסימלית?", options: ["25 בשנייה", "10 בשנייה", "4 בשנייה", "תלוי בגודל התור"], correct: 2, explain: "לפי <b>חוק Little</b>, λ = L / W = 10 / 2.5 = 4 בשנייה. התור לא מוסיף תפוקה, הוא רק מוסיף <b>המתנה</b>." },
    { q: "למה התור לפני השער חייב להיות חסום?", options: ["כדי לחסוך בזיכרון", "כי תור לא חסום לא אומר אף פעם לא: ההמתנה גדלה, הלקוחות מגיעים ל-timeout ושולחים שוב, והשרת עונה על בקשות שאף אחד כבר לא מחכה להן", "כי asyncio לא תומך בתור לא חסום", "כדי שה-p50 יהיה נמוך"], correct: 1, explain: "תור לא חסום רק <b>דוחה</b> את הכישלון. goodput, התשובות שמגיעות בזמן, צונח, בזמן שה-throughput נראה תקין. <b>load shedding</b> מוקדם וזול שומר על latency סביר למי שהתקבל." },
    { q: "במצב leaky, השירות מדווח closed_early: 1 אחרי שהלקוח התנתק. מה המונה של השרת המדומה מראה?", options: ["aborted: 1", "completed: 1, עם כל הטוקנים: הספק המשיך לייצר עד הסוף", "שום דבר, הבקשה לא הגיעה אליו", "failures: 1"], correct: 1, explain: "משימת הרקע לא בוטלה, ולכן היא קראה את כל הזרם לתור שאף אחד לא קרא. <b>המדדים של השירות משקרים</b>, והאמת היא אצל ה-upstream, ובסוף בחשבונית." },
    { q: "השרת כבר שלח 200 ו-15 טוקנים, ואז הספק מחזיר overloaded_error. מה הלקוח מקבל?", options: ["status 503", "status 200 שמשתנה ל-503", "אירוע error בתוך הזרם, עם גוף problem+json, ואחריו סוף הזרם", "שום דבר, הזרם נתקע"], correct: 2, explain: "אחרי שהכותרות נשלחו, <b>אי אפשר לשנות את ה-status</b>. החוזה מגדיר <b>event: error</b> עם אותו type, והלקוח מציג את הטקסט החלקי כלא שלם." },
    { q: "לקוח שולח Idempotency-Key: k1 עם שאלה A, מקבל תשובה, ואחר כך שולח שוב k1 עם שאלה B. מה צריך לחזור לפי הטיוטה של IETF?", options: ["התשובה של A", "תשובה חדשה ל-B", "422: אותו מפתח עם גוף אחר", "409"], correct: 2, explain: "טביעת האצבע של הגוף לא תואמת, וזו <b>422</b>. 409 שמור למקרה שבו הבקשה הראשונה <b>עוד רצה</b>. replay רק כשהגוף זהה." },
    { q: "מה ההבדל בין דחייה של queue_full לדחייה של queue_timeout, מבחינת הלקוח?", options: ["אין הבדל, שתיהן 429", "queue_full מגיעה מיד, queue_timeout מגיעה רק אחרי שהלקוח כבר חיכה את כל ה-timeout", "queue_timeout מחזירה 504", "queue_full לא שולחת Retry-After"], correct: 1, explain: "שתיהן 429 עם Retry-After, אבל בבדיקת העומס שלנו <b>queue_full</b> לקחה 4 מילישניות ו-<b>queue_timeout</b> לקחה 2 שניות. סירוב מאוחר הוא סירוב יקר." },
    { q: "ב-locust, עם self.client.post(..., stream=True), מה מודד הטיימר המובנה?", options: ["את הזמן עד סוף הזרם", "את הזמן עד שהכותרות הגיעו", "את TTFT", "את הזמן עד ה-meta"], correct: 1, explain: "עם <b>stream=True</b>, הבקשה חוזרת כשהכותרות מגיעות. אצלנו זה יצא 25 מילישניות במקום 1.8 שניות. לכן TTFT וזמן כולל נמדדים ביד ונרשמים דרך <b>events.request.fire</b>." },
    { q: "מה לא צריך לקרות ב-/readyz?", options: ["לבדוק שהשירות לא ב-draining", "להחזיר 503 בזמן עלייה", "לשלוח בקשה קטנה ל-Haiku כדי לוודא שהספק עונה", "להחזיר את שם המודל"], correct: 2, explain: "probe רץ כל כמה שניות מכל replica. קריאה למודל היא <b>חשבונית קבועה</b>, ו-probe שנכשל כשהספק איטי מוציא את <b>כל</b> ה-replicas מהסבב ביחד." },
    { q: "לקוח צריך להחליט מה לעשות עם שגיאה. על איזה שדה ב-problem+json הוא אמור לעשות switch?", options: ["detail", "title", "type", "status בלבד"], correct: 2, explain: "<b>type</b> הוא המזהה היציב של סוג הבעיה. detail משתנה בכל מקרה ומיועד לבני אדם, ו-status לבד לא מבחין, למשל, בין rate-limited ל-overloaded, ששניהם 429." },
  ],

  summary: {
    points: [
      { t: "מה מיוחד בשירות LLM", b: "בקשות של שניות ולא מילישניות, עלות לכל בקשה, ספק עם מגבלות ותקלות משלו, ומשתמש שמחכה למילה הראשונה. מכאן: מזרימים, מגבילים מקביליות, מגבילים כל לקוח, נותנים deadline לכל בקשה, ומסרבים מוקדם ובזול, לפי סדר קבוע: אימות, rate limit, idempotency, שער, ורק אז המודל." },
      { t: "async נכון", b: "קריאה סינכרונית בתוך async def מקפיאה את כל ה-worker. אפשר להשתמש ב-endpoint רגיל או ב-threadpool (עד 40 threads כברירת מחדל ב-anyio, וביטול שמחכה ל-thread), או בלקוח async אמיתי. AsyncLLM משתמש מחדש ב-adapters של llmkit, ובלי retries בתוך השרת." },
      { t: "SSE", b: "תשובת HTTP עם text/event-stream ואירועים meta, token, done ו-error. צריך Cache-Control: no-cache, X-Accel-Buffering: no ו-keep-alive. אחרי שה-200 נשלח, שגיאה מגיעה כאירוע error. WebSocket מתאים רק כשהלקוח צריך לדבר תוך כדי, כמו בקול או בהפרעה." },
      { t: "ביטול", b: "ניתוק של הלקוח חייב לסגור את החיבור לספק. Starlette מזהה ניתוק בזרם ומבטל את ה-generator, ו-async with של httpx סוגר את החיבור. משימת רקע שלא קשורה לבקשה דולפת: השירות נראה תקין והספק ממשיך לייצר ולחייב. ב-endpoint רגיל, Starlette לא מבטל, וצריך לבדוק ניתוק בעצמך." },
      { t: "Backpressure", b: "Semaphore מגביל את מה שרץ, תור חסום סופג גלים קצרים, queue timeout מגביל המתנה, וכל השאר נדחה מיד עם 429 ו-Retry-After. תור לא חסום רק דוחה את הקריסה, ודחייה אחרי המתנה יקרה יותר מדחייה מיידית." },
      { t: "חוק Little והברך", b: "L = λ × W. עם 8 מקומות ושתי שניות לקריאה, התקרה היא כ-4 בשנייה. מעל הברך, כל משתמש נוסף קונה רק המתנה, ואחר כך דחיות. בבדיקת עומס מודדים percentiles ו-TTFT מצד הלקוח, וחושדים בתוצאות שנראות טוב מדי." },
      { t: "Rate limit ו-idempotency", b: "Token bucket לפי מפתח מאפשר פרץ עד burst וקצב יציב של rate, ומחזיר זמן המתנה מדויק. בשירות עם כמה replicas, הדלי עובר ל-Redis או ל-gateway. Idempotency-Key מונע תשלום כפול: replay על אותו גוף, 409 כשהבקשה עוד רצה, 422 על גוף אחר, scope לפי לקוח, ובלי לשמור כישלונות." },
      { t: "חוזה ותפעול", b: "כל שגיאה היא problem+json עם type יציב, בלי הודעות של הספק, בלי stack traces ובלי קלט המשתמש. לכל בקשה יש request id ושורת לוג JSON עם client ו-outcome, בלי מפתחות ובלי תוכן. liveness ו-readiness הם שני דברים שונים, ו-probe לא קורא למודל. שינוי שמוסיף נשאר ב-v1, ושינוי ששובר עובר ל-v2 עם Deprecation ו-Sunset." },
    ],
    glossary: [
      ["ASGI", "הממשק בין שרת Python אסינכרוני (uvicorn) לאפליקציה (FastAPI, Starlette): הודעות receive ו-send."],
      ["Event loop", "הלולאה שמריצה את כל המשימות של worker על thread אחד, ומחליפה ביניהן בכל await."],
      ["Threadpool", "מאגר threads להרצת קוד חוסם מתוך קוד async. ב-anyio מוגבל ל-40 כברירת מחדל."],
      ["SSE", "Server-Sent Events: זרם אירועים מהשרת ללקוח בתוך תשובת HTTP אחת, עם text/event-stream."],
      ["TTFT", "Time to first token: הזמן מהשליחה ועד הטוקן הראשון. נמדד אצל הלקוח כדי לכלול הכל."],
      ["Backpressure", "דחיפת עומס חזרה אל השולח (המתנה מוגבלת או סירוב), במקום לספוג אותו בזיכרון."],
      ["Load shedding", "דחייה מוקדמת וזולה של בקשות כשהשירות בקיבולת, כדי לשמור על latency למי שהתקבל."],
      ["Concurrency gate", "Semaphore עם תור חסום ו-queue timeout, שמגביל כמה קריאות למודל רצות בבת אחת."],
      ["Goodput", "החלק מהתפוקה שמצליח ומגיע ללקוח בזמן שעוד שימושי לו."],
      ["Little's law", "L = λ × W: מספר הבקשות במערכת שווה לקצב ההגעה כפול הזמן שכל אחת נשארת."],
      ["Knee", "נקודת הברך: רמת העומס שמעליה עוד עומס מוסיף המתנה ולא תפוקה."],
      ["Token bucket", "אלגוריתם rate limit: דלי עם burst אסימונים שמתמלא בקצב rate, ובקשה לוקחת אסימון."],
      ["Retry-After", "כותרת שאומרת ללקוח כמה שניות לחכות לפני ניסיון נוסף. מגיעה עם 429 ו-503."],
      ["Idempotency-Key", "כותרת שמאפשרת לשלוח שוב POST בבטחה: השרת מזהה ניסיון חוזר ומחזיר את התשובה השמורה."],
      ["problem+json", "פורמט השגיאות של RFC 9457: type, title, status, detail, instance, ושדות הרחבה."],
      ["Readiness", "בדיקה שאומרת אם לשלוח לשירות תנועה. נכשלת בעלייה וב-draining. שונה מ-liveness."],
    ],
    reading: [
      { title: "FastAPI: Server-Sent Events", url: "https://fastapi.tiangolo.com/tutorial/server-sent-events/", note: "התמיכה המובנית ב-SSE, מגרסה 0.135." },
      { title: "FastAPI: Concurrency and async / await", url: "https://fastapi.tiangolo.com/async/", note: "def מול async def, ומתי קוד רץ ב-threadpool." },
      { title: "AnyIO: Working with threads", url: "https://anyio.readthedocs.io/en/stable/threads.html", note: "מגבלת 40 ה-threads, ולמה המתנה ל-thread מוגנת מביטול." },
      { title: "Amazon Builders' Library: Using load shedding to avoid overload", url: "https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload", note: "goodput, ולמה לדחות מוקדם." },
      { title: "RFC 9457: Problem Details for HTTP APIs", url: "https://www.rfc-editor.org/rfc/rfc9457.html", note: "הפורמט של חוזה השגיאות." },
      { title: "IETF draft: The Idempotency-Key HTTP Header Field (08)", url: "https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header", note: "400, 409 ו-422, טביעת אצבע ותפוגה." },
      { title: "IETF draft: RateLimit header fields for HTTP (11)", url: "https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers", note: "RateLimit-Policy ו-RateLimit, והיחס ל-Retry-After." },
      { title: "RFC 9745: The Deprecation HTTP Response Header Field", url: "https://www.rfc-editor.org/rfc/rfc9745.html", note: "הודעה על הוצאה משימוש של גרסה, יחד עם Sunset." },
      { title: "Starlette: Middleware", url: "https://www.starlette.io/middleware/", note: "המגבלה של BaseHTTPMiddleware, ואיך כותבים middleware של ASGI טהור." },
      { title: "Locust documentation", url: "https://docs.locust.io/en/stable/", note: "הכלי של תרגיל 5, כולל event hooks למדדים משלך." },
    ],
  },
};
