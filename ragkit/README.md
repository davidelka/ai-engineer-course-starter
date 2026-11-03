# ragkit

ragkit היא ספריית ה-RAG של הקורס. היא נבנתה בשיעור 9, ושיעורים 10 עד 13, פרויקטי האמצע ו-Company Brain מוסיפים לה מודולים חדשים בלי לשכתב את הקיימים. הספרייה כתובה ב-Python טהור, והתלויות שלה הן pypdf, python-docx ו-beautifulsoup4 (ו-lxml אם הוא מותקן). הקוד מתועד בפירוט בתוך הקבצים, והמסמך הזה רק נותן את התמונה הכללית.

## הצינור

```
files ──loaders──▶ Document ──clean──▶ Document ──Chunker──▶ [Chunk] ──Index.add──▶ Retriever
                                                                                      │
question ───────────────────────────────────────────────────────▶ Retriever.search ──┘
        ──▶ [Hit] ──rag.build_request──▶ ChatRequest ──llm.complete──▶ RagAnswer (citations checked)
```

- **`types.py`** מגדיר שלושה טיפוסים: `Document`, `Chunk` ו-`Hit`. זה החוזה בין כל השלבים. החוזה החשוב ביותר הוא ש-`doc.text[c.start:c.end] == c.text` מתקיים תמיד. בזכותו ציטוט מצביע על טווח מדויק בטקסט, וכל chunk נושא איתו עותק של המטא-דאטה של המסמך: כותרת, גרסה, `effective_date`, `classification`, שפה, `supersedes` ופורמט. כך אפשר לסנן ולצטט גם כשה-chunk נמצא לבד בתוך אינדקס.
- **`loaders/`** ממיר קבצים ל-`Document`. כל loader מקבל `(path, bytes, **options)` ומחזיר `LoadResult`. כל הפורמטים יוצאים באותה צורה: כותרות כ-`#`, פריטי רשימה כ-`- ` ושורות טבלה כ-`a | b`. בזכות זה ה-chunker לפי כותרות עובד על כולם. קובץ צד בשם `<stem>.meta.yaml` גובר על מה שכתוב בקובץ עצמו.
- **`clean.py`** מטפל בנרמול: NFC, הסרת תווים בלתי נראים ותווי bidi, גרשיים, ניקוד ורווחים. אותו נרמול רץ גם על שאילתות ועל ציטוטים, כדי ששני הצדדים של כל השוואה ייראו אותו דבר.
- **`tokens.py`** מגדיר `Tokenizer` עם `count` ועם `spans`. יש שני מימושים: tiktoken (o200k), ו-approx, שהוא דטרמיניסטי ומשמש את הבדיקות.
- **`structure.py`** מוצא כותרות ונתיבי סעיפים.
- **`chunking/`** מכיל את המחלקה `Chunker`. היא מחליטה רק על טווחים, ו-`split()` בונה מהם `Chunk`s באותה דרך לכל האסטרטגיות. מוגדרות ארבע אסטרטגיות: `fixed`, `recursive`, `heading` ו-`sentence`. המחרוזת `make_chunker("heading:400:40")` יוצרת chunker לפי מפרט.
- **`manifest.py` ו-`pipeline.py`** מטפלים ב-ingestion אינקרמנטלי. ה-hash של כל קובץ מחושב מהבייטים הגולמיים ומקובץ הצד שלו, ומחולק לארבע קבוצות: added, changed, unchanged ו-removed. אם ה-pipeline עצמו השתנה (chunker אחר או אפשרויות loader אחרות), כל המסמכים נחשבים changed. המצב נשמר בדיסק בשני קבצים: `manifest.json` ו-`chunks.jsonl`.
- **`retrieval/`** מגדיר את הפרוטוקול `Retriever.search(query, k, where)`. בנוסף יש בו מסננים על מטא-דאטה (`where`), ו-`BM25Index` עם ניתוח בסיסי של תחיליות בעברית.
- **`rag.py`** בונה פרומפט עם מקורות ממוספרים ומטא-דאטה, מפענח `[n]`, ומסמן ציטוטים שמצביעים על מקור שלא נשלח.
- **`fake.py`** מכיל את `ExtractiveAnswerer`, תחליף חינמי לשלב היצירה (הוא לא מודל שפה).
- **`evaluate.py`** מכיל כיסוי ציטוטים (covered, split או missing), פגיעות באחזור לפי סוג שאלה, ובדיקות זולות על תשובות.
- **`acme.py`** מכיל קיצורי דרך לקורפוס של Acme.

