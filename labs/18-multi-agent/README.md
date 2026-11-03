# מעבדה 18: Multi-Agent Patterns

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל. אין תלויות חדשות. הכל בנוי מעל agentkit משיעור 15, toolkit משיעור 14, llmkit.structured משיעור 3 והאינדקס BM25 של ragkit משיעור 9. כלי הכוננות מגיע מ-`mcpkit/oncall.py` של שיעור 17, אבל לא צריך את חבילת `mcp` כדי להריץ את המעבדה.

## הכנה

```bash
source .venv/bin/activate
python -m pytest -q tests/test_multikit.py       # בדיקות הסביבה של multikit
python -m pytest -q labs/18-multi-agent/tests    # התרגילים שלך: בהתחלה הן נכשלות, וזה תקין
```

## מה חדש

- **`multikit/`** היא חבילה חדשה. כל דפוס בה בנוי מ-agents רגילים של agentkit, ולכן כל agent משאיר trajectory רגיל, כמו בשיעור 15:
  - `specialists.py` מגדיר שלושה מומחים, ולכל אחד יש פרומפט משלו וסט כלים קטן משלו:
    - **hr**: הכלים `search_hr_policies` (חיפוש BM25 ב-14 מסמכי משאבי האנוש) ו-`read_document`.
    - **it_access**: ששת הכלים משיעור 14, כלומר `lookup_employee`, `get_system_info`, `list_access_grants`, `check_policy`, `read_document` ו-`create_access_request`. לכלי האחרון יש תופעת לוואי, והוא דורש אישור אנושי.
    - **oncall**: הכלים `get_oncall_for_service` (מקטלוג השירותים, שיעור 17), `search_eng_docs` ו-`read_document`.
    - `make_single` בונה את קו הבסיס: agent אחד עם כל עשרת הכלים ופרומפט שמכסה את שלושת התחומים.
  - `router.py`: הנתב מסווג את הבקשה בקריאה מובנית אחת. הסכמה היא `RouteDecision`, עם השדות reason, routes, confidence ו-clarifying_question. אחר כך **קוד** מחליט, ב-`decide_route`, אם לנתב או לשאול שאלת הבהרה.
  - `supervisor.py`: ה-supervisor הוא Agent שהכלים היחידים שלו הם `delegate_to_hr`, `delegate_to_it_access` ו-`delegate_to_oncall`. כל קריאה כזו מריצה worker עם הקשר נקי, שמכיל רק את ה-task שה-supervisor כתב. כמה קריאות באותו צעד רצות במקביל. ל-`verify` יש שלושה מצבים: `none`, `llm` (ה-worker מחזיר גם את הראיות שלו) ו-`code` (קוד משווה את התשובה לראיות).
  - `handoff.py`: סוכן triage מעביר את השליטה למומחה הראשון, וכל מומחה מעביר למומחה הבא עם סיכום מובנה (`HandoffSummary`). `make_handoff_brief` בודק את הסיכום לפני שההעברה מותרת.
  - `fanout.py`: מתכנן מפרק שאלת מחקר לתתי-שאלות, workers עונים עליהן במקביל עם ציטוטים, ושלב סינתזה כותב תשובה אחת. בסוף נבדק שכל ציטוט הוא מסמך שמישהו באמת קרא.
  - `critic.py`: כותב ומבקר, עם rubric ומספר סבבים מוגבל. מה שקוד יכול לבדוק נבדק בקוד.
  - `attribution.py`: כל ריצה מרובת agents היא עץ של trajectories. כל רשומת `run` מקבלת את השדות `role` (coordinator או worker) ו-`parent_run_id`. `aggregate_runs` מסכם טוקנים, עלות וזמן לכל agent, ו-`merge_for_scoring` מאחד את העץ כדי ש-`agentkit.score_trajectory` ידרג אותו מול **אותו זהב** של שיעור 15.
  - `fake.py`: "מודלים" מזויפים לכל תפקיד. הם דטרמיניסטיים וחינמיים, והטוקנים שלהם **מוערכים** ומתומחרים כמו Haiku 5.5. הם מראים את **המנגנון**: מי קורא למי, כמה הקשר כל agent סוחב, ואיפה כשל מתפשט. הם לא מראים את שיקול הדעת של מודל אמיתי.
  - `patterns.py`: הפונקציה `build(pattern, model)` מחזירה כל דפוס, עם fake או עם מודל אמיתי. `run_set` מריץ סט משימות, ו-`attribute_failure` מנסה להצביע על ה-agent שגרם לכשל.
