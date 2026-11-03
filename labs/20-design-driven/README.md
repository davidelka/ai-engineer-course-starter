# מעבדה 20: Design-Driven Development

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

במרכז המעבדה יש קובץ אחד מסובך בכוונה: `legacy/tangled.py`. זה שירות התשובות של Company Brain בגרסה 0: פונקציה אחת, `answer_question`, שעושה הכל. היא כותבת לוג, קוראת ומעדכנת cache בקובץ, בודקת מדיניות, קוראת את מסמכי Acme מהדיסק בכל שאלה, מחפשת, בונה פרומפט, יוצרת בעצמה `LLM` של llmkit, מפרסרת ציטוטים ושומרת. במעבדה תפרק אותה ל-ports ול-adapters, תכתוב לשירות החדש בדיקות שלא צריכות רשת, תכתוב בדיקות חוזה שכל adapter חייב לעבור, ותתרגל את שאר הכלים של תכנון ברמת הרכיב: גרסאות לפרומפטים ולסכמות, sequence diagram, ו-design review.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/20-design-driven/requirements.txt   # coverage
python -m pytest -q                                   # בדיקות הסביבה, כולל tests/test_design.py
python -m pytest -q labs/20-design-driven/tests       # התרגילים שלך: בהתחלה רובן נכשלות, וזה תקין
```

## מה חדש

- **`designkit/`**: חבילה חדשה בשורש הריפו, עם הקוד של השיעור:
  - `types.py`: טיפוסי הדומיין (`Passage`, `Completion`, `AnswerRequest`, `Answer`, `PromptVersion`) וחוזה השגיאות (`ModelUnavailable` זמני, `ModelRejected` קבוע, `RetrieverUnavailable`). זה החלק **הנתון** של התכנון, ואתה משתמש בו כמו שהוא.
  - `domain.py`: כללים עסקיים טהורים, בלי I/O: `policy_check`, `rank`, `build_prompt`, `parse_citations`, `degraded_text`, ו-`ANSWER_PROMPT_V1`.
  - `adapters.py`: ה-adapters האמיתיים. `LlmkitChatModel` עוטף את llmkit ומתרגם את `LLMError` לחוזה השגיאות. `KeywordRetriever` טוען את מסמכי Acme פעם אחת. `JsonlAnswerStore` שומר לקובץ. `SystemClock` מחזיר את השעה.
  - פתרונות ייחוס: `ports.py`, `fakes.py`, `service.py`, `contract.py`, `registry.py`, `sqlite_store.py`, `reference/access_request_sequence.mmd`, `review_key.py`. אל תפתח אותם לפני שהבדיקות שלך עוברות.
- **`legacy/tangled.py`** והבדיקות שלו ב-`legacy/tests/`: נקודת ההתחלה. שים לב: כשמריצים אותו הוא כותב `brain.log` לתיקייה הנוכחית ו-cache ל-`~/.cache/company_brain/`. גם זה חלק מהבעיה. מחק אותם בסוף.
- **`after_tests/test_scenarios.py`**: אותם תרחישים, אחרי הפירוק, עם fakes.
- **`measure.py`**: מריץ pytest תחת coverage.py עם מדידת branches, ומדווח זמן, הבדיקות האיטיות, וכיסוי של הפונקציה או המחלקה הנבדקת בלבד.
- **`prompts_catalog.py`**: היסטוריית הגרסאות של פרומפט התשובה, עם סכמת פלט לכל גרסה.
- **`designs/`**: מסמך תכנון עם פגמים (`answer_service_v2.md`), צ'קליסט (`review_checklist.md`), קובץ ה-review שלך, קובץ Mermaid להשלמה, ומשימה לסוכן קוד (`adapter_task.md`).
- **`mine.py`**: הקוד שלך לתרגילים 2, 3, 4 ו-6.

## התרגילים

**1. למדוד לפני.** קרא את `legacy/tangled.py` מההתחלה ועד הסוף, וסמן לעצמך לכל קטע לאיזה port עתידי הוא שייך: model, retriever, store, clock, או "לוגיקה עסקית שנשארת בפנים". אחר כך קרא את `legacy/tests/test_tangled.py` וספור כמה monkeypatch צריך כדי לבדוק אותו. הרץ את המדידה ושמור את המספרים: זמן, הבדיקה האיטית ביותר, כיסוי שורות ו-branches.

```bash
python labs/20-design-driven/measure.py --before
```

**2. Ports ו-fakes.** ב-`mine.py`, הגדר את ארבעת ה-ports כ-`typing.Protocol` עם `@runtime_checkable`, וממש fake לכל אחד. הבדיקות בודקות גם שה-adapters האמיתיים מ-`designkit/adapters.py` עונים על ה-Protocols שלך בלי לרשת מהם.

```bash
python -m pytest -q labs/20-design-driven/tests/test_ex2_ports.py
```

**3. השירות מול ports, ו-composition root.** ממש את `AnswerService` לפי הסדר שכתוב ב-docstring. הבדיקות משתמשות ב-fakes של הייחוס, כדי שבאג ב-fakes שלך לא יסתיר באג בשירות. אחר כך:
- הרץ את `answer_demo.py`. זה ה-composition root: המקום היחיד שיודע אילו adapters קיימים. הרץ עם `--model fake`, אחר כך עם mockllm, ואם תרצה עם Claude אמיתי. החלפת ספק היא שינוי של דגל אחד.
- הרץ את המדידה אחרי, והשווה לתרגיל 1.

```bash
python -m pytest -q labs/20-design-driven/tests/test_ex3_service.py
python labs/20-design-driven/answer_demo.py "How many vacation days do I get in my first year?"
python -m mockllm --reply "14 days [vacation_policy.md]."       # טרמינל 2
python labs/20-design-driven/answer_demo.py "How many vacation days do I get in my first year?" --model mock:mock-model
python labs/20-design-driven/answer_demo.py "How many vacation days do I get in my first year?" --model anthropic:claude-haiku-5-5
python labs/20-design-driven/measure.py --both
```

**4. בדיקות חוזה.** כתוב ב-`mine.py` שלוש מחלקות בדיקה לשימוש חוזר: `ChatModelContract`, `RetrieverContract`, `AnswerStoreContract`. קובץ הבדיקות יורש מהן פעם אחת לכל adapter: ה-fakes שלך, `LlmkitChatModel` מול mockllm, `KeywordRetriever` ו-`JsonlAnswerStore`. אחר כך הוא מריץ את החוזה שלך מול שבעה adapters שבורים בכוונה, וכל אחד מהם חייב להיכשל לפחות בבדיקה אחת שלך.

```bash
python -m pytest -q labs/20-design-driven/tests/test_ex4_contract.py
BRAIN_LIVE_MODEL=anthropic:claude-haiku-5-5 python -m pytest -q labs/20-design-driven/tests/test_ex4_contract.py -k Live
```

**5. סוכן קוד מממש adapter מתוך החוזה.** פתח את Claude Code בשורש הריפו, ותן לו את `designs/adapter_task.md` כמשימה. המשימה מפנה ל-port, לחוזה שכתבת בתרגיל 4, ול-adapter קיים לדוגמה. הסוכן צריך לכתוב `labs/20-design-driven/sqlite_store.py` ולהריץ את הבדיקה. שים לב כמה מעט הסברים הוא צריך, ולמה.

```bash
claude "Implement the task in labs/20-design-driven/designs/adapter_task.md"
python -m pytest -q labs/20-design-driven/tests/test_ex5_agent_adapter.py
```

**6. גרסאות לפרומפטים ולסכמות.** ממש את `check_compatible` ואת `PromptRegistry` ב-`mine.py`. קרא קודם את ה-docstring של `prompts_catalog.py`: הוא מספר את ההיסטוריה של פרומפט התשובה, ואיזה שינוי שובר את מי.

```bash
python -m pytest -q labs/20-design-driven/tests/test_ex6_registry.py
python labs/20-design-driven/registry_demo.py
```

**7. Sequence diagram לתהליך אישור הגישה.** השלם את `designs/access_request_sequence.mmd`. כל מה שצריך לדעת על התהליך כתוב בהערות שבראש הקובץ, כולל שלושת המסלולים של Acme. הבודק מוודא את כללי התכנון, ונותן קישור ל-mermaid.live כדי לראות את הדיאגרמה.

```bash
python labs/20-design-driven/check_sequence.py
python -m pytest -q labs/20-design-driven/tests/test_ex7_sequence.py
```

**8. Design review.** קרא את `designs/answer_service_v2.md` עם `designs/review_checklist.md` לידו, וכתוב את הממצאים שלך ב-`designs/my_review.yaml`: סעיף, פריט בצ'קליסט, הבעיה, והתיקון. יש במסמך שמונה בעיות מתוכננות, וגם סעיפים שנראים חשודים ובסדר גמור.

```bash
python labs/20-design-driven/check_review.py
python -m pytest -q labs/20-design-driven/tests/test_ex8_review.py
python labs/20-design-driven/check_review.py --reveal          # רק בסוף
```

## כללים

- רוב המעבדה חינמית: fakes, mockllm וקבצים זמניים. הקריאות בתשלום הן רק ב-`answer_demo.py` עם מודל אמיתי ובמחלקה `Live` של תרגיל 4: כמה קריאות של Haiku 5.5, פחות מסנט אחד בסך הכל.
- תרגיל 5 משתמש ב-Claude Code, ועולה כמו כל סשן קצר שלו.
- את פתרונות הייחוס ב-`designkit/` אל תקרא לפני שהבדיקות שלך עוברות.
