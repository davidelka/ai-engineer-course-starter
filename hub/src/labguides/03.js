window.LABGUIDE = window.LABGUIDE || {};
window.LABGUIDE["03"] = {
 "guide": {
  "goal": "<p>בשיעור ראית שמודל שמתבקש להחזיר JSON לא תמיד מחזיר JSON תקין, ושגם JSON תקין לא תמיד נכון. במעבדה הזו בונים, ובודקים בידיים, את כל השרשרת שהופכת הודעה חופשית של עובד לאובייקט Python שאפשר לסמוך עליו. הדוגמה לאורך כל המעבדה היא <b>בקשות גישה ב-Acme</b>: עובד כותב \"תנו לי גישת עריכה ל-Figma לחודשיים\", והמערכת צריכה להוציא מזה את הכלי, רמת הגישה, משך הזמן, והכי חשוב: לאן הבקשה מנותבת. אישור אוטומטי, מנהל, או צוות האבטחה.</p><p>בסוף המעבדה תדע לשלוח סכמה לספק בלי SDK, לזהות מה הספק לא אוכף, לכתוב בעצמך את שני החלקים של לולאת התיקון (חילוץ ה-JSON מהתשובה וניסוח השגיאות למודל), להוסיף כללים עסקיים שסכמה לא יכולה לבטא, ולמדוד את כל זה על סט של 24 בקשות עם תשובה ידועה.</p>",
  "flow": "<p>המעבדה עולה בשכבות, בדיוק לפי שלוש שכבות ההגנה מהשיעור:</p><ul class=\"clean\"><li><b>תרגילים 1–2, שכבת הספק:</b> מה הספק עושה עם הסכמה, ומה הוא לא אוכף. עדיין לא כותבים קוד, רק מריצים ומסתכלים.</li><li><b>תרגילים 3–4, שכבת הפענוח והתיקון:</b> כותבים ב-<code>mine.py</code> את שתי הפונקציות שהלולאה של llmkit משתמשת בהן, ובודקים אותן מול שרת מדומה ששובר תשובות בכוונה.</li><li><b>תרגיל 5, שכבת הכללים העסקיים:</b> validators של Pydantic, למשל \"admin תמיד הולך לאבטחה\".</li><li><b>תרגילים 6–7, מדידה:</b> מריצים את הכול על סט הבקשות האמיתי (עולה סנטים), ומחליטים לפי מספרים מה לשפר.</li></ul><p>תרגילים 1–5 רצים בחינם (מול <code>--mock</code> או השרת המדומה), חוץ מהקריאה החיה הראשונה בתרגיל 1. רק תרגילים 6–7 צריכים מפתח אמיתי.</p>",
  "map": [
   {
    "path": "labs/03-structured-outputs/acme_schema.py",
    "role": "הסכמה: מחלקת <code>AccessRequest</code> (כל השדות של בקשת גישה) ו-<code>SYSTEM_PROMPT</code>. כל הסקריפטים במעבדה מייבאים ממנה."
   },
   {
    "path": "labs/03-structured-outputs/mine.py",
    "role": "הקוד שלך: <code>extract_json</code> (תרגיל 3), <code>format_errors</code> (תרגיל 4), <code>MyAccessRequest</code> (תרגיל 5)."
   },
   {
    "path": "labs/03-structured-outputs/tests/",
    "role": "בדיקה לכל תרגיל קוד. בהתחלה הן נכשלות, וזה מכוון."
   },
   {
    "path": "llmkit/structured.py",
    "role": "הספרייה: <code>complete_structured</code> (הלולאה), <code>provider_schema</code>, וגרסאות הייחוס של שתי הפונקציות שאתה כותב."
   },
   {
    "path": "llmkit/schema.py",
    "role": "ההמרה בפועל של הסכמה לכל ספק: טבלת <code>UNSUPPORTED</code> של מילות מפתח שכל ספק לא מקבל."
   },
   {
    "path": "data/acme/access_requests.jsonl",
    "role": "16 בקשות רגילות, לכל אחת התשובה הנכונה לכל שדה."
   },
   {
    "path": "data/acme/access_requests_hard.jsonl",
    "role": "8 בקשות קשות: עברית, בקשה עמומה בלי כלי, ניסיון הזרקה, עובד שמתקן את עצמו באמצע, משך יחסי (\"עד סוף הספרינט\"), שני כלים בהודעה אחת, מספר במילים ומייל באותיות גדולות."
   },
   {
    "path": "data/acme/saas_access_policy.md",
    "role": "מדיניות הגישה של Acme. היא נכנסת לפרומפט, וממנה נגזר ה-route הנכון."
   }
  ]
 },
 "toolsDetail": [
  {
   "name": "complete_structured",
   "path": "llmkit/structured.py",
   "what": "הפונקציה המרכזית של השיעור. מקבלת מודל, טקסט ומחלקת Pydantic, ומחזירה <code>StructuredResult</code> שבתוכו <code>.value</code>: מופע תקין של המחלקה. אם אין דרך להגיע לאובייקט תקין, היא זורקת <code>StructuredError</code>, ובשדה <code>stage</code> כתוב למה: <code>refusal</code> (המודל סירב), <code>truncated</code> (נגמר <code>max_tokens</code>, ולכן לא מנסים לתקן) או <code>invalid</code> (נגמרו ניסיונות התיקון).",
   "how": "בפנים יש לולאה: שולחים, מחלצים את ה-JSON (<code>extract</code>), מאמתים עם Pydantic, ואם נכשל, מנסחים את השגיאות (<code>explain</code>), מוסיפים לשיחה את התשובה השגויה ואת השגיאות, ושולחים שוב. במצב <code>native</code> הסכמה נשלחת לספק, שמפעיל constrained decoding. במצב <code>prompt</code> היא רק נכתבת בהוראות.",
   "why": "זו הלולאה שאתה משלים: הפרמטרים <code>extract=</code> ו-<code>explain=</code> מקבלים את הפונקציות שאתה כותב ב-<code>mine.py</code>. בתרגיל 4 רואים אותה עובדת עם הקוד שלך, ובתרגילים 6–7 היא מריצה את כל ה-eval."
  },
  {
   "name": "provider_schema",
   "path": "llmkit/structured.py → llmkit/schema.py",
   "what": "ממירה מחלקת Pydantic לסכמה שספק מסוים מקבל במצב strict, ומחזירה שני דברים: את הסכמה, ורשימה של כל שינוי שנעשה בדרך.",
   "how": "היא מוסיפה <code>additionalProperties: false</code> לכל אובייקט, הופכת כל שדה לחובה (שדה Optional נשאר nullable), ומוחקת מילות מפתח שהספק לא תומך בהן, למשל <code>pattern</code>, <code>minimum</code> ו-<code>maximum</code> אצל Anthropic. את מה שנמחק היא מעבירה לתיאור השדה, כדי שהמודל לפחות יקרא את האילוץ.",
   "why": "כל שורה ברשימת השינויים היא כלל שהספק <b>לא</b> יאכוף, ולכן רק Pydantic יתפוס אותו. זה תרגיל 2."
  },
  {
   "name": "mockllm --json-fault",
   "path": "mockllm/server.py · apply_json_fault",
   "what": "השרת המדומה משיעור 2. הוא מדבר באותו פרוטוקול כמו הספקים האמיתיים, לא עולה כסף, ועם הדגל הזה מחזיר JSON שבור בדרך מסוימת: <code>fence</code> (עטוף ב-```json), <code>prose</code> (טקסט מסביב), <code>truncated</code> (חתוך), <code>missing_field</code>, <code>wrong_type</code>, <code>bad_enum</code> (הערך SUPER_ADMIN), <code>extra_field</code> (שדה notes שלא קיים) או <code>out_of_range</code>.",
   "how": "מריצים בטרמינל נפרד: <code>python -m mockllm --json-fault bad_enum --json-fault-first 1</code>. הדגל <code>--json-fault-first N</code> אומר שרק N הבקשות הראשונות שבורות, ואחריהן התשובות תקינות. כך רואים ניסיון ראשון נכשל ותיקון שמצליח.",
   "why": "כדי לבדוק לולאת תיקון צריך תשובות שבורות, ומודל אמיתי במצב native כמעט אף פעם לא שובר. השרת המדומה נותן כל סוג תקלה לפי בקשה, בחינם."
  },
  {
   "name": "extract_eval.py",
   "path": "labs/03-structured-outputs/extract_eval.py",
   "what": "הסקריפט שמודד. הוא מריץ את <code>complete_structured</code> על כל הבקשות בסט, משווה כל שדה לתשובה הנכונה, ומדפיס: כמה אובייקטים תקינים (ובכמה ניסיונות), דיוק לכל שדה, דיוק ניתוב, הזיות (ערך שהמודל כתב כשהתשובה הנכונה היא null), עלות ל-1,000 בקשות וזמן.",
   "how": "<code>--model</code> בוחר מודל, <code>--mode</code> בוחר native או prompt, <code>--set</code> בוחר normal, hard או all, <code>--schema mine</code> משתמש ב-<code>MyAccessRequest</code> שלך, ו-<code>--show</code> מדפיס כל שדה שגוי. כל שורה נשמרת ב-<code>results/</code>.",
   "why": "בלי מדידה אי אפשר לדעת אם שינוי עזר. בתרגיל 6 משווים מצבים ומודלים, ובתרגיל 7 מתקנים דבר אחד ומודדים שוב."
  },
  {
   "name": "mine.py",
   "path": "labs/03-structured-outputs/mine.py",
   "what": "שלושה חלקים שאתה כותב: <code>extract_json</code>, <code>format_errors</code> ו-<code>MyAccessRequest</code>. לכל אחד יש docstring שמפרט בדיוק מה הוא צריך לעשות, ובדיקה ב-<code>tests/</code>.",
   "how": "כותבים, מריצים את הבדיקה של התרגיל, וחוזרים עד שהיא עוברת. אחר כך <code>repair_demo.py</code> ו-<code>extract_eval.py --schema mine</code> משתמשים בקוד שלך בתוך הצנרת האמיתית.",
   "why": "ב-<code>llmkit/structured.py</code> יש גרסאות ייחוס. נסה לא להציץ לפני שהבדיקות שלך עוברות, ואז השווה."
  }
 ],
 "code": {
  "ex1": "<p><b>הקובץ:</b> <code>raw_structured.py</code>. הוא שולח בקשה אחת לספק עם <code>httpx</code> בלבד, בלי SDK ובלי הלולאה של llmkit, כדי שתראה בדיוק מה יוצא ונכנס ברשת.</p><ul class=\"clean\"><li><b>ההודעה:</b> בראש הקובץ, <code>MESSAGE</code>: Dana Levi מבקשת גישת קריאה למרחב Confluence ל-30 יום.</li><li><b>הסכמה:</b> <code>provider_schema(AccessRequest, provider)</code> מייצרת אותה מהמחלקה ב-<code>acme_schema.py</code>, ומדפיסה כל שינוי (<code>schema note</code>).</li><li><b>הבקשה:</b> הפונקציה <code>build</code> בונה URL, כותרות וגוף לכל ספק. ההבדל המרכזי הוא איפה הסכמה יושבת: אצל Anthropic ב-<code>output_config.format</code>, אצל OpenAI ב-<code>text.format</code> עם <code>strict: true</code>, ואצל Gemini ב-<code>generationConfig.responseJsonSchema</code>.</li><li><b>התשובה:</b> <code>reply_text</code> שולפת את הטקסט ואת סיבת העצירה, כי כל ספק מחזיר מבנה אחר. אחר כך <code>AccessRequest.model_validate_json(text)</code> בודק אם הטקסט עובר ולידציה, ומדפיס VALID או INVALID.</li><li><b>הדגלים:</b> <code>--twice</code> שולח את אותה בקשה פעמיים ומדפיס את הזמן של כל אחת. הקריאה הראשונה עם סכמה חדשה איטית יותר, כי הספק מקמפל את הסכמה לדקדוק ושומר אותו. <code>--bad-schema</code> מוסיף בכוונה <code>minLength</code> לשדה <code>tool</code>, ש-Claude לא תומך בו, כדי שתראה את ה-400. <code>--mock</code> שולח לשרת המדומה במקום לספק.</li></ul>",
  "ex2": "<p><b>הקובץ:</b> <code>schema_inspect.py</code>. קצר מאוד: הוא מדפיס את מה ש-Pydantic מייצר (<code>model_json_schema()</code>), ואחר כך, לכל ספק, קורא ל-<code>provider_schema</code> ומדפיס את רשימת השינויים.</p><ul class=\"clean\"><li><b>מה לחפש בפלט:</b> שורות שאומרות שמילת מפתח הוסרה והועברה לתיאור. אצל Claude תראה את <code>pattern</code> של המייל ואת <code>minimum</code>/<code>maximum</code> של <code>duration_days</code>. אצל Gemini יש רשימה אחרת.</li><li><b>איפה זה מוגדר:</b> הטבלה <code>UNSUPPORTED</code> ב-<code>llmkit/schema.py</code> אומרת מה כל ספק לא מקבל. שם גם נמצאת ההערה על <code>pattern</code>, שהוספנו אחרי שהבדיקה החיה שלך קיבלה \"Schema is too complex\".</li><li><b>התשובה לשאלה \"איזו שורה בכל זאת אוכפת\":</b> חפש ב-<code>complete_structured</code> את <code>model.model_validate_json(...)</code>. היא מאמתת מול המחלקה <b>המקורית</b>, עם כל האילוצים, גם אלה שהוסרו מהסכמה שנשלחה.</li><li><b>דגלים:</b> <code>--full</code> מדפיס את הסכמה המלאה אחרי ההמרה. <code>--model mine</code> בודק את <code>MyAccessRequest</code> שלך.</li></ul>",
  "ex3": "<p><b>מה כותבים:</b> את <code>extract_json(text)</code> ב-<code>mine.py</code>. היא מקבלת את הטקסט הגולמי שהמודל החזיר, ומחזירה <b>מחרוזת</b> שהיא רק אובייקט ה-JSON. הפענוח עצמו קורה אחר כך, ב-<code>model_validate_json</code>.</p><ul class=\"clean\"><li><b>איפה היא רצה:</b> בתוך הלולאה של <code>complete_structured</code>, בשורה <code>model.model_validate_json(extract(r.text))</code>. אם היא זורקת <code>ValueError</code>, הלולאה תופסת את זה, מנסחת שגיאה, ושולחת לתיקון.</li><li><b>הבדיקה:</b> <code>tests/test_ex3_extract.py</code> בודקת שלושה דברים: שהיא מוצאת את האובייקט במגוון מצבים (גדרות markdown, טקסט מסביב, אובייקט מקונן, סוגריים בתוך מחרוזת), שהיא זורקת <code>ValueError</code> כשאין אובייקט, ושהיא זורקת כשהאובייקט נחתך.</li><li><b>למה זה לא טריוויאלי:</b> חיפוש של <code>{</code> הראשון ו-<code>}</code> האחרון נכשל כשיש טקסט עם סוגריים אחרי האובייקט, או סוגר בתוך מחרוזת כמו <code>\"use {x} here\"</code>. הפתרון המקובל עובר תו-תו וסופר עומק, ומתעלם מסוגריים כשהוא בתוך מחרוזת. צריך לשים לב גם ל-<code>\\\"</code>, מרכאה עם escape שלא סוגרת את המחרוזת.</li><li><b>גדרות:</b> אם יש ```json ... ```, קודם חותכים את מה שבתוכן, ורק אז מחפשים את האובייקט.</li></ul>",
  "ex4": "<p><b>מה כותבים:</b> את <code>format_errors(exc)</code> ב-<code>mine.py</code>. היא הופכת חריגה לטקסט קצר שנשלח למודל בהודעת התיקון. הטקסט שהיא מחזירה נכנס לתבנית <code>REPAIR_MSG</code> ב-<code>llmkit/structured.py</code>.</p><ul class=\"clean\"><li><b>הקלט:</b> ל-<code>ValidationError</code> של Pydantic יש <code>exc.errors()</code>: רשימת מילונים, ובכל אחד <code>loc</code> (הנתיב לשדה, tuple), <code>msg</code> (ההודעה) ו-<code>input</code> (הערך שהגיע). כל חריגה אחרת, למשל <code>ValueError</code> מ-<code>extract_json</code>, היא \"לא JSON תקין\".</li><li><b>הפלט:</b> שורה לכל שגיאה בצורה <code>- duration_days: Input should be less than or equal to 365 (got 100000)</code>. הערך נכתב כ-JSON (<code>json.dumps</code>) ומקוצר ל-60 תווים לכל היותר. מעל <code>max_errors</code> שגיאות מוסיפים שורה <code>- ... and N more errors</code>.</li><li><b>הבדיקה:</b> <code>tests/test_ex4_errors.py</code> בונה בקשה תקינה (<code>GOOD</code>), משנה בה שדה אחד (<code>errors_for(...)</code>), ובודקת שהטקסט שלך מזכיר את השדה ואת הערך הבעייתי. בהמשך אותו קובץ יש בדיקות שמריצות את הלולאה המלאה מול השרת המדומה.</li><li><b>החלק השני, <code>repair_demo.py</code>:</b> הוא קורא ל-<code>complete_structured</code> עם <code>extract=</code> ו-<code>explain=</code> מה-<code>mine.py</code> שלך, ומדפיס כל ניסיון שנכשל ואת הטקסט שנשלח למודל. כך אתה רואה בעיניים את ההודעה שהקוד שלך ניסח. עם <code>--reference</code> הוא משתמש בגרסאות של llmkit, להשוואה.</li></ul>",
  "ex5": "<p><b>מה כותבים:</b> validators במחלקה <code>MyAccessRequest</code> ב-<code>mine.py</code>. היא יורשת מ-<code>AccessRequest</code>, כך שכל השדות כבר קיימים. אתה מוסיף רק כללים.</p><ul class=\"clean\"><li><b>כלל 1, נרמול מייל:</b> <code>@field_validator(\"requester_email\")</code> עם classmethod שמקבל את הערך ומחזיר אותו אחרי <code>strip()</code> ו-<code>lower()</code>. שים לב שהמייל יכול להיות <code>None</code>.</li><li><b>כללים 2 ו-3, עקביות בין שדות:</b> <code>@model_validator(mode=\"after\")</code>. הוא רץ אחרי שכל השדות כבר אומתו, ומקבל את האובייקט כ-<code>self</code>. בודקים את התנאים וזורקים <code>ValueError</code>, או מחזירים <code>self</code>.</li><li><b>למה דווקא כאן:</b> JSON Schema מתאר כל שדה לחוד. \"אם production אז route חייב להיות needs_security\" הוא כלל בין שני שדות, ואין לו מקום בסכמה.</li><li><b>הודעות השגיאה נשלחות למודל:</b> השגיאה שאתה זורק עוברת דרך <code>format_errors</code> ונכנסת להודעת התיקון. הודעה כמו <code>route must be needs_security because access_level is admin</code> אומרת למודל בדיוק מה לתקן. הודעה כמו <code>invalid</code> לא אומרת לו כלום.</li><li><b>הבדיקה:</b> <code>tests/test_ex5_rules.py</code> מריצה בקשה תקינה, נרמול מייל, מייל null, כל אחד מחמשת הטריגרים של אבטחה עם route שגוי ועם route נכון, ו-auto_approve עם write.</li></ul>",
  "ex6": "<p><b>הקובץ:</b> <code>extract_eval.py</code>. זה החלק החי של המעבדה: כ-24 קריאות לכל הרצה, וזה עולה סנטים.</p><ul class=\"clean\"><li><b>הנתונים:</b> הוא קורא את <code>data/acme/access_requests.jsonl</code>. בכל שורה יש <code>message</code> ו-<code>expected</code>, התשובה הנכונה לכל שדה. את הפרומפט הוא בונה מ-<code>SYSTEM_PROMPT</code> ב-<code>acme_schema.py</code>, עם המדיניות מ-<code>saas_access_policy.md</code> בתוכו.</li><li><b>הריצה:</b> <code>run_case</code> קוראת ל-<code>complete_structured</code> לכל בקשה, ארבע במקביל (<code>ThreadPoolExecutor</code>). היא שומרת את האובייקט, את מספר הניסיונות, את העלות, ואם נכשל, את השלב.</li><li><b>הציון:</b> <code>match</code> משווה שדה לשדה. מחרוזות משווים בלי רישיות ורווחים, חוץ מהמייל, שמושווה בדיוק, כי נרמול הוא העבודה של תרגיל 5. כשהתשובה הנכונה היא רשימה (למשל שם בעברית או באנגלית), מספיק שאחת מתאימה. <code>hallucinated</code> מסמן ערך שהמודל כתב כשהתשובה הנכונה היא null.</li><li><b>מה לקרוא בפלט:</b> \"valid objects\" במצב native יהיה כמעט תמיד 24/24, וזה לא אומר הרבה. השורות החשובות הן <code>field accuracy</code> ו-<code>route accuracy</code>. ההשוואה בין <code>--mode native</code> ל-<code>--mode prompt</code> מראה מה constrained decoding נותן בפועל.</li></ul>",
  "ex7": "<p><b>אותו קובץ</b>, <code>extract_eval.py</code>, עם שלושה דגלים: <code>--set hard</code> קורא את <code>data/acme/access_requests_hard.jsonl</code>, <code>--schema mine</code> מחליף את המחלקה ב-<code>MyAccessRequest</code> שלך, ו-<code>--show</code> מדפיס לכל בקשה את השדות השגויים (<code>got ... expected ...</code>) ואת הודעות התיקון.</p><ul class=\"clean\"><li><b>מה יש בסט הקשה</b> (קובץ של 8 שורות, כדאי לקרוא אותו לפני ההרצה): x01 בעברית; x02 עמומה (\"the thing we talked about\"), בלי כלי; x03 עם הוראה מוסתרת למודל בתוך ההודעה; x04 עובד שמבקש קריאה ומתקן לכתיבה באמצע; x05 משך יחסי, \"until the end of the sprint\"; x06 שני כלים ושתי רמות גישה בהודעה אחת; x07 משך במילים, \"ninety days\"; x08 מייל באותיות גדולות, שתרגיל 5 אמור לנרמל.</li><li><b>איך מחליטים מה גרם לכישלון:</b> אם המודל נאלץ להמציא ערך כי השדה חובה, הבעיה בסכמה. אם הוא הבין את ההודעה אבל ניתב לא לפי המדיניות, הבעיה בפרומפט. אם גם עם סכמה ופרומפט טובים הוא טועה, זה המודל.</li><li><b>איפה מתקנים:</b> סכמה ופרומפט ב-<code>acme_schema.py</code> (אם תשנה שם, כדאי לשמור עותק של המקור), או ב-<code>MyAccessRequest</code> ב-<code>mine.py</code>. אחרי כל שינוי מריצים שוב, ומשווים לתוצאה הקודמת. כל הרצה נשמרת ב-<code>results/</code>.</li></ul>"
 }
};
