# פרויקט אמצע M1: Acme Knowledge Assistant

כל הפקודות רצות מתוך `projects/m1-knowledge-assistant/`, עם ה-venv של הריפו פעיל, אלא אם כתוב אחרת.

## על הפרויקט

**מה המערכת עושה.** Acme היא חברת תוכנה בדיונית עם כ-200 עובדים, ו-55 מסמכים פנימיים: נהלי משאבי אנוש, מדיניות IT, קטלוג השירותים של ההנדסה, postmortems של תקריות, מחירונים ועוד. עובד שרוצה לדעת כמה ימי חופשה מותר לו להעביר לשנה הבאה, מי אחראי על שירות מסוים, או מה קרה בתקרית של אוגוסט, צריך היום לחפש בתיקיות ולקוות שמצא את הגרסה העדכנית. בפרויקט הזה בונים **עוזר ידע**: העובד שואל בעברית או באנגלית, והמערכת עונה בכמה משפטים, עם מספר מקור ליד כל עובדה. לחיצה על המספר פותחת את המסמך בדיוק על הקטע שממנו נלקחה העובדה.

דוגמה לשיחה אחת:
- העובד, בתפקיד engineering, שואל: "How long was flow-api fully unavailable on August 19, 2026?"
- המערכת מחפשת במסמכים ומוצאת את ה-postmortem של התקרית. היא בוחרת ממנו את הקטעים הרלוונטיים, ועונה במשפט אחד עם הסימון [1].
- אותה שאלה מעובד בתפקיד employee מקבלת סירוב, כי ה-postmortem מסווג כחסוי, והוא לא אמור לדעת אפילו שהמסמך קיים.
- השאלה "כמה קריאות P1 פתוחות יש כרגע?" לא נשלחת בכלל למסמכים, כי התשובה לא כתובה באף מסמך. היא עוברת למסד הנתונים, והתשובה מגיעה משאילתת SQL.

**ארבע הדרישות שהופכות את זה לבעיה אמיתית:**
- **לענות רק מהמסמכים**, ולסרב ("not in the documents") כשהתשובה לא שם, במקום להמציא.
- **הרשאות:** כל תפקיד רואה רק את המסמכים שמותר לו, גם בחיפוש עצמו.
- **גרסאות:** יש גרסה ישנה וחדשה של אותה מדיניות, והתשובה צריכה להגיע מהחדשה.
- **מדידה:** ההחלטה אם המערכת טובה מתקבלת לפי מספרים על 79 שאלות זהב, ולא לפי שאלה אחת שנראתה טוב.

**המטרה בקורס.** זה פרויקט האמצע הראשון. הוא סוגר את שלב 2 (שיעורים 8 עד 13), ומחבר את כל מה שנבנה בשלב הזה למערכת אחת שעובדת מקצה לקצה. זה גם השלב הראשון של Company Brain, המערכת שהקורס כולו בונה: ב-F1, פרויקט הסיום, ה-Company Brain משתמש בעוזר שתבנה כאן, כמו שהוא.

**מה אתה בונה.** את החלקים שהשיעורים לימדו, שש פונקציות ב-`mine.py`:
- **שכבת החיפוש** (`build_retriever`, שיעורים 11 ו-12): הרכבה של חיפוש היברידי, סינון גרסאות ו-reranker לשכבה אחת, כשההרשאות רצות לפני הדירוג.
- **בחירת ההקשר** (`pack_context`, שיעורים 4 ו-13): אילו קטעים נכנסים לפרומפט, בלי כפילויות ובתוך תקציב טוקנים.
- **הפרומפט** (`build_request`, שיעורים 1, 4 ו-24): מבנה הבקשה למודל, עם החלק הקבוע ב-cache ועם הגנה מפני מסמך שמנסה לסגור את התגית שלו.
- **הציטוטים** (`resolve_citations`, שיעור 13): מ-"[2]" בתשובה לקטע מדויק במסמך, וזיהוי של מקור שהמודל המציא.
- **הנתב** (`route_question`, שיעור 8): האם שאלה הולכת למסמכים או למסד הנתונים.
- **מדדי ה-eval** (`answer_metrics`, שיעורים 13 ו-23): המספרים שקובעים אם המערכת טובה.

