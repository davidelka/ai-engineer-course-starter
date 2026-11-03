# מעבדה 12: Advanced Retrieval and Reranking

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/12-advanced-retrieval/requirements.txt
python -m pytest -q                                      # בדיקות הסביבה, כולל tests/test_ragkit_hybrid.py החדש
python -m pytest -q labs/12-advanced-retrieval/tests     # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

אין תלויות חדשות מעבר לשיעור 10. המסלול הלא מקוון צריך רק numpy. ה-cross-encoders המקומיים צריכים את sentence-transformers עם PyTorch בגרסת CPU, בדיוק כמו בשיעור 10. בהרצה הראשונה הם יורדים מ-Hugging Face: `BAAI/bge-reranker-v2-m3` שוקל כ-2.3GB, ו-`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` שוקל כ-470MB. אם ההורדה נתקעת, אפשר להוריד ידנית עם `hf download BAAI/bge-reranker-v2-m3`.

**חשוב לדעת:** סביבת הקורס שבה נבנתה המעבדה לא מגיעה ל-Hugging Face ולא ל-API בתשלום. לכן כל המספרים שמופיעים כאן ובאתר נמדדו במסלול הלא מקוון: embedder מזויף, rewrites שנכתבו ביד, ו-reranker מזויף. הם בודקים שהצנרת עובדת, אבל הם לא מראים את האיכות של e5, של Claude או של cross-encoder. את המספרים האמיתיים תמדוד אצלך.

## שלושת המסלולים

- **מסלול לא מקוון, חינם:** `--dense fake --llm replay --reranker fake`. ה-embedder המזויף הוא `HashingEmbedder` משיעור 10. הוא לקסיקלי, ולכן לא ימצא אף תרגום. ה-LLM במצב `replay` הוא `llmkit.LLM` אמיתי, שה-HTTP שלו נענה מקומית דרך `httpx.MockTransport`: הבקשה נבנית כמו מול Anthropic, כולל הסכמה, ורק התשובה מגיעה מקובץ. ה-rewrites מגיעים מ-`fixtures/rewrites.jsonl`, שבו 69 rewrites **שנכתבו ביד** בסגנון שמודל קטן כותב בלי להכיר את הקורפוס. ה-"שופט" של ה-LLM reranker במצב הזה הוא חפיפה לקסיקלית. העלות שמודפסת היא הערכה של מה ש-Haiku היה גובה.
- **מסלול מקומי, חינם:** `--dense e5-small` (ברירת המחדל) ו-`--reranker ce:bge-m3` או `ce:mmarco`. המטמון של ה-embeddings משותף עם שיעור 10 (`labs/10-embeddings/results/cache/`), ולכן אם הטמעת שם את Acme, לא יוטמע כלום מחדש.
- **מסלול חי, בתשלום:** `--llm anthropic:claude-haiku-5-5` ל-rewriting, ו-`--reranker llm:anthropic:claude-haiku-5-5` או `cohere:rerank-v4.0-fast`. כל סקריפט שמוציא כסף מבקש אישור לפני ההרצה.

## מה חדש

