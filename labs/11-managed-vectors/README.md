# מעבדה 11: Managed Vector Search

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/10-embeddings/requirements.txt -r labs/11-managed-vectors/requirements.txt
python -m pytest -q                                      # בדיקות הסביבה, כולל tests/test_ragkit_managed.py החדש
python -m pytest -q labs/11-managed-vectors/tests        # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין

# שני השרתים המקומיים (Qdrant ו-PostgreSQL עם pgvector):
docker compose -f labs/11-managed-vectors/compose.yaml up -d
docker compose -f labs/11-managed-vectors/compose.yaml ps        # שניהם צריכים להיות healthy
```

התלויות החדשות הן qdrant-client, ‏psycopg ו-pgvector (ראה `requirements.txt` של המעבדה). הקובץ `compose.yaml` מריץ שני שרתים על המחשב שלך, ושניהם מאזינים רק ל-127.0.0.1:
- **Qdrant 1.20.0** בפורט 6333 (REST, ויש גם ממשק ווב ב-`http://localhost:6333/dashboard`) ובפורט 6334 (gRPC).
- **PostgreSQL 18 עם pgvector 0.8.7** בפורט 5432. המשתמש, הסיסמה ושם מסד הנתונים הם כולם `ragkit`. הסיסמה הזו מיועדת רק למעבדה המקומית. ההרחבה `vector` נוצרת אוטומטית בהפעלה הראשונה, דרך `init/01-vector.sql`.

הסקריפטים מוצאים את השרתים בכתובות ברירת המחדל. אפשר לשנות אותן עם משתני הסביבה `QDRANT_URL` ו-`PGVECTOR_DSN`. כשמסיימים: `docker compose ... down` עוצר את השרתים ושומר את הנתונים, ו-`down -v` גם מוחק את הנתונים.

**ה-embeddings לא מחושבים מחדש.** הסקריפטים קוראים את המטמון של שיעור 10 (`labs/10-embeddings/results/cache/`). אם הרצת שם את `embed_corpus.py` עם e5-small, כל הווקטורים כבר מוכנים. אם לא, ההרצה הראשונה תוריד את המודל ותטמיע את 210 ה-chunks בדקה-שתיים. לכל סקריפט שעובד על Acme יש גם `--model fake`: זה embedder לקסיקלי ולא סמנטי, שבודק את הצנרת בלי הורדה ובלי רשת.

**שימו לב למצב in-process של Qdrant.** כשלא נותנים `--qdrant`, הסקריפטים משתמשים ב-`QdrantClient(":memory:")`. זה מימוש Python של Qdrant שרץ בתוך התהליך, והוא מושלם לבדיקות. אבל הוא מחפש **בחיפוש מדויק**, ומתעלם מהגדרות HNSW, quantization ו-payload index: הוא מקבל אותן, ולא עושה בהן כלום. לכן כל מספר על HNSW או quantization חייב לבוא מהשרת האמיתי (`--qdrant`).

## מה חדש

- **`ragkit/vectors/qdrant_store.py`:** `QdrantVectorStore`, המימוש של הפרוטוקול `VectorStore` מעל Qdrant. הוא נכנס ל-`DenseRetriever` משיעור 10 בלי שום שינוי. מה הוא כולל:
  - מזהה נקודה יציב: uuid5 של מזהה ה-chunk. הוספה חוזרת של chunk דורסת את אותה נקודה (upsert).
  - כל המטא-דאטה נשמרת כשדות payload ברמה העליונה, וה-chunk המלא נשמר תחת `_chunk`.
  - payload indexes נוצרים **לפני** הנתונים, כדי ש-Qdrant יבנה את הקשתות הנוספות של filterable HNSW.
  - הפרמטרים של HNSW: ‏`m`, ‏`ef_construct`, ‏`ef_search` ו-`full_scan_threshold`.
  - quantization: ‏`scalar`, ‏`binary`, ‏`product` ו-`turbo`, עם `rescore` ו-`oversampling`.
  - שני מתגים לשאילתה: `exact=True` (ground truth) ו-`acorn=True`.
- **`ragkit/vectors/pgvector_store.py`:** `PgVectorStore` מעל PostgreSQL. מה הוא כולל:
  - טבלה עם עמודת `vector(d)` (או `halfvec`), ‏`meta` מסוג jsonb ואינדקס GIN.
  - אינדקס HNSW (או IVFFlat).
  - ‏`hnsw.ef_search` ו-`hnsw.iterative_scan` כהגדרות `SET LOCAL` לכל שאילתה.
  - ‏`explain()` שמראה אם האינדקס נוצל.
  - כל ה-SQL נבנה בפונקציות טהורות, ולכן נבדק בלי מסד נתונים.
