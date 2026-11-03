# Spec: Access-request API for Company Brain

- **Spec id:** SPEC-006
- **Status:** approved
- **Owner:** the owner (architect), reviewed by: security team
- **Version:** 1.0 (2026-11-01)
- **Interface contract:** `spec/openapi.yaml` (source of truth for paths, fields, types and status codes)
- **Policy source:** `data/acme/saas_access_policy.md` (Acme SaaS Access Policy v2.1)

## 1. Intent

Employees at Acme ask for access to SaaS tools in Slack and email. Today a person reads every
request and decides who must approve it. Company Brain will take over the mechanical part: store
each request, route it to one of the three tracks of the access policy, approve the safe ones
immediately, and let the right person approve the rest. This API is the backend of that
workflow. A later lesson puts an LLM in front of it (free text to `NewAccessRequest`), and an
agent with human approval on top of it. Neither is part of this spec.

Success means: every request lands on the track the policy demands, no request that needs a
human is ever approved without one, and every status change can be audited.

## 2. Context and policy summary

The policy has three tracks. The strictest matching track wins
(needs_security > needs_manager > auto_approve).

- **auto_approve:** approved tool (Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma,
  GitHub), read-only or standard seat, no customer or financial data.
- **needs_manager:** paid seat on an approved tool, a tool that is not on the list but holds no
  customer or financial data, or write access to a team-owned resource.
- **needs_security:** admin/owner/root rights, production infrastructure, customer data,
  financial systems, external sharing or third-party OAuth.

## 3. Requirements

### REQ-1: Create an access request
**Statement:** WHEN an authenticated caller sends a valid `NewAccessRequest` to
`POST /access-requests`, THE SYSTEM SHALL store it, assign a new id matching `^ar_[0-9a-z]+$`,
set `requester` to the value of the `X-Actor` header, set `created_at` to the current UTC time,
and respond 201 with the stored `AccessRequest`.
**Acceptance criteria:**
- AC-1.1: GIVEN a valid body for Jira read access WHEN `dana@acme.example` posts it THEN the response is 201 AND the body has an `id` matching `^ar_[0-9a-z]+$` AND `requester` is `dana@acme.example`.
- AC-1.2: GIVEN a body that contains a `requester` field WHEN it is posted THEN the response is 422 (the requester can never come from the body).
- AC-1.3: GIVEN a request was created WHEN the caller gets it by id THEN the stored fields equal the fields of the 201 response.

### REQ-2: Reject invalid input
**Statement:** IF the body, a query parameter or a path parameter does not match `spec/openapi.yaml`,
THEN THE SYSTEM SHALL respond 422 with error code `validation_error` and SHALL NOT store anything.
**Acceptance criteria:**
- AC-2.1: GIVEN a body without `justification` WHEN it is posted THEN the response is 422 AND `error.code` is `validation_error`.
- AC-2.2: GIVEN a body with `access_level` set to `superuser` WHEN it is posted THEN the response is 422.
- AC-2.3: GIVEN a justification of 9 characters WHEN it is posted THEN the response is 422.
- AC-2.4: GIVEN any rejected body WHEN the caller lists requests afterwards THEN `total` did not change.

### REQ-3: Identify the caller
**Statement:** IF the `X-Actor` header is missing, does not contain "@", or is not 3 to 254
characters long, or the `X-Role` header is missing or not one of `employee`, `manager`,
`security`, THEN THE SYSTEM SHALL respond 401 with error code `unauthenticated` on every endpoint.
**Acceptance criteria:**
- AC-3.1: GIVEN no `X-Actor` header WHEN the caller posts a valid body THEN the response is 401 AND `error.code` is `unauthenticated`.
- AC-3.2: GIVEN `X-Role: admin` WHEN the caller lists requests THEN the response is 401.

### REQ-4: Route by policy
**Statement:** WHEN a request is created, THE SYSTEM SHALL set `route` with these rules, evaluated in
order, where the first matching rule wins:
1. `needs_security` if `access_level` is `admin`, OR any of `production`, `customer_data`,
   `financial_data`, `external_sharing` is true, OR the tool is one of AWS, GCP, Kubernetes,
   NetSuite, Payroll.
2. `needs_manager` if the tool is not on the approved list, OR `access_level` is `write`, OR the
   tool is Figma or GitHub with `access_level` `standard` (a paid or write-capable seat).
3. `auto_approve` otherwise.

Tool names are compared case-insensitively after trimming spaces.
**Acceptance criteria:**
- AC-4.1: GIVEN Jira with `read` and no flags WHEN created THEN `route` is `auto_approve`.
- AC-4.2: GIVEN Slack with `admin` WHEN created THEN `route` is `needs_security`.
- AC-4.3: GIVEN Confluence with `read` and `customer_data` true WHEN created THEN `route` is `needs_security`.
- AC-4.4: GIVEN Notion with `standard` WHEN created THEN `route` is `needs_manager`.
- AC-4.5: GIVEN GitHub with `write` WHEN created THEN `route` is `needs_manager`.
- AC-4.6: GIVEN Figma with `standard` WHEN created THEN `route` is `needs_manager`.
- AC-4.7: GIVEN "  aws " with `read` WHEN created THEN `route` is `needs_security`.

