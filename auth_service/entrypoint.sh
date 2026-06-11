#!/bin/sh
# =============================================================================
# Auth Service — Entrypoint
# Runs Alembic migrations BEFORE starting the application.
# SAD Reference: "Alembic migrations" (pág. 5 diagram — Infrastructure layer)
# =============================================================================
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Starting Auth Service on port ${AUTH_SERVICE_PORT:-8001}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${AUTH_SERVICE_PORT:-8001}" --workers 1
