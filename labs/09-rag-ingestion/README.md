# מעבדה 9: RAG Architecture and Document Ingestion

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/09-rag-ingestion/requirements.txt
python -m pytest -q                                  # בדיקות הסביבה, כולל tests/test_ragkit_ingest.py החדש
python -m pytest -q labs/09-rag-ingestion/tests      # התרגילים שלך: בהתחלה רובן נכשלות, וזה תקין
```

התלויות החדשות הן pypdf, python-docx, beautifulsoup4 ו-lxml. trafilatura אופציונלית, ומשמשת רק להשוואה בתרגיל 1.

## מה חדש

- **`ragkit/` (חבילה חדשה בשורש הריפו):** ספריית ה-RAG של הקורס. שיעורים 10 עד 13, פרויקטי האמצע ו-Company Brain ימשיכו לבנות עליה. פירוט הארכיטקטורה ונקודות ההרחבה נמצא ב-`ragkit/README.md`. בקצרה:
  - `types.py`: שלושה טיפוסים שכל השלבים מדברים בהם. `Document` הוא מסמך אחרי ניקוי, עם המטא-דאטה שלו. `Chunk` הוא קטע של מסמך, עם מזהה, מזהה המסמך, נתיב הסעיף (section path), היסטים של תווים (`start`, `end`) והמטא-דאטה שהועתקה מהמסמך: כותרת, גרסה, תאריך תוקף, סיווג ושפה. `Hit` הוא תוצאת חיפוש עם ציון.
  - `loaders/`: Markdown עם front matter, HTML עם הסרת תפריטים, באנרים ו-footer, PDF עם pypdf והסרת כותרות עליונות ותחתונות, ו-DOCX עם python-docx. כל loader מוציא טקסט באותה צורה: כותרות כ-`#`, פריטי רשימה כ-`- `, ושורות טבלה כ-`a | b | c`.
  - `clean.py`: נרמול Unicode, הסרת תווים בלתי נראים ותווי כיווניות (RLM ודומיו), גרשיים עבריים, ניקוד ורווחים.
  - `chunking/`: ארבע אסטרטגיות. `fixed` (מספר טוקנים קבוע עם חפיפה), `recursive` (לפי מפרידים), `heading` (לפי כותרות Markdown) ו-`sentence` (לפי משפטים).
  - `manifest.py` ו-`pipeline.py`: ingestion אינקרמנטלי. ה-hash של כל קובץ נשמר ב-manifest, וקבצים שלא השתנו לא מפוענחים בכלל.
  - `retrieval/`: הממשק `Retriever` ו-BM25 שלא צריך embeddings, עם ניתוח עברית בסיסי.
  - `rag.py`: בניית פרומפט עם מקורות ממוספרים, פענוח ציטוטים ובדיקה שכל `[n]` מצביע על מקור שנשלח באמת.
  - `fake.py`: `ExtractiveAnswerer`, תחליף חינמי ל-LLM שבוחר משפטים מתוך המקורות. הוא לא מודל שפה, והוא משמש רק כדי שהכול ירוץ בחינם.
  - `evaluate.py`: כיסוי ציטוטים (quote coverage) ופגיעות באחזור לפי סוג שאלה.
- **הנתונים:** קורפוס Acme ב-`data/acme/corpus/`. יש בו 55 מסמכים: 49 ב-Markdown, 3 דפי HTML, 2 קובצי PDF וקובץ DOCX אחד. 9 מהמסמכים בעברית. יש גם 79 שאלות זהב בקובץ `golden/qa.jsonl`, ולכל שאלה רשומים `source_ids` ו-`source_quotes` (ציטוטים מדויקים מהמקור). סוגי השאלות: single_hop, multi_hop, numeric, version_conflict, acronym, hebrew ו-unanswerable. הקורפוס כולל בכוונה גרסאות ישנות של מדיניות שעדיין נשמעות סמכותיות, מסמכים כמעט כפולים, טבלאות בתוך PDF ו-DOCX, ופסקת prompt injection במסמך `sales-partner-northwind-notes`. הפירוט המלא נמצא ב-`data/acme/corpus/README.md`.
- **`mine.py`:** הקוד שלך לתרגילים 3, 4 ו-5.
- **הטוקנייזר:** הסקריפטים משתמשים כברירת מחדל ב-`approx`, טוקנייזר דטרמיניסטי שלא צריך הורדה. כך המספרים שלך יהיו זהים למספרים שבשיעור. אם תוסיף `--tokenizer tiktoken`, הסקריפט ישתמש ב-o200k האמיתי.

## התרגילים

**1. מה החילוץ באמת מוציא.** הסקריפט מציג כל מסמך פעמיים: לפני הניקוי (כל צומת טקסט ב-HTML, הפלט הרגיל של pypdf כולל הכותרות, או DOCX עם header ו-footer) ואחרי ה-loader של ragkit. בנוסף הוא מציג מה הוסר ובודק אם הציטוטים של שאלות הזהב עדיין נמצאים בטקסט.

```bash
python labs/09-rag-ingestion/inspect_extraction.py --all
python labs/09-rag-ingestion/inspect_extraction.py --doc it-helpdesk
python labs/09-rag-ingestion/inspect_extraction.py --doc sales-sla-2026
python labs/09-rag-ingestion/inspect_extraction.py --doc sales-sla-2026 --pdf-mode plain
python labs/09-rag-ingestion/inspect_extraction.py --doc hr-relocation
python labs/09-rag-ingestion/inspect_extraction.py --doc co-haifa-office-he --trafilatura
```

