---
id: eng-oncall-scheduler-he
title: הערות כונן - flow-scheduler
department: engineering
doc_type: runbook
version: "1.5"
effective_date: 2026-07-20
owner: Dana Levi
classification: internal
language: he
---

# הערות כונן: flow-scheduler

המסמך הזה נכתב על ידי צוות Engine בשביל מי שנמצא בכוננות engine-oncall. ה-scheduler הוא שירות Tier 1 שנמצא בבעלות צוות Engine (ראש הצוות: דנה לוי), והכוננות שלו משותפת עם flow-engine. ה-runbook הראשי של flow-engine כתוב באנגלית; כאן יש רק את מה שייחודי ל-scheduler.

## איך ה-scheduler עובד, בקצרה

- בכל רגע יש בדיוק עותק אחד שהוא leader, והוא היחיד שמפעיל לוחות זמנים (schedules). שאר העותקים ממתינים.
- ההנהגה נקבעת לפי lease בטבלה ב-PostgreSQL. מאז התקלה של מרץ 2026 כל הודעה שה-scheduler מפרסם נושאת fencing token (מספר ה-epoch של ה-lease), ו-flow-engine דוחה הודעות מ-epoch ישן.
- ה-scheduler מפרסם הודעות ל-topic בשם runs.requested, בדיוק כמו flow-api.

## התראות נפוצות

### SchedulerLeaderLost
אין leader יותר מ-60 שניות. לוחות זמנים לא מופעלים.

1. לבדוק את ה-pods: ‏kubectl -n flow-scheduler get pods
2. לבדוק בלוגים אם יש שגיאות חיבור ל-PostgreSQL. אם כן, להעיר את platform-oncall.
3. אם יש pod תקוע במצב Terminating על node שמתרוקן (draining), למחוק אותו בכוח: ‏kubectl -n flow-scheduler delete pod NAME --grace-period=0 --force. זה הלקח מהתקלה של מרץ.

### TriggerLagHigh
לוחות זמנים מופעלים באיחור של יותר מ-120 שניות.

1. בתחילת כל שעה עגולה, ובמיוחד ב-1 לחודש בבוקר, יש עומס צפוי. איחור של עד 5 דקות שמתאזן תוך רבע שעה הוא תקין.
2. אם האיחור ממשיך לגדול, לבדוק את ה-lag של flow-engine. לפעמים הבעיה היא בכלל אצל ה-engine.

### TriggerDuplicateRate
יותר מ-0.1% מההפעלות הן כפולות במשך 5 דקות. ההתראה הזו נוספה אחרי תקלת מרץ, ואז חלון הזמן שלה היה 15 דקות; היום הוא 5 דקות.

1. לבדוק כמה עותקים חושבים שהם leader (בלוגים, השדה lease_holder).
2. להקטין את ה-deployment לעותק אחד, ולמחוק בכוח pods תקועים.
3. להכריז SEV2 ולפתוח ערוץ ב-#incidents.

## כוננות: פרטים מעשיים

- הסבב שבועי, וההעברה ביום ראשון בשעה 10:00, בערוץ #engine-oncall.
- תגמול כוננות: 350 ש"ח לכל יום חול בכוננות ו-600 ש"ח לכל יום שישי, שבת או חג. התגמול משולם עם המשכורת.
- מי שמקבל קריאה בלילה (בין 00:00 ל-06:00) ועבד יותר משעה רשאי להתחיל את יום העבודה הבא ב-12:00.
- אם צריך עזרה ולא מתקדמים תוך 15 דקות ב-SEV1, להעיר את דנה לוי.

## מה לא לעשות

- לא להגדיל את מספר ה-replicas כדי "לפתור" עומס. ה-scheduler לא בנוי להתרחבות אופקית, ורק ה-leader עובד.
- לא לשנות ידנית את טבלת ה-lease בבסיס הנתונים.
- לא להפעיל מחדש את כל ה-pods בבת אחת בשעה עגולה.

## העברת בעלות?

בפגישת ראשי הצוותים במאי 2026 עלתה הצעה להעביר את ה-scheduler לצוות Platform. ההצעה נדחתה בינתיים, וצוות Engine נשאר הבעלים. אם זה ישתנה, קטלוג השירותים יעודכן קודם.
