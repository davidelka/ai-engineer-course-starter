// Lesson 18 aids: the pattern comparison animation (message flow + a token meter per agent), a
// "should this be multi-agent?" decision helper, a coordination-cost simulator, and an error-compounding
// simulator with the recorded failure exercise. Uses the globals $, h, esc at call time.
"use strict";
window.AIDS = window.AIDS || {};

// Recorded with multikit (labs/18-multi-agent), November 2026: task x08 for the agent patterns, research
// question r02 for fan-out. Fake models (deterministic heuristics), tokens ESTIMATED (chars / 4).
const L18_FLOWS = {"single": {"steps": [{"a": "single", "calls": ["search_hr_policies"], "tin": 2690, "tout": 34}, {"a": "single", "calls": ["read_document"], "tin": 3165, "tout": 33}, {"a": "single", "calls": ["get_oncall_for_service"], "tin": 3790, "tout": 30}, {"a": "single", "calls": ["list_access_grants"], "tin": 3905, "tout": 37}, {"a": "single", "calls": [], "tin": 4011, "tout": 184}], "ok": null}, "router": {"steps": [{"a": "router", "calls": [], "tin": 301, "tout": 45}, {"a": "hr", "calls": ["search_hr_policies"], "tin": 1022, "tout": 34}, {"a": "hr", "calls": ["read_document"], "tin": 1497, "tout": 33}, {"a": "hr", "calls": [], "tin": 2122, "tout": 106}], "ok": null}, "router2": {"steps": [{"a": "router", "calls": [], "tin": 301, "tout": 45}, {"a": "hr", "calls": ["search_hr_policies"], "tin": 1022, "tout": 34}, {"a": "hr", "calls": ["read_document"], "tin": 1497, "tout": 33}, {"a": "hr", "calls": [], "tin": 2122, "tout": 106}, {"a": "oncall", "calls": ["get_oncall_for_service"], "tin": 1140, "tout": 30}, {"a": "oncall", "calls": [], "tin": 1255, "tout": 92}], "ok": null}, "supervisor": {"steps": [{"a": "supervisor", "calls": ["delegate_to_hr(\"Keren Amar from finance has three questions. How many sick days does )", "delegate_to_oncall(\"Who is on call for connectors-hub?\")", "delegate_to_it_access(\"Does Keren Amar already have NetSuite access? Do not file anything.\")"], "tin": 1503, "tout": 101}, {"a": "supervisor", "calls": [], "tin": 1820, "tout": 184}, {"a": "oncall", "calls": ["get_oncall_for_service"], "tin": 1099, "tout": 30}, {"a": "oncall", "calls": [], "tin": 1213, "tout": 77}, {"a": "hr", "calls": ["search_hr_policies"], "tin": 996, "tout": 34}, {"a": "hr", "calls": ["read_document"], "tin": 1471, "tout": 33}, {"a": "hr", "calls": [], "tin": 2096, "tout": 90}, {"a": "it_access", "calls": ["list_access_grants"], "tin": 2122, "tout": 37}, {"a": "it_access", "calls": [], "tin": 2229, "tout": 31}], "ok": null}, "handoff": {"steps": [{"a": "triage", "calls": ["transfer_to_hr"], "tin": 2116, "tout": 127}, {"a": "hr", "calls": ["search_hr_policies"], "tin": 2281, "tout": 34}, {"a": "hr", "calls": ["read_document"], "tin": 2756, "tout": 33}, {"a": "hr", "calls": ["transfer_to_oncall"], "tin": 3382, "tout": 204}, {"a": "oncall", "calls": ["get_oncall_for_service"], "tin": 2464, "tout": 30}, {"a": "oncall", "calls": ["transfer_to_it_access"], "tin": 2578, "tout": 292}, {"a": "it_access", "calls": ["list_access_grants"], "tin": 3562, "tout": 37}, {"a": "it_access", "calls": [], "tin": 3668, "tout": 184}], "ok": null}, "fanout": {"steps": [{"a": "planner", "calls": [], "tin": 124, "tout": 122}, {"a": "researcher_1", "calls": ["search_docs"], "tin": 799, "tout": 31}, {"a": "researcher_1", "calls": ["read_corpus_doc"], "tin": 1404, "tout": 25}, {"a": "researcher_1", "calls": [], "tin": 2061, "tout": 29}, {"a": "researcher_2", "calls": ["search_docs"], "tin": 800, "tout": 30}, {"a": "researcher_2", "calls": ["read_corpus_doc"], "tin": 1428, "tout": 27}, {"a": "researcher_2", "calls": [], "tin": 1913, "tout": 26}, {"a": "researcher_3", "calls": ["search_docs"], "tin": 792, "tout": 26}, {"a": "researcher_3", "calls": ["read_corpus_doc"], "tin": 1411, "tout": 25}, {"a": "researcher_3", "calls": [], "tin": 2113, "tout": 36}, {"a": "synthesizer", "calls": [], "tin": 210, "tout": 76}], "subs": ["How many unused vacation days can be carried over under the 2026 vacation policy?", "How many days per week can employees work remotely under the 2026 remote work policy?", "What is the 2026 travel per diem for standard cities?"], "answer": "Up to 5 unused days may be carried over to the next calendar year. [hr-vacation-2026] Employees may work remotely up to 2 days per week. [hr-remote-work-2026] Per diem increased from $75 to $85 in standard cities and from $95 to $110 in high-cost cities. [fin-travel-2026]"}};

