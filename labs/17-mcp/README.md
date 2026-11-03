# מעבדה 17: Model Context Protocol (MCP)

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r labs/17-mcp/requirements.txt   # mcp>=2.3.0, ה-SDK הרשמי של MCP ל-Python
python -m pytest -q tests/test_mcpkit.py          # בדיקות הסביבה של mcpkit
python -m pytest -q labs/17-mcp/tests             # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

לתרגיל 2 צריך גם Node בגרסה 22.19 ומעלה, כי ה-MCP Inspector רץ עם `npx`. לתרגיל 5 צריך את Claude Code מותקן.

## מה חדש

- **ה-SDK הרשמי, גרסה 2.** החבילה `mcp` היא ה-SDK הרשמי של MCP ל-Python. בגרסה 2 (יצאה ב-28 ביולי 2026, יחד עם גרסת הפרוטוקול 2026-07-28) המחלקה שנקראה בעבר `FastMCP` נקראת `MCPServer`, והייבוא הוא `from mcp.server.mcpserver import MCPServer`. הפרויקט הנפרד `fastmcp` של Prefect (היום בגרסה 4) הוא מסגרת עבודה גדולה יותר שנבנית מעל אותו SDK. במעבדה משתמשים רק ב-`mcp`.
- **שתי תקופות של הפרוטוקול על אותו שרת.** לקוח ישן (2025-11-25 ומטה) פותח ב-`initialize`. לקוח חדש (2026-07-28) לא עושה handshake בכלל: כל בקשה נושאת את גרסת הפרוטוקול ואת יכולות הלקוח בשדה `_meta`. השרת של ה-SDK מזהה את התקופה לפי הבקשה הראשונה ומשרת את שתיהן.
- **החבילה `mcpkit/`** (חדשה, שלך מעכשיו):
  - `server.py`: השרת acme-mcp. הוא מגיש את ששת הכלים של `toolkit/` משיעור 14 (אותם מודלים של Pydantic, אותו executor), ועוד שני כלים: `search_docs` (חיפוש BM25 של ragkit על 55 המסמכים) ו-`get_oncall_for_service`. כל מסמך בקורפוס הוא resource בכתובת `acme://docs/{doc_id}`, ויש שני prompts: `summarize-policy` ו-`triage-access-request`. מריצים עם `python -m mcpkit`.
  - `create_access_request` לא רץ בלי אישור של אדם. השרת שואל את המשתמש דרך **elicitation**: ב-2026-07-28 הוא מחזיר `input_required` והלקוח שולח את הבקשה שוב עם התשובה, וב-2025-11-25 הוא שולח `elicitation/create` באמצע הקריאה. לקוח שלא הצהיר על יכולת elicitation מקבל שגיאה ברורה, והבקשה לא נפתחת.
  - `bridge.py`: `MCPToolbox` מתחבר לשרת MCP אחד או יותר, הופך את הכלים שלהם לכלים של llmkit, ומשמש כ-executor ללולאה של שיעור 14. כך Haiku משתמש בכל שרת MCP.
  - `auth.py`: בדיקת bearer token ל-Streamable HTTP, עם המנגנון של ה-SDK (401, `WWW-Authenticate`, ומסמך Protected Resource Metadata לפי RFC 9728).
  - `pinning.py`: טביעת אצבע לכל כלי, קובץ נעילה, diff ובדיקת תיאורים חשודים. זו ההגנה מתרגיל 7.
  - `wire.py`: שליחת JSON-RPC ידנית לשרת stdio, בלי SDK.
- **`mine.py`** מכיל את הקוד שלך לתרגילים 3, 4 ו-7.

## הנתונים שהתרגילים עובדים עליהם

- **קטלוג השירותים** (`data/acme/corpus/docs/eng-service-catalog.md`): הטבלה "Production services" מפרטת תשעה שירותים. לכל שירות יש צוות בעלים, ראש צוות, tier, סבב כוננות ושירות PagerDuty. דוגמאות:
  - `flow-api`: צוות Core API, ראש הצוות Itai Barak, Tier 1, סבב `core-api-oncall`, העברה שבועית ביום ראשון ב-10:00.
  - `flow-scheduler`: צוות Engine, ראש הצוות Dana Levi, Tier 1, סבב `engine-oncall` המשותף עם flow-engine.
  - `auth-service`: צוות Identity, סבב `identity-oncall` עם העברה ביום חמישי ב-10:00, וסבב משני `platform-oncall`.
  - `lighthouse`: צוות Data, Tier 3, תמיכה רק בשעות העבודה בערוץ `#data-help`, בלי PagerDuty.
  - כללי ה-tier מאותו מסמך: Tier 1 מחייב אישור קבלה של התראה תוך 5 דקות, Tier 2 תוך 15 דקות, ו-Tier 3 עובד רק בשעות העבודה.
