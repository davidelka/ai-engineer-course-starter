# רמזים לשיעור 6

**איך להשתמש בקובץ הזה.** קודם נסה לבד, רק לפי ה-docstring ב-`mine.py` והבדיקות בתיקייה `tests/`. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, וחזור לנסות. אם עדיין לא הולך, קרא את **רמז 2**, ונסה שוב. **רמז 3** מתאר את האלגוריתם המלא במילים; השאר אותו למקרה שבאמת אין דרך אחרת, ואחריו כתוב את הקוד בעצמך. כל רמז נמצא תחת כותרת משלו, כך שאפשר לעצור אחרי כל אחד.

המימושים של הקורס נמצאים ב-`spectools/lint.py`, `spectools/trace.py` ו-`spectools/contract.py`. כדאי להשוות אליהם רק אחרי שהבדיקות שלך עוברות. מבנה ה-spec המפורסר (`Spec`, `Requirement`, `Criterion`) מתואר ב-`spectools/spec.py`.

בדיקה: `python -m pytest -q labs/06-spec-driven/tests`

## lint_spec

### רמז 1: כיוון

זו לולאה אחת על הדרישות, ובתוכה רצף של בדיקות עצמאיות, כל אחת מוסיפה `Finding` משלה. החלק העדין הוא התאמת מילים: חיפוש תת-מחרוזת פשוט ימצא את "fast" בתוך "breakfast". צריך ביטוי רגולרי עם גבולות מילה, וזכור שיש ברשימות ערכים עם מקף ("user-friendly") ועם רווח ("as needed").

### רמז 2: מבנה

1. שתי פונקציות עזר: אחת שמחזירה אילו מילים מרשימה נתונה מופיעות בטקסט (כל מילה פעם אחת, בסדר הרשימה), ואחת שבודקת אם GIVEN, WHEN, THEN מופיעים כמילים ובסדר הזה.
2. קבוצה (`set`) של מזהים שכבר נראו, לזיהוי כפילויות.
3. לכל דרישה: בדיקות המזהה; אחר כך, אם יש statement, כל בדיקות ה-statement (ואם אין, רק missing-statement); אחר כך בדיקות הקריטריונים.

### רמז 3: האלגוריתם המלא

לכל `r` ב-`spec.requirements`, לפי הסדר:

1. **missing-id**: אם `r.id is None`, `Finding("missing-id", None, ...)`. אחרת, אם המזהה כבר בקבוצה, **duplicate-id** עם `req_id=r.id` (מדווחים על המופע המאוחר). אחרת הוסף לקבוצה.
2. `st = r.statement.strip()`. אם ריק: **missing-statement**, ולא בודקים שום כלל אחר של ה-statement.
3. אם יש statement:
   - **not-ears**: אם אין בו המילה `shall` (גבולות מילה, בלי תלות ברישיות), **או** שהוא לא מתחיל (באותיות קטנות) באחד מ-`"the "`, `"when "`, `"while "`, `"if "`, `"where "`. הרווח חשוב: "Whenever" אינו "WHEN ".
   - **weak-modal**: Finding אחד לכל מילה מ-`WEAK_MODALS` שנמצאה, עם severity `"warning"`, וההודעה מתחילה ב-`'"<word>" in statement'`.
   - **vague-word**: Finding אחד לכל מילה מ-`VAGUE_WORDS` שנמצאה, הודעה `'"<word>" in statement'`.
   - **nfr-not-measurable**: אם `r.kind == "non-functional"` ואין ב-statement אף ספרה (`re.search(r"\d", st)`).
4. **no-criteria**: אם `r.criteria` ריק.
5. לכל קריטריון `c`: `label = c.id` (או `"criterion"` אם אין מזהה). **criterion-not-gwt** אם המילים GIVEN, WHEN, THEN לא מופיעות בסדר הזה (חפש כל אחת אחרי מיקום הקודמת). **vague-word** לכל מילה מעורפלת, הודעה `f'"{w}" in {label}'`, למשל `'"some" in AC-5.1'`.

התאמת מילה: `re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", text, re.I)`. ה-lookarounds במקום `\b` מטפלים נכון במילים עם מקף. כל ה-severities הם `"error"` חוץ מ-weak-modal.

## scan_req_markers

### רמז 1: כיוון