- **`ragkit/fusion.py`:** `rrf(rankings, k=60, weights=None)`, `minmax`, `zscore` ו-`weighted_fusion(score_lists, weights, normalize)`. שוויון נשבר באופן דטרמיניסטי: ציון, אחר כך המקום הטוב ביותר שהפריט קיבל ברשימה כלשהי, ואחר כך המזהה. הסכומים מחושבים עם `math.fsum`, ולכן סדר הרשימות לא משנה את התוצאה.
- **`ragkit/hybrid.py`:** `HybridRetriever({"bm25": ..., "dense": ...}, method="rrf" | "weighted")`. כל retriever בפנים מתבקש בדיוק `fetch_k` תוצאות (ברירת המחדל 50), וכל Hit שומר את הציון של כל שלב, את המקום שלו בכל רשימה (`rank:bm25`, `rank:dense`) ואת הציון המאוחד (`rrf` או `fused`). הוא גם Index, ולכן `IngestPipeline` ו-`rag.answer` עובדים איתו בלי שינוי.
- **`ragkit/query.py`:** `QueryRewriter`, שמבצע קריאה מובנית אחת ל-LLM עם הסכמה `QueryRewrite`: תרגום, ניסוחים חלופיים (multi-query), תתי-שאלות (decomposition), שאלה כללית יותר (step-back) ותשובה היפותטית (HyDE). `RewritingRetriever` מחפש את כל השאילתות ומאחד אותן עם RRF. התרגום מחופש רק בין ה-chunks בשפת היעד.
- **`ragkit/versions.py`:** `drop_superseded`, עם שני מצבים: `retrieved` (משמיט מסמך רק אם הגרסה החדשה שלו נמצאת גם היא בתוצאות) ו-`corpus` (משמיט כל מסמך שיש לו גרסה חדשה בקורפוס). יש גם `boost_recent` (העדפה לפי `effective_date`), `VersionAwareRetriever` ו-`stale_at_k`.
- **`ragkit/rerank/`:** הפרוטוקול `Reranker`, ו-`RerankingRetriever(base, reranker, fetch_k=30)`. המימושים: `CrossEncoderReranker` (sentence-transformers), `CohereReranker` (httpx), `LLMReranker` (llmkit structured), ו-`OverlapReranker`, תחליף מזויף ולקסיקלי לבדיקות. `make_reranker("ce:bge-m3" | "cohere:rerank-v4.0-fast" | "llm:anthropic:claude-haiku-5-5" | "fake")`.
- **`ragkit/replay.py`:** `replay_llm(responder)`, ה-LLM הלא מקוון.
- **`ragkit/ablation.py`:** `evaluate_stage` ו-`format_stage`: איכות לפי סוג שאלה, מסמכים מיושנים ב-top 5, זמן תגובה (p50, p95) ועלות לשאלה.
- **`mine.py`:** הקוד שלך לתרגילים 1, 2 ו-5.

## הנתונים שהמעבדה משתמשת בהם

- **הקורפוס:** `data/acme/corpus/docs/`, 55 מסמכים, 9 מהם בעברית, מחולקים ל-210 chunks עם ה-chunker של ה-baseline (`heading:400:40:150`). כל retriever רואה את `context_text()` של ה-chunk: הכותרת, נתיב הסעיף, ואחריהם הטקסט.
- **שאלות הזהב:** `data/acme/corpus/golden/qa.jsonl`, 79 שאלות, 69 מהן עם מסמכי מקור (`source_ids`). לפי סוג: single_hop (19), multi_hop (11), numeric (9), version_conflict (11), acronym (8), hebrew (11). 6 שאלות מסומנות `cross-lingual`: q039 (באנגלית, המקור `hr-onboarding-he`), q069 (בעברית, המקור `eng-service-catalog`), ו-q011, q047, q049, q068, שדורשות מסמך בכל שפה.
- **גרסאות:** רק הגרסה החדשה של מדיניות מצביעה על הישנה, בשדה `supersedes` במטא-דאטה. תשעה קישורים כאלה קיימים בקורפוס:
  - `hr-vacation-2024` הוחלף ב-`hr-vacation-2026` וב-`hr-vacation-2026-he`.
  - `hr-remote-work-2025` הוחלף ב-`hr-remote-work-2026`.
  - `hr-parental-leave-2025` הוחלף ב-`hr-parental-leave-2026`.
  - `it-password-policy-2024` הוחלף ב-`it-password-mfa-2026`.
  - `it-saas-access-v2-1` הוחלף ב-`it-saas-access-v2-2`.
  - `sales-pricing-2025` הוחלף ב-`sales-pricing-2026`, ו-`sales-sla-2025` ב-`sales-sla-2026` (PDF).
  - `fin-procurement-2025` הוחלף ב-`fin-procurement-2026`, ו-`fin-travel-2025` ב-`fin-travel-2026` (PDF).
- **מסמכים מיושנים בשאלות הזהב:** כל שאלת version_conflict מסומנת `stale:<doc_id>` עם המסמך שייתן תשובה ישנה. בשלוש מהן אין קישור `supersedes`: ב-q004 (`co-allhands-2026-01`, סיכום ישיבה שתוקן אחר כך), ב-q005 (`eng-leads-sync-2026-05`, "החלטה" שבוטלה) וב-q011 (הצעה בישיבה שלא אומצה).
- **ה-baseline משיעורים 9 ו-10:** ב-BM25, recall@5 הוא 0.906 על כל השאלות, 0.727 על multi_hop, ו-0.333 על cross-lingual. בשיעור 9 נמצא ש-5 מתוך 11 התשובות של version_conflict ציטטו את הגרסה הישנה.