- **`ragkit/vectors/s3vectors_store.py`:** `S3VectorsStore` מעל Amazon S3 Vectors, עם לקוח boto3 (או כל אובייקט עם אותן מתודות). זו האפשרות המנוהלת של AWS בתרגיל 8.
- **`ragkit/vectors/filters.py`:** שפת הסינון של ragkit, עם התוספות של השיעור:
  - תוספות לשפה: `$or`, ‏`$and`, ‏`$in`, ‏`$nin` ו-`$contains`.
  - מתרגמים לשלושה ניבים: ‏`to_qdrant_filter`, ‏`to_sql_where` ו-`to_s3vectors_filter`.
  - ‏`acl_where(role)`: מטריצת ההרשאות של שיעור 24, כמסנן.
  - כל מתרגם **נכשל סגור**: אופרטור לא מוכר זורק שגיאה, ולא מושמט בשקט.
- **`ragkit/vectors/bench.py`:** כלי המדידה של השיעור:
  - ‏`recall_ids` ו-`sweep` (לולאת מדידה של recall וזמן).
  - ‏`pareto_frontier`.
  - ‏`exact_filtered_top_k`, ‏`filtered_recall` ו-`post_filter`.
  - נתונים סינתטיים מקובצים.
- **`ragkit/vectors/sizing.py`:** נוסחת זיכרון ל-HNSW, ומודלי עלות חודשית ל-S3 Vectors, ‏OpenSearch Serverless, ‏Aurora עם pgvector, ‏Qdrant על EC2 ו-Pinecone. כל המחירים הם של us-east-1, נובמבר 2026, עם המקורות.
- **`mine.py`:** הקוד שלך לתרגילים 2, 3, 5 ו-6.

## הנתונים שהמעבדה משתמשת בהם

**הקורפוס של Acme** נמצא ב-`data/acme/corpus/docs/`. יש בו 55 מסמכים, והם מחולקים ל-210 chunks עם ה-chunker של ה-baseline משיעור 9 (`heading:400:40:150`). לכל chunk יש עותק של המטא-דאטה של המסמך שלו: `classification`, ‏`department`, ‏`language`, ‏`doc_type`, ‏`effective_date` ועוד.

לפי סיווג, יש 47 מסמכים internal, ‏4 public ו-4 confidential. ארבעת המסמכים החסויים:
- `eng-pm-2026-03-scheduler` (engineering): ‏postmortem על ריצות כפולות של ה-scheduler, מרץ 2026.
- `eng-pm-2026-06-billing` (engineering): ‏postmortem על חיוב יתר בחשבוניות אירו, יוני 2026.
- `eng-pm-2026-08-api` (engineering): ‏postmortem על השבתת flow-api, ‏19 באוגוסט 2026.
- `hr-relocation` (hr): מדיניות הרילוקיישן.

ארבעת המסמכים הפומביים הם מחירוני 2025 ו-2026, וה-SLA של 2025 ושל 2026, כולם של sales_support.

**שאלות הזהב** נמצאות ב-`data/acme/corpus/golden/qa.jsonl`. יש 79 שאלות, ול-69 מהן יש מסמכי מקור (`source_ids`).

**הנתונים הסינתטיים** (תרגילים 1, 2, 3 ו-5): ‏Acme קטן מדי כדי ללמוד ממנו על אינדקסים. ב-210 נקודות כל אינדקס מדויק ומיידי. לכן הסקריפטים מייצרים עשרות אלפי וקטורי יחידה מקובצים סביב "נושאים" (384 ממדים כברירת מחדל), כמו בתרגיל 7 של שיעור 10. אפשר להוסיף את וקטורי Acme האמיתיים עם `--real e5-small`.

## התרגילים

**1. מבט לתוך גרף HNSW.** הסקריפט בונה `faiss.IndexHNSWFlat` על 20 אלף וקטורים, עבור כמה ערכים של M, ומדפיס כמה נתונים:
- כמה צמתים הגיעו לכל שכבה, ולידם התאוריה: n כפול M בחזקת מינוס l.
- מספר השכנים הממוצע והמקסימלי בשכבה 0 ובשכבה 1. התקרה היא 2M בשכבה 0 ו-M בשכבה 1.
- הגודל האמיתי של האינדקס, מול הנוסחה `4d + (2M·4+4) + (M·4+4)/(M−1)` בתים לצומת.
- זמן הבנייה.
- recall@10 ב-efSearch של 16, ‏64 ו-256.
- מה קורה כשמנסים למחוק צומת.

