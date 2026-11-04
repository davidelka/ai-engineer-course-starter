# ADR-0003: Keep M1's file-based hybrid index (BM25 + NumPy vectors) on EFS, no vector database yet

- Status: accepted
- Date: 2026-11-02
- Deciders: Company Brain (the owner, course project F1)
- Related: projects/m1-knowledge-assistant/acmeqa/ingest.py, lesson 10 (embeddings), lesson 11 (managed vectors: Qdrant, pgvector), deploy/terraform/efs.tf, cbrain/workflow.py (open_saver)

## Context and problem statement

הידע של Company Brain הוא 55 מסמכים של Acme, שנחתכים ל-404 קטעים. M1 בנה אינדקס היברידי בקבצים: BM25 ווקטורים של e5-small (384 ממדים) ב-NumPy, עם manifest אינקרמנטלי ו-ACL כ-where לפני הדירוג. ב-404 קטעים כל המטריצה היא כ-600KB, וחיפוש מלא (brute force) לוקח מילישניות. בענן המערכת רצה כמשימת Fargate אחת, ובאותו מקום צריך לשמור גם את ה-state של ה-workflow (checkpoints.db ו-requests.db, SQLite). Acme צפויה לגדול לכמה אלפי מסמכים בשנה הקרובה, לא למיליונים.

השאלה: האם להעביר את החיפוש הווקטורי למסד וקטורי (Qdrant, pgvector), ואיפה שומרים את האינדקס וה-state בענן?

## Decision drivers

- ה-ACL חייב לרוץ לפני הדירוג, ובדיוק כמו ב-M1: אפס דליפות על 7 התפקידים הוא תנאי.
- עלות ותפעול: משימה אחת, בלי עוד שירות מנוהל, ב-200 עובדים.
- latency: p95 של אחזור מתחת ל-250 ms (תקציב ה-latency ב-arch YAML).
- להתחיל מחדש משימה בלי לאבד בקשות שממתינות לאישור.

## Considered options

### Option A: M1's file index on EFS (no vector database)

ה-brain בונה את האינדקס בהפעלה הראשונה לתוך STATE_DIR/index על EFS, ובהפעלות הבאות טוען אותו (ה-manifest מזהה שאין שינוי). checkpoints.db ו-requests.db יושבים באותו EFS.

- Good, because אותו קוד ואותן תוצאות כמו ב-M1 וב-eval: אפס קוד חדש, וה-ACL כבר נבדק.
- Good, because EFS עולה כ-0.30$ ל-GB בחודש, והכל יחד פחות מ-1 GB.
- Bad, because brute force לא מתאים לגדילה של פי 100: מעל כ-100 אלף קטעים צריך אינדקס ANN.
- Bad, because SQLite על מערכת קבצים ברשת: LangGraph מפעיל WAL, וה-wal-index בזיכרון משותף לא עובד על network filesystem (sqlite.org/wal.html). פותחים את checkpoints.db ב-locking_mode=EXCLUSIVE, ואז תהליך אחד בלבד יכול לגשת לקובץ.
- Bad, because אין זמינות גבוהה: משימה אחת בלבד. קריסה של המשימה או בעיה ב-AZ שלה היא השבתה עד שמשימה חדשה עולה ועוברת את ה-health check (כמה דקות, הערכה), וכל deploy הוא השבתה מתוכננת (minimum_healthy_percent=0).
- Bad, because EXCLUSIVE mode על EFS אמיתי לא נבדק מעולם: הבדיקה בפרויקט רצה על דיסק מקומי ומוודאת רק שאין קובץ shm. ההתנהגות של נעילות NFS ב-EFS, ובפרט מה קורה אם משימה ישנה עדיין מחזיקה את הקובץ כשחדשה עולה, היא הנחה עד שתרוץ.
- Bad, because הגיבוי היומי של AWS Backup מעתיק קבצים, ולא snapshot עקבי של מסד: גיבוי של קובץ SQLite פתוח יכול לתפוס אותו באמצע כתיבה. אין point-in-time recovery.

### Option B: Qdrant (lesson 11) as a second service

Qdrant עם payload filters ל-ACL, בקונטיינר נוסף או ב-Qdrant Cloud.

- Good, because HNSW ו-payload filters מתאימים למיליוני קטעים, ו-filter לפני הדירוג נתמך.
- Bad, because עוד שירות עם volume, גיבוי ועוד כ-15 עד 30$ לחודש, בשביל 404 קטעים.
- Bad, because צריך לכתוב מחדש את שכבת ה-ACL כ-payload filter ולבדוק אותה מחדש מול 7 התפקידים.

### Option C: RDS Postgres with pgvector, also for the workflow state

Postgres אחד לווקטורים (pgvector), ל-checkpoints (langgraph-checkpoint-postgres) ולטבלאות הבקשות.

