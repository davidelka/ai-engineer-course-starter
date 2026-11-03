# syntax=docker/dockerfile:1
#
# The job agent image: the same image runs the scheduler (docker compose), one run per
# container (ECS scheduled task) and the admin API. Built from the REPO ROOT, because it
# needs the course packages (llmkit, obskit, guardkit, evalkit, servekit, deploykit):
#   docker build -f projects/f3-job-agent/deploy/Dockerfile -t job-agent:dev .
# Same structure as lesson 27 (labs/27-deployment/app/Dockerfile): uv-locked dependencies in
# a builder stage, a slim runtime with a fixed non-root UID, exec-form CMD.

############################ builder ############################
FROM python:3.12.16-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 UV_NO_DEV=1 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=projects/f3-job-agent/deploy/uv.lock,target=uv.lock \
    --mount=type=bind,source=projects/f3-job-agent/deploy/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

############################ runtime ############################
FROM python:3.12.16-slim-trixie AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="job-agent" \
      org.opencontainers.image.description="Job-alert agent, production edition (AI Engineer course, project F3)"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app:/app/project \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    JOB_AGENT_HOME=/app/project \
    STATE_PATH=/data/state/state.db \
    RESULTS_DIR=/data/results \
    TZ=Asia/Jerusalem
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# The course packages (read-only for the app user: owned by root).
COPY llmkit/ /app/llmkit/
COPY obskit/ /app/obskit/
COPY guardkit/ /app/guardkit/
COPY evalkit/ /app/evalkit/
COPY servekit/ /app/servekit/
COPY deploykit/ /app/deploykit/
COPY projects/f3-job-agent/jobagent/ /app/project/jobagent/
COPY projects/f3-job-agent/mine.py /app/project/mine.py
COPY projects/f3-job-agent/data/ /app/project/data/
# State and results live on a volume (compose) or in /data on the task's ephemeral disk (ECS).
RUN mkdir -p /data/state /data/results && chown -R app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os,sys; sys.exit(0 if os.path.isdir('/app/project/jobagent') else 1)"]
# Default: the long-running scheduler (08:30 / 15:00 / 21:00 Asia/Jerusalem).
# ECS overrides the command with ["python", "-m", "jobagent", "run", "--slot", "auto"].
ENTRYPOINT ["python", "-m", "jobagent"]
CMD ["schedule", "--run"]