```bash
python labs/11-managed-vectors/hnsw_inspect.py --m 8 --m 16 --m 32
python labs/11-managed-vectors/hnsw_inspect.py --ef-construction 20 --ef-construction 200
```

ענה על ארבע שאלות:
- כמה שכבות יש לגרף עם M=16, והאם זה קרוב ל-log בבסיס M של n?
- מה הפער בין הנוסחה לגודל האמיתי?
- פי כמה התייקרה הבנייה מ-M=8 ל-M=32, ומה קיבלת בתמורה ב-efSearch=16?
- למה FAISS מסרב למחוק, ומה מסדי נתונים עושים במקום?

**2. כיוונון efSearch ו-M, וחזית פארטו (קוד).** ממש ב-`mine.py` שתי פונקציות:
- `recall_at_k(found, truth, k)`: כמה מתוך ה-k המדויקים נמצאו.
- `pareto_frontier(points)`: האינדקסים של הנקודות (זמן, recall) שאף נקודה אחרת לא טובה מהן בשני הצירים, ממוינים לפי זמן. כפילויות מדויקות נשמרות פעם אחת.

אחר כך הרץ סריקה של M מתוך {8, 16, 32} ו-ef מתוך {10, ..., 320}. הסקריפט מודד recall@10 מול חיפוש מדויק, זמן ממוצע ו-p95, ומסמן את החזית. הרץ אותו קודם עם FAISS (לא מקוון), ואחר כך מול Qdrant ומול pgvector שבדוקר.

```bash
python -m pytest -q labs/11-managed-vectors/tests/test_ex2_pareto.py
python labs/11-managed-vectors/hnsw_sweep.py --mine
python labs/11-managed-vectors/hnsw_sweep.py --backend qdrant --m 16,32 --ef 16,32,64,128,256
python labs/11-managed-vectors/hnsw_sweep.py --backend pgvector --m 16 --ef 20,40,80,160
```

ענה על שלוש שאלות:
- מהי התצורה הזולה ביותר עם recall@10 של 0.95 ומעלה בכל backend?
- למה אסור להשוות את המילישניות של FAISS לאלה של Qdrant? (רמז: שאילתה ל-Qdrant עוברת ברשת.)
- האם השרת מסכים עם numpy בחיפוש המדויק? הסקריפט בודק את זה.

**3. חיפוש עם מסנן: נכונות, ומלכודת המסנן המצמצם (קוד).** ממש ב-`mine.py` שתי פונקציות:
- `exact_filtered_top_k(query, matrix, mask, k)`: אמת המידה. אלה k השורות הדומות ביותר לפי cosine, מתוך השורות שעוברות את המסנן. מחזירים אינדקסים של המטריצה המלאה.
- `filtered_recall(found, exact, k)`: המכנה הוא min(k, len(exact)).

הסקריפט מייצר 50 אלף וקטורים, ועליהם מסננים בארבע רמות סלקטיביות: 50%, ‏10%, ‏1% ו-0.1%. כל רמה מופיעה בשתי גרסאות:
- **random:** השורות שעוברות פזורות בכל המרחב, כמו שדה שפה.
- **clustered:** השורות שעוברות הן אשכולות שלמים, ובדרך כלל רחוקים מהשאילתה, כמו לקוח (tenant) שהמסמכים שלו עוסקים בנושאים שלו.

על כל מסנן הסקריפט מריץ כמה אסטרטגיות:
- post-filter: חיפוש בלי מסנן, ואז זריקה של מה שלא עובר.
- in-graph: הליכה בגרף שמחזירה רק שורות מותרות.
- pre-filter: חיפוש מדויק על התת-קבוצה.
- planner: מדויק כשמעט שורות עוברות, וגרף אחרת.
- עם `--qdrant` נוספות שתי שורות: Qdrant עם ACORN כבוי ודולק.
- עם `--pgvector` נוספות שתי שורות: pgvector עם iterative scan כבוי ודולק.

לכל אסטרטגיה מודפסים filtered recall, כמה תוצאות חזרו בממוצע, ומילישניות.

```bash
python -m pytest -q labs/11-managed-vectors/tests/test_ex3_filtered.py
python labs/11-managed-vectors/filter_pitfall.py --mine
python labs/11-managed-vectors/filter_pitfall.py --qdrant --pgvector
```

ענה על ארבע שאלות:
- מה קרה ל-post-filter ב-1% וב-0.1%? כמה תוצאות חזרו?
- למה גם in-graph של FAISS מחזיר פחות מ-10 במסנן מצמצם?
- למה clustered קשה יותר מ-random באותה סלקטיביות?
- האם `iterative_scan=relaxed_order` תיקן את pgvector, והאם ACORN שינה משהו ב-Qdrant?

