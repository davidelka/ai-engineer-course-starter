// Lesson 11 — Managed Vector Search (HNSW internals, quantization, filtering, multi-tenancy, AWS options).
window.LESSONS = window.LESSONS || {};
window.LESSONS["11"] = {
  n: 11,
  title: "Managed Vector Search",
  he: "HNSW ואינדקסים מנוהלים בענן",
  hours: "כשלוש שעות שיעור, כחמש שעות מעבדה",

  goals: [
    "להבין את <b>HNSW</b> מבפנים: שכבות של גרף שנבחרות בהטלת מטבע, הכנסה של נקודה (חיפוש מלמעלה למטה, בחירת M שכנים, קישור דו-כיווני וגיזום), וחיפוש (ירידה חמדנית ואז חיפוש רחב בשכבה 0). לדעת לחזות במספרים כמה צמתים יש בכל שכבה וכמה זיכרון הגרף תופס.",
    "לכוונן את שלושת הפרמטרים של HNSW לפי מדידה: <b>M</b>, <b>efConstruction</b> ו-<b>efSearch</b>. למדוד recall@10 מול חיפוש מדויק ואת זמן התגובה (ממוצע ו-p95), ולבחור תצורה מתוך <b>חזית פארטו</b>, ולא לפי ערכי ברירת מחדל.",
    "להשתמש ב-<b>quantization</b> כדי להקטין זיכרון: scalar (int8), ‏binary, ‏product quantization, ‏halfvec ו-TurboQuant החדש של Qdrant. להבין למה <b>rescoring עם oversampling</b> מחזיר את רוב ה-recall שאבד, ואיפה נשמרים המקוריים.",
    "לסנן לפי מטא-דאטה בלי לאבד תוצאות: להבחין בין <b>post-filtering</b>, ‏<b>pre-filtering</b> וסינון <b>בתוך הגרף</b>, לזהות את <b>מלכודת המסנן המצמצם</b>, ולהכיר את מה שהמערכות עושות נגדה: query planner, ‏filterable HNSW ו-ACORN ב-Qdrant, ‏iterative scans ב-pgvector, ומצב ENHANCED ב-S3 Vectors.",
    "לבנות <b>multi-tenancy והרשאות</b> בתוך מסד הנתונים: מסנן לפי סיווג ותפקיד שרץ לפני הדירוג (המטריצה של שיעור 24), payload index לפי לקוח, ולדעת למה סינון אחרי top-k גם מחזיר פחות תוצאות וגם מדליף מידע.",
    "לתפעל אינדקס וקטורי בייצור: עדכונים ומחיקות (tombstones, ‏VACUUM, אופטימייזר), בנייה מחדש כשמחליפים מודל embeddings (שני אוספים ו-alias), גיבויים (snapshots), ‏sharding ו-replicas.",
    "לבחור בין <b>self-hosted</b> (Qdrant, ‏pgvector, ‏OpenSearch) לבין <b>מנוהל ב-AWS</b> (S3 Vectors, ‏OpenSearch Serverless, ‏Aurora עם pgvector), ולחשב עלות חודשית ל-1 ול-10 מיליון וקטורים עם ההנחות כתובות.",
    "לחבר את Company Brain למסד נתונים אמיתי: <code>QdrantVectorStore</code> ו-<code>PgVectorStore</code> נכנסים לאותו <code>DenseRetriever</code> משיעור 10, ומחזירים אותן תוצאות כמו החיפוש המדויק על הקורפוס של Acme.",
  ],
  connects: "בשיעור 10 הוספת ל-ragkit embeddings ו-<code>NumpyVectorStore</code>, חיפוש מדויק שמתאים בדיוק ל-210 ה-chunks של Acme, וראית בקצרה את רעיונות ה-ANN של FAISS. היום עוברים מ\"זה עובד על הלפטופ\" ל\"זה עובד בייצור\": מיליוני וקטורים, עדכונים כל הזמן, מסננים לפי הרשאות, גיבויים ועלות חודשית. נפתח את <b>HNSW</b> עד הסוף, כי הוא האינדקס שכמעט כל מסד נתונים וקטורי משתמש בו (Qdrant, ‏pgvector, ‏OpenSearch), ונחבר את אותו פרוטוקול <code>VectorStore</code> ל-Qdrant, ל-PostgreSQL ול-Amazon S3 Vectors. ההרשאות שתבנה היום הן המטריצה של <b>שיעור 24</b> (אבטחת AI): מסנן לפי <code>classification</code> ותפקיד, שרץ בתוך מסד הנתונים לפני הדירוג. ב<b>שיעור 12</b> נשלב BM25 עם וקטורים ונוסיף reranker, ונראה שחלק מהמסדים של היום עושים hybrid search בעצמם. ב-<b>Company Brain</b> השכבה הזו היא ה-retriever שעומד מאחורי כל תשובה עם ציטוטים, וההחלטה מה להריץ ב-AWS נשענת על תחשיב העלות שתעשה בתרגיל 7.",

  intro: {
    animation: "l11hnsw",
    animationTitle: "HNSW צעד אחר צעד: שכבות, הכנסה וחיפוש",
    animationGuide: `<p><b>מה רואים כאן:</b> גרף HNSW אמיתי, שנבנה בדפדפן מ-120 נקודות במישור. הקוד הוא אותו אלגוריתם שרץ ב-FAISS, ב-Qdrant וב-pgvector, רק בשני ממדים ובקטן, כדי שאפשר יהיה לראות כל צעד. כל נקודה מייצגת וקטור, והמרחק על המסך מייצג את המרחק בין הווקטורים.</p>
<p><b>איך לקרוא את המסך:</b> יש שלושה לוחות, אחד לכל שכבה של הגרף. השכבה העליונה (שכבה 2) מופיעה ראשונה, והשכבה התחתונה (שכבה 0) אחרונה. בכל לוח מופיעות רק הנקודות שהגיעו לשכבה הזו, והקווים הם הקשתות בשכבה. בשכבה 0 נמצאות כל הנקודות. בשכבה 1 יש בערך אחת מכל M נקודות, ובשכבה 2 בערך אחת מכל M בריבוע. נקודת הכניסה של הגרף מסומנת בריבוע. במצב חיפוש, הצלב הכתום הוא השאילתה, הקו העבה הוא המסלול, הנקודות הכחולות הבהירות הן צמתים שהחיפוש חישב אליהם מרחק, והטבעות הירוקות הן התוצאות.</p>
<p><b>חמשת השלבים</b> (כפתורים מעל הלוחות, או "הבא"):</p>
<ol>
<li><b>הגרלת שכבות.</b> כל נקודה מקבלת שכבה מקסימלית בהטלת מטבע: ההסתברות להגיע לשכבה l היא M בחזקת מינוס l. מתחת ללוחות מוצג כמה נקודות הגיעו לכל שכבה, ולידן התחזית.</li>
<li><b>הכנסה של נקודה.</b> נקודה חדשה (סגולה) נכנסת לגרף: יורדת חמדנית מנקודת הכניסה דרך השכבות העליונות, ובכל שכבה שהיא שייכת אליה מחפשת efConstruction מועמדים ומתחברת ל-M הקרובים מביניהם.</li>
<li><b>ירידה חמדנית.</b> חיפוש מתחיל בנקודת הכניסה בשכבה העליונה, וקופץ כל פעם לשכן הקרוב ביותר לשאילתה, עד שאין שכן קרוב יותר. אז הוא יורד שכבה. השכבות העליונות הן "כבישים מהירים": מעט צמתים וקפיצות ארוכות.</li>
<li><b>חיפוש רחב בשכבה 0.</b> בשכבה התחתונה החיפוש מחזיק רשימה של efSearch מועמדים, ולא רק את הטוב ביותר. כך הוא לא נתקע במינימום מקומי.</li>
<li><b>התוצאה מול האמת.</b> משווים ל-k השכנים האמיתיים (חיפוש מדויק), ורואים recall וכמה מרחקים חושבו לעומת 120.</li>
</ol>
<p><b>מה לנסות:</b> שנה את M ואת efSearch בפסים שמתחת ללוחות. M קטן נותן גרף דליל, עם פחות זיכרון ויותר פספוסים. efSearch גדול נותן חיפוש רחב, עם recall גבוה ויותר מרחקים. הכפתור "שאילתה אחרת" מגריל שאילתה חדשה. המספרים בתחתית נמדדו ב-FAISS על 50 אלף וקטורים אמיתיים בגודל 384, כדי שתראה שהאינטואיציה מהמישור מחזיקה גם בממדים גבוהים.</p>`,
    videos: [
      {
        title: "Optimizing Vector Search in PostgreSQL: Best Practices for Generative AI Applications",
        who: "Jonathan Katz (PostgreSQL core team), AWS re:Invent 2023",
        part: "ההרצאה כולה. חשוב במיוחד: HNSW מול IVFFlat, הפרמטרים של בנייה וחיפוש, וסינון עם WHERE",
        minutes: 60,
        url: "https://aws.amazon.com/video/watch/e8ebe5dadc7/",
        required: true,
        kind: "וידאו",
        why: "ההרצאה הטובה ביותר על pgvector בייצור, מאחד מהמפתחים המרכזיים שלו. היא מסבירה איך בוחרים בין HNSW ל-IVFFlat, מה עושים m, ‏ef_construction ו-ef_search בפועל, ולמה סינון עם WHERE הוא הבעיה הקשה. ההרצאה מ-2023, ולכן לא מופיעים בה iterative scans (נוספו ב-pgvector 0.8.0, אוקטובר 2024), ששקף 10 מכסה. אורך ההרצאה לא מצוין בעמוד, והערכתי אותו בכשעה.",
      },
      {
        title: "Filtering in Vector Search: When to Use What",
        who: "Qdrant (Sabrina Aquino, David Myriel)",
        part: "המאמר כולו: post-filtering, ‏pre-filtering, ‏filterable HNSW, ה-query planner ו-ACORN",
        minutes: 15,
        url: "https://qdrant.tech/articles/vector-search-filtering/",
        required: true,
        kind: "מאמר",
        why: "המאמר מסביר בבהירות את שלוש דרכי הסינון, ולמה תוצאה עם מסנן יכולה להחזיר פחות מ-k. הוא גם מסביר איך Qdrant בוחר בין ניקוד מדויק של הנקודות שעוברות לבין הליכה בגרף (full_scan_threshold), ולמה צירוף של שני מסננים קשים שובר את הגרף (ACORN). זה בדיוק מה שתמדוד בתרגיל 3.",
      },
      {
        title: "Hierarchical Navigable Small Worlds (HNSW)",
        who: "Pinecone, Faiss: The Missing Manual",
        part: "המאמר כולו. חשוב במיוחד: ההסתברות לשכבה, בחירת השכנים, והגרפים של recall מול זמן לפי M ו-efSearch",
        minutes: 25,
        url: "https://www.pinecone.io/learn/series/faiss/hnsw/",
        required: false,
        kind: "מאמר",
        why: "השלמה כתובה לאנימציה: אותו אלגוריתם עם קוד FAISS ועם גרפים של זיכרון, זמן בנייה ו-recall כפונקציה של M. קראת אותו כרשות בשיעור 10; היום הוא כבר חומר ליבה.",
      },
      {
        title: "Vector Databases: from Embeddings to Applications",
        who: "DeepLearning.AI עם Weaviate (Sebastian Witalec)",
        part: "השיעורים Approximate Nearest Neighbours, ‏Vector Databases ו-Sparse, Dense, and Hybrid Search",
        minutes: 65,
        url: "https://www.deeplearning.ai/short-courses/vector-databases-embeddings-applications/",
        required: false,
        kind: "קורס",
        why: "קורס קצר וחינמי, עם מחברות קוד. הוא בונה HNSW מאפס, ואחר כך מראה מה מסד נתונים וקטורי מוסיף מעליו (CRUD, מסננים, hybrid). הוא טוב כחזרה לפני המעבדה, אבל רדוד יותר מהשיעור בנושאי סינון ועלות.",
      },
      {
        title: "Amazon S3 Vectors now supports metadata pre-filtering for higher recall on filtered searches",
        who: "AWS News Blog, ‏30 בספטמבר 2026",
        part: "הפוסט כולו: מצב ENHANCED מול CLASSIC, והדוגמה של שאילתה מסוננת לפי לקוח",
        minutes: 8,
        url: "https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-supports-metadata-pre-filtering-for-higher-recall-on-filtered-searches",
        required: false,
        kind: "תיעוד",
        why: "דוגמה טרייה, מהחודש שעבר, לכך שמלכודת המסנן המצמצם היא בעיה של מוצרים אמיתיים ולא רק של תרגיל: לפני השינוי, שאילתה לפי לקוח ב-S3 Vectors החזירה 2 תוצאות מתוך 10 שהתבקשו. הפוסט גם מסביר מה ברירת המחדל לאינדקסים חדשים ואיך מעבירים אינדקס קיים.",
      },
    ],
  },

  slides: [
    {
      kicker: "למה בכלל",
      title: "מ-NumpyVectorStore למסד נתונים וקטורי: מה משתנה בייצור",
      html: `<p>בשיעור 10 החיפוש על Acme היה <b>מדויק</b>: מכפלה אחת של מטריצה בווקטור, על 210 שורות ו-384 ממדים. זה לוקח מיקרו-שניות, ומטריצה כזו תופסת כ-300KB. לקורפוס כזה זו התשובה הנכונה, ולא צעצוע. השאלה היא מה קורה כש-Company Brain גדל: כל ה-Confluence, ה-Slack והטיקטים של חברה בינונית מגיעים בקלות למיליוני chunks.</p>
<p>החשבון פשוט. 10 מיליון וקטורים של 1024 ממדים ב-float32 הם 10M כפול 1024 כפול 4 בתים, כלומר <b>כ-41GB</b>, וזה עוד לפני מטא-דאטה. חיפוש מדויק עובר על כל הזיכרון הזה בכל שאילתה: 10 מיליארד הכפלות וחיבורים, כלומר עשרות עד מאות מילישניות לשאילתה אחת בליבה אחת, וזה תוך כדי חסימה של רוחב הפס של הזיכרון. עם עשרות משתמשים בו-זמנית זה כבר לא עובד. מכאן הצורך באינדקס מקורב (ANN), שבודק רק אלפים בודדים של וקטורים לשאילתה.</p>
<p>אבל מסד נתונים וקטורי הוא הרבה יותר מאינדקס ANN. FAISS הוא ספרייה. הוא יודע לחפש מהר, אבל לא יודע לשמור על הדיסק בצורה בטוחה, לא מוחק בקלות (ב-HNSW בכלל לא), לא מבין מטא-דאטה, ולא משרת בקשות ברשת. אלה הדברים שמערכת בייצור צריכה, וכל אחד מהם הוא שקף בשיעור הזה:</p>
<ul>
<li><b>עמידות ועדכונים:</b> כל כתיבה נרשמת ביומן (WAL) לפני שהיא חוזרת כהצלחה. עדכון או מחיקה של chunk לא דורשים בנייה מחדש של כל האינדקס.</li>
<li><b>מסננים:</b> "רק מסמכים בעברית", "רק מ-2026", ובעיקר "רק מה שהמשתמש הזה מורשה לראות", וכל זה בלי לאבד recall.</li>
<li><b>זיכרון:</b> quantization מכווצת את הווקטורים פי 4 עד 32, והמקוריים עוברים לדיסק.</li>
<li><b>תפעול:</b> גיבויים, שכפול, sharding, ניטור ושדרוגים.</li>
<li><b>עלות:</b> אפשרות אחת משלמת על RAM שדולק 24/7, ואחרת משלמת לפי שאילתה. ההבדל הוא פי 100 בכל כיוון, תלוי בעומס.</li>
</ul>
<div class="example"><b>אותו חוזה, store אחר: ragkit/dense.py לא משתנה</b><pre dir="ltr">from ragkit.dense import DenseRetriever
from ragkit.embed import make_embedder
from ragkit.vectors.qdrant_store import QdrantVectorStore
from ragkit.vectors.pgvector_store import PgVectorStore

emb = make_embedder("e5-small", cache_dir="labs/10-embeddings/results/cache")
dense = DenseRetriever(emb, store=QdrantVectorStore(url="http://localhost:6333", collection="acme"))
# or: store=PgVectorStore("postgresql://ragkit:ragkit@localhost:5432/ragkit", table="acme_chunks")
dense.add(chunks)                                   # upsert: same chunk id = same point
hits = dense.search("כמה ימי חופשה אפשר להעביר?", k=5, where={"language": "he"})</pre></div>
<div class="callout"><b>מתי לא צריך את כל זה:</b> עד כמה מאות אלפי chunks שמתעדכנים לעתים רחוקות, <code>NumpyVectorStore</code> או FAISS בתוך תהליך ה-API הם פתרון לגיטימי לגמרי: מהירים, מדויקים, ובלי שרת נוסף. מסד נתונים וקטורי משתלם כשיש עדכונים תכופים, מסננים, הרשאות, כמה שרתי API, או קורפוס שלא נכנס בנוחות ב-RAM של שרת אחד.</div>`,
    },
    {
      kicker: "HNSW, חלק 1",
      title: "הרעיון: עולם קטן שאפשר לנווט בו, בשכבות",
      html: `<p>HNSW (Hierarchical Navigable Small World, ‏Malkov ו-Yashunin, 2016) בנוי משני רעיונות. הרעיון הראשון הוא <b>גרף שאפשר לנווט בו בחמדנות</b>. כל וקטור הוא צומת, וכל צומת מחובר לכמה מהשכנים הקרובים אליו. כדי למצוא את הקרוב ביותר לשאילתה, מתחילים בצומת כלשהו, וכל פעם עוברים לשכן שקרוב יותר לשאילתה, עד שאין שכן כזה. בגרף של "עולם קטן", כמו רשת חברתית, מגיעים כך כמעט לכל מקום במספר קטן של קפיצות.</p>
<p>הבעיה: בגרף שטוח עם קשתות קצרות בלבד, ההליכה מתחילה רחוק מהיעד, ומתקדמת בצעדים קטנים. הרעיון השני פותר את זה, והוא <b>היררכיה, כמו ב-skip list</b>. בונים כמה שכבות של אותו גרף. בשכבה 0 נמצאים כל הצמתים. בשכבה 1 יש רק חלק קטן מהם, ובשכבה 2 עוד פחות. בשכבות העליונות הצמתים מעטים, ולכן הקשתות ביניהם ארוכות. אלה ה"כבישים המהירים". חיפוש מתחיל למעלה, מתקרב לאזור הנכון בכמה קפיצות ארוכות, ויורד שכבה אחרי שכבה עד הרחובות של שכבה 0.</p>
<p><b>איך נקבע לאיזו שכבה צומת מגיע?</b> בהגרלה, בזמן ההכנסה. השכבה המקסימלית היא <code>floor(-ln(U) · mL)</code>, כאשר U אחיד בין 0 ל-1, ו-<code>mL = 1/ln(M)</code>. התוצאה: ההסתברות שצומת יגיע לשכבה l או מעליה היא בדיוק <b>M בחזקת מינוס l</b>. עם M=16, צומת אחד מכל 16 מגיע לשכבה 1, ואחד מכל 256 לשכבה 2. מספר השכבות גדל כמו log בבסיס M של n, ולכן גם עשרות מיליוני וקטורים מסתדרים ב-6 עד 7 שכבות.</p>
<div class="example"><b>נמדד ב-FAISS: גרף של 20 אלף וקטורים (384 ממדים), labs/11-managed-vectors/hnsw_inspect.py</b><pre dir="ltr">M=16   layer 0: 20,000 nodes   (theory 20,000)
       layer 1:  1,239 nodes   (theory  1,250)
       layer 2:     63 nodes   (theory     78)
       layer 3:      4 nodes   (theory      5)
M=8    layers: 20,000 / 2,526 / 320 / 33 / 4 / 1     (6 layers: log_8(20000) = 4.8)
M=32   layers: 20,000 / 628 / 14 / 1                 (4 layers: log_32(20000) = 2.9)</pre></div>
<p>שים לב מה זה אומר על זיכרון: <b>רוב הגרף הוא שכבה 0</b>. בממוצע לצומת יש רק <code>1/(M−1)</code> שכבות עליונות, כלומר 0.067 עם M=16. לכן כמעט כל הזיכרון של הגרף הוא רשימות השכנים של השכבה התחתונה, וכל השכבות העליונות ביחד הן תוספת של אחוזים בודדים.</p>
<div class="callout"><b>למה הגרלה ולא בחירה חכמה?</b> ההגרלה לא תלויה בנתונים ולא בסדר ההכנסה. לכן אפשר להכניס נקודות אחת אחת לאורך זמן, ומבנה השכבות נשאר מאוזן בממוצע. זה מה שהופך את HNSW לאינדקס <b>אינקרמנטלי</b>, בניגוד ל-IVF, שצריך לאמן k-means על הנתונים מראש, וכשהם משתנים הרבה צריך לאמן שוב.</div>`,
    },
    {
      kicker: "HNSW, חלק 2",
      title: "הכנסה של וקטור: efConstruction, בחירת שכנים וגיזום",
      html: `<p>הכנסה של וקטור חדש q לגרף היא בעצם חיפוש, ואחריו חיבור. השלבים הם:</p>
<ol class="ladder">
<li><b>הגרלת שכבה</b><span>מגרילים ל-q שכבה מקסימלית L, כמו בשקף הקודם. אם L גבוהה מהשכבה העליונה של הגרף, q הופך לנקודת הכניסה החדשה.</span></li>
<li><b>ירידה חמדנית עד שכבה L+1</b><span>מנקודת הכניסה, בכל שכבה שמעל L, קופצים לשכן הקרוב ביותר ל-q עד שאין שיפור, ויורדים. בשכבות האלה q לא יקבל קשתות. הן רק מקרבות אותו לאזור.</span></li>
<li><b>חיפוש רחב בכל שכבה מ-L עד 0</b><span>בכל שכבה כזו מחפשים עם רשימת מועמדים בגודל <b>efConstruction</b> (ב-pgvector ‏<code>ef_construction</code>, ב-Qdrant ‏<code>ef_construct</code>). ככל שהרשימה גדולה יותר, השכנים שנבחרים קרובים יותר לשכנים האמיתיים, והגרף איכותי יותר. המחיר הוא זמן בנייה.</span></li>
<li><b>בחירת M שכנים</b><span>מתוך המועמדים בוחרים עד M שכנים (בשכבה 0 עד 2M). לא פשוט את M הקרובים: <b>היוריסטיקת הבחירה</b> מדלגת על מועמד שקרוב יותר לשכן שכבר נבחר מאשר ל-q. כך הקשתות מכסות כיוונים שונים, ולא רק את הצד הצפוף של האשכול. זה מה ששומר על הגרף מחובר בין אשכולות.</span></li>
<li><b>קישור דו-כיווני וגיזום</b><span>כל קשת נוספת בשני הכיוונים. אם לשכן יש עכשיו יותר מ-M קשתות (או 2M בשכבה 0), הרשימה שלו נגזמת חזרה עם אותה היוריסטיקה. לכן גודל הגרף חסום: לכל צומת יש לכל היותר 2M שכנים בשכבה 0.</span></li>
</ol>
<div class="example"><b>הכנסה, בקיצור (כמו בקוד של האנימציה, aids/l11.js)</b><pre dir="ltr">def insert(q):
    L = floor(-ln(random()) / ln(M))
    ep = entry_point
    for layer in range(top, L, -1):              # above L: greedy, ef = 1
        ep = greedy_closest(q, ep, layer)
    for layer in range(min(L, top), -1, -1):
        cand = search_layer(q, ep, ef=ef_construction, layer=layer)
        nbrs = select_heuristic(q, cand, M if layer else 2 * M)
        for n in nbrs:
            link(q, n, layer); link(n, q, layer)
            if degree(n, layer) > (M if layer else 2 * M):
                prune(n, layer)                    # keep a diverse M (or 2M)
        ep = closest(cand)
    if L > top: entry_point, top = q, L</pre></div>
<p><b>מה זה אומר בפועל.</b> בנייה של HNSW יקרה: כל הכנסה היא חיפוש עם רשימה רחבה, ועוד גיזום אצל השכנים. ב-FAISS, על ליבה אחת, ‏20 אלף וקטורים של 384 ממדים נבנו בקצב של כ-8,900 וקטורים בשנייה עם M=8, כ-6,400 עם M=16, וכ-3,800 עם M=32 (efConstruction=40). זה מסביר שלוש תופעות שתראה בייצור:</p>
<ul>
<li>טעינה ראשונית גדולה ל-pgvector מהירה יותר כשטוענים קודם את הנתונים ורק אחר כך בונים את האינדקס עם <code>CREATE INDEX</code>, כאשר <code>maintenance_work_mem</code> גדול מספיק להכיל את הגרף.</li>
<li>Qdrant בונה את הגרף ברקע, ב-segments, והאוסף "צהוב" עד שהבנייה מסתיימת.</li>
<li>ה-next-gen של OpenSearch Serverless מעביר בנייה של HNSW ל-GPU כשזה משתלם, ומחייב אותה כ-OCUs.</li>
</ul>
<div class="callout"><b>efConstruction נקבע פעם אחת.</b> אי אפשר לשפר גרף שנבנה עם efConstruction נמוך על ידי הגדלת efSearch בלבד: קשתות שלא נבחרו בבנייה לא יופיעו בחיפוש. אם ה-recall לא מגיע ליעד גם עם efSearch גבוה, צריך לבנות מחדש עם efConstruction (או M) גבוה יותר.</div>`,
    },
    {
      kicker: "HNSW, חלק 3",
      title: "חיפוש: ירידה חמדנית, ואז רשימה של efSearch מועמדים",
      html: `<p>החיפוש עובד כמו ההכנסה, רק בלי לקשר. מנקודת הכניסה, בכל שכבה עליונה, קופצים לשכן הקרוב ביותר לשאילתה עד שאין שיפור, ויורדים שכבה. כשמגיעים לשכבה 0 מתחיל החלק החשוב: <b>חיפוש beam</b> עם שתי רשימות. רשימת <b>מועמדים</b> מכילה צמתים שעוד לא בדקנו את השכנים שלהם, ממוינים לפי מרחק. רשימת <b>תוצאות</b> מכילה את ה-ef הטובים ביותר שנמצאו עד עכשיו. בכל צעד מוציאים את המועמד הקרוב ביותר, מחשבים מרחק לכל אחד מהשכנים שלו שעוד לא ראינו, ומכניסים את הטובים לשתי הרשימות. עוצרים כשהמועמד הקרוב ביותר רחוק יותר מהתוצאה הגרועה ביותר ברשימה.</p>
<p><b>efSearch הוא גודל רשימת התוצאות.</b> עם ef=1 זה חיפוש חמדן טהור, שנתקע במינימום המקומי הראשון. עם ef גדול החיפוש ממשיך לחקור גם אחרי שמצא משהו טוב, ולכן מוצא את השכנים שמסתתרים מאחורי "גבעה". תמיד <code>ef ≥ k</code>: אי אפשר להחזיר 10 תוצאות מרשימה של 5. ב-pgvector ‏<code>hnsw.ef_search</code> הוא גם תקרה על מספר השורות שסריקה אחת של האינדקס מחזירה, כך ש-<code>LIMIT 100</code> עם ef_search=40 מחזיר לכל היותר 40 שורות, אלא אם iterative scans פעילים.</p>
<div class="example"><b>נמדד ב-FAISS: ‏50 אלף וקטורים, 384 ממדים, ליבה אחת, recall@10 מול חיפוש מדויק (hnsw_sweep.py)</b><pre dir="ltr">  M   efSearch   recall@10   ms/query
  8      10        0.413      0.081
  8      40        0.786      0.201
  8     160        0.978      0.782
 16      10        0.717      0.123
 16      40        0.986      0.465
 16      80        0.999      0.774
 32      10        0.904      0.266
 32      20        0.986      0.357    <- cheapest config with recall >= 0.95
 32      40        1.000      0.510
exact (numpy, same machine): ~10 ms/query</pre></div>
<p>שלושה דברים בולטים בטבלה. הראשון: <b>אותו recall אפשר להשיג בכמה דרכים</b>. M=16 עם ef=40 ו-M=32 עם ef=20 נותנים שניהם בערך 0.986, אבל במחירים שונים. השני: התשואה הולכת וקטנה. כל הכפלה של ef מכפילה בערך את הזמן, ומוסיפה פחות ופחות recall. השלישי: M גבוה עלה כאן <b>פחות</b> זמן ל-recall נתון, אבל הוא עולה בזמן בנייה ובזיכרון (בשקף הבא). לכן לא בוחרים פרמטר לבד: מודדים רשת של תצורות, ומשאירים רק את <b>חזית פארטו</b>, התצורות שאין תצורה אחרת שטובה מהן גם ב-recall וגם בזמן. זה בדיוק תרגיל 2.</p>
<div class="callout"><b>זהירות עם מספרים של מישהו אחר:</b> הנתונים כאן סינתטיים ומקובצים, והמכונה משותפת. על embeddings אמיתיים, ועל מעבד אחר, הנקודות זזות. גם בתיעוד של Qdrant, של pgvector ושל FAISS ערכי ברירת המחדל שונים: ‏ef_search ברירת מחדל 40 ב-pgvector, ‏16 ב-FAISS, וב-Qdrant ה-ef של החיפוש שווה כברירת מחדל ל-ef_construct (100). מודדים על הנתונים שלך, עם השאלות שלך.</div>`,
    },
    {
      kicker: "פרמטרים וזיכרון",
      title: "M, efConstruction, efSearch, ומה כל אחד עולה בזיכרון",
      html: `<p>לשלושת הפרמטרים של HNSW יש מחירים שונים לגמרי, וכדאי לזכור בדיוק מה כל אחד מהם קונה:</p>
<ul>
<li><b>M</b> (מספר השכנים לצומת). זה פרמטר של <b>בנייה</b>, ושינוי שלו מחייב בנייה מחדש. M גדול יותר נותן יותר קשתות, ולכן גרף מחובר יותר עם recall גבוה יותר בכל ef, אבל גם יותר זיכרון ובנייה איטית יותר. ערכים טיפוסיים: 16 כברירת מחדל ב-Qdrant וב-pgvector, ‏32 עד 64 לממדים גבוהים או כשצריך recall גבוה מאוד.</li>
<li><b>efConstruction</b>. גם זה פרמטר של בנייה. ערך גבוה נותן גרף איכותי יותר, במחיר של זמן בנייה בלבד, בלי זיכרון נוסף. ברירות המחדל: 64 ב-pgvector, ‏100 ב-Qdrant, ‏40 ב-FAISS.</li>
<li><b>efSearch</b>. זה פרמטר של <b>שאילתה</b>, ואפשר לשנות אותו בכל בקשה. הוא הכפתור הזול: ערך גבוה נותן recall גבוה יותר וזמן ארוך יותר, בלי שום שינוי באינדקס. לכן הדרך הנכונה לכוונן היא לבנות פעם אחת עם M ו-efConstruction נדיבים, ולכוונן את efSearch לפי יעד ה-recall.</li>
</ul>
<p><b>הזיכרון של הגרף.</b> בשכבה 0 כל צומת שומר עד 2M מזהים של 4 בתים, ועוד 4 בתים למונה. בממוצע לכל צומת יש <code>1/(M−1)</code> שכבות עליונות, ובכל אחת עד M מזהים ומונה. לכן:</p>
<div class="example"><b>הנוסחה (ragkit/vectors/sizing.py, ותרגיל 5 ב-mine.py)</b><pre dir="ltr">graph bytes per node = (2M·4 + 4) + (M·4 + 4) / (M − 1)
    M=8  ->  68 + 5.1  =  73.1 B
    M=16 -> 132 + 4.5  = 136.5 B
    M=32 -> 260 + 4.3  = 264.3 B
vector bytes = dim · 4 (float32)        384 dims -> 1,536 B;  1024 dims -> 4,096 B

measured (FAISS, 20k x 384):  M=8  30.8 MB (formula 30.7)   M=16 32.0 MB (31.9)   M=32 34.5 MB (34.3)</pre></div>
<p>שתי מסקנות מעשיות. הראשונה: <b>הווקטורים, לא הגרף, הם רוב הזיכרון</b>. ב-384 ממדים ו-M=16 הגרף הוא 8% מהאינדקס. ב-1024 ממדים הוא 3%. לכן להוריד את M כדי לחסוך זיכרון זה כמעט תמיד הכלי הלא נכון, והכלי הנכון הוא quantization (שקף 8). השנייה: <b>HNSW צריך להיות ב-RAM</b>. החיפוש קופץ בין צמתים אקראיים, וכל קפיצה שמגיעה לדיסק עולה עשרות עד מאות מיקרו-שניות במקום ננו-שניות. לכן גודל ה-RAM הוא מה שקובע את העלות של רוב האפשרויות, ובמיוחד את גודל המכונה, מספר ה-OCUs או מספר ה-ACUs.</p>
<div class="callout"><b>תחשיב מהיר ל-10 מיליון chunks ב-1024 ממדים:</b> הווקטורים לבד הם 41GB, והגרף עם M=16 מוסיף 1.4GB. עם quantization ל-int8, והמקוריים בדיסק, צריך כ-11.6GB של RAM. עם binary צריך כ-2.6GB. ההפרש בין 41GB ל-11.6GB הוא ההפרש בין מכונה של 64GB לבין מכונה של 16GB.</div>`,
    },
    {
      kicker: "עדכונים ומחיקות",
      title: "insert, delete ו-re-index: מה קורה לגרף כשהנתונים משתנים",
      html: `<p><b>הכנסה</b> היא הצד הקל: HNSW אינקרמנטלי מטבעו, וכל נקודה חדשה נכנסת כמו בשקף 3. הבעיה האמיתית היא <b>מחיקה</b>. אם פשוט מוחקים צומת, כל הצמתים שהצביעו עליו מאבדים קשת, ויכול להיווצר "חור" שמנתק אזור שלם מהגרף. לכן FAISS בכלל לא מאפשר למחוק מ-HNSW (תראה את השגיאה בתרגיל 1). מסדי נתונים פותרים את זה בשלושה שלבים:</p>
<ol>
<li><b>tombstone:</b> הצומת מסומן כמחוק, ונשאר בגרף. החיפוש עדיין עובר דרכו כדי לנווט, אבל לא מחזיר אותו כתוצאה.</li>
<li><b>תיקון:</b> ברקע, השכנים של צמתים מחוקים מקבלים קשתות חלופיות. ב-pgvector זה קורה ב-<code>VACUUM</code>, וב-Qdrant זה קורה כשהאופטימייזר בונה מחדש segments שיש בהם הרבה נקודות מחוקות (vacuum optimizer).</li>
<li><b>בנייה מחדש:</b> כשהשינויים מצטברים, בונים את ה-segment או את האינדקס מחדש: ב-pgvector עם <code>REINDEX INDEX CONCURRENTLY</code>, וב-Qdrant דרך האופטימייזר, אוטומטית.</li>
</ol>
<p>המשמעות המעשית: <b>הרבה מחיקות שעוד לא טופלו מורידות recall</b>. החיפוש מבזבז צעדים על צמתים מתים, ואזורים מסוימים נעשים קשים להגעה. גם ACORN של Qdrant (שקף 10) מוזכר בתיעוד כפתרון למצב של "הרבה נקודות מחוקות". בתרחיש של Company Brain, שבו מדיניות מתעדכנת כל שבוע, זה אומר לתזמן VACUUM (ב-pgvector, ‏autovacuum בדרך כלל מספיק), ולעקוב אחרי מספר הנקודות המחוקות.</p>
<p><b>עדכון של chunk</b> הוא בפועל מחיקה ואחריה הכנסה. ב-ragkit, ‏<code>add()</code> עם אותו מזהה chunk הוא upsert. ב-Qdrant המזהה הוא uuid5 של <code>chunk.id</code>, וב-pgvector זה <code>INSERT ... ON CONFLICT (id) DO UPDATE</code>. כש-<code>IngestPipeline</code> משיעור 9 מזהה מסמך ששונה, הוא קורא ל-<code>remove(doc_id)</code> ואחר כך ל-<code>add(chunks)</code>, ושני ה-stores החדשים מממשים את שתי הפעולות.</p>
<p><b>החלפת מודל embeddings</b> היא מקרה אחר לגמרי: כל הווקטורים משתנים, והממד לפעמים משתנה. אי אפשר לעדכן את האינדקס במקום, כי וקטורים משני מודלים לא ניתנים להשוואה (שיעור 10). הדרך הבטוחה היא <b>blue/green</b>:</p>
<div class="example"><b>החלפת מודל בלי השבתה: אוסף חדש, ואז העברת alias (Qdrant)</b><pre dir="ltr">new = QdrantVectorStore(url=URL, collection="acme_chunks_bge_m3_v2", dim=1024)
DenseRetriever(make_embedder("bge-m3"), store=new).add(all_chunks)   # build in the background
# evaluate on the golden set (lesson 10 metrics) BEFORE switching
client.update_collection_aliases(change_aliases_operations=[
    models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name="acme_chunks")),
    models.CreateAliasOperation(create_alias=models.CreateAlias(
        collection_name="acme_chunks_bge_m3_v2", alias_name="acme_chunks")),
])                                     # atomic: queries switch in one step; keep the old one for rollback</pre></div>
<div class="callout"><b>ב-PostgreSQL</b> אותו רעיון נעשה עם עמודה חדשה (או טבלה חדשה) ו-VIEW. וב-S3 Vectors עם אינדקס חדש באותו bucket. בכל המקרים העיקרון זהה: בונים לצד הישן, מודדים על שאלות הזהב, מחליפים בבת אחת, ומוחקים את הישן רק אחרי שהחדש הוכיח את עצמו.</div>`,
    },
    {
      kicker: "pgvector",
      title: "HNSW מול IVFFlat ב-PostgreSQL, ומה pgvector 0.8 שינה",
      html: `<p>pgvector היא הרחבה ל-PostgreSQL שמוסיפה טיפוסים (<code>vector</code>, ‏<code>halfvec</code>, ‏<code>sparsevec</code>, ‏<code>bit</code>), אופרטורי מרחק, ושני סוגי אינדקס. היתרון הגדול שלה הוא שהווקטורים יושבים באותו מסד נתונים כמו כל השאר. אותה טרנזקציה כותבת את ה-chunk, את המטא-דאטה ואת ההרשאות. אפשר לעשות JOIN לטבלת משתמשים, וגיבוי אחד מכסה הכול. ב-AWS היא זמינה ב-RDS for PostgreSQL וב-Aurora PostgreSQL, עם <code>CREATE EXTENSION vector</code>.</p>
<div class="example"><b>הסכמה ש-PgVectorStore יוצרת, והאינדקס</b><pre dir="ltr">CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE acme_chunks (id text PRIMARY KEY, doc_id text NOT NULL,
                          meta jsonb NOT NULL, chunk jsonb NOT NULL, embedding vector(384) NOT NULL);
CREATE INDEX ON acme_chunks USING gin (meta);                       -- filters on metadata
CREATE INDEX ON acme_chunks USING hnsw (embedding vector_cosine_ops)
       WITH (m = 16, ef_construction = 64);                         -- the ANN index

BEGIN;
SET LOCAL hnsw.ef_search = 100;                                     -- per query, inside the transaction
SELECT chunk, embedding &lt;=&gt; $1 AS distance FROM acme_chunks
 WHERE meta->>'language' = 'he'
 ORDER BY embedding &lt;=&gt; $1 LIMIT 10;
COMMIT;</pre></div>
<p>שלושה אופרטורים, ולכל אחד opclass משלו. <code>&lt;=&gt;</code> הוא מרחק cosine, עם <code>vector_cosine_ops</code>. ‏<code>&lt;-&gt;</code> הוא מרחק L2, עם <code>vector_l2_ops</code>. ‏<code>&lt;#&gt;</code> הוא <b>מינוס</b> המכפלה הפנימית, עם <code>vector_ip_ops</code>, כי Postgres ממיין בסדר עולה. האינדקס משמש את השאילתה רק אם האופרטור ב-<code>ORDER BY</code> תואם ל-opclass של האינדקס, ויש <code>LIMIT</code>. שאילתה עם האופרטור הלא נכון רצה, אבל בסריקה מלאה ואיטית, בלי שום שגיאה. ‏<code>PgVectorStore.explain()</code> מראה אם האינדקס נוצל.</p>
<p><b>IVFFlat</b> הוא האינדקס השני. הוא מחלק את הווקטורים ל-<code>lists</code> תאים בעזרת k-means, ובשאילתה בודק <code>ivfflat.probes</code> תאים (ברירת המחדל היא 1). הוא נבנה מהר יותר מ-HNSW וקטן יותר, אבל יש לו שלוש חולשות: צריך לבנות אותו <b>אחרי</b> שהנתונים נטענו (k-means צריך נתונים), ה-recall שלו בדרך כלל נמוך יותר באותה מהירות, ואם הנתונים משתנים הרבה המרכזים מתיישנים וצריך לבנות מחדש. ההמלצה של pgvector היא lists = שורות חלקי 1000 עד מיליון שורות, ושורש מספר השורות מעבר לזה. ברוב המקרים של RAG היום בוחרים HNSW.</p>
<p><b>pgvector 0.8.0</b> (אוקטובר 2024) הוסיף את מה שהיה חסר יותר מכל: <b>iterative index scans</b>. Postgres מבצע את ה-WHERE <b>אחרי</b> שסריקת האינדקס מחזירה שורות. בלי iterative scans, הסריקה מחזירה ef_search מועמדים, ה-WHERE זורק את מי שלא עובר, ואם המסנן מצמצם נשארות 2 שורות במקום 10. עם <code>SET hnsw.iterative_scan = relaxed_order</code>, הסריקה ממשיכה בגרף עד שמספיק שורות עוברות, או עד <code>hnsw.max_scan_tuples</code> (ברירת המחדל: 20,000). ב-<code>relaxed_order</code> הסדר יכול להיות מעט לא מדויק, ולכן עוטפים את השאילתה בתת-שאילתה שממיינת שוב. ב-<code>strict_order</code> הסדר מדויק, ומשלמים על זה בזמן.</p>
<div class="callout"><b>גרסאות:</b> בזמן כתיבת השיעור (נובמבר 2026) הגרסה האחרונה ב-Docker Hub היא <code>pgvector/pgvector:0.8.7-pg18</code>, ושינויי 2026 הם בעיקר תיקונים: VACUUM של HNSW, בנייה מקבילית ותמיכה ב-PostgreSQL 18. ב-Aurora וב-RDS הגרסה תלויה בגרסת המנוע. בודקים עם <code>SELECT extversion FROM pg_extension WHERE extname = 'vector'</code>, כי iterative scans קיימים רק מ-0.8.0.</div>`,
    },
    {
      kicker: "Quantization",
      title: "פחות בתים לווקטור: scalar, ‏binary, ‏product, ו-rescoring",
      html: `<p>אם הווקטורים הם רוב הזיכרון, הדרך לחסוך היא לשמור אותם בפחות בתים. <b>Quantization</b> מחליפה כל וקטור בקוד דחוס, ומחשבת עליו מרחקים מקורבים. ככל שהקוד קטן יותר, הזיכרון קטן יותר והחישוב מהיר יותר, אבל המרחקים פחות מדויקים. יש ארבע משפחות עיקריות:</p>
<ul>
<li><b>float16 / halfvec:</b> חצי מקום, וכמעט בלי שום אובדן דיוק. ב-pgvector יש טיפוס <code>halfvec</code>, ואפשר לבנות אינדקס על ביטוי: <code>USING hnsw ((embedding::halfvec(384)) halfvec_cosine_ops)</code>.</li>
<li><b>scalar (int8):</b> כל קואורדינטה הופכת לבית אחד, לפי הטווח של הערכים (ב-Qdrant, ‏<code>quantile=0.99</code> חותך חריגים). הקוד קטן פי 4, ולפי התיעוד של Qdrant האובדן בדרך כלל קטן מ-1%. זו ברירת המחדל הסבירה.</li>
<li><b>binary:</b> ביט אחד לקואורדינטה, כלומר רק הסימן שלה. הקוד קטן פי 32, ומרחק Hamming מחושב בפקודת מעבד אחת. אבל הדיוק תלוי מאוד במודל ובממד: התיעוד של Qdrant ממליץ על binary רק עם rescoring, ובעיקר לממדים גבוהים (1536 ומעלה). ב-Qdrant 1.20 יש גם קידוד של 1.5 ו-2 ביטים, ו-<b>TurboQuant</b> (1, 1.5, 2, 4 או 8 ביטים).</li>
<li><b>product quantization (PQ):</b> מחלקים את הווקטור ל-m תת-וקטורים, ולכל אחד שומרים את המספר של המרכז הקרוב מתוך 256 (בית אחד). אפשר להגיע לדחיסה של פי 16 עד 64, אבל החישוב לא מתאים ל-SIMD, ולכן הוא איטי יותר מ-scalar.</li>
</ul>
<p><b>Rescoring הוא מה שהופך את כל זה לשמיש.</b> הרעיון: מחפשים עם הקודים הדחוסים, אבל מבקשים יותר מועמדים, k כפול oversampling (למשל 40 במקום 10). את המועמדים האלה בלבד מדרגים מחדש עם הווקטורים המקוריים, ומחזירים את 10 הטובים. המקוריים יכולים לשבת <b>בדיסק</b>, כי קוראים רק 40 מהם לשאילתה. כך משלמים RAM של קוד דחוס, ומקבלים כמעט את ה-recall של float32.</p>
<div class="example"><b>נמדד: ‏30 אלף וקטורים, 384 ממדים, recall@10 מול float32 מדויק (quantization.py)</b><pre dir="ltr">method   bytes/vec  RAM @10M   raw    rescore x2   x4     x10
float32     1536    15.58 GB  1.000     1.000    1.000   1.000
float16      768     8.42 GB  1.000     1.000    1.000   1.000
int8         384     4.85 GB  0.996     1.000    1.000   1.000
binary        48     1.72 GB  0.704     0.871    0.929   0.964
pq48          48     1.72 GB  0.834     0.988    0.993   0.996
(RAM = codes + HNSW graph M=16; for quantized rows the originals sit on disk)</pre></div>
<p>שים לב ש-binary ב-384 ממדים איבדה כאן 30% מה-recall, ואפילו oversampling של 10 לא החזיר הכול. זה תואם את ההמלצה בתיעוד: binary מתאים לממדים גבוהים ולמודלים שנבדקו. אבל זה נמדד על נתונים סינתטיים, ולכן בתרגיל 5 תריץ את אותו ניסוי עם <code>--real e5-small</code>, ובמעבדה 4 עם Qdrant האמיתי.</p>
<div class="example"><b>אותו רעיון ב-Qdrant וב-pgvector</b><pre dir="ltr"># Qdrant: int8 in RAM, originals on disk, rescoring with oversampling at query time
QdrantVectorStore(url=URL, collection="acme", quantization="scalar", oversampling=2.0, on_disk=True)

-- pgvector: binary index for candidates, exact re-rank in SQL
CREATE INDEX ON acme_chunks USING hnsw ((binary_quantize(embedding)::bit(384)) bit_hamming_ops);
SELECT * FROM (SELECT id, embedding FROM acme_chunks
               ORDER BY binary_quantize(embedding)::bit(384) &lt;~&gt; binary_quantize($1) LIMIT 40) c
 ORDER BY embedding &lt;=&gt; $1 LIMIT 10;</pre></div>`,
    },
    {
      kicker: "סינון, חלק 1",
      title: "pre, post ו-in-graph: מלכודת המסנן המצמצם",
      html: `<p>כמעט כל שאילתה ב-Company Brain תהיה מסוננת: לפי הרשאות, לפי שפה, לפי תאריך תוקף. השאלה היא <b>מתי</b> המסנן רץ ביחס לחיפוש הווקטורי, ויש לזה שלוש תשובות:</p>
<ul>
<li><b>post-filtering:</b> מחפשים את top-k (או k כפול oversample) בלי מסנן, ואחר כך זורקים את מה שלא עובר. זה פשוט, ושובר מיד כשהמסנן מצמצם. אם רק 1% מהשורות עוברות, מתוך 100 מועמדים יעבור בממוצע אחד.</li>
<li><b>pre-filtering:</b> קודם מוצאים את כל השורות שעוברות (בעזרת אינדקס רגיל על המטא-דאטה), ורק עליהן מחשבים מרחקים בחיפוש מדויק. התוצאה תמיד נכונה, אבל העלות גדלה עם מספר השורות שעוברות. עם מסנן מתירני (50% מ-10 מיליון) זה חיפוש מדויק על 5 מיליון שורות.</li>
<li><b>in-graph filtering:</b> הולכים בגרף כרגיל, אבל מחזירים רק צמתים שעוברים את המסנן. כשהמסנן מתירני זה עובד מצוין. כשהוא מצמצם, רוב הצמתים בדרך לא עוברים, רשימת ה-ef מתמלאת בהם, והחיפוש נעצר לפני שמצא מספיק תוצאות. ואם השורות שעוברות הן אזור שלם שרחוק מנקודת הכניסה, הגרף פשוט לא מוביל אליו.</li>
</ul>
<div class="example"><b>נמדד: ‏50 אלף וקטורים, k=10, ef=64. recall מול האמת המסוננת, ו"got" הוא כמה תוצאות חזרו (filter_pitfall.py)</b><pre dir="ltr">strategy            filter           pass   recall   got
post-filter x10     random 10%       10%    0.744    9.1
post-filter x10     random 1%         1%    0.091    0.9     <- 1 result instead of 10
post-filter x10     clustered 0.1%  0.1%    0.001    0.0     <- empty answer
in-graph (faiss)    random 1%         1%    0.195    7.2
in-graph (faiss)    clustered 10%    10%    0.338   10.0     <- 10 results, mostly wrong ones
pre-filter (exact)  any filter        -     1.000   10.0     (7.5 ms at 50%, 0.01 ms at 0.1%)
planner             any filter        -     1.000   10.0     (exact when <= 6000 rows pass)
                    except clustered 50%    0.770            (graph path, hard case)</pre></div>
<p>שתי שורות כאן מסוכנות במיוחד. post-filter עם מסנן של 1% מחזיר <b>תוצאה אחת במקום 10</b>, ומודל השפה יענה "לא מצאתי", כשהתשובה קיימת. in-graph עם מסנן "clustered" של 10% מחזיר <b>10 תוצאות, רובן לא הנכונות</b>, וזה גרוע עוד יותר, כי מבחוץ זה נראה תקין. "clustered" מדמה לקוח (tenant): השורות שלו מרוכזות בנושאים שלו, ובדרך כלל רחוקות מנקודת הכניסה של הגרף. זה בדיוק המקרה של multi-tenancy.</p>
<p>השורה האחרונה היא הרעיון שכל המערכות הרציניות מממשות: <b>query planner</b>. הוא מעריך כמה שורות יעברו את המסנן, בעזרת אינדקס על המטא-דאטה. אם מעט שורות עוברות, הוא מחשב מרחקים בחיפוש מדויק על התת-קבוצה, וזה גם מדויק וגם זול. אם הרבה שורות עוברות, הוא הולך בגרף, ושם המסנן כמעט לא מפריע. האזור שבאמצע, ובמיוחד המקרה של "clustered" שבו הגרף לא מוביל לשורות שעוברות, הוא מה שהטכניקות בשקף הבא פותרות.</p>
<div class="callout"><b>הבדיקה שחייבת להיות בכל מערכת:</b> <code>filtered_recall</code> מול <code>exact_filtered_top_k</code>, על המסננים האמיתיים שלך: לפי לקוח, לפי תפקיד, לפי שפה. מדד recall ללא מסנן לא אומר כלום על השאילתות שבאמת רצות בייצור. זה תרגיל 3.</div>`,
    },
    {
      kicker: "סינון, חלק 2",
      title: "איך Qdrant, ‏pgvector ו-S3 Vectors מתמודדים עם מסננים",
      html: `<p><b>Qdrant</b> משלב שלושה מנגנונים:</p>
<ol>
<li><b>query planner לפי cardinality:</b> לכל שדה שיש לו <b>payload index</b>, Qdrant יודע להעריך כמה נקודות יעברו. אם הגודל הכולל שלהן קטן מ-<code>full_scan_threshold</code> (ברירת מחדל 10,000KB, כלומר כ-2,500 וקטורים של 1024 ממדים), הוא מחשב מרחקים בחיפוש מדויק על הנקודות האלה. מעל הסף, הוא הולך בגרף.</li>
<li><b>filterable HNSW:</b> בזמן בניית הגרף, Qdrant מוסיף קשתות נוספות בין נקודות שיש להן אותו ערך בשדה מאונדקס. כך גם תת-קבוצה של נקודות עם אותו ערך מחוברת בתוך עצמה, וההליכה לא נתקעת. התנאי: ה-payload index צריך להיות קיים <b>לפני</b> שהנתונים נטענים, ולכן <code>QdrantVectorStore</code> יוצר את האינדקסים מיד אחרי יצירת האוסף. אינדקס שנוסף אחר כך עובד, אבל בלי הקשתות, עד שהגרף נבנה מחדש.</li>
<li><b>ACORN</b> (מגרסה 1.16): הקשתות הנוספות נבנות לכל שדה בנפרד, ולא לצירופים של שדות. שאילתה עם שני מסננים קשים, למשל tenant וגם classification, יכולה לפגוש תת-קבוצה לא מחוברת. כש-ACORN מופעל (<code>AcornSearchParams(enable=True)</code>), החיפוש בודק גם את <b>השכנים של שכנים</b> שנפסלו. הוא רץ רק כשהסלקטיביות המוערכת נמוכה מ-<code>max_selectivity</code> (ברירת מחדל 0.4), ומשפר recall במחיר של זמן.</li>
</ol>
<p><b>pgvector</b> נשען על ה-planner של PostgreSQL. אם המסנן מצמצם ויש אינדקס על העמודה (btree, או GIN על jsonb), הוא בדרך כלל בוחר סריקה של האינדקס הרגיל, ומחשב מרחקים במדויק על השורות שעוברות. זה pre-filtering, וזה מדויק. אם הוא בוחר את אינדקס ה-HNSW, המסנן רץ אחרי הסריקה (post-filter), ואז <b>iterative scans</b> מגינים מפני תשובה קצרה. לסינון קבוע לפי לקוח עם מעט לקוחות גדולים, pgvector מציע גם <b>partial index</b> לכל ערך (<code>CREATE INDEX ... WHERE tenant = 'acme'</code>) או partitioning לפי לקוח.</p>
<p><b>Amazon S3 Vectors</b> נתן לנו דוגמה מהחודש שעבר. באינדקסים מסוג <code>CLASSIC</code> המסנן נבדק תוך כדי החיפוש, והתיעוד אומר במפורש ששאילתה עם מסנן יכולה להחזיר פחות מ-topK כשמעט וקטורים עוברים. ב-30 בספטמבר 2026 הוסיפה AWS מצב <code>ENHANCED</code>: המסנן נפתר קודם, ורק הווקטורים שעוברים נסרקים. לפי AWS, זה מחזיר עד פי 5 יותר תוצאות נכונות במסננים מצמצמים, בלי עלות נוספת. אינדקסים ב-buckets שנוצרו מאותו יום והלאה הם ENHANCED כברירת מחדל. אינדקסים ישנים נשארים CLASSIC, עד <code>update-index-mode --index-mode ENHANCED</code>, או עד שמריצים שאילתה בודדת עם <code>queryMode=ENHANCED</code>.</p>
<div class="example"><b>מסנן אחד, שלושה ניבים (ragkit/vectors/filters.py)</b><pre dir="ltr">where = {"$or": [{"classification": ["public", "internal"]},
                 {"classification": "confidential", "department": "engineering"}]}

to_sql_where(where)
# ("(((meta->>'classification') = ANY(%s)) OR (((meta->>'classification') = %s)
#     AND ((meta->>'department') = %s)))", [['public','internal'], 'confidential', 'engineering'])
to_s3vectors_filter(where)
# {"$or": [{"classification": {"$in": ["public","internal"]}},
#          {"$and": [{"classification": {"$eq": "confidential"}}, {"department": {"$eq": "engineering"}}]}]}
to_qdrant_filter(where)   # Filter(must=[Filter(should=[...MatchAny..., Filter(must=[...MatchValue...])])])</pre></div>
<div class="callout"><b>כלל ברזל בתרגום מסננים:</b> מתרגם שלא מכיר אופרטור חייב <b>להיכשל</b>, ולא להשמיט אותו. מסנן שהשמיט בשקט תנאי של הרשאות הוא דליפת מידע, ולא באג קוסמטי. כל המתרגמים ב-ragkit זורקים <code>ValueError</code> על אופרטור לא מוכר. התרגום ל-SQL נבדק מול PostgreSQL אמיתי, על 17 מסננים, ונתן תוצאה זהה ל-Python.</div>`,
    },
    {
      kicker: "Multi-tenancy והרשאות",
      title: "לקוחות, סיווגים ותפקידים: הסינון שחייב לרוץ לפני הדירוג",
      html: `<p>ב-Company Brain יש שני סוגים של גבולות. <b>multi-tenancy</b> הוא ההפרדה בין לקוחות, אם המערכת תשרת כמה ארגונים. <b>הרשאות בתוך ארגון</b> הן השאלה מי רואה מה לפי סיווג ותפקיד. זו המטריצה של שיעור 24, והקורפוס של Acme מכיל בדיוק את הנתונים לבדוק אותה:</p>
<ul>
<li><b>public</b> (4 מסמכים: מחירוני 2025 ו-2026, ה-SLA של 2025 ושל 2026): גלוי לכל תפקיד, כולל contractor.</li>
<li><b>internal</b> (47 מסמכים): גלוי לכל תפקיד חוץ מ-contractor.</li>
<li><b>confidential</b> (4 מסמכים): שלושה postmortems של engineering (‏<code>eng-pm-2026-03-scheduler</code>, ‏<code>eng-pm-2026-06-billing</code>, ‏<code>eng-pm-2026-08-api</code>) ו-<code>hr-relocation</code> של hr. גלוי ל-security, ולתפקיד שהמחלקה שלו היא המחלקה של המסמך.</li>
<li>כל ערך אחר (חסר, restricted, שגיאת כתיב) ותפקיד לא מוכר: אין גישה. <b>נכשלים סגור.</b></li>
</ul>
<div class="example"><b>המטריצה כמסנן (תרגיל 6), והשימוש בו</b><pre dir="ltr">acl_where("contractor")  -> {"classification": ["public"]}
acl_where("security")    -> {"classification": ["public", "internal", "confidential"]}
acl_where("engineering") -> {"$or": [{"classification": ["public", "internal"]},
                                     {"classification": "confidential", "department": "engineering"}]}

hits = dense.search(question, k=8, where=acl_where(user.role))   # user.role from the auth token, never from the prompt</pre></div>
<p><b>למה לא לסנן אחרי top-k?</b> יש שלוש סיבות, ובתרגיל 6 תראה את כולן. הראשונה: חוזרות פחות תוצאות. contractor ששואל על השבתת אוגוסט מקבל 0 מתוך 5, כי כל ה-top-5 הם chunks של ה-postmortem החסוי. השנייה: <b>הדירוג מדליף</b>. העובדה שהתשובה ריקה, או שמספר המקורות קטן בדיוק בשאלה הזו, אומרת שיש מסמך חסוי על הנושא. השלישית: קוד סינון באפליקציה הוא עוד מקום שבו אפשר לשכוח מקרה. כשהמסנן נשלח למסד הנתונים כחלק מהשאילתה, chunk אסור לא יכול להיכנס לתוצאות, ולא יכול לדחוק תוצאות מותרות החוצה.</p>
<p><b>multi-tenancy ב-Qdrant</b> בנוי על אותו עיקרון, עם שלוש הגדרות נוספות שהתיעוד ממליץ עליהן:</p>
<ul>
<li><b>אוסף אחד לכולם,</b> ולא אוסף ללקוח: לכל אוסף יש תקורה קבועה.</li>
<li><b>payload index עם <code>is_tenant=True</code></b> על שדה הלקוח: Qdrant מסדר את האחסון כך שהנקודות של כל לקוח יישבו יחד.</li>
<li><b><code>hnsw_config(m=0, payload_m=16)</code></b> כשכל השאילתות מסוננות לפי לקוח: הגרף הגלובלי לא נבנה בכלל, ובמקומו נבנה גרף נפרד לכל לקוח.</li>
</ul>
<p>לקוחות גדולים אפשר להעביר ל-shard ייעודי (tiered multitenancy), והתיעוד מציע לעשות את זה סביב 20 אלף נקודות ללקוח. כשנדרשת הפרדה מוחלטת, למשל ברגולציה או במפתחות הצפנה שונים ללקוח, משתמשים באוסף נפרד או אפילו במסד נתונים נפרד.</p>
<div class="callout"><b>הבדיקה שמוכיחה שזה עובד:</b> בתרגיל 6 הסקריפט מריץ את כל 79 שאלות הזהב מול כל 7 התפקידים, 553 חיפושים בסך הכול. הוא בודק שני דברים: <b>אפס</b> chunks אסורים, ואותו top-10 כמו חיפוש מדויק על ה-chunks המותרים בלבד. בדיקה כזו שייכת ל-CI של Company Brain, לצד בדיקות ה-prompt injection של שיעור 24.</div>`,
    },
    {
      kicker: "Hybrid בתוך מסד הנתונים",
      title: "dense ו-sparse באותו מקום: מה כל מערכת יודעת לעשות לבד",
      html: `<p>בשיעור 10 ראית ש-dense ו-BM25 טועים בשאלות שונות: dense מנצח בשאלות בין שפות ובפרפרזות, ו-BM25 מנצח במזהים, בקודים ובמספרים. בשיעור 12 נבנה hybrid retriever ב-ragkit, שממזג שני דירוגים עם RRF ומוסיף reranker. אבל חלק ממסדי הנתונים של היום יודעים לעשות hybrid בעצמם, בשאילתה אחת. זה חוסך round trip, ושומר על המסנן זהה בשני הצדדים:</p>
<ul>
<li><b>Qdrant:</b> לכל נקודה אפשר לשמור כמה <b>named vectors</b>, למשל dense ו-sparse (וקטור דליל של משקלי מילים, כמו BM25 או SPLADE). ה-Query API מריץ כמה חיפושים עם <code>prefetch</code>, וממזג אותם עם <code>FusionQuery(fusion=RRF)</code>. מגרסה 1.20, Qdrant מחשב גם ניקוד BM25 ישירות על אינדקס full-text של ה-payload.</li>
<li><b>PostgreSQL:</b> עמודת <code>tsvector</code> עם אינדקס GIN לצד עמודת <code>vector</code>, ומיזוג RRF ב-SQL עם שני CTEs. הכול באותה טרנזקציה ועם אותו WHERE של הרשאות. ל-full-text בעברית ל-PostgreSQL אין stemmer מובנה, ולכן ה-analyzer של ragkit משיעור 9 עדיין שימושי.</li>
<li><b>OpenSearch:</b> מנוע חיפוש טקסט מלא מלכתחילה (BM25 עם analyzers לשפות), עם שדה <code>knn_vector</code>. שאילתת <code>hybrid</code> עם search pipeline מנרמלת ומשלבת את הציונים. זה היתרון הגדול של OpenSearch Serverless על פני S3 Vectors.</li>
<li><b>S3 Vectors:</b> וקטורים בלבד, בלי חיפוש טקסט. ל-hybrid צריך מנוע נוסף, למשל BM25 משלך או OpenSearch. AWS מציעה גם שילוב שבו OpenSearch משתמש ב-S3 Vectors כשכבת האחסון של הווקטורים.</li>
</ul>
<div class="example"><b>Hybrid בשאילתה אחת ב-Qdrant (תצוגה מקדימה לשיעור 12)</b><pre dir="ltr">client.query_points(
    "acme",
    prefetch=[models.Prefetch(query=dense_vec, using="dense", limit=30, filter=acl),
              models.Prefetch(query=models.SparseVector(indices=ids, values=weights),
                              using="sparse", limit=30, filter=acl)],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=10)</pre></div>
<p><b>מתי זה עדיף על hybrid ב-ragkit?</b> כשהקורפוס גדול וכל round trip עולה, כשהמסנן חייב להיות זהה בשני הצדדים (הרשאות!), וכשלא רוצים לתחזק שני מנועים. hybrid ב-ragkit עדיף כשרוצים שליטה מלאה ב-analyzer, במשקלים ובניפוי באגים (כל שלב כותב ציון ל-<code>Hit.scores</code>), או כשמסד הנתונים לא תומך ב-sparse. שיעור 12 ימדוד את שתי הגישות על אותן שאלות זהב.</p>
<div class="callout"><b>שאלה לבחירת מסד נתונים:</b> אם hybrid search יהיה חלק מהמערכת, וב-RAG ארגוני הוא כמעט תמיד חלק ממנה, זה שיקול שמטה לטובת Qdrant, ‏OpenSearch או PostgreSQL. S3 Vectors לבד מכריח אותך להוסיף מנוע טקסט נפרד.</div>`,
    },
    {
      kicker: "תפעול",
      title: "גיבויים, replicas, ‏sharding וניטור recall",
      html: `<p>אינדקס וקטורי בייצור הוא מסד נתונים לכל דבר, ומקבל את אותן שאלות תפעול. אבל יש לו כמה הבדלים חשובים:</p>
<p><b>גיבויים.</b> ב-Qdrant יש <b>snapshot</b> לכל אוסף (<code>create_snapshot</code>), או snapshot מלא של כל האחסון. ה-snapshot הוא קובץ שאפשר להעביר ל-S3 (מגרסה 1.19.2 גם ל-GCS ול-Azure) ולשחזר ממנו בשרת אחר. ב-PostgreSQL הגיבוי הוא הגיבוי הרגיל: <code>pg_dump</code>, או גיבוי רציף עם WAL. ב-Aurora וב-RDS יש snapshots אוטומטיים ו-point-in-time recovery. ‏S3 Vectors ו-OpenSearch Serverless מנוהלים, והעמידות שלהם היא באחריות AWS. אבל מחיקה בטעות היא עדיין באחריותך. הנקודה שמייחדת אינדקס וקטורי: <b>אפשר לבנות אותו מחדש מהמקור</b>, מהמסמכים ומהמטמון של ה-embeddings משיעור 10. לכן לפעמים "הגיבוי" הוא בעצם צנרת ingestion שאפשר להריץ מחדש. רק צריך לדעת כמה זמן היא לוקחת. עם API בתשלום, צריך לדעת גם כמה היא עולה.</p>
<p><b>Replicas ו-sharding.</b> אלה שני כלים שונים לשתי בעיות שונות:</p>
<ul>
<li><b>replica</b> היא עותק מלא של shard. היא נותנת זמינות (אם שרת נופל, השני עונה) ותפוקת קריאה (שאילתות מתחלקות בין העותקים). ב-Qdrant זה <code>replication_factor</code>, ב-Aurora זה reader instances, וב-OpenSearch Serverless זה standby replicas.</li>
<li><b>shard</b> הוא חלק מהנתונים. sharding פותר את המצב שבו האינדקס לא נכנס ב-RAM של שרת אחד. ב-Qdrant זה <code>shard_number</code> במצב distributed. שאילתה נשלחת לכל ה-shards, וה-top-k שלהם ממוזגים. לכן sharding מוסיף זמן, ולא חוסך אותו. pgvector לא עושה sharding בעצמו, ומעבר לשרת אחד צריך Citus או חלוקה בצד האפליקציה.</li>
</ul>
<p><b>ניטור recall.</b> זה מה שמסדי נתונים רגילים לא צריכים. אינדקס ANN יכול "להתקלקל" בשקט: מחיקות שהצטברו, נתונים חדשים שמשנים את ההתפלגות, או quantization שלא מתאימה למודל חדש. השאילתות ממשיכות לחזור מהר, רק עם פחות מהתוצאות הנכונות. הפתרון הוא <b>canary queries</b>: כמה עשרות שאילתות קבועות שרצות כל שעה פעמיים, פעם רגיל ופעם עם <code>exact=True</code> (ב-Qdrant ‏<code>SearchParams(exact=True)</code>, וב-pgvector סריקה בלי אינדקס). אם recall@10 ביניהן יורד מתחת לסף, שולחים התראה. זה מתחבר ישירות ל-observability של שיעור 22.</p>
<div class="example"><b>מדד recall כ-canary, עם הכלים של השיעור</b><pre dir="ltr">from ragkit.vectors.bench import mean_recall
approx = [[h.chunk.id for h in store.search(v, 10)] for v in canary_vectors]
exact  = [[h.chunk.id for h in store.search(v, 10, exact=True)] for v in canary_vectors]
r = mean_recall(approx, exact, 10)
metrics.gauge("vector_index.recall_at_10", r)      # alert if r &lt; 0.95 for 3 runs</pre></div>
<div class="callout"><b>שדרוגים:</b> ב-compose הגרסאות מוצמדות במכוון (<code>qdrant/qdrant:v1.20.0</code>, ‏<code>pgvector/pgvector:0.8.7-pg18</code>). שדרוג של מסד נתונים וקטורי יכול לשנות את פורמט האינדקס, ולכן הסדר הוא: snapshot, שדרוג בסביבת בדיקה, הרצת canary queries, ורק אז שדרוג בייצור.</div>`,
    },
    {
      kicker: "Self-hosted",
      title: "Qdrant, ‏pgvector או OpenSearch: איך בוחרים כשמריצים בעצמך",
      html: `<p>שלוש האפשרויות הנפוצות להרצה עצמית שונות זו מזו בעיקר במה שמסביב לאינדקס. בשלושתן האינדקס הוא HNSW:</p>
<p><b>Qdrant</b> הוא מסד נתונים וקטורי ייעודי, כתוב ב-Rust, עם רישיון Apache 2.0. הוא מתאים כשהחיפוש הווקטורי הוא הלב של המערכת, ורוצים את כל הכלים: מסננים עשירים עם filterable HNSW ו-ACORN, כל משפחות ה-quantization, named vectors ו-sparse ל-hybrid, multi-tenancy מובנה, snapshots ומצב distributed. הוא מגיע כקונטיינר אחד, ויש לו גם שירות מנוהל משלו (Qdrant Cloud, גם על AWS). החיסרון: זה עוד מסד נתונים לתפעל, ולגבות, ואין בו טרנזקציות משותפות עם הנתונים העסקיים שלך.</p>
<p><b>pgvector</b> מתאים כשכבר יש PostgreSQL, וכשהווקטורים קשורים לנתונים טבלאיים: הרשאות בטבלה, JOIN למסמכים, טרנזקציה אחת לכתיבה. התפעול הוא Postgres רגיל, שרוב הצוותים כבר מכירים, ומקבלים גיבויים, replicas וניטור בלי שום דבר חדש. החולשות: אין sharding מובנה, סינון עם HNSW תלוי ב-planner וב-iterative scans, ובנייה של אינדקס גדול דורשת הרבה <code>maintenance_work_mem</code>. עד מיליוני וקטורים בודדים, על מכונה סבירה, זו בחירה מצוינת.</p>
<p><b>OpenSearch עם k-NN</b> מתאים כשחיפוש טקסט מלא הוא דרישה מרכזית: analyzers לשפות, highlighting, aggregations, ו-hybrid עם נרמול ציונים. הוא יכול להשתמש ב-FAISS או ב-Lucene מתחת, ויש לו מצב <code>on_disk</code> עם דחיסה (ברירת מחדל 32x) ו-rescoring. החיסרון: הוא הכבד מבין השלושה. JVM, אשכול של כמה צמתים, והרבה כפתורים.</p>
<ol class="ladder">
<li><b>יש לך PostgreSQL, ופחות מכמה מיליוני chunks</b><span>pgvector. מוסיפים עמודה ואינדקס, ובלי שירות חדש.</span></li>
<li><b>החיפוש הווקטורי הוא המוצר, עם מסננים מורכבים או multi-tenancy</b><span>Qdrant: הכלים הכי עשירים לבעיות של השיעור הזה.</span></li>
<li><b>טקסט מלא, hybrid ו-analytics על אותם מסמכים</b><span>OpenSearch: מנוע אחד לשניהם.</span></li>
<li><b>פחות מכמה מאות אלפים, עדכונים נדירים, שרת אחד</b><span>אולי בכלל לא צריך מסד נתונים: FAISS או numpy בתוך התהליך.</span></li>
</ol>
<div class="callout"><b>בחירה שקל לשנות:</b> בזכות הפרוטוקול <code>VectorStore</code>, המעבר בין Qdrant ל-pgvector ב-Company Brain הוא שינוי של שורה אחת, וחידוש של ה-ingestion מהמטמון. לכן לא צריך לנחש נכון ביום הראשון: מתחילים פשוט, ומודדים. מה שכן קשה לשנות הוא מודל ה-embeddings, כי החלפה שלו מחייבת לבנות את האינדקס מחדש. הוא, ולא מסד הנתונים, ההחלטה שקובעת.</div>`,
    },
    {
      kicker: "מנוהל ב-AWS",
      title: "S3 Vectors, ‏OpenSearch Serverless ו-Aurora עם pgvector (נובמבר 2026)",
      html: `<p>הענן שלך הוא AWS. יש בו שלוש אפשרויות מנוהלות רציניות, ואחת חדשה יחסית. כל הפרטים כאן נבדקו מול התיעוד והמחירונים בנובמבר 2026 (מחירי us-east-1), ומשתנים. לפני החלטה בודקים שוב.</p>
<p><b>Amazon S3 Vectors</b> (GA בדצמבר 2025) הוא סוג חדש של bucket, עם API לווקטורים: <code>PutVectors</code>, ‏<code>QueryVectors</code> ו-<code>DeleteVectors</code>.</p>
<ul>
<li><b>מחיר:</b> אין שרתים ואין עלות בסרק. משלמים על אחסון (0.06$ ל-GB בחודש), על העלאה (0.20$ ל-GB) ועל שאילתות: 0.0025$ לכל 1,000 שאילתות, ועוד תשלום לפי גודל האינדקס שנסרק. התשלום הזה מדורג לפי מספר הווקטורים, וביוני 2026 הוזל הדירוג של מעל 10 מיליון וקטורים בכ-80%.</li>
<li><b>מגבלות:</b> עד 2 מיליארד וקטורים לאינדקס, 1 עד 4,096 ממדים, ו-cosine או euclidean בלבד. מטא-דאטה של עד 40KB לווקטור, מתוכם עד 2KB שאפשר לסנן לפיהם.</li>
<li><b>ביצועים:</b> לפי AWS, פחות משנייה לשאילתה קרה וכ-100ms לשאילתה חמה, ו-recall ממוצע של 90% ומעלה, בלי כפתורי HNSW.</li>
<li><b>שילובים:</b> משולב ב-Bedrock Knowledge Bases.</li>
<li><b>אזורים:</b> זמין ב-14 אזורים (בדצמבר 2025). תל אביב (il-central-1) לא הייתה ברשימה.</li>
</ul>
<p><b>Amazon OpenSearch Serverless</b> הוא OpenSearch בלי אשכול לנהל, עם collection מסוג VECTORSEARCH. החיוב לפי OCU (כ-6GB זיכרון ו-vCPU), ב-0.24$ ל-OCU לשעה. יש שני דורות:</p>
<ul>
<li><b>הדור הקלאסי:</b> מינימום של 2 OCUs (אחד לאינדקוס ואחד לחיפוש) שדולקים כל הזמן, כלומר כ-350$ בחודש עוד לפני הנתונים. במצב dev/test בלי standby replicas, חצי מזה.</li>
<li><b>ה-NextGen</b> (GA בסביבות מאי 2026): אחסון מופרד ממחשוב, ו-<b>scale to zero</b>. בלי בקשות, אחרי 10 דקות לא משלמים על מחשוב. החזרה לוקחת כ-10 שניות, ובניית HNSW יכולה לרוץ על GPU. מעבר מהדור הקלאסי מחייב collection חדש ו-reindex.</li>
</ul>
<p>היתרון הגדול של OpenSearch Serverless: hybrid search מלא, עם BM25 ו-analyzers.</p>
<p><b>Aurora PostgreSQL עם pgvector</b> הוא pgvector מנוהל. ב-Aurora Serverless (שנקרא עד אפריל 2026 "Serverless v2") החיוב לפי ACU: כ-2GB זיכרון לכל ACU, ב-0.12$ לשעה. אחסון עולה 0.10$ ל-GB בחודש. מינימום של 0 ACU מאפשר auto-pause: בלי חיבורים, אחרי זמן שקובעים, לא משלמים על מחשוב, והחזרה לוקחת עד כ-15 שניות. אבל אינדקס HNSW שצריך להיות ב-RAM אומר שבפועל משלמים על מספיק ACUs להחזיק אותו כל זמן שהמערכת פעילה.</p>
<p><b>Pinecone</b>, לא של AWS, אבל רץ על AWS: בתוכנית Standard יש מינימום של 50$ בחודש, ‏0.33$ ל-GB של אחסון, וחיוב לפי read units ו-write units. הוא מוזכר כאן רק כנקודת השוואה לשירות וקטורי מנוהל ייעודי.</p>
<div class="callout"><b>שאלת המפתח היא דפוס העומס, לא גודל הנתונים.</b> מערכת פנימית שעונה על כמה אלפי שאלות ביום, בשעות העבודה, משלמת ב-S3 Vectors סנטים עד דולרים בודדים. אותה מערכת ב-OpenSearch Serverless הקלאסי משלמת מאות דולרים בחודש על OCUs שרוב הזמן מחכים. מערכת עם מאות שאילתות בשנייה, 24/7, הפוכה: שם התשלום לפי שאילתה מצטבר, ושרת קבוע זול יותר.</div>`,
    },
    {
      kicker: "עלות",
      title: "תחשיב ל-1 ול-10 מיליון וקטורים, וההמלצה ל-Company Brain",
      html: `<p>הטבלה הבאה היא הפלט של <code>aws_cost.py</code> (תרגיל 7), עם 100 אלף שאילתות בחודש ו-1024 ממדים. כל שורה היא הערכה, וההנחות שלה כתובות לידה. מה שחשוב כאן הוא סדרי הגודל והכיוון, ולא הסנט. לפני החלטה מכניסים את אותם מספרים ל-AWS Pricing Calculator.</p>
<div class="example"><b>עלות חודשית משוערת, us-east-1, נובמבר 2026</b><pre dir="ltr">1,000,000 vectors x 1024 dims   (raw float32 3.8 GB; HNSW RAM 3.9 GB; int8 1.1 GB)
  $     1.49  S3 Vectors                      storage + 100k queries, no idle cost
  $    50.00  Pinecone Standard               monthly minimum (read/write units not modelled)
  $    79.78  EC2 r7g.large + Qdrant          int8 in RAM, no replica, no backups, no ops time
  $   144.13  OpenSearch Serverless NextGen   3 OCUs x 200 active hours (work hours only)
  $   175.66  Aurora Serverless + halfvec     2 ACU always on
  $   525.73  OpenSearch Serverless classic   3 OCUs x 730 hours

10,000,000 vectors x 1024 dims  (raw 38 GB; HNSW RAM 39 GB; int8 10.8 GB)
  $    11.92  S3 Vectors
  $   164.70  EC2 r7g.xlarge + Qdrant         (32 GB RAM; add a replica for HA: x2)
  $   721.25  OpenSearch Serverless NextGen   15 OCUs x 200 h
  $ 1,493.84  Aurora Serverless + halfvec     17 ACU always on
  $ 2,629.25  OpenSearch Serverless classic   15 OCUs x 730 h</pre></div>
<p><b>איך לקרוא את זה.</b> S3 Vectors זול בסדרי גודל, כי הוא לא מחזיק RAM ולא מחשוב דולקים. משלמים לפי גודל האינדקס שנסרק בכל שאילתה, ובעומס הזה זה זניח. אבל המספר הזה מגיע עם שלוש הסתייגויות: זמן תגובה של 100ms עד שנייה, ולא מילישניות בודדות; אין hybrid search; ואין שליטה ב-recall. Qdrant על EC2 הוא הזול מבין האפשרויות עם RAM, אבל המחיר לא כולל replica, גיבויים, שדרוגים והזמן שלך. OpenSearch ו-Aurora מתייקרים מהר, כי ה-HNSW צריך לשבת ב-RAM מנוהל, שהוא יקר יותר. ההנחה שלי על חצי OCU לכל 3GB של אינדקס היא הערכה, ולא נתון של AWS. ב-NextGen, ההנחה של 200 שעות פעילות (שעות העבודה) היא מה שמוריד את המחיר פי 3.6.</p>
<p><b>ההמלצה ל-Company Brain</b>, כפי שאני רואה אותה היום. את ההמלצה שלך תכתוב בתרגיל 7:</p>
<ol class="ladder">
<li><b>פיתוח ופיילוט (אלפי chunks)</b><span>Qdrant ו-pgvector בדוקר, מקומית, וב-AWS S3 Vectors: כמעט חינם, ובלי לתפעל כלום. hybrid נשאר ב-ragkit (שיעור 12), עם BM25 בתוך התהליך.</span></li>
<li><b>ייצור פנימי (עשרות אלפים עד מיליון chunks, שעות עבודה)</b><span>pgvector על Aurora Serverless, אם Company Brain ממילא צריך PostgreSQL לטבלאות של בקשות הגישה (שלב 3). אחרת, S3 Vectors עם BM25 ב-ragkit. ההחלטה תלויה ב-latency שהמשתמשים יקבלו.</span></li>
<li><b>ייצור גדול (מיליונים, תמיד דולק, hybrid חובה)</b><span>OpenSearch Serverless NextGen, או Qdrant מנוהל או self-hosted עם replica. כאן מודדים recall ו-latency על העומס האמיתי לפני שמחליטים.</span></li>
</ol>
<div class="callout"><b>Teardown הוא חלק מהתרגיל, לא הערת שוליים.</b> כל אפשרות חוץ מ-S3 Vectors גובה כסף גם כשלא משתמשים בה:</div>
<ul>
<li>‏OpenSearch Serverless הקלאסי: OCUs שדולקים כל הזמן.</li>
<li>‏Aurora: אחסון, ו-ACUs אם אין auto-pause.</li>
<li>‏EC2: המכונה, וגם ה-EBS וה-snapshots אחרי שמכבים אותה.</li>
</ul>
<p>אחרי כל ניסוי בענן: <code>terraform destroy</code>, או <code>s3vectors_demo.py --teardown</code>, ובדיקה ב-Cost Explorer למחרת.</p>`,
    },
  ],

  sims: [
    {
      id: "l11tune",
      title: "מגרש HNSW: בונים גרף, מכוונים M ו-ef, ומודדים recall",
      lead: "300 נקודות במישור, וגרף HNSW אמיתי שנבנה בדפדפן לפי הפרמטרים שתבחר. אחרי כל שינוי של M או של efConstruction הגרף נבנה מחדש. efSearch משפיע רק על החיפוש. לחץ על המפה כדי להזיז את השאילתה. מתחת למפה מוצגים recall@10 מול חיפוש מדויק, מספר המרחקים שחושבו, הזיכרון של הגרף לפי הנוסחה, וגרף קטן של recall מול עלות לכל ערכי efSearch. אפשר גם \"למחוק\" 30% מהנקודות (tombstones) ולראות מה זה עושה לחיפוש.",
      tasks: [
        "קבע <b>M=2</b> ו-efSearch=10. כמה שכנים אמיתיים נמצאו? עכשיו העלה ל-<b>M=8</b> בלי לשנות את efSearch. מה קרה ל-recall ולזיכרון של הגרף?",
        "עם M=6, מצא את efSearch הקטן ביותר שנותן recall@10 של 1.0 בשלוש שאילתות שונות (לחץ במקומות שונים). למה צריך יותר בשאילתה שנמצאת בין שני אשכולות?",
        "הפעל <b>מחיקת 30%</b>. החיפוש עדיין עובר דרך הצמתים המחוקים (אפורים), אבל לא מחזיר אותם. מה קרה ל-recall באותו efSearch, וכמה צריך להעלות אותו כדי לחזור לאותו recall?",
        "השווה <b>efConstruction=4</b> מול <b>efConstruction=64</b> עם אותו M. האם efSearch גבוה מציל גרף שנבנה בחיפזון?",
      ],
    },
    {
      id: "l11filter",
      title: "מלכודת המסנן: post, pre, in-graph ו-planner",
      lead: "400 מסמכים במישור, צבועים לפי לקוח (tenant). השאילתה מבקשת את 10 המסמכים הקרובים ביותר <b>של לקוח אחד בלבד</b>. בוחרים את גודל הלקוח (כמה מהמסמכים שלו) ואת האסטרטגיה, ורואים מה חוזר: טבעת ירוקה היא תוצאה נכונה, טבעת אדומה היא תוצאה נכונה שפוספסה, ואיקס הוא תוצאה שחזרה אבל לא בין 10 הנכונות. לצד המפה: כמה תוצאות חזרו, filtered recall וכמה מרחקים חושבו.",
      tasks: [
        "בחר לקוח <b>קטן (2%)</b> ואסטרטגיה <b>post-filter</b>. כמה תוצאות חזרו מתוך 10? למה זה קורה גם כשהחיפוש עצמו מושלם?",
        "עם אותו לקוח, עבור ל-<b>pre-filter</b>. מה ה-recall, וכמה מרחקים חושבו? עכשיו בחר לקוח <b>גדול (50%)</b>: כמה מרחקים חושבו עכשיו, ולמה pre-filter לבד לא מתאים לכל מקרה?",
        "בחר <b>in-graph</b> עם לקוח בינוני, ושים את השאילתה רחוק מהמסמכים שלו. האם חזרו 10 תוצאות? האם הן הנכונות? זה המקרה שבו post-filter נכשל ברעש, ו-in-graph נכשל בשקט.",
        "בחר <b>planner</b> ושחק עם גודל הלקוח. באיזה גודל הוא עובר מחיפוש מדויק לגרף? זה full_scan_threshold של Qdrant בקטן.",
      ],
    },
    {
      id: "l11cost",
      title: "מחשבון זיכרון ועלות: N וקטורים, ממדים ו-quantization",
      lead: "בוחרים מספר וקטורים, ממד, quantization, ‏M, שאילתות בחודש ושעות פעילות. המחשבון מראה את ה-RAM של אינדקס HNSW, מחולק לווקטורים, קודים וגרף, ואת העלות החודשית המשוערת של כל אפשרות ב-AWS. הנוסחאות והמחירים זהים ל-ragkit/vectors/sizing.py: מחירי us-east-1, נובמבר 2026, וכל שורה מציגה את ההנחות שלה.",
      tasks: [
        "קבע <b>10 מיליון</b> וקטורים ו-<b>1024</b> ממדים בלי quantization. כמה RAM צריך? עכשיו בחר <b>int8</b>. איזה חלק מה-RAM עבר לדיסק, ואיך זה שינה את העלות של EC2 ושל OpenSearch?",
        "השאר 10 מיליון, והעלה את השאילתות ל-<b>10 מיליון בחודש</b>. באיזה עומס S3 Vectors מפסיק להיות הזול ביותר?",
        "הורד את שעות הפעילות מ-730 ל-<b>200</b> (שעות עבודה). מה זה עושה ל-OpenSearch NextGen, ולמה זה לא משנה את הדור הקלאסי?",
        "קבע <b>210 וקטורים, 384 ממדים</b>, כלומר Acme היום. מה הזיכרון, ומה האפשרות הסבירה היחידה בשלב הזה?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/11-managed-vectors",
    intro: "המעבדה נמצאת בתיקייה labs/11-managed-vectors, ומריצה שני מסדי נתונים מקומיים עם docker compose: <b>Qdrant 1.20.0</b> ו-<b>PostgreSQL 18 עם pgvector 0.8.7</b>. ל-ragkit נוספו שלושה stores שמממשים את אותו פרוטוקול <code>VectorStore</code> משיעור 10: ‏<code>QdrantVectorStore</code>, ‏<code>PgVectorStore</code> ו-<code>S3VectorsStore</code>. נוספו גם שפת מסננים עם מתרגמים לשלושתם ו-<code>acl_where</code> לפי המטריצה של שיעור 24, כלי מדידה (sweep, ‏recall, ‏Pareto, ‏filtered recall), ומודל זיכרון ועלות. הנתונים: הקורפוס של Acme (55 מסמכים, 210 chunks, ‏79 שאלות זהב), עם ה-embeddings מהמטמון של שיעור 10, כך ששום דבר לא מוטמע מחדש. לניסויים על אינדקסים יש בנוסף עשרות אלפי וקטורים סינתטיים מקובצים. כל התרגילים רצים בחינם על המחשב שלך. תרגיל 8 (S3 Vectors אמיתי) עולה פחות מסנט, כל עוד מריצים את ה-teardown.",
    setup: [
      "cd ~/projects/\"ai engineer\"/ai-engineer-course && source .venv/bin/activate",
      "uv pip install -r requirements.txt -r labs/10-embeddings/requirements.txt -r labs/11-managed-vectors/requirements.txt",
      "docker compose -f labs/11-managed-vectors/compose.yaml up -d && docker compose -f labs/11-managed-vectors/compose.yaml ps",
      "python -m pytest -q                                      # environment tests, incl. tests/test_ragkit_managed.py",
      "python -m pytest -q labs/11-managed-vectors/tests        # your exercises: all fail at first",
    ],
    tools: [
      "<b>QdrantVectorStore:</b> <code>QdrantVectorStore(url=\"http://localhost:6333\", collection=\"acme\", m=16, ef_construct=100, quantization=\"scalar\", oversampling=2.0)</code>. בלי <code>url</code> הוא רץ בתוך התהליך (<code>:memory:</code>), ושם החיפוש <b>מדויק</b> והגדרות HNSW ו-quantization לא משפיעות. <code>search(v, k, where, ef=..., exact=True)</code>.",
      "<b>PgVectorStore:</b> <code>PgVectorStore(dsn, table=\"acme_chunks\", index=\"hnsw\", ef_search=100, iterative_scan=\"relaxed_order\")</code>. ה-SQL נבנה בפונקציות טהורות (<code>schema_sql</code>, ‏<code>index_sql</code>, ‏<code>search_sql</code>), ו-<code>explain()</code> מראה אם האינדקס נוצל.",
      "<b>S3VectorsStore:</b> <code>S3VectorsStore(boto3.client(\"s3vectors\"), bucket, index)</code>, עם <code>create_index()</code> ו-<code>teardown()</code>. משמש רק בתרגיל 8.",
      "<b>ragkit.vectors.filters:</b> <code>to_qdrant_filter</code>, ‏<code>to_sql_where</code>, ‏<code>to_s3vectors_filter</code>, ‏<code>matches_ext</code> ו-<code>acl_where(role)</code>. נוספו האופרטורים <code>$or</code>, ‏<code>$and</code>, ‏<code>$in</code>, ‏<code>$nin</code> ו-<code>$contains</code>. אופרטור לא מוכר זורק שגיאה.",
      "<b>ragkit.vectors.bench:</b> <code>sweep</code>, ‏<code>recall_ids</code>, ‏<code>pareto_frontier</code>, ‏<code>exact_filtered_top_k</code>, ‏<code>filtered_recall</code> ו-<code>post_filter</code>.",
      "<b>ragkit.vectors.sizing:</b> <code>hnsw_ram_bytes</code> ומודלי עלות: <code>s3vectors_monthly</code>, ‏<code>opensearch_serverless_monthly</code>, ‏<code>aurora_pgvector_monthly</code>, ‏<code>ec2_qdrant_monthly</code> ו-<code>compare</code>.",
      "<b>mine.py:</b> ארבעה חלקים שלך: <code>recall_at_k</code> ו-<code>pareto_frontier</code> (תרגיל 2), <code>exact_filtered_top_k</code> ו-<code>filtered_recall</code> (תרגיל 3), <code>index_ram_bytes</code> (תרגיל 5) ו-<code>acl_where</code> (תרגיל 6).",
    ],
    exercises: [
      {
        id: "ex1",
        title: "מבט לתוך גרף HNSW",
        text: "הסקריפט בונה <code>faiss.IndexHNSWFlat</code> על 20 אלף וקטורים סינתטיים (384 ממדים), עם כמה ערכים של M, ומדפיס ארבעה דברים. הראשון: כמה צמתים הגיעו לכל שכבה, מול התחזית n·M<sup>−l</sup>. השני: מספר השכנים הממוצע והמקסימלי בשכבה 0 (תקרה 2M) ובשכבה 1 (תקרה M). השלישי: גודל האינדקס האמיתי מול הנוסחה <code>4d + (2M·4+4) + (M·4+4)/(M−1)</code> בתים לצומת. הרביעי: זמן הבנייה ו-recall@10 ב-efSearch של 16, ‏64 ו-256. בסוף הוא מנסה למחוק צומת. ענה על ארבע שאלות. (1) כמה שכבות יש עם M=16, והאם זה קרוב ל-log<sub>M</sub>(n)? (2) מה הפער בין הנוסחה לגודל האמיתי? (3) פי כמה התייקרה הבנייה מ-M=8 ל-M=32, ומה קיבלת בתמורה ב-efSearch=16? (4) למה FAISS מסרב למחוק, ומה Qdrant ו-pgvector עושים במקום?",
        cmd: "python labs/11-managed-vectors/hnsw_inspect.py --m 8 --m 16 --m 32\npython labs/11-managed-vectors/hnsw_inspect.py --ef-construction 20 --ef-construction 200",
      },
      {
        id: "ex2",
        title: "כיוונון efSearch ו-M, וחזית פארטו (קוד)",
        text: "ממש ב-<code>mine.py</code> שתי פונקציות. <code>recall_at_k(found, truth, k)</code>: החלק של k התוצאות המדויקות שנמצאו. רק k הראשונים בכל רשימה נספרים, ו-truth ריק נותן 1.0. <code>pareto_frontier(points)</code>: הנקודות (זמן, recall) שאף נקודה אחרת לא טובה מהן בשני הצירים, ממוינות לפי זמן. כפילות מדויקת נשמרת פעם אחת. הדוגמה מה-docstring: <code>[(1.0,0.80),(2.0,0.95),(1.5,0.70),(3.0,0.95),(4.0,0.99)] → [0, 1, 4]</code>. אחר כך הרץ סריקה של M מתוך {8, 16, 32} ו-ef מ-10 עד 320, על 30 אלף וקטורים: קודם FAISS (לא מקוון), ואחר כך Qdrant ו-pgvector שבדוקר. הסקריפט בודק גם שהחיפוש המדויק של השרת מסכים עם numpy. ענה על שלוש שאלות. (1) מהי התצורה הזולה ביותר עם recall@10 של 0.95 ומעלה בכל backend? (2) למה אסור להשוות מילישניות בין FAISS (בתוך התהליך) לבין Qdrant (ברשת)? (3) כמה נקודות מהסריקה נשארו על החזית?",
        cmd: "python -m pytest -q labs/11-managed-vectors/tests/test_ex2_pareto.py\npython labs/11-managed-vectors/hnsw_sweep.py --mine\npython labs/11-managed-vectors/hnsw_sweep.py --backend qdrant --m 16,32 --ef 16,32,64,128,256\npython labs/11-managed-vectors/hnsw_sweep.py --backend pgvector --m 16 --ef 20,40,80,160",
      },
      {
        id: "ex3",
        title: "חיפוש עם מסנן ומלכודת המסנן המצמצם (קוד)",
        text: "ממש ב-<code>mine.py</code> שתי פונקציות. <code>exact_filtered_top_k(query, matrix, mask, k)</code> היא אמת המידה: k השורות הדומות ביותר לפי cosine מתוך השורות שבהן mask הוא True. היא מחזירה <b>אינדקסים של המטריצה המלאה</b>, וכשיש שוויון האינדקס הנמוך קודם. <code>filtered_recall(found, exact, k)</code>: המכנה הוא min(k, len(exact)), ו-exact ריק נותן 1.0. הנתונים: 50 אלף וקטורים, ועליהם מסננים בסלקטיביות של 50%, ‏10%, ‏1% ו-0.1%, כל אחד בשתי גרסאות. ב-<b>random</b> השורות שעוברות פזורות. ב-<b>clustered</b> הן אשכולות שלמים, כמו לקוח. האסטרטגיות: post-filter, ‏in-graph (FAISS IDSelector), ‏pre-filter (מדויק על התת-קבוצה), ‏planner (מדויק עד 6,000 שורות). עם <code>--qdrant</code> מתווסף Qdrant עם ACORN כבוי ודולק, ועם <code>--pgvector</code> מתווסף pgvector עם iterative scan כבוי ודולק. ענה על ארבע שאלות. (1) כמה תוצאות החזיר post-filter ב-1% וב-0.1%? (2) למה גם in-graph מחזיר פחות מ-10 במסנן מצמצם? (3) למה clustered קשה יותר מ-random באותה סלקטיביות? (4) האם relaxed_order תיקן את pgvector, והאם ACORN שינה משהו?",
        cmd: "python -m pytest -q labs/11-managed-vectors/tests/test_ex3_filtered.py\npython labs/11-managed-vectors/filter_pitfall.py --mine\npython labs/11-managed-vectors/filter_pitfall.py --qdrant --pgvector",
      },
      {
        id: "ex4",
        title: "Acme בתוך Qdrant ו-pgvector, מול החיפוש המדויק",
        text: "הסקריפט טוען את 210 ה-chunks של Acme (עם embeddings של e5-small מהמטמון של שיעור 10) ל-Qdrant ול-pgvector, ומריץ את 79 שאלות הזהב (<code>data/acme/corpus/golden/qa.jsonl</code>). לכל store הוא מדפיס: agree@10 (איזה חלק מה-top-10 של <code>NumpyVectorStore</code> חזר גם מה-store), ‏R@5 ו-MRR ברמת המסמך על 69 השאלות שיש להן מקור, וזמני טעינה ושאילתה. אחר כך הוא מריץ את מחזור העדכון: מחיקה של <code>hr-vacation-2026</code> (3 chunks), הוספה מחדש עם טקסט ערוך, ובדיקה שכל ה-stores מסכימים. <code>--where language=he</code> מוסיף מסנן, ו-<code>--show q039</code> מציג את ה-top-5 של כל store לשאלה אחת (q039 היא שאלה באנגלית שהתשובה עליה נמצאת במסמך הקליטה בעברית). ענה על שתי שאלות. (1) האם agree@10 הוא 1.000 בכל ה-stores? אם לא, באיזו שאלה, והאם R@5 השתנה? (2) מה עשתה <code>--quantization binary</code> לווקטורים של e5 ב-384 ממדים?",
        cmd: "python labs/11-managed-vectors/load_acme.py --model fake\npython labs/11-managed-vectors/load_acme.py --qdrant --pgvector\npython labs/11-managed-vectors/load_acme.py --qdrant --pgvector --where language=he --show q039\npython labs/11-managed-vectors/load_acme.py --qdrant --quantization binary",
      },
      {
        id: "ex5",
        title: "Quantization: זיכרון מול recall, ו-rescoring (קוד)",
        text: "ממש ב-<code>mine.py</code> את <code>index_ram_bytes(n, dim, m=16, quantization=None, originals_in_ram=None)</code>. הפונקציה מחזירה את ה-RAM של אינדקס HNSW, ומחברת שלושה חלקים. הגרף: <code>(2m·4+4) + (m·4+4)/(m−1)</code> בתים לצומת (ו-0 אם m קטן מ-2). הקודים: ב-float16 שני בתים לממד, ב-int8 (או scalar) בית אחד, וב-binary ‏ceil(dim/8) בתים. המקוריים ב-float32 נספרים רק אם הם ב-RAM. ברירת המחדל: כן בלי quantization, לא עם quantization. דוגמה: <code>index_ram_bytes(1_000_000, 384)</code> ≈ 1.672e9. אחר כך הסקריפט משווה float32, ‏float16, ‏int8, ‏binary ו-PQ על 30 אלף וקטורים: בתים לווקטור, RAM ב-1 וב-10 מיליון, recall@10 על הקודים בלבד, ו-recall עם rescoring ב-oversampling של 2, ‏4 ו-10. עם <code>--qdrant</code> הניסוי רץ גם על Qdrant עם scalar, ‏binary ו-product. ענה על שלוש שאלות. (1) כמה recall איבדה binary בלי rescoring, וכמה החזיר oversampling של 4? (2) כמה RAM חוסך int8 ל-10 מיליון וקטורים של 1024 ממדים? (3) איפה יושבים המקוריים, ומה עולה לקרוא אותם?",
        cmd: "python -m pytest -q labs/11-managed-vectors/tests/test_ex5_memory.py\npython labs/11-managed-vectors/quantization.py --mine\npython labs/11-managed-vectors/quantization.py --real e5-small --qdrant",
      },
      {
        id: "ex6",
        title: "Multi-tenancy והרשאות לפי סיווג (קוד)",
        text: "ממש ב-<code>mine.py</code> את <code>acl_where(role)</code>. הפונקציה מחזירה מסנן <code>where</code> שמממש את המטריצה של שיעור 24. public גלוי לכל תפקיד. internal גלוי לכל תפקיד חוץ מ-contractor. confidential גלוי ל-security, ולתפקיד שהמחלקה שלו היא המחלקה של המסמך: engineering→engineering, ‏support→sales_support, ‏hr→hr, ‏finance→finance. תפקיד לא מוכר לא רואה כלום. הנתונים (<code>data/acme/corpus/docs/</code>): 47 מסמכים internal ו-4 public (מחירוני 2025 ו-2026, וה-SLA של 2025 ושל 2026). 4 מסמכים confidential: ‏<code>eng-pm-2026-03-scheduler</code>, ‏<code>eng-pm-2026-06-billing</code> ו-<code>eng-pm-2026-08-api</code> של engineering, ו-<code>hr-relocation</code> של hr. התפקידים: engineering, ‏support, ‏hr, ‏finance, ‏security, ‏employee ו-contractor. הסקריפט מדפיס את הנתונים ואת המסנן של כל תפקיד בשלושה ניבים (Qdrant, ‏SQL ו-S3 Vectors). אחר כך הוא מריץ שתי שאלות לכל תפקיד: על השבתת אוגוסט, ועל רילוקיישן לברלין. הוא בודק את כל 79 השאלות מול 7 התפקידים (אפס chunks אסורים, ותוצאות זהות לחיפוש מדויק על המותרים), ומראה את הדרך השגויה: סינון בקוד אחרי top-5. ענה על שתי שאלות. (1) מה רואה contractor בשאלה על ההשבתה, ולמה זה עדיף על תשובה ריקה? (2) למה סינון אחרי top-5 גם מדליף מידע?",
        cmd: "python -m pytest -q labs/11-managed-vectors/tests/test_ex6_acl.py\npython labs/11-managed-vectors/acl_demo.py --mine\npython labs/11-managed-vectors/acl_demo.py --mine --qdrant",
      },
      {
        id: "ex7",
        title: "האפשרויות ב-AWS ותחשיב עלות",
        text: "הסקריפט מחשב עלות חודשית ל-1 ול-10 מיליון וקטורים (ברירת מחדל: 1024 ממדים, 100 אלף שאילתות בחודש), לכל אפשרות: S3 Vectors, ‏OpenSearch Serverless (הדור הקלאסי, ו-NextGen עם 200 שעות פעילות), ‏Aurora Serverless עם pgvector (float32 ו-halfvec), ‏Qdrant על EC2, ו-Pinecone להשוואה. ליד כל שורה מודפסות ההנחות שלה. הוא גם מדפיס את ה-RAM של האינדקס, ואת הוראות ה-teardown לכל אפשרות. המחירים הם של us-east-1, נובמבר 2026, עם המקורות. כתוב המלצה של פסקה ל-Company Brain, שעונה על שלוש שאלות: איזו אפשרות לפיילוט (אלפי chunks, עשרות משתמשים), איזו ל-10 מיליון chunks עם hybrid search, ומה היה גורם לך להחליף. התייחס לעלות בסרק, ל-cold start, ל-hybrid search (שיעור 12) ולזמן התגובה שהמשתמש מרגיש.",
        cmd: "python labs/11-managed-vectors/aws_cost.py\npython labs/11-managed-vectors/aws_cost.py --dims 384,1536 --queries 1000000\npython labs/11-managed-vectors/aws_cost.py --n 210 --dims 384",
      },
      {
        id: "ex8",
        title: "(רשות) S3 Vectors אמיתי, עם Terraform ו-teardown",
        text: "מה צריך: חשבון AWS, ‏<code>aws configure</code> ו-<code>uv pip install boto3</code>. יש שתי דרכים ליצור את המשאבים. הראשונה: התיקייה <code>terraform/</code> יוצרת vector bucket, אינדקס (‏cosine, ‏384 ממדים, ‏<code>chunk</code> כמטא-דאטה שלא מסננים לפיו) ו-IAM policy מינימלית לאינדקס אחד. השנייה: הסקריפט יוצר אותם בעצמו. הסקריפט מעלה את 210 הווקטורים בקבוצות של עד 500, ומשווה את התוצאות לחיפוש המדויק (AWS מבטיחה recall ממוצע של 90% ומעלה). הוא גם מריץ את <code>acl_where</code> של engineering ושל contractor על q014 (השבתת flow-api), כדי להראות שהמסנן רץ בשרת. העלות פחות מסנט. בחר אזור עם S3 Vectors, למשל eu-central-1 (תל אביב לא הייתה ברשימה של דצמבר 2025). בסוף <b>מוחקים</b>, ובודקים ב-Cost Explorer למחרת.",
        cmd: "cd labs/11-managed-vectors/terraform && terraform init && terraform apply -var bucket_name=acme-brain-david && cd -\npython labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-david --region eu-central-1\npython labs/11-managed-vectors/s3vectors_demo.py --bucket acme-brain-david --region eu-central-1 --teardown\ncd labs/11-managed-vectors/terraform && terraform destroy -var bucket_name=acme-brain-david",
      },
    ],
  },

  quiz: [
    {
      q: "ב-HNSW עם M=16, בערך כמה מתוך 10,000 צמתים יגיעו לשכבה 1 ומעלה?",
      options: ["5,000", "625", "1,600", "16"],
      correct: 1,
      explain: "ההסתברות להגיע לשכבה l ומעלה היא <b>M בחזקת מינוס l</b>. לשכבה 1 זה 1/16, כלומר כ-625 מתוך 10,000. ב-FAISS נמדדו 1,239 מתוך 20,000. לכן <b>רוב הזיכרון של הגרף הוא שכבה 0</b>.",
    },
    {
      q: "ה-recall לא מגיע ל-0.95 גם עם efSearch=1000. מה הצעד הנכון?",
      options: ["להעלות עוד את efSearch", "לבנות מחדש עם M או efConstruction גבוהים יותר", "להוריד את k", "להפעיל binary quantization"],
      correct: 1,
      explain: "efSearch רק מרחיב את החיפוש על <b>הגרף הקיים</b>. אם הקשתות הנכונות לא נבחרו בבנייה, אין דרך להגיע אליהן. M ו-efConstruction הם פרמטרים של <b>בנייה</b>, ומחייבים בנייה מחדש.",
    },
    {
      q: "10 מיליון וקטורים של 1024 ממדים, M=16. מה החלק העיקרי של ה-RAM של HNSW בלי quantization?",
      options: ["הגרף (רשימות השכנים)", "הווקטורים עצמם", "המטא-דאטה", "השכבות העליונות"],
      correct: 1,
      explain: "הווקטורים תופסים <b>4,096 בתים</b> לכל אחד, והגרף כ-136 בתים לצומת. כלומר 41GB מול 1.4GB. לכן הכלי לחיסכון בזיכרון הוא <b>quantization</b>, ולא הורדה של M.",
    },
    {
      q: "מה עושה rescoring עם oversampling של 4, כש-k=10?",
      options: ["מחפש 4 פעמים ומחשב ממוצע", "מביא 40 מועמדים עם הקודים הדחוסים, ומדרג אותם מחדש עם הווקטורים המקוריים", "מכפיל את efSearch ב-4", "שומר 4 עותקים של האינדקס"],
      correct: 1,
      explain: "החיפוש רץ על הקודים הזולים, ובוחר <b>k כפול oversampling</b> מועמדים. רק אותם מדרגים מחדש עם float32, ולכן המקוריים יכולים לשבת <b>בדיסק</b>. בתרגיל 5, ‏PQ עלה כך מ-0.83 ל-0.99.",
    },
    {
      q: "מסנן שמשאיר 1% מהשורות. post-filter על 100 מועמדים מ-HNSW. מה צפוי לקרות כש-k=10?",
      options: ["10 תוצאות נכונות", "בערך תוצאה אחת, ותשובה של \"לא מצאתי\"", "שגיאה מהמסד", "10 תוצאות, חלקן לא עוברות את המסנן"],
      correct: 1,
      explain: "מתוך 100 מועמדים, בערך 1% עוברים, כלומר כ<b>תוצאה אחת</b>. במדידה חזרו 0.9 תוצאות בממוצע, עם recall של 0.09. זו <b>מלכודת המסנן המצמצם</b>, ולכן post-filtering נאיבי פסול לסינון לפי לקוח או הרשאה.",
    },
    {
      q: "איך Qdrant מטפל במסנן שמעט מאוד נקודות עוברות אותו?",
      options: ["post-filtering עם oversampling גדול", "ה-planner מעריך את מספר הנקודות לפי payload index, ומתחת ל-full_scan_threshold מחשב מרחקים בחיפוש מדויק עליהן", "מחזיר שגיאה", "בונה גרף חדש לשאילתה"],
      correct: 1,
      explain: "ה-<b>query planner</b> משתמש ב-cardinality של ה-payload index. כשמעט נקודות עוברות, <b>חיפוש מדויק</b> עליהן הוא גם נכון וגם זול. מעל הסף הוא הולך ב-<b>filterable HNSW</b>, ועם ACORN לצירופים קשים.",
    },
    {
      q: "שאילתה ב-pgvector: WHERE tenant = 'x' ORDER BY embedding <=> $1 LIMIT 10 החזירה 3 שורות, למרות שללקוח יש אלפי מסמכים. מה הסיבה הסבירה, ומה התיקון?",
      options: ["חסר אינדקס GIN, וצריך להוסיף אותו", "ה-WHERE רץ אחרי סריקת HNSW שהחזירה רק ef_search מועמדים, והתיקון הוא hnsw.iterative_scan = relaxed_order", "האופרטור <=> שגוי", "צריך VACUUM FULL"],
      correct: 1,
      explain: "ב-pgvector המסנן רץ <b>אחרי</b> סריקת האינדקס. ‏<b>iterative scans</b> (מגרסה 0.8.0) ממשיכים לסרוק עד שמספיק שורות עוברות, או עד <code>hnsw.max_scan_tuples</code>.",
    },
    {
      q: "למה לא לסנן הרשאות בקוד האפליקציה אחרי top-k?",
      options: ["כי זה איטי", "כי חוזרות פחות תוצאות, והפער מדליף שיש מסמכים חסויים על הנושא", "כי מודל השפה יתעלם מהסינון", "כי Qdrant לא מאפשר"],
      correct: 1,
      explain: "סינון אחרי הדירוג <b>מקצר את התשובה</b>: contractor קיבל 0 מתוך 5 בשאלה על ההשבתה. הוא גם <b>מדליף מידע דרך הדירוג</b>. מסנן שנשלח לשאילתה, לפני הדירוג, נכון וגם בטוח.",
    },
    {
      q: "מחליפים את מודל ה-embeddings מ-e5-small (384 ממדים) ל-bge-m3 (1024 ממדים). מה הדרך הבטוחה?",
      options: ["upsert של הווקטורים החדשים לאותו אוסף", "לבנות אוסף חדש לצד הישן, למדוד על שאלות הזהב, ולהעביר alias בבת אחת", "לקצץ את bge-m3 ל-384 ממדים", "לשנות את efSearch"],
      correct: 1,
      explain: "וקטורים משני מודלים <b>לא ניתנים להשוואה</b>, והממד שונה. בונים לצד הישן (<b>blue/green</b>), מודדים, מחליפים alias אטומית, ומשאירים את הישן ל-rollback.",
    },
    {
      q: "Company Brain בפיילוט: 50 אלף chunks, כמה אלפי שאלות בחודש, בשעות העבודה, בלי hybrid בתוך המסד. איזו אפשרות ב-AWS הכי זולה?",
      options: ["OpenSearch Serverless קלאסי", "S3 Vectors", "Aurora עם 4 ACU דולקים", "שני שרתי EC2 עם Qdrant"],
      correct: 1,
      explain: "ב-S3 Vectors <b>אין עלות בסרק</b>: משלמים על אחסון ועל שאילתות, וזה סנטים בחודש. ב-OpenSearch Serverless הקלאסי יש מינימום של <b>2 OCUs</b>, כ-350$ בחודש. ההסתייגויות: זמן התגובה (כ-100ms עד שנייה) ו-hybrid, שיישאר ב-ragkit.",
    },
  ],

  summary: {
    points: [
      { t: "למה מסד נתונים וקטורי", b: "חיפוש מדויק עובד מצוין עד מאות אלפי וקטורים. מעבר לזה, או כשיש עדכונים, מסננים, הרשאות וכמה שרתים, צריך אינדקס ANN ועוד כל מה שמסד נתונים נותן: עמידות, מחיקות, מסננים, quantization, גיבויים ושכפול. ב-ragkit כל store מממש את אותו פרוטוקול <code>VectorStore</code>, ולכן המעבר הוא שורה אחת." },
      { t: "HNSW: שכבות והגרלה", b: "צומת מגיע לשכבה l בהסתברות M בחזקת מינוס l, ולכן יש log בבסיס M של n שכבות, ורוב הגרף הוא שכבה 0. הכנסה היא ירידה חמדנית, ואחריה חיפוש עם efConstruction, בחירה של M שכנים מגוונים, וקישור וגיזום. חיפוש הוא ירידה חמדנית, ואחריה רשימה של efSearch מועמדים בשכבה 0." },
      { t: "כיוונון לפי חזית פארטו", b: "M ו-efConstruction נקבעים בבנייה, ו-efSearch אפשר לשנות בכל שאילתה. מודדים recall@10 מול חיפוש מדויק, ואת הזמן הממוצע ו-p95, על רשת של תצורות, ומשאירים רק את התצורות שאין טובה מהן בשני הצירים. ב-50 אלף וקטורים, M=32 עם ef=20 נתן recall של 0.986 ב-0.36ms." },
      { t: "זיכרון ו-quantization", b: "הגרף תופס כ-136 בתים לצומת (M=16), והווקטורים dim כפול 4 בתים, ולכן הווקטורים הם רוב ה-RAM. int8 חוסך פי 4 כמעט בלי אובדן, ו-binary או PQ חוסכים פי 32 עם אובדן משמעותי. rescoring עם oversampling מחזיר את רוב ה-recall, והמקוריים יושבים בדיסק." },
      { t: "מלכודת המסנן המצמצם", b: "post-filter עם מסנן של 1% מחזיר תוצאה אחת במקום 10, ו-in-graph עם לקוח מרוכז מחזיר 10 תוצאות שגויות בשקט. query planner מחשב מרחקים בחיפוש מדויק כשמעט שורות עוברות, והולך בגרף כשהרבה עוברות. Qdrant מוסיף filterable HNSW ו-ACORN, ‏pgvector 0.8 מוסיף iterative scans, ו-S3 Vectors מוסיף מצב ENHANCED (ספטמבר 2026)." },
      { t: "הרשאות ו-multi-tenancy", b: "המסנן נבנה מהתפקיד המאומת (<code>acl_where(role)</code>), נשלח למסד הנתונים, ורץ לפני הדירוג. סינון אחרי top-k מקצר את התשובה ומדליף מידע. ב-Qdrant: אוסף אחד, ‏payload index עם is_tenant, ו-m=0 עם payload_m=16 כשכל השאילתות לפי לקוח. מתרגם מסננים חייב להיכשל סגור." },
      { t: "עדכונים ובנייה מחדש", b: "מחיקה היא tombstone, ואחריה תיקון ברקע (VACUUM, אופטימייזר). הרבה מחיקות שלא טופלו מורידות recall. עדכון הוא upsert לפי מזהה chunk יציב. החלפת מודל embeddings מחייבת אינדקס חדש לצד הישן, מדידה, והעברה אטומית של alias." },
      { t: "תפעול", b: "snapshots ב-Qdrant, וגיבוי רגיל ב-Postgres. אפשר גם לבנות מחדש מהמקור ומהמטמון של ה-embeddings. replica נותנת זמינות ותפוקה, ו-shard נותן קיבולת, במחיר של זמן. canary queries שמשוות חיפוש רגיל לחיפוש מדויק מנטרות recall בייצור." },
      { t: "הבחירה ב-AWS", b: "S3 Vectors זול בסדרי גודל ובלי עלות בסרק, אבל עם latency של 100ms עד שנייה ובלי hybrid. OpenSearch Serverless נותן hybrid מלא: בדור הקלאסי במינימום של 2 OCUs, וב-NextGen עם scale to zero. Aurora עם pgvector מתאים כשממילא יש PostgreSQL. מה שקובע את ההחלטה הוא דפוס העומס, ומה שקובע את המחיר הוא כמה RAM צריך להיות דולק." },
    ],
    glossary: [
      ["HNSW", "גרף של שכנים קרובים בכמה שכבות. החיפוש מתחיל בשכבה העליונה הדלילה, ויורד חמדנית עד חיפוש רחב בשכבה 0."],
      ["M", "מספר השכנים המקסימלי לצומת בשכבות העליונות (בשכבה 0 עד 2M). פרמטר של בנייה, שקובע את הקישוריות ואת זיכרון הגרף."],
      ["efConstruction", "גודל רשימת המועמדים בזמן הכנסה. ערך גבוה נותן גרף איכותי יותר ובנייה איטית יותר, בלי זיכרון נוסף."],
      ["efSearch", "גודל רשימת התוצאות בחיפוש בשכבה 0. ערך גבוה נותן recall גבוה יותר וזמן ארוך יותר. אפשר לשנות אותו בכל שאילתה."],
      ["recall@k מול חיפוש מדויק", "איזה חלק מ-k השכנים האמיתיים האינדקס החזיר. זה מודד את האינדקס, ולא את הרלוונטיות."],
      ["חזית פארטו", "קבוצת התצורות שאין תצורה אחרת שטובה מהן גם ב-recall וגם בזמן."],
      ["Scalar quantization", "כל קואורדינטה הופכת לבית אחד (int8). הקוד קטן פי 4, והאובדן קטן."],
      ["Binary quantization", "ביט אחד לקואורדינטה, ומרחק Hamming. הקוד קטן פי 32. מתאים לממדים גבוהים, ורק עם rescoring."],
      ["Product quantization", "חלוקת הווקטור לתת-וקטורים, ושמירה של המספר של המרכז הקרוב לכל אחד. דחיסה גבוהה וחישוב איטי יחסית."],
      ["Rescoring / oversampling", "חיפוש עם הקודים הדחוסים על k כפול oversampling מועמדים, ודירוג מחדש שלהם עם הווקטורים המקוריים."],
      ["Post-filtering", "חיפוש בלי מסנן, וזריקה של מה שלא עובר. עם מסנן מצמצם חוזרות פחות מ-k תוצאות."],
      ["Pre-filtering", "מציאת השורות שעוברות, וחיפוש מדויק רק עליהן. תמיד נכון, ויקר כשהרבה שורות עוברות."],
      ["Filterable HNSW / ACORN", "ב-Qdrant: קשתות נוספות בין נקודות עם אותו ערך בשדה מאונדקס, ובדיקה של שכנים של שכנים כשמסננים מצמצמים שוברים את הגרף."],
      ["Iterative index scan", "ב-pgvector מגרסה 0.8: הסריקה של HNSW ממשיכה עד שמספיק שורות עוברות את ה-WHERE."],
      ["Tombstone", "סימון של נקודה כמחוקה בלי להוציא אותה מהגרף. התיקון נעשה ברקע, ב-VACUUM או באופטימייזר."],
      ["OCU / ACU", "יחידות החיוב של OpenSearch Serverless (כ-6GB זיכרון) ושל Aurora Serverless (כ-2GB זיכרון)."],
    ],
    reading: [
      { title: "Efficient and robust approximate nearest neighbor search using HNSW graphs (Malkov & Yashunin)", url: "https://arxiv.org/abs/1603.09320", note: "המאמר המקורי. אלגוריתמים 1 עד 4 (הכנסה, חיפוש בשכבה, בחירת שכנים פשוטה והיוריסטית) הם בדיוק מה שהאנימציה מממשת." },
      { title: "pgvector README", url: "https://github.com/pgvector/pgvector", note: "HNSW ו-IVFFlat, ‏iterative index scans, ‏halfvec, ‏binary_quantize עם re-ranking, וברירות המחדל: m=16, ‏ef_construction=64, ‏ef_search=40." },
      { title: "pgvector CHANGELOG", url: "https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md", note: "0.8.0 (אוקטובר 2024) הוסיף iterative scans. גרסאות 0.8.2 עד 0.8.6 של 2026 הן תיקוני VACUUM ובנייה, ותמיכה ב-PostgreSQL 18." },
      { title: "Qdrant: Indexing (HNSW, payload index, filterable HNSW, ACORN)", url: "https://qdrant.tech/documentation/concepts/indexing/", note: "m=16, ‏ef_construct=100 ו-full_scan_threshold=10000KB כברירת מחדל, ולמה יוצרים payload index לפני הנתונים." },
      { title: "Qdrant: Quantization", url: "https://qdrant.tech/documentation/guides/quantization/", note: "scalar, ‏binary ו-product, עם rescore, ‏oversampling ו-always_ram. המדריך ממליץ על binary רק עם rescoring." },
      { title: "Qdrant: Multitenancy (single collection, is_tenant, tiered shards)", url: "https://qdrant.tech/documentation/guides/multiple-partitions/", note: "m=0 עם payload_m=16, ‏is_tenant, וקידום לקוח גדול ל-shard משלו סביב 20 אלף נקודות." },
      { title: "Qdrant releases (v1.20.0, October 2026)", url: "https://github.com/qdrant/qdrant/releases", note: "BM25 על אינדקס full-text, ‏TurboQuant, ו-inline_storage של HNSW." },
      { title: "Amazon S3 Vectors is now generally available", url: "https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance", note: "דצמבר 2025: עד 2 מיליארד וקטורים לאינדקס, ‏14 אזורים, וכ-100ms לשאילתות חמות." },
      { title: "S3 Vectors: metadata filtering (CLASSIC vs ENHANCED)", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-metadata-filtering.html", note: "האופרטורים, ולמה אינדקס CLASSIC יכול להחזיר פחות מ-topK." },
      { title: "S3 Vectors: limitations", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html", note: "1 עד 4,096 ממדים, ‏500 וקטורים ל-PutVectors, ‏40KB של מטא-דאטה (2KB לסינון), ו-topK עד 10,000 עם דפדוף." },
      { title: "Amazon OpenSearch Service pricing", url: "https://aws.amazon.com/opensearch-service/pricing/", note: "0.24$ ל-OCU לשעה, מינימום בדור הקלאסי, ו-NextGen בלי מינימום. שים לב: חלק מהדוגמאות בעמוד סותרות זו את זו, ולכן משתמשים במחשבון." },
      { title: "Next-gen Amazon OpenSearch Serverless (Classmethod, May 2026)", url: "https://dev.classmethod.jp/articles/20260531-amazon-opensearch-service-nxgn-ga/", note: "ניסוי מעשי: scale to zero אחרי 10 דקות, ‏cold start של כ-10 שניות, ובניית HNSW על GPU. ביפנית, ומתורגם היטב בדפדפן." },
      { title: "Aurora Serverless: scaling to 0 ACUs", url: "https://aws.amazon.com/blogs/database/introducing-scaling-to-0-capacity-with-amazon-aurora-serverless-v2/", note: "auto-pause, חזרה תוך עד כ-15 שניות, כ-2GB ל-ACU, ומה מונע pause." },
      { title: "OpenSearch: disk-based vector search", url: "https://docs.opensearch.org/latest/vector-search/optimizing-storage/disk-based-vector-search/", note: "mode on_disk עם דחיסה של 32x כברירת מחדל ו-rescoring עם oversample_factor." },
    ],
  },
};
