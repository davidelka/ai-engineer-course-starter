"""Build the SAMPLE personal folder (data/sample/) for project M2. Everything is fictional.

    python data/make_sample.py            # needs: playwright + chromium (PDFs), python-docx, pillow

The folder imitates a real home folder on a Linux laptop: Hebrew and English, PDFs with
several pages (so answers can cite page numbers), DOCX, Markdown and text notes, HTML pages
saved from a browser (with menus and footers around the content), two scanned images (OCR),
exact and near duplicates, a private folder that must never be indexed, and a hidden folder.

Why Chromium for the PDFs: it lays out Hebrew right-to-left correctly, the way "Print to PDF"
in a browser or Word does. ReportLab would need a bidi library. Note what pypdf gets back from
such a PDF (see pss/extract.py): in "plain" mode the Hebrew words come out in logical order,
but numbers and punctuation next to Hebrew can move; in "layout" mode every Hebrew line comes
out REVERSED. Real Hebrew PDFs behave the same way, which is why the project checks.

All names, addresses, phone numbers, account numbers and companies are invented. Phone numbers
use the 050-555-01xx block; bank letters are templates with XXXX in place of numbers. The
medical letters are appointment logistics only, with no diagnosis or health details.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "sample"
FIXED_DATE = datetime(2026, 10, 30, 12, 0, 0)

# ---------------------------------------------------------------------------------- content
# Each entry: relative path -> spec. kind: md | txt | html | pdf | docx | png
# For PDFs, "pages" is a list of HTML fragments (one per page), "dir" is rtl or ltr.

FILES: dict[str, dict] = {}


def add(path: str, kind: str, **spec) -> None:
    FILES[path] = {"kind": kind, **spec}


# ----------------------------------------------------------------- home
LEASE_PAGES = [
    """<h1>הסכם שכירות בלתי מוגנת</h1>
<p>שנערך ונחתם במודיעין ביום 15 ביולי 2026, בין <b>יוסף מזרחי</b> (להלן: "המשכיר") לבין <b>יונתן שני</b> (להלן: "השוכר").</p>
<h2>1. המושכר</h2>
<p>דירת 4 חדרים ברחוב הנרקיס 12, דירה 7, מודיעין, כולל מחסן וחניה אחת מקורה.</p>
<h2>2. תקופת השכירות</h2>
<p>תקופת השכירות היא 12 חודשים, מיום 1 באוגוסט 2026 ועד יום 31 ביולי 2027.</p>
<h2>3. דמי שכירות</h2>
<p>השוכר ישלם למשכיר דמי שכירות בסך 4,200 ש"ח לחודש. התשלום יבוצע בהעברה בנקאית עד היום החמישי של כל חודש קלנדרי. איחור של יותר מ-10 ימים יחייב בריבית פיגורים.</p>
<p>חשבונות החשמל, המים, הגז והארנונה יועברו על שם השוכר במהלך החודש הראשון לשכירות.</p>""",
    """<h2>4. ערבות ובטחונות</h2>
<p>להבטחת התחייבויותיו ימסור השוכר למשכיר ערבות בנקאית בסך 12,600 ש"ח, שהם שלושה חודשי שכירות. הערבות תוחזר לשוכר תוך 60 ימים מתום תקופת השכירות, בניכוי נזקים שלא תוקנו.</p>
<h2>5. בעלי חיים</h2>
<p>מותר להחזיק בדירה כלב קטן אחד, בכפוף להסכמה בכתב של המשכיר. השוכר אחראי לכל נזק שייגרם על ידי בעל החיים.</p>
<h2>6. אופציה להארכה</h2>
<p>לשוכר נתונה אופציה להאריך את השכירות בשנה נוספת, בתוספת של 3% לדמי השכירות. כדי לממש את האופציה, השוכר ימסור הודעה בכתב לפחות 60 ימים לפני תום התקופה.</p>""",
    """<h2>7. תיקונים ותחזוקה</h2>
<p>המשכיר יתקן תקלות בדוד, באינסטלציה ובחשמל תוך 14 ימים מקבלת הודעה. תיקונים קטנים, עד 300 ש"ח לתיקון, יחולו על השוכר.</p>
<p>בתום השכירות השוכר יחזיר את הדירה כשהיא צבועה בלבן ונקייה.</p>
<h2>8. סיום מוקדם</h2>
<p>השוכר רשאי לסיים את ההסכם לפני תום התקופה אם יציע שוכר חלופי מתאים, שהמשכיר לא יסרב לו מטעמים בלתי סבירים.</p>
<h2>9. חתימות</h2>
<p>המשכיר: ____________ &nbsp;&nbsp; השוכר: ____________</p>""",
]
add("home/lease-2026.pdf", "pdf", dir="rtl", title="הסכם שכירות 2026", pages=LEASE_PAGES)
add("home/lease-2026 (1).pdf", "copy", source="home/lease-2026.pdf")  # a download done twice

add("home/fridge-warranty-2026-03.pdf", "pdf", dir="rtl", title="תעודת אחריות למקרר", pages=[
    """<h1>תעודת אחריות - מקרר קירור פלוס KP-560</h1>
