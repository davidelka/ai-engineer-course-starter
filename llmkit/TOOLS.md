# llmkit tool calling (lesson 14)

API reference for tool calling in llmkit, mockllm and `toolkit/`. Lessons 15 (agent loops),
16 (LangGraph workflows), 17 (MCP) and 18 (multi-agent) build on it. Wire shapes were checked
against the provider docs in November 2026 (sources at the end).

## Types (llmkit/types.py)

- `Tool(name, description, input_schema, strict=False, cache=None)`: a provider-neutral
  definition. `input_schema` is a JSON Schema object. Build one from a Pydantic model with
  `llmkit.tools.tool_from_model(Model, name=..., description=..., strict=True)`, which also checks
  that the name is portable (`^[a-zA-Z0-9_-]{1,64}$`) and that a description exists.
  `cache="5m"|"1h"` adds Anthropic `cache_control` after that tool definition.
- `ChatRequest.tools: list[Tool]`, `ChatRequest.tool_choice: None | "auto" | "any" | "none" | "<tool name>"`,
  `ChatRequest.parallel_tool_calls: None | bool` (False = at most one call per turn).
- `ToolCall(id, name, arguments: dict, raw_arguments: str, parse_error: str|None, signature: str|None)`.
  `arguments` is always a dict. Arguments that are not valid JSON give `arguments == {}` and a
  `parse_error`: nothing raises, so the executor can reply with an error result.
  `signature` holds Gemini's `thoughtSignature`.
- `ToolResult(call_id, content, is_error=False, name="")`. `content` is a str or anything
  JSON-serializable (sent as JSON text). `name` can stay empty: the Gemini adapter fills it from
  the matching ToolCall in the history.
- `Message.content` is still a plain `str` (unchanged) **or** a list of parts:
  `Block` (text, optional cache breakpoint), `ToolCall` (assistant turn), `ToolResult` (user turn).
  `Message.tool_calls` and `Message.tool_results` are properties.
  `Message.with_tool_results(results, text="")` builds the user turn that answers a tool turn.
  Put ALL results of one assistant turn in ONE message (parallel calls included).
- `Message.raw / raw_provider`: the provider's own output for an assistant turn. Sent back to
  the **same** provider, it is replayed verbatim. This keeps Anthropic thinking blocks, OpenAI
  reasoning items and Gemini thought signatures intact. Sent to another provider, the normalized
  parts are used instead.
- `ChatResult.tool_calls`, `ChatResult.raw_output`, and `ChatResult.message`, which is the
  assistant turn ready to append. It is a plain string when there are no tool calls, and parts
  plus raw when there are.
- `stop_reason == "tool_use"` on all three providers when the model asks for tools. OpenAI's
  "completed" and Gemini's "STOP" are mapped through llmkit markers (`raw_stop_reason` is
  `function_call` / `FUNCTION_CALL`).

## The round trip

```python
from llmkit import LLM, ChatRequest, Message
from toolkit import acme_registry, Executor

reg = acme_registry()
llm = LLM("anthropic:claude-haiku-5-5")
req = ChatRequest(messages=[Message("user", "Who approves a Figma editor seat for dana.levi@acme.example?")],
                  tools=reg.tools(strict=True))
run = Executor(reg)
for _ in range(5):                                   # always bound the rounds
    r = llm.complete(req)
    if not r.tool_calls:
        break
    req.messages.append(r.message)                   # assistant turn, as received
    req.messages.append(Message.with_tool_results(run(r.tool_calls)))
print(r.text)
```

`toolkit.run_tool_loop(llm, question, registry, max_rounds=5, executor=None, tool_choice=None)`
does exactly this and returns a `LoopResult` with `text`, `stop` ("answer" | "max_rounds" |
"refusal" | "max_tokens"), `rounds`, `calls`, `results`, `messages`, token counts and cost.
When `tool_choice` forces a tool, it falls back to "auto" after the first round, otherwise
the model could never answer.

## Provider mapping

- **Anthropic** (`/v1/messages`). `tools[] = {name, description, input_schema, strict?}`.
  `tool_choice = {"type": "auto"|"any"|"none"}` or `{"type": "tool", "name"}`, plus
  `disable_parallel_tool_use: true` INSIDE tool_choice. Calls arrive as `tool_use` blocks
  `{id, name, input}` with `stop_reason: "tool_use"`. Results go in the next user message as
  `tool_result` blocks `{tool_use_id, content, is_error?}`, which must come FIRST in that
  message (the adapter sorts them). Note: per the docs, `any`/`tool` return 400 on Opus 5.5 and
  Sonnet 5.5 (they are fine on Haiku 5.5).
- **OpenAI Responses** (`/v1/responses`). `tools[] = {type: "function", name, description,
  parameters, strict}` (strict is always sent explicitly). `tool_choice = "auto"|"required"|"none"`
  or `{"type": "function", "name"}`. `parallel_tool_calls` is a top-level bool. Calls are
  output items `{type: "function_call", id: "fc_...", call_id: "call_...", name, arguments: "<JSON string>"}`.
  Results are input items `{type: "function_call_output", call_id, output: "<string>"}`. There is
  no is_error field, so the adapter prefixes error text with `ERROR:`.
