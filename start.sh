#!/bin/bash
# Create necessary directories
mkdir -p uploads
mkdir -p instance

# Start the application using UvicornWorker for FastAPI (ASGI)
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
