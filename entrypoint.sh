#!/usr/bin/env sh

export DEEPFACE_GUNICORN_BIND="${DEEPFACE_GUNICORN_BIND:-0.0.0.0:5000}"
export DEEPFACE_GUNICORN_TIMEOUT="${DEEPFACE_GUNICORN_TIMEOUT:-7200}"
export DEEPFACE_GUNICORN_LOG_LEVEL="${DEEPFACE_GUNICORN_LOG_LEVEL:-debug}"

cd /app
exec python -m deepface.api.src.server_entrypoint "$@"
