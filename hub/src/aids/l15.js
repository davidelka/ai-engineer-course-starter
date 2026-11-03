// Lesson 15 aids: the agent loop animation (live scratchpad, tool calls, budget meter, repetition and
// no-progress stops), a trajectory explorer over recorded agentkit runs, and a stop-policy simulator.
// Loaded before the main script; uses its helpers ($, h, esc) at call time.
"use strict";
window.AIDS = window.AIDS || {};

// Recorded with agentkit (labs/15-agent-loops), November 2026. Fake model = AcmeHeuristic, tokens estimated.
const L15_TRAJS = [{"key": "t01-react", "title": "t01 Dana, reactive (fake model)", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "fake-haiku", "mode": "react", "steps": [{"n": 1, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2147, "tout": 27, "cost": 0.000228, "cum": 0.000228, "decision": "continue", "detail": ""}, {"n": 2, "think": "I need the approval route from the policy.", "final": "", "gave_up": "", "calls": [{"name": "check_policy", "args": "{\"system\": \"aws-production\", \"access_level\": \"admin\", \"external_sharing\": false, \"holds_c…", "fp": "b8a8fb"}], "results": [{"err": false, "text": "{\"system\": \"aws-production\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": true, \"access_level\": \"admin\", …", "h": "4a5788"}], "tin": 2246, "tout": 51, "cost": 0.00025, "cum": 0.000478, "decision": "continue", "detail": ""}, {"confirm": "create_access_request", "approved": true}, {"n": 3, "think": "The policy check is done, so I will file the request (a human must confirm).", "final": "", "gave_up": "", "calls": [{"name": "create_access_request", "args": "{\"employee\": \"dana.levi@acme.example\", \"system\": \"aws-production\", \"access_level\": \"admin…", "fp": "562502"}], "results": [{"err": false, "text": "{\"id\": \"AR-00001\", \"idempotency_key\": \"dana.levi@acme.example:aws-production:admin\", \"payload_hash\": \"e7d4d47506f4a022\"…", "h": "71f7e9"}], "tin": 2389, "tout": 103, "cost": 0.00029, "cum": 0.000769, "decision": "continue", "detail": ""}, {"n": 4, "think": "", "final": "Dana Levi (E016) reports to Michal Ben-David (E005). check_policy: admin on aws-production routes to needs_security (security review within 2 business days). Filed AR-00001: route needs_security, status pending_security, approver security-team, expires 2026-1…", "gave_up": "", "calls": [], "results": [], "tin": 2649, "tout": 74, "cost": 0.000302, "cum": 0.001071, "decision": "final_answer", "detail": "the model answered without asking for tools"}], "plans": [], "stop": "final_answer", "detail": "the model answered without asking for tools", "text": "Dana Levi (E016) reports to Michal Ben-David (E005). check_policy: admin on aws-production routes to needs_security (security review within 2 business days). Filed AR-00001: route needs_security, status pending_security, approver security-team, expires 2026-11-04.", "cost": 0.001071, "tin": 9431, "tout": 255, "ncalls": 3, "gold": {"success": true, "reasons": [], "redundant": 0, "eff": 1.0}}, {"key": "t01-plan", "title": "t01 Dana, plan-then-act (fake model)", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "fake-haiku", "mode": "plan", "steps": [{"n": 1, "think": "I need the employee record and manager; I need the approval route from the policy.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}, {"name": "check_policy", "args": "{\"system\": \"aws-production\", \"access_level\": \"admin\", \"external_sharing\": false, \"holds_c…", "fp": "b8a8fb"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}, {"err": false, "text": "{\"system\": \"aws-production\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": true, \"access_level\": \"admin\", …", "h": "4a5788"}], "tin": 2295, "tout": 71, "cost": 0.000402, "cum": 0.000402, "decision": "continue", "detail": ""}, {"confirm": "create_access_request", "approved": true}, {"n": 2, "think": "The policy check is done, so I will file the request (a human must confirm).", "final": "", "gave_up": "", "calls": [{"name": "create_access_request", "args": "{\"employee\": \"dana.levi@acme.example\", \"system\": \"aws-production\", \"access_level\": \"admin…", "fp": "562502"}], "results": [{"err": false, "text": "{\"id\": \"AR-00001\", \"idempotency_key\": \"dana.levi@acme.example:aws-production:admin\", \"payload_hash\": \"e7d4d47506f4a022\"…", "h": "71f7e9"}], "tin": 2538, "tout": 103, "cost": 0.000305, "cum": 0.000708, "decision": "continue", "detail": ""}, {"n": 3, "think": "", "final": "Dana Levi (E016) reports to Michal Ben-David (E005). check_policy: admin on aws-production routes to needs_security (security review within 2 business days). Filed AR-00001: route needs_security, status pending_security, approver security-team, expires 2026-1…", "gave_up": "", "calls": [], "results": [], "tin": 2797, "tout": 74, "cost": 0.000317, "cum": 0.001024, "decision": "final_answer", "detail": "the model answered without asking for tools"}], "plans": [{"rev": 0, "reason": "", "steps": ["Call lookup_employee to get the facts [lookup_employee]", "Call check_policy to get the facts [check_policy]", "File the request if the checks allow it [create_access_request]", "Answer the user with the facts found"], "after": 0}], "stop": "final_answer", "detail": "the model answered without asking for tools", "text": "Dana Levi (E016) reports to Michal Ben-David (E005). check_policy: admin on aws-production routes to needs_security (security review within 2 business days). Filed AR-00001: route needs_security, status pending_security, approver security-team, expires 2026-11-04.", "cost": 0.001024, "tin": 8202, "tout": 408, "ncalls": 3, "gold": {"success": true, "reasons": [], "redundant": 0, "eff": 1.0}}, {"key": "t01-repeat", "title": "t01 with a looping model: repetition stop", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "fake-haiku", "mode": "react", "steps": [{"n": 1, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2147, "tout": 27, "cost": 0.000228, "cum": 0.000228, "decision": "continue", "detail": ""}, {"n": 2, "think": "Let me check the employee again.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2246, "tout": 26, "cost": 0.000238, "cum": 0.000466, "decision": "continue", "detail": ""}, {"n": 3, "think": "Let me check the employee again.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2344, "tout": 26, "cost": 0.000247, "cum": 0.000713, "decision": "repetition", "detail": "lookup_employee called 3 times with identical arguments (limit 3)"}], "plans": [], "stop": "repetition", "detail": "lookup_employee called 3 times with identical arguments (limit 3)", "text": "Stopped before finishing (repetition: lookup_employee called 3 times with identical arguments (limit 3)).", "cost": 0.000713, "tin": 6737, "tout": 79, "ncalls": 3, "gold": {"success": false, "reasons": ["stopped: repetition", "missing tool: check_policy", "missing tool: create_access_request", "expected 1 request, got 0", "answer lacks 'Michal Ben-David'", "answer lacks 'needs_security'"], "redundant": 2, "eff": 1.0}}, {"key": "t01-para", "title": "t01 with a paraphrasing loop: no_progress stop", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "fake-haiku", "mode": "react", "steps": [{"n": 1, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2147, "tout": 27, "cost": 0.000228, "cum": 0.000228, "decision": "continue", "detail": ""}, {"n": 2, "think": "Let me double-check that record.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"dana.levi@acme.example\"}", "fp": "20ca4f"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2246, "tout": 29, "cost": 0.000239, "cum": 0.000467, "decision": "continue", "detail": ""}, {"n": 3, "think": "Let me double-check that record.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"E016\"}", "fp": "d0247a"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2347, "tout": 24, "cost": 0.000247, "cum": 0.000714, "decision": "continue", "detail": ""}, {"n": 4, "think": "Let me double-check that record.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2443, "tout": 26, "cost": 0.000257, "cum": 0.000971, "decision": "no_progress", "detail": "no new information in the last 3 steps"}], "plans": [], "stop": "no_progress", "detail": "no new information in the last 3 steps", "text": "Stopped before finishing (no_progress: no new information in the last 3 steps).", "cost": 0.000971, "tin": 9183, "tout": 106, "ncalls": 4, "gold": {"success": false, "reasons": ["stopped: no_progress", "missing tool: check_policy", "missing tool: create_access_request", "expected 1 request, got 0", "answer lacks 'Michal Ben-David'", "answer lacks 'needs_security'"], "redundant": 1, "eff": 0.75}}, {"key": "t05-plan", "title": "t05 Shani (ambiguous), plan mode with a replan", "task": "Shani needs a Notion member account. Open a request for her.", "model": "fake-haiku", "mode": "plan", "steps": [{"n": 1, "think": "I need the employee record and manager; I need the approval route from the policy.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Shani\"}", "fp": "59f307"}, {"name": "check_policy", "args": "{\"system\": \"notion\", \"access_level\": \"member\", \"external_sharing\": false, \"holds_customer…", "fp": "2ff870"}], "results": [{"err": true, "text": "4 employees are named 'Shani': Shani Barzilai <shani.barzilai@acme.example> (product), Shani Sasson <shani.sasson@acme.…", "h": ""}, {"err": false, "text": "{\"system\": \"notion\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": false, \"access_level\": \"member\", \"route…", "h": "fb72af"}], "tin": 2244, "tout": 68, "cost": 0.000384, "cum": 0.000384, "decision": "continue", "detail": ""}, {"n": 2, "think": "", "final": "I found several people named Shani: Shani Barzilai, Shani Sasson, Shani Shapiro, Shani Alon. Which one do you mean? I have not filed anything.", "gave_up": "", "calls": [], "results": [], "tin": 2406, "tout": 43, "cost": 0.000386, "cum": 0.00077, "decision": "final_answer", "detail": "the model answered without asking for tools"}], "plans": [{"rev": 0, "reason": "", "steps": ["Call lookup_employee to get the facts [lookup_employee]", "Call check_policy to get the facts [check_policy]", "File the request if the checks allow it [create_access_request]", "Answer the user with the facts found"], "after": 0}, {"rev": 1, "reason": "1 of 2 call(s) in step 1 failed: 4 employees are named 'Shani': Shani Barzilai <shani.barzilai@acme.example> (product), Shani Sasson <shani…", "steps": ["Explain the problem and ask the user which person they mean"], "after": 1}], "stop": "final_answer", "detail": "the model answered without asking for tools", "text": "I found several people named Shani: Shani Barzilai, Shani Sasson, Shani Shapiro, Shani Alon. Which one do you mean? I have not filed anything.", "cost": 0.00077, "tin": 6128, "tout": 315, "ncalls": 2, "gold": {"success": true, "reasons": [], "redundant": 0, "eff": 0.5}}, {"key": "t01-keep1", "title": "t01 with keep_tool_results=1 and no notes: it forgets", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "fake-haiku", "mode": "react", "steps": [{"n": 1, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2147, "tout": 27, "cost": 0.000228, "cum": 0.000228, "decision": "continue", "detail": ""}, {"n": 2, "think": "I need the approval route from the policy.", "final": "", "gave_up": "", "calls": [{"name": "check_policy", "args": "{\"system\": \"aws-production\", \"access_level\": \"admin\", \"external_sharing\": false, \"holds_c…", "fp": "b8a8fb"}], "results": [{"err": false, "text": "{\"system\": \"aws-production\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": true, \"access_level\": \"admin\", …", "h": "4a5788"}], "tin": 2246, "tout": 51, "cost": 0.00025, "cum": 0.000478, "decision": "continue", "detail": ""}, {"trim": 1}, {"n": 3, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2342, "tout": 27, "cost": 0.000248, "cum": 0.000726, "decision": "continue", "detail": ""}, {"trim": 1}, {"n": 4, "think": "I need the approval route from the policy.", "final": "", "gave_up": "", "calls": [{"name": "check_policy", "args": "{\"system\": \"aws-production\", \"access_level\": \"admin\", \"external_sharing\": false, \"holds_c…", "fp": "b8a8fb"}], "results": [{"err": false, "text": "{\"system\": \"aws-production\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": true, \"access_level\": \"admin\", …", "h": "4a5788"}], "tin": 2374, "tout": 51, "cost": 0.000263, "cum": 0.000989, "decision": "continue", "detail": ""}, {"trim": 1}, {"n": 5, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2470, "tout": 27, "cost": 0.00026, "cum": 0.001249, "decision": "repetition", "detail": "lookup_employee called 3 times with identical arguments (limit 3)"}], "plans": [], "stop": "repetition", "detail": "lookup_employee called 3 times with identical arguments (limit 3)", "text": "Stopped before finishing (repetition: lookup_employee called 3 times with identical arguments (limit 3)).", "cost": 0.001249, "tin": 11579, "tout": 183, "ncalls": 5, "gold": {"success": false, "reasons": ["stopped: repetition", "missing tool: create_access_request", "expected 1 request, got 0", "answer lacks 'Michal Ben-David'", "answer lacks 'needs_security'"], "redundant": 3, "eff": 0.6}}, {"key": "t01-transient", "title": "t01, lookup_employee fails once (transient)", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "fake-haiku", "mode": "react", "steps": [{"n": 1, "think": "I need the employee record and manager.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": true, "text": "lookup_employee is temporarily unavailable (upstream 503). Try again in a moment.", "h": ""}], "tin": 2147, "tout": 27, "cost": 0.000228, "cum": 0.000228, "decision": "continue", "detail": ""}, {"n": 2, "think": "lookup_employee failed (lookup_employee is temporarily unavailable (upstream 503). T). Retrying once.", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"Dana Levi\"}", "fp": "4b4d93"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2187, "tout": 43, "cost": 0.00024, "cum": 0.000468, "decision": "continue", "detail": ""}, {"n": 3, "think": "I need the approval route from the policy.", "final": "", "gave_up": "", "calls": [{"name": "check_policy", "args": "{\"system\": \"aws-production\", \"access_level\": \"admin\", \"external_sharing\": false, \"holds_c…", "fp": "b8a8fb"}], "results": [{"err": false, "text": "{\"system\": \"aws-production\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": true, \"access_level\": \"admin\", …", "h": "4a5788"}], "tin": 2302, "tout": 51, "cost": 0.000256, "cum": 0.000724, "decision": "continue", "detail": ""}, {"confirm": "create_access_request", "approved": true}, {"n": 4, "think": "The policy check is done, so I will file the request (a human must confirm).", "final": "", "gave_up": "", "calls": [{"name": "create_access_request", "args": "{\"employee\": \"dana.levi@acme.example\", \"system\": \"aws-production\", \"access_level\": \"admin…", "fp": "562502"}], "results": [{"err": false, "text": "{\"id\": \"AR-00001\", \"idempotency_key\": \"dana.levi@acme.example:aws-production:admin\", \"payload_hash\": \"e7d4d47506f4a022\"…", "h": "71f7e9"}], "tin": 2445, "tout": 103, "cost": 0.000296, "cum": 0.00102, "decision": "continue", "detail": ""}, {"n": 5, "think": "", "final": "Dana Levi (E016) reports to Michal Ben-David (E005). check_policy: admin on aws-production routes to needs_security (security review within 2 business days). Filed AR-00001: route needs_security, status pending_security, approver security-team, expires 2026-1…", "gave_up": "", "calls": [], "results": [], "tin": 2704, "tout": 74, "cost": 0.000307, "cum": 0.001328, "decision": "final_answer", "detail": "the model answered without asking for tools"}], "plans": [], "stop": "final_answer", "detail": "the model answered without asking for tools", "text": "Dana Levi (E016) reports to Michal Ben-David (E005). check_policy: admin on aws-production routes to needs_security (security review within 2 business days). Filed AR-00001: route needs_security, status pending_security, approver security-team, expires 2026-11-04.", "cost": 0.001328, "tin": 11785, "tout": 298, "ncalls": 4, "gold": {"success": true, "reasons": [], "redundant": 0, "eff": 0.75}}, {"key": "t11-stale", "title": "t11, read_document returns the stale v2.1 policy", "task": "According to the SaaS access policy document, how long do security reviews take, and when do security-track grants expire? Name the document id.", "model": "fake-haiku", "mode": "react", "steps": [{"n": 1, "think": "I need the document text.", "final": "", "gave_up": "", "calls": [{"name": "read_document", "args": "{\"doc_id\": \"it-saas-access-v2-2\"}", "fp": "ed7ca2"}], "results": [{"err": false, "text": "{\"id\": \"it-saas-access-v2-2\", \"title\": \"SaaS Access Policy\", \"effective_date\": null, \"classification\": \"internal\", \"tex…", "h": "bbd7fe"}], "tin": 2132, "tout": 25, "cost": 0.000226, "cum": 0.000226, "decision": "continue", "detail": ""}, {"n": 2, "think": "", "final": "From it-saas-access-v2-2: - Manager approvals are expected within 2 business days. - Security reviews are completed within 3 business days.", "gave_up": "", "calls": [], "results": [], "tin": 2664, "tout": 42, "cost": 0.000287, "cum": 0.000513, "decision": "final_answer", "detail": "the model answered without asking for tools"}], "plans": [], "stop": "final_answer", "detail": "the model answered without asking for tools", "text": "From it-saas-access-v2-2: - Manager approvals are expected within 2 business days. - Security reviews are completed within 3 business days.", "cost": 0.000513, "tin": 4796, "tout": 67, "ncalls": 1, "gold": {"success": false, "reasons": ["answer lacks '90 days'"], "redundant": 0, "eff": 1.0}}, {"key": "t01-mock-declined", "title": "t01 on mockllm, human declines: the mock retries", "task": "Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her manager, what does the policy say, and open the request (it goes to whatever track the policy requires).", "model": "mock-model", "mode": "react", "steps": [{"n": 1, "think": "", "final": "", "gave_up": "", "calls": [{"name": "lookup_employee", "args": "{\"employee\": \"dana.levi@acme.example\"}", "fp": "20ca4f"}], "results": [{"err": false, "text": "{\"id\": \"E016\", \"name\": \"Dana Levi\", \"email\": \"dana.levi@acme.example\", \"title\": \"Engineering Team Lead\", \"team\": \"engin…", "h": "47c49b"}], "tin": 2200, "tout": 21, "cost": 0.00023, "cum": 0.00023, "decision": "continue", "detail": ""}, {"n": 2, "think": "", "final": "", "gave_up": "", "calls": [{"name": "check_policy", "args": "{\"system\": \"aws-production\", \"access_level\": \"admin\", \"external_sharing\": false, \"holds_c…", "fp": "b8a8fb"}], "results": [{"err": false, "text": "{\"system\": \"aws-production\", \"known_system\": true, \"approved_tool\": false, \"sensitive\": true, \"access_level\": \"admin\", …", "h": "4a5788"}], "tin": 2366, "tout": 41, "cost": 0.000257, "cum": 0.000488, "decision": "continue", "detail": ""}, {"confirm": "create_access_request", "approved": false}, {"n": 3, "think": "", "final": "", "gave_up": "", "calls": [{"name": "create_access_request", "args": "{\"employee\": \"dana.levi@acme.example\", \"system\": \"aws-production\", \"access_level\": \"admin…", "fp": "82c7c3"}], "results": [{"err": true, "text": "The human reviewer DECLINED this action, so it was NOT executed. Do not call it again. Tell the user that the request w…", "h": ""}], "tin": 2568, "tout": 67, "cost": 0.00029, "cum": 0.000778, "decision": "continue", "detail": ""}, {"confirm": "create_access_request", "approved": false}, {"n": 4, "think": "", "final": "", "gave_up": "", "calls": [{"name": "create_access_request", "args": "{\"employee\": \"dana.levi@acme.example\", \"system\": \"aws-production\", \"access_level\": \"admin…", "fp": "82c7c3"}], "results": [{"err": true, "text": "The human reviewer DECLINED this action, so it was NOT executed. Do not call it again. Tell the user that the request w…", "h": ""}], "tin": 2728, "tout": 67, "cost": 0.000306, "cum": 0.001084, "decision": "continue", "detail": ""}, {"confirm": "create_access_request", "approved": false}, {"n": 5, "think": "", "final": "", "gave_up": "", "calls": [{"name": "create_access_request", "args": "{\"employee\": \"dana.levi@acme.example\", \"system\": \"aws-production\", \"access_level\": \"admin…", "fp": "82c7c3"}], "results": [{"err": true, "text": "The human reviewer DECLINED this action, so it was NOT executed. Do not call it again. Tell the user that the request w…", "h": ""}], "tin": 2888, "tout": 67, "cost": 0.000322, "cum": 0.001406, "decision": "repetition", "detail": "create_access_request called 3 times with identical arguments (limit 3)"}], "plans": [], "stop": "repetition", "detail": "create_access_request called 3 times with identical arguments (limit 3)", "text": "Stopped before finishing (repetition: create_access_request called 3 times with identical arguments (limit 3)).", "cost": 0.001406, "tin": 12750, "tout": 263, "ncalls": 5, "gold": {"success": false, "reasons": ["stopped: repetition", "missing tool: create_access_request", "expected 1 request, got 0", "answer lacks 'Michal Ben-David'", "answer lacks 'needs_security'"], "redundant": 0, "eff": 0.6}}];