**4. Acme בתוך Qdrant ו-pgvector, מול ה-baseline המדויק של שיעור 10.** הסקריפט טוען את 210 ה-chunks לשני מסדי הנתונים (עם אותם embeddings), ומריץ את 79 שאלות הזהב. לכל store הוא מדפיס:
- agree@10: איזה חלק מ-10 ה-chunks של החיפוש המדויק חזר גם מה-store.
- R@5 ו-MRR ברמת המסמך.
- זמן טעינה וזמן לשאילתה.

אחר כך הוא מריץ את מחזור העדכון שכל אינדקס בייצור צריך: מחיקת מסמך, הוספה מחדש עם טקסט ערוך, ובדיקה שכל ה-stores עדיין מסכימים.

```bash
python labs/11-managed-vectors/load_acme.py --model fake            # בדיקת צנרת, לא מקוון
python labs/11-managed-vectors/load_acme.py --qdrant --pgvector     # e5-small, השרתים שבדוקר
python labs/11-managed-vectors/load_acme.py --qdrant --pgvector --where language=he --show q039
python labs/11-managed-vectors/load_acme.py --qdrant --quantization binary
```

ענה על שתי שאלות:
- האם agree@10 הוא 1.000 בכל ה-stores? אם לא, באיזו שאלה יש הבדל, והאם R@5 השתנה בגללו?
- מה עשתה binary quantization לווקטורים של e5 ב-384 ממדים, לעומת scalar? (בתיעוד של Qdrant כתוב ש-binary מתאים במיוחד לממדים גבוהים.)

**5. quantization: זיכרון מול recall, ו-rescoring (קוד).** ממש ב-`mine.py` את `index_ram_bytes(n, dim, m, quantization, originals_in_ram)`. הפונקציה מחזירה את ה-RAM של אינדקס HNSW, והיא מורכבת משלושה חלקים:
- הגרף לפי הנוסחה.
- הקודים הדחוסים: ‏float16 תופס 2 בתים לממד, ‏int8 בית אחד, ו-binary ביט אחד (מעוגל למעלה לבתים).
- המקוריים ב-float32: נספרים ב-RAM רק אם הם לא בדיסק.

הסקריפט משווה float32, ‏float16, ‏int8, ‏binary ו-PQ על אותם נתונים. לכל שיטה הוא מדפיס:
- בתים לווקטור.
- RAM ב-1 וב-10 מיליון וקטורים.
- recall@10 על הקודים בלבד.
- recall@10 עם rescoring, ב-oversampling של 2, ‏4 ו-10.

עם `--qdrant` אותו ניסוי רץ גם על אוספים של Qdrant עם scalar, ‏binary ו-product, עם rescoring כבוי ודולק.

```bash
python -m pytest -q labs/11-managed-vectors/tests/test_ex5_memory.py
python labs/11-managed-vectors/quantization.py --mine
python labs/11-managed-vectors/quantization.py --real e5-small --qdrant
```

ענה על שלוש שאלות:
- כמה recall איבדה binary בלי rescoring, וכמה החזיר oversampling של 4?
- כמה RAM חוסך int8 ל-10 מיליון וקטורים של 1024 ממדים?
- איפה יושבים המקוריים כשמשתמשים ב-quantization, ומה המחיר של לקרוא אותם?

**6. Multi-tenancy והרשאות לפי סיווג (קוד).** ממש ב-`mine.py` את `acl_where(role)`. הפונקציה מחזירה מסנן `where` שמממש את מטריצת ההרשאות של שיעור 24:
- public גלוי לכולם.
- internal גלוי לכולם חוץ מ-contractor.
- confidential גלוי ל-security, ולתפקיד שהמחלקה שלו היא המחלקה של המסמך. engineering רואה את ה-postmortems, ו-hr רואה את מדיניות הרילוקיישן.
- תפקיד לא מוכר לא רואה כלום.

הסקריפט עושה ארבעה דברים:
1. מדפיס את הנתונים ואת המסנן של כל תפקיד, בשלושת הניבים.
2. מריץ שתי שאלות לכל תפקיד: על ה-postmortem של אוגוסט, ועל רילוקיישן.
3. בודק את כל 79 השאלות מול כל 7 התפקידים. התוצאה צריכה להיות אפס chunks אסורים, ואותן תוצאות כמו בחיפוש מדויק על המותרים בלבד.
4. מראה את הדרך השגויה: סינון בקוד אחרי top-5.

```bash
python -m pytest -q labs/11-managed-vectors/tests/test_ex6_acl.py
python labs/11-managed-vectors/acl_demo.py --mine
python labs/11-managed-vectors/acl_demo.py --mine --qdrant
```