(function addL18Style() {
  if (document.getElementById("l18-style")) return;
  const st = document.createElement("style");
  st.id = "l18-style";
  st.textContent = `
  .l18 { display: grid; gap: 12px; min-width: 0; }
  .l18 p { margin: 0; line-height: 1.7; }
  .l18 .ltr, .l18i { direction: ltr; unicode-bidi: isolate; }
  .l18 .ltr { text-align: left; }
  .l18-task { direction: ltr; text-align: left; font-family: var(--mono); font-size: .76rem; background: var(--code-bg); border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; overflow-wrap: anywhere; }
  .l18-nodes { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 8px; direction: ltr; }
  .l18-node { border: 1px solid var(--line); border-radius: 10px; padding: 7px 8px; background: var(--surface); display: grid; gap: 4px; min-width: 0; transition: all .25s; }
  .l18-node b { font-family: var(--mono); font-size: .8rem; overflow-wrap: anywhere; }
  .l18-node small { color: var(--muted); font-size: .7rem; }
  .l18-node.on { border-color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 2px var(--accent-soft); }
  .l18-node.idle { opacity: .45; }
  .l18-node.coord b::after { content: " ◆"; color: var(--signal); }
  .l18-bar { height: 10px; background: var(--code-bg); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
  .l18-bar i { display: block; height: 100%; width: 0; background: var(--accent); transition: width .35s; }
  .l18-node.coord .l18-bar i { background: var(--signal); }
  .l18-tok { font-family: var(--mono); font-size: .72rem; }
  .l18-wire { direction: ltr; text-align: left; font-family: var(--mono); font-size: .74rem; line-height: 1.5; background: var(--code-bg); border: 1px solid var(--line); border-radius: 10px; padding: 8px; height: 190px; overflow: auto; }
  .l18-wire div { padding: 2px 4px; border-radius: 4px; overflow-wrap: anywhere; }
  .l18-wire .new { outline: 1px solid var(--accent); background: var(--accent-soft); }
  .l18-wire .to-user { color: var(--good); font-weight: 600; }
  .l18-wire .hand { color: var(--signal); }
  .l18-cap { border-inline-start: 3px solid var(--signal); padding: 6px 12px; background: var(--surface); border-radius: 0 8px 8px 0; min-height: 70px; }
  .l18-total { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .85rem; }
  .l18-total span b { font-family: var(--mono); }
  .l18-q { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 6px; }
  .l18-q p { font-size: .9rem; }
  .l18-q .hint { color: var(--muted); font-size: .8rem; }
  .l18-rec { border: 2px solid var(--accent); border-radius: 12px; padding: 10px 12px; background: var(--accent-soft); display: grid; gap: 6px; }
  .l18-rec h4 { margin: 0; }
  .l18-rec ul { margin: 0; padding-inline-start: 18px; display: grid; gap: 4px; }
  .l18-rec li.minus { color: var(--bad); }
  .l18-rec li.plus { color: var(--ink); }
  .l18-knobs { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }
  .l18-knob { display: grid; gap: 2px; border: 1px solid var(--line); border-radius: 10px; padding: 6px 8px; background: var(--surface); min-width: 0; }
  .l18-knob label { font-size: .8rem; display: flex; justify-content: space-between; gap: 6px; }
  .l18-knob label span { direction: ltr; font-family: var(--mono); }
  .l18-knob input { width: 100%; }
  .l18-cmp { display: grid; gap: 8px; }
  .l18-row { display: grid; grid-template-columns: 120px minmax(0, 1fr) 96px; gap: 8px; align-items: center; font-size: .82rem; }
  .l18-row .lab { font-weight: 600; }
  .l18-row .val { direction: ltr; font-family: var(--mono); text-align: left; font-size: .75rem; }
  .l18-row .l18-bar { height: 14px; }
  .l18-row.multi .l18-bar i { background: var(--signal); }
  @media (max-width: 520px) { .l18-row { grid-template-columns: 84px minmax(0, 1fr) 78px; font-size: .74rem; } }
  .l18-group { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; display: grid; gap: 6px; }
  .l18-group h5 { margin: 0; font-size: .85rem; }
  .l18-list { display: grid; gap: 4px; }
  .l18-li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; padding: 5px 9px; border: 1px solid var(--line); border-radius: 8px; font-size: .8rem; }
  .l18-li.ok { border-color: var(--good); background: var(--good-soft); }
  .l18-li.bad { border-color: var(--bad); background: var(--bad-soft); }
  .l18-li.warn { border-color: var(--signal); background: var(--signal-soft); }
  .l18-big { font-size: 1.6rem; font-family: var(--mono); font-weight: 700; direction: ltr; display: inline-block; }
  `;
  document.head.appendChild(st);
})();

function l18k(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(Math.round(n)); }