<p>שם הלקוח: יונתן שני. תאריך רכישה: 14 במרץ 2026. מקום הרכישה: חשמל המרכז, מודיעין.</p>
<h2>תקופת האחריות</h2>
<p>אחריות מלאה על המקרר, חלקים ועבודה, למשך שנה אחת מיום הרכישה. אחריות על המדחס (קומפרסור) למשך 5 שנים מיום הרכישה.</p>
<p>Warranty: 1 year full warranty (parts and labor). Compressor warranty: 5 years.</p>
<h2>מה לא מכוסה</h2>
<p>האחריות אינה מכסה נזק שנגרם מהובלה שלא על ידי החברה, מנפילות מתח, או משימוש מסחרי.</p>""",
    """<h2>הגשת קריאת שירות</h2>
<p>לפתיחת קריאת שירות יש להתקשר למוקד השירות בטלפון 050-555-0142, בימים א'-ה' בין 08:00 ל-18:00, או להגיש בקשה באתר החברה.</p>
<p>יש להציג חשבונית רכישה מקורית ואת תעודת האחריות. טכנאי יגיע תוך 3 ימי עבודה.</p>
<h2>Service request</h2>
<p>To open a service call, phone the service center at 050-555-0142 (Sun-Thu, 08:00-18:00). Keep the original invoice: without it the warranty does not apply.</p>""",
])

add("home/arnona-2026.md", "md", text="""# ארנונה 2026 - הודעת תשלום

עיריית מודיעין, אגף הגבייה. נכס: רחוב הנרקיס 12, דירה 7. שטח לחיוב: 96 מ"ר.

## סכום החיוב

החיוב השנתי לשנת 2026 הוא 5,880 ש"ח.

## אפשרויות תשלום

- תשלום שנתי מראש עד 31 בינואר: הנחה של 2% מהסכום השנתי.
- תשלומים דו-חודשיים: שישה תשלומים, ב-1 לכל חודש אי-זוגי.
- הוראת קבע בבנק או בכרטיס אשראי: ללא הנחה, אבל אין צורך לזכור מועדים.

## הנחות

ניתן להגיש בקשה להנחה לסטודנטים, לגמלאים ולבעלי הכנסה נמוכה דרך אתר העירייה, עד 31 במרץ.
""")

add("home/solar-water-heater-service.txt", "txt", text="""Solar water heater (dud shemesh) - service log

Last service: 2026-04-10, by Shemesh Solar Services (technician: Amir).
Cost: 250 NIS including the visit.
Recommended: a full service once a year, before winter.
The anode should be replaced every 3 years; it was last replaced in April 2025.
If there is no hot water on a cloudy day, switch on the electric heater for 45 minutes.
Do not leave the electric heater on for more than 2 hours.
""")

add("home/internet-plan-2026.html", "html", lang="he", text="""<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8"><title>פרטי המסלול שלי - סיבנט</title></head>
<body>
<nav><a href="#">דף הבית</a> | <a href="#">חנות</a> | <a href="#">תמיכה</a> | <a href="#">התחברות</a></nav>
<header><div class="promo">מבצע! נטפליקס חודש במתנה למצטרפים חדשים</div></header>
<main>
<h1>פרטי המסלול שלי</h1>
<p>מסלול: סיב אופטי 1000 מגה. מחיר: 99 ש"ח לחודש ב-12 החודשים הראשונים, ולאחר מכן 129 ש"ח לחודש.</p>
<p>ההתחייבות היא ל-12 חודשים. ביטול לפני תום ההתחייבות כרוך בדמי יציאה של 150 ש"ח.</p>
<p>בסיום ההתקשרות יש להחזיר את הנתב תוך 14 ימים, אחרת יחויב החשבון ב-350 ש"ח.</p>
<p>תאריך הצטרפות: 3 באוגוסט 2026.</p>
</main>
<footer>© סיבנט תקשורת בע"מ | תנאי שימוש | מדיניות פרטיות | נגישות</footer>
</body></html>""")

# ----------------------------------------------------------------- receipts
add("receipts/receipt-laptop-2026-03.html", "html", lang="he", text="""<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8"><title>חשבונית מס קבלה 30412 - מחשבים פלוס</title></head>
<body><nav>החשבון שלי | הזמנות | עגלה</nav>
<main>
<h1>חשבונית מס קבלה מספר 30412</h1>
<p>תאריך: 2 במרץ 2026. לקוח: יונתן שני.</p>
<ul>
<li>מחשב נייד Lenovo ThinkPad E14, 16GB RAM, SSD 512GB - 3,890 ש"ח</li>
<li>תיק למחשב נייד - 120 ש"ח</li>
</ul>
<p>סה"כ לתשלום כולל מע"מ: 4,010 ש"ח. שולם בכרטיס אשראי בשלושה תשלומים.</p>
<p>אחריות יצרן למחשב: 3 שנים, שירות במעבדה. החזרת מוצר תקין: תוך 14 ימים באריזה המקורית.</p>
</main><footer>מחשבים פלוס בע"מ | שירות לקוחות</footer></body></html>""")

