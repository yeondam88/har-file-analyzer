FROM python:3.11-slim

WORKDIR /app

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install dependencies 
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache && \
    rm -rf /tmp/*

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p /app/data && \
    chmod -R 777 /app/data

# Create a non-root user
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000

# Run the application with gunicorn
CMD ["gunicorn", "src.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"] 