// Lesson 27 — Containers and Public-Cloud Deployment.
window.LESSONS = window.LESSONS || {};
window.LESSONS["27"] = {
  n: 27,
  title: "Containers and Public-Cloud Deployment",
  he: "Docker, סודות, IAM ופריסה לענן",
  hours: "כשלוש שעות שיעור, כחמש שעות מעבדה (מתוכן שעה עד שלוש בתשלום ב-AWS: כ-5 סנט לשעה לפי <code>deploykit/cost.py</code>, כלומר כ-0.05$ עד 0.15$, הערכה)",

  goals: [
    "להבין מה <b>image</b> ו-<b>container</b> הם באמת: ערימה של שכבות קבצים ועוד config, ותהליך רגיל עם בידוד. ולמה ה-image הוא ה-artifact היחיד שעובר מהמחשב שלך לענן.",
    "לכתוב <b>Dockerfile לפרודקשן</b> לשירות Python: multi-stage, base image מסוג slim עם גרסה מוצמדת, תלויות נעולות עם <b>uv</b>, משתמש שאינו root, HEALTHCHECK, ו-CMD בצורת exec.",
    "להבין את <b>cache השכבות</b>: למה סדר ההוראות קובע אם בנייה לוקחת 3 שניות או 3 דקות, ואיך מודדים את גודל ה-image ומקטינים אותו.",
    "לנהל <b>סודות</b> נכון: לראות בעיניים איך מפתח שנאפה לתוך image דולף (history, config, שכבה שנמחקה), ולהזריק אותו בזמן ריצה: compose secrets מקומית, ו-<b>AWS Secrets Manager</b> בענן.",
    "להריץ <b>סטאק מקומי</b> עם docker compose: השירות, mockllm, health checks, פרופילים וסודות, בלי עלות.",
    "לבחור <b>איפה לפרוס ב-AWS</b> ב-2026: ECS Fargate עם ALB, ECS Express Mode, Lambda, ולמה App Runner כבר לא פתוח ללקוחות חדשים.",
    "להגדיר תשתית בקוד עם <b>Terraform</b>: ECS, ALB, ECR, Secrets Manager, CloudWatch ו-autoscaling, עם <b>IAM של הרשאות מינימליות</b> והפרדה בין execution role ל-task role.",
    "לדעת <b>כמה זה עולה</b> לפני שזה עולה: מודל עלות לפי שורות, תקציב עם התראות, <code>terraform plan</code> לפני כל <code>apply</code>, ופירוק מלא שנבדק.",
  ],
  connects: "ב<b>נושא 26</b> בנית את ה-API של Company Brain עם FastAPI, סטרימינג ו-health endpoints. כאן הוא יוצא מהמחשב שלך: נארז ב-image, רץ ב-compose, ונפרס ל-AWS. השירות במעבדה בנוי באותה צורה כמו servekit, כך שאפשר להחליף ביניהם. ה-<b>least privilege</b> כאן הוא אותו עיקרון מ<b>נושא 24</b> (אבטחה), רק ברמת התשתית. הלוגים של JSON שתראה ב-CloudWatch הם הבסיס ל<b>נושא 22</b> (observability), וה-compose הוא המקום שבו ה-gateway מ<b>נושא 25</b> יתחבר. בפרויקט הסיום, Company Brain כולו נפרס ב-AWS בדיוק בדרך הזו.",

  intro: {
    animation: "l27build",
    animationTitle: "בנייה של image: שכבות, cache, ומה נכנס ל-image הסופי",
    animationGuide: `<p><b>מה רואים כאן:</b> Docker בונה את ה-Dockerfile של המעבדה, הוראה אחרי הוראה. משמאל (בצד האנגלי) ה-Dockerfile, והשורה שרצה עכשיו מסומנת. מימין <b>ערימת השכבות</b>: כל הוראה שמשנה קבצים מוסיפה שכבה, עם הגודל שלה. ההוראות מסודרות בארבעה שלבים (builder, runtime, mockllm, api), וכל שלב הוא ערימה נפרדת.</p>
<p><b>שלושה צבעים לכל שכבה:</b></p>
<ol>
<li><b>ירוק, CACHED:</b> Docker כבר בנה את השכבה הזו בעבר, עם אותה הוראה ואותם קבצי קלט, ולכן הוא משתמש בה כמו שהיא. זה לוקח אפס זמן.</li>
<li><b>כתום, בונה:</b> משהו בקלט השתנה, אז השכבה נבנית מחדש. וחשוב: <b>כל השכבות שאחריה באותו שלב נבנות מחדש גם הן</b>, כי כל שכבה נבנית מעל זו שלפניה.</li>
<li><b>אפור עם קו:</b> שכבה של שלב builder שלא מגיעה ל-image הסופי. רק מה שמועתק במפורש עם <code>COPY --from=builder</code> עובר.</li>
</ol>
<p><b>איך לעבוד איתה:</b> בחר למעלה מה השתנה מאז הבנייה הקודמת: "בנייה ראשונה", "שיניתי קוד", או "שיניתי תלות". הפעל, וראה אילו שכבות נבנות מחדש וכמה זמן זה לוקח בערך. בסוף מופיע הגודל של ה-image הסופי, ולצידו מה היה הגודל עם Dockerfile של שלב אחד. שווה לנסות גם את המתג "סדר גרוע", שמעתיק את הקוד <b>לפני</b> התקנת התלויות, ולראות מה קורה לשינוי קוד קטן.</p>
<p>הזמנים והגדלים הם הערכות שהוכנו לשיעור. את המספרים האמיתיים במחשב שלך תמדוד בתרגיל 1 ו-2.</p>`,
    videos: [
      {
        title: "Building best practices",
        who: "Docker docs",
        part: "multi-stage builds, base image, build cache, pin versions, USER",
        minutes: 25,
        url: "https://docs.docker.com/build/building/best-practices/",
        required: true,
        kind: "תיעוד",
        why: "המסמך הרשמי של Docker על איך כותבים Dockerfile. כמעט כל כלל בבודק הסטטי של המעבדה מופיע כאן, עם ההסבר של Docker עצמם.",
      },
      {
        title: "Using uv in Docker",
        who: "Astral (uv docs)",
        part: "Intermediate layers, Non-editable installs, Caching, Compiling bytecode",
        minutes: 15,
        url: "https://docs.astral.sh/uv/guides/integration/docker/",
        required: true,
        kind: "תיעוד",
        why: "המקור של שלב ה-builder ב-Dockerfile של המעבדה: העתקת uv מה-image הרשמי, cache mount, ושני שלבי sync כדי שהתלויות יישבו בשכבה נפרדת מהקוד.",
      },
      {
        title: "Amazon ECS task execution IAM role",
        who: "AWS docs",
        part: "ההבדל בין execution role ל-task role, והרשאות ל-ECR, ל-logs ול-Secrets Manager",
        minutes: 15,
        url: "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html",
        required: true,
        kind: "תיעוד",
        why: "שני ה-roles של ECS הם המקור הנפוץ ביותר לטעויות IAM. כאן כתוב בדיוק מה כל אחד צריך, וזה מה ש-iam.tf במעבדה מממש.",
      },
      {
        title: "Production-ready Python Docker Containers with uv",
        who: "Hynek Schlawack",
        part: "המאמר כולו (עודכן באוגוסט 2026)",
        minutes: 20,
        url: "https://hynek.me/articles/docker-uv/",
        required: false,
        kind: "מאמר",
        why: "מאמר מעשי ומנומק של מפתח Python מוכר: למה --locked ולא --frozen, איפה לבנות את ה-venv, ולמה לא להריץ כ-root. משלים את התיעוד של uv.",
      },
      {
        title: "Get Started: AWS",
        who: "HashiCorp Developer",
        part: "Create, Manage ו-Destroy infrastructure",
        minutes: 35,
        url: "https://developer.hashicorp.com/terraform/tutorials/aws-get-started",
        required: false,
        kind: "קורס",
        why: "אם לא עבדת עם Terraform, זה המבוא הרשמי והקצר: init, plan, apply, state ו-destroy על משאב אחד, לפני ה-21 של המעבדה.",
      },
    ],
  },

  slides: [
    {
      kicker: "פתיחה",
      title: "מ\"עובד אצלי\" לשירות שרץ בלעדיך",
      html: `<p class="big">ה-API של Company Brain עובד במחשב שלך: venv, קובץ <code>.env</code>, <code>uvicorn</code> בטרמינל. אבל כל אחד מהדברים האלה קיים רק אצלך. שירות אמיתי צריך לרוץ על מכונה שאתה לא רואה, שעולה ויורדת בלי שתדע, ושמישהו אחר יכול להפעיל מחר בבוקר מאותו מקור בדיוק.</p>
<p>הפער הזה נסגר בשני צעדים. הראשון הוא <b>container</b>: אורזים את הקוד, ה-Python, התלויות וההגדרות של מערכת ההפעלה לקובץ אחד שלא משתנה, ה-<b>image</b>. אותו image רץ אצלך, ב-CI ובענן, וזה מה שמבטל את "אבל אצלי זה עבד". הצעד השני הוא <b>תשתית בקוד</b>: הרשת, ה-load balancer, ההרשאות והסודות מוגדרים בקבצים, כך שאפשר לקרוא אותם, לבדוק אותם, ליצור אותם ולמחוק אותם בפקודה אחת.</p>
<p>לשירות LLM יש כמה מאפיינים שמשנים את ההחלטות לאורך השיעור, וכדאי להכיר אותם מראש:</p>
<ul>
<li><b>הוא מחכה, לא מחשב.</b> רוב הזמן של בקשה עובר בהמתנה לתשובה מ-Anthropic. ה-CPU כמעט לא עובד גם כשהשירות עמוס, ולכן autoscaling לפי CPU מגיב מאוחר מדי.</li>
<li><b>בקשות ארוכות.</b> תשובה בסטרימינג יכולה להחזיק חיבור פתוח עשרות שניות. זה משפיע על ה-timeout של ה-load balancer ועל כיבוי מסודר של משימה בזמן deployment.</li>
<li><b>הסוד שווה כסף.</b> מפתח API שדלף לא חושף רק מידע, הוא מאפשר למישהו אחר להוציא כסף על החשבון שלך. לכן חצי מהשיעור עוסק באיפה המפתח נמצא ומי יכול לקרוא אותו.</li>
<li><b>שתי חשבוניות.</b> על הטוקנים משלמים לספק המודל, ועל התשתית משלמים ל-AWS, גם כשאין אף בקשה. את השנייה קל לשכוח.</li>
</ul>
<div class="callout">החלטה של השיעור: הענן הוא <b>AWS</b>, ויש לכל צעד גם <b>מסלול מקומי חינמי</b> עם Docker ו-mockllm. רק תרגיל 8 עולה כסף, בערך 5 סנט לשעה, והוא נגמר בפירוק מלא.</div>`,
    },
    {
      kicker: "מנגנון",
      title: "מה זה image ומה זה container, באמת",
      html: `<p>container הוא לא מכונה וירטואלית. הוא <b>תהליך רגיל</b> של Linux, שהקרנל מבודד בשני מנגנונים: <b>namespaces</b> קובעים מה התהליך רואה (מערכת קבצים משלו, רשת משלו, רשימת תהליכים שבה הוא PID 1), ו-<b>cgroups</b> קובעים כמה הוא יכול לצרוך (CPU וזיכרון). אין קרנל נוסף ואין מערכת הפעלה מלאה שעולה, ולכן container עולה בשנייה ולא בדקה.</p>
<p>ה-<b>image</b> הוא מה שה-container מתחיל ממנו, והוא בנוי משני חלקים:</p>
<ul>
<li><b>ערימה של שכבות.</b> כל שכבה היא קובץ tar של שינויים במערכת הקבצים: קבצים שנוספו, שהשתנו, או סימון שקובץ נמחק. בזמן ריצה הן נערמות אחת על השנייה למערכת קבצים אחת, ומעליהן שכבה דקה וזמנית שה-container כותב אליה.</li>
<li><b>config.</b> JSON עם משתני הסביבה, המשתמש, ה-CMD, הפורטים וה-HEALTHCHECK. כל מי שמושך את ה-image יכול לקרוא אותו עם <code>docker inspect</code>, וזה יהיה חשוב כשנדבר על סודות.</li>
</ul>
<p>ה-image נשמר ב-<b>registry</b> (Docker Hub, ghcr.io, או ECR ב-AWS), ומזוהה בשני אופנים. <b>tag</b> כמו <code>python:3.12-slim</code> הוא שם, ואפשר להזיז אותו לגרסה אחרת בכל רגע: מחר <code>3.12-slim</code> יצביע על patch חדש. <b>digest</b> כמו <code>python@sha256:4f...</code> הוא ה-hash של התוכן, והוא תמיד אותו image בדיוק.</p>
<div class="example"><b>לראות את זה בעיניים</b><pre dir="ltr">docker history company-brain-api:dev     # the layers, one per instruction, with sizes
docker inspect company-brain-api:dev --format '{{json .Config}}'   # the config
docker save company-brain-api:dev -o img.tar && tar -tf img.tar  # the tar files themselves</pre></div>
<div class="callout">מה שחשוב לזכור: image הוא <b>artifact שלא משתנה</b>. לא מתקנים container שרץ, בונים image חדש ומחליפים. ומה שנכנס לשכבה פעם אחת נשאר ב-image, גם אם שכבה מאוחרת יותר "מוחקת" אותו.</div>`,
    },
    {
      kicker: "Cache",
      title: "שכבות ו-cache: למה סדר ההוראות קובע את זמן הבנייה",
      html: `<p>כשאתה בונה שוב, Docker בודק כל הוראה לפי הסדר: האם כבר בניתי שכבה מאותה הוראה, מעל אותה שכבה קודמת, עם אותם קבצי קלט? אם כן, הוא משתמש בה (<code>CACHED</code>). אם לא, הוא בונה אותה מחדש, ו<b>גם את כל מה שבא אחריה באותו שלב</b>, כי כל שכבה נבנית מעל קודמתה.</p>
<p>מכאן הכלל: <b>מה שמשתנה לעיתים רחוקות למעלה, מה שמשתנה כל הזמן למטה.</b> התלויות משתנות פעם בשבועות, הקוד משתנה עשר פעמים ביום. ולכן מתקינים את התלויות לפני שמעתיקים את הקוד:</p>
<div class="example"><b>שלב ה-builder ב-Dockerfile של המעבדה</b><pre dir="ltr">RUN --mount=type=cache,target=/root/.cache/uv \\
    --mount=type=bind,source=labs/27-deployment/app/uv.lock,target=uv.lock \\
    --mount=type=bind,source=labs/27-deployment/app/pyproject.toml,target=pyproject.toml \\
    uv sync --locked --no-install-project
# ...and only later, in the api stage:
COPY labs/27-deployment/app/service/ /app/service/</pre></div>
<ul>
<li><b>bind mount של שני קבצים בלבד.</b> השלב רואה רק את <code>uv.lock</code> ו-<code>pyproject.toml</code>. שינוי ב-<code>main.py</code> לא נוגע בקלט שלו, ולכן הוא נשאר CACHED. בתרגיל 2 תראה את זה בפלט של BuildKit.</li>
<li><b>cache mount.</b> <code>--mount=type=cache</code> שומר את ה-wheels שהורדו <b>בין בניות</b>, בלי שהם ייכנסו לאף שכבה. כשתלות אחת משתנה, uv מוריד רק אותה.</li>
<li><b>הסדר הגרוע.</b> <code>COPY . .</code> ואחריו <code>pip install</code>: כל שינוי בקוד, אפילו הערה, מבטל את ה-cache של ההתקנה, וכל בנייה מורידה ומתקינה הכול מחדש. באנימציה של הפתיחה יש מתג שמראה בדיוק את זה.</li>
</ul>
<p>הבדל של 3 שניות מול 2 דקות לבנייה לא נשמע דרמטי, עד שזוכרים שב-CI הוא קורה בכל push, ושמפתח שמחכה 2 דקות לכל ניסיון מפסיק לבדוק בתוך container ומתחיל לבדוק "רק אצלו".</p>`,
    },
    {
      kicker: "גודל",
      title: "Multi-stage ו-slim: מה נשאר ב-image הסופי",
      html: `<p>image גדול הוא לא רק עניין של דיסק. הוא נמשך לאט יותר בכל פעם שמשימה עולה בענן, ולכן scale out איטי יותר, ובעיקר יש בו יותר חבילות, כלומר יותר פגיעויות ידועות שסורק ימצא ותוקף ינצל. יש שני מנופים גדולים:</p>
<h4>1. ה-base image</h4>
<ul>
<li><b><code>python:3.12</code></b>: Debian מלא עם קומפיילרים, כותרות וכלי פיתוח. בערך גיגה-בייט.</li>
<li><b><code>python:3.12-slim</code></b>: Debian מינימלי עם Python. בערך מאה ומשהו מגה-בייט. מאז אוגוסט 2025 ברירת המחדל שלו היא Debian 13 (trixie). זו הבחירה הסבירה לרוב שירותי Python.</li>
<li><b>Alpine</b>: קטן עוד יותר, אבל עם musl במקום glibc. הרבה wheels של Python מוכנים ל-glibc בלבד, ואז pip מתחיל לקמפל, הבנייה מתארכת וה-image גדל. לשירותי Python בדרך כלל לא שווה את זה.</li>
<li><b>Distroless</b>: רק Python והספריות שלו, בלי shell ובלי מנהל חבילות. משטח תקיפה קטן מאוד, אבל אי אפשר להיכנס ל-container עם shell כדי לדבג.</li>
</ul>
<h4>2. Multi-stage</h4>
<p>שלב <b>builder</b> מכיל את כל מה שצריך כדי <b>לבנות</b>: uv, cache, ולפעמים קומפיילר. שלב <b>runtime</b> מתחיל מ-base נקי, ומקבל רק את התוצאה: <code>COPY --from=builder /opt/venv /opt/venv</code>. כל מה שלא הועתק במפורש פשוט לא קיים ב-image הסופי. ב-Dockerfile של המעבדה יש ארבעה שלבים, וה-<b>אחרון</b>, <code>api</code>, הוא מה ש-<code>docker build</code> מייצר כברירת מחדל. את <code>mockllm</code> בונים רק כשמבקשים במפורש <code>--target mockllm</code>, וכך עושה compose.</p>
<div class="callout">בתרגיל 1 תמדוד את שני ה-images, ותפריד בין התרומה של ה-base לתרומה של ה-multi-stage. אם המדידה שלך שונה מההערכות כאן, המדידה צודקת.</div>`,
    },
    {
      kicker: "שחזוריות",
      title: "תלויות נעולות עם uv, ובנייה שאפשר לשחזר",
      html: `<p>שתי בניות של אותו Dockerfile צריכות לייצר את אותה תוכנה. <code>RUN pip install fastapi uvicorn</code> לא עומד בזה: הוא מתקין את מה שעדכני ביום הבנייה, וגרסה חדשה של תלות עקיפה יכולה לשבור את השירות בלי שאף אחד שינה שורת קוד. יש כאן ארבע שכבות של הצמדה, מהחלשה לחזקה:</p>
<ol class="ladder">
<li><b>שמות חבילות בלבד</b><span><code>pip install fastapi</code>. כל בנייה היא הגרלה. זה <code>Dockerfile.single</code> במעבדה.</span></li>
<li><b>טווחים ב-pyproject.toml</b><span><code>fastapi>=0.162</code>: מבטא כוונה, לא מבטיח שחזור. התלויות העקיפות עדיין פתוחות.</span></li>
<li><b>קובץ lock</b><span><code>uv.lock</code> נועל <b>כל</b> חבילה, כולל העקיפות, לגרסה מדויקת ול-hash של הקובץ. <code>uv sync --locked</code> נכשל אם ה-lock לא תואם ל-pyproject, במקום לפתור מחדש בשקט.</span></li>
<li class="danger"><b>base image לפי digest</b><span>גם <code>python:3.12.16-slim-trixie</code> הוא tag שיכול לזוז אם נבנה מחדש עם תיקוני אבטחה. רק <code>@sha256:...</code> מבטיח את אותם בייטים. המחיר: צריך לעדכן אותו במכוון, אחרת לא מקבלים תיקוני אבטחה.</span></li>
</ol>
<p>הגדרות ה-uv ב-builder, ולמה כל אחת קיימת:</p>
<ul>
<li><b><code>UV_COMPILE_BYTECODE=1</code></b>: מקמפל <code>.pyc</code> בזמן הבנייה, כך שה-container לא עושה את זה בכל הפעלה. מתבטא בזמן עלייה.</li>
<li><b><code>UV_PYTHON_DOWNLOADS=0</code></b>: להשתמש ב-Python של ה-image, ולא להוריד גרסה אחרת בשקט.</li>
<li><b><code>UV_LINK_MODE=copy</code></b>: ה-cache יושב ב-mount נפרד, ולכן hard links לא יעבדו.</li>
<li><b><code>COPY --from=ghcr.io/astral-sh/uv:0.13.6</code></b>: uv כקובץ בינארי מה-image הרשמי, בגרסה מוצמדת. גם הכלי שבונה הוא חלק משרשרת האספקה.</li>
</ul>
<div class="callout">בבודק של המעבדה, tag בלי digest הוא <b>info</b> ולא שגיאה. זו החלטה מכוונת: digest על כל base image הוא סטנדרט טוב בארגון עם Renovate או Dependabot שמעדכנים אותו, ומטרד בפרויקט של אדם אחד.</div>`,
    },
    {
      kicker: "הקשחה",
      title: "לא root, מערכת קבצים לקריאה בלבד, בלי capabilities",
      html: `<p>אם תוקף מצליח להריץ קוד בתוך ה-container, למשל דרך באג בספרייה או דרך prompt injection שגרם לכלי לעשות משהו שלא תכננת, השאלה היא מה הוא יכול לעשות משם. ההקשחה לא מונעת את הפריצה, היא מצמצמת את מה שבא אחריה.</p>
<ul>
<li><b>משתמש שאינו root.</b> כברירת מחדל, תהליך ב-container רץ כ-root (UID 0). זה אותו UID של root במכונה, ומוגבל רק בבידוד של הקרנל. כל פגיעות בבידוד הזה, ויש כאלה כל כמה שנים, הופכת ל-root על המכונה. ב-Dockerfile של המעבדה יש משתמש מערכת <code>app</code> עם UID קבוע 10001, בלי סיסמה, בלי shell ובלי תיקיית בית, והשורה <code>USER app</code> לפני ה-CMD.</li>
<li><b>הקוד שייך ל-root.</b> הקבצים מועתקים בלי <code>--chown</code>, ולכן <code>app</code> יכול לקרוא אותם ולא לשנות אותם. תוקף לא יכול להשתיל קוד שישרוד הפעלה מחדש של התהליך.</li>
<li><b>מערכת קבצים לקריאה בלבד.</b> השירות לא כותב לדיסק. <code>read_only: true</code> ב-compose ו-<code>readonlyRootFilesystem = true</code> ב-ECS הופכים את זה לחוק. <code>PYTHONDONTWRITEBYTECODE=1</code> קיים בדיוק בשביל זה: Python לא ינסה לכתוב <code>.pyc</code>.</li>
<li><b>בלי capabilities.</b> ב-Linux, ההרשאות של root מחולקות לכשלושים capabilities (לשנות רשת, לעקוף הרשאות קבצים...). <code>cap_drop: [ALL]</code> מוריד את כולן. ו-<code>no-new-privileges</code> מונע מתהליך לקבל הרשאות נוספות דרך קובץ setuid.</li>
</ul>
<div class="example"><b>לבדוק</b><pre dir="ltr">docker run --rm company-brain-api:dev id       # uid=10001(app) gid=10001(app)
docker run --rm company-brain-api:single id    # uid=0(root) gid=0(root)</pre></div>
<p>כלל הבודק <code>runs_as_non_root</code>, שתכתוב בתרגיל 5, בודק את השלב <b>הסופי</b>, כולל ירושה: שלב שבנוי <code>FROM runtime</code> יורש את המשתמש של <code>runtime</code>. זו בדיוק הטעות ש-grep פשוט על "USER" היה מפספס.</p>`,
    },
    {
      kicker: "בריאות",
      title: "Health checks: חי, מוכן, ומי שואל",
      html: `<p>שתי שאלות שונות, עם שתי תגובות שונות, ומערבבים ביניהן כל הזמן:</p>
<ul>
<li><b>Liveness, "אתה חי?"</b> (<code>/healthz</code>): התהליך עונה. לא בודק שום תלות. אם התשובה היא לא, הפתרון הוא <b>להרוג ולהפעיל מחדש</b>.</li>
<li><b>Readiness, "אתה מוכן לקבל תנועה?"</b> (<code>/readyz</code>): ההגדרות תקינות, ומה שהשירות צריך זמין (ב-mock: ש-mockllm עונה; עם מפתח: רק שהמפתח נטען, בלי לפנות לספק). ב-Kubernetes, כשלון readiness אומר <b>לא לשלוח אליו בקשות</b>, בלי להרוג אותו. ב-ECS זה שונה, ומיד נראה איך.</li>
</ul>
<p>למה זה חשוב: אם ה-load balancer היה בודק liveness, משימה שלא יכולה לענות (למשל, עלתה בלי mockllm) הייתה ממשיכה לקבל בקשות ולהחזיר 502. ואם בדיקה שגורמת להחלפת משימות הייתה תלויה בשירות חיצוני, תקלה זמנית אצלו הייתה גורמת להחליף את כל המשימות ביחד, בלולאה שלא מתקנת כלום.</p>
<h4>ב-ECS, כשלון ב-ALB גם מחליף את המשימה</h4>
<p>המודל של Kubernetes, שבו readiness רק מוציא מהסבב ו-liveness מפעיל מחדש, <b>לא עובר כמו שהוא ל-ECS</b>. לפי התיעוד של AWS (Amazon ECS services, נבדק בנובמבר 2026), ה-service scheduler מחליף משימה שנכשלה <b>גם</b> ב-health check של ה-container <b>וגם</b> ב-health check של ה-target group: הוא מעלה משימה חלופית, ואחרי שהיא בריאה עוצר את הישנה. כלומר, ב-ECS משימה שנכשלת ב-<code>/readyz</code> לא רק מפסיקה לקבל תנועה, היא <b>נעצרת ומוחלפת</b>.</p>
<p>ובכל זאת ה-ALB של המעבדה בודק את <code>/readyz</code>, וזו החלטה מכוונת. <code>/readyz</code> בודק רק דברים <b>מקומיים למשימה</b>, שהחלפה שלה באמת יכולה לתקן: שההגדרות נטענו, שהמפתח הוזרק, ובמצב mock שה-mockllm שלידה עונה. הוא <b>לא</b> פונה ל-Anthropic. אם הספק נופל, <code>/readyz</code> נשאר 200, המשימות נשארות, ו-<code>/v1/answer</code> מחזיר 502 ברור עם <code>request_id</code>. זה עדיף על מצב שבו ECS מחליף את כל המשימות שוב ושוב בגלל תקלה שאינה שלהן. נפילה של הספק מטפלים בה בקוד (retry, fallback, נושא 19), לא ב-health check.</p>
<h4>מי בודק מה במעבדה</h4>
<ul>
<li><b>HEALTHCHECK ב-Dockerfile</b>: <code>docker run</code> ו-compose משתמשים בו. compose מחכה ש-mockllm יהיה <code>healthy</code> לפני שהוא מעלה את ה-API (<code>depends_on: condition: service_healthy</code>).</li>
<li><b>ECS מתעלם ממנו.</b> בתיעוד של AWS: ECS לא עוקב אחרי health check שמוגדר ב-image אם הוא לא מוגדר גם ב-container definition. לכן ה-<code>healthCheck</code> חוזר ב-Terraform, ובודק <code>/healthz</code>.</li>
<li><b>ה-ALB</b> בודק <code>/readyz</code> דרך ה-target group, ומפסיק לשלוח תנועה למשימה שלא מוכנה. ECS רואה את אותה תוצאה, ומחליף משימה שה-target group סימן כלא בריאה (אחרי <code>health_check_grace_period_seconds</code>).</li>
</ul>
<div class="callout"><b>אף פעם לא לקרוא למודל ב-health check.</b> ALB בודק כל 15 שניות מלפחות שני nodes, כ-345 אלף בדיקות בחודש למשימה, ו-ECS בודק כל 15 שניות מתוך המשימה, עוד כ-173 אלף. יחד זה כ-500 אלף בקשות בחודש לכל משימה. health check שקורא ל-API בתשלום הוא חשבונית ששולמה על שום דבר, וגם הופך מגבלת קצב אצל הספק לנפילה של כל המשימות.</div>`,
    },
    {
      kicker: "כיבוי",
      title: "PID 1, אותות, וכיבוי מסודר",
      html: `<p>כל deployment ב-ECS, כל scale in וכל <code>docker stop</code> נגמרים באותה דרך: התהליך הראשי ב-container מקבל <code>SIGTERM</code>, ויש לו זמן מוגדר (<code>stopTimeout</code>, במעבדה 30 שניות) לסיים. אחרי זה מגיע <code>SIGKILL</code>, שאי אפשר לתפוס. שירות שמכבד את SIGTERM מסיים את הבקשות שבדרך וסוגר חיבורים. שירות שלא מקבל אותו בכלל, נהרג באמצע תשובה.</p>
<h4>הבעיה של צורת ה-shell</h4>
<div class="example"><b>שתי צורות של CMD</b><pre dir="ltr">CMD uvicorn service.main:app --port 8000          # shell form: PID 1 is /bin/sh -c "..."
CMD ["uvicorn", "service.main:app", "--port", "8000"]   # exec form: PID 1 is uvicorn</pre></div>
<p>בצורת shell, Docker מריץ <code>/bin/sh -c "..."</code>. בדרך כלל ה-shell נשאר התהליך הראשון, ו-uvicorn הוא הילד שלו. ה-shell לא מעביר את SIGTERM לילד, ולכן uvicorn לא יודע שצריך לסיים. אחרי 30 שניות שניהם נהרגים. כל deployment נראה תקין, וכל בקשה שהייתה באמצע נחתכת. אבל זה תלוי ב-shell: <code>dash</code>, שהוא <code>/bin/sh</code> ב-images של Debian, עושה לפעמים <code>exec</code> לפקודה בודדת אחרי <code>-c</code>, ואז uvicorn כן יהיה PID 1. מספיק <code>&amp;&amp;</code> או pipe בשורה כדי שזה ישתנה. לכן לא סומכים על זה: צורת exec מבטיחה את ההתנהגות, ואת המצב בפועל בודקים, למשל <code>docker exec &lt;container&gt; ps -o pid,args</code> (או <code>cat /proc/1/cmdline</code> אם אין <code>ps</code> ב-image). BuildKit מזהיר על זה בבדיקה <code>JSONArgsRecommended</code>, והבודק של המעבדה בכלל <code>exec_form</code>.</p>
<h4>הצד של ה-load balancer</h4>
<ul>
<li><b>deregistration delay</b> (במעבדה 30 שניות, ברירת המחדל 300): משימה שמוחלפת מפסיקה לקבל בקשות <b>חדשות</b>, אבל ממשיכה לשרת את מה שכבר התחיל. 300 שניות הופכות כל deployment וכל destroy לאיטיים מאוד.</li>
<li><b>idle timeout</b> (במעבדה 120 שניות, ברירת המחדל 60): כמה זמן חיבור יכול לשתוק. תשובת LLM ארוכה, או מודל שחושב לפני הטוקן הראשון, יכולים לעבור 60 שניות.</li>
</ul>
<p>שלושת המספרים צריכים להתאים זה לזה: הבקשה הארוכה ביותר שאתה מצפה לה צריכה להיגמר בתוך ה-deregistration delay ובתוך ה-stopTimeout. אחרת, כל deployment חותך תשובות של משתמשים.</p>`,
    },
    {
      kicker: "Context",
      title: "Build context ו-.dockerignore: מה בכלל נשלח לבנייה",
      html: `<p>הנקודה בסוף <code>docker build ... .</code> היא ה-<b>build context</b>: התיקייה שכל התוכן שלה נשלח ל-builder. רק ממנה <code>COPY</code> יכול להעתיק. במעבדה ה-context הוא שורש הריפו, כי ה-image צריך את <code>llmkit/</code>. בלי סינון, נשלחים ה-venv (מאות מגה-בייט), <code>.git</code>, ו-<code>.env</code> עם המפתחות שלך. ואז מספיק <code>COPY . .</code> אחד כדי שהם יגיעו ל-image.</p>
<h4>allowlist במקום רשימה שחורה</h4>
<div class="example"><b>Dockerfile.dockerignore (המקוצר)</b><pre dir="ltr">*
!llmkit/
!mockllm/
!labs/27-deployment/app/pyproject.toml
!labs/27-deployment/app/uv.lock
!labs/27-deployment/app/service/
**/__pycache__
**/.env
**/.env.*</pre></div>
<ul>
<li><b>מוציאים הכול</b> (<code>*</code>), ומכניסים בחזרה רק את מה שצריך (<code>!</code>). קובץ חדש בריפו, dump או מפתח, לא ייכנס עד שמישהו יוסיף אותו במכוון. ברשימה שחורה, כל קובץ חדש נכנס עד שמישהו ייזכר להוציא אותו.</li>
<li><b>השורה האחרונה שמתאימה מנצחת.</b> <code>**/.env</code> חייב לבוא <b>אחרי</b> שורות ה-<code>!</code>. אחרת <code>!llmkit/</code> מכניס בחזרה גם <code>llmkit/.env</code>. הבודק של המעבדה בודק בדיוק את זה.</li>
<li><b>ignore לכל Dockerfile.</b> כשיש כמה Dockerfiles עם אותו context, Docker מחפש קובץ בשם <code>&lt;שם ה-Dockerfile&gt;.dockerignore</code> ליד ה-Dockerfile, והוא קודם ל-<code>.dockerignore</code> שבשורש. כך לכל image במעבדה יש סינון משלו.</li>
</ul>
<p>בדקנו את ה-allowlist הזה בפועל: בנייה של <code>FROM scratch</code> ו-<code>COPY . /</code> עם הקובץ הזה, כשבשורש וב-<code>llmkit/</code> יש <code>.env</code>, הוציאה 22 קבצים, 240KB, בלי אף <code>.env</code> ובלי <code>__pycache__</code>.</p>`,
    },
    {
      kicker: "סודות",
      title: "שלוש דרכים לאפות סוד לתוך image, וכולן דולפות",
      html: `<p>הכלל פשוט: <b>מפתח לא נכנס ל-image אף פעם.</b> image נדחף ל-registry, נמשך ל-CI, למחשבים של מפתחים אחרים ולכל משימה בענן, ומי שיכול למשוך אותו יכול לקרוא כל בייט בו. <code>Dockerfile.baked</code> במעבדה עושה את שלוש הטעויות הנפוצות, עם מפתחות מזויפים, ובתרגיל 4 תמצא כל אחד מהם:</p>
<ol class="ladder">
<li><b>ARG</b><span><code>ARG ANTHROPIC_API_KEY</code> ו-<code>--build-arg</code> נראים זמניים. אבל כל <code>RUN</code> שרץ בזמן שה-ARG מוגדר נרשם ב-history של ה-image עם הערך. <code>docker history --no-trunc</code> מראה אותו.</span></li>
<li><b>ENV</b><span><code>ENV ANTHROPIC_API_KEY=sk-ant-...</code> נשמר ב-config. <code>docker inspect</code> מראה אותו, וכל image שנבנה <code>FROM</code> ה-image הזה יורש אותו.</span></li>
<li class="danger"><b>קובץ שנמחק בשכבה הבאה</b><span><code>COPY .env</code> ואחריו <code>RUN rm .env</code>. הקובץ לא קיים במערכת הקבצים הסופית, אבל השכבה שהוסיפה אותו עדיין בתוך ה-image. השכבה שאחריה רק מוסיפה סימון מחיקה (whiteout). <code>docker save</code> ו-<code>layer_peek.py</code> מוצאים אותו.</span></li>
</ol>
<p>BuildKit מזהיר על שתי הראשונות בבדיקה <code>SecretsUsedInArgOrEnv</code>, לפי <b>שם</b> המשתנה. את השלישית אין לו דרך לראות. הבודק של המעבדה מחפש גם לפי <b>צורת הערך</b> (<code>sk-ant-</code>, <code>AKIA</code>, <code>ghp_</code>), ולכן מוצא מפתח גם תחת שם תמים כמו <code>CONFIG</code>.</p>
<h4>ואם צריך סוד בזמן הבנייה?</h4>
<p>למשל token למאגר חבילות פרטי. לזה יש <code>RUN --mount=type=secret,id=pip_token</code>: הסוד זמין כקובץ רק בזמן הריצה של אותה הוראה, ולא נכנס לשכבה, ל-history או ל-cache.</p>
<div class="callout">הבדיקה לפי שם תמיד טועה לשני הכיוונים: <code>MAX_TOKENS</code> מכיל "TOKEN" ואינו סוד, ו-<code>CONFIG=sk-ant-...</code> הוא סוד עם שם תמים. לכן הבודק משלב שם וצורה, ועדיין לא מחליף code review.</div>`,
    },
    {
      kicker: "הזרקה",
      title: "איך הסוד כן מגיע לשירות: ארבע רמות",
      html: `<p>אם הסוד לא ב-image, הוא צריך להגיע בזמן ריצה. יש ארבע דרכים נפוצות, וכל אחת חושפת את הערך למעגל אחר של אנשים ותהליכים:</p>
<ol class="ladder">
<li><b>משתנה סביבה ישיר</b><span><code>docker run -e ANTHROPIC_API_KEY=...</code> או <code>env_file</code> ב-compose. לא ב-image, אבל גלוי ב-<code>docker inspect</code> של ה-container, בהיסטוריה של ה-shell, ולכל תהליך ב-container.</span></li>
<li><b>קובץ סוד</b><span>compose secrets: הערך נטען לקובץ ב-<code>/run/secrets/anthropic_api_key</code>. לא מופיע ב-inspect. השירות קורא את הנתיב מ-<code>ANTHROPIC_API_KEY_FILE</code>. זה <code>api-real</code> בתרגיל 3.</span></li>
<li><b>מנהל סודות, מוזרק בעלייה</b><span>ב-ECS: ה-task definition מכיל רק את ה-<b>ARN</b> של הסוד ב-Secrets Manager (או ב-SSM Parameter Store). כשמשימה עולה, הסוכן של ECS קורא את הערך עם ה-execution role ומגדיר את משתנה הסביבה בתוך ה-container. זו ברירת המחדל של המעבדה.</span></li>
<li class="danger"><b>השירות קורא בעצמו</b><span>הקוד קורא ל-Secrets Manager עם ה-SDK, בהרשאות של ה-task role, ושומר את הערך בזיכרון. מאפשר החלפת מפתח בלי deployment, במחיר של קוד ותלות נוספים.</span></li>
</ol>
<h4>מה חשוב לדעת על רמה 3</h4>
<ul>
<li><b>החלפה דורשת deployment.</b> לפי התיעוד של AWS, הסוד מוזרק כשה-container עולה. אחרי שינוי ערך, משימות קיימות ממשיכות עם הישן עד <code>--force-new-deployment</code>. זה תרגיל 8 ה.</li>
<li><b>גם משתנה סביבה יכול לדלוף מהקוד.</b> לוג שמדפיס את כל הסביבה, או עמוד שגיאה של debug, חושפים אותו. לכן ב-<code>Settings</code> של השירות השדה מוגדר <code>repr=False</code>, והלוג בעלייה כותב רק <code>key_source</code>: file, env או none.</li>
<li><b>Secrets Manager או Parameter Store?</b> Secrets Manager עולה 0.40$ לסוד לחודש ותומך ברוטציה אוטומטית. SecureString ב-Parameter Store בשכבה הסטנדרטית בדרך כלל זול יותר, בלי רוטציה מובנית. לסוד אחד ההבדל זניח. בדוק את המחיר הנוכחי לפני שאתה בוחר לפי זה.</li>
</ul>
<div class="example"><b>מתוך ecs.tf</b><pre dir="ltr">secrets = [
  { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn },
]</pre></div>`,
    },
    {
      kicker: "מקומי",
      title: "docker compose: כל הסטאק במחשב, בחינם",
      html: `<p>לפני שמשהו עולה לענן, הוא צריך לעבוד מקומית <b>בתוך containers</b>, באותו image שייפרס. <code>compose.yaml</code> של המעבדה מגדיר שלושה שירותים:</p>
<ul>
<li><b>mockllm</b>: אותו Dockerfile עם <code>target: mockllm</code>. אין לו <code>ports</code>, כלומר הוא נגיש רק מתוך הרשת של compose, בשם <code>http://mockllm:8765</code>. compose נותן לכל שירות שם DNS לפי שמו.</li>
<li><b>api</b>: ה-image הסופי, עם <code>MOCKLLM_URL</code> שמצביע על mockllm, ו-<code>depends_on: condition: service_healthy</code>. הפורט קשור ל-<code>127.0.0.1:8000</code> ולא לכל הכתובות: בלי זה, כל מי שברשת ה-Wi-Fi שלך יכול לגשת לשירות.</li>
<li><b>api-real</b>: בפרופיל <code>real</code>, כלומר עולה רק עם <code>--profile real</code>. מקבל את המפתח כ-compose secret.</li>
</ul>
<div class="example"><b>הסוד ב-compose, בלי לכתוב אותו לשום קובץ</b><pre dir="ltr">secrets:
  anthropic_api_key:
    environment: ANTHROPIC_API_KEY   # read from the shell that runs docker compose

# in the shell, only for this session:
set -a; . ../../.env; set +a
docker compose --profile real up -d api-real</pre></div>
<p>כמה פרטים שכדאי לשים לב אליהם בקובץ:</p>
<ul>
<li><b>YAML anchors</b> (<code>&amp;hardening</code>, <code>&lt;&lt;: *hardening</code>): ההקשחה (read only, בלי capabilities, no-new-privileges) מוגדרת פעם אחת ומוחלת על כל השירותים.</li>
<li><b>מגבלת משאבים</b> של חצי CPU ו-512MB, בערך הגודל של משימת Fargate בענן. בעיה של זיכרון תתגלה כאן ולא שם.</li>
<li><b>הגדרות לפי סביבה.</b> אותו image רץ עם mock מקומית ועם Claude בענן. מה שמשתנה הוא משתני הסביבה בלבד. בהמשך הקורס יתווספו כאן LiteLLM ו-collector של OpenTelemetry, בלי לגעת ב-image.</li>
</ul>
<p>בדקנו את הקובץ עם <code>docker compose config</code> (גרסה 5.5.1), שמפרסר ומאמת אותו בלי להריץ כלום.</p>`,
    },
    {
      kicker: "סריקה",
      title: "סריקת פגיעויות, ומה היא לא מוצאת",
      html: `<p>סורק images קורא את רשימת החבילות ב-image (חבילות Debian ו-Python), ומשווה אותה למאגר של פגיעויות ידועות (CVE). זה מה שתעשה בתרגיל 2, עם שלוש אפשרויות נפוצות:</p>
<ul>
<li><b>Trivy</b> (Aqua, קוד פתוח): סורק images, קבצי Dockerfile ו-Terraform (<code>trivy config</code>). רץ מקומית וב-CI.</li>
<li><b>Docker Scout</b>: מובנה ב-Docker CLI (<code>docker scout quickview</code>, <code>docker scout cves</code>), דורש התחברות ל-Docker Hub.</li>
<li><b>סריקה ב-ECR</b>: <code>scan_on_push = true</code> ב-Terraform של המעבדה. הסריקה הבסיסית חינמית, והתוצאות מופיעות בקונסולה.</li>
</ul>
<h4>מה עושים עם התוצאה</h4>
<p>רוב הממצאים יהיו בחבילות של מערכת ההפעלה, ולכן image של slim מראה הרבה פחות מ-image מלא: חבילה שלא קיימת לא יכולה להיות פגיעה. וחלק גדול מהתיקונים מגיעים פשוט מבנייה מחדש מעל base image מעודכן. זו הסיבה ש-"Rebuild your images often" מופיע במסמך של Docker.</p>
<h4>מה סורק לא מוצא</h4>
<p>באג בקוד שלך, הרשאה רחבה מדי, סוד בשכבה (לסורקים שלא מחפשים סודות), או prompt injection. סורק מודד <b>חבילות ידועות</b>, לא את המערכת.</p>
<div class="callout"><b>גם הסורק הוא שרשרת אספקה.</b> ב-19 במרץ 2026 פורסמה גרסת Trivy זדונית (0.69.4) עם credentials שנגנבו, ו-76 מתוך 77 התגיות של ה-GitHub Action שלו הוזזו לקוד שגונב סודות מה-CI (CVE-2026-33634). צינור שהריץ <code>trivy-action@v0.28</code> "המוכר והטוב" הריץ קוד זדוני. הלקח: מצמידים גרסה מדויקת, ב-Actions מצמידים ל-SHA של commit, וגם כלי האבטחה עצמם נבדקים. במעבדה: <code>aquasec/trivy:0.76.1</code>.</div>`,
    },
    {
      kicker: "בחירה",
      title: "איפה מריצים container ב-AWS, נכון לנובמבר 2026",
      html: `<p>יש כמה דרכים להריץ את אותו image ב-AWS. ההבדלים הם בכמה אתה מנהל בעצמך, איך מחויבים, ומה המגבלות.</p>
<h4>ECS על Fargate, מאחורי ALB: הבחירה של המעבדה</h4>
<p>AWS מריץ את ה-containers, ואין שרתים לנהל. מחויבים לפי vCPU וזיכרון לשנייה, כל עוד המשימה רצה, ועל ה-load balancer כל שעה. כל רכיב גלוי ומוגדר ב-Terraform, וזו הסיבה שבחרנו בו: אפשר לראות את ה-IAM, הרשת והסודות, ולא רק להאמין שהם בסדר.</p>
<h4>ECS Express Mode</h4>
<p>הוכרז בנובמבר 2025. פקודה אחת, <code>aws ecs create-express-gateway-service</code>, עם image ושני roles, יוצרת שירות Fargate, ALB (משותף לעד 25 שירותים), autoscaling ורשת, עם כתובת HTTPS. אין עליו תוספת מחיר מעבר למשאבים שהוא יוצר. ב-Terraform יש לו משאב, <code>aws_ecs_express_gateway_service</code>. דרך מצוינת לעלות מהר, ואחרי השיעור הזה תבין כל משאב שהוא יוצר בשבילך.</p>
<h4>App Runner: סגור ללקוחות חדשים</h4>
<p>בתיעוד של AWS: "AWS App Runner is no longer open to new customers". לקוחות קיימים ממשיכים כרגיל, בלי פיצ'רים חדשים, ו-AWS ממליצים לעבור ל-ECS Express Mode. הרבה מדריכים מ-2023 עד 2025 עדיין מציעים App Runner כדרך הקלה. לחשבון חדש זו כבר לא אפשרות.</p>
<h4>Lambda</h4>
<p>מתאים לעומס קל ולא רציף: מחויבים לפי בקשה ולפי זמן ריצה, ואפס כשאין תנועה. FastAPI רץ עליו עם Lambda Web Adapter, ו-Function URL תומך בסטרימינג. המלכודת לשירות LLM: <b>משלמים על זמן ההמתנה למודל</b>. בקשה של 5 שניות היא 5 שניות של Lambda, גם אם ה-CPU לא עשה כלום. יש גם תקרה של 15 דקות ו-cold starts.</p>
<h4>ומה עוד</h4>
<p><b>EC2 עם docker compose</b>: הכי זול ברמה של שירות אחד, אבל אתה מנהל את השרת, העדכונים וה-TLS. <b>EKS</b> (Kubernetes): הגיוני לארגון עם עשרות שירותים, ותקורה מיותרת לשירות אחד.</p>`,
    },
    {
      kicker: "ארכיטקטורה",
      title: "מה ה-Terraform יוצר, ואיך בקשה עוברת בו",
      html: `<p>21 משאבים בתיקייה <code>terraform/</code>. במסלול של בקשה:</p>
<ol>
<li><b>ALB</b> ציבורי בשני availability zones, עם security group שמקבל רק פורט 80 מ-<code>allowed_cidr</code> (במעבדה: ה-IP שלך).</li>
<li><b>Target group</b> מסוג <code>ip</code> שבודק <code>/readyz</code>, ומעביר למשימות על פורט 8000.</li>
<li><b>משימת Fargate</b> ב-subnet ציבורי עם IP ציבורי. ה-security group שלה מקבל תנועה <b>רק מה-security group של ה-ALB</b>, כך שגם עם IP ציבורי אי אפשר לפנות אליה ישירות. יציאה מותרת רק ל-443.</li>
<li>מהמשימה, <b>api.anthropic.com</b>, עם המפתח שהוזרק כשהיא עלתה.</li>
</ol>
<p>ומה שקורה <b>לפני</b> הבקשה הראשונה, כשמשימה עולה: הסוכן של ECS מתחבר ל-<b>ECR</b> ומושך את ה-image, קורא את הסוד מ-<b>Secrets Manager</b>, ופותח log stream ב-<b>CloudWatch Logs</b>. כל זה בהרשאות של ה-execution role.</p>
<h4>למה subnet ציבורי ולא פרטי</h4>
<p>מ-subnet פרטי, משימה צריכה דרך החוצה ל-ECR, ל-Secrets Manager, ל-CloudWatch ול-Anthropic. יש שתי דרכים, ושתיהן עולות כסף קבוע:</p>
<ul>
<li><b>NAT gateway</b>: 0.045$ לשעה ועוד 0.045$ לכל GB. בערך 33$ לחודש לפני תעבורה.</li>
<li><b>VPC endpoints</b>: 0.01$ לשעה לכל endpoint בכל AZ. צריך ארבעה (ecr.api, ecr.dkr, logs, secretsmanager) בשני AZs: בערך 58$ לחודש, <b>יותר</b> מ-NAT. ועדיין צריך דרך ל-Anthropic.</li>
</ul>
<p>מול זה, IP ציבורי למשימה עולה 3.65$ לחודש. עם security group שמקבל רק מה-ALB, זו פשרה סבירה למעבדה ולשירות קטן. בפרודקשן רציני בדרך כלל עוברים לפרטי עם NAT. המחשבון במגרש המשחקים מראה את שלוש האפשרויות.</p>
<div class="callout">ה-listener הוא HTTP בלבד, כדי שהמעבדה לא תצטרך דומיין ותעודה. תנועה אמיתית צריכה HTTPS: תעודת ACM (חינמית) לדומיין שלך ו-listener על 443. עד אז, לא שולחים לכתובת הזו שום דבר רגיש.</div>`,
    },
    {
      kicker: "IAM",
      title: "שני roles, והרשאות מינימליות",
      html: `<p>הטעות הנפוצה ביותר ב-ECS היא לערבב בין שני ה-roles. כל אחד שייך למישהו אחר:</p>
<ul>
<li><b>Execution role</b>: של <b>הסוכן של ECS</b>. מושך image מ-ECR, כותב לוגים, קורא סודות ומזריק אותם. לפי התיעוד, ההרשאות האלה לא זמינות לקוד שרץ ב-container.</li>
<li><b>Task role</b>: של <b>הקוד שלך</b>. כל מה שהאפליקציה עושה עם ה-SDK של AWS. במעבדה הוא ריק, כי השירות לא קורא ל-AWS בכלל. כש-Company Brain יקרא מסמכים מ-S3, ההרשאה תיכנס לכאן, ורק לכאן.</li>
</ul>
<div class="example"><b>מתוך iam.tf, בקיצור</b><pre dir="ltr">statement {   # only this repository
  actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
  resources = [aws_ecr_repository.api.arn]
}
statement {   # no resource-level permissions exist for this action
  actions   = ["ecr:GetAuthorizationToken"]
  resources = ["*"]
}
statement {   # only this secret
  actions   = ["secretsmanager:GetSecretValue"]
  resources = [aws_secretsmanager_secret.anthropic.arn]
}</pre></div>
<h4>מה הבודק מחפש, ולמה</h4>
<ul>
<li><b><code>"*"</code> או <code>"s3:*"</code> כפעולה</b>: שגיאה. <code>secretsmanager:*</code> כולל גם <code>DeleteSecret</code> ו-<code>PutSecretValue</code>, לא רק קריאה.</li>
<li><b><code>NotAction</code> עם Allow</b>: שגיאה. "הכול חוץ מ-IAM" זה עדיין כמעט הכול.</li>
<li><b><code>iam:PassRole</code> על <code>"*"</code></b>: שגיאה. מי שיכול להעביר כל role לשירות, יכול להריץ קוד עם ההרשאות של ה-role החזק ביותר בחשבון.</li>
<li><b>resource <code>"*"</code></b>: אזהרה, חוץ מפעולות שבהן זה הערך היחיד האפשרי, כמו <code>ecr:GetAuthorizationToken</code>. זו מגבלה של AWS, לא עצלות.</li>
</ul>
<p>יש גם <b>תנאים ב-trust policy</b>: <code>aws:SourceAccount</code> ו-<code>aws:SourceArn</code> מבטיחים שרק ECS שפועל בשביל החשבון שלך יכול לקחת את ה-role. זו הגנה מפני בעיה שנקראת confused deputy, שירות שמבצע פעולה בשביל מישהו שלא היה אמור להיות מסוגל לבקש אותה.</p>`,
    },
    {
      kicker: "Terraform",
      title: "תשתית בקוד: plan, apply, state, destroy",
      html: `<p>Terraform קורא את קבצי ה-<code>.tf</code> (מה אתה <b>רוצה</b> שיהיה), את ה-<b>state</b> (מה הוא יצר בפעם הקודמת), ואת החשבון (מה <b>קיים</b>), ומחשב את ההפרש. ה-provider של AWS מתרגם את ההפרש לקריאות API. הגרסה הנוכחית שלו היא 6.x (6.71 בסוף אוקטובר 2026), ובמעבדה היא מוצמדת ל-<code>~&gt; 6.0</code>: עדכונים בתוך 6 כן, 7.0 לא, כי major חדש יכול לשנות התנהגות.</p>
<ol class="ladder">
<li><b>init</b><span>מוריד את ה-provider ורושם את ה-checksums שלו ב-<code>.terraform.lock.hcl</code>. את הקובץ הזה כן שומרים ב-git.</span></li>
<li><b>plan</b><span>מראה בדיוק מה ייווצר, ישתנה או <b>יימחק</b>. לא יוצר כלום ולא עולה כסף. <code>-out=tfplan</code> שומר את התוכנית, כך ש-apply יבצע את מה שקראת ולא תוכנית חדשה.</span></li>
<li><b>apply</b><span>מבצע. מכאן מתחיל החיוב. שורה כמו <code>-/+ destroy and then create replacement</code> ליד משאב שיש בו נתונים היא הסיבה שקוראים את ה-plan.</span></li>
<li class="danger"><b>destroy</b><span>מוחק כל מה שב-state. משאב שנוצר ידנית בקונסולה לא ב-state, ולכן לא יימחק. לכן גם בודקים אחרי.</span></li>
</ol>
<h4>state</h4>
<p>קובץ JSON עם כל מה ש-Terraform יצר: מזהים, ARNs, ולפעמים ערכים רגישים. <b>לא נכנס ל-git לעולם</b>. בצוות שומרים אותו ב-S3 עם נעילה (<code>backend "s3"</code> עם <code>use_lockfile = true</code>), כדי ששני אנשים לא יריצו apply ביחד. למעבדה של אדם אחד, state מקומי מספיק.</p>
<h4>למה ערך הסוד לא עובר דרך Terraform</h4>
<p>אם המפתח היה ב-<code>secret_string</code>, הוא היה נשמר בטקסט גלוי ב-state. יש שתי דרכים נכונות: לשים את הערך עם ה-AWS CLI (המעבדה), או להשתמש ב-<b>write-only argument</b>, <code>secret_string_wo</code>, שקיים מ-Terraform 1.11: הערך נשלח ל-AWS ולא נשמר ב-state או ב-plan. כיוון ש-Terraform לא שומר אותו, הוא לא יכול לזהות שינוי, ולכן מעלים את <code>secret_string_wo_version</code> כדי לשלוח ערך חדש.</p>
<div class="callout"><b>Bootstrap:</b> השירות צריך image ב-ECR וערך בסוד לפני שהוא עולה, אבל ה-ECR והסוד נוצרים באותו Terraform. לכן בתרגיל 8 מריצים קודם <code>apply -target</code> לשני המשאבים האלה, דוחפים image ושמים ערך, ורק אז את השאר. <code>-target</code> נועד בדיוק למצבים כאלה, לא לשימוש יומיומי.</div>`,
    },
    {
      kicker: "תפעול ועלות",
      title: "לוגים, autoscaling, כמה זה עולה, ואיך מפרקים",
      html: `<h4>לוגים</h4>
<p>השירות כותב <b>אובייקט JSON אחד לכל שורה</b> ל-stdout, עם <code>rid</code> (מזהה בקשה, שחוזר גם ב-header <code>x-request-id</code>), נתיב, סטטוס, זמן, טוקנים ועלות. ה-log driver <code>awslogs</code> שולח את זה ל-CloudWatch, ו-Logs Insights יודע לשאול על השדות: <code>filter status &gt;= 500</code>. מצב <code>non-blocking</code> מונע מהשירות לקפוא אם CloudWatch איטי, במחיר של שורות שעלולות ללכת לאיבוד. ו-<code>retention_in_days</code>: בלעדיו לוגים נשמרים, ומחויבים, לנצח.</p>
<h4>Autoscaling</h4>
<p>שירות LLM מחכה למודל, וה-CPU שלו נשאר נמוך גם כשהוא עמוס. לכן המעבדה מגדירה target tracking לפי <b><code>ALBRequestCountPerTarget</code></b>: 60 בקשות לדקה למשימה, בין 1 ל-3 משימות. ה-alarm של scale out מגיב אחרי כמה דקות מעל היעד, ושל scale in אחרי זמן ארוך הרבה יותר, בכוונה.</p>
<h4>כמה זה עולה (us-east-1, נובמבר 2026, בלי free tier)</h4>
<ul>
<li><b>ALB:</b> 16.43$ לחודש, גם בלי אף בקשה. 44% מהחשבון.</li>
<li><b>כתובות IPv4 ציבוריות:</b> 10.95$. אחת למשימה ואחת לכל AZ של ה-ALB, 0.005$ לשעה כל אחת. קל לשכוח שהן עולות כסף.</li>
<li><b>Fargate</b> (0.25 vCPU, 0.5GB, x86): 9.01$. ARM64 חוסך כ-20% מזה.</li>
<li><b>Secrets Manager, לוגים, ECR, alarms:</b> בערך 0.75$ ביחד.</li>
<li><b>סך הכול: כ-37.4$ לחודש, 1.23$ ליום, 5 סנט לשעה.</b> 73% מזה הוא הרשת סביב האפליקציה, לא האפליקציה.</li>
</ul>
<h4>תקציב ופירוק</h4>
<p>AWS Budgets חינמי, ובמעבדה הוא root module נפרד שנוצר <b>ראשון</b> ונשאר אחרי destroy. שתי מגבלות: נתוני החיוב מתעדכנים כמה פעמים ביום, כך שהתראה יכולה להגיע שעות אחרי שההוצאה התחילה, ו-budget <b>מתריע</b> ולא עוצר שום דבר. ההגנה האמיתית היא <code>terraform destroy</code> באותו יום, ו-<code>teardown_check.sh</code> שמחפש משאבים לפי ה-tag <code>Project</code> שכל משאב מקבל מ-<code>default_tags</code>.</p>`,
    },
  ],

  sims: [
    {
      id: "l27path",
      title: "המסלול של בקשה ב-AWS, וגבולות ה-IAM",
      lead: "צעד אחרי צעד: מה קורה כשמשימה עולה (image, סוד, לוגים) ומה קורה כשבקשה מגיעה (ALB, משימה, Anthropic). כל חץ מסומן ב-role שמאשר אותו. אפשר לשבור דברים ולראות איפה זה נכשל ואיזו שגיאה תראה.",
      tasks: [
        "עבור על כל הצעדים במצב <b>תקין</b>. אילו צעדים משתמשים ב-<b>execution role</b>, ואילו לא משתמשים באף role?",
        "בחר את התקלה <b>\"אין הרשאה לסוד\"</b>. באיזה שלב זה נכשל, האם הבקשה של המשתמש בכלל מגיעה לקוד שלך, ואיזו הודעה תראה ב-ECS?",
        "בחר <b>\"ה-ALB בודק /healthz\"</b> ואז <b>\"mockllm/Anthropic למטה\"</b>. למה המשתמש מקבל 502 במקום שהמשימה תוצא מהסבב? והאם /readyz של המעבדה היה עוזר מול נפילה של Anthropic?",
      ],
    },
    {
      id: "l27lint",
      title: "Dockerfile linter אינטראקטיבי",
      lead: "בונים Dockerfile מתוך בחירות: base image, multi-stage, משתמש, health check, צורת CMD, סוד, וקובץ ignore. בכל שינוי רואים את ה-Dockerfile שנוצר, את הממצאים של אותם כללים שבבודק של המעבדה, והערכה של גודל ה-image ושל ה-build context.",
      tasks: [
        "התחל מ<b>\"Dockerfile ראשון\"</b> ותקן ממצא אחרי ממצא עד שאין שגיאות. איזה תיקון הקטין הכי הרבה את הגודל?",
        "סמן <b>ENV עם המפתח</b>, ואחר כך במקומו <b>ARG</b>. מה ההבדל בהודעה, ולמה ARG הוא לא באמת זמני?",
        "בחר ignore מסוג <b>allowlist</b> ושים את <b>**/.env לפני שורות ה-!</b>. למה זה שגיאה, למרות ש-.env מופיע בקובץ?",
      ],
    },
    {
      id: "l27cost",
      title: "מחשבון עלות חודשי",
      lead: "התצורה של המעבדה כנקודת התחלה: גודל משימה, מספר משימות ממוצע, ארכיטקטורה, סוג הרשת ושעות פעילות. כל שורה בחשבון מוסברת, והפס מראה מה החלק של כל רכיב. בתחתית: אותו עומס על Lambda, להשוואה.",
      tasks: [
        "עבור בין <b>IP ציבורי</b>, <b>NAT gateway</b> ו-<b>VPC endpoints</b>. כמה עולה כל אחד, ולמה endpoints יקרים כאן יותר מ-NAT?",
        "הגדל את <b>מספר המשימות</b> מ-1 ל-3. בכמה אחוזים עלה החשבון, ולמה לא פי שלושה?",
        "השווה ל-<b>Lambda</b> עם 30,000 בקשות בחודש ו-4 שניות לבקשה, ואז עם 1,000,000 בקשות. איפה Fargate נהיה זול יותר, ולמה זמן ההמתנה למודל קובע?",
      ],
    },
  ],

  lab: {
    repoPath: "labs/27-deployment",
    intro: "המעבדה בתיקייה labs/27-deployment. במרכזה <b>Company Brain mini API</b>: שירות FastAPI קטן מעל llmkit, באותה צורה של השירות משיעור 26, שנארז ב-image, רץ ב-compose ונפרס ל-<b>ECS Fargate</b> עם Terraform. חבילה חדשה בריפו, <b>deploykit</b>, היא קוד הייחוס: parser ל-Dockerfile, בדיקות Terraform עם python-hcl2, ומודל עלות. <b>תרגילים 1 עד 7 חינמיים.</b> תרגיל 8 עולה כ-5 סנט לשעה ב-AWS ונגמר בפירוק מלא.",
    setup: [
      'cd ~/ai-engineer-course-starter && source .venv/bin/activate',
      "uv pip install -r labs/27-deployment/requirements.txt   # python-hcl2, fastapi, uvicorn",
      "python -m pytest -q                                     # environment tests (tests/test_deploy.py)",
      "python -m pytest -q labs/27-deployment/tests            # your exercises: all fail at first",
      "docker compose version && terraform version && aws --version   # Docker + compose v2, Terraform >= 1.11, AWS CLI v2",
    ],
    tools: [
      "<b>app/Dockerfile:</b> ה-image הנכון, ארבעה שלבים: <code>builder</code> (uv ו-uv.lock), <code>runtime</code> (slim ומשתמש 10001), <code>mockllm</code>, ו-<code>api</code> (ברירת המחדל). <code>Dockerfile.single</code> להשוואה, ו-<code>Dockerfile.baked</code> עם שלוש דליפות של מפתחות <b>מזויפים</b>.",
      "<b>compose.yaml:</b> <code>api</code> ו-<code>mockllm</code> בחינם, ו-<code>api-real</code> בפרופיל <code>real</code>, עם המפתח כ-compose secret.",
      "<b>terraform/ ו-budget/:</b> ECS Fargate, ALB, ECR, Secrets Manager, שני IAM roles, CloudWatch ו-autoscaling (21 משאבים). התקציב הוא root module נפרד, כדי שיישאר אחרי destroy.",
      "<b>checks.py:</b> בודק סטטי ל-Dockerfiles, ל-ignore files, ל-Terraform ולמדיניות IAM ב-JSON. משתמש בפונקציות שלך מ-mine.py, ומחזיר exit code 1 כשיש שגיאה.",
      "<b>cost_estimate.py, call_api.py, layer_peek.py, teardown_check.sh:</b> מחשבון עלות, קריאות לשירות (כולל סטרימינג ועומס), חיפוש קבצים בתוך שכבות של image, ובדיקה של מה נשאר ב-AWS.",
      "<b>mine.py:</b> שלושה חלקים שלך: שני כללי Dockerfile (<code>rule_runs_as_non_root</code>, <code>rule_no_secrets_in_build</code>), כלל IAM (<code>rule_iam_least_privilege</code>), ומודל העלות (<code>monthly_cost</code>).",
    ],
    exercises: [
      { id: "ex1", title: "לבנות image ולמדוד אותו (חינם)", text: "בנה את שני ה-images מתיקיית השורש (ה-context הוא השורש כי ה-image צריך את llmkit). השווה גדלים עם docker images, קרא את השכבות עם docker history, ובדוק עם id מי המשתמש בכל image. הרץ את ה-image הטוב ובדוק את /healthz ואת /readyz: למה readyz מחזיר 503 כש-mockllm לא רץ? כדי להפריד בין תרומת ה-base לתרומת ה-multi-stage, שנה זמנית את ה-FROM ב-Dockerfile.single ל-python:3.12.16-slim-trixie ומדוד שוב. אם יש לך Docker 27 ומעלה, הרץ גם docker build --check על Dockerfile.single.", cmd: "docker build -f labs/27-deployment/app/Dockerfile -t company-brain-api:dev .\ndocker build -f labs/27-deployment/app/Dockerfile.single -t company-brain-api:single .\ndocker images company-brain-api\ndocker run --rm company-brain-api:dev id\ndocker run -d --name l27 -p 127.0.0.1:8000:8000 company-brain-api:dev && sleep 20 && docker ps\ncurl -s localhost:8000/healthz; curl -s localhost:8000/readyz; docker rm -f l27" },
      { id: "ex2", title: "Cache של שכבות וסריקת פגיעויות (חינם)", text: "הוסף שורת הערה ל-app/service/main.py ובנה שוב: שלב ה-uv sync צריך להיות CACHED. אחר כך הוסף הערה ל-pyproject.toml ובנה שוב: עכשיו הוא רץ מחדש. הסבר למה. אחר כך סרוק את שני ה-images עם trivy בגרסה מוצמדת (לא 0.69.4, הגרסה הזדונית ממרץ 2026). כמה ממצאי HIGH ו-CRITICAL בכל אחד, ומאיפה רובם מגיעים? החזר את ההערות בסוף. ב-Docker rootless ה-socket נמצא ב-$XDG_RUNTIME_DIR/docker.sock ולא ב-/var/run/docker.sock, אז החלף את הנתיב הראשון ב-mount.", cmd: "docker build -f labs/27-deployment/app/Dockerfile -t company-brain-api:dev .\ndocker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.1 image --severity HIGH,CRITICAL --quiet company-brain-api:dev\ndocker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.1 image --severity HIGH,CRITICAL --quiet company-brain-api:single" },
      { id: "ex3", title: "הסטאק המקומי עם docker compose", text: "הרם את api ו-mockllm, ובדוק שניהם healthy. קרא לשירות רגיל ובסטרימינג, וקרא את הלוגים (JSON, שורה לכל אירוע). עצור את mockllm ובדוק: healthz נשאר 200, readyz הופך ל-503, ו-answer מחזיר 502. הסבר מה היה קורה ב-AWS אם ה-ALB היה בודק את healthz, ולמה גם /readyz לא מזהה נפילה של Anthropic (קרא את readyz ב-app/service/main.py). צעד אופציונלי מול Claude (פחות מעשירית סנט לשאלה): טען את המפתחות ל-shell, הרם את api-real בפרופיל real, ובדוק עם docker inspect שהמפתח לא מופיע בסביבה של ה-container.", cmd: "cd labs/27-deployment && docker compose up --build -d && docker compose ps\npython call_api.py && python call_api.py --stream\ndocker compose stop mockllm && python call_api.py; docker compose start mockllm\nset -a; . ../../.env; set +a; docker compose --profile real up --build -d api-real\npython call_api.py --url http://127.0.0.1:8001\ndocker inspect company-brain-l27-api-real-1 --format '{{json .Config.Env}}'\ndocker compose --profile real down; cd ../.." },
      { id: "ex4", title: "למה אסור לאפות סוד לתוך image (חינם)", text: "Dockerfile.baked בונה מעל company-brain-api:dev ועושה שלוש טעויות עם מפתחות מזויפים: build arg, ENV עם ערך, וקובץ .env שמועתק ונמחק בשכבה הבאה. מצא כל אחד מהשלושה: ב-history, ב-config, ובתוך השכבות עם layer_peek. ענה: מי יכול לראות כל אחד (מי שמושך את ה-image, מי שמריץ אותו, מי שבונה מעליו)? ואיפה נראה מפתח שהועבר עם docker run -e? בסוף מחק את הקובץ ואת ה-image.", cmd: "docker build -f labs/27-deployment/app/Dockerfile.baked --build-arg ANTHROPIC_API_KEY=sk-ant-lab27-FAKE-buildarg-000000 -t company-brain-api:baked .\ndocker history --no-trunc company-brain-api:baked | grep -o \"sk-ant-lab27-FAKE[^ ]*\"\ndocker inspect company-brain-api:baked --format '{{json .Config.Env}}'\ndocker save company-brain-api:baked -o labs/27-deployment/results/baked.tar\npython labs/27-deployment/layer_peek.py labs/27-deployment/results/baked.tar --find .env\nrm labs/27-deployment/results/baked.tar && docker rmi company-brain-api:baked" },
      { id: "ex5", title: "כללי Dockerfile בבודק הסטטי", text: "קרא את rule_base_image_pinned ב-mine.py (דוגמה פתורה), וממש את rule_runs_as_non_root ואת rule_no_secrets_in_build. כל מה שהן מקבלות מתועד בראש הקובץ: parse_dockerfile, stages, env_pairs, looks_like_secret_name ו-looks_like_secret_value. שני מקרים שקל לפספס: שלב שבנוי FROM שלב קודם יורש ממנו את המשתמש, ו-ENV עם ערך ריק הוא placeholder ולא דליפה. אחר כך הרץ את הבודק על שלושת ה-Dockerfiles והשווה למה ש-docker build --check מצא בתרגיל 1.", cmd: "python -m pytest -q labs/27-deployment/tests/test_ex5_dockerfile_rules.py\npython labs/27-deployment/checks.py labs/27-deployment/app/Dockerfile labs/27-deployment/app/Dockerfile.single labs/27-deployment/app/Dockerfile.baked" },
      { id: "ex6", title: "IAM של הרשאות מינימליות", text: "ממש את rule_iam_least_privilege. הבודק רץ על שלושה מקורות: terraform/iam.tf (execution role עם ארבע הצהרות: משיכה מ-repository אחד, ecr:GetAuthorizationToken על *, כתיבה ל-log group אחד, וקריאה של סוד אחד; ו-task role ריק), fixtures/bad_iam.json (שבע הצהרות, בהן Action *, secretsmanager:*, s3:Get*, iam:PassRole על * ו-NotAction), ו-fixtures/bad_task.tf (אותו role לשני התפקידים, מפתח כמשתנה סביבה רגיל, ו-actions *). ה-Terraform של המעבדה צריך לצאת נקי, וה-fixtures צריכים ליפול. ענה: למה GetAuthorizationToken על * לא נחשב הפרה? ואם Company Brain יקרא מסמכים מ-S3, לאיזה role תוסיף את ההרשאה ואיך תיראה ההצהרה?", cmd: "python -m pytest -q labs/27-deployment/tests/test_ex6_iam.py\npython labs/27-deployment/checks.py labs/27-deployment/terraform labs/27-deployment/fixtures/bad_iam.json labs/27-deployment/fixtures/bad_task.tf" },
      { id: "ex7", title: "קודם תקציב, אחר כך plan, ואז מחשבון (חינם)", text: "ממש את monthly_cost והרץ את המחשבון על התצורה של המעבדה, על סשן של 3 שעות, על subnet פרטי עם NAT, עם VPC endpoints, ועל ARM64. אחר כך צור את ה-budget (חינם, ונשאר אחרי destroy) והרץ terraform plan על התשתית: plan לא יוצר כלום. קרא אותו: כמה משאבים ייווצרו (צריך 21), אילו מהם עולים כסף כל שעה גם בלי בקשות, ולמה endpoints יקרים יותר מ-NAT בתצורה קטנה?", cmd: "python -m pytest -q labs/27-deployment/tests/test_ex7_cost.py\npython labs/27-deployment/cost_estimate.py\npython labs/27-deployment/cost_estimate.py --hours 3\npython labs/27-deployment/cost_estimate.py --private-nat\npython labs/27-deployment/cost_estimate.py --private-endpoints\npython labs/27-deployment/cost_estimate.py --arch ARM64\ncd labs/27-deployment/budget && terraform init && terraform plan -var alert_email=YOU@example.com -out=tfplan && terraform apply tfplan\ncd ../terraform && cp terraform.tfvars.example terraform.tfvars   # set allowed_cidr to your IP/32\nterraform init && terraform fmt -check && terraform validate && terraform plan -out=tfplan" },
      { id: "ex8", title: "פריסה, מעקב ופירוק (בתשלום: כ-5 סנט לשעה)", text: "התחל רק כשיש שעה פנויה, וסיים באותו יום. הצעדים המלאים ב-README: (א) apply עם -target ל-ECR ולסוד בלבד, ודחיפת ה-image; (ב) הכנסת המפתח לסוד עם read -rs ו-AWS CLI, בלי Terraform ובלי היסטוריה; (ג) plan ו-apply לכל השאר, קריאה לשירות דרך ה-ALB, ו-aws logs tail; (ד) שאילתת Logs Insights; (ה) force-new-deployment אחרי החלפת סוד; (ו) אופציונלי: בדיקת autoscaling עם 600 בקשות קצרות (כ-1.5 סנט של טוקנים); (ז) terraform destroy ו-teardown_check.sh. ענה בסוף: כמה זמן הסטאק היה למעלה, ומה העלות לפי cost_estimate.py --hours?", cmd: "cd labs/27-deployment/terraform\nterraform apply -target=aws_ecr_repository.api -target=aws_secretsmanager_secret.anthropic\nterraform output -raw push_commands\nread -rs ANTHROPIC_KEY_VALUE && aws secretsmanager put-secret-value --secret-id \"$(terraform output -raw secret_name)\" --secret-string \"$ANTHROPIC_KEY_VALUE\" > /dev/null && unset ANTHROPIC_KEY_VALUE\nterraform plan -out=tfplan && terraform apply tfplan\npython ../call_api.py --url \"$(terraform output -raw url)\" --stream\naws logs tail \"$(terraform output -raw log_group)\" --since 10m\nterraform destroy && cd ../../.. && bash labs/27-deployment/teardown_check.sh" },
    ],
  },

  quiz: [
    { q: "ב-Dockerfile יש COPY .env /app/.env, ובשכבה הבאה RUN rm /app/.env. האם המפתח נמצא ב-image?", options: ["לא: docker run /app/.env לא ימצא את הקובץ, כלומר הוא לא ב-image", "כן: השכבה שהוסיפה אותו נשארת ב-image, והשכבה הבאה רק מסמנת אותו כמחוק", "רק אם ה-image נדחף ל-registry, כי docker push מעלה גם שכבות ביניים של ה-cache", "לא, כל עוד שתי הפקודות נמצאות באותו stage, כי Docker מאחד שכבות של אותו stage בסוף הבנייה"], correct: 1, explain: "image הוא ערימה של שכבות, ו<b>מחיקה רק מוסיפה סימון whiteout</b>. ה-container אכן לא רואה את הקובץ, ולכן הבדיקה עם docker run מטעה, אבל כל מי שמושך את ה-image יכול לפתוח את השכבה המקורית. Docker לא מאחד שכבות של אותו stage. רק multi-stage, שבו ה-stage הסופי לא מעתיק את הקובץ, או סוד בזמן בנייה (--mount=type=secret), משאירים אותו בחוץ. זו הטעות השלישית ב-Dockerfile.baked." },
    { q: "ב-Dockerfile יש, בסדר הזה: COPY . /app, ואחריו RUN uv sync --locked. שינית שורה אחת ב-main.py, והבנייה מתקינה מחדש את כל התלויות. מה התיקון?", options: ["להוסיף --no-cache לבנייה, כדי שה-cache לא יתבלבל", "להעתיק קודם רק את pyproject.toml ו-uv.lock, להריץ את ההתקנה, ורק אחר כך להעתיק את הקוד", "להעביר את RUN uv sync לפני ה-FROM, כדי שהוא ירוץ פעם אחת", "להחליף את uv.lock ב-requirements.txt, כי Docker לא שומר cache לקבצי lock"], correct: 1, explain: "שינוי בשכבה בונה מחדש את <b>כל השכבות שאחריה</b>. COPY . מעתיק גם את main.py, ולכן כל שינוי בקוד מבטל את ה-cache של ההתקנה שבאה אחריו. מתקינים תלויות מתוך קבצי ה-lock בלבד, <b>לפני</b> שמעתיקים את הקוד, ואז ההתקנה נבנית מחדש רק כשה-lock משתנה. --no-cache עושה בדיוק את ההפך ממה שרוצים." },
    { q: "CMD uvicorn service.main:app (צורת shell), ובדקת עם ps ש-/bin/sh הוא PID 1 ו-uvicorn הוא הילד שלו. מה קורה ב-deployment של ECS?", options: ["כלום מיוחד: /bin/sh מעביר את ה-SIGTERM לילד, ו-uvicorn מסיים את הבקשות שבדרך", "uvicorn לא מקבל SIGTERM כי /bin/sh הוא PID 1, ונהרג עם SIGKILL אחרי ה-stopTimeout, באמצע בקשות", "אין נזק: ה-ALB מוציא את המשימה מהסבב (deregistration) לפני העצירה, ולכן אין בקשות פתוחות כשמגיע SIGKILL", "ECS מזהה צורת shell ושולח את ה-SIGTERM ישירות לתהליך uvicorn"], correct: 1, explain: "כשה-shell הוא PID 1, <b>הוא לא מעביר אותות לילד</b>. זה תלוי ב-shell (dash של Debian עושה לפעמים exec לפקודה בודדת), ולכן בודקים עם ps. ה-deregistration רק מפסיק לשלוח בקשות <b>חדשות</b>: בקשות שכבר רצות נחתכות כשמגיע SIGKILL אחרי 30 השניות של stopTimeout. בצורת exec, uvicorn מקבל SIGTERM בוודאות ומסיים בקשות שבדרך." },
    { q: "ה-Dockerfile מגדיר HEALTHCHECK שבודק /healthz, וב-container definition של ה-task אין healthCheck. מה ECS עושה עם ה-HEALTHCHECK?", options: ["משתמש בו כדי להחליף משימות לא בריאות, כמו docker run מקומי", "מתעלם ממנו: ECS עוקב רק אחרי healthCheck שמוגדר ב-container definition", "מעביר אותו ל-ALB כ-health check של ה-target group", "משתמש בו רק בזמן העלייה, עד שעובר ה-health_check_grace_period"], correct: 1, explain: "לפי התיעוד, <b>ECS לא עוקב אחרי health check שמוגדר רק ב-image</b>. מקומית, docker מציג אותו כ-healthy או unhealthy, ולכן קל להניח שגם ECS משתמש בו. לכן ב-Terraform של המעבדה ה-healthCheck חוזר ב-container definition (ecs.tf). ה-health check של ה-ALB מוגדר בנפרד, ב-target group." },
    { q: "ה-ALB בודק /healthz במקום /readyz. במצב mock, משימה עלתה אבל mockllm שלידה לא עונה (כך ש-/readyz שלה מחזיר 503). מה המשתמשים יחוו?", options: ["כלום: ה-healthCheck של ה-container יזהה את הבעיה ו-ECS יחליף את המשימה", "ה-ALB ימשיך לשלוח בקשות למשימה שנראית בריאה, והמשתמשים יקבלו שגיאות 502", "ה-ALB יחזיר 503 למשתמשים עד שהמשימה תהיה מוכנה", "autoscaling יזהה latency גבוה ויוסיף משימות, והבעיה תיפתר מעצמה"], correct: 1, explain: "/healthz בודק <b>רק שהתהליך חי</b>, ולכן גם ה-ALB וגם ה-healthCheck של ה-container (שבמעבדה בודק /healthz) רואים משימה תקינה, והתנועה ממשיכה להגיע אליה. עם <b>/readyz</b> ב-target group, ה-ALB מפסיק לשלוח אליה, ו-ECS גם מחליף אותה. משימות חדשות של autoscaling היו נתקלות באותה בעיה. שים לב: מול Anthropic, גם /readyz של המעבדה לא היה עוזר, כי בכוונה הוא לא פונה לספק. נפילה של הספק מחזירה 502 בכל מקרה, ומטפלים בה ב-fallback." },
    { q: "ב-task definition יש secrets = [{ name = \"ANTHROPIC_API_KEY\", valueFrom = <ARN של הסוד> }]. המשימה נכשלת בעלייה עם AccessDenied על secretsmanager:GetSecretValue. לאיזה role מוסיפים את ההרשאה?", options: ["ל-task role, כי הוא ה-role של ה-container שמשתמש במפתח", "ל-execution role, כי הסוכן של ECS קורא את הסוד לפני שהקוד שלך רץ", "לשניהם, כי הסוכן מעביר את ההרשאה לקוד בזמן ההזרקה", "ל-role של המשתמש שמריץ terraform apply"], correct: 1, explain: "את ההזרקה עושה <b>הסוכן של ECS</b>, עם ה-execution role, עוד לפני שה-container עולה, ולכן השגיאה היא בעלייה. ה-task role הוא של הקוד, והיה צריך את ההרשאה רק אם <b>הקוד</b> היה קורא ל-Secrets Manager בעצמו. לתת לשניהם מרחיב הרשאות בלי צורך." },
    { q: "החלפת את ערך המפתח ב-Secrets Manager. מתי המשימות הרצות ישתמשו בערך החדש?", options: ["מיד, כי valueFrom מצביע על הסוד ולא על הערך", "תוך כמה דקות, כשהסוכן של ECS מרענן את ה-cache של הסודות", "רק במשימות חדשות: צריך deployment חדש, למשל --force-new-deployment", "רק אחרי terraform apply, כי Terraform צריך לעדכן את ה-task definition"], correct: 2, explain: "הסוד מוזרק כמשתנה סביבה <b>כשה-container עולה</b>, ומשתנה סביבה של תהליך רץ לא משתנה. משימות קיימות ממשיכות עם הערך הישן עד שמחליפים אותן. terraform apply לא יעזור, כי ה-task definition מצביע על אותו ARN ולא השתנה בכלל." },
    { q: "עמית כתב ב-Terraform aws_secretsmanager_secret_version עם secret_string = var.anthropic_key, והראה ש-terraform plan מציג (sensitive value) במקום הערך. הוא טוען שזה בטוח. מה נכון?", options: ["הוא צודק: sensitive מונע מהערך להישמר בכל מקום מחוץ ל-AWS", "הערך נשמר בטקסט גלוי ב-state (ובקבצי plan שנשמרו). sensitive רק מסתיר אותו בפלט של המסוף", "הערך מוצפן ב-state כי הוא מסומן sensitive, ולכן הבעיה היא רק ב-git", "הבעיה היחידה היא שהערך יופיע ב-CloudTrail, וזה פתיר בהרשאות"], correct: 1, explain: "ה-<b>state מכיל את ערכי המשאבים</b>, ו-sensitive משפיע רק על התצוגה. מי שקורא את קובץ ה-state (או את ה-bucket שבו הוא נשמר) רואה את המפתח. הפתרונות: לשים את הערך עם ה-CLI, או <b>secret_string_wo</b> (write-only, מ-Terraform 1.11), שלא נשמר ב-state." },
    { q: "התצורה של המעבדה עולה כ-37$ לחודש (משימה אחת של 0.25 vCPU ו-0.5GB). עמית מציע לעבור ל-ARM64 (Graviton), שזול בכ-20% ב-Fargate. כמה זה יחסוך בערך?", options: ["כ-7.5$, שהם 20% מהחשבון", "כ-1.8$, כי Fargate הוא רק כ-9$ מהחשבון, ורובו (כ-73%) הוא ה-ALB וכתובות ה-IPv4 הציבוריות", "כלום, כי ב-Fargate המחיר זהה לכל הארכיטקטורות", "כ-11$, כי ARM מוריד גם את מחיר ה-ALB וגם את מחיר הכתובות"], correct: 1, explain: "לפי deploykit/cost.py, Fargate הוא כ-9$ (CPU וזיכרון), ו-20% ממנו הם כ-1.8$. ה-ALB לבדו הוא 16.43$, גם בלי אף בקשה, ועם הכתובות הציבוריות (10.95$) <b>הרשת סביב האפליקציה היא כ-73% מהחשבון</b>. להחיל את ה-20% על כל החשבון היא הטעות המפתה. מה שבאמת חוסך הוא לא להשאיר את ה-stack רץ: 8 שעות ביום ב-22 ימי עבודה מורידים אותו לכ-9.6$." },
    { q: "ביום שישי בצהריים הגדרת AWS Budget של 10$ עם התראה ב-100%, ושכחת לעשות destroy לתצורה שעולה כ-1.2$ ליום. מה יקרה?", options: ["כשההוצאה תגיע ל-10$, AWS יעצור את המשימות וה-ALB ימשיך לעבוד בלי עלות", "בעוד כשבוע תקבל מייל, לרוב באיחור של כמה שעות אחרי שהסכום נחצה, והמשאבים ימשיכו לרוץ ולחייב", "החיוב ייעצר ב-10$, וכל מה שמעבר לזה לא יחויב", "תקבל מייל מיד, כי budget בודק את ההוצאה בזמן אמת"], correct: 1, explain: "budget <b>מתריע ולא עוצר</b>: אין בו שום פעולה על המשאבים, והחיוב ממשיך. נתוני החיוב גם מתעדכנים רק כמה פעמים ביום, ולכן ההתראה מגיעה באיחור. בקצב של כ-1.2$ ליום, ה-10$ נחצים רק אחרי כשבוע. ההגנה האמיתית היא <b>terraform destroy</b> באותו יום ובדיקה שלא נשאר כלום." },
  ],

  summary: {
    points: [
      { t: "image הוא artifact שלא משתנה", b: "image הוא ערימה של שכבות tar ועוד config, ו-container הוא תהליך רגיל עם namespaces ו-cgroups. אותו image רץ מקומית, ב-CI ובענן. מה שנכנס לשכבה נשאר ב-image גם אם שכבה מאוחרת מוחקת אותו, ו-tag הוא שם שיכול לזוז, בניגוד ל-digest." },
      { t: "Dockerfile לפרודקשן", b: "base מסוג slim עם גרסה מוצמדת, multi-stage שבו רק ה-venv עובר לשלב הסופי, תלויות מ-uv.lock עם uv sync --locked, משתמש מערכת עם UID קבוע, HEALTHCHECK, ו-CMD בצורת exec כדי ש-SIGTERM יגיע לשירות. תלויות לפני קוד, כדי שה-cache יעבוד." },
      { t: "build context ו-ignore", b: "כל ה-context נשלח לבנייה. קובץ ignore בשיטת allowlist מכניס רק את מה שצריך, השורה האחרונה שמתאימה מנצחת, ולכן <code>**/.env</code> בא אחרי שורות ה-<code>!</code>. לכל Dockerfile יכול להיות ignore משלו בשם <Dockerfile>.dockerignore." },
      { t: "סודות לא נכנסים ל-image", b: "ARG נרשם ב-history, ENV נשמר ב-config, וקובץ שנמחק נשאר בשכבה. מזריקים בזמן ריצה: קובץ סוד ב-compose, ו-Secrets Manager דרך valueFrom ב-ECS, שמוזרק כשהמשימה עולה ולכן החלפה דורשת deployment. סוד לבנייה עובר רק ב-RUN --mount=type=secret." },
      { t: "חי ומוכן הן שאלות שונות", b: "liveness (/healthz) שואל אם התהליך חי, readiness (/readyz) שואל אם לשלוח אליו תנועה. ה-ALB בודק readiness, ECS בודק liveness ומתעלם מה-HEALTHCHECK שב-image. בניגוד ל-Kubernetes, ב-ECS גם כשלון ב-ALB גורם להחלפת המשימה, ולכן /readyz בודק רק דברים מקומיים ולא את הספק. health check לעולם לא קורא למודל בתשלום." },
      { t: "איפה מריצים ב-AWS", b: "ECS Fargate עם ALB נותן שליטה מלאה וגלויה, ECS Express Mode יוצר את אותם משאבים בפקודה אחת, App Runner סגור ללקוחות חדשים, ו-Lambda זול לעומס קל אבל מחייב גם על זמן ההמתנה למודל." },
      { t: "שני roles והרשאות מינימליות", b: "ה-execution role שייך לסוכן של ECS (image, לוגים, סודות), וה-task role שייך לקוד. כל הצהרה על פעולות מפורשות ועל ARNs ספציפיים. resource * רק לפעולות שאין להן אחרת, כמו ecr:GetAuthorizationToken, ותנאי SourceAccount ו-SourceArn ב-trust policy." },
      { t: "Terraform בזהירות", b: "provider מוצמד ל-major, plan -out ואז apply של אותו קובץ, state שלא נכנס ל-git, ערך הסוד מחוץ ל-Terraform או ב-secret_string_wo, ו-<code>--target</code> רק ל-bootstrap. destroy מוחק רק מה שב-state." },
      { t: "עלות לפני שהיא קורית", b: "כ-37$ לחודש לתצורה הקטנה ביותר, ו-73% מזה הם ALB וכתובות IPv4. budget נפרד שנוצר ראשון ונשאר, שמתריע באיחור ולא עוצר כלום. ובסוף כל סשן: destroy, בדיקה לפי tags, ו-Cost Explorer למחרת." },
    ],
    glossary: [
      ["Image", "ערימה של שכבות קבצים ועוד config (סביבה, משתמש, CMD). לא משתנה אחרי הבנייה."],
      ["Layer", "קובץ tar של שינויים במערכת הקבצים, שנוצר מהוראה אחת ב-Dockerfile."],
      ["Build context", "התיקייה שנשלחת לבנייה. רק ממנה COPY יכול להעתיק."],
      ["Multi-stage build", "Dockerfile עם כמה FROM, שבו רק מה שמועתק במפורש עובר לשלב הסופי."],
      ["Digest", "ה-hash של תוכן ה-image (sha256). בניגוד ל-tag, תמיד מצביע על אותם בייטים."],
      ["uv.lock", "קובץ שנועל כל תלות, כולל העקיפות, לגרסה ול-hash מדויקים."],
      ["Liveness / Readiness", "האם התהליך חי (להפעיל מחדש אם לא), והאם הוא מוכן לתנועה (לא לשלוח אליו אם לא)."],
      ["PID 1", "התהליך הראשון ב-container. מקבל את SIGTERM, ובצורת shell הוא לרוב /bin/sh ולא השירות (בודקים עם ps)."],
      ["ECS Fargate", "הרצת containers ב-AWS בלי לנהל שרתים, בחיוב לפי vCPU וזיכרון לשנייה."],
      ["Task definition", "התיאור של משימת ECS: image, משאבים, משתני סביבה, סודות, roles, לוגים ו-health check."],
      ["Execution role", "ה-IAM role של הסוכן של ECS: משיכת image, כתיבת לוגים, קריאת סודות."],
      ["Task role", "ה-IAM role של הקוד שרץ ב-container, לכל קריאה ל-AWS מהאפליקציה."],
      ["ALB / Target group", "ה-load balancer הציבורי, וקבוצת היעדים שאליה הוא מעביר בקשות לפי health check."],
      ["Secrets Manager", "שירות AWS לשמירת סודות. ECS מזריק משם ערכים לפי ARN בעליית משימה."],
      ["Terraform state", "הקובץ שבו Terraform זוכר מה יצר. רגיש, ולא נכנס ל-git."],
      ["Write-only argument", "ארגומנט ב-Terraform (מ-1.11) שנשלח ל-provider ולא נשמר ב-state, כמו secret_string_wo."],
    ],
    reading: [
      { title: "Docker: Build context and .dockerignore", url: "https://docs.docker.com/build/concepts/context/", note: "כולל קבצי ignore לכל Dockerfile, וסדר הקדימות ביניהם." },
      { title: "Docker: Build checks", url: "https://docs.docker.com/reference/build-checks/", note: "הבדיקות המובנות של BuildKit, כמו SecretsUsedInArgOrEnv ו-JSONArgsRecommended." },
      { title: "AWS: Pass Secrets Manager secrets to ECS as environment variables", url: "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html", note: "פורמט valueFrom, מפתח JSON בתוך סוד, ולמה החלפה דורשת deployment." },
      { title: "AWS: ECS container health checks", url: "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html", note: "המקור לכך ש-ECS מתעלם מה-HEALTHCHECK שב-image." },
      { title: "AWS App Runner availability change", url: "https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html", note: "App Runner לא פתוח ללקוחות חדשים, וההמלצה לעבור ל-ECS Express Mode." },
      { title: "Announcing Amazon ECS Express Mode", url: "https://aws.amazon.com/about-aws/whats-new/2025/11/announcing-amazon-ecs-express-mode/", note: "מה Express Mode יוצר, ושאין עליו תוספת מחיר." },
      { title: "Terraform: Use temporary write-only arguments", url: "https://developer.hashicorp.com/terraform/language/manage-sensitive-data/write-only", note: "secret_string_wo ו-secret_string_wo_version, מ-Terraform 1.11." },
      { title: "AWS Fargate pricing", url: "https://aws.amazon.com/fargate/pricing/", note: "המחירים שבמודל העלות. בדוק אותם לפני שאתה מצטט." },
      { title: "EGI CSIRT: Trivy supply chain vulnerability", url: "https://csirt.egi.eu/2026/03/31/trivy-supply-chain-vulnerability/", note: "האירוע של מרץ 2026: גרסאות מושפעות וגרסאות בטוחות." },
    ],
  },
};
