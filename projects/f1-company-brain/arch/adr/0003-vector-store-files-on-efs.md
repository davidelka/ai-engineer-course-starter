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

### Option B: Qdrant (lesson 11) as a second service

Qdrant עם payload filters ל-ACL, בקונטיינר נוסף או ב-Qdrant Cloud.

- Good, because HNSW ו-payload filters מתאימים למיליוני קטעים, ו-filter לפני הדירוג נתמך.
- Bad, because עוד שירות עם volume, גיבוי ועוד כ-15 עד 30$ לחודש, בשביל 404 קטעים.
- Bad, because צריך לכתוב מחדש את שכבת ה-ACL כ-payload filter ולבדוק אותה מחדש מול 7 התפקידים.

### Option C: RDS Postgres with pgvector, also for the workflow state

Postgres אחד לווקטורים (pgvector), ל-checkpoints (langgraph-checkpoint-postgres) ולטבלאות הבקשות.

- Good, because מסד אחד עם גיבויים, כמה משימות במקביל, ו-HA.
- Bad, because db.t4g.micro עם אחסון עולה כ-15$ לחודש לפחות, ויותר עם Multi-AZ.
- Bad, because toolkit ו-flowkit כותבים ל-SQLite; המעבר הוא שינוי קוד בספריות של הקורס, לא החלפת הגדרה.

## Decision outcome

Chosen option: "Option A: M1's file index on EFS (no vector database)", because ב-404 קטעים ובמשימה אחת הוא נותן את אותן תוצאות שנמדדו ב-M1, אפס דליפות ACL ואחזור במילישניות, בעלות של סנטים לחודש. נעבור ל-Option C כשנצטרך יותר ממשימה אחת (זמינות, עומס) או יותר מכ-50 אלף קטעים, ול-Option B אם החיפוש יהיה צוואר הבקבוק לפני ה-state.

## Consequences

### Positive

- אין שירות נוסף: הענן מריץ בדיוק את מה שה-eval מדד.
- בקשות שממתינות לאישור שורדות החלפת משימה, deploy וקריסה, כי ה-state על EFS.

### Negative

- משימה אחת ותהליך אחד בלבד: ב-deploy, ה-ECS service עוצר את המשימה הישנה לפני שהחדשה עולה (minimum healthy 0%), כלומר כדקה של חוסר זמינות בכל deploy.
- כלים חיצוניים (python -m cbrain seed) לא יכולים לפתוח את checkpoints.db כשהשירות רץ על EFS: ה-seed עובר דרך POST /admin/seed.
- ה-image של runtime-e5 גדול בכ-1 GB (PyTorch CPU), וזמן ההפעלה הראשונה כולל embedding של 404 קטעים (כדקה ב-0.5 vCPU, הערכה).

## Cost and latency

EFS: כ-$0.30 לחודש לכ-1 GB. Option B היה מוסיף כ-$15 עד $30 לחודש, ו-Option C כ-$15 לחודש לפחות. אחזור offline: p95 של כ-26 ms לכל /ask כולו ב-eval (BM25 ווקטורים מזויפים); עם e5-small ההערכה היא כ-50 עד 100 ms ל-embedding של השאלה ב-CPU. התקציב הוא 250 ms לאחזור.

## Confirmation

- eval הידע ב-AWS זהה ל-eval המקומי באותו embedder: answer_ok ו-context_recall באותם מספרים (הפרש 0).
- אפס דליפות ACL ב-acmeqa eval --parts acl.
- p95 של האחזור (span retrieval) מתחת ל-250 ms ב-SLO report של השבוע הראשון.
- restart יזום של המשימה: כל הבקשות במצב pending נשארות בתיבת האישורים.
