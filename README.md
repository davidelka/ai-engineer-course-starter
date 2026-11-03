# AI Engineer Course — self-study repo

ריפו העבודה של הקורס: 28 מעבדות, שני פרויקטי אמצע, שלושה פרויקטי סיום, וספריות שנבנו לאורך הקורס ומשמשות שוב ושוב. כל ההסברים, השקופיות והעזרים נמצאים ב-hub של הקורס, `hub/course-hub.html`: קובץ אחד שנפתח ישירות בדפדפן, בלי שרת. כל מעבדה מתחילה ב-README משלה.

## ללמוד עם Claude

הקורס בנוי ללמידה עצמית, כש-Claude (למשל Claude Code) משמש כמנחה. הקובץ `CLAUDE.md` מסביר לו את מבנה הקורס, את סדר כל שיעור, את סגנון ההוראה ואת כללי הבטיחות: מפתחות, עלויות ו-AWS. פותחים את Claude Code בתיקייה הזו, והוא טוען את הקובץ לבד. אחר כך כותבים לו: "בוא נתחיל את הקורס משיעור 1". את ההתקדמות הוא מנהל ב-`PROGRESS.md`.

## התחלה מהירה

```bash
uv venv .venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env            # ומלא את המפתחות שיש לך
python -m pytest -q             # כל בדיקות הסביבה, offline, בלי עלות
```

מודלים מקומיים (embeddings, rerankers) נדרשים רק משיעור 10, ומותקנים בנפרד, כי הם מושכים PyTorch:

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements-local-models.txt
```

## מבנה

**מעבדות:** `labs/NN-*/`. בכל אחת יש README בעברית, `mine.py` עם התרגילים שלך, `tests/` שבודקות אותם, וסקריפטים לכל תרגיל. הבדיקות של התרגילים לא רצות כחלק מ-`pytest` של השורש, רק כשמריצים אותן במפורש, למשל `python -m pytest -q labs/14-tool-use/tests`.

**פרויקטים:** `projects/`.
- `m1-knowledge-assistant`: פרויקט אמצע, שאלות על מסמכי Acme עם מקורות (שלב 1 של Company Brain).
- `m2-personal-search`: פרויקט אמצע, חיפוש חכם במסמכים האישיים שלך, מקומי כברירת מחדל.
- `f1-company-brain`: פרויקט סיום, Company Brain המלא.
- `f2-hebrew-tutor`: פרויקט סיום, מורה קולי לעברית מדוברת.
- `f3-job-agent`: פרויקט סיום, סוכן המשרות בגרסת פרודקשן.

**נתונים:** `data/acme/`. מדיניות וסטים מתויגים משיעורים 1 עד 3, ו-`data/acme/corpus/`: קורפוס סינתטי של 55 מסמכים, 79 שאלות זהב ומסד נתונים מובנה (ראה ה-README שלו).

**ספריות הקורס.** כל אחת נבנתה בשיעור מסוים, ושיעורים מאוחרים יותר משתמשים בה:
- `promptlab` (1): ניסויים מבוקרים בפרומפטים.
- `llmkit`, `mockllm` (2, והורחבו ב-3, 4, 14, 21): adapter אחיד לשלושת הספקים, structured outputs, caching, tools, תמונות; ושרת מדומה עם תקלות.
- `ctxkit` (4): ניהול הקשר, caching ו-compaction.
- `repoguard` (5): hooks ובדיקות לסוכני קוד.
- `spectools` (6): linter למפרטים, traceability ו-contract tests.
- `loopkit` (7): לולאות אימות עם תקציבים.
- `datakit` (8): שכבה סמנטית, SQL guard ו-text-to-SQL.
- `ragkit` (9 עד 13): כל צינור ה-RAG, מ-ingestion ועד אבחון כשלים.
- `toolkit` (14): כלי Acme עם executor ושער אישור.
- `agentkit` (15), `flowkit` (16), `mcpkit` (17), `multikit` (18): סוכנים, workflows, MCP ומערכות מרובות סוכנים.
- `archkit` (19), `designkit` (20): ארכיטקטורה ותכנון ממשקים.
- `voicekit` (21): דיבור לטקסט וטקסט לדיבור.
- `obskit` (22), `evalkit` (23), `guardkit` (24), `gatewaykit` (25), `servekit` (26), `deploykit` (27): ניטור, הערכה, אבטחה, gateway, הגשה ופריסה.
- `interviewkit` (28): הכנה לראיונות.

## בדיקות חיות

הבדיקות של הסביבה רצות בלי מפתחות ובלי עלות. מה שדורש מפתחות, Docker או AWS מרוכז ב-[LIVE_CHECKS.md](LIVE_CHECKS.md), עם העלות המשוערת של כל בדיקה.

## אבטחה

הקובץ `.env` נמצא ב-`.gitignore`. בדוק עם `git status` שהוא לא נכנס לפני כל push. אף סקריפט בקורס לא מדפיס ערכי מפתחות.