- Good, because מסד אחד עם גיבויים עקביים ו-point-in-time recovery, כמה משימות במקביל, deploy מתגלגל בלי השבתה, ו-HA עם Multi-AZ.
- Bad, because עלות (הערכה לפי מחירי us-east-1, נבדק בנובמבר 2026): db.t4g.micro ב-Single-AZ עם 20 GB אחסון הוא כ-14$ לחודש, אבל בלי HA, כלומר בלי היתרון העיקרי. Multi-AZ, שנותן HA, הוא כ-28$ לחודש. Aurora Serverless v2 מתחיל בכ-44$ לחודש במינימום של 0.5 ACU, או קרוב לאפס עם auto-pause, במחיר של כ-15 שניות התעוררות בבקשה הראשונה.
- Bad, because toolkit ו-flowkit כותבים ל-SQLite; המעבר הוא שינוי קוד בספריות של הקורס, לא החלפת הגדרה.

## Decision outcome

Chosen option: "Option A: M1's file index on EFS (no vector database)", because ב-404 קטעים ובמשימה אחת הוא נותן את אותן תוצאות שנמדדו ב-M1, אפס דליפות ACL ואחזור במילישניות, בעלות של סנטים לחודש. המחיר שאנחנו מקבלים במודע: אין HA, יש השבתה קצרה בכל deploy, והמצב EXCLUSIVE על EFS עדיין לא נבדק. לכלי פנימי של 200 עובדים, שבו בקשה ממתינה יכולה לחכות כמה דקות, זה סביר. אילו הדרישה הייתה זמינות בזמן deploy, Option C ב-Multi-AZ (כ-28$ לחודש) היה הבחירה. נעבור ל-Option C כשנצטרך יותר ממשימה אחת (זמינות, עומס) או יותר מכ-50 אלף קטעים, ול-Option B אם החיפוש יהיה צוואר הבקבוק לפני ה-state.

## Consequences

### Positive

- אין שירות נוסף: הענן מריץ בדיוק את מה שה-eval מדד.
- בקשות שממתינות לאישור שורדות החלפת משימה, deploy וקריסה, כי ה-state על EFS.

### Negative

- משימה אחת ותהליך אחד בלבד: ב-deploy, ה-ECS service עוצר את המשימה הישנה לפני שהחדשה עולה (minimum healthy 0%), כלומר השבתה מתוכננת בכל deploy: לפחות כדקה, ועם runtime-e5 (start period של 180 שניות) כמה דקות. הערכה, לא נמדד.
- אין HA: קריסה של המשימה או של ה-AZ שלה היא השבתה עד שמשימה חלופית עולה.
- EXCLUSIVE mode על EFS לא נבדק על EFS אמיתי; זה הדבר הראשון לבדוק בפריסה הראשונה (ראה Confirmation).
- הגיבוי של EFS אינו עקבי ברמת המסד. עותק עקבי דורש את ה-backup API של SQLite (או `VACUUM INTO`) מתוך התהליך שמחזיק את הקובץ, וזה עדיין לא ממומש.
- כלים חיצוניים (python -m cbrain seed) לא יכולים לפתוח את checkpoints.db כשהשירות רץ על EFS: ה-seed עובר דרך POST /admin/seed.
- ה-image של runtime-e5 גדול בכ-1 GB (PyTorch CPU), וזמן ההפעלה הראשונה כולל embedding של 404 קטעים (כדקה ב-0.5 vCPU, הערכה).

## Cost and latency

EFS: כ-$0.30 לחודש לכ-1 GB. Option B היה מוסיף כ-$15 עד $30 לחודש. Option C (הערכות, נבדק בנובמבר 2026): כ-$14 לחודש ב-Single-AZ בלי HA, כ-$28 ב-Multi-AZ, ו-Aurora Serverless v2 מכ-$44 (או כמעט אפס עם auto-pause והתעוררות איטית). אחזור offline: p95 של כ-26 ms לכל /ask כולו ב-eval (BM25 ווקטורים מזויפים); עם e5-small ההערכה היא כ-50 עד 100 ms ל-embedding של השאלה ב-CPU. התקציב הוא 250 ms לאחזור.

## Confirmation

- eval הידע ב-AWS זהה ל-eval המקומי באותו embedder: answer_ok ו-context_recall באותם מספרים (הפרש 0).
- אפס דליפות ACL ב-acmeqa eval --parts acl.
- p95 של האחזור (span retrieval) מתחת ל-250 ms ב-SLO report של השבוע הראשון.
- restart יזום של המשימה: כל הבקשות במצב pending נשארות בתיבת האישורים.
- deploy על EFS אמיתי: המשימה החדשה פותחת את checkpoints.db ב-EXCLUSIVE בלי שגיאת "database is locked", אין קובץ checkpoints.db-shm ב-STATE_DIR, ומשך ההשבתה ב-deploy נמדד ונרשם כאן.
