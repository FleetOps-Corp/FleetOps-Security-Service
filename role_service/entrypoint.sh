#!/bin/sh
set -e
echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head
echo "[entrypoint] Starting Role Service on port ${ROLE_SERVICE_PORT:-8002}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${ROLE_SERVICE_PORT:-8002}" --workers 1 --ssl-certfile "${TLS_CERT_PATH}" --ssl-keyfile "${TLS_KEY_PATH}"
