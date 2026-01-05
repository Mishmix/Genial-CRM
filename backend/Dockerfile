FROM python:3.11-slim

WORKDIR /app

# Force rebuild - v2
RUN echo "rebuild trigger v2"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory for SQLite (fallback)
RUN mkdir -p /data

# Environment - DATABASE_URL will be set by Railway
ENV PYTHONUNBUFFERED=1

# Railway uses PORT env variable
ENV PORT=8000
EXPOSE 8000

# Use shell form to expand $PORT variable
# Increase request body limit to 100MB for large imports
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --limit-concurrency 100 --timeout-keep-alive 120
