# מעבדה 13: RAG Quality and Retrieval Diagnostics

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/13-rag-diagnostics/requirements.txt   # transformers רק לתרגיל 8, אופציונלי
python -m pytest -q                                       # בדיקות הסביבה, כולל tests/test_ragkit_diagnose.py החדש
python -m pytest -q labs/13-rag-diagnostics/tests         # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

המסלול הלא מקוון לא צריך שום תלות חדשה. ה-pipeline "best" צריך numpy (כמו בשיעורים 10 עד 12). רק תרגיל 8, מודל NLI מקומי, צריך את transformers ואת PyTorch בגרסת CPU, בדיוק כמו ה-cross-encoders של שיעור 12.

**חשוב לדעת:** סביבת הקורס שבה נבנתה המעבדה לא מגיעה ל-API בתשלום ולא ל-Hugging Face. לכן כל המספרים שמופיעים כאן נמדדו במסלול הלא מקוון: answerer חילוצי (מעתיק משפטים), שופט לקסיקלי, embedder מזויף ו-rewrites שנכתבו ביד. המסווג, האחזור והמדדים אמיתיים. המספרים של שלבי היצירה (generation) לא מייצגים את מה ש-Claude היה עושה. את זה תמדוד בתרגיל 7.

## שלושת המסלולים

- **מסלול לא מקוון, חינם (ברירת המחדל):** `--llm extractive --judge heuristic`. ה-answerer הוא `ExtractiveAnswerer` משיעור 9: הוא בוחר את המשפט או שני המשפטים שחולקים הכי הרבה מילים עם השאלה, ומצטט אותם. הוא לעולם לא ממציא עובדה, ולעולם לא משלב שני מקורות. השופט הוא `heuristic_judge_llm()`, שהוא `llmkit.LLM` אמיתי שה-HTTP שלו נענה מקומית (`ragkit.replay`): שתי הקריאות המובנות נבנות בדיוק כמו מול Anthropic, ורק התשובה מגיעה מכללים לקסיקליים (מילים משותפות, מספרים, מילות שלילה). העלות שמודפסת היא הערכה של מה ש-Haiku היה גובה.
- **מסלול מקומי, חינם:** `--dense e5-small` לאחזור אמיתי (המטמון של שיעור 10 משותף), ו-`claims.py --nli` למודל NLI רב-לשוני מקומי.
- **מסלול חי, בתשלום:** `--llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5`. כל סקריפט שמוציא כסף מציג הערכת עלות ומבקש אישור.

## מה חדש

- **`ragkit/diagnose.py`:** המודול של השיעור. הוא לא משנה שום קובץ קיים ב-ragkit, ב-evalkit או ב-llmkit, רק משתמש בהם.
  - **הטקסונומיה:** `STAGES`, 12 שלבי כשל לפי סדר הצנרת, ו-`FIXES`, התיקון לכל שלב עם השיעור שבו הוא נלמד.
  - **המסווג:** `Case` (כל מה שצריך לדעת על שאלה אחת, כמידע פשוט), ו-`classify(case)`, שמחזיר `Diagnosis` עם השלב, הדגלים ומסלול ההחלטה.
  - **מדדים לפי שלב:** `context_recall`, `context_precision` (מודע לדירוג, כמו ב-Ragas), `simple_precision`, `citation_precision`, `citation_recall`.
  - **groundedness ברמת טענה:** `check_claims(answer, contexts, llm)`, שתי קריאות מובנות: פירוק לטענות (`Claims`), ובדיקת כל טענה מול המקורות (`ClaimVerdicts`, ראיה לפני פסק דין). אחר כך הקוד בודק שהראיה שהשופט ציטט באמת נמצאת במקור.
  - **`NLIChecker`:** אותה בדיקה עם מודל NLI מקומי.
  - **הרצה מלאה:** `trace_question`, `run_diagnosis`, `breakdown`, `funnel`, `to_evalkit_run` ו-`format_*`.
- **`mine.py`:** הקוד שלך לתרגילים 1, 2 ו-3, והניחושים שלך לתרגיל 5.
- **הסקריפטים:** `classify_demo.py`, `metrics_demo.py`, `claims.py`, `run_diagnosis.py`, `traces.py` ו-`fix_loop.py`.
- **fixtures:** `cases.jsonl` (20 מקרים בנויים עם התווית הנכונה והסבר), `claims_examples.jsonl` (5 תשובות עם תוויות של אדם לכל טענה), `traces.jsonl` (6 כשלים מוקלטים לתרגיל 5) ו-`build_traces.py` שבונה אותם מחדש.