- **`mine.py`** מכיל את הקוד שלך לתרגילים 2, 4 ו-6.

## הנתונים שהתרגילים עובדים עליהם

**סט המשימות** הוא `labs/18-multi-agent/data/tasks.jsonl`, עם 23 משימות. לכל משימה יש זהב בפורמט של שיעור 15 (outcome, request, answer_contains, required_tools, forbidden_tools, optimal_calls), ועוד שדה חדש, `domains`: התחומים שהמשימה באמת צריכה.

- **t01 עד t15** הן 15 משימות הגישה משיעור 15, ולכולן `domains: ["it_access"]`. בקצרה: t01 (Dana, admin ב-aws-production ל-3 ימים, needs_security, לפתוח בקשה), t02 (Avital, Figma editor, needs_manager), t03 (האם ל-Lena יש Salesforce, לא לפתוח), t04 (Sapir, admin ב-Miro, רק אם auto_approve), t05 (איזו Shani? צריך לשאול), t06 (עובד שלא קיים), t07 (השוואת github ו-aws-production), t08 (אילו הרשאות יש ל-E016), t09 (Yonatan, GitHub write אם אין לו), t10 (ל-Dana כבר יש GitHub write), t11 (שאלה על מסמך המדיניות), t12 (Keren, NetSuite editor ל-30 יום), t13 (Hila, Zoom member), t14 (OAuth ל-Google Workspace, לא לפתוח) ו-t15 (Itai, Datadog read).
- **x01 עד x08** הן שמונה משימות חדשות, וכמעט כולן חוצות תחומים. זה הטקסט המלא והזהב של כל אחת:
  - **x01** (oncall ואז it_access): "Which on-call rotation covers flow-scheduler, and what is its acknowledge target? Dana Levi needs admin on kubernetes-prod for 2 days to debug the scheduler: open the request." בזהב צריכה להיפתח בקשה: E016, kubernetes-prod, admin, 2 ימים, needs_security. התשובה חייבת להכיל `engine-oncall` ו-`needs_security`. אופטימלי: 4 קריאות.
  - **x02** (hr ואז it_access): "How many unused vacation days can an employee carry over into next year, and until when? Separately, does Avital Tal already have Figma access? Do not file anything." אסור לפתוח בקשה. התשובה חייבת להכיל `5 unused days` ו-`figma`.
  - **x03** (oncall ואז hr): "Ofer Levi is on call for billing-service and is sick for three days. Who leads the billing-service team, and when is the billing on-call handover? Does a 3-day sick absence need a medical certificate?" התשובה חייבת להכיל `Rina Sasson`, `Wednesday` ו-`medical certificate`.
  - **x04** (oncall ואז it_access): "What is the runbook document for flow-api, and which PagerDuty service pages for it? Itai Barak asked for GitHub write. Check whether he already has it, and if not, file the request." בזהב נפתחת בקשה: E009, github, write, needs_manager. התשובה חייבת להכיל `flow-api-prod` ו-`eng-runbook-flow-api`.
  - **x05** (hr ואז it_access): "Under the 2026 remote work policy, how many days per week can employees work remotely? Also, Hila Tzur wants a Zoom member account. File the request." בזהב נפתחת בקשה: E074, zoom, member, auto_approve. התשובה חייבת להכיל `2 days`.
  - **x06** (oncall ואז it_access): "Who leads the team behind auth-service, and what is its secondary on-call rotation? Gil Avraham wants admin on aws-production. Which track would it take? Do not file anything yet." אסור לפתוח בקשה. התשובה חייבת להכיל `Gil Avraham`, `platform-oncall` ו-`needs_security`.
  - **x07** (אף תחום): "Can you sort this out for the new person on my team? They start Sunday." התשובה הנכונה היא שאלת הבהרה (outcome clarify).
  - **x08** (hr, oncall ו-it_access): "Keren Amar from finance has three questions. How many sick days does an employee accrue per month? Who is on call for connectors-hub? Does Keren Amar already have NetSuite access? Do not file anything." התשובה חייבת להכיל `1.5`, `integrations-oncall` ו-`member`.