add("receipts/receipt-furniture-2026-05.txt", "txt", text="""HOME & WOOD - Modiin branch
Receipt no. 77810          Date: 2026-05-19

1 x Bookcase, oak finish, 80x180 cm ......... 690.00 NIS
1 x Desk with drawer, white ................... 550.00 NIS
                                    TOTAL: 1,240.00 NIS
Paid: debit card

Returns: within 30 days with this receipt, items unassembled.
Delivery: not included. Assembly instructions inside the boxes.
""")

add("receipts/receipt-pharmacy-2026-08.txt", "txt", text="""בית מרקחת הנרקיס
קבלה מספר 5521, תאריך 12/08/2026

ויטמין D3 1000 יחב"ל, 100 כמוסות ......... 59.90 ש"ח
קרם הגנה SPF 50 לילדים ................... 64.90 ש"ח
מדחום דיגיטלי ............................ 17.70 ש"ח
סה"כ: 142.50 ש"ח

חבר מועדון: כן. נצברו 14 נקודות.
""")

add("receipts/receipt-supermarket-2026-10.html", "html", lang="he", text="""<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8"><title>הקבלה הדיגיטלית שלך</title></head>
<body><header>סופר השכונה - קבלה דיגיטלית</header><main>
<h1>קבלה דיגיטלית</h1>
<p>תאריך: 24 באוקטובר 2026, סניף הנביאים, מודיעין.</p>
<ul><li>חלב 3% ליטר x2 - 13.80</li><li>לחם מחמצת - 18.90</li><li>עגבניות 2 ק"ג - 15.80</li><li>ביצים L תבנית 12 - 14.90</li><li>אבקת כביסה - 49.90</li><li>עוף שלם - 39.90</li></ul>
<p>סה"כ: 386.20 ש"ח (כולל מוצרים נוספים שלא הוצגו). שולם באפליקציה.</p>
</main><footer>תודה שקניתם אצלנו</footer></body></html>""")

add("scans/hardware-store-receipt.png", "png", lines=[
    "CITY HARDWARE", "Modiin, Industrial Zone", "Date: 2026-06-21",
    "Cordless drill 18V ........ 349.00", "Drill bits set ............ 59.00",
    "Wall anchors x50 .......... 19.90", "TOTAL NIS ................ 427.90",
    "Warranty on drill: 2 years", "Keep this receipt"])

# ----------------------------------------------------------------- kids
add("kids/school-supplies-grade3-2026.docx", "docx", title="רשימת ציוד לכיתה ג'", rtl=True, paras=[
    ("h1", "רשימת ציוד לכיתה ג' - שנת הלימודים תשפ\"ז"),
    ("p", "בית הספר היסודי \"נופים\", מודיעין. כיתה ג'2, המחנכת: מירב אלון."),
    ("p", "יש להביא את כל הציוד עד יום 1 בספטמבר 2026, כשכל פריט מסומן בשם הילד/ה."),
    ("h2", "מחברות"),
    ("li", "4 מחברות חשבון משובצות, 40 דף"),
    ("li", "3 מחברות שורה, 40 דף"),
    ("li", "מחברת אנגלית אחת"),
    ("h2", "כלי כתיבה"),
    ("li", "קלמר עם 6 עפרונות, מחק ומחדד"),
    ("li", "סרגל 30 ס\"מ, מספריים בטיחותיים ודבק סטיק"),
    ("li", "צבעי עיפרון, 24 צבעים"),
    ("p", "תיק גב קשיח ובקבוק מים רב-פעמי. לא להביא טושים מחיקים לבית הספר."),
])

add("kids/school-trip-permission-2026-11.docx", "docx", title="אישור הורים לטיול שנתי", rtl=True, paras=[
    ("h1", "טיול שנתי לכיתות ג' - אישור הורים"),
    ("p", "הורים יקרים, הטיול השנתי של שכבת ג' יתקיים ביום חמישי, 12 בנובמבר 2026, לשמורת עין עבדת."),
    ("p", "היציאה מבית הספר בשעה 07:30 והחזרה משוערת בשעה 15:00."),
    ("p", "עלות הטיול: 85 ש\"ח, שישולמו דרך אתר התשלומים של בית הספר."),
    ("h2", "מה להביא"),
    ("li", "2 ליטר מים לפחות"),
    ("li", "כובע, קרם הגנה ונעלי הליכה סגורות"),
    ("li", "ארוחת בוקר וצהריים ארוזות"),
    ("p", "את ספח האישור החתום יש להחזיר למחנכת עד 5 בנובמבר 2026. ילד ללא אישור חתום לא יוכל לצאת לטיול."),
])

add("kids/kindergarten-itai-2026-27.md", "md", text="""# גן "שקד" - מידע להורים, תשפ"ז

הגננת: ליאת, הסייעת: חנה. הגן של איתי, בשכונת הנביאים.

## שעות פעילות

- ימים א'-ה': 07:30 עד 14:00
- יום ו': 07:30 עד 12:00
- צהרון (בהרשמה מראש): עד 16:30

## ימים שהגן סגור

- ערב ראש השנה ושני ימי החג
- חופשת סוכות: 4 עד 11 באוקטובר 2026
- יום אחד בחנוכה, לפי הודעת העירייה

## מה להביא כל יום

בגדים להחלפה בתיק, בקבוק מים, כריך ופרי. בימי שישי: ארוחת בוקר משותפת לפי תורנות.
""")

