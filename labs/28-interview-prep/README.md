# מעבדה 28: הכנה לראיונות טכניים ל-AI Engineer

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

המעבדה הזו שונה מהקודמות: חלק ממנה הוא קוד (שלושה תרגילים ב-`mine.py`), וחלק הוא אימון. האימון הוא העיקר. ראיון הוא מיומנות של דיבור בקול תחת לחץ זמן, ולכן כל תרגיל אימון כאן נעשה בקול, עם שעון, ועדיף עם הקלטה.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/28-interview-prep/requirements.txt
python -m pytest -q                                   # בדיקות הסביבה, כולל interviewkit מול השרת המדומה
python -m pytest -q labs/28-interview-prep/tests      # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

## מה חדש

- **`interviewkit/`**: חבילה חדשה בשורש הריפו.
  - `bank.py`: טעינה וולידציה של בנק השאלות, ושמות 12 הקטגוריות.
  - `rubric.py`: ניקוד תשובה מול rubric בלי LLM (גרסת הייחוס לתרגיל 2).
  - `srs.py`: חזרה מרווחת בסגנון SM-2 (גרסת הייחוס לתרגיל 3).
  - `aicoding.py`: top-k cosine וקיצוץ היסטוריה לתקציב טוקנים (גרסת הייחוס לתרגיל 6).
  - `interviewer.py`: מראיין ומדרג מעל llmkit. המראיין מחליט בכל תור, עם structured output, אם לשאול שאלת המשך או לסיים. המדרג נותן לכל נקודה ב-rubric החלטה בינארית עם ציטוט, והציון מחושב בקוד מהמשקלים.
- **`data/question_bank.jsonl`**: 84 שאלות ב-12 קטגוריות, בעברית עם מונחים באנגלית. לכל שאלה:
  - `q`: השאלה, ו-`level`: junior, mid או senior.
  - `answer`: תשובת ייחוס, כמו שמועמד חזק היה עונה.
  - `rubric`: 4 עד 7 נקודות שמראיין מקשיב להן. לכל נקודה משקל, וקבוצות של מושגים נרדפים (`concepts`).
  - `follow_ups` ו-`red_flags`: שאלות המשך טיפוסיות, וסימנים שמראיין רואה כבעייתיים.
- **`bank_tool.py`**: סטטיסטיקה, הצגת שאלות, ולידציה, ותרגול יומי עם SM-2.
- **`mock_interview.py`**: ראיון מדומה. Claude שואל, שואל שאלות המשך, ומדרג. יש מצב offline חינמי מול mockllm.
- **`design_check.py`** ו-**`system_design/`**: תרגיל system design של 45 דקות, צ'קליסט של 20 נקודות, תשובה חזקה ותשובה חלשה לדוגמה.
- **`present/`**: תבנית להצגת פרויקט בחמש דקות, קובצי התחלה לשלושת פרויקטי הסיום, ותבנית STAR.

## התרגילים

**1. מפת הראיון ובנק השאלות (אימון, 30 דקות).** הרץ את הסטטיסטיקה, ואז בחר שלוש קטגוריות שאתה מרגיש בהן הכי חלש. לכל אחת, הצג שאלה אחת **בלי** התשובה, ענה עליה בקול תוך שתי דקות (הקלט את עצמך בטלפון), ורק אז הצג אותה עם התשובה וה-rubric. כתוב לעצמך אילו נקודות ב-rubric פספסת.

```bash
python labs/28-interview-prep/bank_tool.py stats
python labs/28-interview-prep/bank_tool.py show --category evals --n 1 --seed 7
python labs/28-interview-prep/bank_tool.py show --id eval-02 --answers
```

**2. rubric scorer (קוד).** ממש את `term_in` ואת `score_answer` ב-`mine.py`. הנקודה החשובה: הניקוד הזה בודק **כיסוי של מושגים**, לא הבנה. אחת הבדיקות מראה ש"סלט מילים" מקבל כיסוי מלא, וזו בדיוק הסיבה שהמדרג ב-LLM דורש ציטוט לכל נקודה. אחרי שהבדיקות עוברות, ענה בכתב על שאלה מהבנק ובדוק את עצמך בתרגיל 3.

```bash
python -m pytest -q labs/28-interview-prep/tests/test_ex2_rubric.py
```

