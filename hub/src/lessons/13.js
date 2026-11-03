// Lesson 13 — RAG Quality and Retrieval Diagnostics.
window.LESSONS = window.LESSONS || {};
window.LESSONS["13"] = {
  n: 13,
  title: "RAG Quality and Retrieval Diagnostics",
  he: "לאבחן איפה RAG נכשל ולמדוד groundedness",
  hours: "כשעתיים וחצי שיעור, כחמש שעות מעבדה",

  goals: [
    "להבין למה מדד אחד מקצה לקצה (\"36 מתוך 79 נכונות\") לא מספיק כדי לשפר מערכת RAG, ולחשוב על התשובה כעל <b>שרשרת של שלבים</b>: קורפוס, חילוץ, chunking, אחזור, חיתוך ל-top-k, יצירה וציטוט. כל שלב יכול לאבד את התשובה, ולכל שלב יש תיקון אחר.",
    "להכיר <b>טקסונומיה של 12 כשלים</b> לפי שלב: חסר בקורפוס, החילוץ איבד, ה-chunk חתך, לא אוחזר, אוחזר ונחתך (ranked low), גרסה מיושנת, סירוב שגוי, lost in the middle, התעלמות מההקשר, hallucination מהידע של המודל, ציטוט שגוי, ואי-סירוב לשאלה שאין לה תשובה. לכל אחד לדעת איך מזהים אותו ומה מתקן אותו.",
    "לבנות <b>נוהל אבחון אוטומטי</b> לכל שאלה שנכשלה: שואלים שאלות לפי סדר הצנרת, והשלב הראשון שנכשל הוא <b>שורש הבעיה</b>. הנוהל נשען על נתוני הזהב (source_ids וציטוטים מדויקים), על trace של האחזור ועל שופט.",
    "להגדיר ולחשב <b>מדדים לפי שלב</b>, עם נוסחאות: context recall, context precision (גם בגרסה שמודעת לדירוג), groundedness (faithfulness), answer relevance, citation precision ו-citation recall. ולדעת מה כל אחד מהם רואה ומה הוא מפספס.",
    "לבדוק <b>groundedness ברמת טענה</b>: לפרק תשובה לטענות אטומיות, ולבדוק כל טענה מול ההקשר עם שופט LLM ו-structured outputs, כשהראיה נכתבת לפני פסק הדין ונבדקת אחר כך בקוד. להכיר את החלופה של <b>מודל NLI</b> מקומי ורב-לשוני, ואת המחיר של כל גישה.",
    "להשוות את <b>Ragas</b> ואת <b>RAGChecker</b> למדדים שתכתוב בעצמך: מה השמות והנוסחאות של המדדים שלהם היום, ומתי עדיף מדד משלך שנשען על נתוני הזהב שלך.",
    "להבין <b>מספיקות של הקשר</b> (sufficient context) ו<b>ייחוס</b> (attribution): מתי למודל אין מספיק מידע ובכל זאת הוא עונה, ואיך ציטוטים מקוריים של Claude מחזירים את הטווח המדויק שצוטט.",
    "להפוך אבחנה לתיקון: למפות כל שלב לתיקון משיעורים 9 עד 12, להפעיל <b>שינוי אחד בכל פעם</b>, ולמדוד אותו בהשוואה מזווגת עם gates. לראות בעיניים שתיקון יכול להזיז כשל לשלב הבא, או ליצור כשל חדש.",
  ],
  connects: "בשיעור 9 בנית את <b>ragkit</b>: ingestion, chunking, BM25 ולולאת תשובה עם ציטוטים. שם גם מדדת כיסוי של ציטוטי זהב (covered, split, missing). בשיעור 10 הוספת embeddings ו-recall@k. בשיעור 11 ה-VectorStore עבר למסד נתונים מנוהל. בשיעור 12 בנית את שכבת האחזור המלאה: RRF, שכתוב שאילתות, סינון גרסאות ו-reranking, ומדדת כל שלב ב-ablation. כל המדידות האלה היו של <b>האחזור</b>. השיעור הזה מודד את <b>התשובה</b>, ומאבחן לכל שאלה שנכשלה איפה בדיוק בצנרת היא נכשלה. הוא סוגר את שלב 2 (ידע), ו<b>פרויקטי האמצע</b> שמגיעים מיד אחריו ישתמשו באבחון הזה כדי להראות למה המערכת שלהם טובה ואיפה היא עוד נכשלת. מושגי ההערכה (שופט LLM, כיול, סטטיסטיקה מזווגת, gates) מוסברים כאן בקצרה, ונבנים לעומק ב<b>שיעור 23</b>. ה-traces שהשיעור מקליט הם בדיוק מה ש-<b>שיעור 22</b> ילמד לאסוף בייצור. ב-<b>Company Brain</b>, כל תשובה שגויה שמשתמש מדווח עליה תעבור את אותו נוהל אבחון.",

  intro: {
    animation: "l13funnel",
    animationTitle: "משפך הכשלים: איפה בצנרת השאלות נופלות",
    animationGuide: `<p><b>מה רואים כאן:</b> 69 שאלות הזהב של Acme שיש להן תשובה בקורפוס, כשהן עוברות את הצנרת שלב אחר שלב. כל שורה היא "שער": שאלה עוברת אותו רק אם השלב הזה לא הוא שורש הכשל שלה. הפס הכחול מראה כמה שאלות הגיעו לשער, והקטע האדום מראה כמה נפלו בו. מתחת לפסים יש רשת של 69 נקודות, נקודה לכל שאלה. כשהשאלה נופלת, הנקודה שלה נצבעת בצבע של קבוצת השלבים: ingestion, retrieval או generation. 10 השאלות שאין להן תשובה מוצגות בנפרד בסוף.</p>
<p><b>מאיפה המספרים:</b> הם נמדדו במעבדה של השיעור, במסלול הלא מקוון: אחזור אמיתי מעל הקורפוס, answerer חילוצי (מעתיק משפטים ולא מודל שפה) ושופט לקסיקלי. לכן השערים של האחזור מדויקים, והשערים של היצירה מראים את החולשות של ה-answerer החילוצי ולא של Claude. בתרגיל 7 תריץ את אותו דבר עם Haiku.</p>
<p><b>איך לקרוא:</b> השלבים מתקדמים לבד, ואפשר לעצור ולדפדף עם החיצים או עם הכפתורים הממוספרים. שלושת הכפתורים למעלה מחליפים את הצנרת:</p>
<ol>
<li><b>baseline:</b> הצנרת של שיעור 9, BM25 ו-5 chunks בפרומפט.</li>
<li><b>best:</b> הצנרת של שיעור 12, hybrid עם שכתוב שאילתה וסינון גרסאות.</li>
<li><b>chunker שבור:</b> ה-baseline עם חלונות קבועים של 100 טוקנים בלי חפיפה.</li>
</ol>
<p>שים לב איך המשפך של best מאבד פחות שאלות בשלבי האחזור, ואיך חלק מהשאלות האלה נופלות עכשיו בשלב מאוחר יותר. ב-chunker השבור מופיע פתאום שער שלא איבד כלום קודם.</p>`,
    videos: [
      {
        title: "Ragas: List of available metrics",
        who: "Ragas (docs)",
        part: "דף הרשימה, ואחר כך שלושה דפים: Faithfulness, Context Precision ו-Context Recall",
        minutes: 25,
        url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/",
        required: true,
        kind: "תיעוד",
        why: "הספרייה הנפוצה ביותר למדדי RAG, עם הנוסחאות המדויקות. Faithfulness: טענות נתמכות חלקי כל הטענות. Context Precision: ממוצע של precision@k במקומות הרלוונטיים. Context Recall: טענות הייחוס שנתמכות בהקשר. שים לב שבגרסה 0.4 יש API חדש (ragas.metrics.collections), וה-API הישן מסומן להסרה בגרסה 1.0. בשיעור תממש את אותן הגדרות בעצמך, מעל ציטוטי הזהב של Acme.",
      },
      {
        title: "RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation",
        who: "Ru et al., NeurIPS 2024 (Datasets and Benchmarks)",
        part: "סעיף 3: המדדים (claim recall, context utilization, noise sensitivity, hallucination, self-knowledge)",
        minutes: 30,
        url: "https://arxiv.org/abs/2408.08067",
        required: true,
        kind: "מאמר",
        why: "המאמר שהכי קרוב לרעיון של השיעור: הוא מפרק כל תשובה לטענות, בודק כל טענה מול האמת ומול כל chunk, ומחלק את הכשלים בין ה-retriever לבין ה-generator. ממנו לקוחות ההגדרות של context utilization (כמה מהמידע שהגיע לפרומפט באמת נכנס לתשובה), ושל ההבחנה בין hallucination ל-self-knowledge.",
      },
      {
        title: "Deeper insights into retrieval augmented generation: The role of sufficient context",
        who: "Google Research blog (מאי 2025), על המאמר של Joren et al., ICLR 2025",
        part: "כל הפוסט",
        minutes: 12,
        url: "https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/",
        required: true,
        kind: "מאמר",
        why: "מבחין בין \"ההקשר לא מספיק\" לבין \"המודל לא השתמש בהקשר\", וזו בדיוק ההבחנה בין שלבי האחזור לשלבי היצירה בטקסונומיה. המספרים שלהם: ה-autorater מסכים עם תוויות של אדם ב-93% לפחות מהמקרים. ב-Gemma, שיעור התשובות השגויות עלה מ-10.2% בלי הקשר ל-66.1% עם הקשר לא מספיק. selective generation שיפר את הדיוק של התשובות שניתנו בעד 10%.",
      },
      {
        title: "Building and Evaluating Advanced RAG",
        who: "DeepLearning.AI, עם Jerry Liu (LlamaIndex) ו-Anupam Datta (Snowflake)",
        part: "השיעור על ה-RAG triad: context relevance, groundedness, answer relevance",
        minutes: 30,
        url: "https://www.deeplearning.ai/short-courses/building-evaluating-advanced-rag/",
        required: false,
        kind: "קורס",
        why: "קורס קצר וחינמי (כשעתיים בסך הכול) שמציג את שלושת המדדים הבסיסיים של RAG עם שופט LLM. הוא טוב כרקע מוחשי. הוא משתמש ב-TruLens, ולא בכלים של הקורס, ולכן מספיק השיעור על ה-triad.",
      },
      {
        title: "Why Your RAG System Is Broken, and How to Fix It (TWIML #709)",
        who: "Jason Liu בפודקאסט TWIML AI",
        part: "החלקים על אבחון בעיות ועל מדדים לפי שלב",
        minutes: 50,
        url: "https://twimlai.com/podcast/twimlai/why-your-rag-pipeline-is-broken-and-how-to-fix-it",
        required: false,
        kind: "וידאו",
        why: "יועץ שעובד על מערכות RAG בחברות מסביר למה מתחילים ממדדי אחזור פשוטים על שאלות אמיתיות, ולא ממדד כללי אחד, ואיך מפצלים כשלים לקבוצות לפני שמתקנים. יש גרסת וידאו ב-YouTube (קישור מהעמוד).",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "\"36 מתוך 79\" לא אומר מה לתקן",
      html: `<p class="big">הרצת את ה-RAG של שיעור 9 על 79 שאלות הזהב של Acme, ו-36 עברו. זה מספר שימושי לדוח, אבל הוא לא עוזר לשפר את המערכת. השאלה המעשית היא לא "כמה נכשלו", אלא "איפה כל אחת נכשלה, ומה יתקן אותה".</p>
<p>תשובת RAG עוברת שרשרת של שלבים, וכל אחד מהם יכול לאבד את התשובה. אם המסמך הנכון בכלל לא נקלט, שום reranker לא יעזור. אם הציטוט המדויק נחתך בין שני chunks, המודל יקבל חצי מהמידע ויכול להשלים את החצי השני מהדמיון. אם המסמך אוחזר אבל במקום התשיעי, ו-k הוא 5, הוא לא יגיע לפרומפט. ואם הוא הגיע לפרומפט, המודל עדיין יכול לסרב, לבחור בגרסה המיושנת, להתעלם ממנו, או להוסיף משפט שלא כתוב בשום מקום.</p>
<p>לכל אחד מהכשלים האלה יש <b>תיקון אחר</b>, ולפעמים התיקון של אחד פוגע באחר. כשמגדילים את k כדי שמסמכים לא ייחתכו, הפרומפט נעשה ארוך יותר, ומידע שנמצא באמצעו נוטה ללכת לאיבוד. כשמוסיפים תרגום שאילתה כדי למצוא מסמכים בעברית, מגיעים לפרומפט יותר מסמכים לא רלוונטיים. בלי אבחון לפי שלב, כל שינוי הוא הימור.</p>
<p>הנה מה שקרה במעבדה כשהשווינו את ה-baseline של שיעור 9 לצנרת הטובה ביותר של שיעור 12. התשובות התקבלו מ-answerer חילוצי, כלומר במסלול הלא מקוון:</p>
<ul>
<li><b>ה-baseline:</b> 36 שאלות עברו.</li>
<li><b>הצנרת של שיעור 12:</b> 42 עברו, שיפור של 6.</li>
<li><b>מה הסתתר מאחורי ה-6:</b> 9 שאלות תוקנו, ו-3 שעבדו קודם נשברו. כשלי הגרסה המיושנת ירדו מ-6 ל-0, וכשלי "לא אוחזר" מ-3 ל-0. מנגד, כשלי "אוחזר ונחתך" עלו מ-7 ל-10, וכשלי סירוב שגוי מ-6 ל-8.</li>
</ul>
<p>המספר הכולל עלה, אבל הכשלים לא נעלמו. הם זזו לשלבים אחרים.</p>
<p>בשיעור הזה תבנה את הכלי שרואה את זה: טקסונומיה של כשלים לפי שלב, נוהל שמסווג כל שאלה שנכשלה לשלב אחד, מדדים לכל שלב, בדיקת groundedness ברמת טענה, ולולאת תיקון שמודדת כל שינוי בהשוואה מזווגת.</p>
<div class="callout"><b>הערת כנות:</b> המספרים בשקופיות נמדדו בסביבת הקורס, ב<b>מסלול הלא מקוון</b>: answerer חילוצי שמעתיק משפטים ולא יכול להמציא עובדה או לשלב שני מקורות, שופט לקסיקלי, embedder מזויף ושכתובים שנכתבו ביד. מספרי האחזור (מה הגיע למועמדים ומה לפרומפט) לא תלויים ברכיבים האלה, ולכן הם אמיתיים. את מספרי היצירה של Haiku תמדוד אצלך בתרגיל 7, ואם הם יסתרו משהו כאן, המדידה שלך קובעת.</div>`,
    },
    {
      kicker: "המודל",
      title: "התשובה כשרשרת של שלבים",
      html: `<p>כדי לאבחן, צריך קודם מודל של מה קורה לשאלה. הנה הצנרת של ragkit, עם מה שכל שלב יכול לאבד. השמות בסוגריים הם התוויות של הטקסונומיה, שנפרט בשלוש השקופיות הבאות.</p>
<div class="example"><b>הצנרת, ומה נשמר מכל שלב ב-trace</b><pre dir="ltr">corpus          is the source document indexed at all?          (missing_from_corpus)
 -> extraction  is the evidence text in the extracted document?  (extraction_lost)
 -> chunking    is the evidence inside ONE chunk?                (chunk_split)
 -> retrieval   is every source doc among the top-50 candidates? (not_retrieved)
 -> top-k cut   is every source doc in the 5 chunks of the prompt? (ranked_low)
 -> generation  current version? answered? stated the facts? only supported claims?
                (stale_version, false_refusal, lost_in_middle, ignored_context, hallucination)
 -> citation    do the [n] point to the sources?                 (wrong_citation)
unanswerable question: did it refuse?                            (failed_to_refuse)</pre></div>
<p><b>למה מבחינים בין מועמדים לפרומפט.</b> זה ההבדל החשוב ביותר באבחון האחזור. מועמדים הם התוצאות של חיפוש עמוק, למשל 50 הראשונות. הפרומפט הוא רק k הראשונות מתוכן. אם המסמך הנכון לא נמצא בין 50 המועמדים, הבעיה היא ב-retriever עצמו, והתיקון הוא hybrid, שכתוב או embeddings טובים יותר. אם הוא נמצא בין המועמדים ונחתך, ה-retriever מצא אותו אבל דירג אותו נמוך, והתיקון הוא reranker, גיוון או k גדול יותר. שני כשלים שנראים זהים בתשובה ("לא מצא"), עם תיקונים שונים לגמרי.</p>
<p><b>למה מבחינים בין שלבי היצירה.</b> כשהראיה נמצאת בפרומפט והתשובה שגויה, הבעיה אצל המודל. אבל "אצל המודל" זה עדיין חמישה דברים שונים. הוא יכול לבחור בגרסה המיושנת, לסרב, לפספס מידע באמצע הקשר ארוך, פשוט לא לכתוב את העובדה, או לכתוב משהו מהידע שלו במקום מהמקורות. התיקון לסירוב שגוי הוא הוראה בפרומפט על מה נחשב "נמצא" (טבלה, שפה אחרת). התיקון ל-hallucination הוא בדיקת groundedness לפני שליחה. ולגרסה המיושנת יש בכלל תיקון באחזור, סינון גרסאות משיעור 12.</p>
<p><b>שלב הציטוט</b> נבדק בנפרד, כי תשובה יכולה להיות נכונה ונאמנה למקורות, ועדיין להצביע על המקור הלא נכון. בעוזר פנימי, ציטוט שגוי הוא כשל אמיתי: העובד לוחץ על המקור כדי לוודא, ומוצא מסמך אחר.</p>
<div class="callout"><b>הרעיון המרכזי:</b> כל שאלה שנכשלה מקבלת <b>שלב אחד</b>, שורש הבעיה, ולצידו רשימת דגלים של בעיות נוספות שנראו. כך אפשר לספור: "13 כשלים בשלב X, 7 בשלב Y", ולתקן קודם את מה שהכי משתלם.</div>`,
    },
    {
      kicker: "טקסונומיה 1",
      title: "כשלי ingestion: הראיה בכלל לא זמינה",
      html: `<p>שלושת הכשלים הראשונים קורים לפני שמישהו שאל שאלה. הם בלתי נראים בתשובה: המודל פשוט לא מקבל את המידע, ועונה בלעדיו. הדרך היחידה לגלות אותם היא לבדוק את הקורפוס מול ציטוטי הזהב, וזו בדיוק הפונקציה <code>quote_coverage</code> משיעור 9. לכל ציטוט זהב היא מחזירה אחד מארבעה מצבים: <code>covered</code> (הציטוט נמצא בשלמותו בתוך chunk אחד), <code>split</code> (הוא נמצא במסמך, אבל בשום chunk לבדו), <code>missing</code> (הוא לא נמצא בטקסט שחולץ), ו-<code>no_doc</code> (המסמך בכלל לא בקורפוס).</p>
<h4>missing_from_corpus: המסמך לא נקלט</h4>
<p>המסמך קיים בארגון, אבל לא באינדקס. הסיבות הנפוצות: ה-connector לא מסנכרן את התיקייה הזו, למשתמש של ה-ingestion אין הרשאה, הפורמט לא נתמך, או שהמסמך נוסף אחרי הסנכרון האחרון. ב-Acme יש דוגמה מכוונת: q075 שואלת על התוספת הגרמנית למדיניות החופשה, שמוזכרת במסמכים אבל לא נמצאת בקורפוס. כאן התשובה הנכונה היא סירוב, ולכן זו שאלה בלי תשובה. אבל אם שאלת זהב מצביעה על מסמך שלא נקלט, הכשל הוא <code>missing_from_corpus</code>.</p>
<h4>extraction_lost: החילוץ איבד את הטקסט</h4>
<p>המסמך באינדקס, אבל הטקסט החשוב לא שרד את החילוץ. זה קורה בעיקר בטבלאות בתוך PDF, בכותרות עליונות ותחתונות שמתערבבות בטקסט, בעמודות, ובדפי HTML שבהם ה-extractor זרק את התוכן יחד עם התפריט. ב-Acme, האש"ל של 2026 נמצא בטבלה בתוך PDF (<code>fin-travel-2026</code>). ב-trace T1 של המעבדה, loader חדש איבד את השורות של הטבלה ואת העמוד השני. בפרומפט נשאר המשפט "according to this table:", בלי טבלה אחריו, והמודל ענה מהגרסה של 2025: 75 דולר במקום 85. הסימפטום נראה כמו "גרסה מיושנת", אבל שורש הבעיה הוא החילוץ.</p>
<h4>chunk_split: הראיה נחתכה בין שני chunks</h4>
<p>הטקסט נמצא במסמך, אבל אף chunk לא מכיל את כולו. כל chunk מקבל ציון אחזור משלו, ולכן ייתכן שרק החצי הראשון יאוחזר. וגם אם שניהם אוחזרו, הם לא בהכרח צמודים בפרומפט. במעבדה, עם <code>fixed:100:0</code> (חלונות של 100 טוקנים בלי חפיפה), 18 מתוך 102 ציטוטי הזהב נחתכו, ו-8 שאלות נכשלו בגלל זה. עם ה-chunker של ה-baseline (<code>heading:400:40:150</code>), אף ציטוט לא נחתך. ב-trace T2, ההגדרה של Quiet Hours במילון נחתכה בדיוק אחרי המילה "until". המודל השלים בעצמו "until midnight", והשופט סימן את הטענה הזו כלא נתמכת. הסימפטום הוא hallucination, ושורש הבעיה הוא ה-chunker.</p>
<div class="callout"><b>למה זה בא ראשון בנוהל:</b> אם הראיה לא זמינה, כל מה שקורה אחר כך הוא תוצאה. מודל שלא קיבל את הטבלה יענה מהגרסה הישנה. מודל שקיבל חצי משפט ישלים את החצי השני. אם מתקנים את הסימפטום (סינון גרסאות, או בדיקת groundedness), הכשל יופיע בצורה אחרת.</div>`,
    },
    {
      kicker: "טקסונומיה 2",
      title: "כשלי אחזור: הראיה קיימת ולא הגיעה, או שהגיעה הגרסה הלא נכונה",
      html: `<p>כאן הראיה קיימת בתוך chunk שלם, והשאלה היא אם ה-retriever הביא אותה לפרומפט. כדי להבחין בין שני הכשלים הראשונים, ה-trace שומר שתי רשימות: <b>המועמדים</b> (חיפוש עמוק של 50) ו<b>הפרומפט</b> (k הראשונים מתוכם). במעבדה זה חיפוש אחד: 50 התוצאות הן המועמדים, ו-5 הראשונות הן הפרומפט. לכן שתי הרשימות עקביות זו עם זו.</p>
<h4>not_retrieved: לא נמצא בין המועמדים</h4>
<p>מסמך מקור אחד לפחות לא מופיע ב-50 התוצאות. ב-baseline זה קרה ב-3 שאלות: q039 (שאלה באנגלית, והמקור בעברית), q047 ו-q068 (שאלות שצריכות מסמך בכל שפה). BM25 לא יכול למצוא מסמך שאין לו אף מילה משותפת עם השאלה. בצנרת של שיעור 12, עם תרגום השאילתה, שלושתן הגיעו למועמדים, ו-not_retrieved ירד ל-0. בשאלת multi-hop, מספיק שמסמך אחד מתוך שניים חסר כדי שזה ייחשב not_retrieved.</p>
<h4>ranked_low: נמצא, ונחתך לפני הפרומפט</h4>
<p>המסמך בין המועמדים, אבל לא ב-k הראשונים. ב-baseline זה קרה ב-7 שאלות, ובצנרת של שיעור 12 ב-10, ו-7 מהן multi-hop. הסיבה ראויה לתשומת לב. ב-q040 הפרומפט של ה-baseline מכיל ארבעה chunks של ה-postmortem ו-chunk אחד של תהליך ה-deploy. קטלוג השירותים, המסמך השני שהשאלה צריכה, הוא המסמך הרביעי ברשימת המועמדים, אבל ה-chunks שלו מדורגים אחרי ה-chunks של ה-postmortem. מסמך אחד "תפס" את כל המקומות. זה כשל מוכר בשאלות multi-hop, והתיקון שלו הוא לא רק reranker אלא גם <b>גיוון</b>: לכל היותר 2 chunks לכל מסמך, כדי להשאיר מקום למסמך השני.</p>
<h4>stale_version: הגרסה המיושנת</h4>
<p>שתי הגרסאות הגיעו לפרומפט, והתשובה ציטטה את הישנה. ב-baseline זה קרה ב-6 שאלות. למשל q010, חופשה להורה שאינו יולד: המדיניות של 2025 נותנת 5 ימים, ושל 2026 נותנת 15. ב-q003, התשובה ציטטה את מדיניות הסיסמאות של 2024 ("Passwords must be changed every 90 days"). שמנו את הכשל הזה בקבוצת האחזור, כי התיקון היעיל שלו הוא באחזור: <code>VersionAwareRetriever</code> משיעור 12, שמשמיט גרסה ישנה כשהחדשה נמצאת גם היא ברשימה. במעבדה התיקון הזה הוריד את stale_version מ-6 ל-0, ו-6 שאלות עברו. המבחן לזיהוי הוא דטרמיניסטי: האם אחד המסמכים שצוטטו מסומן <code>stale:</code> בשאלת הזהב?</p>
<div class="example"><b>q040 ב-baseline: המועמדים מול הפרומפט (מזהי מסמכים, * = מקור זהב)</b><pre dir="ltr">prompt (k=5):  1 eng-pm-2026-08-api*  2 eng-pm-2026-08-api*  3 eng-pm-2026-08-api*
               4 eng-pm-2026-08-api*  5 eng-deploy-process
candidates:    1 eng-pm-2026-08-api*  2 eng-deploy-process  3 eng-architecture
  (by doc)     4 eng-service-catalog*  5 eng-leads-sync-2026-05  ...
diagnosis:     ranked_low  (retrieved but cut before the prompt: eng-service-catalog)</pre></div>`,
    },
    {
      kicker: "טקסונומיה 3",
      title: "כשלי יצירה: הראיה בפרומפט, והתשובה עדיין שגויה",
      html: `<p>אם הראיה הגיעה לפרומפט, הגרסה הנכונה, והתשובה עדיין נכשלה, הבעיה בשלב היצירה. מפרקים אותה לחמישה כשלים, ועוד כשל אחד לשאלות שאין להן תשובה.</p>
<h4>false_refusal: סירב, למרות שהתשובה הייתה שם</h4>
<p>המודל כתב "not in the documents", כשהראיה בפרומפט. זה קורה כשהראיה בשפה אחרת, בטבלה, או מנוסחת אחרת מהשאלה. ב-trace T4, המסמך העברי עם תאריך היעד של הדרכת האבטחה היה במקום השני, והמודל סירב לשאלה באנגלית. חשוב להבחין: אם הראיה <b>לא</b> בפרומפט, סירוב הוא ההתנהגות הנכונה, והכשל הוא באחזור. לכן הנוהל בודק את האחזור לפני שהוא מאשים את המודל.</p>
<h4>lost_in_middle: הראיה באמצע הקשר ארוך</h4>
<p>Liu ועמיתיו הראו ב-2023 (במאמר "Lost in the Middle") שמודלים משתמשים הכי טוב במידע שבתחילת ההקשר ובסופו, ופחות במידע שבאמצע. גרף הדיוק לפי המיקום נראה כמו האות U. מודלים חדשים טובים יותר בזה, אבל התופעה לא נעלמה לגמרי, במיוחד כשההקשר ארוך והמידע בטבלה. בנוהל שלנו, הכשל מוגדר רק כשההקשר ארוך (4,000 טוקנים או יותר, כ-20 chunks), כשכל הראיות נמצאות במקומות שאינם הראשון או האחרון, וכשהעובדות חסרות בתשובה. עם 5 chunks ופרומפט של כ-1,000 טוקנים, זה כמעט לא קורה, ולכן במסלול הרגיל של המעבדה הספירה היא 0. ב-trace T5 מישהו העלה את k ל-20 כדי לתקן כשלי ranked_low. שורת מגבלת ה-API הייתה ב-chunk מספר 8, והתשובה מנתה פרטים אחרים מאותה טבלה ואמרה שהמגבלה לא מופיעה.</p>
<h4>ignored_context: פשוט לא כתב את העובדה</h4>
<p>הראיה בפרומפט, ההקשר קצר, המודל לא סירב, אבל העובדות חסרות. זו קטגוריית "השארית" של היצירה. במסלול הלא מקוון היא הגדולה ביותר (13 ב-baseline), כי ה-answerer החילוצי בוחר משפט לפי מילים משותפות. הוא לא יודע לשלב שני משפטים, וגם לא לקרוא שורה בטבלה. עם Haiku המספר הזה צפוי לרדת הרבה, וזה בדיוק מה שתבדוק בתרגיל 7.</p>
<h4>hallucination: ענה מהידע של עצמו</h4>
<p>יש בתשובה טענות שלא נתמכות בשום מקור, למשל "Outages of this kind usually take about two hours". המודל השלים מהידע הכללי שלו (parametric knowledge), ולפעמים גם צירף לזה ציטוט. הכשל מזוהה רק עם שופט groundedness, כי השוואה לעובדות הזהב לא תתפוס טענה שנוספה בנוסף לעובדות הנכונות. ה-answerer החילוצי מעתיק משפטים, ולכן אצלו המספר הוא 0. זה נכון לגבי ה-answerer, לא לגבי Claude.</p>
<h4>wrong_citation ו-failed_to_refuse</h4>
<p><b>wrong_citation:</b> התוכן נכון ונתמך, אבל הציטוטים לא מצביעים על מסמך מקור, או שיש <code>[n]</code> שמצביע על מקור שלא נשלח. <b>failed_to_refuse:</b> לשאלה אין תשובה בקורפוס, והמערכת ענתה בכל זאת. ב-baseline זה קרה ב-7 מתוך 10 השאלות כאלה. ברוב המקרים היה מסמך "near-miss", למשל ARR של 2024 ו-2025 כשהשאלה על 2023, או חניה בחיפה שמתוארת כחינמית בלי מספר מקומות. מחקר ה-sufficient context של Google מצא את אותה תופעה במודלים גדולים: כשההקשר לא מספיק, הם נוטים לענות במקום לסרב.</p>`,
    },
    {
      kicker: "הנוהל",
      title: "נוהל האבחון: השלב הראשון שנכשל",
      html: `<p>עכשיו אפשר לכתוב את הנוהל. הוא שואל שאלות כן/לא לפי סדר הצנרת, ועוצר בתשובת ה"לא" הראשונה. זה כל מה שהפונקציה <code>classify</code> ב-<code>ragkit/diagnose.py</code> עושה, וזה מה שתממש בתרגיל 1.</p>
<ol class="ladder">
<li><b>האם יש לשאלה תשובה?</b><span>אם אין (<code>source_ids</code> ריק), יש רק שתי תוצאות: סירוב הוא <code>ok</code>, ותשובה היא <code>failed_to_refuse</code>.</span></li>
<li><b>האם התשובה עברה?</b><span>היא נכשלת אם המודל סירב, אם כיסוי העובדות מתחת ל-0.5, אם צוטט מסמך מיושן, אם השופט מצא טענה לא נתמכת, אם לא צוטט אף מסמך מקור, או אם יש <code>[n]</code> מומצא. אם אף אחד מאלה לא קרה: <code>ok</code>.</span></li>
<li><b>האם הראיה זמינה?</b><span>אם יש ציטוט <code>no_doc</code>, הכשל הוא <code>missing_from_corpus</code>. אם יש <code>missing</code>, הכשל הוא <code>extraction_lost</code>. אם יש <code>split</code>, הכשל הוא <code>chunk_split</code>.</span></li>
<li><b>האם כל מסמכי המקור בין המועמדים?</b><span>אם לא: <code>not_retrieved</code>.</span></li>
<li><b>האם כולם בפרומפט?</b><span>אם לא: <code>ranked_low</code>.</span></li>
<li><b>האם צוטט מסמך מיושן?</b><span>אם כן: <code>stale_version</code>.</span></li>
<li><b>האם המודל סירב?</b><span>אם כן: <code>false_refusal</code>.</span></li>
<li><b>האם העובדות חסרות?</b><span>אם יש גם טענות לא נתמכות: <code>hallucination</code>. אם הראיה רק באמצע הקשר ארוך: <code>lost_in_middle</code>. אחרת: <code>ignored_context</code>.</span></li>
<li><b>האם יש טענות לא נתמכות?</b><span>אם כן: <code>hallucination</code>. אם לא, נשארו רק הציטוטים: <code>wrong_citation</code>.</span></li>
</ol>
<p><b>למה השלב הראשון ולא האחרון.</b> כשל מוקדם גורם לכשלים מאוחרים. ב-c17, אחד המקרים הבנויים במעבדה, המסמך הנכון לא אוחזר, ורק הגרסה הישנה הגיעה לפרומפט. המודל ציטט אותה, וזה בדיוק מה שהוא היה צריך לעשות לפי מה שקיבל. אם הנוהל היה מסווג את זה כ-stale_version, היית מוסיף סינון גרסאות. אבל סינון במצב "retrieved" משמיט את הישנה רק כשהחדשה נמצאת ברשימה, ולכן הוא לא היה משנה כלום. התיקון הנכון הוא באחזור.</p>
<p><b>דגלים.</b> הנוהל לא זורק את שאר הבעיות. <code>Diagnosis.flags</code> שומר את כל מה שנכשל בשלב 2, ו-<code>Diagnosis.path</code> שומר את השאלות שנשאלו ואת התשובות עליהן. כך, אחרי שמתקנים את שורש הבעיה ומריצים שוב, רואים אם הבעיה הבאה הייתה תוצאה שנעלמה, או כשל עצמאי שנשאר.</p>
<div class="example"><b>מסלול ההחלטה של T1 (האש"ל, PDF ששבר את הטבלה)</b><pre dir="ltr">T1 q002 [version_conflict] -> extraction_lost
   . outcome passed? no (stale_cited)
   . a golden quote is not in the extracted document text
   flags: stale_cited
   fix (lesson 9): Change the loader for that format (PDF mode, HTML extractor,
        table handling) and re-ingest only the changed documents.</pre></div>
<div class="callout"><b>גבולות הנוהל:</b> הוא כלי לספירה ולמיון, לא אורקל. הספים (0.5 לעובדות, 4,000 טוקנים) הם החלטות. כיסוי העובדות הוא לקסיקלי, ולכן מפספס פרפרזה. השופט יכול לטעות. כשהנוהל מסווג משהו בצורה מוזרה, פותחים את ה-trace ומחליטים. תרגיל 5 מתרגל בדיוק את זה.</div>`,
    },
    {
      kicker: "trace",
      title: "מה צריך להקליט לכל שאלה",
      html: `<p>כדי לאבחן אחרי מעשה, צריך שכל הרצה תשאיר אחריה trace עם כל השדות שהנוהל שואל עליהם. הפונקציה <code>trace_question</code> מקליטה אותו כ-dict פשוט, ו-<code>run_diagnosis.py</code> שומר אותו כשורת JSON. כך אפשר לסווג מחדש, לשנות ספים או לשפר את המסווג בלי להריץ שוב את המודל ובלי לשלם שוב.</p>
<div class="example"><b>trace אחד (מקוצר), כפי שנשמר ב-results/traces_*.jsonl</b><pre dir="ltr">{"qid": "q040", "qtype": "multi_hop", "question": "Which team owns the service ...",
 "source_ids": ["eng-pm-2026-08-api", "eng-service-catalog"], "stale_ids": [],
 "quotes": ["A configuration change to auth-service reduced ...", "| auth-service | Identity | ..."],
 "quote_status": ["covered", "covered"],          # from quote_coverage (lesson 9)
 "candidates": ["eng-pm-2026-08-api", "eng-pm-2026-08-api", ..., "eng-service-catalog", ...],  # top 50
 "context": [{"n": 1, "chunk": "eng-pm-2026-08-api#0", "doc": "...", "text": "..."}, ...],      # top 5
 "context_tokens": 1202, "quote_locations": [[1], []],
 "answer": "...", "citations": [5], "cited": ["eng-deploy-process"], "invalid_citations": 0,
 "abstained": false, "fact_coverage": 0.25,
 "groundedness": {"label": "grounded", "score": 1.0, "claims": [...]}}</pre></div>
<p><b>שלושה פרטים שקל לפספס:</b></p>
<ul>
<li><b>חיפוש עמוק אחד, ולא שניים.</b> אם מחפשים פעם אחת עם k=50 ופעם עם k=5, retriever שהסדר שלו תלוי ב-k (למשל עם fetch_k שגדל עם k) עלול להחזיר פרומפט שאינו התחלה של רשימת המועמדים. אז ranked_low מקבל משמעות מבולבלת. ב-ragkit מחפשים פעם אחת, והפרומפט הוא 5 התוצאות הראשונות.</li>
<li><b>טקסט ה-chunk ולא רק המזהה.</b> בלי הטקסט אי אפשר לחשב <code>quote_locations</code>, כלומר באיזה מקום בפרומפט נמצא כל ציטוט זהב. כל מדדי ההקשר והציטוט נשענים עליו. בייצור, זה גם מה שמאפשר לשחזר מה המודל ראה, גם אחרי שהמסמך השתנה.</li>
<li><b>מה מגיע מנתוני הזהב ומה מהצנרת.</b> <code>source_ids</code>, הציטוטים ו-<code>stale_ids</code> מגיעים משאלת הזהב. כל השאר מגיע מההרצה. לשאלות של משתמשים אמיתיים, שאין להן זהב, אפשר להריץ רק את החלק שלא תלוי בזהב: groundedness, סירוב, ואורך ההקשר. את שאר השאלות שואלים אחרי שמישהו סימן תשובה כשגויה והוסיף אותה לסט הזהב.</li>
</ul>
<p><b>הקשר לשיעור 22.</b> ב-observability, כל בקשה מייצרת span של אחזור (עם מזהי המסמכים והציונים) ו-span של קריאת LLM (עם הפרומפט והתשובה). אלה בדיוק השדות כאן. בשיעור 22 תלמד להקליט אותם עם OpenTelemetry, לפי ה-GenAI semantic conventions. כאן מספיק dict, כי המטרה היא להבין <b>מה</b> צריך להקליט ולמה.</p>
<div class="callout"><b>כלל אצבע:</b> אם הנוהל שלך שואל שאלה שה-trace לא יכול לענות עליה, ה-trace חסר. התשובה היא להוסיף שדה, ולא לנחש.</div>`,
    },
    {
      kicker: "מדדים 1",
      title: "מדדי הקשר: context recall ו-context precision",
      html: `<p>המדדים של שיעורים 10 ו-12, recall@k ו-MRR, נמדדו ברמת <b>מסמך</b>: האם מסמך מקור נמצא ב-k הראשונים. זה לא מספיק לאבחון, כי מסמך יכול להיות בפרומפט דרך chunk שלא מכיל את התשובה. ב-q040, ה-postmortem נמצא בפרומפט ארבע פעמים, אבל רק chunk אחד מתוך הארבעה מכיל את הציטוט על auth-service. לכן מודדים כאן ברמת <b>ראיה</b>, לפי ציטוטי הזהב.</p>
<h4>context recall</h4>
<div class="example"><b>הגדרה</b><pre dir="ltr">context_recall = |{golden quotes found whole in some prompt chunk}| / |golden quotes|</pre></div>
<p>ההשוואה נעשית אחרי נרמול: רווחים מכווצים ואותיות קטנות. זו הגרסה הדטרמיניסטית של context recall ב-Ragas. שם מפרקים את תשובת הייחוס לטענות, ושואלים שופט LLM כמה מהן נתמכות בהקשר. אצלנו יש ציטוט מדויק לכל מקור, ולכן אפשר לבדוק בלי שופט, בחינם, ובאופן שחוזר על עצמו. המחיר: ציטוט שמופיע בהקשר מנוסח קצת אחרת (למשל אחרי חילוץ PDF ששינה רווח בתוך טבלה) ייספר כחסר. בשאלות שהזהב שלהן נכתב מתוך הטקסט המחולץ, זה כמעט לא קורה.</p>
<h4>context precision, בשתי גרסאות</h4>
<p>chunk נחשב רלוונטי אם הוא מכיל לפחות ציטוט זהב אחד. מזה אפשר לחשב שני מדדים שונים מאוד:</p>
<div class="example"><b>שתי הגדרות</b><pre dir="ltr">simple_precision  = relevant chunks / k                         (RAGChecker)

context_precision = sum over relevant positions k of precision@k
                    ------------------------------------------   (Ragas; average precision)
                         number of relevant chunks in the list
precision@k = relevant chunks among the first k / k

example: relevance = [True, False, True, False, False]
simple_precision  = 2/5 = 0.40
context_precision = (1/1 + 2/3) / 2 = 0.83</pre></div>
<p>הגרסה של Ragas <b>מודעת לדירוג</b>: היא מתגמלת מאוד רלוונטי במקום הראשון, ובכלל לא מענישה על chunks לא רלוונטיים <b>אחרי</b> הרלוונטי האחרון. לכן ב-q040 היא נותנת 1.0, כי ה-chunk הרלוונטי היחיד ראשון, למרות ש-4 מתוך 5 chunks לא רלוונטיים. הגרסה הפשוטה נותנת 0.2. שתיהן נכונות, אבל הן עונות על שאלות שונות. הראשונה בודקת אם הדירוג טוב, והשנייה בודקת כמה רעש נכנס לפרומפט. רעש עולה כסף, מאט את התשובה, ויכול לבלבל את המודל (RAGChecker קורא לזה noise sensitivity).</p>
<h4>מה נמדד במעבדה</h4>
<p>ב-baseline, על 69 השאלות: context recall 0.829 ו-context precision 0.765. ב-multi_hop, context recall צונח ל-0.515. כמעט בכל שאלה כזו רק אחד משני הציטוטים מגיע לפרומפט, וזה מתאים בדיוק לכשלי ranked_low שראינו. ב-version_conflict, context precision נמוך (0.508), כי ה-chunk של הגרסה הישנה מקבל ציון גבוה כמו של החדשה, ולפעמים גבוה יותר.</p>
<div class="callout"><b>זהירות עם ממוצעים:</b> כל מדד מוגדר רק לשאלות שהוא חל עליהן. לשאלה בלי ציטוטים, context recall הוא None ולא 0, והוא לא נכנס לממוצע. אחרת, 10 השאלות שאין להן תשובה היו מורידות את הממוצע בלי שום קשר לאחזור.</div>`,
    },
    {
      kicker: "מדדים 2",
      title: "groundedness, answer relevance וציטוטים",
      html: `<p>שלושת המדדים האלה בודקים את התשובה עצמה. כל אחד מהם בודק משהו שאחרים מפספסים.</p>
<h4>groundedness (נקרא גם faithfulness)</h4>
<div class="example"><b>הגדרה</b><pre dir="ltr">faithfulness = |claims in the answer supported by the retrieved context| / |claims in the answer|
               (no claims, e.g. a refusal: undefined; the label is "grounded")</pre></div>
<p>המדד שואל רק דבר אחד: האם כל מה שהתשובה אומרת כתוב בהקשר שנשלח? הוא <b>לא</b> בודק אם התשובה נכונה. תשובה שחוזרת בנאמנות על מדיניות 2025 המיושנת היא grounded לגמרי. זו דוגמה e3 במעבדה. ולהפך, תשובה נכונה שהמודל כתב מהידע הכללי שלו היא לא grounded. היתרון הגדול שלו: <b>הוא לא צריך תשובת זהב</b>. אפשר להריץ אותו על כל תשובה בייצור, וזה מה שהופך אותו לניטור החשוב ביותר של מערכת RAG חיה.</p>
<h4>answer relevance</h4>
<p>האם התשובה עונה על השאלה שנשאלה? תשובה יכולה להיות grounded ונכונה עובדתית, ולענות על שאלה אחרת. ב-Ragas המדד (<code>AnswerRelevancy</code> ב-API החדש, <code>ResponseRelevancy</code> ב-API הישן) מחושב כך: מבקשים מ-LLM לייצר N שאלות (ברירת המחדל 3) שהתשובה עונה עליהן, ומחשבים את ממוצע ה-cosine בין ה-embeddings שלהן לבין השאלה המקורית.</p>
<div class="example"><b>answer relevance לפי Ragas</b><pre dir="ltr">answer_relevance = (1/N) * sum_i cosine(E(q_i), E(question))
                   q_i = a question generated from the answer (N = 3 by default)</pre></div>
<p>במעבדה לא מממשים אותו, משתי סיבות. הראשונה: אצלנו הכשל הזה מתבטא ככיסוי עובדות נמוך (העובדות של השאלה הזו חסרות), והנוהל תופס אותו. השנייה: עם embedder מזויף המדד חסר משמעות. כדאי להכיר אותו, כי בייצור, בלי זהב, הוא אחד משלושת המדדים של ה-"RAG triad": context relevance, groundedness ו-answer relevance.</p>
<h4>citation precision ו-citation recall</h4>
<p>ALCE (Gao ועמיתיו, 2023) הגדירו ציטוטים ברמת משפט, עם מודל NLI. citation recall בודק אם כל משפט נתמך במלואו על ידי המקורות שהוא מצטט. citation precision בודק אם כל ציטוט באמת נחוץ ותומך. אצלנו יש ציטוטי זהב, ולכן ההגדרה פשוטה ודטרמיניסטית:</p>
<div class="example"><b>ההגדרות של המעבדה</b><pre dir="ltr">supporting = prompt positions whose chunk contains a golden quote
citation_precision = |distinct cited [n] that are in supporting| / |distinct cited [n]|   (None if nothing cited)
citation_recall    = |golden quotes with at least one cited chunk containing them| / |golden quotes|

example (q040, baseline): cited [5]; quote 1 is in chunk 1, quote 2 is in no prompt chunk
citation_precision = 0/1 = 0.0      citation_recall = 0/2 = 0.0</pre></div>
<p>ב-baseline: citation precision 0.592 ו-citation recall 0.594 על כל השאלות. ב-multi_hop, citation recall הוא רק 0.182. ב-9 שאלות התשובה לא ציטטה כלום. שם precision לא מוגדר, ולכן הוא מדווח בנפרד ולא נספר כ-0 או כ-1. ממוצע שמסתיר את ההחלטה הזו מטעה.</p>
<div class="callout"><b>מה ההבדל בין citation_scores של שיעור 23 לכאן:</b> evalkit מודד ציטוטים ברמת <b>מסמך</b>: האם המסמכים שצוטטו הם מסמכי המקור. כאן מודדים ברמת <b>chunk וראיה</b>: האם ה-chunk שצוטט מכיל את הציטוט. ציטוט של ה-chunk הלא נכון מתוך המסמך הנכון עובר את הבדיקה הראשונה ונכשל בשנייה.</div>`,
    },
    {
      kicker: "כלים",
      title: "Ragas ו-RAGChecker מול מדדים משלך",
      html: `<p>יש כמה ספריות שמחשבות מדדי RAG. כדאי להכיר אותן, להבין את ההגדרות שלהן, ולהחליט מתי להשתמש בהן ומתי לכתוב מדד בעצמך.</p>
<h4>Ragas (גרסה 0.4.3 ב-PyPI, נובמבר 2026)</h4>
<p>זו הספרייה הנפוצה ביותר. דף המדדים שלה מחלק אותם לקבוצות. מדדי ה-RAG הם: Context Precision, Context Recall, Context Entities Recall, Noise Sensitivity, Response Relevancy, Faithfulness, ושני מדדים מולטימודליים. בנוסף יש מדדים של NVIDIA (Answer Accuracy, Context Relevance, Response Groundedness), מדדי השוואה לטקסט ייחוס (Factual Correctness, Semantic Similarity, BLEU, ROUGE) ומדדים כלליים מבוססי rubric.</p>
<ul>
<li><b>API חדש:</b> בגרסה 0.4, ה-API המומלץ הוא <code>ragas.metrics.collections</code>. בו המדדים נקראים <code>Faithfulness</code>, <code>ContextPrecision</code>, <code>ContextRecall</code> ו-<code>AnswerRelevancy</code>, ויש להם <code>score</code> ו-<code>ascore</code>.</li>
<li><b>API ישן:</b> הוא כולל <code>LLMContextPrecisionWithReference</code>, <code>LLMContextRecall</code>, <code>ResponseRelevancy</code>, <code>IDBasedContextRecall</code> ועוד, עם <code>single_turn_ascore(sample)</code>. התיעוד מסמן אותו להסרה בגרסה 1.0.</li>
<li><b>Faithfulness עם HHEM:</b> יש גם <code>FaithfulnesswithHHEM</code>, שבודק כל טענה עם מסווג קטן במקום עם LLM.</li>
</ul>
<h4>RAGChecker (NeurIPS 2024)</h4>
<p>RAGChecker מפרק גם את תשובת הייחוס וגם את התשובה שנוצרה לטענות, ובודק entailment של כל טענה מול כל chunk. כך הוא מחלק את האשמה בין שני הצדדים:</p>
<ul>
<li><b>ה-retriever:</b> claim recall (כמה מטענות הייחוס נמצאות ב-chunks) ו-context precision (כמה chunks רלוונטיים).</li>
<li><b>ה-generator:</b> context utilization (מהטענות שהיו בהקשר, כמה נכנסו לתשובה), noise sensitivity (טענות שגויות שהגיעו מ-chunk רלוונטי או לא רלוונטי), hallucination (טענות שגויות שלא באו משום chunk) ו-self-knowledge (טענות נכונות שלא באו משום chunk).</li>
</ul>
<p>זו בדיוק החלוקה של הטקסונומיה שלנו, רק ברמת טענה במקום ברמת שאלה.</p>
<h4>מתי מדד משלך עדיף</h4>
<ol class="ladder">
<li><b>יש לך ציטוטי זהב.</b><span>אם כל שאלת זהב מצביעה על הציטוט המדויק, context recall ו-citation recall הם בדיקת מחרוזת, בחינם ובלי שופט. Ragas יקרא ל-LLM כדי להגיע לאותו מספר, בעלות גבוהה יותר ועם רעש.</span></li>
<li><b>אתה צריך להבין כל מספר.</b><span>מדד שמחושב בתוך ספרייה, עם prompt שלא כתבת, קשה לאבחן כשהוא מוזר. במעבדה כל מדד הוא פונקציה של 5 עד 10 שורות.</span></li>
<li><b>השפה והתחום שלך.</b><span>ה-prompts של הספריות כתובים באנגלית, ולא נבדקו על עברית או על הטבלאות שלך. אם משתמשים בהם, כדאי לכייל אותם מול כמה עשרות תוויות של אדם, כמו שתעשה בשיעור 23.</span></li>
<li><b>מתי כן ספרייה.</b><span>כשאין זהב (תעבורת ייצור), כשרוצים מדד סטנדרטי להשוואה מול מאמרים, או כשצריך מדד מורכב כמו answer relevance עם embeddings. גם אז, מריצים אותו לצד המדדים הדטרמיניסטיים ולא במקומם.</span></li>
</ol>
<div class="callout"><b>החלטה של הקורס:</b> המעבדה לא תלויה ב-Ragas. היא מממשת את אותן הגדרות מעל ציטוטי הזהב, ואת groundedness עם שופט משלה, כדי שתבין כל חלק. אם תרצה להשוות, <code>uv pip install ragas</code>, ותריץ את Faithfulness שלו על אותן תשובות.</div>`,
    },
    {
      kicker: "groundedness",
      title: "groundedness ברמת טענה: לפרק ואז לבדוק",
      html: `<p>אפשר לשאול שופט "האם התשובה הזו נתמכת בהקשר?", ולקבל כן או לא. זה עובד גרוע: תשובה של שלושה משפטים, שאחד מהם מומצא, מקבלת לעיתים קרובות "כן", כי רובה נכון. הפתרון המקובל, ב-Ragas, ב-RAGChecker ובשופט של evalkit, הוא לעבוד ב<b>שני צעדים</b>. קודם מפרקים את התשובה לטענות אטומיות, ואחר כך בודקים כל טענה לבד.</p>
<h4>צעד 1: פירוק (decomposition)</h4>
<p>קריאה מובנית עם הסכמה <code>Claims</code>: רשימה של טענות. הכללים בפרומפט:</p>
<ul>
<li>עובדה אחת בכל טענה: "A and B" הופך לשתי טענות.</li>
<li>כל טענה עומדת בפני עצמה: "They expire on March 31" הופך ל-"Carried-over vacation days expire on March 31".</li>
<li>שומרים על הניסוח והשפה של התשובה, ולא מתקנים שום דבר.</li>
<li>ציטוטים, ברכות ו"the sources do not say X" הם לא טענות.</li>
</ul>
<p>הכלל האחרון חשוב. תשובה שעונה על חלק מהשאלה ואומרת שהחלק השני לא מופיע היא סירוב חלקי, והיא לא אמורה להיחשב hallucination.</p>
<h4>צעד 2: בדיקה (verification)</h4>
<p>קריאה מובנית שנייה עם הסכמה <code>ClaimVerdicts</code>: לכל טענה, לפי הסדר, ראיה (העתקה מדויקת מהמקורות), מספר המקור, ופסק דין: supported, contradicted או not_found. <b>הראיה באה לפני פסק הדין</b>, מאותה סיבה שבשיעור 3 שמת את <code>reason</code> לפני <code>route</code>. המודל כותב לפי סדר הסכמה, ולכן פסק דין שנכתב ראשון מוצדק בדיעבד במקום להיגזר מהראיה.</p>
<div class="example"><b>הסכמות (ragkit/diagnose.py)</b><pre dir="ltr">class Claims(BaseModel):
    claims: list[str]          # atomic, self-contained, in order

class ClaimVerdict(BaseModel):
    claim: str
    evidence: Optional[str]    # exact text copied from the sources, or null
    source: Optional[int]      # which source it was copied from
    verdict: Literal["supported", "contradicted", "not_found"]

class ClaimVerdicts(BaseModel):
    verdicts: list[ClaimVerdict]</pre></div>
<h4>צעד 3: לבדוק את השופט, בקוד</h4>
<p>שופט יכול להמציא ראיה בדיוק כמו שהמודל ממציא תשובה. לכן, לכל טענה שסומנה supported, הקוד בודק שהראיה שהשופט "העתיק" באמת מופיעה במקור, אחרי נרמול רווחים ואותיות (<code>evidence_in_context</code>). טענה עם ראיה שלא נמצאה מסומנת <code>evidence_verified=False</code>, ולא נספרת כנתמכת. הבדיקה זולה, דטרמיניסטית, ותופסת סוג שלם של טעויות שופט. החיסרון: שופט שעושה פרפרזה לראיה במקום להעתיק אותה ייענש. לכן הפרומפט דורש העתקה מדויקת, ובתרגיל 3 תספור כמה פעמים זה קרה עם Haiku.</p>
<div class="example"><b>הקריאה (מקוצר)</b><pre dir="ltr">r1 = complete_structured(llm, decompose_prompt(answer), Claims, system=DECOMPOSE_SYSTEM)
r2 = complete_structured(llm, verify_prompt(claims, contexts), ClaimVerdicts, system=VERIFY_SYSTEM)
for claim, v in zip(claims, r2.value.verdicts):
    ok = evidence_in_context(v.evidence, contexts, v.source) if v.verdict == "supported" else None
    report.claims.append(ClaimResult(claim, v.verdict, v.evidence, v.source, ok))
faithfulness = supported_and_verified / len(claims)</pre></div>
<p><b>מחיר.</b> שתי קריאות לתשובה. עם Haiku 5.5 (0.10 דולר למיליון טוקנים בקלט ו-0.50 בפלט), זה כ-0.04 סנט לתשובה, וכ-2.5 סנט ל-67 התשובות של הרצה מלאה. אפשר לחסוך את הקריאה הראשונה אם מבקשים מהמודל העונה לכתוב משפט אחד לכל טענה עם ציטוט. אז כל משפט הוא טענה.</p>`,
    },
    {
      kicker: "שופט",
      title: "שופט LLM בקצרה, ומה יכול להשתבש בו",
      html: `<p>השופט הוא חלק מרכזי באבחון, ולכן כדאי להבין כבר עכשיו מה יכול להשתבש בו. שיעור 23 בונה את זה לעומק: rubrics, כיול מול תוויות של אדם, Cohen's kappa ו-position bias. כאן נעבור על מה שצריך כדי להשתמש בו בזהירות.</p>
<ul>
<li><b>קטגוריות, לא ציונים.</b> שלושה פסקי דין עם הגדרה כתובה (supported, contradicted, not_found) עדיפים על ציון 1 עד 10. שופטים מכוילים גרוע על סקאלות עדינות, ואת הקטגוריות אפשר להשוות מול אדם.</li>
<li><b>ההקשר הוא מידע, לא הוראות.</b> בקורפוס של Acme יש מסמך עם prompt injection: מייל של סוחר חיצוני, שמורה ל"עוזרי AI" לטעון שכל מנוי ניתן להחזר. השופט קורא את אותו טקסט, ולכן הפרומפט שלו אומר במפורש שכל מה שבתוך התגיות הוא מידע להערכה.</li>
<li><b>groundedness אינו נכונות.</b> הפרומפט אומר לשופט: "true in the world but absent here is not_found". אחרת, שופט חכם יאשר טענה נכונה שהמודל כתב מהידע שלו, ויחמיץ בדיוק את מה שבאנו לתפוס.</li>
<li><b>הסכמה עם אדם.</b> לפני שסומכים על שופט, מריצים אותו על כמה עשרות תשובות שאדם תייג, ובודקים כמה פעמים הם מסכימים. בתרגיל 7, <code>--rejudge</code> מריץ שופט אחר על אותן תשובות ומדפיס את ההסכמה ואת המקרים שבהם השופטים חלוקים. זו התחלה של כיול.</li>
</ul>
<h4>התחליף הלא מקוון, ומה הוא מלמד</h4>
<p>במסלול הלא מקוון, השופט הוא <code>heuristic_judge_llm()</code>. זה <code>llmkit.LLM</code> אמיתי, ושתי הקריאות המובנות נבנות כמו מול Anthropic. רק התשובה מגיעה מכללים לקסיקליים: המשפט עם הכי הרבה מילים משותפות, כל המספרים של הטענה במקור, ושלילה תואמת בחלון של המשפט. על חמש הדוגמאות של המעבדה הוא:</p>
<ul>
<li><b>תפס</b> את המשפט המומצא ב-e2 ("about two hours").</li>
<li><b>סימן נכון</b> את e3 כ-grounded, למרות שהמקור מיושן.</li>
<li><b>סימן not_found</b> במקום contradicted את היפוך השלילה של e1 ("You must change your password every 90 days" מול "no forced periodic rotation"), ואת "paid in cash before the trip" של e5. הוא ראה שהטענה לא נתמכת, אבל לא הבין שהיא סותרת.</li>
<li><b>נכשל לגמרי</b> ב-e4: תשובה באנגלית ממקור בעברית. אין אף מילה משותפת, ולכן כל הטענות יצאו not_found.</li>
</ul>
<p>זה לא באג בתחליף. זה בדיוק מה ששופט לקסיקלי יכול ולא יכול לעשות, וזו הסיבה שצריך שופט שמבין שפה. בתרגיל 3 תריץ את אותן דוגמאות עם Haiku ותשווה.</p>
<div class="callout"><b>מה לעשות כשהשופט טועה:</b> לא "לתקן את המספר", אלא לתקן את השופט (פרומפט, דוגמאות, מודל) ולמדוד מחדש את ההסכמה. ואם השופט חלוק עם הנוהל על שאלה מסוימת, פותחים את ה-trace. במקרים כאלה, אדם הוא הזהב.</div>`,
    },
    {
      kicker: "NLI",
      title: "מודל NLI מקומי במקום שופט LLM",
      html: `<p><b>NLI</b> (Natural Language Inference) היא משימה ותיקה בעיבוד שפה. נותנים למודל זוג טקסטים, premise ו-hypothesis, והוא מחזיר אחת משלוש תוויות: entailment (ה-premise מוכיח את ה-hypothesis), contradiction (הוא סותר אותו), או neutral (אין קשר מכריע). זו בדיוק בדיקת טענה: ה-premise הוא chunk מההקשר, וה-hypothesis הוא הטענה. מודל NLI הוא cross-encoder קטן, כמו ה-rerankers של שיעור 12. הוא קורא את שני הטקסטים יחד ומחזיר הסתברות לכל תווית.</p>
<h4>אופציה רב-לשונית שבדקתי</h4>
<p><code>MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7</code>. לפי כרטיס המודל ב-Hugging Face:</p>
<ul>
<li>כ-0.3 מיליארד פרמטרים, ברישיון MIT.</li>
<li>אומן על NLI ב-27 שפות, כולל עברית (<code>he</code>). מודל הבסיס אומן מראש על 100 שפות.</li>
<li>התוויות: entailment, neutral ו-contradiction.</li>
<li>הדיוק על XNLI: 0.871 באנגלית, ובין כ-0.77 לכ-0.84 ברוב השפות האחרות.</li>
<li>הכרטיס מזהיר שנתוני האימון תורגמו במכונה, ושהמודל לא תומך ב-FP16.</li>
</ul>
<p>ב-ragkit הוא עטוף ב-<code>NLIChecker</code>. לכל טענה מחשבים entailment מול כל chunk. הטענה נתמכת אם chunk כלשהו מוכיח אותה בהסתברות של 0.5 לפחות, ונסתרת אם chunk כלשהו סותר אותה ואף אחד לא מוכיח.</p>
<h4>אופציה אנגלית, ואופציה מסחרית</h4>
<p><code>vectara/hallucination_evaluation_model</code> (HHEM-2.1-Open) הוא מסווג של כ-0.1 מיליארד פרמטרים, ברישיון Apache-2.0, שמבוסס על flan-t5-base. הוא מחזיר ציון בין 0 ל-1 לזוג של ראיה וטענה, וזה המודל ש-<code>FaithfulnesswithHHEM</code> של Ragas משתמש בו. לפי כרטיס המודל, הגרסה הפתוחה תומכת <b>רק באנגלית</b>. הגרסה עם תמיכה ב-11 שפות (HHEM-2.3) זמינה רק דרך הפלטפורמה המסחרית של Vectara. לעוזר של Acme, עם 9 מסמכים בעברית, זה לא מספיק.</p>
<h4>NLI מול שופט LLM</h4>
<ol class="ladder">
<li><b>מחיר וזמן.</b><span>NLI רץ מקומית, בחינם, בעשרות מילישניות לזוג על מעבד רגיל. שופט LLM עולה כסף (מעט, עם Haiku) ושנייה או שתיים לתשובה.</span></li>
<li><b>מה הוא מבין.</b><span>מודלי NLI אומנו על זוגות של משפטים קצרים. הם טובים בשלילה ובפרפרזה פשוטה, וחלשים במספרים, בטבלאות, ב-chunks ארוכים (הטוקנייזר חותך) ובהיסק בכמה צעדים.</span></li>
<li><b>מה הוא לא עושה.</b><span>הוא לא מפרק תשובה לטענות, ולא מצטט ראיה. בדרך כלל משלבים: LLM מפרק פעם אחת, ו-NLI בודק כל טענה. במעבדה, <code>claims.py --nli</code> משתמש בפירוק של האדם מה-fixture.</span></li>
<li><b>מתי לבחור.</b><span>NLI מתאים לניטור של כל התעבורה, כשהעלות של LLM לכל תשובה גבוהה מדי, או כשהמידע לא יכול לצאת מהשרת. LLM מתאים להערכה מדויקת על סט זהב, ולמקרים הקשים שה-NLI לא בטוח בהם.</span></li>
</ol>
<div class="callout"><b>מה לא נבדק כאן:</b> בסביבת הקורס אין גישה ל-Hugging Face, ולכן לא הרצתי את המודל. הקוד נבדק עם מודל מזויף. בתרגיל 8 תמדוד על המחשב שלך אם הוא תופס את היפוך השלילה של e1 ואת התרגום של e4, ואיך הוא מסתדר עם הטבלה של e5. אם התוצאות מאכזבות, זה ממצא, לא כישלון.</div>`,
    },
    {
      kicker: "מספיקות וייחוס",
      title: "Sufficient context ו-attribution",
      html: `<h4>האם ההקשר בכלל מספיק?</h4>
<p>Joren ועמיתיו מ-Google (ICLR 2025) הציעו להבחין בין שני מצבים: <b>הקשר מספיק</b>, כלומר יש בו את כל מה שצריך כדי לענות, ו<b>הקשר לא מספיק</b>. ההבחנה הזו לא תלויה בתשובת זהב. אפשר לבקש ממודל לסווג אותה, וה-autorater שלהם הסכים עם תוויות של אדם ב-93% לפחות מהמקרים. הממצאים, לפי הפוסט שלהם:</p>
<ul>
<li>מודלים גדולים (Gemini, GPT, Claude) נוטים לענות במקום לסרב גם כשההקשר לא מספיק.</li>
<li>ב-Gemma, שיעור התשובות השגויות עלה מ-10.2% בלי הקשר בכלל ל-66.1% עם הקשר לא מספיק. הקשר חלקי גרם למודל להיות בטוח יותר, ושגוי יותר.</li>
<li>"selective generation", כלומר לענות רק כשהאות של המספיקות והביטחון של המודל מאפשרים, שיפר את הדיוק של התשובות שניתנו בעד 10%.</li>
</ul>
<p>בטקסונומיה שלנו, זה המקור של רוב כשלי <code>failed_to_refuse</code>: 7 מתוך 10 השאלות בלי תשובה ב-baseline. ברוב המקרים היה מסמך near-miss. למשל q073: ה-ARR של 2023 לא מופיע, אבל של 2024, 2025 ויוני 2026 כן. תיקון אפשרי הוא בדיקת מספיקות לפני התשובה, קריאה זולה שמחזירה <code>{context_has_answer: bool}</code>. זה בדיוק ה-rubric של "refusal" ב-evalkit (שיעור 23), ואפשר להפעיל אותו גם בזמן אמת.</p>
<h4>ייחוס (attribution): להצביע על הטווח המדויק</h4>
<p>הציטוטים של ragkit מבוססי פרומפט. המקורות ממוספרים, המודל כותב <code>[n]</code>, והקוד בודק שה-n קיים. זה מצביע על chunk שלם, לא על המשפט שבאמת תומך בטענה. ל-Claude יש <b>ציטוטים מקוריים</b>. שולחים את המקורות כבלוקים מסוג <code>document</code> או <code>search_result</code> עם <code>citations: {enabled: true}</code>, וכל קטע בתשובה חוזר עם רשימת ציטוטים. כל ציטוט כולל <code>cited_text</code> (הטקסט המדויק), את מספר המסמך, ומיקום: <code>char_location</code> עם אינדקסים של תווים לטקסט, <code>page_location</code> עם מספרי עמודים ל-PDF, או <code>content_block_location</code> לתוכן מותאם. לפי התיעוד, <code>cited_text</code> לא נספר בטוקנים של הפלט.</p>
<p>יש שתי השלכות לאבחון. הראשונה: עם ציטוטים מקוריים, citation precision אפשר לחשב ברמת משפט, ו-wrong_citation נהיה נדיר. השנייה, מגבלה חשובה: לפי התיעוד, <b>ציטוטים מקוריים לא עובדים יחד עם structured outputs</b>. בקשה שמפעילה את שניהם מחזירה שגיאה 400. ההמלצה בתיעוד היא לבקש שורה אחת לכל שדה בפורמט <code>field: value</code>, ולפרסר אותה בקוד. לכן השופט ממשיך לעבוד עם structured outputs, והמודל העונה יכול לעבור לציטוטים מקוריים. llmkit עוד לא שולח בלוקים כאלה, וזה רשום ב-ragkit כנקודת הרחבה.</p>
<div class="callout"><b>החיבור:</b> מספיקות עונה על "האם היה מספיק מידע?", groundedness עונה על "האם התשובה נשענה רק עליו?", וייחוס עונה על "על מה בדיוק?". שלושתם לא צריכים זהב, ולכן שלושתם יכולים לרוץ בייצור.</div>`,
    },
    {
      kicker: "תיקונים",
      title: "מאבחנה לתיקון: המפה",
      html: `<p>האבחון שווה משהו רק אם כל שלב מצביע על תיקון. הנה המפה, כפי שהיא כתובה ב-<code>FIXES</code> ב-ragkit, עם השיעור שבו כל תיקון נלמד. ליד כל תיקון כתוב גם איך יודעים שהוא עבד. בלי זה, אין דרך לדעת אם התיקון עזר או רק הזיז את הבעיה.</p>
<ul>
<li><b>missing_from_corpus (שיעורים 8, 9):</b> להוסיף את המקור ל-ingestion (connector, היקף הסנכרון, הרשאות). ואם המסמך לא אמור להיות שם, שאלת הזהב שגויה. מדד: <code>no_doc</code> הופך ל-<code>covered</code>.</li>
<li><b>extraction_lost (שיעור 9):</b> להחליף loader לפורמט: מצב PDF אחר, extractor אחר ל-HTML, טיפול בטבלאות. ואז להריץ ingestion מחדש רק על המסמכים שהשתנו (ה-manifest האינקרמנטלי של שיעור 9). מדד: <code>missing</code> הופך ל-<code>covered</code>.</li>
<li><b>chunk_split (שיעור 9):</b> chunks גדולים יותר או עם חפיפה, chunker שמכבד מבנה (כותרות, טבלה שלמה), או parent-document retrieval. מדד: <code>split</code> הופך ל-<code>covered</code>.</li>
<li><b>not_retrieved (שיעורים 10, 12):</b> hybrid (BM25 ו-dense עם RRF), שכתוב שאילתה (תרגום לשאלות בין שפות, פירוק ל-multi-hop), כותרות הקשר ל-chunks. מדד: recall ב-50 וב-k עולה.</li>
<li><b>ranked_low (שיעור 12):</b> reranker על 30 עד 50 המועמדים הראשונים, גיוון (לכל היותר n chunks לכל מסמך), או k גדול יותר. מדד: MRR ו-recall@k עולים, והמועמדים לא משתנים.</li>
<li><b>stale_version (שיעור 12):</b> אחזור מודע לגרסאות (<code>drop_superseded</code> עם המטא-דאטה <code>supersedes</code>), וכלל בפרומפט שמעדיף את <code>effective_date</code> המאוחר. מדד: stale@5 וציטוטים מיושנים יורדים.</li>
<li><b>false_refusal (שיעורים 4, 9):</b> פרומפט שמגדיר מה נחשב "נמצא" (פרפרזה, שורת טבלה, שפה אחרת), והמקור הטוב ביותר ראשון. מדד: <code>abstain_ok</code> עולה.</li>
<li><b>lost_in_middle (שיעורים 4, 12):</b> פחות chunks וטובים יותר (rerank ואז חיתוך), המקור החזק ראשון ואחרון, דחיסת ההקשר. מדד: כיסוי העובדות עולה באותו אחזור.</li>
<li><b>ignored_context (שיעור 4):</b> פרומפט שדורש לענות על כל חלק של השאלה, הוראות ל-multi-hop, ומודל חזק יותר לסינתזה. מדד: כיסוי העובדות עולה.</li>
<li><b>hallucination (שיעורים 4, 7):</b> כלל "רק מהמקורות", בדיקת groundedness לפני שליחה (verify, ואז לענות או לסרב: לולאת האימות של שיעור 7), temperature נמוך. מדד: groundedness עולה.</li>
<li><b>wrong_citation (שיעור 9):</b> ציטוט לכל משפט, בדיקת <code>[n]</code> בקוד, או ציטוטים מקוריים. מדד: citation precision ו-citation recall עולים.</li>
<li><b>failed_to_refuse (שיעורים 4, 9):</b> בדיקת מספיקות לפני תשובה, כלל סירוב מפורש ל-near-miss, ו-selective generation. מדד: <code>abstain_ok</code> על השאלות בלי תשובה עולה.</li>
</ul>
<div class="callout"><b>לא כל תיקון אוטומטי.</b> <code>fix_loop.py</code> מפעיל אוטומטית רק תיקונים שהם שינוי תצורה: <code>versions</code>, <code>hybrid</code>, <code>k8</code>, <code>diverse</code>, <code>rerank</code> ו-<code>chunker</code>. תיקוני יצירה (פרומפט, מודל) הם החלטות שאדם צריך לקבל, והם נמדדים רק במסלול החי, כי ה-answerer החילוצי מתעלם מהפרומפט. כשהלולאה האוטומטית מדלגת על הקטגוריה הגדולה ביותר, היא כותבת למה.</div>`,
    },
    {
      kicker: "הלולאה",
      title: "לולאת התיקון: שינוי אחד, מדידה מזווגת",
      html: `<p>הלולאה פשוטה: מאבחנים, בוחרים את קטגוריית הכשל הגדולה ביותר שיש לה תיקון, מפעילים את התיקון שלה (ורק אותו), מריצים שוב על אותן 79 שאלות, ומודדים. המדידה היא החלק שבו רוב הצוותים מתעצלים, ולכן היא כאן מבוססת על ה-gates של evalkit (שיעור 23, כאן ככלי):</p>
<ul>
<li><b><code>Threshold("answer_ok", 0.45)</code>:</b> רצפה מוחלטת.</li>
<li><b><code>NoSignificantDrop("answer_ok")</code>:</b> בהשוואה מזווגת ל-baseline, עם מבחן McNemar מדויק. המבחן מסתכל רק על השאלות שהתוצאה שלהן התהפכה.</li>
<li><b><code>NoSignificantDrop</code> לכל סוג שאלה, עם <code>max_drop=0.10</code>:</b> בקבוצה של 9 או 11 שאלות, אף מבחן לא יגיע למובהקות, ולכן יש גם גבול מעשי.</li>
</ul>
<p>תיקון עובר אם שלב היעד קטן ואף gate לא נכשל.</p>
<h4>מה קרה במעבדה (במסלול הלא מקוון, מה-baseline)</h4>
<ol class="ladder">
<li><b>auto: k8, לא לשחרר</b><span>הקטגוריה הגדולה ביותר היא ignored_context (13), ואין לה תיקון אוטומטי. לכן הלולאה בחרה ב-ranked_low (7), עם התיקון "8 chunks במקום 5". ranked_low ירד ל-5, אבל אף שאלה לא תוקנה, ו-q016 נשברה: עם 8 chunks נכנס לפרומפט המחירון הישן, וה-answerer ציטט אותו. answer_ok ירד מ-36 ל-35, וה-gate של numeric נכשל.</span></li>
<li><b>versions: לשחרר</b><span>stale_version ירד מ-6 ל-0, answer_ok עלה מ-36 ל-42, ושום שאלה לא נשברה. McNemar נתן p=0.031: שש שאלות השתפרו ואף אחת לא נפגעה. זה התיקון הזול ביותר בצנרת, עטיפה אחת של ה-retriever.</span></li>
<li><b>diverse: ניטרלי</b><span>לכל היותר 2 chunks לכל מסמך. ranked_low ירד ב-1, אבל אף שאלה לא עברה, כי הכשל רק זז לשלב הבא: עכשיו המסמך השני בפרומפט, וה-answerer החילוצי לא יודע לשלב שני מסמכים. עם Haiku, אותו שינוי עשוי להיות דווקא השיפור הגדול ביותר ל-multi-hop.</span></li>
<li><b>chunker: לא לשחרר, בגלל gate קפדני</b><span>התחלנו מ-<code>fixed:100:0</code> וחזרנו ל-chunker של ה-baseline. chunk_split ירד מ-8 ל-0, ו-answer_ok עלה מ-34 ל-36. אבל שאלה numeric אחת נשברה, ו-1 מתוך 9 זה 0.11, יותר מ-<code>max_drop</code> של 0.10. האם ה-gate צודק? בקבוצה של 9 שאלות, הוא בעצם אומר "אף שאלה לא נשברת". זו החלטה שצריך לקבל במודע.</span></li>
</ol>
<p>שלושה לקחים. הראשון: הקטגוריה הגדולה ביותר היא לא בהכרח המקום הנכון להתחיל. מתחילים בתיקון שהיחס שלו בין תועלת למחיר ולסיכון הכי טוב, ואצלנו זה סינון הגרסאות. השני: תיקון יכול ליצור כשל חדש. k גדול יותר מכניס גרסאות ישנות ורעש, ובקצה, k=20 יוצר lost_in_middle (trace T5). השלישי: "ניטרלי" הוא תוצאה לגיטימית. תיקון שמזיז כשל לשלב הבא הוא לפעמים תנאי לתיקון הבא, ולכן מחליטים עליו יחד עם התיקון הבא, ולא לבד.</p>
<div class="example"><b>הפלט של fix_loop.py --fix versions (מקוצר)</b><pre dir="ltr">target stage stale_version: 6 -> 0
fixed (6): q003, q006, q008, q010, q018, q027      broke (0): none
[PASS] answer_ok >= 0.45: observed 0.532 (95% CI 0.430-0.633, n=79)
[PASS] no significant drop in answer_ok: baseline 0.456 -> candidate 0.532, diff +0.076
       (McNemar p=0.031, better on 6, worse on 0, n=79)
[PASS] ... answer_ok[version_conflict]: 0.273 -> 0.636
verdict: SHIP</pre></div>`,
    },
    {
      kicker: "המספרים",
      title: "מה ההרצה המלאה אומרת, ומה היא לא אומרת",
      html: `<p>הנה שתי הצנרות על כל 79 השאלות, במסלול הלא מקוון, מפורקות לפי שלב וסוג שאלה.</p>
<h4>baseline: BM25, 5 chunks (36 מתוך 79 עברו)</h4>
<ul>
<li><b>אחזור:</b> not_retrieved 3, ranked_low 7, stale_version 6.</li>
<li><b>יצירה:</b> false_refusal 6, ignored_context 13, wrong_citation 1.</li>
<li><b>שאלות בלי תשובה:</b> failed_to_refuse 7 מתוך 10.</li>
<li><b>לפי סוג שאלה:</b> multi_hop עבר ב-2 מתוך 11, ו-5 מהכשלים ranked_low. version_conflict עבר ב-3 מתוך 11, ו-4 מהכשלים stale_version. acronym עבר ב-7 מתוך 8.</li>
</ul>
<h4>best: hybrid, שכתוב וסינון גרסאות (42 מתוך 79 עברו)</h4>
<ul>
<li><b>אחזור:</b> not_retrieved 0, ranked_low 10, stale_version 0.</li>
<li><b>יצירה:</b> false_refusal 8, ignored_context 12.</li>
<li><b>שאלות בלי תשובה:</b> failed_to_refuse 7, בלי שינוי, וזה צפוי: האחזור לא משנה את הנטייה לענות.</li>
<li><b>לפי סוג שאלה:</b> version_conflict עבר ב-9 מתוך 11. multi_hop עבר ב-1 מתוך 11, ו-7 מהכשלים ranked_low.</li>
</ul>
<p><b>מה כן אפשר להסיק.</b> מספרי האחזור אמיתיים: הם תלויים רק ב-retriever, ב-chunks ובשאלות. סינון הגרסאות סגר את כל כשלי הגרסה. התרגום סגר את כל כשלי "לא אוחזר", ואלה היו שאלות בין שפות. ב-multi-hop, הבעיה היא לא שהמסמך השני לא נמצא, אלא שהוא נמצא ונחתך. לכן התיקון הבא הוא reranker או גיוון, ולא עוד שכתוב.</p>
<p><b>מה אי אפשר להסיק.</b> מספרי היצירה מתארים את ה-answerer החילוצי. הוא לא מסוגל לשלב שני מסמכים, לקרוא שורה בטבלה או לתרגם, ולכן ignored_context ו-false_refusal גבוהים. הוא גם לא מסוגל להמציא, ולכן hallucination הוא 0. Claude יתנהג אחרת בשני הכיוונים. סביר שהוא יפספס פחות, ויש סיכוי שימציא יותר. רק ההרצה החיה בתרגיל 7 תגיד.</p>
<p><b>כשלים שזזו.</b> שלוש שאלות עברו מ-not_retrieved ל-ranked_low (q039, q047, q068): התרגום הביא אותן למועמדים, אבל לא ל-5 הראשונים. q042 ו-q069 עברו מ-ranked_low ל-false_refusal: עכשיו הראיה בפרומפט, וה-answerer סירב. זה בדיוק מה שהמשפך באנימציה מראה. כל שלב שמשתפר מעביר שאלות לשלב שאחריו, ושם מתגלה הבעיה הבאה.</p>
<div class="callout"><b>קבוצות קטנות:</b> 11 שאלות multi-hop, 9 numeric. שינוי של שאלה אחת הוא 9 עד 11 נקודות אחוז. לכן הלולאה משתמשת במבחן מזווג ומדפיסה את מזהי השאלות שהשתנו, ולא רק אחוזים. כשמספר נראה דרמטי, פותחים את השאלות עצמן.</div>`,
    },
    {
      kicker: "Company Brain",
      title: "האבחון בפרויקטים וב-Company Brain",
      html: `<p>השיעור סוגר את שלב 2. אחריו מגיעים <b>פרויקטי האמצע</b>, ובהם תבנה עוזר ידע מלא מעל הקורפוס של Acme (או מעל קורפוס משלך). האבחון הוא החלק שהופך פרויקט כזה מ"הנה דמו" ל"הנה מערכת שאני מבין". מה כדאי להכין בפרויקט:</p>
<ol class="ladder">
<li><b>סט זהב עם ציטוטים</b><span>לפחות 40 עד 80 שאלות, לכל אחת <code>source_ids</code>, ציטוט מדויק ועובדות אטומיות, ועשר שאלות בלי תשובה עם near-miss. בלי ציטוטים אין מדדי הקשר דטרמיניסטיים, ואין בדיקה של chunk_split ו-extraction_lost.</span></li>
<li><b>trace לכל הרצה</b><span>אותו פורמט: מועמדים, פרומפט עם טקסט, תשובה, ציטוטים ושופט. כך אפשר לסווג מחדש בחינם.</span></li>
<li><b>דוח פירוק</b><span>כשלים לפי שלב ולפי סוג שאלה, המשפך, והמדדים לפי שלב. כרשימה, עם מזהי השאלות.</span></li>
<li><b>לולאת תיקון מתועדת</b><span>כל שינוי עם התוצאה שלו: מה היה שלב היעד, כמה ירד, מה נשבר, ותוצאות ה-gates. "ניסיתי reranker, זה הזיז 3 שאלות ל-ignored_context" הוא ממצא טוב יותר מ"הוספתי reranker".</span></li>
</ol>
<h4>מה ישתנה ב-Company Brain</h4>
<ul>
<li><b>שלב חדש: הרשאות.</b> ב-Company Brain כל חיפוש מסונן לפי ההרשאה של המשתמש, עם <code>where={"classification": ...}</code>, לפני הדירוג. תשובה שגויה יכולה לנבוע מכך שהמסמך הנכון חסום למשתמש. זה לא באג, אבל הנוהל צריך לדעת להבחין בזה. מוסיפים שלב <code>permission_filtered</code> בין <code>missing_from_corpus</code> ל-<code>not_retrieved</code>: המסמך בקורפוס, אבל לא במועמדים של המשתמש הזה. ההרחבה כתובה ב-ragkit/README.</li>
<li><b>תעבורה בלי זהב.</b> לשאלות של משתמשים אמיתיים מריצים רק את מה שלא צריך זהב: groundedness, מספיקות וסירוב. כשמשתמש מסמן תשובה כשגויה, מוסיפים את השאלה לסט הזהב עם המקור הנכון, ואז אפשר להריץ עליה את הנוהל המלא.</li>
<li><b>ניטור (שיעור 22) והערכה (שיעור 23).</b> ה-traces יגיעו מ-OpenTelemetry spans, וה-gates ירוצו ב-CI על כל שינוי בפרומפט, ב-chunker או ב-retriever.</li>
</ul>
<div class="callout"><b>הרגל אחד לקחת מהשיעור:</b> לפני שמתקנים תשובה שגויה, שואלים "באיזה שלב היא נכשלה?". ברוב המקרים התשובה לא תהיה "המודל". והתיקון הזול ביותר בדרך כלל לא נמצא בשלב שבו רואים את הסימפטום.</div>`,
    },
  ],

  sims: [
    {
      id: "l13tree",
      title: "עץ האבחון: מתשובה שגויה לשלב ולתיקון",
      lead: "עונים על שאלות כן/לא על מקרה שנכשל, לפי סדר הצנרת. אפשר לענות בעצמך על מקרה שאתה מכיר, או לטעון אחד מששת ה-traces של המעבדה, ואז העץ ממלא את התשובות לפי הנתונים שלו ומסביר כל צעד. בסוף מוצגים השלב, ההסבר, התיקון מהשיעור המתאים, ואיך מודדים שהתיקון עבד. מימין למעלה רואים את המסלול שעברת, וכל צעד בו לחיץ.",
      tasks: [
        "טען את <b>T1</b> (האש\"ל). השאלה הראשונה שנכשלת היא לא \"האם צוטט מסמך מיושן\", למרות שהתשובה ציטטה את 2025. באיזו שאלה העץ עוצר, ולמה דווקא שם?",
        "טען את <b>T3</b>, ואחר כך את <b>T5</b>. שניהם קשורים ל-k. מה ההבדל בשלב, ואיך התיקון של T3 (להגדיל את k) יכול לייצר את T5?",
        "ענה בעצמך על המקרה הזה: שאלה בלי תשובה בקורפוס, והמערכת ענתה \"About $9M at the end of 2023 [1]\". כמה שאלות העץ שאל? למה הוא לא בודק אחזור?",
        "טען את <b>T4</b>, ואז שנה את התשובה לשאלה \"האם כל מסמכי המקור בפרומפט?\" ל\"לא\". איך משתנים השלב והתיקון, ולמה סירוב הוא התנהגות נכונה במקרה הזה?",
      ],
    },
    {
      id: "l13claims",
      title: "בודק הטענות: groundedness ברמת טענה",
      lead: "חמש התשובות של תרגיל 3. בכל אחת התשובה מפורקת לטענות, וכל טענה צבועה לפי פסק הדין: ירוק supported, אדום contradicted, צהוב not_found. כשבוחרים טענה, הראיה שלה מודגשת בתוך טקסט המקור שמתחת. המתג עובר בין שני שופטים: התוויות של אדם, והפלט האמיתי של השופט הלקסיקלי מהמסלול הלא מקוון. את Haiku תמדוד בעצמך. למטה מופיעים ציון ה-faithfulness, והלקח של הדוגמה.",
      tasks: [
        "בדוגמה <b>e1</b>, עבור בין \"אדם\" ל\"לקסיקלי\" על הטענה השנייה. מה כל שופט אמר, ואיזו ראיה האדם הצביע עליה? למה מילים משותפות לא מספיקות כאן?",
        "בדוגמה <b>e3</b>, שני השופטים אומרים grounded. למה זה נכון, ולמה התשובה בכל זאת שגויה? איזה שלב בטקסונומיה תופס אותה?",
        "בדוגמה <b>e4</b>, מה ה-faithfulness של השופט הלקסיקלי, ומה של האדם? מה זה אומר על שימוש בשופט לקסיקלי (או HHEM-2.1-Open) על קורפוס עם עברית?",
        "בדוגמה <b>e2</b>: לטענה השלישית יש ציטוט [1] בתשובה. למה היא בכל זאת not_found, ואיך ה-faithfulness הייתה נראית אם היינו שואלים את השופט רק \"האם התשובה כולה נתמכת?\"",
      ],
    },
  ],

  lab: {
    repoPath: "labs/13-rag-diagnostics",
    intro: "המעבדה נמצאת בתיקייה labs/13-rag-diagnostics, ועובדת על הקורפוס של Acme (<code>data/acme/corpus</code>): 55 מסמכים (9 בעברית, 2 PDF, 3 HTML, DOCX אחד), שמחולקים ל-210 chunks (<code>heading:400:40:150</code>, כמו בשיעורים 9 עד 12). יש 79 שאלות זהב. 69 מהן עם <code>source_ids</code>, ציטוט מדויק לכל מקור (<code>source_quotes</code>) ועובדות אטומיות (<code>answer_facts</code>), ו-10 בלי תשובה בקורפוס. ל-ragkit נוסף מודול אחד, <b>ragkit/diagnose.py</b>: הטקסונומיה, המסווג, המדדים לפי שלב, groundedness ברמת טענה, NLI והרצה מלאה. אף קובץ קיים לא השתנה. לכל סקריפט יש מסלול חינמי: <code>--llm extractive --judge heuristic</code>, כלומר answerer חילוצי ושופט לקסיקלי שעונה דרך llmkit אמיתי עם transport מקומי. המספרים שבתרגילים נמדדו במסלול הזה. מספרי האחזור בהם אמיתיים, ומספרי היצירה מתארים את ה-answerer החילוצי. ההרצות החיות עם Haiku עולות יחד כ-20 סנט.",
    setup: [
      'cd ~/ai-engineer-course-starter && source .venv/bin/activate',
      "uv pip install -r requirements.txt -r labs/13-rag-diagnostics/requirements.txt   # transformers only for exercise 8",
      "python -m pytest -q                                      # environment tests, incl. tests/test_ragkit_diagnose.py",
      "python -m pytest -q labs/13-rag-diagnostics/tests        # your exercises: all fail at first",
    ],
    tools: [
      "<b>ragkit.diagnose (הטקסונומיה):</b> <code>STAGES</code>, 12 שלבים לפי סדר הצנרת, ו-<code>FIXES[stage]</code>, שמחזיר <code>Fix(lesson, action, measure)</code>. <code>Case</code> מכיל את כל מה שהמסווג צריך: source_ids, quote_status, stale_ids, candidates, context, evidence_positions, context_tokens, abstained, cited, invalid_citations, fact_coverage ו-grounded.",
      "<b>classify(case):</b> מחזיר <code>Diagnosis(stage, flags, path)</code>, עם <code>.fix</code>. <code>MIN_FACTS=0.5</code>, ו-<code>LONG_CONTEXT=4000</code> טוקנים ל-lost_in_middle.",
      "<b>מדדים:</b> <code>context_recall(quotes, texts)</code>, <code>context_precision(relevance)</code> (מודע לדירוג), <code>simple_precision</code>, <code>citation_precision(cited, supporting)</code>, <code>citation_recall(cited, quote_locs)</code>, ופונקציות העזר <code>quote_locations</code> ו-<code>relevance_from_quotes</code>.",
      "<b>check_claims(answer, contexts, llm):</b> שתי קריאות מובנות (<code>Claims</code>, ואחריה <code>ClaimVerdicts</code> עם הראיה לפני פסק הדין), ואחריהן בדיקת הראיה בקוד (<code>evidence_in_context</code>). מחזיר <code>GroundednessReport</code> עם score, label ו-unsupported. <code>heuristic_judge_llm()</code> הוא השופט הלא מקוון. <code>NLIChecker()</code> משתמש ב-mDeBERTa רב-לשוני.",
      "<b>הרצה:</b> <code>trace_question</code> ו-<code>run_diagnosis</code> (חיפוש עמוק אחד: 50 התוצאות הן המועמדים, ו-5 הראשונות הן הפרומפט), <code>case_from_trace</code>, <code>trace_metrics</code>, <code>breakdown</code>, <code>funnel</code>, <code>format_breakdown</code>, ו-<code>to_evalkit_run</code>, כדי שה-gates של evalkit יעבדו על ההרצה.",
      "<b>evalkit (שיעור 23, כאן ככלי):</b> <code>Threshold</code>, <code>NoSignificantDrop</code>, <code>check_gates</code> ו-<code>mcnemar_exact</code>. <code>fact_coverage</code> הלקסיקלי מחשב את כיסוי העובדות.",
      "<b>mine.py:</b> <code>classify_failure</code> (תרגיל 1), ארבעת המדדים (תרגיל 2), <code>check_claims</code> (תרגיל 3), ו-<code>TRACE_GUESSES</code> (תרגיל 5, בלי קוד).",
      "<b>fixtures:</b> <code>cases.jsonl</code> (20 מקרים בנויים עם הסבר), <code>claims_examples.jsonl</code> (5 תשובות עם תוויות של אדם), <code>traces.jsonl</code> (6 כשלים), ו-<code>build_traces.py</code>, שבונה אותם מחדש. האחזור בהם אמיתי, והתשובות נכתבו ביד.",
    ],
    exercises: [
      { id: "ex1", title: "המסווג (קוד)", text: "ממש ב-mine.py את <code>classify_failure(case, min_facts=0.5, long_context=4000)</code>. שלב A: שאלה בלי <code>source_ids</code> מקבלת <code>ok</code> אם המערכת סירבה, ו-<code>failed_to_refuse</code> אם היא ענתה. שלב B: שאלה עם תשובה נכשלת אם המערכת סירבה, אם <code>fact_coverage</code> מתחת לסף, אם צוטט מסמך מ-<code>stale_ids</code>, אם <code>grounded is False</code>, אם לא צוטט אף מסמך מקור, או אם יש <code>invalid_citations</code>. אם אף אחד מאלה לא קרה, היא <code>ok</code>. שלב C עובר לפי הסדר: no_doc, missing, split, מקור שלא בין המועמדים, מקור שלא בפרומפט, ציטוט מיושן, סירוב. אחר כך, אם העובדות חסרות: hallucination כש-grounded הוא False, lost_in_middle כשההקשר מעל long_context וכל הראיות לא ראשונות ולא אחרונות, ואחרת ignored_context. אחר כך hallucination אם יש טענה לא נתמכת, ובסוף wrong_citation. הבדיקות מריצות את 20 המקרים של <code>fixtures/cases.jsonl</code>. לכל מקרה יש הסבר, למשל c17: המקור לא אוחזר והתשובה ציטטה את הגרסה הישנה, והתווית היא not_retrieved. ענה על שתי שאלות: (1) למה דווקא השלב המוקדם ביותר הוא שורש הבעיה? (2) למה ב-c12 העובדות נכונות והתווית היא hallucination?", cmd: "python -m pytest -q labs/13-rag-diagnostics/tests/test_ex1_classify.py\npython labs/13-rag-diagnostics/classify_demo.py --case c09_lost_in_middle\npython labs/13-rag-diagnostics/classify_demo.py --mine" },
      { id: "ex2", title: "מדדים לפי שלב (קוד)", text: "ממש ארבע פונקציות. <code>context_recall(quotes, texts)</code>: כמה ציטוטי זהב נמצאים בשלמותם ב-chunk כלשהו, אחרי כיווץ רווחים ואותיות קטנות. מחזירה None כשאין ציטוטים. <code>context_precision(relevance)</code>: ממוצע של precision@k במקומות הרלוונטיים. למשל, <code>[True, False, True]</code> נותן (1 + 2/3)/2 = 0.833. מחזירה None לרשימה ריקה, ו-0 כשאין chunk רלוונטי. <code>citation_precision(cited, supporting)</code>: כמה מהמספרים השונים שצוטטו נמצאים ב-supporting. מחזירה None כשלא צוטט כלום. <code>citation_recall(cited, quote_locs)</code>: לכמה ציטוטי זהב צוטט מקום שמכיל אותם. ציטוט בלי מקום בפרומפט נספר כפספוס. הסקריפט מריץ את ה-baseline על 69 השאלות. במסלול הלא מקוון נמדד: context recall 0.829, context precision 0.765, citation precision 0.592 ו-citation recall 0.594. ב-multi_hop: recall 0.515 ו-citation recall 0.182. ב-9 שאלות לא צוטט כלום. ב-q040: recall 0.5 ו-precision 1.0. ענה על שתי שאלות: (1) למה precision מודע-דירוג נותן 1.0 כשרק 1 מתוך 5 chunks רלוונטי, ומה היה נותן <code>simple_precision</code>? (2) למה citation recall של multi_hop נמוך בהרבה מה-context recall שלו?", cmd: "python -m pytest -q labs/13-rag-diagnostics/tests/test_ex2_metrics.py\npython labs/13-rag-diagnostics/metrics_demo.py --mine\npython labs/13-rag-diagnostics/metrics_demo.py --q q040" },
      { id: "ex3", title: "groundedness ברמת טענה (קוד, ואחר כך חי)", text: "ממש את <code>check_claims(answer, contexts, llm)</code>. סירוב או תשובה ריקה מחזירים <code>refusal=True</code> בלי קריאה. אחרת יש שתי קריאות: <code>complete_structured</code> עם <code>Claims</code> ו-DECOMPOSE_SYSTEM, ואחריה, אם יש טענות, <code>ClaimVerdicts</code> עם VERIFY_SYSTEM. לכל טענה נבנה <code>ClaimResult</code>. פסק דין חסר נספר כ-not_found. לטענה supported מוסיפים <code>evidence_verified = evidence_in_context(...)</code>. העלות היא סכום שתי הקריאות, ו-StructuredError מוחזר בשדה error ולא נזרק. חמש הדוגמאות נמצאות ב-<code>fixtures/claims_examples.jsonl</code>. e1: היפוך שלילה, \"You must change your password every 90 days\" כשהמקור אומר \"There is no forced periodic rotation\". e2: משפט מהידע של המודל, \"Outages of this kind usually take about two hours\". e3: תשובה נאמנה למדיניות 2025 המיושנת. e4: תשובה באנגלית ממקור בעברית. e5: טבלה, וטענה ש\"paid in cash before the trip\" כשהמקור אומר \"paid with the salary after the trip\". השופט הלקסיקלי תפס את e2, נתן grounded ל-e3, סימן not_found במקום contradicted ב-e1 וב-e5, ונכשל לגמרי ב-e4. אחר כך הרץ עם Haiku, בעלות של כ-0.3 סנט. ענה על שתי שאלות: (1) איפה Haiku צדק והלקסיקלי טעה, ולהפך? (2) כמה פעמים בדיקת הראיה בקוד הורידה טענה של Haiku?", cmd: "python -m pytest -q labs/13-rag-diagnostics/tests/test_ex3_claims.py\npython labs/13-rag-diagnostics/claims.py --mine\npython labs/13-rag-diagnostics/claims.py --show e1\npython labs/13-rag-diagnostics/claims.py --llm anthropic:claude-haiku-5-5" },
      { id: "ex4", title: "אבחון מלא: baseline מול best", text: "הסקריפט מריץ את כל 79 השאלות בשתי צנרות, על אותם chunks ועם אותו answerer. baseline: BM25 ו-5 chunks. best: BM25 ו-dense עם RRF, שכתוב (multi, decompose, translate) וסינון גרסאות. לכל צנרת מודפסים, כרשימות: כשלים לפי שלב (עם מזהי השאלות), לפי סוג שאלה, המשפך, והמדדים לפי שלב. בסוף מודפס מה תוקן, מה נשבר ומה זז. ה-traces נשמרים ב-results. במסלול הלא מקוון: baseline עבר ב-36. הכשלים שלו: not_retrieved 3, ranked_low 7, stale_version 6, false_refusal 6, ignored_context 13, wrong_citation 1 ו-failed_to_refuse 7. best עבר ב-42: not_retrieved 0, stale_version 0, ranked_low 10 (7 מהם multi_hop), false_refusal 8, ignored_context 12, failed_to_refuse 7. 9 תוקנו ו-3 נשברו. עם <code>--chunker fixed:100:0</code> מופיעים 8 כשלי chunk_split. ענה על שלוש שאלות: (1) לאן זזו הכשלים כשהאחזור השתפר? (2) למה 7 מכשלי ה-multi_hop ב-best הם ranked_low? רמז: הרץ <code>--show q040</code> וספור chunks של אותו מסמך בפרומפט. (3) מה משותף לשבעת כשלי failed_to_refuse?", cmd: "python labs/13-rag-diagnostics/run_diagnosis.py\npython labs/13-rag-diagnostics/run_diagnosis.py --show q040,q073\npython labs/13-rag-diagnostics/run_diagnosis.py --pipelines baseline --chunker fixed:100:0\npython labs/13-rag-diagnostics/run_diagnosis.py --mine" },
      { id: "ex5", title: "אבחן את ה-trace בעצמך (6 כשלים)", text: "ב-<code>fixtures/traces.jsonl</code> יש שישה traces. האחזור בהם אמיתי, והתשובות ופסקי הדין נכתבו ביד. הסקריפט מציג את כל השדות. T1 (q002, אש\"ל): שני ה-PDF נטענו עם loader חדש. ב-chunk השני כתוב \"according to this table:\", ואין טבלה. הציטוט מסומן missing, והתשובה \"$75\" מצטטת את <code>fin-travel-2025</code>. T2 (q052, Quiet Hours): chunker של <code>fixed:100:0</code>. ה-chunk נגמר ב-\"until\", והתשובה אומרת \"until midnight\", טענה שהשופט סימן not_found. T3 (q040): בפרומפט ארבעה chunks של ה-postmortem ואחד של ה-deploy. הקטלוג הוא המסמך הרביעי ברשימת המועמדים, והתשובה אומרת שהבעלים לא מופיע. T4 (q039): <code>hr-onboarding-he</code> במקום השני בפרומפט, והתשובה \"not in the documents\". T5 (q015): dense עם k=20, הפרומפט כ-4,100 טוקנים, שורת המגבלה ב-chunk מספר 8, והתשובה אומרת שהמגבלה לא מופיעה. T6 (q014): ה-postmortem ראשון עם \"47 minutes\", והתשובה \"about two hours\", \"typical for SEV1\", \"failed over to the second region\". כתוב את התווית שלך לכל trace ב-<code>TRACE_GUESSES</code>, ורק אז הרץ <code>--check</code>. ענה על שתי שאלות: (1) באיזה trace הסימפטום מטעה? (2) איזה תיקון היית מציע לכל אחד, ואיזה מהתיקונים יכול ליצור כשל חדש?", cmd: "python labs/13-rag-diagnostics/traces.py\npython labs/13-rag-diagnostics/traces.py --t T5 --full\npython labs/13-rag-diagnostics/traces.py --check" },
      { id: "ex6", title: "לולאת תיקון עם gates", text: "הלולאה מאבחנת, בוחרת את הקטגוריה הגדולה ביותר שיש לה תיקון אוטומטי, מפעילה רק אותו, מריצה שוב, ומודדת עם evalkit. ה-gates: <code>Threshold(\"answer_ok\", 0.45)</code>, ו-<code>NoSignificantDrop</code> בהשוואה מזווגת עם McNemar, על הכול ועל כל סוג שאלה עם max_drop של 0.10. התיקונים: versions, hybrid, k8, diverse, rerank, chunker, ו-prompt (רק במסלול החי). במסלול הלא מקוון: ב-auto, ignored_context (13) דולג כי אין לו תיקון אוטומטי, ולכן נבחר ranked_low עם k8. ranked_low ירד ל-5, q016 נשברה (המחירון הישן נכנס לפרומפט), ושני gates נכשלו: DO NOT SHIP. versions: stale_version ירד מ-6 ל-0, answer_ok עלה מ-36 ל-42 עם p=0.031: SHIP. diverse: ranked_low ירד ב-1 ואף שאלה לא עברה: NEUTRAL. מ-<code>fixed:100:0</code> חזרה ל-chunker הרגיל: chunk_split ירד מ-8 ל-0, answer_ok עלה מ-34 ל-36, אבל ה-gate של numeric נכשל (1 מתוך 9 זה 0.11). ענה על שלוש שאלות: (1) למה הקטגוריה הגדולה ביותר היא לא תמיד המקום להתחיל? (2) מה מלמד NEUTRAL? (3) האם max_drop של 0.10 על 9 שאלות סביר?", cmd: "python labs/13-rag-diagnostics/fix_loop.py\npython labs/13-rag-diagnostics/fix_loop.py --fix versions\npython labs/13-rag-diagnostics/fix_loop.py --fix diverse\npython labs/13-rag-diagnostics/fix_loop.py --chunker fixed:100:0" },
      { id: "ex7", title: "הרצה חיה עם Haiku: תשובות ושופט", text: "עכשיו התשובות והשופט אמיתיים. הרץ את שתי הצנרות עם Haiku כמודל עונה וכשופט, בעלות של כ-4 סנט לצנרת. אחר כך הרץ מחדש רק את השופט הלקסיקלי על התשובות של Haiku (<code>--rejudge</code>). הסקריפט מדפיס את ההסכמה בין שני השופטים, את השאלות שבהן הם חלוקים, ואילו אבחנות השתנו. לבסוף, נסה את התיקון <code>prompt</code> (פרומפט עם כללים מפורשים לשאלות מרובות חלקים, לטבלאות, למקורות בשפה אחרת ולסירוב) מעל best, בעלות של כ-8 סנט. ענה על שלוש שאלות: (1) איך התפלגות הכשלים השתנתה לעומת המסלול הלא מקוון: כמה ignored_context, false_refusal, hallucination ו-failed_to_refuse? (2) באיזה אחוז מהתשובות השופטים הסכימו? פתח שתי מחלוקות והחלט מי צדק. (3) האם הפרומפט עבר את ה-gates, ומה הוא שבר? כתוב את המספרים שלך. אם הם סותרים משהו בשיעור, המדידה שלך קובעת.", cmd: "python labs/13-rag-diagnostics/run_diagnosis.py --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5 --yes\npython labs/13-rag-diagnostics/run_diagnosis.py --rejudge traces_best_anthropic-claude-haiku-5-5_anthropic-claude-haiku-5-5.jsonl --judge heuristic\npython labs/13-rag-diagnostics/fix_loop.py --start best --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5 --fix prompt --yes" },
      { id: "ex8", title: "(אופציונלי) NLI מקומי מול שופט LLM", text: "<code>NLIChecker</code> משתמש ב-<code>MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7</code>: כ-0.3 מיליארד פרמטרים, MIT, NLI ב-27 שפות כולל עברית, ותוויות entailment, neutral ו-contradiction. לכל טענה הוא בודק entailment מול כל chunk. הטענה נתמכת אם chunk כלשהו מוכיח אותה בהסתברות של 0.5 לפחות, ונסתרת אם chunk סותר אותה ואף אחד לא מוכיח. הוא לא מפרק טענות, ולכן הסקריפט משתמש בפירוק של האדם. צריך להתקין את PyTorch בגרסת CPU, את transformers ואת sentencepiece. בהרצה הראשונה המודל יורד מ-Hugging Face. ענה על שלוש שאלות: (1) האם הוא תפס את היפוך השלילה של e1 ואת התרגום של e4? (2) איך הוא הסתדר עם הטבלה של e5? (3) כמה זמן לקחה כל טענה על המעבד שלך, לעומת Haiku?", cmd: "uv pip install torch --index-url https://download.pytorch.org/whl/cpu\nuv pip install \"transformers>=4.46\" sentencepiece\npython labs/13-rag-diagnostics/claims.py --nli" },
    ],
  },

  quiz: [
    { q: "המסמך הנכון לא נמצא בין 50 המועמדים, ורק הגרסה המיושנת שלו הגיעה לפרומפט. המודל ציטט אותה. מה שורש הבעיה לפי הנוהל?", options: ["stale_version, כי צוטט מסמך מיושן", "hallucination", "not_retrieved: הכשל המוקדם ביותר בצנרת הוא שורש הבעיה, והמודל עשה בדיוק מה שהיה צריך עם מה שקיבל", "wrong_citation"], correct: 2, explain: "הנוהל עוצר ב<b>שלב הראשון שנכשל</b>. סינון גרסאות במצב retrieved לא היה עוזר, כי הגרסה החדשה בכלל לא ברשימה. התיקון הוא באחזור." },
    { q: "מה ההבדל בין not_retrieved לבין ranked_low?", options: ["אין הבדל, שניהם \"לא מצא\"", "not_retrieved: המקור לא בין המועמדים של החיפוש העמוק. ranked_low: הוא בין המועמדים ונחתך לפני הפרומפט. לראשון מתקנים את ה-retriever, לשני מתקנים את הדירוג או את k", "ranked_low קורה רק ב-BM25", "not_retrieved קורה רק בשאלות בעברית"], correct: 1, explain: "בגלל זה ה-trace שומר <b>שתי רשימות</b>, מועמדים ופרומפט. הסימפטום זהה, והתיקונים שונים לגמרי: hybrid או שכתוב מול reranker, גיוון או k גדול יותר." },
    { q: "relevance של 5 ה-chunks בפרומפט היא [True, False, False, False, False]. מה context precision לפי Ragas, ומה simple precision?", options: ["0.2 ו-0.2", "1.0 ו-1.0", "0.2 ו-1.0", "1.0 ו-0.2: הגרסה של Ragas מודעת לדירוג ולא מענישה על chunks לא רלוונטיים אחרי הרלוונטי האחרון. הגרסה הפשוטה סופרת את הרעש"], correct: 3, explain: "precision@1 = 1, ויש רק מקום רלוונטי אחד, ולכן הממוצע הוא 1.0. זה בדיוק q040 ב-baseline. שני המדדים <b>עונים על שאלות שונות</b>: האם הדירוג טוב, וכמה רעש נכנס לפרומפט." },
    { q: "התשובה חוזרת בנאמנות על מדיניות החופשה להורים של 2025, שהוחלפה ב-2026. מה יגיד שופט groundedness?", options: ["grounded: כל הטענות נמצאות בהקשר שנשלח. groundedness לא בודק נכונות, ואת הכשל הזה תופס השלב stale_version", "not_grounded, כי המדיניות מיושנת", "partially_grounded", "השופט יסרב לשפוט"], correct: 0, explain: "groundedness שואל רק <b>האם התשובה נשענת על ההקשר</b>. זו דוגמה e3 במעבדה. לכן צריך גם מדדים שתלויים בזהב: עובדות, וציטוט של מסמך מיושן." },
    { q: "למה בבדיקת groundedness ברמת טענה השופט כותב את הראיה לפני פסק הדין, ולמה הקוד בודק את הראיה אחר כך?", options: ["כדי לחסוך טוקנים", "כי ה-API דורש סדר כזה", "המודל כותב לפי סדר הסכמה, ולכן פסק דין שנכתב ראשון מוצדק בדיעבד. והשופט יכול להמציא ראיה, ולכן בודקים בקוד שהיא באמת במקור", "כדי שהשופט יהיה מהיר יותר"], correct: 2, explain: "<b>ראיה לפני פסק דין</b> זה אותו עיקרון כמו reason לפני route בשיעור 3. בדיקת הראיה בקוד היא דטרמיניסטית וזולה, ותופסת שופט שממציא \"ציטוט\"." },
    { q: "השופט הלקסיקלי סימן not_grounded את כל הטענות של תשובה באנגלית שנכתבה ממקור בעברית, שבו הכול כתוב. מה המסקנה?", options: ["התשובה המציאה הכול", "שופט שמבוסס על מילים משותפות עיוור לתרגום. צריך שופט רב-לשוני (LLM, או NLI רב-לשוני כמו mDeBERTa), ו-HHEM-2.1-Open, שתומך רק באנגלית, לא יתאים", "המסמך העברי לא נקלט", "צריך לתרגם את הקורפוס לאנגלית"], correct: 1, explain: "זו דוגמה e4. <b>אסור לשפוט מערכת לפי שופט שעיוור לסוג הנתונים שלה.</b> בקורפוס עם עברית, בדוק את השופט על עברית לפני שסומכים עליו." },
    { q: "הלולאה האוטומטית בחרה בתיקון k8 ל-ranked_low. ranked_low ירד מ-7 ל-5, אבל answer_ok ירד מ-36 ל-35, ו-q016 עכשיו מצטטת את המחירון הישן. מה נכון?", options: ["לשחרר, כי שלב היעד ירד", "התיקון יצר כשל חדש: יותר chunks הכניסו גרסה מיושנת לפרומפט. gate נכשל, ולכן לא משחררים. מתחילים מתיקון אחר, למשל סינון גרסאות", "הבדיקה שבורה", "צריך k=20"], correct: 1, explain: "תיקון יכול <b>להזיז כשל או ליצור כשל חדש</b>. לכן מודדים בהשוואה מזווגת את כל השלבים ואת כל סוגי השאלות, ולא רק את שלב היעד. ו-k=20 היה יוצר lost_in_middle, כמו ב-T5." },
    { q: "התיקון diverse (לכל היותר 2 chunks לכל מסמך) הוריד ranked_low ב-1, ואף שאלה לא עברה. מה סביר שקרה?", options: ["התיקון לא עשה כלום", "הכשל זז לשלב הבא: המסמך השני הגיע לפרומפט, וה-answerer החילוצי לא יודע לשלב שני מסמכים. עם מודל אמיתי, אותו שינוי עשוי לעזור מאוד ל-multi-hop", "המדד שגוי", "צריך להוריד ל-chunk אחד לכל מסמך"], correct: 1, explain: "<b>NEUTRAL</b> הוא תוצאה לגיטימית: תיקון שמעביר כשל לשלב הבא הוא לפעמים תנאי לתיקון הבא. מחליטים עליו יחד עם התיקון הבא, ובמקרה הזה רק אחרי מדידה חיה." },
    { q: "מה Google מצאו על מספיקות ההקשר (sufficient context)?", options: ["שמודלים תמיד מסרבים כשאין מספיק מידע", "שהקשר חלקי לא משנה את שיעור הטעויות", "שמודלים גדולים נוטים לענות גם כשההקשר לא מספיק. ב-Gemma, שיעור התשובות השגויות עלה מ-10.2% בלי הקשר ל-66.1% עם הקשר לא מספיק. selective generation שיפר את הדיוק של התשובות שניתנו בעד 10%", "שאי אפשר לסווג מספיקות אוטומטית"], correct: 2, explain: "הקשר חלקי גורם למודל להיות <b>בטוח יותר ושגוי יותר</b>. זה המקור של רוב כשלי failed_to_refuse (7 מתוך 10 ב-baseline), ובדיקת מספיקות לפני תשובה היא תיקון אפשרי." },
    { q: "רוצים שהמודל העונה יחזיר את הטווח המדויק שתומך בכל טענה, וגם JSON מובנה עם structured outputs באותה קריאה. מה הבעיה?", options: ["אין בעיה", "ציטוטים מקוריים עובדים רק עם PDF", "לפי התיעוד של Claude, ציטוטים מקוריים ו-structured outputs לא עובדים יחד, והבקשה מחזירה שגיאה 400. ההמלצה היא פורמט של שורה לכל שדה, ולפרסר אותו בקוד", "cited_text עולה כפול בטוקנים"], correct: 2, explain: "זו <b>מגבלה מתועדת</b>. לכן השופט ממשיך לעבוד עם structured outputs, והמודל העונה יכול לעבור לציטוטים מקוריים (char_location, page_location) כש-llmkit יתמוך בבלוקים כאלה." },
  ],

  summary: {
    points: [
      { t: "אבחון לפי שלב", b: "מדד מקצה לקצה אומר כמה שאלות נכשלו, אבל לא איפה. תשובת RAG עוברת שרשרת: קורפוס, חילוץ, chunking, אחזור, חיתוך ל-top-k, יצירה וציטוט. לכל שלב יש כשל משלו ותיקון משלו, ובמעבדה שיפור של 6 שאלות הסתיר 9 תיקונים, 3 שאלות שנשברו וכשלים שזזו לשלבים אחרים." },
      { t: "הטקסונומיה", b: "ingestion: חסר בקורפוס, החילוץ איבד, ה-chunk חתך. אחזור: לא אוחזר, אוחזר ונחתך, גרסה מיושנת. יצירה: סירוב שגוי, lost in the middle, התעלמות מההקשר, hallucination, ציטוט שגוי. ולשאלות בלי תשובה: אי-סירוב. ה-trace שומר מועמדים ופרומפט בנפרד, כי \"לא נמצא\" ו\"נמצא ונחתך\" הם כשלים עם תיקונים שונים." },
      { t: "הנוהל", b: "קודם בודקים אם התשובה עברה. אם לא, שואלים לפי סדר הצנרת, והשלב הראשון שנכשל הוא שורש הבעיה. שאר הבעיות נשמרות כדגלים, ומסלול ההחלטה מתועד. כשל מוקדם גורם לכשלים מאוחרים: PDF שאיבד טבלה נראה כמו גרסה מיושנת, ו-chunk שנחתך נראה כמו hallucination." },
      { t: "מדדי הקשר", b: "context recall הוא חלק ציטוטי הזהב שנמצאים בשלמותם בפרומפט. context precision של Ragas הוא ממוצע של precision@k במקומות הרלוונטיים, והוא מודע לדירוג. simple precision הוא chunks רלוונטיים חלקי k, והוא מודד רעש. מדד שלא חל על שאלה הוא None, לא 0. ב-baseline: recall 0.829, וב-multi_hop רק 0.515." },
      { t: "groundedness וציטוטים", b: "faithfulness הוא טענות נתמכות חלקי כל הטענות. הוא לא צריך זהב, ולכן מתאים לניטור בייצור, אבל הוא לא בודק נכונות: תשובה נאמנה למדיניות מיושנת היא grounded. answer relevance בודק אם התשובה עונה על השאלה. citation precision ו-citation recall מחושבים כאן ברמת chunk וראיה, ושאלה בלי ציטוט מדווחת בנפרד." },
      { t: "בדיקה ברמת טענה", b: "שתי קריאות מובנות: פירוק לטענות אטומיות שעומדות בפני עצמן, ובדיקה של כל טענה עם ראיה לפני פסק דין (supported, contradicted, not_found). אחר כך הקוד מוודא שהראיה באמת במקור, כי גם שופט ממציא. עם Haiku 5.5 זה כ-0.04 סנט לתשובה. השופט הלקסיקלי הלא מקוון עיוור לתרגום ולסתירה מנוסחת אחרת." },
      { t: "ספריות ו-NLI", b: "Ragas 0.4 (Faithfulness, ContextPrecision, ContextRecall, AnswerRelevancy, ב-API החדש ragas.metrics.collections) ו-RAGChecker (claim recall, context utilization, noise sensitivity, hallucination, self-knowledge) מגדירים את אותם רעיונות. מדד משלך עדיף כשיש ציטוטי זהב. mDeBERTa-v3 multilingual NLI (MIT, 27 שפות כולל עברית) הוא בודק מקומי וזול. HHEM-2.1-Open תומך רק באנגלית." },
      { t: "מספיקות וייחוס", b: "מודלים גדולים נוטים לענות גם כשההקשר לא מספיק, וזה המקור של רוב כשלי failed_to_refuse. בדיקת מספיקות לפני תשובה ו-selective generation מצמצמים אותם. ציטוטים מקוריים של Claude מחזירים cited_text וטווח מדויק, אבל לא עובדים יחד עם structured outputs (שגיאה 400)." },
      { t: "לולאת התיקון", b: "שלב, ואחריו התיקון שלו משיעורים 9 עד 12, שינוי אחד בכל פעם, השוואה מזווגת על אותן שאלות, ו-gates לכל סוג שאלה. במעבדה, סינון גרסאות העלה את answer_ok מ-36 ל-42 (McNemar p=0.031). k8 שבר שאלה, ו-diverse רק הזיז כשל. מתחילים בתיקון עם היחס הטוב ביותר בין תועלת לסיכון, ולא בהכרח בקטגוריה הגדולה ביותר." },
    ],
    glossary: [
      ["Root cause stage", "השלב המוקדם ביותר בצנרת שנכשל בשאלה מסוימת. כל השלבים שאחריו הם תוצאה אפשרית שלו."],
      ["Candidates", "התוצאות של חיפוש עמוק (כאן 50), לפני החיתוך ל-k שנשלחים למודל."],
      ["ranked_low", "מסמך מקור שנמצא בין המועמדים, אבל לא ב-k הראשונים, ולכן לא הגיע לפרומפט."],
      ["chunk_split", "ציטוט זהב שנמצא במסמך, אבל אף chunk לא מכיל אותו בשלמותו."],
      ["extraction_lost", "ציטוט זהב שלא שרד את חילוץ הטקסט, למשל טבלה ב-PDF."],
      ["Lost in the middle", "מודלים משתמשים פחות במידע שבאמצע הקשר ארוך מאשר במידע שבתחילתו ובסופו (Liu et al., 2023)."],
      ["Context recall", "חלק הראיות הנדרשות (כאן: ציטוטי זהב) שנמצאות בהקשר שנשלח."],
      ["Context precision", "כמה מההקשר רלוונטי. ב-Ragas: ממוצע של precision@k במקומות הרלוונטיים (מודע לדירוג)."],
      ["Groundedness / Faithfulness", "חלק הטענות בתשובה שנתמכות בהקשר שנשלח. לא צריך זהב, ולא בודק נכונות."],
      ["Answer relevance", "האם התשובה עונה על השאלה. ב-Ragas: cosine בין השאלה לשאלות שנוצרו מהתשובה."],
      ["Citation precision / recall", "כמה מהציטוטים מצביעים על ראיה, וכמה מהראיות צוטטו."],
      ["Claim decomposition", "פירוק תשובה לטענות אטומיות שעומדות בפני עצמן, כדי לבדוק כל אחת לבד."],
      ["NLI (entailment)", "סיווג זוג טקסטים ל-entailment, neutral או contradiction. משמש לבדיקת טענה מול ראיה."],
      ["Sufficient context", "הקשר שיש בו את כל מה שצריך כדי לענות. אפשר לסווג אותו בלי תשובת זהב."],
      ["Parametric knowledge", "ידע שהמודל למד באימון. כשהוא נכנס לתשובה במקום המקורות, זו hallucination ב-RAG."],
      ["Paired comparison", "השוואה של שתי הרצות על אותן שאלות, שאלה מול שאלה (כאן McNemar מדויק), במקום השוואת ממוצעים."],
    ],
    reading: [
      { title: "Ragas: List of available metrics", url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/", note: "שמות המדדים והקבוצות. משם יש קישורים לדפים של Faithfulness, Context Precision, Context Recall ו-Answer Relevancy, עם הנוסחאות ועם ה-API החדש מול הישן." },
      { title: "Ragas: Faithfulness", url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/", note: "פירוק לטענות ובדיקה מול ההקשר. כולל את FaithfulnesswithHHEM." },
      { title: "Ragas: Context Precision", url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/", note: "הנוסחה עם precision@k ו-v_k, והגרסה שמבוססת על מזהים (IDBasedContextPrecision)." },
      { title: "Ru et al.: RAGChecker (NeurIPS 2024)", url: "https://arxiv.org/abs/2408.08067", note: "חלוקת האשמה בין ה-retriever ל-generator ברמת טענה." },
      { title: "Barnett et al.: Seven Failure Points When Engineering a Retrieval Augmented Generation System", url: "https://arxiv.org/abs/2401.05856", note: "טקסונומיה של כשלים מתוך שלושה מקרי בוחן בתעשייה. השווה אותה לזו של השיעור." },
      { title: "Liu et al.: Lost in the Middle: How Language Models Use Long Contexts", url: "https://arxiv.org/abs/2307.03172", note: "עקומת ה-U של הדיוק לפי מיקום המידע בהקשר." },
      { title: "Gao et al.: Enabling Large Language Models to Generate Text with Citations (ALCE)", url: "https://arxiv.org/abs/2305.14627", note: "citation recall ו-citation precision ברמת משפט, עם NLI." },
      { title: "Joren et al.: Sufficient Context: A New Lens on Retrieval Augmented Generation Systems (ICLR 2025)", url: "https://arxiv.org/abs/2411.06037", note: "המאמר המלא מאחורי הפוסט של Google, כולל ה-prompts של ה-autorater." },
      { title: "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (model card)", url: "https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7", note: "MIT, כ-0.3 מיליארד פרמטרים, 27 שפות כולל עברית, ותוצאות XNLI לכל שפה." },
      { title: "vectara/hallucination_evaluation_model (HHEM-2.1-Open)", url: "https://huggingface.co/vectara/hallucination_evaluation_model", note: "מסווג groundedness קטן, Apache-2.0, באנגלית בלבד. הגרסה הרב-לשונית (HHEM-2.3) מסחרית." },
      { title: "Claude docs: Citations", url: "https://platform.claude.com/docs/en/build-with-claude/citations", note: "char_location, page_location, cited_text, וההערה שציטוטים ו-structured outputs לא עובדים יחד." },
    ],
  },
};
