# syntax=docker/dockerfile:1

# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install && npm cache clean --force
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Python backend (uv for 10-100x faster installs)
FROM python:3.13-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip compile pyproject.toml -o /tmp/requirements.txt && \
    uv pip install --prefix=/install -r /tmp/requirements.txt

# Stage 3: Runtime
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r app && useradd -r -g app -m app

COPY --from=builder /install /usr/local
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

COPY alembic.ini .
COPY config/ config/
COPY alembic/ alembic/
COPY src/ src/

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.main"]
