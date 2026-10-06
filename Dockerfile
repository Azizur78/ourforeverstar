# ourforeverstar: single-service image for Render (React build + FastAPI on one origin).
#   docker build -t ourforeverstar --build-arg INSTAGRAM_URL=https://www.instagram.com/<handle>/ .
# Only INSTAGRAM_URL is consumed at build time (it is public by nature). Render passes every service env var as a
# build arg, but no secret is declared with ARG here, so no secret ends up in an image layer.

# ---------- 1. build the React app ----------
FROM node:22-alpine AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG INSTAGRAM_URL=""
ENV INSTAGRAM_URL=${INSTAGRAM_URL}
RUN npm run build

# ---------- 2. API + static files ----------
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /src/frontend/dist /app/frontend/dist

# Writable, but EPHEMERAL on Render Free (wiped on every restart/redeploy; see README "Render staging").
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/backend/data /app/backend/uploads \
    && chown -R appuser /app/backend/data /app/backend/uploads
USER appuser

ENV FRONTEND_DIST=/app/frontend/dist \
    DATABASE_URL=sqlite:////app/backend/data/forever_star.db \
    UPLOAD_DIR=/app/backend/uploads

EXPOSE 10000
# Single worker: the rate limiter and SQLite writer live in-process. Render injects $PORT (default 10000).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
