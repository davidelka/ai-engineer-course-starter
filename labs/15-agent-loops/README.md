# מעבדה 15: Agent Loops and ReAct

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל. אין תלויות חדשות: הכל בנוי על llmkit, mockllm ו-toolkit משיעור 14, ועל obskit משיעור 22 (אופציונלי, רק לתצוגת ה-waterfall).

## הכנה

```bash
source .venv/bin/activate
python -m pytest -q tests/test_agentkit.py      # בדיקות הסביבה של agentkit
python -m pytest -q labs/15-agent-loops/tests   # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

## מה חדש

- **`agentkit/`** היא חבילה חדשה, והיא תשמש גם בשיעורים 16 עד 18. היא בנויה מעל ה-registry וה-executor של toolkit, ולא משכפלת אותם:
  - `Agent` הוא לולאת ה-agent. כל **צעד** הוא קריאה אחת למודל, יחד עם קריאות הכלים שהמודל ביקש והתוצאות שלהן. אחרי כל צעד, מדיניות העצירה מחליטה אם להמשיך.
  - `Budget` מגדיר את הגבולות: מספר צעדים, טוקנים, דולרים, זמן, מספר החזרות המותר על אותה קריאה, צעדים בלי התקדמות, ושגיאות ברצף.
  - `should_stop` היא מדיניות העצירה של הייחוס. בתרגיל 3 תכתוב את שלך.
  - כלי `give_up` מובנה: המודל יכול לעצור בעצמו ולהסביר למה. זו עצירה **מוצלחת**, כי היא כנה.
  - **אישור אנושי**: כל כלי עם תופעת לוואי עובר דרך `confirm(call)`. בלי hook כזה, הכלי פשוט לא רץ.
  - **מצב תכנון** (`mode="plan"`): קודם נוצרת תוכנית מובנית בעזרת `llmkit.structured`, ואחר כך היא מבוצעת. כשקריאה נכשלת, ה-agent מבקש תוכנית מתוקנת.
  - **זיכרון בתוך ריצה**: `keep_tool_results=N` מוחק תוצאות ישנות של כלים, והכלי `note` (עם `scratchpad=True`) שומר עובדות שצריך לזכור.
  - **trajectory**: קובץ JSONL עם שורה לכל אירוע (run, plan, confirm, step, trim, stop). `to_spans` ממיר אותו ל-spans של obskit, כדי לראות אותו כ-waterfall.
  - `evaluate.py` מכיל את מדדי ה-trajectory. בתרגיל 4 תכתוב את שלך.
  - `faults.py` מזריק תקלות בצד הכלים: שגיאה זמנית, קריסה, איטיות, מסמך מטעה ומסמך ישן.
  - `workflow.py` מבצע את אותה עבודה כ-workflow קבוע, בלי לולאה. זו תצוגה מקדימה של שיעור 16.
- **שלושה סוגי מודלים** אפשר להעביר לכל סקריפט עם `--model`:
  - `fake` הוא ברירת המחדל. זה `FakeLLM` עם `AcmeHeuristic`: "מודל" קטן מבוסס חוקים, דטרמיניסטי וחינמי. הוא קורא את המשימה עם regex, קורא את תוצאות הכלים שהוא עדיין **רואה**, ובוחר את הקריאה הבאה. הטוקנים שלו **מוערכים** (תווים חלקי 4) ומתומחרים כמו Haiku 5.5, והפלט מסומן כ-estimated. המטרה שלו היא להראות את **המנגנון** (לולאה, גבולות, מדדים), לא את שיקול הדעת של מודל אמיתי.
  - `mock`, `mock-openai` ו-`mock-gemini` מריצים את mockllm בתוך התהליך, עם `data/mock_script.json`. אלה צורות ה-wire האמיתיות של שלושת הספקים. ה-mock מכיר רק את המשימות שבסקריפט, והוא טיפש בכוונה: למשל, אחרי סירוב הוא ינסה שוב ושוב.
  - `anthropic:claude-haiku-5-5` הוא המודל האמיתי, וזו המדידה האמיתית. הוא עולה כסף, והסקריפטים מדפיסים את העלות.
- **`mine.py`** מכיל את הקוד שלך לתרגילים 3, 4 ו-7.

## הנתונים שהתרגילים עובדים עליהם

- **מדיניות הגישה v2.2** נמצאת ב-`data/acme/corpus/docs/it-saas-access-v2-2.md`, והכלי `check_policy` מממש אותה. יש בה שלושה מסלולים:
  - `auto_approve`: כלי מהרשימה המאושרת (Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma viewer, GitHub read), ברמת read, viewer או member, בלי מידע של לקוחות ובלי מידע פיננסי. ההרשאה ניתנת מיד.
  - `needs_manager`: מושב בתשלום (editor), גישת write, או כלי שלא ברשימה ואין בו מידע רגיש. המנהל הישיר מאשר תוך 2 ימי עבודה.
  - `needs_security`: הרשאות admin או owner, תשתית פרודקשן (למשל aws-production ו-kubernetes-prod), מידע של לקוחות או מידע פיננסי (salesforce, zendesk, netsuite, hilan-payroll), ושיתוף חיצוני או חיבור אפליקציית OAuth ל-Google Workspace. צוות האבטחה בודק תוך 2 ימי עבודה, וההרשאה פגה אחרי 90 יום כברירת מחדל.
  - כשכמה כללים מתאימים, המסלול המחמיר מנצח. הגרסה הקודמת, v2.1 (`it-saas-access-v2-1.md`), קבעה 3 ימי עבודה לבדיקת אבטחה, ולא קבעה תפוגה. היא עדיין נמצאת בקורפוס, וזה בדיוק מה שהופך אותה למלכודת בתרגיל 6.
- **העובדים שמופיעים במשימות** (מתוך הטבלה employees ב-`data/acme/corpus/structured/acme.db`):
  - Dana Levi, `dana.levi@acme.example`, E016, Engineering Team Lead בצוות engine. המנהלת שלה היא Michal Ben-David (E005). ההרשאות הנוכחיות שלה: slack member, auth-service read, github write ו-web-app read.
  - Avital Tal, E017. המנהלת שלה היא Dana Levi.
  - Sapir Golan, E040. המנהל שלה הוא Gil Avraham (E037).
  - Lena Hoffmann, E086. יש לה כבר salesforce write.
  - Yonatan Peled, E023. אין לו הרשאת github.
  - Keren Amar, E106, ב-finance. המנהל שלה הוא Avi Mizrahi (E003), ויש לה netsuite member.
  - Hila Tzur, E074. Ofer Levi, E078. Itai Barak, E009, והמנהלת שלו היא Michal Ben-David.
  - יש **ארבעה** עובדים בשם Shani (Barzilai, Sasson, Shapiro ו-Alon). לכן `lookup_employee("Shani")` מחזיר שגיאה שמפרטת את כולם.
  - `jonathan.mor@acme.example` לא קיים.
- **ששת הכלים** מ-toolkit: `lookup_employee`, `get_system_info`, `list_access_grants`, `check_policy`, `read_document` (הפלט שלו לא אמין) ו-`create_access_request` (יש לו תופעת לוואי, והוא דורש אישור). במעבדה הזו כל ריצה כותבת לקובץ requests.db זמני משלה, כך שה-idempotency של ריצה אחת לא משפיע על ריצה אחרת.
- **סט המשימות** נמצא ב-`labs/15-agent-loops/data/tasks.jsonl`: 15 משימות, ולכל אחת יש תוצאת זהב. אלה הסוגים:
  - **שש משימות שבהן צריך לפתוח בקשה**: t01 (Dana, admin ב-aws-production ל-3 ימים, needs_security), t02 (Avital, Figma editor, needs_manager), t09 (Yonatan, GitHub write, אחרי בדיקה שאין לו), t12 (Keren, NetSuite editor ל-30 יום, needs_security), t13 (Hila, Zoom member, auto_approve) ו-t15 (Itai, Datadog read, needs_manager).
  - **שבע משימות שבהן אסור לפתוח בקשה**: t03 (האם ל-Lena כבר יש Salesforce), t04 (Sapir, admin ב-Miro, "רק אם זה auto_approve"), t06 (עובד שלא קיים), t07 (השוואה בין github ל-aws-production), t08 (אילו הרשאות יש ל-E016), t10 (ל-Dana כבר יש GitHub write) ו-t14 (אפליקציית OAuth ל-Google Workspace, "אל תפתח עדיין").
  - **משימה אחת של בירור**: t05 ("Shani"). התשובה הנכונה היא לשאול לאיזו Shani הכוונה.
  - **משימה אחת על המסמך**: t11 (כמה זמן לוקחת בדיקת אבטחה, ומתי היא פגה, לפי המסמך).
  - לכל משימה יש בזהב את התוצאה הצפויה, את שדות הבקשה (אם צריך לפתוח אחת), עובדות שחייבות להופיע בתשובה, כלים חובה וכלים אסורים, ו-`optimal_calls`: מספר הקריאות במסלול הקצר ביותר.

## התרגילים

**1. ריצה ראשונה: לקרוא trajectory.** הרץ את t01 (Dana) עם המודל המזויף, ואחר כך מול mockllm וגם מול Haiku. בכל צעד ב-trajectory יש ארבעה חלקים: `think` הוא הטקסט שהמודל כתב לפני הקריאה, `act` הוא הקריאה עם ה-fingerprint שלה, `obs` הוא התוצאה, ו-`policy` הוא ההחלטה של מדיניות העצירה. ענה: כמה צעדים היו, וכמה קריאות? למה מספר הצעדים גדול ממספר הקריאות באחד? איפה בדיוק ביקש ה-agent אישור? כמה עלה כל צעד, ולמה כל צעד יקר יותר מהקודם? ב-Haiku: האם הוא עשה lookup ו-check_policy במקביל, באותו צעד?

```bash
python labs/15-agent-loops/run_agent.py t01
python labs/15-agent-loops/run_agent.py t01 --model mock
python labs/15-agent-loops/run_agent.py t01 --model anthropic:claude-haiku-5-5 --approve ask
python labs/15-agent-loops/run_agent.py t01 --spans labs/15-agent-loops/results/spans.jsonl
python -m obskit.viewer labs/15-agent-loops/results/spans.jsonl -o labs/15-agent-loops/results/spans.html
```

**2. תופעות לוואי מאחורי אדם.** הרץ את t02 שלוש פעמים: עם אישור, עם סירוב, ובלי hook בכלל. בכל ריצה חפש ב-trajectory את שורת ה-`confirm` ואת התוצאה שהמודל קיבל. מול mockllm עם סירוב, ה-mock מנסה שוב ושוב. איזה כלל במדיניות העצירה עוצר אותו, ואחרי כמה ניסיונות? למה החזרה של "DECLINED, do not retry" למודל עדיפה על שגיאה כללית?

```bash
python labs/15-agent-loops/run_agent.py t02 --approve yes
python labs/15-agent-loops/run_agent.py t02 --approve no
python labs/15-agent-loops/run_agent.py t02 --approve none
python labs/15-agent-loops/run_agent.py t01 --model mock --approve no
```

**3. מדיניות עצירה (קוד).** ממש את `should_stop` ב-`mine.py`. ה-docstring מגדיר אחד-עשר כללים, וחשוב לבדוק אותם לפי הסדר. אחר כך הרץ את ה-agent עם המדיניות שלך מול שלוש לולאות:
- `--loop repeat`: אותה קריאה בדיוק, שוב ושוב.
- `--loop paraphrase`: אותו lookup, פעם לפי שם, פעם לפי מייל ופעם לפי מזהה. ה-fingerprints שונים, אבל התוצאות זהות. אחרי כמה צעדים כל כלל היה תופס את הלולאה הזו, ולמה repetition לבדו לא מספיק?
- `--max-cost` נמוך, עם `--summarize` ובלעדיו. מה ההבדל בתשובה, וכמה עלה הצעד הנוסף?

```bash
python -m pytest -q labs/15-agent-loops/tests/test_ex3_policy.py
python labs/15-agent-loops/run_agent.py t01 --loop repeat --mine
python labs/15-agent-loops/run_agent.py t01 --loop paraphrase --mine
python labs/15-agent-loops/run_agent.py t01 --max-cost 0.0005 --mine
python labs/15-agent-loops/run_agent.py t01 --max-cost 0.0005 --summarize --mine
```

**4. מדדי trajectory (קוד).** ממש את `score_trajectory` ואת `summarize_scores` ב-`mine.py`. אחר כך הרץ את כל 15 המשימות עם המדדים שלך. המדדים הם:
- **הצלחה**: עצירה רגילה (final_answer או give_up), תוצאה שתואמת לזהב, כלים חובה שהצליחו, כלים אסורים שלא רצו, ועובדות שמופיעות בתשובה.
- **צעדים וקריאות**.
- **קריאות מיותרות**: חזרה על קריאה זהה אחרי שהיא כבר הצליחה.
- **יעילות**: `optimal_calls` חלקי מספר הקריאות.
- **סתירה לראיות**: התשובה מזכירה מסלול אחר מזה ש-check_policy החזיר.
- **עלות להצלחה**.

אחר כך הרץ עם `--fault lookup_employee=error:1` על כל המשימות. אילו מדדים זזו? האם שיעור ההצלחה ירד?

```bash
python -m pytest -q labs/15-agent-loops/tests/test_ex4_metrics.py
python labs/15-agent-loops/eval_tasks.py --mine
python labs/15-agent-loops/eval_tasks.py --mine --fault lookup_employee=error:1
```

**5. Reactive מול plan-then-act.** הרץ את סט המשימות בשני המצבים, קודם offline ואחר כך מול Haiku. ההרצה החיה היא 30 ריצות, ועולה בערך 3 עד 8 סנטים. הסקריפט עוצר אם העלות עוברת $0.30. השווה בין המצבים: שיעור הצלחה, צעדים בממוצע, קריאות בממוצע, יעילות ועלות להצלחה. ב-offline, המודל המזויף במצב plan מריץ את כל הקריאות שלא תלויות זו בזו בצעד אחד, ולכן יש פחות צעדים. אבל ב-t05 וב-t10 הוא מבזבז קריאות שהתוכנית קבעה מראש. ב-Haiku, מה קרה בפועל? האם Haiku עושה קריאות מקבילות גם במצב reactive, כך שהיתרון של התוכנית נעלם? האם קריאת התכנון הנוספת משתלמת? אם המספרים החיים סותרים את מה שראית ב-offline או את מה שכתוב בשקפים, תכתוב את זה.

```bash
python labs/15-agent-loops/eval_tasks.py --modes react,plan
python labs/15-agent-loops/eval_tasks.py --modes react,plan --model anthropic:claude-haiku-5-5
python labs/15-agent-loops/eval_tasks.py --modes plan --tasks t05,t10 --show
```

**6. להשרות כשלים ולראות התאוששות.** `faults_demo.py` מריץ תשעה תרחישים:
- `transient`: כלי שנכשל פעם אחת.
- `tool-down`: כלי שתמיד נכשל.
- `tool-down-stubborn`: אותו כלי, מול מודל שלא מוותר.
- `misleading`: מסמך מושתל שאומר ש-admin בפרודקשן הוא auto_approve, בזמן ש-check_policy אומר needs_security.
- `stale`: המדיניות הישנה v2.1 חוזרת במקום v2.2.
- `loop-repeat` ו-`loop-paraphrase`: לולאות של המודל המזויף.
- `mock-loop`: תקלת הלולאה של mockllm, על פורמט ה-wire האמיתי.
- `ambiguous`: שם שמתאים לכמה עובדים, במצב plan, עם תכנון מחדש.

לכל תרחיש ענה שלוש שאלות: מה עצר את הריצה, האם התוצאה נכונה מול הזהב, ומי תפס את הבעיה (המודל, מדיניות העצירה, או רק ההערכה). ב-`misleading`, הרץ גם עם `--careful` וגם מול Haiku. הפרומפט של המערכת אומר במפורש ש-check_policy הוא הסמכות. האם Haiku מציית לזה, ומזכיר את הסתירה? ב-`stale`, שים לב שאף מנגנון בלולאה לא יכול לתפוס את הטעות. היא מתגלה רק בהערכה מול זהב.

```bash
python labs/15-agent-loops/faults_demo.py --list
python labs/15-agent-loops/faults_demo.py all
python labs/15-agent-loops/faults_demo.py misleading
python labs/15-agent-loops/faults_demo.py misleading --careful
python labs/15-agent-loops/faults_demo.py misleading --model anthropic:claude-haiku-5-5
python labs/15-agent-loops/faults_demo.py ambiguous --mode plan
python labs/15-agent-loops/faults_demo.py tool-down-stubborn --repeat-limit 10
```

**7. זיכרון בתוך ריצה (קוד).** ממש את `clear_old_tool_results` ב-`mine.py`. הפונקציה צריכה להשאיר את כל ה-ids, כי בלעדיהם הספק מחזיר 400. היא גם לא משנה את הקלט. אחר כך הרץ את memory_demo, שמריץ ארבע הגדרות על שתי משימות: לשמור הכל, לשמור 2, לשמור 1, ולשמור 1 עם הכלי note. שים לב לשלושה דברים:
- עם keep 1 ובלי note, המודל המזויף "שוכח" את המנהלת ומביא אותה שוב, עד שמדיניות העצירה עוצרת אותו.
- עם keep 2, המשימה מסתיימת, אבל שם המנהלת נעלם מהתשובה.
- במשימות הקצרות האלה החיסכון בטוקנים קטן, כי רוב הפרומפט הוא הגדרות הכלים והפרומפט של המערכת, ולא התוצאות. מתי מחיקת תוצאות באמת משתלמת?

לסיום, הרץ מול Haiku ובדוק: האם הוא קורא שוב לכלי כשהתוצאה נמחקה, או שהוא משתמש ב-note?

```bash
python -m pytest -q labs/15-agent-loops/tests/test_ex7_memory.py
python labs/15-agent-loops/memory_demo.py --mine
python labs/15-agent-loops/memory_demo.py --mine --show 1
python labs/15-agent-loops/memory_demo.py --model anthropic:claude-haiku-5-5
```

**8. Workflow קבוע מול agent (תצוגה מקדימה לשיעור 16).** אותן 15 משימות, אבל בלי לולאה. ה-workflow מחלץ את השדות, ואז מריץ lookup, אם צריך גם list_access_grants, אחר כך check_policy, החלטה בקוד ו-create עם אישור. offline החילוץ נעשה עם regex. מול Haiku יש קריאת מודל אחת בלבד, לחילוץ עם structured output. השווה לתרגיל 5 שלושה דברים: עלות, צעדים, ואילו משימות ה-workflow לא יודע לעשות בכלל (t07, t08, t11). מה זה אומר על הבחירה בין agent ל-workflow ב-Company Brain?

```bash
python labs/15-agent-loops/eval_tasks.py --modes react,workflow
python labs/15-agent-loops/eval_tasks.py --modes workflow --model anthropic:claude-haiku-5-5
```

## כללים

- כל המעבדה מול Haiku 5.5 עולה בערך 5 עד 15 סנטים. רוב העלות היא תרגיל 5. לכל ריצה יש תקציב (`--max-cost`), ולהערכה יש תקציב כולל (`--total-budget`, ברירת מחדל $0.30).
- המספרים של `--model fake` הם **הערכה**, ולא חיוב אמיתי. הם מראים איך המנגנון מתנהג, לא כמה טוב Claude.
- את קוד הייחוס ב-`agentkit/policy.py`, ב-`agentkit/evaluate.py` וב-`agentkit/memory.py` אל תקרא לפני שהבדיקות שלך עוברות.
- `results/` לא נכנס ל-git. הקבצים `trajectory.jsonl`, `eval.jsonl`, `faults.jsonl` ו-`memory.jsonl` מצטברים, ואפשר למחוק אותם.
