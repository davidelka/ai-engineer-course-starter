# הערות למתזמר: מה להדביק ב-ragkit/README.md

שיעור 11 הוסיף רק מודולים חדשים תחת `ragkit/vectors/`, ולא נגע ב-`ragkit/__init__.py`, ב-`ragkit/vectors/__init__.py` או ב-`ragkit/README.md`. הסעיף הבא מיועד להדבקה ב-`ragkit/README.md`, אחרי הסעיף "שיעור 10: embeddings וחיפוש וקטורי".

שתי הצעות אופציונליות, שדורשות עריכה של קבצים משותפים:
- **רישום ב-`STORES`.** אפשר לרשום את ה-stores החדשים ב-`ragkit/vectors/__init__.py`, ולשנות את `make_store` כך שיקבל `"qdrant"` ו-`"pgvector:<dsn>"`. השינוי המדויק:

```python
# ragkit/vectors/__init__.py
def _qdrant(dim=None, metric="cosine", **kw):
    from .qdrant_store import QdrantVectorStore          # lazy: qdrant-client is optional
    return QdrantVectorStore(dim=dim, metric=metric, **kw)

def _pgvector(dim=None, metric="cosine", **kw):
    from .pgvector_store import PgVectorStore            # lazy: psycopg is optional
    return PgVectorStore(dim=dim, metric=metric, **kw)

STORES = {"numpy": NumpyVectorStore, "faiss": FaissVectorStore, "qdrant": _qdrant, "pgvector": _pgvector}
# in make_store: if kind == "pgvector": return _pgvector(dim=dim, metric=metric, dsn=arg)
#                if kind == "qdrant":   return _qdrant(dim=dim, metric=metric, url=arg or None)
```

- **תלויות.** להוסיף ל-`requirements.txt` שבשורש את `qdrant-client>=1.17`, ‏`psycopg[binary]>=3.2` ו-`pgvector>=0.4` (כמו ב-`labs/11-managed-vectors/requirements.txt`). בלי התלויות האלה, `tests/test_ragkit_managed.py` מדלג על בדיקות ה-Qdrant בצורה נקייה, וכל השאר רץ.

---

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
