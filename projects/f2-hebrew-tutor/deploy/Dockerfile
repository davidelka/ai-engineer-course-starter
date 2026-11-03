# syntax=docker/dockerfile:1
#
# The tutor API image. Built from the REPO ROOT, because it needs the course packages
# (llmkit, voicekit, ragkit, guardkit, obskit, evalkit, servekit):
#   docker build -f projects/f2-hebrew-tutor/deploy/Dockerfile -t hebrew-tutor:dev .
# Same structure as lesson 27: dependencies in a builder stage, a slim runtime with a fixed
# non-root UID, exec-form CMD. The default configuration is FREE (rule tutor, fake STT/TTS);
# real services are switched on with environment variables (compose.yaml, README milestone 10).
# Local Hebrew speech (faster-whisper + ivrit.ai, Piper) is NOT in this image: the model files
# are 1.6 GB; see README for the optional voice image.

############################ builder ############################
FROM python:3.12.16-slim-trixie AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY projects/f2-hebrew-tutor/deploy/requirements.lock /tmp/requirements.lock
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.lock

############################ runtime ############################
FROM python:3.12.16-slim-trixie AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="hebrew-tutor" \
      org.opencontainers.image.description="Spoken-Hebrew tutor API (AI Engineer course, project F2)"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app:/app/project \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    DB_PATH=/data/tutor.db \
    TRACES=/data/traces.jsonl \
    HOST=0.0.0.0 \
    PORT=8080
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# The course packages (read-only for the app user: owned by root).
COPY llmkit/ /app/llmkit/
COPY voicekit/ /app/voicekit/
COPY ragkit/ /app/ragkit/
COPY guardkit/ /app/guardkit/
COPY obskit/ /app/obskit/
COPY evalkit/ /app/evalkit/
COPY servekit/ /app/servekit/
COPY projects/f2-hebrew-tutor/hebtutor/ /app/project/hebtutor/
COPY projects/f2-hebrew-tutor/mine.py /app/project/mine.py
COPY projects/f2-hebrew-tutor/data/ /app/project/data/
RUN mkdir -p /data && chown -R app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
ENTRYPOINT ["python", "-m", "hebtutor"]
CMD ["serve"]
