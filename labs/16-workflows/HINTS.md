# רמזים למעבדה 16

הקובץ הזה הוא המקום לקבל עזרה כשנתקעים. ה-docstring ב-`mine.py` הוא החוזה: מה הפונקציה מקבלת, מה היא מחזירה, ואילו כללים התוצאה חייבת לקיים. כאן יש לכל פונקציה שלוש רמות של רמזים, מהקטן לגדול. כדאי לנסות קודם לבד. אם נתקעת, קרא רק את **רמז 1** ונסה שוב. אם עדיין לא הולך, קרא את **רמז 2**, ורק אחר כך את **רמז 3**, שמכיל את האלגוריתם המלא. אפשר לעצור אחרי כל רמה.

המימושים המלאים נמצאים ב-`flowkit/` (`state.py` לשני ה-reducers, `nodes.py` לניתוב, לצמתים ולשער האישור, שם הבדיקות עצמן נמצאות ב-`judge_decision`). כדאי להשוות אליהם רק אחרי שהבדיקות שלך עוברות.

## merge_audit

### רמז 1: כיוון

reducer הוא פונקציה ש-LangGraph קורא לה כדי לשלב את מה שצומת החזיר עם הערך הקיים. כאן השילוב הוא "הוסף בסוף, אבל בלי כפילויות לפי `id`". שתי מלכודות: `right` יכול להגיע בשלוש צורות (מילון אחד, רשימה, או `None`), ואסור לשנות את `left`, כי הוא הערך הקיים ב-state.

### רמז 2: מבנה

מתחילים מעותק של `left` (או רשימה ריקה אם הוא `None`). מנרמלים את `right` לרשימה. מחזיקים קבוצה של ה-ids שכבר נמצאים בעותק, ועוברים על האירועים החדשים לפי הסדר: אירוע שה-id שלו כבר בקבוצה מדלגים עליו, ואחרת מוסיפים אותו לרשימה ואת ה-id שלו לקבוצה, כך שגם כפילות בתוך `right` עצמו נתפסת.

### רמז 3: האלגוריתם המלא

1. `out = list(left or [])` (רשימה חדשה; לא משנים את `left`).
2. אם `right is None`, מחזירים את `out`.
3. `seen` = קבוצת ה-`"id"` של האירועים ב-`out`.
4. האירועים החדשים הם `[right]` אם `right` הוא dict, אחרת `list(right)`.
5. לכל אירוע לפי הסדר: אם ה-id שלו ב-`seen`, מדלגים (העותק הראשון מנצח). אחרת מוסיפים את ה-id ל-`seen` ואת האירוע ל-`out`.
6. מחזירים את `out`: האירועים של `left` לפי הסדר, ואחריהם האירועים של `right` שה-id שלהם לא הופיע קודם (ב-`left` או מוקדם יותר ב-`right`).

הסיבה: צומת יכול לרוץ פעמיים לאותו צעד (retry, המשך אחרי קריסה, הרצה חוזרת של שער), וה-ids של האירועים דטרמיניסטיים, ולכן כאן מסננים את הכפילויות.

## add_usage

### רמז 1: כיוון

סכימה של ארבעה מונים, כשכל צד יכול להיות `None` או לחסר מפתחות. `dict.get(key, 0)` הוא הכלי. שים לב שהבדיקות דורשות ש-`cost_usd` יהיה float גם כששני הצדדים ריקים.

### רמז 2: מבנה

מתחילים ממילון חדש עם ארבעת המפתחות באפס (`cost_usd` כ-`0.0`). עוברים על שני הצדדים (כש-`None` הופך למילון ריק), ולכל מפתח מוסיפים את הערך או 0.

### רמז 3: האלגוריתם המלא

1. `out = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}` (מילון **חדש**).
2. לכל `part` ב-`(left or {}, right or {})` ולכל אחד מארבעת המפתחות: `out[k] += part.get(k, 0) or 0`.
3. מחזירים את `out`: תמיד ארבעת המפתחות, ו-`cost_usd` כ-float. (המימוש המלא גם מעגל את העלות ל-8 ספרות אחרי הנקודה, כדי למנוע רעש של נקודה צפה.)