add("kids/parents-meeting-2026-10.md", "md", text="""# אסיפת הורים - מאיה, כיתה ג', אוקטובר 2026

נכחו: דוד, המחנכת מירב.

- הקריאה של מאיה השתפרה מאוד מתחילת השנה. מומלץ להמשיך לקרוא איתה 15 דקות כל ערב.
- שיעורי בית: שלוש פעמים בשבוע, בימים א', ג' ו-ה'.
- בחשבון: עובדים על לוח הכפל עד 5. כדאי לתרגל בעל פה בדרך לבית הספר.
- חברתית: משתלבת יפה, אוהבת את חוג השחמט.
- הפגישה הבאה: ינואר 2027.
""")

add("kids/chess-club-2026.html", "html", lang="he", text="""<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8"><title>חוג שחמט - מתנ"ס הנביאים</title></head>
<body><nav>חוגים | צהרונים | אירועים | צור קשר</nav><main>
<h1>חוג שחמט לילדי כיתות ב'-ד'</h1>
<p>החוג נפגש בימי שלישי בשעה 16:00 במתנ"ס הנביאים, חדר 3. משך המפגש: שעה.</p>
<p>מחיר: 180 ש"ח לחודש. הרשמה דרך אתר המתנ"ס. אפשר להצטרף לשיעור ניסיון אחד ללא תשלום.</p>
<p>המדריך: אלכס, מדריך מוסמך של איגוד השחמט.</p>
</main><footer>מתנ"ס הנביאים | כל הזכויות שמורות</footer></body></html>""")

add("kids/maya-reading-list.md", "md", text="""# Maya's reading list / רשימת קריאה של מאיה

Books we finished:
- "Frog and Toad Are Friends" (in English, with dad)
- "הדוב הלבן" - מאיה קראה לבד!

Next:
- "Magic Tree House #1" - the librarian recommended it for grade 3
- "בית הספר של הקוסמים"

Library: the city library in Ramot is open Sun-Thu 10:00-19:00; books are due after 3 weeks.
""")

add("scans/gan-note-he.png", "png", hebrew=True, lines=[
    "הודעה להורים", "ביום שלישי יום פיגמות בגן", "הילדים יגיעו בפיגמה", "אפשר להביא בובה אחת"])

# ----------------------------------------------------------------- health (logistics only)
add("health/clinic-appointment-2026-11-18.pdf", "pdf", dir="rtl", title="זימון לתור", pages=[
    """<h1>זימון לתור - מרפאת הנביאים</h1>
<p>לכבוד: יונתן שני</p>
<p>נקבע עבורך תור לרופאת המשפחה, ד"ר רונית שגיא, ביום רביעי 18 בנובמבר 2026 בשעה 10:40.</p>
<p>כתובת המרפאה: שדרות הציונות 40, מודיעין, קומה 2.</p>
<h2>הנחיות</h2>
<ul><li>יש להגיע 10 דקות לפני מועד התור.</li><li>יש להביא תעודת זהות.</li>
<li>ביטול או שינוי תור: דרך האפליקציה, עד 24 שעות לפני המועד.</li></ul>
<p>מכתב זה נשלח באופן אוטומטי ואינו כולל מידע רפואי.</p>"""])

add("health/dental-checkup-2026-12.txt", "txt", text="""Smile Dental Clinic - appointment reminder

Patient: Yonatan Shani
Appointment: routine check-up and cleaning
Date: 2026-12-03 at 16:15, with Dr. Maya Kaplan
Address: 8 Emek Ayalon Blvd, Modiin, 1st floor

Price with your dental plan: 180 NIS.
Please cancel at least 24 hours in advance to avoid a 100 NIS no-show fee.
""")

add("health/glasses-reimbursement-guide.md", "md", text="""# החזר על משקפיים - קופת החולים

לפי תנאי התוכנית המשלימה (נבדק בספטמבר 2026):

- החזר של עד 300 ש"ח על משקפי ראייה או עדשות מגע.
- פעם אחת בכל שנתיים, לכל מבוטח.
- יש להגיש את הבקשה תוך 6 חודשים מיום הרכישה.

## מסמכים להגשה

1. קבלה מקורית מחנות האופטיקה, על שם המבוטח.
2. מרשם לעדשות מאופטומטריסט או רופא עיניים.

ההגשה דרך האתר או האפליקציה, בקטגוריה "החזרים". הכסף מגיע לחשבון הבנק תוך כ-30 יום.
""")

add("health/school-vaccination-notice-2026.md", "md", text="""# הודעה להורים: חיסון שגרתי בבית הספר

שירותי בריאות התלמיד יגיעו לבית הספר "נופים" ביום ראשון, 22 בנובמבר 2026, לחיסון שגרתי לפי תוכנית משרד הבריאות לשכבה.

- הורים שאינם מעוניינים בחיסון בבית הספר יחתמו על טופס הסירוב עד 15 בנובמבר.
- יש לשלוח את פנקס החיסונים או צילום שלו עם הילד.
- שאלות: אחות בית הספר, בימים א' ו-ג'.
""")

