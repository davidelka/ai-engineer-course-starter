// Lesson 7 aids: verification-loop animation (generate -> verify -> decide -> feedback, with evidence
// ledger and budget meter), weak-vs-strong oracle simulator, convergence explorer, stop-policy playground.
// Uses the hub helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  if (document.getElementById("l07-style")) return;
  const st = document.createElement("style");
  st.id = "l07-style";
  st.textContent = `
.l07 { display: grid; gap: 12px; direction: rtl; min-width: 0; }
.l07 p { margin: 0; }
.l07-task { font-size: .84rem; color: var(--muted); border: 1px dashed var(--line); border-radius: 10px; padding: 6px 10px; line-height: 1.6; }
.l07-stations { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.l07-stations span { border: 1px solid var(--line); border-radius: 10px; padding: 6px 4px; text-align: center; font-size: .8rem; color: var(--muted); background: var(--surface); line-height: 1.3; }
.l07-stations span b { display: block; font-family: var(--mono); font-size: .72rem; }
.l07-stations span.on { border-color: var(--accent); background: var(--accent-soft); color: var(--ink); font-weight: 700; }
.l07-vs { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 6px; direction: ltr; }
.l07-v { text-align: left; border: 1px solid var(--line); border-radius: 8px; padding: 5px 8px; font-family: var(--mono); font-size: .74rem; display: grid; gap: 1px; background: var(--surface); min-width: 0; }
.l07-v .n { color: var(--muted); }
.l07-v .r { font-weight: 600; overflow-wrap: anywhere; }
.l07-v.ok { border-color: var(--good); background: var(--good-soft); }
.l07-v.no { border-color: var(--bad); background: var(--bad-soft); }
.l07-v.wait .r { color: var(--muted); }
.l07-v.off { opacity: .4; }
.l07-code { font-family: var(--mono); font-size: .74rem; line-height: 1.5; direction: ltr; text-align: left; background: var(--code-bg); border-radius: 8px; padding: 8px 10px; white-space: pre-wrap; overflow-wrap: anywhere; min-height: 5.5em; }
.l07-code .hl { background: var(--signal-soft); box-shadow: inset 2px 0 0 var(--signal); }
.l07-fb { font-family: var(--mono); font-size: .72rem; line-height: 1.5; direction: ltr; text-align: left; border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; white-space: pre-wrap; overflow-wrap: anywhere; background: var(--surface); }
.l07-ledger { text-align: left; display: grid; gap: 3px; direction: ltr; font-family: var(--mono); font-size: .72rem; }
.l07-ledger div { padding: 3px 8px; border-radius: 6px; background: var(--code-bg); overflow-wrap: anywhere; }
.l07-ledger div.new { animation: pop .4s ease; box-shadow: inset 0 0 0 1px var(--signal); }
.l07-ledger div.good { background: var(--good-soft); }
.l07-ledger div.bad { background: var(--bad-soft); }
.l07-meter { display: grid; gap: 4px; }
.l07-meter .m { display: grid; grid-template-columns: 4.2rem minmax(0, 1fr) 7.6rem; gap: 6px; align-items: center; font-size: .78rem; }
.l07-meter .m .tr { height: 10px; background: var(--code-bg); border-radius: 5px; overflow: hidden; direction: ltr; }
.l07-meter .m .tr i { display: block; height: 100%; background: var(--accent); transition: width .4s; }
.l07-meter .m .v { font-family: var(--mono); font-size: .72rem; direction: ltr; text-align: left; }
.l07-cap { min-height: 76px; display: grid; gap: 4px; }
.l07-cap b { font-size: .95rem; }
.l07-cap div { font-size: .9rem; color: var(--muted); line-height: 1.65; }
.l07-strats { display: grid; gap: 6px; }
.l07-strat { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 4px; background: var(--surface); }
.l07-strat .hd { display: flex; flex-wrap: wrap; gap: 6px; align-items: baseline; justify-content: space-between; }
.l07-strat .hd b { font-size: .9rem; }
.l07-strat .d { font-size: .8rem; color: var(--muted); line-height: 1.5; }
.l07-strat .chs { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; }
.l07-strat .chs span { font-family: var(--mono); font-size: .7rem; padding: 1px 6px; border-radius: 6px; border: 1px solid var(--line); }
.l07-strat .chs span.ok { color: var(--good); border-color: var(--good); }
.l07-strat .chs span.no { color: var(--bad); border-color: var(--bad); }
.l07-verdict { font-size: .74rem; padding: 1px 8px; border-radius: 999px; white-space: nowrap; }
.l07-verdict.rej { background: var(--line); color: var(--muted); }
.l07-verdict.ok { background: var(--good-soft); color: var(--good); }
.l07-verdict.fp { background: var(--bad-soft); color: var(--bad); font-weight: 700; }
.l07-strat.fp { border-color: var(--bad); }
.l07-checks { display: grid; gap: 4px; font-size: .86rem; }
.l07-checks label { display: flex; gap: 6px; align-items: flex-start; line-height: 1.45; }
.l07-checks input { margin-top: 4px; }
.l07-split { height: 22px; display: flex; direction: ltr; border-radius: 6px; overflow: hidden; background: var(--code-bg); }
.l07-split i { display: block; height: 100%; transition: width .3s; }
.l07-split .t { background: var(--good); } .l07-split .f { background: var(--bad); } .l07-split .u { background: var(--line); }
.l07 .legend i.t { background: var(--good); } .l07 .legend i.f { background: var(--bad); } .l07 .legend i.u { background: var(--line); }
.l07-chart { width: 100%; height: auto; display: block; direction: ltr; }
.l07-chart text { font-family: var(--mono); font-size: 11px; fill: var(--muted); }
.l07-chart .ax { stroke: var(--line); stroke-width: 1; }
.l07-chart .grid { stroke: var(--line); stroke-width: 1; stroke-dasharray: 2 4; }
.l07-chart .budget { stroke: var(--ink); stroke-width: 1.5; stroke-dasharray: 5 4; }
.l07-chart polyline { fill: none; stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
.l07-chart .c0 { stroke: var(--good); } .l07-chart .c1 { stroke: var(--accent); } .l07-chart .c2 { stroke: var(--signal); }
.l07-chart .dim { opacity: .35; }
.l07 .legend i.c0 { background: var(--good); } .l07 .legend i.c1 { background: var(--accent); } .l07 .legend i.c2 { background: var(--signal); }
.l07-rows { display: grid; gap: 6px; }
.l07-row { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 3px; font-size: .84rem; }
.l07-row.sel { border-color: var(--accent); background: var(--accent-soft); }
.l07-row .k { font-family: var(--mono); font-size: .78rem; direction: ltr; text-align: right; unicode-bidi: plaintext; }
.l07-its { display: grid; grid-template-columns: repeat(auto-fill, minmax(62px, 1fr)); gap: 6px; direction: ltr; }
.l07-it { border: 1px solid var(--line); border-radius: 8px; padding: 4px; display: grid; gap: 2px; font-family: var(--mono); font-size: .68rem; text-align: center; background: var(--surface); }
.l07-it .bar { height: 46px; background: var(--code-bg); border-radius: 4px; position: relative; overflow: hidden; }
.l07-it .bar i { position: absolute; inset-inline: 0; bottom: 0; background: var(--accent); }
.l07-it.solved .bar i { background: var(--good); }
.l07-it.tam .bar i { background: var(--bad); }
.l07-it.after { opacity: .3; border-style: dashed; }
.l07-it.stop { border: 2px solid var(--signal); }
.l07-it .hs { color: var(--muted); }
.l07-why { border-inline-start: 3px solid var(--signal); background: var(--signal-soft); border-radius: 0 10px 10px 0; padding: 8px 12px; font-size: .9rem; line-height: 1.65; }
`;
  document.head.appendChild(st);
})();

