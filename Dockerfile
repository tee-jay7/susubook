# SusuBook production image.
#
# The same image runs the web service and the admin job (schema creation,
# seeding), so there is exactly one artefact to reason about and the job cannot
# drift from the service it maintains.
#
# Deployed to Cloud Run, which injects PORT and terminates TLS.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq is required by psycopg at runtime. Installed before the application
# layer so dependency changes do not invalidate this cache layer.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run unprivileged. Cloud Run does not require it, but a container that never
# needs root should never have it.
RUN useradd --create-home --uid 1000 susubook \
 && chown -R susubook:susubook /app
USER susubook

# Documentation only — Cloud Run injects the real value as $PORT.
EXPOSE 8080

# No --preload: each worker builds its own SQLAlchemy engine after fork.
# Preloading would create the engine once and share connection state across
# forked processes, which corrupts connections under load.
#
# 2 workers x 4 threads against Cloud Run's default concurrency of 80 is ample
# for this workload and fits comfortably in the default 512Mi.
CMD exec gunicorn \
    --bind ":${PORT:-8080}" \
    --workers 2 \
    --threads 4 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    "app:create_app()"
