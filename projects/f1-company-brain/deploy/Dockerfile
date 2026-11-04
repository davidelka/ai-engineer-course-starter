# syntax=docker/dockerfile:1
#
# Company Brain image: the API + UI (default), the MCP server and the CLI (eval, seed) from one image.
# Built from the REPO ROOT, because it needs the course packages and the M1 project:
#   docker build -f projects/f1-company-brain/deploy/Dockerfile -t company-brain:dev .                       # BM25 + fake dense
#   docker build -f projects/f1-company-brain/deploy/Dockerfile --target runtime-e5 -t company-brain:e5 .    # + local e5-small
# Same structure as lesson 27 (labs/27-deployment/app/Dockerfile) and F3: uv-locked dependencies in a
# builder stage, a slim runtime with a fixed non-root UID, exec-form CMD, a HEALTHCHECK.
#
# Two runtime targets, one decision (ADR-0003): "runtime" retrieves with BM25 + the fake dense embedder
# (small image, ~250 MB, but cross-lingual questions suffer); "runtime-e5" adds PyTorch CPU and
# intfloat/multilingual-e5-small, downloaded at BUILD time, so a task never downloads 470 MB at start and
# confidential chunks are embedded inside the VPC (policy.yaml forbids sending them to OpenAI).

############################ builder ############################
FROM python:3.12.16-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 UV_NO_DEV=1 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=projects/f1-company-brain/deploy/uv.lock,target=uv.lock \
    --mount=type=bind,source=projects/f1-company-brain/deploy/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

############################ runtime ############################
FROM python:3.12.16-slim-trixie AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="company-brain" \
      org.opencontainers.image.description="Acme Company Brain (AI Engineer course, final project F1)"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app:/app/projects/f1-company-brain \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    STATE_DIR=/data/state \
    HOST=0.0.0.0 \
    PORT=8000
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# The course packages the brain imports (read-only for the app user: owned by root). Same paths as in
# the repo, so cbrain finds the repo root and the M1 project exactly as it does on your laptop.
COPY llmkit/ /app/llmkit/
COPY ragkit/ /app/ragkit/
COPY datakit/ /app/datakit/
COPY ctxkit/ /app/ctxkit/
COPY flowkit/ /app/flowkit/
COPY toolkit/ /app/toolkit/
COPY guardkit/ /app/guardkit/
COPY obskit/ /app/obskit/
COPY gatewaykit/ /app/gatewaykit/
COPY mcpkit/ /app/mcpkit/
COPY evalkit/ /app/evalkit/
COPY servekit/ /app/servekit/
COPY mockllm/ /app/mockllm/
COPY data/acme/corpus/docs/ /app/data/acme/corpus/docs/
COPY data/acme/corpus/golden/ /app/data/acme/corpus/golden/
COPY data/acme/corpus/structured/ /app/data/acme/corpus/structured/
COPY data/acme/saas_access_policy.md /app/data/acme/saas_access_policy.md
COPY labs/25-llm-gateway/policy.yaml /app/labs/25-llm-gateway/policy.yaml
COPY labs/16-workflows/data/ /app/labs/16-workflows/data/
COPY projects/m1-knowledge-assistant/acmeqa/ /app/projects/m1-knowledge-assistant/acmeqa/
COPY projects/m1-knowledge-assistant/data/ /app/projects/m1-knowledge-assistant/data/
COPY projects/f1-company-brain/cbrain/ /app/projects/f1-company-brain/cbrain/
COPY projects/f1-company-brain/data/ /app/projects/f1-company-brain/data/
COPY projects/f1-company-brain/arch/ /app/projects/f1-company-brain/arch/
COPY projects/f1-company-brain/mine.py /app/projects/f1-company-brain/mine.py
# State (checkpoints.db, requests.db, the index, traces) lives on a volume (compose) or EFS (ECS).
RUN mkdir -p /data/state && chown -R app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]
ENTRYPOINT ["python", "-m", "cbrain"]
CMD ["serve"]

############################ runtime-e5 ############################
# PyTorch CPU wheel from the PyTorch index (not PyPI's CUDA build, several GB), pinned; checked on PyPI
# 2026-11-02: torch 2.14.1 (2026-09-30), sentence-transformers 6.1.0 (2026-09-18).
FROM runtime AS runtime-e5
USER root
# uv is bind-mounted from its image for this one RUN only, so it never enters a layer. (A COPY of uv
# followed by `rm` in a later step would leave it in the COPY layer: deleting only adds a whiteout.)
RUN --mount=from=ghcr.io/astral-sh/uv:0.13.6,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --index-url https://download.pytorch.org/whl/cpu "torch==2.14.1" \
 && uv pip install --python /opt/venv/bin/python "sentence-transformers==6.1.0"
ENV HF_HOME=/opt/hf HF_HUB_OFFLINE=1 EMBEDDER=e5-small
RUN HF_HUB_OFFLINE=0 python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')" \
 && chmod -R a+rX /opt/hf
USER app
HEALTHCHECK --interval=30s --timeout=3s --start-period=180s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]
