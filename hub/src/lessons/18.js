// Lesson 18 — Multi-Agent Patterns.
window.LESSONS = window.LESSONS || {};
window.LESSONS["18"] = {
  n: 18,
  title: "Multi-Agent Patterns",
  he: "supervisor, router, handoff ומחיר התיאום",
  hours: "כשעתיים וחצי שיעור, כארבע שעות מעבדה",

  goals: [
    "להבין מה <b>multi-agent</b> הוא בפועל: כמה לולאות agent נפרדות, ולכל אחת יש פרומפט, כלים ו<b>הקשר</b> משלה, עם מנגנון שמעביר עבודה ביניהן. זה לא קסם, אלא בעיקר החלטה <b>מה כל מודל רואה</b>.",
    "להכיר את הדפוסים המרכזיים, ולדעת מה כל אחד קונה ומה הוא עולה: <b>router</b> (מסווגים ושולחים למומחה), <b>supervisor</b> (האצלה דרך כלים), <b>handoff</b> (העברת שליטה עם הקשר), <b>צוותים היררכיים</b>, <b>fan-out מקבילי</b> עם איחוד או הצבעה, ו<b>כותב ומבקר</b>.",
    "להבין למה <b>בידוד הקשר</b> הוא היתרון האמיתי: כל subagent עובד בהקשר נקי וממוקד, ומחזיר רק את מה שחשוב. זה מה ש-Anthropic מתארים במערכת המחקר שלהם.",
    "למדוד את <b>מחיר התיאום</b>: טוקנים שמוכפלים (במערכת של Anthropic, בערך פי 15 מצ'אט), זמן, <b>התפשטות כשלים</b> ו<b>הצטברות שגיאות</b> בשרשרת, וגם תופעות לוואי שרצות שוב כשמאצילים שוב.",
    "לתכנן את <b>החוזה בין agents</b>: מה חייב לעבור ב-handoff (הבקשה המקורית מילה במילה, עובדות עם מקור, פעולות שכבר בוצעו, אילוצים), ומה ה-worker מחזיר למעלה (תשובה וראיות).",
    "להעריך מערכת מרובת agents <b>מקצה לקצה</b> מול אותו זהב של agent יחיד, ולצד זה לבצע <b>ייחוס לכל agent</b>: כמה כל agent עלה, ומי גרם לכשל.",
    "להכיר את <b>נוף הכלים</b> בנובמבר 2026: handoffs ב-OpenAI Agents SDK, supervisor ו-swarm ב-LangGraph, CrewAI, subagents ב-Claude Agent SDK, Google ADK ו-<b>A2A</b>, ולדעת מה כל אחד עושה מתחת למכסה.",
    "לאמץ את הכלל: <b>מתחילים עם agent אחד</b>, ומוסיפים agents רק כשמדידה מראה שזה משתלם.",
  ],
  connects: "בשיעור 15 בנית <b>agent אחד</b>: לולאה, תקציב, מדיניות עצירה ו-trajectory. בשיעור 16 ראית <b>workflow</b> קבוע ב-LangGraph, ובשיעור 17 חשפת את הכלים של Acme דרך <b>MCP</b>. בשיעור הזה מחברים כמה agents כאלה: כל מומחה הוא אותו Agent של agentkit, עם פרומפט וכלים משלו, וה-<b>trajectories</b> שלהם נשמרים כעץ. ב-<b>Company Brain</b> זה הרגע שבו המערכת יוצאת מעולם בקשות הגישה, ומתחילה לענות גם על שאלות HR ועל כוננות. את ההחלטה אם לפצל תקבל לפי מדידה, לא לפי אופנה. בשיעור 19 (ארכיטקטורה) תשקול את הדפוסים האלה מול latency ועלות, בשיעור 22 תראה את העץ הזה כ-traces, ובשיעור 23 תהפוך את ההשוואה לבדיקת רגרסיה.",

  intro: {
    animation: "l18flow",
    animationTitle: "חמישה דפוסים על אותה בקשה: מי מדבר עם מי, ומי משלם",
    animationGuide: `<p><b>מה קורה כאן:</b> הבקשה x08 שואלת שלוש שאלות משלושה תחומים: כמה ימי מחלה צוברים בחודש (HR), מי בכונן של connectors-hub (on-call), והאם ל-Keren Amar כבר יש גישה ל-NetSuite (גישה). אותה בקשה עוברת כל פעם בדפוס אחר, והאנימציה מראה את ההודעות שעוברות בין ה-agents, ואת מונה הטוקנים של כל agent.</p>
<p><b>איך לקרוא את המסך:</b></p>
<ol>
<li><b>הכרטיסים</b> הם ה-agents. כרטיס עם ◆ כתום הוא agent של תיאום (router, supervisor, triage, planner, synthesizer). כרטיס כחול הוא worker שעושה את העבודה בתחום. כרטיס חיוור הוא agent שלא רץ בכלל בדפוס הזה.</li>
<li><b>הפס בכל כרטיס</b> הוא מספר הטוקנים שה-agent הזה צרך עד עכשיו, באותו קנה מידה בכל הדפוסים. כך רואים מיד איפה הכסף הולך.</li>
<li><b>החלון השחור</b> הוא יומן ההודעות: משתמש ל-agent, האצלה, העברה, ותשובה. השורה החדשה מסומנת.</li>
<li><b>ההסבר</b> מתחת לחלון אומר מה קרה בצעד הזה ולמה, כולל גודל ההקשר שהמודל קיבל.</li>
</ol>
<p><b>המסקנה שכדאי לחפש:</b> ב-agent היחיד יש מונה אחד שרק גדל, כי כל תוצאת כלי נשארת בשיחה. ב-supervisor כל worker מתחיל קטן ונשאר קטן, אבל יש agent נוסף שמשלם על תיאום. ה-router הוא הזול ביותר, ועונה רק על שליש מהבקשה. ה-handoff הוא היקר ביותר, כי כל סיכום סוחב איתו את כל מה שקדם לו.</p>
<p><b>איך לעבוד:</b> התחל ב"Agent יחיד", השהה, ועבור צעד אחרי צעד עם החצים. אחר כך עבור על Router, Supervisor ו-Handoff, ובסוף על Fan-out. בסוף כל דפוס מופיע הסכום הכולל, לעומת agent יחיד.</p>`,
    videos: [
      {
        title: "How we built our multi-agent research system",
        who: "Anthropic Engineering",
        part: "כל המאמר. הכי חשובים: Benefits of a multi-agent system, Prompt engineering and evaluations, Production reliability",
        minutes: 30,
        url: "https://www.anthropic.com/engineering/multi-agent-research-system",
        required: true,
        kind: "מאמר",
        why: "התיאור הכי מפורט שפורסם של מערכת multi-agent בפרודקשן: lead agent ו-subagents מקבילים, בידוד הקשר, פי 15 טוקנים מצ'אט, 90.2% שיפור על ה-eval הפנימי שלהם, ואיך מעריכים מערכת כזו. רוב המספרים בשיעור באים מכאן.",
      },
      {
        title: "Don't Build Multi-Agents, ואחריו Multi-Agents: What's Actually Working",
        who: "Walden Yan, Cognition",
        part: "שני המאמרים, לפי הסדר (יוני 2025, ואפריל 2026)",
        minutes: 25,
        url: "https://cognition.ai/blog/dont-build-multi-agents",
        required: true,
        kind: "מאמר",
        why: "הצד השני של הוויכוח. הטענה: פעולות נושאות החלטות סמויות, ולכן agents מקבילים שכותבים מתנגשים. במאמר ההמשך (cognition.com/blog/multi-agents-working) הם מתארים מה כן עובד ב-2026: כתיבה אצל agent אחד, ועוד agents שרק מבקרים או מייעצים.",
      },
      {
        title: "How We Build Effective Agents",
        who: "Barry Zhang, Anthropic, AI Engineer Summit 2025",
        part: "ההרצאה המלאה",
        minutes: 15,
        url: "https://www.youtube.com/watch?v=D7_ipDqhtwk",
        required: false,
        kind: "וידאו",
        why: "הרצאה קצרה על מתי לא לבנות agent בכלל, ואיך לשמור על פשטות. היא מבוססת על המאמר Building effective agents, שבו מוגדרים routing, parallelization, orchestrator-workers ו-evaluator-optimizer.",
      },
      {
        title: "Multi-agent",
        who: "LangChain docs",
        part: "הסקירה, וההשוואה בין subagents, handoffs, skills ו-router",
        minutes: 20,
        url: "https://docs.langchain.com/oss/python/langchain/multi-agent",
        required: false,
        kind: "תיעוד",
        why: "תיעוד שמשווה ארבעה דפוסים לפי מספר קריאות וטוקנים בשלושה תרחישים. שים לב שגם הם כותבים: לא כל משימה מורכבת צריכה את זה.",
      },
      {
        title: "Handoffs",
        who: "OpenAI Agents SDK docs",
        part: "Handoffs, ו-input_filter",
        minutes: 15,
        url: "https://openai.github.io/openai-agents-python/handoffs/",
        required: false,
        kind: "תיעוד",
        why: "המימוש הנפוץ ביותר של handoff: כלי בשם transfer_to_ ואחריו שם ה-agent (למשל transfer_to_billing_agent). כברירת מחדל, ה-agent החדש רואה את כל השיחה הקודמת. בשיעור תראה למה זו החלטה שצריך לחשוב עליה.",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "Company Brain גדל: שלושה תחומים, agent אחד?",
      html: `<p class="big">עד עכשיו Company Brain עשה דבר אחד: בקשות גישה. בשיעור 15 הוא קיבל לולאה, תקציב ומדיניות עצירה, ושישה כלים. עכשיו מבקשים ממנו עוד שני תחומים: שאלות <b>HR</b> (חופשה, מחלה, עבודה מהבית) ושאלות <b>כוננות</b> (מי בכונן של שירות, מתי ההחלפה, איזה runbook). והבקשות האמיתיות לא מגיעות מסודרות לפי תחום.</p>
<p>קח את x08 מהמעבדה: "Keren Amar from finance has three questions. How many sick days does an employee accrue per month? Who is on call for connectors-hub? Does Keren Amar already have NetSuite access? Do not file anything." אלה שלוש שאלות משלושה תחומים, וגם אילוץ ("Do not file anything") שחל רק על אחת מהן. יש שתי דרכים לבנות את זה. הראשונה: agent אחד עם עשרה כלים ופרומפט שמסביר את שלושת התחומים. השנייה: שלושה מומחים, לכל אחד פרומפט קצר ושלושה עד שישה כלים, ומשהו שמחלק ביניהם את העבודה.</p>
<p>הדרך השנייה נשמעת מסודרת יותר, וזו בדיוק הסיבה שצריך להיזהר ממנה. כל agent נוסף הוא עוד קריאות מודל, עוד פרומפט שמשלמים עליו מחדש, עוד מקום שבו מידע הולך לאיבוד בדרך, ועוד trajectory שצריך לדבג. השיעור הזה עוסק בשאלה <b>מתי</b> הפיצול משתלם, <b>איך</b> בונים כל דפוס כך שהוא לא נשבר, ו<b>איך מודדים</b> את זה. המעבדה משווה agent יחיד, router ו-supervisor על אותן 23 משימות ומול אותו זהב.</p>
<div class="callout">התשובה של השיעור, מראש: מתחילים עם agent אחד ומודדים אותו. מוסיפים agents רק כשהמדידה מראה בעיה שפיצול פותר, ובדרך כלל הבעיה היא הקשר שמתמלא או יותר מדי כלים. גם אז מודדים שוב, כי הפיצול עולה כסף.</div>`,
    },
    {
      kicker: "הגדרה",
      title: "מה זה multi-agent, מבחינה טכנית",
      html: `<p>במעבדה, כל "agent" הוא בדיוק ה-Agent של agentkit משיעור 15: לולאה שבה כל צעד הוא קריאת מודל, עם כלים, תקציב ומדיניות עצירה. מערכת multi-agent היא כמה לולאות כאלה, ולכל אחת יש שלושה דברים משלה:</p>
<ul>
<li><b>פרומפט מערכת משלה.</b> המומחה ל-HR יודע להעדיף את הגרסה החדשה של מדיניות. המומחה לגישה יודע ש-check_policy הוא הסמכות. אף אחד מהם לא צריך לקרוא את ההוראות של השני.</li>
<li><b>סט כלים משלה.</b> ל-hr יש שני כלים, ל-oncall שלושה ול-it_access שישה. agent יחיד היה צריך את כל עשרת הכלים בכל קריאה, כולל ההגדרות שלהם, שעולות טוקנים, וכולל הסיכוי לבחור כלי לא נכון.</li>
<li><b>הקשר משלה.</b> זה הדבר החשוב. כל agent מתחיל משיחה ריקה, שמכילה רק את מה שהעבירו לו במפורש. התוצאות של הכלים שלו נשארות אצלו, ולמעלה עולה רק התשובה.</li>
</ul>
<p>מה שמבדיל בין הדפוסים הוא <b>מנגנון ההעברה</b>: מי מחליט מי עובד, מה עובר בין ה-agents, ומי עונה בסוף. ב-router קוד מעביר אחרי סיווג. ב-supervisor ההעברה היא קריאה לכלי, והתשובה חוזרת למי שקרא. ב-handoff השליטה עוברת ולא חוזרת. ב-fan-out מתכנן מפצל ושלב סינתזה מאחד.</p>
<div class="example"><b>במעבדה: כל agent הוא Agent רגיל, עם רשומות שמקשרות אותו לאב שלו</b><pre dir="ltr">{"type": "run", "agent": "hr", "role": "worker",
 "parent_run_id": "9f2c41aa07d3b6e1", "task": "How many sick days ..."}
# role: coordinator | worker      parent_run_id: who started this agent
# a multi-agent run = a TREE of ordinary agentkit trajectories</pre></div>
<p>ההבחנה של Anthropic בין <b>workflow</b> ל-<b>agent</b> משיעור 16 חלה גם כאן. router עם סיווג אחד ושליחה בקוד הוא workflow, כי המסלול נקבע בקוד. supervisor שמחליט בעצמו את מי להפעיל, ומתי, הוא agent שמנהל agents. ככל שהמודל מחליט יותר, יש יותר גמישות, ויותר דרכים להיכשל.</p>`,
    },
    {
      kicker: "מפה",
      title: "שישה דפוסים, מהפשוט למורכב",
      html: `<p>הדפוסים האלה מופיעים, בשמות קצת שונים, אצל Anthropic (Building effective agents), ב-LangChain, ב-Google ADK וב-OpenAI. כדאי להכיר אותם לפי <b>מי מחליט</b> ו<b>מה עובר</b>:</p>
<ol class="ladder">
<li><b>Router</b><span>קריאה אחת מסווגת את הבקשה, וקוד שולח אותה למומחה אחד. ההחלטה מתקבלת פעם אחת, מראש. זה הדפוס הזול ביותר, והוא מתאים לבקשות ששייכות לתחום אחד ברור.</span></li>
<li><b>Supervisor (orchestrator-workers)</b><span>agent שהכלים שלו הם delegate_to_&lt;worker&gt;. הוא מפרק את הבקשה, כותב לכל worker משימה, מקבל תשובות ומחבר אותן. ההחלטה מתעדכנת אחרי כל תשובה.</span></li>
<li><b>Handoff</b><span>agent מעביר את השליטה ל-agent אחר, יחד עם הקשר. אין מנהל, והאחרון בשרשרת עונה למשתמש. זה מתאים לעבודה בשלבים, כמו triage ואחריו מומחה.</span></li>
<li><b>צוותים היררכיים</b><span>worker שהוא בעצמו supervisor, למשל ראש צוות הנדסה שמנהל את oncall ו-deploy. זה מאפשר לפצל מערכת גדולה, ומוסיף שכבת תיאום שעולה כסף ומסתירה מידע.</span></li>
<li><b>Fan-out ואיחוד</b><span>אותה עבודה מפוצלת לחלקים בלתי תלויים שרצים במקביל (map), ומאוחדים (reduce). גרסה אחרת היא הצבעה: אותה משימה כמה פעמים, ולוקחים רוב.</span></li>
<li class="danger"><b>כותב ומבקר</b><span>agent אחד כותב, agent אחר בודק מול rubric, והם עוברים כמה סבבים, עם תקרה. זה עובד כשיש קריטריונים ברורים, וכשהמבקר עצמאי באמת.</span></li>
</ol>
<p>שני דברים משותפים לכל הדפוסים. ראשית, כל agent נוסף מוסיף <b>פרומפט בסיס</b> שמשלמים עליו מחדש. שנית, כל מעבר בין agents הוא <b>דחיסה</b>: מישהו מחליט מה עובר ומה נשאר מאחור. בדחיסה הזו נמצא גם היתרון הגדול (הקשר נקי), וגם הסיכון הגדול (אילוץ שנשמט). שאר השיעור עובר על כל דפוס, ומסתיים במחיר ובמדידה.</p>`,
    },
    {
      kicker: "Router",
      title: "Router: סיווג אחד, החלטה בקוד, ושאלת הבהרה",
      html: `<p>ה-router הוא הדפוס הפשוט ביותר, וגם הכי קל לבנות אותו נכון. קודם מגיעה קריאת מודל אחת עם structured output, כמו בשיעור 3, והיא מחזירה אובייקט ולא טקסט. אחר כך <b>קוד</b> מחליט מה לעשות עם האובייקט. המודל לא מחליט לבד, כי אנחנו רוצים לשלוט בסף, ב-fallback ובתחומים המותרים.</p>
<div class="example"><b>multikit/router.py: הסכמה שהמודל ממלא</b><pre dir="ltr">class RouteDecision(BaseModel):
    reason: str                    # first: reason before deciding (lesson 3)
    routes: list[Literal["hr", "it_access", "oncall"]]   # most important first; [] if vague
    confidence: float              # 0.0 - 1.0
    clarifying_question: Optional[str]

choice = decide_route(decision, threshold=0.6, max_targets=1)
# -> RouteChoice("route", ["oncall"])  or  RouteChoice("clarify", [], "Which ...?")</pre></div>
<p>הכלל ב-<code>decide_route</code> (תרגיל 2): מסירים כפילויות ותחומים לא מותרים, וחותכים ל-max_targets. אם לא נשאר כלום, או שה-confidence מתחת לסף, <b>שואלים</b> במקום לנחש. שאלת הבהרה עולה למשתמש הודעה אחת. ניתוב שגוי של בקשת גישה עולה הרבה יותר: מומחה לא נכון עובד, משלם, ועונה בביטחון על שאלה אחרת. ל-x07 ("Can you sort this out for the new person on my team?") התשובה הנכונה היא שאלה.</p>
<p><b>המחיר:</b> במעבדה, קריאת הסיווג עולה בערך 300 טוקני קלט, פחות מכל צעד של כל agent. המומחה שמקבל את הבקשה עובד עם פרומפט קצר ומעט כלים. ב-offline, על 23 המשימות, הנתב צרך 134 אלף טוקנים, לעומת 234 אלף של agent יחיד: <b>58%</b>.</p>
<p><b>החולשה מבנית:</b> ההחלטה מתקבלת פעם אחת, לפני שמישהו עבד. בקשה שחוצה שני תחומים נשלחת למומחה אחד, והוא עונה על חציה. במעבדה, ב-offline, הנתב הצליח ב-16 מתוך 23 משימות, ורק באחת מתוך שמונה המשימות החוצות (x07, ששם התשובה היא שאלה). עם max_targets=2 הוא הגיע ל-22 מתוך 23, אבל אז כל מומחה מקבל את כל הבקשה, ושתי התשובות פשוט מודבקות זו לזו. שום מודל לא קורא את שתיהן ביחד, ואם הן סותרות, אף אחד לא ישים לב.</p>
<div class="callout">מתי router: כשרוב הבקשות שייכות לתחום אחד ברור, כשהסיווג קל, וכשטעות בניתוב זולה או נתפסת. הצעד הראשון הוא למדוד כמה מהבקשות האמיתיות חוצות תחומים. תרגיל 1 עושה את זה על 23 המשימות.</div>`,
    },
    {
      kicker: "Supervisor",
      title: "Supervisor: האצלה היא קריאה לכלי",
      html: `<p>ב-supervisor אין מנגנון חדש. זה Agent רגיל משיעור 15, שהכלים היחידים שלו הם <code>delegate_to_hr</code>, <code>delegate_to_it_access</code> ו-<code>delegate_to_oncall</code>. הפונקציה של כל כלי כזה מריצה worker, כלומר Agent אחר עם פרומפט וכלים משלו, ומחזירה את התשובה שלו כתוצאת הכלי. לכן כל מה שבנית בשיעורים 14 ו-15 עובד: ולידציה של הארגומנטים, timeout, שגיאות כנתונים, תקציב, trajectory. LangChain כותבים היום ב-README של langgraph-supervisor שהם ממליצים לממש את הדפוס "directly via tools" ולא דרך הספרייה, וזה בדיוק מה ש-multikit עושה.</p>
<div class="example"><b>multikit/supervisor.py: הכלי, והקריאה שה-supervisor שולח</b><pre dir="ltr">class DelegateInput(BaseModel):
    task: str               # self-contained: names, systems, constraints. The worker sees NOTHING else
    context: Optional[str]  # facts from other workers, or a correction note

# step 1 of the supervisor on x08: three tool calls in ONE turn -> run in parallel
delegate_to_hr(task="How many sick days does an employee accrue per month?")
delegate_to_oncall(task="Who is on call for connectors-hub?")
delegate_to_it_access(task="Does Keren Amar already have NetSuite access? Do not file anything.")
# tool result: {"agent": "it_access", "answer": "...", "stop_reason": "final_answer"}</pre></div>
<p><b>שלושה פרטים קובעים אם זה עובד:</b></p>
<ul>
<li><b>המשימה חייבת להיות שלמה.</b> ה-worker לא רואה את השיחה של ה-supervisor. התיעוד של Claude Agent SDK אומר את זה במפורש: הדבר היחיד שעובר מההורה ל-subagent הוא מחרוזת ה-prompt של כלי ה-Agent, ולכן כל נתיב, שגיאה או החלטה שה-subagent צריך חייבים להופיע בה. אם ה-supervisor כותב "בדוק לה את NetSuite", ה-worker לא יודע מי זו "לה". אם הוא שוכח את "Do not file anything", ה-worker עלול לפתוח בקשה.</li>
<li><b>מקביליות היא חינם.</b> כמה קריאות כלים באותו צעד רצות במקביל, כי ה-Executor של toolkit מריץ קריאות קריאה-בלבד במקביל. שלושה workers לוקחים בערך את הזמן של האיטי שבהם. עם <code>--sequential</code> ה-supervisor המזויף מאציל אחד בכל צעד, ומשלם צעד נוסף על כל worker.</li>
<li><b>החיבור הוא קריאת מודל נוספת.</b> אחרי שכל התשובות חזרו, ה-supervisor כותב תשובה אחת. זה הצעד שבו עובדות יכולות ללכת לאיבוד או להשתנות. ב-attribute_failure זה נקרא "coordination: found it but the final answer dropped it".</li>
</ul>
<p>OpenAI קוראים לגרסה הזו "agents as tools" (<code>Agent.as_tool</code>), ומבדילים אותה מ-handoff. ב-agents as tools, התשובה חוזרת למי שקרא, והוא נשאר בשליטה. ב-handoff, השליטה עוברת.</p>`,
    },
    {
      kicker: "היתרון",
      title: "בידוד הקשר: מה באמת קונים",
      html: `<p>אם שואלים מה multi-agent קונה, התשובה הכנה היא בעיקר דבר אחד: <b>כל מודל רואה פחות</b>. Anthropic כותבים על מערכת המחקר שלהם שכל subagent נותן "separation of concerns—distinct tools, prompts, and exploration trajectories", ושה-subagents עובדים בחלונות הקשר משלהם, ודוחסים את מה שמצאו לפני שהם מחזירים ל-lead agent רק את הטוקנים החשובים. ה-lead לא רואה את עשרות החיפושים, רק את התקצירים.</p>
<p>למה זה חשוב? בשיעור 15 ראית שכל צעד יקר יותר מהקודם, כי כל תוצאת כלי נשלחת מחדש בכל צעד. בשיעור 4 ראית שמודלים עונים גרוע יותר כשההקשר מלא בחומר לא רלוונטי. agent יחיד שעונה על x08 סוחב לשאלת NetSuite את כל מסמך ימי המחלה ואת שורת הקטלוג של connectors-hub, למרות שאין להם שום קשר לשאלה.</p>
<div class="example"><b>נמדד במעבדה על x08 (מודלים מזויפים, טוקנים מוערכים): גודל ההקשר בצעד הגדול ביותר</b><pre dir="ltr">single agent      first step 2,690   largest 4,011   total 17,879 tokens
supervisor        first step 1,503   largest 1,820
  hr worker       first step   996   largest 2,096
  oncall worker   first step 1,099   largest 1,213
  it_access       first step 2,122   largest 2,229
supervisor pattern total                          15,166 tokens</pre></div>
<p>שים לב לשני דברים. ראשית, אף מודל בדפוס ה-supervisor לא ראה יותר מ-2,229 טוקנים בצעד אחד, לעומת 4,011 אצל ה-agent היחיד. בבקשות אמיתיות, עם מסמכים ארוכים ועשרות תוצאות, הפער גדל מאוד. שנית, הסכום הכולל לא בהכרח קטן יותר. כאן הוא יצא קצת יותר נמוך, אבל על כל 23 המשימות ה-supervisor צרך פי 1.06 מה-agent היחיד, כי רוב המשימות הן של תחום אחד, ושם השכבה הנוספת היא תוספת נטו.</p>
<div class="callout">בידוד הקשר הוא גם המחיר. מה שה-worker לא החזיר, ה-supervisor לא יודע. מה שה-supervisor לא כתב במשימה, ה-worker לא יודע. Cognition ניסחו את זה כעיקרון "share context", ובמאמר של 2026 דייקו אותו: מבקר עובד טוב יותר דווקא עם הקשר נקי, ויועץ ("Smart Friend") צריך עותק של כל ההקשר. ההחלטה מה עובר היא החלטת עיצוב, לא פרט מימוש.</div>`,
    },
    {
      kicker: "Handoff",
      title: "Handoffs: העברת שליטה, ומה חייב לעבור איתה",
      html: `<p>ב-handoff אין מנהל. triage מחליט מי מתחיל, וכל agent שסיים את החלק שלו מעביר את השליטה לבא אחריו, עד שהאחרון עונה למשתמש. ב-OpenAI Agents SDK, handoff מוצג למודל ככלי בשם <code>transfer_to_&lt;agent_name&gt;</code>. ב-LangGraph הדפוס נקרא swarm. השאלה המעניינת היא <b>מה עובר</b>:</p>
<ul>
<li><b>כל השיחה.</b> זו ברירת המחדל ב-OpenAI Agents SDK: ה-agent החדש רואה את השיחה הקודמת, "as though the new agent takes over the conversation". זה פשוט, אבל כל agent משלם על כל מה שקדם לו, כולל תוצאות של כלים שאין לו, וכולל טעויות של אחרים. בשביל זה יש <code>input_filter</code>, ואופציה בטא, <code>nest_handoff_history</code>, שדוחסת את ההיסטוריה לסיכום.</li>
<li><b>סיכום חופשי.</b> זה זול, אבל מסוכן: מי שמסכם מחליט מה חשוב, ומודל שמנסח מחדש משמיט בדיוק את מה שלא נראה לו מרכזי.</li>
<li><b>סיכום מובנה עם חוזה.</b> זה מה ש-multikit עושה. ארגומנטי כלי ההעברה הם סכמה (HandoffSummary), וקוד בודק אותה לפני שההעברה מותרת.</li>
</ul>
<div class="example"><b>multikit/handoff.py: מה חייב לעבור (תרגיל 4)</b><pre dir="ltr">original_request   the user's message VERBATIM      (a paraphrase loses constraints)
goal               what the next agent must do
facts              [{claim, source}]                (no source -> rejected)
actions_taken      every side effect, with its id   ("Filed AR-00001 ...": nobody redoes it)
constraints        every "do not / only if / not yet" clause, word for word
open_questions     what nobody answered yet
# rejected -> the transfer tool returns an ERROR listing the problems; the agent fixes it</pre></div>
<p><b>מה קורה בלי החוזה:</b> משימת ההדגמה h01 היא "... Dana Levi wants admin on aws-production for 3 days. Open the request, but do not file it before Friday." מסכם רשלני (<code>--lossy</code>) מנסח מחדש: "Open the request." ה-agent של it_access מקבל סיכום שנראה תקין לגמרי, ופותח בקשה. הוא לא יכול לדעת שהוא טועה, כי המידע פשוט לא הגיע אליו. עם הבדיקה, ההעברה נדחית עם השגיאות "original_request must be the user's message verbatim" ו-"constraint missing: 'do not file it before Friday'", והסוכן מתקן. זה בדיוק לולאת התיקון משיעור 3, רק בין agents.</p>
<p><b>המחיר:</b> handoffs רצים ברצף, וכל סיכום ארוך מהקודם. במעבדה, ב-offline, זה היה הדפוס היקר ביותר: פי 1.44 טוקנים לעומת agent יחיד על 23 המשימות. LangChain מגיעים לאותה מסקנה בטבלת ההשוואה שלהם: "Handoffs executes sequentially". היתרון של handoff הוא בשיחה <b>מתמשכת</b> עם משתמש, כשהמומחה הנכון נשאר בשליטה לאורך כמה הודעות. שם, לפי אותה טבלה, דפוסים עם מצב חוסכים 40 עד 50 אחוז מהקריאות בבקשה חוזרת.</p>`,
    },
    {
      kicker: "היררכיה",
      title: "צוותים היררכיים: supervisor של supervisors",
      html: `<p>אם worker יכול להיות כל דבר שיש לו <code>run(task)</code>, הוא יכול להיות גם supervisor. ב-multikit, <code>make_worker</code> יכול להחזיר Supervisor, והעץ נשמר בשלוש רמות: supervisor, ראש צוות, worker. הבדיקה <code>test_hierarchical_team_lead</code> בונה בדיוק את זה: ה-supervisor הראשי מאציל ל-eng_lead, וה-eng_lead מאציל ל-oncall.</p>
<p><b>למה לעשות את זה:</b> במערכת עם עשרות מומחים, supervisor אחד עם 30 כלי delegate סובל מאותה בעיה שבגללה פיצלנו מלכתחילה: יותר מדי אפשרויות בפרומפט אחד. היררכיה מקבצת: הראשי בוחר בין שלושה ראשי צוותים, וכל ראש צוות בוחר בין שלושה עד חמישה workers. היא גם מאפשרת לצוותים שונים לבנות ולתחזק חלקים שונים. LangChain קוראים לזה "distributed development".</p>
<p><b>מה זה עולה:</b> כל רמה מוסיפה קריאות תיאום, וכל רמה דוחסת שוב. תשובה של worker עוברת דרך ראש צוות שמסכם אותה, ואחר כך דרך הראשי שמסכם שוב. כל דחיסה היא הזדמנות לאבד עובדה או לשנות אותה. בשקופית על הצטברות שגיאות תראה את החשבון.</p>
<ul>
<li><b>Claude Agent SDK</b> מאפשר ל-subagents ליצור subagents, ומגביל את זה כברירת מחדל: עומק של 3 שכבות מתחת ל-agent הראשי (<code>CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH</code>), עד 20 subagents במקביל, ותקרת הוצאה (<code>max_budget_usd</code>) שכוללת את כל ה-subagents. התיעוד מציין ש-Opus 5 מאציל ל-subagents בקלות רבה יותר ממודלים קודמים, ולכן הגבולות האלה חשובים במיוחד איתו.</li>
<li><b>CrewAI</b> מציע <code>Process.hierarchical</code>: manager (שנוצר אוטומטית מ-manager_llm, או agent משלך) שמחלק משימות ובודק תוצאות. ברירת המחדל היא <code>Process.sequential</code>, וההאצלה כבויה כברירת מחדל.</li>
</ul>
<div class="callout">כלל אצבע: כל רמה בהיררכיה צריכה להצדיק את עצמה במדידה, בדיוק כמו ה-agent השני. אם ראש הצוות רק מעביר הלאה את מה שקיבל, הוא שכבת עלות בלי ערך.</div>`,
    },
    {
      kicker: "Fan-out",
      title: "Fan-out ואיחוד: מקביליות, הצבעה וציטוטים",
      html: `<p>Anthropic מחלקים parallelization לשני סוגים. <b>Sectioning</b> מפצל משימה לחלקים בלתי תלויים שרצים במקביל. <b>Voting</b> מריץ את אותה משימה כמה פעמים כדי לקבל ביטחון גבוה יותר. מערכת המחקר שלהם היא sectioning בקנה מידה: lead agent מתכנן, מפעיל 3 עד 5 subagents במקביל, וכל אחד מהם מריץ 3 כלים ויותר במקביל. לפי המאמר, זה קיצר את זמן המחקר בשאלות מורכבות בעד 90%. בנוסף, agent נפרד (CitationAgent) מוסיף ציטוטים לפני שהתשובה מגיעה למשתמש.</p>
<div class="example"><b>multikit/fanout.py: ארבעה שלבים</b><pre dir="ltr">plan      complete_structured(..., SubQuestions)  # 2-5 INDEPENDENT sub-questions
map       ThreadPoolExecutor: one research Agent per sub-question
          (search_docs + read_corpus_doc, clean context, answer with [doc_id])
reduce    one synthesis call over the short answers only
check     every [doc_id] in the answer must be a document a worker actually read</pre></div>
<p><b>מה מקביליות קונה, ומה לא:</b> בתרגיל 5, עם השהיה מדומה של חצי שנייה לכל קריאת מודל, שלוש תתי-שאלות עם worker אחד לוקחות פי שלושה יותר זמן בשלב ה-map מאשר עם ארבעה workers. מספר הטוקנים <b>זהה</b>. מקביליות קונה זמן, לא חוסכת כסף. כל worker משלם על הפרומפט, על הגדרות הכלים ועל המסמכים שלו.</p>
<p><b>מתי זה לא עובד:</b> תתי-שאלות שתלויות זו בזו לא יכולות לרוץ במקביל. "איזה שירות גרם לתקלה של אוגוסט, ומי בכונן שלו?" היא שאלה בשני שלבים, כי את השירות צריך לדעת לפני שאפשר לשאול על הכונן. Anthropic כותבים שרוב משימות הקוד כוללות פחות משימות שאפשר באמת להריץ במקביל מאשר מחקר, ושמערכות שבהן כל ה-agents צריכים את אותו הקשר, או שיש בהן הרבה תלויות, לא מתאימות לדפוס הזה כיום.</p>
<p><b>הנחיה כמה agents:</b> הפרומפט של מערכת המחקר מגדיר מאמץ לפי סוג השאלה. לחיפוש עובדה פשוטה: agent אחד עם 3 עד 10 קריאות. להשוואה ישירה: 2 עד 4 subagents. למחקר מורכב: יותר מ-10. בגרסאות המוקדמות, המערכת הפעילה 50 subagents לשאילתות פשוטות. גבולות צריך לכתוב בפרומפט ולאכוף בקוד.</p>
<div class="callout">בדיקת הציטוטים במעבדה תופסת ציטוט שהומצא, כלומר מסמך שאף worker לא קרא. היא לא תופסת מסמך <b>ישן</b> שבאמת נקרא, למשל hr-vacation-2024 במקום 2026, כי הציטוט "נתמך". את זה תופס רק זהב.</div>`,
    },
    {
      kicker: "ביקורת",
      title: "כותב ומבקר: rubric, בדיקות קוד ותקרת סבבים",
      html: `<p>דפוס evaluator-optimizer: agent אחד כותב, agent אחר בודק מול קריטריונים ומחזיר הערות, והכותב מתקן. Anthropic ממליצים עליו כשיש קריטריונים ברורים, וכשסבב נוסף משפר בצורה מדידה. Cognition מתארים ב-2026 לולאה כזו בקוד: Devin כותב ו-Devin Review בודק. לפי המאמר, המבקר מוצא בממוצע 2 באגים ל-PR, וכ-58% מהם חמורים. הם מציינים שהלולאה עובדת הכי טוב כש-"the coding and review agents do not share any context beforehand".</p>
<div class="example"><b>multikit/critic.py: חמישה קריטריונים להודעה ל-Dana על AR-00001</b><pre dir="ltr">facts           [code] request id, system and approver are in the draft
length          [code] at most 80 words
no_promise      [llm]  does not say access is already granted
next_step       [llm]  who reviews, within how many business days, when it expires
plain_language  [llm]  explains the track (no bare "needs_security")
loop: draft -> code checks -> critic (structured Review) -> stop if all pass, else feedback (max_rounds)</pre></div>
<p><b>שלושה כללים:</b></p>
<ol>
<li><b>מה שקוד יכול לבדוק, קוד בודק.</b> ספירת מילים וקיום מזהה בקשה לא צריכים מודל. בדיקה בקוד חינמית, דטרמיניסטית, ולא מתווכחת. בתרגיל 8, עם <code>--no-code-checks</code>, תראה אם Haiku סופר מילים נכון.</li>
<li><b>המבקר מקבל הקשר נקי:</b> ה-rubric, העובדות והטיוטה, בלי השיחה של הכותב. מבקר שקרא את הנימוקים של הכותב נוטה להסכים איתו.</li>
<li><b>תמיד יש תקרה.</b> מבקר שתמיד מוצא משהו (במעבדה, מצב nitpick) שורף סבבים עד max_rounds. מבקר שתמיד מאשר (מצב lenient) הוא חותמת גומי. במעבדה, הטיוטה שהוא אישר הבטיחה לעובדת "you now have access", ורק בדיקת הקוד של facts עצרה סבב אחד.</li>
</ol>
<p><b>מחיר:</b> כל סבב הוא קריאת כתיבה ועוד קריאת ביקורת, והטיוטה והערות נשלחות מחדש בכל סבב. בדרך כלל שניים עד שלושה סבבים מספיקים. אם צריך יותר, הבעיה היא כנראה ב-rubric או בפרומפט של הכותב, לא במספר הסבבים.</p>`,
    },
    {
      kicker: "תקשורת",
      title: "מצב משותף מול העברת הודעות",
      html: `<p>יש שתי דרכים שבהן agents יודעים מה אחרים עשו, ולכל אחת יש מחיר אחר.</p>
<ul>
<li><b>העברת הודעות (message passing).</b> כל agent מקבל רק מה ששלחו לו: משימה, סיכום או תשובה. כך עובדים כל הדפוסים ב-multikit. היתרון הוא בידוד: כל agent רואה מעט, וברור מה הוא קיבל, כי זה כתוב ב-trajectory שלו. החיסרון הוא שמידע שלא נשלח לא קיים, וכל שליחה היא דחיסה.</li>
<li><b>מצב משותף (shared state, blackboard).</b> כל ה-agents קוראים וכותבים לאותו אובייקט. זה ה-state של LangGraph משיעור 16, או session state ב-Google ADK. היתרון: אין דחיסה, וכל אחד רואה את העובדות העדכניות. החיסרון: כל agent עלול לקרוא הכל ולשלם על זה, כתיבות מקבילות מתנגשות, ובאג של agent אחד משחית את המצב של כולם.</li>
</ul>
<p><b>הכלל שעובד בפועל</b> לגבי כתיבות: Cognition כותבים במאמר של אפריל 2026 שהדבר המשותף לדפוסים שעובדים אצלם הוא "writes stay single-threaded and the additional agents contribute intelligence rather than actions". כלומר, agent אחד כותב, והשאר קוראים, בודקים ומייעצים. גם ב-Company Brain כדאי לבנות כך: <code>create_access_request</code> שייך רק ל-it_access, וגם אז הוא עובר דרך אדם. ה-workers של HR ושל oncall לא כותבים כלום.</p>
<div class="example"><b>מה קרה בתרגיל 7 כשה-supervisor האציל שוב ל-worker שכותב</b><pre dir="ltr">verify=code  x01  re-delegated=yes  filed=2 call(s)/1 id(s)  &lt;- expected 1 request, got 2
# the worker ran again and called create_access_request again;
# the idempotency key (lesson 14) returned the SAME AR-00001, so nothing was duplicated,
# but the human was asked to confirm twice</pre></div>
<p>זו התפשטות כשל קלאסית: worker שענה לא נכון, supervisor שתפס ושלח שוב (מה שנכון), והרצה חוזרת שמבצעת שוב את תופעת הלוואי. מה שהציל את המצב הוא idempotency key בצד הכלי, לא שיקול דעת של מודל. התיקון הנכון הוא להעביר בהאצלה החוזרת את ה-actions_taken, כמו בחוזה של ה-handoff.</p>`,
    },
    {
      kicker: "המחיר",
      title: "מחיר התיאום: טוקנים, זמן וכסף",
      html: `<p>המספר הכי מצוטט מגיע מ-Anthropic: agents משתמשים בערך בפי 4 יותר טוקנים מאינטראקציית צ'אט, ומערכות multi-agent בערך בפי 15. הם גם מצאו שבמבחן BrowseComp, כמות הטוקנים לבדה הסבירה 80% מהשונות בביצועים, ויחד עם מספר קריאות הכלים ובחירת המודל, 95%. כלומר, חלק גדול מהיתרון של multi-agent במחקר הוא פשוט שהוא <b>מוציא יותר טוקנים על הבעיה</b>, במקביל ובהקשרים נקיים. המסקנה שלהם: הכלכלה עובדת רק למשימות שערכן מצדיק את העלות.</p>
<p><b>מאיפה הטוקנים באים:</b></p>
<ul>
<li><b>פרומפט בסיס לכל agent.</b> כל worker משלם מחדש על פרומפט המערכת שלו, על הגדרות הכלים, ובשיעור 15 ראית שגם על 286 טוקני ה-tool prompt של Anthropic, בכל צעד.</li>
<li><b>שכבת התיאום.</b> ה-supervisor משלם על הפרומפט שלו, על המשימות שהוא כותב, ועל כל התשובות שחוזרות אליו. במעבדה, ב-offline, זה 31% מהעלות של דפוס ה-supervisor על 23 המשימות, ו-7% אצל הנתב.</li>
<li><b>עבודה כפולה.</b> מסמך ששני workers קוראים נקרא פעמיים. האצלה חוזרת אחרי טעות מריצה את כל ה-worker מחדש: בתרגיל 7, x01 עם verify עלה בערך 28 אלף טוקנים במקום 15 אלף.</li>
</ul>
<div class="example"><b>נמדד במעבדה, offline: 23 משימות, מודלים מזויפים, טוקנים מוערכים</b><pre dir="ltr">single      success 23/23  cross 8/8  tokens 233,809   x1.00
router      success 16/23  cross 1/8  tokens 134,474   x0.58
router2     success 22/23  cross 7/8  tokens 179,540   x0.77
supervisor  success 23/23  cross 8/8  tokens 248,917   x1.06   coordination 31%
handoff     success 23/23  cross 8/8  tokens 335,903   x1.44   coordination 16%</pre></div>
<p><b>קריאה כנה של הטבלה:</b> ב-offline, ה-agent היחיד מצליח בכל המשימות. זה לא מפתיע, כי ה"מודל" המזויף שלו מפרק משימות בדיוק כמו ה-supervisor המזויף. הטבלה מראה את <b>המחיר</b> של כל דפוס, לא את <b>האיכות</b> של Claude בכל דפוס. את האיכות תמדוד מול Haiku בתרגיל 6. אם גם שם ה-agent היחיד מצליח כמו ה-supervisor ובפחות טוקנים, זו המסקנה ל-Company Brain, ולא כישלון של התרגיל.</p>
<p><b>זמן:</b> מקביליות מקצרת את הזמן הכולל עד לזמן של ה-worker האיטי ביותר, ועוד קריאות התיאום. ברצף (handoff, או supervisor שמאציל אחד אחד), הזמן הוא סכום. גם ה-supervisor עצמו מוסיף לפחות שתי קריאות: אחת כדי לחלק, ואחת כדי לחבר.</p>`,
    },
    {
      kicker: "כשלים",
      title: "התפשטות כשלים והצטברות שגיאות",
      html: `<p>המחקר "Why Do Multi-Agent LLM Systems Fail?" (Cemri ועמיתים, מ-Berkeley, NeurIPS 2025) ניתח שבע מסגרות multi-agent פופולריות, על יותר מ-200 משימות, עם שישה מתייגים מומחים (Cohen's Kappa של 0.88). הם הגיעו ל-14 סוגי כשל בשלוש קטגוריות: בעיות <b>הגדרה</b> (תפקיד לא ברור, משימה לא מוגדרת), <b>חוסר תיאום בין agents</b> (מידע שלא הועבר, agent שמתעלם מאחר), ו<b>אימות</b> (אף אחד לא בודק, או בדיקה שטחית). נקודת המוצא שלהם: על בנצ'מרקים פופולריים, השיפור לעומת agent יחיד "often remain minimal".</p>
<p><b>החשבון של הצטברות שגיאות.</b> אם התוצאה נכונה רק כשכל agent בשרשרת צדק, ההסתברויות מוכפלות. חמישה agents עם 95% כל אחד נותנים 0.95 בחזקת 5, כלומר בערך 77%. עשרה agents נותנים 60%. שרשרת ארוכה של agents סבירים היא מערכת לא סבירה. בסימולטור למטה אפשר לשחק עם המספרים, ולראות כמה בדיקה טובה צריכה לתפוס כדי לחזור למעלה.</p>
<p><b>מה קרה בתרגיל 7:</b> התשובה של worker אחד שובשה, בזמן שהכלים והראיות שלו נשארו נכונים:</p>
<ul>
<li><b>verify=none:</b> ה-supervisor ראה רק את התשובה, וכל השיבושים עברו הלאה, אל המשתמש. ה-supervisor לא יכול לתפוס טעות שאין לו מול מה להשוות אותה.</li>
<li><b>verify=llm:</b> ה-worker מחזיר גם את הראיות (תוצאות הכלים הגולמיות), וה-supervisor מתבקש להשוות. המודל המזויף תמיד משווה. אם Haiku עושה את זה, ובאיזו תדירות, זו מדידה שלך.</li>
<li><b>verify=code:</b> קוד משווה את התשובה לראיות (<code>evidence_conflicts</code>): מסלול מול check_policy, שם ראש צוות ורוטציה מול הקטלוג, מזהה בקשה מול מה שנפתח. זה דטרמיניסטי וזול. חוק האצבע: כל בדיקה שאפשר לכתוב בקוד, עדיפה על לבקש ממודל "לשים לב".</li>
<li><b>מה אף מצב לא תופס:</b> מספר שהשתנה בתשובת ה-HR (10 ימים במקום 5). אין לו ראיה מובנית, כי ה-worker קרא מסמך. גם מסמך ישן שנקרא ומצוטט "נכון" לא נתפס. את אלה תופס רק eval מול זהב.</li>
</ul>`,
    },
    {
      kicker: "הערכה",
      title: "הערכה: מקצה לקצה, ואחר כך ייחוס לכל agent",
      html: `<p>הטעות הנפוצה היא להעריך כל agent לבד: ה-router מסווג נכון ב-95%, כל worker מצליח ב-90%, ולכן "המערכת טובה". המשתמש לא רואה agents. הוא רואה תשובה אחת, ולכן <b>המדד הראשי הוא מקצה לקצה</b>, מול אותו זהב שבו מודדים agent יחיד. רק כך ההשוואה בין הדפוסים הוגנת.</p>
<div class="example"><b>multikit: אותו בודק משיעור 15, על העץ כולו</b><pre dir="ltr">merged = merge_for_scoring(result)   # all agents' steps (delegate/transfer calls removed)
                                     # + one stop record: the user-facing text, TOTAL tokens and cost
score  = agentkit.score_trajectory(merged, gold)   # request fields, required/forbidden tools,
                                                    # facts in the answer, evidence conflicts
blame  = attribute_failure(result, score, gold)     # "router: did not route to it_access"
                                                    # "coordination: oncall never ran"
                                                    # "coordination: hr found it but the final answer dropped it"
agg    = aggregate_runs(result.records)  # per agent: tokens, cost, share, coordination share, parallelism</pre></div>
<p><b>ייחוס לכל agent</b> עונה על שתי שאלות שהמדד הראשי לא עונה עליהן. הראשונה: <b>איפה הכסף הולך?</b> (תרגיל 6): כמה עלה כל agent, איזה חלק מהעלות הוא תיאום, והאם ה-agents באמת רצו במקביל, כלומר זמן agents כולל חלקי זמן קיר. השנייה: <b>מי גרם לכשל?</b> אם ה-router לא ניתב ל-it_access, הכשל של המשימה הוא של ה-router, גם אם ה-worker של oncall עשה עבודה מושלמת. אם worker מצא עובדה וה-supervisor השמיט אותה בחיבור, זה כשל תיאום, לא כשל של ה-worker. שם צריך לתקן את הפרומפט של ה-supervisor, לא להחליף מודל ל-worker.</p>
<p><b>ממה ש-Anthropic למדו בהערכת המערכת שלהם:</b></p>
<ul>
<li>הם התחילו עם בערך 20 שאילתות אמיתיות. בהתחלה האפקטים גדולים, ולכן מדגם קטן מספיק כדי לראות אותם.</li>
<li>שופט LLM עם rubric (דיוק עובדתי, דיוק ציטוטים, שלמות, איכות מקורות, יעילות כלים) בקריאה אחת, שמחזירה ציון מ-0 עד 1 ו-pass/fail, היה העקבי ביותר.</li>
<li>במערכות עם מצב, הם העדיפו להעריך את <b>מצב הסיום</b> ("whether it achieved the correct final state") ולא כל צעד. אצלנו: האם נפתחה הבקשה הנכונה, ולא אילו agents רצו בדרך.</li>
<li>בדיקה אנושית תפסה מה שהאוטומציה פספסה. אצלם, למשל, הטיה לטובת אתרי תוכן מקודמים.</li>
</ul>`,
    },
    {
      kicker: "כלים",
      title: "נוף הכלים בנובמבר 2026",
      html: `<p>כל הכלים האלה מממשים את אותם דפוסים. מה שחשוב הוא לדעת מה כל אחד עושה מתחת למכסה, ובמיוחד מה עובר בין agents כברירת מחדל. כל מה שכתוב כאן נבדק בתיעוד הרשמי בנובמבר 2026:</p>
<ul>
<li><b>OpenAI Agents SDK.</b> handoff מוצג למודל ככלי <code>transfer_to_&lt;agent&gt;</code>. כברירת מחדל, ה-agent החדש רואה את כל השיחה, ו-<code>input_filter</code> משנה את זה. ל-<code>nest_handoff_history</code> (בטא, כבוי כברירת מחדל) יש אזהרה מפורשת: הוא לא מסתיר מידע רגיש. <code>Agent.as_tool</code> הוא דפוס ה-supervisor: מומחה שנקרא ככלי, בלי להעביר את השיחה.</li>
<li><b>LangGraph ו-LangChain.</b> לספרייה langgraph-supervisor יש <code>create_supervisor</code>, עם handoff tools ו-<code>output_mode</code> של full_history או last_message. אבל ה-README שלה אומר היום: "We now recommend using the supervisor pattern directly via tools rather than this library for most use cases". התיעוד של LangChain מתאר ארבעה דפוסים: subagents, handoffs, skills ו-router, ומשווה ביניהם במספר קריאות ובטוקנים. ב-LangGraph יש גם swarm, שהוא handoffs בלי מנהל.</li>
<li><b>CrewAI.</b> agents עם role ו-goal, ו-Crew שרץ ב-<code>Process.sequential</code> (ברירת המחדל) או ב-<code>Process.hierarchical</code>, עם manager שמחלק משימות ובודק תוצאות. ההאצלה כבויה כברירת מחדל.</li>
<li><b>Claude Agent SDK.</b> subagents מוגדרים ב-<code>agents</code> (AgentDefinition: description, prompt, tools, model ועוד), ונקראים דרך הכלי <code>Agent</code>, שנקרא קודם Task. כל subagent מתחיל בשיחה חדשה, ורק ההודעה הסופית שלו חוזרת להורה. יש הגבלות על עומק, על מקביליות ועל תקציב, כפי שראית בשקופית על היררכיה.</li>
<li><b>Google ADK.</b> ב-2.0 יש graph-based workflows, שמשלבים agents וצמתים דטרמיניסטיים בגרף. יש גם template workflows: sequential, loop ו-parallel. יש collaborative workflows, שבהם agent מתאם sub-agents, ו-agent routing ניסיוני.</li>
<li><b>A2A (Agent2Agent).</b> פרוטוקול פתוח לתקשורת <b>בין agents</b> של ספקים ומסגרות שונים. Google פיתחו אותו ותרמו אותו ל-Linux Foundation, והוא מתוחזק בידי ועדה עם נציגים מ-AWS, Cisco, Google, IBM, Microsoft, Salesforce, SAP ו-ServiceNow. האתר שלו מגדיר את היחס ל-MCP משיעור 17: MCP הוא agent-to-tool, A2A הוא agent-to-agent, והוא "Not a replacement for MCP".</li>
</ul>
<div class="callout">Anthropic כותבים ב-Building effective agents שמסגרות מקלות על ההתחלה, אבל מוסיפות שכבות שמסתירות את הפרומפטים ואת התשובות, ולכן קשה יותר לדבג. ההמלצה שלהם: להתחיל עם ה-API ישירות, ואם משתמשים במסגרת, להבין את הקוד שמתחתיה. multikit הוא בערך 2,000 שורות מעל agentkit, כולל המודלים המזויפים, וזה פחות או יותר מה שכל מסגרת עושה.</div>`,
    },
    {
      kicker: "ההחלטה",
      title: "מתחילים עם agent אחד, ומוסיפים רק כשמדדנו",
      html: `<p>כל המקורות בשיעור הזה מגיעים, בסוף, לאותה המלצה. Anthropic: למצוא את הפתרון הפשוט ביותר, ולהוסיף מורכבות רק כשצריך. LangChain (ינואר 2026): להתחיל עם agent יחיד וכלים מתוכננים היטב, ולהוסיף agents רק כשניהול ההקשר או פיתוח מבוזר הופכים לבעיה אמיתית. Cognition: לא להריץ כותבים במקביל. המחקר של Berkeley: השיפור לעתים קרובות קטן.</p>
<p><b>סדר העבודה שאני ממליץ עליו ל-Company Brain:</b></p>
<ol>
<li><b>agent יחיד, עם eval.</b> 23 המשימות של המעבדה הן ההתחלה. מודדים הצלחה, טוקנים ועלות להצלחה.</li>
<li><b>מחפשים את הכשל הספציפי.</b> האם ה-agent בוחר כלי לא נכון כשיש עשרה כלים? האם ההקשר מתנפח במשימות עם מסמכים ארוכים? האם הוא שוכח אילוץ באמצע? רק כשל מהסוג הזה הוא סיבה לפצל.</li>
<li><b>הדפוס הזול שפותר אותו.</b> אם רוב הבקשות הן של תחום אחד, router עם fallback של שאלת הבהרה. אם יש הרבה בקשות שחוצות תחומים, supervisor עם delegate tools. עבודה בשלבים עם משתמש שחוזר: handoffs עם חוזה סיכום. מחקר רחב: fan-out.</li>
<li><b>מודדים שוב, מול אותו זהב.</b> משווים הצלחה, טוקנים, זמן, חלק התיאום בעלות, וייחוס כשלים. אם אין שיפור, חוזרים ל-agent היחיד.</li>
<li><b>מגינים על הגבולות.</b> כתיבות אצל agent אחד, ראיות חוזרות למעלה ונבדקות בקוד, תקציב לכל העץ, עומק ומקביליות מוגבלים.</li>
</ol>
<p>מה זה אומר בפועל? Company Brain כנראה יכול להישאר agent אחד עם עשרה כלים עוד הרבה זמן. כשיגיעו תחום רביעי וחמישי, או מסמכים ארוכים באמת, הצעד הראשון יהיה router, לא צוות. זו לא מסקנה מאכזבת. זו בדיוק ההנדסה שהשיעור הזה מלמד.</p>
<div class="callout">ה"עוזר להחלטה" בכרטיסיית התרגול מנסח את השאלות האלה כרשימה. נסה לענות עליו לגבי שלוש מערכות: Company Brain, מערכת מחקר וסוכן קוד, וראה איך ההמלצה משתנה.</div>`,
    },
  ],

  sims: [
    {
      id: "l18decide",
      title: "האם זה צריך להיות multi-agent?",
      lead: "תשע שאלות על המשימה שלך: מדידה, כלים, הקשר, מקביליות, תלויות, כתיבות, ערך וזמן תגובה. בכל תשובה ההמלצה מתעדכנת, ולידה הנימוקים בעד ונגד. ברירת המחדל, כשאין מספיק סיבות, היא agent יחיד.",
      tasks: [
        "לחץ על <b>דוגמה: Company Brain</b>. למה ההמלצה היא router ולא supervisor? איזו תשובה הייתה צריכה להשתנות כדי שההמלצה תהיה supervisor?",
        "לחץ על <b>דוגמה: סוכן קוד</b>. איזה דפוס מומלץ, ואיזה משפט של Cognition מסביר אותו?",
        "שנה בכל אחת מהדוגמאות את התשובה לשאלה הראשונה (מדדת?) ל\"לא\". מה קורה להמלצה, ולמה זה צריך להיות כך?",
      ],
    },
    {
      id: "l18cost",
      title: "סימולטור מחיר התיאום",
      lead: "agent יחיד מול supervisor עם workers, על אותה עבודה. מזיזים את מספר ה-workers, את גודל הפרומפט, את הגדרות הכלים, את מה שנוסף בכל צעד ואת גודל התשובות, ורואים טוקנים, הקשר מקסימלי, עלות וזמן.",
      tasks: [
        "השאר את ברירות המחדל, והעלה את מספר ה-workers מ-1 ל-6. מה קורה ליחס הטוקנים, ומה קורה ל<b>הקשר הגדול ביותר</b> של agent יחיד לעומת worker?",
        "הורד את \"טוקנים שנוספים בכל צעד\" ל-100, והעלה את \"פרומפט בסיס\" ל-3000. מתי multi-agent נעשה יקר יותר, ולמה?",
        "עבור ל-<b>workers ברצף</b>. מה קורה לזמן, ומה קורה לטוקנים? מה המסקנה לגבי ההבטחה ש\"מקביליות חוסכת\"?",
      ],
    },
    {
      id: "l18fail",
      title: "הצטברות שגיאות ובדיקה",
      lead: "כמה agents תלויים זה בזה, כל אחד צודק בהסתברות p. מה הסיכוי שהתוצאה הסופית נכונה, ומה בדיקה או הצבעה עושות לסיכוי ולעלות? מתחת למחשבון: התוצאות שנמדדו בתרגיל 7.",
      tasks: [
        "קבע <b>p=95%</b> והעלה את <b>n</b> מ-1 ל-8. באיזה n הסיכוי יורד מתחת ל-70%?",
        "עם n=5: כמה אחוזים מהשגיאות הבדיקה צריכה לתפוס (<b>c</b>) כדי לחזור ל-90%? כמה זה עולה בקריאות?",
        "ברשימה של תרגיל 7: איזה סוג שיבוש לא נתפס באף מצב, ולמה הצבעה (k=3) לא הייתה עוזרת שם?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/18-multi-agent",
    intro: "המעבדה נמצאת בתיקייה labs/18-multi-agent. החבילה החדשה, <b>multikit</b>, בונה את כל הדפוסים מעל ה-Agent של שיעור 15: router עם structured output, supervisor עם delegate tools, handoffs עם חוזה סיכום, fan-out עם ציטוטים, וכותב ומבקר. יש שלושה מומחים של Acme: <b>hr</b>, <b>it_access</b> ו-<b>oncall</b>. כל דפוס רץ גם עם מודלים מזויפים, חינם, וגם מול Haiku. בלב המעבדה יש השוואה בין agent יחיד, router ו-supervisor על <b>23 משימות</b>: 15 משימות הגישה משיעור 15, ועוד 8 משימות חדשות שחוצות תחומים. לכל משימה יש תוצאת זהב, והטקסט המלא והזהב של כל המשימות מופיעים ב-README של המעבדה.",
    setup: [
      'cd ~/ai-engineer-course-starter && source .venv/bin/activate',
      "python -m pytest -q tests/test_multikit.py          # environment tests",
      "python -m pytest -q labs/18-multi-agent/tests       # your exercises: they fail at first",
    ],
    tools: [
      "<b>build(pattern, model):</b> מחזיר דפוס מוכן להרצה: <code>single</code>, <code>router</code>, <code>router2</code> (שני יעדים), <code>supervisor</code> או <code>handoff</code>. <code>model</code> הוא <code>fake</code> או <code>anthropic:claude-haiku-5-5</code>. כל דפוס מחזיר <code>MultiResult</code>: התשובה, וכל ה-trajectories כעץ (<code>runs</code>).",
      "<b>run_set / score_multi / attribute_failure:</b> מריצים סט משימות, מדרגים כל ריצה עם הבודק של שיעור 15 על העץ המאוחד, ומצביעים על ה-agent שגרם לכשל.",
      "<b>Supervisor(verify=...):</b> <code>none</code>, <code>llm</code> (ה-worker מחזיר ראיות) או <code>code</code> (<code>evidence_conflicts</code> משווה תשובה לראיות). <code>worker_faults</code> משבש את התשובה של worker, לתרגיל 7.",
      "<b>HandoffRunner(brief=...):</b> הבודק של הסיכום. <code>make_handoff_brief</code> (שלך או של הייחוס) או <code>render_unchecked</code>. <code>lossy=True</code> מדמה מסכם רשלני.",
      "<b>הנתונים:</b> <code>data/tasks.jsonl</code> (23 משימות, עם השדה החדש <code>domains</code>), <code>data/research.jsonl</code> (3 שאלות מחקר עם עובדות ומקורות חובה), <code>data/critic_case.json</code> (ההודעה ל-Dana על AR-00001).",
      "<b>mine.py:</b> שלושה חלקים שלך: <code>decide_route</code> (סף ושאלת הבהרה), <code>make_handoff_brief</code> (החוזה של ה-handoff), <code>aggregate_runs</code> (עלות וזמן לכל agent).",
    ],
    exercises: [
      { id: "ex1", title: "Router: סיווג אחד ומומחה אחד", text: "הרץ את הנתב על x03: \"Ofer Levi is on call for billing-service and is sick for three days. Who leads the billing-service team, and when is the billing on-call handover? Does a 3-day sick absence need a medical certificate?\". בזהב, התשובה חייבת להכיל Rina Sasson, Wednesday ו-medical certificate. קרא את ה-RouteDecision ואת ההחלטה של הקוד. מה קרה לשאלה על האישור הרפואי, ומה ייחוס הכשל? הרץ שוב עם --max-targets 2. אחר כך הרץ --accuracy על כל 23 המשימות, offline ומול Haiku (פחות מסנט): האם Haiku מחזיר confidence נמוך ל-x07 (\"Can you sort this out for the new person on my team?\"), והאם הוא מחזיר את כל התחומים במשימות החוצות?", cmd: "python labs/18-multi-agent/run_router.py x03\npython labs/18-multi-agent/run_router.py x03 --max-targets 2\npython labs/18-multi-agent/run_router.py --accuracy --model anthropic:claude-haiku-5-5" },
      { id: "ex2", title: "החלטת ניתוב ו-fallback (קוד)", text: "ממש את decide_route ב-mine.py. החוקים, לפי הסדר: מסירים כפילויות ותחומים לא מותרים וחותכים ל-max_targets; שאלה = clarifying_question אם הוא לא ריק, אחרת DEFAULT_QUESTION; אם לא נשארו יעדים, או אם confidence נמוך מהסף (סף שווה בדיוק עובר), מחזירים clarify. אחר כך הרץ --accuracy --mine עם ספים של 0.5, 0.75 ו-0.95, וספור ניתובים נכונים ושאלות הבהרה. איפה היית שם את הסף ב-Company Brain, ולמה?", cmd: "python -m pytest -q labs/18-multi-agent/tests/test_ex2_router.py\npython labs/18-multi-agent/run_router.py --accuracy --mine --threshold 0.75" },
      { id: "ex3", title: "Supervisor ובידוד הקשר", text: "הרץ את x08: \"Keren Amar from finance has three questions. How many sick days does an employee accrue per month? Who is on call for connectors-hub? Does Keren Amar already have NetSuite access? Do not file anything.\" (זהב: 1.5, integrations-oncall ו-member, ובלי לפתוח בקשה). קרא את שלוש קריאות ה-delegate, ואת גודל ההקשר של כל agent לעומת agent יחיד. מה הצעד הגדול ביותר אצל כל worker, ומה הוא אצל ה-agent היחיד? כמה עלה ה-supervisor עצמו? הרץ עם --sequential. מול Haiku: האם הוא מאציל את שלושת החלקים באותו צעד, והאם ה-task ל-it_access מעתיק את \"Do not file anything\"?", cmd: "python labs/18-multi-agent/run_supervisor.py x08\npython labs/18-multi-agent/run_supervisor.py x08 --sequential\npython labs/18-multi-agent/run_supervisor.py x01 --model anthropic:claude-haiku-5-5 --approve ask" },
      { id: "ex4", title: "Handoff: החוזה של הסיכום (קוד)", text: "משימת ההדגמה h01: \"Who is on call for flow-api? Dana Levi wants admin on aws-production for 3 days. Open the request, but do not file it before Friday.\" (בזהב אסור לפתוח בקשה). ממש את make_handoff_brief: original_request מילה במילה (אחרי נרמול רווחים ואותיות), goal לא ריק, לכל עובדה יש claim ו-source, כל פסוקית אילוץ מהבקשה מופיעה באחד האילוצים, וכל side effect עם id מוזכר ב-actions_taken. אוספים את כל הבעיות וזורקים HandoffError, או מחזירים render_brief. אחר כך הרץ עם מסכם זהיר, עם --lossy, ועם --lossy --no-check. מה קרה בריצה השלישית, ולמה ה-agent של it_access לא יכול לדעת שהוא טועה?", cmd: "python -m pytest -q labs/18-multi-agent/tests/test_ex4_handoff.py\npython labs/18-multi-agent/handoff_demo.py --lossy --mine\npython labs/18-multi-agent/handoff_demo.py --lossy --no-check" },
      { id: "ex5", title: "Fan-out מקבילי עם ציטוטים", text: "שלוש שאלות מחקר ב-data/research.jsonl. למשל r01: הזמינות של flow-api באוגוסט 2026 (זהב: 99.89%, ממסמך eng-pm-2026-08-api) והזיכוי ל-Enterprise כשהזמינות בין 99.5% ל-99.95% (זהב: 10%, מ-sales-sla-2026, שהוא PDF). לכל שאלה: מה תתי-השאלות, אילו מסמכים נקראו, והאם יש ציטוט שלא נתמך. אחר כך השווה worker אחד מול ארבעה, עם השהיה מדומה של חצי שנייה: כמה זמן נחסך, והאם מספר הטוקנים השתנה? מול Haiku, מדוד את הזמן האמיתי.", cmd: "python labs/18-multi-agent/fanout_demo.py\npython labs/18-multi-agent/fanout_demo.py --delay 0.5 --workers 1\npython labs/18-multi-agent/fanout_demo.py --delay 0.5 --workers 4\npython labs/18-multi-agent/fanout_demo.py --model anthropic:claude-haiku-5-5 --workers 4" },
      { id: "ex6", title: "ייחוס עלות (קוד), וההשוואה הגדולה", text: "ממש את aggregate_runs: קבץ רשומות לפי run_id, וסכם לכל agent ריצות, צעדים, קריאות כלים (בלי note), טוקנים, עלות, זמן וחלק מהעלות. לכל המערכת: עלות התיאום (role=coordinator) וחלקה, זמן קיר (ts מקסימלי פחות מינימלי), וזמן agents חלקי זמן קיר (parallelism). אחר כך הרץ את compare.py על 23 המשימות: agent יחיד, router ו-supervisor. מול Haiku, ההרצה עוצרת ב-$0.40. רשום לכל דפוס הצלחה, הצלחה בשמונה המשימות החדשות, טוקנים, עלות, זמן, חלק התיאום וייחוס כשלים. האם ה-supervisor מצדיק את המחיר מול agent יחיד עם עשרה כלים?", cmd: "python -m pytest -q labs/18-multi-agent/tests/test_ex6_attribution.py\npython labs/18-multi-agent/compare.py --mine --show-failures\npython labs/18-multi-agent/compare.py --mine --model anthropic:claude-haiku-5-5" },
      { id: "ex7", title: "תרגיל כשל: worker מחזיר מידע שגוי", text: "failure_demo משבש את התשובה הסופית של worker אחד, בזמן שהכלים והראיות שלו נכונים. יש ארבעה סוגים: route (auto_approve במקום needs_security), lead (ראש צוות שגוי), rotation (רוטציה שגויה) ו-number (10 ימים במקום 5). כל סוג רץ מול verify=none, llm ו-code. לכל שילוב: האם ה-supervisor תפס, ובכמה טוקנים? למה number לא נתפס באף מצב? מה קרה ב-x01 וב-x04 עם route כשה-supervisor האציל שוב, ומה מנע בקשה כפולה בפועל? מול Haiku, עם --verify none,llm: כמה פעמים הוא תפס את הסתירה כשהראיות היו מולו?", cmd: "python labs/18-multi-agent/failure_demo.py\npython labs/18-multi-agent/failure_demo.py --fault route --times 1\npython labs/18-multi-agent/failure_demo.py --fault route,lead --verify none,llm --model anthropic:claude-haiku-5-5" },
      { id: "ex8", title: "כותב ומבקר", text: "ההודעה ל-Dana על AR-00001 (admin ב-aws-production, needs_security, המאשר הוא צוות האבטחה, בדיקה תוך 2 ימי עבודה, תפוגה ב-2026-11-04). ב-rubric יש חמישה קריטריונים: facts ו-length נבדקים בקוד, ו-no_promise, next_step ו-plain_language נבדקים על ידי המבקר. הרץ עם מבקר strict, lenient ו-nitpick. כמה סבבים היו בכל מצב, ומה עלה כל סבב? מה הטיוטה של lenient הבטיחה לעובדת, ומי בכל זאת תפס משהו? מול Haiku: כמה סבבים, ועם --no-code-checks, האם הוא ספר מילים נכון?", cmd: "python labs/18-multi-agent/critic_demo.py\npython labs/18-multi-agent/critic_demo.py --critic lenient\npython labs/18-multi-agent/critic_demo.py --model anthropic:claude-haiku-5-5 --no-code-checks" },
    ],
  },

  quiz: [
    { q: "נמדד במעבדה על x08 (שלוש שאלות משלושה תחומים, מודלים מזויפים): ל-agent היחיד, הצעד הגדול ביותר היה 4,011 טוקנים, והסך 17,879. בדפוס ה-supervisor, אף מודל לא ראה יותר מ-2,229 טוקנים בצעד, והסך 15,166. על כל 23 המשימות, ה-supervisor צרך פי 1.06 מה-agent היחיד. מה הדפוס קונה כאן באמת?", options: ["חיסכון בטוקנים: x08 מראה שפיצול זול יותר, והתוספת של 6% היא רעש", "כל מודל רואה הקשר קטן וממוקד יותר בכל צעד. הסך הכולל לא בהכרח קטן, ובמשימות של תחום אחד שכבת התיאום היא תוספת נטו", "מקביליות: שלושת ה-workers רצו במקביל, ולכן גם הזמן וגם הטוקנים ירדו", "איכות: ה-workers מצליחים יותר כי לכל אחד יש פחות כלים, ולכן ה-supervisor הצליח במשימות שה-agent היחיד נכשל בהן"], correct: 1, explain: "היתרון האמיתי הוא <b>בידוד הקשר</b>: כל worker מתחיל קטן ונשאר קטן, וזה מה ש-Anthropic מתארים כ-separation of concerns. אבל x08 הוא משימה חוצת תחומים, ועל כל 23 המשימות ה-supervisor <b>יקר יותר</b>, כי רוב המשימות הן של תחום אחד. מקביליות קונה זמן, לא טוקנים. ובטבלת ה-offline גם ה-agent היחיד הצליח ב-23 מתוך 23, ולכן אין כאן ראיה לאיכות." },
    { q: "ה-RouteDecision שחזר מהמודל: <code>routes=[\"oncall\"]</code>, <code>confidence=0.55</code>, <code>clarifying_question=null</code>. הקריאה היא <code>decide_route(decision, threshold=0.6, max_targets=1)</code>, והתחומים המותרים הם hr, it_access ו-oncall. מה חוזר?", options: ["<code>RouteChoice(\"route\", [\"oncall\"])</code>, כי נשאר יעד מותר אחד, והוא בדיוק max_targets", "<code>RouteChoice(\"clarify\", [], DEFAULT_QUESTION)</code>: ה-confidence מתחת לסף, והמודל לא כתב שאלה, ולכן משתמשים בשאלת ברירת המחדל", "<code>RouteChoice(\"clarify\", [], None)</code>: מחזירים clarify בלי שאלה, כי המודל לא כתב אחת", "<code>RouteChoice(\"route\", [\"oncall\"])</code> עם אזהרה בשדה why, כי 0.55 קרוב מספיק לסף"], correct: 1, explain: "יש יעד מותר, אבל <b>confidence מתחת לסף</b>, ולכן <b>שואלים ולא מנחשים</b>. כש-clarifying_question ריק, הקוד משתמש ב-<b>DEFAULT_QUESTION</b>, כדי שלמשתמש תמיד תגיע שאלה. העובדה שיש יעד מותר אחד היא תנאי הכרחי לניתוב, אבל לא מספיק: הסף נבדק אחריו. שאלת הבהרה עולה הודעה אחת, וניתוב שגוי של בקשת גישה עולה הרבה יותר." },
    { q: "משימה x03: \"Ofer Levi is on call for billing-service and is sick for three days. Who leads the billing-service team, and when is the billing on-call handover? Does a 3-day sick absence need a medical certificate?\". ה-router, עם max_targets=1, נכשל: בתשובה חסר \"medical certificate\". למי attribute_failure מייחס את הכשל, ולמה?", options: ["ל-worker של oncall: הוא קיבל את כל הבקשה, כולל שאלת המחלה, ולא ענה עליה", "ל-router: ההחלטה התקבלה פעם אחת, לפני שמישהו עבד, ובקשה של שני תחומים נשלחה למומחה אחד. hr לא רץ בכלל", "לתיאום: hr מצא את התשובה, אבל החיבור הסופי השמיט אותה", "ל-router, כי ה-confidence היה נמוך והוא שאל שאלת הבהרה במקום לנתב"], correct: 1, explain: "זו חולשה <b>מבנית</b> של router: אחרי הסיווג, קוד שולח למומחה אחד, ושום דבר לא בודק אם נשאר חלק בלי מענה. attribute_failure מצביע על \"router: did not route to hr\". ה-worker של oncall אכן קיבל את כל הטקסט, אבל אין לו כלים של HR, ולכן הכשל לא שלו, והתיקון הוא לא להחליף לו מודל. כשל תיאום (\"found it but the final answer dropped it\") דורש ש-hr ירוץ, וב-router אין בכלל שלב חיבור." },
    { q: "על x08, ה-supervisor שלח: <code>delegate_to_it_access(task=\"Check whether she already has NetSuite access.\", context=null)</code>. מה יקרה ב-worker?", options: ["ה-worker יבין ש-she היא Keren Amar, כי הוא רץ באותו תהליך ורואה את השיחה של ה-supervisor", "ה-worker יקבל רק את ה-task וה-context האלה, ולא יודע מי היא. גם האילוץ \"Do not file anything\" לא הגיע אליו", "הוולידציה של <code>DelegateInput</code> תדחה את הקריאה, כי אין ב-task שם של עובד", "ה-worker יקרא את הבקשה המקורית מהמצב המשותף של multikit"], correct: 1, explain: "ב-supervisor של multikit ה-worker מתחיל מ<b>הקשר נקי</b>: הדבר היחיד שעובר הוא ה-<b>task</b> וה-<b>context</b>. כך זה גם ב-Claude Agent SDK, שבו רק מחרוזת ה-prompt עוברת ל-subagent. DelegateInput הוא סכמה של שני שדות טקסט: התיאור שלו מבקש משימה שלמה, אבל קוד לא בודק שיש בה שם. וכל הדפוסים ב-multikit עובדים בהעברת הודעות, לא במצב משותף." },
    { q: "משימה h01: \"... Dana Levi wants admin on aws-production for 3 days. Open the request, but do not file it before Friday.\". בהרצה עם <code>--lossy</code>, ה-triage העביר ל-it_access סיכום חופשי: \"Open the request.\", בלי בדיקת החוזה. מה קורה?", options: ["ה-agent של it_access יזהה שהסיכום חשוד וישאל את המשתמש, כי בקשת admin תמיד מעוררת בדיקה", "ה-agent של it_access פותח בקשה עכשיו. הסיכום נראה תקין לגמרי, והאילוץ פשוט לא הגיע אליו, ולכן אין לו דרך לדעת שהוא טועה", "ה-idempotency key של create_access_request ימנע את הפתיחה, כי הבקשה כבר קיימת", "ה-agent של it_access יראה את השיחה המלאה, כמו בברירת המחדל של OpenAI Agents SDK, וימצא את האילוץ שם"], correct: 1, explain: "ניסוח מחדש <b>משמיט אילוצים</b>, וה-agent הבא לא יכול לדעת מה לא הגיע אליו. לכן החוזה של multikit דורש original_request <b>מילה במילה</b> ואת כל פסוקיות האילוץ, ודוחה העברה עם \"constraint missing: 'do not file it before Friday'\". idempotency key מונע <b>כפילות</b> של בקשה שכבר נפתחה, לא פתיחה מוקדמת של הראשונה. וב-multikit ה-agent הבא מקבל את הסיכום, לא את כל השיחה." },
    { q: "בתרגיל 5, fan-out עם שלוש תתי-שאלות בלתי תלויות, והשהיה מדומה של חצי שנייה לכל קריאת מודל. מריצים פעם עם worker אחד ופעם עם ארבעה workers. מה צפוי בשלב ה-map?", options: ["הזמן יורד לבערך שליש, ומספר הטוקנים זהה", "הזמן יורד לבערך רבע, כי יש ארבעה workers, ומספר הטוקנים זהה", "הזמן יורד לבערך שליש, והטוקנים יורדים, כי כל worker רואה הקשר קטן יותר", "הזמן לא משתנה, כי קריאות המודל של כל worker הן ברצף"], correct: 0, explain: "<b>מקביליות קונה זמן, לא חוסכת טוקנים.</b> עם שלוש תתי-שאלות, רק שלושה workers עובדים, ולכן הזמן יורד בערך פי שלושה, לא פי ארבעה: ה-worker הרביעי פשוט לא מקבל עבודה. מספר הטוקנים זהה, כי אותם שלושה agents רצים עם אותם פרומפטים, כלים ומסמכים, רק בו-זמנית. ההקשר של כל worker קטן בשני המקרים, ולכן גם הוא לא משנה את הסכום." },
    { q: "שרשרת של ארבעה agents, שכל אחד מהם צודק ב-90% מהמקרים, באופן בלתי תלוי. התוצאה נכונה רק אם כולם צדקו, ואין בדיקה בין השלבים. מה בערך הסיכוי לתוצאה נכונה?", options: ["90%, כי השרשרת טובה כמו החוליה החלשה שלה", "בערך 66%", "60%, כי כל agent מוריד 10%", "81%, כי רק שתי טעויות יכולות להצטבר"], correct: 1, explain: "ההסתברויות <b>מוכפלות</b>: 0.9 בחזקת 4 הוא בערך <b>0.656</b>. 60% הוא החיסור הלינארי (100 פחות 4×10), שמניח שטעויות לא חופפות, ולכן הוא קרוב אבל נמוך מדי. \"החוליה החלשה\" נכון למערכת שבה כל agent יכול לתקן את קודמו, לא לשרשרת שבה כל טעות עוברת הלאה. לכן שרשרת ארוכה צריכה בדיקות בין השלבים." },
    { q: "worker של HR קרא את מסמך המדיניות, והחזיר ל-supervisor \"10 ימים\" במקום \"5 ימים\". כל קריאות הכלים שלו נכונות. איזה מצב verify של תרגיל 7 יתפוס את השיבוש?", options: ["verify=none", "verify=llm, כי ה-supervisor מקבל את הראיות ומתבקש להשוות", "verify=code, כי evidence_conflicts משווה את התשובה לראיות", "אף אחד באופן אמין: אין ראיה מובנית למספר הזה, כי הוא בא מטקסט חופשי של מסמך. רק eval מול זהב תופס"], correct: 3, explain: "<b>evidence_conflicts</b> משווה שדות מובנים מכלים: מסלול מול check_policy, ראש צוות ורוטציה מול הקטלוג, מזהה בקשה מול מה שנפתח. מספר שמופיע בתוך <b>טקסט של מסמך</b> אין לו מול מה להשוות בקוד. verify=llm נשמע מבטיח, כי ה-supervisor מקבל את הראיות, אבל המודל המזויף \"תמיד משווה\" רק ב-offline, ואם Haiku ימצא מספר בתוך מסמך ארוך זו מדידה שלך, לא הבטחה. את זה תופס <b>eval מול זהב</b>." },
    { q: "טבלת ה-offline על 23 המשימות: single הצליח ב-23/23 עם 233,809 טוקנים, supervisor הצליח ב-23/23 עם 248,917 טוקנים (פי 1.06). מה המסקנה הנכונה ל-Company Brain?", options: ["להישאר עם agent יחיד: הוא הצליח בכל המשימות וזול יותר, ולכן ה-supervisor מיותר", "לעבור ל-supervisor: 6% תוספת זה מחיר נמוך על בידוד הקשר", "עדיין אין מסקנה על איכות: המודלים המזויפים מפרקים משימות באותה דרך, ולכן הטבלה מראה מחיר ולא איכות. ההחלטה תלויה במדידה מול מודל אמיתי", "להעדיף router2: 22/23 ב-0.77 מהטוקנים הוא היחס הטוב ביותר"], correct: 2, explain: "המספרים המזויפים מראים את <b>המנגנון והמחיר</b> של כל דפוס, לא את האיכות של Claude בו. \"להישאר עם agent יחיד\" עשויה להיות המסקנה הנכונה בסוף, אבל רק אם <b>גם מול Haiku</b> ה-agent היחיד מצליח כמו ה-supervisor, וזו בדיוק המדידה של תרגיל 6. בחירה ב-supervisor בגלל בידוד הקשר מתעלמת מזה שכאן לא נמדד שום שיפור. ו-router2 מדביק שתי תשובות שאף מודל לא קרא ביחד." },
    { q: "ב-Company Brain, עובד מתחיל שיחה, triage מזהה שזה נושא גישה, ומשם העובד ממשיך כמה הודעות הלוך ושוב עם המומחה ל-it_access: מבהיר מערכת, מוסיף הצדקה, שואל על משך. איזה דפוס מתאים, ולמה?", options: ["Handoff: השליטה עוברת למומחה ונשארת אצלו לאורך השיחה, ולא צריך לחזור דרך מתאם בכל הודעה", "Agents as tools (supervisor): התשובה חוזרת ל-triage אחרי כל הודעה, ולכן הוא תמיד בשליטה וזה זול יותר", "Router עם max_targets=2, כדי שגם hr יקבל כל הודעה למקרה שהשיחה תעבור לנושא אחר", "Fan-out: כל הודעה של העובד מפוצלת לתתי-שאלות שרצות במקביל"], correct: 0, explain: "<b>handoff מעביר שליטה</b>, ו-agent-as-tool <b>מחזיר תשובה</b> למי שקרא. בשיחה <b>מתמשכת</b> עם אותו מומחה, handoff חוסך את קריאת התיאום בכל הודעה: לפי טבלת LangChain, דפוסים עם מצב חוסכים 40 עד 50 אחוז מהקריאות בבקשה חוזרת. supervisor מתאים כשרוצים מישהו שמחבר כמה תשובות לתשובה אחת, כמו ב-x08, אבל כאן הוא משלם על עוד קריאה בכל סבב. router2 מריץ מומחה מיותר על כל הודעה." },
  ],

  summary: {
    points: [
      { t: "מה זה multi-agent", b: "כמה לולאות agent נפרדות, ולכל אחת יש פרומפט, כלים והקשר משלה, עם מנגנון שמעביר עבודה ביניהן. מה שמבדיל בין הדפוסים הוא מי מחליט מי עובד, מה עובר בין ה-agents, ומי עונה בסוף." },
      { t: "Router", b: "סיווג מובנה אחד, וקוד שמחליט: נתב, או שאל שאלת הבהרה כשה-confidence נמוך. זה הדפוס הזול ביותר (58% מהטוקנים של agent יחיד במעבדה), והחולשה שלו מבנית: בקשה שחוצה תחומים מקבלת תשובה חלקית." },
      { t: "Supervisor", b: "agent שהכלים שלו הם delegate_to_hr, delegate_to_oncall וכן הלאה. האצלות באותו צעד רצות במקביל, וכל worker מתחיל מהקשר נקי ומקבל רק את המשימה שנכתבה לו. שכבת התיאום עלתה במעבדה כשליש מהעלות של הדפוס." },
      { t: "Handoff וחוזה הסיכום", b: "השליטה עוברת ולא חוזרת. מה שעובר חייב לכלול את הבקשה המקורית מילה במילה, עובדות עם מקור, כל תופעת לוואי עם המזהה שלה, וכל אילוץ. סיכום רשלני גורם ל-agent הבא לטעות בלי שהוא יכול לדעת." },
      { t: "Fan-out וביקורת", b: "מקביליות על חלקים בלתי תלויים קונה זמן, לא חוסכת טוקנים, ולא עובדת על שאלות שתלויות זו בזו. כותב ומבקר עובד עם rubric ברור, בדיקות קוד לכל מה שאפשר, מבקר עם הקשר נקי ותקרת סבבים." },
      { t: "בידוד הקשר הוא היתרון", b: "כל מודל רואה פחות ומתמקד יותר. זה מה ש-Anthropic מתארים כיתרון המרכזי, וזה גם המחיר: מה שלא עבר, לא קיים. ההחלטה מה עובר היא החלטת עיצוב." },
      { t: "המחיר", b: "agents צורכים בערך פי 4 טוקנים מצ'אט, ומערכות multi-agent בערך פי 15 (Anthropic). כל agent משלם מחדש על פרומפט וכלים, התיאום עולה קריאות נוספות, ושגיאות מצטברות בכפל לאורך שרשרת. האצלה חוזרת מריצה שוב גם תופעות לוואי." },
      { t: "הערכה", b: "המדד הראשי הוא מקצה לקצה, מול אותו זהב של agent יחיד. ייחוס לכל agent עונה איפה הכסף הולך ומי גרם לכשל: router, worker, או חיבור שהשמיט עובדה. בדיקות בקוד עדיפות על לבקש ממודל לשים לב." },
      { t: "הכלל", b: "מתחילים עם agent אחד ו-eval. מפצלים רק כשמדידה מראה כשל שפיצול פותר, למשל יותר מדי כלים או הקשר מזוהם. בוחרים את הדפוס הזול שפותר אותו, ומודדים שוב. כתיבות נשארות אצל agent אחד." },
    ],
    glossary: [
      ["Multi-agent system", "כמה לולאות agent עם פרומפט, כלים והקשר נפרדים, ומנגנון שמעביר עבודה ביניהן."],
      ["Router", "סיווג אחד של הבקשה, ושליחה בקוד למומחה מתאים. ההחלטה מתקבלת פעם אחת, מראש."],
      ["Supervisor (orchestrator-workers)", "agent שמאציל חלקי עבודה ל-workers דרך כלים, ומחבר את התשובות שלהם."],
      ["Worker / subagent", "agent שמבצע חלק מהעבודה בהקשר נקי, ומחזיר רק את התשובה שלו."],
      ["Handoff", "העברת שליטה מ-agent ל-agent, יחד עם הקשר. ה-agent האחרון בשרשרת עונה למשתמש."],
      ["Agent as tool", "מומחה שנקרא ככלי. התשובה חוזרת למי שקרא, והוא נשאר בשליטה."],
      ["Context isolation", "כל agent רואה רק מה שהועבר אליו במפורש. זה היתרון המרכזי, וגם הסיכון."],
      ["Fan-out / map-reduce", "פיצול לחלקים בלתי תלויים שרצים במקביל, ואיחוד התוצאות."],
      ["Voting", "הרצה של אותה משימה כמה פעמים, ובחירה לפי רוב. משלמים פי k קריאות."],
      ["Evaluator-optimizer", "כותב ומבקר בלולאה מול rubric, עם תקרת סבבים."],
      ["Coordination cost", "טוקנים, קריאות וזמן שהולכים על תיאום ולא על עבודה בתחום: פרומפטים, משימות, תשובות וחיבור."],
      ["Error compounding", "בשרשרת של agents תלויים, הסיכויים להצלחה מוכפלים, והסיכוי הכולל יורד מהר."],
      ["Per-agent attribution", "פירוק העלות, הזמן והכשלים לפי agent, מעל trajectories מקושרים (parent_run_id)."],
      ["Shared state", "אובייקט שכל ה-agents קוראים וכותבים אליו (למשל state ב-LangGraph). החלופה היא העברת הודעות."],
      ["A2A (Agent2Agent)", "פרוטוקול פתוח, תחת Linux Foundation, לתקשורת בין agents של מסגרות וספקים שונים. משלים את MCP."],
      ["Clarifying question", "התשובה הנכונה כשהבקשה עמומה או שה-confidence נמוך: לשאול במקום לנחש."],
    ],
    reading: [
      { title: "Anthropic: How we built our multi-agent research system", url: "https://www.anthropic.com/engineering/multi-agent-research-system", note: "חובה. פי 15 טוקנים, בידוד הקשר, כמה subagents להפעיל, הערכה." },
      { title: "Anthropic: Building effective agents", url: "https://www.anthropic.com/engineering/building-effective-agents", note: "ההגדרות של routing, parallelization, orchestrator-workers ו-evaluator-optimizer, וההמלצה להתחיל פשוט." },
      { title: "Cognition: Don't Build Multi-Agents", url: "https://cognition.ai/blog/dont-build-multi-agents", note: "share context, ופעולות שנושאות החלטות סמויות." },
      { title: "Cognition: Multi-Agents: What's Actually Working", url: "https://cognition.com/blog/multi-agents-working", note: "אפריל 2026: כתיבה אצל agent אחד, review loop, ו-Smart Friend." },
      { title: "Why Do Multi-Agent LLM Systems Fail? (Cemri et al.)", url: "https://arxiv.org/abs/2503.13657", note: "MAST: 14 סוגי כשל בשלוש קטגוריות, בשבע מסגרות." },
      { title: "Claude Agent SDK: Subagents", url: "https://code.claude.com/docs/en/agent-sdk/subagents", note: "מה subagent יורש ומה לא, והגבלות על עומק, מקביליות ותקציב." },
      { title: "OpenAI Agents SDK: Handoffs", url: "https://openai.github.io/openai-agents-python/handoffs/", note: "transfer_to_ ושם ה-agent, input_filter ו-nest_handoff_history." },
      { title: "LangChain: Multi-agent", url: "https://docs.langchain.com/oss/python/langchain/multi-agent", note: "subagents, handoffs, skills ו-router, עם השוואת קריאות וטוקנים." },
      { title: "LangChain blog: Choosing the right multi-agent architecture", url: "https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture", note: "ינואר 2026: להתחיל עם agent יחיד. שים לב: הטענה על 67% פחות טוקנים לא תואמת לטבלה שבמאמר עצמו (9K מול 15K זה בערך 40%)." },
      { title: "langgraph-supervisor", url: "https://github.com/langchain-ai/langgraph-supervisor-py", note: "create_supervisor, וההמלצה העדכנית לממש את הדפוס ישירות עם כלים." },
      { title: "A2A Protocol", url: "https://a2a-protocol.org/latest/", note: "תקשורת agent-to-agent, תחת Linux Foundation. משלים את MCP." },
      { title: "Google ADK: Workflows", url: "https://adk.dev/workflows/", note: "graph-based workflows ב-ADK 2.0, template workflows ו-collaborative workflows." },
      { title: "CrewAI: Hierarchical process", url: "https://docs.crewai.com/en/learn/hierarchical-process", note: "manager_llm או manager_agent, וההאצלה כבויה כברירת מחדל." },
    ],
  },
};