- **Gemini** (`generateContent`). `tools = [{functionDeclarations: [{name, description,
  parametersJsonSchema}]}]`. `toolConfig.functionCallingConfig.mode`: AUTO / ANY / NONE, and
  VALIDATED when any tool is strict. A specific tool = ANY plus `allowedFunctionNames: [name]`.
  There is no parallel switch. Calls are `functionCall` parts `{name, args, id?}`. The first one
  in a response carries `thoughtSignature`, which **must** be sent back (Gemini 3+ returns 400
  otherwise). Results are `functionResponse` parts `{name, response: {...}, id?}` in a user turn.
  The response must be an object: a dict is sent as is, other values as `{"result": v}`, errors as
  `{"error": v}`. When Gemini sends no id, llmkit makes a local one (`llmkit-local-N`) and never
  sends it back. A call that Gemini did not produce (cross-provider history) gets the documented
  dummy signature `skip_thought_signature_validator`.

Strict tools: each adapter sends `llmkit.schema.strict_schema(schema, provider)`, the same
transform `llmkit.structured.provider_schema` uses (additionalProperties false, every property
required, unsupported keywords moved into the description). Pydantic validation in the executor
still enforces everything.

## Streaming

`LLM.stream(req)` yields `StreamEvent`s of type `"text"`, `"tool_call_delta"` (`text` = a
fragment of the arguments JSON, `tool_call` = id and name so far), `"tool_call"` (one complete
ToolCall), and `"done"` (`result.tool_calls`, `result.raw_output`). All three providers are
supported:
- Anthropic: `content_block_start` (tool_use) + `input_json_delta` + `content_block_stop`.
- OpenAI: `response.output_item.added` + `response.function_call_arguments.delta` +
  `response.output_item.done`.
- Gemini: no argument deltas, because a functionCall arrives whole in one chunk.

`complete(req, stream=True)` collects a stream into the same ChatResult as a non-streaming call.

## mockllm

When a request has tools, the mock answers with provider-shaped calls. See mockllm/tools.py.
- Config / CLI: `tool_script` (JSON rules `{"match": regex, "calls": [{name, arguments}],
  "then": [[...round 2...]], "final": "...{results}..."}`; several calls = parallel),
  `tool_router` (keyword routing on name + description when no rule matches; default on),
  `tool_max_retries` (default 2), `tool_fault` = `invalid_args` | `unknown_tool` | `loop` |
  `bad_json` with `tool_fault_first` / `tool_fault_rate`, and `tool_injectable` (obeys
  instructions found inside tool results, like a naive model).
- After an `is_error` result it retries with corrected arguments. After good results it answers
  in text that names the tools and quotes the results.
- It returns real-API-like 400s: a missing or misplaced `tool_result` (Anthropic), a
  `function_call_output` with an unknown call_id (OpenAI), and a missing `thoughtSignature`
  (Gemini). Anthropic usage includes the tool system-prompt overhead (286 tokens for auto/none,
  406 for any/tool).

## toolkit (Acme tools)

- `acme_registry(db_path=None, requests_db=None)` provides six tools. Five are read-only over
  `data/acme/corpus/structured/acme.db`, which is opened read-only: `lookup_employee`,
  `get_system_info`, `list_access_grants`, `check_policy` (policy v2.2, matches all 300 recorded
  grants) and `read_document` (`untrusted_output=True`). One has a side effect:
  `create_access_request` (`side_effect=True`, idempotent by `idempotency_key`). It writes to
  `labs/14-tool-use/results/requests.db`, or to `$ACME_REQUESTS_DB`.
- `Registry` / `ToolSpec(name, description, input_model, fn, side_effect, untrusted_output,
  timeout_s, strict)` / `ToolError`. `registry.tools(names=None, strict=None)` returns the llmkit
  Tool list. `registry.subset([...])` gives least privilege. `with_descriptions(...)` is for A/B tests.
- `execute_tool(call, registry, timeout_s=5, confirmed=None)` never raises. Unknown tool, bad
  JSON, Pydantic errors, a missing confirmation, a ToolError, a crash and a timeout all become
  `ToolResult(is_error=True)` with text written for the model.
- `Executor(registry, confirmed=..., run=execute_tool)` runs read-only calls concurrently and
  side-effect calls sequentially, keeps result order, and records `trace`.
- `ConfirmationGate`: `approve(call)` issues a single-use token bound to the call's
  fingerprint, `check(call, token)` verifies it, and `confirmed` is the Executor hook. The model
  never sees tokens.
- `guards`: `spotlight(result)`, `scan(text)`, `output_violations(text)` and `Taint(registry)`,
  which blocks side-effect calls after untrusted text entered the context.

## Not done yet (for later lessons)

- Server tools (web_search, code execution), Anthropic tool search, `input_examples`, and
  OpenAI `allowed_tools`: use `extra_body` for now.
- Async: servekit/async_llm.py has no tool support.
- OpenAI `store=false` with reasoning models needs `include: ["reasoning.encrypted_content"]`
  for the raw replay to keep reasoning. llmkit uses the default (`store=true`).

Sources: platform.claude.com/docs/en/agents-and-tools/tool-use/{overview, implement-tool-use,
handle-tool-calls, parallel-tool-use, strict-tool-use}, platform.claude.com/docs/en/build-with-claude/streaming,
developers.openai.com/api/docs/guides/function-calling, ai.google.dev/api/generate-content,
ai.google.dev/api/caching (FunctionCallingConfig), ai.google.dev/gemini-api/docs/generate-content/thought-signatures.
