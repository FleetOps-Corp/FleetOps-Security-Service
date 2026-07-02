# =============================================================================
# API Gateway — Dockerfile
# Multi-stage build (Rule R5): builder + runtime
# Runs as non-root user (Rule R5)
# SAD Reference: Security Layer container (pág. 5)
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies into a prefix directory
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create a non-root user and group (Rule R5: security best practice)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy only the application source (not tests, not build artifacts)
COPY app/ ./app/

# Set ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the port (actual value injected via ENV at runtime)
EXPOSE 8000

# Health check — consistent with docker-compose healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start the application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${GATEWAY_PORT:-8000} --workers 1 --ssl-certfile ${TLS_CERT_PATH} --ssl-keyfile ${TLS_KEY_PATH}"]
