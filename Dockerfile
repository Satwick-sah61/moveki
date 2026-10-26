# Stage 1: build the React front end.
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python API, which also serves the built front end.
FROM python:3.13-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY --from=web /web/dist ./frontend/dist

# Run as an unprivileged user; nothing in the image needs root at runtime.
RUN useradd --create-home --uid 10001 desk && chown -R desk:desk /srv
USER desk

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/health\")"

# PORT is honoured so the same image also runs on hosts that inject a port. `exec` makes
# uvicorn PID 1 so `docker stop` reaches it and it shuts down cleanly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