דוגמה: `add_usage({"calls": 1, "cost_usd": 0.1}, {"calls": 2, "input_tokens": 5})` מחזיר `{"calls": 3, "input_tokens": 5, "output_tokens": 0, "cost_usd": 0.1}`.

## route_after_file

### רמז 1: כיוון

פונקציית ניתוב מחזירה **שם של צומת**, לא ערך. היא מסתכלת רק על `state["status"]`. שים לב שבקשה שמחכה לאבטחה לא הולכת ישר לשער אלא קודם לצומת שכותב סיכום סיכונים.

### רמז 2: מבנה

שני מקרים מיוחדים וברירת מחדל. `state.get("status")` מונע קריסה אם המפתח חסר.

### רמז 3: האלגוריתם המלא

- status `"pending_manager"`: מחזירים `"manager_approval"`.
- status `"pending_security"`: מחזירים `"risk_summary"` (הבודק מקבל קודם סיכום שכתב ה-LLM).
- כל דבר אחר (approved, failed, ...): מחזירים `"notify"`.

## route_after_gate

### רמז 1: כיוון

סדר הבדיקות קובע: שגיאה בשער גוברת על כל החלטה. המלכודת: `gate_error` יכול להיות חסר לגמרי או `None`, ושניהם אומרים "אין שגיאה". גם `decision` יכול להיות חסר.

### רמז 2: מבנה

בודקים קודם את `gate_error`. אם יש שגיאה, בונים את שם הצומת משם השער שבתוכה. אחר כך בודקים את ההחלטה: רק פסק זמן בשער של המנהל מוביל להסלמה. כל השאר הולכים ליישום ההחלטה.

### רמז 3: האלגוריתם המלא

1. `err = state.get("gate_error")`. אם הוא dict (לא ריק): מחזירים `f"{err['gate']}_approval"` (אותו שער רץ שוב ועוצר, ומציג את השגיאה).
2. `d = state.get("decision") or {}`. אם `d.get("decision") == "timeout"` וגם `d.get("gate") == "manager"`: מחזירים `"escalate"` (מדיניות v2.2: אין תשובה מהמנהל, ולכן האבטחה בודקת).
3. אחרת (approve, reject, או פסק זמן של אבטחה): מחזירים `"apply_decision"`.

## intake_node

### רמז 1: כיוון

זה הצומת היחיד שבו LLM מחליט משהו, והוא רק מחלץ שדות מטקסט חופשי. כל החלקים כבר מיובאים: `complete_structured`, `IntakeRequest`, `INTAKE_SYSTEM`, `SYSTEMS`, `usage_of` ו-`audit_event`. הטקסט של המשתמש לא אמין, ולכן עוטפים אותו בתגיות כדי שהמודל יידע איפה הוא מתחיל ואיפה הוא נגמר. מלכודת: `StructuredError` לא נזרק החוצה, אלא הופך לסטטוס `needs_info`.

### רמז 2: מבנה

בונים פרומפט שמכיל את השולח ואת הטקסט בתוך `<request>`. קוראים ל-`complete_structured` בתוך try. ב-except בונים עדכון של `needs_info` עם הודעת שגיאה שמכילה את השלב שנכשל, ומוסיפים usage רק אם יש לשגיאה תוצאה. בהצלחה ממירים את הערך למילון, משלימים את העובד מהשולח אם הוא ריק, ומחזירים עדכון חלקי.

### רמז 3: האלגוריתם המלא