## שיעור 10: embeddings וחיפוש וקטורי

המודולים האלה צריכים numpy (ו-faiss-cpu ו-sentence-transformers רק כשמשתמשים בהם). `import ragkit` לא טוען אותם עד שניגשים אליהם, כך שהקוד של שיעור 9 רץ גם בלי numpy.

- **`embed/`**: הפרוטוקול `Embedder` ושלושה מימושים. `HashingEmbedder` הוא תחליף דטרמיניסטי וחינמי לבדיקות. הוא לקסיקלי ולא סמנטי, ולכן אסור לשפוט לפיו מודלים. `SentenceTransformerEmbedder` מריץ מודל פתוח מקומית, עם presets: `e5-small` (ברירת המחדל, 384 ממדים, עם התחיליות `query:` ו-`passage:`), `e5-base`, `bge-m3` ו-`qwen3-0.6b`. `OpenAIEmbedder` עובד מעל httpx, תומך בפרמטר `dimensions`, ועוקב אחרי טוקנים ועלות. `CachedEmbedder` שומר כל וקטור בקובץ SQLite לפי sha256 של `model_id`, סוג הטקסט (query או document) והטקסט עצמו. `make_embedder("e5-small", cache_dir=...)` בונה embedder ממחרוזת.
- **`vectors/`**: הפרוטוקול `VectorStore`, ושני מימושים. `NumpyVectorStore` מבצע חיפוש מדויק, עם סינון לפני הדירוג ושמירה לדיסק. `FaissVectorStore` מקבל מחרוזת `index_factory`, למשל `Flat`, `HNSW32`, `IVF64,Flat` או `IVF64,PQ16`, ומסנן עם `IDSelectorBatch`, או בחיפוש מדויק כשמעט שורות עוברות את הסינון. ב-`vecmath.py` נמצאות פונקציות העזר: `l2_normalize`, `similarity` (cosine, dot ו-l2), `top_k`, `cosine_top_k` ו-`truncate_dims` (קיצוץ Matryoshka).
- **`dense.py`**: `DenseRetriever(embedder, store)`. הוא retriever ו-Index בדיוק כמו `BM25Index`, וכל Hit שלו נושא `scores["vector"]`.
- **`metrics.py`**: recall@k, hit@k, reciprocal rank ו-MRR ברמת המסמך, ו-`run_queries` עם `summarize`, שמחשבים אותם על שאלות הזהב לפי סוג שאלה. יש גם שורה נפרדת לשאלות שמסומנות `cross-lingual`.

## נקודות הרחבה לשיעורים הבאים

- **פורמט חדש:** `register_loader(".pptx", fn)`.
- **אסטרטגיית chunking חדשה** (למשל semantic chunking בשיעור 10): יורשים מ-`Chunker`, מממשים `spans(doc)`, ורושמים ב-`chunking.CHUNKERS`.
- **Embeddings** (שיעור 10, מומש): `ragkit/embed/` עם הפרוטוקול `Embedder` (`embed_documents(texts)` ו-`embed_queries(texts)`, שמחזירים מערך numpy מסוג float32 בצורה `(n, dim)`, ועם `model_id`, `dim` ו-`normalized`). מודל חדש מממש את שתי המתודות. מה שמוטמע הוא `Chunk.context_text()`, ולא רק הטקסט.
- **Vector store** (שיעור 11): מחלקה שמממשת את הפרוטוקול `ragkit.vectors.VectorStore`: `add(chunks, vectors)`, `remove(doc_id)`, `search(vector, k, where) -> list[Hit]`, `len()`, `dim` ו-`metric`. היא נכנסת ל-`DenseRetriever(embedder, store=...)` בלי שינוי, וה-retriever עצמו עובד עם `IngestPipeline(index=...)` ועם `rag.answer`. המסננים ב-`retrieval.base.matches` מגדירים את הסמנטיקה שגם vector store צריך לכבד, ומסד נתונים מנוהל מתרגם אותם לשפת הסינון שלו. רושמים store חדש ב-`ragkit.vectors.STORES`.
- **Hybrid ו-reranking** (שיעור 12): retriever שעוטף שני retrievers או יותר. מיזוג הדירוגים נעשה למשל עם RRF, וכל שלב כותב את הציון שלו ל-`Hit.scores`.
- **Evaluation** (שיעור 13): מרחיבים את `evaluate.py` עם LLM judge ועם בדיקה של עובדות (answer_facts). ה-`RagAnswer` כבר שומר את הבקשה, את ה-hits ואת התוצאה.
- **הרשאות** (Company Brain): `where={"classification": [...]}` לפי ההרשאה של המשתמש. הסינון קורה לפני הדירוג, ולא אחריו.
- **ציטוטים מקוריים של Claude:** בלוקים מסוג `search_result` עם `citations.enabled` מחזירים את הטווח המדויק שצוטט. כדי להשתמש בהם צריך ש-llmkit ידע לשלוח בלוקי תוכן כאלה. היום `rag.py` עושה ציטוטים מבוססי פרומפט, ובודק אותם בקוד.
- **Transform לפני chunking:** `IngestPipeline(transform=fn)`, למשל להסרת PII (שיעור 27).

