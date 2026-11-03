# מעבדה 16: Stateful Workflow Orchestration

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

במעבדה הזו אתה בונה את הליבה של **שלב 3 ב-Company Brain**: תהליך אישור של בקשות גישה, כ-workflow עם מצב, ב-**LangGraph**. הבקשה נכתבת בטקסט חופשי, צעד LLM אחד הופך אותה לשדות, כלים של Acme מעשירים אותה, קוד דטרמיניסטי מחליט על המסלול, והתהליך **נעצר ומחכה לאדם** כשהמדיניות דורשת אישור. כל צעד נשמר ב-checkpoint בקובץ SQLite, ולכן אפשר להרוג את התהליך באמצע, להמשיך מאותה נקודה בתהליך חדש, לאשר בקשה מ-CLI נפרד שעה אחר כך, ולחזור אחורה בזמן כדי לנסות "מה היה קורה אילו".

## הכנה

```bash
source .venv/bin/activate
uv pip install -r labs/16-workflows/requirements.txt     # langgraph, langgraph-checkpoint-sqlite
python -m pytest -q                                      # בדיקות הסביבה, כולל tests/test_flowkit.py
python -m pytest -q labs/16-workflows/tests              # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

אם LangGraph לא מותקן, הבדיקות של השיעור מדלגות על עצמן (skip) עם הודעה ברורה, ושאר הסוויטה ממשיכה לעבור.

## מה חדש

- **LangGraph 1.2** (נבדק עם 1.2.19 ו-langgraph-checkpoint-sqlite 3.1.3, נובמבר 2026). מה שתשתמש בו:
  - `StateGraph(State)`: גרף של צמתים וקשתות מעל state מטיפוס TypedDict. כל צומת מחזיר עדכון חלקי, ו-reducer לכל מפתח קובע איך העדכון מתמזג.
  - `add_conditional_edges(node, router, [targets])`: ניתוב לפי פונקציה רגילה שקוראת את ה-state.
  - `compile(checkpointer=SqliteSaver(...))`: checkpoint אחרי כל צעד, לפי `thread_id`.
  - `interrupt(payload)` בתוך צומת, ו-`Command(resume=value)` כדי להמשיך. בהמשך הצומת **רץ שוב מההתחלה**, ו-`interrupt` מחזיר את הערך.
  - `RetryPolicy(max_attempts, initial_interval, backoff_factor, retry_on)` לכל צומת, ו-`error_handler` שרץ כשהניסיונות נגמרו.
  - `get_state_history`, `update_state` ו-`invoke(None, config)` לחזרה בזמן ולהמשך אחרי קריסה.
  - `stream(..., stream_mode=["updates", "custom"], durability="sync")`: אירועי התקדמות בזמן אמת, ושמירה לפני כל צעד הבא.
- **`flowkit/`** (בשורש הריפו) היא חבילת הייחוס של השיעור:
  - `state.py`: ה-state, ה-reducers, והסכמה `IntakeRequest`.
  - `nodes.py`: כל הצמתים, שער האישור ופונקציות הניתוב.
  - `graph.py`: `build_graph(deps, impl=...)`, שמחליף את הפונקציות שלך מ-`mine.py` בפונקציות הייחוס.
  - `runner.py`: התחלה, המשך, סיכום, רשימת ממתינים והיסטוריה.
  - `store.py`: טבלאות ה-audit וה-outbox, ועדכון סטטוס מותנה.
  - `fake.py`: `FakeLLM`, מודל מזויף לעבודה בלי מפתח.
  - `faults.py`: הזרקת timeouts ושגיאות לכלים.
- **`mine.py`** מכיל את הקוד שלך לתרגילים 2, 3 ו-5.

## הנתונים שהתרגילים עובדים עליהם

**המדיניות** (`data/acme/saas_access_policy.md`, והגרסה v2.2 ב-`data/acme/corpus/docs/it-saas-access-v2-2.md`). כל בקשה הולכת לאחד משלושה מסלולים, והמחמיר מנצח:

- **auto_approve:** כלי מהרשימה המאושרת (Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma, GitHub), ברמת read, viewer או member, בלי מידע של לקוחות ובלי מידע פיננסי. מאושר מיד.
- **needs_manager:** מושב בתשלום (editor) או write בכלי מאושר, או כלי שלא ברשימה ואין בו מידע רגיש (למשל Notion). המנהל הישיר מאשר, תוך 2 ימי עבודה.
- **needs_security:** admin או owner, תשתית פרודקשן (aws-production, kubernetes-prod), מערכות עם מידע של לקוחות או מידע פיננסי (salesforce, zendesk, netsuite, hilan-payroll), ושיתוף חיצוני או אפליקציית OAuth על Google Workspace. צוות האבטחה מאשר, תוך 2 ימי עבודה, וההרשאה פגה אחרי 90 יום.

**החוזה** הוא SPEC-006 מ-`labs/06-spec-driven/spec/access-requests.spec.md`. ה-workflow מממש את הדרישות האלה, והבדיקות של תרגיל 8 מסומנות לפיהן:

- **REQ-4 ו-REQ-5:** הניתוב לפי המדיניות, וסטטוס התחלתי: approved ב-auto_approve, אחרת pending. כאן הניתוב הוא `check_policy` של v2.2.
- **REQ-8:** מי רשאי לאשר. ב-needs_manager זה המנהל הישיר או צוות האבטחה. ב-needs_security רק צוות האבטחה.
- **REQ-9:** אי אפשר לאשר בקשה של עצמך, ומי שאין לו סמכות לא משנה כלום.
- **REQ-10:** בקשה סגורה נשארת סגורה.
- **REQ-11:** כל שינוי סטטוס נרשם, עם request_id, actor, from_status ו-to_status.
- **שינוי מכוון לעומת v1:** יש כאן גם rejected (דחייה עם הערה חובה) ו-expired (כשאף אחד לא החליט בזמן). ב-SPEC-006 v1 אלה היו "מחוץ לתחום".

**הארגון** (`data/acme/corpus/structured/acme.db`, נפתח לקריאה בלבד דרך הכלים של `toolkit/`):

- Dana Levi (E016, `dana.levi@acme.example`) היא Engineering Team Lead. המנהלת שלה היא Michal Ben-David (E005, VP Engineering).
- Noa Cohen (E076) היא מעצבת. המנהלת שלה היא Hila Tzur (E074).
- צוות האבטחה (team `security`): Tamar Golan (E062, CISO), Lior Ashkenazi (E063), Neta Yosef (E064), Ruth Malka (E065).
- Itai Barak (E009) הוא ראש צוות אחר, ולא המנהל של דנה. הוא שימושי לבדיקת סירוב.

**שמונה הבקשות לדוגמה** (`labs/16-workflows/data/requests.jsonl`):

- **r1:** Avital Tal מבקשת read ב-Jira. צפוי: auto_approve, ומאושר מיד.
- **r2:** Dana Levi מבקשת מושב editor ב-Figma. צפוי: needs_manager, ממתין ל-E005.
- **r3:** Barak Mizrahi (מכירות) מבקש read ב-Salesforce. צפוי: needs_security, כי זו מערכת עם מידע של לקוחות.
- **r4:** Tomer Shani מבקש admin ב-aws-production ל-7 ימים. צפוי: needs_security.
- **r5:** Noa Cohen מבקשת חשבון member ב-Notion. צפוי: needs_manager, ממתין ל-E074.
- **r6:** Amit Gabay מבקש גישה ל-GitHub בשביל "Yossi Cohen", שלא קיים. צפוי: needs_info.
- **r7:** Barak Dahan מבקש read ב-Jira, שכבר יש לו. צפוי: already_granted.
- **r8:** Alon Sasson רוצה לחבר אפליקציית OAuth ל-Google Workspace כדי לשתף עם סוכנות חיצונית. צפוי: needs_security, בגלל השיתוף החיצוני.

**הקבצים שהמעבדה כותבת** (ב-`labs/16-workflows/results/`, לא נכנס ל-git):

- `checkpoints.db`: ה-checkpoints של LangGraph, כל thread וכל צעד.
- `requests.db`: הטבלה `access_requests` של toolkit, ולצידה `flow_audit` ו-`flow_outbox` של flowkit.
- `python labs/16-workflows/run.py --reset` מוחק את שני הקבצים.

## הגרף

```
START -> intake -[needs_info]-> notify
                -> enrich -[needs_info | already_granted]-> notify
                          -> policy -> file_request -[approved]-> notify
                                                    -[pending_manager]-> manager_approval
                                                    -[pending_security]-> risk_summary -> security_approval