- **העובדות שהמשימות החדשות נשענות עליהן**:
  - מקטלוג השירותים (`data/acme/corpus/docs/eng-service-catalog.md`): flow-scheduler שייך ל-Engine (ראש הצוות Dana Levi), והרוטציה engine-oncall משותפת עם flow-engine. billing-service שייך ל-Billing (Rina Sasson), וההחלפה ביום רביעי ב-12:00. auth-service שייך ל-Identity (Gil Avraham), והרוטציה המשנית היא platform-oncall. connectors-hub שייך ל-Integrations (Omer Haddad), עם הרוטציה integrations-oncall. בשירותים ב-tier 1 זמן התגובה הוא 5 דקות.
  - ממסמכי משאבי האנוש: לפי `hr-vacation-2026`, עד 5 ימים לא מנוצלים עוברים לשנה הבאה ופגים ב-31 במרץ (בגרסה הישנה, `hr-vacation-2024`, היו 3 ימים). לפי `hr-remote-work-2026`, מותר לעבוד מהבית עד יומיים בשבוע. לפי `hr-sick-leave`, צוברים 1.5 ימי מחלה בחודש, ומ-3 ימים רצופים צריך אישור רפואי.
- **שאלות המחקר לתרגיל 5** נמצאות ב-`data/research.jsonl`. לכל שאלה יש עובדות זהב ומסמכי מקור חובה:
  - **r01**: הזמינות של flow-api באוגוסט 2026 (99.89%, לפי `eng-pm-2026-08-api`), והזיכוי ללקוחות Enterprise כשהזמינות בין 99.5% ל-99.95% (10%, לפי `sales-sla-2026`, שהוא PDF).
  - **r02**: ימי חופשה שעוברים לשנה הבאה (5), ימי עבודה מהבית בשבוע (2), ואש"ל בערים רגילות ב-2026 ($85, לפי `fin-travel-2026`, PDF).
  - **r03**: מי הבעלים של auth-service ומתי ההחלפה (Identity, יום חמישי), וכמה ימי עבודה לוקחת בדיקת אבטחה לפי מדיניות v2.2 (2 ימי עבודה).
- **המקרה של תרגיל 8** נמצא ב-`data/critic_case.json`: הודעת Slack ל-Dana על הבקשה AR-00001 (admin ב-aws-production, needs_security). המאשר הוא צוות האבטחה, בדיקה תוך 2 ימי עבודה, ותפוגה ב-2026-11-04.

## התרגילים

**1. Router: סיווג אחד, ואז מומחה אחד.** הרץ את הנתב על x03. קרא את ה-RouteDecision שחזר מהקריאה המובנית, ואת ההחלטה של הקוד. ענה: לאיזה מומחה הבקשה הגיעה, ומה קרה לחצי השני שלה? כמה טוקנים עלה הסיווג, לעומת המומחה? אחר כך הרץ עם `--max-targets 2`. מה השתנה בתשובה, ולמה אף מודל לא קרא את שתי התשובות יחד? הרץ את `--accuracy` על כל 23 המשימות, קודם offline ואחר כך מול Haiku (23 קריאות סיווג קטנות, פחות מסנט). האם Haiku מחזיר confidence נמוך על x07? האם הוא מחזיר את כל התחומים במשימות החוצות?