(function addL15Style() {
  if (document.getElementById("l15-style")) return;
  const st = document.createElement("style");
  st.id = "l15-style";
  st.textContent = `
  .l15 { display: grid; gap: 12px; min-width: 0; }
  .l15 p { margin: 0; line-height: 1.7; }
  .l15 .ltr { direction: ltr; text-align: left; unicode-bidi: isolate; }
  .l15 .l15i, .l15i { direction: ltr; unicode-bidi: isolate; display: inline; }
  .l15-ring { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; direction: ltr; }
  .l15-ring > div { border: 1px solid var(--line); border-radius: 10px; padding: 8px 4px; text-align: center; font-size: .8rem;
    background: var(--surface); transition: all .25s; min-width: 0; overflow-wrap: anywhere; }
  .l15-ring > div b { display: block; font-size: .95rem; }
  .l15-ring > div.on { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .l15-ring > div.stop { border-color: var(--bad); background: var(--bad-soft); }
  .l15-ring > div.done { border-color: var(--good); background: var(--good-soft); }
  .l15-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 10px; }
  @media (max-width: 640px) { .l15-grid { grid-template-columns: minmax(0, 1fr); } }
  .l15-pad { direction: ltr; text-align: left; font-family: var(--mono); font-size: .74rem; line-height: 1.5; background: var(--code-bg);
    border: 1px solid var(--line); border-radius: 10px; padding: 8px; height: 300px; overflow: auto; min-width: 0; }
  .l15-pad div { padding: 2px 4px; border-radius: 4px; overflow-wrap: anywhere; white-space: pre-wrap; }
  .l15-pad .sys { color: var(--muted); }
  .l15-pad .usr { color: var(--ink); font-weight: 600; }
  .l15-pad .thk { color: var(--accent); }
  .l15-pad .act { color: var(--signal); }
  .l15-pad .obs { color: var(--good); }
  .l15-pad .err { color: var(--bad); }
  .l15-pad .cnf { color: var(--bad); font-weight: 600; }
  .l15-pad .fin { color: var(--ink); background: var(--good-soft); }
  .l15-pad .new { outline: 1px solid var(--accent); background: var(--accent-soft); }
  .l15-meters { display: grid; gap: 8px; align-content: start; min-width: 0; }
  .l15-meter { display: grid; gap: 3px; }
  .l15-meter .lbl { display: flex; justify-content: space-between; gap: 6px; font-size: .8rem; }
  .l15-meter .lbl span:last-child { direction: ltr; font-family: var(--mono); }
  .l15-meter .bar { height: 12px; background: var(--code-bg); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
  .l15-meter .bar i { display: block; height: 100%; width: 0; background: var(--accent); transition: width .35s; }
  .l15-meter.hot .bar i { background: var(--bad); }
  .l15-meter.warm .bar i { background: var(--signal); }
  .l15-cap { border-inline-start: 3px solid var(--signal); padding: 6px 12px; background: var(--surface); border-radius: 0 8px 8px 0; min-height: 64px; }
  .l15-dec { padding: 8px 12px; border-radius: 10px; border: 1px solid var(--line); font-size: .9rem; }
  .l15-dec.ok { border-color: var(--good); background: var(--good-soft); }
  .l15-dec.bad { border-color: var(--bad); background: var(--bad-soft); }
  .l15-steps { display: grid; gap: 8px; }
  .l15-step { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--surface); display: grid; gap: 4px; min-width: 0; }
  .l15-step.cur { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
  .l15-step.future { display: none; }
  .l15-step .hd { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: baseline; font-size: .82rem; }
  .l15-step .hd b { font-size: .9rem; }
  .l15-step .hd .m { direction: ltr; font-family: var(--mono); color: var(--muted); font-size: .75rem; }
  .l15-line { direction: ltr; text-align: left; font-family: var(--mono); font-size: .75rem; line-height: 1.45; overflow-wrap: anywhere; }
  .l15-line .k { display: inline-block; min-width: 46px; color: var(--muted); }
  .l15-line.err { color: var(--bad); }
  .l15-line.ok { color: var(--good); }
  .l15-line.thk { color: var(--accent); }
  .l15-tag { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .75rem; border: 1px solid var(--line); background: var(--code-bg); direction: ltr; }
  .l15-tag.ok { border-color: var(--good); background: var(--good-soft); }
  .l15-tag.bad { border-color: var(--bad); background: var(--bad-soft); }
  .l15-tag.warn { border-color: var(--signal); background: var(--signal-soft); }
  .l15-plan { border: 1px dashed var(--accent); border-radius: 10px; padding: 8px 10px; background: var(--accent-soft); display: grid; gap: 3px; }
  .l15-head { display: grid; gap: 6px; }
  .l15-stats { display: flex; flex-wrap: wrap; gap: 6px; }
  .l15-sel { width: 100%; max-width: 100%; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); font: inherit; }
  .l15-knobs { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
  .l15-knob { display: grid; gap: 2px; border: 1px solid var(--line); border-radius: 10px; padding: 6px 8px; background: var(--surface); min-width: 0; }
  .l15-knob label { font-size: .8rem; display: flex; justify-content: space-between; gap: 6px; }
  .l15-knob label span { direction: ltr; font-family: var(--mono); }
  .l15-knob input { width: 100%; }
  .l15-rows { display: grid; gap: 4px; }
  .l15-row { display: grid; grid-template-columns: 34px minmax(0, 1fr) minmax(0, 1fr) 76px; gap: 6px; align-items: center; padding: 5px 8px;
    border: 1px solid var(--line); border-radius: 8px; background: var(--surface); font-size: .78rem; }
  .l15-row.hd { background: var(--code-bg); font-weight: 600; }
  .l15-row.after { opacity: .4; }
  .l15-row.stop { border-color: var(--bad); background: var(--bad-soft); }
  .l15-row.fin { border-color: var(--good); background: var(--good-soft); }
  .l15-row .c { direction: ltr; text-align: left; font-family: var(--mono); overflow-wrap: anywhere; }
  @media (max-width: 520px) { .l15-row { grid-template-columns: 28px minmax(0, 1fr) 64px; } .l15-row .res { display: none; }
    .l15-ring > div { font-size: .68rem; padding: 6px 2px; } }
  .l15-rules { display: grid; gap: 4px; }
  .l15-rule { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; padding: 5px 10px; border: 1px solid var(--line); border-radius: 8px; font-size: .82rem; }
  .l15-rule.win { border-color: var(--bad); background: var(--bad-soft); font-weight: 600; }
  .l15-rule.fin { border-color: var(--good); background: var(--good-soft); font-weight: 600; }
  .l15-rule.never { opacity: .55; }
  `;
  document.head.appendChild(st);
})();