## הנתונים שהמעבדה משתמשת בהם

- **הקורפוס:** `data/acme/corpus/docs/`, 55 מסמכים (9 בעברית, 2 PDF, 3 HTML, DOCX אחד), שמחולקים ל-210 chunks עם ה-chunker של ה-baseline (`heading:400:40:150`).
- **שאלות הזהב:** `data/acme/corpus/golden/qa.jsonl`, 79 שאלות. 69 עם מסמכי מקור: single_hop (19), multi_hop (11), numeric (9), version_conflict (11), acronym (8), hebrew (11). 10 שאלות unanswerable, ובשמונה מהן יש "near-miss", מסמך שנראה כאילו הוא עונה.
- **מה כל שאלת זהב מכילה:** `source_ids` (מסמכי המקור), `source_quotes` (ציטוט מדויק מכל מקור, הבסיס לכל המדדים כאן), `answer_facts` (עובדות אטומיות שתשובה טובה חייבת לכלול), ו-`tags`. למשל `stale:hr-vacation-2024` מסמן את הגרסה המיושנת שעלולה לבלבל.
- **דוגמה:** q040, multi-hop: "Which team owns the service whose configuration change caused the August 2026 flow-api outage, who leads that team, and when does its on-call rotation hand over?". המקורות הם `eng-pm-2026-08-api` (הסיבה: שינוי תצורה ב-auth-service) ו-`eng-service-catalog` (צוות Identity, ראש הצוות Gil Avraham, החלפת כוננות ביום חמישי ב-10:00).
- **כיסוי הציטוטים:** עם ה-chunker של ה-baseline, כל 102 הציטוטים נמצאים בשלמותם בתוך chunk אחד. עם `fixed:100:0` (חלונות של 100 טוקנים בלי חפיפה), 18 מהם נחתכים בין שני chunks.

## איך מאבחנים שאלה אחת (בקצרה)

לכל שאלה רצה צנרת אחת. חיפוש עמוק אחד (50 תוצאות) נותן את **המועמדים**, ו-5 הראשונים שבהם הם **הפרומפט**. אחר כך נשמרים התשובה, הציטוטים, כיסוי העובדות (לקסיקלי, משיעור 23) ופסק הדין של השופט. המסווג שואל שאלות לפי סדר הצנרת, והשלב הראשון שנכשל הוא שורש הבעיה:

1. האם התשובה עברה? אם כן: `ok`.
2. האם ציטוט הזהב קיים בקורפוס, בטקסט שחולץ, ובתוך chunk אחד?
3. האם כל מסמכי המקור בין המועמדים? ובפרומפט?
4. האם צוטט מסמך מיושן?
5. האם המודל סירב למרות שהראיה הייתה בפרומפט?
6. האם העובדות חסרות? ואם כן, האם יש טענות לא נתמכות, או שהראיה הייתה באמצע הקשר ארוך?
7. האם יש טענות לא נתמכות? אם לא, הבעיה היא בציטוטים.

לשאלה בלי תשובה בקורפוס יש רק שתי אפשרויות: `ok` אם המערכת סירבה, ו-`failed_to_refuse` אם היא ענתה.

## התרגילים

**1. המסווג (קוד).** ממש את `classify_failure(case, min_facts=0.5, long_context=4000)` ב-`mine.py`. ה-docstring מפרט את כל הנוהל, צעד אחר צעד, כולל ההגדרה המדויקת של "lost in the middle": הקשר של לפחות 4,000 טוקנים, לפחות 3 chunks, וכל הראיות במקומות שהם לא הראשון ולא האחרון. הבדיקות משתמשות ב-20 המקרים של `fixtures/cases.jsonl`, אחד לכל תווית ועוד מקרי קצה, ולכל אחד יש הסבר. למשל, `c17_upstream_wins`: המסמך הנכון בכלל לא אוחזר, והתשובה ציטטה את הגרסה הישנה. התווית היא `not_retrieved` ולא `stale_version`, כי שורש הבעיה נמצא מוקדם יותר בצנרת.

