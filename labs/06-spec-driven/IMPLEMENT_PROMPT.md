# Exercise 6: give the spec to Claude Code

Run from the repo root (`ai-engineer-course/`), in a **fresh** session, so the agent knows only
what the spec tells it. The deny rules keep its file tools away from the reference solution and,
in part A, from the acceptance tests. They are best effort: they cover Claude Code's file tools
and shell commands like `cat`, not a Python script that opens files itself. The prompt asks it
not to try.

## Part A: blind (the spec alone)

```bash
claude --disallowedTools \
  "Read(./labs/06-spec-driven/reference/**)" "Read(./labs/06-spec-driven/drift/**)" \
  "Read(./labs/06-spec-driven/fixtures/**)" "Read(./spectools/**)" \
  "Read(./labs/06-spec-driven/acceptance/**)" "Read(./labs/06-spec-driven/grade.py)" \
  "Edit(./labs/06-spec-driven/spec/**)"
```

Paste this prompt:

```text
Implement SPEC-006.

Read labs/06-spec-driven/spec/access-requests.spec.md and labs/06-spec-driven/spec/openapi.yaml.
They are the only source of truth. Follow section 8 (Plan) and work through the tasks in section 9.

Rules:
- Write code only under labs/06-spec-driven/impl/: app.py with create_app(), routing.py, store.py,
  and your tests in labs/06-spec-driven/impl/tests/.
- Mark every test with the requirement it checks: @pytest.mark.req("REQ-4"). A test may name
  several ids. Register the marker in impl/tests/conftest.py.
- Do not read or run anything in labs/06-spec-driven/reference/, drift/, fixtures/, acceptance/,
  grade.py or spectools/. Do not change anything in spec/. If the spec is ambiguous, choose the
  reading that is safer for security, write the decision in impl/DECISIONS.md, and go on.
- Before you finish, run: python -m pytest -q labs/06-spec-driven/impl/tests
  and show me the output. List which requirements your tests cover and which they do not.
```

When it says it is done, grade it yourself (the agent did not see these checks):

```bash
python labs/06-spec-driven/grade.py --app impl
```

Write down: how many requirements pass, which fail and why, how much drift the contract check
reports, and how many of the agent's tests carry a marker. Read impl/DECISIONS.md: which of its
decisions point at a real ambiguity in the spec?

## Part B: with the grader (closing the loop)

Same session, or a new one without the acceptance/grade deny rules:

```bash
claude --disallowedTools \
  "Read(./labs/06-spec-driven/reference/**)" "Read(./labs/06-spec-driven/drift/**)" \
  "Read(./labs/06-spec-driven/fixtures/**)" "Read(./spectools/**)" \
  "Edit(./labs/06-spec-driven/spec/**)" "Edit(./labs/06-spec-driven/acceptance/**)"
```

```text
Run python labs/06-spec-driven/grade.py --app impl and fix labs/06-spec-driven/impl/ until every
requirement that has tests is PASSING and the contract drift section says "none".
Do not edit spec/ or acceptance/. If a failing check looks wrong to you, stop and tell me why
instead of working around it. Show me the final grade output.
```

Compare A and B: what did the spec alone carry, and what did only the checks catch?