לא מייבאים את קובצי הבדיקה (זה היה מריץ קוד); קוראים אותם כעץ תחביר עם המודול `ast`. ה-decorator `@pytest.mark.req("REQ-1")` הוא בעץ צומת `ast.Call` שה-`func` שלו הוא `ast.Attribute` עם `attr == "req"`. המלכודת: אותו marker יכול להופיע בשלושה מקומות (פונקציה, מחלקה, `pytestmark` ברמת המודול), והמזהים מכל המקומות מצטרפים.

### רמז 2: מבנה

1. פונקציית עזר שמקבלת ביטוי AST ומחזירה את רשימת המזהים אם הוא קריאה ל-`*.mark.req(...)` או `mark.req(...)`, אחרת רשימה ריקה.
2. פונקציית עזר שאוספת קובצי בדיקה מנתיב (קובץ בודד, או חיפוש רקורסיבי בתיקייה).
3. לכל קובץ: פרסר עם `ast.parse`; מצא את המזהים ברמת המודול (`pytestmark`); עבור על הצמתים העליונים: פונקציות test ומחלקות Test עם המתודות שלהן. לכל בדיקה חבר את המזהים מכל הרמות והוסף את ה-node id למילון של קבוצות.
4. בסוף הפוך כל קבוצה לרשימה ממוינת.

### רמז 3: האלגוריתם המלא

1. **קבצים**: אם הנתיב הוא קובץ, הוא עצמו, ו-`<file>` הוא `f.name`. אם תיקייה, `rglob` על `test_*.py` ועל `*_test.py`, ו-`<file>` הוא `f.relative_to(root).as_posix()`.
2. **זיהוי marker**: ביטוי `node` הוא marker של req אם הוא `ast.Call`, ה-`func` שלו הוא `ast.Attribute` עם `attr == "req"`, ו-`func.value` הוא או `ast.Attribute` עם `attr == "mark"` (`pytest.mark.req`) או `ast.Name` עם `id == "mark"` (אחרי `from pytest import mark`). המזהים הם ה-`value` של כל ארגומנט שהוא `ast.Constant` מסוג מחרוזת, כך ש-`req("REQ-1", "REQ-2")` נותן שניים.
3. **רמת מודול**: חפש ב-`tree.body` השמה (`ast.Assign`) ליעד בשם `pytestmark`. אם הערך הוא marker, קח את המזהים שלו; אם הוא `ast.List` או `ast.Tuple`, קח מכל איבר שהוא marker. ה-markers האחרים ברשימה (`pytest.mark.slow`) מתעלמים.
4. **פונקציות**: לכל `ast.FunctionDef` (וגם `AsyncFunctionDef`) ברמה העליונה ששמה מתחיל ב-`test`: המזהים מכל ה-`decorator_list` שלה ועוד מזהי המודול; node id הוא `f"{file}::{name}"`.
5. **מחלקות**: לכל `ast.ClassDef` ששמה מתחיל ב-`Test`: מזהי המחלקה מה-decorators שלה. לכל מתודה בגוף ששמה מתחיל ב-`test`: המזהים שלה ועוד של המחלקה ועוד של המודול; node id הוא `f"{file}::{Class}::{method}"`.
6. decorators אחרים (`parametrize`, `skip`, ...), פונקציות שלא מתחילות ב-`test`, ומחלקות שלא מתחילות ב-`Test` מתעלמים.
7. החזר `{id: sorted(set_of_node_ids)}`.

## build_matrix

### רמז 1: כיוון

כאן אין אלגוריתם קשה: זו "הצלבה" בין שני מקורות, רשימת המזהים של ה-spec ומילון ה-markers מהתרגיל הקודם. שני הפערים הם בדיוק הכיוונים של ההצלבה: דרישה בלי בדיקה, ובדיקה שמצביעה על דרישה שלא קיימת.

### רמז 2: מבנה

לולאה על `spec.ids()` שבונה `Row` לכל מזהה (הכותרת מ-`spec.get(id)`). מתוך השורות, אלה שאין להן בדיקות הן ה-uncovered. אחר כך מעבר על מפתחות ה-markers ובחירת אלה שאינם ב-spec. החזר `Matrix`.

### רמז 3: האלגוריתם המלא

1. `rows`: לכל `rid` ב-`spec.ids()` (כבר בסדר ה-spec, מופע ראשון): `req = spec.get(rid)`, ו-`Row(rid, req.title if req else "", sorted(markers.get(rid, [])))`. ה-`results` נשאר ריק (ברירת המחדל).
2. `uncovered = [r.req_id for r in rows if not r.tests]`, בסדר ה-spec.
3. `known = set(spec.ids())`; `orphans = {k: sorted(v) for k, v in sorted(markers.items()) if k not in known}`, כך שהמפתחות ממוינים.
4. `Matrix(rows=rows, uncovered=uncovered, orphans=orphans)`.