## התרגילים

**1. Reciprocal Rank Fusion (קוד).** ממש את `rrf(rankings, k=60, weights=None)` ב-`mine.py`. הנוסחה: לכל מזהה, סכום של `w_i / (k + rank_i)` על כל הרשימות שהוא מופיע בהן, כאשר rank מתחיל מ-1. הדרישות:
- מזהה שחסר ברשימה לא מקבל ממנה כלום, לא עונש ולא אפס.
- מזהה שמופיע פעמיים באותה רשימה נספר רק במקום הראשון שלו.
- הסכום מחושב עם `math.fsum`.
- שוויון: קודם המזהה עם המקום הטוב ביותר ברשימה כלשהי, ואחר כך לפי `str(id)`.
- `ValueError` אם מספר המשקלות לא מתאים, או אם k שלילי.

דוגמה לבדיקה ביד: `rrf([["a","b","c"],["c","a"]])` נותן a = 1/61 + 1/62 = 0.03252, c = 1/63 + 1/61 = 0.03227, b = 1/62 = 0.01613.

אחר כך הרץ את הדמו. הוא מציג את ה-chunks המובילים של BM25 ושל dense לשאלה q040 ("Which team owns the service whose configuration change caused the August 2026 flow-api outage..."; המקורות `eng-pm-2026-08-api` ו-`eng-service-catalog`), כותב כל איבר של RRF במפורש, ומראה איך ה-top 5 משתנה עם k.

```bash
python -m pytest -q labs/12-advanced-retrieval/tests/test_ex1_rrf.py
python labs/12-advanced-retrieval/fusion_demo.py --mine
python labs/12-advanced-retrieval/fusion_demo.py --q q050 --mine
python labs/12-advanced-retrieval/fusion_demo.py --dense e5-small
```

ענה על שלוש שאלות:
- איפה דירג BM25 את `eng-service-catalog#4`, איפה דירג אותו dense, ולאיזה מקום RRF העלה אותו?
- ב-q050, מה קרה ל-recall@5 כש-k עבר מ-0 ל-60, ולמה?
- למה ב-RRF לא צריך לנרמל ציונים?

**2. Weighted fusion ונרמול (קוד).** ממש את `minmax_normalize(scores)` ואת `weighted_fusion(score_lists, weights, missing=0.0)`. כשכל הציונים שווים, או כשיש רק ציון אחד, כולם מקבלים 1.0. מזהה שחסר ברשימה מקבל ממנה `missing`. הדוגמה מה-docstring: BM25 `{a: 10, b: 5, c: 0}` ו-dense `{b: 0.9, c: 0.8}`, עם משקלות 0.5 ו-0.5, נותנים b = 0.75, a = 0.5, c = 0.0. שים לב ש-c היה שני אצל dense, וקיבל ממנו 0, בדיוק כמו a ש-dense לא החזיר בכלל.

```bash
python -m pytest -q labs/12-advanced-retrieval/tests/test_ex2_weighted.py
python labs/12-advanced-retrieval/fusion_demo.py --part weighted --mine
```

הסקריפט מציג את הציונים הגולמיים של שני ה-retrievers ל-q040 (BM25 בסביבות 16 עד 28, וה-cosine של ה-embedder המזויף בין 0.34 ל-0.48), את הערכים אחרי min-max, ואת ה-top 5 בחמישה משקלות. אחר כך הוא מראה שלוש מלכודות על מספרים קטנים. ענה: באיזה מצב היית מעדיף weighted על RRF, ומה צריך כדי לבחור את המשקלות?

**3. חיפוש היברידי על שאלות הזהב.** הסקריפט משווה על 69 השאלות את BM25, את dense, את RRF עם k=60 ואת weighted fusion עם שלושה משקלות ועם z-score, ומדפיס recall@5 ו-MRR לכל סוג שאלה ולשורת cross-lingual, כרשימה. אחר כך הוא סופר בכמה שאלות רק BM25 מוצא מסמך רלוונטי ב-top 5, בכמה רק dense, בכמה שניהם ובכמה אף אחד. הספירה הזו היא הסיבה שאיחוד עוזר.

