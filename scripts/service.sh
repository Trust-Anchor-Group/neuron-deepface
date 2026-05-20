#!/usr/bin/env bash
cd ..

# run the service with flask - not for production purposes
# python api.py

# run the service with gunicorn - for prod purposes
export DEEPFACE_GUNICORN_BIND="${DEEPFACE_GUNICORN_BIND:-0.0.0.0:5005}"
export DEEPFACE_GUNICORN_TIMEOUT="${DEEPFACE_GUNICORN_TIMEOUT:-3600}"

exec python -m deepface.api.src.server_entrypoint "$@"