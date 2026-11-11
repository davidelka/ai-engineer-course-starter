# רמזים לפרויקט M1: עוזר הידע של Acme

הקובץ הזה הוא למקרה שנתקעת. כדאי קודם לנסות לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, ונסה שוב. אם עדיין לא הולך, עבור ל-**רמז 2**, ורק בסוף ל-**רמז 3**, שמתאר את האלגוריתם המלא במילים. כל רמת רמז נמצאת תחת כותרת משלה, כך שאפשר לעצור אחרי כל אחת.

מימושי הייחוס נמצאים בענף `solutions` של הריפו, בקובץ `projects/m1-knowledge-assistant/acmeqa/_reference.py`. כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים (`python -m pytest -q projects/m1-knowledge-assistant/tests`). אפשר לראות את הקובץ בלי לעבור ענף: `git show origin/solutions:projects/m1-knowledge-assistant/acmeqa/_reference.py`.

## build_retriever

### רמז 1: כיוון
אתה לא כותב כאן אלגוריתם חיפוש: כל השכבות כבר קיימות ב-`ragkit` משיעורים 9 עד 12. העבודה היא **להרכיב** אותן בסדר הנכון, כשכל שכבה עוטפת את זו שמתחתיה ומדברת באותו ממשק, `search(query, k, where)`. המלכודת: סינון הגרסאות צריך לעטוף את החיפוש ההיברידי, וה-reranker עוטף את סינון הגרסאות, ולא להפך. וה-ACL לא נבנה כאן בכלל: הוא מגיע כ-`where` בזמן החיפוש, וכל שכבה מעבירה אותו פנימה עד השלב הראשון.

### רמז 2: מבנה
התחל משלושת המקרים הפשוטים, שמחזירים את מה שכבר יש ב-job. אחר כך התחל ממשתנה `r = job.index` ועטוף אותו שלב אחרי שלב: אם `version_mode` אינו `"off"`, עטוף ב-`VersionAwareRetriever`, וב-`"corpus"` חשב קודם את מפת הגרסאות. אם `upto == "versions"`, החזר כאן. אחרת, אם יש `rerank`, עטוף ב-`RerankingRetriever`. אל תשכח שה-settings מגיעים מהארגומנט, ורק אם הוא `None` מ-`job.s`.

### רמז 3: האלגוריתם המלא
1. `s = s or job.s`.
2. `upto == "bm25"` מחזיר `job.bm25`; `"dense"` מחזיר `job.dense`; `"hybrid"` מחזיר `job.index`.
3. `r = job.index`. אם `s.version_mode != "off"`:
   - `sup = supersedes_map(job.all_chunks())` אם המצב הוא `"corpus"`, אחרת `None`;
   - `r = VersionAwareRetriever(r, mode=s.version_mode, superseded_by=sup, fetch_k=50)`.
4. אם `upto == "versions"`, החזר את `r`.
5. אם `s.rerank`: ‏`r = RerankingRetriever(r, make_reranker(s.rerank), fetch_k=30)`.
6. החזר את `r`.

למה הסדר הזה: סינון הגרסאות מוריד גרסה ישנה רק כשגם החדשה נמצאת במועמדים, ולכן הוא צריך רשימה רחבה (50). ה-reranker יקר, ולכן הוא מקבל רק את 30 הראשונים אחרי שהגרסאות הישנות כבר ירדו. ה-ACL רץ כ-`where` בתוך BM25 ובתוך החיפוש הווקטורי, **לפני** הדירוג, כך שמסמך חסוי לא תופס מקום בעשירייה הראשונה (שיעור 11).

## pack_context

### רמז 1: כיוון
זו בחירה **חמדנית** (greedy) לאורך רשימה שכבר ממוינת מהטוב לגרוע: אתה עובר פעם אחת ומחליט על כל hit אם לקחת אותו. המלכודת העיקרית היא תקציב הטוקנים: hit שלא נכנס **לא** עוצר את הלולאה, כי chunk קטן יותר בהמשך עוד יכול להיכנס. מלכודת שנייה: אסור לשנות את ה-Hit המקוריים, ולכן `dataclasses.replace` מיובא בראש הקובץ.

### רמז 2: מבנה
שמור שלושה דברים תוך כדי מעבר: קבוצה (`set`) של טקסטים מנורמלים שכבר נלקחו, מונה (dict) של כמה hits נלקחו מכל `doc_id`, וסכום הטוקנים עד עכשיו. לכל hit בדוק קודם כפילות, אחר כך את המגבלה למסמך, ואחר כך את התקציב (עם החריג של ה-hit הראשון). אם עבר את כל הבדיקות, הוסף אותו ועדכן את שלושת המצבים. עצור כשהגעת ל-`max_chunks`. בסוף בנה Hits חדשים עם דירוג חדש.

