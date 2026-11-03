# מעבדה 10: Embeddings and Vector Search

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
# PyTorch בגרסת CPU קודם: הגרסה הרגילה מ-PyPI מושכת את CUDA ושוקלת כמה ג'יגה
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt -r labs/10-embeddings/requirements.txt
python -m pytest -q                                  # בדיקות הסביבה, כולל tests/test_ragkit_dense.py החדש
python -m pytest -q labs/10-embeddings/tests         # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

התלויות החדשות הן numpy, faiss-cpu ו-sentence-transformers (עם PyTorch). להרצה הראשונה של מודל מקומי צריך אינטרנט: sentence-transformers מוריד את המשקלות מ-Hugging Face לתיקייה `~/.cache/huggingface`. המודל `intfloat/multilingual-e5-small` שוקל כ-470MB. אחרי ההורדה הכול רץ גם בלי רשת. ל-OpenAI צריך `OPENAI_API_KEY` בקובץ `.env`. הסקריפטים קוראים אותו דרך `llmkit.load_dotenv`, ואף פעם לא מדפיסים אותו.

לכל סקריפט יש מסלול חינמי ולא מקוון: `--model fake`. זה `HashingEmbedder`, embedder דטרמיניסטי שמבוסס על hashing של מילים ושל רצפים של 4 תווים. הוא **לקסיקלי ולא סמנטי**, ולכן הוא לא יפתור שום שאלה בין שפות. הוא קיים כדי שהבדיקות ירוצו בכל מקום ושהצנרת תיבדק בלי הורדה. אסור לשפוט embeddings לפי המספרים שלו, ולכן כל סקריפט מדפיס אזהרה כשמשתמשים בו.

## מה חדש

- **`ragkit/embed/`:** הפרוטוקול `Embedder` עם שתי מתודות, `embed_documents(texts)` ו-`embed_queries(texts)`. שתיהן מחזירות מערך numpy בצורה `(n, dim)` מסוג float32, מנורמל לאורך 1. יש שתי מתודות ולא אחת כי מודלים אסימטריים כמו multilingual-e5 אומנו עם התחילית `query: ` לפני שאלות ו-`passage: ` לפני מסמכים. המימושים:
  - `SentenceTransformerEmbedder`: מודל פתוח שרץ על המחשב שלך. ה-presets הם `e5-small` (ברירת המחדל: כ-118 מיליון פרמטרים, 384 ממדים, רישיון MIT), `e5-base` (768 ממדים), `bge-m3` (1024 ממדים, בלי תחיליות, הורדה של כ-2.3GB) ו-`qwen3-0.6b` (אומן עם Matryoshka, הורדה של כ-1.2GB).
  - `OpenAIEmbedder`: קריאה ישירה ב-httpx ל-`/v1/embeddings`, עם הפרמטר `dimensions`, ניסיונות חוזרים על 429, וספירה של טוקנים ועלות. `text-embedding-3-small` עולה 0.02 דולר למיליון טוקנים, ו-`text-embedding-3-large` עולה 0.13 דולר.
  - `HashingEmbedder`: התחליף המזויף לבדיקות.
  - `CachedEmbedder`: מטמון על הדיסק, קובץ SQLite לכל מודל בתיקייה `labs/10-embeddings/results/cache/`. המפתח הוא sha256 של שלושה דברים: `model_id`, הסוג (query או document) והטקסט. הרצה שנייה לא עולה כלום.
  - `make_embedder("e5-small" | "openai:text-embedding-3-small:256" | "fake")`.
- **`ragkit/vectors/`:** הפרוטוקול `VectorStore`, עם `add(chunks, vectors)`, `remove(doc_id)` ו-`search(vector, k, where)`. שיעור 11 יממש אותו מעל מסדי נתונים מנוהלים. יש שני מימושים:
  - `NumpyVectorStore`: חיפוש מדויק, עם סינון לפני הדירוג.
  - `FaissVectorStore`: מקבל מחרוזת index_factory, למשל `Flat`, `HNSW32` או `IVF64,Flat`.
  - בנוסף יש פונקציות עזר ב-`vecmath.py`: `l2_normalize`, `similarity`, `top_k`, `cosine_top_k` ו-`truncate_dims`.
- **`ragkit/dense.py`:** `DenseRetriever(embedder, store)`. הוא retriever בדיוק כמו `BM25Index`, ולכן `rag.answer`, `IngestPipeline(index=...)` ו-`retrieval_eval` משיעור 9 עובדים איתו בלי שינוי.
- **`ragkit/metrics.py`:** recall@k, hit@k, reciprocal rank ו-MRR ברמת המסמך, ו-`summarize` לפי סוג שאלה, עם שורה נפרדת ל-`cross-lingual`.
- **`mine.py`:** הקוד שלך לתרגילים 2, 3 ו-4.