**מה מקבלים מוכן,** כי זה לא נושא הפרויקט: ה-ingestion (טעינה, chunking ואינדקס, משיעור 9), השירות ב-HTTP וה-UI, שורת הפקודה, מנוע ה-SQL של המסלול לנתונים (משיעור 8), ה-tracing, והקוד שמריץ את ה-eval ומדפיס את הדוח.

**התוצר בסוף.** שירות שרץ אצלך, עם דף בעברית שבו בוחרים תפקיד ושואלים. eval על 79 שאלות הזהב, עם אבחון של כל כשל: האם הוא קרה בחיפוש או ביצירה. שער רגרסיה ב-pytest. והרצה אחת מול מודל אמיתי, ב-5 עד 8 סנט, שאת התוצאות שלה אפשר להראות בראיון.

**איך עובדים.** לכל פונקציה יש ב-`mine.py` חוזה: מה היא מקבלת, מה היא מחזירה ומה היא חייבת להבטיח. לכל אבן דרך יש בדיקות ב-`tests/`. כל פקודה של `python -m acmeqa` משתמשת בפונקציות שלך, ופקודה שצריכה פונקציה שעוד לא כתבת עוצרת ואומרת איזו. נתקעת? ב-`HINTS.md` יש שלוש רמות רמז לכל פונקציה. קוד הייחוס נמצא בענף `solutions` של הריפו, להשוואה אחרי שהבדיקות שלך עוברות.

## מה עולה כסף, ומה לא

- **כמעט הכול חינם.** ברירת המחדל היא `MODE=offline`: embedder מזויף (HashingEmbedder, לקסיקלי ולא סמנטי), "עונה" חילוצי של ragkit (בוחר את המשפט הטוב ביותר מהמקורות, הוא לא מודל שפה), תוכניות SQL מוקלטות, ושופט groundedness לקסיקלי. כל אבני הדרך חוץ מ-9 רצות כך.
- **`MODE=mock`, גם חינם:** ה-adapter האמיתי של llmkit מול mockllm ב-HTTP. כך רואים streaming, ניסיונות חוזרים ו-prompt caching (שדות ה-cache ב-usage) בלי מפתח.
- **`MODE=live`, אבן דרך 9:** Claude Haiku 5.5 לתשובות, לתוכניות ה-SQL ולשופט, ו-e5-small מקומי ל-embeddings (הורדה חד פעמית של כ-470MB). ההערכה לפני הרצה, לפי `llmkit/pricing.py` (0.10$ למיליון טוקני קלט, 0.50$ לפלט): כ-2,300 טוקני קלט לשאלה, ולכן 79 תשובות עולות כ-2.5 סנט, השופט עוד כ-2.5 סנט, ו-16 שאלות הנתונים כסנט. **הרצה מלאה: בערך 5 עד 8 סנט, והתקרה שקבענו היא 0.20$.** הסכום האמיתי מודפס בסוף הריצה.

## הכנה

```bash
cd ~/ai-engineer-course-starter && source .venv/bin/activate
uv pip install -r projects/m1-knowledge-assistant/requirements.txt
python -m pytest -q                              # בדיקות הסביבה, כולל tests/test_m1_knowledge_assistant.py
cd projects/m1-knowledge-assistant
python -m pytest -q tests                        # אבני הדרך שלך: בהתחלה רובן נכשלות, וזה תקין
python -m acmeqa ingest                          # האינדקס: עובד כבר עכשיו, בלי קוד שלך
```

## מה יש בתיקייה

