# מעבדה 27: Containers and Public-Cloud Deployment

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל, אלא אם כתוב אחרת.

הרעיון של המעבדה: לקחת שירות LLM שרץ אצלך במחשב, ולהפוך אותו לשירות שרץ בענן **בלי לסמוך על המחשב שלך בשום דבר**. זה עובר בארבע תחנות: image של Docker שבנוי נכון (קטן, לא רץ כ-root, בלי סודות, עם health check), סביבה מקומית מלאה עם docker compose, תשתית ב-AWS שמוגדרת בקוד (Terraform), ובסוף פריסה אמיתית, מעקב בלוגים, ופירוק מלא של הכול. לאורך כל הדרך יש בודק סטטי (`checks.py`) שאוכף את כללי השיעור, ואת חלק מהכללים שלו אתה כותב.

## מה עולה כסף, ומה לא

- **תרגילים 1 עד 6: חינם לגמרי.** הכול רץ אצלך, מול mockllm. בתרגיל 3 יש צעד אופציונלי מול Claude Haiku 5.5: פחות מעשירית סנט לשאלה.
- **תרגיל 7: חינם.** `terraform plan` לא יוצר שום משאב. ה-budget של AWS לא עולה כסף.
- **תרגיל 8: עולה כסף, כ-0.05$ לשעה** כל עוד הסטאק קיים (load balancer, כתובות IPv4 ציבוריות, משימת Fargate). סשן של שלוש שעות עולה בערך 0.15$ עד 0.25$, ועוד כמה סנטים של טוקנים. **סטאק שנשכח דולק עולה כ-1.25$ ליום, כ-37$ לחודש.** לכן תרגיל 8 נגמר ב-`terraform destroy` ובבדיקה שלא נשאר כלום, וה-budget מתרגיל 7 נשאר לשמור עליך.
- המספרים מגיעים מ-`deploykit/cost.py` (מחירי us-east-1, נבדקו ב-1 בנובמבר 2026, עם קישורים למקורות). אחרי תרגיל 7 תוכל לחשב אותם בעצמך לכל תצורה.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r labs/27-deployment/requirements.txt   # python-hcl2, fastapi, uvicorn
python -m pytest -q                                     # בדיקות הסביבה, כולל tests/test_deploy.py
python -m pytest -q labs/27-deployment/tests            # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

כלים שצריך במחשב (לא Python):

- **Docker** עם התוסף compose v2 (`docker compose version`). ב-Linux: Docker Engine, ולא חובה Docker Desktop.
- **Terraform 1.11 ומעלה** (`terraform version`). הגרסה הנוכחית בנובמבר 2026 היא 1.17.x. נדרש 1.11 לפחות בגלל write-only arguments, שמוזכרים בשיעור.
- **AWS CLI v2** עם הרשאות לחשבון שלך (`aws sts get-caller-identity` צריך להחזיר את מספר החשבון). רק לתרגילים 7 ו-8.
- אופציונלי: **trivy** לסריקת images. שים לב: במרץ 2026 פורסמה גרסה זדונית של trivy (0.69.4) ותגיות של ה-GitHub Action שלו הוחלפו בקוד שגונב credentials. אל תשתמש ב-0.69.4, ותמיד הצמד גרסה מדויקת. הגרסה הנוכחית היא 0.76.x.

## מה חדש בריפו

- **`deploykit/`**: חבילה חדשה עם קוד הייחוס של השיעור:
  - `dockerfile.py`: parser קטן ל-Dockerfile (המשכי שורות, heredoc, multi-stage) והכללים: base image מוצמד, משתמש שאינו root, אין סודות ב-ENV או ARG, HEALTHCHECK, צורת exec ל-CMD, שכבות רזות, ובדיקה של קובץ ה-ignore.
  - `terraform.py`: קורא קבצי Terraform עם python-hcl2 (בלי הבינארי של terraform ובלי חשבון AWS) ובודק: IAM של הרשאות מינימליות, אין סודות בטקסט גלוי, הפרדה בין execution role ל-task role, retention ללוגים, גרסת provider מוצמדת, ופורטים פתוחים לאינטרנט.
  - `cost.py`: מודל עלות חודשי לתצורה של המעבדה, עם המחירים והמקורות.