## הנתונים שהמעבדה משתמשת בהם

הקורפוס של Acme נמצא ב-`data/acme/corpus/docs/`. יש בו 55 מסמכים, ו-9 מהם בעברית: `hr-vacation-2026-he`, `hr-health-insurance-he`, `hr-onboarding-he`, `hr-reserve-duty-he`, `it-ai-usage-he`, `eng-oncall-scheduler-he`, `sup-meeting-2026-09-he`, `co-parking-tlv-he` ו-`co-haifa-office-he`. הם מחולקים ל-210 chunks עם אותו chunker כמו ה-baseline של שיעור 9: `heading:400:40:150`. כל chunk מוטמע כ-`context_text()`, כלומר הכותרת ונתיב הסעיף, שורה חדשה, ואחריהן טקסט ה-chunk.

שאלות הזהב נמצאות ב-`data/acme/corpus/golden/qa.jsonl`. יש בו 79 שאלות, ו-69 מהן ניתנות למענה. לכל שאלה רשומים `source_ids`, כלומר המסמכים שהתשובה נמצאת בהם. סוגי השאלות: single_hop (19), multi_hop (11), numeric (9), version_conflict (11), acronym (8), hebrew (11) ו-unanswerable (10).

6 שאלות מסומנות `cross-lingual`, כלומר השאלה בשפה אחת והמקור בשפה אחרת. אלה השאלות שבהן BM25 נכשל בשיעור 9:
- q039 באנגלית, והמקור הוא `hr-onboarding-he`.
- q069 בעברית, על `eng-service-catalog` שכתוב באנגלית.
- q011, q047, q049 ו-q068 דורשות מסמך אחד בכל שפה.

## התרגילים

**1. הגאומטריה של embeddings.** בחלק הראשון יש שלושה וקטורים בשני ממדים, שעליהם dot product, cosine ו-L2 מדרגים אחרת, ואחרי נרמול מדרגים בדיוק אותו דבר. בחלק השני יש שמונה משפטים אמיתיים:
- משפט באנגלית על העברת ימי חופשה, והתרגום שלו לעברית.
- פרפרזה בלי אף מילה משותפת.
- השלילה של המשפט ("may not be carried over").
- שני משפטים על חניה, באנגלית ובעברית.
- משפט עם שם קוד (Quiet Hours).
- משפט עם מזהה (il-central-1).

הסקריפט מציג מטריצת cosine בין כל המשפטים, ואחר כך מדרג את המשפטים מול שאלה אחת, פעם עם התחיליות של e5 ופעם בלעדיהן.

```bash
python labs/10-embeddings/similarity_demo.py --part math
python labs/10-embeddings/similarity_demo.py                      # e5-small, הורדה חד-פעמית
python labs/10-embeddings/similarity_demo.py --model openai:text-embedding-3-small
```

ענה על ארבע שאלות:
- מה ה-cosine בין המשפט האנגלי לתרגום העברי, לעומת המשפט האנגלי והשלילה שלו?
- מה זה אומר על שאלות שהתשובה עליהן היא "לא"?
- האם התחיליות שינו את הדירוג או רק את הפער בין התוצאות?
- למה אסור להשוות ציון 0.82 של e5 לציון 0.45 של OpenAI?

**2. cosine top-k ונרמול (קוד).** ממש ב-`mine.py` את `l2_normalize` ואת `cosine_top_k`. הדרישות:
- שורה של אפסים נשארת אפסים.
- כשיש שוויון, האינדקס הנמוך קודם.
- k גדול מ-n מחזיר את כל השורות.
- בלי לולאה ב-Python. הבונוס: `np.argpartition`.

הבדיקות משוות את הפונקציה שלך למימוש של ragkit על 2,000 וקטורים אקראיים, ועל ה-chunks של Acme עם ה-embedder המזויף.

```bash
python -m pytest -q labs/10-embeddings/tests/test_ex2_vectors.py
python labs/10-embeddings/similarity_demo.py --mine
```

**3. recall@k ו-MRR (קוד).** ממש את `recall_at_k` ואת `reciprocal_rank` ברמת המסמך. קודם מסירים כפילויות מהדירוג: אם שני chunks של אותו מסמך חזרו, המסמך נספר פעם אחת, במקום הראשון שלו. ב-multi-hop יש שניים או שלושה מסמכים רלוונטיים, ולכן מציאת אחד מתוך שניים נותנת recall של 0.5. אחר כך הרץ את ההשוואה עם הפונקציות שלך.

