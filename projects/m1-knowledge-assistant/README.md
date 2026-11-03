# פרויקט אמצע M1: Acme Knowledge Assistant

כל הפקודות רצות מתוך `projects/m1-knowledge-assistant/`, עם ה-venv של הריפו פעיל, אלא אם כתוב אחרת.

זה השלב הראשון של Company Brain, והסיום של השלב השני בקורס (שיעורים 8 עד 13). עוזר שעונה על שאלות של עובדי Acme מתוך 55 המסמכים של החברה, עם מספר מקור ליד כל עובדה, שמסרב כשהתשובה לא כתובה, שמראה לכל תפקיד רק את המסמכים שמותר לו לראות, ושולח שאלות על נתונים ("כמה קריאות P1 פתוחות יש?") למסד הנתונים במקום למסמכים. יש לו שירות HTTP עם תשובה שזורמת (SSE), דף אינטרנט אחד בעברית שבו כל מספר מקור נפתח על הקטע המדויק במסמך, eval על 79 שאלות הזהב עם אבחון לפי שלב, ושער רגרסיה ב-pytest. הוא בנוי מהספריות שכבר בנית: `ragkit` (שיעורים 9 עד 13), `datakit` (שיעור 8), `llmkit`, ו-`obskit` ל-traces.

## מה עולה כסף, ומה לא

- **כמעט הכול חינם.** ברירת המחדל היא `MODE=offline`: embedder מזויף (HashingEmbedder, לקסיקלי ולא סמנטי), "עונה" חילוצי של ragkit (בוחר את המשפט הטוב ביותר מהמקורות, הוא לא מודל שפה), תוכניות SQL מוקלטות, ושופט groundedness לקסיקלי. כל אבני הדרך חוץ מ-9 רצות כך.
- **`MODE=mock`, גם חינם:** ה-adapter האמיתי של llmkit מול mockllm ב-HTTP. כך רואים streaming, ניסיונות חוזרים ו-prompt caching (שדות ה-cache ב-usage) בלי מפתח.
- **`MODE=live`, אבן דרך 9:** Claude Haiku 5.5 לתשובות, לתוכניות ה-SQL ולשופט, ו-e5-small מקומי ל-embeddings (הורדה חד פעמית של כ-470MB). ההערכה לפני הרצה, לפי `llmkit/pricing.py` (0.10$ למיליון טוקני קלט, 0.50$ לפלט): כ-2,300 טוקני קלט לשאלה, ולכן 79 תשובות עולות כ-2.5 סנט, השופט עוד כ-2.5 סנט, ו-16 שאלות הנתונים כסנט. **הרצה מלאה: בערך 5 עד 8 סנט, והתקרה שקבענו היא 0.20$.** הסכום האמיתי מודפס בסוף הריצה.

## הכנה

```bash
cd ~/projects/"ai engineer"/ai-engineer-course && source .venv/bin/activate
uv pip install -r projects/m1-knowledge-assistant/requirements.txt
python -m pytest -q                              # בדיקות הסביבה, כולל tests/test_m1_knowledge_assistant.py
cd projects/m1-knowledge-assistant
python -m pytest -q tests                        # אבני הדרך שלך: בהתחלה הבדיקות של 4-6 נכשלות, וזה תקין
python -m acmeqa demo                            # שש שאלות, שני המסלולים, שלושה תפקידים
```

## מה יש בתיקייה