manager_approval  -[refused]-> manager_approval   -[timeout]-> escalate -> risk_summary
                  -[approve | reject]-> apply_decision
security_approval -[refused]-> security_approval  -[approve | reject | timeout]-> apply_decision
apply_decision -> notify -> END
```

יש רק שני צעדים של LLM: `intake` (טקסט לשדות, עם llmkit.structured) ו-`risk_summary` (סיכום לסוקר האבטחה). כל השאר קוד דטרמיניסטי וכלים.

## התרגילים

**1. קרא את הגרף והרץ אותו.** הרץ את `--show-graph` והדבק את ה-Mermaid ב-mermaid.live. אחר כך הרץ את כל שמונה הבקשות במצב offline, וקרא את הזרם: השורות עם `>` הן עדכונים שצומת סיים לכתוב, השורות עם `.` הן אירועי התקדמות מתוך הצומת, ו-`||` היא עצירה בשער אישור. ענה: כמה קריאות LLM היו לכל בקשה, ולמה ל-r1 יש אחת ול-r4 שתיים? באיזה צומת נעצרה כל בקשה?

```bash
python labs/16-workflows/run.py --show-graph
python labs/16-workflows/run.py --all
```

**2. reducers וניתוב (קוד).** ממש ב-`mine.py` את `merge_audit` (צירוף אירועים בלי כפילויות לפי id), את `add_usage` (סכימה של שימוש ב-LLM), ואת שתי פונקציות הניתוב, `route_after_file` ו-`route_after_gate`. הבדיקה האחרונה מריצה את הגרף כולו עם ה-reducers שלך.

```bash
python -m pytest -q labs/16-workflows/tests/test_ex2_state.py
python labs/16-workflows/run.py --all --mine ex2 --reset && python labs/16-workflows/run.py --all --mine ex2
```

**3. הצמתים (קוד, עם LLM מזויף).** ממש את `intake_node` (‏complete_structured עם `IntakeRequest`, תיקון אחד, ו-needs_info כשנכשל), את `policy_node` (‏`check_policy` בלבד, בלי LLM), ואת `file_request_node` (תופעת הלוואי, עם מפתח idempotency, והעלאת המסלול כשיש שיתוף חיצוני שה-toolkit לא רואה). הבדיקות קוראות לצמתים ישירות עם `FakeLLM(replies=[...])`, כולל תשובה לא תקינה ותיקון, ואחר כך מריצות אותם בתוך הגרף.

```bash
python -m pytest -q labs/16-workflows/tests/test_ex3_nodes.py
```

**4. להרוג באמצע ולהמשיך.** שלושה ניסויים:
- `--crash-in file_request` מפיל את התהליך עם `os._exit(137)` אחרי שהבקשה כבר נרשמה ב-requests.db, אבל לפני שה-checkpoint של הצעד נשמר. ב-`--status` תראה שהצעד הבא עדיין file_request. ב-`--resume` הצומת רץ שוב, וה-toolkit מחזיר את אותה רשומה עם `deduplicated`. בלי מפתח ה-idempotency הייתה כאן רשומה כפולה.
- `--slow 3` נותן לך שלוש שניות בכל צומת. הרוג את התהליך ביד מטרמינל אחר (`kill -9`) או עם Ctrl+C, והמשך עם `--resume`.
- חזור על הקריסה עם `--durability exit`, ואז עם `async`. מה נשמר בכל מצב? למה עם exit אין ממה להמשיך, ומה בכל זאת מגן עליך אם תריץ את אותו thread מחדש?

```bash
python labs/16-workflows/run.py --sample r2 --crash-in file_request
python labs/16-workflows/run.py --status r2
python labs/16-workflows/run.py --resume r2
python labs/16-workflows/run.py --sample r1 --slow 3          # kill -9 <pid> from another terminal, then:
python labs/16-workflows/run.py --resume r1
python labs/16-workflows/run.py --sample r4 --thread r4x --crash-in file_request --durability exit
python labs/16-workflows/run.py --resume r4x
```

**5. שער האישור (קוד) ו-CLI של מאשר.** ממש את `approval_gate`: ‏`interrupt(gate_payload(...))`, ואחר כך בדיקה של התשובה לפי REQ-8 ו-REQ-9 ודחייה עם הערה חובה. הסמכות נקבעת לפי הנתונים של Acme ולא לפי מה שהמאשר טוען על עצמו. אחר כך הפעל את ה-CLI. כל פקודה היא תהליך חדש שטוען את ה-thread מהדיסק. נסה לאשר בתור דנה עצמה, בתור Itai Barak, ובסוף בתור Michal. בבקשה r4 נסה לאשר בתור מנהלת, ואחר כך דחה בתור Neta מצוות האבטחה. ב-r5 שלח timeout פעמיים: מה קרה אחרי הראשון, ומה אחרי השני?

```bash
python -m pytest -q labs/16-workflows/tests/test_ex5_gate.py
python labs/16-workflows/approve.py pending --mine ex5
python labs/16-workflows/approve.py show r2
python labs/16-workflows/approve.py decide r2 --as dana.levi@acme.example --approve --mine ex5
python labs/16-workflows/approve.py decide r2 --as E009 --approve --mine ex5
python labs/16-workflows/approve.py decide r2 --as michal.ben-david@acme.example --approve --comment "ok for Q4" --mine ex5
python labs/16-workflows/approve.py decide r4 --as E005 --approve --mine ex5
python labs/16-workflows/approve.py decide r4 --as neta.yosef@acme.example --reject --comment "use the scoped migration role" --mine ex5
python labs/16-workflows/approve.py timeout r5 && python labs/16-workflows/approve.py timeout r5
python labs/16-workflows/approve.py audit r2
```

**6. חזרה בזמן.** הצג את ההיסטוריה של thread (כל checkpoint, עם step, source, הצומת הבא והסטטוס). אחר כך צור fork מהנקודה שלפני `policy`, עם `access_level=viewer` במקום editor: המסלול משתנה ל-auto_approve. שים לב לשני דברים. ההיסטוריה הישנה לא נמחקה, וה-fork הוא ענף חדש עם checkpoint אב. וב-requests.db יש עכשיו **שתי** רשומות, כי ה-fork הריץ שוב את file_request עם מפתח חדש. לסיום, `replay` לפני risk_summary מריץ שוב את צעד ה-LLM. עם מודל אמיתי תקבל ניסוח אחר.

```bash
python labs/16-workflows/run.py --sample r2 --thread r2t
python labs/16-workflows/timetravel.py history r2t
python labs/16-workflows/timetravel.py fork r2t --before policy --set access_level=viewer
python labs/16-workflows/timetravel.py history r2t
python labs/16-workflows/run.py --sample r4 --thread r4t
python labs/16-workflows/timetravel.py replay r4t --before risk_summary
```

**7. הזרקת תקלות ו-retries ברמת הצומת.** `--fault timeout:get_system_info:2` גורם לשתי הקריאות הראשונות לכלי לחרוג מה-timeout (0.2 שניות). הצומת enrich זורק `ToolUnavailable`, וה-`RetryPolicy` שלו מריץ אותו שוב, כולו, כולל ה-lookup שכבר הצליח. עם `:5` הניסיונות נגמרים, ה-`error_handler` מעביר את הבקשה ל-failed, ו-notify מודיע לעובד. שים לב ש-`retry_on=ToolUnavailable` מוגדר במפורש. ברירת המחדל של LangGraph לא מנסה שוב על OSError, ו-TimeoutError הוא תת-מחלקה של OSError. ענה: למה file_request בטוח ל-retry, ולמה intake לא מקבל RetryPolicy משלו?

```bash
python labs/16-workflows/run.py --sample r4 --thread r4f --fault timeout:get_system_info:2
python labs/16-workflows/run.py --sample r1 --thread r1f --fault timeout:check_policy:5
python labs/16-workflows/run.py --sample r1 --thread r1e --fault error:check_policy:1
```

**8. בדיקות ל-workflow, והשוואה ל-agent חופשי.** שני חלקים:
- `test_ex8_contract.py` מריץ את הגרף כולו עם כל החלקים שלך ומודל מזויף, ובודק את SPEC-006: כל דוגמה מגיעה לסטטוס הנכון, שום דבר שצריך אדם לא מאושר בלעדיו, audit לכל שינוי, בקשה סגורה נשארת סגורה, retry על timeout, ו-needs_info כשהטקסט לא קריא. בתחתית הקובץ יש שתי בדיקות שאתה כותב: הסלמה שמסתיימת באישור של צוות האבטחה, ו-fork שמריץ שוב תופעת לוואי.
- `compare.py` מריץ את אותן שמונה בקשות פעם דרך ה-workflow ופעם דרך agent חופשי: הלולאה משיעור 14, עם כל ששת הכלים ואישור אוטומטי. במצב offline ה-agent רץ מול mockllm, וזה מראה רק את המכניקה. ההשוואה האמיתית היא על Haiku 5.5 עם `--repeat 3`. השווה בין השניים: כמה תוצאות נכונות, כמה קריאות וטוקנים, כמה רצפי צעדים שונים לאותה בקשה, וכמה תשובות של ה-agent אומרות "approved" כשהרשומה עדיין ממתינה. תכתוב לי מה מדדת.

```bash
python -m pytest -q labs/16-workflows/tests
python labs/16-workflows/compare.py
python labs/16-workflows/compare.py --model anthropic:claude-haiku-5-5 --repeat 3
python labs/16-workflows/run.py --all --model anthropic:claude-haiku-5-5 --reset && python labs/16-workflows/run.py --all --model anthropic:claude-haiku-5-5
```

## כללים

- המעבדה כולה על Haiku 5.5 עולה בערך 2 עד 5 סנטים. רוב העלות היא ההשוואה עם `--repeat 3`, כי ה-agent שולח את הגדרות ששת הכלים (כ-1,450 טוקנים) בכל סבב. ה-workflow שולח רק שתי קריאות קטנות.
- את קוד הייחוס ב-`flowkit/nodes.py` וב-`flowkit/state.py` אל תקרא לפני שהבדיקות שלך עוברות.
- `--model` ברירת המחדל הוא `fake`, שעובד בלי מפתח ובחינם. אפשר לקבוע אחרת עם משתנה הסביבה `FLOW_MODEL`.
- כל פקודה של `approve.py` ו-`timetravel.py` מקבלת `--model` (בשביל risk_summary אחרי הסלמה או replay) ו-`--mine`.
