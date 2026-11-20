# syntax=docker/dockerfile:1.6
# =============================================================================
# Smart Campus — single-deployable Dockerfile
# Multi-stage build:
#   1. frontend-build  : builds the React/Vite static assets
#   2. backend-deps    : installs Python dependencies
#   3. runtime         : FastAPI app + served static frontend
# On Render this same image is used by the Render Web Service.
# =============================================================================

# ---------- Stage 1: build frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
# Inline the backend origin so the SPA talks to the same origin in production.
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# ---------- Stage 2: backend dependencies ----------
FROM python:3.11-slim AS backend-deps
WORKDIR /app/backend
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY backend/requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ---------- Stage 3: runtime ----------
FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

# Runtime libs needed for psycopg/argon2 and image validation
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 libpq-dev curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy installed packages from deps stage
COPY --from=backend-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin

# Copy backend source
COPY backend/ ./backend/

# Copy compiled frontend into a directory FastAPI will mount as static
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Persistent local file storage mount point (Render Disk mounts here when configured)
RUN mkdir -p /app/storage/materials
VOLUME ["/app/storage"]

ENV PYTHONPATH=/app/backend \
    STORAGE_LOCAL_PATH=/app/storage/materials \
    FRONTEND_DIST_DIR=/app/frontend/dist

EXPOSE 8000

# Healthcheck hits the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

# Run migrations on container start, then launch uvicorn
CMD ["sh", "-c", "cd /app/backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