1. `prompt = f"Sender: {state['requester']}\n<request>\n{state['text']}\n</request>"`.
2. `res = complete_structured(deps.llm, prompt, IntakeRequest, max_repairs=1, max_tokens=400, system=INTAKE_SYSTEM.format(systems=", ".join(SYSTEMS)))`.
3. ב-`StructuredError exc`: מחזירים `{"status": "needs_info", "error": <טקסט שמכיל את exc.stage>, "audit": [audit_event(state, deps, to="needs_info")]}`, ומוסיפים `"usage": usage_of(exc.result)` כש-`exc.result is not None`. (המימוש המלא כותב `f"could not read the request ({exc.stage})"`; הבדיקה מחפשת את המילה `invalid`, שהיא ה-stage כשהתיקון נכשל.)
4. אחרת `req = res.value.model_dump()`. אם `req["employee"]` ריק, מציבים בו את `state["requester"]` (השולח מבקש לעצמו).
5. מחזירים `{"request": req, "status": "extracted", "usage": usage_of(res), "audit": [audit_event(state, deps, to="extracted")]}`.

## policy_node

### רמז 1: כיוון

העיקרון כאן הוא **דטרמיניזם**: את ה-route קובע הכלי `check_policy`, ולעולם לא ה-LLM. העבודה היא לקרוא לכלי דרך `call_tool` עם הארגומנטים הנכונים ולהחזיר עדכון חלקי. אל תתפוס חריגות: אם הכלי לא זמין, ה-RetryPolicy של הצומת צריך לראות את החריגה.

### רמז 2: מבנה

קריאה אחת ל-`call_tool`, עם מילון של ארבעה ארגומנטים שנלקחים מ-`state["system_info"]` ומ-`state["request"]`, ואז החזרה של מילון עם המדיניות, ה-route, הסטטוס ואירוע audit.

### רמז 3: האלגוריתם המלא

```
pol = call_tool(deps, "check_policy", {
    "system": state["system_info"]["name"], "access_level": state["request"]["access_level"],
    "external_sharing": bool(state["request"].get("external_sharing")),
    "holds_customer_or_financial_data": None})
```

מחזירים `{"policy": pol, "route": pol["route"], "status": "routed", "audit": [audit_event(state, deps, to="routed")]}`. נותנים ל-`ToolUnavailable` לעבור הלאה (ה-RetryPolicy של הצומת מנסה שוב).

## file_request_node

### רמז 1: כיוון

זה צומת עם **תופעת לוואי** (כתיבה למסד הנתונים), ולכן הוא חייב להיות בטוח להרצה כפולה. הכלי `create_access_request` כבר יודע לזהות כפילות לפי `idempotency_key`, ו-`idempotency_key(state)` כבר קיים. החלק השני הוא החמרת ה-route: הכלי לא רואה שיתוף חיצוני, ולכן ייתכן שה-route שלו מקל יותר מזה של ה-workflow.

### רמז 2: מבנה

קוראים לכלי עם המפתח. לוקחים את הסטטוס מהרשומה. אם ה-workflow דורש אבטחה והרשומה לא, מעדכנים את השורה במסד (`store.set_status` עם הסטטוס הצפוי, כדי שהעדכון יהיה מותנה) ובונים רשומה מעודכנת. אחר כך בונים אירוע audit עם הרשומה החדשה, כותבים אותו למסד כשורה קבועה, ומחזירים עדכון חלקי.

### רמז 3: האלגוריתם המלא

1. קוראים לכלי:

   ```
   rec = call_tool(deps, "create_access_request", {
       "employee": state["employee"]["id"], "system": state["system_info"]["name"],
       "access_level": state["request"]["access_level"],
       "justification": state["request"].get("justification") or "(none given)",
       "duration_days": state["request"].get("duration_days"),
       "idempotency_key": idempotency_key(state)})
   ```

   אותו מפתח מחזיר את השורה הקיימת עם `rec["deduplicated"] == True`.
2. `status = rec["status"]` (approved, pending_manager או pending_security). הכלי לא רואה את `external_sharing`, ולכן ה-route שלו יכול להיות מקל יותר מ-`state["route"]`. אם `state["route"] == "needs_security"` וגם `rec["route"] != "needs_security"`:
   - `status = "pending_security"`;
   - `store.set_status(deps.requests_db, rec["id"], expected=rec["status"], to=status, approver="security-team", route="needs_security")`;
   - `rec = {**rec, "status": status, "route": "needs_security"}`.

   (המימוש המלא מטפל גם ב-needs_manager מעל auto_approve, עם המנהל כמאשר; אתה לא חייב.)