- **`acmeqa/`**: המערכת עצמה (קוד הייחוס).
  - `config.py`: ההגדרות מהסביבה (MODE, EMBEDDER, RERANK, VERSION_MODE, TOP_K), והמפעלים של המודלים לכל מצב.
  - `ingest.py`: עבודת ה-ingestion. `IngestPipeline` של ragkit עם manifest (אינקרמנטלי: added, changed, unchanged, removed), אינדקס היברידי (BM25 ו-dense), ומאגר מסמכים (`docs.jsonl`) עם הטקסט הנקי שהציטוטים מצביעים לתוכו.
  - `retrieval.py`: שכבות החיפוש. ACL לפי תפקיד כמסנן שרץ לפני הדירוג, RRF, סינון גרסאות, ו-reranker אופציונלי.
  - `context.py`: `pack_context`, הבחירה של הקטעים שנכנסים לפרומפט (אבן דרך 4).
  - `citations.py`: `resolve_citations`, מ-[2] בטקסט לקטע מדויק במסמך (אבן דרך 5).
  - `answer.py`: הפרומפט (הוראות מערכת של כ-950 טוקנים, בבלוק אחד עם cache), זיהוי סירוב, streaming, ושלושה "מודלים": llmkit, העונה החילוצי, והשמעה חוזרת של תשובות מוקלטות.
  - `router.py`: `route_question` (אבן דרך 6), והמסלול לנתונים דרך text-to-SQL של datakit, עם מיפוי מתפקיד המסמכים לתפקיד הנתונים.
  - `assistant.py`: שאלה אחת מקצה לקצה, כרצף אירועים (route, data, sources, token, answer, done), עם trace לכל שאלה.
  - `service.py` ו-`ui/index.html`: ה-API (FastAPI) והדף בעברית.
  - `evaluate.py`: ה-eval. תשובות לפי סוג שאלה, groundedness, אבחון שורש הכשל, הנתב, ACL, ו-ablation של החיפוש.
  - `hooks.py`: הפונקציות שלך מ-`mine.py`, או קוד הייחוס כל עוד הן TODO.