```bash
python -m pytest -q labs/10-embeddings/tests/test_ex3_metrics.py
python labs/10-embeddings/compare.py --models fake --mine            # רק כדי לבדוק את הפונקציות שלך
```

**4. הטמעת הקורפוס, עם מטמון (קוד והרצה).** ממש את `cache_key` ואת `embed_with_cache`. הדרישות:
- קריאה אחת בלבד למודל, ורק עם הטקסטים שחסרים במטמון.
- כל טקסט נשלח פעם אחת, לפי סדר ההופעה הראשונה.
- המפתח חייב להיות זהה לזה של ragkit, כדי שהמטמון שלך ושל `CachedEmbedder` יהיו אותו קובץ.

אחר כך הטמע את כל הקורפוס ואת 79 השאלות פעמיים: פעם עם המודל המקומי ופעם עם OpenAI. כל מודל מריצים פעמיים, כדי לראות שבהרצה השנייה הכול מגיע מהמטמון.

```bash
python -m pytest -q labs/10-embeddings/tests/test_ex4_cache.py
python labs/10-embeddings/embed_corpus.py                                       # e5-small, חינם, דקה-שתיים על CPU
python labs/10-embeddings/embed_corpus.py                                       # שוב: 289 hits, 0 קריאות
python labs/10-embeddings/embed_corpus.py --model e5-small --mine-cache         # עם הפונקציה שלך
python labs/10-embeddings/embed_corpus.py --model openai:text-embedding-3-small # כעשירית סנט
python labs/10-embeddings/embed_corpus.py --model openai:text-embedding-3-large # כחצי סנט
```

רשום לעצמך:
- כמה זמן לקח למודל המקומי.
- כמה טוקנים OpenAI חייב בפועל, לעומת ההערכה (שלוש תווים לטוקן).
- כמה זיכרון תופס הקורפוס בכל מודל: 384, 1536 או 3072 ממדים.

**5. BM25 מול dense מול איחוד, לפי סוג שאלה.** הסקריפט משווה שלושה retrievers על 69 השאלות שניתנות למענה, ומדפיס R@1, R@5, R@10 ו-MRR לכל סוג שאלה ולשורת `cross-lingual`:
- BM25 משיעור 9.
- dense עם כל מודל שביקשת.
- איחוד פשוט שמשלב את שתי הרשימות לסירוגין. זה איחוד נאיבי בכוונה: שיעור 12 יחליף אותו ב-RRF וב-reranker.

אחרי הטבלאות הסקריפט מדפיס, לכל שאלה בין שפות, את המקום של המסמך הרלוונטי הראשון בכל retriever, ואת השאלות שבהן dense טוב או גרוע בבירור מ-BM25.

```bash
python labs/10-embeddings/compare.py
python labs/10-embeddings/compare.py --models e5-small,openai:text-embedding-3-small --show cross-lingual,hebrew,acronym
```

ענה על שלוש שאלות:
- האם dense תיקן את q039 ואת q069?
- באילו סוגי שאלות BM25 עדיין מנצח, ולמה (חפש מספרים, קודים ומונחים נדירים)?
- האם האיחוד הנאיבי טוב יותר משניהם, או רק "באמצע"?

**6. סייר השכנים הקרובים.** כאן רואים מה קרוב למה. תריץ את הניסויים הבאים:
- שאלה בעברית על מסמך באנגלית.
- מזהה מדויק, עם `--bm25` לצד התוצאות: `il-central-1`, `#sec-incidents`, `FIDO2`, `extension 5000`.
- מילה נרדפת: "time off" מול "vacation".
- השכנים של chunk אחד (`--chunk`).
- רשימת זוגות כמעט-כפולים בין מסמכים (`--dups`).

```bash
python labs/10-embeddings/neighbors.py "When is the deadline to finish the new-hire security training?" --bm25
python labs/10-embeddings/neighbors.py "il-central-1" --bm25
python labs/10-embeddings/neighbors.py "time off rollover" --bm25
python labs/10-embeddings/neighbors.py "parking" --where language=he
python labs/10-embeddings/neighbors.py --chunk it-laptop-policy#1
python labs/10-embeddings/neighbors.py --dups 0.95
python labs/10-embeddings/neighbors.py                               # מצב אינטראקטיבי
```