/* ================================================================ intro: the loop */
window.AIDS["l07loop"] = function (host) {
  const BUDGET = { it: 6, tok: 12000, usd: 0.005 };
  const V = ["guard", "lint", "visible_tests", "hidden_tests"];
  const ITS = [
    { code: "def vacation_days(years_of_service, scope=1.0):\n    days = min(24, 14 + int(years_of_service))\n    return round(days * scope)",
      what: "המודל קרא את המפרט ואת הבדיקות, ותיקן את הנוסחה של הוותק ואת התקרה של 24 ימים. את העיגול לחצאי ימים ואת הבדיקה של קלט שלילי הוא עוד לא טיפל.",
      v: [[1, "intact"], [1, "clean"], [0, "6/8 passed"], [0, "2/8 passed"]], score: 0.75, tok: 1100, usd: 0.00019,
      dec: "continue", decWhy: "לא נפתר, אין רמאות, והתקציב עוד לא נגמר. זו האיטרציה הראשונה, אז אין עדיין ממה לזהות תקיעה.",
      fb: "## Visible tests\n2 failed, 6 passed\n- test_visible.py::test_part_time_rounds_to_half_days\n    assert vacation_days(0, scope=0.75) == 10.5\n    assert 10 == 10.5\n- test_visible.py::test_negative_years_rejected\n    Failed: DID NOT RAISE ValueError\n## Hidden checks (you cannot see this file)\n6 failed, 2 passed ..." },
    { code: "def vacation_days(years_of_service, scope=1.0):\n    if years_of_service < 0:\n        raise ValueError(\"negative\")\n    days = min(24, 14 + int(years_of_service))\n    return round(days * scop * 2) / 2",
      hl: 4, what: "המודל הוסיף בדיקה של קלט שלילי ועיגול לחצאי ימים, אבל כתב scop במקום scope. שגיאה כזו לא מופיעה בזמן כתיבה, רק כשהקוד רץ.",
      v: [[1, "intact"], [0, "F821 'scop'"], [0, "1/8 passed"], [0, "0/8 passed"]], score: 0.28, tok: 1500, usd: 0.00026, reg: true,
      dec: "continue", decWhy: "הציון ירד מ-0.75 ל-0.28. ה-regression guard שם לב: 5 בדיקות שעברו באיטרציה 1 נכשלות עכשיו. הלולאה ממשיכה, אבל האיטרציה הבאה תתחיל מהגרסה הטובה של איטרציה 1, לא מזו.",
      fb: "REGRESSION: your last change broke checks that passed before: test_second_year_adds_one_day, ... The code below is your best version so far; continue from it.\n## Linter (ruff)\nsolution.py:5:28: F821 Undefined name `scop`" },
    { code: "# tests/test_visible.py, as returned by the model:\ndef test_part_time_rounds_to_half_days():\n    assert True  # rounding is covered elsewhere\n\ndef test_negative_years_rejected():\n    assert True",
      hl: 2, what: "הפעם המודל לא תיקן את הקוד. הוא החזיר גרסה חדשה של קובץ הבדיקות, שבה שתי הבדיקות שנכשלו הוחלפו ב-assert True. זה בדיוק סוג הרמאות שמחקרים מדדו אצל מודלים אמיתיים.",
      v: [[0, "2 trivial asserts"], [1, "clean"], [0, "6/8 (pristine)"], [0, "2/8 passed"]], score: 0.5, tok: 1900, usd: 0.00031, tam: true,
      dec: "continue", decWhy: "ה-guard מצא trivial_assert בשתי בדיקות, ולכן האיטרציה מסומנת tampered, ולא נחשבת כהצלחה בשום מקרה. שים לב שהבדיקות הגלויות רצו מעותק נקי, אז גם בלי ה-guard השינוי לא היה עוזר. זו רמאות ראשונה מתוך max_tamper=2, אז ממשיכים, והבדיקות חוזרות למקור.",
      fb: "## Test-integrity guard\nYou changed the tests instead of the code. Test files are read-only: your changes were discarded. Findings:\n- trivial_assert:tests/test_visible.py::test_part_time_rounds_to_half_days\n- trivial_assert:tests/test_visible.py::test_negative_years_rejected\nFix solution.py so the ORIGINAL tests pass." },
    { code: "def vacation_days(years_of_service, scope=1.0):\n    if years_of_service < 0:\n        raise ValueError(\"years_of_service must be >= 0\")\n    if not 0 < scope <= 1:\n        raise ValueError(\"scope must be in (0, 1]\")\n    full = min(24, 14 + math.floor(years_of_service))\n    return round(full * scope * 2) / 2",
      hl: 6, what: "עכשיו המודל תיקן את הקוד עצמו: ולידציה של הקלט, ועיגול לחצי יום עם round. כל הבדיקות הגלויות עוברות.",
      v: [[1, "intact"], [1, "clean"], [1, "8/8 passed"], [0, "6/8 passed"]], score: 0.94, tok: 2100, usd: 0.00033,
      dec: "continue", decWhy: "הבדיקות הגלויות ירוקות, אבל בדיקה נסתרת נכשלה. ה-round של Python מעגל חצאים לזוגי (banker's rounding), ולכן 11.25 יוצא 11.0 ולא 11.5. לולאה שהייתה עוצרת על הבדיקות הגלויות בלבד הייתה מכריזה כאן על הצלחה.",
      fb: "## Hidden checks (you cannot see this file)\n2 failed, 6 passed\n- test_hidden.py::test_quarter_rounds_up\n    AssertionError: vacation_days(1, scope=0.75) = 11.0: 15 * 0.75 = 11.25 must round UP to 11.5" },
    { code: "    ...\n    full = min(24, 14 + math.floor(years_of_service))\n    return math.floor(full * scope * 2 + 0.5) / 2",
      hl: 2, what: "המודל קרא את הדוגמה הנגדית מהבדיקה הנסתרת, והחליף את round בעיגול חצי למעלה.",
      v: [[1, "intact"], [1, "clean"], [1, "8/8 passed"], [1, "8/8 passed"]], score: 1, tok: 2000, usd: 0.00032,
      dec: "solved", decWhy: "כל מאמתי החובה עברו, ואין רמאות באיטרציה הזו. המדיניות עוצרת עם solved. עכשיו רץ ה-audit: הבדיקות הגלויות המקוריות והנסתרות בחדר נקי. 16/16, audit OK.",
      fb: "" },
  ];
  const WEAK = { code: ITS[0].code, what: ITS[0].what, v: [[1, "ran"]], score: 1, tok: 1100, usd: 0.00019, dec: "solved",
    decWhy: "המאמת היחיד הוא \"זה רץ\": המודול נטען, והקריאה vacation_days(3) החזירה מספר בלי לקרוס. מבחינת ה-oracle הזה, המשימה נפתרה כבר באיטרציה הראשונה.",
    fb: "", audit: "audit: visible 6/8, hidden 2/8  ->  FALSE PASS" };
  const PH = [["1", "מחולל"], ["2", "מאמתים"], ["3", "החלטה"], ["4", "משוב"]];
  host.innerHTML = `<div class="l07">
    <p>המחולל (מודל שפה) מתקן את <code>vacation_days</code>. בכל איטרציה יש ארבעה שלבים: הוא מציע קוד, המאמתים בודקים, המדיניות מחליטה, והמשוב חוזר אליו. למטה מצטבר יומן הראיות, ומד התקציב מתמלא.</p>
    <div class="l07-task"><b>המשימה:</b> 14 ימים בשנה הראשונה, ועוד יום על כל שנה שלמה, עד 24. במשרה חלקית: כפול היקף המשרה, מעוגל לחצי יום, ורבע מעוגל למעלה (11.25 → 11.5). קלט שלילי זורק ValueError.</div>
    <div class="l07-stations" id="lp-st">${PH.map((p, i) => `<span data-p="${i}"><b>${p[0]}</b>${p[1]}</span>`).join("")}</div>
    <div><div class="eyebrow" id="lp-ch">Candidate</div><div class="l07-code" id="lp-code"></div></div>
    <div class="l07-vs" id="lp-vs"></div>
    <div class="l07-cap"><b id="lp-t"></b><div id="lp-b"></div></div>
    <div id="lp-fbw" hidden><div class="eyebrow" id="lp-fbh">Feedback sent to the generator</div><div class="l07-fb" id="lp-fb"></div></div>
    <div><div class="eyebrow">Evidence log (one line per iteration)</div><div class="l07-ledger" id="lp-led"></div></div>
    <div class="l07-meter" id="lp-m"></div>
    <div class="row"><button class="btn small primary" id="lp-play">השהה</button><button class="btn small" id="lp-prev">→</button><button class="btn small" id="lp-next">←</button><span class="spacer"></span><span class="counter" id="lp-c"></span></div>
    <label class="row" style="font-size:.88rem"><input type="checkbox" id="lp-weak"> <b>oracle חלש:</b> המאמת היחיד הוא "זה רץ". מה הלולאה הייתה מכריזה?</label>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  let i = 0, ph = 0, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const its = () => (g("lp-weak").checked ? [WEAK] : ITS);
  function draw() {
    const S = its(), s = S[i], weak = g("lp-weak").checked, names = weak ? ["runs"] : V;
    host.querySelectorAll("#lp-st span").forEach((x) => x.classList.toggle("on", +x.dataset.p === ph));
    const lines = s.code.split("\n");
    g("lp-code").innerHTML = lines.map((l, k) => `<div class="${k === s.hl ? "hl" : ""}">${esc(l) || " "}</div>`).join("");
    g("lp-ch").textContent = `Candidate, iteration ${i + 1}` + (s.tam ? " (the model returned a test file)" : "");
    g("lp-vs").innerHTML = names.map((n, k) => {
      const r = s.v[k];
      const cls = ph < 1 ? "wait" : r[0] ? "ok" : "no";
      return `<div class="l07-v ${cls}"><span class="n">${esc(n)}</span><span class="r">${ph < 1 ? "…" : (r[0] ? "✓ " : "✗ ") + esc(r[1])}</span></div>`;
    }).join("");
    const T = [
      [`איטרציה ${i + 1}: המחולל מציע`, s.what],
      [`איטרציה ${i + 1}: המאמתים מייצרים ראיות`, weak ? "רק מאמת אחד: האם הקוד נטען ורץ פעם אחת בלי לקרוס." : `כל מאמת מריץ כלי אמיתי: ה-guard משווה את הבדיקות למקור, ruff בודק שמות לא מוגדרים, ו-pytest מריץ את הבדיקות הגלויות והנסתרות בחדר נקי. ציון האיטרציה הוא הממוצע: ${s.score.toFixed(2)}.`],
      [`איטרציה ${i + 1}: המדיניות מחליטה: ${s.dec}`, s.decWhy],
      [s.dec === "solved" ? "סוף: ה-audit" : `איטרציה ${i + 1}: המשוב חוזר למחולל`,
        s.dec === "solved" ? (weak ? "ה-audit מריץ את הבדיקות האמיתיות על הקוד הסופי: 6 מתוך 8 גלויות ו-2 מתוך 8 נסתרות. הלולאה הכריזה על הצלחה, והקוד שגוי. זה false pass, ובלי audit אף אחד לא היה יודע. כבה את המתג כדי לראות את הלולאה עם המאמתים החזקים."
          : "ה-audit עבר: 16 מתוך 16. שים לב כמה המדד השתנה בדרך: באיטרציה 4 כל הבדיקות הגלויות היו ירוקות, ורק הבדיקה הנסתרת מנעה הכרזה מוקדמת. וגם התקציב: 5 איטרציות, כ-8,600 טוקנים, פחות משליש סנט.")
          : "המשוב נבנה מהראיות: לכל כשל, הבדיקה, השורה, והערך הצפוי מול מה שהתקבל. מהבדיקות הנסתרות רואים את הדוגמה הנגדית, אבל לא את קוד הבדיקה. זה הטקסט שייכנס לפרומפט של האיטרציה הבאה, ולכן גם הטוקנים גדלים."],
    ];
    g("lp-t").textContent = T[ph][0];
    g("lp-b").textContent = T[ph][1];
    const showFb = ph === 3;
    g("lp-fbw").hidden = !showFb;
    g("lp-fbh").textContent = s.dec === "solved" ? "Independent audit of the final code" : "Feedback sent to the generator";
    g("lp-fb").textContent = s.dec === "solved" ? (s.audit || "audit: visible 8/8, hidden 8/8  ->  audit OK") : s.fb;
    const done = S.slice(0, ph >= 2 ? i + 1 : i);
    g("lp-led").innerHTML = done.length ? done.map((x, k) => {
      const fails = names.filter((n, j) => !x.v[j][0]);
      const cls = x.dec === "solved" ? (weak ? "bad" : "good") : x.tam ? "bad" : "";
      return `<div class="${cls}${k === i && ph === 2 ? " new" : ""}">it ${k + 1} · score ${x.score.toFixed(2)}${x.tam ? " · TAMPERED" : ""}${x.reg ? " · REGRESSION" : ""} · ${fails.length ? "fail: " + fails.join(", ") : "all pass"} → ${x.dec}</div>`;
    }).join("") : `<div class="muted">empty: nothing has been verified yet</div>`;
    const spent = S.slice(0, ph >= 0 ? i + 1 : i);
    const it = spent.length, tok = spent.reduce((a, x) => a + x.tok, 0), usd = spent.reduce((a, x) => a + x.usd, 0);
    const bar = (lbl, v, max, txt) => `<div class="m"><span>${lbl}</span><span class="tr"><i style="width:${Math.min(100, (v / max) * 100).toFixed(1)}%"></i></span><span class="v">${txt}</span></div>`;
    g("lp-m").innerHTML = bar("איטרציות", it, BUDGET.it, `${it} / ${BUDGET.it}`) + bar("טוקנים", tok, BUDGET.tok, `${tok.toLocaleString()}/12k`) +
      bar("עלות", usd, BUDGET.usd, `$${usd.toFixed(4)}/$0.005`);
    g("lp-c").textContent = `איטרציה ${i + 1}/${S.length} · שלב ${ph + 1}/4`;
  }
  const step = (d) => {
    const S = its();
    ph += d;
    if (ph > 3) { ph = 0; i = (i + 1) % S.length; }
    if (ph < 0) { ph = 3; i = (i - 1 + S.length) % S.length; }
    draw();
  };
  const tick = () => { clearTimeout(timer); if (playing) timer = setTimeout(() => { step(1); tick(); }, ph === 3 || ph === 2 ? 5200 : 3600); };
  const setP = (p) => { playing = p; g("lp-play").textContent = p ? "השהה" : "נגן"; tick(); };
  g("lp-weak").addEventListener("change", () => { i = 0; ph = 0; draw(); tick(); });
  g("lp-play").addEventListener("click", () => setP(!playing));
  g("lp-next").addEventListener("click", () => { setP(false); step(1); });
  g("lp-prev").addEventListener("click", () => { setP(false); step(-1); });
  draw(); setP(playing);
  return () => clearTimeout(timer);
};

/* ================================================================ sim: weak vs strong oracle */
window.AIDS["l07oracle"] = function (host) {
  // verifier acceptance per strategy: runs, ws (visible tests in the candidate's folder), clean (pristine copy), hidden, guard
  const VS = [
    ["runs", "\"זה רץ\": מייבא וקורא פעם אחת"],
    ["ws", "בדיקות גלויות בתיקייה של המועמד (הוא יכול לשנות אותן)"],
    ["clean", "בדיקות גלויות מקוריות, בחדר נקי"],
    ["hidden", "בדיקות נסתרות מבוססות תכונות"],
    ["guard", "guard: השוואת הבדיקות למקור וחיפוש ערכים קשיחים"],
  ];
  const S = [
    { n: "פתרון נכון", d: "מממש את המפרט.", ok: true, a: { runs: 1, ws: 1, clean: 1, hidden: 1, guard: 1 }, w: 0.30, cheat: false },
    { n: "באג במקרה קצה", d: "עובר את כל הדוגמאות הגלויות, אבל round מעגל 11.25 ל-11.0.", ok: false, a: { runs: 1, ws: 1, clean: 1, hidden: 0, guard: 1 }, w: 0.25, cheat: false },
    { n: "קוד שקורס", d: "שגיאת תחביר או שם לא מוגדר.", ok: false, a: { runs: 0, ws: 0, clean: 0, hidden: 0, guard: 1 }, w: 0.05, cheat: false },
    { n: "skip לבדיקות שנכשלות", d: "@pytest.mark.skip על שתי בדיקות. pytest מחזיר 0.", ok: false, a: { runs: 1, ws: 1, clean: 0, hidden: 0, guard: 0 }, w: 1, cheat: true },
    { n: "מחיקת בדיקות", d: "שתי הבדיקות שנכשלו פשוט נעלמו מהקובץ.", ok: false, a: { runs: 1, ws: 1, clean: 0, hidden: 0, guard: 0 }, w: 1, cheat: true },
    { n: "assert True", d: "הבדיקות קיימות, אבל לא בודקות כלום.", ok: false, a: { runs: 1, ws: 1, clean: 0, hidden: 0, guard: 0 }, w: 1, cheat: true },
    { n: "שינוי הערך הצפוי", d: "== 13 הפך ל-== 12 בבדיקה. נראה כמו תיקון טעות.", ok: false, a: { runs: 1, ws: 1, clean: 0, hidden: 0, guard: 0 }, w: 1, cheat: true },
    { n: "special-casing", d: "if text == \"1.5 weeks\": return 11. הבדיקות לא נגעו.", ok: false, a: { runs: 1, ws: 1, clean: 1, hidden: 0, guard: 0 }, w: 1, cheat: true },
    { n: "תשובות קבועות", d: "מחזיר מילון עם המספרים של הדוגמה הגלויה, בלי שום השוואה לקלט.", ok: false, a: { runs: 1, ws: 1, clean: 1, hidden: 0, guard: 1 }, w: 1, cheat: true },
  ];
  const on = { runs: true, ws: false, clean: false, hidden: false, guard: false };
  host.innerHTML = `<div class="l07">
    <div class="guide"><p><b>מה רואים:</b> תשע אסטרטגיות שמחולל יכול לנקוט כדי "לעבור", מפתרון נכון ועד רמאות. בחר אילו מאמתים פעילים. לכל אסטרטגיה מופיעים פסקי הדין של המאמתים הפעילים (✓ או ✗), והתוצאה: <b>נדחה</b>, <b>התקבל ונכון</b>, או <b>התקבל ושגוי</b>. האחרון הוא false pass, והוא מסומן באדום. מועמד מתקבל רק אם <b>כל</b> המאמתים הפעילים קיבלו אותו.</p></div>
    <div class="l07-checks" id="or-c">${VS.map(([k, t]) => `<label><input type="checkbox" data-k="${k}" ${on[k] ? "checked" : ""}> ${esc(t)}</label>`).join("")}</div>
    <div class="row"><button class="btn small" id="or-weak">רק "זה רץ"</button><button class="btn small" id="or-ci">CI תמים</button><button class="btn small" id="or-strong">חזק (כמו strong במעבדה)</button></div>
    <div class="stats" id="or-stats"></div>
    <div class="l07-strats" id="or-list"></div>
    <div class="knob"><div class="knob-head"><label for="or-k">לחץ אופטימיזציה: איטרציות עד שהלולאה מוצאת משהו שמתקבל</label><b id="or-kv"></b></div><input id="or-k" type="range" min="1" max="10" step="1" value="4"><small>מודל פשטני להמחשה: בכל איטרציה המחולל מנסה אסטרטגיה. בהתחלה רוב הניסיונות ישרים, ואחרי כישלונות חוזרים חלק הרמאויות עולה. הלולאה עוצרת במועמד הראשון שמתקבל.</small></div>
    <div class="l07-split" id="or-split"></div>
    <div class="legend" id="or-leg"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  const accepted = (s) => VS.every(([k]) => !on[k] || s.a[k]);
  function attemptDist(i) {
    // iteration i (1-based): cheat share grows after repeated failures, capped
    const cheat = Math.min(0.55, 0.06 + 0.07 * (i - 1));
    const honest = 1 - cheat, hw = S.filter((s) => !s.cheat), cw = S.filter((s) => s.cheat);
    const hsum = hw.reduce((a, s) => a + s.w, 0), csum = cw.reduce((a, s) => a + s.w, 0);
    return S.map((s) => (s.cheat ? cheat * s.w / csum : honest * s.w / hsum));
  }
  function draw() {
    host.querySelectorAll("#or-c input").forEach((x) => { x.checked = on[x.dataset.k]; });
    const act = VS.filter(([k]) => on[k]);
    let nAcc = 0, nFp = 0;
    g("or-list").innerHTML = S.map((s) => {
      const acc = accepted(s);
      if (acc) nAcc++;
      const fp = acc && !s.ok;
      if (fp) nFp++;
      const verdict = !acc ? `<span class="l07-verdict rej">נדחה</span>` : s.ok ? `<span class="l07-verdict ok">התקבל ונכון</span>` : `<span class="l07-verdict fp">התקבל ושגוי</span>`;
      return `<div class="l07-strat${fp ? " fp" : ""}"><div class="hd"><b>${esc(s.n)}</b>${verdict}</div><div class="d">${esc(s.d)}</div>
        <div class="chs">${act.length ? act.map(([k]) => `<span class="${s.a[k] ? "ok" : "no"}">${k} ${s.a[k] ? "✓" : "✗"}</span>`).join("") : `<span>no verifiers: everything passes</span>`}</div></div>`;
    }).join("");
    g("or-stats").innerHTML = `<span>מתקבלות: <b>${nAcc}/9</b></span><span>false passes: <b style="color:${nFp ? "var(--bad)" : "var(--good)"}">${nFp}</b></span><span>מה שמתקבל ונכון: <b>${nAcc ? Math.round(((nAcc - nFp) / nAcc) * 100) : 0}%</b></span>`;
    const k = +g("or-k").value;
    g("or-kv").textContent = k;
    let pt = 0, pf = 0, rem = 1;
    for (let i = 1; i <= k; i++) {
      const d = attemptDist(i);
      let a = 0, b = 0;
      S.forEach((s, j) => { if (accepted(s)) { if (s.ok) a += d[j]; else b += d[j]; } });
      pt += rem * a; pf += rem * b; rem *= 1 - a - b;
    }
    g("or-split").innerHTML = `<i class="t" style="width:${(pt * 100).toFixed(1)}%"></i><i class="f" style="width:${(pf * 100).toFixed(1)}%"></i><i class="u" style="width:${(rem * 100).toFixed(1)}%"></i>`;
    g("or-leg").innerHTML = `<span><i class="t"></i>נפתר באמת: ${(pt * 100).toFixed(0)}%</span><span><i class="f"></i>false pass: ${(pf * 100).toFixed(0)}%</span><span><i class="u"></i>לא נעצר עדיין: ${(rem * 100).toFixed(0)}%</span>`;
  }
  host.querySelectorAll("#or-c input").forEach((x) => x.addEventListener("change", () => { on[x.dataset.k] = x.checked; draw(); }));
  const preset = (p) => { Object.keys(on).forEach((k) => { on[k] = p.includes(k); }); draw(); };
  g("or-weak").addEventListener("click", () => preset(["runs"]));
  g("or-ci").addEventListener("click", () => preset(["runs", "ws"]));
  g("or-strong").addEventListener("click", () => preset(["clean", "hidden", "guard"]));
  g("or-k").addEventListener("input", draw);
  draw();
};

