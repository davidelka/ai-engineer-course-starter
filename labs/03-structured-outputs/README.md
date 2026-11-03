# מעבדה 3: Structured Outputs and Validation

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt
python -m pytest -q                                   # בדיקות הסביבה, כולל llmkit.structured מול השרת המדומה
python -m pytest -q labs/03-structured-outputs/tests  # התרגילים שלך: בהתחלה רובן נכשלות, וזה תקין
```

## מה חדש

- **`llmkit/structured.py`**: הפונקציה `complete_structured(llm, text, Model)` מחזירה אובייקט Pydantic תקין, או זורקת `StructuredError` עם השלב שבו זה נכשל (`refusal`, `truncated`, `invalid`). בפנים יש שלוש שכבות:
  - מצב native של כל ספק (constrained decoding).
  - ולידציה של Pydantic מול המודל המקורי.
  - לולאת תיקון ששולחת למודל את השגיאות. ברירת המחדל היא עד 2 תיקונים.
- **`provider_schema(Model, provider)`**: ממיר מודל Pydantic לסכמה שכל ספק מקבל:
  - `additionalProperties: false` בכל אובייקט.
  - כל השדות מסומנים כ-required. שדה אופציונלי נשאר nullable.
  - מילות מפתח שהספק לא תומך בהן עוברות לתיאור של השדה.
- **`mockllm`**: כשבבקשה יש סכמה, השרת המדומה מחזיר אובייקט לדוגמה שנבנה ממנה. עם `--json-fault` הוא שובר אותו בדרך אחת מוגדרת:
  - `fence`, `prose`, `truncated`
  - `missing_field`, `wrong_type`, `bad_enum`, `extra_field`, `out_of_range`
  - `--json-fault-first N` שובר רק את N הבקשות הראשונות, ו-`--json-fault-rate` שובר בהסתברות.
- **`acme_schema.py`**: המודל `AccessRequest` ופרומפט החילוץ.
- **`data/acme/access_requests.jsonl`**: 16 בקשות גישה עם תשובה נכונה לכל שדה.
- **`data/acme/access_requests_hard.jsonl`**: 8 מקרים קשים: עברית, מידע חסר, injection, תיקון עצמי, משך יחסי, שתי בקשות בהודעה, מספר במילים ומייל באותיות גדולות.
- **`mine.py`**: הקוד שלך לתרגילים 3, 4 ו-5.

## התרגילים

**1. סכמה מקורית בלי SDK.** שלח בקשה עם סכמה ל-Claude, וראה איפה הסכמה יושבת בבקשה ומה חוזר. אחר כך:
- הרץ עם `--twice` והשווה זמנים. הקריאה הראשונה עם סכמה חדשה כוללת קומפילציה של הדקדוק.
- הרץ עם `--bad-schema`. הדגל מוסיף לסכמה בכוונה מילת מפתח שהתיעוד של Anthropic מסמן כלא נתמכת (`minLength`). יש שלוש תוצאות אפשריות: 400 (הספק דוחה), 200 עם אכיפה, או 200 בלי אכיפה (הספק מקבל ומתעלם). בבדיקה החיה בנובמבר 2026 Claude החזיר 200 על `minLength`. כדי לדעת אם הוא אוכף או מתעלם, הרץ גם `--bad-schema minlength40`: אם `tool` חוזר קצר מ-40 תווים, המילה התקבלה ולא נאכפה. נסה גם `pattern` ו-`addprops`, וכתוב מה כל אחד מחזיר.

```bash
python labs/03-structured-outputs/raw_structured.py --twice
python labs/03-structured-outputs/raw_structured.py --bad-schema
python labs/03-structured-outputs/raw_structured.py --bad-schema minlength40
python labs/03-structured-outputs/raw_structured.py --bad-schema pattern
python labs/03-structured-outputs/raw_structured.py --bad-schema addprops
python labs/03-structured-outputs/raw_structured.py --provider openai --show-body
```

**2. מה הספק לא אוכף.** הרץ, וענה: אילו אילוצים מהמודל לא נאכפים אצל Claude, ואילו לא נאכפים אצל Gemini? מי אוכף אותם עכשיו?

```bash
python labs/03-structured-outputs/schema_inspect.py
```

**3. למצוא את ה-JSON.** ממש את `extract_json` ב-`mine.py`.

```bash
python -m pytest -q labs/03-structured-outputs/tests/test_ex3_extract.py
```

**4. שגיאות שהמודל יכול לתקן.** ממש את `format_errors`. אחרי שהבדיקות עוברות, הרץ את לולאת התיקון עם הפונקציות שלך מול כל סוג תקלה:

```bash
python -m pytest -q labs/03-structured-outputs/tests/test_ex4_errors.py
python -m mockllm --json-fault bad_enum --json-fault-first 1      # טרמינל 2
python labs/03-structured-outputs/repair_demo.py
```

**5. כללים שסכמה לא יכולה לבטא.** הוסף validators ל-`MyAccessRequest`:
- נרמול של המייל.
- גישת admin, פרודקשן, מידע של לקוחות או מידע פיננסי מחייבים `needs_security`.
- `auto_approve` מותר רק לגישת קריאה או לחשבון רגיל.

```bash
python -m pytest -q labs/03-structured-outputs/tests/test_ex5_rules.py
```

**6. Eval.** השווה מצב native למצב prompt על Haiku 5.5, ואם תרצה גם על GPT-5.4-mini. שים לב לשלושה דברים: כמה אובייקטים יצאו תקינים בניסיון הראשון, הדיוק בכל שדה, והעלות.

```bash
python labs/03-structured-outputs/extract_eval.py --model anthropic:claude-haiku-5-5
python labs/03-structured-outputs/extract_eval.py --model anthropic:claude-haiku-5-5 --mode prompt
```

**7. קלטים קשים.** הרץ את הסט הקשה עם `--show`, ומצא לכל כישלון מה גרם לו: הסכמה, הפרומפט או המודל. תקן דבר אחד, הרץ שוב, ותכתוב לי מה השתנה.

```bash
python labs/03-structured-outputs/extract_eval.py --set hard --schema mine --show
```

## כללים

- הרצה מלאה של ה-eval על Haiku 5.5 היא 16 עד 24 קריאות, ועולה פחות מסנט. תרגיל 6 בשני המצבים ובשני הספקים עולה כמה סנטים.
- את קוד הייחוס ב-`llmkit/structured.py` אל תקרא לפני שהבדיקות שלך עוברות.
