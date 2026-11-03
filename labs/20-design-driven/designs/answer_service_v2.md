# Design doc: Company Brain Answer Service v2

Author: platform team. Status: **in review**. Reviewers: you.

The doc is split into numbered sections, D1 to D12. In your review
(`designs/my_review.yaml`) you point at a section by its number.
Not every section has a problem.

---

**[D1] Context and goal.**
Company Brain answers employee questions over Acme's documents (HR policies,
the SaaS access policy) with citations. v1 is one 140-line function
(`legacy/tangled.py`). v2 splits it into a core service and adapters so we can
swap the model provider and move from keyword search to a vector store in Q1.
Traffic: about 2,000 questions a day, peak 5 per second. Target p95 latency 4 s.

**[D2] The model port.**
```python
class ChatModel(Protocol):
    def complete(self, system: str, prompt: str) -> anthropic.types.Message: ...
```
The service reads `message.content[0].text` and `message.usage.input_tokens`
directly, so we keep all the metadata Anthropic returns.

**[D3] The retriever port.**
```python
class Retriever(Protocol):
    def search(self, embedding: list[float], top_k: int, ef_search: int = 64) -> list[dict]: ...
```
The service embeds the question with `text-embedding-3-small` and passes the
vector in. `ef_search` lets the service tune HNSW recall per request.

**[D4] Failures and retries.**
The adapter wraps the SDK client, which retries 2 times by default. The service
also retries every failed `complete()` call 3 times with exponential backoff,
to be safe. Exceptions from the SDK propagate to the API layer, which returns
HTTP 500 with the exception message.

**[D5] Request flow.**
1. Receive the question. 2. Retrieve passages. 3. Call the model.
4. Run the policy check (salary questions, credentials, non-employees) on the
question and on the generated answer; if it fails, replace the answer with a
refusal. 5. Store and return.

**[D6] Storage and retries from clients.**
Each answer is inserted into the `answers` table with an auto-increment `id`,
which is returned to the client. The API gateway retries a request
automatically if the service does not answer within 5 s; mobile clients also
retry on network errors.

**[D7] Time and logging.**
The service receives a `Clock` in its constructor (`SystemClock` in production,
`FixedClock` in tests). Every log line carries `request_id`, status, latency
and cost; the question text and the answer are not logged.

**[D8] Prompts.**
The system prompt is a constant in `service.py`. When we improve it, we edit it
in place and deploy. Answers are cached for 24 hours, keyed by
`sha1(question)`.

**[D9] Response schema.**
v1 returns `{"text", "citations", "status"}`. In v2 we rename `citations` to
`sources` (a list of `{doc_id, title}` objects) because it reads better. The
Slack bot and the HR portal will update their parsers when they can.

**[D10] Store adapters.**
`AnswerStore` has `get(request_id)` and `put(answer) -> bool` (first write
wins). Two adapters: SQLite for local development, Postgres in production. Both
run the same contract test suite in CI.

**[D11] Test plan.**
The core service is tested end to end: a nightly CI job runs 40 golden
questions against the real Anthropic API and the staging vector store. Unit
tests are not needed for the service because it is mostly glue code.

**[D12] Rollout.**
v2 runs in shadow mode for one week: it receives a copy of the traffic, its
answers are stored but not shown, and we compare them with v1 on the golden
set before switching. Rollback is a config flag.