- **`acmeqa/`**: המערכת עצמה. החלקים שאתה כותב נקראים מ-`mine.py`, וכל השאר מוכן.
  - `config.py`: ההגדרות מהסביבה (MODE, EMBEDDER, RERANK, VERSION_MODE, TOP_K), והמפעלים של המודלים לכל מצב.
  - `ingest.py`: עבודת ה-ingestion. `IngestPipeline` של ragkit עם manifest (אינקרמנטלי: added, changed, unchanged, removed), אינדקס היברידי (BM25 ו-dense), ומאגר מסמכים (`docs.jsonl`) עם הטקסט הנקי שהציטוטים מצביעים לתוכו.
  - `retrieval.py`: ה-ACL לפי תפקיד, כמסנן שרץ לפני הדירוג. את שכבות החיפוש (RRF, סינון גרסאות ו-reranker) מרכיב `build_retriever` שלך (אבן דרך 3).
  - `context.py`: ההסבר למה צריך לבחור קטעים. את הבחירה עצמה כותבים ב-`pack_context` שלך (אבן דרך 4).
  - `citations.py`: המחלקה `Citation` וה-regex של הסימונים. את הפענוח כותבים ב-`resolve_citations` שלך (אבן דרך 5).
  - `answer.py`: הוראות המערכת (`SYSTEM`, כ-950 טוקנים), זיהוי סירוב, streaming, ושלושה "מודלים": llmkit, העונה החילוצי, והשמעה חוזרת של תשובות מוקלטות. את הבקשה עצמה בונה `build_request` שלך (אבן דרך 5).
  - `router.py`: רשימות הדפוסים של הנתב (את ההחלטה כותבים ב-`route_question`, אבן דרך 6), והמסלול לנתונים דרך text-to-SQL של datakit, עם מיפוי מתפקיד המסמכים לתפקיד הנתונים.
  - `assistant.py`: שאלה אחת מקצה לקצה, כרצף אירועים (route, data, sources, token, answer, done), עם trace לכל שאלה.
  - `service.py` ו-`ui/index.html`: ה-API (FastAPI) והדף בעברית.
  - `evaluate.py`: ה-eval. תשובות לפי סוג שאלה, groundedness, אבחון שורש הכשל, הנתב, ACL, ו-ablation של החיפוש. המדדים של כל שאלה מגיעים מ-`answer_metrics` שלך (אבן דרך 8).
  - `hooks.py`: החיבור בין המערכת לפונקציות שלך ב-`mine.py`. פונקציה שעוד לא כתבת עוצרת את הפקודה עם הודעה שאומרת איזו אבן דרך חסרה.