- **מסדי הנתונים והמדיניות** משיעור 14: `data/acme/corpus/structured/acme.db` (120 עובדים, 28 מערכות, 300 הרשאות) ומדיניות הגישה v2.2. דוגמה: Dana Levi, `dana.levi@acme.example`, E016. המנהלת שלה היא Michal Ben-David. מושב editor ב-Figma הולך למסלול `needs_manager`.
- **השרת הזדוני** (`labs/17-mcp/evil_server.py`): שרת "עזרים" עם שני כלי תאריכים. התיאור של `format_date` מסתיר הוראות למודל: לקרוא את ה-postmortem החסוי `eng-pm-2026-06-billing` ולהעביר אותו בפרמטר `context`, לא לספר למשתמש, ולשנות את אופן השימוש ב-`create_access_request` של שרת אחר. הכלי `business_days_between` נקי ברשימה הראשונה, ואחרי הקריאה הראשונה אליו התיאור שלו מתחלף (rug pull). השרת לא שולח שום דבר החוצה: מה שהוא מקבל נשמר בזיכרון ומודפס.

## התרגילים

**1. הפרוטוקול בעיניים.** הסקריפט מפעיל את acme-mcp כתהליך בן, ושולח לו JSON-RPC בשורות, בלי SDK. כל הודעה שנשלחת ומתקבלת מודפסת. הריצה הראשונה היא בתקופה הישנה: initialize, notifications/initialized, tools/list ו-tools/call. השנייה בתקופה החדשה: server/discover, ה-`_meta` בכל בקשה, ו-elicitation שמגיע כ-`input_required`. השלישית מראה מה קורה כשמערבבים תקופות.

```bash
python labs/17-mcp/raw_stdio.py --era legacy
python labs/17-mcp/raw_stdio.py --era modern
python labs/17-mcp/raw_stdio.py --era modern --approve
python labs/17-mcp/raw_stdio.py --era mixed
```

**2. ה-MCP Inspector.** הכלי הרשמי לבדיקת שרתים. ממשק הדפדפן מראה כל primitive בלשונית משלו, וחלון צד מציג את ה-JSON-RPC. ב-CLI, כל מה שלפני `--` הוא הפקודה שמפעילה את השרת, וכל מה שאחריו הוא הדגלים של ה-Inspector. ברירת המחדל של ה-Inspector היא התקופה הישנה, ו-`--protocol-era modern` מחליף.

```bash
npx @modelcontextprotocol/inspector .venv/bin/python -- -m mcpkit
npx @modelcontextprotocol/inspector --cli .venv/bin/python -m mcpkit -- --method tools/list
npx @modelcontextprotocol/inspector --cli .venv/bin/python -m mcpkit -- --method tools/call --tool-name get_oncall_for_service --tool-arg service=flow-api
npx @modelcontextprotocol/inspector --cli .venv/bin/python -m mcpkit -- --method resources/read --uri acme://docs/eng-service-catalog --protocol-era modern
python labs/17-mcp/primitives.py
```

**3. כלי חדש: `get_oncall_for_service`.** ממש את הפונקציה ב-`mine.py`. ה-docstring מפרט את הטבלה, את 14 המפתחות שהפונקציה מחזירה ואת השגיאות. הבדיקה האחרונה מגישה את הפונקציה שלך דרך acme-mcp, ומפעילה אותה עם לקוח MCP בזיכרון, בלי תהליך ובלי רשת.

```bash
python -m pytest -q labs/17-mcp/tests/test_ex3_oncall.py
```

**4. הגשר בין MCP ל-llmkit.** ממש את `mcp_tool_to_llmkit` ואת `call_result_to_tool_result`. זה מה שכל host עושה: Claude Code, Claude Desktop ו-Cursor. הבדיקות משוות לכל שמונת הכלים של acme-mcp, ומריצות agent מול mockllm שמשתמש בגשר שלך. אחר כך הרץ את Company Brain על Haiku, והשווה ל-`--mine`.

```bash
python -m pytest -q labs/17-mcp/tests/test_ex4_bridge.py
python labs/17-mcp/agent.py --model mock --set
python labs/17-mcp/agent.py --set
python labs/17-mcp/agent.py --set --mine
python labs/17-mcp/agent.py --allow-write "File a Figma editor request for dana.levi@acme.example, she needs it for design reviews"
```

