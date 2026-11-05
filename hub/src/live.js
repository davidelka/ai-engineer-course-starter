/* Live findings: what a lesson's lab showed when run against real providers, after the course was
   written. Shown in the lab station's "ממצאים חיים" tab. When a live result contradicts a slide,
   the live result wins: add it here (newest first) with the date, and fix the slide if needed.
   Format: window.LIVE["NN"] = [{ date: "YYYY-MM-DD", text: "<html>" }] */
window.LIVE = window.LIVE || {};
window.LIVE["02"] = [
  { date: "2026-10", text: "<b>tok/s</b> שמחושב על כל טוקני הפלט מנופח במודלים עם חשיבה: טוקני החשיבה נוצרים לפני הטוקן הנראה הראשון. <code>llmkit</code> סופר עכשיו רק טוקנים נראים (תוקן בעקבות הבדיקה)." },
  { date: "2026-10", text: "ב-<b>Gemini</b> זרם שנחתך לא מסתיים באירוע סיום נפרד; הסימן היחיד הוא שאין <code>finishReason</code> בחלק האחרון. ב-Anthropic הסימן הוא שחסר <code>message_stop</code>." },
  { date: "2026-10", text: "מפתח חינמי של Gemini נתקע ב-<b>429 של מכסה</b> (quota), לא של קצב: retry לא עוזר, וצריך לזהות את זה לפי גוף השגיאה ולא רק לפי הקוד." },
];
window.LIVE["03"] = [
  { date: "2026-11-03", text: "<b><code>pattern</code></b> בסכמה ל-Claude Haiku 5.5 נדחה עם <b>400</b> (\"Schema is too complex\"), גם על תבנית מייל פשוטה. לכן <code>llmkit</code> חייב להוריד אותו לפני השליחה." },
  { date: "2026-11-03", text: "<b><code>minLength</code></b> מתקבל <b>ונאכף</b>: עם <code>minLength=40</code> על <code>tool</code> המודל החזיר 63 תווים, אף ששם כלי אמיתי הוא כ-10. זה סותר את רשימת המילים הלא נתמכות בתיעוד. עוד לא נבדקו באותה שיטה <code>maxLength</code> ו-<code>minimum</code>/<code>maximum</code>." },
  { date: "2026-11-03", text: "<b><code>additionalProperties: true</code></b> מתקבל עם 200. גם אם המודל מוסיף שדה, <code>extra=\"forbid\"</code> ב-Pydantic תופס אותו בצד שלנו." },
];
