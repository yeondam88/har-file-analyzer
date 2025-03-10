FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev sqlite3 && \
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
    chmod 666 /app/data/.keep

# Create a non-root user
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /app/data

# Make the diagnostic script executable
RUN chmod +x /app/coolify.sh

# Create entrypoint script to handle permissions and startup
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Detect if running in Coolify based on environment variables\n\
if [ -n "$COOLIFY_SERVICE_ID" ] || [ -n "$COOLIFY_APP_ID" ]; then\n\
  echo "Detected Coolify environment"\n\
  export IN_COOLIFY=true\n\
else\n\
  export IN_COOLIFY=false\n\
fi\n\
\n\
# Ensure data directory has correct permissions at runtime\n\
mkdir -p /app/data\n\
chmod -R 777 /app/data\n\
\n\
# Explicitly create the database file if it doesn\'t exist and set permissions\n\
if [ ! -f /app/data/har_analyzer.db ]; then\n\
  echo "Creating database file..."\n\
  touch /app/data/har_analyzer.db\n\
  chmod 666 /app/data/har_analyzer.db\n\
  echo "Database file created with permissive permissions"\n\
fi\n\
\n\
# For Coolify environment, run a more intensive permission fix\n\
if [ "$IN_COOLIFY" = "true" ]; then\n\
  echo "Applying Coolify-specific fixes..."\n\
  # Ensure SQLite has write permission to the directory\n\
  chmod 777 /app/data\n\
  \n\
  # Try to initialize the database directly with sqlite3\n\
  echo "Testing direct SQLite access..."\n\
  sqlite3 /app/data/har_analyzer.db "CREATE TABLE IF NOT EXISTS startup_test (id INTEGER PRIMARY KEY);" || echo "SQLite direct access failed: $?"\n\
fi\n\
\n\
# Use the specified .env file for Coolify if it exists\n\
if [ -f .env.coolify ]; then\n\
  cp .env.coolify .env\n\
  echo "Using .env.coolify for configuration"\n\
elif [ "$IN_COOLIFY" = "true" ] && [ ! -f .env ]; then\n\
  echo "Creating .env file for Coolify environment"\n\
  echo "DATABASE_URL=sqlite:////app/data/har_analyzer.db" > .env\n\
  echo "SECRET_KEY=$SECRET_KEY" >> .env\n\
  echo "JWT_SECRET_KEY=$JWT_SECRET_KEY" >> .env\n\
  echo "DEBUG=False" >> .env\n\
  echo "IN_COOLIFY=true" >> .env\n\
fi\n\
\n\
# Run diagnostics if in Coolify environment or debug mode\n\
if [ "$IN_COOLIFY" = "true" ] || [ "$DEBUG" = "True" ]; then\n\
  echo "Running diagnostic tests..."\n\
  /app/coolify.sh\n\
fi\n\
\n\
# Debug info\n\
echo "Directory listing of /app/data:"\n\
ls -la /app/data\n\
echo "Current user and group:"\n\
id\n\
\n\
# If we\'re in Coolify, try first with the root user to eliminate permission issues\n\
if [ "$IN_COOLIFY" = "true" ] && [ "$(id -u)" != "0" ]; then\n\
  echo "In Coolify environment, trying to run with root privileges..."\n\
  exec gunicorn src.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}\n\
else\n\
  # Start the application with gunicorn\n\
  echo "Starting application with database URL from environment: $DATABASE_URL"\n\
  exec gunicorn src.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}\n\
fi\n\
' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Expose the port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000
ENV DATABASE_URL=sqlite:////app/data/har_analyzer.db
ENV PYTHONUNBUFFERED=1

# Run the application with the entrypoint script
# We're not setting a default user - the entrypoint will handle user switching if needed
ENTRYPOINT ["/app/entrypoint.sh"] 