# Multi-stage build that bundles the React SPA into the FastAPI image so
# Railway can run a single service instead of two.
#
# Why this lives at /backend with frontend nested inside it:
# Railway's service config pins the build context to /backend (rootDirectory),
# which means a Dockerfile at /backend can only COPY from /backend/. We mirror
# the frontend source into /backend/frontend so it stays inside that context.
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
#   /app/                 ← cwd, backend python code
#   /app/app/main.py
#   /app/static/          ← frontend dist/ copied here
#   /app/static/index.html
#   /app/static/assets/
#   /app/avatars/
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source (excludes frontend/ via .dockerignore so we don't ship
# 200 MB of node_modules/source into the runtime image).
COPY . .

# Drop the bundled frontend source from the runtime image — only the built
# dist/ from stage 1 is needed at runtime.
RUN rm -rf /app/frontend

# Drop in the built SPA from stage 1.
COPY --from=frontend-builder /fe/dist ./static

RUN mkdir -p /data avatars

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
EXPOSE 8000

CMD python run_migrations.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --limit-concurrency 20 --timeout-keep-alive 120
