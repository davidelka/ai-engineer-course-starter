# מעבדה 6: Spec-Driven Development

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

במעבדה הזו אתה לוקח פיצ'ר אמיתי של Company Brain, **API של בקשות גישה**, ועובר איתו את כל הדרך: מכוונה ארכיטקטונית, דרך מפרט עם דרישות ממוספרות וקריטריוני קבלה, חוזה ממשק ב-OpenAPI, ועד מימוש שסוכן קוד כותב מהמפרט בלבד. בדרך אתה בונה את הכלים שהופכים מפרט למשהו שאפשר לבדוק אוטומטית: linter למפרט, מטריצת traceability מדרישה לבדיקה, ובדיקת drift בין החוזה לקוד.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/06-spec-driven/requirements.txt
python -m pytest -q                                   # בדיקות הסביבה, כולל tests/test_spectools.py
python -m pytest -q labs/06-spec-driven/acceptance    # בדיקות הקבלה מול המימוש לדוגמה: כולן עוברות
python -m pytest -q labs/06-spec-driven/tests         # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

## מדיניות הגישה של Acme, בקיצור

הפיצ'ר מממש את `data/acme/saas_access_policy.md` (גרסה 2.1). כל בקשה הולכת לאחד משלושה מסלולים, והמחמיר מנצח (needs_security, אחריו needs_manager, אחריו auto_approve):

- **auto_approve:** כלי מהרשימה המאושרת (Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma, GitHub), גישת קריאה או חשבון רגיל, בלי מידע של לקוחות ובלי מידע פיננסי. מאושר מיד.
- **needs_manager:** חשבון בתשלום בכלי מאושר, כלי שלא ברשימה אבל בלי מידע רגיש, או הרשאת כתיבה למשאב של צוות. המנהל הישיר מאשר.
- **needs_security:** הרשאות admin, תשתית פרודקשן (AWS, GCP, Kubernetes), מידע של לקוחות, מערכות פיננסיות (NetSuite, payroll), או שיתוף חיצוני. צוות האבטחה מאשר.

## מה יש בתיקייה

- **`spec/TEMPLATE.md`**: תבנית למפרט, עם הסבר על כל סעיף ועל הפורמט שה-linter קורא.
- **`spec/access-requests.spec.md`**: המפרט המלא, SPEC-006. אחת-עשרה דרישות פונקציונליות (REQ-1 עד REQ-11) ושתי דרישות לא-פונקציונליות (NFR-1, NFR-2), כל אחת עם משפט בצורת EARS וקריטריוני קבלה בצורת GIVEN/WHEN/THEN. אחריהן: אילוצים, מה מחוץ לתחום, שאלות פתוחות, תוכנית, משימות ופקודת אימות.
- **`spec/openapi.yaml`**: חוזה הממשק. ארבע פעולות: יצירה, רשימה, שליפה לפי id, ואישור. הוא מקור האמת לנתיבים, לשדות, לטיפוסים ולקודי הסטטוס.
- **`spec/draft-vague.spec.md`**: טיוטה גרועה בכוונה, לתרגיל 1.
- **`reference/`**: מימוש לדוגמה ב-FastAPI. אל תראה אותו לסוכן בתרגיל 6.
- **`acceptance/`**: בדיקות הקבלה, כל אחת מסומנת `@pytest.mark.req("REQ-n")`. כל תשובה שעוברת דרך ה-fixture `client` נבדקת מול החוזה עם **openapi-core**, ו-`test_acc_nfr.py` מריץ את **Schemathesis**, שמייצר בקשות מתוך החוזה. משתנה הסביבה `ACCESS_APP` בוחר מול איזה מימוש הן רצות: `reference`, `impl`, או `module:factory`.
- **`impl/`**: ריק. כאן Claude Code יכתוב את המימוש שלו בתרגיל 6.
- **`drift/scenarios.py`**: ארבעה שינויי קוד בלי שינוי במפרט, לתרגיל 5.
- **`spectools/`** (בשורש הריפו): parser למפרט, linter, traceability, השוואת חוזים, וסקירת מפרט עם LLM. אלה גרסאות הייחוס לתרגילים.
- **`mine.py`**: הקוד שלך לתרגילים 2, 3 ו-5.

## התרגילים

**1. אנטומיה של מפרט, ומה הופך דרישה לבדיקה.** קרא את `spec/TEMPLATE.md` ואת `spec/access-requests.spec.md` (מספיק לעבור על סעיפים 3 ו-5 עד 9). אחר כך הרץ את ה-linter לדוגמה על הטיוטה הגרועה, ושכתב אותה לקובץ חדש `spec/my-rewrite.spec.md` עד שה-linter נקי. שים לב: linter נקי הוא תנאי הכרחי, לא מספיק. דרישה יכולה לעבור את ה-linter ועדיין להיות עמומה, ונחזור לזה בתרגיל 7.

```bash
python labs/06-spec-driven/spec_lint.py labs/06-spec-driven/spec/draft-vague.spec.md --reference
python labs/06-spec-driven/spec_lint.py labs/06-spec-driven/spec/my-rewrite.spec.md --reference
```

**2. Linter למפרט.** ממש את `lint_spec` ב-`mine.py`: מזהים חסרים או כפולים, משפט שאינו בצורת EARS, מילים חלשות כמו should, מילים עמומות מהרשימה `VAGUE_WORDS`, דרישה לא-פונקציונלית בלי מספר, וקריטריון שאינו GIVEN/WHEN/THEN.

```bash
python -m pytest -q labs/06-spec-driven/tests/test_ex2_lint.py
python labs/06-spec-driven/spec_lint.py labs/06-spec-driven/spec/draft-vague.spec.md
```