function l15Short(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
function l15Money(x) { return "$" + Number(x || 0).toFixed(5); }

/* ---------------- animation: the agent loop ---------------- */
window.AIDS["l15loop"] = function (host) {
  const RUNS = {
    ok: L15_TRAJS.find((t) => t.key === "t01-react"),
    rep: L15_TRAJS.find((t) => t.key === "t01-repeat"),
    para: L15_TRAJS.find((t) => t.key === "t01-para"),
  };
  const LIMITS = { steps: 8, cost: 0.002, repeat: 3, noprog: 3 };
  host.innerHTML = `<div class="l15">
    <div class="guide"><p><b>איך לקרוא:</b> הטבעת למעלה היא ארבע התחנות של כל צעד. החלון עם הקוד הוא ה-scratchpad: מה שהמודל רואה בצעד הזה (השורה החדשה מסומנת). המדים לידו מתמלאים עם הריצה, ופס אדום הוא הגבול שעוצר. עבור עם החצים, וקרא את ההסבר שמתחת.</p></div>
    <div class="seg" role="group" aria-label="ריצה">
      <button aria-pressed="true" data-run="ok">הצלחה (t01)</button>
      <button aria-pressed="false" data-run="rep">לולאה זהה</button>
      <button aria-pressed="false" data-run="para">לולאה מוסווית</button>
    </div>
    <div class="l15-ring">
      <div data-st="0"><b>Observe</b>שולחים הכל</div>
      <div data-st="1"><b>Think</b>מה חסר</div>
      <div data-st="2"><b>Act</b>כלי או תשובה</div>
      <div data-st="3"><b>Check</b>should_stop</div>
    </div>
    <div class="l15-grid">
      <div class="l15-pad" data-pad aria-live="polite"></div>
      <div class="l15-meters">
        <div class="l15-meter" data-m="steps"><div class="lbl"><span>צעדים</span><span></span></div><div class="bar"><i></i></div></div>
        <div class="l15-meter" data-m="cost"><div class="lbl"><span>עלות (תקציב לדוגמה)</span><span></span></div><div class="bar"><i></i></div></div>
        <div class="l15-meter" data-m="repeat"><div class="lbl"><span>אותה קריאה בדיוק</span><span></span></div><div class="bar"><i></i></div></div>
        <div class="l15-meter" data-m="noprog"><div class="lbl"><span>צעדים בלי מידע חדש</span><span></span></div><div class="bar"><i></i></div></div>
        <div class="l15-dec" data-dec>—</div>
      </div>
    </div>
    <div class="l15-cap" data-cap></div>
    <div class="row"><button class="btn small" data-prev>‹ הקודם</button><button class="btn small primary" data-play>השהה</button><button class="btn small" data-next>הבא ›</button><span class="muted" data-ctr></span></div>
  </div>`;

  function framesFor(run) {
    const F = [];
    const pad = [{ c: "sys", t: "[system] You are Company Brain ... (+ 7 tool definitions: lookup_employee, get_system_info, list_access_grants, check_policy, read_document, create_access_request, give_up)" },
      { c: "usr", t: "[user] " + l15Short(run.task, 170) }];
    let cost = 0, n = 0, maxRep = 0, streak = 0;
    const fpCount = {}, seen = new Set();
    let pendingConfirm = null;
    F.push({ st: -1, pad: pad.slice(), newIdx: 1, m: { steps: 0, cost: 0, repeat: 0, noprog: 0 }, dec: null,
      cap: "<b>ההתחלה.</b> לשיחה יש שני חלקים: הפרומפט של המערכת עם שבע הגדרות כלים (כולל give_up), והמשימה של המשתמש. זה מה שיישלח למודל בצעד הראשון. עוד לא קרה כלום." });
    for (const s of run.steps) {
      if (s.confirm) { pendingConfirm = s; continue; }
      if (s.trim) continue;
      n += 1;
      const m0 = { steps: n, cost, repeat: maxRep, noprog: streak };
      F.push({ st: 0, pad: pad.slice(), newIdx: -1, m: m0, dec: null,
        cap: `<b>צעד ${n}, Observe.</b> כל ה-scratchpad נשלח למודל מחדש: <span class="l15i">${s.tin.toLocaleString()}</span> טוקני קלט (בהערכה). ${n > 1 ? "זה יותר מהצעד הקודם, כי כל קריאה ותוצאה נשארות בשיחה." : "רובם הם הבסיס הקבוע: פרומפט, הגדרות כלים, ו-286 טוקני ה-tool prompt של Anthropic."}` });
      if (s.final) {
        pad.push({ c: "fin", t: "[assistant] " + l15Short(s.final, 260) });
        cost += s.cost;
        F.push({ st: 2, pad: pad.slice(), newIdx: pad.length - 1, m: { steps: n, cost, repeat: maxRep, noprog: streak }, dec: null,
          cap: `<b>צעד ${n}, Act: תשובה סופית.</b> הפעם המודל לא ביקש כלים. הוא כתב תשובה מבוססת על שלוש התצפיות: המנהלת, המסלול ופרטי הבקשה שנפתחה.` });
        F.push({ st: 3, pad: pad.slice(), newIdx: -1, m: { steps: n, cost, repeat: maxRep, noprog: streak }, dec: { ok: true, reason: s.decision, detail: s.detail },
          cap: `<b>Check: final_answer.</b> גם התשובה הסופית עוברת דרך מדיניות העצירה, וכך כל עצירה מגיעה ממקום אחד ונרשמת. סה"כ: ${n} צעדים, ${run.ncalls} קריאות, <span class="l15i">${l15Money(run.cost)}</span> (הערכה).` , end: true });
        continue;
      }
      if (s.think) {
        pad.push({ c: "thk", t: "[assistant] " + s.think });
        F.push({ st: 1, pad: pad.slice(), newIdx: pad.length - 1, m: m0, dec: null,
          cap: `<b>צעד ${n}, Think.</b> לפני הקריאה המודל כותב משפט קצר: מה חסר לו ולמה. זה ה-Thought של ReAct, והוא מה שהופך את ה-trajectory לקריא.` });
      }
      const callLines = s.calls.map((c) => ({ c: "act", t: `  tool_use ${c.name}(${l15Short(c.args, 90)})   #${c.fp}` }));
      callLines.forEach((x) => pad.push(x));
      let capAct = `<b>צעד ${n}, Act.</b> המודל ביקש ${s.calls.length > 1 ? s.calls.length + " קריאות" : "קריאה אחת"}: <span class="l15i">${s.calls.map((c) => c.name).join(", ")}</span>. ה-fingerprint <span class="l15i">#${s.calls[0].fp}</span> מזהה את השם יחד עם הארגומנטים.`;
      for (const c of s.calls) fpCount[c.fp] = (fpCount[c.fp] || 0) + 1;
      maxRep = Math.max(maxRep, ...s.calls.map((c) => fpCount[c.fp]));
      if (s.calls.some((c) => fpCount[c.fp] > 1)) capAct += ` <b>שים לב:</b> הקריאה הזו כבר הופיעה, וזו הפעם ה-${Math.max(...s.calls.map((c) => fpCount[c.fp]))}.`;
      if (pendingConfirm) {
        pad.push({ c: "cnf", t: `  [human] confirm ${pendingConfirm.confirm}? -> ${pendingConfirm.approved ? "APPROVED" : "DECLINED"}` });
        capAct += ` לפני שהקריאה רצה, ה-agent עצר ושאל אדם, כי ל-<span class="l15i">create_access_request</span> יש תופעת לוואי. האדם אישר, ונוצר token שקשור לקריאה המדויקת.`;
        pendingConfirm = null;
      }
      F.push({ st: 2, pad: pad.slice(), newIdx: pad.length - 1, m: { steps: n, cost, repeat: maxRep, noprog: streak }, dec: null, cap: capAct });
      s.results.forEach((r) => pad.push({ c: r.err ? "err" : "obs", t: `  tool_result ${r.err ? "ERROR " : ""}${l15Short(r.text, 110)}   hash ${r.h || "-"}` }));
      cost += s.cost;
      const fresh = s.results.some((r) => r.h && !seen.has(r.h));
      s.results.forEach((r) => r.h && seen.add(r.h));
      streak = fresh ? 0 : streak + 1;
      F.push({ st: 0, pad: pad.slice(), newIdx: pad.length - 1, m: { steps: n, cost, repeat: maxRep, noprog: streak }, dec: null,
        cap: `<b>צעד ${n}, Observe: התוצאה.</b> ה-executor הריץ את הכלי והחזיר תוצאה, וה-hash שלה הוא <span class="l15i">${s.results[0].h || "-"}</span>. ${fresh ? "זה hash שלא נראה קודם בריצה, כלומר מידע חדש." : "<b>את ה-hash הזה כבר ראינו.</b> אין כאן מידע חדש, ולכן מונה הצעדים בלי התקדמות עולה."}` });
      const stop = s.decision !== "continue";
      const ruleTxt = { repetition: `<b>Check: repetition.</b> <span class="l15i">(${esc(s.detail)})</span>. אותה קריאה עם אותם ארגומנטים, שלוש פעמים: המודל תקוע, ולא יכול לקבל משהו חדש. הריצה נעצרת, וכל הקריאות כבר קיבלו תוצאה, כך שהשיחה לא שבורה.`,
        no_progress: `<b>Check: no_progress.</b> <span class="l15i">(${esc(s.detail)})</span>. כל קריאה הייתה שונה (fingerprints שונים), ולכן repetition לא תפס. אבל שלושה צעדים ברצף לא החזירו אף hash חדש. repetition היה עוצר רק בצעד 7.` };
      F.push({ st: 3, pad: pad.slice(), newIdx: -1, m: { steps: n, cost, repeat: maxRep, noprog: streak }, dec: { ok: !stop, reason: s.decision, detail: s.detail },
        cap: stop ? (ruleTxt[s.decision] || `<b>Check: ${s.decision}.</b> <span class="l15i">${esc(s.detail)}</span>`) : `<b>צעד ${n}, Check: continue.</b> אף כלל לא חל. צעדים ${n} מתוך ${LIMITS.steps}, הקריאה שחזרה הכי הרבה הופיעה ${maxRep} פעמים, ו-${streak} צעדים בלי מידע חדש. ממשיכים לצעד הבא.`, end: stop });
    }
    return F;
  }

  let runKey = "ok", frames = framesFor(RUNS.ok), i = 0, timer = null;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let playing = !reduce;
  const padEl = host.querySelector("[data-pad]"), capEl = host.querySelector("[data-cap]"), decEl = host.querySelector("[data-dec]");
  const ctr = host.querySelector("[data-ctr]"), btn = host.querySelector("[data-play]");

  function meter(name, val, max, txt) {
    const el = host.querySelector(`[data-m="${name}"]`);
    const frac = Math.min(1, val / max);
    el.querySelector("i").style.width = (frac * 100).toFixed(1) + "%";
    el.querySelector(".lbl span:last-child").textContent = txt;
    el.classList.toggle("hot", frac >= 1);
    el.classList.toggle("warm", frac >= 0.66 && frac < 1);
  }
  function draw() {
    const f = frames[i];
    padEl.innerHTML = f.pad.map((x, k) => `<div class="${x.c}${k === f.newIdx ? " new" : ""}">${esc(x.t)}</div>`).join("");
    padEl.scrollTop = padEl.scrollHeight;
    host.querySelectorAll("[data-st]").forEach((d) => {
      const k = +d.dataset.st;
      d.className = k === f.st ? (f.dec && f.dec.reason !== "continue" ? (f.dec.reason === "final_answer" ? "done" : "stop") : "on") : "";
    });
    meter("steps", f.m.steps, LIMITS.steps, `${f.m.steps} / ${LIMITS.steps}`);
    meter("cost", f.m.cost, LIMITS.cost, `${l15Money(f.m.cost)} / $${LIMITS.cost}`);
    meter("repeat", f.m.repeat, LIMITS.repeat, `${f.m.repeat} / ${LIMITS.repeat}`);
    meter("noprog", f.m.noprog, LIMITS.noprog, `${f.m.noprog} / ${LIMITS.noprog}`);
    if (f.dec) {
      decEl.className = "l15-dec " + (f.dec.reason === "continue" ? "" : f.dec.reason === "final_answer" ? "ok" : "bad");
      decEl.innerHTML = `<span class="l15i"><b>should_stop → ${esc(f.dec.reason)}</b></span>${f.dec.detail && f.dec.reason !== "continue" ? `<br><span class="muted l15i">${esc(f.dec.detail)}</span>` : ""}`;
    } else { decEl.className = "l15-dec"; decEl.textContent = "should_stop: עוד לא נבדק בצעד הזה"; }
    capEl.innerHTML = f.cap;
    ctr.textContent = `${i + 1} / ${frames.length}`;
    btn.textContent = playing ? "השהה" : "נגן";
  }
  function arm() { clearInterval(timer); if (playing) timer = setInterval(() => { i = (i + 1) % frames.length; draw(); }, 4200); }
  host.querySelector("[data-next]").addEventListener("click", () => { playing = false; arm(); i = Math.min(frames.length - 1, i + 1); draw(); });
  host.querySelector("[data-prev]").addEventListener("click", () => { playing = false; arm(); i = Math.max(0, i - 1); draw(); });
  btn.addEventListener("click", () => { playing = !playing; arm(); draw(); });
  host.querySelectorAll("[data-run]").forEach((b) => b.addEventListener("click", () => {
    host.querySelectorAll("[data-run]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    runKey = b.dataset.run; frames = framesFor(RUNS[runKey]); i = 0; draw(); arm();
  }));
  draw(); arm();
  return () => clearInterval(timer);
};

/* ---------------- sim: trajectory explorer ---------------- */
window.AIDS["l15traj"] = function (host) {
  const HE = {
    "t01-react": "t01 (Dana), reactive", "t01-plan": "t01 (Dana), plan-then-act", "t01-repeat": "t01, מודל בלולאה זהה",
    "t01-para": "t01, לולאה מוסווית", "t05-plan": "t05 (Shani, עמום), plan עם תכנון מחדש",
    "t01-keep1": "t01 עם keep_tool_results=1, בלי פתקים", "t01-transient": "t01, הכלי נכשל פעם אחת",
    "t11-stale": "t11, מסמך מדיניות ישן (v2.1)", "t01-mock-declined": "t01 on mockllm, human declines",
  };
  const NOTE = {
    "t01-react": "המסלול הקצר: שלוש קריאות לפי הסדר, אישור לפני ה-create, ותשובה.",
    "t01-plan": "קודם תוכנית (קריאה נוספת), ואז שתי קריאות במקביל בצעד 1. צעד אחד פחות.",
    "t01-repeat": "אותה קריאה בדיוק שלוש פעמים: repetition עוצר.",
    "t01-para": "שם, מייל, מזהה: fingerprints שונים, אותו hash. no_progress עוצר בצעד 4.",
    "t05-plan": "התוכנית שלחה lookup ו-check_policy במקביל. lookup נכשל (ארבע Shani), ולכן נוצרה תוכנית מתוקנת.",
    "t01-keep1": "כל תוצאה ישנה נמחקת. המודל שוכח את Dana, ומביא אותה שוב ושוב.",
    "t01-transient": "שגיאה זמנית חוזרת כתצפית. המודל מנסה שוב פעם אחת, ממשיך ומצליח.",
    "t11-stale": "שום דבר בלולאה לא נראה שגוי. רק בדיקת הזהב מגלה שהתשובה שגויה.",
    "t01-mock-declined": "mockllm טיפש בכוונה: אחרי סירוב הוא מבקש שוב, עד ש-repetition עוצר.",
  };
  host.innerHTML = `<div class="l15">
    <div class="guide"><p><b>מה רואים:</b> ריצה מוקלטת אחת, צעד אחרי צעד. בכל כרטיס יש ארבע שורות: <span class="l15i">think</span> (מה המודל כתב), <span class="l15i">act</span> (הקריאה וה-fingerprint שלה), <span class="l15i">obs</span> (התוצאה וה-hash שלה; אדום = שגיאה), ו-<span class="l15i">policy</span> (ההחלטה). מסגרת מקווקוות = תוכנית. בסוף יש בדיקת זהב. <b>מה לנסות:</b> בחר ריצה, ולחץ "הבא" עד הסוף.</p></div>
    <select class="l15-sel" data-pick aria-label="בחר ריצה">${L15_TRAJS.map((t) => `<option value="${t.key}">${esc(HE[t.key] || t.title)}</option>`).join("")}</select>
    <div class="l15-head" data-head></div>
    <div class="row"><button class="btn small" data-prev>‹ הקודם</button><button class="btn small primary" data-next>הבא ›</button><button class="btn small" data-all>הצג הכל</button><span class="muted" data-ctr></span></div>
    <div class="l15-steps" data-steps></div>
    <div data-gold></div>
  </div>`;
  let run = L15_TRAJS[0], cur = 0;
  const stepsEl = host.querySelector("[data-steps]");
  function cards() {
    // a flat list of "cards": plans, confirms, trims and steps, in order
    const out = [];
    let pi = 0;
    const plans = run.plans || [];
    let stepCount = 0;
    const pushPlans = () => { while (pi < plans.length && plans[pi].after <= stepCount) out.push({ plan: plans[pi++] }); };
    pushPlans();
    for (const s of run.steps) {
      if (s.n) { out.push({ step: s }); stepCount += 1; pushPlans(); }
      else out.push({ misc: s });
    }
    while (pi < plans.length) out.push({ plan: plans[pi++] });
    return out;
  }
  let C = cards();
  function render() {
    const stepsSoFar = C.slice(0, cur + 1).filter((x) => x.step).map((x) => x.step);
    const last = stepsSoFar[stepsSoFar.length - 1];
    const calls = stepsSoFar.reduce((a, s) => a + s.calls.length, 0);
    const errs = stepsSoFar.reduce((a, s) => a + s.results.filter((r) => r.err).length, 0);
    const tin = stepsSoFar.reduce((a, s) => a + s.tin, 0);
    host.querySelector("[data-head]").innerHTML = `
      <p class="ltr" style="font-size:.85rem"><b>TASK:</b> ${esc(l15Short(run.task, 220))}</p>
      <p class="muted">${esc(NOTE[run.key] || "")}</p>
      <div class="l15-stats">
        <span class="l15-tag">model ${esc(run.model)}</span><span class="l15-tag">mode ${esc(run.mode)}</span>
        <span class="l15-tag">steps ${stepsSoFar.length}</span><span class="l15-tag">calls ${calls}</span>
        <span class="l15-tag ${errs ? "bad" : ""}">errors ${errs}</span><span class="l15-tag">input tokens ${tin.toLocaleString()}</span>
        <span class="l15-tag">cost ${l15Money(last ? last.cum : 0)}${run.model.startsWith("fake") ? " (est.)" : ""}</span>
      </div>`;
    stepsEl.innerHTML = C.map((x, k) => {
      const cls = "l15-step" + (k === cur ? " cur" : "") + (k > cur ? " future" : "");
      if (x.plan) {
        return `<div class="${cls} l15-plan"><div class="hd"><b>${x.plan.rev ? "REPLAN #" + x.plan.rev : "PLAN"}</b>${x.plan.reason ? `<span class="m">${esc(x.plan.reason)}</span>` : ""}</div>
          ${x.plan.steps.map((p, j) => `<div class="l15-line">${j + 1}. ${esc(p)}</div>`).join("")}</div>`;
      }
      if (x.misc) {
        if (x.misc.confirm) return `<div class="${cls}"><div class="hd"><b>confirm</b><span class="l15-tag ${x.misc.approved ? "ok" : "bad"}">${x.misc.approved ? "APPROVED" : "DECLINED"}</span><span class="m">${esc(x.misc.confirm)}</span></div><p class="muted" style="font-size:.82rem">${x.misc.approved ? "אדם אישר את הקריאה המדויקת, ונוצר token חד-פעמי שהמודל לא רואה." : "אדם סירב. המודל יקבל DECLINED, והכלי לא ירוץ."}</p></div>`;
        return `<div class="${cls}"><div class="hd"><b>memory</b><span class="l15-tag warn">cleared ${x.misc.trim}</span></div><p class="muted" style="font-size:.82rem">תוצאות ישנות הוחלפו ב-placeholder. ה-ids נשארו, אבל התוכן נעלם מההקשר של המודל.</p></div>`;
      }
      const s = x.step;
      const dec = s.decision === "continue" ? "" : (s.decision === "final_answer" || s.decision === "gave_up" ? "ok" : "bad");
      let body = "";
      if (s.think) body += `<div class="l15-line thk"><span class="k">think</span>${esc(s.think)}</div>`;
      s.calls.forEach((c, j) => {
        const r = s.results[j] || {};
        body += `<div class="l15-line"><span class="k">act</span>${esc(c.name)}(${esc(c.args)}) <span class="muted">#${esc(c.fp)}</span></div>`;
        body += `<div class="l15-line ${r.err ? "err" : "ok"}"><span class="k">obs</span>${r.err ? "ERR " : "ok  "}${esc(r.text || "")} <span class="muted">${r.h ? "hash " + esc(r.h) : ""}</span></div>`;
      });
      if (s.final) body += `<div class="l15-line"><span class="k">final</span>${esc(s.final)}</div>`;
      if (s.gave_up) body += `<div class="l15-line"><span class="k">give_up</span>${esc(s.gave_up)}</div>`;
      body += `<div class="l15-line"><span class="k">policy</span><span class="l15-tag ${dec}">${esc(s.decision)}</span> ${s.decision !== "continue" ? esc(s.detail || "") : ""}</div>`;
      return `<div class="${cls}"><div class="hd"><b>step ${s.n}</b><span class="m">tokens ${s.tin}+${s.tout} · ${l15Money(s.cost)} · total ${l15Money(s.cum)}</span></div>${body}</div>`;
    }).join("");
    const done = cur >= C.length - 1;
    const g = run.gold;
    host.querySelector("[data-gold]").innerHTML = done ? `<div class="l15-dec ${g && g.success ? "ok" : "bad"}">
      <b>STOP <span class="l15i">${esc(run.stop)}</span></b> <span class="muted l15i">${esc(run.detail || "")}</span><br>
      <span class="l15i" style="font-size:.85rem">ANSWER: ${esc(run.text)}</span><br>
      <b>בדיקת זהב: ${g && g.success ? "הצלחה" : "כישלון"}</b>${g && g.reasons.length ? `<ul class="ltr" style="margin:4px 0 0">${g.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
      ${g ? `<span class="muted"> · קריאות מיותרות: ${g.redundant} · יעילות: ${g.eff == null ? "n/a" : Number(g.eff).toFixed(2)}</span>` : ""}</div>` : "";
    host.querySelector("[data-ctr]").textContent = `${cur + 1} / ${C.length}`;
    const el = stepsEl.children[cur];
    if (el && el.scrollIntoView && cur > 0) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  host.querySelector("[data-pick]").addEventListener("change", (e) => { run = L15_TRAJS.find((t) => t.key === e.target.value); C = cards(); cur = 0; render(); });
  host.querySelector("[data-next]").addEventListener("click", () => { cur = Math.min(C.length - 1, cur + 1); render(); });
  host.querySelector("[data-prev]").addEventListener("click", () => { cur = Math.max(0, cur - 1); render(); });
  host.querySelector("[data-all]").addEventListener("click", () => { cur = C.length - 1; render(); });
  render();
};

/* ---------------- sim: stop-policy simulator ---------------- */
window.AIDS["l15budget"] = function (host) {
  // Per-step data: fps (one per call), hs (result hash per call, null = error), cost, final.
  const mk = (n, f) => Array.from({ length: n }, (_, k) => f(k));
  const SCEN = {
    long: { name: "ריצה תקינה ארוכה", desc: "שבעה צעדים, ובכל אחד קריאה חדשה שמחזירה מידע חדש. התשובה הסופית מגיעה בצעד 8. העלות עולה מצעד לצעד, כי השיחה גדלה.",
      steps: mk(7, (k) => ({ fps: ["c" + k], hs: ["h" + k], cost: 0.00023 + k * 0.00003 })).concat([{ fps: [], hs: [], cost: 0.00045, final: true }]) },
    rep: { name: "לולאה זהה", desc: "אחרי צעד ראשון תקין, אותה קריאה בדיוק חוזרת בכל צעד ומחזירה את אותה תוצאה.",
      steps: mk(10, () => ({ fps: ["A"], hs: ["h1"], cost: 0.00024 })) },
    para: { name: "לולאה מוסווית", desc: "אותו מידע, נשאל כל פעם אחרת: שם, מייל, מזהה, וחוזר חלילה. ה-fingerprints שונים, וה-hash זהה.",
      steps: mk(10, (k) => ({ fps: [["N", "M", "I"][k % 3]], hs: ["h1"], cost: 0.00024 })) },
    down: { name: "כלי למטה, מודל עקשן", desc: "הכלי תמיד נכשל, והמודל ממשיך לנסות את אותה קריאה.",
      steps: mk(10, () => ({ fps: ["A"], hs: [null], cost: 0.00022 })) },
    down2: { name: "כלי למטה, מודל שמשנה ארגומנטים", desc: "הכלי תמיד נכשל. המודל משנה את הארגומנטים בכל ניסיון, ולכן אף קריאה לא זהה לקודמת.",
      steps: mk(10, (k) => ({ fps: ["X" + k], hs: [null], cost: 0.00022 })) },
  };
  const K = { max_steps: 8, max_cost: 0.003, repeat_limit: 3, no_progress: 3, max_errors: 3 };
  const KN = [
    ["max_steps", "max_steps", 1, 12, 1, (v) => v],
    ["max_cost", "max_cost_usd", 0.0005, 0.004, 0.0001, (v) => "$" + v.toFixed(4)],
    ["repeat_limit", "repeat_limit", 2, 8, 1, (v) => v],
    ["no_progress", "no_progress_steps (0 = כבוי)", 0, 6, 1, (v) => v],
    ["max_errors", "max_consecutive_errors (0 = כבוי)", 0, 6, 1, (v) => v],
  ];
  host.innerHTML = `<div class="l15">
    <div class="guide"><p><b>מה רואים:</b> תרחיש הוא רצף של צעדים, ולכל צעד יש קריאות (לפי fingerprint), תוצאות (לפי hash; ✗ = שגיאה) ועלות. אחרי כל צעד הסימולטור מריץ את <span class="l15i">should_stop</span>, לפי אותו סדר כמו ב-agentkit. <b>רשימת הכללים</b> מראה, לכל כלל, באיזה צעד הוא היה עוצר אילו היה לבד. הכלל שעוצר בפועל מודגש. <b>מה לנסות:</b> הזז את המחוונים וראה איך העצירה זזה.</p></div>
    <div class="seg" role="group" aria-label="תרחיש">${Object.entries(SCEN).map(([k, s], j) => `<button aria-pressed="${j === 2}" data-sc="${k}">${s.name}</button>`).join("")}</div>
    <p class="muted" data-desc></p>
    <div class="l15-knobs">${KN.map(([k, lbl, mn, mx, stp]) => `<div class="l15-knob"><label>${lbl}<span data-v="${k}"></span></label><input type="range" min="${mn}" max="${mx}" step="${stp}" value="${K[k]}" data-k="${k}" aria-label="${lbl}"></div>`).join("")}</div>
    <div class="l15-dec" data-res></div>
    <div class="l15-rules" data-rules></div>
    <div class="l15-rows" data-rows></div>
  </div>`;
  let sc = "para";

  function decide(hist) {
    if (!hist.length) return ["continue", ""];
    const last = hist[hist.length - 1];
    if (last.final) return ["final_answer", "the model answered"];
    if (hist.length >= K.max_steps) return ["max_steps", `${hist.length} steps`];
    const cost = hist.reduce((a, s) => a + s.cost, 0);
    if (cost >= K.max_cost) return ["budget_cost", `$${cost.toFixed(5)} spent`];
    if (cost + last.cost > K.max_cost) return ["budget_cost", `$${cost.toFixed(5)} + next ~$${last.cost.toFixed(5)} > $${K.max_cost.toFixed(4)}`];
    const cnt = {};
    hist.forEach((s) => s.fps.forEach((f) => { cnt[f] = (cnt[f] || 0) + 1; }));
    for (const f of last.fps) if (cnt[f] >= K.repeat_limit) return ["repetition", `same call ${cnt[f]} times`];
    const k = K.max_errors;
    if (k > 0 && hist.length >= k && hist.slice(-k).every((s) => s.fps.length && s.hs.every((h) => h === null))) return ["tool_errors", `all calls failed in ${k} steps`];
    const w = K.no_progress;
    if (w > 0 && hist.length >= w) {
      const seen = new Set(); const prog = [];
      hist.forEach((s) => { const nw = s.hs.filter((h) => h && !seen.has(h)); prog.push(nw.length > 0); nw.forEach((h) => seen.add(h)); });
      if (!prog.slice(-w).some(Boolean)) return ["no_progress", `no new hash in ${w} steps`];
    }
    return ["continue", ""];
  }
  function aloneAt(rule, steps) {
    // first step at which `rule` alone would fire (others disabled)
    const save = { ...K };
    const off = { max_steps: 999, max_cost: 999, repeat_limit: 999, no_progress: 0, max_errors: 0 };
    const keep = { max_steps: ["max_steps"], budget_cost: ["max_cost"], repetition: ["repeat_limit"], no_progress: ["no_progress"], tool_errors: ["max_errors"] }[rule];
    Object.assign(K, off); keep.forEach((x) => { K[x] = save[x]; });
    let at = null;
    for (let n = 1; n <= steps.length; n++) { const d = decide(steps.slice(0, n)); if (d[0] === rule) { at = n; break; } if (d[0] === "final_answer") break; }
    Object.assign(K, save);
    return at;
  }
  function render() {
    const S = SCEN[sc];
    host.querySelector("[data-desc]").textContent = S.desc;
    KN.forEach(([k, , , , , fmt]) => { host.querySelector(`[data-v="${k}"]`).textContent = fmt(K[k]); });
    let stopAt = null, reason = "continue", detail = "";
    const decs = [];
    for (let n = 1; n <= S.steps.length; n++) {
      const d = decide(S.steps.slice(0, n));
      decs.push(d);
      if (d[0] !== "continue") { stopAt = n; reason = d[0]; detail = d[1]; break; }
    }
    const cum = []; S.steps.reduce((a, s, j) => (cum[j] = a + s.cost), 0);
    const res = host.querySelector("[data-res]");
    res.className = "l15-dec " + (reason === "final_answer" ? "ok" : reason === "continue" ? "" : "bad");
    res.innerHTML = stopAt ? `<b>עצירה בצעד ${stopAt}: <span class="l15i">${reason}</span></b> <span class="muted l15i">(${esc(detail)})</span> · עלות עד העצירה <span class="l15i">${l15Money(cum[stopAt - 1])}</span>`
      : "התרחיש נגמר בלי עצירה (במציאות max_steps היה עוצר).";
    const rules = [["final_answer", "התשובה הסופית"], ["max_steps", "max_steps"], ["budget_cost", "budget_cost (כולל הסתכלות קדימה)"], ["repetition", "repetition (fingerprint)"], ["tool_errors", "tool_errors"], ["no_progress", "no_progress (hash)"]];
    host.querySelector("[data-rules]").innerHTML = rules.map(([r, lbl]) => {
      const at = r === "final_answer" ? (S.steps.findIndex((s) => s.final) + 1 || null) : aloneAt(r, S.steps);
      const cls = r === reason ? (r === "final_answer" ? "fin" : "win") : (at ? "" : "never");
      return `<div class="l15-rule ${cls}"><span class="l15i">${lbl}</span><span>${at ? "לבד: צעד " + at : "לא חל"}${r === reason ? " ← עוצר" : ""}</span></div>`;
    }).join("");
    host.querySelector("[data-rows]").innerHTML = `<div class="l15-row hd"><span>#</span><span>קריאות</span><span class="res">תוצאות</span><span>מצטבר</span></div>` +
      S.steps.map((s, j) => {
        const n = j + 1;
        const cls = stopAt === n ? (reason === "final_answer" ? "fin" : "stop") : (stopAt && n > stopAt ? "after" : "");
        return `<div class="l15-row ${cls}"><span>${n}</span><span class="c">${s.final ? "final answer" : s.fps.map((f) => "#" + f).join(" ")}</span><span class="c res">${s.final ? "—" : s.hs.map((h) => (h ? "hash " + h : "✗ error")).join(" ")}</span><span class="c">${l15Money(cum[j])}</span></div>`;
      }).join("");
  }
  host.querySelectorAll("[data-k]").forEach((inp) => inp.addEventListener("input", () => { K[inp.dataset.k] = Number(inp.value); render(); }));
  host.querySelectorAll("[data-sc]").forEach((b) => b.addEventListener("click", () => {
    host.querySelectorAll("[data-sc]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    sc = b.dataset.sc; render();
  }));
  render();
};