- **`labs/27-deployment/app/`**: השירות שנפרס. Company Brain mini API, שירות FastAPI קטן שבנוי על llmkit, באותה צורה של השירות משיעור 26 (`/healthz`, `/readyz`, `/v1/answer`, `/v1/answer/stream`). בלי מפתח הוא מדבר עם mockllm, בחינם.
  - `Dockerfile`: ה-image הנכון. ארבעה שלבים: `builder` (uv מתקין את התלויות הנעולות), `runtime` (Python slim ומשתמש מערכת בלי הרשאות), `mockllm` (בשביל compose), `api` (השלב האחרון, ולכן ברירת המחדל).
  - `Dockerfile.dockerignore`: קובץ ignore בשיטת allowlist: מוציא הכול ומכניס בחזרה רק את מה שצריך. Docker משתמש בקובץ `<שם ה-Dockerfile>.dockerignore` שליד ה-Dockerfile לפני `.dockerignore` שבשורש ה-context.
  - `Dockerfile.single`: Dockerfile ראשון טיפוסי, להשוואה. `Dockerfile.baked`: שלוש דרכים לאפות סוד לתוך image, עם מפתחות **מזויפים**, כדי לראות שכל אחת מהן דולפת.
  - `pyproject.toml` ו-`uv.lock`: התלויות של ה-image, נעולות לגרסה ול-hash מדויקים.
- **`compose.yaml`**: הסביבה המקומית. `api` ו-`mockllm` כברירת מחדל, ו-`api-real` (פרופיל `real`) שמקבל את המפתח כ-compose secret.
- **`terraform/`**: ECS Fargate מאחורי Application Load Balancer, ECR, Secrets Manager, שני IAM roles, CloudWatch Logs ו-autoscaling. 21 משאבים. **`budget/`**: תקציב חודשי עם התראות במייל, כ-root module נפרד, כדי שלא יימחק עם המעבדה.
- **`fixtures/`**: `bad_iam.json` ו-`bad_task.tf` (תשתית גרועה בכוונה, לבודק), ו-`fake.env` (מפתח מזויף לתרגיל 4).
- **הסקריפטים**: `checks.py` (הבודק הסטטי), `cost_estimate.py`, `call_api.py` (קריאות, סטרימינג ובדיקת עומס קטנה), `layer_peek.py` (מחפש קבצים בתוך שכבות של image), `teardown_check.sh` (מה נשאר ב-AWS אחרי destroy).
- **`mine.py`**: הקוד שלך לתרגילים 5, 6 ו-7. כל הסקריפטים משתמשים בפונקציות שלך. כל עוד פונקציה היא TODO, הסקריפט משתמש בגרסת הייחוס ומודיע על זה. עם `--reference` הוא משתמש רק בגרסאות הייחוס.

## התרגילים

**1. לבנות image ולמדוד אותו (חינם).** בנה את שני ה-images. ה-context הוא שורש הריפו, כי ה-image צריך את `llmkit/`. אחרי הבנייה השווה גדלים, הסתכל על השכבות, והרץ את השירות.

```bash
docker build -f labs/27-deployment/app/Dockerfile        -t company-brain-api:dev .
docker build -f labs/27-deployment/app/Dockerfile.single -t company-brain-api:single .
docker images company-brain-api
docker history company-brain-api:dev
docker run --rm company-brain-api:dev id          # uid=10001(app): לא root
docker run --rm company-brain-api:single id       # uid=0(root)
docker run -d --name l27 -p 127.0.0.1:8000:8000 company-brain-api:dev
docker ps                                          # אחרי כ-20 שניות: (healthy)
curl -s localhost:8000/healthz; curl -s localhost:8000/readyz   # readyz מחזיר 503: אין mockllm. למה זה נכון?
docker rm -f l27
```

