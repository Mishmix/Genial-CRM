FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /data

# Environment
ENV DATABASE_URL=sqlite:////data/crm.db
ENV PYTHONUNBUFFERED=1

# Railway uses PORT env variable
ENV PORT=8000
EXPOSE 8000

# Use shell form to expand $PORT variable
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
