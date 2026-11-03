# Spec: Access-request API (first draft)

- **Spec id:** SPEC-006-draft
- **Status:** draft
- **Owner:** a hurried product manager

## 1. Intent

We want a simple API so employees can ask for access and the right people can approve.

## 3. Requirements

### REQ-1: Create requests
**Statement:** WHEN an employee submits a request, THE SYSTEM SHALL store it quickly and return it.
**Acceptance criteria:**
- AC-1.1: GIVEN a valid request WHEN it is posted THEN it is stored.

### Approving requests
**Statement:** WHEN a manager approves a request, THE SYSTEM SHALL mark it approved.
**Acceptance criteria:**
- AC-2.1: GIVEN a pending request WHEN a manager approves it THEN it is approved.

### REQ-3: Routing
**Statement:** THE SYSTEM SHALL route requests to the appropriate track according to the policy, etc.
**Acceptance criteria:**
- AC-3.1: Requests for admin access go to security.

### REQ-4: Errors
**Statement:** The system should handle invalid input gracefully.

### REQ-3: Listing
**Statement:** WHEN a user lists requests, THE SYSTEM SHALL return the relevant requests in a user-friendly order.
**Acceptance criteria:**
- AC-5.1: GIVEN some requests WHEN the user lists them THEN the results are shown as needed.

## 4. Non-functional requirements

### NFR-1: Performance
**Statement:** THE SYSTEM SHALL be fast and scalable.
**Acceptance criteria:**
- AC-N1.1: GIVEN normal load WHEN requests are sent THEN responses are fast.