```bash
python labs/18-multi-agent/run_router.py x03
python labs/18-multi-agent/run_router.py x03 --max-targets 2
python labs/18-multi-agent/run_router.py --accuracy
python labs/18-multi-agent/run_router.py --accuracy --model anthropic:claude-haiku-5-5
python labs/18-multi-agent/run_router.py x07 --model anthropic:claude-haiku-5-5
```

**2. החלטת הניתוב ו-fallback (קוד).** ממש את `decide_route` ב-`mine.py`. ה-docstring מגדיר חמישה כללים, לפי הסדר. אחרי שהבדיקות עוברות, הרץ את `--accuracy --mine` עם ספים שונים: 0.5, 0.75 ו-0.95. בכל סף ספור כמה משימות נותבו נכון, וכמה שאלות הבהרה נשאלו. איפה נכון לשים את הסף ב-Company Brain, כשמחיר של ניתוב שגוי לבקשת גישה גבוה יותר ממחיר של שאלה מיותרת?

```bash
python -m pytest -q labs/18-multi-agent/tests/test_ex2_router.py
python labs/18-multi-agent/run_router.py --accuracy --mine --threshold 0.75
python labs/18-multi-agent/run_router.py --accuracy --mine --threshold 0.95 --model anthropic:claude-haiku-5-5
```

**3. Supervisor: האצלה ככלי, ובידוד הקשר.** הרץ את x08. הסקריפט מדפיס את קריאות ה-delegate (מה כל worker קיבל), את גודל ההקשר של כל agent בצעד הראשון ובצעד הגדול ביותר, ואת אותה משימה עם agent יחיד, להשוואה. ענה: מה הצעד הגדול ביותר של כל worker, לעומת הצעד הגדול ביותר של ה-agent היחיד? למה ה-worker של hr לא רואה את השאלה על NetSuite? כמה עלתה השכבה של ה-supervisor עצמו (coordination share)? הרץ עם `--sequential`, ובדוק שה-supervisor עשה צעד נוסף לכל worker. מול Haiku, בדוק אם הוא מאציל את שלושת החלקים באותו צעד, ואם ה-task שהוא כותב ל-it_access מעתיק מילה במילה את "Do not file anything".

```bash
python labs/18-multi-agent/run_supervisor.py x08
python labs/18-multi-agent/run_supervisor.py x08 --sequential
python labs/18-multi-agent/run_supervisor.py x01 --show
python labs/18-multi-agent/run_supervisor.py x01 --model anthropic:claude-haiku-5-5 --approve ask
```

**4. Handoff והחוזה של הסיכום (קוד).** משימת ההדגמה h01 היא: "Who is on call for flow-api? Dana Levi wants admin on aws-production for 3 days. Open the request, but do not file it before Friday." בזהב שלה **אסור** לפתוח בקשה. ממש את `make_handoff_brief` ב-`mine.py`: היא בודקת שהבקשה המקורית הועתקה מילה במילה, שלכל עובדה יש מקור, שכל אילוץ ("do not ...") עבר, ושכל בקשה שכבר נפתחה מופיעה ב-actions_taken. אחר כך הרץ שלוש פעמים:
- עם מסכם זהיר.
- עם `--lossy`: המסכם מנסח מחדש ומשמיט את האילוץ. הבדיקה שלך דוחה את הסיכום, והסוכן מתקן אותו.
- עם `--lossy --no-check`: אין בדיקה בכלל.

מה קרה בריצה השלישית, ולמה ה-agent של it_access לא יכול לדעת שהוא טועה? מול Haiku, עם `--show-briefs`, קרא את ה-brief שכל agent קיבל. האם Haiku העתיק את הבקשה מילה במילה?