## שיעור 11: מסדי נתונים וקטוריים בייצור

המודולים האלה נטענים רק כשמייבאים אותם ישירות, למשל `from ragkit.vectors.qdrant_store import QdrantVectorStore`. כך `import ragkit` ו-`import ragkit.vectors` לא תלויים ב-qdrant-client, ב-psycopg או ב-boto3. שלושת ה-stores מממשים את אותו פרוטוקול `VectorStore` משיעור 10, ולכן כל אחד מהם נכנס ל-`DenseRetriever(embedder, store=...)` ולכל מה שנבנה מעליו בלי שינוי.

- **`vectors/qdrant_store.py`:** ‏`QdrantVectorStore(url=... | location=":memory:" | client=..., collection, m, ef_construct, ef_search, full_scan_threshold, quantization=None|"scalar"|"binary"|"product"|"turbo", rescore, oversampling, exact, acorn)`. פרטי המימוש:
  - מזהה הנקודה הוא uuid5 של `chunk.id`, ולכן הוספה חוזרת היא upsert.
  - המטא-דאטה נשמרת כשדות payload ברמה העליונה, ו-`_chunk` מחזיק את ה-chunk המלא.
  - payload indexes נוצרים לפני הנתונים, כדי ש-Qdrant יבנה את הקשתות של filterable HNSW.
  - ‏`search(..., ef=, exact=)` דורס פרמטרים לשאילתה בודדת. ‏`info()` ו-`snapshot()` משמשים לתפעול.
  - **מצב `:memory:` מחפש בחיפוש מדויק**, ומתעלם מ-HNSW ומ-quantization. הוא מתאים לבדיקות בלבד.
- **`vectors/pgvector_store.py`:** ‏`PgVectorStore(dsn | conn=..., table, index="hnsw"|"ivfflat"|None, m, ef_construction, lists, ef_search, iterative_scan="off"|"relaxed_order"|"strict_order", max_scan_tuples, probes, halfvec)`. פרטי המימוש:
  - הטבלה: `id`, ‏`doc_id`, ‏`meta jsonb` (עם GIN), ‏`chunk jsonb`, ‏`embedding vector(d)`.
  - ההגדרות לכל שאילתה נקבעות עם `SET LOCAL` בתוך הטרנזקציה.
  - ‏`explain()` מחזיר EXPLAIN ANALYZE.
  - ה-SQL נבנה בפונקציות טהורות (`schema_sql`, ‏`index_sql`, ‏`session_sql`, ‏`search_sql`), ולכן נבדק בלי מסד נתונים.
- **`vectors/s3vectors_store.py`:** ‏`S3VectorsStore(boto3.client("s3vectors"), bucket, index)`. פרטי המימוש:
  - ‏PutVectors בקבוצות של 500, ו-QueryVectors עם דפדוף (100 תוצאות לדף).
  - ‏`chunk` נשמר כמטא-דאטה שלא מסננים לפיו.
  - ‏`remove(doc_id)` עובד דרך ListVectors ו-DeleteVectors, כי אין מחיקה לפי מסנן.
  - ‏`create_index()` ו-`teardown()` יוצרים ומוחקים את המשאבים.
  - יש תמיכה רק ב-cosine וב-euclidean.
