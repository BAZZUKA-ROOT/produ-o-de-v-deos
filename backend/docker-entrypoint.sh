#!/bin/sh
set -e
case "$1" in
  api)
    python -m app.cli init
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${API_WORKERS:-2}" --proxy-headers --forwarded-allow-ips='*'
    ;;
  worker)
    exec celery -A app.workers.celery_app worker -Q default,render --concurrency "${WORKER_CONCURRENCY:-2}" --loglevel INFO
    ;;
  beat)
    exec celery -A app.workers.celery_app beat --loglevel INFO --schedule /data/tmp/celerybeat-schedule
    ;;
  *)
    exec "$@"
    ;;
esac