```bash
python -m pytest -q labs/13-rag-diagnostics/tests/test_ex1_classify.py
python labs/13-rag-diagnostics/classify_demo.py --case c09_lost_in_middle
python labs/13-rag-diagnostics/classify_demo.py --mine
```

ענה על שתי שאלות:
- למה דווקא השלב המוקדם ביותר הוא שורש הבעיה, ומה היה קורה אם היית מתקן קודם את הסימפטום המאוחר?
- ב-`c12_hallucination_extra_claim` העובדות נכונות, ובכל זאת התווית היא hallucination. למה זה כשל, ומה המחיר שלו בעוזר פנימי?

**2. מדדים לפי שלב (קוד).** ממש ארבע פונקציות:
- `context_recall(quotes, context_texts)`: כמה מציטוטי הזהב נמצאים בשלמותם ב-chunk כלשהו בפרומפט, אחרי נרמול רווחים ואותיות.
- `context_precision(relevance)`: ממוצע של precision@k בכל מקום k שבו יש chunk רלוונטי. זו ההגדרה של Ragas. דוגמה: `[True, False, True]` נותן (1/1 + 2/3)/2 = 0.833.
- `citation_precision(cited, supporting)`: כמה מהמספרים השונים שצוטטו מצביעים על chunk שמכיל ציטוט זהב.
- `citation_recall(cited, quote_locs)`: לכמה מציטוטי הזהב צוטט לפחות chunk אחד שמכיל אותם.

```bash
python -m pytest -q labs/13-rag-diagnostics/tests/test_ex2_metrics.py
python labs/13-rag-diagnostics/metrics_demo.py --mine
python labs/13-rag-diagnostics/metrics_demo.py --q q040
```

במסלול הלא מקוון, על ה-baseline (69 שאלות), נמדד:
- ALL: context recall 0.829, context precision 0.765, citation precision 0.592, citation recall 0.594.
- multi_hop: context recall 0.515, citation recall 0.182.
- version_conflict: context precision 0.508.
- ב-9 שאלות התשובה לא ציטטה כלום, ולכן citation precision לא מוגדר שם, והן לא נכנסות לממוצע.

ב-q040, context recall הוא 0.5 (רק הציטוט מה-postmortem הגיע לפרומפט), אבל context precision הוא 1.0, כי ה-chunk הרלוונטי היחיד נמצא במקום הראשון. ענה על שלוש שאלות:
- למה precision מודע-דירוג נותן 1.0 כשרק 1 מתוך 5 chunks רלוונטי? מה היה נותן `simple_precision`?
- איזה מדד מבין הארבעה הכי קרוב לבעיה האמיתית של q040?
- למה citation recall של multi_hop נמוך בהרבה מה-context recall שלו?

**3. groundedness ברמת טענה (קוד).** ממש את `check_claims(answer, contexts, llm)`, לפי ה-docstring:
- סירוב לא עולה אף קריאה.
- קריאה מובנית ראשונה מפרקת את התשובה לטענות אטומיות.
- קריאה שנייה בודקת כל טענה מול המקורות, וכותבת את הראיה לפני פסק הדין.
- אחר כך, בקוד, בודקים שהראיה של כל טענה "supported" באמת מופיעה במקור (`evidence_in_context`). טענה שהראיה שלה הומצאה לא נספרת כנתמכת.

הבדיקות משתמשות ב-LLM מקומי (`ragkit.replay`) עם תשובות קבועות, ובודקות גם ראיה מומצאת, פסק דין חסר ושגיאת JSON. אחר כך הרץ את חמש הדוגמאות של `fixtures/claims_examples.jsonl`:
- **e1:** היפוך שלילה. "You must change your password every 90 days", כשהמקור אומר "There is no forced periodic rotation".
- **e2:** משפט מהידע של המודל, עם ציטוט: "Outages of this kind usually take about two hours".
- **e3:** תשובה נאמנה למקור מיושן (מדיניות 2025).
- **e4:** תשובה באנגלית ממקור בעברית (`hr-onboarding-he`).
- **e5:** מספרים מטבלה, וטענה שסותרת את "It is paid with the salary after the trip".

```bash
python -m pytest -q labs/13-rag-diagnostics/tests/test_ex3_claims.py
python labs/13-rag-diagnostics/claims.py --mine
python labs/13-rag-diagnostics/claims.py --show e1
python labs/13-rag-diagnostics/claims.py --llm anthropic:claude-haiku-5-5        # כ-0.3 סנט
```