שאלות: כמה מגה-בייט כל image? כמה מההפרש נובע מה-base image (`python:3.12` מלא מול `slim`), וכמה מה-multi-stage? כדי להפריד, שנה זמנית את השורה הראשונה ב-`Dockerfile.single` ל-`python:3.12.16-slim-trixie`, בנה שוב, ומדוד. אם יש לך Docker 27 ומעלה, הרץ גם `docker build --check -f labs/27-deployment/app/Dockerfile.single .` וראה מה הבודק המובנה של BuildKit מוצא.

**2. Cache של שכבות וסריקת פגיעויות (חינם).** הוסף שורת הערה ל-`app/service/main.py` ובנה שוב. בפלט של BuildKit תראה `CACHED` ליד שלב ה-`uv sync`: התלויות לא הותקנו מחדש, כי רק קבצי ה-lock מחוברים לשלב הזה. עכשיו הוסף שורת הערה ל-`pyproject.toml` ובנה שוב: הפעם `uv sync` רץ מחדש. אחר כך סרוק את שני ה-images (trivy רץ בתוך container, והגרסה מוצמדת):

```bash
docker build -f labs/27-deployment/app/Dockerfile -t company-brain-api:dev .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.1 \
  image --severity HIGH,CRITICAL --quiet company-brain-api:dev
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.1 \
  image --severity HIGH,CRITICAL --quiet company-brain-api:single
```

שאלות: כמה פגיעויות HIGH ו-CRITICAL בכל image, ומאיפה רובן מגיעות (חבילות מערכת או חבילות Python)? למה image קטן יותר הוא גם image בטוח יותר? אם אתה מחובר ל-Docker Hub, אפשר להשוות גם עם `docker scout quickview company-brain-api:dev`. החזר את ההערות שהוספת לפני שממשיכים.

**3. הסטאק המקומי עם docker compose (חינם, וצעד אופציונלי של פחות מסנט).** הרם את השירות יחד עם mockllm. ה-API מחכה ש-mockllm יהיה healthy לפני שהוא עולה, והפורט פתוח רק ל-localhost.

```bash
cd labs/27-deployment
docker compose up --build -d
docker compose ps                                   # שני השירותים healthy
python call_api.py                                  # health, ואז תשובה מ-mockllm
python call_api.py --stream
docker compose logs api | tail -5                   # לוגים של JSON, שורה לכל אירוע
docker compose stop mockllm
python call_api.py                                  # healthz 200, readyz 503, answer 502
docker compose start mockllm
```

הסבר במשפט אחד: למה `/healthz` נשאר 200 כש-mockllm למטה, ומה היה קורה ב-AWS אם ה-load balancer היה בודק את `/healthz` במקום את `/readyz`?

הצעד האופציונלי, מול Claude: המפתח נטען רק ל-shell הנוכחי, ו-compose מעביר אותו כ-secret, כלומר כקובץ ב-`/run/secrets/anthropic_api_key` ולא כמשתנה סביבה.

```bash
set -a; . ../../.env; set +a
docker compose --profile real up --build -d api-real
python call_api.py --url http://127.0.0.1:8001
docker inspect company-brain-l27-api-real-1 --format '{{json .Config.Env}}'   # אין שם מפתח
docker compose --profile real down
cd ../..
```

**4. למה אסור לאפות סוד לתוך image (חינם, מפתחות מזויפים).** `Dockerfile.baked` בונה מעל ה-image הטוב ועושה שלוש טעויות: build arg, ENV עם ערך, וקובץ שמועתק ונמחק בשכבה הבאה. בנה אותו ומצא את שלושת המפתחות המזויפים בשלוש דרכים שונות:

```bash
docker build -f labs/27-deployment/app/Dockerfile.baked \
  --build-arg ANTHROPIC_API_KEY=sk-ant-lab27-FAKE-buildarg-000000 -t company-brain-api:baked .
docker history --no-trunc company-brain-api:baked | grep -o "sk-ant-lab27-FAKE[^ ]*"
docker inspect company-brain-api:baked --format '{{json .Config.Env}}'
docker save company-brain-api:baked -o labs/27-deployment/results/baked.tar
python labs/27-deployment/layer_peek.py labs/27-deployment/results/baked.tar --find .env
docker run --rm company-brain-api:baked ls -la /app       # הקובץ "לא קיים"... בשכבה האחרונה
```

