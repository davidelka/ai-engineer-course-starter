# תוצאות מעבדה 5

העתק את הקובץ ל-`results/RESULTS.md` (התיקייה לא נכנסת ל-git) ומלא. את המספרים לוקחים מ-`python labs/05-coding-agents/report.py`.

## הסביבה

- גרסת Claude Code (`claude --version`):
- מודל (`--model`):
- קונפיגורציה: mine או reference, hooks: mine או reference
- מספר ריצות לכל צירוף:

## משימה bugfix

- bare: הצלחות __ מתוך __, turns (median) __, עלות (median) __, זמן (median) __
- configured: הצלחות __ מתוך __, turns (median) __, עלות (median) __, זמן (median) __
- כמה פעמים ה-hooks חסמו או נתנו feedback, ועל מה:
- האם סוכן כלשהו ניסה לבצע את ה-injection, או קרא את `.env`:

## משימה feature

- bare: הצלחות __ מתוך __, turns (median) __, עלות (median) __, זמן (median) __
- configured: הצלחות __ מתוך __, turns (median) __, עלות (median) __, זמן (median) __
- האם הסוכן השתמש ב-skill (חפש `Skill` ב-tool_counts):
- כמה בדיקות חדשות נוספו בכל גרסה:

## תצפיות

- מה הקונפיגורציה שינתה בפועל, לפי ה-transcripts (לא לפי מה שציפית):
- איפה היא הפריעה או עלתה בזמן:
- כשל אחד שראית, ואיזו שכבה (הוראות, הרשאות, hook, בדיקות) הייתה צריכה לתפוס אותו:
- מה הייתי משנה בקונפיגורציה, ואיך הייתי מודד שהשינוי עזר:

## השוואה לריצות שבתיקייה fixtures

`python labs/05-coding-agents/report.py --file labs/05-coding-agents/fixtures/sandbox_runs.jsonl`

- איפה המספרים שלך דומים, ואיפה שונים, ולמה לדעתך:
