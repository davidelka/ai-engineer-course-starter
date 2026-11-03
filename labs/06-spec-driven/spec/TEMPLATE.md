# Spec: <feature name>

<!--
How to use this template
- Copy it to spec/<feature>.spec.md and fill every section. Delete these comments.
- The linter (spec_lint.py) reads the format below, so keep the headings and markers:
    ### REQ-<n>: <title>         one functional requirement
    ### NFR-<n>: <title>         one non-functional requirement (must contain a number)
    **Statement:** ...           one sentence in EARS form, with SHALL
    **Acceptance criteria:**     followed by bullets "- AC-<n>.<m>: GIVEN ... WHEN ... THEN ..."
- EARS forms (pick one per statement):
    THE SYSTEM SHALL <response>                                 always true
    WHEN <trigger>, THE SYSTEM SHALL <response>                 event
    WHILE <state>, THE SYSTEM SHALL <response>                  state
    IF <unwanted condition>, THEN THE SYSTEM SHALL <response>   errors and abuse
    WHERE <feature is enabled>, THE SYSTEM SHALL <response>     optional feature
- Every acceptance criterion must be checkable by a test without asking anyone what it means.
  Words like "fast", "user-friendly", "appropriate", "etc." fail the linter.
- Every requirement needs at least one test marked @pytest.mark.req("REQ-<n>").
-->

- **Spec id:** SPEC-<nnn>
- **Status:** draft | in review | approved | superseded
- **Owner:** <name>, reviewed by: <names>
- **Version:** <x.y> (<date>)
- **Interface contract:** <path to openapi.yaml / JSON Schema / types file, or "none">

## 1. Intent

<Two short paragraphs: the problem, who has it, and what success looks like in observable terms.
This is the architectural intent the rest of the spec makes precise.>

## 2. Context

<What the reader must know that is not in the code: policies, existing systems, data shapes.
Summarize the source and give its path.>

## 3. Requirements

### REQ-1: <short title>
**Statement:** WHEN <trigger>, THE SYSTEM SHALL <observable response>.
**Acceptance criteria:**
- AC-1.1: GIVEN <state> WHEN <action> THEN <observable result>.
- AC-1.2: GIVEN <edge case> WHEN <action> THEN <observable result>.

### REQ-2: <short title>
**Statement:** IF <unwanted condition>, THEN THE SYSTEM SHALL <response>.
**Acceptance criteria:**
- AC-2.1: GIVEN ... WHEN ... THEN ...

## 4. Non-functional requirements

### NFR-1: <latency | cost | availability | security | privacy>
**Statement:** WHILE <load or state>, THE SYSTEM SHALL <measurable target with a number and a unit>.
**Acceptance criteria:**
- AC-N1.1: GIVEN <setup> WHEN <measurement> THEN <number> <unit>.

## 5. Constraints

<Language, framework, files and entry points, dependencies allowed, things that must not change.>

## 6. Out of scope

<What this spec deliberately does not cover. An agent fills silence with guesses; this list
removes the silence.>

## 7. Open questions

<Decisions not made yet, each with the default the implementation uses until it is decided.>

## 8. Plan

<Files, modules, interfaces, and how they connect. Enough for a reviewer to spot a wrong design
before any code exists.>

## 9. Tasks

- [ ] T1: <small, independently testable step>. (REQ-…)
- [ ] T2: ...

## 10. Verification

<One command that proves the feature works end to end, and what "done" means.>
