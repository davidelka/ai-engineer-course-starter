// Lesson 27 aids: image-build animation (layers + cache), AWS request path with IAM boundaries,
// interactive Dockerfile linter, monthly cost estimator. Uses $, h, esc at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l27-style";
  function style() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent = `
.l27 .l27-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 12px; }
@media (max-width: 640px) { .l27 .l27-grid { grid-template-columns: minmax(0, 1fr); } }
.l27 .l27-df { font-family: var(--mono); font-size: .72rem; line-height: 1.5; background: var(--code-bg); border-radius: 8px; padding: 6px 4px; direction: ltr; text-align: left; overflow-x: auto; }
.l27 .l27-df div { padding: 0 6px; white-space: pre; border-left: 3px solid transparent; }
.l27 .l27-df div.st { color: var(--muted); }
.l27 .l27-df div.on { background: var(--signal-soft); border-left-color: var(--signal); }
.l27 .l27-df div.bad { background: var(--bad-soft); border-left-color: var(--bad); }
.l27 .l27-stacks { display: grid; gap: 8px; direction: ltr; }
.l27 .l27-stack { border: 1px solid var(--line); border-radius: 8px; padding: 6px; display: grid; gap: 3px; }
.l27 .l27-stack h5 { margin: 0 0 2px; font-family: var(--mono); font-size: .72rem; color: var(--muted); font-weight: 600; }
.l27 .l27-ly { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; font-family: var(--mono); font-size: .7rem; padding: 3px 6px; border-radius: 5px; background: var(--code-bg); color: var(--muted); }
.l27 .l27-ly.cached { background: var(--good-soft); color: var(--ink); }
.l27 .l27-ly.build { background: var(--signal-soft); color: var(--ink); animation: pop .4s ease; }
.l27 .l27-ly.drop { text-decoration: line-through; opacity: .55; }
.l27 .l27-ly span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.l27 .l27-pill { font-family: var(--mono); font-size: .66rem; padding: 0 6px; border-radius: 999px; background: var(--surface); }
.l27 .l27-arch { display: grid; gap: 6px; direction: ltr; }
.l27 .l27-zone { border: 1.5px dashed var(--line); border-radius: 10px; padding: 8px; display: grid; gap: 6px; }
.l27 .l27-zone > b { font-family: var(--mono); font-size: .7rem; color: var(--muted); font-weight: 600; }
.l27 .l27-row { display: flex; flex-wrap: wrap; gap: 6px; }
.l27 .l27-box { flex: 1 1 110px; min-width: 0; border: 1.5px solid var(--line); border-radius: 8px; padding: 6px 8px; font-size: .74rem; background: var(--surface); text-align: center; line-height: 1.3; }
.l27 .l27-box small { display: block; color: var(--muted); font-size: .64rem; }
.l27 .l27-box.on { border-color: var(--accent); background: var(--accent-soft); }
.l27 .l27-box.err { border-color: var(--bad); background: var(--bad-soft); }
.l27 .l27-box.ok { border-color: var(--good); }
.l27 .l27-steps { display: grid; gap: 4px; }
.l27 .l27-step { font-size: .84rem; padding: 4px 8px; border-radius: 6px; color: var(--muted); display: grid; grid-template-columns: 1.6rem minmax(0, 1fr); gap: 6px; }
.l27 .l27-step b { font-family: var(--mono); }
.l27 .l27-step.on { background: var(--accent-soft); color: var(--ink); }
.l27 .l27-step.err { background: var(--bad-soft); color: var(--ink); }
.l27 .l27-step.done { color: var(--ink); }
.l27 .l27-role { font-family: var(--mono); font-size: .68rem; padding: 0 6px; border-radius: 999px; border: 1px solid var(--line); white-space: nowrap; }
.l27 .l27-role.exec { border-color: var(--signal); color: var(--signal); }
.l27 .l27-role.task { border-color: var(--accent); color: var(--accent); }
.l27 .l27-find { display: grid; gap: 4px; }
.l27 .l27-f { font-size: .82rem; padding: 4px 8px; border-radius: 6px; border-inline-start: 3px solid var(--line); }
.l27 .l27-f.error { border-color: var(--bad); background: var(--bad-soft); }
.l27 .l27-f.warning { border-color: var(--signal); background: var(--signal-soft); }
.l27 .l27-f.info { border-color: var(--accent); background: var(--accent-soft); }
.l27 .l27-f code { font-size: .78rem; }
.l27 .l27-opts { display: grid; gap: 8px; }
.l27 .l27-opt { display: grid; gap: 4px; }
.l27 .l27-opt > span { font-size: .84rem; color: var(--muted); }
.l27 .l27-items { display: grid; gap: 4px; }
.l27 .l27-it { display: grid; grid-template-columns: minmax(0, 1fr) 4.6rem; gap: 2px 8px; font-size: .84rem; padding: 4px 0; border-bottom: 1px solid var(--line); }
.l27 .l27-it .v { font-family: var(--mono); text-align: left; direction: ltr; font-variant-numeric: tabular-nums; }
.l27 .l27-it small { grid-column: 1 / -1; color: var(--muted); font-size: .76rem; }
.l27 .l27-it i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-inline-end: 6px; vertical-align: middle; }
.l27 .l27-big { font-size: 1.3rem; font-weight: 700; font-family: var(--mono); direction: ltr; unicode-bidi: isolate; }
`;
    document.head.append(s);
  }
  const C = ["var(--accent)", "var(--signal)", "var(--good)", "var(--bad)", "color-mix(in srgb, var(--accent) 45%, var(--surface))",
    "color-mix(in srgb, var(--signal) 45%, var(--surface))", "color-mix(in srgb, var(--good) 45%, var(--surface))", "var(--muted)",
    "color-mix(in srgb, var(--bad) 40%, var(--surface))", "color-mix(in srgb, var(--muted) 40%, var(--surface))", "var(--ink)"];

  /* ================= animation: image build ================= */
  window.AIDS["l27build"] = function (host) {
    style();
    // Each step: stage, Dockerfile text, layer label, size MB, seconds when built, depends: "deps" | "code" | "base" | null
    const GOOD = [
      { st: "builder", t: "FROM python:3.12.16-slim-trixie AS builder", ly: "base: python slim", mb: 125, s: 0, dep: "base", base: true },
      { st: "builder", t: "COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/", ly: "uv binary", mb: 40, s: 2, dep: null },
      { st: "builder", t: "ENV UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv ...", ly: "(config only)", mb: 0, s: 0, dep: null },
      { st: "builder", t: "RUN --mount=bind uv.lock,pyproject.toml uv sync --locked", ly: "/opt/venv (deps)", mb: 45, s: 35, dep: "deps" },
      { st: "runtime", t: "FROM python:3.12.16-slim-trixie AS runtime", ly: "base: python slim", mb: 125, s: 0, dep: "base", base: true },
      { st: "runtime", t: "RUN groupadd ... && useradd --uid 10001 app", ly: "user app", mb: 0.1, s: 1, dep: null },
      { st: "runtime", t: "ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app", ly: "(config only)", mb: 0, s: 0, dep: null },
      { st: "api", t: "FROM runtime AS api", ly: "(runtime layers)", mb: 0, s: 0, dep: null },
      { st: "api", t: "COPY --from=builder /opt/venv /opt/venv", ly: "venv from builder", mb: 45, s: 2, dep: "deps" },
      { st: "api", t: "COPY llmkit/ /app/llmkit/", ly: "llmkit", mb: 0.2, s: 0.3, dep: null },
      { st: "api", t: "COPY labs/27-deployment/app/service/ /app/service/", ly: "service code", mb: 0.05, s: 0.3, dep: "code" },
      { st: "api", t: "USER app / HEALTHCHECK ... / CMD [\"uvicorn\", ...]", ly: "(config only)", mb: 0, s: 0, dep: null },
    ];
    const BAD = [
      { st: "single", t: "FROM python:3.12", ly: "base: python full", mb: 1020, s: 0, dep: "base", base: true },
      { st: "single", t: "WORKDIR /app", ly: "(config only)", mb: 0, s: 0, dep: null },
      { st: "single", t: "COPY . .   (the code FIRST)", ly: "all the code", mb: 0.3, s: 0.5, dep: "code" },
      { st: "single", t: "RUN pip install -r requirements.txt", ly: "site-packages + pip cache", mb: 70, s: 55, dep: "deps" },
      { st: "single", t: "CMD uvicorn service.main:app", ly: "(config only)", mb: 0, s: 0, dep: null },
    ];
    host.innerHTML = `<div class="sim l27">
      <div class="seg" role="group" aria-label="change">${[["first", "בנייה ראשונה"], ["code", "שיניתי קוד"], ["deps", "שיניתי תלות"]].map(([k, t], i) => `<button data-k="${k}" aria-pressed="${i === 1}">${t}</button>`).join("")}</div>
      <label style="font-size:.88rem"><input type="checkbox" id="bb-bad"> <b>סדר גרוע</b>: Dockerfile של שלב אחד, שמעתיק את הקוד <b>לפני</b> התקנת התלויות</label>
      <div class="l27-grid">
        <div><div class="eyebrow">Dockerfile</div><div class="l27-df" id="bb-df"></div></div>
        <div><div class="eyebrow">Layers</div><div class="l27-stacks" id="bb-st"></div></div>
      </div>
      <div class="cap"><b id="bb-t"></b><div class="muted" id="bb-b"></div></div>
      <div class="stats" id="bb-stats"></div>
      <div class="row"><button class="btn small primary" id="bb-play">השהה</button><button class="btn small" id="bb-prev">→</button><button class="btn small" id="bb-next">←</button><span class="spacer"></span><span class="counter" id="bb-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let change = "code", i = -1, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    const steps = () => (g("bb-bad").checked ? BAD : GOOD);
    function status(S) {
      // which steps rebuild: from the first step whose dependency changed, to the end of its stage
      const out = S.map(() => "cached");
      if (change === "first") return S.map(() => "build");
      // single-stage: requirements.txt arrives with COPY . . so a dependency change is also a code change
      const ch = g("bb-bad").checked && change === "deps" ? "code" : change;
      S.forEach((s, k) => {
        if (s.dep === ch) {
          for (let j = k; j < S.length && S[j].st === s.st; j++) out[j] = "build";
          // stages built FROM this stage, or copying from it, are affected too
          if (s.st === "builder") S.forEach((x, m) => { if (x.dep === "deps" && x.st !== "builder") out[m] = "build"; });
        }
      });
      // in the good file, a later COPY in the api stage rebuilds what follows it
      S.forEach((s, k) => { if (out[k] === "build") for (let j = k; j < S.length && S[j].st === s.st; j++) out[j] = "build"; });
      return out;
    }
    function draw() {
      const S = steps(), stt = status(S), bad = g("bb-bad").checked;
      g("bb-df").innerHTML = S.map((s, k) => `<div class="${k === i ? "on" : ""}">${esc(s.t)}</div>`).join("");
      const stages = [...new Set(S.map((s) => s.st))];
      g("bb-st").innerHTML = stages.map((st) => {
        const rows = S.map((s, k) => [s, k]).filter(([s]) => s.st === st);
        const dropped = st === "builder";
        return `<div class="l27-stack"><h5>${esc(st)}${dropped ? " (not shipped)" : st === "api" || st === "single" ? " (final image)" : ""}</h5>${rows.map(([s, k]) => {
          if (k > i) return `<div class="l27-ly"><span>…</span><span></span></div>`;
          const cls = (stt[k] === "cached" ? "cached" : "build") + (dropped ? " drop" : "");
          const lab = stt[k] === "cached" ? "CACHED" : s.s ? `${s.s}s` : "0s";
          return `<div class="l27-ly ${cls}"><span>${esc(s.ly)}</span><span class="l27-pill">${s.mb ? s.mb + " MB · " : ""}${lab}</span></div>`;
        }).join("")}</div>`;
      }).join("");
      const done = Math.min(i, S.length - 1);
      const secs = S.slice(0, done + 1).reduce((a, s, k) => a + (stt[k] === "build" ? s.s : 0), 0);
      const finalMb = bad ? S.reduce((a, s) => a + s.mb, 0) : S.filter((s) => s.st !== "builder").reduce((a, s) => a + s.mb, 0) - 0;
      g("bb-stats").innerHTML = `<span>זמן בנייה עד כאן: <b>~${secs.toFixed(1)}s</b></span>` + (i >= S.length - 1
        ? `<span>image סופי: <b>~${Math.round(finalMb)} MB</b></span><span>${bad ? "עם multi-stage ו-slim: <b>~171 MB</b>" : "ב-Dockerfile.single: <b>~1090 MB</b>"}</span>` : "");
      const cur = S[Math.max(0, i)];
      let t, b;
      if (i < 0) { t = "מוכן לבנייה"; b = change === "first" ? "אין cache: כל שכבה תיבנה." : change === "code" ? "שינית שורה ב-service/main.py. אילו שכבות ייבנו מחדש?" : "הוספת תלות ל-pyproject.toml והרצת uv lock. אילו שכבות ייבנו מחדש?"; }
      else if (i >= S.length - 1) {
        t = "הבנייה הסתיימה";
        b = bad && change === "code" ? "שינוי של שורה אחת בקוד גרם להתקנה מחדש של כל התלויות, כי COPY . . בא לפני pip install. זה המחיר של הסדר הגרוע, בכל בנייה."
          : !bad && change === "code" ? "רק שכבת הקוד נבנתה מחדש. שלב ה-uv sync נשאר CACHED, כי הוא רואה רק את uv.lock ו-pyproject.toml."
          : change === "deps" ? "שינוי בתלויות בונה מחדש את ה-venv, ואת כל מה שמעתיק אותו. זה צפוי, וקורה רק כשהתלויות משתנות."
          : bad ? "image של שלב אחד: ה-base המלא וה-cache של pip נשארים בו." : "שלב builder לא נשלח: רק ה-venv הועתק ממנו ל-image הסופי.";
      } else {
        t = `${cur.st}: ${cur.t.split(" ")[0]}`;
        b = stt[i] === "cached" ? "CACHED: אותה הוראה, אותה שכבה קודמת, אותם קבצי קלט. Docker משתמש בשכבה הקיימת, בלי זמן."
          : cur.dep === change && change !== "first" ? "הקלט של ההוראה הזו השתנה, ולכן היא נבנית מחדש, וגם כל מה שאחריה באותו שלב."
          : change === "first" ? (cur.base ? "מושכים את ה-base image מה-registry (ב-cache מקומי אחרי הפעם הראשונה)." : "נבנית לראשונה.")
          : "נבנית מחדש כי שכבה קודמת באותו שלב השתנתה: כל שכבה בנויה מעל זו שלפניה.";
      }
      g("bb-t").textContent = t; g("bb-b").textContent = b;
      g("bb-c").textContent = `${Math.max(0, i + 1)}/${S.length}`;
      host.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.k === change)));
    }
    const step = (d) => { const S = steps(); i = Math.max(-1, Math.min(S.length - 1, i + d)); draw(); };
    const tick = () => {
      clearTimeout(timer);
      if (!playing) return;
      timer = setTimeout(() => { const S = steps(); if (i >= S.length - 1) { i = -1; } else step(1); draw(); tick(); }, i >= steps().length - 1 ? 4500 : 1300);
    };
    const setP = (p) => { playing = p; g("bb-play").textContent = p ? "השהה" : "נגן"; tick(); };
    host.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { change = b.dataset.k; i = -1; draw(); setP(true); }));
    g("bb-bad").addEventListener("change", () => { i = -1; draw(); setP(true); });
    g("bb-play").addEventListener("click", () => setP(!playing));
    g("bb-next").addEventListener("click", () => { setP(false); step(1); });
    g("bb-prev").addEventListener("click", () => { setP(false); step(-1); });
    draw(); setP(playing);
    return () => clearTimeout(timer);
  };

  /* ================= sim: request path with IAM boundaries ================= */
  window.AIDS["l27path"] = function (host) {
    style();
    const STEPS = [
      { box: "ecr", role: "exec", t: "המשימה עולה: הסוכן של ECS מושך את ה-image מ-ECR", b: "ecr:GetAuthorizationToken (על *, אין דרך אחרת) ואז ecr:BatchGetImage ו-GetDownloadUrlForLayer, רק על ה-repository של השירות. הקוד שלך עוד לא רץ.", fail: "noecr" },
      { box: "sm", role: "exec", t: "הסוכן קורא את הסוד מ-Secrets Manager", b: "secretsmanager:GetSecretValue רק על ה-ARN של הסוד. הערך הופך למשתנה הסביבה ANTHROPIC_API_KEY בתוך ה-container. ה-task definition מכיל רק את ה-ARN.", fail: "nosecret" },
      { box: "cw", role: "exec", t: "נפתח log stream ב-CloudWatch Logs", b: "logs:CreateLogStream ו-PutLogEvents רק על ה-log group. מכאן כל שורה ש-uvicorn כותב ל-stdout מגיעה ל-CloudWatch.", fail: null },
      { box: "task", role: null, t: "ה-container עלה. ECS בודק /healthz, ה-ALB בודק /readyz", b: "ECS: האם התהליך חי (אם לא, מחליף). ה-ALB: האם מוכן לתנועה (אם לא, לא שולח אליו, ו-ECS גם מחליף את המשימה: בניגוד ל-Kubernetes, כשלון ב-target group אינו רק הוצאה מהסבב). רק כשה-target group מסמן healthy, המשימה בסבב.", fail: "health" },
      { box: "alb", role: null, t: "בקשה מגיעה: משתמש ← ALB על פורט 80", b: "ה-security group של ה-ALB מקבל רק את allowed_cidr. ה-ALB בוחר משימה בריאה מה-target group.", fail: null },
      { box: "task", role: null, t: "ALB ← משימה על פורט 8000", b: "ה-security group של המשימה מקבל תנועה רק מה-security group של ה-ALB. גם עם IP ציבורי, אי אפשר לפנות אליה ישירות.", fail: null },
      { box: "llm", role: null, t: "משימה ← api.anthropic.com על 443", b: "עם המפתח שהוזרק בעלייה. זו קריאה ל-API חיצוני, לא ל-AWS, ולכן אין כאן IAM: ההגנה היא שהמפתח לא דולף. אם הקוד היה קורא ל-S3, הוא היה משתמש ב-task role.", fail: "llm" },
      { box: "alb", role: null, t: "התשובה חוזרת (או זורמת) דרך ה-ALB", b: "סטרימינג מחזיק את החיבור פתוח: לכן idle_timeout הוא 120 שניות. השורה answer עם rid ועלות נכתבת ל-CloudWatch.", fail: null },
    ];
    const FAILS = {
      none: "תקין",
      noecr: "אין הרשאה ל-ECR",
      nosecret: "אין הרשאה לסוד",
      health: "ה-ALB בודק /healthz",
      llm: "mockllm/Anthropic למטה",
    };
    host.innerHTML = `<div class="sim l27">
      <p style="margin:0">הדיאגרמה מראה את מה שה-Terraform של המעבדה יוצר. <b>צעדים 1 עד 4</b> קורים כשמשימה עולה, לפני שמשתמש שולח משהו. <b>צעדים 5 עד 8</b> הם בקשה של משתמש. התגית ליד כל צעד אומרת איזה IAM role מאשר אותו: <span class="l27-role exec">execution role</span> של הסוכן של ECS, או <span class="l27-role task">task role</span> של הקוד שלך (במעבדה הוא ריק). בחר תקלה כדי לראות איפה היא נתקעת.</p>
      <div class="seg" role="group" aria-label="fault">${Object.entries(FAILS).map(([k, t], n) => `<button data-f="${k}" aria-pressed="${n === 0}">${t}</button>`).join("")}</div>
      <div class="l27-arch">
        <div class="l27-row"><div class="l27-box" data-b="user">User<small>your IP only</small></div></div>
        <div class="l27-zone"><b>AWS account · default VPC · 2 AZs</b>
          <div class="l27-row"><div class="l27-box" data-b="alb">ALB :80<small>SG: allowed_cidr</small></div></div>
          <div class="l27-zone"><b>Fargate task (public subnet) · SG: from ALB only</b>
            <div class="l27-row"><div class="l27-box" data-b="task">api container<small>uid 10001 · read-only fs</small></div></div>
          </div>
          <div class="l27-row"><div class="l27-box" data-b="ecr">ECR<small>image</small></div><div class="l27-box" data-b="sm">Secrets Manager<small>API key</small></div><div class="l27-box" data-b="cw">CloudWatch Logs<small>JSON lines</small></div></div>
        </div>
        <div class="l27-row"><div class="l27-box" data-b="llm">api.anthropic.com<small>HTTPS 443</small></div></div>
      </div>
      <div class="l27-steps" id="rp-steps"></div>
      <div class="cap"><b id="rp-t"></b><div class="muted" id="rp-b"></div></div>
      <div class="row"><button class="btn small primary" id="rp-play">נגן</button><button class="btn small" id="rp-prev">→</button><button class="btn small" id="rp-next">←</button><span class="spacer"></span><span class="counter" id="rp-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, fault = "none", timer = null, playing = false;
    const failAt = () => STEPS.findIndex((s) => s.fail === fault);
    function msg(k) {
      if (fault === "noecr" && k === failAt()) return ["המשימה לא עולה", "ECS מנסה ונכשל: CannotPullContainerError ... AccessDenied. ב-ECS תראה את המשימה ב-STOPPED עם הסיבה, וה-circuit breaker יחזיר את ה-deployment הקודם. אף בקשה לא מגיעה לקוד שלך."];
      if (fault === "nosecret" && k === failAt()) return ["המשימה לא עולה", "ResourceInitializationError: unable to pull secrets ... AccessDeniedException. אותה תקלה מופיעה גם כשלסוד עדיין אין ערך: לכן בתרגיל 8 שמים ערך לפני שהשירות נוצר. הקוד שלך לא רץ בכלל."];
      if (fault === "health" && k === failAt()) return ["נראה תקין, וזו הבעיה", "/healthz מחזיר 200 כל עוד התהליך חי. משימה שלא יכולה לענות (למשל, במצב mock כש-mockllm לא עונה) תמשיך לקבל בקשות, כי מבחינת ה-ALB היא בריאה. בחר גם את התקלה הבאה כדי לראות את התוצאה."];
      if (fault === "llm" && k === failAt()) return ["502 למשתמש", "llmkit מנסה שוב לפי ה-retry policy ונכשל, והשירות מחזיר 502 עם request_id. מול mockllm, בדיקת /readyz (הנכונה) הייתה מסמנת את המשימה כלא מוכנה, וב-ECS גם מחליפה אותה. מול Anthropic, גם /readyz לא היה עוזר: בכוונה הוא לא פונה לספק, כי אחרת ECS היה מחליף את כל המשימות בלולאה. יש לך תקלה אמיתית אצל הספק, וזה הזמן ל-fallback (נושא 19)."];
      return null;
    }
    function draw() {
      const fa = failAt(), stop = fa >= 0 && fault !== "health" ? fa : STEPS.length - 1;
      g("rp-steps").innerHTML = STEPS.map((s, k) => {
        const cls = k === i ? (fa === k && fault !== "health" ? "err" : "on") : k < i ? "done" : "";
        const role = s.role === "exec" ? `<span class="l27-role exec">execution role</span>` : s.box === "llm" ? `<span class="l27-role">no IAM: the API key</span>` : `<span class="l27-role">no role</span>`;
        return `<div class="l27-step ${cls}"><b>${k + 1}</b><span>${esc(s.t)} ${role}</span></div>`;
      }).join("");
      host.querySelectorAll(".l27-box").forEach((b) => {
        b.classList.remove("on", "err", "ok");
        const s = STEPS[i];
        if (b.dataset.b === s.box) b.classList.add(fa === i && fault !== "health" ? "err" : "on");
        if (i >= 4 && b.dataset.b === "user") b.classList.add("on");
      });
      const m = msg(i);
      g("rp-t").textContent = m ? m[0] : STEPS[i].t;
      g("rp-b").textContent = m ? m[1] : STEPS[i].b;
      g("rp-c").textContent = `צעד ${i + 1}/${STEPS.length}` + (fa >= 0 && fault !== "health" && i >= fa ? " · נעצר" : "");
      g("rp-next").disabled = i >= stop;
    }
    const step = (d) => {
      const fa = failAt(), stop = fa >= 0 && fault !== "health" ? fa : STEPS.length - 1;
      i = Math.max(0, Math.min(stop, i + d)); draw();
    };
    const tick = () => {
      clearTimeout(timer); if (!playing) return;
      timer = setTimeout(() => {
        const fa = failAt(), stop = fa >= 0 && fault !== "health" ? fa : STEPS.length - 1;
        if (i >= stop) { setP(false); return; }
        step(1); tick();
      }, 2600);
    };
    const setP = (p) => { playing = p; g("rp-play").textContent = p ? "השהה" : "נגן"; tick(); };
    host.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
      fault = b.dataset.f; i = 0;
      host.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      draw(); setP(true);
    }));
    g("rp-play").addEventListener("click", () => { const fa = failAt(); if (i >= (fa >= 0 && fault !== "health" ? fa : STEPS.length - 1)) i = 0; setP(!playing); draw(); });
    g("rp-next").addEventListener("click", () => { setP(false); step(1); });
    g("rp-prev").addEventListener("click", () => { setP(false); step(-1); });
    draw();
    return () => clearTimeout(timer);
  };

  /* ================= sim: interactive Dockerfile linter ================= */
  window.AIDS["l27lint"] = function (host) {
    style();
    const st = { base: "full", multi: false, lock: false, user: false, hc: false, exec: false, secret: "none", ignore: "none", pipcache: false };
    const PRESETS = {
      first: { base: "full", multi: false, lock: false, user: false, hc: false, exec: false, secret: "none", ignore: "none", pipcache: false },
      lab: { base: "pinned", multi: true, lock: true, user: true, hc: true, exec: true, secret: "none", ignore: "allow", pipcache: true },
    };
    const OPTS = [
      ["base", "Base image", [["full", "python:3.12"], ["latest", "python:latest"], ["slim", "python:3.12-slim"], ["pinned", "3.12.16-slim-trixie"], ["digest", "...@sha256"]]],
      ["multi", "Multi-stage", [[false, "שלב אחד"], [true, "builder + runtime"]]],
      ["lock", "תלויות", [[false, "pip install fastapi ..."], [true, "uv sync --locked"]]],
      ["user", "משתמש", [[false, "root (ברירת מחדל)"], [true, "USER app"]]],
      ["hc", "HEALTHCHECK", [[false, "אין"], [true, "/healthz"]]],
      ["exec", "CMD", [[false, "shell form"], [true, "exec form [\"...\"]"]]],
      ["secret", "סוד", [["none", "אין"], ["env", "ENV עם המפתח"], ["arg", "ARG + --build-arg"], ["copyrm", "COPY .env ואז rm"]]],
      ["ignore", ".dockerignore", [["none", "אין"], ["basic", ".env, .venv, .git"], ["allow", "allowlist, **/.env בסוף"], ["allowbad", "allowlist, **/.env לפני !"]]],
    ];
    host.innerHTML = `<div class="sim l27">
      <p style="margin:0"><b>מה רואים:</b> למעלה בוחרים איך ה-Dockerfile נכתב. משמאל (בצד האנגלי) ה-Dockerfile שנוצר מהבחירות, ושורות עם בעיה מסומנות באדום. מתחת: הממצאים של אותם כללים שבבודק של המעבדה (<code>checks.py</code>), לפי חומרה: <b>error</b> שובר את הבנייה ב-CI, <b>warning</b> כדאי לתקן, <b>info</b> המלצה. בסוף: הערכה של גודל ה-image ושל ה-build context. הגדלים הם הערכות לשיעור, לא מדידה.</p>
      <div class="row"><button class="btn small" data-p="first">Dockerfile ראשון</button><button class="btn small" data-p="lab">ה-Dockerfile של המעבדה</button></div>
      <div class="l27-opts">${OPTS.map(([k, label, vals]) => `<div class="l27-opt"><span>${label}</span><div class="seg" data-k="${k}">${vals.map(([v, t]) => `<button data-v="${String(v)}">${esc(t)}</button>`).join("")}</div></div>`).join("")}
        <label style="font-size:.86rem"><input type="checkbox" id="dl-pc"> pip/uv בלי cache בשכבה (--no-cache-dir או cache mount)</label></div>
      <div class="l27-grid">
        <div><div class="eyebrow">Generated Dockerfile</div><div class="l27-df" id="dl-df"></div></div>
        <div><div class="eyebrow">Findings</div><div class="l27-find" id="dl-f"></div></div>
      </div>
      <div><div class="eyebrow">Estimated image size</div><div class="stackbar" id="dl-bar"></div><div class="legend" id="dl-leg" style="margin-top:6px"></div><div class="stats" id="dl-stats" style="margin-top:6px"></div></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    function build() {
      const L = [], bad = {};
      const baseRef = { full: "python:3.12", latest: "python:latest", slim: "python:3.12-slim", pinned: "python:3.12.16-slim-trixie", digest: "python:3.12.16-slim-trixie@sha256:4f1c..." }[st.base];
      const runBase = st.base === "full" || st.base === "latest" ? baseRef : baseRef;
      const add = (t, key) => { L.push(t); if (key) bad[L.length - 1] = key; return L.length; };
      if (st.multi) {
        add(`FROM ${baseRef} AS builder`, "base");
        if (st.lock) { add("COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/"); add("RUN --mount=type=cache,target=/root/.cache/uv \\"); add("    --mount=type=bind,source=uv.lock,target=uv.lock ... \\"); add("    uv sync --locked --no-install-project", st.pipcache ? null : "lean"); }
        else add(`RUN pip install ${st.pipcache ? "--no-cache-dir " : ""}--prefix=/install fastapi uvicorn httpx`, st.pipcache ? null : "lean");
        add("");
        add(`FROM ${runBase}`, "base");
        if (st.user) add("RUN useradd --system --uid 10001 app");
        add(st.lock ? "COPY --from=builder /opt/venv /opt/venv" : "COPY --from=builder /install /usr/local");
      } else {
        add(`FROM ${baseRef}`, "base");
        if (st.user) add("RUN useradd --system --uid 10001 app");
        add("WORKDIR /app");
        if (st.lock) add("COPY uv.lock pyproject.toml ./"), add(`RUN pip install uv && uv sync --locked`, st.pipcache ? null : "lean");
        else add(`RUN pip install ${st.pipcache ? "--no-cache-dir " : ""}fastapi uvicorn httpx`, st.pipcache ? null : "lean");
      }
      if (st.secret === "arg") add("ARG ANTHROPIC_API_KEY", "secret"), add('RUN test -n "$ANTHROPIC_API_KEY"');
      if (st.secret === "env") add("ENV ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxx", "secret");
      if (st.secret === "copyrm") add("COPY .env /app/.env", "secret"), add("RUN rm /app/.env");
      add("COPY . /app", st.ignore === "none" || st.ignore === "allowbad" ? "ignore" : null);
      if (st.user) add("USER app");
      if (st.hc) add('HEALTHCHECK CMD ["python", "-c", "...urlopen(\'http://127.0.0.1:8000/healthz\')"]');
      add(st.exec ? 'CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]' : "CMD uvicorn service.main:app --host 0.0.0.0 --port 8000", st.exec ? null : "exec");
      if (!st.user) bad[L.length - 1] = bad[L.length - 1] || "user";
      return { L, bad };
    }
    function findings() {
      const F = [];
      if (st.base === "full") F.push(["info", "base_image_pinned", "<code>python:3.12</code> מוצמד לפי tag בלבד, וזה גם ה-image המלא: כגיגה-בייט של קומפיילרים וכלים."]);
      if (st.base === "latest") F.push(["error", "base_image_pinned", "<code>:latest</code> זז בכל פעם: שתי בניות של אותו קובץ יקבלו Python שונה."]);
      if (st.base === "slim") F.push(["info", "base_image_pinned", "<code>3.12-slim</code> הוא tag מתגלגל: הוא יזוז ל-patch הבא. עדיף גרסה מלאה, ו-digest לשחזור מלא."]);
      if (st.base === "pinned") F.push(["info", "base_image_pinned", "מוצמד לגרסה מלאה. ל-bit-for-bit צריך גם <code>@sha256</code>."]);
      if (!st.user) F.push(["error", "runs_as_non_root", "השלב הסופי רץ כ-root: אין <code>USER</code>."]);
      if (st.secret === "env") F.push(["error", "no_secrets_in_build", "<code>ENV ANTHROPIC_API_KEY</code> מכיל ערך שנראה כמו מפתח: הוא ב-config של ה-image, וכל <code>docker inspect</code> מראה אותו."]);
      if (st.secret === "arg") F.push(["error", "no_secrets_in_build", "<code>ARG ANTHROPIC_API_KEY</code> נראה כמו סוד: build args נרשמים ב-history. השתמש ב-<code>RUN --mount=type=secret</code>."]);
      if (st.secret === "copyrm") F.push(["warning", "(no rule!)", "הבודק לא רואה את זה: הוא לא יודע מה יש בקובץ שמועתק. השכבה של <code>COPY .env</code> נשארת ב-image גם אחרי <code>rm</code>. רק allowlist ב-ignore היה מונע את זה, ו-<code>layer_peek.py</code> מוצא את זה אחרי הבנייה."]);
      if (!st.hc) F.push(["warning", "healthcheck", "אין <code>HEALTHCHECK</code>: compose לא יכול לחכות ל-healthy. ב-ECS צריך אותו גם ב-task definition."]);
      if (!st.exec) F.push(["warning", "exec_form", "<code>CMD</code> בצורת shell: <code>/bin/sh</code> הוא PID 1 ולא מעביר SIGTERM ל-uvicorn."]);
      if (!st.pipcache) F.push(["warning", "lean_layers", "התקנה בלי <code>--no-cache-dir</code> או cache mount: ה-cache של ה-wheels נשאר בשכבה."]);
      if (st.ignore === "none") F.push(["error", "dockerignore", "<code>COPY . /app</code> בלי <code>.dockerignore</code>: <code>.env</code>, <code>.git</code> ו-<code>.venv</code> נכנסים ל-context, ומשם ל-image."]);
      if (st.ignore === "basic") F.push(["error", "dockerignore", "<code>.env</code> בשורש מוחרג, אבל <code>.env</code> בתיקיות משנה לא: צריך <code>**/.env</code>."]);
      if (st.ignore === "allowbad") F.push(["error", "dockerignore", "<code>.env</code> בתוך <code>llmkit/</code> לא מוחרג: <code>!llmkit/</code> בא אחרי <code>**/.env</code>, והשורה האחרונה שמתאימה מנצחת."]);
      if (!st.lock) F.push(["info", "(review)", "תלויות בלי lock: כל בנייה מקבלת את מה שעדכני באותו יום. אין לזה כלל בבודק, אבל זה הבדל אמיתי בשחזוריות."]);
      return F;
    }
    function sizes() {
      const parts = [];
      const fullBase = st.base === "full" || st.base === "latest";
      parts.push(["base OS + Python", fullBase ? 1020 : 125]);
      parts.push(["dependencies", 45]);
      if (!st.pipcache) parts.push(["pip/uv cache", 25]);
      if (!st.multi && st.lock) parts.push(["uv + build tools", 40]);
      const ctx = st.ignore === "none" ? 650 : st.ignore === "basic" ? 6 : 0.24;
      parts.push(["copied context", st.ignore === "none" ? 2 : st.ignore === "basic" ? 1.5 : 0.24]);
      return { parts, ctx };
    }
    function draw() {
      host.querySelectorAll(".seg[data-k]").forEach((seg) => seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === String(st[seg.dataset.k])))));
      g("dl-pc").checked = st.pipcache;
      const { L, bad } = build();
      g("dl-df").innerHTML = L.map((t, k) => `<div class="${bad[k] ? "bad" : ""}">${esc(t || " ")}</div>`).join("");
      const F = findings(), order = { error: 0, warning: 1, info: 2 };
      F.sort((a, b) => order[a[0]] - order[b[0]]);
      const ne = F.filter((f) => f[0] === "error").length, nw = F.filter((f) => f[0] === "warning").length;
      g("dl-f").innerHTML = `<div class="stats"><span>errors: <b>${ne}</b></span><span>warnings: <b>${nw}</b></span><span>${ne ? "CI: נכשל" : "CI: עובר"}</span></div>` +
        F.map(([s, r, m]) => `<div class="l27-f ${s}"><b>${s.toUpperCase()}</b> <code>${esc(r)}</code> ${m}</div>`).join("");
      const { parts, ctx } = sizes(), total = parts.reduce((a, p) => a + p[1], 0);
      g("dl-bar").innerHTML = parts.map((p, k) => `<i style="width:${(p[1] / total * 100).toFixed(1)}%;background:${C[k]}"></i>`).join("");
      g("dl-leg").innerHTML = parts.map((p, k) => `<span><i style="background:${C[k]}"></i>${esc(p[0])} ~${p[1] >= 10 ? Math.round(p[1]) : p[1]} MB</span>`).join("");
      g("dl-stats").innerHTML = `<span>image: <b>~${Math.round(total)} MB</b></span><span>build context: <b>~${ctx >= 10 ? Math.round(ctx) + " MB" : ctx >= 1 ? ctx + " MB" : Math.round(ctx * 1000) + " KB"}</b></span>`;
    }
    host.querySelectorAll(".seg[data-k]").forEach((seg) => seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      const k = seg.dataset.k, v = b.dataset.v;
      st[k] = v === "true" ? true : v === "false" ? false : v; draw();
    })));
    g("dl-pc").addEventListener("change", (e) => { st.pipcache = e.target.checked; draw(); });
    host.querySelectorAll("[data-p]").forEach((b) => b.addEventListener("click", () => { Object.assign(st, PRESETS[b.dataset.p]); draw(); }));
    draw();
  };

  /* ================= sim: monthly cost estimator ================= */
  window.AIDS["l27cost"] = function (host) {
    style();
    const P = { x86: [0.0404784, 0.004446], arm: [0.03237984, 0.00356004], alb: 0.0225, lcu: 0.008, ip: 0.005, nat: 0.045, natgb: 0.045, vpce: 0.01, secret: 0.40, logs: 0.53, ecr: 0.10, alarm: 0.10,
      lreq: 0.20 / 1e6, lgbs: 0.0000166667 };
    const SIZES = [["0.25 vCPU / 0.5 GB", 0.25, 0.5], ["0.5 vCPU / 1 GB", 0.5, 1], ["1 vCPU / 2 GB", 1, 2]];
    const st = { size: 0, arch: "x86", tasks: 1, net: "public", hours: 730, lambdaReq: 30000, lambdaSec: 4 };
    host.innerHTML = `<div class="sim l27">
      <p style="margin:0"><b>מה רואים:</b> החשבון החודשי של התשתית מהמעבדה, לפי מחירי us-east-1 (נובמבר 2026), בלי free tier. כל שורה היא רכיב שמחויב בנפרד, עם הסבר למה הוא קיים. הפס הצבעוני מראה את החלק של כל רכיב בחשבון. הטוקנים של המודל <b>לא</b> כלולים: עליהם משלמים ל-Anthropic בנפרד. בתחתית: אותו עומס על Lambda, להשוואה.</p>
      <div class="l27-opts">
        <div class="l27-opt"><span>גודל משימה</span><div class="seg" data-k="size">${SIZES.map((s, k) => `<button data-v="${k}">${s[0]}</button>`).join("")}</div></div>
        <div class="l27-opt"><span>ארכיטקטורה</span><div class="seg" data-k="arch"><button data-v="x86">X86_64</button><button data-v="arm">ARM64 (Graviton)</button></div></div>
        <div class="l27-opt"><span>רשת</span><div class="seg" data-k="net"><button data-v="public">subnet ציבורי + IP למשימה</button><button data-v="nat">פרטי + NAT gateway</button><button data-v="vpce">פרטי + 4 VPC endpoints</button></div></div>
        <div class="l27-opt"><span>שעות שהסטאק קיים בחודש</span><div class="seg" data-k="hours"><button data-v="730">כל החודש (730)</button><button data-v="220">ימי עבודה, 10 שעות (220)</button><button data-v="3">סשן מעבדה (3)</button></div></div>
        <div class="knob"><div class="knob-head"><span>משימות בממוצע (autoscaling)</span><b id="cc-tv"></b></div><input type="range" id="cc-t" min="1" max="6" step="0.5"></div>
      </div>
      <div class="stackbar" id="cc-bar"></div>
      <div class="l27-items" id="cc-items"></div>
      <div class="row"><span>סך הכול:</span><span class="l27-big" id="cc-total"></span><span class="spacer"></span><span class="muted" id="cc-day"></span></div>
      <div class="callout" id="cc-note"></div>
      <div class="card" style="padding:12px">
        <h4 style="margin:0">להשוואה: Lambda עם Function URL</h4>
        <div class="knob"><div class="knob-head"><span>בקשות בחודש</span><b id="cc-lrv"></b></div><input type="range" id="cc-lr" min="0" max="20" step="1"></div>
        <div class="knob"><div class="knob-head"><span>שניות לבקשה (כולל ההמתנה למודל)</span><b id="cc-lsv"></b></div><input type="range" id="cc-ls" min="1" max="20" step="1"></div>
        <div class="stats" id="cc-lam"></div>
      </div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    const REQ = [0, 1000, 3000, 10000, 30000, 60000, 100000, 200000, 300000, 500000, 750000, 1e6, 1.5e6, 2e6, 3e6, 4e6, 5e6, 7e6, 1e7, 1.5e7, 2e7];
    g("cc-lr").value = String(REQ.indexOf(st.lambdaReq)); g("cc-ls").value = String(st.lambdaSec); g("cc-t").value = String(st.tasks);
    const fmt = (v) => (v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2));
    function compute() {
      const [, vcpu, mem] = SIZES[st.size], [pc, pm] = P[st.arch], h = st.hours, sc = h / 730, t = st.tasks;
      const items = [
        ["ALB", P.alb * h, "קיים כל שעה, גם בלי בקשות"],
        ["Public IPv4", ((st.net === "public" ? t : 0) + 2) * P.ip * h, (st.net === "public" ? `${t} למשימות + ` : "") + "2 ל-ALB (אחת לכל AZ), 0.005$ לשעה כל אחת"],
        ["Fargate CPU", t * vcpu * pc * h, `${t} × ${vcpu} vCPU × ${h} שעות`],
        ["Fargate memory", t * mem * pm * h, `${t} × ${mem} GB × ${h} שעות`],
        ["NAT gateway", st.net === "nat" ? P.nat * h + 5 * sc * P.natgb : 0, "0.045$ לשעה + 0.045$ ל-GB (כאן 5GB לחודש)"],
        ["VPC endpoints", st.net === "vpce" ? 4 * 2 * P.vpce * h : 0, "ecr.api, ecr.dkr, logs, secretsmanager, בשני AZs, 0.01$ לשעה כל אחד"],
        ["ALB LCU", 0.05 * P.lcu * h, "יחידות קיבולת: חיבורים, בייטים, כללים"],
        ["Secrets Manager", P.secret * sc, "0.40$ לסוד לחודש"],
        ["Alarms", 2 * P.alarm * sc, "autoscaling יוצר שני alarms"],
        ["Logs + ECR", (0.2 * P.logs + 0.4 * P.ecr) * sc, "0.2GB לוגים, 0.4GB images"],
      ].filter((x) => x[1] > 0.0005);
      return items;
    }
    function draw() {
      host.querySelectorAll(".seg[data-k]").forEach((seg) => seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === String(st[seg.dataset.k])))));
      g("cc-tv").textContent = st.tasks;
      const items = compute(), total = items.reduce((a, x) => a + x[1], 0);
      g("cc-bar").innerHTML = items.map((x, k) => `<i style="width:${(x[1] / total * 100).toFixed(1)}%;background:${C[k]}" title="${esc(x[0])}"></i>`).join("");
      g("cc-items").innerHTML = items.map((x, k) => `<div class="l27-it"><span><i style="background:${C[k]}"></i>${esc(x[0])} <span class="muted">${(x[1] / total * 100).toFixed(0)}%</span></span><span class="v">$${fmt(x[1])}</span><small>${esc(x[2])}</small></div>`).join("");
      g("cc-total").textContent = `$${fmt(total)}`;
      g("cc-day").textContent = `ל-${st.hours} שעות · $${(total / st.hours).toFixed(3)} לשעה`;
      const net = items.filter((x) => ["ALB", "Public IPv4", "NAT gateway", "VPC endpoints", "ALB LCU"].includes(x[0])).reduce((a, x) => a + x[1], 0);
      const app = items.filter((x) => x[0].startsWith("Fargate")).reduce((a, x) => a + x[1], 0);
      g("cc-note").innerHTML = `הרשת סביב האפליקציה (ALB, כתובות, NAT או endpoints) היא <b>${(net / total * 100).toFixed(0)}%</b> מהחשבון, והמשימות עצמן <b>${(app / total * 100).toFixed(0)}%</b>. ${st.net === "vpce" ? "ארבעה endpoints בשני AZs יקרים יותר מ-NAT אחד: endpoints משתלמים כשיש הרבה תעבורה (NAT גובה לפי GB), לא בשירות קטן." : st.net === "nat" ? "NAT gateway הוא עלות קבועה של כ-33$ לחודש עוד לפני תעבורה." : "IP ציבורי למשימה, עם security group שמקבל רק מה-ALB, הוא הפשרה הזולה של המעבדה."}`;
      const req = REQ[+g("cc-lr").value], sec = +g("cc-ls").value;
      g("cc-lrv").textContent = req.toLocaleString("en-US"); g("cc-lsv").textContent = sec + "s";
      const gbs = req * sec * 0.5, lam = req * P.lreq + gbs * P.lgbs;
      const fixed730 = (() => { const save = st.hours; st.hours = 730; const it = compute(); st.hours = save; return it.reduce((a, x) => a + x[1], 0); })();
      g("cc-lam").innerHTML = `<span>GB-seconds (512MB): <b>${Math.round(gbs).toLocaleString("en-US")}</b></span><span>Lambda: <b>$${fmt(lam)}</b> לחודש</span><span>Fargate בתצורה למעלה, חודש מלא: <b>$${fmt(fixed730)}</b></span><span>${lam < fixed730 ? "Lambda זול יותר כאן" : "Fargate זול יותר כאן"}</span>`;
    }
    host.querySelectorAll(".seg[data-k]").forEach((seg) => seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      const k = seg.dataset.k, v = b.dataset.v;
      st[k] = k === "size" || k === "hours" ? +v : v; draw();
    })));
    g("cc-t").addEventListener("input", (e) => { st.tasks = +e.target.value; draw(); });
    g("cc-lr").addEventListener("input", draw);
    g("cc-ls").addEventListener("input", draw);
    draw();
  };
})();