```bash
python -m pytest -q labs/18-multi-agent/tests/test_ex4_handoff.py
python labs/18-multi-agent/handoff_demo.py --mine
python labs/18-multi-agent/handoff_demo.py --lossy --mine
python labs/18-multi-agent/handoff_demo.py --lossy --no-check
python labs/18-multi-agent/handoff_demo.py x08 --show-briefs
python labs/18-multi-agent/handoff_demo.py --model anthropic:claude-haiku-5-5 --show-briefs --mine
```

**5. Fan-out מקבילי עם ציטוטים.** הרץ את שלוש שאלות המחקר. לכל שאלה ענה שלוש שאלות: לאילו תתי-שאלות היא פורקה, אילו מסמכים נקראו, והאם יש ציטוט שלא נתמך. אחר כך השווה זמנים עם השהיה מדומה של 0.5 שניות לכל קריאת מודל: worker אחד מול ארבעה. כמה זמן חסכה ההרצה המקבילית? האם מספר הטוקנים השתנה? (רמז: לא. מקביליות קונה זמן, לא חוסכת טוקנים.) הרץ גם עם `--naive`, שבו ה-workers לוקחים את התוצאה הראשונה בחיפוש בלי לבדוק תאריך. בשלוש השאלות האלה BM25 מדרג את הגרסה החדשה ראשונה, ולכן התוצאה לא משתנה. אבל חשוב על המקרה ההפוך: אילו worker היה קורא את `hr-vacation-2024` ומצטט אותו, האם בדיקת הציטוטים הייתה תופסת את זה? (לא: הציטוט "נתמך", כי המסמך באמת נקרא. רק זהב תופס עובדה ישנה.) מול Haiku, מדוד את הזמן האמיתי בשני המצבים.

```bash
python labs/18-multi-agent/fanout_demo.py
python labs/18-multi-agent/fanout_demo.py --delay 0.5 --workers 1
python labs/18-multi-agent/fanout_demo.py --delay 0.5 --workers 4
python labs/18-multi-agent/fanout_demo.py --naive
python labs/18-multi-agent/fanout_demo.py --model anthropic:claude-haiku-5-5 --workers 1
python labs/18-multi-agent/fanout_demo.py --model anthropic:claude-haiku-5-5 --workers 4
```

**6. עלות וייחוס לכל agent (קוד), ואז ההשוואה הגדולה.** ממש את `aggregate_runs` ב-`mine.py`. אחר כך הרץ את `compare.py` על 23 המשימות, עם ה-agent היחיד, הנתב וה-supervisor, ואם תרצה גם עם router2 ו-handoff. לכל דפוס רשום: הצלחה (כוללת, ובשמונה המשימות החדשות), טוקנים, עלות, זמן ממוצע, החלק של שכבת התיאום בעלות, וייחוס הכשלונות. מול Haiku ההרצה עוצרת אם העלות עוברת $0.40. ההערכה שלי היא 10 עד 25 סנט לשלושה דפוסים, אבל תכתוב לי את המספר האמיתי. שאלות לסיום: איזה דפוס הכי זול, ואיפה הוא נכשל? האם ה-supervisor מצדיק את המחיר שלו, לעומת agent יחיד עם עשרה כלים? אם ב-Haiku ה-agent היחיד מצליח כמו ה-supervisor, ובפחות טוקנים, זו תוצאה לגיטימית לגמרי, ותכתוב אותה.

```bash
python -m pytest -q labs/18-multi-agent/tests/test_ex6_attribution.py
python labs/18-multi-agent/compare.py --mine --show-failures
python labs/18-multi-agent/compare.py --patterns single,router,router2,supervisor,handoff
python labs/18-multi-agent/compare.py --mine --model anthropic:claude-haiku-5-5
```

