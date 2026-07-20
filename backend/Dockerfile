# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Caviar backend - production image (multi-stage).
#
# Stage 1 (builder): install dependencies into a virtualenv.
# Stage 2 (runtime): copy only the venv + app onto a slim base, run as a
# non-root user. The heavy optional [speech]/[tts] extras (faster-whisper,
# ctranslate2, kokoro) are NOT installed here: they pull large native/model
# payloads and are lazy-loaded at runtime only when interview audio is used.
# Deployments that need local STT/TTS build with --build-arg INSTALL_SPEECH=1.
# ---------------------------------------------------------------------------

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Create an isolated virtualenv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only dependency metadata first for better layer caching.
COPY pyproject.toml README.md ./
# Copy the package so the project itself installs (hatchling needs the tree).
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

ARG INSTALL_SPEECH=0
RUN pip install --upgrade pip && \
    if [ "$INSTALL_SPEECH" = "1" ]; then \
        pip install ".[speech,tts]"; \
    else \
        pip install .; \
    fi

# ---------------------------------------------------------------------------

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

# Non-root runtime user.
RUN groupadd --system caviar && useradd --system --gid caviar --home /app caviar

WORKDIR /app

# Copy the built virtualenv and the application source.
COPY --from=builder /opt/venv /opt/venv
COPY --chown=caviar:caviar app ./app
COPY --chown=caviar:caviar migrations ./migrations
COPY --chown=caviar:caviar alembic.ini ./

USER caviar

EXPOSE 8000

# Container-level liveness probe hitting the app's own health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else sys.exit(1)"

# Single worker by default; scale horizontally with more containers rather
# than in-process workers (the in-process rate limiter is per-process).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