3. `ev = audit_event({**state, "record": rec}, deps, to=status, frm=None)`, ואז `store.write_audit(deps.requests_db, ev)`: שורת audit קבועה, אידמפוטנטית לפי `ev["id"]`.
4. מחזירים `{"record": rec, "status": status, "audit": [ev]}`.

## approval_gate

### רמז 1: כיוון

הדבר החשוב ביותר להבין כאן הוא איך `interrupt` עובד: בפעם הראשונה הוא **עוצר** את הגרף ושולח את ה-payload לקורא. כשמישהו ממשיך עם `Command(resume=value)`, LangGraph מריץ את הצומת **שוב מההתחלה**, והפעם `interrupt()` מחזיר את `value`. לכן שום דבר עם תופעת לוואי לא יכול לבוא לפניו. אחרי זה הכול אימות: הסמכות נקבעת לפי המדריך של Acme (`lookup_actor`), ולעולם לא לפי מה שהקורא טוען על עצמו.

### רמז 2: מבנה

השורה הראשונה היא `interrupt`. אחר כך פונקציית עזר קטנה שמחזירה `gate_error` עם הודעה, ורשימה של בדיקות שכל אחת מחזירה מיד: האם ההחלטה חוקית; פסק זמן (שמדלג על בדיקות המאשר); האם המאשר קיים; האם הוא מחליט על הבקשה של עצמו; האם יש לו סמכות לשער הזה; והאם לדחייה יש הערה. רק אם הכול עבר, בונים את ההחלטה. כדאי לנרמל את ההערה (strip) פעם אחת בהתחלה.

### רמז 3: האלגוריתם המלא

1. `answer = interrupt(gate_payload(state, gate))`.
2. מאמתים את התשובה (מילון `{"decision", "actor", "comment"}`). תשובה לא חוקית מחזירה `{"gate_error": {"gate": gate, "message": <למה>}}`, והניתוב מחזיר את הגרף לאותו שער, שעוצר שוב. הכללים, לפי הסדר:
   - א. `decision` אינו אחד מ-`("approve", "reject", "timeout")` (או שהתשובה אינה dict): לא חוקי. ההודעה חייבת להכיל את המילה `decision` (המימוש המלא: `"answer must be a dict with decision approve, reject or timeout"`).
   - ב. `decision == "timeout"` (נשלח מטיימר ה-SLA): חוקי, בלי בדיקת מאשר. מחזירים `{"gate_error": None, "decision": {"gate": gate, "decision": "timeout", "actor_id": "system:sla-timer", "actor_name": "SLA timer", "comment": <ההערה, או טקסט ברירת מחדל כמו "no decision in time">}}`.
   - ג. `actor = lookup_actor(deps, answer["actor"])` הוא `None`: לא חוקי, ההודעה מכילה `unknown` (`"unknown approver"`).
   - ד. `actor["id"]` הוא `state["employee"]["id"]` או `state["requester_info"]["id"]`: לא חוקי, ההודעה מכילה `"own request"`.
   - ה. השער הוא `"security"` ו-`actor["team"] != deps.security_team`: לא חוקי, ההודעה מכילה `"only the security team"`.
   - ו. השער הוא `"manager"` והמאשר אינו `state["employee"]["manager"]["id"]` וגם אינו בצוות האבטחה: לא חוקי, ההודעה מכילה `"manager"`.
   - ז. `decision == "reject"` עם הערה ריקה: לא חוקי, ההודעה מכילה `"comment"`.
3. חוקי: מחזירים `{"gate_error": None, "decision": {"gate": gate, "decision": answer["decision"], "actor_id": actor["id"], "actor_name": actor["name"], "comment": <ההערה אחרי strip>}}`.

(המימוש המלא גם כותב אירוע audit לכל סירוב, עם id שסופר את הסירובים הקודמים. זה לא נדרש בבדיקות.)