```bash
python labs/12-advanced-retrieval/hybrid_eval.py --dense fake          # לא מקוון: בדיקת צנרת
python labs/12-advanced-retrieval/hybrid_eval.py                       # e5-small
python labs/12-advanced-retrieval/hybrid_eval.py --sweep-k --mine
```

במסלול הלא מקוון נמדד: BM25 0.906, dense מזויף 0.867, ו-RRF 0.903 על כל השאלות. על multi_hop, RRF עלה ל-0.758 לעומת 0.727 ב-BM25. ענה על שלוש שאלות:
- עם e5-small, באילו סוגים RRF טוב משניהם?
- באילו סוגים הוא רק "באמצע", ולמה?
- כמה שאלות מוצא רק dense, ומה משותף להן?

**4. Query rewriting.** קריאה מובנית אחת לכל שאלה (`QueryRewriter`) מחזירה חמישה שדות: `translation`, `variants`, `subquestions`, `step_back` ו-`hypothetical_answer`. קודם תסתכל על ה-rewrites של שלוש שאלות:
- q040 (multi-hop): המקורות הם `eng-pm-2026-08-api` ו-`eng-service-catalog`.
- q039: באנגלית, והמקור `hr-onboarding-he` בעברית.
- q069: בעברית, והמקור `eng-service-catalog` באנגלית.

אחר כך הרץ את ההשוואה של כל מצב לחוד ושל השילוב multi+decompose+translate.

```bash
python labs/12-advanced-retrieval/rewrite.py --show q040,q039,q069
python labs/12-advanced-retrieval/rewrite.py                                   # BM25 + rewrites מהקובץ
python labs/12-advanced-retrieval/rewrite.py --orig-weight 2
python labs/12-advanced-retrieval/rewrite.py --llm anthropic:claude-haiku-5-5 --record   # כ-1.5 סנט
python labs/12-advanced-retrieval/rewrite.py --base hybrid --dense e5-small
```

במסלול הלא מקוון, עם BM25 כבסיס, נמדד:
- רק תרגום: cross-lingual עלה מ-0.333 ל-1.000, אבל ה-MRR הכללי ירד מ-0.879 ל-0.609, וה-recall@5 של hebrew ירד מ-0.864 ל-0.727.
- השילוב multi+decompose+translate: 0.940 על כל השאלות ו-0.803 על multi_hop.

אחרי `--record`, הרצות `replay` הבאות משתמשות ב-rewrites האמיתיים שלך מ-`results/rewrites_recorded.jsonl` במקום בשורות שנכתבו ביד. ענה על שלוש שאלות:
- למה תרגום לבד פוגע בשאלות שהמקור שלהן באותה שפה?
- מה עושה `--orig-weight 2`?
- האם תתי-השאלות של Haiku ל-q040 עצמאיות, או שהשנייה תלויה בתשובה לראשונה ("that service")? מה זה אומר על decomposition בצעד אחד לעומת אחזור איטרטיבי?

**5. סינון לפי גרסה (קוד).** ממש את `drop_superseded(hits)`: משמיטים כל Hit שהמסמך שלו מופיע ב-`supersedes` של מסמך **אחר** שנמצא גם הוא ברשימה. הדרישות:
- הסדר נשמר, ומחזירים אובייקטים חדשים עם rank ממוספר מחדש מ-1.
- `supersedes` יכול להיות מחרוזת או רשימה.
- מסמך לא משמיט את עצמו.
- אם הגרסה החדשה לא נמצאה, הישנה נשארת.

הדוגמה: הרשימה `hr-vacation-2024`, `hr-vacation-2026` (עם `supersedes: hr-vacation-2024`), `hr-sick-leave` הופכת ל-`hr-vacation-2026`, `hr-sick-leave`.

```bash
python -m pytest -q labs/12-advanced-retrieval/tests/test_ex5_versions.py
python labs/12-advanced-retrieval/versions_eval.py --dense fake --mine
python labs/12-advanced-retrieval/versions_eval.py --mine
```