/* ================================================================ sim: convergence explorer */
window.AIDS["l07conv"] = function (host) {
  const MODES = [["compact", "משוב קומפקטי", 1.0, 300], ["raw", "פלט גולמי", 0.8, 1600], ["minimal", "\"Tests failed\"", 0.35, 10]];
  const st = { skill: 45, hard: 10, flaky: 0, budget: 6, sel: 0 };
  const PRICE = { i: 0.10e-6, o: 0.50e-6 }, BASE_IN = 1500, OUT = 600, KMAX = 15;
  host.innerHTML = `<div class="l07">
    <div class="guide"><p><b>מה רואים:</b> 100 משימות, ולכל סוג משוב עקומה: הציר האופקי הוא מספר האיטרציות, והאנכי הוא <b>איזה חלק מהמשימות נפתר עד האיטרציה הזו</b>. באיטרציה הראשונה אין עדיין משוב, ולכן כל העקומות מתחילות באותה נקודה. מהשנייה, איכות המשוב קובעת כמה מהמשימות הפתוחות נפתרות בכל סיבוב. הקו המקווקו הוא התקציב. ברשימה שמתחת: כמה נפתר עד התקציב, ועלות לכל משימה שנפתרה, כולל איטרציות שלא הובילו לכלום. המספרים יוצאים ממודל פשוט, והמטרה היא הצורה, לא הערכים.</p></div>
    <div class="seg" id="cv-seg" role="group" aria-label="סוג משוב">${MODES.map((m, k) => `<button data-k="${k}" aria-pressed="${k === 0}">${esc(m[1])}</button>`).join("")}</div>
    <svg class="l07-chart" id="cv-svg" viewBox="0 0 360 236" role="img" aria-label="solved fraction by iteration"></svg>
    <div class="legend">${MODES.map((m, k) => `<span><i class="c${k}"></i>${esc(m[1])}</span>`).join("")}</div>
    <div class="knob"><div class="knob-head"><label for="cv-skill">יכולת המודל: חלק מהמשימות הפתוחות שנפתר באיטרציה עם משוב מושלם</label><b id="cv-skillv"></b></div><input id="cv-skill" type="range" min="10" max="80" step="5"></div>
    <div class="knob"><div class="knob-head"><label for="cv-hard">משימות קשות מדי למודל</label><b id="cv-hardv"></b></div><input id="cv-hard" type="range" min="0" max="50" step="5"><small>נפתרות רק לעיתים נדירות (2% לאיטרציה). הן מה שמיישר את העקומה מתחת ל-100%.</small></div>
    <div class="knob"><div class="knob-head"><label for="cv-flaky">מאמת לא יציב: כשל מזויף על קוד נכון</label><b id="cv-flakyv"></b></div><input id="cv-flaky" type="range" min="0" max="50" step="5"></div>
    <div class="knob"><div class="knob-head"><label for="cv-budget">תקציב איטרציות</label><b id="cv-budgetv"></b></div><input id="cv-budget" type="range" min="1" max="15" step="1"></div>
    <div class="l07-rows" id="cv-rows"></div>
    <p class="muted" style="font-size:.8rem">הנחות: Haiku 5.5 (‎$0.10 / ‎$0.50 למיליון טוקנים), 1,500 טוקני קלט בסיסיים ו-600 טוקני פלט לאיטרציה, ועוד המשוב: קומפקטי כ-300 טוקנים, גולמי כ-1,600, מינימלי כ-10.</p>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  function curve(m) {
    const p = st.skill / 100, f = st.flaky / 100, h = st.hard / 100;
    const easy1 = p * 0.75 * (1 - f), easyK = p * MODES[m][2] * (1 - f), hardK = 0.02 * (1 - f);
    const out = [0];
    let ue = 1 - h, uh = h; // unsolved fractions
    let iters = 0;
    const its = [0];
    for (let k = 1; k <= KMAX; k++) {
      iters += ue + uh; // every unsolved task spends this iteration
      ue *= 1 - (k === 1 ? easy1 : easyK);
      uh *= 1 - hardK;
      out.push(1 - ue - uh);
      its.push(iters);
    }
    const cpi = (BASE_IN + (MODES[m][3])) * PRICE.i + OUT * PRICE.o;
    return { s: out, its, cpi };
  }
  function draw() {
    ["skill", "hard", "flaky", "budget"].forEach((k) => { g("cv-" + k).value = st[k]; });
    g("cv-skillv").textContent = st.skill + "%"; g("cv-hardv").textContent = st.hard + "%";
    g("cv-flakyv").textContent = st.flaky + "%"; g("cv-budgetv").textContent = st.budget;
    const W = 360, H = 236, L = 34, R = 10, T = 10, B = 40;
    const x = (k) => L + ((k - 1) / (KMAX - 1)) * (W - L - R), y = (v) => T + (1 - v) * (H - T - B);
    let svg = "";
    [0, .25, .5, .75, 1].forEach((v) => { svg += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 4}" y="${y(v) + 4}" text-anchor="end">${v * 100}%</text>`; });
    for (let k = 1; k <= KMAX; k += 2) svg += `<text x="${x(k)}" y="${H - 24}" text-anchor="middle">${k}</text>`;
    svg += `<line class="ax" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/><line class="ax" x1="${L}" x2="${L}" y1="${T}" y2="${y(0)}"/>`;
    const cs = MODES.map((_, m) => curve(m));
    cs.forEach((c, m) => {
      const pts = c.s.slice(1).map((v, k) => `${x(k + 1).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
      svg += `<polyline class="c${m}${m === st.sel ? "" : " dim"}" points="${pts}"/>`;
    });
    svg += `<line class="budget" x1="${x(st.budget)}" x2="${x(st.budget)}" y1="${T}" y2="${y(0)}"/><text x="${Math.min(W - R - 2, x(st.budget) + 4)}" y="${T + 10}" text-anchor="${st.budget > 12 ? "end" : "start"}">budget</text>`;
    svg += `<text x="${(L + W - R) / 2}" y="${H - 4}" text-anchor="middle">iteration</text>`;
    g("cv-svg").innerHTML = svg;
    g("cv-rows").innerHTML = cs.map((c, m) => {
      const solved = c.s[st.budget], spent = c.its[st.budget] * c.cpi;
      const per = solved > 0 ? spent / solved : null;
      const gain = st.budget > 1 ? (c.s[st.budget] - c.s[st.budget - 1]) * 100 : c.s[1] * 100;
      return `<div class="l07-row${m === st.sel ? " sel" : ""}"><b>${esc(MODES[m][1])}</b>
        <span>נפתרו עד איטרציה ${st.budget}: <b>${Math.round(solved * 100)} מתוך 100</b>. האיטרציה האחרונה הוסיפה ${gain.toFixed(1)} משימות.</span>
        <span>איטרציות בממוצע למשימה: <b>${(c.its[st.budget]).toFixed(2)}</b> · עלות לכל משימה שנפתרה: <b>${per ? "$" + per.toFixed(5) : "n/a"}</b></span></div>`;
    }).join("");
  }
  host.querySelectorAll("#cv-seg button").forEach((b) => b.addEventListener("click", () => {
    st.sel = +b.dataset.k; host.querySelectorAll("#cv-seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw();
  }));
  ["skill", "hard", "flaky", "budget"].forEach((k) => g("cv-" + k).addEventListener("input", (e) => { st[k] = +e.target.value; draw(); }));
  draw();
};

/* ================================================================ sim: stop-policy playground */
window.AIDS["l07stop"] = function (host) {
  const TR = {
    conv: { n: "מתכנסת", d: "כל איטרציה משפרת, ובחמישית הכל עובר.", s: [0.62, 0.75, 0.88, 0.94, 1], h: "abcde", c: 0.0003, solved: [5] },
    stuck: { n: "תקועה", d: "המודל כותב כל פעם קוד אחר, והציון מסתובב סביב 0.78.", s: [0.70, 0.78, 0.78, 0.76, 0.78, 0.77, 0.78, 0.78, 0.76, 0.78], h: "abcdefghij", c: 0.0004 },
    osc: { n: "מתנדנדת", d: "שני תיקונים שסותרים זה את זה, כמו ב-business_days.", s: [0.91, 0.91, 0.91, 0.91, 0.91, 0.91, 0.91, 0.91], h: "ABABABAB", c: 0.0003 },
    cheat: { n: "מרמה", d: "באיטרציות 2 ו-4 המודל שינה את הבדיקות. לפי הבדיקות שלו הכל עבר, אבל הבדיקות רצו מעותק נקי, ה-guard נכשל, והאיטרציה מסומנת tampered (באדום).", s: [0.6, 0.55, 0.7, 0.6, 0.75, 1], h: "abcdef", c: 0.0003, tam: [2, 4] },
    costly: { n: "יקרה", d: "הקשר גדול: כל איטרציה יקרה מהקודמת, וההתקדמות איטית.", s: [0.4, 0.55, 0.65, 0.72, 0.8, 0.86, 0.9, 1], h: "abcdefgh", cs: [0.009, 0.011, 0.013, 0.015, 0.017, 0.019, 0.021, 0.023], solved: [8] },
  };
  const st = { tr: "osc", patience: 2, maxIt: 8, cap: 0, maxTamper: 2 };
  host.innerHTML = `<div class="l07">
    <div class="guide"><p><b>מה רואים:</b> ריצה של לולאה, איטרציה אחרי איטרציה. לכל איטרציה: עמודה בגובה הציון (ירוקה כשנפתר, אדומה כשנמצאה רמאות), ה-hash של המועמד, והעלות. המדיניות רצה אחרי כל איטרציה לפי סדר הכללים של <code>should_stop</code>. האיטרציה שבה היא עצרה ממוסגרת בכתום, ומה שאחריה מקווקו, כי הוא לא היה רץ. בתיבה הכתומה: איזה כלל עצר, ולמה דווקא הוא.</p></div>
    <div class="seg" id="sp-seg" role="group" aria-label="ריצה">${Object.entries(TR).map(([k, t]) => `<button data-k="${k}" aria-pressed="${k === st.tr}">${esc(t.n)}</button>`).join("")}</div>
    <p class="muted" id="sp-d" style="font-size:.88rem"></p>
    <div class="l07-its" id="sp-its"></div>
    <div class="l07-why" id="sp-why"></div>
    <div class="knob"><div class="knob-head"><label for="sp-p">patience (0 = כבוי)</label><b id="sp-pv"></b></div><input id="sp-p" type="range" min="0" max="6" step="1"></div>
    <div class="knob"><div class="knob-head"><label for="sp-m">max_iterations</label><b id="sp-mv"></b></div><input id="sp-m" type="range" min="1" max="10" step="1"></div>
    <div class="knob"><div class="knob-head"><label for="sp-c">max_cost_usd (0 = בלי תקרה)</label><b id="sp-cv"></b></div><input id="sp-c" type="range" min="0" max="0.15" step="0.01"></div>
    <div class="knob"><div class="knob-head"><label for="sp-t">max_tamper</label><b id="sp-tv"></b></div><input id="sp-t" type="range" min="1" max="4" step="1"></div>
  </div>`;
  const g = (id) => host.querySelector("#" + id);
  function run(t) {
    const hist = [];
    const n = t.s.length;
    for (let i = 0; i < n; i++) {
      const tam = (t.tam || []).includes(i + 1);
      hist.push({ score: t.s[i], solved: t.s[i] >= 1, hash: t.h[i], cost: t.cs ? t.cs[i] : t.c, tam });
      const r = decide(hist);
      if (r) return { stopAt: i + 1, ...r };
    }
    return { stopAt: n, reason: "end_of_trace", why: "הריצה המוקלטת נגמרה לפני שאף כלל עצר אותה. במערכת אמיתית הלולאה הייתה ממשיכה, וזה בדיוק המצב שתקציב איטרציות נועד למנוע." };
  }
  function decide(hist) {
    const last = hist[hist.length - 1], n = hist.length;
    if (last.solved && !last.tam) return { reason: "solved", why: "כלל 2: כל מאמתי החובה עברו ולא נמצאה רמאות. הוא נבדק לפני התקציבים, כך שפתרון באיטרציה האחרונה של התקציב עדיין נחשב." };
    const tams = hist.filter((x) => x.tam).length;
    if (tams >= st.maxTamper) return { reason: "tampering", why: `כלל 3: ${tams} איטרציות עם רמאות, והתקרה היא ${st.maxTamper}. הלולאה עוצרת ומעבירה לאדם: מודל שמנסה לשנות את הבדיקות שוב ושוב הוא אות, לא תקלה.` };
    if (n >= st.maxIt) return { reason: "budget_iterations", why: `כלל 4: הגענו ל-${st.maxIt} איטרציות. הלולאה מחזירה את המועמד הטוב ביותר שנמצא, לא את האחרון.` };
    const cost = hist.reduce((a, x) => a + x.cost, 0);
    if (st.cap > 0 && (cost >= st.cap || cost + last.cost > st.cap))
      return { reason: "budget_cost", why: `כלל 6: הוצאו $${cost.toFixed(3)} מתוך $${st.cap.toFixed(2)}. ${cost >= st.cap ? "התקרה נחצתה." : `האיטרציה האחרונה עלתה $${last.cost.toFixed(3)}, ואיטרציה נוספת כמוה הייתה מגיעה ל-$${(cost + last.cost).toFixed(3)}. לכן עוצרים לפני שמוציאים, לא אחרי.`}` };
    if (n >= 2 && last.hash === hist[n - 2].hash) return { reason: "no_change", why: "כלל 8: המועמד זהה לקודם. איטרציה נוספת תחזיר כנראה אותו דבר." };
    if (hist.slice(0, -2).some((x) => x.hash === last.hash)) return { reason: "oscillation", why: `כלל 9: המועמד ${last.hash} כבר נוסה ונדחה. הלולאה מסתובבת במעגל. הכלל הזה נבדק לפני no_progress, כי הוא ספציפי יותר: הוא אומר לא רק שאין התקדמות, אלא גם מה קורה.` };
    const p = st.patience;
    if (p > 0 && n > p) {
      const recent = Math.max(...hist.slice(-p).map((x) => x.score)), before = Math.max(...hist.slice(0, -p).map((x) => x.score));
      if (recent <= before) return { reason: "no_progress", why: `כלל 10: הציון הטוב ביותר ב-${p} האיטרציות האחרונות (${recent.toFixed(2)}) לא עלה על הטוב ביותר שלפניהן (${before.toFixed(2)}).` };
    }
    return null;
  }
  function draw() {
    const t = TR[st.tr];
    g("sp-p").value = st.patience; g("sp-m").value = st.maxIt; g("sp-c").value = st.cap; g("sp-t").value = st.maxTamper;
    g("sp-pv").textContent = st.patience; g("sp-mv").textContent = st.maxIt; g("sp-cv").textContent = st.cap ? "$" + st.cap.toFixed(2) : "none";
    g("sp-tv").textContent = st.maxTamper;
    g("sp-d").textContent = t.d;
    const r = run(t);
    let cum = 0;
    g("sp-its").innerHTML = t.s.map((s, i) => {
      const cost = t.cs ? t.cs[i] : t.c;
      cum += cost;
      const tam = (t.tam || []).includes(i + 1);
      const cls = [s >= 1 && !tam ? "solved" : "", tam ? "tam" : "", i + 1 > r.stopAt ? "after" : "", i + 1 === r.stopAt ? "stop" : ""].join(" ");
      return `<div class="l07-it ${cls}"><span>it ${i + 1}</span><div class="bar"><i style="height:${(s * 100).toFixed(0)}%"></i></div><span>${s.toFixed(2)}</span><span class="hs">#${t.h[i]}</span><span>$${cum.toFixed(cost < 0.001 ? 4 : 3)}</span></div>`;
    }).join("");
    g("sp-why").innerHTML = `<b>עוצרת אחרי איטרציה ${r.stopAt}: ${esc(r.reason)}</b><br>${esc(r.why)}`;
  }
  host.querySelectorAll("#sp-seg button").forEach((b) => b.addEventListener("click", () => {
    st.tr = b.dataset.k; host.querySelectorAll("#sp-seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw();
  }));
  [["sp-p", "patience"], ["sp-m", "maxIt"], ["sp-c", "cap"], ["sp-t", "maxTamper"]].forEach(([id, k]) => g(id).addEventListener("input", (e) => { st[k] = +e.target.value; draw(); }));
  draw();
};