ענה על שלוש שאלות:
- מה קרה לטבלת הזיכויים של ה-SLA במצב `plain`?
- איזו שאלת זהב (q041) הייתה נפגעת אם הייתה צריכה את השורה כולה?
- למה הכותרת העליונה של ה-PDF מזיקה דווקא בחיפוש, למרות שהיא "רק" חוזרת בכל עמוד?

**2. עברית ותווים בלתי נראים.** הסקריפט בונה משפט עברי שמכיל RLM, רווח באפס רוחב, רווח קשיח, גרשיים וניקוד, ומראה מה קורה לחיפוש ולהתאמה מדויקת לפני הנרמול ואחריו. בחלק השני הוא סופר טוקנים של אותה מדיניות באנגלית ובעברית.

```bash
python labs/09-rag-ingestion/normalize_demo.py
python labs/09-rag-ingestion/normalize_demo.py --tokenizer tiktoken --claude   # על המחשב שלך: הספירה של Claude חינמית
```

**3. Chunker לפי כותרות.** ממש את `heading_chunks` ב-`mine.py`:
- כל סעיף נמשך מכותרת עד הכותרת הבאה, ומקבל נתיב סעיף.
- כותרת בלי גוף מצטרפת לסעיף שאחריה.
- סעיף ארוך מפוצל בתוך הסעיף, עם חפיפה, וכל החלקים שלו שומרים על אותו נתיב.
- ההיסטים חייבים להתאים לטקסט במדויק.

הבדיקות משוות את הנתיב של כל אחד מ-102 הציטוטים מול `tests/golden_sections.json`.

```bash
python -m pytest -q labs/09-rag-ingestion/tests/test_ex3_chunker.py
```

**4. כיסוי ציטוטים והשוואת אסטרטגיות.** ממש את `quote_status`: האם ציטוט נמצא כולו בתוך chunk אחד (`covered`), נחתך בין שני chunks (`split`), או בכלל לא קיים בטקסט שחולץ (`missing`). אחר כך הרץ את ההשוואה. היא מדרגת 12 תצורות לפי פגיעה בתקציב טוקנים קבוע, כך ש-chunks גדולים לא מנצחים רק בגלל שהם שולחים יותר טקסט.

```bash
python -m pytest -q labs/09-rag-ingestion/tests/test_ex4_coverage.py
python labs/09-rag-ingestion/chunk_compare.py --mine
python labs/09-rag-ingestion/chunk_compare.py --show-split fixed:128:0
```

**5. Ingestion אינקרמנטלי.** ממש את `content_hash` ואת `plan_ingest`. אחר כך הרץ את הדמו. הוא מעתיק את הקורפוס, מריץ, משנה מסמך אחד, משנה סיווג של מסמך אחר רק בקובץ ה-sidecar, מוחק מסמך ומוסיף מסמך, ובסוף מחליף את ה-chunker.

```bash
python -m pytest -q labs/09-rag-ingestion/tests/test_ex5_incremental.py
python labs/09-rag-ingestion/ingest.py --demo
```

**6. הלולאה המלאה לשאלה אחת.** הסקריפט מריץ את כל השלבים ומדפיס כל אחד מהם: אחזור (עם המונחים שתרמו לציון), בניית הפרומפט, תשובה, וציטוטים שמתורגמים למסמך, לסעיף ולהיסטים.

```bash
python labs/09-rag-ingestion/rag_answer.py --qid q001
python labs/09-rag-ingestion/rag_answer.py --qid q001 --where-latest
python -m mockllm                                                                   # טרמינל 2
python labs/09-rag-ingestion/rag_answer.py --qid q041 --model mock:mock-model
python labs/09-rag-ingestion/rag_answer.py --qid q041 --model anthropic:claude-haiku-5-5 --show-prompt
```

**7. ה-baseline על כל שאלות הזהב, וכשלים לפי סוג.** תתחיל בהרצה החינמית, ואחר כך תריץ חי עם Haiku. ההרצה החיה עולה בערך 2 סנט, והסקריפט מדפיס הערכה לפני שהוא מתחיל. בתוצאות תסתכל במיוחד על שלושה סוגי שאלות: hebrew, version_conflict ו-multi_hop. לכל כשל, החלט באיזה שלב הוא קרה: חילוץ, chunking, אחזור, יצירה או ציטוט.

```bash
python labs/09-rag-ingestion/rag_eval.py --failures
python labs/09-rag-ingestion/rag_eval.py --model anthropic:claude-haiku-5-5 --failures
```

**8. מתי לא צריך RAG.** כל הקורפוס הוא בערך 42 אלף טוקנים, ונכנס לפרומפט אחד. הסקריפט משווה עלות לשאלה בשלוש דרכים: RAG, כל הקורפוס בכל פרומפט, וכל הקורפוס עם prompt caching. עם `--live` הוא שואל חמש שאלות שה-baseline נכשל בהן, עם כל הקורפוס בפרומפט. העלות היא בערך סנט אחד.

```bash
python labs/09-rag-ingestion/long_context.py
python labs/09-rag-ingestion/long_context.py --live --claude-count
```

## עלות

- כל התרגילים רצים בחינם עם `extractive` או עם `mock:mock-model`.
- ההרצות החיות עם claude-haiku-5-5:
  - תרגיל 6: פחות מעשירית סנט לשאלה.
  - תרגיל 7: בערך 2 סנט.
  - תרגיל 8: בערך סנט אחד.
- סך הכול: פחות מ-5 סנט.
