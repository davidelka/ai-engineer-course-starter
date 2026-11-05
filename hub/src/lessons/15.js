// Lesson 15 — Agent Loops and ReAct.
window.LESSONS = window.LESSONS || {};
window.LESSONS["15"] = {
  n: 15,
  title: "Agent Loops and ReAct",
  he: "plan-act-observe, תנאי עצירה ותקציבים",
  hours: "כשעתיים וחצי שיעור, כארבע שעות מעבדה",

  goals: [
    "להבין מה <b>agent</b> הוא בפועל: מודל שרץ <b>בלולאה</b>, ובכל צעד בוחר בעצמו את הפעולה הבאה לפי מה שראה עד עכשיו (<b>observe, think, act, observe</b>). זה שונה מקוד שקובע מראש את כל המסלול.",
    "להכיר את <b>ReAct</b> המקורי (מחשבה, פעולה ותצפית כטקסט חופשי) ואת <b>הגרסה המודרנית</b> שלו: קריאה מובנית לכלים, טקסט חשיבה בין הקריאות, ו-<b>adaptive thinking</b> של Claude, כולל הכלל שבלוקי thinking חוזרים לספק בלי שינוי.",
    "להשוות בין סוכן <b>תגובתי</b> (reactive) לבין <b>plan-then-act</b>: מה תוכנית מובנית נותנת (שקיפות, קריאות מקבילות), מה היא עולה (קריאת מודל נוספת, תוכנית שנכתבה לפני שראו נתונים), ומתי <b>מתכננים מחדש</b>.",
    "לתכנן <b>תנאי עצירה</b> כמערכת: תשובה סופית, <b>ויתור מפורש</b>, מספר צעדים, <b>תקציב</b> של טוקנים, דולרים וזמן, <b>זיהוי חזרות</b>, <b>זיהוי חוסר התקדמות</b>, ושגיאות ברצף. כל אלה נבדקים בסדר קבוע.",
    "לנהל <b>זיכרון בתוך ריצה</b>: למה כל צעד יקר יותר מהקודם, איך <b>מוחקים תוצאות ישנות של כלים</b> בלי לשבור את השיחה, ולמה בלי <b>scratchpad</b> הסוכן שוכח ומביא את אותו מידע שוב.",
    "לטפל בשגיאות כ<b>תצפיות</b>: retries בשלוש שכבות, fallbacks, ויתור כן, ו-<b>אישור אנושי</b> לכל פעולה עם תופעת לוואי, עם token שהמודל לא רואה.",
    "<b>להעריך agents</b> לפי ה-<b>trajectory</b> ולא רק לפי התשובה: הצלחה מול תוצאת זהב, מספר צעדים, <b>קריאות מיותרות</b>, יעילות, עלות להצלחה, <b>סתירה לראיות</b>, ו-<b>pass^k</b> בשביל אמינות.",
    "לזהות מתי agent הוא <b>הכלי הלא נכון</b>: כשהצעדים ידועים מראש, <b>workflow קבוע</b> זול יותר, צפוי יותר וקל יותר לבדיקה. זו ההקדמה לשיעור 16 ולבורר הדפוסים של שיעור 19.",
  ],
  connects: "בשיעור 14 בנינו <b>לולאה לשאלה אחת</b>: המודל מבקש כלי, הקוד מריץ אותו ומחזיר את התוצאה, עד <code>max_rounds</code>. השיעור הזה הופך את הלולאה ל<b>agent</b> של ממש: יש לו תקציב, מדיניות עצירה, ויתור מפורש, תכנון, זיכרון בתוך הריצה, אישור אנושי ו-trajectory שאפשר להעריך. החבילה החדשה <b>agentkit</b> בנויה מעל ה-registry וה-executor של <b>toolkit</b> משיעור 14, משתמשת ב-<b>llmkit.structured</b> משיעור 3 בשביל התוכנית, ממחזרת את רעיון התקציבים וסיבות העצירה של <b>loopkit</b> משיעור 7, ויודעת לייצא spans של <b>obskit</b> משיעור 22. ב-<b>Company Brain</b> זה הסוכן של שלב 3: הוא מקבל בקשת גישה בשפה חופשית, מברר מי העובד, מה המדיניות ומה כבר קיים, ופותח בקשה רק באישור של אדם. ב<b>שיעור 16</b> אותה עבודה תהפוך ל-workflow ב-LangGraph, עם אישור אנושי כצומת בגרף. ב<b>שיעור 17</b> הכלים יוגשו דרך MCP. ב<b>שיעור 18</b> כמה agents יעבדו יחד. וב<b>שיעור 23</b> נחזור להערכת trajectories בקנה מידה, עם LLM-as-judge.",

  intro: {
    animation: "l15loop",
    animationTitle: "לולאת ה-agent: scratchpad חי, קריאות לכלים ומד תקציב, כולל ריצה שנעצרת על חזרה",
    animationGuide: `<p><b>מה רואים כאן:</b> ריצה אחת של ה-agent של Company Brain, צעד אחרי צעד. הנתונים לקוחים מריצות אמיתיות של <code>agentkit</code> עם המודל המזויף של המעבדה (<code>--model fake</code>), ולא הומצאו לאנימציה. המשימה היא t01 מסט המשימות: <bdi>"Dana Levi asks for admin access on AWS production for 3 days ... Who is her manager, what does the policy say, and open the request"</bdi>. כדי להבין את הריצה צריך לדעת שלוש עובדות: המנהלת של Dana היא Michal Ben-David (E005). לפי מדיניות v2.2, הרשאת admin על תשתית פרודקשן היא <b>needs_security</b>. ו-<code>create_access_request</code> כותב רשומה, ולכן דורש אישור של אדם.</p>
<p><b>ארבעת האזורים במסך:</b></p>
<ol>
<li><b>טבעת הלולאה</b> (למעלה): ארבע תחנות. <b>Observe</b>: המודל מקבל את כל השיחה. <b>Think</b>: המודל כותב משפט קצר על מה שהוא צריך ולמה. <b>Act</b>: קריאה לכלי, או תשובה סופית. <b>Check</b>: מדיניות העצירה מחליטה אם להמשיך. התחנה הפעילה מודגשת.</li>
<li><b>ה-scratchpad</b>: ההקשר שהמודל רואה בצעד הנוכחי. כל צעד מוסיף לו שורות: הטקסט של המודל, הקריאה, והתוצאה. שים לב שהוא רק גדל, וכל צעד שולח את כולו מחדש.</li>
<li><b>מד התקציב</b>: ארבעה פסים. צעדים (מתוך 8), עלות (מתוך $0.002, תקציב שנבחר לאנימציה כדי שהפס יזוז. ב-<code>Budget</code> עצמו אין ברירת מחדל לעלות, והסקריפטים במעבדה משתמשים ב-$0.02 או $0.01), מספר הפעמים שהקריאה הכי חוזרת הופיעה (מתוך 3), ומספר הצעדים ברצף בלי מידע חדש (מתוך 3). פס שמגיע לסוף נצבע באדום, וזה הגבול שעוצר את הריצה.</li>
<li><b>החלטת המדיניות</b> (למטה): מה <code>should_stop</code> החליט אחרי הצעד, ובאיזה כלל.</li>
</ol>
<p><b>שלוש הריצות</b> (הכפתורים למעלה): <b>הצלחה</b>: ארבעה צעדים ושלוש קריאות, אישור אנושי לפני ה-create, ותשובה סופית. <b>לולאה זהה</b>: מודל שקורא שוב ושוב ל-<code>lookup_employee</code> עם אותם ארגומנטים, עד שכלל ה-<b>repetition</b> עוצר אותו בצעד 3. <b>לולאה מוסווית</b>: אותו חיפוש, פעם לפי שם, פעם לפי מייל ופעם לפי מזהה. ה-fingerprint של כל קריאה שונה, ולכן כלל החזרות לא תופס אותה, אבל התוצאה זהה בכל פעם, ולכן כלל ה-<b>no_progress</b> עוצר אותה.</p>
<p><b>איך לעבוד איתה:</b> התחל ב"הצלחה" ועבור צעד אחרי צעד עם החצים. בכל צעד קרא את ההסבר שמתחת. אחר כך עבור ל"לולאה זהה" ול"לולאה מוסווית", ובכל אחת מהן שים לב לפס שמתמלא ראשון.</p>`,
    videos: [
      {
        title: "How We Build Effective Agents",
        who: "Barry Zhang, Anthropic (AI Engineer Summit 2025)",
        part: "כל ההרצאה",
        minutes: 15,
        url: "https://www.youtube.com/watch?v=D7_ipDqhtwk",
        required: true,
        kind: "וידאו",
        why: "שלושה רעיונות שהשיעור כולו בנוי עליהם. הראשון: agent הוא החלטה ארכיטקטונית ולא שדרוג אוטומטי, ו-workflow עדיף כשאפשר למפות את הצעדים מראש. השני: agent בסיסי הוא סביבה, כלים ופרומפט של מערכת, בתוך לולאה. השלישי: כדי לדבג, קוראים את ה-trajectory מנקודת המבט של המודל. בסוף ההרצאה הוא מציין שאכיפת תקציבים של זמן, כסף וטוקנים היא בעיה פתוחה, וזה בדיוק מה שנבנה במעבדה.",
      },
      {
        title: "Building effective agents",
        who: "Anthropic, דצמבר 2024 (עם הערת עורך מעודכנת)",
        part: "כל המאמר, ובמיוחד החלקים Workflows vs agents ו-Agents",
        minutes: 25,
        url: "https://www.anthropic.com/research/building-effective-agents",
        required: true,
        kind: "מאמר",
        why: "ההגדרה שהתעשייה מאמצת: workflow הוא מסלול שנקבע בקוד, ו-agent הוא מודל שמכוון את התהליך בעצמו. מכאן מגיעים שני משפטים שנחזור אליהם: \"חשוב שה-agent יקבל ground truth מהסביבה בכל צעד\", ו\"מקובל להוסיף תנאי עצירה, כמו מספר מקסימלי של איטרציות\". בראש העמוד יש הערת עורך שאומרת שחלק מהכלים שהמאמר מתאר השתנו מאז.",
      },
      {
        title: "AI Agents in LangGraph: Build an Agent from Scratch",
        who: "DeepLearning.AI, עם Harrison Chase (LangChain)",
        part: "השיעור השני, Build an Agent from Scratch (12 דקות)",
        minutes: 12,
        url: "https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/",
        required: true,
        kind: "קורס",
        why: "בונה ReAct ב<b>גרסה המקורית</b>: פרומפט שמבקש מהמודל לכתוב Thought, Action ו-PAUSE, regex שמפרסר את הפעולה, ולולאה עם max_turns. כדאי לראות את זה כדי להבין מה tool calling מודרני חוסך לנו. אצלנו אותו מבנה נאכף על ידי ה-API, בלי פרסור טקסט. השיעורים הבאים בקורס מכינים לשיעור 16.",
      },
      {
        title: "Extended thinking and adaptive thinking, with tool use",
        who: "Anthropic docs",
        part: "החלקים Adaptive thinking ו-Thinking with tool use",
        minutes: 15,
        url: "https://platform.claude.com/docs/en/build-with-claude/thinking",
        required: false,
        kind: "תיעוד",
        why: "הגרסה המודרנית של \"Thought\" ב-ReAct. ב-Haiku 5.5 יש adaptive thinking: המודל מחליט בעצמו אם לחשוב וכמה, וה-effort שמוגדר כברירת מחדל הוא medium. כשחושבים בין קריאות לכלים, חובה להחזיר את בלוקי ה-thinking לספק בדיוק כפי שהתקבלו, אחרת מתקבלת שגיאת 400. ב-Haiku 5.5 החשיבה מוסתרת כברירת מחדל (display: omitted). זו הסיבה ש-llmkit שומר את התשובה הגולמית של הספק ומחזיר אותה כמו שהיא.",
      },
      {
        title: "Effective context engineering for AI agents",
        who: "Anthropic Engineering, ספטמבר 2025",
        part: "החלקים על compaction, structured note-taking ו-tool result clearing",
        minutes: 20,
        url: "https://anthropic.com/engineering/effective-context-engineering-for-ai-agents",
        required: false,
        kind: "מאמר",
        why: "הבסיס לתרגיל 7. מחיקת תוצאות ישנות של כלים מתוארת שם כ\"אחת הדרכים הבטוחות\" לכווץ הקשר. רישום פתקים (note-taking) שומר את מה שחשוב מחוץ להקשר. העיקרון המנחה הוא למצוא את \"הקבוצה הקטנה ביותר של טוקנים עם הרבה סיגנל\".",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "מלולאה לשאלה אחת ל-agent",
      html: `<p class="big">ב-agent, ה<b>מודל</b> מחליט מה הצעד הבא. בכל צעד הוא רואה את המשימה ואת כל מה שנצפה עד עכשיו, ובוחר אם לקרוא לכלי, לאיזה כלי ועם אילו ארגומנטים, או שכבר אפשר לענות. הקוד שלך לא קובע את המסלול. הוא קובע את <b>הגבולות</b>: אילו כלים מותרים, כמה מותר להוציא, מתי עוצרים, ומה אסור לעשות בלי אדם.</p>
<p>בשיעור 14 כבר כתבנו את הלב של זה: <code>run_tool_loop</code> קורא למודל, מריץ את הכלים שהוא ביקש, מחזיר את התוצאות, וחוזר על זה עד שהמודל עונה או עד <code>max_rounds</code>. זו לולאה לשאלה אחת, ויש לה גבול אחד. ב-production חסרים בה הרבה דברים. אין לה מושג של כסף או של זמן. היא לא מזהה שהמודל תקוע וקורא שוב ושוב לאותו כלי. אין למודל דרך מסודרת להגיד "אני לא יכול להשלים את זה". אין תוכנית שאפשר להציג לפני שמשהו קורה. אין טיפול בהקשר שגדל. ואין רישום מסודר של מה קרה, שאפשר להעריך אחר כך.</p>
<p>agent הוא הלולאה הזו, עם כל מה שחסר לה. הכל נמצא ב-<code>agentkit.Agent</code>, וכל מה שמתואר בשיעור הוא קוד שאפשר להריץ במעבדה:</p>
<ul>
<li><b>תקציב</b> (<code>Budget</code>): צעדים, טוקנים, דולרים וזמן.</li>
<li><b>מדיניות עצירה</b> (<code>should_stop</code>): פונקציה טהורה שרצה אחרי כל צעד ומחזירה "המשך", או "עצור" יחד עם הסיבה.</li>
<li><b>כלי ויתור</b> (<code>give_up</code>): דרך כנה לעצור.</li>
<li><b>אישור אנושי</b> לכל כלי עם תופעת לוואי.</li>
<li><b>מצב תכנון</b>, עם תכנון מחדש כשמשהו נכשל.</li>
<li><b>ניהול זיכרון</b> בתוך הריצה.</li>
<li><b>trajectory</b>: קובץ JSONL שמתעד כל צעד.</li>
</ul>
<div class="callout">המשימה שתלווה את השיעור היא t01 מסט המשימות: "Dana Levi asks for admin access on AWS production for 3 days. Who is her manager, what does the policy say, and open the request". כדי לבצע אותה צריך שלושה כלים לפי סדר: <code>lookup_employee</code> (המנהלת היא Michal Ben-David), <code>check_policy</code> (admin על aws-production הוא needs_security, כי זו גם הרשאת admin וגם תשתית פרודקשן), ו-<code>create_access_request</code>, שכותב רשומה ולכן מחכה לאישור של אדם. הבקשה נכנסת למסלול האבטחה, ותפוג אחרי 3 ימים, ב-2026-11-04.</div>`,
    },
    {
      kicker: "המנגנון",
      title: "הלולאה: observe, think, act, observe",
      html: `<p>כל <b>צעד</b> ב-agentkit הוא קריאה אחת למודל, יחד עם מה שקורה סביבה. ההגדרה הזו חשובה, כי היא קובעת מה סופרים: <code>max_steps=8</code> פירושו שמונה קריאות למודל, בלי קשר למספר הכלים שהוא הפעיל בכל קריאה.</p>
<ol class="ladder">
<li><b>Observe</b><span>המודל מקבל בקשה שלמה: הפרומפט של המערכת (ואם יש, גם התוכנית והפתקים), הגדרות הכלים, המשימה, וכל הצעדים הקודמים. זה כולל כל קריאה וכל תוצאה. למודל אין זיכרון בין קריאות, ולכן ה"זיכרון" של ה-agent הוא השיחה עצמה.</span></li>
<li><b>Think</b><span>לפני הקריאה לכלי, המודל כותב טקסט קצר כמו "I need the employee record and manager". זה ה-Thought של ReAct. בפרומפט של המערכת שלנו ביקשנו את המשפט הזה במפורש, כי הוא הופך את ה-trajectory לקריא. במודלים עם thinking יש בנוסף חשיבה פנימית.</span></li>
<li><b>Act</b><span>המודל מחזיר קריאות לכלים, אחת או כמה במקביל, או תשובה סופית בלי כלים. ה-executor של toolkit מריץ את הקריאות: ולידציה, timeout, ושגיאות שחוזרות כנתונים. כלי עם תופעת לוואי עובר קודם דרך <code>confirm(call)</code>.</span></li>
<li><b>Observe שוב</b><span>התוצאות נכנסות לשיחה בהודעת user אחת, ונרשמת שורת <code>step</code> ב-trajectory.</span></li>
<li><b>Check</b><span><code>policy(history, budget)</code> מחליט אם להמשיך. אם התשובה היא "עצור", הלולאה נגמרת עם <code>stop_reason</code>. אם לא, חוזרים לשלב הראשון.</span></li>
</ol>
<div class="example"><b>הלב של Agent._run, מקוצר</b><pre dir="ltr">while True:
    r = llm.complete(req)                       # observe + think + choose
    if not r.tool_calls:                        # a final answer
        history.append(StepRecord(n, final=True, ...))
        decision = policy(history, budget); break
    req.messages.append(r.message)              # the assistant turn, raw (thinking blocks kept)
    results = execute(r.tool_calls)             # confirm side effects, validate, timeout
    req.messages.append(Message.with_tool_results(results))
    history.append(StepRecord(n, calls=..., fingerprints=..., result_hashes=..., tokens=..., cost_usd=...))
    decision = policy(history, budget)          # continue, or stop with a reason
    if decision.stop: break</pre></div>
<p>שתי החלטות עיצוב שכדאי לשים לב אליהן. הראשונה: <b>גם התשובה הסופית עוברת דרך המדיניות</b>. כך כל עצירה, כולל עצירה רגילה, מגיעה ממקום אחד, וה-trajectory תמיד מסתיים בשורה שאומרת מה עצר אותו ולמה. השנייה: כשהמדיניות עוצרת באמצע, <b>כל הקריאות כבר קיבלו תוצאות</b>. שיחה שנגמרת בבקשה לכלי בלי תוצאה היא שיחה שבורה, וכל ספק ידחה אותה אם מישהו ימשיך אותה. כך גם עשינו בשיעור 14.</p>`,
    },
    {
      kicker: "היסטוריה",
      title: "ReAct המקורי: חשיבה ופעולה שזורות זו בזו",
      html: `<p>המאמר <b>ReAct: Synergizing Reasoning and Acting in Language Models</b> (Yao ועמיתים, 2022, הוצג ב-ICLR 2023) הציע רעיון שנשמע היום מובן מאליו. לפניו היו שתי גישות נפרדות. <b>Chain-of-thought</b> נותן למודל לחשוב בקול, אבל רק מתוך מה שהוא כבר יודע, ולכן הוא ממציא עובדות. <b>Act-only</b> נותן למודל לפעול (למשל, לחפש בוויקיפדיה), אבל בלי לנמק, ולכן הוא מאבד את הכיוון. ReAct שוזר את השתיים: המודל כותב מחשבה, אחר כך פעולה, אחר כך מקבל תצפית מהעולם, וחוזר חלילה.</p>
<div class="example"><b>הפורמט המקורי: טקסט חופשי שהקוד מפרסר</b><pre dir="ltr">Thought: I need Dana's manager first.
Action: lookup_employee[dana.levi@acme.example]
PAUSE
Observation: {"name": "Dana Levi", "manager": {"name": "Michal Ben-David"}}
Thought: Now the policy route for admin on aws-production.
Action: check_policy[aws-production, admin]
PAUSE
Observation: {"route": "needs_security", ...}
Thought: I have what I need.
Answer: Michal Ben-David is her manager; the request goes to security review.</pre></div>
<p>הקוד שמסביב הוא מה שתראה בשיעור של DeepLearning.AI. פרומפט ארוך מסביר את הפורמט, עם דוגמאות. stop sequence עוצר את המודל אחרי "PAUSE". regex מוצא את שורת ה-Action. הקוד מריץ את הפעולה, ומדביק "Observation:" לפרומפט. במאמר, ReAct שיפר את שיעור ההצלחה ב-ALFWorld (משחק טקסט של משימות בבית) ב-34 נקודות אחוז, לעומת שיטות של imitation learning ו-reinforcement learning. ב-HotpotQA, עם API של ויקיפדיה, הוא הפחית הזיות לעומת chain-of-thought, כי כל טענה נשענה על תצפית.</p>
<p>הבעיות של הפורמט הזה הן הבעיות של כל פרסור טקסט. המודל שוכח את ה-PAUSE. הוא כותב "Action: lookup employee" עם רווח. הוא ממציא Observation בעצמו, כי מבחינתו זה פשוט עוד טקסט להשלים. הארגומנטים הם מחרוזת חופשית, בלי סכמה. וקריאה מקבילה פשוט לא קיימת. בשיעור 3 ראינו את אותו מעבר, מ"תחזיר JSON בבקשה" ל-structured output שנאכף על ידי הספק. כאן קורה אותו דבר: הרעיון של ReAct נשאר, והפורמט עבר לתוך ה-API.</p>
<div class="callout">ReAct הוא קודם כול <b>רעיון</b> ורק אחר כך <b>פורמט</b>. הרעיון הוא שכל צעד נשען על תצפית אמיתית מהעולם, ולא על מה שהמודל זוכר. המאמר של Anthropic מנסח את זה כך: חשוב שה-agent יקבל ground truth מהסביבה בכל צעד. זה נכון בדיוק באותה מידה גם כשהפורמט הוא tool calling.</div>`,
    },
    {
      kicker: "היום",
      title: "ReAct המודרני: tool calling, טקסט בין קריאות ו-thinking",
      html: `<p>ב-agent מודרני אותם שלושה חלקים קיימים, אבל ה-API אוכף אותם. ה<b>פעולה</b> היא בלוק <code>tool_use</code> עם שם, ארגומנטים שעברו ולידציה מול סכמה, ומזהה. ה<b>תצפית</b> היא <code>tool_result</code> שמקושר לקריאה לפי אותו מזהה, והמודל לא יכול לזייף אותה, כי רק הקוד שלך כותב אותה. ה<b>מחשבה</b> מופיעה בשתי צורות. הצורה הגלויה היא הטקסט שהמודל כותב לפני הקריאות באותה תשובה. ב-agentkit הוא נשמר בשדה <code>thought</code> של כל צעד. הצורה השנייה היא <b>חשיבה פנימית</b>, במודלים שתומכים בה.</p>
<h4>חשיבה בין קריאות לכלים ב-Claude</h4>
<p>לפי התיעוד של Anthropic מנובמבר 2026, <b>adaptive thinking</b> הוא המצב המומלץ, ו-Haiku 5.5 תומך בו. במצב הזה המודל מחליט בעצמו אם לחשוב וכמה, ואת העומק קובע הפרמטר <code>effort</code>. ב-Haiku 5.5 ה-effort שמוגדר כברירת מחדל הוא <b>medium</b>. ב-llmkit זה <code>ChatRequest(effort=...)</code>, וב-Agent זה <code>Agent(effort="high")</code>. עם adaptive thinking, החשיבה שזורה בין קריאות לכלים באופן אוטומטי ("interleaved thinking"), בלי beta header. יש כאן הסתייגות: הכלל הכללי בתיעוד מכסה את Haiku 5.5, אבל הרשימה המפורשת של המודלים שבהם החשיבה בין הקריאות תמיד מופיעה לא כוללת אותו. כדאי לבדוק את זה במעבדה.</p>
<p>יש שלושה כללים שאסור לפספס:</p>
<ul>
<li><b>בלוקי thinking חוזרים לספק בלי שינוי.</b> בתוך סבב של כלים, חובה להחזיר את בלוקי ה-thinking מתשובת המודל, שלמים ובלי שום שינוי. בלוק ששונה נדחה עם שגיאת 400. לכן llmkit שומר את התשובה הגולמית של הספק (<code>Message.raw</code>) ומחזיר אותה כמו שהיא, ו-Agent מוסיף לשיחה את <code>r.message</code> בלי לבנות אותו מחדש.</li>
<li><b>ב-Haiku 5.5 החשיבה מוסתרת כברירת מחדל.</b> ברירת המחדל היא <code>display: "omitted"</code>: הבלוק חוזר עם שדה thinking ריק. כדי לראות סיכום של החשיבה צריך לבקש <code>"summarized"</code>, דרך <code>extra_body</code>. מחויבים על כל טוקני החשיבה, גם אם רואים רק סיכום שלהם, או לא רואים כלום.</li>
<li><b>tool_choice ו-thinking.</b> ב-extended thinking הידני (שכבר deprecated) מותר רק auto או none. ב-adaptive, כפיית כלי מותרת, חוץ מכמה מודלים (Opus 5.5, Sonnet 5.5 ועוד). Haiku 5.5 לא ברשימה הזו (נבדק בנובמבר 2026; רשימות כאלה משתנות).</li>
</ul>
<p>מה עם <b>"think" tool</b>, כלי ריק שהמודל קורא לו כדי לעצור ולחשוב? Anthropic פרסמה עליו מאמר במרץ 2025, עם שיפור משמעותי ב-τ-bench בתחום התעופה. בטקסט של המאמר מופיעים 0.370 בלי הכלי ו-0.570 עם הכלי ועם פרומפט מותאם. בטבלת ה-pass^1 באותו מאמר המספרים קצת שונים: 0.332 בלי הכלי, 0.404 עם הכלי לבד, 0.412 עם extended thinking ו-0.584 עם הכלי והפרומפט. המאמר לא מיישב בין השניים, ולכן כדאי להתייחס למספרים כאל סדר גודל (נבדק בנובמבר 2026). ב-15 בדצמבר 2025 נוספה למאמר הערה: extended thinking השתפר, ובמרבית המקרים עדיף להשתמש בו ולא בכלי נפרד. זה סימן טוב לכמה מהר התחום זז, וסיבה לבדוק תיעוד עדכני לפני שמעתיקים טריק.</p>
<div class="callout">הטקסט הגלוי לפני קריאה לכלי הוא הכלי הכי זול שיש לך לדיבאג. משפט אחד, "I need the approval route from the policy", מסביר את הקריאה למי שקורא את ה-trajectory, וגם עוזר למודל עצמו להישאר בכיוון. זה עולה כמה טוקני פלט בכל צעד.</div>`,
    },
    {
      kicker: "תכנון",
      title: "Reactive מול plan-then-act",
      html: `<p>agent <b>תגובתי</b> (reactive) מחליט רק על הצעד הבא, לפי מה שראה. agent שמתכנן קודם (<b>plan-then-act</b>, או plan-and-execute) מבקש מהמודל תוכנית מלאה לפני שמשהו רץ, ואז מבצע אותה. ב-agentkit, <code>Agent(mode="plan")</code> קורא קודם ל-<code>make_plan</code>. הפונקציה משתמשת ב-<code>complete_structured</code> משיעור 3, עם מודל Pydantic בשם <code>Plan</code>, שיש בו שלושה שדות: goal, ‏steps (לכל צעד: id, ‏action, ‏tool ו-depends_on) ו-done_when. התוכנית נכנסת לפרומפט של המערכת של לולאת הביצוע, עם הוראה להריץ באותו צעד את כל השלבים שלא תלויים זה בזה.</p>
<div class="example"><b>התוכנית ש-t01 קיבל, כפי שהיא נרשמת ב-trajectory</b><pre dir="ltr">PLAN  tokens=732 cost=$0.00014
  1. Call lookup_employee to get the facts [lookup_employee]
  2. Call check_policy to get the facts [check_policy]
  3. File the request if the checks allow it [create_access_request]   (after 1, 2)
  4. Answer the user with the facts found                               (after 1, 2, 3)</pre></div>
<p><b>מה תוכנית נותנת.</b> הדבר הראשון הוא <b>שקיפות לפני פעולה</b>: אפשר לרשום את התוכנית, להציג אותה, או לבקש מאדם לאשר אותה לפני כל תופעת לוואי. הדבר השני הוא <b>מקביליות</b>: שלבים 1 ו-2 לא תלויים זה בזה, ולכן רצים באותו צעד. ב-t01, המודל המזויף במצב plan סיים בשלושה צעדים, לעומת ארבעה במצב reactive. הדבר השלישי הוא <b>כיוון במשימות ארוכות</b>. הבלוג של LangChain על plan-and-execute (פברואר 2024) מונה שלושה יתרונות: מהירות, עלות (אפשר לבצע שלבים עם מודל קטן יותר) ואיכות. את האיכות הוא מציג כהבטחה, לא כתוצאה שנמדדה.</p>
<p><b>מה תוכנית עולה.</b> קודם כול, קריאת מודל נוספת לתכנון. שנית, תוכנית נכתבת <b>לפני</b> שראו נתונים, ולכן היא יכולה להיות שגויה. ב-t05 ("Shani needs a Notion account") התוכנית שלחה במקביל גם lookup וגם check_policy. ה-lookup נכשל, כי יש ארבע Shani, ולכן בדיקת המדיניות הייתה מיותרת. ב-t10 התוכנית בדקה מדיניות לבקשה שבסוף לא נפתחה, כי ל-Dana כבר יש GitHub write. offline, במצב plan היעילות הממוצעת יורדת מ-1.00 ל-0.90. שלישית, כשמשהו נכשל צריך <b>לתכנן מחדש</b>. ב-agentkit, כל צעד שיש בו קריאה שנכשלה מפעיל <code>replan</code>, עם התצפיות עד אותו רגע, עד <code>max_replans</code> פעמים.</p>
<div class="callout">במודלים של היום, היתרון של מקביליות קיים גם בלי תוכנית: Claude מבקש קריאות מקבילות בעצמו כשהן לא תלויות זו בזו. לכן ההשוואה האמיתית היא בין <b>שקיפות ותכנון מחדש</b> לבין <b>קריאה נוספת ושלבים מיותרים</b>. תרגיל 5 מודד את זה על Haiku. אם המספרים החיים יראו שהתוכנית לא משתלמת במשימות קצרות כאלה, זו תוצאה, וצריך לכתוב אותה.</div>`,
    },
    {
      kicker: "עצירה",
      title: "תנאי עצירה: כל הסיבות שריצה נגמרת",
      html: `<p>agent בלי תנאי עצירה טובים הוא תקלה שמחכה לקרות. Barry Zhang מ-Anthropic מסיים את ההרצאה שלו ברשימת בעיות פתוחות, והראשונה שבהן היא אכיפת תקציבים של זמן, כסף וטוקנים. ב-agentkit כל העצירות מגיעות ממקום אחד, <code>should_stop(history, budget)</code>, ונבדקות <b>בסדר קבוע</b>, כך שכאשר כמה כללים חלים, הסיבה דטרמיניסטית:</p>
<ol class="ladder">
<li><b>final_answer</b><span>המודל ענה בלי לבקש כלים. זה הסוף הרגיל. נבדק ראשון, כדי שתשובה שהגיעה בצעד האחרון המותר תיחשב הצלחה ולא חריגה מהתקציב.</span></li>
<li><b>gave_up</b><span>המודל קרא לכלי <code>give_up</code> עם סיבה. זו עצירה <b>מוצלחת</b>: ה-agent ידע שהוא לא יכול להשלים את המשימה, ואמר את זה.</span></li>
<li><b>max_steps</b><span>תקרה קשיחה. כל לולאה צריכה אחת כזו, גם כשיש את כל השאר.</span></li>
<li><b>budget_tokens, budget_cost, budget_time</b><span>כסף וזמן. כלל העלות גם צופה צעד אחד קדימה: אם הצעד הבא יעלה כמו האחרון, האם נחרוג?</span></li>
<li><b>repetition</b><span>אותה קריאה בדיוק (אותו כלי ואותם ארגומנטים) הופיעה <code>repeat_limit</code> פעמים בריצה.</span></li>
<li><b>tool_errors</b><span>בכמה צעדים ברצף, כל הקריאות נכשלו. או שהכלים למטה, או שהמודל לא מצליח לבנות קריאה תקינה.</span></li>
<li><b>no_progress</b><span>בכמה צעדים ברצף, אף צעד לא החזיר תוצאה מוצלחת <b>חדשה</b>. זו הלולאה המוסווית, שבה כל קריאה שונה מהקודמת.</span></li>
</ol>
<p>שלוש סיבות נוספות נקבעות בתוך ה-agent, ולא במדיניות. <code>refusal</code>: המודל סירב. <code>max_tokens</code>: התשובה נחתכה. <code>model_error</code>: ה-API נכשל, גם אחרי ה-retries של llmkit. אלה מצבים שהמדיניות לא יכולה לשנות.</p>
<p><b>למה הסדר חשוב.</b> נניח שבצעד 3 גם הגענו ל-max_steps, גם עברנו את התקציב, וגם חזרנו על אותה קריאה בפעם השלישית. כל שלושת הכללים נכונים, אבל ה-trajectory צריך להגיד סיבה אחת, ותמיד את אותה סיבה. הסדר שלנו שם קודם את מה שהכי חשוב לדעת: האם המשימה הסתיימה, אחר כך האם הגענו לגבולות הקשיחים, ורק בסוף האם המודל תקוע. בתרגיל 6 יש דוגמה לסדר בפעולה. מודל עקשן שקורא שוב ושוב לכלי שלא עובד נעצר על <code>repetition</code>, כי הכלל הזה נבדק לפני <code>tool_errors</code>. אם מעלים את repeat_limit, אותה ריצה נעצרת על tool_errors.</p>
<div class="callout">"עצירה" ו"כישלון" הם לא אותו דבר. <code>gave_up</code> עם הסבר כמו "יש ארבע Shani, לאיזו הכוונה?" הוא תוצאה <b>טובה</b>. <code>max_steps</code> בלי הסבר הוא תוצאה גרועה, גם אם בדרך נאספו כל העובדות. ההערכה בתרגיל 4 סופרת gave_up כעצירה תקינה.</div>`,
    },
    {
      kicker: "עצירה",
      title: "תקציבים: למה כל צעד יקר יותר מהקודם",
      html: `<p>כל צעד שולח את <b>כל</b> השיחה מחדש. לכן עלות הקלט של הצעד ה-n כוללת את הפרומפט של המערכת, את הגדרות הכלים, את המשימה, ואת כל הקריאות והתוצאות של n-1 הצעדים הקודמים. לכן הקלט של כל צעד גדל <b>ליניארית</b> עם מספר הצעדים שקדמו לו, והסכום של ריצה שלמה הוא בסיס כפול מספר הצעדים, ועוד רכיב שגדל <b>בריבוע</b> של מספר הצעדים. בריצות קצרות הבסיס שולט והסכום נראה כמעט ליניארי. הרכיב הריבועי נהיה משמעותי רק כשהריצה ארוכה או כשהתוצאות גדולות. הנה המספרים של t01 עם המודל המזויף (הערכה של תווים חלקי 4, מתומחרת כמו Haiku 5.5, ‏$0.10 למיליון טוקני קלט ו-$0.50 למיליון טוקני פלט, נבדק בנובמבר 2026):</p>
<div class="example"><b>t01, reactive: טוקני הקלט של כל צעד</b><pre dir="ltr">step 1   2,147 in +  27 out   $0.00023   (system + 7 tool definitions + task + 286: the fake model's fixed tool-prompt estimate)
step 2   2,246 in +  51 out   $0.00025   (+ the lookup call and its result)
step 3   2,389 in + 103 out   $0.00029   (+ check_policy)
step 4   2,649 in +  74 out   $0.00030   (+ create_access_request and its result)
total    9,431 in + 255 out   $0.00107   (estimated)</pre></div>
<p>שני דברים בולטים במספרים. הראשון: <b>הבסיס כבד</b>. כמעט 2,000 טוקנים חוזרים בכל צעד, עוד לפני שקרה משהו: פרומפט המערכת, שבע הגדרות כלים (כולל give_up), ו-286 טוקנים של פרומפט הכלים. המספר 286 הוא <b>קבוע של המודל המזויף</b> (<code>TOOL_PROMPT_TOKENS</code> ב-<code>agentkit/fake.py</code>), שמחקה את פרומפט המערכת ש-Anthropic מוסיפה כשיש כלים. הגודל האמיתי של הפרומפט הזה תלוי במודל ובערך של <code>tool_choice</code>, ואת המספר המדויק רואים ב-usage של ריצה חיה. בריצה של 8 צעדים זה כבר 16,000 טוקנים רק על הבסיס. במספרים של t01 רואים גם את הצד השני: הקלט עולה מ-2,147 ל-2,649 טוקנים, תוספת של 100 עד 260 טוקנים לצעד, כך שבריצה הזו הגידול כמעט ליניארי. לכן <b>prompt caching</b> משיעור 4 משתלם במיוחד ב-agents: הבסיס זהה בכל צעד. השני: במשימות קצרות, התוצאות עצמן הן חלק קטן מהעלות. זה ישפיע על ההחלטה מתי למחוק תוצאות ישנות.</p>
<h4>איך מגדירים תקציב</h4>
<ul>
<li><b>max_steps</b>: לפי המשימה הארוכה ביותר שאתה מצפה לה, ועוד מרווח. בסט שלנו המסלול הארוך ביותר הוא 4 צעדים, ולכן 8 זה נדיב.</li>
<li><b>max_cost_usd</b>: לפי ערך המשימה. בקשת גישה שווה אולי סנט אחד, ולכן $0.01 לריצה, שזה פי 10 מהעלות הצפויה. זו המלצה, ולא ברירת מחדל: ב-<code>Budget</code> הערך הוא None (בלי גבול) עד שמגדירים אותו. כלל ההסתכלות קדימה עוצר <b>לפני</b> הצעד שהיה עובר את הגבול, ולא אחריו.</li>
<li><b>max_seconds</b>: לפי ההבטחה למשתמש. אם יש מישהו שמחכה בצ'אט, 60 שניות זה הרבה. כדאי לדעת מה בדיוק נספר: <code>budget_time</code> סוכם את <code>elapsed_s</code> של הצעדים. צעד כולל את קריאת המודל, את הכלים (גם איטיים) ואת ההמתנה לאישור האנושי שבתוכו. הוא <b>לא</b> כולל את קריאת ה-planner שלפני הלולאה, את התכנון מחדש שאחרי צעד שנכשל, ואת קריאת הסיכום (<code>summarize_on_stop</code>) שאחרי העצירה. לכן זמן הקיר של ריצה יכול להיות ארוך מהגבול, ואדם שמאשר לאט "שורף" את תקציב הזמן.</li>
<li><b>max_tokens</b>: שימושי כשהמחיר לא ליניארי. ב-Haiku 5.5, מעל 100,000 טוקני פרומפט כל המחירים מוכפלים פי 5 (נבדק בנובמבר 2026). זה מופיע ב-<code>llmkit/pricing.py</code>.</li>
</ul>
<p>תקציב לריצה הוא רק שכבה אחת. בשיעור 25 (LLM gateway) נוסיף תקציבים למשתמש, לצוות וליום. תקציב לריצה לא מגן מפני מיליון ריצות זולות.</p>
<div class="callout">כשהתקציב נגמר, יש שתי אפשרויות. אפשר להחזיר "Stopped before finishing" עם הסיבה. ואפשר להפעיל <code>summarize_on_stop=True</code>: קריאה אחת נוספת, עם <code>tool_choice="none"</code>, שמבקשת מהמודל לסכם מה נמצא ומה חסר. הקריאה הזו עולה כסף מעבר לתקציב (בתרגיל 3 תמדוד כמה), אבל המשתמש מקבל תשובה שימושית במקום הודעת שגיאה. זו החלטה של מוצר, ולא של טכנולוגיה.</div>`,
    },
    {
      kicker: "עצירה",
      title: "זיהוי חזרות וחוסר התקדמות",
      html: `<p>הלולאה הכי נפוצה ב-agents היא מודל שתקוע: הוא קורא לאותו כלי, מקבל את אותה תוצאה, ולא יודע מה לעשות איתה. בשיעור 14 ראינו את תקלת ה-<code>loop</code> של mockllm. שם רק <code>max_rounds</code> עצר אותה, אחרי שכל הסבבים כבר נוצלו. כאן יש שני כלים מדויקים יותר.</p>
<h4>Fingerprint של קריאה</h4>
<p><code>fingerprint(call)</code> הוא sha256 של שם הכלי ושל הארגומנטים כ-JSON קנוני (עם מפתחות ממוינים). זו בדיוק הפונקציה <code>call_fingerprint</code> של <code>ConfirmationGate</code> משיעור 14. לשתי קריאות עם אותו שם ואותם ארגומנטים יהיה אותו fingerprint, וכל שינוי בארגומנטים ייתן fingerprint אחר. כלל ה-<b>repetition</b> סופר כמה פעמים כל fingerprint של הצעד האחרון הופיע בכל הריצה. עם <code>repeat_limit=3</code>, הקריאה השלישית הזהה עוצרת. בריצה "לולאה זהה" באנימציה זה קורה בצעד 3.</p>
<h4>Hash של תוצאה</h4>
<p>יש לולאה שה-fingerprint לא תופס: מודל שמחפש את Dana פעם לפי "Dana Levi", פעם לפי "dana.levi@acme.example" ופעם לפי "E016". שלוש קריאות שונות, שלושה fingerprints שונים, ושלוש פעמים אותה רשומה בדיוק. לכן לכל תוצאה מוצלחת נשמר <code>result_hash</code>, ולתוצאה שנכשלה נשמר None. גם לקריאה ל-<code>note</code> נשמר None: הפתק הוא רישום פנימי ולא מידע חדש מהעולם, והתוצאה שלו ("Saved. N note(s) kept.") משתנה בכל קריאה, כך שבלי זה מודל שרק כותב פתקים היה נראה כאילו הוא מתקדם, ולא היה נעצר אף פעם. צעד "התקדם" אם הוא החזיר hash שלא נראה קודם בריצה. כלל ה-<b>no_progress</b> עוצר אחרי <code>no_progress_steps</code> צעדים ברצף שאף אחד מהם לא התקדם. בריצה "לולאה מוסווית" זה קורה בצעד 4. כלל ה-repetition היה עוצר אותה רק בצעד 7.</p>
<div class="example"><b>אותה לולאה, דרך שני הכללים</b><pre dir="ltr">step 1  lookup_employee("Dana Levi")              fp 4b4d93  hash 47c49b  NEW      progress
step 2  lookup_employee("dana.levi@acme.example") fp 20ca4f  hash 47c49b  seen     no progress
step 3  lookup_employee("E016")                   fp d0247a  hash 47c49b  seen     no progress
step 4  lookup_employee("Dana Levi")              fp 4b4d93  hash 47c49b  seen     no progress -> no_progress
        (repetition would need fp 4b4d93 a 3rd time: step 7)</pre></div>
<h4>שגיאות ברצף, ותוצאות שגויות</h4>
<p>כלל ה-<b>tool_errors</b> עוצר כשבכמה צעדים ברצף <b>כל</b> הקריאות נכשלו. כדאי לשים לב ש-no_progress היה תופס גם את זה, כי לתוצאה שנכשלה אין hash. אבל סיבה מדויקת יותר עוזרת לדבג: "הכלים למטה" ו"המודל תקוע" הן בעיות שונות, עם פתרונות שונים.</p>
<p>לפעמים הכללים טועים. יש כלים שבהם קריאה חוזרת היא דבר לגיטימי: polling של סטטוס, או קריאה לשעון. כלי כזה צריך להחריג מהספירה, או להגדיל לו את הגבול. גם no_progress יכול לעצור מוקדם מדי: צעד שבו המודל רק כותב פתק לא נחשב התקדמות (ה-Agent רושם לפתק hash של None), גם אם המודל רק מסדר את המחשבות לפני הצעד הבא. בדיוק בגלל זה לכלל יש חלון של כמה צעדים, ולא צעד אחד. צעד שיש בו גם פתק וגם קריאה אמיתית נמדד לפי הקריאה האמיתית.</p>`,
    },
    {
      kicker: "עצירה",
      title: "ויתור מפורש ועצירה מכובדת",
      html: `<p>מודל שלא יכול להשלים משימה בדרך כלל עושה אחד משלושה דברים: ממשיך לנסות עד שהתקציב נגמר, ממציא תשובה, או עונה תשובה עמומה שנשמעת כמו הצלחה. שלושתם גרועים. הפתרון הוא לתת לו <b>דרך מפורשת לעצור</b>. ב-agentkit זה הכלי <code>give_up(reason, missing)</code>, שמוצע למודל בכל ריצה (<code>give_up_tool=True</code>). התיאור שלו אומר מתי להשתמש בו: האדם לא חד-משמעי או לא קיים, חסר מידע, הבקשה היא משהו שאסור לעשות, או שהכלים ממשיכים להיכשל. ה-agent לא מריץ את הכלי הזה. הוא מזהה את הקריאה, עוצר עם <code>stop_reason="gave_up"</code>, ובונה תשובה מהסיבה.</p>
<div class="example"><b>t06: עובד שלא קיים</b><pre dir="ltr">step 1  act:  lookup_employee({"employee": "jonathan.mor@acme.example"})
        obs:  ERR No employee matches 'jonathan.mor@acme.example'. Check the spelling, or ask the user ...
step 2  give_up({"reason": "No Acme employee matches 'jonathan.mor@acme.example'.",
                 "missing": "the person's correct work email"})
STOP gave_up
ANSWER: I could not complete this: No Acme employee matches ... Missing: the person's correct work email</pre></div>
<p>למה כלי, ולא פשוט לבקש מהמודל לענות "I can't"? יש לזה שלוש סיבות. הראשונה: קריאה לכלי היא <b>אות מובנה</b>. הקוד יודע בוודאות שזה ויתור, ולא תשובה רגילה שבמקרה מכילה את המילה can't. השנייה: השדה <code>missing</code> מכריח את המודל לנסח מה חסר. זה הופך ויתור לבקשה ברורה מהמשתמש. השלישית: אפשר <b>למדוד</b> את זה. אם שיעור הוויתורים קופץ אחרי שינוי בפרומפט, זה מידע.</p>
<p>יש מקרה גבולי: משימה עמומה, כמו t05 עם ארבע Shani. מודל יכול לקרוא ל-give_up, אבל הוא יכול גם פשוט לענות בשאלה: "לאיזו Shani הכוונה?". שתי התגובות נכונות, וההערכה מקבלת את שתיהן (התוצאה בזהב היא <code>clarify</code>). מה שלא מתקבל הוא לנחש Shani אחת ולפתוח לה בקשה.</p>
<div class="callout">כשהמדיניות עוצרת בגלל גבול ולא בגלל תשובה, ה-agent לא משאיר אחריו שיחה שבורה. כל הקריאות כבר קיבלו תוצאות, ו-trajectory נגמר בשורת <code>stop</code> עם הסיבה, הפרטים והסכומים. אפשר להמשיך את השיחה, לשמור אותה, או להעביר אותה לאדם. בשיעור 16 נראה checkpoint שמאפשר להמשיך ריצה מאמצע.</div>`,
    },
    {
      kicker: "זיכרון",
      title: "זיכרון בתוך ריצה: מחיקת תוצאות ופתקים",
      html: `<p>ההקשר של agent רק גדל: כל צעד מוסיף קריאה ותוצאה. בריצות ארוכות, למשל agent שקורא עשרות מסמכים או מריץ עשרות פקודות, התוצאות הישנות הן רוב הפרומפט, ומשלמים עליהן בכל צעד מחדש. יש שלוש טכניקות לטפל בזה, מהקלה לכבדה:</p>
<ol class="ladder">
<li><b>מחיקת תוצאות ישנות</b><span>משאירים את N התורות האחרונות של תוצאות כמו שהן, ובכל תור ישן יותר מחליפים את התוכן של כל תוצאה במשפט קצר. ה-ids נשארים, אחרת הספק מחזיר 400. זה <code>clear_old_tool_results</code>, תרגיל 7.</span></li>
<li><b>פתקים (scratchpad)</b><span>כלי <code>note(text)</code> שהמודל קורא לו כדי לשמור עובדה. הפתקים נשמרים בפרומפט של המערכת, ולכן לא נמחקים יחד עם התוצאות.</span></li>
<li><b>Compaction</b><span>כשההקשר מתקרב לגבול, מסכמים את כל השיחה ומתחילים חלון חדש מהסיכום. זה חזק, אבל מאבד פרטים, ועולה קריאת מודל.</span></li>
</ol>
<p>Anthropic מציעה את הטכניקה הראשונה בצד השרת, כ-<b>context editing</b>, עם האסטרטגיה <code>clear_tool_uses_20250919</code> וה-beta header ‏<code>context-management-2025-06-27</code>. לפי התיעוד, ברירות המחדל הן כאלה: המחיקה מתחילה מעל 100,000 טוקני קלט (<code>trigger</code>), נשמרות 3 הקריאות האחרונות (<code>keep</code>), התוצאה שנמחקה מוחלפת בטקסט שאומר למודל שהיא הוסרה, ואפשר להחריג כלים מסוימים (<code>exclude_tools</code>). יש גם אזהרה חשובה: מחיקה <b>שוברת את ה-prompt cache</b> מנקודת המחיקה והלאה. לכן יש פרמטר <code>clear_at_least</code>, שדואג שכל מחיקה תחסוך מספיק כדי להצדיק כתיבה מחדש של ה-cache.</p>
<div class="example"><b>מה המעבדה מראה (memory_demo.py, t01, המודל המזויף)</b><pre dir="ltr">keep all        final_answer  4 steps  3 calls  9,431 input tokens
keep 2          final_answer  4 steps  3 calls  9,384   -> the answer lost "Michal Ben-David"
keep 1          repetition    5 steps  5 calls  11,579  -> forgot, re-fetched, got stopped
keep 1 + notes  final_answer  4 steps  5 calls  10,145  -> 2 note calls, nothing forgotten</pre></div>
<p>שלושה לקחים מהמספרים. הראשון: <b>מחיקה בלי פתקים גורמת לשכחה</b>. מודל שלא רואה יותר את הרשומה של Dana יביא אותה שוב. זה עולה יותר ממה שחסכנו, ובמקרה הגרוע נגמר בלולאה, כמו כאן. השני: <b>שכחה שקטה גרועה יותר מלולאה</b>. עם keep 2 הריצה הצליחה, אבל שם המנהלת נעלם מהתשובה, ורק ההערכה מול הזהב תפסה את זה. השלישי: במשימות קצרות <b>אין מה לחסוך</b>. רוב הפרומפט הוא הבסיס הקבוע, והפתקים אפילו הוסיפו טוקנים. מחיקה משתלמת כשהתוצאות גדולות: מסמכים, לוגים, תוצאות חיפוש.</p>
<div class="callout">ב-Haiku 5.5 המחיר מוכפל פי 5 מעל 100,000 טוקני פרומפט. זה גם סף ברירת המחדל של context editing. agent שמתקרב לגבול הזה בלי ניהול הקשר משלם פי חמישה על כל צעד.</div>`,
    },
    {
      kicker: "שגיאות",
      title: "שגיאות כתצפיות, retries ו-fallbacks",
      html: `<p>בשיעור 14 קבענו את הכלל שהכל נשען עליו: <b>ה-executor לעולם לא זורק</b>. כל כשל, בין אם זה כלי לא מוכר, ארגומנטים לא תקינים, timeout או קריסה, הופך ל-<code>ToolResult(is_error=True)</code>, עם טקסט שנכתב בשביל המודל. ב-agent זה מקבל משמעות נוספת: שגיאה היא <b>תצפית</b>, והמודל מחליט מה לעשות איתה, בדיוק כמו עם כל תצפית אחרת. אבל לא כל ההחלטות צריכות להיות שלו. יש שלוש שכבות של ניסיון חוזר, וכל אחת מטפלת בבעיה אחרת:</p>
<ol class="ladder">
<li><b>שכבת ה-HTTP: llmkit</b><span>שגיאות 429, ‏529, 5xx וניתוקי רשת נוסים שוב אוטומטית, עם backoff (שיעור 2). המודל וה-agent לא יודעים שזה קרה. רק אם כל הניסיונות נכשלו, ה-agent עוצר עם <code>model_error</code>.</span></li>
<li><b>שכבת הכלי: המודל</b><span>כלי שהחזיר "temporarily unavailable, try again" או "Invalid arguments: field required". המודל קורא את השגיאה ומחליט: לנסות שוב (רק אם השגיאה זמנית), לתקן את הארגומנטים, לעבור לכלי אחר, או לוותר. הודעת שגיאה טובה אומרת לו איזו מהאפשרויות מתאימה.</span></li>
<li><b>שכבת התוכנית: ה-agent</b><span>במצב plan, צעד שיש בו קריאה שנכשלה מפעיל תכנון מחדש. ובכל מצב, מדיניות העצירה מגבילה את הכל: repetition ו-tool_errors עוצרים מודל שמנסה שוב ושוב בלי סוף.</span></li>
</ol>
<div class="example"><b>faults_demo.py transient: הכלי נכשל פעם אחת</b><pre dir="ltr">step 1  act:  lookup_employee({"employee": "Dana Levi"})
        obs:  ERR lookup_employee is temporarily unavailable (upstream 503). Try again in a moment.
step 2  think: lookup_employee failed (...). Retrying once.
        act:  lookup_employee({"employee": "Dana Levi"})            same fingerprint: count 2 of 3
        obs:  ok  {"id": "E016", "name": "Dana Levi", ...}
step 3  ...check_policy, then create_access_request, then the answer.   GOLD: SUCCESS</pre></div>
<p><b>Fallbacks</b> הם המשך טבעי של אותו רעיון. אם כלי אחד נכשל, אפשר לנסות דרך אחרת לאותו מידע: <code>list_access_grants</code> מחזיר גם את פרטי העובד, כך שאם <code>lookup_employee</code> למטה, יש מקור חלופי (רק בלי המנהל). אם מודל אחד נכשל, אפשר לעבור למודל אחר (שיעור 25). ואם אין דרך, הדרך האחרונה היא ויתור כן. מה שלא עושים הוא <b>לנסות שוב פעולה עם תופעת לוואי</b> בלי idempotency. retry של <code>create_access_request</code> אחרי timeout יכול ליצור שתי בקשות. בגלל זה יש <code>idempotency_key</code>, ובגלל זה המפתח נבנה מהתוכן (<code>email:system:level</code>) ולא באקראי.</p>
<div class="callout">הבחנה שחוסכת הרבה כאב: <b>שגיאה זמנית</b> (503, timeout) מצדיקה ניסיון חוזר. <b>שגיאה קבועה</b> (עובד לא קיים, מערכת לא מוכרת, ארגומנט לא חוקי) מצדיקה תיקון או ויתור. כלי שמבחין בין השתיים בטקסט השגיאה ("try again" לעומת "check the spelling, or ask the user") חוסך למודל צעדים שווא. מודל ש<b>לא</b> מבחין ביניהן הוא בדיוק התרחיש tool-down-stubborn בתרגיל 6.</div>`,
    },
    {
      kicker: "בטיחות",
      title: "בטיחות: תופעות לוואי, הרשאות ותקציב",
      html: `<p>agent מגדיל את הסיכון של כלים, כי אף אחד לא רואה את הצעדים בזמן שהם קורים. בשיעור 14 בנינו את אבני הבניין: <code>ConfirmationGate</code> עם token חד-פעמי שקשור לקריאה המדויקת, <code>Taint</code>, ‏<code>least privilege</code> ו-idempotency. ב-agentkit הן מחוברות ללולאה:</p>
<ul>
<li><b>כל כלי עם <code>side_effect=True</code> עובר דרך <code>confirm(call)</code></b>, לפני שהוא נשלח ל-executor. אם האדם אישר, ה-agent מנפיק token דרך <code>gate.approve(call)</code>, וה-executor מריץ רק קריאה שיש לה token תקף. אם האדם סירב, המודל מקבל <code>"The human reviewer DECLINED this action ... Do not call it again"</code>. אם אין hook בכלל, הכלי <b>לעולם</b> לא רץ. המודל לא רואה tokens, ולכן טקסט במסמך לא יכול לייצר אחד.</li>
<li><b>שורת <code>confirm</code> ב-trajectory</b> רושמת מה הוצג לאדם, מה הוא החליט, והאם תוכן לא אמין (מסמך שנקרא עם read_document) נכנס לשיחה קודם. אם כן, זה סימן לאדם להיות חשדן במיוחד.</li>
<li><b>הודעת סירוב ברורה</b> מונעת לולאה. מודל שמקבל "NOT executed" כללי עלול לנסות שוב. mockllm עושה את זה בכוונה (תרגיל 2), ונעצר על <code>repetition</code> אחרי שלושה ניסיונות. מודל אמיתי שקיבל "DECLINED, do not retry" בדרך כלל מדווח ועוצר.</li>
<li><b>least privilege לכל משימה</b>: <code>registry.subset([...])</code> מציע רק את הכלים שהמשימה צריכה. agent שעונה על שאלה לא צריך את <code>create_access_request</code> בכלל. כלי שלא הוצע לא יכול להיקרא.</li>
<li><b>התקציב הוא גם מנגנון בטיחות.</b> הוא חוסם agent שנחטף על ידי הזרקה ומנסה לרוץ בלי סוף, וחוסם באג שגורם ללולאה יקרה. max_steps קטן הוא הגנה זולה ואמינה.</li>
</ul>
<div class="example"><b>מה האדם רואה (confirm_hook של המעבדה, --approve ask)</b><pre dir="ltr">&gt;&gt;&gt; The agent wants to run create_access_request({"employee": "dana.levi@acme.example",
    "system": "aws-production", "access_level": "admin", "justification": "...",
    "duration_days": 3, "idempotency_key": "dana.levi@acme.example:aws-production:admin"})
&gt;&gt;&gt; Approve? [y/N]</pre></div>
<p>שים לב מה האדם מאשר: את <b>הארגומנטים המדויקים</b>, ולא את תיאור הכוונה של המודל. "פתח לדנה בקשה" עלול להסתיר duration_days של 365 או רמת owner. ה-token קשור ל-fingerprint של הקריאה, כך שאם המודל ישנה ארגומנט אחרי האישור, האישור לא יחול. בשיעור 16 האישור יהפוך לצומת בגרף של LangGraph, שיכול לחכות לאדם שעות, עם checkpoint. בשיעור 24 נחזור לכל משטח התקיפה.</p>`,
    },
    {
      kicker: "בחירה",
      title: "מתי agent הוא הכלי הלא נכון",
      html: `<p>המאמר של Anthropic מגדיר: <b>workflow</b> הוא מערכת שבה מודלים וכלים מתוזמרים לאורך מסלולי קוד מוגדרים מראש. <b>agent</b> הוא מערכת שבה המודל מכוון את התהליך ואת השימוש בכלים בעצמו. ההמלצה שם היא להתחיל מהפתרון הפשוט ביותר, ולהוסיף מורכבות רק כשצריך. Barry Zhang מוסיף שאלות שכדאי לשאול לפני שנותנים אוטונומיה: האם המשימה מורכבת ועמומה מספיק? האם היא שווה את העלות? האם המודל באמת מסוגל לבצע את החלקים הקריטיים? כמה יקרה טעות, וכמה קל לגלות אותה?</p>
<p>בקשת גישה היא מקרה מעניין, כי רוב הבקשות הן <b>באותה צורה</b>: אדם אחד, מערכת אחת, רמה אחת. בשביל הצורה הזו אפשר לכתוב workflow קבוע: חילוץ שדות, lookup, בדיקת הרשאות קיימות אם ביקשו, check_policy, החלטה בקוד, create עם אישור, ותשובה. זה <code>agentkit.workflow.run_workflow</code>, והוא כותב trajectory באותו פורמט, כך שאותה הערכה בודקת את שניהם.</p>
<div class="example"><b>eval_tasks.py --modes react,workflow (offline)</b><pre dir="ltr">== react (fake)      success 15/15   mean steps 2.93   mean tool calls 1.93   cost $0.01109 (estimated)
== workflow (fake)   success 12/15   mean steps 1.93   mean tool calls 1.93   cost $0.00000
   failed: t07 (compare two systems), t08 (list someone's access), t11 (what does the document say)
   -> all three: "unsupported", outside the workflow's shape</pre></div>
<p>ה-workflow לא עולה כלום בלי מודל (offline הוא מחלץ שדות עם regex). מול Haiku יש בו קריאה אחת, לחילוץ עם structured output. הוא צפוי לחלוטין, קל לבדוק אותו בבדיקות יחידה, ואין לו מה לתקצב. אבל הוא לא יודע לעשות שום דבר מחוץ לצורה שלו. ה-agent עולה יותר, אבל מתמודד גם עם "השווה בין github ל-aws-production" וגם עם "מה המסמך אומר". בפועל, המערכות הטובות משלבות: <b>workflow למקרה הנפוץ, ו-agent לשאר</b>. נתב בכניסה מחליט לאן כל בקשה הולכת. זה בדיוק דפוס ה-routing שנפגוש בבורר הדפוסים של שיעור 19.</p>
<div class="callout">כלל אצבע: אם אתה יכול לצייר את תרשים הזרימה לפני שראית את הקלט, תכתוב workflow. אם התרשים תלוי במה שיתגלה בדרך (אילו מסמכים קיימים, מה הכלי החזיר, מה חסר), תכתוב agent. ותמיד תשאל אם אפשר לצמצם את ה-agent לכמה workflows ונתב. בשיעור 16 נבנה את ה-workflow הזה כגרף ב-LangGraph, עם צומת אישור אנושי ו-checkpoints.</div>`,
    },
    {
      kicker: "הערכה",
      title: "הערכת agents: התוצאה וגם הדרך",
      html: `<p>תשובה סופית נכונה יכולה להסתיר trajectory גרוע: מודל שקרא לאותו כלי חמש פעמים, ניחש לפני שבדק, או פתח בקשה כפולה ובמקרה גם ענה נכון. ולהפך, תשובה שנראית שגויה יכולה להיות ויתור נכון. לכן מעריכים agents בשתי רמות, ושתיהן מחושבות מתוך ה-trajectory, ולא מתוך הטקסט בלבד:</p>
<ol class="ladder">
<li><b>תוצאה (outcome)</b><span>האם המצב בעולם הוא המצב שרצינו? בבקשת גישה זה אומר: נוצרה בדיוק בקשה אחת, עם העובד, המערכת, הרמה, משך הזמן והמסלול הנכונים, או שלא נוצרה אף אחת. את זה בודקים מתוך <b>התוצאה של create_access_request</b>, כלומר מתוך מה שבאמת נכתב, ולא מתוך מה שהמודל אמר שעשה.</span></li>
<li><b>תהליך (trajectory)</b><span>כמה צעדים וקריאות היו, כמה מהן <b>מיותרות</b> (קריאה זהה אחרי שכבר הצליחה), מה ה<b>יעילות</b> (optimal_calls חלקי מספר הקריאות), האם הופעלו כלים אסורים, האם יש <b>סתירה לראיות</b> (התשובה מזכירה מסלול שונה מזה ש-check_policy החזיר), ומה עלה כל דבר.</span></li>
</ol>
<div class="example"><b>שורה אחת בסט המשימות (data/tasks.jsonl)</b><pre dir="ltr">{"id": "t01", "task": "Dana Levi asks for admin access on AWS production for 3 days ...",
 "gold": {"outcome": "request_created",
          "request": {"employee": "E016", "system": "aws-production", "access_level": "admin",
                      "duration_days": 3, "route": "needs_security"},
          "answer_contains": ["Michal Ben-David", "needs_security"],
          "required_tools": ["lookup_employee", "check_policy", "create_access_request"],
          "optimal_calls": 3}}</pre></div>
<p><b>אמינות, ולא רק הצלחה.</b> agent שמצליח ב-80% מהריצות לא מצליח ב-80% מהמשימות באופן עקבי. ב-τ-bench (Yao ועמיתים, 2024) הוצע המדד <b>pass^k</b>: ההסתברות שהמשימה מצליחה בכל k ניסיונות. במאמר, gpt-4o השיג בתחום הקמעונאות pass^8 נמוך מ-25%. כשמריצים את אותה משימה שמונה פעמים, ברוב המשימות לפחות ריצה אחת נכשלת. במודל אמיתי שווה להריץ כל משימה כמה פעמים, ולהסתכל על הפיזור, ולא רק על הממוצע. במודל המזויף של המעבדה אין לזה משמעות, כי הוא דטרמיניסטי.</p>
<p><b>מה המדדים תפסו במעבדה.</b> התרחיש stale (read_document מחזיר את v2.1) עובר כל בדיקה של הלולאה: אין שגיאות, אין חזרות, והתשובה נשמעת בטוחה. רק ההשוואה לזהב ("2 business days") מגלה שהיא שגויה. התרחיש misleading עם מודל תמים נתפס על ידי <code>evidence_conflict</code>: התשובה אומרת auto_approve, ו-check_policy אמר needs_security. ושכחה עם keep 2 נתפסה כי שם המנהלת חסר בתשובה. בשיעור 23 נוסיף לזה LLM-as-judge, שמעריך את איכות ה-trajectory במקומות שבהם קשה לנסח כלל.</p>`,
    },
    {
      kicker: "תצפיות",
      title: "ה-trajectory: יומן ריצה שאפשר לקרוא, להעריך ולצייר",
      html: `<p>Barry Zhang ממליץ לדבג agent מנקודת המבט של המודל: לקרוא את מה שהוא ראה בכל צעד, ולשאול אם עם המידע הזה היית מחליט אחרת. לשם כך צריך רישום מלא. ב-agentkit כל ריצה כותבת קובץ JSONL, שורה לכל אירוע, ואותן שורות נשמרות גם בזיכרון, ב-<code>AgentResult.records</code>:</p>
<ul>
<li><b>run</b>: מזהה ריצה, המשימה, המודל, המצב (react, plan או workflow), התקציב המלא והכלים שהוצעו.</li>
<li><b>plan</b>: התוכנית. בכל תכנון מחדש נרשמת שורה נוספת, עם הסיבה ועם העלות של קריאת התכנון.</li>
<li><b>confirm</b>: איזו קריאה הוצגה לאדם, האם הוא אישר, והאם תוכן לא אמין נכנס לשיחה קודם.</li>
<li><b>step</b>: הטקסט של המודל, הקריאות (שם, ארגומנטים ו-fingerprint), התוצאות (שגיאה או לא, hash, ‏600 התווים הראשונים, ותוצאות של תופעות לוואי במלואן), טוקנים, עלות, סכום מצטבר, זמנים, וההחלטה של המדיניות.</li>
<li><b>trim</b>: כמה תוצאות נמחקו.</li>
<li><b>stop</b>: הסיבה, פירוט, וסכומים: צעדים, קריאות, שגיאות, טוקנים, עלות וזמן. בנוסף, התשובה הסופית, ו-estimated_cost כשהטוקנים מוערכים.</li>
</ul>
<p>הפורמט הזה הוא ממשק בין חלקים: <code>format_trajectory</code> מדפיס אותו, <code>score_trajectory</code> מעריך אותו, ו-<code>to_spans</code> ממיר אותו ל-spans בפורמט של obskit משיעור 22. ה-span הראשי הוא <code>invoke_agent company_brain</code>, ותחתיו יש span ‏<code>chat</code> לכל צעד ו-span ‏<code>execute_tool</code> לכל קריאה, עם אותם שמות שדות של OpenTelemetry GenAI. כך <code>python -m obskit.viewer</code> מצייר ריצה כ-waterfall, ו-<code>obskit.analyze</code> מחשב עליה עלות ואחוזונים. אם יש tracer פעיל, <code>Agent(trace=True)</code> מייצר את ה-spans בזמן אמת.</p>
<div class="example"><b>run_agent.py: הפלט של format_trajectory (מקוצר)</b><pre dir="ltr">RUN t01  model=fake-haiku  mode=react  budget: steps&lt;=8 cost&lt;=0.02 tokens&lt;=None time&lt;=60.0
  step 1  tokens=2147+27  cost=$0.00023  total=$0.00023
    think: I need the employee record and manager.
    act:   lookup_employee({"employee": "Dana Levi"})  #4b4d93bd2452
    obs:   ok  {"id": "E016", "name": "Dana Levi", "email": "dana.levi@acme.example", ...
    policy -&gt; continue
  ...
  confirm APPROVED: create_access_request({"employee": "dana.levi@acme.example", ...})
  ...
STOP final_answer  steps=4 tool_calls=3 errors=0 tokens=9431+255 cost=$0.00107 (estimated)</pre></div>
<div class="callout">ב-production, ה-trajectory מכיל מידע רגיש: שמות עובדים, הרשאות ותוכן של מסמכים. ב-obskit יש מעבד redaction (שיעור 22), ו-content capture כבוי כברירת מחדל, לפי ה-GenAI conventions. כדאי לנהוג באותה זהירות גם בקבצי ה-JSONL: לא להעלות אותם ל-git, ולהגדיר להם מדיניות שמירה.</div>`,
    },
    {
      kicker: "מעשי",
      title: "ערכי ברירת מחדל, ומה לבדוק לפני production",
      html: `<p>אלה הערכים שאנחנו ממליצים עליהם ב-agentkit, וההיגיון מאחורי כל אחד. חלקם ברירות מחדל של <code>Budget</code> (‏max_steps, ‏repeat_limit, ‏no_progress_steps, ‏max_consecutive_errors), וחלקם ערכים שהסקריפטים מגדירים, כי ב-<code>Budget</code> העלות, הטוקנים והזמן הם None, כלומר לא נבדקים. אלה נקודות פתיחה, לא חוקים. את הערכים הנכונים קובעים לפי המדידות על סט המשימות שלך.</p>
<ul>
<li><b>max_steps = 8</b>: פי שניים מהמסלול הארוך ביותר בסט (4 צעדים). agent שצריך יותר ממשימה כזו כנראה תקוע.</li>
<li><b>max_cost_usd = 0.01 לריצה</b> (המלצה): בערך פי 10 מהעלות הצפויה ב-Haiku 5.5. ביחד עם כלל ההסתכלות קדימה, הריצה נעצרת לפני החריגה. בספרייה ברירת המחדל היא None. בסקריפטים: <code>eval_tasks.py</code> משתמש ב-$0.01 למשימה, ו-<code>run_agent.py</code>, <code>faults_demo.py</code> ו-<code>memory_demo.py</code> ב-$0.02.</li>
<li><b>max_seconds = 60 עד 90</b> (המלצה): לפי מי שמחכה. בספרייה ברירת המחדל היא None. <code>run_agent.py</code> משתמש ב-60 ו-<code>eval_tasks.py</code> ב-90. כלי איטי (<code>slow:S</code> ב-faults) וההמתנה לאישור נספרים כאן. ה-planner וקריאת הסיכום לא נספרים.</li>
<li><b>repeat_limit = 3</b>: ניסיון, ניסיון חוזר אחד אחרי שגיאה זמנית, ועצירה. 2 קשוח מדי, כי הוא חוסם את ה-retry הלגיטימי.</li>
<li><b>no_progress_steps = 3</b>: שלושה צעדים בלי מידע חדש (צעד של פתקים בלבד נחשב צעד בלי מידע חדש). פחות מזה יעצור agent שעוצר לכתוב פתק או שניים, ויותר מזה יבזבז.</li>
<li><b>max_consecutive_errors = 3</b>: אחרי שלושה צעדים שבהם הכל נכשל, הכלים כנראה למטה.</li>
<li><b>max_replans = 1</b>: תכנון מחדש אחד. אם גם התוכנית המתוקנת נכשלת, עדיף לוותר מאשר להמשיך לתכנן.</li>
<li><b>give_up_tool = True</b>, ‏<b>confirm = None</b> (אף אחד לא מאשר, ולכן תופעות לוואי לא רצות עד שמחברים אדם), ‏<b>keep_tool_results = None</b> (בלי מחיקה, עד שמודדים שצריך).</li>
</ul>
<h4>רשימת בדיקה לפני שמשחררים agent</h4>
<ol>
<li>יש סט משימות עם תוצאות זהב, כולל משימות שבהן <b>אסור</b> לפעול ומשימות עמומות.</li>
<li>כל תופעת לוואי עוברת אישור, עם idempotency key שנבנה מהתוכן.</li>
<li>הרצת את כל התרחישים של faults: כלי שנכשל, כלי למטה, מסמך מטעה, לולאות. לכל אחד ידוע מה עוצר אותו.</li>
<li>אמינות: כל משימה רצה כמה פעמים על המודל האמיתי, ונמדד הפיזור.</li>
<li>ה-trajectories נשמרים (עם redaction), ומישהו קורא אותם באופן קבוע, לא רק כשמשהו נשבר.</li>
<li>שאלת את עצמך בכנות אם workflow קבוע היה עושה את רוב העבודה.</li>
</ol>`,
    },
    {
      kicker: "Company Brain",
      title: "איפה זה נכנס ב-Company Brain",
      html: `<p>שלב 3 של Company Brain הוא <b>פעולות</b>: מעבר מעוזר שעונה לעוזר שעושה. בשיעור 14 הוא קיבל כלים. בשיעור הזה הוא מקבל לולאה עם גבולות. זה ה-agent שמטפל בבקשות גישה בשפה חופשית, וזה מה שהוא יודע לעשות עכשיו:</p>
<ul>
<li>להבין בקשה כמו "Dana needs admin on AWS prod for 3 days", ולברר בעצמו מי העובדת, מי המנהלת שלה, מה המסלול לפי המדיניות ומה כבר קיים.</li>
<li>לפתוח בקשה <b>רק</b> כשהמשתמש ביקש, ורק אחרי בדיקת מדיניות ואישור של אדם. לא לפתוח כשההרשאה כבר קיימת, או כשהמשתמש אמר "רק אם זה auto_approve".</li>
<li>לשאול כשהבקשה עמומה ("איזו Shani?"), ולוותר בצורה מסודרת כשהעובד לא קיים או כשהכלים למטה.</li>
<li>לעצור לפני שהוא מוציא יותר מדי, ולתעד כל צעד ב-trajectory שאפשר להעריך ולצייר.</li>
</ul>
<p>מה חסר עדיין, ומתי זה מגיע. <b>שיעור 16</b>: ההחלטה המרכזית של השיעור הזה מתממשת. רוב הבקשות יעברו ב-workflow קבוע ב-LangGraph, עם צומת אישור שיכול לחכות לאדם שעות (checkpoint), וה-agent יטפל רק במה שלא מתאים לצורה. <b>שיעור 17</b>: ששת הכלים יוגשו כ-MCP server, כך שגם Claude Desktop וגם agents אחרים יוכלו להשתמש בהם. <b>שיעור 18</b>: agent לבקשות ו-agent למסמכים יעבדו יחד. <b>שיעורים 22 ו-23</b>: ה-trajectories יגיעו ל-Phoenix או ל-Langfuse, וההערכה תרוץ ב-CI, עם LLM-as-judge.</p>
<div class="callout">במעבדה תריץ את ה-agent על 15 משימות בשלושה מצבים (reactive, ‏plan ו-workflow), תכתוב מדיניות עצירה, מדדי trajectory ומחיקת תוצאות, ותשרה כשלים. כל זה offline ובחינם, ואחר כך מול Haiku, בעלות כוללת של בערך 5 עד 15 סנטים. אם משהו שתמדוד סותר את מה שכתוב כאן, תכתוב לי: בשביל זה מודדים.</div>`,
    },
  ],

  sims: [
    {
      id: "l15traj",
      title: "סייר trajectories: לעבור צעד אחרי צעד על ריצות מוקלטות",
      lead: "תשע ריצות אמיתיות של agentkit, שהוקלטו מהמעבדה. רובן עם המודל המזויף, ואחת מול mockllm. בוחרים ריצה, ועוברים צעד אחרי צעד. בכל צעד מופיעים ארבעה דברים: מה המודל כתב, אילו קריאות הוא ביקש (עם fingerprint), מה חזר (עם hash), ומה מדיניות העצירה החליטה. בצד מופיעים הסכומים המצטברים, ובסוף בדיקת הזהב: האם הריצה הצליחה, ואם לא, למה.",
      tasks: [
        "פתח את <b>t01 reactive</b> ואחריו את <b>t01 plan</b>. כמה צעדים וכמה קריאות היו בכל אחת? באיזה צעד בריצת ה-plan רצו שתי קריאות במקביל? כמה עלתה קריאת התכנון, והאם החיסכון בצעד אחד כיסה אותה?",
        "פתח את <b>t01 keep_tool_results=1</b>. באיזה צעד המודל קורא שוב ל-lookup_employee, ולמה? (רמז: חפש את שורות ה-trim.) איזה כלל עצר את הריצה, ומה היה מונע את כל זה?",
        "פתח את <b>t11 stale</b>. אין שגיאות, אין חזרות, והתשובה נשמעת בטוחה. מה בדיקת הזהב מצאה? איזה מנגנון בלולאה היה יכול לתפוס את זה, אם בכלל?",
        "פתח את <b>t01 on mockllm, human declines</b>. כמה פעמים ה-mock ניסה שוב אחרי הסירוב? למה מודל אמיתי שמקבל DECLINED בדרך כלל לא עושה את זה, ומה תפס את ה-mock?",
      ],
    },
    {
      id: "l15budget",
      title: "סימולטור מדיניות עצירה: איזה כלל עוצר, ומתי",
      lead: "בוחרים תרחיש: רצף צעדים עם קריאות, תוצאות, שגיאות ועלויות. אחר כך מזיזים את הגבולות של ה-Budget. הסימולטור מריץ את אותה מדיניות כמו <code>agentkit.should_stop</code> (אותו קוד, ב-JavaScript) אחרי כל צעד. בטבלת הצעדים רואים איפה כל כלל היה עוצר אם הוא היה לבד, ואיזה כלל באמת עוצר, לפי הסדר.",
      tasks: [
        "בחר <b>לולאה מוסווית</b> עם ברירות המחדל. איזה כלל עוצר, ובאיזה צעד? עכשיו כבה את no_progress (0). מתי repetition תופס את אותה לולאה, וכמה זה עלה ביותר?",
        "בחר <b>כלי למטה, מודל עקשן</b>. עם repeat_limit=3 העצירה היא repetition. העלה את repeat_limit ל-6. מה עוצר עכשיו? ואם תוריד גם את max_consecutive_errors ל-0?",
        "בחר <b>ריצה תקינה ארוכה</b>, והורד את max_cost בהדרגה. באיזה ערך הריצה כבר לא מגיעה לתשובה הסופית? שים לב לכלל ההסתכלות קדימה: לפעמים הוא עוצר כשהעלות עוד מתחת לגבול. למה זה הגיוני?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/15-agent-loops",
    intro: "המעבדה נמצאת בתיקייה labs/15-agent-loops. החבילה החדשה <b>agentkit/</b> בנויה מעל toolkit משיעור 14. יש בה <code>Agent</code> (לולאה עם תקציב, מדיניות עצירה, give_up, אישור אנושי, מצב plan, פתקים ומחיקת תוצאות), trajectory ב-JSONL שאפשר להמיר ל-spans של obskit, מדדי הערכה, הזרקת תקלות בצד הכלים, ו-workflow קבוע להשוואה. יש שלושה סוגי מודלים: <b>fake</b> (מודל מבוסס חוקים, דטרמיניסטי וחינמי, עם טוקנים מוערכים), <b>mock</b> (mockllm עם צורות ה-wire האמיתיות), ו-<b>Haiku 5.5</b> בשביל המדידה האמיתית. סט של 15 משימות של Acme עם תוצאות זהב נמצא ב-<code>data/tasks.jsonl</code>.",
    setup: [
      'cd ~/ai-engineer-course-starter && source .venv/bin/activate',
      "python -m pytest -q tests/test_agentkit.py         # environment tests for agentkit",
      "python -m pytest -q labs/15-agent-loops/tests      # your exercises: all fail at first",
    ],
    tools: [
      "<b>agentkit:</b> <code>Agent(llm, registry, budget=Budget(...), confirm=..., mode=\"react\"|\"plan\", keep_tool_results=N, scratchpad=True, log_path=...)</code>, ו-<code>res = agent.run(task)</code> מחזיר <code>stop_reason</code>, <code>text</code>, <code>steps</code>, <code>cost_usd</code> ו-<code>records</code>. בנוסף: <code>should_stop</code>, ‏<code>score_trajectory</code>, ‏<code>format_trajectory</code>, ‏<code>to_spans</code>, ‏<code>with_faults</code> ו-<code>run_workflow</code>.",
      "<b>המודלים:</b> <code>--model fake</code> הוא ברירת המחדל (<code>FakeLLM(AcmeHeuristic())</code>), עם אפשרויות שמשחזרות כשלים: <code>--loop repeat|paraphrase</code>, ‏<code>--stubborn</code>, ‏<code>--naive-docs</code>. ‏<code>--model mock</code> מריץ את mockllm עם <code>data/mock_script.json</code>. ‏<code>--model anthropic:claude-haiku-5-5</code> הוא המודל האמיתי.",
      "<b>תקלות:</b> תקלות בצד הכלים עוברות ב-<code>--fault tool=mode</code>. המצבים: <code>error:N</code>, ‏<code>error</code>, ‏<code>crash:N</code>, ‏<code>slow:S</code>, ‏<code>misleading</code> (מסמך מושתל) ו-<code>stale</code> (המדיניות הישנה v2.1). תקלות של המודל עוברות ב-<code>--mock-fault loop</code>.",
      "<b>הנתונים:</b> מדיניות v2.2. ‏auto_approve: כלי מהרשימה המאושרת, ברמה בסיסית, בלי מידע רגיש. ‏needs_manager: editor, ‏write, או כלי שלא ברשימה. ‏needs_security: admin, פרודקשן, מידע של לקוחות או מידע פיננסי, או OAuth. ‏Dana Levi היא E016, והמנהלת שלה Michal Ben-David (E005). יש ארבע Shani. כל הפרטים נמצאים ב-README של המעבדה.",
      "<b>mine.py:</b> שלושה תרגילי קוד: <code>should_stop</code> (תרגיל 3), <code>score_trajectory</code> ו-<code>summarize_scores</code> (תרגיל 4), ו-<code>clear_old_tool_results</code> (תרגיל 7).",
    ],
    exercises: [
      { id: "ex1", title: "ריצה ראשונה: לקרוא trajectory", text: "המשימה היא t01: <bdi>Dana Levi asks for admin access on AWS production for 3 days ... Who is her manager, what does the policy say, and open the request</bdi>. הנתונים שצריך: Dana היא E016, המנהלת שלה Michal Ben-David (E005), ו-admin על aws-production הוא needs_security לפי מדיניות v2.2. הרץ את המשימה עם המודל המזויף, אחר כך מול mockllm, ובסוף מול Haiku עם --approve ask. בכל צעד ב-trajectory יש ארבעה חלקים: think, ‏act (עם fingerprint), ‏obs ו-policy. ענה על השאלות: כמה צעדים וכמה קריאות היו, ולמה יש צעד אחד יותר מקריאות? איפה בדיוק התבקש אישור? למה כל צעד יקר יותר מהקודם? והאם Haiku הריץ lookup ו-check_policy במקביל? לסיום, צייר את הריצה כ-waterfall עם obskit.viewer.", cmd: "python labs/15-agent-loops/run_agent.py t01\npython labs/15-agent-loops/run_agent.py t01 --model mock\npython labs/15-agent-loops/run_agent.py t01 --model anthropic:claude-haiku-5-5 --approve ask\npython labs/15-agent-loops/run_agent.py t01 --spans labs/15-agent-loops/results/spans.jsonl\npython -m obskit.viewer labs/15-agent-loops/results/spans.jsonl -o labs/15-agent-loops/results/spans.html" },
      { id: "ex2", title: "תופעות לוואי מאחורי אדם", text: "המשימה היא t02: <bdi>Avital Tal needs a Figma editor seat. Who approves it? File the request.</bdi> המנהלת של Avital (E017) היא Dana Levi, ו-Figma editor הוא needs_manager. הרץ שלוש פעמים: עם אישור, עם סירוב, ובלי hook בכלל. בכל ריצה מצא את שורת ה-confirm ואת מה שהמודל קיבל בחזרה. אחר כך הרץ את t01 מול mockllm עם סירוב. ה-mock ינסה שוב ושוב. איזה כלל עוצר אותו, ואחרי כמה ניסיונות? למה \"DECLINED, do not retry\" עדיף על שגיאה כללית?", cmd: "python labs/15-agent-loops/run_agent.py t02 --approve yes\npython labs/15-agent-loops/run_agent.py t02 --approve no\npython labs/15-agent-loops/run_agent.py t02 --approve none\npython labs/15-agent-loops/run_agent.py t01 --model mock --approve no" },
      { id: "ex3", title: "מדיניות עצירה (קוד)", text: "ממש את should_stop ב-mine.py. יש אחד-עשר כללים, לפי הסדר: empty, ‏final_answer, ‏gave_up, ‏max_steps, ‏budget_tokens, ‏budget_cost (כולל הסתכלות קדימה), ‏budget_time, ‏repetition (fingerprint של הצעד האחרון שמופיע repeat_limit פעמים בכל ההיסטוריה), ‏tool_errors, ‏no_progress (אף hash חדש ב-w הצעדים האחרונים), ו-continue. כל StepRecord מחזיק ערכים של הצעד שלו, לא סכומים מצטברים. אחר כך הרץ את ה-agent עם המדיניות שלך: מול --loop repeat, מול --loop paraphrase (אחרי כמה צעדים כל כלל היה עוצר אותה?), ומול --max-cost נמוך, עם --summarize ובלעדיו. כמה עלתה קריאת הסיכום?", cmd: "python -m pytest -q labs/15-agent-loops/tests/test_ex3_policy.py\npython labs/15-agent-loops/run_agent.py t01 --loop repeat --mine\npython labs/15-agent-loops/run_agent.py t01 --loop paraphrase --mine\npython labs/15-agent-loops/run_agent.py t01 --max-cost 0.0005 --mine\npython labs/15-agent-loops/run_agent.py t01 --max-cost 0.0005 --summarize --mine" },
      { id: "ex4", title: "מדדי trajectory (קוד)", text: "ממש את score_trajectory ואת summarize_scores ב-mine.py. ההגדרות: הצלחה היא עצירה רגילה, תוצאה שתואמת לזהב (בקשה אחת עם השדות הנכונים, או אף בקשה), כלים חובה שהצליחו, כלים אסורים שלא רצו, ועובדות שמופיעות בתשובה. בנוסף: steps, ‏tool_calls (בלי note), ‏redundant_calls (קריאה זהה אחרי שכבר הצליחה; ניסיון חוזר אחרי כשל לא נחשב), efficiency, ‏evidence_conflict ועלות. סט המשימות נמצא ב-data/tasks.jsonl: שש משימות שבהן צריך לפתוח בקשה, שבע שבהן אסור, אחת עמומה (t05, ארבע Shani) ואחת על המסמך (t11). הרץ את ההערכה עם המדדים שלך, ואחר כך שוב עם --fault lookup_employee=error:1. אילו מדדים זזו?", cmd: "python -m pytest -q labs/15-agent-loops/tests/test_ex4_metrics.py\npython labs/15-agent-loops/eval_tasks.py --mine\npython labs/15-agent-loops/eval_tasks.py --mine --fault lookup_employee=error:1" },
      { id: "ex5", title: "Reactive מול plan-then-act", text: "הרץ את 15 המשימות בשני המצבים, offline ומול Haiku. ההרצה החיה היא 30 ריצות, בערך 3 עד 8 סנטים, והסקריפט עוצר אם העלות עוברת $0.30. השווה: הצלחה, צעדים, קריאות, יעילות ועלות להצלחה. offline, מצב plan חוסך צעדים, כי הוא מריץ קריאות במקביל, אבל ב-t05 וב-t10 הוא מבזבז קריאות שהתוכנית קבעה מראש. מול Haiku: האם הוא מריץ קריאות במקביל גם במצב reactive? האם קריאת התכנון משתלמת? אם המספרים סותרים את השקפים, תכתוב.", cmd: "python labs/15-agent-loops/eval_tasks.py --modes react,plan\npython labs/15-agent-loops/eval_tasks.py --modes react,plan --model anthropic:claude-haiku-5-5\npython labs/15-agent-loops/eval_tasks.py --modes plan --tasks t05,t10 --show" },
      { id: "ex6", title: "להשרות כשלים ולראות התאוששות", text: "faults_demo.py מריץ תשעה תרחישים. transient: כלי שנכשל פעם אחת. tool-down: כלי שתמיד נכשל, והמודל מוותר. tool-down-stubborn: אותו כלי, עם מודל עקשן. misleading: מסמך מושתל שאומר ש-admin על aws-production הוא auto_approve, בזמן ש-check_policy אומר needs_security. stale: המדיניות v2.1 (בדיקת אבטחה ב-3 ימי עבודה, בלי תפוגה) חוזרת במקום v2.2 (2 ימי עבודה, תפוגה אחרי 90 יום). loop-repeat ו-loop-paraphrase: לולאות. mock-loop: תקלת הלולאה של mockllm. ambiguous: ארבע Shani במצב plan, עם תכנון מחדש. לכל תרחיש ענה: מה עצר את הריצה, האם היא נכונה מול הזהב, ומי תפס את הבעיה (המודל, המדיניות, או רק ההערכה). ב-misleading הרץ גם עם --careful וגם מול Haiku: האם הוא מעדיף את check_policy, כמו שהפרומפט מבקש, ומזכיר את הסתירה?", cmd: "python labs/15-agent-loops/faults_demo.py all\npython labs/15-agent-loops/faults_demo.py misleading\npython labs/15-agent-loops/faults_demo.py misleading --careful\npython labs/15-agent-loops/faults_demo.py misleading --model anthropic:claude-haiku-5-5\npython labs/15-agent-loops/faults_demo.py ambiguous --mode plan\npython labs/15-agent-loops/faults_demo.py tool-down-stubborn --repeat-limit 10" },
      { id: "ex7", title: "זיכרון בתוך ריצה (קוד)", text: "ממש את clear_old_tool_results ב-mine.py. N תורות התוצאות האחרונות נשארות כמו שהן. בכל תור ישן יותר, תוכן התוצאות מוחלף ב-placeholder, וה-call_id, ה-name וה-is_error נשארים. אסור לשנות את הקלט, ותוצאה שכבר נמחקה לא נספרת שוב. אחר כך הרץ את memory_demo: ארבע הגדרות (לשמור הכל, 2, ‏1, ‏1 עם note) על שתי משימות. מה קורה עם keep 1 בלי note? מה נעלם מהתשובה עם keep 2? למה במשימות הקצרות האלה החיסכון בטוקנים כמעט אפסי, ומתי מחיקה באמת משתלמת? לסיום, בדוק מול Haiku אם הוא קורא שוב לכלים או משתמש בפתקים.", cmd: "python -m pytest -q labs/15-agent-loops/tests/test_ex7_memory.py\npython labs/15-agent-loops/memory_demo.py --mine\npython labs/15-agent-loops/memory_demo.py --mine --show 1\npython labs/15-agent-loops/memory_demo.py --model anthropic:claude-haiku-5-5" },
      { id: "ex8", title: "Workflow קבוע מול agent", text: "אותן 15 משימות, בלי לולאה: חילוץ שדות, ואז lookup, ‏list_access_grants אם צריך, check_policy, החלטה בקוד, ו-create עם אישור. offline החילוץ נעשה עם regex, ומול Haiku יש קריאת מודל אחת עם structured output. השווה לתרגיל 5: עלות, צעדים, ואילו משימות ה-workflow לא יודע לעשות (t07: השוואת מערכות, t08: רשימת הרשאות, t11: שאלה על מסמך). כתוב פסקה: איך היית מחלק את העבודה ב-Company Brain בין workflow, ‏agent ונתב? זו ההכנה לשיעור 16.", cmd: "python labs/15-agent-loops/eval_tasks.py --modes react,workflow\npython labs/15-agent-loops/eval_tasks.py --modes workflow --model anthropic:claude-haiku-5-5" },
    ],
  },

  quiz: [
    {"q":"ריצה של agentkit: בקריאה הראשונה למודל הוא ביקש במקביל lookup_employee ו-check_policy. בקריאה השנייה הוא ביקש create_access_request. בקריאה השלישית הוא ענה בטקסט. כמה צעדים וכמה קריאות לכלים נרשמו?","options":["3 צעדים ו-3 קריאות לכלים","4 צעדים ו-3 קריאות, כי כל קריאה לכלי היא צעד, ועוד צעד לתשובה","2 צעדים ו-3 קריאות, כי התשובה הסופית אינה צעד","3 צעדים ו-2 קריאות, כי שתי קריאות מקבילות נספרות כקריאה אחת"],"correct":0,"explain":"צעד הוא <b>קריאה אחת למודל</b>, יחד עם הקריאות לכלים שהיא ביקשה. שתי קריאות מקבילות באותה תשובה הן צעד אחד, אבל שתי קריאות לכלים. גם התשובה הסופית היא קריאה למודל, ולכן היא צעד, והיא עוברת דרך המדיניות כמו כל צעד. כך גם ב-t01: 4 צעדים ו-3 קריאות, כשהצעד האחרון הוא התשובה."},
    {"q":"ב-agent בסגנון ReAct המקורי, המודל כתב בעצמו שורה \"Observation: {\\\"route\\\": \\\"auto_approve\\\"}\" ולא עצר ב-PAUSE, והקוד המשיך כאילו זו תצפית אמיתית. מה ב-tool calling מודרני מונע את זה?","options":["התצפית היא tool_result שרק הקוד שלך כותב, והיא מקושרת לקריאה לפי מזהה. המודל מחזיר בלוק tool_use מובנה, ולא טקסט שמפרסרים","stop sequence על המילה Observation, שעוצר את המודל לפני שהוא כותב תצפית","regex מחמיר יותר על שורת ה-Action, שדוחה כל פלט שלא תואם בדיוק לפורמט","interleaved thinking, שנותן למודל לחשוב לפני כל פעולה ולכן לא להמציא תצפיות"],"correct":0,"explain":"הרעיון של ReAct, ש<b>כל צעד נשען על תצפית אמיתית</b>, נשאר. מה שהשתנה הוא הפורמט: במקום טקסט חופשי ו-regex, יש <b>tool_use מובנה</b> עם סכמה ומזהה, ותוצאה שהמודל לא יכול לזייף. stop sequence ו-regex מחמיר הם בדיוק הטלאים של הפורמט הישן, ומודל עדיין יכול לשכוח את הפורמט או לנסח אחרת. וחשיבה לפני פעולה לא משנה את העובדה שבפורמט טקסטואלי התצפית היא עוד טקסט שהמודל יכול להשלים."},
    {"q":"agent על Haiku 5.5 עם adaptive thinking. כדי לחסוך טוקנים, הקוד מקצר את בלוק ה-thinking בתשובת המודל לפני שהוא מוסיף אותה לשיחה, ואז שולח את תוצאות הכלים. מה יקרה?","options":["שגיאת 400: בתוך סבב של כלים חובה להחזיר את בלוקי ה-thinking שלמים ובלי שינוי. התיקון הוא להוסיף את r.message כמו שהוא","זה יעבוד ויחסוך טוקנים, כי חשיבה מתורות קודמות לא מחויבת שוב","אין לזה השפעה: ב-Haiku 5.5 החשיבה מוסתרת כברירת מחדל, ולכן הבלוק ריק בכל מקרה","המודל פשוט יחשוב מחדש מההתחלה. זה עולה יותר, אבל בלי שגיאה"],"correct":0,"explain":"לפי התיעוד, בתוך סבב של כלים חובה להחזיר את בלוקי ה-thinking <b>שלמים ובלי שינוי</b>, ובלוק ששונה נדחה עם 400. לכן llmkit שומר את <b>התשובה הגולמית</b>, ו-Agent מוסיף את r.message בלי לבנות אותו מחדש. נכון שב-Haiku 5.5 ברירת המחדל היא display: omitted, ושדה ה-thinking חוזר ריק, אבל הבלוק עדיין חלק מהתשובה, וגם אותו מחזירים כמו שהוא. ומחויבים על טוקני החשיבה גם כשלא רואים אותם."},
    {"q":"מודל מחפש את Dana לפי \"Dana Levi\", אחר כך לפי \"dana.levi@acme.example\", אחר כך לפי \"E016\", ושוב לפי \"Dana Levi\". כל הקריאות מחזירות את אותה רשומה. איזה כלל יעצור אותו ראשון, עם ברירות המחדל (repeat_limit=3, no_progress_steps=3)?","options":["repetition, כי זה אותו כלי בכל הצעדים","no_progress, כי התוצאה זהה ואין מידע חדש","tool_errors, כי המודל לא מצליח להתקדם","max_steps, כי המודל לא יגיע לתשובה"],"correct":1,"explain":"ה-fingerprints <b>שונים</b>, כי הם כוללים את הארגומנטים ולא רק את שם הכלי, ולכן repetition יתפוס רק כשאותה קריאה בדיוק תופיע בפעם השלישית, בצעד 7. אבל ה-<b>hash של התוצאה</b> זהה, ולכן no_progress עוצר אחרי 3 צעדים בלי מידע חדש, בצעד 4. tool_errors דורש שכל הקריאות ייכשלו, וכאן כולן מצליחות. ו-max_steps=8 רחוק יותר."},
    {"q":"max_steps=4. בצעד הרביעי המודל ענה בטקסט, בלי לבקש כלים. איזה stop_reason נרשם?","options":["final_answer, כי הכלל הזה נבדק ראשון במדיניות","max_steps, כי מונה הצעדים הגיע לגבול","max_steps, כי המדיניות בודקת קודם את הגבולות הקשיחים, ליתר ביטחון","שתי הסיבות נרשמות יחד"],"correct":0,"explain":"הכללים נבדקים <b>בסדר קבוע</b>, והסיבה שנרשמת היא הראשונה שחלה. <b>final_answer נבדק ראשון</b>, ולכן ריצה שענתה בצעד ה-4 מתוך 4 נרשמת כהצלחה ולא כחריגה. אילו הגבולות הקשיחים היו נבדקים קודם, תשובה תקינה בצעד האחרון המותר הייתה נרשמת ככישלון. וה-trajectory תמיד אומר סיבה אחת, כדי שהתוצאה תהיה דטרמיניסטית."},
    {"q":"הגבול הוא max_cost_usd=0.0004. אחרי הצעד הראשון, שעלה $0.00023, הריצה נעצרה עם budget_cost, למרות שהעלות עד עכשיו מתחת לגבול. למה?","options":["כלל ההסתכלות קדימה: עוד צעד כמו האחרון יביא ל-$0.00046, מעל הגבול, ולכן הריצה נעצרת לפני החריגה","הכלל שומר מרווח ביטחון, ועוצר כשהעלות עוברת חצי מהגבול","קריאת הסיכום של summarize_on_stop כבר נספרה בעלות ועברה את הגבול","באג: budget_cost אמור לעצור רק כשהעלות בפועל עוברת את הגבול"],"correct":0,"explain":"הכלל צופה צעד אחד קדימה: <b>עלות עד עכשיו ועוד עלות הצעד האחרון גדולה מהגבול</b>, כלומר 0.00023 ועוד 0.00023 הם 0.00046. כך הריצה נעצרת <b>לפני</b> הצעד שהיה עובר את הגבול, ולא אחריו. אין בכלל מרווח של חצי: התוצאה כאן רק נראית כך. וקריאת הסיכום קורית <b>אחרי</b> העצירה, ולכן היא לא יכולה לגרום לה, ובגלל זה היא עולה כסף מעבר לתקציב."},
    {"q":"memory_demo.py על t01 עם המודל המזויף:<br><code>keep all: final_answer, 4 steps, 3 calls, 9,431 input tokens</code><br><code>keep 2: final_answer, 4 steps, 3 calls, 9,384 (the answer lost \"Michal Ben-David\")</code><br><code>keep 1: repetition, 5 steps, 5 calls, 11,579</code><br><code>keep 1 + notes: final_answer, 4 steps, 5 calls, 10,145</code><br>איזו מסקנה נכונה?","options":["עם keep 1 התוצאות הישנות נמחקו, המודל שכח את הרשומה של Dana, הביא אותה שוב ונעצר על repetition. זה עלה יותר ממה שנחסך, ופתקים מונעים את השכחה","keep 2 הוא הפשרה הבטוחה: הוא הצליח, בפחות טוקנים מ-keep all","keep 1 בסדר, ו-repetition כאן הוא התרעת שווא. צריך להעלות את repeat_limit","הריצה עם keep 1 נכשלה כי המחיקה הסירה גם את מזהי הקריאות, והמודל לא הצליח לקשר תוצאות לקריאות"],"correct":0,"explain":"מחיקה <b>בלי פתקים</b> גורמת לשכחה, ושכחה גורמת למודל להביא את אותו מידע שוב, עד שהמדיניות עוצרת אותו. כלי <b>note</b> שומר עובדות בפרומפט של המערכת, שם הן לא נמחקות. keep 2 הוא המקרה המסוכן יותר: <b>שכחה שקטה</b>, ששם המנהלת נעלם מהתשובה ורק ההערכה מול הזהב תפסה את זה. repetition כאן תפס חזרה אמיתית. והמזהים נשארים: רק התוכן של התוצאות הישנות מוחלף, אחרת הספק היה מחזיר 400."},
    {"q":"המשתמש סירב לבקשה, והמודל המזויף ממשיך לבקש את אותה קריאה ל-create_access_request, עם אותם ארגומנטים, בצעדים 3, 4 ו-5. כל אחת מהן חוזרת כשגיאה. בצעד 5 מתקיימים גם repetition, גם tool_errors (3 צעדים ברצף שבהם כל הקריאות נכשלו) וגם no_progress. איזו סיבה תירשם?","options":["repetition, כי הכלל הזה נבדק לפני tool_errors ולפני no_progress","tool_errors, כי כל הקריאות נכשלו","no_progress, כי לתוצאה שנכשלה אין hash ולכן אין מידע חדש","max_steps, כי אף אחד מהכללים האלה לא חל על כלי עם תופעת לוואי"],"correct":0,"explain":"כשכמה כללים חלים באותו צעד, <b>הסדר</b> קובע: repetition (שלוש קריאות עם אותו fingerprint) נבדק לפני tool_errors, ו-tool_errors לפני no_progress. אותה ריצה הייתה נעצרת על tool_errors אם היו מעלים את repeat_limit, וזו בדיוק הדוגמה של תרגיל 6. הכללים חלים על כל כלי, כולל כלים עם תופעת לוואי. ובמודל אמיתי, הודעת \"DECLINED, do not retry\" ברורה מונעת את רוב הניסיונות החוזרים: ה-mock טיפש בכוונה."},
    {"q":"בתרחיש stale, read_document מחזיר את המדיניות הישנה v2.1, וה-agent עונה בביטחון \"3 business days\". התשובה הנכונה לפי v2.2 היא \"2 business days\". מי יתפוס את זה?","options":["repetition","no_progress","evidence_conflict, כי הוא משווה את התשובה למה שהכלים החזירו","רק הערכה מול תוצאת זהב"],"correct":3,"explain":"אין שגיאה, אין חזרה, ויש מידע חדש בכל צעד, ולכן <b>אף כלל בלולאה</b> לא חל. evidence_conflict תופס תשובה שסותרת את מה שהכלים החזירו, אבל כאן התשובה <b>נאמנה</b> לכלי: הכלי עצמו החזיר מסמך מיושן. רק השוואה ל<b>זהב</b> מגלה שהתשובה שגויה, ובגלל זה מעריכים agents מול סט משימות עם תוצאות ידועות."},
    {"q":"eval_tasks.py במסלול הלא מקוון:<br><code>react: success 15/15, mean steps 2.93, cost $0.01109</code><br><code>workflow: success 12/15, mean steps 1.93, cost $0.00000</code><br><code>failed: t07 (compare two systems), t08 (list someone's access), t11 (what does the document say)</code><br>איזה תכנון מתאים ל-Company Brain?","options":["נתב בכניסה: workflow לצורה הנפוצה (אדם אחד, מערכת אחת, רמה אחת), ו-agent לבקשות שמחוץ לצורה הזו","agent לכל הבקשות, כי הוא הצליח ב-15 מתוך 15","workflow לכל הבקשות, ודחייה של מה שהוא לא תומך בו, כי הוא עולה אפס","agent במצב plan לכל הבקשות, כי תוכנית נותנת את הצפיות של workflow ואת הגמישות של agent"],"correct":0,"explain":"כשאפשר לצייר את תרשים הזרימה <b>לפני שרואים את הקלט</b>, workflow זול יותר, צפוי יותר וקל לבדיקה. שלושת הכשלים שלו הם בקשות מחוץ לצורה שלו, ושם agent שווה את המחיר, ולכן משלבים עם <b>נתב</b>. agent לכל הבקשות משלם על כל בקשה נפוצה בלי צורך, ו-workflow בלבד זונח שאלות לגיטימיות. ומצב plan מוסיף קריאת תכנון, ותוכנית שנכתבת לפני שראו נתונים יכולה להיות שגויה: offline היעילות שלו ירדה מ-1.00 ל-0.90."},
  ],

  summary: {
    points: [
      {t:"agent הוא לולאה עם גבולות", b:"בכל צעד המודל רואה את כל מה שנצפה ובוחר את הפעולה הבאה. הקוד שלך לא קובע את המסלול, אבל הוא קובע את הגבולות: כלים מותרים, תקציב, תנאי עצירה ואישור אנושי לתופעות לוואי."},
      {t:"ReAct הוא רעיון, tool calling הוא הפורמט", b:"כל צעד נשען על תצפית אמיתית מהעולם. היום הפורמט נאכף על ידי ה-API. הטקסט שהמודל כותב לפני הקריאה הוא ה-Thought, ו-adaptive thinking מוסיף חשיבה פנימית, שחייבים להחזיר לספק בלי שינוי."},
      {t:"תוכנית קונה שקיפות ומקביליות", b:"plan-then-act מציג את המסלול לפני כל תופעת לוואי, ומריץ במקביל שלבים שלא תלויים זה בזה. המחיר הוא קריאה נוספת, ושלבים מיותרים כשהתוכנית נכתבה לפני שראו נתונים. תכנון מחדש מוגבל מטפל בכשלים."},
      {t:"עצירה היא מדיניות שנבדקת בסדר קבוע", b:"final_answer, ‏gave_up, ‏max_steps, טוקנים, דולרים, זמן, repetition, ‏tool_errors ו-no_progress. הסדר קובע איזו סיבה נרשמת כשכמה כללים חלים. כלל העלות מסתכל צעד אחד קדימה."},
      {t:"שתי טביעות אצבע לשני סוגי לולאות", b:"fingerprint של קריאה (שם וארגומנטים קנוניים) תופס חזרה זהה. hash של תוצאה תופס לולאה מוסווית, שבה הקריאות שונות אבל לא מתקבל מידע חדש."},
      {t:"ויתור כן הוא הצלחה", b:"הכלי give_up עם reason ו-missing הוא אות מובנה, שאפשר למדוד. ויתור עם הסבר עדיף על ניחוש, ועדיף על ריצה שנעצרת בגלל התקציב בלי להגיד כלום."},
      {t:"ההקשר גדל, ומחיקה בלי פתקים גורמת לשכחה", b:"כל צעד שולח הכל מחדש: הקלט של צעד גדל ליניארית, והסכום של ריצה ארוכה גדל עד בריבוע. בריצות קצרות הבסיס הכבד שולט. מחיקת תוצאות ישנות חוסכת כשהתוצאות גדולות, אבל בלי scratchpad המודל מביא את אותו מידע שוב, או שוכח בשקט."},
      {t:"מעריכים גם את התוצאה וגם את הדרך", b:"הצלחה נבדקת מול זהב, לפי מה שבאמת נכתב בעולם. לצד זה: צעדים, קריאות מיותרות, יעילות, סתירה לראיות, עלות להצלחה, ו-pass^k לאמינות. יש טעויות, כמו מסמך ישן, שרק הערכה תופסת."},
      {t:"workflow למקרה הנפוץ, agent לשאר", b:"כשאפשר לצייר את תרשים הזרימה מראש, workflow קבוע זול יותר, צפוי יותר וקל יותר לבדיקה. agent מצדיק את המחיר כשהמסלול תלוי במה שמתגלה בדרך. נתב מחליט לאן כל בקשה הולכת."},
    ],
    glossary: [
      ["Agent", "מערכת שבה המודל מכוון את התהליך ואת השימוש בכלים בעצמו, בלולאה, עד שהוא עונה, מוותר, או נעצר בגלל גבול."],
      ["Workflow", "מערכת שבה מודלים וכלים מתוזמרים לאורך מסלול שנקבע מראש בקוד."],
      ["ReAct", "Reasoning + Acting: מחשבה, פעולה ותצפית שזורות זו בזו (Yao ועמיתים, 2022). היום נאכף בעזרת tool calling."],
      ["Step (צעד)", "קריאה אחת למודל, יחד עם הקריאות לכלים שהיא ביקשה והתוצאות שלהן. זו היחידה ש-max_steps סופר."],
      ["Trajectory", "הרצף המלא של צעדים בריצה: מחשבות, קריאות, תוצאות, החלטות, עלויות. ב-agentkit נשמר כ-JSONL."],
      ["Stop reason", "הסיבה שהריצה נגמרה: final_answer, ‏gave_up, ‏max_steps, ‏budget_*, ‏repetition, ‏tool_errors, ‏no_progress, ‏refusal, ‏max_tokens, ‏model_error."],
      ["Budget", "הגבולות של ריצה: צעדים, טוקנים, דולרים, זמן, וספים לחזרות, לחוסר התקדמות ולשגיאות ברצף."],
      ["Fingerprint", "sha256 של שם הכלי ושל הארגומנטים כ-JSON קנוני. לקריאות זהות יש אותו fingerprint. משמש לזיהוי חזרות ולקשירת אישור לקריאה."],
      ["No progress", "כמה צעדים ברצף שאף אחד מהם לא החזיר תוצאה מוצלחת עם hash חדש. תופס לולאות שבהן כל קריאה שונה."],
      ["give_up", "כלי מובנה שהמודל קורא לו כדי לעצור, עם reason ו-missing. עצירה מוצלחת וכנה."],
      ["Plan-then-act", "קודם תוכנית מובנית, אחר כך ביצוע שלה. מאפשר שקיפות ומקביליות. כשמשהו נכשל, מתכננים מחדש."],
      ["Adaptive thinking", "מצב החשיבה המומלץ ב-Claude: המודל מחליט אם לחשוב וכמה, לפי effort. בין קריאות לכלים החשיבה שזורה באופן אוטומטי."],
      ["Tool result clearing", "החלפת התוכן של תוצאות ישנות ב-placeholder, עם אותם ids. ב-Anthropic: clear_tool_uses_20250919."],
      ["Scratchpad", "פתקים שהמודל שומר עם כלי note. הם נשמרים בפרומפט של המערכת, ולא נמחקים יחד עם התוצאות."],
      ["pass^k", "ההסתברות שמשימה מצליחה בכל k ניסיונות. מדד אמינות, מ-τ-bench."],
      ["Evidence conflict", "תשובה שמזכירה מסלול אישור, אבל אף פעם לא את המסלול ש-check_policy החזיר. סימן לכך שהמודל האמין למקור הלא נכון."],
    ],
    reading: [
      {title: "ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., ICLR 2023)", url: "https://arxiv.org/abs/2210.03629", note: "המאמר המקורי. ALFWorld: שיפור מוחלט של 34% בשיעור ההצלחה. HotpotQA: פחות הזיות מ-chain-of-thought, כי כל טענה נשענת על תצפית."},
      {title: "Building effective agents (Anthropic)", url: "https://www.anthropic.com/research/building-effective-agents", note: "workflow לעומת agent, ground truth בכל צעד, ותנאי עצירה."},
      {title: "How We Build Effective Agents (Barry Zhang, AI Engineer Summit)", url: "https://www.youtube.com/watch?v=D7_ipDqhtwk", note: "מתי agent ומתי workflow, ודיבאג מנקודת המבט של המודל. תקציבים הם בעיה פתוחה."},
      {title: "Thinking with tool use: adaptive thinking (Anthropic docs)", url: "https://platform.claude.com/docs/en/build-with-claude/thinking", note: "בלוקי thinking חוזרים בלי שינוי. ב-Haiku 5.5 ה-effort הוא medium וה-display הוא omitted כברירת מחדל. ההגבלות של tool_choice."},
      {title: "Context editing (Anthropic docs)", url: "https://platform.claude.com/docs/en/build-with-claude/context-editing", note: "clear_tool_uses_20250919: ‏trigger, ‏keep, ‏clear_at_least, ‏exclude_tools, ואזהרת ה-cache."},
      {title: "Effective context engineering for AI agents (Anthropic)", url: "https://anthropic.com/engineering/effective-context-engineering-for-ai-agents", note: "compaction, רישום פתקים ומחיקת תוצאות."},
      {title: "The \"think\" tool (Anthropic, עם עדכון מדצמבר 2025)", url: "https://www.anthropic.com/engineering/claude-think-tool", note: "τ-bench airline: מ-0.370 ל-0.570 לפי טקסט המאמר (בטבלת pass^1: מ-0.332 ל-0.584). העדכון מדצמבר 2025 ממליץ על extended thinking במקום הכלי (נבדק בנובמבר 2026)."},
      {title: "Plan-and-Execute Agents (LangChain)", url: "https://www.langchain.com/blog/planning-agents", note: "plan-and-execute, ‏ReWOO ו-LLMCompiler: מה מבטיח כל אחד מהם, ומה המחיר."},
      {title: "τ-bench: A Benchmark for Tool-Agent-User Interaction (Yao et al., 2024)", url: "https://arxiv.org/abs/2406.12045", note: "המדד pass^k. ‏gpt-4o עם pass^8 נמוך מ-25% בתחום הקמעונאות."},
    ],
  },
};
