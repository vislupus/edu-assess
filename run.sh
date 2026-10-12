#!/usr/bin/env bash
# Стартира платформата с няколко работни процеса (WEB_CONCURRENCY) и много нишки.
set -euo pipefail
cd "$(dirname "$0")"
export WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
export WORKER_THREADS="${WORKER_THREADS:-40}"
exec uv run uvicorn app.main:app \
  --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" \
  --workers "$WEB_CONCURRENCY" \
  --loop uvloop --http httptools \
  --timeout-keep-alive 15 --backlog 2048 \
  --proxy-headers --forwarded-allow-ips='*'
