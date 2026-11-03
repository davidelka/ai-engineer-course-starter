#!/usr/bin/env bash
# The same request as raw_http.py, in curl. Run from the repo root:
#   set -a; source .env; set +a; bash labs/02-llm-apis/curl_examples.sh anthropic
# -i prints response headers. -N disables buffering so the stream shows live.
set -euo pipefail
case "${1:-anthropic}" in
anthropic)
  curl -sS -i https://api.anthropic.com/v1/messages \
    -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d '{"model":"claude-haiku-5-5","max_tokens":200,"messages":[{"role":"user","content":"Name two colors."}]}' ;;
anthropic-stream)
  curl -sS -N https://api.anthropic.com/v1/messages \
    -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d '{"model":"claude-haiku-5-5","max_tokens":200,"stream":true,"messages":[{"role":"user","content":"Name two colors."}]}' ;;
openai)
  curl -sS -i https://api.openai.com/v1/responses \
    -H "Authorization: Bearer $OPENAI_API_KEY" -H "content-type: application/json" \
    -d '{"model":"gpt-5.4-mini","max_output_tokens":200,"input":"Name two colors."}' ;;
gemini)
  curl -sS -i "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" -H "content-type: application/json" \
    -d '{"contents":[{"parts":[{"text":"Name two colors."}]}]}' ;;
mock)
  curl -sS -N http://127.0.0.1:8765/v1/messages \
    -H "x-api-key: x" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d '{"model":"mock-model","max_tokens":200,"stream":true,"messages":[{"role":"user","content":"Name two colors."}]}' ;;
*) echo "usage: $0 anthropic|anthropic-stream|openai|gemini|mock"; exit 1 ;;
esac
echo
