FROM python:3.11-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY pyproject.toml poetry.lock* ./

# Install poetry, export requirements, then install them with pip
# All in one layer to avoid intermediate containers
RUN pip install --no-cache-dir poetry==1.5.1 && \
    poetry export -f requirements.txt --without-hashes -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn && \
    rm -rf /root/.cache && \
    rm -rf /tmp/*

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p /app/data && \
    chmod 777 /app/data

# Create a non-root user
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000

# Run the application with gunicorn
CMD ["gunicorn", "src.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"] 