שאלות: מי יכול לראות כל אחד מהשלושה (מי שמושך את ה-image, מי שמריץ אותו, מי שבונה image מעליו)? ולמה גם `docker run -e ANTHROPIC_API_KEY=...` הוא פשרה: איפה הערך נראה במקרה הזה (רמז: `docker inspect` של ה-container)? בסוף: `rm labs/27-deployment/results/baked.tar && docker rmi company-brain-api:baked`.

**5. כללי Dockerfile בבודק הסטטי (קוד).** קרא את `rule_base_image_pinned` ב-`mine.py` (דוגמה פתורה), וממש את `rule_runs_as_non_root` ואת `rule_no_secrets_in_build`. כל מה שהפונקציות מקבלות מתועד בראש הקובץ. שים לב לשני מקרים שקל לפספס: שלב שבנוי `FROM` שלב קודם יורש ממנו את המשתמש, ו-`ENV ANTHROPIC_API_KEY=` ריק הוא placeholder ולא דליפה. כשהבדיקות עוברות, הרץ את הבודק על שלושת ה-Dockerfiles והשווה למה שמצא `docker build --check` בתרגיל 1: מה כל אחד מוצא ששני לא?

```bash
python -m pytest -q labs/27-deployment/tests/test_ex5_dockerfile_rules.py
python labs/27-deployment/checks.py labs/27-deployment/app/Dockerfile labs/27-deployment/app/Dockerfile.single labs/27-deployment/app/Dockerfile.baked
```

**6. IAM של הרשאות מינימליות (קוד).** ממש את `rule_iam_least_privilege`. אחר כך הרץ את הבודק על ה-Terraform של המעבדה (צריך לצאת נקי) ועל שני ה-fixtures (צריכים ליפול). הנתונים שהבודק עובד עליהם:

- **`terraform/iam.tf`**: שני roles. ה-execution role מקבל ארבע הצהרות: `ecr:BatchGetImage` ו-`ecr:GetDownloadUrlForLayer` רק על ה-repository של השירות, `ecr:GetAuthorizationToken` על `"*"`, `logs:CreateLogStream` ו-`logs:PutLogEvents` רק על ה-log group, ו-`secretsmanager:GetSecretValue` רק על הסוד של המפתח. ה-task role ריק.
- **`fixtures/bad_iam.json`**: שבע הצהרות, ביניהן `"Action": "*"`, `secretsmanager:*`, `s3:Get*`, `iam:PassRole` על `"*"`, ו-`NotAction`.
- **`fixtures/bad_task.tf`**: אותו role ל-execution ול-task, המפתח כמשתנה סביבה רגיל, `actions = ["*"]`, ומשתנה של מפתח עם default.

```bash
python -m pytest -q labs/27-deployment/tests/test_ex6_iam.py
python labs/27-deployment/checks.py labs/27-deployment/terraform labs/27-deployment/fixtures/bad_iam.json labs/27-deployment/fixtures/bad_task.tf
```

שאלות: למה `ecr:GetAuthorizationToken` מקבל `"*"` ולא נחשב הפרה? אם Company Brain יצטרך לקרוא מסמכים מ-S3, לאיזה role מוסיפים את ההרשאה, ואיך תיראה ההצהרה?

**7. קודם תקציב, אחר כך plan, ואז מחשבון (קוד, וחינם ב-AWS).** ממש את `monthly_cost` והרץ את המחשבון על כמה תצורות. אחר כך צור את ה-budget (חינם) ותריץ `terraform plan` על התשתית: plan קורא מהחשבון אבל לא יוצר כלום.