ענה על שתי שאלות:
- מה רואה contractor בשאלה על ההשבתה, ולמה זה עדיף על "אין לך הרשאה"?
- למה סינון אחרי top-5 גם מדליף מידע, ולא רק מחזיר פחות תוצאות?

**7. האפשרויות ב-AWS, ותחשיב עלות.** הסקריפט מחשב עלות חודשית ל-1 ול-10 מיליון וקטורים, לכל אפשרות:
- S3 Vectors.
- OpenSearch Serverless, בדור הקלאסי ובדור החדש (next-gen).
- Aurora Serverless עם pgvector, ב-float32 וב-halfvec.
- Qdrant על EC2.
- Pinecone, להשוואה בלבד.

ליד כל שורה מודפסות ההנחות שלה. בסוף מודפסות הוראות teardown לכל אפשרות.

```bash
python labs/11-managed-vectors/aws_cost.py
python labs/11-managed-vectors/aws_cost.py --dims 384,1536 --queries 1000000
python labs/11-managed-vectors/aws_cost.py --n 210 --dims 384          # Acme היום
```

כתוב המלצה של פסקה ל-Company Brain, שעונה על שלוש שאלות:
- איזו אפשרות לבחור בשלב הפיילוט (אלפי chunks, עשרות משתמשים)?
- איזו אפשרות לבחור ב-10 מיליון chunks עם חיפוש היברידי?
- מה הייתה גורם להחליף אפשרות?

התייחס לשלושה דברים: עלות במצב סרק, cold start, ו-hybrid search, שהוא הנושא של שיעור 12.

**8. (רשות) S3 Vectors אמיתי, עם Terraform ו-teardown.** מה צריך: חשבון AWS, ‏`aws configure`, ו-`uv pip install boto3`. יש שתי דרכים ליצור את המשאבים:
- עם Terraform. התיקייה `terraform/` יוצרת vector bucket, אינדקס (cosine, ‏384 ממדים, ‏`chunk` כמטא-דאטה שלא מסננים לפיו) ו-IAM policy מינימלית.
- עם הסקריפט, שיוצר אותם בעצמו.

הסקריפט מעלה את 210 הווקטורים, משווה את התוצאות לחיפוש המדויק, ומריץ את מסנני ההרשאות. העלות אפסית בפועל: פחות מסנט. בסוף **מוחקים**.

```bash
cd labs/11-managed-vectors/terraform && terraform init && terraform apply -var bucket_name=acme-brain-david && cd -
python labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-david --region eu-central-1
python labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-david --region eu-central-1 --teardown
cd labs/11-managed-vectors/terraform && terraform destroy -var bucket_name=acme-brain-david
```

## עלות

- תרגילים 1 עד 7 חינמיים: הכול רץ מקומית.
- המטמון של שיעור 10 מבטיח שאף טקסט לא נשלח שוב למודל. עם e5-small אין עלות בכלל.
- תרגיל 8 (S3 Vectors) עולה פחות מסנט, כל עוד מריצים את ה-teardown.

## מה לבדוק כשמשהו לא עובד

- **`cannot reach Qdrant`:** בדוק ש-`docker compose ... ps` מראה healthy, ושהפורט 6333 פנוי (`ss -ltnp | grep 6333`).
- **`connection refused` מ-Postgres:** אם פורט 5432 תפוס על ידי Postgres מקומי, שנה ב-compose את המיפוי ל-`"127.0.0.1:5433:5432"`, ועדכן את `PGVECTOR_DSN`.
- **`type "vector" does not exist`:** ההרחבה לא נוצרה. ‏`init/01-vector.sql` רץ רק על volume חדש. הרץ `docker compose ... exec postgres psql -U ragkit -c "CREATE EXTENSION vector"`.
- **Qdrant עדיין "yellow":** האופטימייזר בונה את הגרף ברקע. הסקריפטים מחכים ל-green ול-indexed_vectors_count מלא לפני שהם מודדים. אם מודדים מוקדם מדי, השאילתות רצות על segments לא מאונדקסים, כלומר בחיפוש מדויק ואיטי.
- **בניית HNSW ב-pgvector איטית מאוד:** ‏`maintenance_work_mem` קטן מהגרף. ב-compose הוא 1GB, ו-pgvector מדפיס NOTICE כשהגרף לא נכנס.
- **מספרים שונים מאלה שבשיעור:** זה צפוי. זמנים תלויים במעבד ובעומס. ההשוואה הנכונה היא בין תצורות על אותה מכונה, ולא מול המספרים שלי.