- **`vectors/filters.py`:** שפת ה-`where` של ragkit, עם התוספות של השיעור: `$or`, ‏`$and`, ‏`$in`, ‏`$nin` ו-`$contains`. הפונקציות:
  - ‏`matches_ext` ו-`as_callable`: בשביל `NumpyVectorStore` ו-`FaissVectorStore`.
  - שלושה מתרגמים: ‏`to_qdrant_filter`, ‏`to_sql_where` (ערכים תמיד כפרמטרים, מפתחות רק מרשימה בטוחה) ו-`to_s3vectors_filter`.
  - ‏`acl_where(role)`: מטריצת ההרשאות של שיעור 24 (`guardkit/acl.py`) כמסנן שרץ לפני הדירוג.
  - כל המתרגמים נכשלים סגור, כלומר אופרטור לא מוכר זורק `ValueError`. התרגום ל-SQL נבדק מול PostgreSQL אמיתי.
- **`vectors/bench.py`:** כלי המדידה:
  - ‏`recall_ids` ו-`mean_recall`: ‏recall מול חיפוש מדויק.
  - ‏`sweep(search, queries, truth, params)`: לולאת מדידה של recall, זמן ממוצע ו-p95.
  - ‏`pareto_frontier`.
  - ‏`exact_filtered_top_k`, ‏`filtered_recall`, ‏`post_filter` ו-`violations`.
  - ‏`synth_clustered` ו-`exact_top_k_matrix`.
- **`vectors/sizing.py`:** ‏`hnsw_ram_bytes(n, dim, m, quantization)`. לפי הנוסחה, הגרף תופס `(2M·4+4) + (M·4+4)/(M−1)` בתים לצומת, והיא נבדקה מול FAISS ונמצאה מדויקת עד כ-1%. יש גם מודלי עלות חודשית ל-S3 Vectors, ‏OpenSearch Serverless (הדור הקלאסי והדור החדש), ‏Aurora Serverless עם pgvector, ‏Qdrant על EC2 ו-Pinecone. ‏`PRICES` מכיל את המחירים, עם תאריך ומקורות.

**נקודות הרחבה:**
- **Hybrid בתוך מסד הנתונים (שיעור 12):** ב-Qdrant זה named vectors (dense ו-sparse) ו-Query API עם `prefetch` ו-fusion. ב-pgvector זה `tsvector` לצד `vector`, ו-RRF ב-SQL.
- **הרשאות ב-Company Brain:** ‏`DenseRetriever.search(q, where=acl_where(user.role))`. אסור לסנן אחרי ה-top-k.
- **multi-tenancy ב-Qdrant:** ‏payload index עם `is_tenant=True`, ו-`hnsw_config(m=0, payload_m=16)` כשכל השאילתות מסוננות לפי לקוח.

## שיעור 12: חיפוש היברידי, query rewriting, גרסאות ו-reranking

אף אחד מהמודולים האלה לא משנה קוד קיים. כולם עוטפים retrievers, ולכן כל אחד מהם הוא בעצמו retriever, עם `search(query, k, where)`, ועובד עם `rag.answer`, עם `evaluate` ועם `metrics.run_queries` בלי שינוי. כל שלב כותב את הציון שלו ל-`Hit.scores`, ושומר את זמני הריצה שלו ב-`last_timing`.

