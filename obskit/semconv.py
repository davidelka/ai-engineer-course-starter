"""Attribute names: the OpenTelemetry GenAI semantic conventions, plus obskit's own.

Source: github.com/open-telemetry/semantic-conventions-genai (docs/gen-ai/*.md), read on
2026-11-01. The GenAI conventions moved out of the main semantic-conventions repo into
that repo during 2026, and they are still marked **Development**: names can change. Two
examples of that, both relevant here:
  - gen_ai.system was replaced by gen_ai.provider.name.
  - gen_ai.usage.cache_creation.input_tokens was renamed to
    gen_ai.usage.cache_write.input_tokens (changelog.d/440.breaking.md). The Python
    package opentelemetry-semantic-conventions 0.66b2 still ships the OLD name.
That is why the names live in one module: when the spec moves, you change one file.

We define the strings ourselves instead of importing
opentelemetry.semconv._incubating (an underscore module, unstable by design).
"""

# ---------------------------------------------------------------- shared
OPERATION = "gen_ai.operation.name"          # chat | execute_tool | retrieval | invoke_agent | ...
PROVIDER = "gen_ai.provider.name"            # anthropic | openai | gcp.gemini | ...
CONVERSATION_ID = "gen_ai.conversation.id"
ERROR_TYPE = "error.type"                    # stable (general conventions)
SERVER_ADDRESS = "server.address"
SERVER_PORT = "server.port"

# ---------------------------------------------------------------- inference (span "chat {model}")
REQUEST_MODEL = "gen_ai.request.model"
REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
REQUEST_TEMPERATURE = "gen_ai.request.temperature"
REQUEST_STREAM = "gen_ai.request.stream"
REQUEST_REASONING = "gen_ai.request.reasoning.level"
OUTPUT_TYPE = "gen_ai.output.type"           # text | json
PROMPT_NAME = "gen_ai.prompt.name"
PROMPT_VERSION = "gen_ai.prompt.version"
RESPONSE_MODEL = "gen_ai.response.model"
RESPONSE_ID = "gen_ai.response.id"
FINISH_REASONS = "gen_ai.response.finish_reasons"
TIME_TO_FIRST_CHUNK = "gen_ai.response.time_to_first_chunk"   # seconds, streaming only
USAGE_INPUT = "gen_ai.usage.input_tokens"    # ALL input tokens, cached ones included
USAGE_OUTPUT = "gen_ai.usage.output_tokens"
USAGE_CACHE_READ = "gen_ai.usage.cache_read.input_tokens"
USAGE_CACHE_WRITE = "gen_ai.usage.cache_write.input_tokens"
USAGE_REASONING = "gen_ai.usage.reasoning.output_tokens"

# Content: Opt-In. Only recorded when content capture is enabled (see tracing.capture_mode).
SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"   # JSON string on spans
INPUT_MESSAGES = "gen_ai.input.messages"             # JSON string on spans
OUTPUT_MESSAGES = "gen_ai.output.messages"           # JSON string on spans

# ---------------------------------------------------------------- tools (span "execute_tool {name}")
TOOL_NAME = "gen_ai.tool.name"
TOOL_CALL_ID = "gen_ai.tool.call.id"
TOOL_TYPE = "gen_ai.tool.type"               # function | extension | datastore
TOOL_ARGUMENTS = "gen_ai.tool.call.arguments"  # Opt-In content
TOOL_RESULT = "gen_ai.tool.call.result"        # Opt-In content

# ---------------------------------------------------------------- retrieval (span "retrieval {data_source}")
DATA_SOURCE_ID = "gen_ai.data_source.id"
RETRIEVAL_TOP_K = "gen_ai.retrieval.top_k"
RETRIEVAL_QUERY = "gen_ai.retrieval.query.text"      # Opt-In content
RETRIEVAL_DOCUMENTS = "gen_ai.retrieval.documents"   # Opt-In; [{"id", "score"}] as JSON string

# ---------------------------------------------------------------- agents (span "invoke_agent {name}")
AGENT_NAME = "gen_ai.agent.name"
AGENT_ID = "gen_ai.agent.id"
WORKFLOW_NAME = "gen_ai.workflow.name"

# Well-known gen_ai.operation.name values
OP_CHAT = "chat"
OP_TOOL = "execute_tool"
OP_RETRIEVAL = "retrieval"
OP_EMBEDDINGS = "embeddings"
OP_AGENT = "invoke_agent"
OP_WORKFLOW = "invoke_workflow"

# llmkit provider name -> gen_ai.provider.name well-known value
PROVIDER_NAMES = {"anthropic": "anthropic", "openai": "openai", "gemini": "gcp.gemini"}

# llmkit normalized stop reason -> finish reason in the OpenAI-style vocabulary the
# conventions use in their examples ("stop", "length", "tool_call", "content_filter").
FINISH_REASON_MAP = {"end": "stop", "stop_sequence": "stop", "max_tokens": "length",
                     "tool_use": "tool_call", "refusal": "content_filter"}

# ---------------------------------------------------------------- obskit's own (not in the spec)
# Things the spec has no attribute for yet, but every LLM team records.
SPAN_TYPE = "obskit.span.type"        # llm | retrieval | tool | agent | cache | guard | other
COST_USD = "obskit.cost_usd"          # computed with llmkit.pricing at call time
ATTEMPTS = "obskit.attempts"          # llmkit retries: total attempts used
PARTIAL = "obskit.partial"            # a stream broke after text arrived
CACHE_HIT = "obskit.cache.hit"        # response cache (not the provider prompt cache)
FALLBACK = "obskit.fallback"          # this step used a fallback path (model, answer, ...)
INDEX_VERSION = "obskit.retrieval.index_version"
RETRIEVAL_RESULTS = "obskit.retrieval.results"   # richer than gen_ai.retrieval.documents: doc, date, version
GROUNDED = "obskit.grounded"          # an online groundedness check passed (lesson 23)
REPLAY_OF = "obskit.replay_of"        # trace id this span replays
REDACTED = "obskit.redacted"          # how many values the redaction processor changed

CONTENT_KEYS = (SYSTEM_INSTRUCTIONS, INPUT_MESSAGES, OUTPUT_MESSAGES, TOOL_ARGUMENTS, TOOL_RESULT,
                RETRIEVAL_QUERY, RETRIEVAL_DOCUMENTS, RETRIEVAL_RESULTS)

TYPE_BY_OPERATION = {OP_CHAT: "llm", "text_completion": "llm", "generate_content": "llm",
                     OP_TOOL: "tool", OP_RETRIEVAL: "retrieval", OP_EMBEDDINGS: "embeddings",
                     OP_AGENT: "agent", OP_WORKFLOW: "agent"}