### REQ-5: Set the initial status
**Statement:** WHEN a request is created with route `auto_approve`, THE SYSTEM SHALL set `status` to
`approved`, `decided_by` to `system` and `decided_at` to `created_at`; for any other route it SHALL
set `status` to `pending` and `decided_by` and `decided_at` to null.
**Acceptance criteria:**
- AC-5.1: GIVEN a request routed to `auto_approve` WHEN created THEN `status` is `approved` AND `decided_by` is `system` AND `decided_at` equals `created_at`.
- AC-5.2: GIVEN a request routed to `needs_manager` WHEN created THEN `status` is `pending` AND `decided_by` is null.

### REQ-6: List requests
**Statement:** WHEN a caller sends `GET /access-requests`, THE SYSTEM SHALL return the requests
that match the optional `status` filter, ordered by `created_at` descending with ties broken by
`id` descending, at most `limit` items (default 20, allowed 1 to 100), and `total` equal to the
number of matching requests before the limit.
**Acceptance criteria:**
- AC-6.1: GIVEN requests A, B, C created in that order WHEN the caller lists THEN the ids come back as C, B, A.
- AC-6.2: GIVEN 25 requests WHEN the caller lists without `limit` THEN 20 items come back AND `total` is 25.
- AC-6.3: GIVEN one approved and two pending requests WHEN the caller lists with `status=pending` THEN exactly the two pending ones come back.
- AC-6.4: GIVEN `limit=101` WHEN the caller lists THEN the response is 422.

### REQ-7: Get one request
**Statement:** WHEN a caller sends `GET /access-requests/{request_id}` for an existing id, THE SYSTEM
SHALL respond 200 with that request; IF the id does not exist, THEN THE SYSTEM SHALL respond 404 with
error code `not_found`, on this endpoint and on the approve endpoint.
**Acceptance criteria:**
- AC-7.1: GIVEN an id that was never created WHEN the caller gets it THEN the response is 404 AND `error.code` is `not_found`.
- AC-7.2: GIVEN an id that was never created WHEN a security user approves it THEN the response is 404.

### REQ-8: Approve with the right authority
**Statement:** WHEN a caller approves a pending request and the caller's role is allowed for its
route, THE SYSTEM SHALL set `status` to `approved`, `decided_by` to the caller's `X-Actor`, and
`decided_at` to the current UTC time, and respond 200 with the updated request. Allowed roles:
for `needs_manager`, `manager` or `security`; for `needs_security`, only `security`.
**Acceptance criteria:**
- AC-8.1: GIVEN a pending `needs_manager` request WHEN a manager approves it THEN the response is 200 AND `status` is `approved` AND `decided_by` is the manager's email.
- AC-8.2: GIVEN a pending `needs_security` request WHEN a security user approves it THEN the response is 200.
- AC-8.3: GIVEN a pending `needs_manager` request WHEN a security user approves it THEN the response is 200.

### REQ-9: Refuse approvals without authority
**Statement:** IF the caller's role is not allowed for the request's route, OR the caller is the
requester of that request, THEN THE SYSTEM SHALL respond 403 with error code `forbidden` and SHALL
NOT change the request.
**Acceptance criteria:**
- AC-9.1: GIVEN a pending `needs_security` request WHEN a manager approves it THEN the response is 403 AND the request is still `pending`.
- AC-9.2: GIVEN a pending `needs_manager` request WHEN an employee approves it THEN the response is 403.
- AC-9.3: GIVEN a pending `needs_security` request created by `sec@acme.example` WHEN `sec@acme.example` with role `security` approves it THEN the response is 403.

### REQ-10: Refuse decisions on closed requests
**Statement:** IF a caller approves a request whose `status` is not `pending`, THEN THE SYSTEM SHALL
respond 409 with error code `conflict` and SHALL NOT change the request. This check runs after
REQ-7 (unknown id) and before REQ-9 (authority).
**Acceptance criteria:**
- AC-10.1: GIVEN an `auto_approve` request (already approved) WHEN a security user approves it THEN the response is 409 AND `error.code` is `conflict`.
- AC-10.2: GIVEN a request a manager already approved WHEN another manager approves it THEN the response is 409 AND `decided_by` is still the first manager.

### REQ-11: Audit every status change
**Statement:** WHEN a request's status is set or changed (including approval at creation), THE
SYSTEM SHALL write exactly one log record to the logger `access_api.audit` at level INFO whose
message is a JSON object with the keys `request_id`, `actor`, `from_status`, `to_status`.
`from_status` is null at creation.
**Acceptance criteria:**
- AC-11.1: GIVEN a Jira read request WHEN created THEN one audit record has `from_status` null AND `to_status` `approved` AND `actor` `system`.
- AC-11.2: GIVEN a pending request WHEN a manager approves it THEN one audit record has `from_status` `pending` AND `to_status` `approved` AND `actor` the manager's email.