הסקריפט משווה חמש מדיניויות מעל ה-hybrid: בלי סינון, `retrieved`, `corpus`, ו-`recent` במשקלות 0.1 ו-0.3. לכל אחת הוא מדפיס את המדדים ואת מספר שאלות ה-version_conflict שבהן מסמך מיושן עדיין ב-top 5. אחר כך הוא מדפיס רשימה לכל שאלה, ובסוף שאלה ששואלת **על** הגרסה הישנה. במסלול הלא מקוון נמדד:
- בלי סינון: מסמך מיושן ב-top 5 ב-9 מתוך 11 שאלות, ו-MRR של 0.682 על version_conflict.
- עם `retrieved`: מסמך מיושן ב-1 מתוך 11, ו-MRR של 0.955. ה-MRR הכללי עלה מ-0.831 ל-0.892.
- `recent` במשקל 0.3: ה-MRR הכללי ירד ל-0.643.

ענה על שלוש שאלות:
- איזו שאלה נשארה עם מסמך מיושן, ולמה הסינון לא יכול לתקן אותה?
- מה המחיר של `corpus` מול `retrieved`?
- למה `recent` פוגע בשאר סוגי השאלות?

**6. Reranking.** שלב ראשון: hybrid, ואחריו סינון גרסאות. 30 המועמדים הראשונים עוברים ל-reranker. הסקריפט מדפיס recall@5 ו-MRR לפי סוג שאלה, ואת זמן התגובה (p50, p95) והעלות של שלב ה-reranking לשאלה. `--sweep-fetch` מריץ את ה-reranker הראשון עם 10, 20, 30 ו-50 מועמדים. אלה ה-rerankers:
- `ce:bge-m3`: `BAAI/bge-reranker-v2-m3`, כ-568 מיליון פרמטרים, Apache-2.0, רב-לשוני.
- `ce:mmarco`: כ-118 מיליון פרמטרים, Apache-2.0. אומן על 14 שפות, ועברית לא ביניהן, ולכן בדוק אותו על שאלות hebrew.
- `llm:...`: Haiku נותן ציון בין 0 ל-10 לכל קטע, בקריאה מובנית אחת.
- `cohere:...`: API מנוהל. צריך `COHERE_API_KEY` ב-`.env`.

```bash
python labs/12-advanced-retrieval/rerank_eval.py --dense fake                      # fake + llm:replay, לא מקוון
python labs/12-advanced-retrieval/rerank_eval.py --rerankers ce:mmarco,ce:bge-m3
python labs/12-advanced-retrieval/rerank_eval.py --rerankers ce:bge-m3 --sweep-fetch 10,20,50
python labs/12-advanced-retrieval/rerank_eval.py --rerankers llm:anthropic:claude-haiku-5-5   # כ-4 סנט
python labs/12-advanced-retrieval/rerank_eval.py --rerankers cohere:rerank-v4.0-fast          # אופציונלי
```

ה-reranker המזויף לקסיקלי. הוא פוגע ב-cross-lingual (מ-0.500 ל-0.250), כי הוא לא מבין תרגום. זו בדיוק הסיבה לא לשפוט לפיו. רשום לעצמך:
- כמה ms לשאלה לוקח bge-m3 על המעבד שלך, וכמה זמן לקח לטעון אותו.
- האם הוא שיפר את multi_hop ואת hebrew.
- כמה עלה ה-LLM reranker לשאלה, לעומת ההערכה של כ-0.0006 דולר.
- מאיזה fetch_k השיפור נעצר.

**7. Ablation מלא.** הסקריפט בונה שבעה שלבים, וכל שלב מוסיף דבר אחד לקודם. כולם עובדים על אותם 210 chunks ועל אותן 69 שאלות:
1. BM25.
2. dense לבד (להשוואה, מחוץ לשרשרת).
3. איחוד נאיבי לסירוגין, כמו בשיעור 10.
4. RRF.
5. query rewrite.
6. סינון גרסאות.
7. rerank.

לכל שלב מודפסים, כרשימה: recall@5 ו-MRR עבור ALL, multi_hop, version_conflict, hebrew ו-cross-lingual, עם השינוי מהשלב הקודם. אחריהם מסמכים מיושנים ב-top 5, זמן תגובה ועלות לשאלה.

