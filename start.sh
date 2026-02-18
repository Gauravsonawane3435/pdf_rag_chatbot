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
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
