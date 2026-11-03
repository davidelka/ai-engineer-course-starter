// Lesson 8 aids: question -> answer-with-provenance animation, SQL guard playground,
// "documents or database?" router game, execution-accuracy judge.
// Registered on window.AIDS; uses the hub helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const STYLE_ID = "l08-style";
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const st = document.createElement("style");
    st.id = STYLE_ID;
    st.textContent = `
.l08 .guide { background: var(--accent-soft); border-radius: 10px; padding: 10px 14px; font-size: .92rem; }
.l08 .guide p { margin: 0 0 6px; } .l08 .guide p:last-child { margin: 0; }
.l08-steps { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; direction: rtl; }
.l08-steps button { border: 1px solid var(--line); background: var(--surface); border-radius: 8px; padding: 5px 2px; font-size: .68rem; line-height: 1.25; color: var(--muted); min-width: 0; }
.l08-steps button b { display: block; font-family: var(--mono); font-size: .75rem; color: var(--ink); }
.l08-steps button.on { border-color: var(--accent); background: var(--accent-soft); color: var(--ink); }
.l08-steps button.done { border-color: var(--good); }
.l08-stage { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px; min-height: 250px; display: grid; gap: 10px; align-content: start; overflow: hidden; }
.l08-stage pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .76rem; }
.l08-kv { display: grid; gap: 4px; direction: ltr; text-align: left; font-family: var(--mono); font-size: .78rem; }
.l08-kv div { padding: 4px 8px; border-radius: 6px; background: var(--code-bg); overflow-wrap: anywhere; }
.l08-kv div.hot { background: var(--signal-soft); box-shadow: inset 0 0 0 1px var(--signal); }
.l08-kv div.dim { opacity: .45; }
.l08-verdict { font-weight: 700; padding: 6px 10px; border-radius: 8px; display: inline-block; }
.l08-verdict.ok { background: var(--good-soft); color: var(--good); }
.l08-verdict.no { background: var(--bad-soft); color: var(--bad); }
.l08-chips { display: flex; flex-wrap: wrap; gap: 5px; direction: ltr; }
.l08-chip { font-family: var(--mono); font-size: .74rem; padding: 2px 8px; border-radius: 999px; background: var(--code-bg); border: 1px solid var(--line); overflow-wrap: anywhere; max-width: 100%; }
.l08-chip.pii { background: var(--bad-soft); border-color: var(--bad); color: var(--bad); }
.l08-chip.fin { background: var(--signal-soft); border-color: var(--signal); color: var(--signal); }
.l08-chip.src { background: var(--accent-soft); border-color: var(--accent); color: var(--ink); }
.l08-answer { border-inline-start: 3px solid var(--good); padding: 6px 10px; background: var(--good-soft); border-radius: 0 8px 8px 0; direction: ltr; text-align: left; }
.l08-answer.bad { border-color: var(--bad); background: var(--bad-soft); }
.l08-rows { direction: ltr; font-family: var(--mono); font-size: .76rem; display: grid; gap: 2px; }
.l08-rows div { display: flex; gap: 10px; padding: 2px 6px; border-radius: 4px; background: var(--code-bg); overflow-wrap: anywhere; }
.l08-rows div.h { background: transparent; color: var(--muted); }
.l08-grid2 { display: grid; gap: 12px; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 760px) { .l08-grid2 { grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); } }
.l08 textarea { width: 100%; min-height: 92px; font-family: var(--mono); font-size: .84rem; direction: ltr; text-align: left; background: var(--code-bg); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; resize: vertical; }
.l08 select { max-width: 100%; font: inherit; font-size: .84rem; padding: 5px 8px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); }
.l08-schema { font-family: var(--mono); font-size: .72rem; direction: ltr; text-align: left; display: grid; gap: 6px; }
.l08-schema div { overflow-wrap: anywhere; }
.l08-schema b { color: var(--accent); }
.l08-schema .pii { color: var(--bad); font-weight: 600; }
.l08-schema .fin { color: var(--signal); font-weight: 600; }
.l08-q { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; display: grid; gap: 8px; background: var(--surface); }
.l08-q .qt { direction: ltr; text-align: left; font-weight: 500; }
.l08-q.right { border-color: var(--good); } .l08-q.wrong { border-color: var(--bad); }
.l08-pair { display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 620px) { .l08-pair { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }
.l08-switch { display: flex; gap: 8px; align-items: flex-start; font-size: .88rem; }
.l08-switch input { margin-top: 4px; }
`;
    document.head.append(st);
  }

  /* ================= shared: Acme schema and policy (summary of acme_semantic.yaml) ================= */
  const SCHEMA = {
    employees: ["id", "name", "email", "title", "team", "manager_id", "location", "start_date"],
    teams: ["id", "name", "department", "lead_id", "parent_lead_id", "main_location", "headcount"],
    systems: ["name", "owner_team", "tier", "data_classification", "approved_tool", "kind", "sensitive"],
    access_grants: ["id", "employee_id", "system", "level", "granted_at", "approved_by", "route", "expires_at", "policy_version"],
    customers: ["id", "name", "plan", "region", "seats", "arr_usd", "currency", "red_folder"],
    tickets: ["id", "customer_id", "customer_plan", "subject", "priority", "status", "created_at", "first_response_minutes",
      "sla_target_minutes", "sla_breached", "assigned_team", "red_folder", "incident_id"],
  };
  const SENS = { "employees.email": "pii", "employees.start_date": "pii", "customers.arr_usd": "financial" };
  const ALL = Object.keys(SCHEMA);
  const ROLES = {
    analyst: { tables: ALL, sees: [], d: "כל הטבלאות, בלי PII ובלי נתונים פיננסיים" },
    finance: { tables: ["customers", "tickets", "teams"], sees: ["financial"], d: "לקוחות, קריאות וצוותים, כולל ARR" },
    people_ops: { tables: ALL, sees: ["pii"], d: "כל הטבלאות, כולל PII, בלי ARR" },
  };
  const ROW_LIMIT = 200;

  /* ================= a small SQL guard in JavaScript (the lab uses sqlglot) ================= */
  const KW = new Set(("select from where group by order having limit offset join inner left right full outer cross on as and or not in is null like " +
    "between case when then else end union all intersect except distinct with asc desc exists insert update delete drop create alter pragma " +
    "attach detach replace vacuum reindex into values set table database glob escape cast collate natural using recursive").split(" "));
  const FORBID_KW = new Set(["insert", "update", "delete", "drop", "create", "alter", "pragma", "attach", "detach", "replace", "vacuum", "reindex"]);
  const FORBID_FN = new Set(["load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "randomblob", "zeroblob"]);
  const STOP_FROM = new Set(["where", "group", "order", "limit", "having", "union", "intersect", "except", "on", "join", "inner", "left",
    "right", "full", "cross", "natural", "using", "offset"]);

  function tokenize(sql) {
    const out = []; let i = 0;
    while (i < sql.length) {
      const c = sql[i];
      if (/\s/.test(c)) { i++; continue; }
      if (c === "-" && sql[i + 1] === "-") { while (i < sql.length && sql[i] !== "\n") i++; continue; }
      if (c === "/" && sql[i + 1] === "*") { const j = sql.indexOf("*/", i + 2); i = j < 0 ? sql.length : j + 2; continue; }
      const s = i;
      if (c === "'") { i++; while (i < sql.length) { if (sql[i] === "'" && sql[i + 1] === "'") { i += 2; continue; } if (sql[i] === "'") { i++; break; } i++; } out.push({ t: "str", v: sql.slice(s, i), s, e: i }); continue; }
      if (c === '"' || c === "[" || c === "`") {
        const close = c === "[" ? "]" : c; const j = sql.indexOf(close, i + 1); const e = j < 0 ? sql.length : j + 1;
        out.push({ t: "id", v: sql.slice(i + 1, j < 0 ? sql.length : j).toLowerCase(), q: true, s, e }); i = e; continue;
      }
      if (/[0-9]/.test(c)) { while (i < sql.length && /[0-9.]/.test(sql[i])) i++; out.push({ t: "num", v: sql.slice(s, i), s, e: i }); continue; }
      if (/[A-Za-z_]/.test(c)) { while (i < sql.length && /[A-Za-z0-9_$]/.test(sql[i])) i++; const w = sql.slice(s, i).toLowerCase(); out.push({ t: KW.has(w) ? "kw" : "id", v: w, s, e: i }); continue; }
      if ("();,.*".includes(c)) { out.push({ t: "p", v: c, s, e: i + 1 }); i++; continue; }
      i++; out.push({ t: "op", v: c, s, e: i });
    }
    return out;
  }

  function guard(sql, role) {
    const R = ROLES[role];
    const all = tokenize(sql);
    const stmts = []; let cur = [];
    for (const t of all) { if (t.t === "p" && t.v === ";") { if (cur.length) stmts.push(cur); cur = []; } else cur.push(t); }
    if (cur.length) stmts.push(cur);
    const no = (reason) => ({ ok: false, reason, tables: [], cols: [] });
    if (!stmts.length) return no("SQL does not parse: empty");
    if (stmts.length !== 1) return no(`exactly one statement is allowed, got ${stmts.length}`);
    const T = stmts[0];
    const first = T[0];
    if (!(first.t === "kw" && (first.v === "select" || first.v === "with"))) return no(`only SELECT queries are allowed, got ${first.v.toUpperCase()}`);
    const bad = T.find((t) => t.t === "kw" && FORBID_KW.has(t.v));
    if (bad) return no(`forbidden operation inside the query: ${bad.v.toUpperCase()}`);
    for (let k = 0; k < T.length - 1; k++) {
      if (T[k].t === "id" && T[k + 1].v === "(" && FORBID_FN.has(T[k].v)) return no(`function ${T[k].v}() is not allowed`);
    }
    // CTE names: <id> AS ( preceded by WITH / RECURSIVE / ','
    const ctes = new Set();
    for (let k = 1; k < T.length - 2; k++) {
      if (T[k].t === "id" && T[k + 1].v === "as" && T[k + 2].v === "(" && ["with", "recursive", ","].includes(T[k - 1].v)) ctes.add(T[k].v);
    }
    // scopes: one per SELECT, by parenthesis depth
    const scopes = []; const atDepth = {}; let depth = 0;
    const tokScope = new Array(T.length); const tokDepth = new Array(T.length);
    for (let k = 0; k < T.length; k++) {
      const t = T[k];
      if (t.v === "(" && t.t === "p") depth++;
      else if (t.v === ")" && t.t === "p") { delete atDepth[depth]; depth--; }
      else if (t.t === "kw" && t.v === "select") {
        const sc = { id: scopes.length, depth, tables: [], alias: {}, derived: false, parent: atDepth[depth - 1] || null };
        scopes.push(sc); atDepth[depth] = sc;
      }
      let sd = depth; while (sd >= 0 && !atDepth[sd]) sd--; // inside function parens: the enclosing SELECT
      tokScope[k] = sd >= 0 ? atDepth[sd] : null; tokDepth[k] = depth;
    }
    // table references after FROM / JOIN (and comma lists)
    const used = []; const skip = new Set();
    for (let k = 0; k < T.length; k++) {
      const t = T[k];
      if (!(t.t === "kw" && (t.v === "from" || t.v === "join"))) continue;
      let j = k + 1;
      while (j < T.length) {
        const sc = tokScope[k];
        if (T[j].v === "(") { // derived table: skip to its matching ')', then an optional alias
          let d = 0; for (; j < T.length; j++) { if (T[j].v === "(") d++; else if (T[j].v === ")") { d--; if (d === 0) break; } }
          j++; if (T[j] && T[j].v === "as") j++;
          if (T[j] && T[j].t === "id") { skip.add(j); if (sc) { sc.alias[T[j].v] = null; sc.derived = true; } j++; }
        } else if (T[j].t === "id") {
          const name = T[j].v; skip.add(j);
          if (T[j + 1] && T[j + 1].v === "(") return no("table-valued functions are not allowed");
          if (T[j + 1] && T[j + 1].v === ".") return no(`schema-qualified table ${name}.${(T[j + 2] || {}).v || ""} is not allowed; use the bare table name`);
          j++;
          let alias = name;
          if (T[j] && T[j].v === "as") j++;
          if (T[j] && T[j].t === "id") { alias = T[j].v; skip.add(j); j++; }
          if (ctes.has(name)) { if (sc) { sc.alias[alias] = null; sc.derived = true; } }
          else {
            if (!SCHEMA[name]) return no(`table ${name} does not exist or is not allowed`);
            if (!R.tables.includes(name)) return no(`table ${name} is not allowed for role ${role}`);
            if (!used.includes(name)) used.push(name);
            if (sc) { sc.tables.push(name); sc.alias[alias] = name; sc.alias[name] = name; }
          }
        } else break;
        if (T[j] && T[j].v === ",") { j++; continue; }
        break;
      }
    }
    // column aliases (AS x, not followed by '(') and CTE column lists are names, not reads
    const colAlias = new Set();
    for (let k = 0; k < T.length - 1; k++) if (T[k].v === "as" && T[k + 1].t === "id" && !(T[k + 2] && T[k + 2].v === "(")) { colAlias.add(T[k + 1].v); skip.add(k + 1); }
    for (let k = 0; k < T.length; k++) if (T[k].t === "id" && ctes.has(T[k].v)) skip.add(k);
    const reads = [];
    const addRead = (tab, col) => { const r = `${tab}.${col}`; if (!reads.includes(r)) reads.push(r); };
    const findAlias = (sc, a) => { for (let s = sc; s; s = s.parent) if (a in s.alias) return { hit: true, tab: s.alias[a] }; return { hit: false }; };
    for (let k = 0; k < T.length; k++) {
      const t = T[k]; const sc = tokScope[k];
      if (t.t === "p" && t.v === "*") {
        const prev = T[k - 1];
        if (prev && prev.v === ".") continue; // alias.* handled below
        if (prev && (prev.v === "select" || prev.v === "," || prev.v === "distinct") && sc) {
          for (const tab of sc.tables) for (const c of SCHEMA[tab]) addRead(tab, c);
        }
        continue;
      }
      if (t.t !== "id" || skip.has(k)) continue;
      if (T[k + 1] && T[k + 1].v === "(") continue; // function name
      if (T[k + 1] && T[k + 1].v === ".") { // qualified: a.b or a.*
        const nx = T[k + 2]; const f = findAlias(sc, t.v);
        if (!f.hit) return no(`cannot resolve columns: table or alias '${t.v}' is not in the query`);
        if (f.tab === null) { skip.add(k + 2); continue; } // derived source: checked inside
        if (nx && nx.v === "*") { for (const c of SCHEMA[f.tab]) addRead(f.tab, c); continue; }
        if (nx && nx.t === "id") {
          skip.add(k + 2);
          if (!SCHEMA[f.tab].includes(nx.v)) return no(`unknown column ${f.tab}.${nx.v}`);
          addRead(f.tab, nx.v);
        }
        continue;
      }
      if (colAlias.has(t.v)) continue;
      let found = null; let s = sc; let derived = false;
      for (; s; s = s.parent) {
        const hits = s.tables.filter((tab, i, arr) => arr.indexOf(tab) === i && SCHEMA[tab].includes(t.v));
        derived = derived || s.derived;
        if (hits.length > 1) return no(`cannot resolve columns: Column '${t.v}' could not be resolved (it is in ${hits.join(" and ")})`);
        if (hits.length === 1) { found = hits[0]; break; }
        if (s.derived) break;
      }
      if (found) addRead(found, t.v);
      else if (!derived) return no(`cannot resolve columns: Column '${t.v}' could not be resolved`);
    }
    for (const r of reads) {
      const lvl = SENS[r];
      if (lvl && !R.sees.includes(lvl)) return { ok: false, reason: `column ${r} is ${lvl}; role ${role} may not see it`, tables: used, cols: reads };
    }
    // LIMIT on the outermost query
    let li = -1; for (let k = 0; k < T.length; k++) if (T[k].v === "limit" && tokDepth[k] === 0) li = k;
    const clean = sql.trim().replace(/;\s*$/, "");
    let final = clean; const changes = [];
    if (li < 0) { final = clean + ` LIMIT ${ROW_LIMIT}`; changes.push(`added LIMIT ${ROW_LIMIT}`); }
    else {
      const n = T[li + 1]; const after = T[li + 2];
      if (!n || n.t !== "num" || /\./.test(n.v) || (after && !["offset", ","].includes(after.v))) return { ok: false, reason: "LIMIT must be a plain integer", tables: used, cols: reads };
      if (+n.v > ROW_LIMIT) { final = sql.slice(0, n.s) + ROW_LIMIT + sql.slice(n.e); final = final.trim().replace(/;\s*$/, ""); changes.push(`lowered LIMIT ${n.v} to ${ROW_LIMIT}`); }
    }
    return { ok: true, sql: final, tables: used, cols: reads, changes };
  }

  /* ================= animation: question -> answer with provenance ================= */
  window.AIDS["l08flow"] = function (host) {
    ensureStyle();
    const STEPS = [
      { k: "שאלה", t: "השאלה ומי שואל", body: (w) => `
        <div class="eyebrow">Question</div>
        <div class="prompt-line">How many open P1 tickets do we have right now?</div>
        <div class="eyebrow">User (from login, not from the chat)</div>
        <div class="l08-kv"><div>role = analyst</div><div>may see: all tables, no PII, no financial columns</div></div>`,
        b: "זו שאלה של ספירה ומצב נוכחי, ולכן הנתב שולח אותה לטבלאות ולא למסמכים. התפקיד של המשתמש מגיע מהאימות, והוא יקבע אילו טבלאות ועמודות המודל יראה ואילו השאילתה תוכל לקרוא." },
      { k: "סמנטיקה", t: "שכבת הסמנטיקה נכנסת ל-context", body: (w) => `
        <div class="eyebrow">Rendered context (excerpt, ~1,800 tokens in full)</div>
        <div class="l08-kv">
          <div>### tickets (one row per ticket; pk id) - Zendesk, May-Oct 2026, a 200-ticket extract</div>
          <div>- priority text [values: P1, P2, P3, P4]</div>
          <div>- status text [values: open, pending, solved, closed]</div>
          <div class="${w ? "dim" : "hot"}">${w ? "(business term 'open ticket' missing from this layer)" : "- open ticket (also: unresolved, backlog): tickets.status IN ('open', 'pending')"}</div>
          <div>- open_tickets = COUNT(*) FROM tickets WHERE status IN ('open', 'pending')</div>
        </div>`,
        b: (w) => w ? "במצב הניסוי, המונח העסקי 'open ticket' לא נמצא בשכבה. המודל רואה רק את ערכי ה-enum, ובלי הגדרה, 'open' נשמע כמו status = 'open'." :
          "רק הטבלאות שהתפקיד רשאי לראות נכנסות, עם ערכי ה-enum בתוך השורה. השורה המסומנת היא הקריטית: בדוח של התמיכה, קריאה ב-pending עדיין נחשבת פתוחה. שום דבר בסכמה של ה-DB לא אומר את זה." },
      { k: "SQLPlan", t: "המודל מחזיר אובייקט מובנה", body: (w) => `
        <div class="eyebrow">Structured output: SQLPlan</div>
        <pre>{
  "assumptions": [${w ? '"open means status = \'open\'"' : '"open = open or pending, per the business terms"'}],
  "tables_used": ["tickets"],
  "answerable": true,
  "sql": "SELECT COUNT(*) AS open_p1 FROM tickets WHERE priority = 'P1' AND ${w ? "status = 'open'" : "status IN ('open', 'pending')"}",
  "clarification": null
}</pre>`,
        b: (w) => w ? "המודל כתב SQL תקין לגמרי, וגם הצהיר על ההנחה שלו. השדה assumptions הוא המקום היחיד שבו משתמש יכול לראות שההגדרה לא נכונה." :
          "ההנחות באות לפני ה-SQL, כמו שלמדת בשיעור 3: המודל מתחייב קודם להגדרה, ואז כותב שאילתה שתואמת לה. answerable=true, כי זו שאלה שהטבלאות עונות עליה." },
      { k: "Guard", t: "ה-guard בודק את עץ התחביר", body: (w) => `
        <div class="eyebrow">Guard decision (role analyst)</div>
        <div class="l08-kv"><div>1 statement ✓</div><div>SELECT only ✓</div><div>tables: tickets ✓ allowed</div>
        <div>columns: tickets.priority, tickets.status ✓ none sensitive</div><div class="hot">LIMIT missing → added LIMIT 200</div></div>
        <span class="l08-verdict ok">ACCEPT</span>`,
        b: (w) => "ה-guard בודק מבנה והרשאות: פקודה אחת, רק SELECT, טבלאות ועמודות מותרות, ו-LIMIT. הוא מאשר" + (w ? ", כי ה-SQL תקין ומותר. ה-guard לא יודע מה הארגון מתכוון ב'פתוחה', וזה לא התפקיד שלו." : ". הוא לא בודק אם ההגדרה נכונה, זה התפקיד של שכבת הסמנטיקה ושל ה-eval.") },
      { k: "הרצה", t: "הרצה על חיבור read-only", body: (w) => `
        <div class="eyebrow">Execution: file:acme.db?mode=ro · timeout 2 s · max 200 rows</div>
        <div class="l08-rows"><div class="h"><span>open_p1</span></div><div><span>${w ? 1 : 5}</span></div></div>
        <div class="muted" style="font-size:.85rem">${w ? "1 row matched: T-10190 (open)" : "5 rows matched: T-10190 (open), T-10113, T-10120, T-10123, T-10127 (pending)"}</div>`,
        b: (w) => w ? "השאילתה רצה ומחזירה 1. ארבע הקריאות ב-pending, כולן מתקלת 19 באוגוסט, לא נספרו." :
          "החיבור פתוח read-only, עם progress handler שעוצר שאילתה אחרי 2 שניות, ותקרת שורות. גם אם ה-guard היה מפספס משהו, SQLite עצמו היה מסרב לכתוב." },
      { k: "Provenance", t: "הקוד מחשב את המקור", body: (w) => `
        <div class="eyebrow">Computed by code from what ran (not written by the model)</div>
        <div class="l08-kv"><div>table tickets ← provenance: Zendesk API, object tickets.json</div>
        <div>extracted_at (oldest row) 2026-10-31T23:00:00Z → 10 h old, limit 24 h → fresh</div>
        <div>lineage: SELECT DISTINCT tickets.id FROM tickets WHERE priority = 'P1' AND ${w ? "status = 'open'" : "status IN (...)"}</div></div>`,
        b: "שאילתת השושלת לוקחת את אותם FROM ו-WHERE, ומחזירה את המפתחות של השורות שנספרו. זמן החילוץ מגיע מטבלת provenance ומהשורה הכי ישנה. אם הנתונים היו ישנים מהמגבלה של הטבלה, הייתה כאן אזהרה." },
      { k: "תשובה", t: "התשובה, עם שבבי המקור", body: (w) => `
        <div class="l08-answer ${w ? "bad" : ""}">${w ? "There is 1 open P1 ticket." : "There are 5 open P1 tickets (1 open, 4 pending)."}</div>
        <div class="l08-chips"><span class="l08-chip src">tickets · Zendesk API · extracted 2026-10-31T23:00Z · ${w ? "1 row: T-10190" : "5 rows: T-10190, T-10113, T-10120, T-10123, T-10127"}</span></div>
        <div class="muted" style="font-size:.85rem;direction:ltr;text-align:left">assumptions: ${w ? "open means status = 'open'" : "open = open or pending"}</div>`,
        b: (w) => w ? "תשובה שגויה, עם SQL תקין, guard שאישר ו-provenance מדויק. ה-provenance מראה בדיוק מה נספר, ולכן מנהלת התמיכה יכולה לזהות את הטעות. אבל רק הגדרה כתובה הייתה מונעת אותה, ורק eval מגלה אותה באופן שיטתי." :
          "המשפט נכתב על ידי המודל מתוך השורות. השבב שמתחתיו נכתב על ידי הקוד, ומי שרוצה לבדוק יכול לפתוח את T-10113 ב-Zendesk. ההנחה מוצגת, כדי שאפשר יהיה לראות באיזו הגדרה המערכת השתמשה." },
    ];
    host.innerHTML = `<div class="sim l08">
      <p style="margin:0">שאלה עסקית עוברת שבעה שלבים בדרך לתשובה. לחץ על שלב כדי לקפוץ אליו, או תן לאנימציה לרוץ.</p>
      <div class="l08-steps" id="f-steps">${STEPS.map((s, i) => `<button data-i="${i}"><b>${i + 1}</b>${esc(s.k)}</button>`).join("")}</div>
      <div class="l08-stage" id="f-stage"></div>
      <div class="cap"><b id="f-t"></b><div id="f-b" class="muted"></div></div>
      <div class="row"><button class="btn small primary" id="f-play">השהה</button><button class="btn small" id="f-prev">→</button><button class="btn small" id="f-next">←</button><span class="spacer"></span><span class="counter" id="f-c"></span></div>
      <label class="l08-switch"><input type="checkbox" id="f-what"> <span><b>מה אם המונח העסקי חסר בשכבה?</b> אותה שאלה, בלי ההגדרה ש"פתוחה" כוללת pending.</span></label>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, timer = null, playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    function draw() {
      const w = g("f-what").checked, s = STEPS[i];
      g("f-stage").innerHTML = s.body(w);
      g("f-t").textContent = `${i + 1}. ${s.t}`;
      g("f-b").textContent = typeof s.b === "function" ? s.b(w) : s.b;
      g("f-c").textContent = `${i + 1}/${STEPS.length}`;
      host.querySelectorAll("#f-steps button").forEach((b) => { const k = +b.dataset.i; b.classList.toggle("on", k === i); b.classList.toggle("done", k < i); });
    }
    function tick() { i = (i + 1) % STEPS.length; draw(); }
    function setPlay(p) { playing = p; g("f-play").textContent = p ? "השהה" : "נגן"; clearInterval(timer); if (p) timer = setInterval(tick, 5200); }
    g("f-play").onclick = () => setPlay(!playing);
    g("f-next").onclick = () => { setPlay(false); i = Math.min(STEPS.length - 1, i + 1); draw(); };
    g("f-prev").onclick = () => { setPlay(false); i = Math.max(0, i - 1); draw(); };
    host.querySelectorAll("#f-steps button").forEach((b) => (b.onclick = () => { setPlay(false); i = +b.dataset.i; draw(); }));
    g("f-what").onchange = () => { draw(); };
    draw(); setPlay(playing);
    return () => clearInterval(timer);
  };

  /* ================= sim: SQL guard playground ================= */
  window.AIDS["l08guard"] = function (host) {
    ensureStyle();
    const PRESETS = [
      ["שאילתה רגילה", "SELECT priority, COUNT(*) AS n FROM tickets GROUP BY priority"],
      ["SELECT * על עובדים", "SELECT * FROM employees WHERE team = 'identity'"],
      ["שתי פקודות", "SELECT 1; DROP TABLE tickets"],
      ["PRAGMA", "PRAGMA table_info(employees)"],
      ["קטלוג המערכת", "SELECT * FROM sqlite_master"],
      ["שם עם schema", "SELECT id FROM main.customers"],
      ["סוגריים מרובעים", "SELECT [email] FROM employees"],
      ["alias ופונקציה", "SELECT lower(email) AS team FROM employees"],
      ["תת-שאילתה", "SELECT x FROM (SELECT email AS x FROM employees)"],
      ["PII ב-WHERE", "SELECT COUNT(*) FROM employees WHERE email LIKE 'gil%'"],
      ["UNION", "SELECT id FROM tickets UNION SELECT email FROM employees"],
      ["הערה עם DELETE", "SELECT name FROM employees -- ; DELETE FROM employees"],
      ["ARR", "SELECT SUM(arr_usd) FROM customers WHERE red_folder = 1"],
      ["LIMIT גדול", "SELECT id, subject FROM tickets LIMIT 5000"],
      ["LIMIT שאינו מספר", "SELECT id FROM tickets LIMIT (SELECT 1000000)"],
      ["עמודה שלא קיימת", "SELECT name, role FROM employees"],
      ["join עם בעלים", "SELECT s.name, t.name AS team, e.name AS lead FROM systems s JOIN teams t ON t.id = s.owner_team JOIN employees e ON e.id = t.lead_id WHERE s.tier = 1"],
      ["load_extension", "SELECT load_extension('/tmp/x.so')"],
    ];
    host.innerHTML = `<div class="sim l08">
      <div class="guide"><p><b>מה רואים כאן:</b> משמאל (או למטה בטלפון) יש את הסכמה של acme.db. עמודות PII מסומנות באדום, ועמודות פיננסיות בכתום. מעל יש תיבת SQL ובחירת תפקיד. בכל שינוי, ה-guard מחליט מחדש.</p>
      <p><b>איך לקרוא את התוצאה:</b> ACCEPT או REJECT, עם הסיבה כפי שהיא נשלחת למודל. מתחת מופיעים הטבלאות והעמודות שהשאילתה <b>באמת</b> קוראת, כולל מה שמסתתר מאחורי <code>*</code>, aliases ותת-שאילתות. אם השאילתה התקבלה, מוצג גם ה-SQL שירוץ, עם ה-LIMIT.</p>
      <p><b>שים לב:</b> זו גרסה מפושטת ב-JavaScript שרצה בדפדפן. במעבדה ה-guard מפרסר עם sqlglot, שמבין SQL מלא. כאן יש tokenizer וכללים פשוטים יותר, כך שבמקרי קצה נדירים התשובה יכולה להיות שונה.</p></div>
      <div class="l08-grid2">
        <div class="stack" style="gap:10px">
          <div class="row"><select id="g-pre" aria-label="examples"><option value="">דוגמאות…</option>${PRESETS.map((p, i) => `<option value="${i}">${esc(p[0])}</option>`).join("")}</select></div>
          <textarea id="g-sql" spellcheck="false" aria-label="SQL"></textarea>
          <div class="row"><span style="font-size:.88rem">תפקיד:</span><div class="seg" id="g-role">${Object.keys(ROLES).map((r) => `<button data-r="${r}">${r}</button>`).join("")}</div></div>
          <div class="muted" id="g-roled" style="font-size:.84rem"></div>
          <div id="g-out" class="stack" style="gap:8px"></div>
        </div>
        <div class="card" style="padding:10px;align-self:start;align-content:start"><div class="eyebrow">acme.db schema · row limit ${ROW_LIMIT}</div>
          <div class="l08-schema">${ALL.map((t) => `<div><b>${t}</b>(${SCHEMA[t].map((c) => { const s = SENS[t + "." + c]; return s ? `<span class="${s === "pii" ? "pii" : "fin"}">${c}*</span>` : c; }).join(", ")})</div>`).join("")}
          <div class="muted">* red = pii · orange = financial</div></div></div>
      </div></div>`;
    const ta = host.querySelector("#g-sql");
    let role = "analyst";
    function run() {
      const res = guard(ta.value, role);
      const chips = (res.cols || []).map((c) => { const s = SENS[c]; return `<span class="l08-chip ${s === "pii" ? "pii" : s ? "fin" : ""}">${esc(c)}</span>`; }).join("");
      host.querySelector("#g-out").innerHTML = `
        <div><span class="l08-verdict ${res.ok ? "ok" : "no"}">${res.ok ? "ACCEPT" : "REJECT"}</span></div>
        ${res.ok ? "" : `<div class="prompt-line" style="font-size:.82rem">${esc(res.reason)}</div>`}
        <div class="eyebrow">Tables read</div><div class="l08-chips">${(res.tables || []).map((t) => `<span class="l08-chip">${esc(t)}</span>`).join("") || '<span class="muted">-</span>'}</div>
        <div class="eyebrow">Columns read (after expanding * and aliases)</div><div class="l08-chips">${chips || '<span class="muted">-</span>'}</div>
        ${res.ok ? `<div class="eyebrow">SQL that runs</div><div class="prompt-line" style="font-size:.82rem">${esc(res.sql)}</div>${res.changes.length ? `<div class="muted" style="font-size:.84rem">changes: ${esc(res.changes.join(", "))}</div>` : ""}` : ""}`;
    }
    function setRole(r) { role = r; host.querySelectorAll("#g-role button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.r === r))); host.querySelector("#g-roled").textContent = ROLES[r].d; run(); }
    host.querySelectorAll("#g-role button").forEach((b) => (b.onclick = () => setRole(b.dataset.r)));
    host.querySelector("#g-pre").onchange = (e) => { if (e.target.value !== "") { ta.value = PRESETS[+e.target.value][1]; run(); } };
    let deb = null; ta.addEventListener("input", () => { clearTimeout(deb); deb = setTimeout(run, 150); });
    ta.value = PRESETS[1][1];
    setRole("analyst");
    return () => clearTimeout(deb);
  };

  /* ================= sim: documents or database? ================= */
  window.AIDS["l08route"] = function (host) {
    ensureStyle();
    const OPTS = [["db", "טבלאות"], ["docs", "מסמכים"], ["both", "שניהם"], ["none", "אף אחד"]];
    const QS = [
      { q: "How many open P1 tickets do we have right now?", a: "db", why: "ספירה ומצב נוכחי: tickets, עם ההגדרה ש'פתוחה' היא open או pending. RAG היה מוצא את מסמך הסלמות, שמגדיר P1 אבל לא סופר כלום." },
      { q: "How many vacation days can I carry over to next year?", a: "docs", why: "כלל של מדיניות: hr-vacation-2026 (5 ימים, עד 31 במרץ). אין טבלה כזו, ומודל שנשלח ל-SQL היה כותב משהו, או צריך לסרב. שים לב שיש גם גרסה ישנה מ-2024 עם תשובה אחרת: זו בעיה של שיעורי ה-RAG." },
      { q: "Who leads the team that owns auth-service?", a: "db", why: "systems → teams → employees. המידע מופיע גם ב-eng-service-catalog, אבל בעלות היא מצב נוכחי, ומערכת הרשומה היא המקור המחייב. זה המקרה של 'flow-scheduler': סיכום ישיבה ישן אמר משהו אחר." },
      { q: "Why did the August 19 outage happen?", a: "docs", why: "סיבה, ולכן טקסט: eng-pm-2026-08-api (מאגר חיבורים של auth-service ירד מ-200 ל-20). ב-SQL המודל היה מחזיר נושאים של קריאות מהתקלה, ולא סיבה. לכן ב-SQLPlan יש answerable." },
      { q: "What is the SLA breach rate for enterprise tickets?", a: "db", why: "מדד: sla_breach_rate מתוך שכבת הסמנטיקה, עם הסינון של הקריאות שיש להן יעד. התשובה ב-acme.db היא 0.1591." },
      { q: "What is the first-response target for a P1 ticket from an Enterprise customer?", a: "docs", why: "זה כלל, ו-sup-escalation הוא המקור המחייב (30 דקות, 24/7). העמודה sla_target_minutes היא עותק שחושב מהמסמך. אם המדיניות תשתנה ואף אחד לא יחשב מחדש, העותק יטעה." },
      { q: "Which service caused the August outage, and how many tickets in our data are linked to it?", a: "both", why: "רק ה-postmortem יודע שהשורש היה ב-auth-service. רק tickets יודעת שיש 15 קריאות מקושרות ל-INC-2026-08-19. זה תרגיל 8." },
      { q: "How do I request admin access to AWS production?", a: "docs", why: "נוהל: it-saas-access-v2-2 (מסלול needs_security, בדיקה של 2 ימי עבודה, תפוגה אחרי 90 יום). בטבלת access_grants יש הרשאות שניתנו, לא איך מבקשים." },
      { q: "What will our ARR be next year?", a: "none", why: "תחזית: אין אותה בשום טבלה ובשום מסמך. ב-SQL המודל היה מחזיר SUM(arr_usd) של היום, שהוא מספר אמיתי שעונה על שאלה אחרת. התשובה הנכונה היא סירוב מנומק." },
      { q: "How many support tickets did the August outage generate?", a: "both", why: "הפח: ה-postmortem אומר 203 קריאות, וב-acme.db יש 15. זו לא סתירה: המסמך סופר את כל Zendesk, וה-DB הוא extract של 200 קריאות. תשובה טובה מציגה את שני המספרים ומסבירה." },
      { q: "What is Gil Avraham's salary?", a: "none", why: "נתוני שכר אישיים מסווגים Restricted במדיניות סיווג המידע, ולא נמצאים בשום מקור שהמערכת רואה, וטוב שכך. התשובה הנכונה היא סירוב, ולא 'לא מצאתי'." },
      { q: "What does Red Folder mean, and how many Red Folder customers have open tickets?", a: "both", why: "ההגדרה ב-co-glossary (25 הלקוחות עם ה-ARR הגבוה ביותר). הספירה ב-customers ו-tickets, עם red_folder = 1 ו-status IN ('open', 'pending')." },
    ];
    host.innerHTML = `<div class="sim l08">
      <div class="guide"><p><b>מה רואים כאן:</b> שתים עשרה שאלות שעובדים ב-Acme שואלים. לכל אחת יש ארבעה כפתורים: <b>טבלאות</b> (acme.db), <b>מסמכים</b> (55 המסמכים של Acme), <b>שניהם</b>, או <b>אף אחד</b>, כשהתשובה הנכונה היא סירוב.</p>
      <p><b>איך משחקים:</b> בחר תשובה, וההסבר יופיע מיד: איפה התשובה נמצאת, ומה היה קורה בניתוב שגוי. הציון מתעדכן למטה. אפשר לשנות בחירה.</p></div>
      <div class="stack" id="r-list" style="gap:8px"></div>
      <div class="stats" id="r-score"></div></div>`;
    const list = host.querySelector("#r-list"); const ans = {};
    QS.forEach((x, k) => {
      const el = h(`<div class="l08-q"><div class="row"><b>${k + 1}.</b><span class="qt"></span></div>
        <div class="seg">${OPTS.map(([v, l]) => `<button data-v="${v}">${l}</button>`).join("")}</div><div class="why" hidden></div></div>`);
      el.querySelector(".qt").textContent = x.q;
      el.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
        ans[k] = b.dataset.v;
        el.querySelectorAll(".seg button").forEach((y) => y.setAttribute("aria-pressed", String(y === b)));
        const ok = b.dataset.v === x.a; el.classList.toggle("right", ok); el.classList.toggle("wrong", !ok);
        const w = el.querySelector(".why"); w.hidden = false;
        w.innerHTML = `<b>${ok ? "נכון." : `התשובה: ${OPTS.find((o) => o[0] === x.a)[1]}.`}</b> ${esc(x.why)}`;
        score();
      }));
      list.append(el);
    });
    function score() {
      const done = Object.keys(ans).length, right = Object.entries(ans).filter(([k, v]) => QS[k].a === v).length;
      host.querySelector("#r-score").innerHTML = `<span>נענו: <b>${done}/${QS.length}</b></span><span>נכונים: <b>${right}</b></span>`;
    }
    score();
  };

  /* ================= sim: execution-accuracy judge ================= */
  window.AIDS["l08judge"] = function (host) {
    ensureStyle();
    const PAIRS = [
      { id: "q05", q: "How many employees work in each office?", ordered: false,
        gold: [["Berlin", 13], ["Haifa", 28], ["Tel Aviv", 79]], pred: [[79, "Tel Aviv"], [28, "Haifa"], [13, "Berlin"]],
        sql: "SELECT COUNT(*) AS employees, location FROM employees GROUP BY location", truth: true,
        why: "אותה תשובה, בסדר עמודות אחר. EX משווה תשובות, ולכן מנסה את כל הסידורים של העמודות." },
      { id: "q09", q: "What is our overall SLA breach rate?", ordered: false, gold: [[0.1552]], pred: [[0.135]],
        sql: "SELECT ROUND(1.0 * SUM(sla_breached) / COUNT(*), 4) FROM tickets", truth: false,
        why: "טעות אמיתית: קריאות starter, בלי יעד, נספרו במכנה. ההשוואה תופסת את זה, כי הערכים שונים." },
      { id: "q15", q: "How many tier 1 systems does each team own? Use team names.", ordered: false,
        gold: [["Billing", 1], ["Core API", 1], ["Engine", 2], ["Identity", 1], ["Platform", 2]],
        pred: [["billing", "Billing", 1], ["core-api", "Core API", 1], ["engine", "Engine", 2], ["identity", "Identity", 1], ["platform", "Platform", 2]],
        sql: "SELECT t.id, t.name, COUNT(*) ... GROUP BY t.id, t.name", truth: null,
        why: "השמות והמספרים נכונים, ויש עמודה מיותרת. strict דוחה, lenient מקבל. זו החלטה שצריך לקבל במודע, לפי מה שמשתמש צריך." },
      { id: "q19", q: "How many tickets were created in each month of 2026? (ordered by month)", ordered: true,
        gold: [["2026-05", 30], ["2026-06", 40], ["2026-07", 30], ["2026-08", 38], ["2026-09", 36], ["2026-10", 26]],
        pred: [["2026-06", 40], ["2026-08", 38], ["2026-09", 36], ["2026-05", 30], ["2026-07", 30], ["2026-10", 26]],
        sql: "SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) ... ORDER BY COUNT(*) DESC", truth: false,
        why: "המספרים נכונים, אבל השאלה ביקשה סדר לפי חודש, והמודל מיין לפי כמות. כשהשאלה מבקשת סדר, הסדר הוא חלק מהתשובה." },
      { id: "q18", q: "How many tickets were created in August 2026?", ordered: false, gold: [[38]], pred: [[38]],
        sql: "SELECT COUNT(*) FROM tickets WHERE created_at BETWEEN '2026-08-01' AND '2026-08-31'", truth: false,
        why: "ההשוואה מקבלת, אבל ה-SQL שגוי: created_at כולל שעה, ולכן '2026-08-31T10:00' גדול מ-'2026-08-31' ולא נספר. ב-acme.db פשוט אין קריאות מ-31 באוגוסט. מה היה חושף את זה: עוד מצב של הנתונים, או בדיקה ידנית של ה-SQL." },
      { id: "q22", q: "Which customers opened tickets linked to the June billing incident?", ordered: false,
        gold: [["Granite Retail"], ["Lumen Finance"], ["Delta Foods"], ["Quartz Finance"], ["Summit Labs"], ["Delta Retail"]],
        pred: [["Granite Retail"], ["Lumen Finance"], ["Delta Foods"], ["Lumen Finance"], ["Quartz Finance"], ["Quartz Finance"], ["Summit Labs"], ["Delta Retail"]],
        sql: "SELECT c.name FROM tickets t JOIN customers c ON c.id = t.customer_id WHERE t.incident_id = 'INC-2026-06-03'", truth: false,
        why: "חסר DISTINCT: לקוח עם שתי קריאות מופיע פעמיים. ההשוואה היא multiset, ולכן 8 שורות מול 6 נכשלות. רשימה עם כפילויות היא באמת תשובה גרועה יותר." },
    ];
    const norm = (v) => typeof v === "number" ? Math.round(v * 1e4) / 1e4 : typeof v === "string" ? v.trim() : v;
    const key = (r) => JSON.stringify(r.map(norm));
    function perms(n, k) { const out = []; const rec = (cur, used) => { if (cur.length === k) { out.push(cur.slice()); return; } for (let i = 0; i < n; i++) if (!used[i]) { used[i] = 1; cur.push(i); rec(cur, used); cur.pop(); used[i] = 0; } }; rec([], []); return out; }
    function same(a, b, ordered) {
      if (ordered) return a.every((r, i) => key(r) === key(b[i]));
      const c = {}; a.forEach((r) => (c[key(r)] = (c[key(r)] || 0) + 1)); b.forEach((r) => (c[key(r)] = (c[key(r)] || 0) - 1));
      return Object.values(c).every((x) => x === 0);
    }
    function match(p, g, ordered, extra) {
      if (p.length !== g.length) return false; if (!g.length) return true;
      const pw = p[0].length, gw = g[0].length;
      if (pw < gw || (pw > gw && !extra)) return false;
      return perms(pw, gw).some((cols) => same(p.map((r) => cols.map((i) => r[i])), g, ordered));
    }
    host.innerHTML = `<div class="sim l08">
      <div class="guide"><p><b>מה רואים כאן:</b> שישה זוגות מתוך ה-golden set של המעבדה. בכל זוג יש תוצאת זהב (מימין, או למעלה בטלפון), ותוצאה שהשאילתה של המודל החזירה, עם ה-SQL שלה.</p>
      <p><b>איך משחקים:</b> לכל זוג, החלט אם לדעתך התשובה נכונה. אחרי הבחירה תראה מה ההשוואה האוטומטית אומרת, לפי ההגדרות למטה, ולמה. אחר כך שנה את ההגדרות, וראה איזה זוג משנה תוצאה.</p></div>
      <label class="l08-switch"><input type="checkbox" id="j-extra"> <span><b>עמודות מיותרות מותרות</b> (lenient): תוצאה שמכילה את עמודות הזהב, ועוד עמודות, נחשבת נכונה.</span></label>
      <label class="l08-switch"><input type="checkbox" id="j-order"> <span><b>להתעלם תמיד מסדר השורות</b>, גם כשהשאלה מבקשת סדר.</span></label>
      <div class="stack" id="j-list" style="gap:10px"></div>
      <div class="stats" id="j-score"></div></div>`;
    const list = host.querySelector("#j-list"); const picks = {};
    const rowsHtml = (rows) => `<div class="l08-rows">${rows.map((r) => `<div>${r.map((v) => `<span>${esc(v)}</span>`).join("")}</div>`).join("")}</div>`;
    PAIRS.forEach((p, k) => {
      const el = h(`<div class="l08-q"><div class="row"><b>${esc(p.id)}</b><span class="qt"></span></div>
        <div class="l08-pair"><div><div class="eyebrow">Gold result</div>${rowsHtml(p.gold)}</div><div><div class="eyebrow">Model result</div>${rowsHtml(p.pred)}</div></div>
        <div class="prompt-line" style="font-size:.76rem"></div>
        <div class="row" style="font-size:.88rem"><span>לדעתך:</span><div class="seg"><button data-v="1">נכון</button><button data-v="0">לא נכון</button></div></div>
        <div class="why" hidden></div></div>`);
      el.querySelector(".qt").textContent = p.q;
      el.querySelector(".prompt-line").textContent = p.sql;
      el.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
        picks[k] = +b.dataset.v; el.querySelectorAll(".seg button").forEach((y) => y.setAttribute("aria-pressed", String(y === b))); draw();
      }));
      list.append(el);
    });
    function draw() {
      const extra = host.querySelector("#j-extra").checked, ign = host.querySelector("#j-order").checked;
      let auto = 0;
      PAIRS.forEach((p, k) => {
        const m = match(p.pred, p.gold, p.ordered && !ign, extra); auto += m ? 1 : 0;
        const el = list.children[k], w = el.querySelector(".why");
        if (!(k in picks)) { w.hidden = true; return; }
        w.hidden = false;
        w.innerHTML = `<b>ההשוואה: ${m ? "נכון" : "לא נכון"}.</b> ${p.truth === null ? "" : `ה-SQL עצמו ${p.truth ? "נכון" : "שגוי"}. `}${esc(p.why)}`;
      });
      host.querySelector("#j-score").innerHTML = `<span>execution accuracy לפי ההגדרות: <b>${auto}/${PAIRS.length}</b></span><span>שפטת: <b>${Object.keys(picks).length}/${PAIRS.length}</b></span>`;
    }
    host.querySelector("#j-extra").onchange = draw; host.querySelector("#j-order").onchange = draw;
    draw();
  };

  // exposed for a quick self-test from the console
  window.AIDS.__l08guard = guard;
})();
