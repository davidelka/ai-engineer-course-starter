# ADR-0002: The LLM gateway sits between the brain and the providers, in-process for now

- Status: accepted
- Date: 2026-11-02
- Deciders: Company Brain (the owner, course project F1)
- Related: cbrain/gateway.py, labs/25-llm-gateway/policy.yaml, lesson 25 (gatewaykit), arch/company_brain.arch.yaml (component gateway)

## Context and problem statement

Company Brain קורא למודל בשלושה מקומות שונים: תשובה לשאלת ידע (חלק מהקטעים confidential, למשל postmortems של הנדסה), חילוץ וסיכום סיכון ב-workflow, והנתב. מדיניות ה-AI של Acme (sec-data-classification ו-it-ai-usage-he, מקודדת ב-policy.yaml שצוות האבטחה מחזיק) אומרת: confidential רק ל-Anthropic ורק באזורים us ו-eu, restricted לאף מודל. בנוסף צריך תקציב חודשי, audit של כל קריאה, redaction של טלפונים ותעודות זהות, ו-fallback לספק שני לנתונים פנימיים. ב-200 עובדים מדובר בכ-2,400 קריאות מודל בחודש, ובתקציב טוקנים של כ-1$ לחודש לפי מודל העלות, כך שהסיכון העיקרי הוא לא העלות אלא דליפה ומעקב.

השאלה: איפה יושב ה-gateway (gatewaykit), מי מחליט על סיווג הנתונים של כל קריאה, והאם הוא שירות נפרד?

## Decision drivers

- קריאה עם הקשר confidential לא מגיעה לעולם לספק שהמדיניות אוסרת, גם לא ב-fallback.
- מי שיודע את הסיווג הוא מי שאחזר את הקטעים: רק ה-brain יודע אילו מסמכים נכנסו לפרומפט.
- תקציב נפרד לכל מטרה (תשובות, workflow, נתב), כדי שבאג בנתב לא יאכל את תקציב התשובות.
- פשטות תפעולית: משימת Fargate אחת, בלי שירות נוסף לתחזק כל עוד יש אפליקציה אחת.

## Considered options

### Option A: In-process gateway between the brain and the providers

ה-brain בונה Gateway של gatewaykit בתוך התהליך, עם שלושה virtual keys (brain-answer 15$, brain-flow 5$, brain-router 2$ לחודש). אחרי האחזור, ה-brain מחשב את הסיווג של הקריאה (request_classification: הסיווג הגבוה בין הקטעים, לא פחות מ-internal) ומעביר אותו כ-x-data-classification. ה-gateway אוכף את policy.yaml, מסנן, ממשיך ל-fallback רק לפריסות מותרות, ורושם audit.

- Good, because הסיווג מגיע ממי שיודע אותו, והאכיפה ממי שמחזיק את המדיניות: שתי אחריויות נפרדות.
- Good, because אין שירות נוסף: אותו image ואותה משימה, ואותו קוד רץ offline בבדיקות.
- Bad, because ה-gateway של הקורס הוא text-only ובלי streaming: structured outputs עוברים ל-prompt mode, ה-cache breakpoints נעלמים, וזמן הטוקן הראשון שווה לזמן המלא.
- Bad, because אפליקציה שנייה ב-Acme לא יכולה להשתמש בו בלי להעביר אותו לשירות.

### Option B: Gateway in front of the brain (API gateway for employees)

ה-gateway מקבל את הבקשות של העובדים ומעביר אותן ל-brain.

- Good, because נקודה אחת ל-rate limiting של עובדים.
- Bad, because ה-gateway לא רואה את הקטעים שהאחזור בחר, ולכן לא יכול לדעת את הסיווג של הקריאה למודל.
- Bad, because זו שכבה אחרת (API gateway, ALB), לא LLM gateway: את התקציב לפי מודל והמדיניות לפי סיווג היא לא נותנת.

### Option C: A separate gateway service (gatewaykit or LiteLLM) shared by all apps

ה-brain קורא ל-GATEWAY_URL עם keys לכל מטרה.

- Good, because כל אפליקציות ה-AI של Acme עוברות באותה מדיניות ובאותו audit.
- Good, because LiteLLM מעביר streaming, cache_control ו-structured outputs.
- Bad, because שירות נוסף עם מסד נתונים (LiteLLM צריך Postgres לתקציבים), עוד כ-30$ לחודש ב-Fargate ו-ALB פנימי, ועוד hop ברשת.

## Decision outcome

Chosen option: "Option A: In-process gateway between the brain and the providers", because הוא שומר את שתי האחריויות (ה-brain מסווג, ה-gateway אוכף) בלי שירות נוסף, וזה מה שהמדיניות דורשת ב-200 עובדים עם אפליקציה אחת. הקוד כבר תומך ב-Option C (GATEWAY_URL ו-GATEWAY_KEY_*), ונעבור אליו כשאפליקציה שנייה תצטרך את אותה מדיניות, או אם ה-TTFT של מסלול ה-gateway יעבור את יעד ה-SLO.

## Consequences

### Positive

- הקשר confidential לא יכול להגיע לפריסת OpenAI: ה-gateway מסנן פריסות לפני ה-fallback (בדיקה ב-tests/test_f1_company_brain.py).
- לכל מטרה תקציב, ו-402 כשהוא נגמר; ה-brain מציג הודעה ברורה במקום לנסות שוב.
- audit לכל קריאה עם key_id, סיווג, פריסה, טוקנים ועלות, בלי תוכן הפרומפט.

### Negative

- במסלול ה-gateway אין streaming אמיתי: התשובה נשלחת בחלקים אחרי שהיא הושלמה, וה-TTFT גדל.
- structured outputs ב-prompt mode: יותר repairs מאשר ב-constrained decoding. סופרים אותם ב-traces.
- ה-prompt cache לא עובד דרך ה-gateway של הקורס (אין cache_control), כך שהעלות לשאלה גבוהה בכ-30% מהמודל.

## Cost and latency

התקציבים: 15$ + 5$ + 2$ = 22$ לחודש, מול עלות צפויה של כ-$0.80 לחודש בטוקנים (python -m cbrain cost), כלומר מרווח גדול לגידול ולתקלות. בלי prompt cache, שאלה עולה כ-$0.00043 במקום כ-$0.00034. ה-gateway עצמו מוסיף פחות מ-5 ms offline (נמדד ב-traces של ה-eval). TTFT: במסלול direct עם Haiku בערך 0.5 s, במסלול ה-gateway שווה לזמן המלא, כ-2 עד 3 s; יעד ה-SLO הוא p95 של 8 s לשאלה, והוא נשמר.

## Confirmation

- בבדיקה: קריאה עם קטע confidential לא מגיעה לפריסת openai-global ב-100% מהמקרים, גם כשהפריסה הראשונה נופלת.
- ב-audit של חודש ראשון: 100% מהקריאות עם key_id וסיווג, ואפס קריאות restricted שעברו.
- latency: p95 של /ask במסלול ה-gateway מתחת ל-8 s ב-SLO report.