# ----------------------------------------------------------------- finance (templates, no real numbers)
add("finance/bank-standing-order-template.docx", "docx", title="תבנית הוראת קבע", rtl=True, paras=[
    ("h1", "תבנית: בקשה להקמת הוראת קבע"),
    ("p", "לכבוד בנק XXXX, סניף XXX"),
    ("p", "אני הח\"מ מבקש להקים הוראת קבע לחיוב חשבוני מספר XX-XXX-XXXXXX לטובת המוטב: ועד הבית, רחוב הנרקיס 12."),
    ("p", "סכום החיוב החודשי: XXX ש\"ח. מועד החיוב: ה-10 בכל חודש."),
    ("p", "ידוע לי שאוכל לבטל את ההוראה בכל עת בהודעה בכתב לבנק, והביטול ייכנס לתוקף תוך 3 ימי עסקים."),
    ("p", "חתימה: ________  תאריך: ________"),
])

add("finance/bank-account-confirmation-template.md", "md", text="""# Template: request for an account ownership confirmation

To: Bank XXXX, branch XXX

Please issue a letter confirming that account no. XX-XXX-XXXXXX is held in my name.
The letter is needed for: my employer's payroll department / the health fund refunds.

Notes for myself:
- The bank charges a fee for this letter unless it is downloaded from the app (free).
- In the app: Account > Documents > Account ownership confirmation.
""")

INS_PAGES = [
    """<h1>פוליסת ביטוח רכב מקיף 2026</h1>
<p>המבוטח: יונתן שני. רכב: מאזדה 3, שנת ייצור 2021.</p>
<p>תקופת הביטוח: מיום 1 בינואר 2026 ועד יום 31 בדצמבר 2026.</p>
<h2>1. כיסויים עיקריים</h2>
<p>נזק לרכב המבוטח בתאונה, גניבה, שריפה ונזקי טבע. נזק לרכוש צד שלישי עד 1,000,000 ש"ח.</p>""",
    """<h2>2. השתתפות עצמית</h2>
<ul><li>תיקון במוסך שבהסדר: 1,850 ש"ח לכל מקרה.</li>
<li>תיקון במוסך שאינו בהסדר: 3,700 ש"ח לכל מקרה.</li>
<li>החלפת שמשה קדמית ברשת המורשית: 450 ש"ח.</li>
<li>גניבה מוחלטת: 10% משווי הרכב.</li></ul>
<h2>3. נהגים מורשים</h2>
<p>כל נהג מעל גיל 24 עם ותק של שנתיים לפחות.</p>""",
    """<h2>4. שירותים נוספים</h2>
<p>שירותי גרירה ודרך 24 שעות ביממה, בכל הארץ, בטלפון 050-555-0177.</p>
<p>רכב חלופי: עד 7 ימים במקרה של תאונה, ועד 30 ימים במקרה של גניבה.</p>
<h2>5. הגשת תביעה</h2>
<p>יש לדווח על אירוע תוך 7 ימים, ולצרף דו"ח שמאי ותמונות של הנזק.</p>""",
]
add("finance/car-insurance-2026.pdf", "pdf", dir="rtl", title="פוליסת ביטוח רכב 2026", pages=INS_PAGES)

add("finance/tax-refund-checklist-2025.md", "md", text="""# החזר מס לשנת 2025 - רשימת מסמכים

אפשר להגיש בקשה להחזר מס עד 6 שנים אחורה. את הבקשה לשנת 2025 אפשר להגיש כבר מינואר 2026.

## מה צריך

- טופס 106 מכל מעסיק שעבדתי אצלו בשנה (בית הספר + העבודה הנוספת).
- קבלות על תרומות למוסדות מוכרים (סעיף 46): זיכוי של 35% מהסכום.
- אישור על ילדים: נקודות זיכוי על מאיה ואיתי.
- אישור ניכוי מס במקור, אם היו הכנסות מעבודה עצמאית.

## איך מגישים

דרך האזור האישי באתר רשות המסים, טופס 135. תשובה מגיעה בדרך כלל תוך 90 יום.
""")

add("finance/pension-annual-statement-2025.html", "html", lang="en", text="""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Annual pension statement 2025 - summary</title></head>
<body><nav>Home | My savings | Documents | Logout</nav><main>
<h1>Annual pension statement 2025 (summary)</h1>
<p>Member: Yonatan Shani. Fund: Horizon Pension (fictional). Track: general, age-based.</p>
<p>Management fees: 0.22% of the accumulated savings per year, and 1.5% of each monthly deposit.</p>
<p>Return in 2025 for your track: 7.4% (before fees).</p>
<p>Insurance coverage: disability and survivors, according to the default coverage of the fund.</p>
<p>To change your investment track, log in and choose My savings &gt; Change track. The change applies from the next month.</p>
</main><footer>Horizon Pension | Privacy | Accessibility</footer></body></html>""")

