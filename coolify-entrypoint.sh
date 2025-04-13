#!/bin/bash
set -e

echo "=== HAR File Analyzer - Coolify Deployment ==="
echo "Starting entrypoint script at $(date)"

# Set environment flags
export IN_COOLIFY=true

# Create and set permissions for data directory
mkdir -p /app/data
chmod -R 777 /app/data

# Create database file if it doesn't exist
if [ ! -f /app/data/har_analyzer.db ]; then
  echo "Creating database file..."
  touch /app/data/har_analyzer.db
  chmod 666 /app/data/har_analyzer.db
  echo "Database file created with permissive permissions"
fi

# If CORS_ORIGINS isn't set, use a default that allows all
if [ -z "$CORS_ORIGINS" ]; then
  export CORS_ORIGINS='["*"]'
  echo "CORS_ORIGINS not set, allowing all origins"
fi

# If DATABASE_URL isn't set, use the default SQLite path
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL="sqlite:////app/data/har_analyzer.db"
  echo "DATABASE_URL not set, using default: $DATABASE_URL"
fi

# Print important environment variables
echo "=== Configuration ==="
echo "DATABASE_URL: $DATABASE_URL"
echo "CORS_ORIGINS: $CORS_ORIGINS"
echo "DEBUG: $DEBUG"
echo "IN_COOLIFY: $IN_COOLIFY"

# Directory listing for diagnostics
echo "=== Directory listing of /app/data ==="
ls -la /app/data

# Start the application with gunicorn
echo "Starting application..."
exec gunicorn src.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 120 --graceful-timeout 60 --keep-alive 5 --max-requests 200 --max-requests-jitter 20 