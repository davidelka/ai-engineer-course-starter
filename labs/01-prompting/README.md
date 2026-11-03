# מעבדה 1: Prompt Engineering and Model Behavior

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`).

## הכנה (פעם אחת)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ומלא את המפתחות שיש לך
python -m pytest -q         # בדיקות offline, לא עולות כסף
```

לתרגיל 2 צריך גם מודל מקומי:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

## הכלים

| כלי | מה הוא עושה | איך מריצים |
| --- | --- | --- |
| Prompt Lab | ניסוי מבוקר: variants × cases × repeats, לוג מלא וטבלת סיכום | `python -m promptlab run <yaml>` |
| `count_tokens.py` | ספירת טוקנים לאותו טקסט באנגלית, עברית וערבית | `python labs/01-prompting/count_tokens.py` |
| Arena | נחש מה המודל יעשה, ואז תריץ ותבדוק | `python labs/01-prompting/arena.py` |
| promptfoo | אותו ניסוי few-shot בכלי קוד פתוח מוכן, עם תצוגה בדפדפן | ראה למטה |
| `TUTORIAL_GUIDE.md` | אילו פרקים מהמדריך הרשמי של Anthropic שווה לעשות | קריאה |

## Prompt Lab בקצרה

כל ניסוי הוא קובץ YAML ב-`experiments/`. בכל variant משנים **משתנה אחד**.

```bash
# תמיד קודם dry-run: רואים את הפרומפט בדיוק כמו שיישלח, ובכמה קריאות מדובר
python -m promptlab run labs/01-prompting/experiments/ex6_fewshot.yaml --dry-run

# הרצה זולה על 3 מקרים בלבד, לבדוק שהכל עובד
python -m promptlab run labs/01-prompting/experiments/ex6_fewshot.yaml --limit 3 --repeats 1

# הרצה מלאה
python -m promptlab run labs/01-prompting/experiments/ex6_fewshot.yaml

# סיכום מחדש של תוצאות קיימות
python -m promptlab report labs/01-prompting/results/<file>.jsonl
```

עמודות הסיכום:

- **pass**: שיעור ההצלחה לפי ה-scorer של הניסוי.
- **consist**: באיזה אחוז מהמקרים כל החזרות נתנו אותה תשובה.
- **distinct**: כמה תשובות שונות בממוצע לכל מקרה.
- **in_tok / out_tok**: ממוצע טוקנים. out כולל טוקני חשיבה.
- **p50 s**: זמן תגובה חציוני.
- **$/1k**: עלות ל-1,000 קריאות, אם מילאת `prices` ב-YAML מדף המחירים של הספק.
- **err**: קריאות שנכשלו. השגיאה הראשונה מודפסת מתחת לטבלה.

כל קריאה נשמרת כשורת JSON ב-`results/`, כולל הפלט המלא, hash של הפרומפט והפרמטרים.

## התרגילים

| # | קובץ | הערה |
| --- | --- | --- |
| 1 | `count_tokens.py` | בלי מפתחות רץ רק tiktoken; עם מפתח Anthropic נוסף Claude |
| 2 | `experiments/ex2_temperature.yaml` | ה-variant האחרון אמור להיכשל ב-400. זה חלק מהתרגיל |
| 3 | `experiments/ex3_effort.yaml` | השווה pass מול out_tok ו-p50 |
| 4 | `experiments/ex4_hr_system.yaml` | כתוב את הפרומפט שלך ב-`prompts/hr_system_mine.md` |
| 5 | `experiments/ex5_injection.yaml` | מסמך "מורעל" ב-`prompts/hr_policies_poisoned.md` |
| 6 | `experiments/ex6_fewshot.yaml` + `promptfoo/` | שים לב לשורת `outputs` מתחת לטבלה |
| 7 | מזכר החלטה | חצי עמוד, עם המספרים מתרגיל 6 |

**הגשה:** שלח לי את קובץ ה-YAML ששינית, את טבלת הסיכום, ושתיים-שלוש שורות פרשנות לכל תרגיל.

## promptfoo

```bash
cd labs/01-prompting/promptfoo
npx promptfoo@latest eval -c promptfooconfig.yaml
npx promptfoo@latest view
```

אותו ניסוי, אותו כלל ניקוד. השווה את המספרים ל-Prompt Lab: אם הם שונים, נסה להבין למה.

## עלויות

הניסוי הגדול ביותר (תרגיל 6) הוא 240 קריאות קצרות למודל Haiku. תמיד הרץ קודם `--dry-run` ו-`--limit`,
והגדר spending limit ב-Console של כל ספק.