מה השופט הלקסיקלי נתן במסלול הלא מקוון:
- **e1:** את הטענה השנייה הוא סימן not_found ולא contradicted.
- **e2:** תפס את המשפט המומצא.
- **e3:** "grounded", וזה נכון: השופט לא אמור לדעת שהמקור מיושן.
- **e4:** not_grounded, כי הוא עיוור לתרגום.
- **e5:** את "paid in cash" הוא סימן not_found ולא contradicted.

ענה על שלוש שאלות:
- באילו מהדוגמאות Haiku צדק והשופט הלקסיקלי טעה, ולהפך?
- למה e3 מראה ש-groundedness ונכונות הם שני מדדים שונים?
- מה מרוויחים מבדיקת הראיה בקוד, וכמה פעמים היא הורידה טענה ב-Haiku?

**4. אבחון מלא של שתי צנרות.** הסקריפט מריץ את כל 79 השאלות בשתי צנרות, על אותם chunks ועם אותו answerer:
- **baseline:** הצנרת של שיעור 9, BM25 ו-5 chunks.
- **best:** הצנרת של שיעור 12: BM25 ו-dense מאוחדים ב-RRF, שכתוב שאילתה (multi, decompose, translate) וסינון גרסאות.

לכל צנרת מודפסים כרשימה: כשלים לפי שלב, כשלים לפי סוג שאלה, המשפך (כמה שאלות שורדות כל שלב), והמדדים לפי שלב. בסוף מודפס אילו שאלות התוקנו, אילו נשברו, ואילו עברו משלב לשלב.

```bash
python labs/13-rag-diagnostics/run_diagnosis.py
python labs/13-rag-diagnostics/run_diagnosis.py --show q040,q073
python labs/13-rag-diagnostics/run_diagnosis.py --pipelines baseline --chunker fixed:100:0
python labs/13-rag-diagnostics/run_diagnosis.py --mine
python labs/13-rag-diagnostics/run_diagnosis.py --dense e5-small
```

במסלול הלא מקוון נמדד:
- **baseline:** 36 מתוך 79 עברו. הכשלים: not_retrieved 3, ranked_low 7, stale_version 6, false_refusal 6, ignored_context 13, wrong_citation 1, failed_to_refuse 7.
- **best:** 42 מתוך 79 עברו. not_retrieved ירד ל-0, ו-stale_version ירד ל-0. מנגד, ranked_low עלה ל-10 ו-false_refusal ל-8. 9 שאלות תוקנו (שבע מהן היו stale_version), ו-3 נשברו (q049, q051, q064).
- **עם `fixed:100:0`:** מופיעים 8 כשלים מסוג chunk_split.

ענה על ארבע שאלות:
- לאן "זזו" הכשלים כשהאחזור השתפר, ולמה זה צפוי?
- כמה מהכשלים של best הם בשלבי היצירה, ומה זה אומר על ה-answerer החילוצי?
- למה ב-multi_hop של best, 7 מתוך 11 הם ranked_low? רמז: הסתכל ב-`--show q040` על הפרומפט, ושים לב לכמה chunks של אותו מסמך.
- מה משותף ל-7 כשלי failed_to_refuse?