**3. מטריצת traceability.** ממש את `scan_req_markers` (קריאה סטטית של קובצי הבדיקות עם `ast`) ואת `build_matrix`. אחר כך הרץ את המטריצה עם תוצאות. דרישה אחת על אישורים מסומנת UNTESTED: מצא אותה במפרט, כתוב לה בדיקות לפי שני קריטריוני הקבלה שלה ב-`acceptance/test_acc_approve.py` עם ה-marker הנכון, והרץ שוב.

```bash
python -m pytest -q labs/06-spec-driven/tests/test_ex3_trace.py
python labs/06-spec-driven/trace_matrix.py --run
```

**4. חוזה ובדיקת חוזה.** קרא את `spec/openapi.yaml`. הרץ את בדיקת החוזה של Schemathesis מול המימוש לדוגמה, פעם עם ה-seed הקבוע ופעם עם קלטים אקראיים ויותר דוגמאות. אחר כך קרא ב-`reference/app.py` את שלוש ההערות שמתחילות ב-"Found by": אלה באגים אמיתיים שבדיקת החוזה מצאה במימוש לדוגמה בזמן שבניתי את המעבדה. ענה: למה בדיקה שנטענת מ-`from_asgi` (הסכמה שהאפליקציה מייצרת על עצמה) לא הייתה מוצאת אף אחד מהם?

```bash
python -m pytest -q labs/06-spec-driven/acceptance/test_acc_nfr.py -k contract
CONTRACT_RANDOM=1 CONTRACT_EXAMPLES=500 python -m pytest -q labs/06-spec-driven/acceptance/test_acc_nfr.py -k contract
python labs/06-spec-driven/serve.py --app reference      # ואז curl, לפי הדוגמאות בראש serve.py
```

**5. Spec drift.** ממש את `find_drift`: השוואה בין החוזה לבין ה-OpenAPI שהקוד מייצר על עצמו. אחר כך הרץ את ארבעת התרחישים, וראה איזו רשת תופסת כל אחד. בתרחיש האחרון אף רשת לא תופסת כלום. הוסף למפרט קריטריון קבלה שהיה תופס אותו (AC-4.8), כתוב לו בדיקה, והרץ את התרחיש שוב.

```bash
python -m pytest -q labs/06-spec-driven/tests/test_ex5_drift.py
python labs/06-spec-driven/drift_demo.py --all
```

**6. סוכן מממש מהמפרט (חי).** פתח את `IMPLEMENT_PROMPT.md` ועקוב אחרי שני החלקים. בחלק א' Claude Code מקבל רק את המפרט ואת החוזה, בלי לראות את בדיקות הקבלה ואת ה-grader, ואתה מדרג את התוצאה. בחלק ב' הוא מקבל את ה-grader ומתקן עד שהכול ירוק. רשום: כמה דרישות עברו בחלק א', מה נכשל ולמה, ומה כתוב ב-`impl/DECISIONS.md`.

```bash
python labs/06-spec-driven/grade.py --app reference     # כך נראית תוצאה טובה
python labs/06-spec-driven/grade.py --app impl          # אחרי שהסוכן סיים
```

**7. סקירת מפרט עם LLM.** הרץ קודם במצב offline, שבו mockllm מחזיר תשובה שנכתבה ביד (לא הקלטה של מודל) כדי לראות את הצנרת ואת ה-grounding, שזורק ממצאים עם ציטוט שלא קיים במפרט. אחר כך הרץ חי על Haiku 5.5. השווה למה שה-linter מצא: מה המודל מוצא שה-linter לא יכול, ומה הוא ממציא? תקן במפרט ממצא אחד שאתה מסכים איתו.

```bash
python labs/06-spec-driven/spec_review.py --offline --show-dropped
python labs/06-spec-driven/spec_review.py --model anthropic:claude-haiku-5-5
python labs/06-spec-driven/spec_review.py --spec labs/06-spec-driven/spec/draft-vague.spec.md
```

**8. בקשת שינוי: דחיית בקשה.** הוסף את היכולת לדחות בקשה, מקצה לקצה ובסדר הנכון: דרישה חדשה REQ-12 במפרט עם קריטריוני קבלה (והסר את "Rejecting" מ-Out of scope), נתיב `POST /access-requests/{request_id}/reject` וסטטוס `rejected` בחוזה, בדיקות קבלה עם `@pytest.mark.req("REQ-12")`, ורק אז Claude Code מממש ב-`impl/`. הרץ את ה-linter, את המטריצה ואת ה-grader. בסוף, כתוב שתי שורות: כמה זמן הלך על המפרט לעומת המימוש, והאם בשינוי בגודל הזה SDD היה שווה את זה.

```bash
python labs/06-spec-driven/spec_lint.py --reference
python labs/06-spec-driven/trace_matrix.py --reference --run --app impl --tests acceptance impl/tests
python labs/06-spec-driven/grade.py --app impl
```

## כללים

- הכלים שבונים כאן הם כלי פיתוח רגילים ולא קוראים ל-LLM, חוץ מתרגיל 7 (וכמובן Claude Code בתרגילים 6 ו-8). הרצה חיה של `spec_review.py` שולחת בערך 7,000 עד 8,000 טוקנים ועולה בערך עשירית סנט על Haiku 5.5.
- את קוד הייחוס ב-`spectools/` אל תקרא לפני שהבדיקות שלך עוברות.
- `grade.py` משתמש בגרסאות הייחוס של `spectools` כדי שהציון לא יהיה תלוי בקוד התרגילים שלך. עם `--mine` הוא משתמש בשלך.
