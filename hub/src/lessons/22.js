// Lesson 22 — AI Observability and Tracing.
window.LESSONS = window.LESSONS || {};
window.LESSONS["22"] = {
  n: 22,
  title: "AI Observability and Tracing",
  he: "traces, עלות, latency ופורנזיקה של כשלים",
  hours: "כשעתיים וחצי שיעור, כחמש שעות מעבדה",

  goals: [
    "להבין למה מערכת LLM צריכה <b>tracing</b> ולא רק לוגים ומטריקות: תשובה שגויה היא כשל שקט שמחזיר 200, והדרך היחידה להבין אותו היא לראות את כל השלבים של אותה בקשה, עם הקלטים והפלטים שלהם.",
    "להכיר את המודל של <b>OpenTelemetry</b>: trace, span, היררכיית אב וילד, attributes, events, status ו-links, ואיך context עובר בין שלבים בתוך התהליך ובין שירותים.",
    "לעבוד לפי ה-<b>GenAI semantic conventions</b>: שמות spans, ערכי gen_ai.operation.name, ה-attributes של קריאה למודל, של שליפה ושל כלי, ולדעת שהתקן עדיין בסטטוס Development ושמות בו משתנים.",
    "להחליט <b>מה לרשום</b>: טוקנים, עלות, latency, TTFT, retries, cache, גרסת מודל ופרומפט, תוצאות שליפה עם ציונים, וקריאות לכלים, ולהבין את הפשרה של <b>content capture</b>: פרטיות מול היכולת לשחזר.",
    "לבנות צינור טלמטריה אמיתי: SDK, processors, exporters ו-Collector, עם <b>sampling</b> (head מול tail) ו-<b>redaction</b> של מידע אישי לפני שהוא יוצא מהתהליך.",
    "להגדיר <b>SLOs</b> למערכת LLM (זמינות, p95 latency, עלות לבקשה, שיעור עיגון), לחשב <b>burn rate</b>, ולהבין למה התראות טובות משתמשות בשני חלונות זמן.",
    "לבצע <b>פורנזיקה</b> של תשובה שגויה מתוך traces בלבד: להשוות trace רע לטוב, להבדיל בין איטי לשגוי, ולאשר את סיבת השורש ב-<b>replay</b> של אותה בקשה בדיוק.",
    "לחבר traces ל-<b>משוב משתמשים</b> ול-<b>evals</b>: trace עם משוב שלילי הופך למקרה בדיקה בנושא 23.",
  ],
  connects: "בנושא 2 llmkit למד למדוד עלות, latency ו-TTFT לכל קריאה, ובנושא 4 ראית את שדות ה-prompt cache. בנושא 9 בנית RAG עם ragkit, ובנושא 19 שמת \"Tracing\" כקופסה בארכיטקטורה של Company Brain. עכשיו הקופסה הופכת לקוד: חבילה חדשה, <b>obskit</b>, עוטפת את llmkit ואת ragkit מבחוץ ומייצרת spans לפי התקן. זה הבסיס לשלב 4 של <b>Company Brain</b> (deployed, observed, evaluated, secured): ב<b>נושא 23</b> ה-traces עם משוב שלילי יהפכו ל-eval set, וה-groundedness שמחושב כאן על כל תשובה יהיה מדד רציף בפרודקשן. את אותם spans תוכל להוסיף לכל workflow וסוכן שתבנה (נושאים 14 עד 18).",

  intro: {
    animation: "l22wf",
    animationTitle: "Waterfall של trace: בקשה אחת עוברת במערכת",
    animationGuide: `<p><b>מה רואים כאן:</b> עובד שואל את שירות התשובות של Acme "מי אחראי על מדיניות ימי המחלה, ומה המייל שלו?". הבקשה עוברת בכמה שלבים: מטמון, שליפה, קריאה למודל שמחליט להפעיל כלי, הכלי עצמו, וקריאה שנייה למודל שכותבת את התשובה. כל שלב כזה הוא <b>span</b>, וכל ה-spans של הבקשה יחד הם <b>trace</b> אחד.</p>
<p><b>איך לקרוא את ה-waterfall:</b> כל שורה היא span. <b>ההזחה</b> מראה מי קרא למי: כל ה-spans מוזחים מתחת ל-span הראשי <code>invoke_workflow acme_answer</code>, כי הוא האב שלהם. <b>הציר האופקי הוא זמן</b> מתחילת הבקשה: הפס של כל span מתחיל כשהשלב התחיל ונגמר כשהוא נגמר. פס ארוך הוא שלב איטי, ופסים שלא חופפים רצו בזה אחר זה. הצבע מסמן את סוג ה-span: מודל, שליפה, כלי, מטמון או סוכן.</p>
<p><b>החלונית שמתחת</b> מציגה את ה-<b>attributes</b> של ה-span הנוכחי, ברגע שהם נרשמים. שים לב שחלק נרשמים בתחילת ה-span (המודל, max_tokens, גרסת הפרומפט) וחלק רק בסופו (טוקנים, עלות, סיבת עצירה), כי רק אז הם ידועים. בקריאה הראשונה למודל תראה גם <b>event</b> בשם retry: הספק החזיר 529, llmkit ניסה שוב, וזה נרשם כנקודה בזמן על אותו span, לא כ-span נפרד.</p>
<p><b>איך לעבוד איתה:</b> האנימציה מתחילה מהבקשה הריקה ובונה את ה-trace צעד אחרי צעד. השהה, ועבור עם החצים. בסוף, לחץ על כל שורה כדי לראות שוב את ה-attributes שלה, והשווה: איפה הלך רוב הזמן, ואיפה רוב הכסף?</p>`,
    videos: [
      {
        title: "Inside the LLM Call: GenAI Observability with OpenTelemetry",
        who: "OpenTelemetry blog, James Newton-King, מאי 2026",
        part: "המאמר כולו",
        minutes: 15,
        url: "https://opentelemetry.io/blog/2026/genai-observability/",
        required: true,
        kind: "מאמר",
        why: "הסבר עדכני מהפרויקט עצמו: איך ה-GenAI conventions מתעדים קריאה למודל, למה content capture כבוי כברירת מחדל, ואיך נראה עץ spans של קריאות LLM וכלים בכלי צפייה.",
      },
      {
        title: "Semantic conventions for generative client AI spans",
        who: "OpenTelemetry, ריפו semantic-conventions-genai",
        part: "Inference, Retrievals, Execute tool span, ו-Capturing instructions, inputs, and outputs",
        minutes: 30,
        url: "https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md",
        required: true,
        kind: "תיעוד",
        why: "התקן שהמעבדה עוקבת אחריו. ב-2026 ה-GenAI conventions עברו מהריפו הראשי לריפו נפרד, והדף הישן ב-opentelemetry.io מפנה לשם. קרא את טבלאות ה-attributes ואת רמות הדרישה (Required, Recommended, Opt-In).",
      },
      {
        title: "Alerting on SLOs",
        who: "Google SRE Workbook, פרק 5",
        part: "מ-\"Alert on burn rate\" ועד \"Multiwindow, multi-burn-rate alerts\"",
        minutes: 25,
        url: "https://sre.google/workbook/alerting-on-slos/",
        required: true,
        kind: "תיעוד",
        why: "המקור של burn rate ושל התראות עם שני חלונות, שתממש בתרגיל 6. הפרק בונה את הגישה בהדרגה, משש גרסאות חלשות ועד הגרסה המומלצת, ומסביר את החיסרון של כל אחת.",
      },
      {
        title: "Evaluating AI Agents",
        who: "DeepLearning.AI עם Arize AI",
        part: "השיעורים על tracing ועל ויזואליזציה של traces",
        minutes: 40,
        url: "https://www.deeplearning.ai/short-courses/evaluating-ai-agents/",
        required: false,
        kind: "קורס",
        why: "קורס וידאו קצר שמראה traces של סוכן בכלי של Arize, ואיך משתמשים בהם כבסיס ל-evals. גשר טוב לנושא 23.",
      },
      {
        title: "Phoenix: Overview: Tracing",
        who: "Arize Phoenix docs",
        part: "Overview, ואחריו ה-Advanced Setup",
        minutes: 15,
        url: "https://arize.com/docs/phoenix/tracing/llm-traces",
        required: false,
        kind: "תיעוד",
        why: "הכלי שתריץ ב-Docker בתרגיל 2. Phoenix מקבל traces ב-OTLP, ומגרסה 15.10 ממיר attributes של gen_ai.* לפורמט שלו, כך שה-spans של obskit מוצגים בתצוגת LLM מלאה.",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "למה מערכת LLM צריכה traces",
      html: `<p class="big">בשירות רגיל, רוב הכשלים רועשים: exception, קוד 500, timeout. מערכת LLM נכשלת הרבה פעמים <b>בשקט</b>. היא מחזירה 200, תשובה מנוסחת היטב, וציטוט שנראה אמין, והתשובה פשוט שגויה.</p>
<p>קח את מה שתראה במעבדה: עובד שואל כמה ימי חופשה אפשר להעביר לשנה הבאה, ומקבל "עד 3 ימים, פגים ב-28 בפברואר". זו התשובה של מדיניות 2024. מדיניות 2026 אומרת 5 ימים עד 31 במרץ. מה השתבש? אולי המודל התעלם מהכלל "העדף את המקור המאוחר". אולי השליפה בכלל לא הביאה את מסמך 2026. אולי השאלה הגיעה מהמטמון. אולי הקריאה למודל נכשלה ומודל גיבוי ענה מהזיכרון. מהלוג "request 200, 1.1s" אי אפשר לדעת אף אחד מאלה.</p>
<p>לכן במערכות LLM שלושת עמודי ה-observability מקבלים משקל שונה. <b>מטריקות</b> (latency, שיעור שגיאות, עלות) אומרות שמשהו לא בסדר ומתי. <b>לוגים</b> אומרים מה קרה בנקודה אחת. <b>Traces</b> מראים את כל המסלול של בקשה אחת, שלב אחרי שלב, עם הקלטים והפלטים של כל שלב, וזה מה שצריך כדי לענות על השאלה "למה התשובה הזו יצאה ככה".</p>
<h4>מה מיוחד ב-LLM</h4>
<ul>
<li><b>אי-דטרמיניזם:</b> אותה בקשה יכולה להחזיר תשובה אחרת. בלי לרשום מה בדיוק נשלח, אי אפשר לשחזר.</li>
<li><b>עלות לכל בקשה:</b> כל קריאה עולה כסף לפי טוקנים, ובקשה אחת יכולה לעשות קריאה אחת או עשרים. עלות היא מדד תפעולי כמו latency.</li>
<li><b>שרשראות ארוכות:</b> RAG, כלים וסוכנים הופכים בקשה אחת לעשרות שלבים, וכל שלב יכול להיות סיבת השורש.</li>
<li><b>האיכות היא חלק מהזמינות:</b> תשובה שגויה גרועה מתשובה שלא הגיעה, ולכן מודדים גם עיגון, לא רק הצלחה.</li>
</ul>
<div class="callout">המטרה של השיעור: שכל משוב "התשובה שגויה" יוביל, בתוך כמה דקות, ל-trace אחד, ל-span אחד בתוכו, ולסיבה אחת שאפשר לתקן.</div>`,
    },
    {
      kicker: "המודל",
      title: "Trace, span, attributes, events: המודל של OpenTelemetry",
      html: `<p>OpenTelemetry (או OTel) הוא תקן פתוח, ואוסף SDKs, לטלמטריה: traces, מטריקות ולוגים. הוא לא כלי צפייה. הוא השפה המשותפת שהקוד שלך מדבר, וכל כלי (Phoenix, Langfuse, Datadog, Honeycomb, Jaeger) יודע לקרוא אותה. בגלל זה מחליפים כלי בלי לגעת בקוד.</p>
<h4>אבני הבניין</h4>
<ul>
<li><b>Trace:</b> כל מה שקרה בבקשה אחת. מזוהה ב-<code>trace_id</code> של 32 תווי hex, שכל ה-spans שלו חולקים.</li>
<li><b>Span:</b> פעולה אחת עם התחלה וסוף: קריאה למודל, שליפה, כלי. יש לו <code>span_id</code>, ו-<code>parent_id</code> שמצביע על ה-span שקרא לו. ה-span בלי אב הוא ה-<b>root</b>, ובדרך כלל הוא מייצג את הבקשה כולה.</li>
<li><b>Attributes:</b> זוגות של מפתח וערך על span: <code>gen_ai.request.model = claude-haiku-5-5</code>. הערכים הם מחרוזות, מספרים, בוליאנים או רשימות שלהם. זה המקום של כל מה שתרצה לחפש ולקבץ לפיו.</li>
<li><b>Events:</b> נקודות בזמן בתוך span, עם attributes משלהן. retry, exception, ה-chunk הראשון בסטרים. Event מתאים לדבר שקרה <b>בתוך</b> פעולה, לא לפעולה בפני עצמה.</li>
<li><b>Status:</b> UNSET (ברירת המחדל), OK או ERROR עם הודעה. לפי כללי ה-Recording Errors, span שנכשל מקבל ERROR ו-attribute בשם <code>error.type</code>.</li>
<li><b>Kind:</b> CLIENT לקריאה לשירות אחר (כמו API של מודל), INTERNAL לפעולה בתוך התהליך, SERVER לבקשה נכנסת.</li>
<li><b>Links:</b> קשר בין spans שאינו אב וילד. ב-replay, למשל, ה-span החדש מקושר ל-span המקורי, אבל הוא trace חדש.</li>
</ul>
<h4>איך span יודע מי האב שלו</h4>
<p>ה-SDK שומר "span נוכחי" ב-context (ב-Python, ב-contextvars). כשפותחים span בתוך <code>with</code> של span אחר, החדש הופך לילד שלו אוטומטית. בין שירותים, ה-context עובר ב-header של HTTP בשם <code>traceparent</code> (תקן W3C Trace Context), ולכן trace יכול לעבור מה-API שלך לשירות השליפה ובחזרה.</p>
<div class="example"><b>אותו trace, כמו שה-JSONL exporter של obskit שומר אותו (מקוצר)</b><pre dir="ltr">{"trace_id": "63249c84...", "span_id": "9f1e...", "parent_id": "b07a...",
 "name": "chat mock-model", "kind": "CLIENT", "duration_ms": 1148.0, "status": "OK",
 "attributes": {"gen_ai.operation.name": "chat", "gen_ai.usage.input_tokens": 1190, ...},
 "events": []}</pre></div>`,
    },
    {
      kicker: "התקן",
      title: "GenAI semantic conventions: שפה משותפת לקריאות LLM",
      html: `<p>OTel מגדיר איך שולחים span. הוא לא מגדיר איך לקרוא ל-attribute של "כמה טוקני קלט". אם כל צוות היה ממציא שם, אף כלי לא היה יודע להציג טוקנים. את זה פותרות ה-<b>semantic conventions</b>: מוסכמות לשמות של spans ו-attributes לכל תחום. לבינה יוצרת יש קבוצה משלה, ה-GenAI conventions.</p>
<h4>הסטטוס, נכון לנובמבר 2026</h4>
<ul>
<li>הן עדיין בסטטוס <b>Development</b>. כלומר, שמות יכולים להשתנות בלי תקופת מעבר.</li>
<li>במהלך 2026 הן <b>עברו לריפו נפרד</b>, <code>open-telemetry/semantic-conventions-genai</code>. הדף הישן באתר של OpenTelemetry רק מפנה לשם.</li>
<li>שינויים אמיתיים מהתקופה האחרונה: <code>gen_ai.system</code> הוחלף ב-<code>gen_ai.provider.name</code>, ו-<code>gen_ai.usage.cache_creation.input_tokens</code> שונה ל-<code>gen_ai.usage.cache_write.input_tokens</code>. חבילת ה-Python <code>opentelemetry-semantic-conventions</code> בגרסה 0.66b2 עדיין מכילה את השם הישן. זו בדיוק הסיבה ש-obskit מגדיר את כל השמות בקובץ אחד, <code>semconv.py</code>.</li>
</ul>
<h4>שמות של spans ושל פעולות</h4>
<p>לכל span יש <code>gen_ai.operation.name</code>, והשם שלו נגזר ממנו:</p>
<ul>
<li><b>קריאה למודל:</b> <code>chat claude-haiku-5-5</code>, כלומר <code>{operation} {request.model}</code>, ו-kind מסוג CLIENT.</li>
<li><b>שליפה:</b> <code>retrieval acme-kb</code>, כלומר <code>{operation} {data_source.id}</code>.</li>
<li><b>כלי:</b> <code>execute_tool lookup_employee</code>, kind מסוג INTERNAL.</li>
<li><b>סוכן ו-workflow:</b> <code>invoke_agent {name}</code> ו-<code>invoke_workflow {name}</code>. יש גם <code>embeddings</code>, <code>plan</code>, <code>create_agent</code> ופעולות זיכרון.</li>
</ul>
<p>השמות האלה חשובים יותר ממה שנראה. Phoenix, Datadog ו-Honeycomb מזהים span של LLM לפי ה-attributes של <code>gen_ai.*</code>, ומציגים אותו בתצוגה מיוחדת: הודעות, טוקנים, עלות. span עם שמות שהמצאת יוצג כ-span רגיל וריק. Datadog, למשל, מתעד במפורש שהוא <b>מוחק</b> spans שאין עליהם אף attribute של <code>gen_ai.*</code>.</p>
<div class="callout">כלל עבודה: עקוב אחרי התקן היכן שיש לו attribute, והוסף namespace משלך (ב-obskit: <code>obskit.*</code>) לכל מה שאין לו. עלות, גרסת אינדקס, פגיעה במטמון תשובות: את כל אלה כל צוות רושם, ואין להם עדיין שם בתקן.</div>`,
    },
    {
      kicker: "קריאה למודל",
      title: "מה רושמים על span של קריאה למודל",
      html: `<p>זה ה-span החשוב ביותר, כי הוא היקר, האיטי והפחות צפוי. אלה ה-attributes ש-<code>InstrumentedLLM</code> רושם, מחולקים לפי מתי הם ידועים:</p>
<h4>בתחילת הקריאה</h4>
<ul>
<li><b><code>gen_ai.operation.name</code>, <code>gen_ai.provider.name</code></b> (Required בתקן), ו-<code>gen_ai.request.model</code>.</li>
<li><b><code>gen_ai.request.max_tokens</code>, <code>gen_ai.request.stream</code></b>, ו-<code>gen_ai.output.type = json</code> כשיש סכמה (נושא 3).</li>
<li><b><code>gen_ai.prompt.name</code> ו-<code>gen_ai.prompt.version</code></b>. שינוי פרומפט הוא deploy לכל דבר, וכשהאיכות יורדת, השאלה הראשונה היא "איזו גרסה ענתה". בלי ה-attribute הזה אין לזה תשובה.</li>
<li><b><code>server.address</code>, <code>server.port</code></b>: לאיזה endpoint פנינו. חשוב כשיש gateway או כמה אזורים.</li>
</ul>
<h4>בסוף הקריאה</h4>
<ul>
<li><b><code>gen_ai.usage.input_tokens</code></b>: לפי התקן, כולל טוקנים מה-cache. <code>gen_ai.usage.cache_read.input_tokens</code> ו-<code>cache_write.input_tokens</code> לחוד, ו-<code>gen_ai.usage.output_tokens</code>. llmkit כבר מנרמל את זה כך (נושא 4).</li>
<li><b><code>gen_ai.response.model</code>, <code>gen_ai.response.id</code></b>: המודל שענה בפועל (לפעמים גרסה מדויקת יותר) ו-request id של הספק, שהוא מה שהתמיכה של הספק תבקש ממך.</li>
<li><b><code>gen_ai.response.finish_reasons</code></b>: <code>["stop"]</code>, <code>["length"]</code>, <code>["tool_call"]</code>. תשובה שנקטעה ב-max_tokens נראית רגילה עד שמסתכלים על זה.</li>
<li><b><code>gen_ai.response.time_to_first_chunk</code></b>: TTFT בשניות, בקריאת סטרים.</li>
<li><b><code>obskit.cost_usd</code> ו-<code>obskit.attempts</code></b>: עלות לפי <code>llmkit/pricing.py</code>, ומספר הניסיונות.</li>
</ul>
<h4>retry הוא event, לא span</h4>
<p>התקן מגדיר את ה-span כ"קריאה לוגית" למודל. llmkit מבצע retries בתוך הקריאה הזו (נושא 2), ולכן obskit רושם כל ניסיון חוזר כ-<b>event</b> בשם <code>retry</code>, עם מספר הניסיון, סוג השגיאה וזמן ההמתנה. התוצאה: סערת 429 נראית ב-trace כ-span אחד ארוך עם שלוש נקודות אדומות עליו. אם הקריאה נכשלה סופית, ה-span מקבל status ERROR, <code>error.type</code> (למשל <code>rate_limit_error</code> או <code>timeout</code>), ו-event מסוג exception.</p>
<div class="example"><b>שימוש</b><pre dir="ltr">llm = InstrumentedLLM(LLM("anthropic:claude-haiku-5-5"),
                      prompt_name="rag-answer", prompt_version="v3")
result = llm.complete(req)       # same API, same ChatResult, plus a span</pre></div>`,
    },
    {
      kicker: "פרטיות",
      title: "Content capture: לרשום את הפרומפט, או לא",
      html: `<p>ה-attributes הכי שימושיים לפורנזיקה הם גם המסוכנים ביותר: <code>gen_ai.system_instructions</code>, <code>gen_ai.input.messages</code> ו-<code>gen_ai.output.messages</code>, כלומר הטקסט המלא שנשלח למודל ושחזר ממנו. אותו דבר ל-<code>gen_ai.tool.call.arguments</code>, <code>gen_ai.tool.call.result</code> ו-<code>gen_ai.retrieval.query.text</code>. הטקסט הזה מכיל את מה שהעובד כתב, כולל שמות, מספרי ת"ז ופרטים רפואיים, ואת המסמכים שנשלפו, כולל מסמכים חסויים.</p>
<p>לכן התקן מגדיר אותם כ-<b>Opt-In</b>, ומחייב כל instrumentation לתת הגדרה שמפעילה אותם. אם ההגדרה היא משתנה סביבה, השם שלו הוא <code>OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT</code>, עם ארבעה ערכים:</p>
<ul>
<li><b><code>NO_CONTENT</code></b>: ברירת המחדל. רק מטא-דאטה: מודל, טוקנים, זמנים.</li>
<li><b><code>SPAN_ONLY</code></b>: התוכן נרשם כ-attributes על ה-spans.</li>
<li><b><code>EVENT_ONLY</code></b> ו-<b><code>SPAN_AND_EVENT</code></b>: התוכן נרשם כ-events (לוגים), או בשני המקומות.</li>
</ul>
<p>ערך לא מוכר נחשב <code>NO_CONTENT</code>. על spans, התקן אומר לשמור את ההודעות כמחרוזת JSON כשהשפה לא תומכת ב-attributes מובנים, וזה מה ש-obskit עושה. יש גם אפשרות להעלות את התוכן לאחסון חיצוני ולשמור על ה-span רק הפניה (<code>gen_ai.input.messages_ref</code>), כך שאפשר לתת לתוכן הרשאות ותקופת שמירה משלו.</p>
<h4>הפשרה האמיתית</h4>
<p>בלי תוכן, trace אומר לך <b>ש</b>הקריאה הייתה איטית או נכשלה. הוא לא אומר <b>מה</b> נשאל ומה נשלף, ולכן אי אפשר לשחזר אותה. תראה את זה בתרגיל 7: ה-replay בונה את הבקשה מחדש מתוך <code>gen_ai.input.messages</code>, ובלעדיו הוא פשוט נכשל עם הודעה ברורה. ההחלטה הנפוצה בפרודקשן היא לא "הכול או כלום" אלא שכבות:</p>
<ol class="ladder">
<li><b>מטא-דאטה תמיד</b><span>מודל, טוקנים, עלות, זמנים, status, ids ו-ציונים של מסמכים. אין בהם תוכן של משתמש.</span></li>
<li><b>תוכן עם redaction</b><span>הטקסט נשמר אחרי הסרה של מידע אישי (תרגיל 4), בתוך התהליך, לפני שהוא יוצא.</span></li>
<li><b>תוכן מלא, בגישה מוגבלת</b><span>רק לחלק מה-traces, למשל אלה עם משוב שלילי, באחסון עם הרשאות ותקופת שמירה קצרה.</span></li>
</ol>`,
    },
    {
      kicker: "RAG, כלים וסוכנים",
      title: "spans של שליפה, כלי וסוכן: מה ההבדל בין trace שימושי לחסר תועלת",
      html: `<p>ברוב התשובות השגויות של מערכת RAG, המודל עשה בדיוק מה שביקשו ממנו, עם המקורות הלא נכונים. לכן span של שליפה שרק אומר "לקח 40 ms" כמעט חסר ערך. מה שצריך לרשום:</p>
<h4>Retrieval</h4>
<ul>
<li><b><code>gen_ai.data_source.id</code> ו-<code>gen_ai.retrieval.top_k</code></b>: מאיפה ביקשנו וכמה.</li>
<li><b><code>gen_ai.retrieval.documents</code></b> (Opt-In): רשימה של <code>{"id", "score"}</code> לכל מסמך שחזר. בזה רואים אם המסמך הנכון בכלל הגיע, ובאיזה מקום.</li>
<li><b>מה שהתקן לא מכסה, ומציל חקירות:</b> <code>obskit.retrieval.index_version</code> (מתי האינדקס נבנה), ה-replica שענה, ה-effective_date והגרסה של כל מסמך (<code>obskit.retrieval.results</code>), והפילטר שהופעל. בתרגיל 5 אחת התשובות השגויות נפתרת בדיוק בעזרת גרסת האינדקס.</li>
</ul>
<h4>Execute tool</h4>
<ul>
<li><b><code>gen_ai.tool.name</code>, <code>gen_ai.tool.call.id</code>, <code>gen_ai.tool.type</code></b>. ה-call id מחבר בין הבקשה של המודל לכלי לבין ההפעלה עצמה.</li>
<li><b><code>gen_ai.tool.call.arguments</code> ו-<code>gen_ai.tool.call.result</code></b> (Opt-In): עם מה הכלי נקרא, ומה הוא החזיר. כלי שמחזיר "not found" בשקט הוא סיבת שורש נפוצה.</li>
</ul>
<h4>Agent ו-workflow</h4>
<p>ה-root של בקשה הוא <code>invoke_workflow</code> (רצף שלבים קבוע) או <code>invoke_agent</code> (מודל שמחליט מה לעשות). עליו obskit רושם את מה שמתאר את הבקשה כולה: גרסת הפרומפט, משתמש (מזוהה, לא מייל), <code>gen_ai.conversation.id</code> לשיחה מרובת סבבים, סוג התשובה (מודל, מטמון, גיבוי), ותוצאת בדיקת העיגון. אצל סוכן, כל צעד בלולאה (קריאה למודל, כלי, קריאה למודל) הוא span ילד, וה-waterfall מראה את הלולאה עצמה.</p>
<div class="example"><b>ב-acme_app.py</b><pre dir="ltr">with agent_span("acme_answer", workflow=True) as root:
    hits = InstrumentedRetriever(index, "acme-kb", index_version="2026-10-30").search(q, k=3)
    with tool_span("lookup_employee", call_id="call_dir_1", arguments={"name": owner}) as t:
        person = lookup_employee(owner)
        record_tool_result(t, person)
    res = llm.complete(build_request(q, hits))      # InstrumentedLLM: a child span
    root.set_attribute("obskit.grounded", grounded)</pre></div>`,
    },
    {
      kicker: "מדדים",
      title: "Latency, TTFT ועלות: ממוצע הוא שקר",
      html: `<p>מתוך ה-spans מחשבים את המדדים שלוח הבקרה מציג. שלושה כללים:</p>
<h4>אחוזונים, לא ממוצעים</h4>
<p>זמני תגובה של LLM הם התפלגות עם זנב ארוך: רוב הבקשות לוקחות שנייה, ומעטות לוקחות שמונה, בגלל retry, timeout, או תשובה ארוכה במיוחד. ממוצע מערבב את הכול ומסתיר את הזנב. <b>p50</b> (חציון) אומר מה המשתמש הרגיל חווה, ו-<b>p95</b> אומר מה חווה אחד מכל עשרים. ב-12 ה-traces של המעבדה ה-p50 הוא כ-1.8 שניות וה-p95 כ-5.4 שניות. הפער הזה כולו מגיע מ-retries ומ-timeout, וזה מה שה-trace מסביר. בתרגיל 3 תחשב אחוזון עם אינטרפולציה לינארית: עם 12 ערכים, p95 נופל בין הערך ה-11 ל-12.</p>
<h4>לפי סוג span, ולפי שלב</h4>
<p>p95 של הבקשה כולה אומר שיש בעיה. p95 לפי סוג span (llm, retrieval, tool, cache) אומר איפה. ב-RAG טיפוסי השליפה לוקחת מילישניות והמודל לוקח כמעט את כל הזמן, ולכן שיפור בשליפה לא ישפיע על latency, ושינוי מודל או prompt caching כן. מדד נפרד וחשוב הוא <b>TTFT</b>: בממשק עם סטרימינג, הוא הזמן שהמשתמש מחכה לפני שהוא רואה משהו, ולכן הוא חשוב יותר מהזמן הכולל.</p>
<h4>עלות לכל trace</h4>
<p>עלות של קריאה בודדת מטעה, כי בקשה אחת יכולה לעשות כמה קריאות: retry ששילם על טוקנים, מודל גיבוי, סוכן שעשה שש איטרציות. מה שמעניין את העסק הוא <b>עלות לבקשה</b>: סכום העלות של כל ה-spans ב-trace. ממנה מחשבים ממוצע, p95 ועלות יומית. ומכיוון שעלות לא נמצאת בתקן, היא נרשמת בזמן הקריאה לפי מחירון שאתה מתחזק. מחיר שהשתנה אצל הספק לא משנה את העבר ב-traces, וזה דווקא טוב: אתה רואה כמה שילמת אז.</p>
<div class="example"><b>trace_stats.py על 12 ה-traces של הבוקר</b><pre dir="ltr">latency by span type (ms):
  llm        n=12    p50=   1804.1  p95=   5432.4  max=   7527.2  errors=2
  retrieval  n=11    p50=      0.3  p95=      0.6  max=      0.8  errors=0
cost: total $0.000965   mean/trace $0.000080   p95/trace $0.000211
tokens: input 15,143  output 347  cache read 8,561 (57% of input)</pre></div>`,
    },
    {
      kicker: "Instrumentation",
      title: "איך מוסיפים spans: מבחוץ, אוטומטית, או ביד",
      html: `<p>יש שלוש דרכים להכניס spans לקוד, ובפרויקט אמיתי משתמשים בשילוב.</p>
<h4>עטיפה מבחוץ (מה ש-obskit עושה)</h4>
<p><code>InstrumentedLLM</code> הוא wrapper, לא subclass: הוא מקבל כל אובייקט עם <code>complete()</code>, מעביר אליו את הקריאה, ופותח span סביבה. כל attribute אחר עובר לאובייקט העטוף. למה לא subclass של <code>LLM</code>? כי אז כל שינוי פנימי ב-llmkit (למשל tool calling בנושא 14) עלול לשבור את ה-instrumentation, וכי ה-wrapper עובד גם על ה-<code>ExtractiveAnswerer</code> של ragkit או על כל client אחר. retries נתפסים דרך ה-hook הקיים של llmkit, <code>on_retry</code>, שה-wrapper משרשר ומחזיר למצבו בסוף הקריאה.</p>
<h4>Auto-instrumentation</h4>
<p>ספריות שעוטפות SDKs של ספקים בלי שינוי בקוד שלך. <b>OpenLLMetry</b> של Traceloop (רישיון Apache-2.0) מתקינים עם <code>pip install traceloop-sdk</code> ומפעילים עם <code>Traceloop.init()</code>, והיא עוטפת בין השאר את ה-SDKs של Anthropic ו-OpenAI. ל-OpenTelemetry עצמו יש instrumentations ל-GenAI בפרויקט ה-contrib. היתרון: אפס קוד. החיסרון: הן עוטפות SDK, ו-llmkit מדבר HTTP ישירות, אז הן לא יראו אותו. והן לא יודעות כלום על השלבים שלך: מטמון, replica, בדיקת עיגון.</p>
<h4>spans ידניים</h4>
<p>לשלבים שרק אתה מכיר: <code>span("cache.lookup", type="cache")</code>, או הדקורטור <code>@traced("guard")</code>. התקן עצמו ממליץ למפתחים לתעד ביד קריאות לכלים שה-instrumentation האוטומטי לא מכסה.</p>
<div class="callout"><b>מה לא לעשות:</b> לפתוח span לכל פונקציה. trace עם 400 spans קשה לקריאה כמו לוג בלי trace בכלל, ויקר לשמור. span צריך לייצג שלב שאפשר לשאול עליו שאלה: "האם השלב הזה איטי, נכשל או החזיר משהו מוזר?".</div>`,
    },
    {
      kicker: "הצינור",
      title: "מה-span ועד המסך: SDK, processors, exporters ו-Collector",
      html: `<p>כשה-span נגמר, הוא עובר בצינור. כדאי להכיר את החלקים, כי כל החלטה של sampling ו-redaction יושבת במקום מסוים בצינור הזה.</p>
<ol class="ladder">
<li><b>TracerProvider</b><span>האובייקט המרכזי של ה-SDK. יש לו <b>Resource</b>, כלומר attributes של השירות כולו (<code>service.name</code>, <code>service.version</code>, <code>deployment.environment</code>), ו-<b>Sampler</b> שמחליט אם לרשום trace.</span></li>
<li><b>SpanProcessor</b><span>מקבל כל span בהתחלה (on_start) ובסוף (on_end). <code>SimpleSpanProcessor</code> מייצא מיד, ומתאים לפיתוח ולבדיקות. <code>BatchSpanProcessor</code> אוסף ושולח ברקע, ומתאים לפרודקשן כי הוא לא מעכב את הבקשה. ה-<code>RedactingSpanProcessor</code> של obskit יושב כאן: הוא מקבל את ה-span, יוצר ממנו עותק מנוקה, ומעביר אותו הלאה. הוא חייב ליצור עותק, כי span שהסתיים הוא קריאה בלבד.</span></li>
<li><b>SpanExporter</b><span>שולח: <code>ConsoleSpanExporter</code> מדפיס, <code>OTLPSpanExporter</code> שולח ב-OTLP (הפרוטוקול של OTel, ב-HTTP או gRPC), ו-<code>JsonlSpanExporter</code> של obskit כותב לקובץ.</span></li>
<li><b>Collector</b><span>שירות נפרד (אופציונלי) שמקבל OTLP מכל השירותים, מעבד ושולח לכלי אחד או יותר. בו שמים tail sampling, redaction נוסף, וניתוב: למשל spans של LLM ל-Phoenix והכול ל-Datadog.</span></li>
</ol>
<div class="example"><b>setup_tracing ב-obskit</b><pre dir="ltr">tr = setup_tracing("acme-answer",
        jsonl="results/traces.jsonl",                   # local file
        otlp_endpoint="http://localhost:6006/v1/traces", # Phoenix
        capture_content=True, redact=True, sample_ratio=1.0)
...
tr.shutdown()    # flush: spans still in a batch are lost without it</pre></div>
<p>שים לב לשורה האחרונה. סקריפט שמסתיים בלי <code>shutdown()</code> או <code>force_flush()</code> מאבד את ה-spans שעדיין חיכו ב-batch. זה הבאג הנפוץ ביותר ב"הוספתי tracing ולא רואים כלום".</p>`,
    },
    {
      kicker: "Sampling",
      title: "לא שומרים הכול: head sampling מול tail sampling",
      html: `<p>trace של LLM עם תוכן יכול לשקול עשרות קילובייטים: ב-12 ה-traces של המעבדה, עם system prompt של כ-5,000 תווים בכל קריאה, הקובץ שוקל כ-125KB. מאה אלף בקשות ביום הן גיגה-בייטים, וכלי צפייה מסחריים גובים לפי נפח. לכן בדרך כלל לא שומרים כל trace. השאלה היא <b>מתי</b> מחליטים.</p>
<h4>Head sampling</h4>
<p>ההחלטה מתקבלת כשה-root מתחיל, לפי ה-trace id: <code>ParentBased(TraceIdRatioBased(0.1))</code> שומר 10% מה-traces, וכל ה-spans באותו trace מקבלים אותה החלטה (זה תפקיד ה-ParentBased). זה זול ופשוט, ויש לו חיסרון אחד גדול: ההחלטה מתקבלת <b>לפני</b> שמישהו יודע אם הבקשה תיכשל. עם 10% sampling ושיעור שגיאות של 0.5%, תשמור רק עשירית מהשגיאות, בדיוק ה-traces שבשבילם יש tracing.</p>
<h4>Tail sampling</h4>
<p>ההחלטה מתקבלת <b>אחרי</b> שכל ה-trace הגיע, ב-Collector. ב-collector-contrib יש processor בשם <code>tail_sampling</code> (בסטטוס beta), עם policies כמו: שמור כל trace עם status ERROR, שמור כל trace מעל 5 שניות, ומהשאר שמור 10%. זה בדיוק הקובץ <code>collector/otel-collector.yaml</code> במעבדה. המחיר: ה-Collector צריך להחזיק traces בזיכרון עד שהוא מחליט (<code>decision_wait</code>, ברירת מחדל 30 שניות, ו-<code>num_traces</code>, ברירת מחדל 50,000), וכל ה-spans של trace חייבים להגיע לאותו Collector.</p>
<h4>ומה עם התשובות השגויות?</h4>
<p>תשובה שגויה היא לא ERROR ולא איטית. tail sampling לפי status לא ישמור אותה. שתי דרכים לטפל בזה: לסמן על ה-root attribute כמו <code>obskit.grounded=false</code> ולהוסיף policy שתשמור אותו, או לשמור תמיד מטא-דאטה מלא (זול) ותוכן רק ל-traces שנבחרו. ומשוב שלילי מגיע דקות אחרי התשובה, כש-tail sampling כבר החליט, ולכן מערכות רבות שומרות את כל ה-traces לזמן קצר ומוחקות אחר כך.</p>`,
    },
    {
      kicker: "Redaction",
      title: "מידע אישי לא יוצא מהתהליך",
      html: `<p>ברגע שמפעילים content capture, כל ת"ז, טלפון ומייל שעובד כתב בשאלה נמצאים ב-span. אם ה-spans נשלחים לשירות ענן, המידע עבר גבול אמון (נושא 19). לכן redaction צריך לקרות <b>בתוך התהליך</b>, לפני ה-exporter: אם ה-span יצא מהמכונה לא נקי, כבר מאוחר מדי.</p>
<h4>מה תממש בתרגיל 4</h4>
<ul>
<li><b>מיילים</b> הופכים ל-<code>[EMAIL]</code>.</li>
<li><b>טלפונים ישראליים</b> הופכים ל-<code>[PHONE]</code>: נייד 05X ועוד 7 ספרות, קווי 0 עם ספרה אחת ו-7 ספרות, 07X, עם או בלי מקפים ורווחים, וגם בפורמט <code>+972</code>.</li>
<li><b>מספרי ת"ז</b> הופכים ל-<code>[IL_ID]</code>: בדיוק 9 ספרות, ש<b>עוברות את ספרת הביקורת</b>. מכפילים את הספרות ב-1, 2, 1, 2 וכן הלאה משמאל, מחברים את הספרות של כל מכפלה, והסכום חייב להתחלק ב-10. למשל, 123456782 תקין ו-123456789 לא.</li>
</ul>
<p>למה לבדוק ספרת ביקורת? כי בלי זה כל מספר הזמנה, סכום או מזהה של 9 ספרות יוסתר, וה-traces יאבדו מידע שימושי. המחיר אמיתי: ת"ז שהוקלדה עם טעות לא תוסתר. מערכת שמחמירה יותר תוותר על הבדיקה ותסתיר כל רצף של 9 ספרות, וזה מה ש-<code>redact_text(..., validate_ids=False)</code> וגם הקונפיגורציה של ה-Collector עושים.</p>
<h4>שתי שכבות</h4>
<p>השכבה הראשונה היא ה-<code>RedactingSpanProcessor</code> בתוך כל שירות. השנייה היא ה-processor בשם <code>redaction</code> ב-Collector (גם הוא beta), עם <code>blocked_values</code> של regex. הוא תופס שירות ששכח, אבל הוא לא מחליף את הראשונה: הנתונים כבר עברו ברשת עד אליו. ושימו לב ל-attributes שהם JSON: <code>gen_ai.input.messages</code> הוא מחרוזת, ומנקים אותו כטקסט. התחליפים לא מכילים מירכאות, ולכן ה-JSON נשאר תקין.</p>
<div class="callout">Redaction לפי regex הוא רשת ביטחון, לא הבטחה. שם של אדם, כתובת או אבחנה רפואית לא יתפסו. לכן הוא בא יחד עם מדיניות: מה בכלל מותר ללכוד, מי רשאי לראות traces, וכמה זמן הם נשמרים.</div>`,
    },
    {
      kicker: "כלים",
      title: "כלי observability ל-LLM: מה כל אחד עושה (נבדק בנובמבר 2026)",
      html: `<p>כל הכלים כאן מקבלים OpenTelemetry, ולכן ה-spans של obskit מגיעים לכולם בלי שינוי קוד, רק עם endpoint אחר. ההבדלים הם בתצוגה, ב-evals המובנים, באירוח ובמחיר.</p>
<h4>Arize Phoenix (קוד פתוח)</h4>
<p>רץ מקומית ב-Docker: <code>docker run -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest</code>. ה-UI וה-OTLP ב-HTTP בפורט 6006 (<code>/v1/traces</code>), ו-gRPC ב-4317. Phoenix משתמש בתקן משלו, OpenInference, ומגרסה 15.10 (מאי 2026) הוא ממיר attributes של <code>gen_ai.*</code> לפורמט שלו כשהם מגיעים: הודעות, כלים, מסמכים וטוקנים. הגרסה האחרונה ב-PyPI כשהשיעור נכתב: 21.0.0. אפשר גם <code>pip install arize-phoenix</code> ו-<code>phoenix serve</code>, בלי Docker.</p>
<h4>Langfuse (קוד פתוח, אפשר self-hosted)</h4>
<p>גרסה 4. מריצים מקומית עם <code>git clone</code> של הריפו ו-<code>docker compose up</code>, וה-UI בפורט 3000. הוא מריץ כמה שירותים (Postgres, ClickHouse, Redis, אחסון אובייקטים), והתיעוד ממליץ על 4 ליבות ו-16GB לשרת. traces מגיעים ל-<code>/api/public/otel</code> ב-OTLP על HTTP בלבד (gRPC לא נתמך), עם Basic auth של המפתח הציבורי והסודי. Langfuse ממפה <code>gen_ai.request.model</code>, <code>gen_ai.usage.*</code> ועוד, ויש לו גם ניהול פרומפטים ו-evals.</p>
<h4>OpenLLMetry (Traceloop)</h4>
<p>לא כלי צפייה, אלא ספריית auto-instrumentation בקוד פתוח מעל OpenTelemetry. שולחת לכל backend.</p>
<h4>Datadog</h4>
<p>המוצר (שבתיעוד העדכני נקרא Agent Observability) מקבל OTLP ישירות, בלי Agent של Datadog, לפי GenAI conventions מגרסה 1.37 ומעלה, עם header בשם <code>dd-otlp-source=llmobs</code>. spans בלי attributes של <code>gen_ai.*</code> נמחקים, ויש עיכוב של 3 עד 5 דקות עד שהם מופיעים.</p>
<h4>Honeycomb</h4>
<p>לפי פוסט מאפריל 2026: מזהה spans עם <code>gen_ai.operation.name</code> ומציג להם אייקון ופאנל של attributes של GenAI, ומאפשר שאילתות ו-heatmaps על טוקנים ומשך, ו-SLOs על הנתונים האלה. הם מציינים שה-instrumentation האוטומטי מכסה את התקן רק חלקית, וממליצים להוסיף attributes ביד.</p>
<div class="callout">ההמלצה למעבדה: Phoenix, כי הוא קונטיינר אחד. אם אין Docker, ה-viewer של obskit מייצר waterfall ב-HTML מקובץ ה-JSONL, בלי שום תלות.</div>`,
    },
    {
      kicker: "SLOs",
      title: "SLOs למערכת LLM: מה נחשב בקשה טובה",
      html: `<p><b>SLI</b> (Service Level Indicator) הוא יחס: כמה בקשות היו טובות מתוך הבקשות שנבדקו. <b>SLO</b> הוא יעד ל-SLI על פני תקופה: "99.5% מהבקשות מצליחות, ב-30 יום מתגלגלים". ההפרש מ-100% הוא <b>תקציב השגיאות</b>: עם יעד של 99.5%, מותר ל-0.5% מהבקשות להיכשל. כל עוד נשאר תקציב, אפשר לשחרר שינויים. כשהוא נגמר, עוצרים ומייצבים.</p>
<h4>ארבעה SLIs למערכת כמו Company Brain</h4>
<ul>
<li><b>זמינות:</b> בקשה טובה היא בקשה שה-root שלה לא הסתיים ב-ERROR. retry שהצליח בסוף הוא לא כשל של בקשה.</li>
<li><b>Latency:</b> בקשה טובה היא בקשה מוצלחת שהסתיימה בתוך 8 שניות. שים לב לניסוח: "p95 מתחת ל-8 שניות" הופך ל"95% מהבקשות מתחת ל-8 שניות". זה אותו דבר, אבל בצורה הזו אפשר לספור בקשות טובות ורעות ולחשב תקציב. בקשה שנכשלה <b>לא נספרת</b> כאן (היא שייכת לזמינות), אחרת כשל מהיר היה משפר את ה-latency.</li>
<li><b>עיגון (groundedness):</b> בקשה טובה היא תשובה שעברה בדיקת עיגון, כלומר מצטטת מקור שבאמת נשלף. תשובות שלא נבדקו (שגיאה, מטמון, תשובה קבועה) לא נספרות. זה ה-SLI שאין לשירותים רגילים, והוא תופס את מה שזמינות לא רואה: בקשה שהצליחה טכנית וענתה שטויות.</li>
<li><b>עלות לבקשה:</b> בדרך כלל לא SLO אלא תקציב: עלות יומית והתראה על קפיצה. לולאת סוכן שלא נעצרת, או פרומפט שגדל פי 3 אחרי deploy, נראים קודם כל כאן.</li>
</ul>
<h4>לוח הבקרה</h4>
<p>לכל SLI: הערך הנוכחי, כמה תקציב נשאר, ו-burn rate (השקופית הבאה). ולצידם, המדדים שמסבירים: p50 ו-p95 לפי סוג span, TTFT, שיעור פגיעה ב-prompt cache, שיעור retries, שיעור תשובות גיבוי, ועלות לבקשה לפי גרסת פרומפט ומודל. כל גרף צריך לאפשר לחיצה שמובילה ל-traces עצמם: גרף שאי אפשר לרדת ממנו ל-trace הוא קישוט.</p>`,
    },
    {
      kicker: "התראות",
      title: "Burn rate והתראות עם שני חלונות",
      html: `<p><b>Burn rate</b> הוא קצב הצריכה של תקציב השגיאות ביחס ל-SLO: שיעור הבקשות הרעות בחלון, חלקי התקציב. עם יעד של 99.5% (תקציב 0.5%), שעה שבה 2% מהבקשות נכשלו היא burn rate של 4: בקצב הזה, תקציב של 30 יום נגמר אחרי 7.5 ימים. burn rate של 1 גומר את התקציב בדיוק בסוף התקופה.</p>
<h4>למה לא פשוט "התראה כששיעור השגיאות מעל X"</h4>
<p>חלון קצר (5 דקות) מתריע על כל קפיצה רגעית ומעייף את התורן. חלון ארוך (יום) מתריע מאוחר מדי, וממשיך להתריע שעות אחרי שהבעיה נפתרה. הפתרון של ה-SRE workbook של Google: התראה נורית רק כש<b>שני</b> חלונות עוברים את הסף יחד. החלון הארוך מבטיח שהבעיה משמעותית, והקצר (1/12 מהארוך) מבטיח שהיא עדיין קורית עכשיו, ולכן ההתראה נכבית כמה דקות אחרי התיקון.</p>
<ol class="ladder">
<li><b>page: 14.4x על 1h ו-5m</b><span>2% מתקציב של 30 יום נשרפו בשעה אחת. מישהו צריך לקום.</span></li>
<li><b>page: 6x על 6h ו-30m</b><span>5% מהתקציב בשש שעות.</span></li>
<li class="danger"><b>ticket: 3x על 24h ו-2h</b><span>שריפה איטית. אין צורך להעיר מישהו, אבל צריך לטפל השבוע. (בטבלה של ה-workbook זה 1x על 3d ו-6h; במעבדה יש רק יום אחד של נתונים, ולכן הכלל של 24h/2h מהקונפיגורציה לדוגמה באותו פרק.)</span></li>
</ol>
<h4>מה תראה בתרגיל 6</h4>
<p>יום סינתטי עם שתי תקלות. עומס אצל הספק במשך 30 דקות מקפיץ את שיעור השגיאות ל-25%, ומוציא page אחרי כ-20 דקות: החלון של שעה צריך לצבור מספיק בקשות רעות. פריסה של פרומפט גרוע מורידה את העיגון ל-86% למשך שבע וחצי שעות, ולא מעירה אף אחד. היא מוציאה ticket. ויש עוד משהו שלמדת מהנתונים: בלילה, כשיש מעט בקשות, בקשה רעה אחת יכולה להקפיץ burn rate. התראות אמיתיות דורשות גם מספר מינימלי של בקשות בחלון.</p>`,
    },
    {
      kicker: "פורנזיקה",
      title: "מהמשוב לסיבת השורש: שיטה לחקירת תשובה שגויה",
      html: `<p>משתמש כתב "התשובה שגויה". כך עוברים ממנו לסיבה, בלי לנחש:</p>
<ol class="ladder">
<li><b>מצא את ה-trace</b><span>המשוב חייב לשאת trace_id. בשירות של המעבדה, כל משוב ב-<code>feedback.jsonl</code> מחובר ל-trace. בלי החיבור הזה, אתה מחפש לפי זמן ומשתמש, ומקווה.</span></li>
<li><b>סווג: שגוי, איטי, או לא ענה</b><span>"התשובה נכונה אבל איטית" היא בעיית latency, לא איכות, ומטופלת אחרת לגמרי. "לא מצא" היא לא תמיד בעיית שליפה.</span></li>
<li><b>קרא את ה-root</b><span>סוג התשובה (מודל, מטמון, גיבוי, קבועה), עיגון, גרסת פרומפט, events של fallback. לפעמים זה כבר פותר: תשובה מסוג fallback_model לא עברה במקורות בכלל.</span></li>
<li><b>לך מלמטה למעלה</b><span>קודם השליפה: האם המסמך הנכון חזר, באיזה ציון ובאיזה מקום, ומאיזה אינדקס? אחר כך הכלים: מה הם החזירו? אחר כך המודל: status, ניסיונות, סיבת עצירה, טוקנים, ו-<code>gen_ai.input.messages</code>: מה הוא קיבל בפועל?</span></li>
<li><b>השווה ל-trace טוב</b><span>זו הטכניקה החזקה ביותר. trace תקין לשאלה דומה מראה מה "נורמלי": גרסת אינדקס, מספר טוקני קלט, cache read. ההבדל הוא בדרך כלל הסיבה. קלט של 56 טוקנים במקום 1,150 אומר שהמקורות לא היו בפרומפט.</span></li>
<li><b>אשר ב-replay</b><span>שלח את הבקשה המוקלטת שוב. אם התשובה זהה, הבעיה בקלט (מקורות, פרומפט). אם היא נכונה כשהתשתית תקינה, הבעיה הייתה בתשתית (timeout, rate limit).</span></li>
<li><b>תעד ותהפוך לבדיקה</b><span>סיבה, הראיות (אילו attributes), תיקון, ומקרה eval חדש שימנע רגרסיה.</span></li>
</ol>
<div class="callout"><b>מלכודת נפוצה:</b> ה-trace האיטי ביותר בסט הוא לא בהכרח החשוב. בסט של תרגיל 5 יש traces איטיים עם תשובות נכונות ובלי משוב, ו-trace עם משוב שלילי שהבעיה שלו היא רק latency. "איטי" ו"שגוי" הן שתי שאלות שונות, וה-trace עונה על שתיהן בנפרד.</div>`,
    },
    {
      kicker: "Replay ו-evals",
      title: "Replay, משוב ו-evals: לסגור את הלולאה",
      html: `<p><b>Replay</b> הוא שליחה מחדש של קריאה מוקלטת, עם אותם קלטים בדיוק. <code>obskit.replay.request_from_span</code> בונה <code>ChatRequest</code> מתוך <code>gen_ai.system_instructions</code>, <code>gen_ai.input.messages</code> ו-<code>gen_ai.request.max_tokens</code>, ו-<code>replay()</code> שולח אותו בתוך span חדש עם <b>link</b> ל-span המקורי, כך שבכלי הצפייה רואים שהם קשורים.</p>
<h4>מה replay מוכיח</h4>
<ul>
<li><b>אותה תשובה בדיוק:</b> הבעיה דטרמיניסטית ונמצאת בקלט. בתרגיל 7 תראה את זה בתשובה על החופשה: המקורות היו של 2024, והמודל ענה נכון לפי מה שקיבל.</li>
<li><b>תשובה נכונה, כשהמקור נכשל:</b> הפרומפט והמקורות היו בסדר, והכשל היה בתשתית. זה מה שתראה ב-trace של ה-timeout.</li>
<li><b>החלפה של רכיב אחד:</b> replay עם שליפה חדשה (<code>--fresh-retrieval</code>) בודק את התיקון לפני שמשחררים אותו. ובמקרה של החופשה הוא מגלה עוד בעיה: גם האינדקס התקין מחזיר את מסמך 2024 לצד 2026.</li>
</ul>
<p>מול mockllm, replay מדויק. מול מודל אמיתי, אותה בקשה יכולה להחזיר נוסח אחר, ולכן משווים משמעות ולא בתים, או מריצים כמה פעמים. temperature נמוכה עוזרת, אבל לא מבטיחה זהות.</p>
<h4>מ-trace ל-eval</h4>
<p>כל trace עם משוב שלילי ועם סיבה מאושרת הוא מקרה בדיקה מוכן: יש לו שאלה, את מה שנשלף, את התשובה השגויה, ואת מה שהמשתמש אמר שנכון. בנושא 23 תהפוך אותם ל-eval set, ותריץ אותו בכל שינוי. בכיוון ההפוך, ה-evals רצים גם על traces מפרודקשן: בדיקת העיגון ש-acme_app.py רושמת כ-<code>obskit.grounded</code> היא eval פשוט שרץ על כל תשובה, ומזין את ה-SLO של עיגון.</p>
<div class="callout">החיבור שחייב להיות: trace_id על כל תשובה שהמשתמש רואה (למשל בכפתור המשוב), ו-trace_id בכל רשומת משוב. בלי זה, observability ו-evals הן שתי מערכות שלא מדברות.</div>`,
    },
    {
      kicker: "מלכודות",
      title: "איפה צוותים נופלים",
      html: `<ul>
<li><b>לרשום רק latency וסטטוס.</b> בלי מסמכים שנשלפו, גרסת פרומפט וגרסת אינדקס, ה-trace יגיד שהכול תקין בדיוק כשהתשובה שגויה.</li>
<li><b>להמציא שמות של attributes.</b> הכלים לא יזהו את ה-spans כ-LLM, ו-Datadog פשוט ימחק אותם. עקוב אחרי התקן, והוסף namespace משלך רק למה שחסר בו.</li>
<li><b>לשכוח שהתקן בסטטוס Development.</b> שמות משתנים. רכז אותם בקובץ אחד, ובדוק את ה-changelog כשמעדכנים.</li>
<li><b>content capture בלי redaction ובלי מדיניות.</b> traces הופכים למאגר הגדול ביותר של מידע אישי בחברה, עם ההרשאות של כלי ניטור.</li>
<li><b>redaction רק ב-Collector.</b> המידע כבר עבר ברשת. הוא שכבה שנייה, לא ראשונה.</li>
<li><b>head sampling נמוך בלי tail sampling.</b> תזרוק את רוב השגיאות, בדיוק את מה שחיפשת.</li>
<li><b>span לכל retry, או אף רישום של retries.</b> הראשון מנפח את ה-trace, השני מסתיר סערת rate limit. event על ה-span הלוגי.</li>
<li><b>לא לקרוא ל-shutdown או flush.</b> ה-batch האחרון הולך לאיבוד, ונראה כאילו ה-tracing לא עובד.</li>
<li><b>ממוצעים בלוח הבקרה.</b> הזנב הוא המשתמשים שכועסים. p95 ו-p99.</li>
<li><b>SLO רק על זמינות.</b> מערכת שמחזירה 200 עם תשובה שגויה תיראה מושלמת. צריך SLI של איכות, כמו עיגון.</li>
<li><b>התראה על כל קפיצה.</b> חלון אחד קצר מעייף את התורן, חלון ארוך מאחר. שני חלונות, ומספר מינימלי של בקשות.</li>
<li><b>משוב בלי trace_id.</b> אי אפשר לחקור אותו, ואי אפשר להפוך אותו ל-eval.</li>
</ul>`,
    },
  ],

  sims: [
    {
      id: "l22forensic",
      title: "חוקר traces: ארבעה משובים שליליים",
      lead: "12 ה-traces של שירות התשובות של Acme מבוקר אחד, אותם traces שבמעבדה (fixtures/forensic.jsonl). בוחרים trace, קוראים את ה-waterfall ואת ה-attributes, ולכל trace עם משוב שלילי בוחרים את סיבת השורש. הכלי מסביר אם צדקת, ואילו ראיות מוכיחות את זה.",
      tasks: [
        "התחל מ-trace תקין (בלי משוב) וקרא את <b>כל</b> ה-spans שלו: גרסת אינדקס, טוקני קלט, cache read, ניסיונות. זה ה\"נורמלי\" שתשווה אליו.",
        "לכל אחד מארבעת ה-traces עם 👎, מצא את ה-span שמתנהג אחרת מהנורמלי, ובחר סיבה. כתוב לעצמך את שם ה-attribute שהוכיח אותה.",
        "מיין לפי <b>משך</b>. אילו מה-traces האיטיים ביותר הם בכלל לא תשובות שגויות? מה המסקנה לגבי חקירה שמתחילה מה-trace האיטי ביותר?",
      ],
    },
    {
      id: "l22slo",
      title: "סימולטור SLO ו-burn rate",
      lead: "יום של תעבורה עם תקלה אחת שאתה מגדיר: מתי היא מתחילה, כמה זמן היא נמשכת, וכמה מהבקשות נכשלות בזמנה. הגרף מראה את ה-burn rate בשני החלונות של כל כלל התראה, והרשימה מראה מתי כל התראה נורית ונכבית, וכמה מתקציב השגיאות נשרף.",
      tasks: [
        "התחל מתקלה של 30 דקות עם 25% שגיאות (ברירת המחדל). כמה דקות עוברות עד שה-page של 1h/5m נורה, ולמה לא מיד?",
        "הקטן את שיעור השגיאות ל-5% והארך את התקלה ל-6 שעות. איזו התראה נורית עכשיו, ואיזו כבר לא? זה ההבדל בין שריפה מהירה לאיטית.",
        "החלף את היעד מ-99.5% ל-99.9%, בלי לשנות את התקלה. מה קורה ל-burn rate ולהתראות, ולמה יעד מחמיר יותר הוא החלטה עסקית ולא רק טכנית?",
      ],
    },
    {
      id: "l22sampling",
      title: "Head sampling מול tail sampling",
      lead: "10,000 traces ביום, עם שיעור שגיאות ושיעור בקשות איטיות שאתה קובע. משווים כמה traces נשמרים, כמה מהשגיאות והבקשות האיטיות נשארות לחקירה, ומה זה עושה לנפח האחסון, בשתי השיטות.",
      tasks: [
        "עם head sampling של 10% ו-0.5% שגיאות: כמה מ-50 השגיאות של היום תוכל לחקור? ועם tail sampling?",
        "הדלק את \"תשובות שגויות\" (לא ERROR ולא איטיות). מה tail sampling לפי status ו-latency שומר מהן, ואיזו policy היית מוסיף?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/22-observability",
    intro: "המעבדה בתיקייה labs/22-observability. חבילה חדשה בריפו, <b>obskit</b>, מוסיפה spans של OpenTelemetry לפי ה-GenAI conventions ל-llmkit ול-ragkit מבחוץ, עם JSONL exporter, redaction, אגרגציות, SLOs, replay ו-viewer של HTML. במרכז המעבדה: <b>שירות התשובות של Acme</b>, מערכת RAG קטנה עם מטמון, שליפה, כלי ומודל גיבוי, ו-12 traces מוקלטים מבוקר אחד שבו ארבעה משתמשים נתנו משוב שלילי. הכול רץ offline מול mockllm.",
    setup: [
      'cd ~/projects/"ai engineer"/ai-engineer-course && source .venv/bin/activate',
      "uv pip install -r labs/22-observability/requirements.txt   # opentelemetry-sdk 1.45 + OTLP exporter",
      "python -m pytest -q                                        # environment tests (tests/test_obskit.py)",
      "python -m pytest -q labs/22-observability/tests            # your exercises: they fail at first",
    ],
    tools: [
      "<b>InstrumentedLLM:</b> <code>InstrumentedLLM(LLM(...), prompt_name=, prompt_version=)</code> עוטף כל אובייקט עם <code>complete()</code> ומייצר span בשם <code>chat &lt;model&gt;</code> עם טוקנים, cache, עלות, TTFT, סיבת עצירה, ניסיונות, ו-event לכל retry.",
      "<b>setup_tracing:</b> בוחר exporters (JSONL, console, OTLP ל-Phoenix או Langfuse), sampling, redaction ו-content capture. לא לשכוח <code>tr.shutdown()</code> בסוף.",
      "<b>agent_span, retrieval_span, tool_span, InstrumentedRetriever:</b> spans לשלבים האחרים, עם ה-attributes של התקן ושל obskit.",
      "<b>הסקריפטים:</b> <code>trace_demo.py</code> (מריץ את השירות ומייצא), <code>trace_view.py</code> (waterfall ב-HTML), <code>trace_stats.py</code>, <code>forensic_check.py</code>, <code>make_day.py</code> ו-<code>slo_report.py</code>, <code>replay_trace.py</code>.",
      "<b>collector/:</b> compose עם Phoenix ו-OpenTelemetry Collector, וקונפיגורציה עם tail sampling ו-redaction.",
      "<b>mine.py:</b> שלושה חלקים שלך: <code>percentile</code> ו-<code>summarize</code>, <code>israeli_id_valid</code>, <code>redact_text</code> ו-<code>redact_attributes</code>, ו-<code>is_good</code>, <code>burn_rate</code> ו-<code>alerts_at</code>.",
    ],
    exercises: [
      { id: "ex1", title: "ה-spans הראשונים", text: "הרץ את שירות התשובות של Acme על ארבע שאלות, עם הדפסה של כל span. סווג את ה-attributes של ה-span <code>chat mock-model</code> לאלה שבאים מהתקן (<code>gen_ai.*</code>) ולאלה של obskit. הרץ שוב בלי content capture: מה נעלם, ומה כבר אי אפשר לעשות עם ה-trace? ולמה לשאלה הרביעית אין span של chat בכלל?", cmd: "python labs/22-observability/trace_demo.py --console\npython labs/22-observability/trace_demo.py --no-content" },
      { id: "ex2", title: "לראות traces", text: "צור waterfall ב-HTML מקובץ ה-JSONL ופתח בדפדפן. אם יש Docker, הרם את Phoenix, שלח אליו את אותם spans ב-OTLP, ובדוק שהטוקנים, המודל וההודעות מוצגים בתצוגת LLM. אחר כך נסה דרך ה-Collector (פורט 4318), שעושה tail sampling: אילו traces הגיעו ל-Phoenix ואילו לא?", cmd: "python labs/22-observability/trace_demo.py\npython labs/22-observability/trace_view.py results/traces.jsonl\ndocker run -d --name phoenix -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest\npython labs/22-observability/trace_demo.py --otlp http://localhost:6006/v1/traces" },
      { id: "ex3", title: "Latency ועלות מתוך spans", text: "ממש את <code>percentile</code> (אינטרפולציה לינארית) ואת <code>summarize</code>: p50 ו-p95 לכל סוג span, עלות לכל trace ו-N ה-traces האיטיים. הרץ על 12 ה-traces של הבוקר: מה ה-p95 של בקשה, איזה סוג span אחראי לרוב הזמן, ומה הפער בין p50 ל-p95 מספר?", cmd: "python -m pytest -q labs/22-observability/tests/test_ex3_stats.py\npython labs/22-observability/trace_stats.py labs/22-observability/fixtures/forensic.jsonl" },
      { id: "ex4", title: "Redaction של מידע אישי", text: "ממש את <code>israeli_id_valid</code>, <code>redact_text</code> (מיילים, טלפונים ישראליים, ת\"ז עם ספרת ביקורת) ו-<code>redact_attributes</code>. הדמו עם <code>--pii</code> מעביר כל span דרך RedactingSpanProcessor עם הפונקציה שלך. ודא שאין ב-JSONL אף ערך גולמי. למה בודקים ספרת ביקורת, ומה המחיר? למה redaction ב-Collector לא מספיק לבד?", cmd: "python -m pytest -q labs/22-observability/tests/test_ex4_redact.py\npython labs/22-observability/trace_demo.py --pii\ngrep -c 123456782 labs/22-observability/results/traces.jsonl" },
      { id: "ex5", title: "פורנזיקה: ארבעה משובים שליליים", text: "ב-fixtures/forensic.jsonl יש 12 traces מבוקר של 2026-10-29, וב-feedback.jsonl ארבעה משובים שליליים: \"Since January it's 5 days\", \"the policy says 3 or more consecutive days\", \"Right answer, but much slower than usual\", \"It's in the password policy!\". את העובדות על המסמכים והשירות תמצא ב-README של המעבדה, בסעיף \"השירות שה-traces מתארים\". לכל משוב מצא את סיבת השורש מתוך ה-traces בלבד, וכתוב אילו attributes הוכיחו אותה. השווה כל trace רע ל-trace טוב. בדוק עם forensic_check.", cmd: "python labs/22-observability/trace_view.py labs/22-observability/fixtures/forensic.jsonl --feedback labs/22-observability/fixtures/feedback.jsonl\npython labs/22-observability/forensic_check.py\npython labs/22-observability/forensic_check.py <trace_id prefix> <cause>" },
      { id: "ex6", title: "SLO ו-burn rate", text: "ממש את <code>is_good</code>, <code>burn_rate</code> ו-<code>alerts_at</code> (שני חלונות). make_day מייצר יום של כ-3,500 בקשות שבו פרומפט v4 נפרס ב-02:00 (והוחזר ב-09:30), והספק היה בעומס בין 11:20 ל-11:50. SLOs: זמינות 99.5%, 95% מתחת ל-8 שניות, 97% מעוגנות. אילו התראות נורו ומתי? למה העומס לא הוציא התראת latency? ואיזו התראה בלילה היא רעש, ולמה?", cmd: "python -m pytest -q labs/22-observability/tests/test_ex6_slo.py\npython labs/22-observability/make_day.py\npython labs/22-observability/slo_report.py --hourly" },
      { id: "ex7", title: "Replay של קריאה מוקלטת", text: "replay_trace בונה את הבקשה מחדש מתוך ה-span ושולח אותה לשרת מדומה תקין. הרץ על שלושה מה-traces של תרגיל 5. לכל אחד: האם התשובה זהה למוקלטת, ומה זה מוכיח על סיבת השורש? אחר כך הרץ את trace החופשה עם <code>--fresh-retrieval</code>: מה השתנה במקורות, ומה עדיין לא תקין?", cmd: "python labs/22-observability/replay_trace.py <trace_id prefix>\npython labs/22-observability/replay_trace.py <trace_id prefix> --fresh-retrieval" },
      { id: "ex8", title: "(רשות, חי) Claude אמיתי ב-Phoenix", text: "הרץ את הדמו מול Claude Haiku 5.5 עם Phoenix פתוח. השווה ל-mock: TTFT, cache read בקריאה השנייה, עלות, ואיכות התשובה בשאלה עם ה-tool. אחר כך replay עם <code>--live</code> שלוש פעמים: האם התשובה זהה? פחות מסנט.", cmd: "python labs/22-observability/trace_demo.py --live --otlp http://localhost:6006/v1/traces\npython labs/22-observability/replay_trace.py <trace_id prefix> --live" },
    ],
  },

  quiz: [
    { q: "משתמש מדווח על תשובה שגויה. בלוגים: \"POST /answer 200 1.1s\". למה זה לא מספיק?", options: ["כי הלוג לא כולל את קוד השגיאה", "כי תשובה שגויה היא כשל שקט: צריך לראות את כל השלבים של אותה בקשה, עם מה שנשלף ומה שנשלח למודל", "כי צריך לוג ברמת DEBUG", "כי 1.1 שניות זה איטי מדי"], correct: 1, explain: "תשובה שגויה מחזירה 200. רק <b>trace</b> מראה את המסלול: האם המסמך הנכון נשלף, איזה פרומפט נשלח, האם ענה מודל גיבוי." },
    { q: "llmkit עשה שני retries אחרי 529 ואז הצליח. איך obskit מתעד את זה?", options: ["שלושה spans נפרדים של chat", "span אחד של chat עם status ERROR", "span אחד של chat, עם שני events בשם retry ו-obskit.attempts=3", "לא מתעד, כי בסוף זה הצליח"], correct: 2, explain: "התקן מגדיר span לכל <b>קריאה לוגית</b>. כל ניסיון חוזר הוא <b>event</b> על אותו span, וכך סערת rate limit נראית כ-span ארוך עם כמה נקודות." },
    { q: "מה ברירת המחדל של OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT, ולמה?", options: ["SPAN_AND_EVENT, כדי שיהיה הכי הרבה מידע", "NO_CONTENT, כי פרומפטים ותשובות עלולים להכיל מידע רגיש, ולכן לכידה שלהם היא Opt-In", "SPAN_ONLY, כי events יקרים", "אין ברירת מחדל"], correct: 1, explain: "התקן מגדיר את התוכן כ-<b>Opt-In</b>, וערך לא מוכר נחשב גם הוא NO_CONTENT. המחיר: בלי תוכן אי אפשר לעשות replay." },
    { q: "ב-head sampling של 10%, עם 0.5% שגיאות ו-10,000 בקשות ביום, כמה traces של שגיאות תוכל לחקור?", options: ["50", "בערך 5", "בערך 500", "כולן, כי שגיאות תמיד נשמרות"], correct: 1, explain: "ההחלטה מתקבלת כשה-root מתחיל, לפני שידוע אם הבקשה תיכשל. 10% מ-50 שגיאות הם כ-5. <b>Tail sampling</b> ב-Collector יכול לשמור את כולן." },
    { q: "למה redaction צריך לקרות בתוך התהליך ולא רק ב-Collector?", options: ["כי ה-Collector לא תומך ב-regex", "כי ה-Collector איטי", "כי ה-span כבר עבר ברשת עד ה-Collector, ואולי לשירות צד שלישי: ניקוי שם הוא שכבה שנייה, לא ראשונה", "אין הבדל"], correct: 2, explain: "המידע חצה גבול אמון ברגע שיצא מהתהליך. ה-<b>RedactingSpanProcessor</b> מנקה לפני ה-exporter, וה-Collector תופס שירות ששכח." },
    { q: "למה בודקים ספרת ביקורת לפני שמסתירים רצף של 9 ספרות כת\"ז?", options: ["כדי לא להסתיר כל מספר הזמנה או סכום בן 9 ספרות, ולשמור את ה-traces שימושיים. המחיר: ת\"ז עם טעות הקלדה לא תוסתר", "כי זו דרישה של OpenTelemetry", "כדי שהקוד ירוץ מהר יותר", "כי ת\"ז לא חוקית היא לא מידע אישי בכלל"], correct: 0, explain: "זו פשרה בין <b>false positives</b> (הסתרה של מידע שימושי) ל-<b>false negatives</b>. מערכת מחמירה מוותרת על הבדיקה, וזה מה שהקונפיגורציה של ה-Collector עושה." },
    { q: "יעד זמינות 99.5%. בשעה האחרונה 3% מהבקשות נכשלו. מה ה-burn rate?", options: ["0.03", "3", "6", "14.4"], correct: 2, explain: "Burn rate הוא שיעור הרעות חלקי התקציב: 0.03 / 0.005 = <b>6</b>. בקצב הזה, תקציב של 30 יום נגמר בחמישה ימים." },
    { q: "למה כלל ההתראה דורש שגם החלון הקצר (5 דקות) וגם הארוך (שעה) יעברו 14.4x?", options: ["כדי להתריע מהר יותר", "החלון הארוך מבטיח שהבעיה משמעותית, והקצר מבטיח שהיא עדיין קורית, ולכן ההתראה נכבית מהר אחרי התיקון", "כי Prometheus דורש שני חלונות", "כדי לחסוך בחישוב"], correct: 1, explain: "חלון ארוך לבד ממשיך להתריע שעה אחרי התיקון. חלון קצר לבד מתריע על כל קפיצה. <b>שניהם יחד</b> נותנים התראה משמעותית שנכבית מהר." },
    { q: "ב-trace של תשובה שגויה, ה-span של המודל הוא ERROR עם rate_limit_error, ואחריו span של chat mock-small עם 56 טוקני קלט (בבקשות רגילות כ-1,150). מה הכי סביר?", options: ["המודל הקטן הזה פשוט גרוע", "אחרי שה-retries נגמרו, השירות עבר למודל גיבוי עם פרומפט בלי המקורות, ולכן הוא ענה מהזיכרון", "השליפה נכשלה", "ה-prompt cache החמיץ"], correct: 1, explain: "56 טוקנים אומרים שה<b>מקורות לא היו בפרומפט</b>. סיבת השורש היא rate limit שהפעיל fallback בלי עיגון, לא איכות המודל." },
    { q: "replay של קריאה מוקלטת מחזיר בדיוק את אותה תשובה שגויה. מה זה מוכיח?", options: ["שהמודל לא דטרמיניסטי", "שהבעיה בקלט שנשלח (מקורות או פרומפט), ולא בתשתית או באקראיות", "שה-replay לא עובד", "שצריך להחליף מודל"], correct: 1, explain: "אותו קלט, אותה תשובה: הבעיה <b>בקלט</b>. אם replay מול תשתית תקינה היה מחזיר תשובה נכונה, הבעיה הייתה בתשתית, כמו timeout." },
  ],

  summary: {
    points: [
      { t: "למה traces", b: "מערכת LLM נכשלת בשקט: 200, תשובה מנוסחת, ציטוט, ותוכן שגוי. מטריקות אומרות שיש בעיה, ו-trace מראה את המסלול של בקשה אחת, שלב אחרי שלב, עם מה שנשלף ומה שנשלח למודל. רק ממנו אפשר להגיע לסיבת השורש." },
      { t: "המודל של OpenTelemetry", b: "Trace הוא בקשה, span הוא שלב עם התחלה, סוף ואב. Attributes הם מה שמחפשים ומקבצים לפיו, events הם נקודות בזמן בתוך span (retry, exception), status הוא OK או ERROR עם error.type, ו-links מחברים spans בלי היררכיה. ה-context עובר אוטומטית בתוך התהליך, וב-traceparent בין שירותים." },
      { t: "GenAI semantic conventions", b: "שמות ל-spans (chat {model}, retrieval {source}, execute_tool {name}, invoke_agent) ול-attributes (gen_ai.request.model, gen_ai.usage.input_tokens, finish_reasons, time_to_first_chunk). הן בסטטוס Development, עברו לריפו נפרד, ושמות בהן משתנים, ולכן מרכזים אותם בקובץ אחד ומוסיפים namespace משלך רק למה שחסר, כמו עלות." },
      { t: "מה לרשום", b: "על המודל: מודל, גרסת פרומפט, טוקנים כולל cache, עלות, TTFT, סיבת עצירה, ניסיונות. על השליפה: מסמכים וציונים, גרסת אינדקס ו-replica. על כלים: שם, call id, ארגומנטים ותוצאה. על ה-root: סוג התשובה, עיגון, משתמש ושיחה. Retry הוא event על ה-span הלוגי." },
      { t: "תוכן ופרטיות", b: "פרומפטים ותשובות הם Opt-In (OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT, ברירת מחדל NO_CONTENT). בלעדיהם אין replay. הפתרון הוא שכבות: מטא-דאטה תמיד, תוכן אחרי redaction בתוך התהליך (מיילים, טלפונים, ת\"ז עם ספרת ביקורת), ותוכן מלא רק בגישה מוגבלת. ה-Collector הוא שכבת redaction שנייה." },
      { t: "הצינור וה-sampling", b: "TracerProvider עם Resource ו-Sampler, SpanProcessors (Simple לפיתוח, Batch לפרודקשן, Redacting לפניהם), exporters (OTLP, JSONL, console), ו-Collector אופציונלי. Head sampling מחליט לפני שידוע אם הבקשה תיכשל, ולכן מאבד שגיאות. Tail sampling ב-Collector שומר שגיאות ובקשות איטיות, במחיר זיכרון." },
      { t: "SLOs ו-burn rate", b: "SLI הוא יחס של בקשות טובות: זמינות, latency (95% מתחת לסף, בלי לספור כשלים), ועיגון, שתופס תשובות שגויות שזמינות לא רואה. Burn rate הוא שיעור הרעות חלקי התקציב. התראות טובות דורשות שני חלונות (14.4x על 1h/5m, 6x על 6h/30m, ticket על שריפה איטית) ומספר מינימלי של בקשות." },
      { t: "פורנזיקה ו-replay", b: "מהמשוב ל-trace (דרך trace_id), סיווג לשגוי, איטי או לא ענה, קריאה של ה-root, מעבר מהשליפה למודל, והשוואה ל-trace תקין. Replay של אותה בקשה מבדיל בין בעיה בקלט (אותה תשובה) לבעיה בתשתית (תשובה נכונה כשהכול תקין). כל מקרה מאושר הופך ל-eval בנושא 23." },
    ],
    glossary: [
      ["Trace", "כל ה-spans של בקשה אחת, עם trace_id משותף."],
      ["Span", "שלב אחד בבקשה, עם התחלה, סוף, אב, attributes ו-events."],
      ["Attribute", "זוג של מפתח וערך על span, למשל gen_ai.request.model."],
      ["Event", "נקודה בזמן בתוך span, עם attributes משלה: retry, exception."],
      ["Span link", "קשר בין spans שאינו אב וילד, למשל בין replay לקריאה המקורית."],
      ["Semantic conventions", "מוסכמות OTel לשמות של spans ו-attributes בתחום מסוים."],
      ["gen_ai.operation.name", "סוג פעולת ה-GenAI: chat, retrieval, execute_tool, invoke_agent."],
      ["Content capture", "רישום של פרומפטים, תשובות וארגומנטים על spans. Opt-In בתקן."],
      ["OTLP", "הפרוטוקול של OpenTelemetry לשליחת טלמטריה, ב-HTTP או gRPC."],
      ["SpanProcessor", "רכיב ב-SDK שמקבל כל span בהתחלה ובסוף: batch, redaction."],
      ["Collector", "שירות שמקבל OTLP, מעבד (sampling, redaction) ושולח לכלים."],
      ["Head sampling", "החלטה אם לשמור trace כשה-root מתחיל, לפי trace_id."],
      ["Tail sampling", "החלטה אחרי שכל ה-trace הגיע, לפי status, משך או attributes."],
      ["Redaction", "הסרה של מידע אישי מטלמטריה לפני שהיא נשמרת או נשלחת."],
      ["SLI ו-SLO", "יחס של בקשות טובות, ויעד עבורו לאורך תקופה."],
      ["Burn rate", "קצב צריכת תקציב השגיאות: שיעור הרעות חלקי (1 פחות היעד)."],
    ],
    reading: [
      { title: "OpenTelemetry GenAI semantic conventions (repo)", url: "https://github.com/open-telemetry/semantic-conventions-genai", note: "התקן, כולל ה-changelog עם שינויי השמות. נקרא ב-1 בנובמבר 2026." },
      { title: "Phoenix: OTel semantic conventions conversion (release note)", url: "https://arize.com/docs/phoenix/release-notes/05-2026/05-15-2026-otel-semconv-conversion", note: "מגרסה 15.10, Phoenix ממיר gen_ai.* לפורמט שלו." },
      { title: "Langfuse: OpenTelemetry integration", url: "https://langfuse.com/integrations/native/opentelemetry", note: "ה-endpoint, ה-auth והמיפוי של gen_ai.*." },
      { title: "Langfuse: self-hosting with Docker Compose", url: "https://langfuse.com/self-hosting/deployment/docker-compose", note: "הרצה מקומית של Langfuse v4." },
      { title: "Datadog: OpenTelemetry instrumentation for LLM/Agent Observability", url: "https://docs.datadoghq.com/llm_observability/instrumentation/otel_instrumentation/", note: "GenAI conventions 1.37+, ה-header dd-otlp-source=llmobs, והמגבלות." },
      { title: "Honeycomb: Fast AI Feedback Loops with Honeycomb and OpenTelemetry", url: "https://www.honeycomb.io/blog/fast-ai-feedback-loops-honeycomb-opentelemetry", note: "מה Honeycomb מציג ל-spans של GenAI (אפריל 2026)." },
      { title: "OpenLLMetry", url: "https://github.com/traceloop/openllmetry", note: "auto-instrumentation בקוד פתוח מעל OpenTelemetry." },
      { title: "Tail sampling processor (collector-contrib)", url: "https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor", note: "ה-policies שבקונפיגורציה של המעבדה." },
      { title: "Hamel Husain: A Field Guide to Rapidly Improving AI Products", url: "https://hamel.dev/blog/posts/field-guide/", note: "למה לקרוא נתונים אמיתיים (ו-traces) היא הפעילות החשובה ביותר בפיתוח AI." },
    ],
  },
};
