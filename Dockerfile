FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies 
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache && \
    rm -rf /tmp/*

# Copy application code
COPY . .

# Create data directory for SQLite database with very permissive permissions
RUN mkdir -p /app/data && \
    chmod -R 777 /app/data && \
    touch /app/data/.keep && \
    chmod 666 /app/data/.keep && \
    ls -la /app/data

# Create a non-root user
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /app/data

# Create entrypoint script to handle permissions and startup
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Ensure data directory has correct permissions at runtime\n\
mkdir -p /app/data\n\
chmod -R 777 /app/data\n\
\n\
# Explicitly create the database file if it doesn\'t exist\n\
touch /app/data/har_analyzer.db\n\
chmod 666 /app/data/har_analyzer.db\n\
\n\
# Use the specified .env file for Coolify if it exists\n\
if [ -f .env.coolify ]; then\n\
  cp .env.coolify .env\n\
  echo "Using .env.coolify for configuration"\n\
fi\n\
\n\
# Start the application with gunicorn\n\
exec gunicorn src.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}\n\
' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000
ENV DATABASE_URL=sqlite:////app/data/har_analyzer.db
ENV PYTHONUNBUFFERED=1

# Run the application with the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"] 