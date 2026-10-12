FROM python:3.12.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_SYSTEM_PYTHON=1 \
    WEB_CONCURRENCY=2 WORKER_THREADS=40 PORT=8000

RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY data/curricula ./data/curricula
COPY run.sh ./

VOLUME ["/app/data"]
EXPOSE 8000
CMD ["./run.sh"]
