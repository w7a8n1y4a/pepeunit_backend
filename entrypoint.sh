#!/bin/bash

alembic upgrade head
gunicorn app.main:app \
    --bind 0.0.0.0:5000 \
    --log-level 'warning' \
    --access-logfile /dev/stdout \
    --error-logfile /dev/stderr \
    --timeout 300 \
    --workers=1 \
    --threads=2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --worker-tmp-dir=/dev/shm \
    --preload \
    --max-requests=1000 \
    --max-requests-jitter=100