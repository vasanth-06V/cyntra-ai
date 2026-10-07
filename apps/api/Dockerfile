FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

# Production dependencies only (not requirements-dev.txt).
COPY requirements.txt .
RUN pip install -r requirements.txt

# scripts/ rides along so the owner-run tools can be used from a shell if wanted.
COPY app ./app
COPY scripts ./scripts

USER appuser

# ONE worker, no --reload: the rate limiter, throttles, caches, job runner and
# sweepers all live in this process. Render sets $PORT.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