- **`data/`**: `data_questions.jsonl`, 16 שאלות נתונים עם SQL זהב, התשובות הנכונות מ-acme.db, ותוכנית מוקלטת לכל אחת (נבנה ע"י `make_data_questions.py`). `recorded/`: התשובות של Haiku מאבן דרך 9.
- **`mine.py`**: שלוש אבני דרך שאתה כותב (4, 5, 6).
- **`tests/`**: בדיקות לאבני הדרך, ושער הרגרסיה (`test_m9_regression_gate.py`).

## הנתונים בקצרה (כדי שלא תצטרך לזכור משיעורים קודמים)

- **הקורפוס:** `data/acme/corpus/docs/`, 55 מסמכים: 49 Markdown, 3 HTML, 2 PDF ו-DOCX אחד. 46 באנגלית ו-9 בעברית. סיווג: 47 internal, 4 public (שני המחירונים ושני מסמכי ה-SLA) ו-4 confidential (שלושת ה-postmortems של הנדסה, ו-`hr-relocation` של משאבי אנוש). תשעה זוגות של גרסה ישנה מול חדשה, והחדשה מצביעה על הישנה בשדה `supersedes`. מסמך אחד (`sales-partner-northwind-notes`) מכיל ניסיון הזרקה.
- **שאלות הזהב:** `data/acme/corpus/golden/qa.jsonl`, 79 שאלות: 19 single_hop, 11 multi_hop, 9 numeric, 11 version_conflict, 8 acronym, 11 hebrew, ו-10 unanswerable (התשובה הנכונה: `not in the documents`). לכל שאלה: `source_ids`, ציטוטים מדויקים, ו-`answer_facts`.
- **הנתונים המובנים:** `data/acme/corpus/structured/acme.db` (SQLite): employees, teams, systems, access_grants, customers, tickets, provenance. שכבת הסמנטיקה של datakit (`datakit/data/acme_semantic.yaml`) מגדירה תפקידי נתונים: analyst (בלי PII ובלי עמודות כספיות), support_lead, finance, manager, people_ops.
- **מטריצת ההרשאות** (מ-`ragkit.vectors.filters.acl_where`): public לכולם; internal לכולם חוץ מ-contractor; confidential ל-security, או לתפקיד שהמחלקה שלו היא מחלקת המסמך (engineering, support למכירות ותמיכה, hr, finance). כל דבר אחר: אין גישה.

## אבני הדרך

**1. הרצה ראשונה (חינם).** בונים את האינדקס, מריצים שוב כדי לראות שהוא אינקרמנטלי, מריצים את ההדגמה, ומרימים את השירות.

```bash
python -m acmeqa ingest          # added 55 ... chunks +404
python -m acmeqa ingest          # unchanged 55, chunks +0
python -m acmeqa stats
python -m acmeqa demo
python -m acmeqa serve           # http://127.0.0.1:8000
```

בדיקת קבלה: הריצה השנייה של ingest לא מעבדת אף מסמך; בהדגמה, אותה שאלה על ה-postmortem של אוגוסט מקבלת סירוב כ-employee ותשובה עם ציטוט כ-engineering; שאלת ה-P1 עוברת ל-SQL כ-support ומקבלת "אין גישה" כ-contractor. ענה: למה הריצה השנייה מהירה פי עשרה, ומה היה קורה אם היית מחליף chunker?

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

**3. החיפוש: היברידי, גרסאות והרשאות.**

```bash
python -m acmeqa eval --parts ablation,acl
python -m acmeqa acl
python -m acmeqa ask "How long was flow-api fully unavailable on August 19, 2026?" --role employee --context
python -m acmeqa ask "How long was flow-api fully unavailable on August 19, 2026?" --role engineering --context
```

בדיקת קבלה: אפס דליפות לכל שבעת התפקידים, ו-stale@5 יורד מ-0.91 ל-0.18 כשמוסיפים את סינון הגרסאות. ענה: למה ה-ACL הוא `where` שרץ לפני הדירוג, ולא סינון של עשרת הראשונים? (רמז: ספור כמה תוצאות מקבל employee כשהשאלה היא על postmortem.)

**4. בחירת ההקשר (קוד: `pack_context`).** ממש את הפונקציה ב-`mine.py`: בלי כפילויות טקסט, לכל היותר 2 קטעים ממסמך, תקציב טוקנים, ותמיד לפחות קטע אחד.

```bash
python -m pytest -q tests/test_m4_context.py
python -m acmeqa eval --parts answers --no-judge
TOP_K=3 python -m acmeqa eval --parts answers --no-judge
TOP_K=10 python -m acmeqa eval --parts answers --no-judge
```

ענה: מה קורה ל-context_recall ומה קורה ל-answer_ok כשמגדילים את k? איזה שלב באבחון גדל, ולמה?

**5. ציטוטים, סירוב ו-prompt caching (קוד: `resolve_citations`).** ממש את הפונקציה. אחר כך הרם את mockllm בטרמינל אחר ובדוק שהוראות המערכת נשמרות ב-cache.

```bash
python -m pytest -q tests/test_m5_citations.py
cd ../.. && python -m mockllm &           # in another terminal is nicer
cd projects/m1-knowledge-assistant
python -m acmeqa --mode mock cache-check
```

בדיקת קבלה: בשאלה הראשונה cache write של כ-950 טוקנים, ובשנייה cache read של אותו מספר. ענה: למה הוראות המערכת נכתבו ארוכות מ-512 טוקנים? מה היה קורה עם הוראות של 200 טוקנים?

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

**7. השירות וה-UI.**

```bash
python -m acmeqa serve &
curl -N -s localhost:8000/ask -H 'content-type: application/json' -d '{"question":"What is Blue Room?","role":"employee"}'
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{"question":"How many open P1 tickets do we have right now?","role":"support","stream":false}' | python -m json.tool | head -30
curl -s -o /dev/null -w '%{http_code}\n' "localhost:8000/docs/eng-pm-2026-08-api?role=employee"
curl -s localhost:8000/readyz
xdg-open http://127.0.0.1:8000
```

בדיקת קבלה: האירועים מגיעים בסדר route, sources, token (הרבה), answer, done; המסמך החסוי מחזיר 404 ל-employee; ב-UI, לחיצה על [1] פותחת את המסמך עם הקטע מסומן. ענה: למה 404 ולא 403? ולמה בהדגמה מותר לקבל את התפקיד מהדפדפן, ובמערכת אמיתית אסור?

**8. ה-eval המלא, offline.**

```bash
python -m acmeqa eval --misses | less
python -m acmeqa eval --json results/eval_offline.json
```

ענה: מתוך השאלות שנכשלו, כמה נכשלו בשלב החיפוש וכמה בשלב היצירה? בחר שלוש שנכשלו ב-ignored_context, ובדוק אם המשפט הנכון היה בפרומפט. למה מודל אמיתי אמור לתקן את רובן, ולא reranker?

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
