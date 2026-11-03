# מעבדה 8: Enterprise Data and Business Context Integration

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/08-enterprise-data/requirements.txt   # sqlglot
python -m pytest -q tests/test_datakit.py                # בדיקות הסביבה של datakit
python -m pytest -q labs/08-enterprise-data/tests        # התרגילים שלך: בהתחלה רובן נכשלות, וזה תקין
```

## הנתונים שהמעבדה עובדת עליהם

קובץ ה-SQLite הוא `data/acme/corpus/structured/acme.db`. זה extract לילי של מערכות Acme, ויש בו שש טבלאות נתונים וטבלת provenance אחת:

- **employees** (120 שורות, מקור HiBob): id, name, email, title, team, manager_id, location, start_date. העמודות email ו-start_date מסומנות **pii**.
- **teams** (20 שורות, מקור HiBob): id, name, department, lead_id, parent_lead_id, main_location, headcount.
- **systems** (28 שורות, מקור IT asset register): name, owner_team, tier, data_classification, approved_tool, kind, sensitive.
- **access_grants** (300 שורות, מקור Okta ו-access-bot): id, employee_id, system, level, granted_at, approved_by, route, expires_at, policy_version.
- **customers** (150 שורות, מקור Salesforce): id, name, plan, region, seats, arr_usd, currency, red_folder. העמודה arr_usd מסומנת **financial**.
- **tickets** (200 שורות, מקור Zendesk): id, customer_id, customer_plan, subject, priority, status, created_at, first_response_minutes, sla_target_minutes, sla_breached, assigned_team, red_folder, incident_id. זה **extract של 200 קריאות**, לא כל הקריאות.
- **provenance**: שורה לכל טבלה, עם מערכת המקור, אובייקט המקור, זמן החילוץ (2026-10-31T23:00:00Z), מספר השורות והערות.
- בכל שורה בכל טבלת נתונים יש גם `_source_system` ו-`_extracted_at`.

"היום" בעולם של Acme הוא 31 באוקטובר 2026, והסקריפטים מניחים ש"עכשיו" הוא 2026-11-01T09:00:00Z, אלא אם נותנים `--now`.

## מה חדש

- **`datakit/`**: חבילה חדשה לנתונים מובנים:
  - `semantic.py` טוען את שכבת הסמנטיקה מ-YAML, מאמת אותה, מרנדר אותה ל-context קומפקטי, ובונה ממנה את ה-policy של ה-guard.
  - `guard.py` בודק SQL על עץ התחביר של sqlglot: רק SELECT, רק טבלאות ועמודות מותרות, עמודות רגישות לפי תפקיד, ו-LIMIT.
  - `rls.py` מממש row-level security בשכתוב השאילתה.
  - `db.py` פותח את הקובץ read-only, עם timeout, תקרת שורות ו-authorizer שחוסם עמודות ברמת מסד הנתונים.
  - `provenance.py` מחשב מאילו טבלאות, מאילו שורות ומאיזה זמן חילוץ התשובה הגיעה.
  - `freshness.py` מזהה נתונים ישנים מדי.
  - `evaluate.py` מחשב execution accuracy.
  - `text2sql.py` מחבר את כל השלבים ללולאה אחת.
- **`datakit/data/acme_semantic.yaml`**: שכבת הסמנטיקה של Acme. היא כוללת תיאורי טבלאות ועמודות, ערכי enum, רגישות, נתיבי join, מונחים עסקיים, מדדים, תפקידים, row policy, מגבלות ודוגמאות מאומתות.
- **`golden/business_questions.jsonl`**: 27 שאלות עסקיות, כל אחת עם SQL זהב ותוצאת זהב שחושבה מה-DB. שלוש מהן הן שאלות שצריך **לסרב** להן. הקובץ נבנה עם `golden/build_golden.py`.
- **`fixtures/replay.jsonl`**: תשובות מודל **סינתטיות**, שנכתבו ביד כדי להתנהג כמו מודל. יש בהן שלוש טעויות טיפוסיות ושני תיקונים, והן מאפשרות להריץ את כל הלולאה בלי מפתח ובלי עלות. עם `--live --record` מוסיפים להן תשובות אמיתיות.
- **`mine.py`**: הקוד שלך לתרגילים 3, 5, 6 ו-7.

## התרגילים

**1. שני סוגי מקורות, חברה אחת.** הסקריפט מציג מה יש ב-DB, ואחר כך ארבע עובדות: מה ה-DB אומר ומה מסמך אומר. בשתיים יש הסכמה, ובשתיים אין, ומסיבות שונות. כתוב 3 עד 5 שורות ב-`results/ex1.md`: מתי היית עונה מה-DB, מתי ממסמך, ומה תשובה צריכה להגיד כשהם לא מסכימים.

```bash
python labs/08-enterprise-data/explore_data.py
python labs/08-enterprise-data/explore_data.py --sql "SELECT status, COUNT(*) FROM tickets GROUP BY status"
```

**2. שכבת סמנטיקה.** ב-`semantic/my_semantic.yaml` יש עותק של שכבת הייחוס, וחסרים בו כמה חלקים:
- שלושה מדדים: `sla_breach_rate`, `open_tickets` ו-`red_folder_arr`.
- שני מונחים עסקיים: open ticket ו-Red Folder.
- שני נתיבי join: tickets אל customers, ו-systems אל teams.

ההגדרות העסקיות שצריך מופיעות בראש הקובץ. השלם אותן, רנדר, והשווה את גודל ה-context לגודל ה-DDL הגולמי.

```bash
python labs/08-enterprise-data/render_context.py --compare
python labs/08-enterprise-data/render_context.py --role finance --quiet
python labs/08-enterprise-data/render_context.py --tables tickets,customers --quiet
python -m pytest -q labs/08-enterprise-data/tests/test_ex2_semantic.py
```

**3. SQL guard.** ממש את `guard_sql` ב-`mine.py`. ה-docstring מגדיר את סדר הבדיקות ואת הודעות השגיאה. הבדיקות כוללות 33 ניסיונות עקיפה: stacked statements, PRAGMA, ATTACH, sqlite_master, `main.x`, table-valued functions, `SELECT *`, מירכאות וסוגריים מרובעים, alias, תת-שאילתה, CTE, UNION, PII בתוך WHERE, ו-LIMIT שהוא לא מספר.

```bash
python -m pytest -q labs/08-enterprise-data/tests/test_ex3_guard.py
python labs/08-enterprise-data/guard_cli.py
python labs/08-enterprise-data/guard_cli.py --run --sql "SELECT priority, COUNT(*) FROM tickets GROUP BY 1"
```

**4. הלולאה המלאה.** שאלה, SQLPlan (structured output), guard, row policy, הרצה read-only, ותשובה עם provenance. התחל offline, ואז הרץ live. השווה את ה-SQL שהמודל האמיתי כותב לזה שבתשובות הסינתטיות. נסה גם שאלה משלך, ותכתוב מה קרה.

```bash
python labs/08-enterprise-data/ask.py --list
python labs/08-enterprise-data/ask.py "How many open P1 tickets do we have right now?"
python labs/08-enterprise-data/ask.py --live --show-prompt "How many open P1 tickets do we have right now?"
python labs/08-enterprise-data/ask.py --live "Show everything about the employees of the Identity team."
python labs/08-enterprise-data/ask.py --live --mine "What is our overall SLA breach rate?"
```

**5. Execution accuracy.** ממש את `results_match`, והרץ את ה-eval offline. הוא יוצא 24/27, כי יש שלוש טעויות מכוונות בתשובות הסינתטיות. לכל טעות, החלט אם זו טעות של המודל, של ההגדרה או של המדידה. אחר כך הרץ live, והשווה.

```bash
python -m pytest -q labs/08-enterprise-data/tests/test_ex5_match.py
python labs/08-enterprise-data/eval_sql.py
python labs/08-enterprise-data/eval_sql.py --lenient
python labs/08-enterprise-data/eval_sql.py --live
```

**6. Row-level security.** ממש את `apply_row_policy`. אחר כך הרץ את אותן שאילתות בתור ארבעה משתמשים: analyst, מנהל של core-api, מנהלת של identity ו-people_ops.

```bash
python -m pytest -q labs/08-enterprise-data/tests/test_ex6_rls.py
python labs/08-enterprise-data/rls_demo.py
python labs/08-enterprise-data/ask.py --live --role manager --team core-api "List the people on my team with their email addresses."
```

**7. טריות נתונים.** ממש את `freshness_report`. הגיל של טבלה הוא הגיל של **השורה הכי ישנה** שלה, ולא מה שכתוב בטבלת ה-provenance. `--simulate-partial` מייצר עותק שבו טעינת הקריאות נקטעה באמצע, ומראה איך האזהרה מגיעה עד התשובה.

```bash
python -m pytest -q labs/08-enterprise-data/tests/test_ex7_freshness.py
python labs/08-enterprise-data/freshness_check.py
python labs/08-enterprise-data/freshness_check.py --now 2026-11-03T09:00:00Z
python labs/08-enterprise-data/freshness_check.py --simulate-partial
```

**8. שאלה אחת, שני סוגי מקורות.** "מי הבעלים של השירות שגרם לתקלה של 19 באוגוסט, כמה קריאות מקושרות אליה, וכמה מהן חרגו מה-SLA?" את השירות אפשר למצוא רק ב-postmortem, ואת הבעלים ואת המספרים רק ב-DB. הרץ על שלושת ה-postmortems. ב-postmortem של החיוב הקישור נכשל, כי אין במסמך מזהה תקלה, והתאריך כתוב בו "June 2-3". הסבר למה, ומה היית משנה במטא-דאטה של המסמכים.

```bash
python labs/08-enterprise-data/hybrid_answer.py
python labs/08-enterprise-data/hybrid_answer.py --doc eng-pm-2026-06-billing
python labs/08-enterprise-data/hybrid_answer.py --doc eng-pm-2026-03-scheduler
python labs/08-enterprise-data/hybrid_answer.py --live --doc eng-pm-2026-06-billing
```

## עלויות

- שאלה אחת ב-`ask.py --live` היא שתי קריאות ל-Haiku 5.5: אחת ל-SQLPlan, ואחת לניסוח התשובה. זה בערך 2,600 טוקני קלט ו-100 טוקני פלט, כלומר כ-0.0003 עד 0.0006 דולר.
- הרצה מלאה של `eval_sql.py --live` היא כ-30 קריאות, ועולה כ-0.01 דולר.
- כל המעבדה, כולל כמה הרצות חוזרות, עולה הרבה פחות מ-10 סנט.

## כללים

- את קוד הייחוס ב-`datakit/` אל תקרא לפני שהבדיקות שלך עוברות.
- הסקריפטים משתמשים בפונקציות מ-`mine.py`. כל עוד פונקציה עדיין TODO, הם עוברים לייחוס ומודיעים על זה. עם `--reference` הם משתמשים בייחוס בכוונה.
- ה-DB נפתח תמיד read-only. אם משהו מנסה לכתוב אליו, זה באג.
