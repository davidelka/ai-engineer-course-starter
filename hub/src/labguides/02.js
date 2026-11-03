window.LABGUIDE = window.LABGUIDE || {};
window.LABGUIDE["02"] = {
 "guide": {
  "goal": "<p>בשיעור 1 דיברת עם המודל דרך Prompt Lab, שמסתיר כמעט את כל מה שקורה ברשת. בשיעור 2 פותחים את המכסה: מה בדיוק נשלח לכל ספק, מה חוזר (כולל headers שאף SDK לא מראה לך), איך נראה זרם SSE שורה אחרי שורה, ומה עושים כשקריאה נכשלת. הבעיה שהמעבדה פותרת היא בעיה של כל מערכת אמיתית: ספקים נכשלים (429, 529, זרם שנקטע באמצע), כל ספק מדבר בפורמט אחר, ואתה רוצה קוד אחד שעובד מול כולם ומדווח טוקנים, עלות וזמן באותה צורה. הדוגמה היא שוב <b>Acme</b>: עוזר ה-HR משיעור 1, שבסוף המעבדה רץ דרך <code>llmkit</code> ועובר ספק בשינוי של מחרוזת אחת.</p><p>בסוף המעבדה תדע לשלוח בקשה גולמית בלי SDK ולקרוא ממנה request-id ומגבלות קצב, לזהות זרם שלא הסתיים כמו שצריך, להחליט לבד אילו שגיאות שווה לנסות שוב, לכתוב backoff עם full jitter, ולנרמל אירועי סטרימינג של OpenAI לפורמט האחיד של llmkit. שלוש הפונקציות האלה נכתבות ב-<code>mine.py</code>, והן מתחברות ישירות לתוך <code>LLM</code>, המחלקה שתשתמש בה מכאן ועד סוף הקורס. בנוסף תמדוד TTFT, זמן כולל ועלות בעזרת <code>bench.py</code>.</p>",
  "flow": "<p>המעבדה בנויה משלוש קבוצות:</p><ul class=\"clean\"><li><b>תרגילים 1–2, הפרוטוקול:</b> <code>raw_http.py</code> שולח בקשה ב-httpx בלבד ומדפיס הכול: headers, גוף, וכל שורת SSE עם הזמן שבו הגיעה. בתרגיל 2 מוסיפים את השרת המדומה, שקוטע את הזרם בכוונה, כדי לראות איך זרם שבור נראה מבפנים.</li><li><b>תרגילים 3–5, הקוד שלך ב-<code>mine.py</code>:</b> <code>classify_error</code> (מה מנסים שוב), <code>backoff_delay</code> (כמה מחכים), ו-<code>openai_event_to_item</code> (נרמול הזרם). שלושתן הן נקודות חיבור ש-llmkit חושף בכוונה: <code>RetryPolicy(classify=..., delay=...)</code> ו-<code>OpenAIProvider.event_mapper</code>. הבדיקות מריצות את הקוד שלך בתוך הצנרת האמיתית מול השרת המדומה.</li><li><b>תרגילים 6–7, שימוש:</b> מדידת ביצועים עם <code>bench.py</code>, והרצת עוזר ה-HR משיעור 1 דרך llmkit, עם החלפת ספק בדגל <code>--model</code> בלבד.</li></ul><p>מה עולה כסף: כל מה שרץ מול <code>--mock</code> או <code>mock:</code>/<code>mock-openai:</code>/<code>mock-gemini:</code> הוא חינם ובלי מפתח, וכך גם כל הבדיקות (<code>python -m pytest</code> מרים את השרת המדומה בעצמו). קריאה אמיתית יש בתרגיל 1, בחלק הראשון של תרגיל 2, בתרגיל 6 (לפי ה-README, <code>--runs 10</code> על Haiku 5.5 עולה פחות מסנט) ובריצה הראשונה של תרגיל 7.</p>",
  "map": [
   {
    "path": "labs/02-llm-apis/mine.py",
    "role": "הקוד שלך: <code>classify_error</code> (תרגיל 3), <code>backoff_delay</code> (תרגיל 4), <code>openai_event_to_item</code> (תרגיל 5). כל אחת עם docstring מפורט ו-<code>NotImplementedError</code> בהתחלה."
   },
   {
    "path": "labs/02-llm-apis/tests",
    "role": "<code>test_ex3_errors.py</code>, <code>test_ex4_backoff.py</code>, <code>test_ex5_stream.py</code>, ו-<code>conftest.py</code> שמרים שרת מדומה בתוך התהליך (<code>start_in_thread</code>) ומאפס אותו לפני כל בדיקה."
   },
   {
    "path": "labs/02-llm-apis/raw_http.py",
    "role": "תרגילים 1–2: בקשה לכל ספק ב-httpx בלבד. הפונקציה <code>build</code> כותבת ביד את הצורה של כל ספק, ו-<code>mask</code> מסתירה את המפתח בהדפסה."
   },
   {
    "path": "labs/02-llm-apis/curl_examples.sh",
    "role": "אותן בקשות ב-curl: <code>anthropic</code>, <code>anthropic-stream</code>, <code>openai</code>, <code>gemini</code>, <code>mock</code>."
   },
   {
    "path": "labs/02-llm-apis/retry_demo.py",
    "role": "תרגיל 4, חלק שני: מריץ את <code>classify_error</code> ו-<code>backoff_delay</code> שלך מול שרת מדומה שנכשל, ומדפיס כל המתנה. עם <code>--reference</code> משתמש בגרסאות של llmkit."
   },
   {
    "path": "labs/02-llm-apis/bench.py",
    "role": "תרגיל 6: אותה משימת HR על כמה מודלים, עם TTFT, זמן כולל, טוקנים לשנייה, טוקני חשיבה ועלות ל-1,000 משימות."
   },
   {
    "path": "labs/02-llm-apis/hr_via_llmkit.py",
    "role": "תרגיל 7: עוזר ה-HR משיעור 1 דרך <code>LLM</code>. קורא את הפרומפט מ-<code>labs/01-prompting/prompts/hr_system_mine.md</code> ואת השאלות מ-<code>data/acme/hr_questions.jsonl</code>."
   },
   {
    "path": "llmkit/client.py",
    "role": "המחלקה <code>LLM</code>: <code>parse_spec</code> מפרק את מחרוזת המודל, <code>complete</code> ו-<code>stream</code> עושים את ה-I/O, מודדים זמן ו-TTFT, ומפעילים retries."
   },
   {
    "path": "llmkit/retry.py",
    "role": "<code>RetryPolicy</code> ו-<code>call_with_retry</code>, וגרסת הייחוס של <code>backoff_delay</code>."
   },
   {
    "path": "llmkit/errors.py",
    "role": "<code>LLMError</code> (שגיאה אחת לכל הספקים), <code>RetryDecision</code>, וגרסת הייחוס של <code>classify_error</code>."
   },
   {
    "path": "llmkit/providers",
    "role": "מתאם לכל ספק (<code>anthropic.py</code>, <code>openai.py</code>, <code>gemini.py</code>) ו-<code>base.py</code> עם <code>TextDelta</code>, <code>StreamEnd</code> ו-<code>generic_error</code>. מתאם רק מתרגם: הוא לא פותח חיבורים ולא ישן."
   },
   {
    "path": "mockllm/server.py",
    "role": "השרת המדומה: מדבר בפורמט של שלושת הספקים, כולל סטרימינג, ומזריק תקלות לפי <code>MockConfig</code>."
   }
  ]
 },
 "toolsDetail": [
  {
   "name": "LLM",
   "path": "llmkit/client.py",
   "what": "המחלקה היחידה שקוד אפליקציה מדבר איתה. <code>LLM(\"anthropic:claude-haiku-5-5\")</code> בוחר מתאם לפי הקידומת. <code>complete</code> מחזיר <code>ChatResult</code> עם <code>text</code>, <code>stop_reason</code> מנורמל (למשל <code>end</code>, <code>max_tokens</code>), <code>raw_stop_reason</code>, <code>usage</code>, <code>cost_usd</code> (מטבלת <code>PRICES</code> ב-<code>llmkit/pricing.py</code>), <code>latency_s</code>, <code>ttft_s</code>, <code>request_id</code> ו-<code>attempts</code>. <code>stream</code> מחזיר אירועים מסוג <code>text</code>, ובסוף אירוע <code>done</code> עם ה-<code>ChatResult</code>.",
   "how": "קידומת <code>mock:</code> מפנה את מתאם Anthropic לשרת המדומה (<code>MOCKLLM_URL</code>, ברירת מחדל <code>http://127.0.0.1:8765</code>), ו-<code>mock-openai:</code> או <code>mock-gemini:</code> את המתאמים האחרים. <code>retry=</code> מקבל <code>RetryPolicy</code>, ו-<code>on_retry=</code> פונקציה שנקראת לפני כל המתנה. ה-timeout מוגדר ב-<code>DEFAULT_TIMEOUT</code>: 5 שניות להתחברות ו-60 שניות בין בתים, כלומר בין אירועים בזרם. <code>complete(..., stream=True)</code> אוסף זרם בפנים כדי למדוד TTFT, ואם הזרם נשבר הוא מנסה מההתחלה, כי אף משתמש עוד לא ראה כלום.",
   "why": "שלוש הפונקציות שלך נכנסות לתוכו. ב-<code>stream</code> יש כלל חשוב שכדאי לקרוא: retry קורה רק לפני שהגיע טקסט. אחרי זה שגיאה נזרקת עם <code>partial_text</code>, והקוד שקרא מחליט מה המשתמש רואה. הבדיקה האחרונה של תרגיל 5 בודקת בדיוק את זה."
  },
  {
   "name": "RetryPolicy + call_with_retry",
   "path": "llmkit/retry.py",
   "what": "<code>RetryPolicy</code> הוא dataclass עם <code>max_attempts</code> (כולל הניסיון הראשון, ברירת מחדל 4), <code>base</code> (0.5), <code>cap</code> (20), ושלוש פונקציות שאפשר להחליף: <code>classify</code>, <code>delay</code> ו-<code>sleep</code>. <code>RetryPolicy.none()</code> הוא ניסיון אחד בלבד.",
   "how": "<code>call_with_retry</code> מריץ את הקריאה, ואם נזרק <code>LLMError</code> הוא קורא ל-<code>policy.classify(err)</code>. אם ההחלטה היא לא לנסות, או שנגמרו הניסיונות, השגיאה עולה למעלה. אחרת הוא מחשב <code>policy.delay(attempt - 1, base, cap, decision.retry_after, rng)</code>, קורא ל-<code>on_retry</code>, וישן. כלומר <code>attempt</code> שמגיע לפונקציה שלך הוא 0 בהמתנה הראשונה.",
   "why": "זו הסיבה שאפשר לבדוק את הקוד שלך בלי לחכות: הבדיקה מעבירה <code>sleep=sleeps.append</code>, כך שבמקום לישון היא רק אוספת את זמני ההמתנה ובודקת אותם."
  },
  {
   "name": "LLMError + classify_error",
   "path": "llmkit/errors.py",
   "what": "<code>LLMError</code> מאחד את השגיאות של כל הספקים לשדות קבועים: <code>status</code> (קוד HTTP, או None), <code>kind</code> (סוג השגיאה של הספק, או <code>timeout</code>, <code>network</code>, <code>stream_truncated</code>, <code>malformed_response</code>), <code>retry_after</code>, <code>request_id</code> ו-<code>partial_text</code>. <code>RetryDecision</code> הוא <code>retry</code> ו-<code>retry_after</code>.",
   "how": "מי ממלא את השדות: <code>generic_error</code> ב-<code>llmkit/providers/base.py</code> מפענח גוף שגיאה של HTTP ואת ה-header <code>retry-after</code> (דרך <code>parse_retry_after</code>). <code>_transport_error</code> ב-<code>client.py</code> הופך חריגות של httpx ל-<code>timeout</code> או <code>network</code> בלי status. כל מתאם זורק <code>stream_truncated</code> כשהזרם נגמר בלי אירוע סיום.",
   "why": "תרגיל 3 הוא לכתוב את ההחלטה על סמך השדות האלה. חשוב להבין שבשגיאה שמגיעה בתוך זרם (אחרי HTTP 200) אין status, ויש רק <code>kind</code>."
  },
  {
   "name": "mockllm",
   "path": "mockllm/__main__.py → mockllm/server.py",
   "what": "שרת HTTP מקומי (פורט 8765) שעונה ב-<code>/v1/messages</code>, <code>/v1/responses</code> ו-<code>/v1beta/models/...:generateContent</code> או <code>streamGenerateContent</code>, בפורמט של Anthropic, OpenAI ו-Gemini. התשובה היא \"This is a mock answer from mockllm. You asked: ...\", או מה שמעבירים ב-<code>--reply</code>.",
   "how": "דגלי תקלות: <code>--fail-rate</code> (הסתברות לכישלון), <code>--fail-first N</code>, <code>--status</code> (ברירת מחדל 529), <code>--retry-after</code> (ל-429 נשלח 1 גם בלי הדגל), <code>--truncate-after N</code> (סוגר את החיבור אחרי N אירועי טקסט, בלי אירוע סיום), <code>--error-after N</code> (אירוע שגיאה בתוך הזרם), <code>--malformed-rate</code>, ו-<code>--latency</code>, <code>--ttft</code>, <code>--tps</code> לתזמון. בתשובה תקינה של Anthropic הוא שולח גם <code>request-id</code> ו-headers של מגבלות קצב מזויפות. <code>GET /__admin/stats</code> מחזיר מונים, ו-<code>POST /__admin/config</code> משנה תקלות בלי להפעיל מחדש.",
   "why": "בלי השרת הזה היה צריך לחכות ל-529 אמיתי כדי לבדוק retry. איתו כל תקלה זמינה לפי בקשה, בחינם, וחוזרת על עצמה, ולכן הבדיקות של תרגילים 4 ו-5 יכולות לרוץ מולו."
  },
  {
   "name": "raw_http.py",
   "path": "labs/02-llm-apis/raw_http.py",
   "what": "סקריפט שמראה את הפרוטוקול בלי שום שכבה. הוא מדפיס את ה-URL ואת ה-headers של הבקשה (עם מפתח מוסתר), את כל ה-headers של התשובה, ואז או את גוף ה-JSON, או כל שורה לא ריקה בזרם עם מספר השניות מתחילת הבקשה.",
   "how": "<code>--provider</code> (anthropic, openai, gemini), <code>--model</code>, <code>--prompt</code> (ברירת מחדל \"Name two colors.\"), <code>--stream</code>, <code>--max-tokens</code> (300), <code>--show-body</code> מדפיס את גוף הבקשה, ו-<code>--mock</code> מחליף את הדומיין בכתובת השרת המדומה ושם <code>mock-key</code> במקום מפתח.",
   "why": "תרגילים 1–2. הוא לא משתמש ב-llmkit בכלל (רק ב-<code>load_dotenv</code>), כך שמה שאתה רואה הוא בדיוק מה שהספק שלח."
  },
  {
   "name": "bench.py",
   "path": "labs/02-llm-apis/bench.py",
   "what": "מריץ את אותה בקשה (<code>TASK</code>: עובד בשנה השלישית שואל על ימי חופש והעברתם, עם <code>TASK_SYSTEM</code> של עד 60 מילים) N פעמים לכל מודל, תמיד בסטרימינג, ומדפיס טבלה: ok, TTFT p50/p95, זמן כולל p50/p95, tok/s, out, think, $/1k ו-retry.",
   "how": "<code>--models</code> רשימה מופרדת בפסיקים בפורמט <code>provider:model[@effort]</code>. <code>--runs</code> (10), <code>--workers</code> (2 קריאות במקביל, כדי לא לחרוג ממגבלות קצב), <code>--max-tokens</code> (1500). אפשר להריץ חינם: <code>--models mock:mock-model,mock-openai:mock-model</code>.",
   "why": "תרגיל 6. הוא משתמש ב-<code>ChatResult.ttft_s</code> וב-<code>tokens_per_second</code>, שלא סופר טוקני חשיבה, כי הם נוצרים לפני הטוקן הנראה הראשון ונכללים ב-TTFT."
  },
  {
   "name": "mine.py",
   "path": "labs/02-llm-apis/mine.py",
   "what": "שלוש פונקציות שאתה כותב. הקובץ כבר מייבא את מה שצריך: <code>LLMError</code>, <code>RetryDecision</code>, <code>StreamEnd</code>, <code>TextDelta</code>, ושתי פונקציות עזר מהמתאם של OpenAI, <code>raw_stop_from</code> ו-<code>usage_from</code>.",
   "how": "כותבים, מריצים את קובץ הבדיקה של התרגיל, וחוזרים עד שהוא עובר. אחר כך <code>retry_demo.py</code> מריץ את שתי הראשונות מול שרת אמיתי בטרמינל שני.",
   "why": "גרסאות הייחוס יושבות ב-<code>llmkit/errors.py</code>, <code>llmkit/retry.py</code> ו-<code>llmkit/providers/openai.py</code> (<code>event_to_item</code>). נסה לא להציץ לפני שהבדיקות שלך עוברות, ואז השווה."
  }
 ],
 "code": {
  "ex1": "<p><b>הקובץ:</b> <code>labs/02-llm-apis/raw_http.py</code>, ובמקביל <code>curl_examples.sh</code>. זו קריאה אמיתית אחת, ועולה שבריר סנט.</p><ul class=\"clean\"><li><b>הבנייה:</b> <code>build</code> מחזירה URL, headers וגוף, כתובים ביד לכל ספק כדי שתוכל להשוות. ב-Anthropic: <code>/v1/messages</code>, המפתח ב-<code>x-api-key</code>, גרסה ב-<code>anthropic-version: 2023-06-01</code>, וה-system בשדה נפרד. ב-OpenAI: <code>/v1/responses</code>, <code>Bearer</code>, ו-<code>instructions</code>. ב-Gemini: המודל בתוך ה-URL, <code>x-goog-api-key</code>, ו-<code>systemInstruction</code>.</li><li><b>המפתח:</b> <code>load_dotenv</code> קורא את <code>.env</code> שבשורש. אם המפתח חסר הסקריפט יוצא עם הודעה שמציעה <code>--mock</code>. בהדפסה <code>mask</code> משאיר רק 7 תווים ראשונים.</li><li><b>מה לחפש בפלט:</b> אחרי <code>HTTP 200</code> מודפסים כל ה-headers של התשובה. אצל Anthropic יש <code>request-id</code> (זה מה ששולחים לתמיכה כשמשהו נכשל) ו-headers שמתחילים ב-<code>anthropic-ratelimit-</code>: מגבלה ויתרה לבקשות, לטוקני קלט ולטוקני פלט. השאלה בתרגיל היא היחס בין <code>output-tokens-limit</code> ל-<code>input-tokens-limit</code>.</li><li><b>בגוף:</b> <code>usage</code> (טוקני קלט ופלט) ו-<code>stop_reason</code>. <code>--show-body</code> מדפיס גם את מה שנשלח.</li><li><b>curl:</b> צריך קודם לייצא את המשתנים מ-<code>.env</code> לסביבה (זה מה ש-<code>set -a; source .env; set +a</code> עושה). הדגל <code>-i</code> מדפיס את ה-headers, וכך רואים שזו אותה בקשה בדיוק.</li></ul>",
  "ex2": "<p><b>הקובץ:</b> אותו <code>raw_http.py</code>, עם <code>--stream</code>. הגוף מקבל <code>\"stream\": true</code> (ב-Gemini משתנה ה-URL ל-<code>streamGenerateContent?alt=sse</code>), והקריאה עוברת ל-<code>http.stream(...)</code>, שמדפיס כל שורה לא ריקה עם הזמן שעבר מתחילת הבקשה.</p><ul class=\"clean\"><li><b>הסדר אצל Anthropic:</b> <code>message_start</code> (עם usage של הקלט), <code>content_block_start</code>, <code>ping</code>, סדרה של <code>content_block_delta</code> עם <code>text_delta</code>, <code>content_block_stop</code>, <code>message_delta</code> (עם <code>stop_reason</code> וטוקני הפלט), ובסוף <code>message_stop</code>. הפער בין שורת ה-headers לשורת הטקסט הראשונה הוא ה-TTFT.</li><li><b>הזרם הקטוע:</b> <code>python -m mockllm --truncate-after 5</code> גורם ל-<code>_stream_anthropic</code> בשרת לחזור באמצע הלולאה אחרי 5 אירועי טקסט, בלי <code>message_delta</code> ובלי <code>message_stop</code>. החיבור פשוט נסגר, והסקריפט מדפיס \"connection closed\".</li><li><b>איך קוד יודע:</b> ב-<code>parse_stream</code> של <code>llmkit/providers/anthropic.py</code>, אם הלולאה על האירועים נגמרה בלי <code>message_stop</code>, נזרק <code>LLMError</code> עם <code>kind=\"stream_truncated\"</code>. ה-status הוא 200, כך שבדיקה של קוד HTTP לא הייתה מגלה כלום.</li><li><b>Gemini:</b> עם <code>--provider gemini --mock</code> אין אירוע סיום בכלל, גם בזרם תקין. כל chunk הוא JSON עם <code>candidates</code>, ורק ב-chunk האחרון יש <code>finishReason</code>. לכן ב-<code>llmkit/providers/gemini.py</code> הבדיקה היא \"האם ראינו <code>finishReason</code>\", ואם לא, <code>stream_truncated</code>.</li></ul>",
  "ex3": "<p><b>מה כותבים:</b> את <code>classify_error(err)</code> ב-<code>mine.py</code>. היא מקבלת <code>LLMError</code> ומחזירה <code>RetryDecision(retry=..., retry_after=...)</code>.</p><ul class=\"clean\"><li><b>איפה היא רצה:</b> ב-<code>call_with_retry</code> (ב-<code>llmkit/retry.py</code>), אחרי כל כישלון, וגם בלולאה של <code>LLM.stream</code>. אם היא מחזירה <code>retry=False</code>, השגיאה עולה מיד לקוד שקרא, בלי המתנה.</li><li><b>מה הבדיקה בודקת:</b> <code>tests/test_ex3_errors.py</code>: 429, 500, 502, 503, 529 ו-408 צריכים להיות retry. 400, 401, 403, 404, 413 ו-422 לא. כש-<code>status</code> הוא None, <code>timeout</code>, <code>network</code>, <code>stream_truncated</code>, <code>overloaded_error</code> ו-<code>malformed_response</code> הם retry, אבל <code>invalid_request_error</code> (שגיאה של הבקשה שהגיעה בתוך זרם) לא. ובסוף, ש-<code>retry_after=12</code> עובר הלאה כמו שהוא.</li><li><b>המלכודות:</b> 408 הוא 4xx אבל זמני (timeout של הבקשה), אז כלל של \"כל 4xx לא\" נכשל. ב-503 ה-kind הוא <code>UNAVAILABLE</code> (הסגנון של Gemini), ובקוד 502 ה-kind ריק, כך שאי אפשר להסתמך רק על <code>kind</code>. ולהפך, בשגיאות בלי status יש רק <code>kind</code>.</li><li><b>כיוון:</b> קודם מחליטים לפי <code>status</code> אם הוא קיים, ורק אם הוא None לפי <code>kind</code>. שתי קבוצות קבועות (סטטוסים זמניים וסוגים זמניים) מספיקות. הכלל מהשיעור: אם השליחה מחדש של אותה בקשה בדיוק תיכשל שוב, אין טעם לנסות.</li></ul>",
  "ex4": "<p><b>מה כותבים:</b> את <code>backoff_delay(attempt, base, cap, retry_after, rng)</code> ב-<code>mine.py</code>. היא מחזירה מספר שניות להמתנה לפני הניסיון הבא.</p><ul class=\"clean\"><li><b>איפה היא רצה:</b> <code>call_with_retry</code> קורא לה כ-<code>policy.delay(attempt - 1, policy.base, policy.cap, decision.retry_after, policy.rng)</code>. ה-<code>retry_after</code> מגיע מה-<code>RetryDecision</code> שהחזירה <code>classify_error</code> שלך מתרגיל 3, ולכן אם שם לא העברת אותו הלאה, כאן הוא תמיד None.</li><li><b>מה הבדיקה בודקת:</b> <code>tests/test_ex4_backoff.py</code>: שכל ערך בין 0 ל-<code>min(cap, base * 2**attempt)</code>; שהערכים באמת אקראיים (יותר מ-150 שונים מתוך 200, וממוצע בין 1.5 ל-2.5 ב-attempt 3, כמו <code>uniform(0, 4)</code>); שהממוצע עולה עם attempt; שהתקרה נשמרת גם ב-attempt 30; ש-<code>retry_after=6</code> הוא רצפה. הבדיקה האחרונה מריצה 60 קריאות מול שרת מדומה עם 40% כישלונות ו-4 ניסיונות, ודורשת לפחות 54 הצלחות.</li><li><b>המלכודות:</b> חובה להשתמש ב-<code>rng.uniform</code> ולא ב-<code>random.uniform</code>, אחרת הבדיקות לא ישוחזרו. התקרה חלה על החלק האקספוננציאלי <b>לפני</b> ההגרלה, לא אחריה. ו-<code>retry_after</code> הוא מינימום, לא תוספת.</li><li><b>החלק החי:</b> <code>retry_demo.py</code> בונה <code>RetryPolicy</code> עם הפונקציות שלך (<code>base=0.2</code>, <code>cap=5</code>, 4 ניסיונות) ומדפיס \"attempt N failed ... waiting X s\" לכל המתנה. עם <code>--status 429 --retry-after 3</code> כל המתנה תהיה לפחות 3 שניות. עם <code>--status 400</code> כל קריאה מסתיימת מיד ב-\"GAVE UP\", בלי המתנה, כי השגיאה היא של הבקשה.</li></ul>",
  "ex5": "<p><b>מה כותבים:</b> את <code>openai_event_to_item(event_type, data, provider)</code> ב-<code>mine.py</code>. היא מקבלת אירוע אחד מזרם ה-Responses API של OpenAI ומחזירה פריט אחיד של llmkit, או None.</p><ul class=\"clean\"><li><b>איפה היא רצה:</b> ב-<code>OpenAIProvider.parse_stream</code> (ב-<code>llmkit/providers/openai.py</code>), דרך <code>self.event_mapper</code>. אירועים של כלים מטופלים שם לפני שהיא נקראת, כך שאתה צריך לטפל רק בטקסט, בסיום ובשגיאות. כשהיא מחזירה <code>StreamEnd</code>, <code>parse_stream</code> משלים לו request-id ומסיים. אם הזרם נגמר בלי <code>StreamEnd</code>, הוא זורק <code>stream_truncated</code>.</li><li><b>מה הבדיקה בודקת:</b> <code>tests/test_ex5_stream.py</code>: <code>response.output_text.delta</code> נותן <code>TextDelta</code> עם <code>data[\"delta\"]</code>; חמישה אירועי ניהול, כולל <code>response.output_text.done</code>, מחזירים None; <code>response.completed</code> נותן <code>StreamEnd</code> עם <code>raw_stop == \"completed\"</code>, טוקני פלט 7 וטוקני חשיבה 3; <code>response.incomplete</code> נותן <code>max_output_tokens</code>; <code>error</code> ו-<code>response.failed</code> זורקים <code>LLMError</code>.</li><li><b>שתי הבדיקות האחרונות:</b> הן מחליפות את <code>OpenAIProvider.event_mapper</code> בפונקציה שלך (<code>monkeypatch</code>) ושולחות לשרת המדומה את אותה שאלה פעם בפורמט של Anthropic ופעם של OpenAI. הטקסט, <code>stop_reason == \"end\"</code> וטוקני הפלט חייבים להיות זהים. האחרונה מפעילה <code>error_after = 2</code> ובודקת שה-<code>LLMError</code> שנזרק מכיל <code>partial_text</code>.</li><li><b>המלכודת:</b> <code>response.output_text.done</code> מכיל את <b>כל</b> הטקסט שוב. אם תחזיר עליו <code>TextDelta</code>, הטקסט יוכפל ובדיקת ההשוואה תיכשל. עוד דבר: אל תחשב usage ו-raw_stop לבד, <code>usage_from</code> ו-<code>raw_stop_from</code> כבר יודעות לקרוא את <code>data[\"response\"]</code>.</li></ul>",
  "ex6": "<p><b>הקובץ:</b> <code>labs/02-llm-apis/bench.py</code>. זה חלק חי: <code>--runs 10</code> על שני variants הם 20 קריאות ל-Haiku 5.5.</p><ul class=\"clean\"><li><b>מה הוא שולח:</b> <code>bench</code> מפרק כל spec לפי <code>@</code> למודל ול-effort, בונה <code>ChatRequest.from_prompt(TASK, system=TASK_SYSTEM, max_tokens=..., effort=...)</code>, ומריץ <code>llm.complete(req, stream=True)</code> N פעמים עם <code>ThreadPoolExecutor</code>. המתאם של Anthropic שולח את ה-effort כ-<code>output_config</code>. שגיאה לא עוצרת את הריצה: היא נאספת ונספרת.</li><li><b>מה נמדד:</b> <code>ttft_s</code> נמדד ב-<code>_collect_stream</code> ברגע שמגיע ה-<code>TextDelta</code> הראשון. <code>latency_s</code> הוא הזמן הכולל, כולל retries. <code>tokens_per_second</code> סופר רק טוקנים נראים אחרי ה-TTFT. העלות מחושבת ב-<code>cost_usd</code> ב-<code>llmkit/pricing.py</code>, לפי המחירים שבטבלה (Haiku 5.5: 0.10 קלט, 0.50 פלט, דולר למיליון).</li><li><b>מה לצפות:</b> עם effort גבוה המודל חושב לפני שהוא מתחיל לכתוב, ולכן ה-TTFT עולה, וגם <code>think</code> ו-<code>$/1k</code>. קצב הכתיבה (<code>tok/s</code>) כמעט לא אמור להשתנות. ההבדל בזמן הכולל נובע בעיקר מה-TTFT.</li><li><b>אחוזונים:</b> <code>pct</code> מחשב אחוזון על רשימה ממוינת. עם 10 ריצות, p95 הוא בפועל הערך המקסימלי, ולכן הסקריפט עצמו מזהיר להתייחס אליו כסימן גס.</li><li><b>בדיקה חינמית קודם:</b> <code>--models mock:mock-model,mock-openai:mock-model --runs 20</code> רץ מול השרת המדומה ומראה שהטבלה עובדת. אפשר גם להוסיף <code>--ttft 1</code> לשרת ולראות את העמודה זזה.</li></ul>",
  "ex7": "<p><b>הקובץ:</b> <code>labs/02-llm-apis/hr_via_llmkit.py</code>. זה עוזר ה-HR של תרגיל 4 בשיעור 1, בלי Prompt Lab: לולאה פשוטה על 10 השאלות.</p><ul class=\"clean\"><li><b>הקלט:</b> ה-system prompt נקרא מ-<code>labs/01-prompting/prompts/hr_system_mine.md</code> (אפשר לשנות עם <code>--prompt</code>). אם לא כתבת אותו בשיעור 1, יישלח טקסט ה-TODO. המסמך הוא <code>data/acme/hr_policies.md</code>, והשאלות <code>data/acme/hr_questions.jsonl</code>. ה-user נבנה באותה תבנית של שיעור 1: <code>&lt;documents&gt;</code> ואחריו <code>&lt;question&gt;</code>.</li><li><b>השורה היחידה שתלויה בספק:</b> <code>llm = LLM(a.model)</code>. כל השאר, <code>ChatRequest.from_prompt(..., effort=a.effort)</code>, <code>r.text</code>, <code>r.usage</code>, <code>r.cost_usd</code>, זהה לכל ספק, כי המתאמים מנרמלים את הכול.</li><li><b>הניקוד:</b> כמו ב-<code>contains_any</code> של Prompt Lab: עובר אם אחת המחרוזות ב-<code>expect_any</code> מופיעה בתשובה. בסוף מודפסים מספר ההצלחות, העלות הכוללת, והעלות ל-1,000 שאלות.</li><li><b>עם <code>mock-openai:mock-model</code>:</b> <code>parse_spec</code> הופך את זה למתאם של OpenAI שמכוון לשרת המדומה, עם <code>mock-key</code>. השרת מחפש <code>&lt;question&gt;</code> בבקשה ועונה \"You asked: ...\", כך שכמעט כל השאלות ייכשלו, וזה צפוי. מה שבודקים כאן הוא שהצנרת רצה בפורמט אחר בלי לשנות שורת קוד. העלות שתודפס מחושבת לפי המחיר שהוגדר ל-<code>mock-model</code> ב-<code>PRICES</code>, ואינה עלות אמיתית.</li></ul>"
 }
};