```bash
python labs/12-advanced-retrieval/ablation.py --dense fake --llm replay --reranker fake   # $0
python labs/12-advanced-retrieval/ablation.py --reranker ce:bge-m3                        # e5 + bge, חינם
python labs/12-advanced-retrieval/ablation.py --llm anthropic:claude-haiku-5-5 --reranker ce:bge-m3 --yes
```

במסלול הלא מקוון, שלב 6 (סינון גרסאות) הוריד את המסמכים המיושנים מ-10 ל-2 מתוך 11, והעלה את ה-MRR הכללי ב-0.043. שלב 5 עם ה-rewrites שנכתבו ביד ושלב 7 עם ה-reranker המזויף לא עזרו, וחלקם אף פגעו. זה צפוי מרכיבים מזויפים.

כתוב פסקה לכל אחת משלוש השאלות:
- איזה שלב תרם הכי הרבה לכל סוג שאלה?
- איזה שלב עולה הכי הרבה בזמן תגובה ובכסף?
- איזו תצורה היית בוחר ל-Company Brain, בתקציב של p95 מתחת ל-1.5 שניות ופחות מ-0.001 דולר לשאלה?

**8. מעקב אחרי שאלה אחת.** `--trace` מדפיס, לשאלה אחת, את 5 המסמכים המובילים בכל שלב, עם כל הציונים שהשלבים כתבו ל-`Hit.scores`: `bm25`, `vector`, `rank:bm25`, `rank:dense`, `rrf` ו-`rerank`. בשלב ה-rewrite הוא מדפיס גם את השאילתות שחופשו.

```bash
python labs/12-advanced-retrieval/ablation.py --dense fake --llm replay --reranker fake --trace q041
python labs/12-advanced-retrieval/ablation.py --trace q001
python labs/12-advanced-retrieval/ablation.py --trace q039 --reranker ce:bge-m3
```

על מה להסתכל בשלוש השאלות:
- q041 שואלת על זיכוי SLA לאוגוסט. המקורות הם ה-postmortem (זמינות 99.89%) וטבלת הזיכויים ב-PDF של `sales-sla-2026`. באיזה שלב `sales-sla-2025` נעלם?
- ב-q001, ראה את `hr-vacation-2024` נעלם בשלב 6.
- ב-q039, ראה מה ה-reranker עושה למסמך העברי.

## עלות

- כל התרגילים רצים בחינם במסלול הלא מקוון או המקומי.
- Rewriting עם Haiku 5.5: בערך 700 טוקנים בקלט ו-250 בפלט לשאלה. זה כ-0.0002 דולר לשאלה, וכ-1.5 סנט ל-69 שאלות.
- LLM reranker עם Haiku 5.5: 30 קטעים של עד 700 תווים, בערך 6,000 טוקנים בקלט. זה כ-0.0006 דולר לשאלה, וכ-4 סנט ל-69 שאלות.
- Cohere: התמחור השתנה באוקטובר 2026. Rerank 4 מחויב לפי "חיפוש" (2 עד 2.5 דולר לאלף חיפושים). לפי אתר מעקב מחירים, Rerank 5 מחויב לפי טוקנים (0.02 עד 0.05 דולר למיליון). בדוק ב-cohere.com/pricing. בכל מקרה מדובר בכמה סנטים לכל היותר, ויש מפתח ניסיון חינמי.
- הסך הכול במסלול החי: פחות מ-10 סנטים.

## מה לבדוק כשמשהו לא עובד

- **`ImportError: sentence-transformers`:** התקן את PyTorch בגרסת CPU, ואחר כך את sentence-transformers, כמו בשיעור 10.
- **ההורדה מ-Hugging Face נתקעת:** הרץ `hf download BAAI/bge-reranker-v2-m3` פעם אחת.
- **`COHERE_API_KEY is not set`:** הוסף את המפתח ל-`.env`. הקובץ כבר ב-.gitignore.
- **rewrite החזיר JSON לא תקין:** `QueryRewriter` הוא fail-open. במקרה כזה הוא מחפש רק את השאלה המקורית, וה-trace מראה `ERROR`.
- **מספרים שונים מאלה שכאן:** אלה כמעט תמיד הבדלים בין `fake` לבין `e5-small`, או בין rewrites שנכתבו ביד לבין rewrites אמיתיים. בדוק איזה מודל כל סקריפט מדפיס בשורת ה-note.
