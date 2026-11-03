# syntax=docker/dockerfile:1
#
# Company Brain mini API: the production image of lesson 27.
#
# Build from the REPO ROOT (the image needs llmkit/ from there):
#   docker build -f labs/27-deployment/app/Dockerfile -t company-brain-api:dev .
# The build context is filtered by Dockerfile.dockerignore (next to this file), which
# takes precedence over a .dockerignore at the root of the context.
#
# Four stages:
#   builder   has uv; resolves the locked dependencies into /opt/venv. Never shipped.
#   runtime   slim Python + an unprivileged user. The common base of the next two.
#   mockllm   the free fake LLM server, for docker compose (target: mockllm)
#   api       the service itself. LAST, so it is what `docker build` produces by default.

############################ builder ############################
# Pinned by full version tag. For bit-for-bit reproducible builds, pin the digest too:
#   FROM python:3.12.16-slim-trixie@sha256:<digest>   (docker buildx imagetools inspect <image>)
FROM python:3.12.16-slim-trixie AS builder

# uv as a static binary from its official image, pinned. No pip, no curl | sh.
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

# UV_COMPILE_BYTECODE: compile .pyc now, so containers start faster.
# UV_LINK_MODE=copy: the cache is a separate mount, so hard links would fail.
# UV_PYTHON_DOWNLOADS=0: use the image's Python, never download another one.
# UV_PROJECT_ENVIRONMENT: build the venv at a fixed path we copy into the runtime stage.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /src
# Only the two dependency files are mounted here, so this layer is rebuilt only when
# the dependencies change, not on every code change. The cache mount keeps downloaded
# wheels between builds without putting them in any layer.
# --locked fails the build if uv.lock is out of date with pyproject.toml.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=labs/27-deployment/app/uv.lock,target=uv.lock \
    --mount=type=bind,source=labs/27-deployment/app/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

############################ runtime ############################
FROM python:3.12.16-slim-trixie AS runtime

# A system user with a fixed UID (10001): no password, no shell, no home directory.
# A fixed UID matters for file permissions on volumes and for Kubernetes runAsNonRoot.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

############################ mockllm ############################
FROM runtime AS mockllm
# Code is owned by root and only readable by the app user: the process cannot modify it.
COPY mockllm/ /app/mockllm/
USER app
EXPOSE 8765
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/__admin/stats', timeout=2)"]
CMD ["python", "-m", "mockllm", "--host", "0.0.0.0", "--port", "8765"]

############################ api (final) ############################
FROM runtime AS api
# Which commit is running? Pass --build-arg APP_VERSION=$(git rev-parse --short HEAD).
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="company-brain-mini" \
      org.opencontainers.image.description="Company Brain mini API (AI Engineer course, lesson 27)"

# Only the finished venv crosses over from the builder: no uv, no caches, no build tools.
COPY --from=builder /opt/venv /opt/venv
COPY llmkit/ /app/llmkit/
COPY labs/27-deployment/app/service/ /app/service/

# Configuration comes from the environment at RUN time. No keys here, ever.
ENV APP_VERSION=${APP_VERSION} \
    LLM_MODEL=auto

USER app
EXPOSE 8000
# Used by `docker run` and docker compose. ECS ignores it: the task definition has its own healthCheck.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
# Exec form: uvicorn is PID 1 and receives SIGTERM directly, so `docker stop` and ECS
# deployments shut it down gracefully instead of killing it after the timeout.
CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
