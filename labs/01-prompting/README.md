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

- **Prompt Lab:** ניסוי מבוקר, variants × cases × repeats, עם לוג מלא וטבלת סיכום. מריצים: `python -m promptlab run <yaml>`.
- **`count_tokens.py`:** ספירת טוקנים לאותו טקסט באנגלית, עברית וערבית. מריצים: `python labs/01-prompting/count_tokens.py`.
- **Arena:** נחש מה המודל יעשה, ואז תריץ ותבדוק. מריצים: `python labs/01-prompting/arena.py`.
- **promptfoo:** אותו ניסוי few-shot בכלי קוד פתוח מוכן, עם תצוגה בדפדפן. ההוראות למטה.
- **`TUTORIAL_GUIDE.md`:** אילו פרקים מהמדריך הרשמי של Anthropic שווה לעשות. קריאה בלבד.

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

1. **תרגיל 1, `count_tokens.py`:** בלי מפתחות רץ רק tiktoken; עם מפתח Anthropic נוספת שורת Claude. מהספירה של Claude מופחתים טוקני המעטפת של ההודעה, כדי שהשורה תראה את הטקסט לבד.
2. **תרגיל 2, `experiments/ex2_temperature.yaml`:** ה-variant האחרון אמור להיכשל ב-400. זה חלק מהתרגיל. כאן 10 חזרות, כי המדד הוא distinct (כמה תשובות שונות), וצריך הרבה דגימות כדי לראות פיזור.
3. **תרגיל 3, `experiments/ex3_effort.yaml`:** השווה pass מול out_tok ו-p50. יש בו 15 בעיות: 10 קלות (l01–l10) ו-5 קשות (h01–h05). על הקלות שתי רמות ה-effort צפויות להצליח כמעט תמיד, ולכן רק הקשות יכולות להראות מה effort גבוה קונה. 15 × 3 חזרות × 2 variants = 90 קריאות.
4. **תרגיל 4, `experiments/ex4_hr_system.yaml`:** כתוב את הפרומפט שלך ב-`prompts/hr_system_mine.md`. הקובץ מגיע עם שורת פתיחה ו-TODO שמפרט מה לכסות.
5. **תרגיל 5, `experiments/ex5_injection.yaml`:** מסמך "מורעל" ב-`prompts/hr_policies_poisoned.md`. שלושה variants, וכל אחד מוסיף דבר אחד על הקודם: בלי מבנה, אחר כך רק תגיות `<documents>`, ואחר כך תגיות וגם כלל מפורש ב-system. כאן 5 חזרות ולא 3, כי דליפה היא אירוע נדיר, ועם יותר חזרות יש יותר סיכוי לראות אותה.
6. **תרגיל 6, `experiments/ex6_fewshot.yaml` + `promptfoo/`:** שים לב לשורת `outputs` מתחת לטבלה.
7. **תרגיל 7, מזכר החלטה:** חצי עמוד, עם המספרים מתרגיל 6.

**כמה חזרות:** ברוב התרגילים 3 חזרות לכל מקרה. זה המינימום שבו אפשר לראות שהמודל לא עקבי, והוא שומר על עלות של סנטים. בפרודקשן, כשההחלטה חשובה, כדאי 5 ומעלה. תרגילים 2 ו-5 משתמשים ביותר חזרות מהסיבות שכתובות לידם.

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

לפני כל ריצה בתשלום, `promptlab run` מדפיס תוכנית: כמה קריאות לכל variant, והערכה של המקרה הגרוע (טוקני הפרומפט לפי תווים חלקי 4, וכל תשובה באורך המלא של `max_tokens`). הוא שואל `Run it? [y/N]`, ומסרב לרוץ אם ההערכה עוברת את `--max-cost` (ברירת מחדל: דולר אחד). `--yes` מדלג על השאלה, אבל לא על התקרה. מודלים מקומיים (Ollama) נספרים כחינם ולא נשאלים. ההערכות לתרגילים, בערך: 2 עד 36 סנט כל אחד, והמחיר האמיתי נמוך מהן בדרך כלל, כי רוב התשובות קצרות מ-`max_tokens`.