# ----------------------------------------------------------------- courses and work notes
RAG = """# RAG notes (AI Engineer course)

## Lexical search
BM25 ranks chunks by term frequency and inverse document frequency. Parameters: k1 controls term saturation (1.2 is a good default), b controls length normalization (0.75).
It is great for exact names, numbers and codes, and weak for paraphrases.

## Dense retrieval
Embeddings map text to vectors; cosine similarity finds paraphrases and cross-lingual matches.
multilingual-e5 needs the prefixes "query: " and "passage: ".

## Hybrid
Reciprocal Rank Fusion: score = sum of 1/(k + rank) over the lists, with k = 60.
RRF ignores the raw scores, so BM25 and cosine scores never need to be on the same scale.

## Chunking
Chunks of 200-400 tokens with an overlap of about 10-15%. Keep the title and the section path with each chunk.
"""
add("courses/ai-engineer-rag-notes.md", "md", text=RAG)
add("courses/ai-engineer-rag-notes-v2.md", "md", text=RAG.replace(
    "(1.2 is a good default)", "(1.2 is a good default, 1.5 for long documents)").replace(
    "# RAG notes (AI Engineer course)", "# RAG notes (AI Engineer course) - v2, after lesson 12"))

add("courses/prompting-notes-he.md", "md", text="""# סיכום: הנדסת פרומפטים

- **Few-shot**: שתיים עד חמש דוגמאות מגוונות עדיפות על הסבר ארוך. הדוגמאות קובעות את הפורמט יותר מההוראות.
- **Structured outputs**: עם JSON Schema המודל מחזיר אובייקט תקין, אבל עדיין צריך ולידציה של הערכים.
- **Temperature**: בחילוץ עובדות 0 עד 0.3. בכתיבה יצירתית 0.7 ומעלה.
- הוראת מערכת קבועה בתחילת הפרומפט, כדי שה-prompt cache יעבוד.
- תמיד לבדוק על סט דוגמאות קבוע לפני ואחרי שינוי בפרומפט.
""")

add("courses/home-budget-app-spec.md", "md", text="""# אפליקציה לניהול תקציב משפחתי - אפיון ראשוני

## קהל יעד

משפחות שרוצות לראות פעם בשבוע לאן הלך הכסף, בלי להקליד כל קנייה ביד.

## תכונות ל-MVP

1. ייבוא של קובץ התנועות מהבנק, ומיון אוטומטי לקטגוריות: מזון, חינוך, רכב, בית.
2. סיכום שבועי קצר: כמה הוצאנו בכל קטגוריה לעומת השבוע הקודם.
3. יעד חיסכון אחד, עם פס התקדמות.

## לא ב-MVP

חיבור ישיר לבנק, שיתוף בין כמה משתמשים, והתראות. קודם לוודא שהסיכום השבועי באמת נקרא.
""")

add("courses/guitar-practice-ideas.md", "md", text="""# רעיונות לתרגול גיטרה למתחילים

## חימום של חמש דקות

- סולם כרומטי לאט על כל המיתרים, ארבע אצבעות, עם מטרונום על 60.
- מתיחות קלות לאצבעות של יד שמאל לפני שמתחילים.

## אקורדים פתוחים

- להחליף בין שני אקורדים (למשל לה מינור ומי מינור) דקה שלמה בלי לעצור. סופרים כמה החלפות.
- שיר אחד פשוט בשלושה אקורדים בכל שבוע, עד שהוא יוצא בלי להסתכל על היד.

## קצב

פריטה בסיסית למטה-למטה-למעלה, קודם בלי אקורדים, רק על מיתרים מושתקים. רק כשהקצב יציב מוסיפים אקורדים.
""")

add("courses/node-backend-cheatsheet.md", "md", text="""# Node.js backend cheat sheet

- Express error handling: an error middleware has four arguments (err, req, res, next) and goes last.
- Async route handlers: wrap them, or use Express 5, which forwards rejected promises to the error middleware.
- Graceful shutdown: on SIGTERM stop accepting connections, finish in-flight requests, close the DB pool.
- pm2: `pm2 start app.js -i max` runs one process per CPU core; `pm2 logs` tails the logs.
- Never log request bodies with personal data; redact before logging.
""")

# ----------------------------------------------------------------- recipes
SHAK = """# שקשוקה של שבת בבוקר

## מצרכים (ל-4 סועדים)

- 6 עגבניות בשלות, קצוצות
- 4 ביצים
- 1 פלפל אדום ו-3 שיני שום
- כפית כמון, כפית פפריקה מתוקה, מלח
- 3 כפות שמן זית

## אופן ההכנה

מטגנים את השום והפלפל בשמן זית 5 דקות. מוסיפים עגבניות ותבלינים ומבשלים על אש בינונית 15 דקות, עד שהרוטב מסמיך. עושים גומות, שוברים לתוכן את הביצים, מכסים ומבשלים עוד 6 דקות.
"""
add("recipes/shakshuka.md", "md", text=SHAK)
add("recipes/shakshuka-copy.md", "md", text=SHAK.replace("- 4 ביצים", "- 5 ביצים").replace(
    "עוד 6 דקות", "עוד 7 דקות"))

