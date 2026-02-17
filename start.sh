#!/bin/bash
# Create necessary directories
mkdir -p uploads
mkdir -p instance

# Start the application
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --log-level info --access-logfile - --error-logfile -
