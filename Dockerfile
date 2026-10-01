# ==========================================
# Stage 1: Build Frontend UI
# ==========================================
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-builder

WORKDIR /app/ui

# Copy package manifests and install dependencies
COPY ui/package.json ui/package-lock.json ./
RUN npm ci

# Copy UI source code and build
COPY ui/ ./
RUN npm run build

# ==========================================
# Stage 2: Python Backend Runtime
# ==========================================
FROM python:3.10-slim AS backend

WORKDIR /app

# Expose default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    AGY_API_KEY=sk-dummy \
    AGY_IS_API_CALL=1

# Install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (filtered by .dockerignore)
COPY . .

# Copy compiled frontend UI from Stage 1 into /app/ui/dist
COPY --from=frontend-builder /app/ui/dist ./ui/dist

# Expose default HTTP port
EXPOSE 8000

# Launch Uvicorn with dynamic HOST and PORT support and Unix signal trapping
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