/* ---------------- animation: the patterns side by side ---------------- */
window.AIDS["l18flow"] = function (host) {
  const TASK_X08 = "Keren Amar from finance has three questions. How many sick days does an employee accrue per month? Who is on call for connectors-hub? Does Keren Amar already have NetSuite access? Do not file anything.";
  const TASK_R02 = "How many unused vacation days can be carried over under the 2026 vacation policy? How many days per week can employees work remotely under the 2026 remote work policy? What is the 2026 travel per diem for standard cities?";
  const PAT = {
    single: { name: "Agent יחיד", task: TASK_X08, coord: [],
      intro: "<b>Agent יחיד עם עשרה כלים.</b> אין תיאום. סוכן אחד מחזיק את הפרומפט של שלושת התחומים ואת ההגדרות של כל עשרת הכלים, וכל תוצאה של כלי נשארת בשיחה שלו עד הסוף. שים לב למונה שלו: הוא היחיד, והוא רק גדל." },
    router: { name: "Router", task: TASK_X08, coord: ["router"],
      intro: "<b>Router.</b> קריאה מובנית אחת, קטנה מאוד, מחליטה לאן הבקשה הולכת. אחר כך מומחה אחד עובד עם פרומפט קצר ושני כלים. זה הדפוס הזול ביותר, אבל כאן הבקשה נוגעת בשלושה תחומים, והנתב שולח אותה לתחום אחד בלבד." },
    router2: { name: "Router, שני יעדים", task: TASK_X08, coord: ["router"],
      intro: "<b>Router עם max_targets=2.</b> אותו סיווג, אבל הבקשה נשלחת לשני המומחים הראשונים. כל אחד עונה על החלק שלו, והתשובות פשוט מודבקות זו לזו. שום מודל לא קורא את שתיהן יחד, והתחום השלישי עדיין לא מקבל מענה." },
    supervisor: { name: "Supervisor", task: TASK_X08, coord: ["supervisor"],
      intro: "<b>Supervisor.</b> ה-supervisor הוא agent שהכלים היחידים שלו הם delegate_to_&lt;worker&gt;. הוא כותב לכל worker משימה קצרה, ושלוש ההאצלות יוצאות באותו צעד, כלומר במקביל. כל worker מתחיל מהקשר נקי, ומחזיר רק את התשובה שלו." },
    handoff: { name: "Handoff", task: TASK_X08, coord: ["triage"],
      intro: "<b>Handoffs.</b> אין מנהל. triage מעביר את השליטה למומחה הראשון, וכל מומחה מעביר הלאה עם סיכום מובנה, עד שהאחרון עונה למשתמש. העבודה רצה ברצף, וכל סיכום נעשה ארוך יותר, כי הוא נושא איתו את כל מה שנמצא עד אז." },
    fanout: { name: "Fan-out", task: TASK_R02, coord: ["planner", "synthesizer"],
      intro: "<b>Fan-out ו-synthesis.</b> שאלת מחקר (r02) מפורקת לשלוש תתי-שאלות בלתי תלויות. שלושה researchers עובדים עליהן במקביל, כל אחד עם הקשר נקי משלו, ושלב סינתזה כותב מהתשובות הקצרות תשובה אחת עם ציטוטים." },
  };
  const MAX = 24000;
  host.innerHTML = `<div class="l18">
    <div class="guide"><p><b>מה רואים:</b> אותה בקשה, x08, שנוגעת בשלושה תחומים (ימי מחלה, כוננות ל-connectors-hub, והרשאת NetSuite), עוברת כל פעם בדפוס אחר. ב-Fan-out השאלה היא r02. כל <b>כרטיס</b> הוא agent אחד: ◆ כתום מסמן agent של תיאום, וכחול מסמן agent שעושה את העבודה בתחום. <b>הפס</b> בכל כרטיס הוא מונה הטוקנים של ה-agent הזה, באותו קנה מידה בכל הדפוסים. <b>החלון השחור</b> מראה את ההודעות שעוברות בין ה-agents, וההודעה החדשה מסומנת. <b>איך לעבוד:</b> בחר דפוס, השהה, ועבור צעד אחרי צעד עם החצים. בסוף כל דפוס מופיע הסכום הכולל, לעומת agent יחיד.</p>
    <p class="muted">המספרים נמדדו ב-multikit עם המודלים המזויפים, ולכן הטוקנים הם <b>הערכה</b> (תווים חלקי 4). היחס בין הדפוסים אמיתי. את המספרים האמיתיים של Haiku תמדוד בתרגיל 6.</p></div>
    <div class="seg" role="group" aria-label="דפוס">${Object.entries(PAT).map(([k, p], j) => `<button aria-pressed="${j === 0}" data-p="${k}">${p.name}</button>`).join("")}</div>
    <div class="l18-task" data-task></div>
    <div class="l18-nodes" data-nodes></div>
    <div class="l18-wire" data-wire aria-live="polite"></div>
    <div class="l18-cap" data-cap></div>
    <div class="l18-total" data-total></div>
    <div class="row"><button class="btn small" data-prev>‹ הקודם</button><button class="btn small primary" data-play>השהה</button><button class="btn small" data-next>הבא ›</button><span class="muted" data-ctr></span></div>
  </div>`;

  function ordered(key) {
    const S = L18_FLOWS[key].steps.slice();
    if (key === "supervisor") {
      const sup = S.filter((s) => s.a === "supervisor");
      return [sup[0], ...S.filter((s) => s.a !== "supervisor"), ...sup.slice(1)];
    }
    return S;
  }
  function agentsOf(key) {
    const names = [...new Set(ordered(key).map((s) => s.a))];
    if (key === "router" || key === "router2") ["hr", "oncall", "it_access"].forEach((n) => { if (!names.includes(n)) names.push(n); });
    return names;
  }
  function framesFor(key) {
    const P = PAT[key], S = ordered(key);
    const F = [], wire = [], tok = {};
    const entry = S[0].a;
    wire.push({ c: "", t: `user → ${entry}: "${P.task.slice(0, 70)}…"` });
    F.push({ wire: wire.slice(), tok: { ...tok }, on: [entry], cap: P.intro });
    let prevAgent = null;
    const done = new Set();
    S.forEach((s, i) => {
      const used = s.tin + s.tout;
      tok[s.a] = (tok[s.a] || 0) + used;
      const isCoord = P.coord.includes(s.a);
      let line, cls = "", cap;
      const fresh = prevAgent !== s.a;
      if (s.calls.length) {
        const deleg = s.calls.filter((c) => c.startsWith("delegate_to_"));
        const trans = s.calls.filter((c) => c.startsWith("transfer_to_"));
        if (deleg.length) {
          line = deleg.map((c) => `${s.a} → ${c.split("(")[0].replace("delegate_to_", "")}: task=${c.slice(c.indexOf("(") + 1, -1)}`).join("\n");
          cls = "hand";
          cap = `<b>${s.a}, צעד ${i + 1}:</b> ${deleg.length} קריאות delegate <b>באותו צעד</b>. ה-executor מריץ אותן במקביל. כל worker יקבל רק את ה-task שכתוב כאן, ולא את הבקשה המלאה. ההקשר של הצעד הזה: <span class="l18i">${s.tin.toLocaleString()}</span> טוקנים.`;
        } else if (trans.length) {
          line = `${s.a} → ${trans[0].replace("transfer_to_", "")}: handoff summary (original request, facts, constraints)`;
          cls = "hand";
          cap = `<b>${s.a}:</b> סיים את החלק שלו וקורא ל-<span class="l18i">${trans[0]}</span>. הארגומנטים הם הסיכום, והם <b>כל</b> מה שה-agent הבא יראה. בצעד הזה ההקשר כבר <span class="l18i">${s.tin.toLocaleString()}</span> טוקנים, ויצאו <span class="l18i">${s.tout}</span> טוקנים של סיכום.`;
        } else {
          line = `${s.a}: tool_use ${s.calls.join(", ")}`;
          cap = `<b>${s.a}:</b> קורא ל-<span class="l18i">${s.calls.join(", ")}</span>. ${fresh && !isCoord && key !== "single" ? "זה הצעד הראשון שלו, וההקשר שלו קטן: הפרומפט שלו, הכלים שלו והמשימה שלו בלבד. " : ""}ההקשר שנשלח למודל בצעד הזה: <span class="l18i">${s.tin.toLocaleString()}</span> טוקנים.${key === "single" && i > 0 ? " כל תוצאה קודמת עדיין בשיחה, ולכן המספר רק עולה." : ""}`;
        }
      } else {
        const last = i === S.length - 1;
        const parent = key === "supervisor" && s.a !== "supervisor" ? "supervisor" : key === "fanout" && s.a.startsWith("researcher") ? "synthesizer" : "user";
        if (s.a === "router") {
          line = `router: RouteDecision → ${key === "router" ? "hr" : "hr, oncall"}`; cls = "hand";
          cap = `<b>router:</b> קריאה מובנית אחת של <span class="l18i">${s.tin}</span> טוקנים בלבד. היא מחזירה routes, confidence ו-clarifying_question, ו<b>קוד</b> (decide_route) מחליט: ${key === "router" ? "רק <b>hr</b>, כי max_targets=1." : "<b>hr</b> ו-<b>oncall</b>, כי max_targets=2. it_access לא יקבל כלום."}`;
        } else if (s.a === "planner") {
          line = `planner: ${L18_FLOWS.fanout.subs.length} sub-questions`; cls = "hand";
          cap = `<b>planner:</b> קריאה מובנית אחת מפרקת את השאלה ל-${L18_FLOWS.fanout.subs.length} תתי-שאלות <b>בלתי תלויות</b>. רק בגלל שהן לא תלויות זו בזו, אפשר להריץ אותן במקביל.`;
        } else {
          line = `${s.a} → ${parent}: answer`; cls = parent === "user" ? "to-user" : "";
          cap = parent === "user"
            ? `<b>${s.a} עונה למשתמש.</b> ${key === "router" ? "התשובה מכסה רק את ימי המחלה. השאלה על connectors-hub והשאלה על NetSuite אבדו: הנתב החליט פעם אחת, מראש." : key === "router2" ? "שתי תשובות מודבקות. השאלה על NetSuite אבדה." : key === "handoff" ? "ה-agent האחרון בשרשרת עונה, יחד עם העובדות שהועברו אליו בסיכומים." : key === "fanout" ? "הסינתזה קראה רק את שלוש התשובות הקצרות, לא את המסמכים, ולכן היא זולה." : key === "supervisor" ? "ה-supervisor ראה רק שלוש תשובות קצרות, ולא את ה-trajectories של ה-workers. זה בידוד ההקשר." : "התשובה הסופית. כל ההקשר שנצבר נשלח שוב בצעד הזה."}`
            : `<b>${s.a} מסיים</b> ומחזיר ל-${parent} רק את התשובה שלו, בלי החיפושים והמסמכים שקרא. בצעד הגדול שלו היו <span class="l18i">${s.tin.toLocaleString()}</span> טוקנים בהקשר.`;
          done.add(s.a);
        }
      }
      line.split("\n").forEach((ln) => wire.push({ c: cls, t: ln }));
      prevAgent = s.a;
      F.push({ wire: wire.slice(), tok: { ...tok }, on: [s.a], cap, end: i === S.length - 1 });
    });
    return F;
  }

  let key = "single", frames = framesFor(key), i = 0, timer = null;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let playing = !reduce;
  const btn = host.querySelector("[data-play]");
  const totalOf = (k) => L18_FLOWS[k].steps.reduce((a, s) => a + s.tin + s.tout, 0);
  function draw() {
    const f = frames[i], P = PAT[key];
    host.querySelector("[data-task]").textContent = P.task;
    host.querySelector("[data-nodes]").innerHTML = agentsOf(key).map((a) => {
      const t = f.tok[a] || 0;
      const coord = P.coord.includes(a);
      const ran = L18_FLOWS[key].steps.some((s) => s.a === a);
      return `<div class="l18-node ${coord ? "coord" : ""} ${f.on.includes(a) ? "on" : ""} ${!ran ? "idle" : ""}"><b>${esc(a)}</b><small>${coord ? "coordinator" : ran ? "worker" : "לא רץ"}</small><div class="l18-bar"><i style="width:${Math.min(100, (t / MAX) * 100).toFixed(1)}%"></i></div><span class="l18-tok">${t.toLocaleString()} tok</span></div>`;
    }).join("");
    const w = host.querySelector("[data-wire]");
    w.innerHTML = f.wire.map((x, k) => `<div class="${x.c}${k === f.wire.length - 1 ? " new" : ""}">${esc(x.t)}</div>`).join("");
    w.scrollTop = w.scrollHeight;
    host.querySelector("[data-cap]").innerHTML = f.cap;
    const tot = Object.values(f.tok).reduce((a, b) => a + b, 0);
    const single = totalOf("single");
    host.querySelector("[data-total]").innerHTML = `<span>טוקנים עד עכשיו: <b>${tot.toLocaleString()}</b></span>` +
      (f.end ? `<span>סה"כ בדפוס: <b>${totalOf(key).toLocaleString()}</b></span>${key !== "fanout" ? `<span>agent יחיד על אותה משימה: <b>${single.toLocaleString()}</b> (×${(totalOf(key) / single).toFixed(2)})</span>` : ""}<span>agents: <b>${new Set(L18_FLOWS[key].steps.map((s) => s.a)).size}</b></span>` : "");
    host.querySelector("[data-ctr]").textContent = `${i + 1} / ${frames.length}`;
    btn.textContent = playing ? "השהה" : "נגן";
  }
  function arm() { clearInterval(timer); if (playing) timer = setInterval(() => { i = (i + 1) % frames.length; draw(); }, 3800); }
  host.querySelector("[data-next]").addEventListener("click", () => { playing = false; arm(); i = Math.min(frames.length - 1, i + 1); draw(); });
  host.querySelector("[data-prev]").addEventListener("click", () => { playing = false; arm(); i = Math.max(0, i - 1); draw(); });
  btn.addEventListener("click", () => { playing = !playing; arm(); draw(); });
  host.querySelectorAll("[data-p]").forEach((b) => b.addEventListener("click", () => {
    host.querySelectorAll("[data-p]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    key = b.dataset.p; frames = framesFor(key); i = 0; draw(); arm();
  }));
  draw(); arm();
  return () => clearInterval(timer);
};

/* ---------------- sim: should this be multi-agent? ---------------- */
window.AIDS["l18decide"] = function (host) {
  const Q = [
    { id: "measured", q: "מדדת agent יחיד על סט משימות עם זהב, והוא נכשל באופן שחוזר על עצמו?", hint: "בלי מדידה אין לך מול מה להשוות. זו השאלה הראשונה, לא האחרונה." },
    { id: "tools", q: "agent יחיד יצטרך הרבה כלים (בערך 15 ומעלה), או הוראות שונות מאוד לכל תחום?", hint: "LangChain מציינים זאת כסיבה העיקרית: agent עם יותר מדי כלים בוחר גרוע." },
    { id: "context", q: "ההקשר של agent יחיד מתמלא בחומר ששייך לחלק אחר של המשימה, כמו מסמכים ארוכים ותוצאות כלים רבות?", hint: "זה היתרון האמיתי: כל subagent עובד בהקשר נקי וממוקד." },
    { id: "parallel", q: "המשימה מתפרקת לחלקים שלא תלויים זה בזה, ואפשר לעבוד עליהם במקביל?", hint: "מחקר: כן. שינוי קוד במודולים שתלויים זה בזה: בדרך כלל לא." },
    { id: "single_domain", q: "רוב הבקשות שייכות לתחום אחד ברור, ואפשר לסווג אותן בקלות?", hint: "אם כן, router זול מספיק." },
    { id: "shared", q: "החלקים צריכים לשתף הרבה הקשר, או לקבל החלטות שתלויות זו בזו?", hint: "Cognition: פעולות נושאות החלטות סמויות, ושני כותבים במקביל מתנגשים." },
    { id: "writes", q: "יותר מחלק אחד כותב לעולם (פותח בקשות, משנה קבצים)?", hint: "כתיבות מקבילות הן מקור לסתירות ולכפילויות." },
    { id: "value", q: "המשימה שווה מספיק כדי לשלם פי 3 עד 15 בטוקנים?", hint: "Anthropic: multi-agent השתמש בכ-15 פעמים יותר טוקנים מצ'אט." },
    { id: "latency", q: "זמן התגובה קריטי, והעבודה כוללת הרבה חיפושים איטיים?", hint: "מקביליות קונה זמן, אבל לא חוסכת טוקנים." },
  ];
  const ans = {};
  Q.forEach((x) => { ans[x.id] = "?"; });
  host.innerHTML = `<div class="l18">
    <div class="guide"><p><b>מה זה:</b> רשימת שאלות שעוזרת להחליט אם להפוך משימה ל-multi-agent, ולאיזה דפוס. ענה על כל שאלה ב"כן", "לא" או "לא יודע". ההמלצה למטה מתעדכנת מיד, וברשימה שמתחתיה מופיע הנימוק: <b>שורה שחורה</b> היא סיבה בעד, ו<b>שורה אדומה</b> היא סיבה נגד. ברירת המחדל, כשאין מספיק סיבות, היא agent יחיד. <b>מה לנסות:</b> ענה כמו שהיית עונה על Company Brain, ואחר כך כמו על מערכת מחקר. לבסוף נסה סוכן קוד שמשנה עשרה קבצים.</p></div>
    <div class="seg" role="group" aria-label="דוגמה"><button data-ex="brain">דוגמה: Company Brain</button><button data-ex="research">דוגמה: מערכת מחקר</button><button data-ex="code">דוגמה: סוכן קוד</button><button data-ex="clear">נקה</button></div>
    <div data-qs style="display:grid;gap:8px"></div>
    <div class="l18-rec" data-rec></div>
  </div>`;
  const EX = {
    brain: { measured: "yes", tools: "no", context: "no", parallel: "yes", single_domain: "yes", shared: "no", writes: "no", value: "no", latency: "no" },
    research: { measured: "yes", tools: "no", context: "yes", parallel: "yes", single_domain: "no", shared: "no", writes: "no", value: "yes", latency: "yes" },
    code: { measured: "yes", tools: "no", context: "yes", parallel: "no", single_domain: "no", shared: "yes", writes: "yes", value: "yes", latency: "no" },
  };
  function render() {
    host.querySelector("[data-qs]").innerHTML = Q.map((x) => `<div class="l18-q"><p>${x.q}</p><p class="hint">${x.hint}</p>
      <div class="seg" role="group" aria-label="${x.id}">${[["yes", "כן"], ["no", "לא"], ["?", "לא יודע"]].map(([v, l]) => `<button data-q="${x.id}" data-v="${v}" aria-pressed="${ans[x.id] === v}">${l}</button>`).join("")}</div></div>`).join("");
    host.querySelectorAll("[data-q]").forEach((b) => b.addEventListener("click", () => { ans[b.dataset.q] = b.dataset.v; render(); }));
    const y = (k) => ans[k] === "yes", n = (k) => ans[k] === "no";
    const plus = [], minus = [];
    let pattern = "agent יחיד, עם כלים טובים";
    let why = "אין עדיין סיבה מדודה לפצל. agent יחיד הוא הכי זול, הכי מהיר לבנות, והכי קל לדבג.";
    if (!y("measured")) minus.push("לא מדדת agent יחיד. קודם בונים אותו, מריצים אותו על סט עם זהב, ורק אז יודעים מה צריך לשפר.");
    if (y("tools")) plus.push("יותר מדי כלים או הוראות סותרות לסוכן אחד: לכל מומחה יהיו פרומפט וכלים משלו.");
    if (y("context")) plus.push("ההקשר מזוהם: subagent עם הקשר נקי מחזיר רק את מה שחשוב. זה היתרון המרכזי.");
    if (y("parallel")) plus.push("יש חלקים בלתי תלויים: fan-out או supervisor יריצו אותם במקביל.");
    if (y("latency")) plus.push("זמן התגובה חשוב: מקביליות מקצרת את הזמן, אבל לא את מספר הטוקנים.");
    if (y("shared")) minus.push("החלקים תלויים זה בזה: agents נפרדים יקבלו החלטות סותרות (Cognition). עדיף agent אחד, או כותב יחיד עם יועצים.");
    if (y("writes")) minus.push("כמה חלקים כותבים: השאר את כל הכתיבות אצל agent אחד, ותן לאחרים רק לקרוא ולייעץ.");
    if (n("value")) minus.push("המשימה לא שווה פי כמה בטוקנים. בקשת גישה פשוטה לא מצדיקה צוות.");
    if (y("value")) plus.push("המשימה שווה את המחיר, כך שאפשר לשלם על תיאום.");
    const score = plus.length - minus.length;
    if (y("measured") && y("single_domain") && !y("context") && !y("tools") && score <= 1) {
      pattern = "Router: סיווג אחד ומומחה אחד";
      why = "רוב הבקשות שייכות לתחום אחד, וסיווג זול מספיק. שים fallback של שאלת הבהרה מתחת לסף confidence, ובדוק כמה בקשות חוצות תחומים.";
    } else if (y("measured") && score >= 2 && y("parallel") && !y("shared")) {
      pattern = y("context") && !y("single_domain") ? "Fan-out או supervisor עם workers מקבילים" : "Supervisor עם delegate tools";
      why = "החלקים בלתי תלויים, וכל worker ירוויח מהקשר נקי. מדוד: success, טוקנים, ואת החלק של שכבת התיאום בעלות. תן ל-workers להחזיר ראיות, ובדוק אותן בקוד.";
    } else if (y("measured") && y("shared") && y("value")) {
      pattern = "Agent אחד שכותב, ועוד agents שרק קוראים ומבקרים";
      why = "התבנית שעובדת ב-2026 לפי Cognition: הכתיבות נשארות אצל agent אחד, ושאר ה-agents תורמים ביקורת או עצה, למשל review loop.";
    } else if (y("measured") && y("tools") && !y("parallel")) {
      pattern = "Handoffs, או מומחים מאחורי router";
      why = "תחומים שונים מאוד, אבל העבודה היא ברצף: כל מומחה מחזיק את הכלים שלו. הקפד על חוזה סיכום מחמיר בין מומחה למומחה.";
    }
    host.querySelector("[data-rec]").innerHTML = `<h4>ההמלצה: ${pattern}</h4><p>${why}</p><ul>${plus.map((p) => `<li class="plus">✓ ${p}</li>`).join("")}${minus.map((p) => `<li class="minus">✗ ${p}</li>`).join("")}</ul>`;
  }
  host.querySelectorAll("[data-ex]").forEach((b) => b.addEventListener("click", () => {
    const e = EX[b.dataset.ex];
    Q.forEach((x) => { ans[x.id] = e ? e[x.id] : "?"; });
    render();
  }));
  render();
};

/* ---------------- sim: coordination cost ---------------- */
window.AIDS["l18cost"] = function (host) {
  const K = { workers: 3, steps: 3, base: 1200, tooldefs: 500, add: 600, brief: 200, result: 300, coordSteps: 2, latency: 2.0, parallel: 1 };
  const KN = [
    ["workers", "מספר workers (תחומים)", 1, 10, 1, (v) => v],
    ["steps", "צעדים לכל worker", 1, 8, 1, (v) => v],
    ["base", "פרומפט בסיס לכל agent (טוקנים)", 300, 4000, 100, (v) => v],
    ["tooldefs", "הגדרות כלים לכל תחום", 100, 2000, 100, (v) => v],
    ["add", "טוקנים שנוספים בכל צעד (תוצאות כלים)", 100, 4000, 100, (v) => v],
    ["brief", "גודל המשימה שה-supervisor כותב", 50, 1500, 50, (v) => v],
    ["result", "גודל התשובה שחוזרת מ-worker", 50, 3000, 50, (v) => v],
    ["coordSteps", "צעדים של ה-supervisor", 1, 5, 1, (v) => v],
    ["latency", "שניות לכל קריאת מודל", 0.5, 10, 0.5, (v) => v.toFixed(1) + "s"],
  ];
  host.innerHTML = `<div class="l18">
    <div class="guide"><p><b>מה זה:</b> מחשבון שמשווה, לאותה עבודה, agent יחיד ל-supervisor עם workers. ה-agent היחיד עושה את כל הצעדים של כל התחומים בשיחה אחת, עם כל הגדרות הכלים, וכל צעד שולח מחדש את כל ההקשר שנצבר. ב-supervisor, כל worker מתחיל מהקשר נקי: הפרומפט שלו, הכלים של התחום שלו והמשימה שקיבל. ה-supervisor משלם על הפרומפט שלו ועל התשובות שחוזרות אליו. <b>איך לקרוא:</b> כל שורה היא פס, והפס הארוך ביותר בכל קבוצה הוא 100%. כחול הוא agent יחיד, כתום הוא multi-agent. <b>מה לנסות:</b> (1) הגדל את מספר ה-workers, וראה שהטוקנים הכוללים של שני הדפוסים קרובים, בזמן שה<b>הקשר הגדול ביותר</b> שונה מאוד. (2) הקטן את "טוקנים שנוספים בכל צעד" ל-100, וראה מתי multi-agent יקר יותר. (3) כבה את המקביליות וראה מה קורה לזמן.</p>
    <p class="muted">זה מודל פשוט, לא מדידה: אין בו cache, ואין בו קריאות חוזרות. את המספרים האמיתיים מודדים בתרגיל 6.</p></div>
    <div class="l18-knobs">${KN.map(([k, lbl, mn, mx, st]) => `<div class="l18-knob"><label>${lbl}<span data-v="${k}"></span></label><input type="range" min="${mn}" max="${mx}" step="${st}" value="${K[k]}" data-k="${k}" aria-label="${lbl}"></div>`).join("")}</div>
    <div class="seg" role="group" aria-label="מקביליות"><button data-par="1" aria-pressed="true">workers במקביל</button><button data-par="0" aria-pressed="false">workers ברצף</button></div>
    <div data-out style="display:grid;gap:10px"></div>
  </div>`;
  function calc() {
    const N = K.workers, s = K.steps;
    // single agent: N*s tool steps + 1 final step; context grows by `add` each step
    const baseS = K.base + N * K.tooldefs;
    let sIn = 0, sMax = 0;
    const T = N * s + 1;
    for (let k = 0; k < T; k++) { const c = baseS + k * K.add; sIn += c; sMax = Math.max(sMax, c); }
    const sOut = T * 60;
    // workers: s tool steps + 1 final, context starts at base + own tooldefs + brief
    let wIn = 0, wMax = 0;
    for (let k = 0; k < s + 1; k++) { const c = K.base + K.tooldefs + K.brief + k * K.add; wIn += c; wMax = Math.max(wMax, c); }
    wIn *= N;
    const wOut = N * (s + 1) * 60;
    // supervisor: coordSteps; first step = base + delegate tool defs; later steps carry the results
    let cIn = 0, cMax = 0;
    for (let k = 0; k < K.coordSteps; k++) { const c = K.base + N * 150 + (k > 0 ? N * (K.result + K.brief) : 0); cIn += c; cMax = Math.max(cMax, c); }
    const cOut = K.coordSteps * 80 + N * K.brief;
    const mIn = wIn + cIn, mOut = wOut + cOut;
    const price = (i, o) => (i * 0.10 + o * 0.50) / 1e6;
    const latS = T * K.latency;
    const latM = (K.coordSteps + (K.parallel ? (s + 1) : N * (s + 1))) * K.latency;
    return { sTok: sIn + sOut, mTok: mIn + mOut, sMax, wMax, cMax, sCost: price(sIn, sOut), mCost: price(mIn, mOut), latS, latM, coordShare: (cIn + cOut) / (mIn + mOut), calls: { s: T, m: K.coordSteps + N * (s + 1) } };
  }
  function bars(title, rows, fmt) {
    const max = Math.max(...rows.map((r) => r[1]), 1e-9);
    return `<div class="l18-group"><h5>${title}</h5><div class="l18-cmp">${rows.map(([lbl, v, cls]) => `<div class="l18-row ${cls}"><span class="lab">${lbl}</span><div class="l18-bar"><i style="width:${(v / max * 100).toFixed(1)}%"></i></div><span class="val">${fmt(v)}</span></div>`).join("")}</div></div>`;
  }
  function render() {
    KN.forEach(([k, , , , , f]) => { host.querySelector(`[data-v="${k}"]`).textContent = f(K[k]); });
    const r = calc();
    const ratio = r.mTok / r.sTok;
    host.querySelector("[data-out]").innerHTML =
      `<div class="l18-total"><span>טוקנים, multi חלקי יחיד: <span class="l18-big">×${ratio.toFixed(2)}</span></span><span>חלק התיאום בעלות של multi: <b>${(r.coordShare * 100).toFixed(0)}%</b></span><span>קריאות מודל: <b>${r.calls.s}</b> מול <b>${r.calls.m}</b></span></div>` +
      bars("סה\"כ טוקנים (קלט ופלט)", [["agent יחיד", r.sTok, ""], ["multi-agent", r.mTok, "multi"]], (v) => Math.round(v).toLocaleString()) +
      bars("ההקשר הגדול ביותר שמודל אחד ראה בצעד אחד", [["agent יחיד", r.sMax, ""], ["worker", r.wMax, "multi"], ["supervisor", r.cMax, "multi"]], (v) => Math.round(v).toLocaleString()) +
      bars("עלות (מחיר Haiku 5.5)", [["agent יחיד", r.sCost, ""], ["multi-agent", r.mCost, "multi"]], (v) => "$" + v.toFixed(5)) +
      bars("זמן (קריאות ברצף כפול שניות לקריאה)", [["agent יחיד", r.latS, ""], ["multi-agent", r.latM, "multi"]], (v) => v.toFixed(1) + "s") +
      `<p class="muted">${ratio > 1.15 ? "כאן multi-agent <b>יקר יותר</b> בטוקנים. כל worker משלם מחדש על פרומפט הבסיס, וה-supervisor משלם על התשובות. מה שהוא קונה זה הקשר קטן יותר לכל מודל" + (K.parallel ? ", וזמן קצר יותר." : ".") : ratio < 0.85 ? "כאן multi-agent <b>זול יותר</b>. ההקשר של ה-agent היחיד מתנפח, כי כל תוצאת כלי נשלחת מחדש בכל צעד, בכל התחומים. אצל ה-workers ההקשר מתאפס בכל תחום." : "כאן שני הדפוסים קרובים בטוקנים. ההבדל הוא בגודל ההקשר המקסימלי ובזמן."}</p>`;
  }
  host.querySelectorAll("[data-k]").forEach((inp) => inp.addEventListener("input", () => { K[inp.dataset.k] = Number(inp.value); render(); }));
  host.querySelectorAll("[data-par]").forEach((b) => b.addEventListener("click", () => {
    host.querySelectorAll("[data-par]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    K.parallel = Number(b.dataset.par); render();
  }));
  render();
};

/* ---------------- sim: error compounding and verification ---------------- */
window.AIDS["l18fail"] = function (host) {
  const K = { n: 3, p: 95, c: 0, votes: 1 };
  const REC = [{"label": "route \u00b7 x01 \u00b7 verify=none", "v": "bad"}, {"label": "route \u00b7 x06 \u00b7 verify=none", "v": "bad"}, {"label": "route \u00b7 x01 \u00b7 verify=llm", "v": "warn"}, {"label": "route \u00b7 x06 \u00b7 verify=llm", "v": "ok"}, {"label": "route \u00b7 x01 \u00b7 verify=code", "v": "warn"}, {"label": "route \u00b7 x06 \u00b7 verify=code", "v": "ok"}, {"label": "lead \u00b7 x03 \u00b7 verify=none", "v": "bad"}, {"label": "lead \u00b7 x03 \u00b7 verify=llm", "v": "ok"}, {"label": "lead \u00b7 x03 \u00b7 verify=code", "v": "ok"}, {"label": "number \u00b7 x02 \u00b7 verify=none", "v": "bad"}, {"label": "number \u00b7 x02 \u00b7 verify=llm", "v": "bad"}, {"label": "number \u00b7 x02 \u00b7 verify=code", "v": "bad"}];
  host.innerHTML = `<div class="l18">
    <div class="guide"><p><b>מה זה:</b> בחלק העליון יש מחשבון. כש-<b>n</b> agents תלויים זה בזה, וכל אחד צודק בהסתברות <b>p</b>, התוצאה הסופית נכונה רק אם כולם צדקו: p בחזקת n. <b>בדיקה</b> שתופסת חלק c מהשגיאות, ושולחת לנסות שוב פעם אחת, מעלה את p של כל agent. <b>הצבעה</b> מריצה כל agent k פעמים ולוקחת רוב (עם k אי-זוגי). בחלק התחתון מוצגות התוצאות האמיתיות מתרגיל 7 (המודלים המזויפים): worker שתשובתו שובשה, מול שלושה מצבי verify. <b>מה לנסות:</b> קבע p=95% ו-n=5. כמה יוצא? כמה בדיקה טובה צריכה לתפוס כדי לחזור ל-95%?</p></div>
    <div class="l18-knobs">
      <div class="l18-knob"><label>n: agents ברצף<span data-v="n"></span></label><input type="range" min="1" max="10" step="1" value="3" data-k="n" aria-label="n"></div>
      <div class="l18-knob"><label>p: דיוק כל agent<span data-v="p"></span></label><input type="range" min="70" max="99.9" step="0.1" value="95" data-k="p" aria-label="p"></div>
      <div class="l18-knob"><label>c: אחוז השגיאות שהבדיקה תופסת<span data-v="c"></span></label><input type="range" min="0" max="100" step="5" value="0" data-k="c" aria-label="c"></div>
      <div class="l18-knob"><label>k: הצבעה (ריצות לכל agent)<span data-v="votes"></span></label><input type="range" min="1" max="7" step="2" value="1" data-k="votes" aria-label="votes"></div>
    </div>
    <div data-out></div>
    <div class="l18-group"><h5>מתרגיל 7: האם ה-supervisor תפס את ה-worker שטעה?</h5><div class="l18-list" data-rec></div>
    <p class="muted">"נתפס חלקית" אומר שה-supervisor שם לב ושלח שוב, אבל ההרצה החוזרת הגישה שוב את הבקשה. ה-idempotency key משיעור 14 החזיר את אותו מזהה, ולכן לא נוצרה כפילות, אבל האדם התבקש לאשר פעמיים. מספר שהשתנה בתשובת ה-HR לא נתפס באף מצב, כי אין לו ראיה מובנית להשוות אליה.</p></div>
  </div>`;
  function maj(p, k) {
    if (k === 1) return p;
    let s = 0;
    const C = (a, b) => { let r = 1; for (let i = 1; i <= b; i++) r = r * (a - b + i) / i; return r; };
    for (let j = Math.ceil((k + 1) / 2); j <= k; j++) s += C(k, j) * Math.pow(p, j) * Math.pow(1 - p, k - j);
    return s;
  }
  function render() {
    host.querySelector('[data-v="n"]').textContent = K.n;
    host.querySelector('[data-v="p"]').textContent = K.p.toFixed(1) + "%";
    host.querySelector('[data-v="c"]').textContent = K.c + "%";
    host.querySelector('[data-v="votes"]').textContent = K.votes;
    const p = K.p / 100, c = K.c / 100;
    const pv = maj(p, K.votes);
    const pe = pv + (1 - pv) * c * pv;
    const raw = Math.pow(p, K.n), fin = Math.pow(pe, K.n);
    const cost = K.votes * (1 + (1 - pv) * c);
    host.querySelector("[data-out]").innerHTML = `<div class="l18-cmp">
      <div class="l18-row"><span class="lab">בלי כלום</span><div class="l18-bar"><i style="width:${(raw * 100).toFixed(1)}%"></i></div><span class="val">${(raw * 100).toFixed(1)}%</span></div>
      <div class="l18-row multi"><span class="lab">עם הצבעה ובדיקה</span><div class="l18-bar"><i style="width:${(fin * 100).toFixed(1)}%"></i></div><span class="val">${(fin * 100).toFixed(1)}%</span></div></div>
      <p class="muted">דיוק של agent אחד אחרי הצבעה ובדיקה: <span class="l18i">${(pe * 100).toFixed(1)}%</span>. העלות: בערך <span class="l18i">×${cost.toFixed(2)}</span> קריאות לכל agent. ${K.n >= 4 && raw < 0.85 ? "שים לב כמה מהר המספר יורד: שרשרת ארוכה של agents סבירים היא מערכת לא סבירה." : ""}</p>`;
  }
  host.querySelector("[data-rec]").innerHTML = REC.map((r) => `<div class="l18-li ${r.v}"><span class="l18i">${esc(r.label)}</span><span>${r.v === "ok" ? "נתפס ותוקן" : r.v === "warn" ? "נתפס חלקית" : "לא נתפס"}</span></div>`).join("");
  host.querySelectorAll("[data-k]").forEach((inp) => inp.addEventListener("input", () => { K[inp.dataset.k] = Number(inp.value); render(); }));
  render();
};
