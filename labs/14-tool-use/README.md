# מעבדה 14: Tool Use and Function Calling

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל. אין תלויות חדשות.

## הכנה

```bash
source .venv/bin/activate
python -m pytest -q                          # בדיקות הסביבה, כולל tests/test_tools.py
python -m pytest -q labs/14-tool-use/tests   # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

## מה חדש

- **llmkit יודע לעבוד עם כלים** בשלושת הספקים. המסמך המלא נמצא ב-`llmkit/TOOLS.md`. בקצרה:
  - `Tool` מגדיר כלי: שם, תיאור, JSON Schema ודגל `strict`. את ההגדרה בונים עם `tool_from_model(Model, ...)`.
  - ב-`ChatRequest` נוספו שלושה שדות: `tools`, `tool_choice` (אחד מ-`auto`, `any`, `none` או שם של כלי) ו-`parallel_tool_calls`.
  - `ChatResult.tool_calls` היא רשימה של `ToolCall`, כל אחד עם id, name ו-arguments מסוג dict. התשובה עצמה זמינה כ-`ChatResult.message`, ומוסיפים אותה לשיחה כמו שהיא.
  - `Message.with_tool_results([...])` בונה הודעת user אחת שמכילה את כל התוצאות.
  - הודעות שהתוכן שלהן מחרוזת רגילה ממשיכות לעבוד בדיוק כמו קודם.
  - יש streaming של קריאות לכלים: אירועים מסוג `tool_call_delta` ו-`tool_call`.
- **mockllm מחזיר קריאות לכלים** בצורה של כל ספק:
  - את ההחלטה על הכלי מקבלים כללי `--tool-script`, או נתב מילים שקורא את השם והתיאור של כל כלי.
  - אחרי שהתוצאות חוזרות, הוא עונה בטקסט שמזכיר אותן.
  - תקלות שאפשר להפעיל עם `--tool-fault`: `invalid_args`, `unknown_tool`, `loop`, `bad_json`.
  - עם `--tool-injectable` הוא מתנהג כמו מודל תמים שמציית להוראות שמופיעות בתוך תוצאה של כלי.
  - הוא מחזיר שגיאות 400 כמו של ה-API האמיתי, למשל כש-`tool_result` חסר או כש-thought signature חסר ב-Gemini.
- **`toolkit/`** היא החבילה של הכלים של Acme, שתשמש גם בשיעורים 15 עד 18:
  - שישה כלים מעל `data/acme/corpus/structured/acme.db`, שנפתח לקריאה בלבד: `lookup_employee`, `get_system_info`, `list_access_grants`, `check_policy` (מדיניות v2.2), `read_document` (הפלט שלו מסומן כלא אמין) ו-`create_access_request` (כלי עם תופעת לוואי, שכותב לטבלה מקומית ב-`labs/14-tool-use/results/requests.db`).
  - `Registry` מרכז את הכלים, `execute_tool` ו-`Executor` מריצים אותם, `run_tool_loop` מריץ את הלולאה, `ConfirmationGate` מטפל באישור אנושי, ו-`guards` מכיל את שכבות ההגנה מפני הזרקה.
- **`mine.py`** מכיל את הקוד שלך לתרגילים 3, 4 ו-6.

## הנתונים שהתרגילים עובדים עליהם

- **מדיניות הגישה** נמצאת ב-`data/acme/saas_access_policy.md`, והגרסה v2.2 שלה ב-`data/acme/corpus/docs/it-saas-access-v2-2.md`. יש בה שלושה מסלולים:
  - `auto_approve`: כלי מהרשימה המאושרת (Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma viewer, GitHub read), ברמת read, viewer או member, בלי מידע של לקוחות ובלי מידע פיננסי.
  - `needs_manager`: מושב בתשלום (editor), גישת write, או כלי שלא נמצא ברשימה ואין בו מידע רגיש.
  - `needs_security`: הרשאות admin או owner, תשתית פרודקשן, מידע של לקוחות או מידע פיננסי, ושיתוף חיצוני.
  - כשכמה כללים מתאימים, המסלול המחמיר מנצח. ב-v2.2 בדיקת אבטחה לוקחת עד 2 ימי עבודה, והרשאה שעברה במסלול security פגה אחרי 90 יום.
- **הטבלאות** ב-`acme.db`:
  - `employees`: 120 עובדים. דוגמה: Dana Levi, `dana.levi@acme.example`, E016, Engineering Team Lead בצוות engine, והמנהלת שלה Michal Ben-David (E005).
  - `systems`: 28 מערכות. לכל מערכת יש owner_team, tier, approved_tool ו-sensitive.
  - `access_grants`: 300 הרשאות. המסלול של כל אחת מהן חושב לפי אותם כללים, והבדיקות מוודאות ש-`check_policy` מחזיר את אותו מסלול בכל ה-300.

## התרגילים

**1. הלוך-חזור בלי SDK.** הסקריפט מדפיס את כל ה-JSON: הבקשה עם הכלים, התשובה עם הקריאה לכלי, מה הקוד שלך הריץ, הבקשה השנייה עם התוצאה, והתשובה הסופית.

```bash
python labs/14-tool-use/raw_roundtrip.py
python labs/14-tool-use/raw_roundtrip.py --parallel
python labs/14-tool-use/raw_roundtrip.py --mock --provider openai
python labs/14-tool-use/raw_roundtrip.py --mock --provider gemini --parallel
```

**2. כמה עולות הגדרות הכלים.** הסקריפט מראה מה strict mode משנה בסכמה אצל כל ספק. עם `--live` הוא מודד את מספר הטוקנים המדויק בעזרת count_tokens של Anthropic, וזה בחינם.

```bash
python labs/14-tool-use/tool_cost.py
python labs/14-tool-use/tool_cost.py --show create_access_request --provider anthropic
python labs/14-tool-use/tool_cost.py --live
```

**3. Executor שלא קורס.** ממש את `execute_tool` ב-`mine.py`. הוא צריך לטפל בכלי לא מוכר, ב-JSON שבור, בשגיאות Pydantic, בכלי עם תופעת לוואי שלא קיבל אישור, ב-ToolError, בקריסה ובחריגה מזמן. כל מקרה כזה מחזיר תוצאה עם `is_error`.

```bash
python -m pytest -q labs/14-tool-use/tests/test_ex3_executor.py
```

**4. הלולאה לשאלה אחת.** ממש את `run_tool_loop`. הבדיקות רצות מול mockllm ובודקות כמה דברים:
- סבב אחד.
- קריאות מקבילות, שהתוצאות שלהן חוזרות בהודעה אחת.
- שרשרת של שני סבבים.
- התאוששות מארגומנטים שגויים ומכלי שלא קיים.
- לולאה אינסופית שנעצרת אחרי `max_rounds`.

```bash
python -m pytest -q labs/14-tool-use/tests/test_ex4_loop.py
python labs/14-tool-use/ask.py --model mock --fault invalid_args --mine "Look up dana.levi@acme.example"
```

**5. האם התיאור קובע איזה כלי נבחר.** אותם שישה כלים בשלוש גרסאות: good, bad (תיאור של שורה עמומה אחת) ו-opaque (גם שמות עמומים). על 18 שאלות מודדים כמה פעמים נבחר הכלי הנכון.
- בלי `--model`, ההרצה היא מול נתב המילים של ה-mock. זה צעצוע, אבל גם הוא תלוי בתיאור.
- עם Haiku 5.5 זו המדידה האמיתית: 54 קריאות, בערך סנט אחד.

```bash
python labs/14-tool-use/route_eval.py --show
python labs/14-tool-use/route_eval.py --model anthropic:claude-haiku-5-5 --show
```

**6. כלי עם תופעת לוואי מאחורי אישור.** ממש את `call_fingerprint` ואת `ConfirmationGate`. אחר כך הרץ את ה-demo. בהרצה רואים שתי הגנות: בלי אישור אנושי הקריאה לא רצה, וקריאה חוזרת עם אותו `idempotency_key` לא יוצרת רשומה שנייה.

```bash
python -m pytest -q labs/14-tool-use/tests/test_ex6_confirm.py
python labs/14-tool-use/confirm_demo.py
python labs/14-tool-use/confirm_demo.py --model anthropic:claude-haiku-5-5
```

**7. הזרקת הוראות דרך תוצאה של כלי.** המסמך הוא `data/acme/corpus/docs/sales-partner-northwind-notes.md`. הפקודה הראשונה מדפיסה את הפסקה המורעלת. אחר כך הרץ את שני התרחישים, כל אחד עם שכבות הגנה שונות:
- **text:** ההזרקה מנסה לשנות את התשובה.
- **action:** ההזרקה מנסה להפעיל כלי שכותב.

```bash
python labs/14-tool-use/injection_demo.py --show-doc
python labs/14-tool-use/injection_demo.py --defense none
python labs/14-tool-use/injection_demo.py --defense output
python labs/14-tool-use/injection_demo.py --scenario action --defense taint
python labs/14-tool-use/injection_demo.py --model anthropic:claude-haiku-5-5 --defense none
python labs/14-tool-use/injection_demo.py --model anthropic:claude-haiku-5-5 --defense all
```

**8. Company Brain עונה עם כלים.** הרץ חמש שאלות עם trace מלא: סבבים, קריאות מקבילות, שגיאות ועלות. אחר כך הרץ את אותו סט עם `--parallel-off` ועם `--no-strict`, והשווה.

```bash
python labs/14-tool-use/ask.py --set
python labs/14-tool-use/ask.py --set --parallel-off
python labs/14-tool-use/ask.py --set --mine
```

## כללים

- המעבדה כולה על Haiku 5.5 עולה בערך 2 עד 3 סנטים. ההרצה הכבדה היא תרגיל 5.
- את קוד הייחוס ב-`toolkit/executor.py`, ב-`toolkit/loop.py` וב-`toolkit/confirm.py` אל תקרא לפני שהבדיקות שלך עוברות.
- `results/` לא נכנס ל-git. הטבלה `requests.db` נוצרת שם, ואפשר למחוק אותה כדי להתחיל מחדש.
