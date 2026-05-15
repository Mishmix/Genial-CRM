# Single-image build: bundle the React frontend into the FastAPI backend so
# Railway runs one service instead of two. Saves the entire marvelous-vitality
# replica (~$0.35/mo) without touching any feature.
#
# Stage 1: build the Vite/React SPA. The frontend talks to the backend via
# relative URLs (/api, /ws), so VITE_API_URL/VITE_WS_URL are baked in here.
FROM node:20-alpine AS frontend-builder
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_URL=/api
ENV VITE_WS_URL=/ws
RUN npm run build

# Stage 2: backend + bundled SPA. Layout in the final image:
#   /app/                      ← cwd, backend python code (was /backend in repo)
#   /app/app/main.py
#   /app/static/               ← frontend dist/ copied here
#   /app/static/index.html
#   /app/static/assets/        ← hashed JS/CSS bundles
#   /app/avatars/              ← user-uploaded avatars (created by app)
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-builder /fe/dist ./static

RUN mkdir -p /data avatars

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000

CMD python run_migrations.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --limit-concurrency 20 --timeout-keep-alive 120