**3. חזרה מרווחת (קוד ואימון).** ממש את `sm2_review`, `grade_from_score` ו-`pick_session`. כשהבדיקות עוברות, התחל תרגול יומי של עשר דקות: `drill` בוחר שאלות שהגיע זמנן ועוד כמה חדשות, מנקד את התשובה שלך עם ה-scorer שכתבת, מראה את התשובה וה-rubric, ושואל אותך כמה טוב ענית (0 עד 5). המצב נשמר ב-`results/srs_state.json`.

```bash
python -m pytest -q labs/28-interview-prep/tests/test_ex3_srs.py
python labs/28-interview-prep/bank_tool.py drill --new 5 --limit 10
python labs/28-interview-prep/bank_tool.py due
```

**4. ראיון מדומה (אימון).** קודם הרץ offline, כדי לראות את הזרימה בלי לשלם: השורות של המראיין יהיו "example", כי השרת המדומה מחזיר אובייקט לדוגמה. אחר כך שלושה ראיונות אמיתיים מול Haiku 5.5: אחד ב-RAG, אחד ב-evals, ואחד באנגלית. בסוף כל ראיון תקבל ציון מה-LLM (לפי נקודות ה-rubric שהוא מצא להן ציטוט), ציון מילולי מה-scorer שלך, משוב בעברית, ועדכון של SM-2. השווה את שני הציונים: פער גדול ביניהם הוא בדיוק המקום ללמוד ממנו.

```bash
python labs/28-interview-prep/mock_interview.py --offline --id rag-02
python labs/28-interview-prep/mock_interview.py --category rag
python labs/28-interview-prep/mock_interview.py --category evals --followups 3
python labs/28-interview-prep/mock_interview.py --lang en --category system_design
```

**5. system design בזמן (אימון, 45 דקות ועוד 15 לבדיקה).** קרא את `system_design/ticket_triage.md`: המשימה, הנתונים שמראיין היה נותן אם היית שואל, ומה להגיש. כתוב את התשובה בקובץ markdown תוך 45 דקות, לפי תשעת הסעיפים של המסגרת. אחר כך הרץ את הבדיקה, ורק אז קרא את `model_answer.md`. לפני כן, כדאי להריץ את הבדיקה על `weak_answer.md` כדי לראות איך נראית תשובה שמפספסת כמעט הכל.

```bash
python labs/28-interview-prep/design_check.py prompt
python labs/28-interview-prep/design_check.py check labs/28-interview-prep/results/my_design.md
python labs/28-interview-prep/design_check.py check labs/28-interview-prep/results/my_design.md --llm
```

**6. סבב coding טיפוסי ל-AI (קוד, 30 דקות עם שעון).** ממש את `top_k_cosine` ואת `fit_to_budget`. אלה שאלות אמיתיות מראיונות: הן נראות פשוטות, והציון נקבע במקרי הקצה (וקטור אפס, k גדול מ-n, שוויון ציונים, הודעת system, תחילת שיחה בהודעת assistant). תרגל כמו בראיון: לפני שאתה כותב קוד, אמור בקול את הגישה ואת מקרי הקצה, ורק אז כתוב. מדוד את הזמן.

```bash
python -m pytest -q labs/28-interview-prep/tests/test_ex6_aicoding.py
```

**7. להציג פרויקט (אימון).** קרא את `present/project_template.md` ואת `present/star_stories.md`. מלא את `present/company_brain.md` עם מה שכבר יש לך (את המספרים תשלים בפרויקט הסיום), והכן שני סיפורי STAR. הצג את הפרויקט בקול עם שעון של חמש דקות, ואז תן ל-Claude לחקור אותך עליו. חזור על זה עם שני הפרויקטים האחרים כשתסיים אותם.

```bash
python labs/28-interview-prep/mock_interview.py --project labs/28-interview-prep/present/company_brain.md --title "Company Brain"
```

## כללים ועלויות

- ראיון מדומה אחד מול Haiku 5.5 הוא 3 עד 5 קריאות, בערך 5,000 עד 10,000 טוקנים, ועולה פחות מסנט. בדיקת system design עם `--llm` היא קריאה אחת, גם היא פחות מסנט.
- כל הבדיקות האוטומטיות רצות מול השרת המדומה ולא עולות כלום.
- את קוד הייחוס ב-`interviewkit/` אל תקרא לפני שהבדיקות שלך עוברות.
- התשובות שלך והתמלילים נשמרים ב-`results/`, שלא נכנס ל-git.