- **`fusion.py`:** `rrf(rankings, k=60, weights=None)` (Reciprocal Rank Fusion: לכל מזהה, סכום של `w/(k+rank)` על כל הרשימות שהוא מופיע בהן), `minmax`, `zscore` ו-`weighted_fusion(score_lists, weights, normalize)`. שוויון נשבר לפי הציון, אחר כך לפי המקום הטוב ביותר ברשימה כלשהי, ואחר כך לפי המזהה. הסכומים מחושבים עם `math.fsum`.
- **`hybrid.py`:** `HybridRetriever({"bm25": bm25, "dense": dense}, method="rrf" | "weighted", fetch_k=50)` ו-`fuse_hits`. כל retriever בפנים מתבקש בדיוק `fetch_k` תוצאות, ולכן הסדר לא תלוי ב-k. כל Hit נושא את הציון של כל retriever, את `rank:<name>` ואת `rrf` או `fused`. הוא גם Index: `add` ו-`remove` מועברים לכל retriever בפנים.
- **`query.py`:** `QueryRewriter(llm)` מבצע קריאה מובנית אחת עם llmkit, לפי הסכמה `QueryRewrite`. השדות הם language, translation, variants, subquestions, step_back ו-hypothetical_answer. הוא שומר תוצאות במטמון לפי שאלה, יכול להקליט ל-JSONL, ואם הקריאה נכשלת הוא ממשיך עם השאלה המקורית (fail-open). `RewritingRetriever(base, rewriter, modes=("multi", "decompose", "translate"))` מחפש כל שאילתה ומאחד עם RRF. התרגום מחופש רק בשפת היעד, ו-`orig_weight` נותן משקל לשאלה המקורית. `replay_rewriter(fixtures)` הוא המסלול הלא מקוון.
- **`versions.py`:** `drop_superseded(hits)` משמיט מסמך כשגרסה חדשה שלו נמצאת גם היא בתוצאות. עם `superseded_by=supersedes_map(chunks)` הוא משמיט כל מסמך שיש לו גרסה חדשה בקורפוס. בנוסף יש `boost_recent(hits, weight)`, `VersionAwareRetriever(base, mode="retrieved" | "corpus" | "recent")`, ו-`stale_docs` עם `stale_at_k` לתגיות `stale:<id>` של שאלות הזהב. הקישור מגיע מ-`supersedes` במטא-דאטה של הגרסה החדשה.
- **`rerank/`:** הפרוטוקול `Reranker.rerank(query, hits, top_n)`. ל-`BaseReranker` מממשים רק `score(query, texts)`. כשיש שוויון נשמר הסדר של השלב הראשון, וכל Hit מקבל `scores["rerank"]` ו-`first_stage_rank`. `stats` מחזיק את זמן הריצה, העלות והטוקנים. `RerankingRetriever(base, reranker, fetch_k=30)` מדרג מחדש את `fetch_k` המועמדים הראשונים, ואם מבקשים יותר, השאר נשארים בסדר המקורי. המימושים:
  - `CrossEncoderReranker`, עם ה-presets `bge-m3` (`BAAI/bge-reranker-v2-m3`, Apache-2.0) ו-`mmarco`.
  - `CohereReranker`, ב-httpx ל-`/v2/rerank`, עם ניסיונות חוזרים והערכת עלות שמסומנת כלא מאומתת.
  - `LLMReranker`, עם llmkit structured: ציון בין 0 ל-10 לכל קטע, וקטע שחסר בתשובה מקבל 1-.
  - `OverlapReranker`, תחליף לקסיקלי מזויף.
  - `make_reranker(spec)` בונה reranker ממחרוזת.
- **`replay.py`:** `replay_llm(responder)` מחזיר `llmkit.LLM` אמיתי, שה-HTTP שלו נענה מקומית דרך `httpx.MockTransport`. `dispatch` בוחר מי עונה לפי סמן בפרומפט המערכת. השימוש בטוקנים מוערך.
- **`ablation.py`:** `evaluate_stage(name, retriever, qa)` ו-`format_stage(report, prev)` מודדים recall@5 ו-MRR לפי סוג שאלה, stale@5, זמן תגובה (p50, p95) ועלות לשאלה. התוצאה מודפסת כרשימה, עם השינוי מהשלב הקודם.

נקודות הרחבה:
- **reranker חדש** (למשל Voyage או Jina): יורשים מ-`BaseReranker`, מממשים `score`, ומוסיפים ל-`make_reranker`.
- **מדיניות גרסאות חדשה:** פונקציה מ-`list[Hit]` ל-`list[Hit]`, בתוך wrapper כמו `VersionAwareRetriever`.
- **Company Brain:** `RerankingRetriever(VersionAwareRetriever(RewritingRetriever(HybridRetriever(...))))`, עם `where={"classification": ...}`. ה-where מועבר עד ה-retrievers הפנימיים, כך שהסינון קורה לפני הדירוג.

## שיעור 13: אבחון כשלים ו-groundedness

`ragkit/diagnose.py` עובד על מידע פשוט: מזהי מסמכים, טקסטים ומילונים. לכן אפשר לאבחן גם trace שהוקלט בייצור, בלי להריץ מחדש. הוא משתמש ב-`ragkit.evaluate` (כיסוי ציטוטים), ב-`ragkit.rag` (הפרומפט והציטוטים), ב-`ragkit.replay` (שופט לא מקוון), ב-`llmkit.structured` (השופט החי), וב-`evalkit.metrics.fact_coverage`. את evalkit הוא טוען רק בתוך הפונקציות שצריכות אותו.

- **הטקסונומיה:** `STAGES` מכיל 12 שלבי כשל לפי סדר הצנרת:
  - ingestion: `missing_from_corpus`, `extraction_lost`, `chunk_split`.
  - retrieval: `not_retrieved`, `ranked_low`, `stale_version`.
  - generation: `false_refusal`, `lost_in_middle`, `ignored_context`, `hallucination`, `wrong_citation`, `failed_to_refuse`.
  
  `FIXES[stage]` נותן את התיקון, את השיעור שבו הוא נלמד ואת המדד שמראה שהוא עבד.