## find_drift

### רמז 1: כיוון

השוואה בין שני מסמכי OpenAPI היא השוואה בין **קבוצות** ברמות שונות: קבוצת הפעולות, קבוצת קודי התשובה לכל פעולה, וקבוצת ה-properties בכל סכמה. הפונקציות ב-`spectools/contract.py` כבר עושות את ה"צנרת" של OpenAPI (נרמול נתיבים, פתרון `$ref`, הסרת עטיפת nullable), כך שאתה יכול להתרכז בהשוואה. המלכודת: כל מסמך פותר את ה-`$ref` שלו מול עצמו, אז תמיד העבר את המסמך הנכון לכל helper.

### רמז 2: מבנה

1. `operations()` לשני המסמכים, והפרשי קבוצות בשני הכיוונים לפעולות חסרות ולא מתועדות.
2. לכל פעולה משותפת: הפרשי קבוצות של קודי תשובה (בלי `"default"`).
3. פונקציית עזר **רקורסיבית** שמשווה שתי סכמות אובייקט: properties חסרים, לא מתועדים, enum שונה, ואז ירידה לתוך כל property משותף (אובייקט או מערך של אובייקטים), עם קידומת נתיב ועומק.
4. קרא לה על ה-request body ועל כל תשובת 2xx משותפת.

### רמז 3: האלגוריתם המלא

כלים מ-`spectools/contract.py`:

- `operations(doc)` מחזירה `{("POST", "/access-requests/{}"): op}`, עם פרמטרי נתיב מנורמלים.
- `json_body_schema(doc, x)` מחזירה את סכמת ה-`application/json` הפתורה של requestBody או של response, או `None`.
- `unwrap(doc, schema)` פותרת `$ref` ומסירה עטיפת `anyOf`/`oneOf` של nullable.
- `enum_values(doc, schema)` מחזירה את קבוצת הערכים המותרים (`enum` או `const`), או `None`.

האלגוריתם:

1. `oc, oi = operations(contract), operations(implemented)`.
2. לכל מפתח ב-`oc` שלא ב-`oi`: `Drift("missing-operation", f"{method} {path}")`. לכל מפתח ב-`oi` שלא ב-`oc`: `"undocumented-operation"`.
3. לכל פעולה בשניהם, `where = f"{method} {path}"`:
   1. `rc`, `ri` = קבוצות קודי התשובה כמחרוזות, בלי `"default"`. `Drift("missing-status", where, code)` לכל קוד ב-`rc - ri` (ממוין), ו-`"undocumented-status"` לכל קוד ב-`ri - rc`.
   2. request body: `json_body_schema` של `requestBody` בכל צד, כל אחד מול המסמך שלו. אם שתיהן לא `None`, השווה עם `where = f"{where} request body"`.
   3. לכל קוד משותף שמתחיל ב-`"2"`: אותו דבר על אובייקט התשובה, עם `where = f"{where} {code} response"`. (מפתחות התשובות יכולים להיות מספרים או מחרוזות; מצא את המפתח שה-`str` שלו שווה לקוד.)
4. **השוואת סכמות** `compare(sc, si, where, prefix, depth)`:
   1. אם `depth > 5`: עצור.
   2. קבל את ה-properties של כל צד (אחרי `unwrap`, מ-`properties` של סכמה מסוג אובייקט). אם לאחד הצדדים אין, עצור.
   3. `Drift("missing-property", where, prefix + name)` לכל property בחוזה שאין בקוד; `"undocumented-property"` להפך.
   4. לכל property בשניהם: אם `enum_values` של שני הצדדים אינם `None` ושונים, `Drift("enum-mismatch", where, f"{prefix}{name}: contract [...] vs code [...]")`. ה-detail חייב להתחיל בנתיב ה-property ונקודתיים.
   5. ירידה: `unwrap` לשני הצדדים. אם שניהם `"type": "array"`, קרא רקורסיבית על ה-`items` שלהם עם `prefix + name + "[]."`; אחרת קרא רקורסיבית על הסכמות עצמן עם `prefix + name + "."`. בשני המקרים `depth + 1`. כך מתקבל נתיב כמו `"items[].status"`.