כתוב פסקה: מתי dense מנצח, מתי BM25 מנצח, ומה זה אומר על חיפוש היברידי (שיעור 12). הסבר גם למה זוגות כמעט-כפולים כמו `hr-vacation-2024` ו-`hr-vacation-2026` מסוכנים דווקא כשהחיפוש "טוב".

**7. FAISS: מדויק מול מקורב.** הסקריפט בונה 100 אלף וקטורים סינתטיים ב-384 ממדים, מקובצים סביב 2,000 "נושאים" כדי שידמו ל-embeddings אמיתיים. עם `--real e5-small` מצטרפים אליהם גם 210 הווקטורים האמיתיים של Acme ו-79 השאלות. על הנתונים האלה הסקריפט משווה:
- `Flat`, חיפוש מדויק.
- `HNSW32` עם efSearch מ-16 עד 256.
- `IVF` עם nprobe מ-1 עד 64.
- `IVF,PQ`, עם ובלי דירוג מחדש מדויק.

לכל אחד מודדים זמן בנייה, זמן לשאילתה, recall@10 מול החיפוש המדויק וגודל בזיכרון. בסוף מודפס חישוב זיכרון ל-1 ול-10 מיליון וקטורים.

```bash
python labs/10-embeddings/faiss_bench.py --n 20000          # מהיר
python labs/10-embeddings/faiss_bench.py                    # 100 אלף, דקה-שתיים
python labs/10-embeddings/faiss_bench.py --real e5-small --threads 1
python labs/10-embeddings/faiss_bench.py --clusters 0       # וקטורים אקראיים לגמרי: למה זה בנצ'מרק גרוע?
```

ענה על ארבע שאלות:
- איזה efSearch נותן recall של 0.95 ומעלה, ופי כמה הוא מהיר מ-Flat?
- למה PQ לבד מגיע ל-recall נמוך, ומה החזיר אותו?
- כמה זיכרון יידרש ל-10 מיליון chunks עם OpenAI large (3072 ממדים) ב-Flat?
- מעל איזה גודל קורפוס בכלל צריך ANN, לפי המספרים שלך?

**8. פחות ממדים (Matryoshka).** הסקריפט קוצץ את הווקטורים מהמטמון לגדלים 384, 192, 96 ו-48 (או מ-1536 עד 96 ב-OpenAI), מנרמל מחדש, ומודד recall ו-MRR על שאלות הזהב, וגם את הגודל לווקטור ולמיליון chunks. את ההרצה מבצעים פעמיים: על e5, שלא אומן עם Matryoshka, ועל OpenAI, שאומן כך. `--api-check` שולח שתי קריאות קטנות, ובודק אם `dimensions=256` של ה-API זהה לקיצוץ שלנו.

```bash
python labs/10-embeddings/dims.py
python labs/10-embeddings/dims.py --model openai:text-embedding-3-small
python labs/10-embeddings/dims.py --model openai:text-embedding-3-small --api-check
```

ענה: איזה מודל שומר על ה-recall טוב יותר כשמקצצים, ובאיזה גודל היית בוחר ל-Company Brain?

## עלות

- כל התרגילים רצים בחינם עם `e5-small`, המודל המקומי, או עם `fake`.
- OpenAI: הקורפוס ו-79 השאלות הם כ-160 אלף תווים, כלומר כ-50 אלף טוקנים.
  - ב-small העלות היא כעשירית סנט.
  - ב-large העלות היא כחצי סנט.
  - `--api-check` עולה פחות מאלפית סנט.
- המטמון מבטיח שכל טקסט משולם פעם אחת בלבד.
- סך הכול: פחות משני סנטים, הרבה מתחת ל-5 הסנטים שהוקצבו.

## מה לבדוק כשמשהו לא עובד

- **`ImportError: sentence-transformers`:** התקן את PyTorch בגרסת CPU, ואחר כך את sentence-transformers, לפי הפקודות בהכנה.
- **ההורדה מ-Hugging Face נתקעת:** אפשר להוריד את המודל פעם אחת ידנית, עם ה-CLI שמגיע עם huggingface-hub: `hf download intfloat/multilingual-e5-small`. אחר כך הסקריפטים ימצאו אותו במטמון.
- **`OPENAI_API_KEY is not set`:** הוסף את המפתח לקובץ `.env` שבשורש הריפו. הקובץ כבר ב-.gitignore.
- **החלפת מודל או chunker:** המטמון לא צריך ניקוי, כי המפתח כולל את `model_id` ואת הטקסט. כדי להתחיל מאפס, מחק את `labs/10-embeddings/results/cache/`.