### רמז 3: האלגוריתם המלא
1. אם `count` הוא `None`, השתמש ב-`get_tokenizer("approx").count` (דטרמיניסטי, בלי הורדה).
2. עבור על `hits` לפי הסדר (הטוב ראשון). לכל hit:
   - **כפילות**: חשב `collapse_ws(normalize(hit.chunk.text)).lower()`. אם הטקסט הזה שווה לטקסט של hit שכבר נשמר, דלג (it-laptop-policy ו-it-laptop-faq חוזרים על פסקאות שלמות).
   - **למסמך**: אם ל-`doc_id` של ה-hit כבר יש `max_per_doc` hits שמורים, דלג.
   - **תקציב**: אם הוספת `count(chunk.text)` לסכום תגרום לסכום לעבור את `max_tokens`, דלג **והמשך** הלאה. החריג: ה-hit הראשון שנשמר תמיד נשמר, גם אם הוא לבדו מעל התקציב (prompt ריק לא עוזר לאף אחד).
   - אחרת שמור אותו ועדכן את הקבוצה, המונה והסכום.
   - עצור ברגע שנשמרו `max_chunks` hits.
3. החזר Hits **חדשים** עם `dataclasses.replace(hit, rank=i, scores=dict(hit.scores))`, כאשר `i` רץ מ-1 עד n. אל תשנה את ה-hits שבקלט. קלט ריק מחזיר `[]`.

## build_request

### רמז 1: כיוון
זה הפרומפט של כל המערכת, ושלושה שיעורים פוגשים בו: **הסדר** (שיעור 4: החלק הקבוע ראשון, כדי שה-cache יעבוד), **המבנה** (שיעור 1: תוחמים ברורים בין מקורות לשאלה), ו**ה-escaping** (שיעור 24: מסמך שמכיל `</source>` לא יכול לסגור את התגית ולדבר עם המודל). הפורמט צריך להיות מדויק עד התו, כי הטסטים משווים מחרוזת שלמה. התחל מהטסט `test_exact_user_message` ובנה עד שהוא עובר.

### רמז 2: מבנה
כתוב קודם פונקציית עזר שמקבלת מספר מקור ו-Hit ומחזירה את תגית ה-`<source>` שלו. בתוכה בנה את המאפיינים לפי הסדר, דלג על מה שריק, וצטט כל ערך. אחר כך ב-`build_request`: חבר את המקורות בשורה חדשה (או הטקסט החלופי כשאין מקורות), עטוף אותם ואת השאלה, ובנה את ה-`ChatRequest` עם ה-system כבלוק cache או כמחרוזת.

### רמז 3: האלגוריתם המלא
1. מקור מספר n (מ-1): `c = hit.chunk`. המאפיינים לפי הסדר: `id=str(n)`, `doc=c.doc_id`, `title=c.title`, `section=c.section`, `effective_date=c.effective_date`, `version=c.version`. מדלגים על כל מאפיין שערכו ריק, וכל ערך עובר `quoteattr` (הוא מוסיף את המרכאות בעצמו, ובוחר גרש כשיש מרכאות בערך). מחברים ברווח: `" ".join(f"{k}={quoteattr(v)}" ...)`.
2. התגית: `f"<source {attrs}>\n{escape(c.text, quote=False)}\n</source>"`.
3. `sources = "\n".join(<תגית לכל hit, לפי הסדר>)`, ואם זה ריק: `"(no sources found)"`.
4. `user = f"<sources>\n{sources}\n</sources>\n\n<question>{escape(question, quote=False)}</question>"`.
5. `system = [Block(SYSTEM, cache="5m")]` כש-`cache` אמת, אחרת `SYSTEM`.
6. החזר `ChatRequest(messages=[Message("user", user)], system=system, max_tokens=max_tokens)`.

## resolve_citations

### רמז 1: כיוון
`CITE_RE` (מיובא מ-`acmeqa.citations`) כבר מוצא את כל צורות הסימון, כולל קבוצה כמו "[1, 3]". מה שנשאר לך הוא לפרק כל קבוצה למספרים, לשמור על סדר ההופעה הראשונה בלי כפילויות, ולבדוק שהמספר בטווח. שים לב שהמספרים מתחילים ב-1 ולא ב-0.

### רמז 2: מבנה
עבור על כל ההתאמות של `CITE_RE` בטקסט לפי הסדר. מכל התאמה פרק את התוכן לפי פסיק או נקודה-פסיק למספרים שלמים. החזק קבוצה של מספרים שכבר ראית, כדי לא לחזור על מספר. לכל מספר חדש בנה Citation תקין מתוך ה-chunk המתאים, או Citation לא תקין אם הוא מחוץ לטווח.

### רמז 3: האלגוריתם המלא
1. סימנים: "[2]", וקבוצות "[1, 3]" או "[1;3]". `CITE_RE` תופס את שלוש הצורות. את תוכן הקבוצה מפצלים לפי "," או ";" (למשל `re.split(r"[,;]", group)`) ומנקים רווחים. "[1][3]" הם שני סימנים נפרדים.
2. סדר: לפי ההופעה הראשונה בטקסט. מספר שמופיע שוב לא נוסף שוב.
3. מספר תקין כאשר `1 <= n <= len(context)`. אז `chunk = context[n-1].chunk`, וממלאים כל שדה:
   `Citation(n, True, chunk.doc_id, chunk_id=chunk.id, title=chunk.title, section=chunk.section or None, effective_date=chunk.effective_date or None, start=chunk.start, end=chunk.end, snippet=snippet_of(chunk.text))`
