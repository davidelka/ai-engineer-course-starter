// Lesson 20 — Design-Driven Development: components, boundaries and interfaces before implementation.
window.LESSONS = window.LESSONS || {};
window.LESSONS["20"] = {
  n: 20,
  title: "Design-Driven Development",
  he: "לתכנן רכיבים וממשקים לפני מימוש",
  hours: "כשעתיים וחצי שיעור, כחמש שעות מעבדה",

  goals: [
    "להבחין בין שלוש רמות של תכנון: <b>ארכיטקטורה</b> (שיעור 19: אילו רכיבים יש ואיך הם מחוברים), <b>מפרט</b> (שיעור 6: מה הפיצ'ר צריך לעשות), ו<b>תכנון ברמת הרכיב</b> (השיעור הזה: הממשקים, הגבולות והחוזים בתוך רכיב אחד).",
    "להחיל <b>ports and adapters</b> (ארכיטקטורה משושה) על מערכת LLM: המודל, ה-retriever, ה-store, הכלים והשעון הם ports, ו-llmkit הוא דוגמה ל-adapter.",
    "להגדיר ממשקים כ-<b>typing.Protocol</b> שמדברים רק ב<b>טיפוסי דומיין</b> של Pydantic, ולדעת מתי עדיף ABC.",
    "לתכנן <b>חוזה שגיאות</b> לכל port: מה זמני ומה קבוע, מי מתרגם, ושכבה אחת בלבד שאחראית על retries.",
    "להשתמש ב-<b>dependency injection</b> דרך הבנאי וב-<b>composition root</b> אחד, ולבדוק את השירות עם <b>fakes</b> בלי רשת.",
    "לכתוב <b>בדיקות חוזה</b> לשימוש חוזר שכל adapter חייב לעבור, אמיתי או מזויף, ולוודא שהן תופסות adapters שבורים.",
    "לתכנן <b>idempotency</b> ו<b>גרסאות לפרומפטים ולסכמות</b>, כולל בדיקת תאימות מצד הקוד שקורא את הפלט.",
    "לשרטט תהליך של סוכן וכלים כ-<b>sequence diagram</b> ב-Mermaid, להריץ <b>design review</b> עם צ'קליסט, ולהבין למה מסמך תכנון הופך סוכן קוד ליעיל יותר.",
  ],
  connects: "בשיעור 19 החלטת <b>אילו רכיבים</b> יש ל-Company Brain ואיך הם מחוברים. השיעור הזה נכנס <b>לתוך רכיב אחד</b>, שירות התשובות, ומתכנן את הממשקים שלו לפני שכותבים אותו. הוא מחבר כמה חוטים מהעבר: <b>llmkit</b> משיעור 2 הופך כאן ל-adapter מאחורי port, <b>הסכמות</b> משיעור 3 מקבלות גרסאות, ו<b>סוכני הקוד והמפרטים</b> משיעורים 5 ו-6 מקבלים את מה שהם הכי צריכים: ממשק מוגדר ובדיקה שאפשר להריץ. בהמשך, ב<b>נושא 22</b> ה-request_id שמסתובב בין ה-ports יהיה ה-trace id, ב<b>נושא 23</b> בדיקות החוזה יצטרפו ל-eval, וב<b>נושא 25</b> ה-gateway יהיה עוד adapter מאחורי אותו port של המודל.",

  intro: {
    animation: "l20untangle",
    animationTitle: "מפונקציה אחת סבוכה ל-ports ו-adapters",
    animationGuide: `<p><b>מה רואים כאן:</b> בצד אחד יש את הפונקציה <code>answer_question</code> מתוך <code>legacy/tangled.py</code> במעבדה, מקוצרת לשש-עשרה שורות שמייצגות את מה שהיא עושה. כל שורה צבועה לפי <b>האחריות</b> שלה: קריאה למודל, חיפוש במסמכים, שמירה ו-cache, שעון, לוג, או לוגיקה עסקית. בהתחלה הכל אפור, כי בקוד האמיתי אין שום סימן שמפריד בין האחריויות האלה. הכל שורות באותה פונקציה.</p>
<p><b>בכל צעד</b> האנימציה מזהה אחריות אחת, צובעת את השורות שלה, ומוציאה אותן החוצה: למעלה מופיע <b>ה-port</b> (הממשק שהשירות מדבר איתו), ולידו <b>ה-adapter</b> (הקוד האמיתי שמממש אותו). מתחת לאנימציה יש הסבר של הצעד: למה דווקא זה הופך ל-port, ומה זה מאפשר לבדוק שקודם לא היה אפשר.</p>
<p><b>שימו לב לשני צעדים מיוחדים:</b> מדיניות הגישה <b>לא</b> הופכת ל-port, כי היא הלוגיקה העסקית עצמה, והיא נשארת בליבה כפונקציה טהורה. והצעד האחרון מראה את התמונה המלאה: ליבה שמכירה רק ממשקים, adapters מסביב, ו-<b>composition root</b> אחד שמחבר ביניהם.</p>
<p><b>איך לעבוד איתה:</b> היא מתחילה לרוץ לבד, צעד כל כמה שניות. אפשר להשהות ולעבור צעד אחרי צעד עם החצים. מומלץ לעבור עליה פעם אחת לפני השקפים, ופעם נוספת אחרי תרגיל 1 במעבדה, כשהקוד המלא כבר מוכר לך.</p>`,
    videos: [
      {
        title: "The Clean Architecture in Python",
        who: "Brandon Rhodes, PyOhio 2014",
        part: "כל ההרצאה. החלק החשוב: להוציא את ה-I/O לשוליים, והדוגמה של פונקציה שקשה לבדוק",
        minutes: 50,
        url: "https://www.youtube.com/watch?v=DJtef410XaM",
        required: true,
        kind: "וידאו",
        why: "ההרצאה הכי ברורה שיש על הרעיון שבבסיס השיעור, ב-Python: לוגיקה טהורה באמצע, קלט ופלט בקצוות, ותלויות שמגיעות מבחוץ. היא מ-2014 ולא מזכירה LLM, אבל מודל שפה הוא בדיוק סוג ה-I/O שהיא מדברת עליו: איטי, יקר ולא דטרמיניסטי.",
      },
      {
        title: "Hexagonal Architecture",
        who: "Alistair Cockburn",
        part: "המאמר המקורי מ-2005: ה-intent, ההגדרה של port ושל adapter, וההבחנה בין צד מניע לצד מונע",
        minutes: 25,
        url: "https://alistair.cockburn.us/hexagonal-architecture/",
        required: true,
        kind: "מאמר",
        why: "המקור של המונחים port ו-adapter. המשפט המרכזי בו הוא שהאפליקציה צריכה להיות ניתנת להפעלה באותה מידה על ידי משתמשים, תוכניות ובדיקות אוטומטיות, ולרוץ בבידוד מהמכשירים ומבסיסי הנתונים. זה בדיוק מה שתעשה לשירות התשובות במעבדה.",
      },
      {
        title: "Best practices for Claude Code",
        who: "Anthropic docs",
        part: "הסעיפים Give Claude a way to verify its work, Explore first then plan then code, ו-Let Claude interview you",
        minutes: 15,
        url: "https://code.claude.com/docs/en/best-practices",
        required: true,
        kind: "תיעוד",
        why: "החיבור לשיעורים 5 ו-6. התיעוד אומר במפורש שהמפרטים המועילים ביותר הם אלה שמציינים את הקבצים והממשקים, ושבדיקה שהסוכן יכול להריץ היא ההבדל בין סשן שצריך לשבת לידו לסשן שאפשר לעזוב. ממשק מוגדר ובדיקות חוזה הם בדיוק שני הדברים האלה, ותרגיל 5 במעבדה בנוי עליהם.",
      },
      {
        title: "Standard tests (LangChain)",
        who: "LangChain docs",
        part: "איך ספק חדש יורש מחבילת בדיקות סטנדרטית, ומה ההבדל בין unit ל-integration",
        minutes: 10,
        url: "https://docs.langchain.com/oss/python/contributing/standard-tests-langchain",
        required: false,
        kind: "תיעוד",
        why: "דוגמה מהתעשייה לבדיקות חוזה: כל אינטגרציה של מודל ב-LangChain יורשת מאותה מחלקת בדיקות ומצהירה אילו יכולות היא תומכת בהן. זה אותו מבנה כמו ChatModelContract שתכתוב בתרגיל 4, בקנה מידה של מאות ספקים.",
      },
      {
        title: "Alistair in the Hexagone",
        who: "Alistair Cockburn, עם Thomas Pierrain",
        part: "החלק הראשון, כחצי שעה: למה הוא בנה את התבנית, וקוד חי",
        minutes: 30,
        url: "https://www.youtube.com/watch?v=th4AgBcrEHA",
        required: false,
        kind: "וידאו",
        why: "Cockburn עצמו מסביר את התבנית ומראה אותה בקוד. שווה למי שרוצה לשמוע את הנימוקים מהמקור, כולל מה התבנית לא אומרת (למשל, שאין שום דבר מיוחד במספר שש).",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "שלוש רמות של תכנון, והשיעור הזה הוא האמצעית",
      html: `<p class="big">לפני שכותבים קוד של מערכת AI, מחליטים דברים בשלוש רמות שונות. קל לבלבל ביניהן, כי כולן נקראות "תכנון", אבל כל אחת עונה על שאלה אחרת, ונכשלת בדרך אחרת.</p>
<ol class="ladder">
<li><b>ארכיטקטורה (שיעור 19)</b><span>אילו רכיבים יש במערכת, איך הם מתקשרים, איפה כל אחד רץ, ואיך הנתונים זורמים ביניהם. למשל: שירות תשובות, שירות אישורים, vector store מנוהל, gateway למודלים, תור. ההחלטות כאן קשות לשינוי, ומשפיעות על עלות, latency ואמינות של כל המערכת.</span></li>
<li><b>מפרט (שיעור 6)</b><span>מה פיצ'ר מסוים צריך לעשות, מבחוץ: קלטים, פלטים, מקרי קצה, וקריטריונים לקבלה. "עובד ששואל על ימי חופשה מקבל תשובה עם ציטוט, ואם אין מסמך מתאים הוא מקבל 'לא יודע'".</span></li>
<li class="danger"><b>תכנון רכיב (השיעור הזה)</b><span>איך רכיב אחד בנוי מבפנים: אילו ממשקים יש לו, מה בדיוק כל ממשק מבטיח, אילו שגיאות הוא זורק, מי קורא למי ובאיזה סדר, ואיך בודקים אותו בלי העולם החיצוני. זו הרמה שבה נקבע אם אפשר להחליף ספק מודל בשורה אחת או בשבוע עבודה.</span></li>
</ol>
<p>הסיבה שהרמה האמצעית חשובה במיוחד במערכות LLM היא שכמעט כל תלות חיצונית שלהן מתנהגת רע: המודל <b>איטי, יקר ולא דטרמיניסטי</b>, ה-vector store יכול להיות מוחלף פעמיים בשנה, והספקים משנים מחירים ומודלים כל כמה חודשים. קוד שמערבב את התלויות האלה עם הלוגיקה העסקית נהיה קשה לבדיקה, קשה להחלפה, ומסוכן לשינוי.</p>
<div class="callout"><b>מה תעשה בשיעור:</b> תיקח את שירות התשובות של Company Brain בגרסה 0, פונקציה אחת סבוכה, ותתכנן אותו מחדש ברמת הרכיב: ports, adapters, חוזי שגיאות, בדיקות חוזה, גרסאות, ודיאגרמת רצף. בסוף תמדוד מה השתנה.</div>`,
    },
    {
      kicker: "הבעיה",
      title: "פונקציה אחת שעושה הכל",
      html: `<p>זה השלד של <code>legacy/tangled.py</code> מהמעבדה. הקוד עובד, והוא נראה כמו הרבה קוד אמיתי שנכתב בשבוע הראשון של פרויקט LLM:</p>
<div class="example"><b>מתוך legacy/tangled.py, מקוצר</b><pre dir="ltr">def answer_question(question, user_email, request_id=None):
    with open(LOG_PATH, "a") as f:                       # log, with the full question
        f.write(f"{datetime.now()} {user_email} asked: {question}")
    cache = json.loads(CACHE_PATH.read_text())          # store, a global path
    if key in cache: return cache[key]
    if re.search(r"salar|payslip", question): ...       # policy
    for fname in ["hr_policies.md", ...]:               # read files on EVERY call
        text = (DATA / fname).read_text()
    scored = [...]                                      # keyword search, inline
    llm = LLM(os.environ.get("BRAIN_MODEL", ...))        # model, built right here
    try:
        r = llm.complete(prompt, system="You are...")
    except LLMError:
        return {"status": "degraded", ...}               # 401? 529? same answer
    cache[key] = {..., "created_at": datetime.now()}    # clock, hidden
    CACHE_PATH.write_text(json.dumps(cache))</pre></div>
<h4>למה זה כואב, בדיוק</h4>
<ul>
<li><b>אי אפשר לבדוק בלי העולם.</b> כדי לבדוק את הפונקציה צריך שרת HTTP מדומה, ארבעה monkeypatch על משתנים פנימיים (כולל משתנה פנימי של llmkit), ותיקייה זמנית. הבדיקה של "המודל נפל" אמיתית: llmkit באמת ממתין בין הניסיונות, ואין דרך להעביר לו מדיניות אחרת. במדידה שלנו הבדיקה הזו לבדה לקחה בין 1.9 ל-2.8 שניות.</li>
<li><b>אי אפשר להבחין בין כשלים.</b> <code>except LLMError</code> תופס הכל. מפתח API שגוי (401) נראה למשתמש בדיוק כמו עומס זמני (529): "השירות לא זמין כרגע". באג קונפיגורציה מסתתר כתקלה זמנית, לפעמים במשך ימים.</li>
<li><b>אי אפשר לבדוק מה שתלוי בזמן.</b> <code>datetime.now()</code> בתוך הפונקציה אומר שאין דרך לבדוק את <code>created_at</code>, או תפוגה של cache, בלי לשחק עם השעון של המערכת.</li>
<li><b>החלפה נוגעת בהכל.</b> מעבר מחיפוש מילות מפתח ל-vector store, או מ-Anthropic ל-gateway, הוא שינוי בתוך הפונקציה שמכילה גם את המדיניות וגם את השמירה. כל שינוי כזה הוא סיכון לשבור משהו שלא קשור.</li>
<li><b>סדר שגוי שאף אחד לא רואה.</b> השאלה נכתבת ללוג, כולל המייל, <b>לפני</b> בדיקת המדיניות. ותשובה מה-cache חוזרת לפני בדיקת המדיניות, כך ששינוי מדיניות לא חל על שאלות שכבר נענו.</li>
</ul>`,
    },
    {
      kicker: "Ports and adapters",
      title: "ליבה שלא יודעת מה יש בחוץ",
      html: `<p>Alistair Cockburn תיאר את התבנית ב-2005, תחת השם <b>Hexagonal Architecture</b>. הרעיון: האפליקציה צריכה לעבוד באותה מידה כשמפעילים אותה משתמשים, תוכניות אחרות או בדיקות אוטומטיות, ולרוץ בבידוד מבסיסי הנתונים ומהשירותים החיצוניים שלה. כדי שזה יקרה, מחלקים את הקוד לשלושה סוגים:</p>
<ul>
<li><b>הליבה (core).</b> הלוגיקה העסקית והסדר של הפעולות. בשירות התשובות: לבדוק מדיניות, לחפש, להחליט אם יש מספיק הקשר, לבקש תשובה, לסנן ציטוטים, לשמור. הליבה <b>לא מייבאת</b> שום ספרייה של ספק, שום HTTP client, ושום driver של בסיס נתונים.</li>
<li><b>Port.</b> ממשק שהליבה מגדירה, <b>בשפה שלה</b>: "תן לי עד k קטעים רלוונטיים לשאלה הזו". ה-port שייך לליבה, לא לספק. זה ההבדל המהותי: לא עוטפים את ה-API של Pinecone, אלא מגדירים מה הליבה צריכה, ואז מישהו מתאים את Pinecone לזה.</li>
<li><b>Adapter.</b> הקוד שמממש port מול טכנולוגיה אחת: <code>LlmkitChatModel</code>, <code>KeywordRetriever</code>, <code>JsonlAnswerStore</code>. ה-adapter מתרגם: טיפוסי הליבה נכנסים, קריאה לספק יוצאת, וטיפוסי הליבה (והשגיאות שלה) חוזרים.</li>
</ul>
<h4>שני צדדים</h4>
<p>יש ports <b>מניעים</b> (driving), שדרכם העולם מפעיל את הליבה: endpoint של HTTP, בוט ב-Slack, שורת פקודה, וגם הבדיקות שלך. ויש ports <b>מונעים</b> (driven), שדרכם הליבה מפעילה את העולם: המודל, ה-retriever, ה-store, הכלים והשעון. רוב השיעור עוסק בצד המונע, כי שם נמצאות כל התלויות הבעייתיות של מערכת LLM.</p>
<div class="example"><b>שירות התשובות של Company Brain, בתמונה אחת</b><pre dir="ltr">  driving side                core                     driven side
  ------------         ------------------         -----------------------------
  HTTP API   ---->    |                  | ---->  ChatModel   <- LlmkitChatModel / Fake
  Slack bot  ---->    |  AnswerService   | ---->  Retriever   <- KeywordRetriever / pgvector / Fake
  tests      ---->    |  + domain rules  | ---->  AnswerStore <- JsonlAnswerStore / SQLite / Fake
                      |                  | ---->  Clock       <- SystemClock / FixedClock</pre></div>
<p>אין שום דבר מיוחד במספר שש. Cockburn בחר משושה כדי שיהיה מקום לצייר כמה ports בלי שהציור ייראה כמו שכבות. מה שחשוב הוא הכיוון: <b>התלויות מצביעות פנימה</b>. ה-adapter מכיר את ה-port, וה-port לא מכיר אף adapter.</p>`,
    },
    {
      kicker: "גבולות",
      title: "מה הופך משהו ל-port, ומה נשאר בפנים",
      html: `<p>הטעות הנפוצה אחרי שמכירים את התבנית היא להפוך הכל ל-port. ממשק לכל פונקציה, adapter לכל מחלקה, ושלוש שכבות של הפניות כדי לחשב סכום. זה מייקר כל שינוי, ולא מוסיף כלום. השאלה הנכונה היא: <b>מה בתלות הזו מקשה עליי?</b></p>
<h4>סימנים שמשהו צריך להיות port</h4>
<ul>
<li><b>הוא איטי או יקר.</b> קריאה למודל לוקחת שניות ועולה כסף. בבדיקה שרצה מאה פעמים ביום, זה ההבדל בין שנייה לעשר דקות.</li>
<li><b>הוא לא דטרמיניסטי.</b> אותו פרומפט מחזיר תשובות שונות, אז אי אפשר לכתוב עליו assert מדויק. השעון והמזהים האקראיים באותה קטגוריה.</li>
<li><b>הוא חיצוני, ויכול ליפול.</b> רשת, ספק, בסיס נתונים. את המקרים המעניינים (timeout, 429, סירוב) צריך לייצר לפי דרישה בבדיקות.</li>
<li><b>סביר שיוחלף.</b> מודלים מתחלפים כל כמה חודשים, ו-vector stores כל שנה. אם אתה יודע כבר עכשיו שתעבור מחיפוש מילות מפתח לחיפוש וקטורי ברבעון הבא, הגבול הזה שווה ממשק.</li>
</ul>
<h4>מה לא צריך להיות port</h4>
<ul>
<li><b>הלוגיקה העסקית.</b> <code>policy_check</code> בודק אם שאלה עוסקת בשכר או בסיסמאות. זה מהיר, דטרמיניסטי, ושלנו. הוא נשאר פונקציה טהורה ב-<code>domain.py</code>, ונבדק ישירות. אם יום אחד המדיניות תעבור למנוע חיצוני (למשל OPA), אז ורק אז היא תהפוך ל-port.</li>
<li><b>ספריות טהורות.</b> Pydantic, <code>re</code>, <code>json</code>. אין שום סיבה לעטוף אותן.</li>
<li><b>דברים שיש מהם מימוש אחד ואין סיבה לבדוק בלעדיהם.</b> ממשק עם מימוש אחד ובלי fake הוא בדרך כלל סתם עקיפה.</li>
</ul>
<div class="callout"><b>port לכל תפקיד, לא לכל ספק.</b> יש port אחד בשם ChatModel, ושלושה adapters (Anthropic, OpenAI, fake). לא <code>AnthropicPort</code> ו-<code>OpenAIPort</code>. אם השם של ה-port מכיל שם של ספק, הוא לא באמת port.</div>`,
    },
    {
      kicker: "Protocol",
      title: "ממשקים ב-Python: Protocol או ABC",
      html: `<p>ב-Python יש שתי דרכים להגדיר ממשק. ההבדל ביניהן הוא לא רק תחבירי, הוא קובע מי צריך להכיר את מי.</p>
<div class="example"><b>מתוך designkit/ports.py</b><pre dir="ltr">from typing import Protocol, runtime_checkable

@runtime_checkable
class Retriever(Protocol):
    def search(self, query: str, k: int = 4) -> list[Passage]:
        """At most k passages, highest score first, unique doc_ids.
        No match returns [], it does not raise. Same query, same result.
        Raises RetrieverUnavailable when the backend is down."""
        ...

class KeywordRetriever:            # no inheritance at all
    def search(self, query: str, k: int = 4) -> list[Passage]: ...

r: Retriever = KeywordRetriever()  # OK for mypy/pyright: the shape matches</pre></div>
<h4>Protocol: טיפוסיות מבנית</h4>
<p><code>typing.Protocol</code> (מאז Python 3.8, PEP 544) אומר: כל אובייקט שיש לו את המתודות האלה, עם החתימות האלה, נחשב מימוש. ה-adapter <b>לא יורש</b> מכלום ולא מייבא את ה-port. זה מתאים בדיוק לכיוון של ports and adapters: אפשר לכתוב adapter בחבילה נפרדת, ואפילו להשתמש במחלקה קיימת של ספריה חיצונית אם הצורה שלה מתאימה.</p>
<p>שני דברים חשוב לדעת. ראשית, הבדיקה העיקרית היא <b>סטטית</b>: mypy או pyright בודקים שהחתימות תואמות. שנית, <code>@runtime_checkable</code> מאפשר <code>isinstance(x, Retriever)</code>, אבל הבדיקה הזו רק מוודאת <b>שהמתודות קיימות</b>. היא לא בודקת חתימות, טיפוסים או התנהגות. לכן היא טובה לבדיקה מהירה בבדיקות, ולא כהגנה.</p>
<h4>ABC: טיפוסיות נומינלית</h4>
<p><code>abc.ABC</code> עם <code>@abstractmethod</code> מחייב ירושה מפורשת, וזורק שגיאה ביצירת מחלקה שלא מימשה הכל. הוא עדיף כשרוצים <b>לשתף קוד</b> בין המימושים (מתודה משותפת במחלקת הבסיס), או כשרוצים שגיאה מיידית בזמן ריצה. החיסרון: כל adapter חייב לייבא את מחלקת הבסיס, כלומר תלות בכיוון ההפוך.</p>
<div class="callout"><b>מה שהחתימה לא אומרת:</b> "לכל היותר k", "ממוין", "רשימה ריקה ולא חריגה", "אותה שאלה, אותה תשובה". אף type checker לא יבדוק את אלה. לכן ה-docstring של port הוא חלק מהחוזה, ולכן צריך בדיקות חוזה. נגיע אליהן.</div>`,
    },
    {
      kicker: "טיפוסי דומיין",
      title: "מה עובר דרך port: רק טיפוסים של הליבה",
      html: `<p>port שמחזיר אובייקט של ספק הוא לא port. אם <code>ChatModel.complete()</code> מחזיר <code>anthropic.types.Message</code>, והשירות קורא <code>message.content[0].text</code>, אז החלפה ל-OpenAI מחייבת לשנות את השירות, וכל fake צריך לחקות את ה-SDK של Anthropic. ההפרדה קיימת על הנייר בלבד.</p>
<div class="example"><b>מתוך designkit/types.py</b><pre dir="ltr">class Completion(BaseModel):
    text: str
    model: str            # "anthropic:claude-haiku-5-5"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)
    doc_id: str           # what the answer cites
    title: str
    text: str
    score: float = 0.0</pre></div>
<p>שלושה עקרונות לטיפוסים שעוברים בגבול:</p>
<ul>
<li><b>מה שהליבה צריכה, לא מה שהספק מחזיר.</b> Anthropic מחזיר עשרות שדות. הליבה צריכה טקסט, שם מודל, טוקנים ועלות. אם יום אחד תצטרך <code>stop_reason</code>, מוסיפים שדה <b>מנורמל</b> (כמו ש-llmkit עושה), לא את הערך הגולמי.</li>
<li><b>מודלים של Pydantic, לא dict.</b> <code>list[dict]</code> בגבול אומר שכל צד מנחש את המפתחות. מודל Pydantic נותן ולידציה, השוואה (<code>==</code> עובד בבדיקות), סריאליזציה ל-JSON בשביל ה-store, ותיעוד. <code>frozen=True</code> על <code>Passage</code> מונע מהשירות לשנות בטעות קטע שה-retriever החזיר.</li>
<li><b>הטיפוס מכיל את השפה של הדומיין.</b> <code>doc_id</code> ולא <code>pinecone_id</code>. <code>score</code> ולא <code>distance</code>. אם ה-vector store מחזיר מרחק (קטן יותר זה טוב יותר), ה-adapter הופך אותו לציון (גדול יותר זה טוב יותר). אחרת הליבה צריכה לדעת איזה מנוע יושב מאחורה.</li>
</ul>
<p>זה אותו רעיון כמו בשיעור 3, רק בכיוון אחר. שם Pydantic הגדיר את הגבול בין המודל לקוד. כאן הוא מגדיר את הגבול בין הליבה לכל adapter.</p>`,
    },
    {
      kicker: "חוזה שגיאות",
      title: "שגיאות הן חלק מהממשק",
      html: `<p>חתימה של פונקציה מתארת מה קורה כשהכל עובד. במערכות LLM, החלק המעניין הוא מה קורה כשלא. לכן כל port מגדיר <b>אילו שגיאות</b> הוא זורק, ומה כל אחת אומרת למי שקורא לו.</p>
<div class="example"><b>מתוך designkit/types.py ו-adapters.py</b><pre dir="ltr">class ModelUnavailable(BrainError):   # transient: 429, 5xx, 529, timeout
    retryable = True                    # (after the adapter's own retries)

class ModelRejected(BrainError):      # permanent: 400, 401, refusal
    retryable = False                   # the same request fails again

class LlmkitChatModel:
    def complete(self, system, prompt, *, max_tokens=512):
        try:
            r = self.llm.complete(prompt, system=system, max_tokens=max_tokens)
        except LLMError as exc:
            if classify_error(exc).retry:              # lesson 2's rule
                raise ModelUnavailable(str(exc)) from exc
            raise ModelRejected(str(exc)) from exc
        if r.stop_reason == "refusal":
            raise ModelRejected("the model refused")</pre></div>
<h4>שלושה כללים</h4>
<ul>
<li><b>ה-adapter מתרגם, תמיד.</b> שום <code>LLMError</code>, <code>httpx.TimeoutException</code> או <code>sqlite3.Error</code> לא יוצא מ-adapter. אחרת הליבה צריכה לייבא את השגיאות של כל ספק, וההחלפה שוב לא באמת החלפה. <code>from exc</code> שומר את השגיאה המקורית ב-<code>__cause__</code>, כך שה-traceback והלוג עדיין מראים מה קרה.</li>
<li><b>שכבה אחת אחראית על retries.</b> כאן זו llmkit, בתוך ה-adapter. אם גם ה-SDK מנסה שוב פעמיים וגם השירות מנסה שוב שלוש פעמים, תקלה אחת אצל הספק הופכת ל-3 כפול 4, כלומר עד 12 קריאות לשאלה, בדיוק ברגע שהספק עמוס. זה נקרא retry storm, והוא אחד הפגמים במסמך שתבדוק בתרגיל 8.</li>
<li><b>הליבה מחליטה מה לעשות עם כל סוג.</b> <code>ModelUnavailable</code> הופך לתשובה במצב <code>degraded</code>: רשימת המסמכים הרלוונטיים, בלי תשובה מנוסחת, ו<b>בלי לשמור</b>, כדי שניסיון חוזר יוכל להצליח. <code>ModelRejected</code> לא נתפס: זה באג או בעיית קונפיגורציה, והוא צריך ליפול בקול, להגיע ללוג ולהתראה.</li>
</ul>
<div class="callout">בגרסה הסבוכה, מפתח API שפג תוקפו היה מחזיר לכל העובדים "השירות לא זמין זמנית". עם חוזה שגיאות, הוא מחזיר 500 עם התראה בדקה הראשונה. ההבדל הוא לא בקוד של הטיפול בשגיאה, הוא ב<b>תכנון</b> של איזה מידע עובר בגבול.</div>`,
    },
    {
      kicker: "Dependency injection",
      title: "התלויות מגיעות מבחוץ, ומתחברות במקום אחד",
      html: `<p>Dependency injection נשמע כמו framework. ב-Python הוא בדרך כלל פשוט: <b>הבנאי מקבל את התלויות</b>, במקום ליצור אותן.</p>
<div class="example"><b>לפני ואחרי</b><pre dir="ltr"># before: the function builds its own dependencies
def answer_question(question, user_email, request_id=None):
    llm = LLM(os.environ.get("BRAIN_MODEL", "anthropic:claude-haiku-5-5"))
    ...

# after: the service receives them
class AnswerService:
    def __init__(self, model: ChatModel, retriever: Retriever,
                 store: AnswerStore, clock: Clock, *, prompt=ANSWER_PROMPT_V1):
        self.model, self.retriever, self.store, self.clock = model, retriever, store, clock</pre></div>
<h4>ה-composition root</h4>
<p>מישהו עדיין צריך ליצור את ה-adapters האמיתיים. המקום הזה נקרא <b>composition root</b>, והכלל הוא שיש <b>אחד</b>, בקצה של התוכנית: ה-main, ה-factory של האפליקציה ב-FastAPI, או במעבדה <code>answer_demo.py</code>. זה הקובץ היחיד שמייבא גם את llmkit וגם את ה-store וגם את השירות:</p>
<div class="example"><b>מתוך answer_demo.py</b><pre dir="ltr">model = FakeChatModel() if spec == "fake" else LlmkitChatModel(LLM(spec))
store = JsonlAnswerStore(path) if kind == "jsonl" else InMemoryAnswerStore()
svc = AnswerService(model, KeywordRetriever.from_files(), store, SystemClock())</pre></div>
<h4>שלוש מלכודות</h4>
<ul>
<li><b>ברירת מחדל שיוצרת תלות.</b> <code>def __init__(self, model=LlmkitChatModel(LLM("anthropic:...")))</code> נראה נוח, אבל הערך נוצר <b>פעם אחת, בזמן הייבוא</b>, ובודק מפתח API כשמישהו רק מייבא את המודול. ברירות מחדל כאלה שייכות ל-composition root.</li>
<li><b>Service locator.</b> פונקציה גלובלית <code>get_model()</code> שהשירות קורא לה מבפנים היא monkeypatch בתחפושת: התלות עדיין נסתרת, רק במקום אחר.</li>
<li><b>Container כבד בלי צורך.</b> ספריות כמו dependency-injector קיימות, ובמערכות גדולות הן מועילות. לשירות עם ארבע תלויות, בנאי ופונקציה אחת שמחברת הם כל מה שצריך.</li>
</ul>
<p>שים לב גם ל-<code>prompt</code>: גם הפרומפט מוזרק. זה מה שמאפשר להריץ את אותו שירות עם גרסה אחרת של הפרומפט בבדיקה, או ב-shadow mode, בלי לגעת בקוד.</p>`,
    },
    {
      kicker: "Fakes",
      title: "Fake, stub ו-mock: למה fakes ל-ports",
      html: `<p>יש כמה סוגים של "אובייקט מזויף" בבדיקות, ו-Martin Fowler ו-Gerard Meszaros נתנו להם שמות. ההבדל משנה מה הבדיקה שלך באמת בודקת.</p>
<ul>
<li><b>Stub</b> מחזיר תשובה קבועה, ותו לא. "כל קריאה ל-complete מחזירה 'שלום'".</li>
<li><b>Mock</b> מתעד קריאות, והבדיקה בודקת <b>אילו קריאות</b> נעשו ובאיזה סדר: <code>mock.complete.assert_called_once_with(...)</code>. זו בדיקת אינטראקציה.</li>
<li><b>Fake</b> הוא מימוש עובד ופשוט של אותו ממשק: dict במקום בסיס נתונים, רשימה בזיכרון במקום vector store. הוא <b>שומר את אותן הבטחות</b> כמו המימוש האמיתי, והבדיקה בודקת את <b>התוצאה</b>: מה נשמר, מה הוחזר.</li>
</ul>
<div class="example"><b>מתוך designkit/fakes.py</b><pre dir="ltr">class InMemoryAnswerStore:
    def __init__(self):
        self.data: dict[str, Answer] = {}
    def get(self, request_id):
        return self.data.get(request_id)
    def put(self, answer):
        if answer.request_id in self.data:
            return False                 # first write wins, like the real one
        self.data[answer.request_id] = answer
        return True</pre></div>
<h4>למה fakes עדיפים כאן</h4>
<p>בדיקה עם mocks יודעת <b>איך</b> השירות עשה את העבודה. אם תשנה את השירות כך שיקרא ל-<code>get</code> פעמיים במקום פעם אחת, הבדיקה תיכשל, למרות שההתנהגות לא השתנתה. בדיקה עם fake יודעת רק <b>מה</b> יצא: התשובה נשמרה, היא זהה בקריאה השנייה, המודל לא נקרא שוב. זה מאפשר refactoring בלי לשכתב את הבדיקות.</p>
<p>ה-fakes במעבדה גם <b>מתעדים</b> קריאות (<code>model.calls</code>), אבל רק כדי לבדוק דברים שהם חלק מההתנהגות: "בשאלה על שכר, המודל לא נקרא בכלל" היא דרישה עסקית ודרישת פרטיות, לא פרט מימוש.</p>
<div class="callout"><b>הסיכון של fakes:</b> fake יכול להתרחק מהמימוש האמיתי. ה-fake מחזיר רשימה ממוינת, וה-adapter של pgvector לא. כל הבדיקות של השירות ירוקות, ובפרודקשן התשובות גרועות. התשובה לסיכון הזה היא השקף הבא.</div>`,
    },
    {
      kicker: "בדיקות חוזה",
      title: "חבילת בדיקות אחת, כל ה-adapters",
      html: `<p>בדיקת חוזה (contract test) היא חבילת בדיקות שכתובה <b>מול ה-port</b>, לא מול adapter מסוים. כל adapter, אמיתי או מזויף, יורש ממנה ומספק פונקציה אחת שיוצרת אותו. אם ה-fake וה-adapter האמיתי עוברים את אותה חבילה, יש סיבה טובה להאמין שהבדיקות של השירות עם ה-fake אומרות משהו על פרודקשן.</p>
<div class="example"><b>המבנה, מתוך designkit/contract.py ו-test_ex4_contract.py</b><pre dir="ltr">class AnswerStoreContract:              # no "Test" prefix: not collected alone
    def make_store(self):
        raise NotImplementedError
    def test_first_write_wins(self):
        s = self.make_store()
        s.put(_answer("r1", "first"))
        assert s.put(_answer("r1", "second")) is False
        assert s.get("r1").text == "first"

class TestInMemoryStore(AnswerStoreContract):
    def make_store(self): return InMemoryAnswerStore()

class TestJsonlStore(AnswerStoreContract):
    def make_store(self): return JsonlAnswerStore(tmp_dir() / "a.jsonl")

class TestSqliteStore(AnswerStoreContract):       # exercise 5: written by an agent
    def make_store(self): return SqliteAnswerStore(":memory:")</pre></div>
<h4>מה נכנס לחוזה</h4>
<ul>
<li><b>ההבטחות מה-docstring:</b> ממוין, לכל היותר k, ייחודי, דטרמיניסטי, first write wins.</li>
<li><b>חוזה השגיאות:</b> במצב "unavailable" נזרק <code>ModelUnavailable</code> ולא שום דבר אחר. ב-<code>LlmkitChatModel</code> זה נבדק מול mockllm שמחזיר 529 בכל ניסיון.</li>
<li><b>מקרי הקצה שהשירות סומך עליהם:</b> שאילתה ריקה מחזירה רשימה ריקה, לא חריגה.</li>
</ul>
<h4>איך יודעים שהחוזה חזק מספיק</h4>
<p>במעבדה, אחרי שהחוזה שלך עובר על ה-adapters התקינים, הבדיקות מריצות אותו גם מול <b>שבעה adapters שבורים בכוונה</b>: אחד שמשחרר <code>LLMError</code> החוצה, אחד שמחליף בין זמני לקבוע, store שדורס, retriever שלא ממיין. כל אחד מהם חייב להיכשל לפחות בבדיקה אחת שלך. זה רעיון של mutation testing בקטן: בדיקה שעוברת גם על קוד שבור לא בודקת כלום.</p>
<div class="callout"><b>בתעשייה:</b> LangChain עושים בדיוק את זה, בקנה מידה גדול. כל אינטגרציה של מודל יורשת מ-<code>ChatModelIntegrationTests</code> שבחבילה <code>langchain-tests</code>, ומצהירה אילו יכולות היא תומכת בהן. ובמעבדה יש גם מחלקה <code>Live</code> שמריצה את החוזה מול Claude אמיתי: זה מה שרץ בלילה ב-CI, לא בכל commit.</div>`,
    },
    {
      kicker: "החלפה",
      title: "מה באמת משתנה כשמחליפים adapter",
      html: `<p>ההבטחה של התבנית היא שהחלפת ספק היא שינוי ב-adapter וב-composition root, ולא בשום מקום אחר. ברוב המקרים זה נכון, אבל במערכות LLM יש כמה צימודים שהממשק לא מסתיר, וחשוב להכיר אותם מראש. בסימולציה "החלף את ה-adapter" תוכל לראות את זה לכל port.</p>
<h4>החלפת מודל (Haiku ל-GPT, או ל-gateway)</h4>
<p>הקוד: adapter חדש, או רק מחרוזת אחרת ל-llmkit, ושורה ב-composition root. השירות, הדומיין והבדיקות שלו לא משתנים. <b>מה שהממשק לא מסתיר:</b> הפרומפט. פרומפט שכויל על Claude לא בהכרח עובד אותו דבר על מודל אחר, ובמיוחד ההוראה לצטט <code>[doc_id]</code>. לכן החלפת מודל היא גם הזדמנות לגרסה חדשה של הפרומפט, ומריצים את ה-eval (נושא 23) לפני ואחרי.</p>
<h4>החלפת vector store (מילות מפתח ל-pgvector)</h4>
<p>הקוד: adapter חדש שעובר את <code>RetrieverContract</code>. <b>מה שהממשק לא מסתיר:</b> סקאלת הציונים. בחיפוש מילות מפתח הציון הוא שבר בין 0 ל-1. בחיפוש וקטורי זה דמיון קוסינוס, עם התפלגות אחרת לגמרי. הסף <code>min_score=0.2</code> שבשירות כויל על הסקאלה הישנה. יש שתי דרכים: לנרמל את הציון בתוך ה-adapter, או להעביר את ההחלטה "האם יש מספיק הקשר" לתוך ה-adapter. בשני המקרים זו החלטת תכנון, ועדיף לקבל אותה במודע. וגם: צריך לבנות אינדקס מחדש, וזה תהליך נפרד (נושאים 10-11).</p>
<h4>החלפת store (JSONL ל-Postgres)</h4>
<p>הקוד: adapter שעובר את <code>AnswerStoreContract</code>. <b>מה שהממשק לא מסתיר:</b> מיגרציה של הנתונים הקיימים, ו-"first write wins" שצריך להיות <b>אטומי</b> בבסיס הנתונים (primary key ו-<code>INSERT ... ON CONFLICT DO NOTHING</code>), לא בדיקה ב-Python ואז הכנסה.</p>
<div class="callout"><b>מבחן הדליפה:</b> אם החלפת adapter מחייבת לשנות את <code>service.py</code>, ה-port דולף. החתימה של <code>search(embedding, top_k, ef_search)</code> היא דוגמה: היא מניחה חיפוש וקטורי עם HNSW, והחלפה לחיפוש היברידי משנה את השירות. החתימה <code>search(query, k)</code> לא מניחה כלום.</div>`,
    },
    {
      kicker: "Idempotency",
      title: "אותה בקשה פעמיים, אותה תוצאה, תשלום אחד",
      html: `<p>בקשות חוזרות הן לא מקרה קצה, הן שגרה. ה-gateway מנסה שוב אחרי timeout, האפליקציה בטלפון מנסה שוב כשהרשת קופצת, ותור מעביר הודעה פעמיים. בשירות רגיל, בקשה כפולה עולה קצת CPU. בשירות LLM היא עולה <b>קריאה נוספת למודל</b>, ובגרוע מזה, מחזירה <b>תשובה אחרת</b> לאותה שאלה, כי המודל לא דטרמיניסטי. ובתהליך עם כלים (שלב 3 של Company Brain), היא יכולה <b>לתת גישה פעמיים</b>.</p>
<h4>ארבעה רכיבים של idempotency</h4>
<ul>
<li><b>מפתח מהלקוח.</b> הלקוח יוצר <code>request_id</code> פעם אחת, ושולח את אותו ערך בכל ניסיון חוזר. מזהה שהשרת יוצר (auto-increment) לא עוזר, כי כל ניסיון מקבל מזהה חדש. ב-HTTP זה בדרך כלל header בשם <code>Idempotency-Key</code>.</li>
<li><b>בודקים לפני שעובדים.</b> הצעד הראשון של השירות הוא <code>store.get(request_id)</code>. אם יש תשובה, מחזירים אותה, בלי חיפוש, בלי מודל, בלי עלות.</li>
<li><b>הראשון מנצח, באופן אטומי.</b> שני עובדים יכולים לקבל את אותה בקשה באותו רגע, ושניהם יעברו את ה-<code>get</code>. לכן <code>put</code> מחזיר <code>False</code> אם המפתח כבר קיים, והשירות מחזיר את מה שנשמר ראשון. במעבדה יש בדיקה שמדמה בדיוק את המרוץ הזה.</li>
<li><b>לא שומרים כישלון זמני.</b> תשובת <code>degraded</code> לא נשמרת. אם היא הייתה נשמרת, ניסיון חוזר אחרי שהספק חזר היה מקבל שוב "לא זמין", לנצח.</li>
</ul>
<div class="example"><b>מתוך designkit/service.py</b><pre dir="ltr">existing = self.store.get(req.request_id)
if existing is not None:
    return existing                       # replay: free, and the same answer
...
if self.store.put(answer):
    return answer
return self.store.get(answer.request_id)  # someone else stored it first</pre></div>
<p>אותו עיקרון עובר לכלים: כשהשירות קורא ל-<code>IdentityProvider.grant</code>, הוא מעביר את ה-<code>request_id</code> הלאה, כדי שגם הצד השני יוכל לזהות כפילות. בדיאגרמת הרצף של תרגיל 7 זה אחד הכללים.</p>`,
    },
    {
      kicker: "גרסאות",
      title: "גרסאות לפרומפטים ולסכמות",
      html: `<p>פרומפט וסכמת פלט הם ממשק לכל דבר: הקוד שלך תלוי במבנה של מה שהמודל מחזיר, והתשובות תלויות בניסוח. כששניהם נערכים "במקום", אין דרך לדעת איזה פרומפט יצר תשובה מסוימת, אין rollback, ושינוי קטן יכול לשבור את מי שקורא את הפלט.</p>
<h4>הכללים</h4>
<ul>
<li><b>גרסה סמנטית.</b> MAJOR.MINOR.PATCH. תיקון ניסוח שלא משנה מבנה הוא PATCH. שדה אופציונלי חדש הוא MINOR. שינוי שיכול לשבור את הקוד הקורא הוא MAJOR.</li>
<li><b>גרסאות לא משתנות.</b> <code>answer@1.0.1</code> הוא תמיד אותו טקסט. ב-registry של המעבדה, רישום של אותה גרסה עם תוכן אחר נכשל, ורישום זהה שוב הוא no-op. ה-fingerprint (hash של התוכן) הוא מה שבודק את זה.</li>
<li><b>הצרכן מצמיד גרסה.</b> השירות מבקש <code>answer@1</code>, כלומר הגרסה הגבוהה ביותר מסדרה 1. גרסה 2.0.0 יכולה להתפרסם בלי שהשירות יקבל אותה בהפתעה.</li>
<li><b>הגרסה נרשמת על כל פלט.</b> <code>Answer.prompt_version = "answer@1.0.0"</code>. כשתשובה שגויה מגיעה מהשטח, יודעים בדיוק איזה פרומפט יצר אותה. וכל cache צריך לכלול את ה-fingerprint במפתח, אחרת אחרי שינוי פרומפט הוא ממשיך להגיש תשובות של הגרסה הקודמת.</li>
</ul>
<h4>מה שובר את מי שקורא</h4>
<p>הבדיקה היא מצד <b>הצרכן</b>: המודל כותב את ה-JSON, והקוד שלך קורא אותו. מכאן נובעות כמה תוצאות שנראות הפוכות במבט ראשון:</p>
<ul>
<li><b>ערך enum חדש שובר.</b> הוספת <code>"partial"</code> ל-status נראית כמו הרחבה תמימה. אבל קוד שעושה <code>match status</code> עם שני מקרים לא יודע מה לעשות איתו.</li>
<li><b>שדה שהופך ל-nullable שובר.</b> <code>text.strip()</code> ייפול על <code>None</code>.</li>
<li><b>שדה חובה שהוסר, או שהפך לאופציונלי, שובר.</b> שינוי שם הוא הסרה ועוד הוספה.</li>
<li><b>שדה אופציונלי חדש לא שובר,</b> וגם צמצום של enum לא שובר: הקורא פשוט לא יפגוש ערך שהוא מכיר.</li>
</ul>
<div class="callout"><b>בתעשייה:</b> כלים לניהול פרומפטים, כמו Langfuse, עובדים עם מספרי גרסה שלא משתנים ועם <b>labels</b> שזזים: הקוד מבקש את הגרסה שמסומנת <code>production</code>, ו-rollback הוא הזזה של ה-label לגרסה קודמת. ה-registry במעבדה הוא גרסה מינימלית של אותו רעיון, עם בדיקת תאימות שהכלים האלה בדרך כלל משאירים לך.</div>`,
    },
    {
      kicker: "Sequence diagram",
      title: "לשרטט מי קורא למי, ובאיזה סדר",
      html: `<p>דיאגרמת רכיבים מראה <b>מה</b> מחובר למה. דיאגרמת רצף מראה <b>מתי</b>: מי קורא למי, באיזה סדר, מי מחכה, ומה קורה כשמשהו נכשל. בתהליכים של סוכנים וכלים, רוב הבאגים החמורים הם באגים של <b>סדר</b>: הכלי הופעל לפני בדיקת המדיניות, הלוג נכתב לפני הסינון, ה-cache נבדק לפני ההרשאה.</p>
<div class="example"><b>Mermaid, מתוך תחילת תהליך אישור הגישה</b><pre dir="ltr">sequenceDiagram
    actor Emp as Employee
    participant Svc as AccessService
    participant Store as RequestStore
    participant LLM as Classifier
    Emp->>Svc: request {text, request_id}
    Svc->>Store: get(request_id)
    Store-->>Svc: none (new request)
    Svc->>LLM: classify(text)
    alt model timeout or unavailable
        LLM-->>Svc: ModelUnavailable
        Svc->>Svc: route = needs_manager
    else ok
        LLM-->>Svc: AccessRequest {proposed route}
    end</pre></div>
<h4>איך לקרוא, ואיך לכתוב</h4>
<ul>
<li><b>חץ מלא</b> (<code>->></code>) הוא קריאה, <b>חץ מקווקו</b> (<code>-->></code>) הוא תשובה. קריאה למודל בלי חץ תשובה היא בדרך כלל סימן ששכחת לחשוב על מה חוזר, כולל שגיאות.</li>
<li><b>בלוקים</b>: <code>alt</code> ו-<code>else</code> לענפים, <code>opt</code> לצעד אופציונלי, <code>loop</code> ללולאה (למשל לולאת סוכן משיעור 15), <code>break</code> ליציאה מוקדמת. כל בלוק נסגר ב-<code>end</code>.</li>
<li><b>מה לחפש בדיאגרמה:</b> כל קריאה לכלי עם תופעת לוואי, האם יש לפניה החלטה. כל קריאה למודל, האם יש ענף לכישלון שלה. כל בקשה מבחוץ, האם יש מפתח idempotency. כל החלטה, האם היא נשמרת לביקורת.</li>
</ul>
<p>Mermaid נבחר כי הוא טקסט: הוא חי בריפו ליד הקוד, נכנס ל-diff ול-code review, GitHub מציג אותו ישירות בקובצי Markdown, וסוכן קוד יכול לקרוא ולכתוב אותו. בתרגיל 7 תשרטט את כל תהליך אישור הגישה, והבודק במעבדה מוודא עשרה כללי תכנון.</p>`,
    },
    {
      kicker: "Design review",
      title: "ביקורת תכנון: לתפוס את הבאג לפני שהוא קוד",
      html: `<p>באג שנתפס במסמך תכנון עולה פסקה. אותו באג אחרי שלושה שבועות של מימוש עולה refactoring, ואחרי עלייה לפרודקשן הוא עולה תקרית. Design review הוא התהליך שמנצל את הפער הזה: מסמך קצר, קוראים שלא כתבו אותו, וצ'קליסט שמכוון את תשומת הלב.</p>
<h4>איך עושים את זה בפועל</h4>
<ul>
<li><b>מסמך כתוב, לא שיחה.</b> הקשר ומטרה, ממשקים עם חתימות, זרימה, כשלים, בדיקות, rollout. מסמך מכריח לנסח דברים שבשיחה נשארים מעורפלים ("ונטפל בשגיאות").</li>
<li><b>מספרים בהקשר.</b> 2,000 שאלות ביום, p95 של 4 שניות. בלי מספרים אי אפשר לראות, למשל, ש-timeout של 5 שניות ב-gateway עם p95 של 4 שניות אומר שהבקשות האיטיות ירוצו פעמיים.</li>
<li><b>צ'קליסט ברמת הממשק.</b> במעבדה יש תשעה פריטים: ports שמדברים בשפת הדומיין, חוזה שגיאות, ממשקים שלא מעוצבים לפי מימוש אחד, idempotency, גרסאות, סדר השומרים, בדיקות בלי רשת, תאימות של סכמות ציבוריות, ו-observability.</li>
<li><b>כל ממצא עם תיקון.</b> "D4 לא טוב" לא עוזר לכותב. "D4: retries בשתי שכבות, עד 12 קריאות בתקלה. להשאיר retries רק ב-adapter" עוזר.</li>
<li><b>לא כל דבר חשוד הוא פגם.</b> במסמך של תרגיל 8 יש סעיפים שנראים חשודים ותקינים לגמרי. ביקורת שמסמנת הכל מבזבזת את הזמן של הכותב, ומלמדת אותו להתעלם מביקורות.</li>
</ul>
<p>Google מתארים מסמכי תכנון כמקום שבו נרשמים <b>ה-trade-offs</b>, לא רק הפתרון: אילו חלופות נשקלו ולמה נדחו. בשביל ביקורת, זה החלק החשוב ביותר, כי שם רואים אם הכותב הבין את הבעיה.</p>
<div class="callout">בסימולציה "מצא את הפגם" יש מסמך קצר אחר, על adapter של הכלי שנותן גישה. כדאי לעשות אותה לפני תרגיל 8, כדי להתרגל לקרוא עם הצ'קליסט.</div>`,
    },
    {
      kicker: "סוכני קוד",
      title: "למה מסמך תכנון הופך סוכן קוד ליעיל יותר",
      html: `<p>בשיעורים 5 ו-6 ראית שסוכן קוד עובד הכי טוב עם הקשר ממוקד ועם דרך לבדוק את עצמו. התכנון של השיעור הזה מספק את שניהם, כמעט כתוצר לוואי.</p>
<ul>
<li><b>הקשר קטן ומדויק.</b> כדי לממש <code>SqliteAnswerStore</code>, הסוכן צריך לקרוא שלושה דברים: הטיפוס <code>Answer</code>, ה-port <code>AnswerStore</code> עם ה-docstring שלו, ו-adapter קיים לדוגמה. הוא לא צריך להבין את המדיניות, את החיפוש או את הפרומפט. בפונקציה הסבוכה, כל שינוי מחייב לקרוא את כל 140 השורות, וכל שינוי יכול לשבור כל דבר.</li>
<li><b>בדיקה שהוא יכול להריץ.</b> התיעוד של Claude Code אומר זאת במפורש: לתת לסוכן בדיקה שהוא יכול להריץ, כמו חבילת בדיקות או build, זה ההבדל בין סשן שצריך לשבת לידו לבין סשן שאפשר לעזוב. בדיקות החוזה הן בדיוק זה: "גמרת" מוגדר כ-"<code>pytest test_ex5_agent_adapter.py</code> עובר".</li>
<li><b>גבולות ברורים למה אסור לגעת.</b> המשימה בתרגיל 5 אומרת: לא לשנות את <code>mine.py</code>, את <code>designkit</code> או את הבדיקות. בלי ports, ההוראה הזו לא הייתה אפשרית, כי כל שינוי היה צריך לגעת בפונקציה המרכזית.</li>
</ul>
<div class="example"><b>מתוך designs/adapter_task.md</b><pre dir="ltr">## Done when
    python -m pytest -q labs/20-design-driven/tests/test_ex5_agent_adapter.py
passes, and you have shown the test output.
If a test fails, fix the adapter, not the test.</pre></div>
<p>התיעוד מוסיף שהמפרטים המועילים ביותר הם עצמאיים: הם <b>מציינים את הקבצים והממשקים</b>, אומרים מה מחוץ לתחום, ומסתיימים בצעד אימות. זה ההבדל בין מפרט (שיעור 6) לתכנון רכיב: המפרט אומר <b>מה</b>, ומסמך התכנון נותן לסוכן את <b>הצורה</b> שאליה הוא צריך להתאים. בפרויקט אמיתי, את הצורה הזו שמים ב-<code>docs/design/</code> ומפנים אליה מ-CLAUDE.md במשפט אחד, כדי שלא תיטען לכל סשן.</p>`,
    },
    {
      kicker: "מדידה",
      title: "מה המדידה מראה, ומה היא לא מראה",
      html: `<p>בתרגילים 1 ו-3 מריצים <code>measure.py</code>, שמריץ את אותם תרחישים לפני ואחרי, תחת coverage.py עם מדידת branches. אלה המספרים שקיבלנו בשתי הרצות בסביבת הבנייה של המעבדה (Python 3.13, coverage 7.17). אצלך המספרים יהיו קצת אחרים, וזה בסדר:</p>
<ul>
<li><b>לפני:</b> 6 בדיקות, בין 2.7 ל-3.6 שניות של pytest. הבדיקה "המודל נפל" לבדה: בין 1.9 ל-2.8 שניות, כי llmkit באמת ממתין עם backoff ואין דרך להזריק מדיניות אחרת. עוד חצי שנייה בכיבוי שרת ה-HTTP המדומה. כיסוי של <code>answer_question</code>: <b>94% מהשורות ו-93% מה-branches</b>.</li>
<li><b>אחרי:</b> 12 בדיקות, בין 0.22 ל-0.38 שניות. אף בדיקה לא חצתה 0.05 שניות. כיסוי של <code>AnswerService</code>: <b>100% מהשורות ומה-branches</b>.</li>
</ul>
<h4>הקריאה הכנה של המספרים</h4>
<p>אחוזי הכיסוי <b>לפני</b> היו גבוהים כבר. מי שמסתכל רק על coverage יגיד שלא היה צורך בפירוק. אבל הכיסוי מודד אילו שורות <b>רצו</b>, לא מה <b>נבדק</b>. הקוד הסבוך הריץ את השורה של <code>created_at</code> בכל בדיקה, ואף בדיקה לא יכלה לבדוק את הערך שלה. הוא הריץ את <code>except LLMError</code>, ואף בדיקה לא יכלה לבדוק ש-401 מטופל אחרת מ-529, כי הוא <b>לא</b> מטופל אחרת. שש הבדיקות החדשות שמסומנות NEW בודקות דברים שלא היה אפשר לבטא קודם.</p>
<p>והמהירות: פער של פי עשר בזמן הבדיקות נראה קטן כשמדובר בשלוש שניות. אבל הבדיקה האיטית היא זו שבודקת התנהגות בכשל. עם כל port נוסף שנופל (ה-retriever, הכלי), מוסיפים עוד בדיקות כאלה, וכל אחת מוסיפה שניות. זה מה שגורם לצוותים להפסיק להריץ בדיקות לפני commit.</p>
<div class="callout"><b>על coverage.py:</b> הגרסה הנוכחית היא 7.17 (אוקטובר 2026). מגרסה 7.9.1, על Python 3.14 ומעלה ה-core ברירת המחדל הוא sysmon, שמבוסס על sys.monitoring ומהיר יותר. על Python 3.12 ו-3.13 sysmon לא תומך במדידת branches, ולכן עם <code>--branch</code> coverage משתמש ב-ctrace, ה-core הוותיק. אצלך, על 3.12, זה מה שירוץ, ואין צורך לשנות כלום. <code>pytest --cov</code> של pytest-cov עוטף את אותו מנוע.</div>`,
    },
    {
      kicker: "סיכום",
      title: "מתי כן, מתי לא, ומה לקחת הלאה",
      html: `<p>התבנית של השיעור עולה משהו: יותר קבצים, יותר שמות, ועוד שכבה שצריך לעבור כדי להבין מה קורה. השאלה היא תמיד אם המחיר הזה קונה משהו.</p>
<h4>כדאי כש...</h4>
<ul>
<li>יש תלות <b>איטית, יקרה או לא דטרמיניסטית</b>, וצריך לבדוק את הלוגיקה שסביבה הרבה פעמים ביום. כל מערכת LLM עונה על זה.</li>
<li>יש <b>סיבה קונקרטית</b> לצפות להחלפה: מעבר מתוכנן ל-vector store, gateway שנכנס בנושא 25, ספק שני לגיבוי.</li>
<li>כמה אנשים, או סוכנים, עובדים על אותו רכיב, וצריך גבולות ברורים כדי שהעבודה לא תתנגש.</li>
</ul>
<h4>לא כדאי כש...</h4>
<ul>
<li>זה סקריפט חד-פעמי, notebook של ניסוי, או אב-טיפוס שייזרק בעוד שבוע. שם הפונקציה הסבוכה היא בחירה סבירה.</li>
<li>הממשק מומצא "למקרה ש". port בלי fake ובלי מימוש שני הוא עקיפה בלי תמורה. אפשר להוסיף אותו כשהצורך מגיע, וה-refactoring של תרגיל 3 מראה שזה לא קשה כשיש בדיקות.</li>
</ul>
<h4>מה לקחת הלאה</h4>
<p>מכאן והלאה, כל רכיב חדש ב-Company Brain מתחיל בשלושה קבצים לפני שורת מימוש אחת: <b>ports עם docstrings</b> שמתארים הבטחות ושגיאות, <b>fakes</b>, ו<b>חבילת חוזה</b>. בנושא 22 ה-<code>request_id</code> שעובר בין ה-ports יהפוך ל-trace. בנושא 23 בדיקות החוזה החיות יצטרפו ל-eval הלילי. בנושא 24 שומר האבטחה יהיה עוד שלב בליבה שרץ לפני כל port. ובנושא 25 ה-gateway יהיה עוד adapter של ChatModel, בלי לגעת בשירות.</p>`,
    },
  ],

  sims: [
    {
      id: "l20swap",
      title: "החלף את ה-adapter",
      lead: "הליבה של שירות התשובות, עם ארבעת ה-ports שלה. בוחרים adapter אחר לכל port, ורואים אילו קבצים משתנים, אילו לא, אילו בדיקות צריך להריץ, ומה הממשק לא מסתיר. מתג 'ports דולפים' מראה מה קורה לאותן החלפות כשהממשקים מעוצבים לפי ספק.",
      tasks: [
        "החלף את <b>ChatModel</b> מ-Claude ל-GPT. אילו קבצים משתנים? ומה הדבר שלא משתנה בקוד אבל בכל זאת צריך לבדוק מחדש?",
        "החלף את <b>Retriever</b> ל-pgvector. למה הסף <code>min_score</code> מופיע ברשימת האזהרות, ואיפה הוא צריך לגור?",
        "הפעל את <b>ports דולפים</b> וחזור על שתי ההחלפות. כמה קבצים משתנים עכשיו, ולמה <code>service.py</code> ובדיקות השירות נכנסו לרשימה?",
      ],
    },
    {
      id: "l20errors",
      title: "מסלול של שגיאה",
      lead: "בוחרים מה קרה אצל ספק המודל (429, 529, timeout, 401, 400, סירוב), ורואים את הדרך שהשגיאה עוברת: retries בתוך llmkit, התרגום ב-adapter, ההחלטה של השירות, ומה המשתמש מקבל. בצד מוצגת אותה שגיאה בקוד הסבוך, לשם השוואה.",
      tasks: [
        "השווה את <b>529</b> ל-<b>401</b>. איפה המסלולים מתפצלים, ומה כל אחד מהם מחזיר למשתמש? מה הקוד הסבוך מחזיר בשניהם?",
        "בחר <b>סירוב</b>. למה זה ModelRejected ולא ModelUnavailable, למרות שה-HTTP הוא 200?",
        "הפעל את <b>retries גם בשירות</b>. כמה קריאות יוצאות לספק בתקלה אחת של 529, ולמה זה הכי גרוע דווקא אז?",
      ],
    },
    {
      id: "l20review",
      title: "מצא את הפגם: design review",
      lead: "מסמך תכנון קצר של ה-adapter שנותן גישה בתהליך האישור של Company Brain, וצ'קליסט של תשעה פריטים. לכל סעיף בוחרים אם הוא תקין או איזה פריט בצ'קליסט הוא מפר, ומקבלים מיד הסבר. חלק מהסעיפים תקינים.",
      tasks: [
        "עבור על כל תשעת הסעיפים. כמה פגמים מצאת, וכמה סעיפים סימנת כפגומים כשהם בעצם תקינים?",
        "לכל פגם שמצאת: נסח במשפט אחד את התיקון, לפני שאתה קורא את ההסבר.",
        "איזה פגם היה הכי יקר אם היה מגיע לפרודקשן, ולמה?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/20-design-driven",
    intro: "המעבדה בתיקייה labs/20-design-driven, וחבילה חדשה בשורש הריפו, <b>designkit</b>, מחזיקה את טיפוסי הדומיין, ה-adapters האמיתיים ופתרונות הייחוס. במרכז: <b>legacy/tangled.py</b>, שירות התשובות של Company Brain כפונקציה אחת סבוכה. תמדוד אותו, תפרק אותו ל-ports ו-adapters, תכתוב בדיקות חוזה שגם סוכן קוד יכול לעבוד מולן, ותתרגל גרסאות, דיאגרמת רצף ו-design review. כמעט הכל רץ בלי רשת ובחינם.",
    setup: [
      'cd ~/ai-engineer-course-starter && source .venv/bin/activate',
      "uv pip install -r requirements.txt -r labs/20-design-driven/requirements.txt",
      "python -m pytest -q                                  # environment tests (tests/test_design.py)",
      "python -m pytest -q labs/20-design-driven/tests      # your exercises: most fail at first",
    ],
    tools: [
      "<b>designkit/types.py:</b> טיפוסי הדומיין (<code>Passage</code>, <code>Completion</code>, <code>AnswerRequest</code>, <code>Answer</code>, <code>PromptVersion</code>) וחוזה השגיאות: <code>ModelUnavailable</code> זמני, <code>ModelRejected</code> קבוע, <code>RetrieverUnavailable</code>. זה החלק הנתון של התכנון.",
      "<b>designkit/domain.py:</b> כללים טהורים שהשירות שלך קורא להם: <code>policy_check</code>, <code>rank</code>, <code>build_prompt</code>, <code>parse_citations</code>, <code>degraded_text</code>, <code>ANSWER_PROMPT_V1</code>.",
      "<b>designkit/adapters.py:</b> <code>LlmkitChatModel</code> (llmkit מאחורי ה-port, עם תרגום שגיאות), <code>KeywordRetriever</code> (מסמכי Acme, נטענים פעם אחת), <code>JsonlAnswerStore</code>, <code>SystemClock</code>.",
      "<b>measure.py:</b> מריץ את התרחישים לפני ואחרי תחת coverage.py עם <code>--branch</code>, ומדווח זמן, הבדיקות האיטיות וכיסוי של הקוד הנבדק בלבד.",
      "<b>answer_demo.py:</b> ה-composition root. <code>--model fake</code> (חינם), <code>mock:mock-model</code>, או ספק אמיתי. <code>--store jsonl</code> ו-<code>--request-id</code> כדי לראות replay.",
      "<b>check_sequence.py ו-check_review.py:</b> הבודקים של תרגילים 7 ו-8. הראשון נותן גם קישור ל-mermaid.live.",
      "<b>mine.py:</b> ארבעה חלקים שלך: ports ו-fakes, <code>AnswerService</code>, שלוש מחלקות חוזה, ו-registry לגרסאות.",
    ],
    exercises: [
      { id: "ex1", title: "למדוד לפני", text: "קרא את legacy/tangled.py מההתחלה ועד הסוף, וסמן לכל קטע לאיזה port עתידי הוא שייך: model, retriever, store, clock, או לוגיקה עסקית שנשארת בפנים. קרא את legacy/tests/test_tangled.py וספור את ה-monkeypatch. הרץ את המדידה ושמור: זמן, הבדיקה האיטית ולמה היא איטית, כיסוי שורות ו-branches, ומה אי אפשר לבדוק בכלל.", cmd: "python labs/20-design-driven/measure.py --before" },
      { id: "ex2", title: "Ports ו-fakes", text: "ב-mine.py: הגדר את ChatModel, Retriever, AnswerStore ו-Clock כ-Protocol עם runtime_checkable, וממש FakeChatModel, InMemoryRetriever, InMemoryAnswerStore ו-FixedClock. הבדיקות מוודאות גם שה-adapters האמיתיים עונים על ה-Protocols שלך בלי לרשת מהם.", cmd: "python -m pytest -q labs/20-design-driven/tests/test_ex2_ports.py" },
      { id: "ex3", title: "השירות מול ports, והמדידה אחרי", text: "ממש את AnswerService לפי הסדר שב-docstring: replay, מדיניות, חיפוש, מודל, ציטוטים, שמירה. אחר כך הרץ את answer_demo עם fake, עם mockllm, ואם תרצה עם Haiku אמיתי, ושים לב שהחלפת הספק היא דגל אחד. בסוף הרץ את המדידה על שני הצדדים והשווה לתרגיל 1: מה השתנה בזמן, מה בכיסוי, ומה עכשיו אפשר לבדוק.", cmd: "python -m pytest -q labs/20-design-driven/tests/test_ex3_service.py\npython labs/20-design-driven/answer_demo.py \"How many vacation days do I get in my first year?\"\npython labs/20-design-driven/answer_demo.py \"How many vacation days do I get in my first year?\" --model anthropic:claude-haiku-5-5\npython labs/20-design-driven/measure.py --both" },
      { id: "ex4", title: "בדיקות חוזה", text: "כתוב ב-mine.py את ChatModelContract, RetrieverContract ו-AnswerStoreContract: מתודות test_ שמקבלות רק self. הקובץ מריץ אותן על ה-fakes שלך, על LlmkitChatModel מול mockllm, על KeywordRetriever ועל JsonlAnswerStore, ואחר כך מול שבעה adapters שבורים בכוונה. כל שבור חייב להיכשל לפחות בבדיקה אחת שלך. אם תרצה, הרץ את המחלקה Live מול Claude אמיתי.", cmd: "python -m pytest -q labs/20-design-driven/tests/test_ex4_contract.py\nBRAIN_LIVE_MODEL=anthropic:claude-haiku-5-5 python -m pytest -q labs/20-design-driven/tests/test_ex4_contract.py -k Live" },
      { id: "ex5", title: "סוכן קוד מממש adapter מתוך החוזה", text: "תן ל-Claude Code את designs/adapter_task.md. הוא צריך לכתוב labs/20-design-driven/sqlite_store.py שעובר את החוזה שלך מתרגיל 4 ובדיקת התמדה. שים לב כמה קבצים הוא קרא, כמה שאלות שאל, ואם נגע במשהו שהמשימה אסרה. כתוב לי שתי שורות: מה במשימה עזר לו, ומה היית מוסיף.", cmd: "claude \"Implement the task in labs/20-design-driven/designs/adapter_task.md\"\npython -m pytest -q labs/20-design-driven/tests/test_ex5_agent_adapter.py" },
      { id: "ex6", title: "גרסאות לפרומפטים ולסכמות", text: "קרא את ה-docstring של prompts_catalog.py, שמספר את היסטוריית הגרסאות של פרומפט התשובה. ממש ב-mine.py את check_compatible (מה שובר את הקוד שקורא את הפלט) ואת PromptRegistry (pins, גרסאות שלא משתנות, וסירוב לשינוי שובר בלי major חדש). הרץ את ה-demo וראה אילו גרסאות נדחות ולמה.", cmd: "python -m pytest -q labs/20-design-driven/tests/test_ex6_registry.py\npython labs/20-design-driven/registry_demo.py" },
      { id: "ex7", title: "Sequence diagram לתהליך אישור הגישה", text: "השלם את designs/access_request_sequence.mmd. כל מה שצריך לדעת על התהליך כתוב בהערות שבראש הקובץ: המשתתפים, שלושת המסלולים של Acme, ומה קורה כשהמודל לא זמין. הבודק מוודא עשרה כללי תכנון ונותן קישור ל-mermaid.live כדי לראות את הדיאגרמה.", cmd: "python labs/20-design-driven/check_sequence.py\npython -m pytest -q labs/20-design-driven/tests/test_ex7_sequence.py" },
      { id: "ex8", title: "Design review", text: "קרא את designs/answer_service_v2.md עם designs/review_checklist.md לידו. כתוב את הממצאים ב-designs/my_review.yaml: סעיף, פריט בצ'קליסט, בעיה ותיקון. יש שמונה בעיות מתוכננות וגם סעיפים שנראים חשודים ותקינים. רק בסוף הרץ עם --reveal.", cmd: "python labs/20-design-driven/check_review.py\npython -m pytest -q labs/20-design-driven/tests/test_ex8_review.py\npython labs/20-design-driven/check_review.py --reveal" },
    ],
  },

  quiz: [
    { q: "אלה ארבע החלטות על Company Brain. איזו מהן שייכת לרמת התכנון של השיעור הזה, ולא לארכיטקטורה של שיעור 19?", options: ["תהליך בקשת הגישה יהיה workflow עם אישור אנושי ולא סוכן", "<code>AnswerService</code> יקבל ChatModel, Retriever, AnswerStore ו-Clock בבנאי, ו-<code>ModelUnavailable</code> יהפוך לתשובה במצב degraded שלא נשמרת", "response cache יישב לפני ה-retriever, והמפתח יכלול את קבוצות ההרשאה ואת גרסת האינדקס", "70% מהשאלות ינותבו ל-Haiku 5.5 והשאר ל-Sonnet 5.5"], correct: 1, explain: "ארכיטקטורה (שיעור 19) עונה על <b>אילו רכיבים</b> יש, איך הם מחוברים, ומה הם עולים: pattern, מטמון, ניתוב בין מודלים. תכנון רכיב עונה על <b>איך רכיב אחד בנוי</b>: אילו ports הוא מקבל, מה כל אחד מבטיח, ומה הוא עושה עם כל סוג שגיאה. ההחלטה על המטמון נשמעת טכנית ומפורטת, אבל היא החלטה על רכיב נוסף בזרימה ועל מה עובר בו, ולכן היא ארכיטקטורה." },
    { q: "ב-Company Brain, ה-port מוגדר כך: <code>class ChatModel(Protocol): def complete(self, system, prompt) -&gt; anthropic.types.Message</code>. היום יש בפרודקשן רק adapter של Anthropic. מה הבעיה העיקרית?", options: ["אין בעיה: יש רק ספק אחד, ו-fake לבדיקות יכול פשוט לבנות <code>anthropic.types.Message</code> ידנית", "ה-port דולף: כל fake וכל adapter אחר חייבים לחקות את ה-SDK של Anthropic, והליבה תלויה בספק. ההחלפה קיימת רק על הנייר", "הבעיה היא ביצועים: אובייקט Message כבד יותר מטיפוס דומיין", "הבעיה היא רק השם: צריך לקרוא לו AnthropicChatModel, כדי שיהיה ברור לאיזה ספק הוא שייך"], correct: 1, explain: "port מדבר <b>בטיפוסי הדומיין</b> בלבד. ה-fake שבונה Message ידנית הוא בדיוק הסימפטום: הבדיקות שלך תלויות עכשיו בגרסה של ה-SDK, ו-adapter של OpenAI יצטרך לתרגם לפורמט של Anthropic. ושינוי השם הוא הכיוון ההפוך: <b>port לכל תפקיד, לא לכל ספק</b>. אם בשם של ה-port יש שם של ספק, הוא לא באמת port." },
    { q: "<code>Retriever</code> מוגדר כ-Protocol עם <code>@runtime_checkable</code>, וה-docstring שלו מבטיח שהתוצאות ממוינות לפי ציון ושיש לכל היותר k. <code>KeywordRetriever</code> לא יורש ממנו, ו-<code>isinstance(KeywordRetriever(), Retriever)</code> מחזיר True. מה זה מוכיח?", options: ["שהחתימה של search תואמת: אותם פרמטרים ואותו טיפוס מוחזר", "שהמחלקה עומדת בהבטחות שב-docstring, כי Protocol כולל אותן", "רק שקיימת במחלקה מתודה בשם search. את החתימות בודק type checker סטטי, ואת ההבטחות (ממוין, לכל היותר k) רק בדיקות חוזה", "שהמחלקה תעבור את ה-RetrieverContract, כי runtime_checkable מריץ אותו"], correct: 2, explain: "<b>runtime_checkable</b> בודק רק <b>שהמתודות קיימות</b>, לא את הפרמטרים שלהן ולא את הטיפוסים. את החתימות בודק <b>mypy או pyright</b>, ואת ההבטחות ההתנהגותיות רק <b>בדיקות חוזה</b> שרצות על כל adapter. הבלבול הנפוץ הוא להניח ש-isinstance בודק חתימה, כמו בשפות עם ממשקים מפורשים." },
    { q: "מתכננים רכיב חדש ב-Company Brain, שמטפל בבקשות גישה. יש לו ארבע תלויות. איזו מהן צריכה להישאר פונקציה רגילה בליבה, ולא להפוך ל-port?", options: ["פונקציה שמחשבת מסלול מהשדות לפי הכלל \"המחמיר מנצח\"", "השעון, שקובע את created_at ואת מועד התפוגה של הגישה", "מחולל המזהים האקראיים של הבקשות", "<code>IdentityProvider.grant</code>, שנותן את הגישה בפועל"], correct: 0, explain: "חישוב המסלול הוא <b>לוגיקה עסקית</b>: מהיר, דטרמיניסטי ושלנו. נבדק ישירות, בלי fake. ports הם לתלויות שהן <b>איטיות, לא דטרמיניסטיות, חיצוניות או מתחלפות</b>. השעון והמזהים האקראיים נראים פנימיים ופשוטים, אבל הם לא דטרמיניסטיים, ובלי port אי אפשר לכתוב assert מדויק על created_at או על מזהה." },
    { q: "ה-SDK של הספק מוגדר לנסות שוב 2 פעמים (3 ניסיונות לכל קריאה). השירות עוטף כל קריאה ל-adapter בלולאה של 2 ניסיונות חוזרים (3 ניסיונות). הספק מחזיר 529 על כל קריאה במשך דקה. כמה קריאות יוצאות לספק בשאלה אחת של עובד?", options: ["4: שני retries בכל שכבה", "6: שלושה ניסיונות בכל שכבה", "9: כל אחד משלושת הניסיונות של השירות מפעיל שלושה ניסיונות של ה-SDK", "5: הניסיון המקורי ועוד ארבעה retries"], correct: 2, explain: "retries בשכבות <b>מוכפלים</b>, לא מתחברים: 3 כפול 3 הוא <b>9</b>. 6 הוא הטעות הנפוצה, שסוכמת את השכבות. וזה קורה דווקא כשהספק עמוס, ולכן זה נקרא <b>retry storm</b>. הכלל של השיעור: <b>שכבה אחת</b> אחראית על retries, וכאן זו llmkit בתוך ה-adapter." },
    { q: "מפתח ה-API של Company Brain פג תוקף, והספק מחזיר 401 על כל קריאה. מה השירות המתוכנן (designkit) עושה?", options: ["השירות תופס את השגיאה ומחזיר תשובה במצב degraded עם רשימת המסמכים, כדי שהעובד יקבל לפחות משהו", "ה-adapter זורק <code>ModelRejected</code>, והשירות לא תופס אותה: זה באג קונפיגורציה, שצריך ליפול בקול ולהגיע ללוג ולהתראה", "llmkit מנסה שוב 3 פעמים עם backoff, ורק אחר כך ה-adapter זורק ModelUnavailable", "ה-adapter מעביר את ה-LLMError המקורית הלאה, כדי שקוד הסטטוס 401 יופיע ב-traceback"], correct: 1, explain: "401 לא ייעלם בניסיון חוזר, ולכן <code>classify_error</code> מסווג אותה כלא-retryable, וה-adapter זורק <b>ModelRejected</b>. degraded נשמע אחראי, אבל הוא מיועד לתקלה <b>זמנית</b>, ובקוד הסבוך הוא בדיוק מה שהסתיר מפתח פג תוקף מאחורי \"לא זמין זמנית\". ה-adapter <b>תמיד מתרגם</b>, ו-<code>from exc</code> שומר את השגיאה המקורית ב-<code>__cause__</code>, כך שה-401 עדיין מופיע בלוג." },
    { q: "בקשה עם <code>request_id=\"r-17\"</code> הגיעה ב-10:00, הספק החזיר 529, והשירות החזיר תשובה במצב degraded. ב-10:05 הלקוח שולח שוב את אותה בקשה, עם אותו request_id, והספק כבר תקין. מה קורה?", options: ["השירות מחזיר את תשובת ה-degraded מ-10:00, כי idempotency מבטיחה אותה תשובה לאותו מפתח", "<code>store.get(\"r-17\")</code> לא מוצא כלום, כי degraded לא נשמר. השירות רץ במלואו, מקבל תשובה מהמודל ושומר אותה", "<code>store.put</code> מחזיר False, כי המפתח r-17 כבר קיים מהניסיון הראשון, והשירות מחזיר את מה שנשמר", "השירות דוחה את הבקשה ככפולה, כי אותו request_id כבר טופל"], correct: 1, explain: "השמירה היא מה שהופך בקשה ל-idempotent, ולכן <b>לא שומרים כישלון זמני</b>: אם ה-degraded היה נשמר, כל ניסיון חוזר היה מקבל \"לא זמין\" לנצח. idempotency מבטיחה אותה תשובה רק לבקשה <b>שהושלמה</b>. ו-put לא נכשל כאן, כי שום דבר לא נכתב ב-10:00." },
    { q: "סכמת הפלט <code>answer@1.1.0</code> מוסיפה את הערך <code>\"partial\"</code> ל-enum של השדה status, שהיה <code>[\"answered\", \"no_context\"]</code>. לפי הכללים של השיעור, שבודקים מצד הקוד הקורא, מה הגרסה הבאה?", options: ["1.1.1: לא השתנה מבנה, רק נוסף ערך", "1.2.0: זו הרחבה. הסרה של ערך מה-enum הייתה MAJOR", "2.0.0: ערך enum חדש הוא ערך שהקוד הקורא מעולם לא ראה, ו-match עם שני מקרים לא יודע מה לעשות איתו", "1.2.0, כמו שדה אופציונלי חדש: קוד ישן פשוט יתעלם מהערך"], correct: 2, explain: "המודל <b>כותב</b> את ה-JSON והקוד שלך <b>קורא</b> אותו, ולכן שובר הוא כל דבר שהקורא לא מוכן לו. <b>ערך enum חדש</b> שובר, ולכן זה <b>MAJOR</b>. הכיוון ההפוך הוא מה שמבלבל: צמצום של enum דווקא <b>לא</b> שובר, כי הקורא פשוט לא יפגוש ערך שהוא מכיר. ושדה אופציונלי חדש אפשר להתעלם ממנו, אבל ערך חדש בשדה קיים מגיע לקוד שמטפל בשדה הזה." },
    { q: "כתבת <code>AnswerStoreContract</code>. הוא עובר על <code>InMemoryAnswerStore</code>, וגם על store שבור שב-put של מפתח קיים <b>דורס</b> את התשובה הקודמת ומחזיר True. מה המסקנה?", options: ["שני ה-stores תקינים, כי בשניהם get מחזיר תשובה אחרי put", "החוזה חלש: חסרה בדיקה של first write wins (put שני על אותו מפתח מחזיר False ולא משנה את התשובה). בדיקה שעוברת על adapter שבור לא בודקת את מה שהיא אמורה לבדוק", "צריך להחליף את ה-fake ב-mock, ולבדוק עם assert_called_once ש-put נקרא פעם אחת", "ה-store הדורס בסדר, כי השירות תמיד קורא ל-get לפני put"], correct: 1, explain: "זה המבחן של תרגיל 4: כל <b>adapter שבור</b> חייב להיכשל לפחות בבדיקה אחת. התשובה \"השירות קורא get קודם\" נשמעת מרגיעה, אבל שני עובדים יכולים לעבור את ה-get באותו רגע, ובדיוק בשביל המרוץ הזה <b>put חייב להחזיר False</b> על מפתח קיים. mock בודק <b>איך</b> השירות קרא, לא <b>מה</b> ה-store מבטיח, ולכן הוא לא תופס את הבאג." },
    { q: "measure.py מראה ל-<code>answer_question</code> הסבוך 94% כיסוי שורות, ול-<code>AnswerService</code> אחרי הפירוק 100%. זמן הבדיקות ירד מכ-3 שניות לכ-0.3. מה הקריאה הנכונה?", options: ["הפירוק הוסיף רק 6% כיסוי, ולכן הערך היחיד שלו הוא המהירות", "כיסוי מודד אילו שורות רצו, לא מה נבדק. בקוד הסבוך השורות של created_at ושל except LLMError רצו, אבל אי אפשר היה לבדוק את הערך של created_at, או ש-401 מטופל אחרת מ-529. אחרי הפירוק אפשר, ובעשירית מהזמן", "94% לפני מראה שהבדיקות היו טובות, והבאגים ישבו ב-6% השורות שלא כוסו", "100% אחרי מראה שהבדיקות החדשות תופסות את כל הבאגים בשירות"], correct: 1, explain: "<b>כיסוי הוא לא בדיקה.</b> הקוד הסבוך הריץ כמעט הכל, אבל לא איפשר לכתוב assert על הערכים: 401 ו-529 לא טופלו אחרת, ולכן לא היה מה לבדוק. הבאגים לא ישבו בשורות שלא כוסו, אלא בשורות שרצו בלי שאף אחד יכול לבדוק אותן. היתרון האמיתי הוא במה שאפשר <b>לבטא</b>, ובמהירות של הבדיקות של מצבי כשל, שהן האיטיות." },
  ],

  summary: {
    points: [
      { t: "שלוש רמות של תכנון", b: "ארכיטקטורה מחליטה אילו רכיבים יש ואיך הם מחוברים. מפרט מחליט מה פיצ'ר צריך לעשות מבחוץ. תכנון רכיב מחליט איך רכיב אחד בנוי: ports, הבטחות, שגיאות וסדר. במערכות LLM הרמה האחרונה קובעת אם אפשר לבדוק ולהחליף תלויות שהן איטיות, יקרות ולא דטרמיניסטיות." },
      { t: "Ports and adapters", b: "הליבה מגדירה ports בשפה שלה, ו-adapters מממשים אותם מול טכנולוגיה אחת. התלויות מצביעות פנימה. מודל, retriever, store, כלים ושעון הם ports; המדיניות העסקית נשארת פונקציה טהורה בליבה. port לכל תפקיד, לא לכל ספק." },
      { t: "Protocol וטיפוסי דומיין", b: "typing.Protocol נותן טיפוסיות מבנית: adapter לא יורש ולא מייבא את ה-port. runtime_checkable בודק רק שמתודות קיימות. מה שעובר בגבול הוא מודלים של Pydantic מהדומיין, אף פעם לא אובייקט של ספק או dict." },
      { t: "חוזה שגיאות", b: "כל port מגדיר אילו שגיאות הוא זורק, זמניות או קבועות. ה-adapter מתרגם תמיד, עם from exc. שכבה אחת אחראית על retries, אחרת הם מוכפלים. השירות מתדרדר בשגיאה זמנית ולא שומר, ונופל בקול בשגיאה קבועה." },
      { t: "Dependency injection ו-fakes", b: "השירות מקבל את התלויות בבנאי, ו-composition root אחד מחבר את האמיתיות. fakes הם מימושים עובדים ופשוטים ששומרים את אותן הבטחות, והבדיקות בודקות תוצאות ולא קריאות, ולכן שורדות refactoring." },
      { t: "בדיקות חוזה", b: "חבילה אחת לכל port, שכל adapter יורש ממנה. היא מוודאת שה-fake וה-adapter האמיתי מתנהגים אותו דבר, ולכן הבדיקות עם fakes אומרות משהו על פרודקשן. חוזה טוב נכשל על adapters שבורים בכוונה. גרסה חיה שלו רצה בלילה מול הספק האמיתי." },
      { t: "Idempotency", b: "מפתח שהלקוח יוצר, בדיקה ב-store לפני כל עבודה, first write wins אטומי, ולא שומרים כישלון זמני. ב-LLM בקשה כפולה עולה כסף ומחזירה תשובה אחרת, ובכלים היא יכולה לבצע פעולה פעמיים." },
      { t: "גרסאות לפרומפטים ולסכמות", b: "גרסה סמנטית, גרסאות שלא משתנות, pin אצל הצרכן, והגרסה נרשמת על כל פלט ונכנסת למפתח של כל cache. תאימות נבדקת מצד הקורא: ערך enum חדש, שדה שהפך ל-nullable או שדה חובה שהוסר הם שינויים שוברים." },
      { t: "דיאגרמות, ביקורות וסוכנים", b: "sequence diagram ב-Mermaid חושף באגים של סדר ומסלולי כשל. design review עם צ'קליסט ברמת הממשק תופס אותם כשהם עוד פסקה. ותכנון כזה נותן לסוכן קוד בדיוק מה שהוא צריך: הקשר קטן, ממשק מוגדר, ובדיקה שהוא יכול להריץ." },
    ],
    glossary: [
      ["Port", "ממשק שהליבה מגדירה בשפה שלה, דרכו היא מדברת עם העולם או העולם איתה."],
      ["Adapter", "מימוש של port מול טכנולוגיה אחת, שמתרגם טיפוסים ושגיאות בשני הכיוונים."],
      ["Hexagonal architecture", "השם המקורי של ports and adapters, מאת Alistair Cockburn, 2005."],
      ["Driving / driven port", "port שדרכו מפעילים את הליבה (API, בדיקות), מול port שדרכו הליבה מפעילה תלות (מודל, store)."],
      ["typing.Protocol", "ממשק מבני: כל אובייקט עם המתודות המתאימות נחשב מימוש, בלי ירושה."],
      ["ABC", "מחלקת בסיס מופשטת: ממשק נומינלי שמחייב ירושה ומאפשר קוד משותף."],
      ["Error contract", "רשימת השגיאות ש-port זורק, ומה כל אחת אומרת: זמנית או קבועה."],
      ["Dependency injection", "העברת התלויות לרכיב מבחוץ, בדרך כלל בבנאי, במקום שייצור אותן בעצמו."],
      ["Composition root", "המקום היחיד בקצה התוכנית שיוצר את ה-adapters האמיתיים ומחבר אותם לליבה."],
      ["Fake", "מימוש עובד ופשוט של port ששומר את אותן הבטחות, לשימוש בבדיקות."],
      ["Mock", "כפיל שמתעד קריאות כדי שהבדיקה תבדוק אילו קריאות נעשו."],
      ["Contract test", "חבילת בדיקות שנכתבה מול port, וכל adapter יורש ממנה ומריץ אותה."],
      ["Idempotency key", "מזהה שהלקוח יוצר פעם אחת ושולח בכל ניסיון חוזר, כדי שהפעולה תתבצע פעם אחת."],
      ["Semantic versioning", "MAJOR.MINOR.PATCH: שינוי שובר מעלה MAJOR, תוספת תואמת מעלה MINOR, תיקון מעלה PATCH."],
      ["Sequence diagram", "דיאגרמה שמראה מי קורא למי ובאיזה סדר, כולל ענפים ותשובות."],
      ["Design review", "קריאה ביקורתית של מסמך תכנון, עם צ'קליסט, לפני המימוש."],
    ],
    reading: [
      { title: "Alistair Cockburn: Hexagonal Architecture", url: "https://alistair.cockburn.us/hexagonal-architecture/", note: "המאמר המקורי. חובה." },
      { title: "Protocols and structural subtyping", url: "https://typing.python.org/en/latest/reference/protocols.html", note: "המדריך הרשמי ל-Protocol, כולל runtime_checkable ומגבלותיו." },
      { title: "Architecture Patterns with Python, פרק 3: On Coupling and Abstractions", url: "https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/ch03.html", note: "Percival ו-Gregory על הפשטות, צימוד ובדיקות עם fakes ב-Python. הספר כולו רלוונטי, ובמיוחד פרק 13 על dependency injection." },
      { title: "Mermaid: Sequence diagrams", url: "https://mermaid.js.org/syntax/sequenceDiagram", note: "התחביר המלא, לתרגיל 7." },
      { title: "Design Docs at Google", url: "https://www.industrialempathy.com/posts/design-docs-at-google/", note: "איך נראה מסמך תכנון טוב ומה עושים איתו בביקורת." },
      { title: "Langfuse: Prompt version control", url: "https://langfuse.com/docs/prompt-management/features/prompt-version-control", note: "גרסאות ו-labels בכלי ניהול פרומפטים אמיתי." },
      { title: "LangChain: Standard tests", url: "https://docs.langchain.com/oss/python/contributing/standard-tests-langchain", note: "בדיקות חוזה לאינטגרציות של מודלים, בתעשייה." },
      { title: "Best practices for Claude Code", url: "https://code.claude.com/docs/en/best-practices", note: "בדיקה שהסוכן יכול להריץ, ומפרטים שמציינים קבצים וממשקים." },
      { title: "mypy: Protocols", url: "https://mypy.readthedocs.io/en/stable/protocols.html", note: "איך type checker סטטי בודק התאמה ל-Protocol." },
    ],
  },
};