add("recipes/lentil-soup.txt", "txt", text="""Red lentil soup (serves 4, 35 minutes)

1.5 cups red lentils, rinsed
1 onion, 2 carrots, 2 garlic cloves
1 tsp cumin, 1/2 tsp turmeric
6 cups water or vegetable stock
juice of half a lemon

Fry the onion and carrots for 8 minutes, add garlic and spices for 1 minute, then the lentils
and water. Simmer 25 minutes and blend. Finish with lemon juice and salt.
""")

add("recipes/grandma-challah.docx", "docx", title="החלה של סבתא", rtl=True, paras=[
    ("h1", "החלה של סבתא"),
    ("h2", "מצרכים"),
    ("li", "1 ק\"ג קמח לבן"),
    ("li", "50 גרם שמרים טריים"),
    ("li", "3/4 כוס סוכר"),
    ("li", "2 ביצים ועוד ביצה להברשה"),
    ("li", "1/2 כוס שמן ו-1.5 כוסות מים פושרים"),
    ("h2", "הכנה"),
    ("p", "לשים 10 דקות עד לקבלת בצק רך. מתפיחים שעה וחצי, קולעים שתי חלות ומתפיחים עוד חצי שעה."),
    ("p", "מברישים בביצה ואופים בתנור שחומם ל-180 מעלות במשך 30 דקות, עד שהחלות שחומות."),
])

add("recipes/pita-bread.html", "html", lang="en", text="""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Fluffy homemade pita bread | Best Recipes Blog</title></head>
<body>
<nav>Home | Breads | Desserts | Subscribe | Shop</nav>
<aside>Sponsored: buy our cookbook! 30% off this week only.</aside>
<main>
<h1>Fluffy homemade pita bread</h1>
<p>Makes 8 pitas. Ingredients: 500 g flour, 7 g dry yeast, 1 tsp sugar, 1.5 tsp salt, 330 ml warm water, 2 tbsp olive oil.</p>
<p>Knead for 8 minutes and let the dough rise for 1 hour. Divide into 8 balls and roll each to 5 mm.</p>
<p>Bake on a preheated stone or tray at 250°C for about 4 minutes, until the pitas puff up. Keep them covered with a towel so they stay soft.</p>
</main>
<footer>© Best Recipes Blog. All rights reserved. Cookie settings.</footer>
</body></html>""")

# ----------------------------------------------------------------- travel
add("travel/rome-hotel-booking-2026-08.pdf", "pdf", dir="ltr", title="Hotel booking confirmation", pages=[
    """<h1>Booking confirmation - Old Town Rooms, Rome</h1>
<p>Guest: Yonatan Shani, 2 adults and 2 children. Confirmation number: OTR-58213.</p>
<p>Arrival: 3 August 2026. Departure: 7 August 2026 (4 nights). Family room with a balcony.</p>
<h2>Check-in and check-out</h2>
<p>Check-in from 14:00. Check-out until 11:00. Late check-out until 14:00 costs 20 USD, subject to availability.</p>
<h2>Cancellation policy</h2>
<p>Free cancellation until 48 hours before arrival. After that, the first night is charged.</p>""",
    """<h2>Parking and transfers</h2>
<p>Private parking near the hotel: 15 EUR per night, reservation needed.</p>
<p>Airport transfer: 60 EUR each way for up to 4 passengers. Book at least one day in advance by email.</p>
<h2>Payment</h2>
<p>Total price: 420 USD, paid at the property in cash or by card. City tax is included.</p>""",
])

add("travel/flight-eticket-tlv-fco-2026-08.html", "html", lang="en", text="""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Your e-ticket - QZ7K2P</title></head>
<body><header>FlyEast - Manage booking</header><main>
<h1>E-ticket receipt</h1>
<p>Booking reference: QZ7K2P. Passengers: 4 (2 adults, 2 children).</p>
<p>Outbound: 3 August 2026, Tel Aviv (TLV) 06:10 to Rome (FCO) 09:05, flight FE 701.</p>
<p>Return: 14 August 2026, Rome (FCO) 22:40 to Tel Aviv (TLV) 00:55 (+1), flight FE 702.</p>
<p>Baggage allowance per passenger: one checked bag of 23 kg and one cabin bag of 8 kg.</p>
<p>Online check-in opens 24 hours before departure.</p>
</main><footer>FlyEast | Conditions of carriage</footer></body></html>""")

add("travel/car-rental-italy-voucher.pdf", "pdf", dir="ltr", title="Car rental voucher", pages=[
    """<h1>Car rental voucher - Roma Auto</h1>
<p>Driver: Yonatan Shani. Voucher number: KC-2026-0815.</p>
<p>Pick-up: Rome Fiumicino Airport, 3 August 2026, 10:00. Return: Rome Fiumicino Airport, 14 August 2026, 19:00.</p>
<p>Car: Toyota RAV4 4x4 or similar, automatic. Unlimited mileage.</p>
<h2>Deposit and insurance</h2>
<p>A security deposit of 300 USD is blocked on the driver's credit card at pick-up and released within 14 days after return.</p>
<p>Insurance: CDW included, with an excess of 500 USD. Driving on unpaved country roads is not covered.</p>"""])

