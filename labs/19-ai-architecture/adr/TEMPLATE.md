# ADR-0001: <short decision title, e.g. "Fixed workflow with LLM steps for access requests">

- Status: proposed
- Date: 2026-11-01
- Deciders: <who decides>
- Related: <links to other ADRs, specs, issues>

## Context and problem statement

<!-- 4-8 sentences. What problem, for whom, at what scale, under which constraints?
     Put the numbers here: requests/day, latency targets, budget, accuracy targets, what a mistake costs.
     End with the question this ADR answers, as one sentence. -->

## Decision drivers

<!-- At least 3 bullets. The forces that decide between the options, most important first.
     Good drivers are testable: "a wrong auto_approve is a security incident" beats "security is important". -->
- 
- 
- 

## Considered options

<!-- At least 2 options, each as a "### Option ..." heading. Describe every option FAIRLY:
     someone who prefers it should agree with your description. -->

### Option A: <name>

<!-- 2-4 sentences: how it works. -->
- Good, because 
- Bad, because 

### Option B: <name>

- Good, because 
- Bad, because 

## Decision outcome

Chosen option: "<Option A: name>", because <the reason, tied to the top drivers>.

<!-- Optional: what would make us revisit this decision (a trigger, e.g. "if more than 20% of requests
     do not fit the fixed steps"). -->

## Consequences

### Positive

- 

### Negative

<!-- Required. Every real decision has costs. If you cannot name one, you have not looked. -->
- 

## Cost and latency

<!-- Numbers for the chosen option, and for the main alternative if you have them.
     Cost per request and per month (USD), p95 latency per path (ms or s).
     Say where each number comes from: cost_model.py, a measurement, or an assumption. -->

## Confirmation

<!-- How we will know the decision was right, with thresholds:
     e.g. "routing accuracy >= 95% on the 120-request golden set; zero auto_approve on a needs_security request
     over 4 weeks; p95 <= 5 s". -->

## Diagram (optional)

<!-- Paste the Mermaid code from diagram.py inside a ```mermaid block; GitHub renders it. -->