4. מספר לא תקין (0, או גדול ממספר המקורות): `Citation(n=n, valid=False)`, ושאר השדות `None`. המודל המציא מקור; הממשק מציג אותו באדום וההערכה סופרת אותו.
5. אין סימנים בכלל: מחזירים `[]`.

## route_question

### רמז 1: כיוון
רשימות ה-regex ‏`DOC_CUES`, `AGG_CUES` ו-`ENTITY_CUES` כבר קיימות ב-`acmeqa/router.py`; אתה רק מפעיל אותן ומחליט. המלכודת: הדפוסים כתובים באותיות קטנות, ולכן צריך לנרמל את השאלה לפני החיפוש. וחשוב גם הסדר: ניסוח של מדיניות גובר על כל השאר.

### רמז 2: מבנה
נרמל את השאלה פעם אחת. לכל אחת משלוש הרשימות אסוף, לפי סדר הרשימה, את הטקסט שכל דפוס תפס (רק דפוסים שתפסו משהו). אחר כך החלט בשלושה מקרים: יש התאמות של מסמכים, יש גם צבירה וגם ישות, או אף אחד מהם. לכל מקרה יש `reason` קבוע ורשימת `matched` משלו.

### רמז 3: האלגוריתם המלא
1. נרמול: `q = " ".join(question.lower().split())`.
2. לכל regex בכל אחת משלוש הרשימות הפעל `re.search(pattern, q)`. לכל דפוס שתפס, אסוף את `m.group(0)` לפי סדר הרשימה. כך מתקבלות שלוש רשימות: doc, agg, entity.
3. אם יש לפחות התאמה אחת של `DOC_CUES`: ‏`Route("docs", "policy/process wording", <רשימת doc>)`.
4. אחרת, אם יש התאמה של `AGG_CUES` **וגם** של `ENTITY_CUES`: ‏`Route("data", "aggregate over a table entity", <agg> + <entity>)`.
5. אחרת: ‏`Route("docs", "no aggregate + table entity", <agg> + <entity>)`.

דוגמאות: "How many open P1 tickets do we have right now?" נותן data עם matched ‏["how many", "tickets", "p1"]; "How many sick days do employees in Israel accrue per year?" נותן docs (בגלל המילה "accrue"); "כמה קריאות P1 פתוחות יש כרגע?" נותן data; "What is a Red Folder account?" נותן docs.

## answer_metrics

### רמז 1: כיוון
אלה המדדים של שיעור 13: האם המקור הנכון **הגיע לפרומפט** (context_recall), האם התשובה **ציטטה** את המקורות הנכונים (precision ו-recall של ציטוטים), והאם המערכת **סירבה כשצריך**. כל המדדים הם פעולות על קבוצות, ולכן כדאי להפוך כל רשימה ל-`set` כבר בהתחלה, וכך גם כפילויות נספרות פעם אחת. המלכודת: שאלה שאין לה תשובה בקורפוס מתנהגת אחרת לגמרי.

### רמז 2: מבנה
חלץ מהשאלה שתי קבוצות: המקורות, והגרסאות הישנות מתוך התגיות שמתחילות ב-`stale:`. הפוך גם את מסמכי הפרומפט ואת הציטוטים לקבוצות. אחר כך פצל לשני מקרים: יש מקורות (מחשבים שלושה יחסים, והסירוב הוא טעות), או אין מקורות (שלושת היחסים `None`, והסירוב הוא הדבר הנכון). `stale_cited` לא תלוי במקרה.

### רמז 3: האלגוריתם המלא
1. `srcs = set(q.get("source_ids") or [])`; `stale = {t.split(":", 1)[1] for t in q.get("tags") or [] if t.startswith("stale:")}`; `ctx = set(context_docs)`; `cit = set(cited)`.
2. אם `srcs` לא ריק:
   - `context_recall = len(srcs & ctx) / len(srcs)`;
   - `citation_precision = len(cit & srcs) / len(cit)`, ו-`0.0` כש-`cit` ריק;
   - `citation_recall = len(cit & srcs) / len(srcs)`;
   - `abstain_ok = not refused`.
3. אחרת: שלושת היחסים `None`, ו-`abstain_ok = refused`.
4. `stale_cited = bool(cit & stale)`.
5. החזר dict עם חמשת המפתחות בדיוק: `context_recall`, `citation_precision`, `citation_recall`, `stale_cited`, `abstain_ok`.

אותו חישוב קיים ב-`evalkit.metrics.citation_scores` משיעור 23. כאן כותבים אותו בעצמך כדי לראות בדיוק מה כל מספר בדוח של ה-eval סופר.