**5. אבחן את ה-trace בעצמך.** ב-`fixtures/traces.jsonl` יש שישה כשלים, באותו פורמט ש-`run_diagnosis.py` שומר. האחזור בכל אחד מהם אמיתי. התשובות ופסקי הדין של השופט נכתבו ביד, בסגנון של מודל אמיתי, כדי שכל trace יראה כשל אחד. הסקריפט מציג לכל trace: הסיפור, השאלה, מסמכי הזהב והסטטוס של כל ציטוט, המועמדים, כל chunk בפרומפט (ומי מהם מכיל ציטוט זהב), התשובה, הציטוטים, כיסוי העובדות ופסק הדין של השופט. הנה תקציר של כל אחד, כדי שתוכל לחשוב גם בלי להריץ:
- **T1 (q002, אש"ל בעיר רגילה):** שני ה-PDF של מדיניות הנסיעות נטענו מחדש עם loader חדש. ב-chunk השני בפרומפט כתוב "according to this table:", ואין אחריו טבלה. הציטוט מסומן `missing`. התשובה: 75 דולר, עם ציטוט של `fin-travel-2025`.
- **T2 (q052, Quiet Hours):** ה-chunker הוחלף ל-`fixed:100:0`. ה-chunk הראשון נגמר במילה "until". התשובה אומרת שבערב חג Quiet Hours נמשכות "until midnight", והשופט סימן את הטענה הזו not_found.
- **T3 (q040, multi-hop):** ה-baseline. בפרומפט יש ארבעה chunks של ה-postmortem ו-chunk אחד של תהליך ה-deploy. `eng-service-catalog` הוא המסמך הרביעי ברשימת המועמדים. התשובה מסבירה את הסיבה לתקלה, ואומרת שהבעלים לא מופיע במקורות.
- **T4 (q039, הדרכת אבטחה):** הצנרת best מצאה את `hr-onboarding-he` (בעברית) ושמה אותו במקום השני בפרומפט. התשובה: "not in the documents".
- **T5 (q015, מגבלת API לתוכנית Business):** k הועלה ל-20 על ה-retriever הדחוס, והפרומפט עכשיו כ-4,100 טוקנים. השורה "API rate limit (requests/min) | 60 | 300 | 1,000 | 5,000" נמצאת ב-chunk מספר 8. התשובה מונה פרטים אחרים מאותה טבלה, ואומרת שהמגבלה לא מופיעה.
- **T6 (q014, משך התקלה):** ה-postmortem במקום הראשון, עם "47 minutes". התשובה: "about two hours", "typical for SEV1 incidents", ו"failed over to the second region".

כתוב את התווית שלך לכל trace ב-`TRACE_GUESSES` שב-`mine.py`, ורק אחר כך הרץ את `--check`.

```bash
python labs/13-rag-diagnostics/traces.py
python labs/13-rag-diagnostics/traces.py --t T5 --full
python labs/13-rag-diagnostics/traces.py --check
```

ענה על שתי שאלות:
- באיזה trace הסימפטום הבולט מטעה, כלומר נראה כמו שלב אחר?
- איזה תיקון היית מציע לכל אחד מהשישה, ואיזה מהם יכול ליצור כשל חדש?

**6. לולאת תיקון.** הלולאה היא: אבחון, בחירת קטגוריית הכשל הגדולה ביותר שיש לה תיקון אוטומטי, הפעלת התיקון שלה, הרצה מחדש, ומדידה עם ה-gates של evalkit (שיעור 23; כאן הוא כלי, ושם תבנה אותו). ה-gates הם:
- `Threshold("answer_ok", 0.45)`.
- `NoSignificantDrop("answer_ok")` על כל השאלות.
- `NoSignificantDrop` לכל סוג שאלה, עם `max_drop=0.10`.

כולם בהשוואה מזווגת על אותן 79 שאלות, עם McNemar מדויק. אלה התיקונים:
- `versions` (stale_version)
- `hybrid` (not_retrieved)
- `k8` (ranked_low)
- `diverse` (ranked_low: לכל היותר 2 chunks לכל מסמך)
- `rerank` (ranked_low)
- `chunker` (chunk_split)
- `prompt` (שלבי היצירה, רק במסלול החי)

```bash
python labs/13-rag-diagnostics/fix_loop.py                      # auto
python labs/13-rag-diagnostics/fix_loop.py --fix versions
python labs/13-rag-diagnostics/fix_loop.py --fix diverse
python labs/13-rag-diagnostics/fix_loop.py --chunker fixed:100:0
```

במסלול הלא מקוון נמדד:
- **auto:** הקטגוריה הגדולה ביותר היא ignored_context (13), אבל אין לה תיקון אוטומטי. לכן הוא בחר ב-ranked_low (7) עם `k8`. ranked_low ירד ל-5, אבל אף שאלה לא תוקנה, ו-q016 נשברה (היא ציטטה עכשיו את המחירון הישן). הפסק: DO NOT SHIP.
- **`versions`:** stale_version ירד מ-6 ל-0, ו-answer_ok עלה מ-36 ל-42. McNemar נתן p=0.031. הפסק: SHIP.
- **`diverse`:** ranked_low ירד ב-1, אבל אף שאלה לא עברה. הפסק: NEUTRAL, הכשל רק זז שלב.
- **`--chunker fixed:100:0`, ואחריו `chunker`:** chunk_split ירד מ-8 ל-0, ו-answer_ok עלה מ-34 ל-36. אבל שאלה numeric אחת נשברה, וה-gate של numeric נכשל, כי 1 מתוך 9 זה 0.11, יותר מ-0.10.

ענה על שלוש שאלות:
- למה התיקון של הקטגוריה הגדולה ביותר הוא לא תמיד התיקון הנכון?
- מה מלמד המקרה של `diverse`?
- האם gate עם `max_drop=0.10` על קבוצה של 9 שאלות הוא סביר? מה היית משנה?

**7. הרצה חיה עם Haiku.** עכשיו התשובות והשופט אמיתיים. הרץ את שתי הצנרות, ואז הרץ מחדש רק את השופט על התשובות של Haiku, כדי להשוות שופטים על אותן תשובות.

```bash
python labs/13-rag-diagnostics/run_diagnosis.py --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5 --yes
python labs/13-rag-diagnostics/run_diagnosis.py --rejudge traces_best_anthropic-claude-haiku-5-5_anthropic-claude-haiku-5-5.jsonl --judge heuristic
python labs/13-rag-diagnostics/fix_loop.py --start best --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5 --fix prompt --yes
```

העלות המשוערת: כ-4 סנט לצנרת (תשובות ושופט), כ-8 סנט לשתיהן, ועוד כ-8 סנט ל-`fix_loop` החי. ענה על שלוש שאלות:
- איך התפלגות הכשלים השתנתה לעומת המסלול הלא מקוון?
- כמה hallucination ו-failed_to_refuse יש ל-Haiku?
- באיזה אחוז מהתשובות השופט הלקסיקלי מסכים עם Haiku, ובאילו שאלות הם חלוקים? פתח שתיים ידנית, והחלט מי צודק.

כתוב את המספרים שלך. אם הם סותרים משהו שכתוב כאן, המדידה שלך קובעת.

**8. (אופציונלי) NLI מקומי מול שופט LLM.** `NLIChecker` משתמש ב-`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`. זה מודל NLI עם כ-0.3 מיליארד פרמטרים, ברישיון MIT, שאומן על 27 שפות, כולל עברית, ומחזיר entailment, neutral או contradiction. המודל לא מפרק טענות, ולכן הסקריפט משתמש בפירוק של האדם מ-`claims_examples.jsonl`.

```bash
python labs/13-rag-diagnostics/claims.py --nli
```

ענה על שלוש שאלות:
- האם הוא תפס את היפוך השלילה של e1 ואת התרגום של e4?
- איך הוא הסתדר עם הטבלה של e5?
- כמה זמן לקחה כל טענה על המעבד שלך, לעומת קריאה ל-Haiku?

## עלות

- כל התרגילים רצים בחינם במסלול הלא מקוון.
- `claims.py` עם Haiku 5.5: 5 דוגמאות, 2 קריאות לכל אחת, כ-0.3 סנט.
- `run_diagnosis.py` חי: כ-4 סנט לצנרת. התשובות הן 79 קריאות של כ-1,400 טוקנים בקלט, והשופט כ-0.04 סנט לתשובה.
- `fix_loop.py` חי: שתי הרצות מלאות, כ-8 סנט.
- הסך הכול במסלול החי: כ-20 סנט.

## מה לבדוק כשמשהו לא עובד

- **`NotImplementedError` מ-`--mine`:** עוד לא מימשת את התרגיל. הרץ בלי `--mine`.
- **`ImportError: numpy`:** הצנרת best צריכה numpy. הרץ `--pipelines baseline`, או התקן את numpy.
- **`NLIChecker needs transformers and torch`:** התקן את PyTorch בגרסת CPU, ואחר כך את `transformers` ואת `sentencepiece`. אם הטוקנייזר מתלונן על המרה, התקן גם `protobuf`.
- **השופט החי החזיר שגיאה:** `check_claims` לא זורק חריגה. הוא מחזיר `error`, והשאלה מסווגת כאילו לא נשפטה. בדוק את `results/traces_*.jsonl`.
- **מספרים שונים מאלה שכאן:** כמעט תמיד זה הבדל בין `extractive` לבין Haiku, או בין `fake` לבין `e5-small`. כל סקריפט מדפיס בשורת ה-note אילו רכיבים לא מקוונים הוא הפעיל.
