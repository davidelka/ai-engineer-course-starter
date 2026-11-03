#!/usr/bin/env sh
# Writes .env with random keys (the values are not printed). Refuses to overwrite.
set -eu
cd "$(dirname "$0")"
if [ -f .env ]; then echo ".env exists; delete it first if you really want new keys"; exit 1; fi
umask 077
printf 'LITELLM_MASTER_KEY=sk-%s\nLITELLM_SALT_KEY=sk-%s\nPOSTGRES_PASSWORD=%s\n' \
  "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" "$(openssl rand -hex 12)" > .env
echo "wrote $(pwd)/.env (mode 600)"