**5. חיבור ל-Claude Code.** הוסף את השרת ברמת local (ברירת המחדל, נשמר ב-`~/.claude.json`). הפקודה שאחרי `--` היא מה ש-Claude Code יפעיל. הדגל `--env` מקבל כמה זוגות, ולכן לפי התיעוד שמים אחריו אופציה אחרת (כאן `--transport`) לפני שם השרת. בגלל שבנתיב של הריפו יש רווח, הנתיבים במירכאות. אחר כך פתח את Claude Code בתיקיית הריפו והרץ `/mcp`. נסה שלושה דברים: שאלה שמפעילה כלי, הפניה ל-resource עם `@acme:acme://docs/hr-vacation-2026`, ו-prompt עם `/mcp__acme__triage-access-request dana.levi@acme.example figma editor`. אפשרות נוספת היא קובץ `.mcp.json` ברמת project, שמתחלק דרך git. הדוגמה ב-`labs/17-mcp/mcp.json.example` משתמשת בהרחבת משתנים `${...}`.

```bash
claude mcp add --env PYTHONPATH="$PWD" --transport stdio acme -- "$PWD/.venv/bin/python" -m mcpkit
claude mcp list
claude mcp get acme
claude mcp remove acme
```

**6. Streamable HTTP עם bearer token.** הסקריפט יוצר שני tokens, מפעיל את השרת עם `--auth`, ובודק חמישה מקרים: בלי token, מסמך ה-metadata, token שגוי, token לקריאה בלבד (הכלים עובדים, `create_access_request` נחסם בגלל scope), ו-token מלא עם אישור. בסוף חבר את Claude Code לשרת ה-HTTP.

```bash
python labs/17-mcp/http_demo.py
export ACME_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m mcpkit --transport http --auth          # בטרמינל נפרד
claude mcp add --transport http acme-http http://127.0.0.1:8765/mcp --header "Authorization: Bearer $ACME_MCP_TOKEN"
python labs/17-mcp/agent.py --server http://127.0.0.1:8765/mcp --token-env ACME_MCP_TOKEN --set
```

שים לב: `claude mcp add --header` שומר את ה-token כמו שהוא ב-`~/.claude.json`. בקובץ `.mcp.json` עדיף `${ACME_MCP_TOKEN}`, כמו בדוגמה.

**7. הרעלת כלים, ו-pinning כהגנה.** קודם קרא את התיאורים המלאים. אחר כך ממש את `tool_fingerprint` ואת `diff_tool_pins` ב-`mine.py`, והרץ את תרחיש ה-rug pull עם הקוד שלך. לסיום הרץ את המתקפה: פעם בסימולציה (mock שמציית בכוונה לתיאור), פעם על Haiku, ופעם עם ההגנה.

```bash
python labs/17-mcp/poison_demo.py --show
python -m pytest -q labs/17-mcp/tests/test_ex7_pins.py
python labs/17-mcp/poison_demo.py --rug-pull --mine
python labs/17-mcp/poison_demo.py --attack --model mock
python labs/17-mcp/poison_demo.py --attack
python labs/17-mcp/poison_demo.py --attack --defense
```

**8. resource או tool? תרגיל תכנון.** לכל אחד מששת הצרכים הבאים, החלט אם הוא tool, resource או prompt, ונמק במשפט אחד: מי מחליט מתי הוא נכנס להקשר (המודל, האפליקציה או המשתמש), האם יש לו תופעת לוואי, והאם הוא צריך פרמטרים.
  1. מדיניות החופשה המלאה, `hr-vacation-2026`, כדי שעובד יוכל לצרף אותה לשיחה.
  2. "מי בכוננות עכשיו ל-flow-api".
  3. רשימת כל ההרשאות של עובד מסוים.
  4. תבנית קבועה ל"סיכום postmortem לפי המבנה של Acme".
  5. פתיחת בקשת גישה.
  6. סכמת מסד הנתונים `acme.db`, כדי שמודל יוכל לכתוב שאילתות.
  אחר כך הרץ את `primitives.py` והשווה להחלטות שנעשו ב-acme-mcp. שאלה לסיום: למה acme-mcp מגיש את המסמכים גם כ-resources וגם דרך הכלי `read_document`?

```bash
python labs/17-mcp/primitives.py
python labs/17-mcp/primitives.py --stdio --legacy
```

## כללים

- המעבדה כולה על Haiku 5.5 עולה בערך 3 עד 5 סנטים: `agent.py --set` פעמיים או שלוש, ו-`poison_demo.py --attack` פעמיים.
- את קוד הייחוס ב-`mcpkit/oncall.py`, ב-`mcpkit/bridge.py` וב-`mcpkit/pinning.py` אל תקרא לפני שהבדיקות שלך עוברות.
- כל הכתיבות של הדמואים הולכות לקובץ SQLite זמני, ולא ל-`labs/14-tool-use/results/requests.db`. השרת עצמו (`python -m mcpkit`) כותב לשם, אלא אם מעבירים `--requests-db`.
- tokens נשמרים רק במשתני סביבה. לא מדפיסים אותם ולא מכניסים אותם ל-git.
