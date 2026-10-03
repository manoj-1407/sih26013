# ─────────────────────────────────────────────────────────────────────────────
# GeoSamanvay — Multi-stage Docker build
#
# Stage 1 (builder): builds the React/TypeScript frontend
# Stage 2 (runtime): Python backend + copied frontend dist
#
# This ensures a clean clone + docker compose up just works —
# no pre-built frontend/dist needed in the repository.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Frontend build ───────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

COPY frontend/ ./
# vite.config.ts sets outDir: '../static'
# With WORKDIR=/frontend, '../static' resolves to /static inside the container
RUN npx vite build


# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Team Aikta — SIH26013 GeoSamanvay"
LABEL description="Evidence-Aware Multi-Source Geospatial Harmonization Engine"

# System-level geospatial dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev \
    libproj-dev \
    proj-data \
    proj-bin \
    libspatialindex-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (cached layer)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ /app/backend/

# Frontend dist from build stage → served as static files by FastAPI
# vite.config.ts outDir: '../static' → built to /static in the builder stage
COPY --from=frontend-builder /static /app/static/

# Demo data
COPY data/ /app/data/

# Runtime data directories
RUN mkdir -p /app/data/db /app/data/keys /app/data/evidence \
             /app/data/audit /app/data/exports /app/data/models

ENV PYTHONPATH=/app/backend
ENV GS_DATA_DIR=/app/data
ENV GS_DEMO_MODE=1
ENV GS_ENV=production

EXPOSE 8013

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8013/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8013", "--workers", "2"]
