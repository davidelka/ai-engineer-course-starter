// Lesson 13 aids: failure funnel animation (l13funnel), diagnosis tree (l13tree),
// claim-level groundedness checker (l13claims). Numbers come from the lab's OFFLINE run
// (labs/13-rag-diagnostics, extractive answerer + lexical judge); claims data from
// fixtures/claims_examples.jsonl. Self-contained; only CSS variables from index.html.
"use strict";
window.AIDS = window.AIDS || {};

(function () {
  const CSS = `
  .l13 { display: grid; gap: 12px; direction: rtl; }
  .l13 .l13-bar { display: flex; flex-wrap: wrap; gap: 4px; }
  .l13 .l13-bar button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 3px 9px; font-size: .78rem; }
  .l13 .l13-bar button.on { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .l13 .l13-bar button.done { color: var(--muted); }
  .l13 .l13-cap { font-size: .9rem; line-height: 1.75; }
  .l13 .l13-cap b.t { display: block; font-size: .98rem; margin-bottom: 2px; }
  .l13 .l13-note { font-size: .78rem; color: var(--muted); line-height: 1.6; }
  .l13 .l13-box { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 6px; min-width: 0; }
  .l13 .l13-box h5 { margin: 0; font-size: .86rem; }
  .l13 .l13-fun { display: grid; gap: 4px; }
  .l13 .l13-frow { display: grid; grid-template-columns: minmax(0, 10.5rem) minmax(0, 1fr) 4.6rem; gap: 6px; align-items: center; font-size: .8rem; transition: opacity .4s; }
  .l13 .l13-frow.off { opacity: .28; }
  .l13 .l13-frow.now .nm { font-weight: 700; color: var(--accent); }
  .l13 .l13-frow .nm { line-height: 1.3; overflow-wrap: anywhere; }
  .l13 .l13-frow .nm small { display: block; color: var(--muted); font-family: var(--mono); font-size: .66rem; direction: ltr; text-align: right; }
  .l13 .l13-track { height: 14px; border-radius: 4px; background: var(--line); position: relative; overflow: hidden; }
  .l13 .l13-track i { position: absolute; top: 0; bottom: 0; right: 0; background: var(--accent); transition: width .6s ease, right .6s ease; }
  .l13 .l13-track i.drop { background: var(--bad); }
  .l13 .l13-track i.okb { background: var(--good); }
  .l13 .l13-frow b { font-family: var(--mono); font-size: .76rem; direction: ltr; text-align: left; white-space: nowrap; }
  .l13 .l13-frow b em { font-style: normal; color: var(--bad); }
  .l13 .l13-dots { display: flex; flex-wrap: wrap; gap: 4px; direction: ltr; }
  .l13 .l13-dot { width: 13px; height: 13px; border-radius: 50%; background: var(--line); transition: background .5s, transform .5s; }
  .l13 .l13-dot.ing { background: var(--signal); }
  .l13 .l13-dot.ret { background: var(--bad); }
  .l13 .l13-dot.gen { background: var(--accent); }
  .l13 .l13-dot.ok { background: var(--good); }
  .l13 .l13-dot.new { transform: scale(1.2); box-shadow: 0 0 0 2px var(--surface); }
  .l13 .l13-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .74rem; color: var(--muted); align-items: center; }
  .l13 .l13-legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-inline-end: 4px; vertical-align: middle; background: var(--line); }
  .l13 .l13-legend span.ing::before { background: var(--signal); }
  .l13 .l13-legend span.ret::before { background: var(--bad); }
  .l13 .l13-legend span.gen::before { background: var(--accent); }
  .l13 .l13-legend span.ok::before { background: var(--good); }
  .l13 .l13-ids { font-family: var(--mono); font-size: .74rem; direction: ltr; text-align: left; overflow-wrap: anywhere; color: var(--muted); }
  .l13 .l13-cmp { display: grid; gap: 6px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .l13 .l13-cmp { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .l13 .l13-cmp ul { margin: 0; padding-inline-start: 18px; font-size: .8rem; line-height: 1.6; }
  .l13 .l13-q { font-size: .92rem; line-height: 1.7; font-weight: 600; }
  .l13 .l13-help { font-size: .82rem; color: var(--muted); line-height: 1.6; }
  .l13 .l13-path { display: grid; gap: 4px; }
  .l13 .l13-step { display: grid; grid-template-columns: 1.4rem minmax(0, 1fr) auto; gap: 6px; align-items: start; font-size: .8rem; line-height: 1.5; border: 1px solid var(--line); border-radius: 8px; padding: 5px 7px; background: var(--surface); }
  .l13 .l13-step .k { font-family: var(--mono); color: var(--muted); }
  .l13 .l13-step .l13-why { display: block; color: var(--muted); font-size: .74rem; }
  .l13 .l13-step button { border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 999px; padding: 1px 9px; font-size: .74rem; white-space: nowrap; }
  .l13 .l13-step button.yes { border-color: var(--good); color: var(--good); }
  .l13 .l13-step button.no { border-color: var(--bad); color: var(--bad); }
  .l13 .l13-res { border-radius: 10px; padding: 10px 12px; display: grid; gap: 6px; line-height: 1.7; font-size: .88rem; }
  .l13 .l13-res.bad { background: var(--bad-soft); border-inline-start: 3px solid var(--bad); }
  .l13 .l13-res.good { background: var(--good-soft); border-inline-start: 3px solid var(--good); }
  .l13 .l13-res code { font-size: .82rem; }
  .l13 .l13-sum { font-size: .82rem; line-height: 1.65; }
  .l13 .l13-sum .ltr { direction: ltr; text-align: left; font-family: var(--mono); font-size: .76rem; overflow-wrap: anywhere; display: block; background: var(--code-bg); border-radius: 6px; padding: 4px 7px; margin-top: 3px; }
  .l13 .l13-ans { direction: ltr; text-align: left; font-size: .84rem; line-height: 1.6; background: var(--code-bg); border-radius: 8px; padding: 7px 10px; overflow-wrap: anywhere; }
  .l13 .l13-claims { display: grid; gap: 4px; }
  .l13 .l13-claim { display: grid; grid-template-columns: 6.4rem minmax(0, 1fr); gap: 6px; align-items: center; text-align: left; direction: ltr; border: 1px solid var(--line); border-radius: 8px; padding: 5px 7px; background: var(--surface); color: var(--ink); font-size: .8rem; line-height: 1.45; cursor: pointer; width: 100%; }
  .l13 .l13-claim.sel { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .l13 .l13-claim span.v { font-family: var(--mono); font-size: .7rem; border-radius: 6px; padding: 2px 5px; text-align: center; font-weight: 600; }
  .l13 .v-supported { background: var(--good-soft); color: var(--good); }
  .l13 .v-contradicted { background: var(--bad-soft); color: var(--bad); }
  .l13 .v-not_found { background: var(--signal-soft); color: var(--signal); }
  .l13 .l13-src { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
  .l13 .l13-src h6 { margin: 0; padding: 4px 8px; font-family: var(--mono); font-size: .72rem; background: var(--code-bg); direction: ltr; text-align: left; }
  .l13 .l13-src div { padding: 6px 8px; font-size: .78rem; line-height: 1.6; white-space: pre-wrap; max-height: 13rem; overflow: auto; overflow-wrap: anywhere; unicode-bidi: plaintext; text-align: start; }
  .l13 .l13-src mark { border-radius: 3px; padding: 0 1px; color: var(--ink); }
  .l13 .l13-src mark.m-supported { background: var(--good-soft); outline: 1px solid var(--good); }
  .l13 .l13-src mark.m-contradicted { background: var(--bad-soft); outline: 1px solid var(--bad); }
  .l13 .l13-score { font-size: .86rem; line-height: 1.7; direction: ltr; text-align: left; }
  .l13 .l13-qltr { direction: ltr; text-align: left; }
  .l13 .l13-score b { font-family: var(--mono); }
  @media (max-width: 480px) { .l13 .l13-frow .nm small { display: none; } .l13 .l13-frow { grid-template-columns: minmax(0, 7.4rem) minmax(0, 1fr) 4.2rem; } .l13 .l13-claim { grid-template-columns: 5.4rem minmax(0, 1fr); } }
  `;
  function style() {
    if (document.getElementById("l13-style")) return;
    const s = document.createElement("style");
    s.id = "l13-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const FUN = {"baseline": {"labels": {"q001": "ok", "q007": "ok", "q011": "ok", "q013": "ok", "q015": "ok", "q016": "ok", "q020": "ok", "q021": "ok", "q022": "ok", "q023": "ok", "q024": "ok", "q025": "ok", "q030": "ok", "q031": "ok", "q032": "ok", "q034": "ok", "q035": "ok", "q036": "ok", "q037": "ok", "q046": "ok", "q049": "ok", "q051": "ok", "q052": "ok", "q053": "ok", "q055": "ok", "q056": "ok", "q057": "ok", "q058": "ok", "q059": "ok", "q060": "ok", "q061": "ok", "q063": "ok", "q064": "ok", "q070": "ok", "q074": "ok", "q078": "ok", "q002": "ignored_context", "q009": "ignored_context", "q012": "ignored_context", "q014": "ignored_context", "q017": "ignored_context", "q019": "ignored_context", "q033": "ignored_context", "q038": "ignored_context", "q041": "ignored_context", "q044": "ignored_context", "q054": "ignored_context", "q065": "ignored_context", "q067": "ignored_context", "q003": "stale_version", "q006": "stale_version", "q008": "stale_version", "q010": "stale_version", "q018": "stale_version", "q027": "stale_version", "q004": "ranked_low", "q040": "ranked_low", "q042": "ranked_low", "q043": "ranked_low", "q048": "ranked_low", "q050": "ranked_low", "q069": "ranked_low", "q005": "wrong_citation", "q026": "false_refusal", "q028": "false_refusal", "q029": "false_refusal", "q045": "false_refusal", "q062": "false_refusal", "q066": "false_refusal", "q039": "not_retrieved", "q047": "not_retrieved", "q068": "not_retrieved", "q071": "failed_to_refuse", "q072": "failed_to_refuse", "q073": "failed_to_refuse", "q075": "failed_to_refuse", "q076": "failed_to_refuse", "q077": "failed_to_refuse", "q079": "failed_to_refuse"}}, "best": {"labels": {"q001": "ok", "q003": "ok", "q004": "ok", "q005": "ok", "q006": "ok", "q007": "ok", "q008": "ok", "q010": "ok", "q011": "ok", "q013": "ok", "q015": "ok", "q016": "ok", "q018": "ok", "q020": "ok", "q021": "ok", "q022": "ok", "q023": "ok", "q024": "ok", "q025": "ok", "q027": "ok", "q030": "ok", "q031": "ok", "q032": "ok", "q034": "ok", "q035": "ok", "q036": "ok", "q037": "ok", "q046": "ok", "q052": "ok", "q053": "ok", "q054": "ok", "q055": "ok", "q056": "ok", "q057": "ok", "q058": "ok", "q059": "ok", "q060": "ok", "q061": "ok", "q063": "ok", "q070": "ok", "q074": "ok", "q078": "ok", "q002": "ignored_context", "q009": "ignored_context", "q012": "ignored_context", "q014": "ignored_context", "q017": "ignored_context", "q019": "ignored_context", "q033": "ignored_context", "q038": "ignored_context", "q041": "ignored_context", "q044": "ignored_context", "q065": "ignored_context", "q067": "ignored_context", "q026": "false_refusal", "q028": "false_refusal", "q029": "false_refusal", "q042": "false_refusal", "q062": "false_refusal", "q064": "false_refusal", "q066": "false_refusal", "q069": "false_refusal", "q039": "ranked_low", "q040": "ranked_low", "q043": "ranked_low", "q045": "ranked_low", "q047": "ranked_low", "q048": "ranked_low", "q049": "ranked_low", "q050": "ranked_low", "q051": "ranked_low", "q068": "ranked_low", "q071": "failed_to_refuse", "q072": "failed_to_refuse", "q073": "failed_to_refuse", "q075": "failed_to_refuse", "q076": "failed_to_refuse", "q077": "failed_to_refuse", "q079": "failed_to_refuse"}}, "fixed": {"labels": {"q001": "stale_version", "q003": "stale_version", "q006": "stale_version", "q007": "stale_version", "q008": "stale_version", "q027": "stale_version", "q002": "ignored_context", "q009": "ignored_context", "q012": "ignored_context", "q014": "ignored_context", "q017": "ignored_context", "q019": "ignored_context", "q033": "ignored_context", "q048": "ignored_context", "q065": "ignored_context", "q067": "ignored_context", "q004": "ranked_low", "q005": "ranked_low", "q040": "ranked_low", "q041": "ranked_low", "q043": "ranked_low", "q069": "ranked_low", "q010": "ok", "q011": "ok", "q013": "ok", "q015": "ok", "q016": "ok", "q018": "ok", "q020": "ok", "q021": "ok", "q022": "ok", "q023": "ok", "q024": "ok", "q025": "ok", "q030": "ok", "q031": "ok", "q034": "ok", "q035": "ok", "q036": "ok", "q037": "ok", "q046": "ok", "q049": "ok", "q052": "ok", "q053": "ok", "q054": "ok", "q055": "ok", "q056": "ok", "q057": "ok", "q059": "ok", "q060": "ok", "q061": "ok", "q063": "ok", "q064": "ok", "q070": "ok", "q074": "ok", "q078": "ok", "q026": "false_refusal", "q028": "false_refusal", "q029": "false_refusal", "q045": "false_refusal", "q062": "false_refusal", "q066": "false_refusal", "q032": "chunk_split", "q038": "chunk_split", "q042": "chunk_split", "q044": "chunk_split", "q050": "chunk_split", "q051": "chunk_split", "q058": "chunk_split", "q068": "chunk_split", "q039": "not_retrieved", "q047": "not_retrieved", "q071": "failed_to_refuse", "q072": "failed_to_refuse", "q073": "failed_to_refuse", "q075": "failed_to_refuse", "q076": "failed_to_refuse", "q077": "failed_to_refuse", "q079": "failed_to_refuse"}}};
  const QTYPE = {"q001": "version_conflict", "q002": "version_conflict", "q003": "version_conflict", "q004": "version_conflict", "q005": "version_conflict", "q006": "version_conflict", "q007": "version_conflict", "q008": "version_conflict", "q009": "version_conflict", "q010": "version_conflict", "q011": "version_conflict", "q012": "numeric", "q013": "numeric", "q014": "numeric", "q015": "numeric", "q016": "numeric", "q017": "numeric", "q018": "numeric", "q019": "numeric", "q020": "numeric", "q021": "single_hop", "q022": "single_hop", "q023": "single_hop", "q024": "single_hop", "q025": "single_hop", "q026": "single_hop", "q027": "single_hop", "q028": "single_hop", "q029": "single_hop", "q030": "single_hop", "q031": "single_hop", "q032": "single_hop", "q033": "single_hop", "q034": "single_hop", "q035": "single_hop", "q036": "single_hop", "q037": "single_hop", "q038": "single_hop", "q039": "single_hop", "q040": "multi_hop", "q041": "multi_hop", "q042": "multi_hop", "q043": "multi_hop", "q044": "multi_hop", "q045": "multi_hop", "q046": "multi_hop", "q047": "multi_hop", "q048": "multi_hop", "q049": "multi_hop", "q050": "multi_hop", "q051": "acronym", "q052": "acronym", "q053": "acronym", "q054": "acronym", "q055": "acronym", "q056": "acronym", "q057": "acronym", "q058": "acronym", "q059": "hebrew", "q060": "hebrew", "q061": "hebrew", "q062": "hebrew", "q063": "hebrew", "q064": "hebrew", "q065": "hebrew", "q066": "hebrew", "q067": "hebrew", "q068": "hebrew", "q069": "hebrew", "q070": "unanswerable", "q071": "unanswerable", "q072": "unanswerable", "q073": "unanswerable", "q074": "unanswerable", "q075": "unanswerable", "q076": "unanswerable", "q077": "unanswerable", "q078": "unanswerable", "q079": "unanswerable"};
  const CLAIMS = [{"id": "e1", "qid": "q003", "question": "What is the minimum password length, and do I have to change my password every 90 days?", "answer": "Passwords must be at least 14 characters long [1]. You must change your password every 90 days [1].", "sources": [{"chunk": "it-password-mfa-2026#0", "text": "# Password and MFA Policy (effective January 15, 2026)\n\nThis policy replaces the June 2024 Password Policy. It follows current guidance (such as NIST SP 800-63B) that long passphrases and strong MFA protect better than frequent forced password changes.\n\n## Scope\n\nEvery account used for Acme work: Okta single sign-on, SaaS tools that do not use Okta, laptop accounts, and service accounts.\n\n## Passwords and passphrases\n\n- Passwords must be at least 14 characters long. We recommend a passphrase of four or more unrelated words.\n- There is no forced periodic rotation. Passwords must be changed immediately if there is any suspicion of compromise, and when Okta reports that the password appears in a known breach list.\n- Passwords must not be reused across accounts, and must not contain the employee's name or the word \"acme\"."}, {"chunk": "it-password-mfa-2026#3", "text": "## Summary of changes from 2024\n\n- Minimum length: from 10 to 14 characters.\n- Forced rotation every 90 days: removed.\n- SMS as a second factor: no longer allowed.\n- 1Password: from recommended to mandatory.\n- Lockout: from 5 attempts and 30 minutes to 10 attempts and 15 minutes."}], "human": [{"claim": "Passwords must be at least 14 characters long", "verdict": "supported", "evidence": "Passwords must be at least 14 characters long", "source": 1}, {"claim": "You must change your password every 90 days", "verdict": "contradicted", "evidence": "There is no forced periodic rotation", "source": 1, "evidence2": ["Forced rotation every 90 days: removed", 2]}], "heur": [{"claim": "Passwords must be at least 14 characters long", "verdict": "supported", "evidence": "- Passwords must be at least 14 characters long.", "source": 1}, {"claim": "You must change your password every 90 days", "verdict": "not_found", "evidence": null, "source": null}], "lesson": "היפוך שלילה: המקור אומר שאין החלפת סיסמה כפויה. הטענה השנייה חולקת עם המקור כמעט את כל המילים, ובגלל זה שופט לקסיקלי לא רואה שהיא הפוכה. הוא מסמן not_found, ולא contradicted."}, {"id": "e2", "qid": "q014", "question": "How long was flow-api fully unavailable on August 19, 2026?", "answer": "flow-api was fully unavailable for 47 minutes [1], from 14:06 to 14:53 Israel time [1]. Outages of this kind usually take about two hours to resolve [1].", "sources": [{"chunk": "eng-pm-2026-08-api#0", "text": "# Postmortem: flow-api outage on August 19, 2026\n\n- **Date of incident:** August 19, 2026\n- **Severity:** SEV1\n- **Duration of full unavailability:** 47 minutes (14:06 to 14:53 Israel time)\n- **Affected service:** flow-api in both regions; root cause in auth-service\n- **Incident commander:** Tomer Shani (core-api-oncall primary)\n- **Reviewed in:** Blue Room, August 27, 2026\n\n## Summary\n\nA configuration change to auth-service reduced its database connection pool from 200 to 20 connections per pod. Token validation requests from flow-api queued behind the small pool and timed out, and flow-api returned errors for 92% of requests at the peak. For 47 minutes the public API, the web app and inbound webhooks were effectively unavailable in both regions. The configuration change skipped the canary stage, because configuration-only changes were not canaried at the time."}, {"chunk": "eng-pm-2026-08-api#2", "text": "## Timeline (Israel time)\n\n- 14:03: An identity engineer merges a configuration change to auth-service intended to set a per-pod connection limit of 200; a typo sets it to 20. Conveyor applies it to both regions in under 2 minutes, without a canary.\n- 14:06: flow-api 5xx rate rises to 92%. Customer-facing outage begins.\n- 14:09: FlowApi5xxRateHigh pages core-api-oncall. Tomer Shani acknowledges at 14:10.\n- 14:15: SEV1 declared, Tomer Shani is incident commander. Status page updated at 14:21.\n- 14:19: No flow-api deploy in the last hour; the error breakdown shows `upstream=auth` timeouts. identity-oncall paged.\n- 14:31: identity-oncall finds the connection pool change in #deploys.\n- 14:41: Rollback of the configuration started with `conveyor rollback auth-service`.\n- 14:49: auth-service pods restarted with the correct pool size; error rate dropping.\n- 14:53: flow-api error rate back to normal. Outage ends.\n- 15:20: Webhook backlog fully replayed."}], "human": [{"claim": "flow-api was fully unavailable for 47 minutes", "verdict": "supported", "evidence": "47 minutes (14:06 to 14:53 Israel time)", "source": 1}, {"claim": "The outage lasted from 14:06 to 14:53 Israel time", "verdict": "supported", "evidence": "47 minutes (14:06 to 14:53 Israel time)", "source": 1}, {"claim": "Outages of this kind usually take about two hours to resolve", "verdict": "not_found", "evidence": null, "source": null}], "heur": [{"claim": "flow-api was fully unavailable for 47 minutes", "verdict": "supported", "evidence": "For 47 minutes the public API, the web app and inbound webhooks were effectively unavailable in both regions.", "source": 1}, {"claim": "from 14:06 to 14:53 Israel time", "verdict": "supported", "evidence": "- **Duration of full unavailability:** 47 minutes (14:06 to 14:53 Israel time)", "source": 1}, {"claim": "Outages of this kind usually take about two hours to resolve", "verdict": "not_found", "evidence": null, "source": null}], "lesson": "ידע של המודל: המשפט האחרון נשמע סביר ויש לו ציטוט [1], אבל שום מקור לא אומר אותו. הציטוט לא הופך אותו ל-grounded."}, {"id": "e3", "qid": "q010", "question": "How much paid leave does the non-birth parent get from Acme?", "answer": "The non-birth parent receives 5 paid days of leave from Acme [1], to be taken within the first 3 months after the birth or adoption [1].", "sources": [{"chunk": "hr-parental-leave-2025#1", "text": "## Non-birth parent (Israel)\n\n- The non-birth parent receives 5 paid days of leave from Acme, to be taken within the first 3 months after the birth or adoption.\n- This is in addition to the statutory paternity days.\n\n## Adoption and surrogacy\n\nAdoptive parents and parents through surrogacy receive the same benefits as birth and non-birth parents above, starting from the date the child joins the family.\n\n## Berlin employees\n\nEmployees of the Berlin office are covered by German parental leave law (Elternzeit and Elterngeld). Acme provides the same 5 paid days for the non-birth parent on top of the statutory entitlement."}], "human": [{"claim": "The non-birth parent receives 5 paid days of leave from Acme", "verdict": "supported", "evidence": "The non-birth parent receives 5 paid days of leave from Acme", "source": 1}, {"claim": "The days must be taken within the first 3 months after the birth or adoption", "verdict": "supported", "evidence": "to be taken within the first 3 months after the birth or adoption", "source": 1}], "heur": [{"claim": "The non-birth parent receives 5 paid days of leave from Acme", "verdict": "supported", "evidence": "- The non-birth parent receives 5 paid days of leave from Acme, to be taken within the first 3 months after the birth or adoption.", "source": 1}, {"claim": "to be taken within the first 3 months after the birth or adoption", "verdict": "supported", "evidence": "- The non-birth parent receives 5 paid days of leave from Acme, to be taken within the first 3 months after the birth or adoption.", "source": 1}], "lesson": "נאמן למקור ושגוי: כל הטענות כתובות בהקשר, אבל ההקשר הוא המדיניות של 2025, שהוחלפה (ב-2026: 15 ימים בתוך 6 חודשים). groundedness בודק מול מה שאוחזר, לא מול האמת. את זה תופס השלב stale_version."}, {"id": "e4", "qid": "q039", "question": "When is the deadline to finish the new-hire security training?", "answer": "The online information security training is mandatory and must be completed within 14 days of starting work [1]. An employee who does not finish it on time loses access to the non-basic tools until it is completed [1].", "sources": [{"chunk": "hr-onboarding-he#1", "text": "## היום הראשון\n\n- העובדים החדשים בתל אביב מתחילים ביום ראשון בשעה 09:30, בקבלה בקומה 6. בחיפה מתחילים ביום ראשון בשעה 09:30 בקומה 3. בברלין מתחילים ביום שני בשעה 10:00.\n- איסוף המחשב הנייד מצוות ה-IT והתחברות ראשונה, כולל הגדרת סיסמה והתקנת אפליקציית האימות הדו-שלבי.\n- ארוחת צהריים עם המנהל והבאדי.\n- מפגש היכרות של שעה עם נציג משאבי אנוש: הטבות, ביטוח בריאות, פנסיה, ימי חופשה.\n\n## השבועיים הראשונים\n\n- הדרכת אבטחת מידע מקוונת היא חובה, ויש להשלים אותה תוך 14 יום מתחילת העבודה. עובד שלא השלים את ההדרכה בזמן יאבד גישה לכלים הלא-בסיסיים עד להשלמה.\n- קריאת מדיניות סיווג המידע ומדיניות השימוש בכלי AI, ואישור בפורטל.\n- עובדי הנדסה: הקמת סביבת פיתוח לפי המדריך ב-Confluence, ופתיחת pull request ראשון עד סוף השבוע השני."}], "human": [{"claim": "The online information security training is mandatory", "verdict": "supported", "evidence": "הדרכת אבטחת מידע מקוונת היא חובה", "source": 1}, {"claim": "It must be completed within 14 days of starting work", "verdict": "supported", "evidence": "יש להשלים אותה תוך 14 יום מתחילת העבודה", "source": 1}, {"claim": "An employee who does not finish on time loses access to non-basic tools until completion", "verdict": "supported", "evidence": "עובד שלא השלים את ההדרכה בזמן יאבד גישה לכלים הלא-בסיסיים עד להשלמה", "source": 1}], "heur": [{"claim": "The online information security training is mandatory and must be completed within 14 days of starting work", "verdict": "not_found", "evidence": null, "source": null}, {"claim": "An employee who does not finish it on time loses access to the non-basic tools until it is completed", "verdict": "not_found", "evidence": null, "source": null}], "lesson": "בין שפות: תשובה באנגלית ממקור בעברית. כל הטענות נתמכות, אבל אין אף מילה משותפת, ולכן השופט הלקסיקלי אומר not_found על הכול. צריך שופט רב-לשוני."}, {"id": "e5", "qid": "q002", "question": "What is the daily per diem for a business trip to a standard (not high-cost) city?", "answer": "The per diem is $85 per day in standard cities [1] and $110 in high-cost cities such as Tokyo [1]. It is paid in cash before the trip [1].", "sources": [{"chunk": "fin-travel-2026#1", "text": "## 3. Hotels\n\nHotel caps per night: up to $210 in standard cities and up to $300 in high-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo). Berlin office visits: employees must stay in the Acme corporate apartment when it is available. When it is not available, the hotel cap in Berlin is 170 EUR per night.\n\n## 4. Per diem\n\nThe per diem covers meals, local transport within the city, and small expenses. It is paid with the salary after the trip, based on the number of days abroad, according to this table:\n\nDestination | Per diem per day\nStandard cities | $85\nHigh-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo) | $110\nBerlin office visits | 65 EUR\n\nThe day of departure and the day of return count as full days when the flight leaves before 12:00 or lands after 18:00 local time; otherwise they count as half days. When meals are provided by a conference or a customer, the per diem for that day is reduced by 30%."}, {"chunk": "fin-travel-2026#2", "text": "## 5. Domestic travel\n\nTrips between Tel Aviv and Haifa: the train is preferred. Private car use is reimbursed per the Business Expenses Policy. Overnight stays in Haifa for workshops: up to 650 NIS per night.\n\n## 6. Insurance and safety\n\nTravel health insurance is purchased centrally by Acme for every approved trip. Travelers to countries on the Security team's high-risk list must request a loaner laptop from IT at least 5 working days before the trip.\n\n## 7. Summary of changes from 2025\n\nPer diem increased from $75 to $85 in standard cities and from $95 to $110 in high-cost cities. Hotel caps increased from $180 to $210 (standard) and from $260 to $300 (high-cost). Premium economy is new for flights over 6 hours, business class for VPs now starts at 8 hours instead of 10, and Tokyo was added to the high-cost list."}], "human": [{"claim": "The per diem is $85 per day in standard cities", "verdict": "supported", "evidence": "Standard cities | $85", "source": 1}, {"claim": "The per diem is $110 in high-cost cities such as Tokyo", "verdict": "supported", "evidence": "High-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo) | $110", "source": 1}, {"claim": "The per diem is paid in cash before the trip", "verdict": "contradicted", "evidence": "It is paid with the salary after the trip", "source": 1}], "heur": [{"claim": "The per diem is $85 per day in standard cities", "verdict": "supported", "evidence": "Per diem increased from $75 to $85 in standard cities and from $95 to $110 in high-cost cities.", "source": 2}, {"claim": "and $110 in high-cost cities such as Tokyo", "verdict": "supported", "evidence": "High-cost cities (London, New York, San Francisco, Zurich, Paris, Tokyo) | $110", "source": 1}, {"claim": "It is paid in cash before the trip", "verdict": "not_found", "evidence": null, "source": null}], "lesson": "טבלה וסתירה: המספרים מגיעים משורות טבלה, והטענה האחרונה סותרת את 'It is paid with the salary after the trip'. השופט הלקסיקלי רואה שהיא לא נתמכת, אבל לא שהיא סותרת."}];

  // ------------------------------------------------------------------ shared taxonomy
  const GROUP = { missing_from_corpus: "ing", extraction_lost: "ing", chunk_split: "ing", not_retrieved: "ret", ranked_low: "ret",
    stale_version: "ret", false_refusal: "gen", lost_in_middle: "gen", ignored_context: "gen", hallucination: "gen",
    wrong_citation: "gen", failed_to_refuse: "gen" };
  const STAGE_HE = {
    missing_from_corpus: "המסמך לא בקורפוס", extraction_lost: "החילוץ איבד את הטקסט", chunk_split: "הראיה נחתכה בין chunks",
    not_retrieved: "לא אוחזר", ranked_low: "אוחזר ונחתך לפני הפרומפט", stale_version: "גרסה מיושנת",
    false_refusal: "סירוב שגוי", lost_in_middle: "אבד באמצע הקשר ארוך", ignored_context: "התעלם מההקשר",
    hallucination: "hallucination (טענות לא נתמכות)", wrong_citation: "ציטוט שגוי", failed_to_refuse: "לא סירב לשאלה בלי תשובה",
  };
  const ROWS = [
    { he: "המסמך בקורפוס", st: ["missing_from_corpus"], step: 1 },
    { he: "הטקסט חולץ", st: ["extraction_lost"], step: 1 },
    { he: "הראיה בתוך chunk אחד", st: ["chunk_split"], step: 1 },
    { he: "בין 50 המועמדים", st: ["not_retrieved"], step: 2 },
    { he: "בפרומפט (5 chunks)", st: ["ranked_low"], step: 3 },
    { he: "הגרסה העדכנית", st: ["stale_version"], step: 4 },
    { he: "ענה ולא סירב", st: ["false_refusal"], step: 5 },
    { he: "כתב את העובדות", st: ["lost_in_middle", "ignored_context"], step: 6 },
    { he: "רק טענות נתמכות", st: ["hallucination"], step: 7 },
    { he: "ציטט נכון", st: ["wrong_citation"], step: 7 },
  ];
  const SCEN = [
    { k: "baseline", he: "baseline (שיעור 9)", sub: "BM25, 5 chunks" },
    { k: "best", he: "best (שיעור 12)", sub: "hybrid, שכתוב, סינון גרסאות" },
    { k: "fixed", he: "chunker שבור", sub: "baseline עם fixed:100:0" },
  ];
  const FSTEPS = [
    { name: "נכנסות", title: "69 שאלות עם תשובה נכנסות לצנרת",
      cap: "כל נקודה היא שאלת זהב אחת שיש לה תשובה בקורפוס. כל השאלות מתחילות אפורות. בכל שלב בודקים שער אחד, ושאלה שהשער הזה הוא שורש הכשל שלה נצבעת ונעצרת שם. 10 השאלות בלי תשובה בקורפוס נבדקות בנפרד, בסוף." },
    { name: "ingestion", title: "שלושת שערי ה-ingestion",
      cap: "האם מסמך המקור בקורפוס, האם ציטוט הזהב שרד את החילוץ, והאם הוא נמצא בשלמותו בתוך chunk אחד. אלה כשלים בלתי נראים בתשובה, ומזהים אותם רק מול ציטוטי הזהב (quote_coverage משיעור 9). עם ה-chunker של ה-baseline אף שאלה לא נופלת כאן. בחר \"chunker שבור\" וראה מה קורה." },
    { name: "מועמדים", title: "בין 50 המועמדים?",
      cap: "חיפוש עמוק אחד מחזיר 50 תוצאות. אם מסמך מקור כלשהו לא ביניהן, הכשל הוא not_retrieved, והתיקון הוא ב-retriever: hybrid, תרגום, embeddings. ב-baseline נופלות כאן שאלות בין שפות, כי ל-BM25 אין אף מילה משותפת עם מסמך בשפה אחרת." },
    { name: "פרומפט", title: "בתוך 5 ה-chunks של הפרומפט?",
      cap: "המסמך נמצא בין המועמדים, אבל לא ב-5 הראשונים, ולכן לא הגיע למודל. זה ranked_low, והתיקון הוא דירוג (reranker), גיוון, או k גדול יותר. רוב הנופלות כאן הן multi-hop: מסמך אחד תופס את כל המקומות, והמסמך השני נדחק החוצה." },
    { name: "גרסה", title: "הגרסה העדכנית?",
      cap: "שתי הגרסאות הגיעו לפרומפט, והתשובה ציטטה את המיושנת (מסומנת stale: בשאלת הזהב). ב-best השער הזה לא מאבד אף שאלה, כי סינון הגרסאות משיעור 12 משמיט את הישנה כשהחדשה ברשימה." },
    { name: "סירוב", title: "ענה, ולא סירב?",
      cap: "הראיה בפרומפט, והמודל כתב \"not in the documents\". שים לב: שאלה שהראיה שלה לא הגיעה לפרומפט נעצרה כבר קודם, כי שם הסירוב נכון. כאן נשארות רק שאלות שבהן הסירוב הוא אשמת המודל. ה-answerer החילוצי מסרב כשאין משפט עם מספיק מילים משותפות, למשל כשהמקור בעברית." },
    { name: "עובדות", title: "כתב את העובדות?",
      cap: "הראיה בפרומפט והמודל ענה, אבל עובדות הזהב חסרות. זו קטגוריית ignored_context (ו-lost_in_middle, כשההקשר ארוך והראיה באמצע). כאן נופלות הכי הרבה שאלות במסלול הלא מקוון, כי ה-answerer מעתיק משפט אחד ולא יודע לשלב מקורות או לקרוא טבלה. עם Haiku המספר הזה צפוי לרדת." },
    { name: "נאמנות", title: "רק טענות נתמכות, וציטוט נכון?",
      cap: "השופט בודק כל טענה מול ההקשר, ואחר כך נבדקים הציטוטים. ה-answerer החילוצי מעתיק משפטים, ולכן כמעט לא נופל ב-hallucination. זה נכון לגבי ה-answerer הזה, לא לגבי מודל אמיתי. בתרגיל 7 תראה מה קורה עם Haiku." },
    { name: "תוצאה", title: "מה נשאר: תשובות נכונות, ו-10 השאלות בלי תשובה",
      cap: "הנקודות הירוקות עברו את כל השערים. מתחת מופיעות 10 השאלות שאין להן תשובה בקורפוס. בהן יש רק שאלה אחת: האם המערכת סירבה. ברוב המקרים היא ענתה בכל זאת, מתוך מסמך שנראה קרוב (near-miss)." },
    { name: "השוואה", title: "שלוש הצנרות, זו לצד זו",
      cap: "מה כל צנרת איבדה בכל קבוצת שלבים. best איבדה פחות באחזור, אבל חלק מהשאלות שעברו את האחזור נפלו בשלב היצירה. כשלים לא נעלמים, הם זזים. בגלל זה מאבחנים לפי שלב, ולא רק סופרים." },
  ];

  function counts(labels) {
    const c = {};
    Object.values(labels).forEach((s) => { c[s] = (c[s] || 0) + 1; });
    return c;
  }
  const ANS = Object.keys(QTYPE).filter((q) => QTYPE[q] !== "unanswerable").sort();
  const UNANS = Object.keys(QTYPE).filter((q) => QTYPE[q] === "unanswerable").sort();

  window.AIDS["l13funnel"] = function (host) {
    style();
    host.innerHTML = `<div class="l13">
      <div class="guide"><p><b>מה רואים:</b> 69 שאלות הזהב שיש להן תשובה, עוברות שער אחרי שער. בכל שורה, <b>הפס הכחול</b> הוא כמה שאלות הגיעו לשער, ו<b>הקטע האדום</b> הוא כמה נפלו בו (השער הוא שורש הכשל שלהן). מתחת, כל נקודה היא שאלה, והיא נצבעת לפי הקבוצה שבה נפלה. השלבים מתקדמים לבד. אפשר לעצור, לדפדף, ולהחליף צנרת בכל רגע. המספרים נמדדו במעבדה, במסלול הלא מקוון.</p></div>
      <div class="seg" id="f-scen"></div>
      <div class="l13-bar" id="f-bar"></div>
      <div class="l13-box"><div class="l13-fun" id="f-rows"></div></div>
      <div class="l13-box"><div class="l13-dots" id="f-dots"></div>
        <div class="l13-legend"><span class="ing">ingestion</span><span class="ret">retrieval</span><span class="gen">generation</span><span class="ok">נכונה</span><span>עוד בצנרת</span></div>
        <div id="f-un"></div></div>
      <div class="l13-cap" id="f-cap"></div>
      <div class="l13-ids" id="f-ids"></div>
      <div class="row"><button class="btn small primary" id="f-play">השהה</button><button class="btn small" id="f-prev" aria-label="שלב קודם">→</button><button class="btn small" id="f-next" aria-label="שלב הבא">←</button><span class="spacer"></span><span class="counter" id="f-c"></span></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let i = 0, scen = "baseline", timer = null, playing = !RM();
    g("f-scen").innerHTML = SCEN.map((s) => `<button data-k="${s.k}" aria-pressed="${s.k === scen}">${s.he}<span class="l13-note"> · ${s.sub}</span></button>`).join("");
    g("f-bar").innerHTML = FSTEPS.map((s, k) => `<button data-k="${k}">${k + 1}. ${s.name}</button>`).join("");
    g("f-dots").innerHTML = ANS.map((q) => `<span class="l13-dot" data-q="${q}" title="${q} (${QTYPE[q]})"></span>`).join("");
    function stepOf(stage) {
      const r = ROWS.find((x) => x.st.includes(stage));
      return r ? r.step : 99;
    }
    function draw() {
      const L = FUN[scen].labels;
      const s = FSTEPS[i];
      // funnel rows
      let left = ANS.length, h = "";
      ROWS.forEach((r) => {
        const drop = ANS.filter((q) => r.st.includes(L[q])).length;
        const on = i >= r.step;
        const pct = (left / ANS.length) * 100, dp = (drop / ANS.length) * 100;
        h += `<div class="l13-frow ${on ? "" : "off"} ${i === r.step ? "now" : ""}"><span class="nm">${r.he}<small>${r.st.join(" / ")}</small></span>
          <span class="l13-track"><i style="width:${on ? pct : 100}%"></i>${on && drop ? `<i class="drop" style="right:${pct - dp}%;width:${dp}%"></i>` : ""}</span>
          <b>${on ? `${left}${drop ? ` <em>−${drop}</em>` : ""}` : "?"}</b></div>`;
        if (on) left -= drop;
      });
      const okN = ANS.filter((q) => L[q] === "ok").length;
      h += `<div class="l13-frow ${i >= 8 ? "" : "off"}"><span class="nm"><b style="font-family:inherit">נכונות</b><small>ok</small></span><span class="l13-track"><i class="okb" style="width:${i >= 8 ? (okN / ANS.length) * 100 : 0}%"></i></span><b>${i >= 8 ? okN + "/69" : "?"}</b></div>`;
      g("f-rows").innerHTML = h;
      // dots
      host.querySelectorAll(".l13-dot").forEach((d) => {
        const st = L[d.dataset.q];
        const k = st === "ok" ? 8 : stepOf(st);
        d.className = "l13-dot" + (i >= k ? " " + (st === "ok" ? "ok" : GROUP[st]) : "") + (i === k && i < 9 ? " new" : "");
        d.title = `${d.dataset.q} (${QTYPE[d.dataset.q]})` + (i >= k ? `: ${st}` : "");
      });
      // unanswerable
      if (i >= 8) {
        const fr = UNANS.filter((q) => L[q] === "failed_to_refuse");
        g("f-un").innerHTML = `<div class="l13-note" style="margin-top:6px">10 השאלות בלי תשובה: סירבה ב-${10 - fr.length}, ענתה בכל זאת (failed_to_refuse) ב-${fr.length}</div>
          <div class="l13-dots">${UNANS.map((q) => `<span class="l13-dot ${L[q] === "ok" ? "ok" : "gen"}" title="${q}: ${L[q]}"></span>`).join("")}</div>`;
      } else g("f-un").innerHTML = "";
      // caption and ids
      let ids = "";
      if (i >= 1 && i <= 7) {
        const rows = ROWS.filter((r) => r.step === i);
        ids = rows.map((r) => {
          const qs = ANS.filter((q) => r.st.includes(L[q]));
          return `${r.st.join("/")}: ${qs.length ? qs.map((q) => `${q} (${QTYPE[q]})`).join(", ") : "none"}`;
        }).join("<br>");
      } else if (i === 8) {
        ids = "failed_to_refuse: " + UNANS.filter((q) => L[q] === "failed_to_refuse").join(", ");
      }
      g("f-ids").innerHTML = ids;
      let cap = `<b class="t">${s.title}</b>${s.cap}`;
      if (i === 9) {
        cap += `<div class="l13-cmp">` + SCEN.map((sc) => {
          const c = counts(FUN[sc.k].labels);
          const grp = { ing: 0, ret: 0, gen: 0 };
          Object.entries(c).forEach(([st, n]) => { if (GROUP[st] && st !== "failed_to_refuse") grp[GROUP[st]] += n; });
          return `<div class="l13-box"><h5>${sc.he}</h5><ul><li>נכונות: <b>${c.ok || 0}/79</b></li><li>ingestion: ${grp.ing}</li><li>retrieval: ${grp.ret}</li><li>generation: ${grp.gen}</li><li>לא סירבה: ${c.failed_to_refuse || 0}/10</li></ul></div>`;
        }).join("") + `</div>`;
      }
      g("f-cap").innerHTML = cap;
      g("f-c").textContent = `${i + 1}/${FSTEPS.length}`;
      host.querySelectorAll("#f-bar button").forEach((b, k) => { b.classList.toggle("on", k === i); b.classList.toggle("done", k < i); });
      host.querySelectorAll("#f-scen button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === scen)));
      g("f-play").textContent = playing ? "השהה" : "הפעל";
      clearTimeout(timer);
      if (playing) timer = setTimeout(() => { i = (i + 1) % FSTEPS.length; draw(); }, i === 0 ? 6500 : 9000);
    }
    g("f-play").addEventListener("click", () => { playing = !playing; draw(); });
    g("f-prev").addEventListener("click", () => { playing = false; i = (i + FSTEPS.length - 1) % FSTEPS.length; draw(); });
    g("f-next").addEventListener("click", () => { playing = false; i = (i + 1) % FSTEPS.length; draw(); });
    host.querySelectorAll("#f-bar button").forEach((b) => b.addEventListener("click", () => { playing = false; i = +b.dataset.k; draw(); }));
    host.querySelectorAll("#f-scen button").forEach((b) => b.addEventListener("click", () => { scen = b.dataset.k; draw(); }));
    draw();
    return () => clearTimeout(timer);
  };

  // ------------------------------------------------------------------ diagnosis tree
  const NODES = {
    ans: { q: "האם יש לשאלה תשובה בקורפוס?", help: "בשאלת הזהב יש source_ids. אם הרשימה ריקה, השאלה נועדה לבדוק סירוב.", yes: "pass", no: "refused" },
    refused: { q: "האם המערכת סירבה (\"not in the documents\")?", help: "לשאלה בלי תשובה אין צנרת לאבחן: או שסירבה, או שענתה מתוך משהו שנראה קרוב.", yes: "R:ok_unans", no: "R:failed_to_refuse" },
    pass: { q: "האם התשובה עברה?", help: "עוברת אם: לא סירבה, כיסוי העובדות 0.5 לפחות, לא צוטט מסמך מיושן, השופט לא מצא טענה לא נתמכת, צוטט מסמך מקור, ואין [n] מומצא.", yes: "R:ok", no: "doc" },
    doc: { q: "האם מסמך המקור נמצא בקורפוס?", help: "ציטוט הזהב מסומן no_doc כשהמסמך לא נקלט בכלל.", yes: "ext", no: "R:missing_from_corpus" },
    ext: { q: "האם ציטוט הזהב נמצא בטקסט שחולץ מהמסמך?", help: "missing: המסמך באינדקס, אבל הטקסט לא שרד את החילוץ (טבלת PDF, עמוד שנפל, extractor של HTML).", yes: "chunk", no: "R:extraction_lost" },
    chunk: { q: "האם הציטוט נמצא בשלמותו בתוך chunk אחד?", help: "split: הטקסט במסמך, אבל כל chunk מכיל רק חלק ממנו.", yes: "cand", no: "R:chunk_split" },
    cand: { q: "האם כל מסמכי המקור בין המועמדים (50 התוצאות)?", help: "בשאלת multi-hop, מספיק שמסמך אחד חסר.", yes: "prompt", no: "R:not_retrieved" },
    prompt: { q: "האם כל מסמכי המקור בפרומפט (k הראשונים)?", help: "נמצא בין המועמדים, אבל נחתך לפני שהגיע למודל.", yes: "stale", no: "R:ranked_low" },
    stale: { q: "האם התשובה ציטטה גרסה מיושנת?", help: "מסמך שמסומן stale:<id> בשאלת הזהב, למשל hr-vacation-2024.", yes: "R:stale_version", no: "refuse2" },
    refuse2: { q: "האם המודל סירב?", help: "הראיה בפרומפט (בדקנו), ובכל זאת \"not in the documents\".", yes: "R:false_refusal", no: "facts" },
    facts: { q: "האם עובדות הזהב חסרות בתשובה?", help: "כיסוי העובדות (לקסיקלי) מתחת ל-0.5.", yes: "unsup1", no: "unsup2" },
    unsup1: { q: "האם השופט מצא טענות לא נתמכות?", help: "עובדות חסרות, ובמקומן טענות שלא כתובות בשום מקור.", yes: "R:hallucination", no: "middle" },
    middle: { q: "האם ההקשר ארוך (4,000 טוקנים ומעלה) והראיה רק באמצע?", help: "כל מקומות הראיה הם לא הראשון ולא האחרון בפרומפט.", yes: "R:lost_in_middle", no: "R:ignored_context" },
    unsup2: { q: "האם השופט מצא טענות לא נתמכות?", help: "העובדות שם, אבל נוספו טענות שלא נתמכות.", yes: "R:hallucination", no: "R:wrong_citation" },
  };
  const RES = {
    ok: { good: true, t: "ok: התשובה עברה", b: "אין מה לאבחן. אם אתה חושב שהתשובה בכל זאת שגויה, אולי הבדיקה (כיסוי עובדות לקסיקלי, שופט) פספסה. פתח את ה-trace." },
    ok_unans: { good: true, t: "ok: סירוב נכון", b: "לשאלה אין תשובה בקורפוס, והמערכת אמרה זאת." },
    failed_to_refuse: { lesson: "4, 9", b: "לשאלה אין תשובה, והמערכת ענתה, בדרך כלל מתוך מסמך near-miss (ARR של 2024 כשהשאלה על 2023).", fix: "בדיקת מספיקות לפני התשובה, כלל סירוב מפורש ל-near-miss, ו-selective generation.", m: "abstain_ok על השאלות בלי תשובה עולה." },
    missing_from_corpus: { lesson: "8, 9", b: "המסמך לא באינדקס, ולכן שום שלב אחר לא יכול לעזור.", fix: "להוסיף את המקור ל-ingestion (connector, היקף, הרשאות). ואם המסמך לא אמור להיות שם, שאלת הזהב שגויה.", m: "no_doc הופך ל-covered ב-quote_coverage." },
    extraction_lost: { lesson: "9", b: "המסמך באינדקס, אבל הטקסט החשוב לא שרד את החילוץ. הסימפטום לרוב נראה אחר, למשל גרסה מיושנת, כי המודל עונה ממה שכן קיבל.", fix: "להחליף loader לפורמט (מצב PDF, extractor של HTML, טבלאות), ולהריץ ingestion מחדש רק על המסמכים שהשתנו.", m: "missing הופך ל-covered." },
    chunk_split: { lesson: "9", b: "הראיה נחתכה בין שני chunks. המודל קיבל חצי, ולעיתים השלים את החצי השני מהדמיון.", fix: "chunks גדולים יותר או עם חפיפה, chunker לפי מבנה (כותרות, טבלה שלמה), או parent-document retrieval.", m: "split הופך ל-covered." },
    not_retrieved: { lesson: "10, 12", b: "ה-retriever לא מצא את המסמך גם ב-50 התוצאות.", fix: "hybrid (BM25 ו-dense עם RRF), שכתוב שאילתה (תרגום, פירוק ל-multi-hop), כותרות הקשר ל-chunks.", m: "recall ב-50 וב-k עולה." },
    ranked_low: { lesson: "12", b: "המסמך נמצא, אבל דורג נמוך ונחתך. ב-multi-hop, לרוב מסמך אחד תפס את כל המקומות.", fix: "reranker על 30 עד 50 המועמדים, גיוון (לכל היותר 2 chunks לכל מסמך), או k גדול יותר. k גדול מדי יכול ליצור lost_in_middle.", m: "MRR ו-recall@k עולים, והמועמדים לא משתנים." },
    stale_version: { lesson: "12", b: "שתי הגרסאות בפרומפט, והתשובה בחרה בישנה.", fix: "VersionAwareRetriever (drop_superseded לפי supersedes), וכלל בפרומפט שמעדיף את effective_date המאוחר.", m: "stale@5 וציטוטים מיושנים יורדים." },
    false_refusal: { lesson: "4, 9", b: "הראיה בפרומפט, והמודל סירב. זה קורה בעיקר כשהראיה בשפה אחרת, בטבלה, או מנוסחת אחרת.", fix: "פרומפט שמגדיר מה נחשב \"נמצא\" (פרפרזה, שורת טבלה, שפה אחרת), והמקור הטוב ביותר ראשון.", m: "abstain_ok עולה." },
    lost_in_middle: { lesson: "4, 12", b: "הראיה הייתה באמצע הקשר ארוך, והתשובה פספסה אותה (עקומת ה-U של Liu et al.).", fix: "פחות chunks וטובים יותר (rerank ואז חיתוך), המקור החזק ראשון ואחרון, דחיסת ההקשר.", m: "כיסוי העובדות עולה באותו אחזור." },
    ignored_context: { lesson: "4", b: "הראיה בפרומפט, ההקשר קצר, המודל ענה, והעובדות לא בתשובה.", fix: "פרומפט שדורש לענות על כל חלק של השאלה, הוראות ל-multi-hop, ומודל חזק יותר לסינתזה.", m: "כיסוי העובדות עולה." },
    hallucination: { lesson: "4, 7", b: "בתשובה יש טענות שלא כתובות בשום מקור: המודל השלים מהידע שלו.", fix: "כלל \"רק מהמקורות\", בדיקת groundedness לפני שליחה (לולאת האימות של שיעור 7), temperature נמוך.", m: "groundedness עולה." },
    wrong_citation: { lesson: "9", b: "התוכן נכון ונתמך, והציטוטים מצביעים על מקור אחר, או על מקור שלא קיים.", fix: "ציטוט לכל משפט, בדיקת [n] בקוד, או ציטוטים מקוריים של Claude.", m: "citation precision ו-citation recall עולים." },
  };
  const PRESETS = {
    T1: { sum: "q002: מה האש\"ל היומי בעיר רגילה? הזהב: fin-travel-2026 ($85). שני ה-PDF נטענו עם loader חדש. ב-chunk 2 בפרומפט כתוב \"according to this table:\" ואין טבלה, והציטוט מסומן missing.", ans: "The per diem for a standard city is $75 per day [1]. (cites fin-travel-2025)",
      a: { ans: [1, "יש source_ids: fin-travel-2026"], pass: [0, "צוטט fin-travel-2025, שמסומן stale"], doc: [1, "fin-travel-2026 בקורפוס"], ext: [0, "הציטוט missing: הטבלה והעמוד השני לא חולצו"], chunk: [1, "אילו החילוץ היה תקין"], cand: [1, "fin-travel-2026 שני במועמדים"], prompt: [1, "chunk 2 בפרומפט"], stale: [1, "צוטט fin-travel-2025"] } },
    T2: { sum: "q052: מתי deploys חסומים בגלל Quiet Hours? chunker של fixed:100:0. ה-chunk של המילון נגמר במילה \"until\".", ans: "... and on the eve of an Israeli public holiday from 15:00 until midnight [1].",
      a: { ans: [1, "שני מקורות: eng-deploy-process, co-glossary"], pass: [0, "השופט: \"until midnight\" not_found"], doc: [1, "בקורפוס"], ext: [1, "הציטוט בטקסט שחולץ"], chunk: [0, "ההגדרה נחתכה אחרי \"until\": split"], cand: [1, "שניהם במועמדים"], prompt: [1, "שניהם בפרומפט"], stale: [0, "אין גרסה מיושנת"], refuse2: [0, "ענה"], facts: [0, "כיסוי העובדות 1.0"], unsup2: [1, "\"until midnight\" לא נתמך"] } },
    T3: { sum: "q040, multi-hop: איזה צוות אחראי על השירות שגרם לתקלה של אוגוסט? המקורות: ה-postmortem וקטלוג השירותים. בפרומפט: 4 chunks של ה-postmortem ו-1 של ה-deploy.", ans: "The outage was caused by a configuration change to auth-service [1]. The sources do not say who owns auth-service ...",
      a: { ans: [1, "שני מקורות"], pass: [0, "כיסוי העובדות 0.25"], doc: [1, "בקורפוס"], ext: [1, "חולץ"], chunk: [1, "covered"], cand: [1, "הקטלוג הוא המסמך הרביעי במועמדים"], prompt: [0, "הקטלוג לא ב-5 ה-chunks"], stale: [0, "אין"], refuse2: [0, "ענה"], facts: [1, "רק עובדה אחת מארבע"], unsup1: [0, "כל הטענות נתמכות"], middle: [0, "1,202 טוקנים בלבד"] } },
    T4: { sum: "q039: מתי צריך לסיים את הדרכת האבטחה? המקור: hr-onboarding-he (בעברית). הצנרת best שמה אותו במקום השני בפרומפט.", ans: "not in the documents",
      a: { ans: [1, "יש מקור"], pass: [0, "סירב"], doc: [1, "בקורפוס"], ext: [1, "חולץ"], chunk: [1, "covered"], cand: [1, "במועמדים"], prompt: [1, "מקום 2 בפרומפט"], stale: [0, "אין"], refuse2: [1, "\"not in the documents\""] } },
    T5: { sum: "q015: מה מגבלת ה-API לתוכנית Business? dense עם k=20, הפרומפט כ-4,100 טוקנים. שורת המגבלה בטבלה ב-chunk מספר 8.", ans: "For the Business plan, overage costs $6 per additional 1,000 runs [8] ... The sources do not give the API rate limit.",
      a: { ans: [1, "יש מקורות"], pass: [0, "כיסוי העובדות 0"], doc: [1, "בקורפוס"], ext: [1, "חולץ"], chunk: [1, "covered"], cand: [1, "במועמדים"], prompt: [1, "k=20: בפרומפט"], stale: [0, "אין"], refuse2: [0, "ענה (סירוב חלקי)"], facts: [1, "המגבלה חסרה"], unsup1: [0, "שלוש הטענות נתמכות"], middle: [1, "4,141 טוקנים, הראיה במקום 8 מתוך 20"] } },
    T6: { sum: "q014: כמה זמן flow-api לא היה זמין? ה-postmortem ראשון בפרומפט, עם \"47 minutes\".", ans: "flow-api was down for about two hours [1], which is typical for SEV1 incidents at Acme [1] ...",
      a: { ans: [1, "יש מקור"], pass: [0, "עובדות חסרות, טענות לא נתמכות"], doc: [1, "בקורפוס"], ext: [1, "חולץ"], chunk: [1, "covered"], cand: [1, "במועמדים"], prompt: [1, "מקום 1"], stale: [0, "אין"], refuse2: [0, "ענה"], facts: [1, "47 דקות חסר"], unsup1: [1, "\"about two hours\" נסתר, השאר not_found"] } },
  };

  window.AIDS["l13tree"] = function (host) {
    style();
    host.innerHTML = `<div class="l13">
      <div class="guide"><p><b>איך משתמשים:</b> בחר אחד מששת ה-traces של המעבדה, או \"מקרה משלי\" כדי לענות בעצמך. העץ שואל שאלות כן/לא לפי סדר הצנרת, ועוצר בתשובת ה\"לא\" הראשונה (או ב\"כן\" שמצביע על כשל). ב-trace טעון, כל צעד מראה את התשובה ואת הנימוק מתוך הנתונים. לחיצה על התשובה בצעד כלשהו הופכת אותה, וכך אפשר לבדוק \"מה אם\". בסוף מוצגים השלב, ההסבר, התיקון ואיך מודדים אותו.</p></div>
      <div class="seg" id="t-pre"></div>
      <div class="l13-box l13-sum" id="t-sum"></div>
      <div class="l13-path" id="t-path"></div>
      <div id="t-ask"></div>
      <div id="t-res"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let pre = "T1", answers = {};
    const keys = ["T1", "T2", "T3", "T4", "T5", "T6", "own"];
    g("t-pre").innerHTML = keys.map((k) => `<button data-k="${k}" aria-pressed="false">${k === "own" ? "מקרה משלי" : k}</button>`).join("");
    function load(k) {
      pre = k;
      answers = {};
      if (k !== "own") Object.entries(PRESETS[k].a).forEach(([n, [v, why]]) => { answers[n] = { v: !!v, why, preset: true }; });
      draw();
    }
    function draw() {
      host.querySelectorAll("#t-pre button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === pre)));
      g("t-sum").innerHTML = pre === "own" ? "<b>מקרה משלך:</b> ענה על כל שאלה לפי מה שאתה יודע על הכשל. אפשר לחזור ולהפוך כל תשובה." :
        `<b><bdi>${pre}</bdi></b> · ${esc(PRESETS[pre].sum)}<span class="ltr">${esc(PRESETS[pre].ans)}</span>`;
      let node = "ans", n = 0, h = "", res = null;
      while (node) {
        if (node.startsWith("R:")) { res = node.slice(2); break; }
        const a = answers[node];
        if (!a) break;
        n++;
        h += `<div class="l13-step"><span class="k">${n}</span><span>${NODES[node].q}${a.why ? `<span class="l13-why">${esc(a.why)}</span>` : ""}</span><button data-n="${node}" class="${a.v ? "yes" : "no"}" aria-label="הפוך תשובה">${a.v ? "כן" : "לא"}</button></div>`;
        node = a.v ? NODES[node].yes : NODES[node].no;
      }
      g("t-path").innerHTML = h;
      if (!res && node) {
        const nd = NODES[node];
        g("t-ask").innerHTML = `<div class="l13-box"><div class="l13-q">${n + 1}. ${nd.q}</div><div class="l13-help">${nd.help}</div>
          <div class="row"><button class="btn small" data-a="1">כן</button><button class="btn small" data-a="0">לא</button></div></div>`;
        g("t-ask").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { answers[node] = { v: b.dataset.a === "1", why: "" }; draw(); }));
        g("t-res").innerHTML = "";
      } else {
        g("t-ask").innerHTML = "";
        const r = RES[res];
        if (r.good) g("t-res").innerHTML = `<div class="l13-res good"><b>${r.t}</b><span>${r.b}</span></div>`;
        else g("t-res").innerHTML = `<div class="l13-res bad"><b>שורש הבעיה: <code>${res}</code> (${STAGE_HE[res]})</b><span>${r.b}</span>
          <span><b>התיקון (שיעור ${r.lesson}):</b> ${r.fix}</span><span><b>איך יודעים שעבד:</b> ${r.m}</span></div>`;
      }
      host.querySelectorAll("#t-path button").forEach((b) => b.addEventListener("click", () => {
        const a = answers[b.dataset.n];
        answers[b.dataset.n] = { v: !a.v, why: a.preset ? "(הפכת את התשובה)" : "" };
        draw();
      }));
    }
    host.querySelectorAll("#t-pre button").forEach((b) => b.addEventListener("click", () => load(b.dataset.k)));
    load("T1");
    return () => {};
  };

  // ------------------------------------------------------------------ claim checker
  function markText(text, spans) {
    // spans: [{s, cls}] -> escaped text with <mark> around the first occurrence of each span
    const hits = [];
    spans.forEach((sp) => {
      if (!sp.s) return;
      let at = text.indexOf(sp.s);
      let s = sp.s;
      if (at < 0 && s.startsWith("- ")) { s = s.slice(2); at = text.indexOf(s); }
      if (at >= 0 && !hits.some((h) => at < h.e && at + s.length > h.a)) hits.push({ a: at, e: at + s.length, cls: sp.cls });
    });
    hits.sort((x, y) => x.a - y.a);
    let out = "", p = 0;
    hits.forEach((h) => { out += esc(text.slice(p, h.a)) + `<mark class="${h.cls}">` + esc(text.slice(h.a, h.e)) + "</mark>"; p = h.e; });
    return out + esc(text.slice(p));
  }

  window.AIDS["l13claims"] = function (host) {
    style();
    host.innerHTML = `<div class="l13">
      <div class="guide"><p><b>מה רואים:</b> תשובה אחת, מפורקת לטענות. כל טענה מסומנת לפי פסק הדין: <span class="v-supported">supported</span> (המקור אומר אותה), <span class="v-contradicted">contradicted</span> (המקור אומר משהו אחר) או <span class="v-not_found">not_found</span> (המקור לא מכריע). לחיצה על טענה מדגישה את הראיה שלה בטקסט המקור שמתחת. המתג מחליף שופט: <b>אדם</b> (תוויות שנכתבו ביד) או <b>לקסיקלי</b> (הפלט האמיתי של השופט הלא מקוון של המעבדה). את Haiku תריץ בתרגיל 3.</p></div>
      <div class="seg" id="c-ex"></div>
      <div class="seg" id="c-judge"><button data-j="human" aria-pressed="true">אדם</button><button data-j="heur" aria-pressed="false">שופט לקסיקלי (לא מקוון)</button></div>
      <div class="l13-q" id="c-q"></div>
      <div class="l13-ans" id="c-ans"></div>
      <div class="l13-claims" id="c-claims"></div>
      <div class="l13-score" id="c-score"></div>
      <div id="c-src" style="display:grid;gap:6px"></div>
      <div class="callout l13-cap" id="c-lesson"></div>
    </div>`;
    const g = (id) => host.querySelector("#" + id);
    let ex = 0, judge = "human", sel = 0;
    g("c-ex").innerHTML = CLAIMS.map((e, k) => `<button data-k="${k}" aria-pressed="${k === 0}">${e.id} (${e.qid})</button>`).join("");
    function draw() {
      const e = CLAIMS[ex];
      const list = e[judge];
      host.querySelectorAll("#c-ex button").forEach((b, k) => b.setAttribute("aria-pressed", String(k === ex)));
      host.querySelectorAll("#c-judge button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.j === judge)));
      g("c-q").innerHTML = `<div class="l13-qltr">${esc(e.question)}</div>`;
      g("c-ans").textContent = e.answer;
      if (sel >= list.length) sel = 0;
      g("c-claims").innerHTML = list.map((c, k) => `<button class="l13-claim ${k === sel ? "sel" : ""}" data-k="${k}"><span class="v v-${c.verdict}">${c.verdict}</span><span>${esc(c.claim)}</span></button>`).join("");
      const sup = list.filter((c) => c.verdict === "supported").length;
      const score = list.length ? sup / list.length : null;
      const label = score === null ? "grounded" : score === 1 ? "grounded" : score === 0 ? "not_grounded" : "partially_grounded";
      const other = judge === "human" ? e.heur : e.human;
      const os = other.length ? other.filter((c) => c.verdict === "supported").length / other.length : 1;
      g("c-score").innerHTML = `faithfulness = ${sup}/${list.length} = <b>${score === null ? "-" : score.toFixed(2)}</b>, label <b>${label}</b>
        <span class="l13-note"> · other judge: ${os.toFixed(2)}</span>`;
      const c = list[sel] || {};
      g("c-src").innerHTML = e.sources.map((s, k) => {
        const spans = [];
        if (c.source === k + 1 && c.evidence) spans.push({ s: c.evidence, cls: c.verdict === "contradicted" ? "m-contradicted" : "m-supported" });
        if (c.evidence2 && c.evidence2[1] === k + 1) spans.push({ s: c.evidence2[0], cls: "m-contradicted" });
        return `<div class="l13-src"><h6>[${k + 1}] ${esc(s.chunk)}</h6><div>${markText(s.text, spans)}</div></div>`;
      }).join("") + `<div class="l13-note">${c.evidence ? "הראיה של הטענה שנבחרה מודגשת במקור." : "לטענה שנבחרה אין ראיה במקורות (not_found)."}</div>`;
      host.querySelectorAll(".l13-src div").forEach((d) => { const m = d.querySelector("mark"); if (m) d.scrollTop = Math.max(0, m.offsetTop - d.offsetTop - 30); });
      g("c-lesson").innerHTML = `<b>הלקח של ${e.id}:</b> ${esc(e.lesson)}`;
      host.querySelectorAll(".l13-claim").forEach((b) => b.addEventListener("click", () => { sel = +b.dataset.k; draw(); }));
    }
    host.querySelectorAll("#c-ex button").forEach((b) => b.addEventListener("click", () => { ex = +b.dataset.k; sel = 0; draw(); }));
    host.querySelectorAll("#c-judge button").forEach((b) => b.addEventListener("click", () => { judge = b.dataset.j; draw(); }));
    draw();
    return () => {};
  };
})();