```bash
python -m pytest -q labs/27-deployment/tests/test_ex7_cost.py
python labs/27-deployment/cost_estimate.py
python labs/27-deployment/cost_estimate.py --hours 3
python labs/27-deployment/cost_estimate.py --private-nat
python labs/27-deployment/cost_estimate.py --private-endpoints
python labs/27-deployment/cost_estimate.py --arch ARM64

cd labs/27-deployment/budget
terraform init && terraform plan -var alert_email=YOU@example.com -out=tfplan && terraform apply tfplan
cd ../terraform
cp terraform.tfvars.example terraform.tfvars        # ושים ב-allowed_cidr את ה-IP שלך: curl -s https://checkip.amazonaws.com
terraform init
terraform fmt -check && terraform validate
terraform plan -out=tfplan
cd ../../..
```

קרא את ה-plan מלמעלה למטה. שאלות: כמה משאבים ייווצרו (צריך להיות 21)? אילו מהם עולים כסף כל שעה שהם קיימים, גם בלי אף בקשה? ומה החלק של העלות שלא תלוי בכלל במספר המשימות? ולמה private subnets עם VPC endpoints יוצא יקר יותר מ-NAT gateway בתצורה כזו קטנה?

**8. פריסה, מעקב ופירוק (עולה כסף: כ-0.05$ לשעה, ופחות מסנט של טוקנים).** התחל רק כשיש לך שעה פנויה, וסיים את כל הצעדים באותו יום. ההגדרה: `terraform/terraform.tfvars` מתרגיל 7.

א. **Bootstrap**: קודם רק ה-repository והסוד, כי השירות צריך image וערך לסוד לפני שהוא עולה. `-target` נועד בדיוק למצב כזה, ולא לשימוש יומיומי.

```bash
cd labs/27-deployment/terraform
terraform apply -target=aws_ecr_repository.api -target=aws_secretsmanager_secret.anthropic
terraform output -raw push_commands                 # שלוש פקודות: login, tag, push. הרץ אותן מתיקיית השורש
```

ב. **הערך של הסוד**, בלי שיופיע בהיסטוריה של ה-shell ובלי לעבור דרך Terraform:

```bash
read -rs ANTHROPIC_KEY_VALUE      # הדבק את המפתח ולחץ Enter: שום דבר לא מוצג
aws secretsmanager put-secret-value --secret-id "$(terraform output -raw secret_name)" \
  --secret-string "$ANTHROPIC_KEY_VALUE" > /dev/null && unset ANTHROPIC_KEY_VALUE
```

ג. **כל השאר**, ואז לבדוק:

```bash
terraform plan -out=tfplan && terraform apply tfplan          # כ-3 עד 5 דקות
python ../call_api.py --url "$(terraform output -raw url)"
python ../call_api.py --url "$(terraform output -raw url)" --stream
aws logs tail "$(terraform output -raw log_group)" --since 10m --follow
```

ד. **Logs Insights**: ב-CloudWatch, Logs Insights, בחר את ה-log group והרץ:

```
fields @timestamp, msg, rid, path, status, ms, cost_usd
| filter msg = "answer" or status >= 500
| sort @timestamp desc
| limit 20
```

ה. **החלפת סוד**: ECS מזריק את הסוד רק כשמשימה עולה. אחרי `put-secret-value` עם ערך חדש, משימות קיימות ממשיכות עם הישן עד deployment חדש:

```bash
aws ecs update-service --cluster company-brain --service company-brain-api --force-new-deployment > /dev/null
aws ecs wait services-stable --cluster company-brain --services company-brain-api
```

ו. **Autoscaling** (אופציונלי: 600 בקשות קצרות ל-Haiku 5.5 הן בערך 70 טוקני קלט ו-30 טוקני פלט כל אחת, כלומר כ-1.5 סנט בסך הכול). המדיניות מכוונת ל-60 בקשות לדקה למשימה. ה-alarm של target tracking מוסיף משימה רק אחרי כשלוש דקות רצופות מעל היעד, ולכן העומס צריך להימשך יותר משלוש דקות, לא להיות חזק במיוחד. עם 3 בקשות במקביל ותשובה של כשנייה, יוצא בערך 180 בקשות לדקה, פי שלושה מהיעד, למשך כשלוש וחצי דקות:

```bash
python ../call_api.py --url "$(terraform output -raw url)" --load 600 --concurrency 3 --max-tokens 30
aws ecs describe-services --cluster company-brain --services company-brain-api --query 'services[0].[desiredCount,runningCount]'
```

אם desiredCount לא עלה, חכה עוד דקה ובדוק שוב, ובדוק ב-CloudWatch Alarms את ה-alarm ש-autoscaling יצר. אחרי כרבע שעה בלי עומס הוא יחזור ל-1: ה-alarm של scale in דורש הרבה יותר נקודות מדידה, בכוונה, כדי לא להוריד משימות בגלל הפוגה קצרה.

ז. **פירוק. חובה, באותו יום:**

```bash
terraform destroy                                   # מאשרים עם yes. כ-3 עד 5 דקות
cd ../../..
bash labs/27-deployment/teardown_check.sh           # כל הסעיפים ריקים, חוץ מה-budget
```

ורשימת הבדיקה לפירוק, שכדאי לעבור עליה גם בעתיד בכל פרויקט:

- `terraform destroy` הסתיים עם "Destroy complete", ו-`terraform state list` ריק.
- `teardown_check.sh` לא מראה load balancer, cluster, משימות, repository, סוד או log group של הפרויקט.
- ה-budget עדיין קיים (הוא ב-root module אחר, וזה בכוונה).
- `docker logout` מה-registry של ECR, ומחיקת `terraform.tfstate*` אם אתה לא מתכנן לחזור לזה.
- מחר: Billing, ואז Cost Explorer. העלות של היום מופיעה באיחור של כמה שעות. סכום של כמה עשרות סנטים הוא מה שציפינו.

שאלות לסיום: כמה זמן הסטאק היה למעלה, ומה העלות לפי `cost_estimate.py --hours <מספר השעות>`? האם זה מתאים למה שתראה מחר ב-Cost Explorer?

## לפרוס את השירות משיעור 26 במקום

השירות כאן בנוי בכוונה באותה צורה כמו `servekit` משיעור 26: אותם endpoints של health, אותה הגדרה דרך משתני סביבה, ואותו llmkit. כדי לפרוס את servekit עם אותה תשתית:

1. העתק את `app/Dockerfile` ושנה בשלב `api` את ה-COPY של `labs/27-deployment/app/service/` לתיקייה של servekit, ואת ה-CMD לנתיב של אפליקציית ה-ASGI שלו (למשל `servekit.app:app`, לפי מה שקיים בפועל).
2. הוסף את התלויות של servekit ל-`app/pyproject.toml` והרץ `uv lock` באותה תיקייה.
3. הוסף את התיקייה החדשה כשורת `!` ב-`Dockerfile.dockerignore`, לפני שורות ה-`**/.env`.
4. ודא ש-`/healthz` ו-`/readyz` קיימים ומחזירים 200, כי ה-load balancer וה-healthCheck של ECS בודקים אותם. בנה עם tag חדש (למשל `v2`), שנה את `image_tag` ב-tfvars, ו-`terraform apply`.

## כללים

- **אף מפתח אמיתי לא נכנס ל-image, ל-Dockerfile, ל-compose.yaml, ל-Terraform או ל-state.** המפתחות במעבדה (`sk-ant-lab27-FAKE-...`) מזויפים, ונועדו להימצא.
- **תמיד `terraform plan` לפני `apply`**, ותמיד לקרוא אותו. `terraform apply` בלי קובץ plan מציג plan ומבקש אישור: קרא גם אותו.
- **ה-state של Terraform לא נכנס ל-git** (`terraform/.gitignore` דואג לזה). הוא מכיל מזהים של משאבים, ויכול להכיל סודות.
- המחירים משתנים. לפני שאתה מצטט מספר למישהו, בדוק אותו בעמודי המחירים של AWS.
- את קוד הייחוס ב-`deploykit/` אל תקרא לפני שהבדיקות שלך עוברות.