## 4. Non-functional requirements

### NFR-1: Latency
**Statement:** WHILE 1,000 requests are stored, THE SYSTEM SHALL answer `POST /access-requests` and
`GET /access-requests` with a p95 latency of at most 50 ms each, measured in-process with
Starlette's `TestClient` over 200 calls on a developer laptop.
**Acceptance criteria:**
- AC-N1.1: GIVEN 1,000 stored requests WHEN 200 creates and 200 lists are timed THEN the p95 of each is at most 50 ms.

### NFR-2: Contract conformance
**Statement:** THE SYSTEM SHALL return, for every request that `spec/openapi.yaml` describes, a
status code that the contract documents for that operation and a body that validates against the
documented schema, and SHALL never respond 5xx.
**Acceptance criteria:**
- AC-N2.1: GIVEN requests generated by Schemathesis from `spec/openapi.yaml` WHEN they are sent to the app THEN no response breaks the status-code, content-type or schema checks AND none is 5xx.

## 5. Constraints

- Python 3.12, FastAPI. Entry point: a function `create_app() -> FastAPI` in `impl/app.py`.
- The grader imports `impl.app:create_app` with `labs/06-spec-driven/` on `sys.path`, so modules
  inside `impl/` import each other relatively (`from .routing import route_for`), and tests import
  `from impl.app import create_app` after their `conftest.py` puts `labs/06-spec-driven/` on `sys.path`.
- Storage is in memory, behind a small class, so a database can replace it later. Each call to
  `create_app()` starts with an empty store.
- The routing decision (REQ-4) is a pure function with no I/O and no LLM call.
- The HTTP interface must match `spec/openapi.yaml`. If the code and the contract disagree, the
  contract wins until the spec is changed on purpose.
- No new third-party dependencies beyond FastAPI and what `requirements.txt` already has.

## 6. Out of scope

- Real authentication. The gateway sets `X-Actor` and `X-Role`; this service trusts them.
- Rejecting, cancelling or expiring requests (there is no `rejected` status in v1).
- Persistence across restarts, notifications, and granting the access in the target tool.
- Detecting paid seats or sensitive data from the tool name beyond the lists in REQ-4.
- Parsing free text into a request (that is lesson 3's extractor, wired in later).

## 7. Open questions

- Should a `needs_security` request be visible to its requester only, or to everyone? (v1: everyone.)
- Should approvals expire after N days? (v1: no expiry; tracked for v2.)

## 8. Plan

- `impl/app.py`: `create_app()`, the FastAPI routes, and exception handlers that turn every error
  into the `Error` shape of the contract (including FastAPI's own validation errors, which must
  become 422 `validation_error`, not FastAPI's default body).
- `impl/routing.py`: `route_for(tool, access_level, flags) -> str`, pure (REQ-4).
- `impl/store.py`: an in-memory store with `add`, `get`, `list(status, limit)`, `update`.
- Pydantic models that mirror `NewAccessRequest`, `AccessRequest`, `AccessRequestList`, `Decision`
  with `extra="forbid"` on input models.
- Tests in `impl/tests/`, each marked with the requirement it checks: `@pytest.mark.req("REQ-4")`.
- Known trap: when GET and POST on one path are separate FastAPI routes, Starlette's default 405
  response lists only one route's methods in the `Allow` header. The contract test (NFR-2) checks
  `Allow`, so a 405 handler must list every method the path supports.
- Known trap: a body that cannot be decoded at all (for example invalid UTF-8) makes FastAPI
  answer 400 "There was an error parsing the body". The contract has no 400; REQ-2 makes it 422.

## 9. Tasks

- [ ] T1: Pydantic models and the error shape. (REQ-1, REQ-2)
- [ ] T2: `route_for` with a table-driven unit test for every rule in REQ-4. (REQ-4)
- [ ] T3: In-memory store and id generation. (REQ-1, REQ-6)
- [ ] T4: Header identity dependency. (REQ-3)
- [ ] T5: Create, list and get endpoints with initial status and audit records. (REQ-1, REQ-5, REQ-6, REQ-7, REQ-11)
- [ ] T6: Approve endpoint with checks in the order 404, 409, 403. (REQ-7, REQ-8, REQ-9, REQ-10, REQ-11)
- [ ] T7: Run `python labs/06-spec-driven/grade.py --app impl` until every requirement is green. (NFR-1, NFR-2)

## 10. Verification

`python labs/06-spec-driven/grade.py --app impl` runs the acceptance tests in `acceptance/` against
`impl/app.py`, the Schemathesis contract test, the traceability matrix, and the contract drift
check. The feature is done when every requirement is covered by at least one passing test and
the drift check reports nothing.