**7. תרגיל כשל: worker מחזיר מידע שגוי.** `failure_demo.py` משבש את התשובה הסופית של worker אחד, בזמן שהכלים והראיות שלו נשארים נכונים. יש ארבעה סוגי שיבוש:
- `route`: it_access אומר auto_approve במקום needs_security.
- `lead`: oncall נותן שם שגוי של ראש צוות.
- `rotation`: oncall נותן רוטציה שגויה.
- `number`: hr משנה מספר, למשל 10 ימים במקום 5.

כל שיבוש רץ מול שלושה מצבי verify: `none`, `llm` ו-`code`. לכל שילוב ענה: האם ה-supervisor תפס את השגיאה, ומה זה עלה בטוקנים? למה `number` לא נתפס באף מצב? שים לב גם למה שקורה ב-x01 וב-x04 עם `route`: ה-supervisor מאציל שוב ל-it_access, וה-worker מגיש שוב את הבקשה. מה מנע בקשה כפולה בפועל, ולמה הבודק משיעור 15 בכל זאת מסמן כשל? אחר כך הרץ עם `--times 1`, כך שה-worker טועה רק בפעם הראשונה. מול Haiku עם `--verify none,llm`: כמה פעמים Haiku תפס את הסתירה כשהראיות היו מולו?

```bash
python labs/18-multi-agent/failure_demo.py
python labs/18-multi-agent/failure_demo.py --fault route --times 1
python labs/18-multi-agent/failure_demo.py --fault route,lead --verify none,llm --model anthropic:claude-haiku-5-5
```

**8. כותב ומבקר.** ב-rubric יש חמישה קריטריונים. שניים מהם נבדקים בקוד: facts (מזהה הבקשה, המערכת והמאשר) ו-length (עד 80 מילים). שלושה נבדקים על ידי מבקר מודל: no_promise (לא להבטיח שהגישה כבר פעילה), next_step (מי בודק, תוך כמה זמן, ומתי זה פג) ו-plain_language (להסביר את המסלול במילים פשוטות). הרץ את המבקר בשלושה מצבים:
- `strict`: מבקר ישר.
- `lenient`: חותמת גומי, שמאשרת הכל.
- `nitpick`: מבקר שתמיד מוצא משהו.

ענה: כמה סבבים היו בכל מצב, ומה עלה כל סבב? מה הטיוטה הסופית במצב lenient הבטיחה לעובדת, ומי בכל זאת תפס חלק מהבעיות? מול Haiku: כמה סבבים הוא היה צריך? הרץ גם עם `--no-code-checks`, שמעביר את כל הקריטריונים למבקר. האם הוא ספר מילים נכון?

```bash
python labs/18-multi-agent/critic_demo.py
python labs/18-multi-agent/critic_demo.py --critic lenient
python labs/18-multi-agent/critic_demo.py --critic nitpick --max-rounds 4
python labs/18-multi-agent/critic_demo.py --model anthropic:claude-haiku-5-5
python labs/18-multi-agent/critic_demo.py --model anthropic:claude-haiku-5-5 --no-code-checks
```

## כללים

- כל המעבדה מול Haiku 5.5 צריכה לעלות פחות מ-40 סנט. רוב העלות היא תרגיל 6. ל-`compare.py` יש תקציב כולל (`--total-budget`, ברירת מחדל $0.40), ול-`failure_demo.py` יש תקציב של $0.15.
- המספרים של `--model fake` הם **הערכה**. הם מראים איך המנגנון מתנהג: כמה agents רצו, כמה הקשר כל אחד סחב, ומי שילם על מה. הם לא מראים כמה טוב Claude מתאם agents. ב-offline, ה-agent היחיד מצליח בכל 23 המשימות, כי ה"מודל" המזויף שלו מפרק משימות בדיוק כמו ה-supervisor המזויף. ההבדל האמיתי באיכות נמדד רק מול מודל אמיתי.
- את קוד הייחוס ב-`multikit/router.py`, ב-`multikit/handoff.py` וב-`multikit/attribution.py` אל תקרא לפני שהבדיקות שלך עוברות.
- `results/` לא נכנס ל-git.