- **`data/`**: `data_questions.jsonl`, 16 שאלות נתונים עם SQL זהב, התשובות הנכונות מ-acme.db, ותוכנית מוקלטת לכל אחת (נבנה ע"י `make_data_questions.py`). `recorded/`: התשובות של Haiku מאבן דרך 9.
- **`mine.py`**: שש הפונקציות שאתה כותב, באבני הדרך 3, 4, 5, 6 ו-8. ה-docstring של כל אחת הוא החוזה שלה.
- **`tests/`**: בדיקות לאבני הדרך, ושער הרגרסיה (`test_m9_regression_gate.py`).

## הנתונים בקצרה (כדי שלא תצטרך לזכור משיעורים קודמים)

- **הקורפוס:** `data/acme/corpus/docs/`, 55 מסמכים: 49 Markdown, 3 HTML, 2 PDF ו-DOCX אחד. 46 באנגלית ו-9 בעברית. סיווג: 47 internal, 4 public (שני המחירונים ושני מסמכי ה-SLA) ו-4 confidential (שלושת ה-postmortems של הנדסה, ו-`hr-relocation` של משאבי אנוש). תשעה זוגות של גרסה ישנה מול חדשה, והחדשה מצביעה על הישנה בשדה `supersedes`. מסמך אחד (`sales-partner-northwind-notes`) מכיל ניסיון הזרקה.
- **שאלות הזהב:** `data/acme/corpus/golden/qa.jsonl`, 79 שאלות: 19 single_hop, 11 multi_hop, 9 numeric, 11 version_conflict, 8 acronym, 11 hebrew, ו-10 unanswerable (התשובה הנכונה: `not in the documents`). לכל שאלה: `source_ids`, ציטוטים מדויקים, ו-`answer_facts`.
- **הנתונים המובנים:** `data/acme/corpus/structured/acme.db` (SQLite): employees, teams, systems, access_grants, customers, tickets, provenance. שכבת הסמנטיקה של datakit (`datakit/data/acme_semantic.yaml`) מגדירה תפקידי נתונים: analyst (בלי PII ובלי עמודות כספיות), support_lead, finance, manager, people_ops.
- **מטריצת ההרשאות** (מ-`ragkit.vectors.filters.acl_where`): public לכולם; internal לכולם חוץ מ-contractor; confidential ל-security, או לתפקיד שהמחלקה שלו היא מחלקת המסמך (engineering, support למכירות ותמיכה, hr, finance). כל דבר אחר: אין גישה.

## אבני הדרך

**1. הרצה ראשונה (חינם).** בונים את האינדקס ומריצים שוב, כדי לראות שהוא אינקרמנטלי. החלק הזה מוכן ועובד בלי קוד שלך. אחר כך מריצים את הבדיקות, כדי לראות מה מחכה לך.

```bash
python -m acmeqa ingest          # added 55 ... chunks +404
python -m acmeqa ingest          # unchanged 55, chunks +0
python -m acmeqa stats
python -m pytest -q tests        # רובן נכשלות: אלה אבני הדרך 3 עד 8
python -m acmeqa demo            # עוצר עם "milestone 3: mine.build_retriever is still a TODO"
```

בדיקת קבלה: הריצה השנייה של ingest לא מעבדת אף מסמך, וההדגמה עוצרת עם הודעה שמפנה לאבן דרך 3. ענה: למה הריצה השנייה מהירה פי עשרה, ומה היה קורה אם היית מחליף chunker?

**2. ה-ingestion: manifest, שינוי סיווג ומחיקה.** עובדים על עותק של התיקייה, כדי לא לגעת בקורפוס.

```bash
cp -r ../../data/acme/corpus/docs /tmp/acme-docs
python -m acmeqa --index /tmp/acme-idx ingest --docs /tmp/acme-docs
sed -i '0,/classification: internal/s//classification: confidential/' /tmp/acme-docs/co-glossary.md
rm /tmp/acme-docs/hr-vacation-2024.md
python -m acmeqa --index /tmp/acme-idx ingest --docs /tmp/acme-docs --dry-run
python -m acmeqa --index /tmp/acme-idx ingest --docs /tmp/acme-docs
python -c "import sys; sys.path.insert(0,'../..'); from ragkit.acme import *; from ragkit.evaluate import quote_coverage; print(quote_coverage(acme_documents(), acme_chunks(), acme_qa()).summary())"
```

בדיקת קבלה: changed 1 (co-glossary) ו-removed 1, בלי לגעת בשאר; הכיסוי של ציטוטי הזהב 102 מתוך 102 (אף ציטוט לא נחתך בין שני chunks). ענה: למה שינוי סיווג בלי שינוי טקסט חייב להגיע לאינדקס? מה היה דולף אם ה-hash היה מחושב רק מהטקסט?

**3. החיפוש: היברידי, גרסאות והרשאות (קוד: `build_retriever`).** ממש את הפונקציה ב-`mine.py`: היא מרכיבה את שכבות החיפוש של ragkit לשכבה אחת. אחר כך מודדים מה כל שכבה תורמת, ובודקים שההרשאות לא דולפות.

```bash
python -m pytest -q tests/test_m3_retriever.py
python -m acmeqa eval --parts ablation,acl
python -m acmeqa acl
```

בדיקת קבלה: אפס דליפות לכל שבעת התפקידים, ו-stale@5 יורד מ-0.91 ל-0.18 כשמוסיפים את סינון הגרסאות. ענה: למה ה-ACL הוא `where` שרץ לפני הדירוג, ולא סינון של עשרת הראשונים? (רמז: ספור כמה תוצאות מקבל employee כשהשאלה היא על postmortem.)

**4. בחירת ההקשר (קוד: `pack_context`).** ממש את הפונקציה ב-`mine.py`: בלי כפילויות טקסט, לכל היותר 2 קטעים ממסמך, תקציב טוקנים, ותמיד לפחות קטע אחד.

```bash
python -m pytest -q tests/test_m4_context.py
```

ענה: למה hit שלא נכנס בתקציב לא עוצר את הלולאה? תן דוגמה מ-Acme שבה זה משנה את התשובה. (את ההשפעה של k על ה-eval תמדוד באבן דרך 8, כשכל המסלול יעבוד.)

**5. הפרומפט והציטוטים (קוד: `build_request`, `resolve_citations`).** שתי פונקציות. הראשונה בונה את הבקשה למודל: הוראות המערכת בבלוק אחד עם cache, ואחריהן המקורות הממוספרים והשאלה. השנייה מפענחת את המספרים שהמודל כתב, ובודקת שכל מספר מצביע על מקור שבאמת נשלח.

```bash
python -m pytest -q tests/test_m5_request.py tests/test_m5_citations.py
```

ענה: למה ההוראות הקבועות באות לפני המקורות ולא אחריהם? מה היה קורה לו מסמך מכיל את הטקסט `</source>` ולא היית עושה escaping? (רמז: יש מסמך כזה בקורפוס, `sales-partner-northwind-notes`.)

**6. הנתב והמסלול לנתונים (קוד: `route_question`).**

```bash
python -m pytest -q tests/test_m6_router.py
python -m acmeqa ask "How many open P1 tickets do we have right now?" --role support
python -m acmeqa ask "כמה עובדים יש בכל משרד?" --role support
python -m acmeqa ask "What is the total ARR of the Red Folder customers?" --role employee
python -m acmeqa ask "What is the total ARR of the Red Folder customers?" --role finance
python -m acmeqa eval --parts router
```

ענה: אילו ארבע שאלות זהב הולכות קודם לנתונים, ולמה התשובה הסופית שלהן בכל זאת מגיעה מהמסמכים? למה טעות לכיוון "נתונים" זולה יותר מטעות לכיוון "מסמכים"?

**7. ההדגמה, ה-cache, השירות וה-UI.** אחרי אבני הדרך 3 עד 6 כל המסלול של שאלה עובד, וזו הפעם הראשונה שרואים את המערכת שלך עונה. מתחילים בהדגמה, ממשיכים לבדיקה של prompt caching מול mockllm, ומסיימים בשירות.

```bash
python -m acmeqa demo                     # שש שאלות, שני המסלולים, שלושה תפקידים
cd ../.. && python -m mockllm &           # in another terminal is nicer
cd projects/m1-knowledge-assistant
python -m acmeqa --mode mock cache-check
python -m acmeqa serve &
curl -N -s localhost:8000/ask -H 'content-type: application/json' -d '{"question":"What is Blue Room?","role":"employee"}'
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{"question":"How many open P1 tickets do we have right now?","role":"support","stream":false}' | python -m json.tool | head -30
curl -s -o /dev/null -w '%{http_code}\n' "localhost:8000/docs/eng-pm-2026-08-api?role=employee"
curl -s localhost:8000/readyz
xdg-open http://127.0.0.1:8000
```

בדיקת קבלה: בהדגמה, אותה שאלה על ה-postmortem של אוגוסט מקבלת סירוב כ-employee ותשובה עם ציטוט כ-engineering, ושאלת ה-P1 עוברת ל-SQL כ-support ומקבלת "אין גישה" כ-contractor. ב-cache-check, בשאלה הראשונה יש cache write של כ-950 טוקנים, ובשנייה cache read של אותו מספר. בשירות, האירועים מגיעים בסדר route, sources, token (הרבה), answer, done; המסמך החסוי מחזיר 404 ל-employee; ב-UI, לחיצה על [1] פותחת את המסמך עם הקטע מסומן. ענה: למה הוראות המערכת נכתבו ארוכות מ-512 טוקנים? מה היה קורה עם הוראות של 200 טוקנים? למה 404 ולא 403? ולמה בהדגמה מותר לקבל את התפקיד מהדפדפן, ובמערכת אמיתית אסור?

**8. ה-eval המלא, offline (קוד: `answer_metrics`).** ממש את המדדים של שאלה אחת: האם המקור הגיע לפרומפט, האם צוטט, והאם המערכת סירבה כשצריך. ה-eval מחשב איתם את הממוצעים לפי סוג שאלה. אחר כך מריצים את ה-eval המלא ומשחקים עם k.

```bash
python -m pytest -q tests/test_m8_metrics.py
python -m acmeqa eval --misses | less
python -m acmeqa eval --json results/eval_offline.json
TOP_K=3 python -m acmeqa eval --parts answers --no-judge
TOP_K=10 python -m acmeqa eval --parts answers --no-judge
python -m pytest -q tests/test_m9_regression_gate.py
```

ענה: מה קורה ל-context_recall ומה קורה ל-answer_ok כשמגדילים את k? איזה שלב באבחון גדל, ולמה? מתוך השאלות שנכשלו, כמה נכשלו בשלב החיפוש וכמה בשלב היצירה? בחר שלוש שנכשלו ב-ignored_context, ובדוק אם המשפט הנכון היה בפרומפט. למה מודל אמיתי אמור לתקן את רובן, ולא reranker?

**9. הרצה אמיתית: e5-small ו-Haiku 5.5 (בתשלום: בערך 5 עד 8 סנט).**

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cpu    # if not installed in lesson 10
python -m acmeqa --mode live ingest                                       # downloads e5-small once, embeds 404 chunks
python -m acmeqa --mode live cache-check
python -m acmeqa --mode live eval --record --misses --json results/eval_live.json
python -m pytest -q tests/test_m9_regression_gate.py                      # now also replays the recording, free
```

בדיקת קבלה: העלות המודפסת נמוכה מ-0.20$; בשאלה השנייה של cache-check יש cached input tokens; הקובץ `data/recorded/claude-haiku-5-5.jsonl` נוצר, והבדיקה הרביעית בשער כבר לא מדולגת. ענה: מה השתנה בכל שלב באבחון לעומת offline? איפה e5 שיפר את החיפוש (רמז: שאלות cross-lingual), ואיפה Haiku שיפר את היצירה?

**10. ניטור, הצגה ו-README לתיק.**

```bash
TRACE_FILE=results/traces.jsonl python -m acmeqa demo
cd ../.. && python -m obskit.viewer projects/m1-knowledge-assistant/results/traces.jsonl -o projects/m1-knowledge-assistant/results/traces.html
```

פתח את מפל ה-spans של שאלה אחת: route, retrieval (עם מזהי הקטעים והציונים), ה-LLM (טוקנים, cache, עלות). אחר כך עבור על תסריט ההצגה של 5 דקות ועל רשימת הבדיקה ל-README שבתחנה "מסכם" במרכז הלמידה.

## מה לבדוק אצלך, כי כאן לא היה אפשר

- הרצה אמיתית של Haiku 5.5 ושל e5-small (אבן דרך 9): העלות בפועל, ה-cache read, ומספרי התשובות והאבחון. כל המספרים בהסברים הם של המצב החינמי (embedder מזויף ועונה חילוצי), ולכן התשובות שם חלשות בכוונה: הן מודדות את הצנרת ואת החיפוש, לא מודל.
- ה-UI בדפדפן אמיתי (נבדק כאן עם TestClient בלבד).
