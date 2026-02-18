#!/bin/bash
# Create necessary directories
mkdir -p uploads
mkdir -p instance
mkdir -p static/dist

# Build Tailwind CSS for production
if command -v npm &> /dev/null
then
    echo "Building Tailwind CSS..."
    npm install
    npm run build:css
fi

# Start the application using UvicornWorker for FastAPI (ASGI)
# Using 1 worker and 4 threads to save memory on free instances (Fixes 502)
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 300 \
    --log-level info \
    --access-logfile - \
    --error-logfile -