- **`Case` ו-`classify(case)`:** הנוהל עונה קודם על השאלה "האם התשובה עברה?", ואחר כך עובר על הצנרת לפי הסדר. השלב הראשון שנכשל הוא שורש הבעיה, ושאר הבעיות נשמרות כדגלים (`Diagnosis.flags`). `Diagnosis.path` מתעד את השאלות שנשאלו בדרך. `MIN_FACTS=0.5`, ו-`LONG_CONTEXT=4000` טוקנים, הסף שמתחתיו "lost in the middle" לא נחשב סיבה סבירה.
- **מדדים לפי שלב, מציטוטי הזהב:**
  - `context_recall`: ציטוטים שנמצאים בשלמותם בפרומפט, חלקי מספר הציטוטים.
  - `context_precision`: מודע לדירוג, כמו ב-Ragas: ממוצע של precision@k במקומות הרלוונטיים.
  - `simple_precision`: chunks רלוונטיים חלקי k, כמו ב-RAGChecker.
  - `citation_precision` ו-`citation_recall`: ברמת chunk, לפי ציטוטי הזהב.
  - `quote_locations` ו-`relevance_from_quotes`: פונקציות עזר.
- **`check_claims(answer, contexts, llm)`:** שתי קריאות מובנות: `Claims` ואחריה `ClaimVerdicts`, כשהראיה נכתבת לפני פסק הדין. אחר כך `evidence_in_context` מוודא בקוד שהראיה באמת במקור, וטענה עם ראיה מומצאת לא נספרת כנתמכת. סירוב לא עולה אף קריאה. שגיאת JSON מוחזרת כ-`error` ולא נזרקת. `GroundednessReport` מספק `score` (faithfulness), `label` (grounded, partially_grounded או not_grounded) ו-`unsupported`.
- **`heuristic_judge_llm()`:** `llmkit.LLM` אמיתי שה-transport שלו מקומי, עם `heuristic_claims_responder`. הוא לקסיקלי: מילים משותפות, מספרים ושלילה בחלון של המשפט. הוא עיוור לפרפרזה ולתרגום, ולכן משמש לבדיקת הצנרת ולא למדידה.
- **`NLIChecker(model=NLI_DEFAULT)`:** `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (MIT, כ-0.3 מיליארד פרמטרים, 27 שפות כולל עברית). הוא צריך transformers ו-torch, ונטען רק כשמשתמשים בו. אפשר להעביר לו `predict=` מזויף בבדיקות.
- **הרצה:**
  - `trace_question` מבצע חיפוש עמוק אחד (depth=50): הוא נותן את המועמדים, ו-k הראשונים שלו הם הפרומפט. אחריו באים התשובה, הציטוטים, כיסוי העובדות והשופט, וה-trace נשמר כ-dict שאפשר לכתוב ל-JSON.
  - `run_diagnosis`, `case_from_trace`, `trace_metrics`, `save_traces` ו-`load_traces`.
  - `breakdown`, `funnel`, `format_breakdown`, `format_funnel` ו-`format_diagnosis` מדפיסים רשימות, לא טבלאות.
  - `to_evalkit_run` ממיר הרצה ל-`evalkit.Run`: `answer_ok`, ציון של 0 או 1 לכל שלב (`stage:<name>`), והמדדים. כך ה-gates וה-McNemar של שיעור 23 עובדים עליה כפי שהם.

נקודות הרחבה:
- **שלב כשל חדש** (למשל `permission_filtered` ב-Company Brain: המסמך בקורפוס, אבל לא במועמדים של המשתמש הזה): מוסיפים אותו ל-`STAGES` במקום הנכון בסדר, מוסיפים תנאי ב-`classify` ו-`Fix` ב-`FIXES`.
- **traces מייצור** (שיעור 22): span של retrieval ו-span של LLM נושאים את אותם שדות (מזהי מסמכים, טקסט הפרומפט, התשובה). ממירים אותם ל-dict בפורמט של `trace_question`, ו-`case_from_trace` עובד עליהם.
- **שופט אחר:** כל `llmkit.LLM` עובד עם `check_claims`. כדי לכייל אותו מול תוויות של אדם, משתמשים ב-`evalkit.calibration` (שיעור 23).