add("travel/packing-list-italy.md", "md", text="""# רשימת ציוד לאיטליה, אוגוסט 2026

- דרכונים לכל המשפחה (לבדוק תוקף של לפחות 6 חודשים)
- רישיון נהיגה בינלאומי
- מעילים קלים: בדולומיטים קר בערב גם באוגוסט
- כיסאות בטיחות? לבדוק מול חברת ההשכרה
- מתאם חשמל: באיטליה שקע מסוג F/L
- תרופות קבועות ופלסטרים
- כסף מזומן ביורו לכפרים הקטנים
""")

add("travel/eilat-weekend-ideas.md", "md", text="""# סוף שבוע באילת - רעיונות

- שנורקלינג בחוף האלמוגים: להגיע בבוקר, לפני החום. כניסה בתשלום לשמורה.
- פארק תמנע: מסלול קצר לפטריות ולעמודי שלמה, מתאים לילדים. כדאי לצאת עד 09:00.
- מצפה התת-ימי: יקר, אבל הילדים אוהבים.
- לינה: לבדוק דירות נופש עם מטבח, זה זול יותר מבית מלון למשפחה.
- בקיץ: לא לטייל בצהריים, 40 מעלות ומעלה.
""")

# ----------------------------------------------------------------- what must never be indexed
add("private/passwords-DO-NOT-INDEX.txt", "txt", text="""THIS FILE MUST NEVER BE INDEXED.
(Fictional placeholder used by the project's privacy tests.)
wifi password: placeholder-not-a-real-password
safe code: 0000
""")
add(".cache/thumbnails-index.md", "md", text="# hidden cache file\nThis hidden folder must be skipped by the scanner.\n")

# ---------------------------------------------------------------------------------- writers
HTML_PAGE = """<!doctype html><html dir="{dir}" lang="{lang}"><head><meta charset="utf-8"><title>{title}</title>
<style>
@page {{ size: A4; margin: 22mm 18mm; }}
body {{ font-family: 'DejaVu Sans', sans-serif; font-size: 12pt; line-height: 1.5; }}
h1 {{ font-size: 18pt; }} h2 {{ font-size: 14pt; margin-top: 16pt; }}
.pb {{ page-break-after: always; }}
</style></head><body>{body}</body></html>"""


def write_pdf(path: Path, spec: dict, browser) -> None:
    body = '<div class="pb"></div>'.join(spec["pages"])
    html = HTML_PAGE.format(dir=spec["dir"], lang="he" if spec["dir"] == "rtl" else "en",
                            title=spec["title"], body=body)
    page = browser.new_page()
    page.set_content(html)
    page.pdf(path=str(path), format="A4", print_background=False)
    page.close()


def write_docx(path: Path, spec: dict) -> None:
    import docx
    from docx.oxml.ns import qn

    d = docx.Document()
    d.core_properties.title = spec["title"]
    d.core_properties.author = "Me"
    d.core_properties.created = FIXED_DATE
    d.core_properties.modified = FIXED_DATE
    for kind, text in spec["paras"]:
        if kind == "h1":
            p = d.add_heading(text, level=1)
        elif kind == "h2":
            p = d.add_heading(text, level=2)
        elif kind == "li":
            p = d.add_paragraph(text, style="List Bullet")
        else:
            p = d.add_paragraph(text)
        if spec.get("rtl"):
            ppr = p._p.get_or_add_pPr()
            bidi = ppr.makeelement(qn("w:bidi"), {})
            ppr.append(bidi)
    d.save(str(path))


def write_png(path: Path, spec: dict) -> None:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    lines = spec["lines"]
    w, h = 1100, 90 + 60 * len(lines)
    img = Image.new("L", (w, h), 255)
    dr = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        if spec.get("hebrew"):
            # PIL has no bidi: draw the characters in visual order, right-aligned
            vis = line[::-1]
            tw = dr.textlength(vis, font=font)
            dr.text((w - 60 - tw, 45 + 60 * i), vis, fill=0, font=font)
        else:
            dr.text((60, 45 + 60 * i), line, fill=0, font=font)
    img.save(str(path), optimize=True)


def main() -> None:
    from playwright.sync_api import sync_playwright

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for rel, spec in FILES.items():
            p = OUT / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            kind = spec["kind"]
            if kind in ("md", "txt", "html"):
                p.write_text(spec["text"], encoding="utf-8")
            elif kind == "pdf":
                write_pdf(p, spec, browser)
            elif kind == "docx":
                write_docx(p, spec)
            elif kind == "png":
                write_png(p, spec)
        browser.close()
    for rel, spec in FILES.items():          # copies last, so the source exists
        if spec["kind"] == "copy":
            shutil.copyfile(OUT / spec["source"], OUT / rel)
    # stable modification times (git does not keep them anyway; the date filter prefers the
    # date in the file name or the document's own metadata, see pss/extract.py)
    ts = FIXED_DATE.timestamp()
    for p in OUT.rglob("*"):
        if p.is_file():
            os.utime(p, (ts, ts))
    n = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"wrote {n} files to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
