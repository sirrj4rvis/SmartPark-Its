# syntax=docker/dockerfile:1
# ----- Stage 1: build wheels -----
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ----- Stage 2: runtime -----
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    PORT=5000

# Tesseract OCR engine for ANPR (license-plate recognition).
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security.
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=4s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','5000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz').status==200 else 1)"

# Shell form so $PORT (injected by Render/Heroku/etc.) is honored; defaults to 5000.
# gthread worker supports Flask-SocketIO (threading async mode) + normal HTTP.
CMD gunicorn --worker-class gthread --threads 8 -w 1 \
    --bind 0.0.0.0:${PORT:-5000} --access-logfile - wsgi:application
